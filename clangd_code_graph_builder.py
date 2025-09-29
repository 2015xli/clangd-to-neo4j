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

import tempfile

# Import processors from the library scripts
from clangd_symbol_nodes_builder import PathManager, Neo4jManager, PathProcessor, SymbolProcessor
from tree_sitter_span_extractor import SpanExtractor
from clangd_call_graph_builder import ClangdCallGraphExtractor, FunctionSpan

BATCH_SIZE = 500

def main():
    parser = argparse.ArgumentParser(description='Build a code graph from a clangd index.')
    parser.add_argument('index_file', help='Path to the clangd index YAML file')
    parser.add_argument('project_path', help='Root path of the project being indexed')
    args = parser.parse_args()

    # --- Pre-Pass: Sanitize the large YAML file --- 
    print(f"Sanitizing input file: {args.index_file}")
    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8', errors='ignore') as temp_f:
            with open(args.index_file, 'r', errors='ignore') as f_in:
                for line in f_in:
                    temp_f.write(line.replace('\t', '  '))
            clean_yaml_path = temp_f.name
        print(f"Sanitized YAML written to temporary file: {clean_yaml_path}")

        # --- Main Processing --- 
        path_manager = PathManager(args.project_path)
        
        with Neo4jManager() as neo4j_mgr:
            if not neo4j_mgr.check_connection():
                print("Failed to connect to Neo4j. Exiting.", file=sys.stderr)
                return 1

            # Reset database and create constraints
            neo4j_mgr.reset_database()
            neo4j_mgr.create_project_node(path_manager.project_path)
            neo4j_mgr.create_constraints()

            # --- Pass 1: Ingest File & Folder Structure ---
            print("--- Starting Pass 1: Ingesting File & Folder Structure ---")
            path_processor = PathProcessor(path_manager, neo4j_mgr)
            path_processor.ingest_paths(clean_yaml_path)
            print("--- Finished Pass 1 ---")

            # --- Pass 2: Ingest Symbol Definitions ---
            print("\n--- Starting Pass 2: Ingesting Symbol Definitions ---")
            symbol_processor = SymbolProcessor(path_manager)
            batch, count, total_symbols = [], 0, 0

            with open(clean_yaml_path, "r") as f:
                for sym in yaml.safe_load_all(f):
                    if not sym:
                        continue
                    total_symbols += 1
                    if total_symbols % 500 == 0:
                        print(f"Processed {total_symbols} symbols...")
                    
                    ops = symbol_processor.process_symbol(sym)
                    batch.extend(ops)
                    
                    if len(batch) >= BATCH_SIZE:
                        neo4j_mgr.process_batch(batch)
                        count += len(batch)
                        print(f"Committed {count} symbol operations...")
                        batch = []
            
            if batch:
                neo4j_mgr.process_batch(batch)
                count += len(batch)
            
            print(f"Completed symbol ingestion. Total operations: {count}")
            print("--- Finished Pass 2 ---")

            # --- Pass 3: Ingest Call Graph ---
            print("\n--- Starting Pass 3: Ingesting Call Graph ---")
            call_graph_extractor = ClangdCallGraphExtractor()

            # 1. Extract function spans from source code
            print("Extracting function spans with tree-sitter...")
            span_extractor = SpanExtractor()
            function_span_dicts = span_extractor.get_function_spans_from_folder(args.project_path, format="dict")
            print(f"Found {len(function_span_dicts)} function definitions.")

            # 2. Parse clangd index and match spans
            print("Parsing clangd index for call graph...")
            with open(clean_yaml_path, 'r') as f:
                call_graph_extractor.parse_yaml(f)
            
            # Convert dicts to FunctionSpan objects before assigning
            call_graph_extractor.function_spans = [FunctionSpan.from_dict(d) for d in function_span_dicts]
            call_graph_extractor.match_function_spans()

            # 3. Extract and ingest call relationships
            call_relations = call_graph_extractor.extract_call_relationships()
            query, params = call_graph_extractor.get_call_relation_ingest_query(call_relations)
            
            if query:
                print(f"Ingesting {len(call_relations)} call relationships with a single query...")
                with neo4j_mgr.driver.session() as session:
                    session.run(query, **params)
                print("Call graph ingestion complete.")
            else:
                print("No call relationships found to ingest.")
            print("--- Finished Pass 3 ---")

        print("\n✅ All passes complete. Code graph ingestion finished.")
        return 0

    finally:
        # --- Cleanup --- 
        if 'clean_yaml_path' in locals() and os.path.exists(clean_yaml_path):
            print(f"Cleaning up temporary file: {clean_yaml_path}")
            os.remove(clean_yaml_path)

if __name__ == "__main__":
    sys.exit(main())