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
import gc
import math

# Import processors and managers from the library scripts
from clangd_symbol_nodes_builder import PathManager, PathProcessor, SymbolProcessor
from clangd_call_graph_builder import ClangdCallGraphExtractorWithContainer, ClangdCallGraphExtractorWithoutContainer
from clangd_index_yaml_parser import SymbolParser, ParallelSymbolParser
from neo4j_manager import Neo4jManager
from utils import Debugger


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    try:
        default_workers = math.ceil(os.cpu_count() / 2)
    except (NotImplementedError, TypeError):
        default_workers = 1

    parser = argparse.ArgumentParser(description='Build a code graph from a clangd index.')
    parser.add_argument('index_file', help='Path to the clangd index YAML file')
    parser.add_argument('project_path', help='Root path of the project being indexed')
    parser.add_argument('--num-parse-workers', type=int, default=default_workers,
                        help=f'Number of parallel workers for parsing. Set to 1 for single-threaded mode. (default: {default_workers})')
    parser.add_argument('--log-batch-size', type=int, default=1000, help='Log progress every N items (default: 1000)')
    parser.add_argument('--cypher-tx-size', type=int, default=2000, 
                        help='Target items (nodes/relationships) per server-side transaction (default: 2000).')
    parser.add_argument('--ingest-batch-size', type=int, default=None, 
                        help='Target items (nodes/relationships) per client submission. Default: (cypher-tx-size * num-parse-workers). Controls progress indicator and parallelism.')
    parser.add_argument('--idempotent-merge', action='store_true', help='Use slower, idempotent MERGE for relationships. Default is fast, non-idempotent CREATE.')
    parser.add_argument('--keep-orphans', action='store_true',
                      help='Keep orphan nodes in the graph (skip cleanup)')
    parser.add_argument('--debug-memory', action='store_true', help='Enable memory profiling with tracemalloc.')
    args = parser.parse_args()

    # Set default for ingest_batch_size if not provided
    if args.ingest_batch_size is None:
        args.ingest_batch_size = args.cypher_tx_size * args.num_parse_workers

    debugger = Debugger(turnon=args.debug_memory)

    try:
        # --- Phase 0: Load, Parse, and Link Symbols ---
        logger.info("\n--- Starting Phase 0: Loading, Parsing, and Linking Symbols ---")

        if args.num_parse_workers > 1:
            logger.info(f"Using ParallelSymbolParser with {args.num_parse_workers} workers.")
            symbol_parser = ParallelSymbolParser(
                index_file_path=args.index_file,
                log_batch_size=args.log_batch_size,
                debugger=debugger
            )
            symbol_parser.parse(num_workers=args.num_parse_workers)
        else:
            logger.info("Using standard SymbolParser in single-threaded mode.")
            symbol_parser = SymbolParser(log_batch_size=args.log_batch_size, debugger=debugger)
            symbol_parser.parse_yaml_file(args.index_file)

        # Phase 0.5: Link all parsed data
        symbol_parser.build_cross_references()
        logger.info("--- Finished Phase 0 ---")

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
            symbol_processor = SymbolProcessor(
                path_manager,
                log_batch_size=args.log_batch_size,
                ingest_batch_size=args.ingest_batch_size,
                cypher_tx_size=args.cypher_tx_size
            )
            symbol_processor.ingest_symbols_and_relationships(symbol_parser.symbols, neo4j_mgr, args.idempotent_merge)
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
                extractor.load_spans_from_project(args.project_path)
            
            call_relations = extractor.extract_call_relationships()
            extractor.ingest_call_relations(call_relations, neo4j_manager=neo4j_mgr)
            
            del extractor, call_relations
            gc.collect()
            logger.info("--- Finished Phase 3 ---")

            # --- Phase 4: Cleanup Orphan Nodes (Optional) ---
            if not args.keep_orphans:
                logger.info("\n--- Starting Phase 4: Cleaning up Orphan Nodes ---")
                deleted_nodes_count = neo4j_mgr.cleanup_orphan_nodes()
                logger.info(f"Removed {deleted_nodes_count} orphan nodes.")
                logger.info("--- Finished Phase 4 ---")
            else:
                logger.info("\n--- Skipping Phase 4: Keeping orphan nodes as requested ---")

        del symbol_parser, path_manager
        gc.collect()
        logger.info("\n✅ All passes complete. Code graph ingestion finished.")
        return 0

    finally:
        debugger.stop()

if __name__ == "__main__":
    sys.exit(main())