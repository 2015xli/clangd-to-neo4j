#!/usr/bin/env python3
"""
This module processes an in-memory collection of clangd symbols to create
the file, folder, and symbol nodes in a Neo4j graph.
"""
import os
import sys
import argparse
from pathlib import Path
from urllib.parse import urlparse, unquote
from typing import List, Dict, Any, Tuple, Optional
from neo4j import GraphDatabase
import logging
import gc

# New imports from the common parser module
from clangd_index_yaml_parser import SymbolParser, Symbol, Location

logger = logging.getLogger(__name__)

# -------------------------
# Constants
# -------------------------
BATCH_SIZE = 500

# -------------------------
# Neo4j connection settings
# -------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")

# --------------------------
# Helper classes (PathManager, Neo4jManager)
# -------------------------
class PathManager:
    """Manages file paths and their relationships within the project."""
    def __init__(self, project_path: str) -> None:
        self.project_path = str(Path(project_path).resolve())
        
    def uri_to_relative_path(self, uri: str) -> str:
        parsed = urlparse(uri)
        if parsed.scheme != 'file': return uri
        path = unquote(parsed.path)
        try:
            return str(Path(path).relative_to(self.project_path))
        except ValueError:
            return path

    def is_within_project(self, path: str) -> bool:
        try:
            Path(path).relative_to(self.project_path)
            return True
        except ValueError:
            return False

class Neo4jManager:
    """Manages Neo4j database operations."""
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD) -> None:
        self.uri, self.user, self.password = uri, user, password
        self.driver = None
        
    def __enter__(self):
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver: self.driver.close()
    
    def check_connection(self) -> bool:
        try:
            self.driver.verify_connectivity()
            logger.info("✅ Connection established!")
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
        
    def reset_database(self) -> None:
        with self.driver.session() as session:
            logger.info("Deleting existing data...")
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("Database cleared.")
    
    def create_constraints(self) -> None:
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:FILE) REQUIRE f.path IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:FOLDER) REQUIRE f.path IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (fn:FUNCTION) REQUIRE fn.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (ds:DATA_STRUCTURE) REQUIRE ds.id IS UNIQUE",
        ]
        with self.driver.session() as session:
            for constraint in constraints:
                session.run(constraint)
    
    def create_project_node(self, project_path: str) -> None:
        with self.driver.session() as session:
            session.run(
                "MERGE (p:PROJECT:FOLDER {path: $path}) SET p.name = $name",
                {"path": project_path, "name": Path(project_path).name or "Project"}
            )
    
    def process_batch(self, batch: List[Tuple[str, Dict]]) -> None:
        with self.driver.session() as session:
            with session.begin_transaction() as tx:
                for cypher, params in batch:
                    tx.run(cypher, **params)

    def cleanup_orphan_nodes(self) -> int:
        query = "MATCH (n) WHERE COUNT { (n)--() } = 0 DETACH DELETE n"
        with self.driver.session() as session:
            result = session.run(query)
            return result.consume().counters.nodes_deleted

# -------------------------
# Symbol processing
# -------------------------
class SymbolProcessor:
    """Processes Symbol objects and prepares data for Neo4j operations."""
    def __init__(self, path_manager: PathManager):
        self.path_manager = path_manager
    
    def process_symbol(self, sym: Symbol) -> Optional[Dict]:
        if not sym.id or not sym.kind:
            return None

        symbol_data = {
            "id": sym.id,
            "name": sym.name,
            "kind": sym.kind,
            "scope": sym.scope,
            "language": sym.language,
            "has_definition": sym.definition is not None,
        }

        if sym.kind == "Function":
            symbol_data.update({
                "signature": sym.signature,
                "return_type": sym.return_type,
                "type": sym.type,
            })
            primary_location = sym.definition or sym.declaration
            if primary_location:
                abs_file_path = unquote(urlparse(primary_location.file_uri).path)
                if self.path_manager.is_within_project(abs_file_path):
                    symbol_data["path"] = self.path_manager.uri_to_relative_path(primary_location.file_uri)
                else:
                    symbol_data["path"] = abs_file_path
                symbol_data["location"] = [primary_location.start_line, primary_location.start_column]
            
        # Add file relationship data if a definition exists within the project
        if sym.definition:
            abs_file_path = unquote(urlparse(sym.definition.file_uri).path)
            if self.path_manager.is_within_project(abs_file_path):
                symbol_data["file_path"] = self.path_manager.uri_to_relative_path(sym.definition.file_uri)
        
        return symbol_data

    def ingest_symbols_and_relationships(self, symbols: Dict[str, Symbol], neo4j_mgr: Neo4jManager, log_batch_size: int = 1000):
        symbol_data_list = []
        logger.info("Processing symbols for ingestion...")
        for i, sym in enumerate(symbols.values()):
            if (i + 1) % log_batch_size == 0:
                print(".", end="", flush=True)
            
            data = self.process_symbol(sym)
            if data:
                symbol_data_list.append(data)
        print(flush=True)
        
        if symbol_data_list:
            function_data_list = [d for d in symbol_data_list if d['kind'] == 'Function']
            data_structure_data_list = [d for d in symbol_data_list if d['kind'] in ('Struct', 'Class', 'Union', 'Enum')]

            if function_data_list:
                logger.info(f"Creating {len(function_data_list)} FUNCTION nodes using UNWIND...")
                function_merge_query = """
                UNWIND $function_data AS data
                MERGE (n:FUNCTION {id: data.id})
                ON CREATE SET n += data
                ON MATCH SET n += data
                """
                neo4j_mgr.process_batch([(function_merge_query, {"function_data": function_data_list})])
            
            if data_structure_data_list:
                logger.info(f"Creating {len(data_structure_data_list)} DATA_STRUCTURE nodes using UNWIND...")
                data_structure_merge_query = """
                UNWIND $data_structure_data AS data
                MERGE (n:DATA_STRUCTURE {id: data.id})
                ON CREATE SET n += data
                ON MATCH SET n += data
                """
                neo4j_mgr.process_batch([(data_structure_merge_query, {"data_structure_data": data_structure_data_list})])

            defines_data_list = [d for d in symbol_data_list if 'file_path' in d]
            if defines_data_list:
                logger.info(f"Creating {len(defines_data_list)} DEFINES relationships using UNWIND...")
                defines_rel_query = """
                UNWIND $defines_data AS data
                MATCH (f:FILE {path: data.file_path})
                MATCH (n {id: data.id})
                MERGE (f)-[:DEFINES]->(n)
                """
                neo4j_mgr.process_batch([(defines_rel_query, {"defines_data": defines_data_list})])

        del symbol_data_list, function_data_list, data_structure_data_list, defines_data_list
        gc.collect()
 
class PathProcessor:
    """Discovers and ingests file/folder structure into Neo4j."""
    def __init__(self, path_manager: PathManager, neo4j_mgr: Neo4jManager, log_batch_size: int = 1000):
        self.path_manager, self.neo4j_mgr, self.log_batch_size = path_manager, neo4j_mgr, log_batch_size

    def _discover_paths(self, symbols: Dict[str, Symbol]) -> Tuple[set, set]:
        project_files, project_folders = set(), set()
        logger.info("Discovering project file structure...")
        for i, sym in enumerate(symbols.values()):
            if (i + 1) % self.log_batch_size == 0:
                print(".", end="", flush=True)
            for loc in [sym.definition, sym.declaration]:
                if loc and urlparse(loc.file_uri).scheme == 'file':
                    abs_path = unquote(urlparse(loc.file_uri).path)
                    if self.path_manager.is_within_project(abs_path):
                        relative_path = self.path_manager.uri_to_relative_path(loc.file_uri)
                        project_files.add(relative_path)
                        parent = Path(relative_path).parent
                        while str(parent) != '.' and str(parent) != '/':
                            project_folders.add(str(parent))
                            parent = parent.parent
        print(flush=True)
        logger.info(f"Discovered {len(project_files)} files and {len(project_folders)} folders.")
        return project_files, project_folders

    def ingest_paths(self, symbols: Dict[str, Symbol]):
        project_files, project_folders = self._discover_paths(symbols)
        folder_data_list = []
        sorted_folders = sorted(list(project_folders), key=lambda p: len(Path(p).parts))
        for folder_path in sorted_folders:
            parent_path = str(Path(folder_path).parent)
            if parent_path == '.':
                folder_data_list.append({
                    "path": folder_path,
                    "name": Path(folder_path).name,
                    "parent_path": self.path_manager.project_path, # Use project_path as parent for root folders
                    "is_root": True
                })
            else:
                folder_data_list.append({
                    "path": folder_path,
                    "name": Path(folder_path).name,
                    "parent_path": parent_path,
                    "is_root": False
                })
        
        if folder_data_list:
            logger.info(f"Creating {len(folder_data_list)} folder nodes using UNWIND...")
            folder_merge_query = """
            UNWIND $folder_data AS data
            MERGE (f:FOLDER {path: data.path})
            ON CREATE SET f.name = data.name
            ON MATCH SET f.name = data.name
            """
            self.neo4j_mgr.process_batch([(folder_merge_query, {"folder_data": folder_data_list})])

            logger.info(f"Creating {len(folder_data_list)} folder relationships using UNWIND...")
            folder_rel_query = """
            UNWIND $folder_data AS data
            MATCH (child:FOLDER {path: data.path})
            WITH child, data
            MATCH (parent {path: data.parent_path}) // Match either PROJECT or FOLDER
            MERGE (parent)-[:CONTAINS]->(child)
            """
            self.neo4j_mgr.process_batch([(folder_rel_query, {"folder_data": folder_data_list})])
        
        del folder_data_list
        gc.collect()
        # B. Create Files using UNWIND
        file_data_list = []
        for file_path in project_files:
            parent_path = str(Path(file_path).parent)
            if parent_path == '.':
                file_data_list.append({
                    "path": file_path,
                    "name": Path(file_path).name,
                    "parent_path": self.path_manager.project_path, # Use project_path as parent for root files
                    "is_root": True
                })
            else:
                file_data_list.append({
                    "path": file_path,
                    "name": Path(file_path).name,
                    "parent_path": parent_path,
                    "is_root": False
                })
        
        if file_data_list:
            logger.info(f"Creating {len(file_data_list)} file nodes using UNWIND...")
            file_merge_query = """
            UNWIND $file_data AS data
            MERGE (f:FILE {path: data.path})
            ON CREATE SET f.name = data.name
            ON MATCH SET f.name = data.name
            """
            self.neo4j_mgr.process_batch([(file_merge_query, {"file_data": file_data_list})])

            logger.info(f"Creating {len(file_data_list)} file relationships using UNWIND...")
            file_rel_query = """
            UNWIND $file_data AS data
            MATCH (child:FILE {path: data.path})
            WITH child, data
            MATCH (parent {path: data.parent_path}) // Match either PROJECT or FOLDER
            MERGE (parent)-[:CONTAINS]->(child)
            """
            self.neo4j_mgr.process_batch([(file_rel_query, {"file_data": file_data_list})])
        
        del file_data_list
        del project_files, project_folders, sorted_folders
        gc.collect()

def main():
    parser = argparse.ArgumentParser(description='Import Clangd index into Neo4j')
    parser.add_argument('index_file', help='Path to the clangd index YAML file')
    parser.add_argument('project_path', help='Root path of the project')
    parser.add_argument('--log-batch-size', type=int, default=1000, help='Log progress every N items (default: 1000)')
    args = parser.parse_args()
    
    logger.info("Pass 0: Parsing clangd index file...")
    symbol_parser = SymbolParser(args.log_batch_size)
    symbol_parser.parse_yaml_file(args.index_file)
    
    path_manager = PathManager(args.project_path)
    with Neo4jManager() as neo4j_mgr:
        if not neo4j_mgr.check_connection(): return 1
        neo4j_mgr.reset_database()
        neo4j_mgr.create_project_node(path_manager.project_path)
        neo4j_mgr.create_constraints()
        
        path_processor = PathProcessor(path_manager, neo4j_mgr, args.log_batch_size)
        path_processor.ingest_paths(symbol_parser.symbols)

        logger.info("Pass 2: Processing symbols and relationships...")
        symbol_processor = SymbolProcessor(path_manager, neo4j_mgr)
        symbol_processor.ingest_symbols_and_relationships(symbol_parser.symbols, neo4j_mgr, args.log_batch_size)
        
        del symbol_processor
        gc.collect()
        
        logger.info(f"Done. Processed {len(symbol_parser.symbols)} symbols with {len(symbol_parser.symbols)} total operations.")
        return 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    sys.exit(main())
