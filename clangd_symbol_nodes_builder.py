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
from clangd_index_symbol_parser import SymbolParser, Symbol, Location

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
    """Processes Symbol objects and generates Neo4j operations."""
    def __init__(self, path_manager: PathManager):
        self.path_manager = path_manager
    
    def process_symbol(self, sym: Symbol) -> List[Tuple[str, Dict]]:
        ops = []
        if not sym.id or not sym.kind:
            return []

        if sym.kind == "Function":
            ops.extend(self._process_function(sym))
        elif sym.kind in ("Struct", "Class", "Union", "Enum"):
            ops.extend(self._process_data_structure(sym))

        ops.extend(self._process_file_relationships(sym))
        return ops
    
    def _process_node(self, sym: Symbol, label: str) -> List[Tuple[str, Dict]]:
        props = {"id": sym.id, "name": sym.name, "scope": sym.scope, "language": sym.language}
        return [(f"MERGE (n:{label} {{id: $id}}) SET n += $props", {"id": sym.id, "props": props})]
    
    def _process_function(self, sym: Symbol) -> List[Tuple[str, Dict]]:
        ops = self._process_node(sym, "FUNCTION")
        props = ops[0][1]["props"]
        props.update({
            "signature": sym.signature, "return_type": sym.return_type,
            "type": sym.type, "has_definition": sym.definition is not None
        })
        primary_location = sym.definition or sym.declaration
        if primary_location:
            abs_file_path = unquote(urlparse(primary_location.file_uri).path)
            if self.path_manager.is_within_project(abs_file_path):
                props["path"] = self.path_manager.uri_to_relative_path(primary_location.file_uri)
            else:
                props["path"] = abs_file_path
            props["location"] = [primary_location.start_line, primary_location.start_column]
        return ops
    
    def _process_data_structure(self, sym: Symbol) -> List[Tuple[str, Dict]]:
        ops = self._process_node(sym, "DATA_STRUCTURE")
        ops[0][1]["props"].update({"kind": sym.kind, "has_definition": sym.definition is not None})
        return ops
    
    def _process_file_relationships(self, sym: Symbol) -> List[Tuple[str, Dict]]:
        if not sym.definition:
            return []
        abs_file_path = unquote(urlparse(sym.definition.file_uri).path)
        if not self.path_manager.is_within_project(abs_file_path):
            return []
        file_path = self.path_manager.uri_to_relative_path(sym.definition.file_uri)
        if sym.kind in ["Function", "Struct", "Class", "Union", "Enum"]:
            label = "FUNCTION" if sym.kind == "Function" else "DATA_STRUCTURE"
            return [(f"MATCH (f:FILE {{path: $file_path}}), (n:{label} {{id: $node_id}}) MERGE (f)-[:DEFINES]->(n)",
                     {"file_path": file_path, "node_id": sym.id})]
        return []

class PathProcessor:
    """Discovers and ingests file/folder structure into Neo4j."""
    def __init__(self, path_manager: PathManager, neo4j_mgr: Neo4jManager, log_batch_size: int = 1000):
        self.path_manager, self.neo4j_mgr, self.log_batch_size = path_manager, neo4j_mgr, log_batch_size

    def _discover_paths(self, symbols: Dict[str, Symbol]) -> Tuple[set, set]:
        project_files, project_folders = set(), set()
        logger.info("Pass 1: Discovering project file structure...")
        for i, sym in enumerate(symbols.values()):
            if (i + 1) % self.log_batch_size == 0:
                logger.info(f"Discovered paths from {i + 1} symbols...")
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
        logger.info(f"Discovered {len(project_files)} files and {len(project_folders)} folders.")
        return project_files, project_folders

    def ingest_paths(self, symbols: Dict[str, Symbol]):
        project_files, project_folders = self._discover_paths(symbols)
        batch = []
        sorted_folders = sorted(list(project_folders), key=lambda p: len(Path(p).parts))
        for folder_path in sorted_folders:
            parent_path = str(Path(folder_path).parent)
            cypher, params = ("MATCH (p:PROJECT {path: $proj}) MERGE (f:FOLDER {path: $path}) SET f.name = $name MERGE (p)-[:CONTAINS]->(f)",
                              {"proj": self.path_manager.project_path, "path": folder_path, "name": Path(folder_path).name})
            if parent_path != '.':
                cypher, params = ("MERGE (c:FOLDER {path: $path}) SET c.name = $name WITH c MATCH (p:FOLDER {path: $parent}) MERGE (p)-[:CONTAINS]->(c)",
                                  {"path": folder_path, "name": Path(folder_path).name, "parent": parent_path})
            batch.append((cypher, params))
        if batch: self.neo4j_mgr.process_batch(batch); batch = []
        for file_path in project_files:
            parent_path = str(Path(file_path).parent)
            cypher, params = ("MATCH (p:PROJECT {path: $proj}) MERGE (f:FILE {path: $path}) SET f.name = $name MERGE (p)-[:CONTAINS]->(f)",
                              {"proj": self.path_manager.project_path, "path": file_path, "name": Path(file_path).name})
            if parent_path != '.':
                cypher, params = ("MATCH (p:FOLDER {path: $parent}) MERGE (f:FILE {path: $path}) SET f.name = $name MERGE (p)-[:CONTAINS]->(f)",
                                  {"parent": parent_path, "path": file_path, "name": Path(file_path).name})
            batch.append((cypher, params))
        if batch: self.neo4j_mgr.process_batch(batch)
        del project_files, project_folders, sorted_folders, batch; gc.collect()

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
        symbol_processor = SymbolProcessor(path_manager)
        batch, count = [], 0
        for i, sym in enumerate(symbol_parser.symbols.values()):
            if (i + 1) % BATCH_SIZE == 0: logger.info(f"Processed {i + 1} symbols...")
            batch.extend(symbol_processor.process_symbol(sym))
            if len(batch) >= BATCH_SIZE:
                neo4j_mgr.process_batch(batch)
                count += len(batch)
                logger.info(f"Committed {count} total operations...")
                batch = []
        if batch: neo4j_mgr.process_batch(batch); count += len(batch)
        del batch, symbol_processor, symbol_parser; gc.collect()
        logger.info(f"Done. Processed {len(symbol_parser.symbols)} symbols with {count} total operations.")
        return 0

if __name__ == "__main__":
    sys.exit(main())