#!/usr/bin/env python3
"""
Main entry point for the code graph ingestion pipeline.

This script orchestrates the different processors to build a complete code graph:
1. Extracts function spans using tree-sitter.
2. Ingests the code's file/folder structure.
3. Ingests symbol definitions (functions, structs, etc.).
4. Ingests the function call graph.
"""

import argparse
import sys
import yaml
import logging
import os
import tempfile

# Import processors from the library scripts
from clangd_symbol_nodes_builder import PathManager, Neo4jManager, PathProcessor, SymbolProcessor
from tree_sitter_span_extractor import SpanExtractor
from clangd_call_graph_builder import ClangdCallGraphExtractor, FunctionSpan

BATCH_SIZE = 500

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description='Build a code graph from a clangd index.')
    parser.add_argument('index_file', help='Path to the clangd index YAML file')
    parser.add_argument('project_path', help='Root path of the project being indexed')
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

        # --- Main Processing --- 
        path_manager = PathManager(args.project_path)
        
        with Neo4jManager() as neo4j_mgr:
            if not neo4j_mgr.check_connection():
                logger.error("Failed to connect to Neo4j. Exiting.")
                return 1

            # Reset database and create constraints
            neo4j_mgr.reset_database()
            neo4j_mgr.create_project_node(path_manager.project_path)
            neo4j_mgr.create_constraints()

            # --- Pass 1: Ingest File & Folder Structure ---
            logger.info("--- Starting Pass 1: Ingesting File & Folder Structure ---")
            path_processor = PathProcessor(path_manager, neo4j_mgr, args.log_batch_size)
            path_processor.ingest_paths(clean_yaml_path)
            logger.info("--- Finished Pass 1 ---")

            # --- Pass 2: Ingest Symbol Definitions ---
            logger.info("\n--- Starting Pass 2: Ingesting Symbol Definitions ---")
            symbol_processor = SymbolProcessor(path_manager)
            batch, count, total_symbols = [], 0, 0

            with open(clean_yaml_path, "r") as f:
                for sym in yaml.safe_load_all(f):
                    if not sym:
                        continue
                    total_symbols += 1
                    if total_symbols % args.log_batch_size == 0:
                        logger.info(f"Processed {total_symbols} symbols...")
                    
                    ops = symbol_processor.process_symbol(sym)
                    batch.extend(ops)
                    
                    if len(batch) >= BATCH_SIZE:
                        neo4j_mgr.process_batch(batch)
                        count += len(batch)
                        logger.info(f"Committed {count} symbol operations...")
                        batch = []
            
            if batch:
                neo4j_mgr.process_batch(batch)
                count += len(batch)
            
            logger.info(f"Completed symbol ingestion. Total operations: {count}")
            logger.info("--- Finished Pass 2 ---")

            # --- Pass 3: Ingest Call Graph ---
            logger.info("\n--- Starting Pass 3: Ingesting Call Graph ---")
            call_graph_extractor = ClangdCallGraphExtractor(args.log_batch_size)

            # 1. Extract function spans from source code
            logger.info("Extracting function spans with tree-sitter...")
            span_extractor = SpanExtractor(args.log_batch_size)
            function_span_file_dicts = span_extractor.get_function_spans_from_folder(args.project_path, format="dict")
            
            num_functions = sum(len(d.get('Functions', [])) for d in function_span_file_dicts)
            logger.info(f"Found {num_functions} function definitions in {len(function_span_file_dicts)} files.")

            # 2. Parse clangd index and match spans
            logger.info("Parsing clangd index for call graph...")
            with open(clean_yaml_path, 'r') as f:
                call_graph_extractor.parse_yaml(f)
            
            # Manually build the function_spans_by_file dictionary from the new format
            spans_by_file = {}
            for file_dict in function_span_file_dicts:
                file_uri = file_dict.get('FileURI')
                if not file_uri or 'Functions' not in file_dict:
                    continue
                
                # Create FunctionSpan objects which now use RelativeLocation
                spans_in_file = [FunctionSpan.from_dict(func_data) for func_data in file_dict['Functions'] if func_data]
                if spans_in_file:
                    spans_by_file[file_uri] = spans_in_file
            
            call_graph_extractor.function_spans_by_file = spans_by_file
            del function_span_file_dicts # Free memory
            call_graph_extractor.match_function_spans()

            # 3. Extract and ingest call relationships
            call_relations = call_graph_extractor.extract_call_relationships()
            
            # Free memory from large intermediate objects
            del call_graph_extractor.symbols
            del call_graph_extractor.functions
            del call_graph_extractor.function_spans_by_file

            query, params = call_graph_extractor.get_call_relation_ingest_query(call_relations)
            
            if query:
                logger.info(f"Ingesting {len(call_relations)} call relationships with a single query...")
                with neo4j_mgr.driver.session() as session:
                    session.run(query, **params)
                logger.info("Call graph ingestion complete.")
            else:
                logger.info("No call relationships found to ingest.")
            
            del call_relations # Free memory
            logger.info("--- Finished Pass 3 ---")

            # --- Pass 4: Cleanup Orphan Nodes (Optional) ---
            if not args.keep_orphans:
                logger.info("\n--- Starting Pass 4: Cleaning up Orphan Nodes ---")
                deleted_nodes_count = neo4j_mgr.cleanup_orphan_nodes()
                logger.info(f"Removed {deleted_nodes_count} orphan nodes.")
                logger.info("--- Finished Pass 4 ---")
            else:
                logger.info("\n--- Skipping Pass 4: Keeping orphan nodes as requested ---")

        logger.info("\n✅ All passes complete. Code graph ingestion finished.")
        return 0

    finally:
        # --- Cleanup --- 
        if 'clean_yaml_path' in locals() and os.path.exists(clean_yaml_path):
            logger.info(f"Cleaning up temporary file: {clean_yaml_path}")
            os.remove(clean_yaml_path)

if __name__ == "__main__":
    sys.exit(main())