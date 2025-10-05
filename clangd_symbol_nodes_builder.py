#!/usr/bin/env python3
"""
This module processes an in-memory collection of clangd symbols to create
the file, folder, and symbol nodes in a Neo4j graph.
"""
import os
import sys
import argparse
import math
from pathlib import Path
from urllib.parse import urlparse, unquote
from typing import List, Dict, Any, Tuple, Optional
import logging
import gc

# New imports from the common parser module
from clangd_index_yaml_parser import SymbolParser, ParallelSymbolParser, Symbol, Location
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)

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

class SymbolProcessor:
    """Processes Symbol objects and prepares data for Neo4j operations."""
    def __init__(self, path_manager: PathManager, log_batch_size: int = 1000, ingest_batch_size: int = 1000, cypher_tx_size: int = 500):
        self.path_manager = path_manager
        self.ingest_batch_size = ingest_batch_size
        self.log_batch_size = log_batch_size
        self.cypher_tx_size = cypher_tx_size
    
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
            
        if sym.definition:
            abs_file_path = unquote(urlparse(sym.definition.file_uri).path)
            if self.path_manager.is_within_project(abs_file_path):
                symbol_data["file_path"] = self.path_manager.uri_to_relative_path(sym.definition.file_uri)
        
        return symbol_data

    def _process_and_filter_symbols(self, symbols: Dict[str, Symbol]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        symbol_data_list = []
        logger.info("Processing symbols for ingestion...")
        for i, sym in enumerate(symbols.values()):
            if (i + 1) % self.log_batch_size == 0:
                print(".", end="", flush=True)
            
            data = self.process_symbol(sym)
            if data:
                symbol_data_list.append(data)
        print(flush=True)
        
        function_data_list = [d for d in symbol_data_list if d['kind'] == 'Function']
        data_structure_data_list = [d for d in symbol_data_list if d['kind'] in ('Struct', 'Class', 'Union', 'Enum')]
        defines_data_list = [d for d in symbol_data_list if 'file_path' in d]

        del symbol_data_list
        gc.collect()

        return function_data_list, data_structure_data_list, defines_data_list

    def ingest_symbols_and_relationships(self, symbols: Dict[str, Symbol], neo4j_mgr: Neo4jManager):
        function_data_list, data_structure_data_list, defines_data_list = self._process_and_filter_symbols(symbols)

        self._ingest_function_nodes(function_data_list, neo4j_mgr)
        self._ingest_data_structure_nodes(data_structure_data_list, neo4j_mgr)
        self._ingest_defines_relationships(defines_data_list, neo4j_mgr)

        del function_data_list, data_structure_data_list, defines_data_list
        gc.collect()

    def _ingest_function_nodes(self, function_data_list: List[Dict], neo4j_mgr: Neo4jManager):
        if not function_data_list:
            return
        logger.info(f"Creating {len(function_data_list)} FUNCTION nodes in batches...")
        for i in range(0, len(function_data_list), self.ingest_batch_size):
            batch = function_data_list[i:i + self.ingest_batch_size]
            function_merge_query = """
            UNWIND $function_data AS data
            MERGE (n:FUNCTION {id: data.id})
            ON CREATE SET n += data
            ON MATCH SET n += data
            """
            neo4j_mgr.process_batch([(function_merge_query, {"function_data": batch})])
            print(".", end="", flush=True)
        print(flush=True)

    def _ingest_data_structure_nodes(self, data_structure_data_list: List[Dict], neo4j_mgr: Neo4jManager):
        if not data_structure_data_list:
            return
        logger.info(f"Creating {len(data_structure_data_list)} DATA_STRUCTURE nodes in batches...")
        for i in range(0, len(data_structure_data_list), self.ingest_batch_size):
            batch = data_structure_data_list[i:i + self.ingest_batch_size]
            data_structure_merge_query = """
            UNWIND $data_structure_data AS data
            MERGE (n:DATA_STRUCTURE {id: data.id})
            ON CREATE SET n += data
            ON MATCH SET n += data
            """
            neo4j_mgr.process_batch([(data_structure_merge_query, {"data_structure_data": batch})])
            print(".", end="", flush=True)
        print(flush=True)

    def _ingest_defines_relationships(self, defines_data_list: List[Dict], neo4j_mgr: Neo4jManager):
        if not defines_data_list:
            return
        logger.info(f"Creating {len(defines_data_list)} DEFINES relationships in batches...")
        for i in range(0, len(defines_data_list), self.ingest_batch_size):
            batch = defines_data_list[i:i + self.ingest_batch_size]
            # Use apoc.periodic.iterate for server-side parallelism
            # This requires the APOC plugin to be installed on the Neo4j server.
            defines_rel_query = """
            CALL apoc.periodic.iterate(
                "UNWIND $defines_data AS data RETURN data",
                "MATCH (f:FILE {path: data.file_path}) MATCH (n {id: data.id}) MERGE (f)-[:DEFINES]->(n)",
                {batchSize: $cypher_tx_size, parallel: true, params: {defines_data: $defines_data}}
            )
            """
            neo4j_mgr.execute_autocommit_query(
                defines_rel_query,
                {
                    "defines_data": batch,
                    "cypher_tx_size": self.cypher_tx_size
                }
            )
            print(".", end="", flush=True)
        print(flush=True)
 
class PathProcessor:
    """Discovers and ingests file/folder structure into Neo4j."""
    def __init__(self, path_manager: PathManager, neo4j_mgr: Neo4jManager, log_batch_size: int = 1000, ingest_batch_size: int = 1000):
        self.path_manager, self.neo4j_mgr, self.log_batch_size, self.ingest_batch_size = path_manager, neo4j_mgr, log_batch_size, ingest_batch_size

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
                    "parent_path": self.path_manager.project_path,
                    "is_root": True
                })
            else:
                folder_data_list.append({
                    "path": folder_path,
                    "name": Path(folder_path).name,
                    "parent_path": parent_path,
                    "is_root": False
                })
        
        self._ingest_folder_nodes_and_relationships(folder_data_list)
        del folder_data_list
        gc.collect()

        file_data_list = []
        for file_path in project_files:
            parent_path = str(Path(file_path).parent)
            if parent_path == '.':
                file_data_list.append({
                    "path": file_path,
                    "name": Path(file_path).name,
                    "parent_path": self.path_manager.project_path,
                    "is_root": True
                })
            else:
                file_data_list.append({
                    "path": file_path,
                    "name": Path(file_path).name,
                    "parent_path": parent_path,
                    "is_root": False
                })
        
        self._ingest_file_nodes_and_relationships(file_data_list)
        del file_data_list
        del project_files, project_folders, sorted_folders
        gc.collect()

    def _ingest_folder_nodes_and_relationships(self, folder_data_list: List[Dict]):
        if not folder_data_list:
            return
        logger.info(f"Creating {len(folder_data_list)} folder nodes and relationships in batches...")
        for i in range(0, len(folder_data_list), self.ingest_batch_size):
            batch = folder_data_list[i:i + self.ingest_batch_size]
            folder_merge_query = """
            UNWIND $folder_data AS data
            MERGE (f:FOLDER {path: data.path})
            ON CREATE SET f.name = data.name
            ON MATCH SET f.name = data.name
            """
            self.neo4j_mgr.process_batch([(folder_merge_query, {"folder_data": batch})])

            folder_rel_query = """
            UNWIND $folder_data AS data
            MATCH (child:FOLDER {path: data.path})
            WITH child, data
            MATCH (parent {path: data.parent_path})
            MERGE (parent)-[:CONTAINS]->(child)
            """
            self.neo4j_mgr.process_batch([(folder_rel_query, {"folder_data": batch})])
            print(".", end="", flush=True)
        print(flush=True)

    def _ingest_file_nodes_and_relationships(self, file_data_list: List[Dict]):
        if not file_data_list:
            return
        logger.info(f"Creating {len(file_data_list)} file nodes and relationships in batches...")
        for i in range(0, len(file_data_list), self.ingest_batch_size):
            batch = file_data_list[i:i + self.ingest_batch_size]
            file_merge_query = """
            UNWIND $file_data AS data
            MERGE (f:FILE {path: data.path})
            ON CREATE SET f.name = data.name
            ON MATCH SET f.name = data.name
            """
            self.neo4j_mgr.process_batch([(file_merge_query, {"file_data": batch})])

            file_rel_query = """
            UNWIND $file_data AS data
            MATCH (child:FILE {path: data.path})
            WITH child, data
            MATCH (parent {path: data.parent_path})
            MERGE (parent)-[:CONTAINS]->(child)
            """
            self.neo4j_mgr.process_batch([(file_rel_query, {"file_data": batch})])
            print(".", end="", flush=True)
        print(flush=True)

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    try:
        default_workers = math.ceil(os.cpu_count() / 2)
    except (NotImplementedError, TypeError):
        default_workers = 1

    parser = argparse.ArgumentParser(description='Import Clangd index symbols and file structure into Neo4j.')
    parser.add_argument('index_file', help='Path to the clangd index YAML file')
    parser.add_argument('project_path', help='Root path of the project')
    parser.add_argument('--log-batch-size', type=int, default=1000, help='Log progress every N items (default: 1000)')
    parser.add_argument('--ingest-batch-size', type=int, default=1000, help='Batch size for ingesting nodes and relationships (default: 1000).')
    parser.add_argument('--cypher-tx-size', type=int, default=500, help='Batch size for server-side Cypher transactions (default: 500).')
    parser.add_argument('--num-parse-workers', type=int, default=default_workers,
                        help=f'Number of parallel workers for parsing. Set to 1 for single-threaded mode. (default: {default_workers})')
    args = parser.parse_args()
    
    # --- Phase 0: Load, Parse, and Link Symbols ---
    logger.info("\n--- Starting Phase 0: Loading, Parsing, and Linking Symbols ---")

    if args.num_parse_workers > 1:
        logger.info(f"Using ParallelSymbolParser with {args.num_parse_workers} workers.")
        symbol_parser = ParallelSymbolParser(
            index_file_path=args.index_file,
            log_batch_size=args.log_batch_size
        )
        symbol_parser.parse(num_workers=args.num_parse_workers)
    else:
        logger.info("Using standard SymbolParser in single-threaded mode.")
        symbol_parser = SymbolParser(log_batch_size=args.log_batch_size)
        symbol_parser.parse_yaml_file(args.index_file)

    symbol_parser.build_cross_references()
    logger.info("--- Finished Phase 0 ---")
    
    path_manager = PathManager(args.project_path)
    with Neo4jManager() as neo4j_mgr:
        if not neo4j_mgr.check_connection(): return 1
        neo4j_mgr.reset_database()
        neo4j_mgr.create_project_node(path_manager.project_path)
        neo4j_mgr.create_constraints()
        
        logger.info("\n--- Starting Phase 1: Ingesting File & Folder Structure ---")
        path_processor = PathProcessor(path_manager, neo4j_mgr, args.log_batch_size, args.ingest_batch_size)
        path_processor.ingest_paths(symbol_parser.symbols)
        del path_processor
        gc.collect()
        logger.info("--- Finished Phase 1 ---")

        logger.info("\n--- Starting Phase 2: Ingesting Symbol Definitions ---")
        symbol_processor = SymbolProcessor(
            path_manager,
            log_batch_size=args.log_batch_size,
            ingest_batch_size=args.ingest_batch_size,
            cypher_tx_size=args.cypher_tx_size
        )
        symbol_processor.ingest_symbols_and_relationships(symbol_parser.symbols, neo4j_mgr)
        
        del symbol_processor
        gc.collect()
        
        logger.info(f"\n✅ Done. Processed {len(symbol_parser.symbols)} symbols.")
        return 0

if __name__ == "__main__":
    sys.exit(main())