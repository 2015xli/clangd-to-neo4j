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
from clangd_symbol_nodes_builder import PathManager, Neo4jManager, PathProcessor, SymbolProcessor
from clangd_call_graph_builder import ClangdCallGraphExtractorWithContainer, ClangdCallGraphExtractorWithoutContainer
from clangd_index_yaml_parser import SymbolParser

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
    parser.add_argument('--keep-orphans', action='store_true',
                      help='Keep orphan nodes in the graph (skip cleanup)')
    args = parser.parse_args()

    # --- Pre-Pass: Sanitize the large YAML file --- 
    logger.info(f"Sanitizing input file: {args.index_file}")
    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8', errors='ignore') as temp_f:
            with open(args.index_file, 'r', errors='ignore') as f_in:
                for line in f_in:
                    temp_f.write(line.replace('\t', '  '))
            clean_yaml_path = temp_f.name
        logger.info(f"Sanitized YAML written to temporary file: {clean_yaml_path}")

        # --- Pass 0: Parse Clangd Index ---
        logger.info("\n--- Starting Pass 0: Parsing Clangd Index ---")
        symbol_parser = SymbolParser(args.log_batch_size, nonstream_parsing=args.nonstream_parsing)
        symbol_parser.parse_yaml_file(clean_yaml_path)

        # --- Main Processing --- 
        path_manager = PathManager(args.project_path)
        with Neo4jManager() as neo4j_mgr:
            if not neo4j_mgr.check_connection():
                return 1

            neo4j_mgr.reset_database()
            neo4j_mgr.create_project_node(path_manager.project_path)
            neo4j_mgr.create_constraints()

            # --- Pass 1: Ingest File & Folder Structure ---
            logger.info("\n--- Starting Pass 1: Ingesting File & Folder Structure ---")
            path_processor = PathProcessor(path_manager, neo4j_mgr, args.log_batch_size)
            path_processor.ingest_paths(symbol_parser.symbols)
            del path_processor
            gc.collect()
            logger.info("--- Finished Pass 1 ---")

            # --- Pass 2: Ingest Symbol Definitions ---
            logger.info("\n--- Starting Pass 2: Ingesting Symbol Definitions ---")
            symbol_processor = SymbolProcessor(path_manager)
            batch, count = [], 0
            for i, sym in enumerate(symbol_parser.symbols.values()):
                if (i + 1) % args.log_batch_size == 0:
                    logger.info(f"Processed {i + 1} symbols...")
                batch.extend(symbol_processor.process_symbol(sym))
                if len(batch) >= BATCH_SIZE:
                    neo4j_mgr.process_batch(batch)
                    count += len(batch)
                    logger.info(f"Committed {count} symbol operations...")
                    batch = []
            if batch:
                neo4j_mgr.process_batch(batch)
                count += len(batch)
            
            logger.info(f"Completed symbol ingestion. Total operations: {count}")
            del batch
            del symbol_processor
            gc.collect()
            logger.info("--- Finished Pass 2 ---")

            # --- Pass 3: Ingest Call Graph ---
            logger.info("\n--- Starting Pass 3: Ingesting Call Graph ---")
            
            if symbol_parser.has_container_field:
                extractor = ClangdCallGraphExtractorWithContainer(symbol_parser, args.log_batch_size)
                logger.info("Using ClangdCallGraphExtractorWithContainer (new format detected).")
            else:
                extractor = ClangdCallGraphExtractorWithoutContainer(symbol_parser, args.log_batch_size)
                logger.info("Using ClangdCallGraphExtractorWithoutContainer (old format detected).")
                # Load spans from project only if needed
                extractor.load_spans_from_project(args.project_path)
            
            call_relations = extractor.extract_call_relationships()
            query, params = extractor.get_call_relation_ingest_query(call_relations)
            
            del extractor # Deletes the extractor and its reference to symbol_parser
            gc.collect()
            
            if query:
                logger.info(f"Ingesting {len(call_relations)} call relationships...")
                with neo4j_mgr.driver.session() as session:
                    session.run(query, **params)
                logger.info("Call graph ingestion complete.")
            
            del call_relations
            gc.collect()
            logger.info("--- Finished Pass 3 ---")

            # --- Pass 4: Cleanup Orphan Nodes (Optional) ---
            if not args.keep_orphans:
                logger.info("\n--- Starting Pass 4: Cleaning up Orphan Nodes ---")
                deleted_nodes_count = neo4j_mgr.cleanup_orphan_nodes()
                logger.info(f"Removed {deleted_nodes_count} orphan nodes.")
                logger.info("--- Finished Pass 4 ---")
            else:
                logger.info("\n--- Skipping Pass 4: Keeping orphan nodes as requested ---")

        del symbol_parser
        del path_manager
        gc.collect()
        logger.info("\n✅ All passes complete. Code graph ingestion finished.")
        return 0

    finally:
        # --- Cleanup --- 
        if 'clean_yaml_path' in locals() and os.path.exists(clean_yaml_path):
            logger.info(f"Cleaning up temporary file: {clean_yaml_path}")
            os.remove(clean_yaml_path)

if __name__ == "__main__":
    sys.exit(main())