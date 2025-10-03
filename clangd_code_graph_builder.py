#!/usr/bin/env python3
"""
Main entry point for the code graph ingestion pipeline.

This script orchestrates the different processors to build a complete code graph:
0. Parses the clangd YAML index into an in-memory object.
1. Ingests the code's file/folder structure.
2. Ingests symbol definitions (functions, structs, etc.).
3. Ingests the function call graph.
4. Cleans up orphan nodes.
"""

import argparse
import sys
import logging
import os
import tempfile
import gc

# Import processors from the library scripts
from clangd_symbol_nodes_builder import PathManager, PathProcessor, SymbolProcessor
from clangd_call_graph_builder import ClangdCallGraphExtractorWithContainer, ClangdCallGraphExtractorWithoutContainer
from clangd_index_yaml_parser import SymbolParser
from neo4j_manager import Neo4jManager # Import Neo4jManager
from utils import Debugger # Import Debugger

BATCH_SIZE = 500

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description='Build a code graph from a clangd index.')
    parser.add_argument('index_file', help='Path to the clangd index YAML file')
    parser.add_argument('project_path', help='Root path of the project being indexed')
    parser.add_argument('--nonstream-parsing', action='store_true',
                        help='Use non-streaming (two-pass) YAML parsing for SymbolParser')
    parser.add_argument('--log-batch-size', type=int, default=1000, help='Log progress every N items (default: 1000)')
    parser.add_argument('--ingest-batch-size', type=int, default=1000, help='Batch size for ingesting call relations (default: 1000).')
    parser.add_argument('--keep-orphans', action='store_true',
                      help='Keep orphan nodes in the graph (skip cleanup)')
    parser.add_argument('--debug-memory', action='store_true', help='Enable memory profiling with tracemalloc.')
    args = parser.parse_args()

    debugger = Debugger(turnon=args.debug_memory)

    # --- Pre-Phase: Sanitize the large YAML file --- 
    logger.info(f"Sanitizing input file: {args.index_file}")
    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8', errors='ignore') as temp_f:
            with open(args.index_file, 'r', errors='ignore') as f_in:
                for line in f_in:
                    temp_f.write(line.replace('\t', '  '))
            clean_yaml_path = temp_f.name
        logger.info(f"Sanitized YAML written to temporary file: {clean_yaml_path}")

        # --- Phase 0: Parse Clangd Index ---
        logger.info("\n--- Starting Phase 0: Parsing Clangd Index ---")
        symbol_parser = SymbolParser(args.log_batch_size, nonstream_parsing=args.nonstream_parsing, debugger=debugger)
        symbol_parser.parse_yaml_file(clean_yaml_path)

        # --- Main Processing --- 
        path_manager = PathManager(args.project_path)
        with Neo4jManager() as neo4j_mgr:
            if not neo4j_mgr.check_connection():
                return 1

            neo4j_mgr.reset_database()
            neo4j_mgr.create_project_node(path_manager.project_path)
            neo4j_mgr.create_constraints()

            # --- Phase 1: Ingest File & Folder Structure ---
            logger.info("\n--- Starting Phase 1: Ingesting File & Folder Structure ---")
            path_processor = PathProcessor(path_manager, neo4j_mgr, args.log_batch_size, args.ingest_batch_size)
            path_processor.ingest_paths(symbol_parser.symbols)
            del path_processor
            gc.collect()
            logger.info("--- Finished Phase 1 ---")

            # --- Phase 2: Ingest Symbol Definitions ---
            logger.info("\n--- Starting Phase 2: Ingesting Symbol Definitions ---")
            symbol_processor = SymbolProcessor(path_manager, args.log_batch_size, args.ingest_batch_size)
            symbol_processor.ingest_symbols_and_relationships(symbol_parser.symbols, neo4j_mgr)
            del symbol_processor
            gc.collect()
            logger.info("--- Finished Phase 2 ---")

            # --- Phase 3: Ingest Call Graph ---
            logger.info("\n--- Starting Phase 3: Ingesting Call Graph ---")
            
            if symbol_parser.has_container_field:
                extractor = ClangdCallGraphExtractorWithContainer(symbol_parser, args.log_batch_size, args.ingest_batch_size)
                logger.info("Using ClangdCallGraphExtractorWithContainer (new format detected).")
            else:
                extractor = ClangdCallGraphExtractorWithoutContainer(symbol_parser, args.log_batch_size, args.ingest_batch_size)
                logger.info("Using ClangdCallGraphExtractorWithoutContainer (old format detected).")
                # Load spans from project only if needed
                extractor.load_spans_from_project(args.project_path)
            
            call_relations = extractor.extract_call_relationships()
            
            # Use the new ingest_call_relations method for batched ingestion
            extractor.ingest_call_relations(call_relations, neo4j_manager=neo4j_mgr)
            
            del extractor # Deletes the extractor and its reference to symbol_parser
            gc.collect()
            
            del call_relations
            gc.collect()
            logger.info("Call graph ingestion complete.")
            logger.info("--- Finished Phase 3 ---")

            # --- Phase 4: Cleanup Orphan Nodes (Optional) ---
            if not args.keep_orphans:
                logger.info("\n--- Starting Phase 4: Cleaning up Orphan Nodes ---")
                deleted_nodes_count = neo4j_mgr.cleanup_orphan_nodes()
                logger.info(f"Removed {deleted_nodes_count} orphan nodes.")
                logger.info("--- Finished Phase 4 ---")
            else:
                logger.info("\n--- Skipping Phase 4: Keeping orphan nodes as requested ---")

        del symbol_parser
        del path_manager
        gc.collect()
        logger.info("\n✅ All passes complete. Code graph ingestion finished.")
        return 0

    finally:
        debugger.stop()
        # --- Cleanup ---
        if 'clean_yaml_path' in locals() and os.path.exists(clean_yaml_path):
            logger.info(f"Cleaning up temporary file: {clean_yaml_path}")
            os.remove(clean_yaml_path)

if __name__ == "__main__":
    sys.exit(main())