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
from clangd_index_yaml_parser import SymbolParser
from neo4j_manager import Neo4jManager
from memory_debugger import Debugger


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
    parser.add_argument('--defines-generation', choices=['unwind-create', 'parallel-merge', 'parallel-create'], default='parallel-create',
                        help='Strategy for ingesting DEFINES relationships. (default: parallel-create)')
    parser.add_argument('--keep-orphans', action='store_true',
                      help='Keep orphan nodes in the graph (skip cleanup)')
    parser.add_argument('--debug-memory', action='store_true', help='Enable memory profiling with tracemalloc.')
    
    # RAG generation arguments
    rag_group = parser.add_argument_group('RAG Generation (Optional)')
    rag_group.add_argument('--generate-summary', action='store_true',
                        help='Generate AI summaries and embeddings for the code graph.')
    rag_group.add_argument('--llm-api', choices=['openai', 'deepseek', 'ollama'], default='deepseek',
                        help='The LLM API to use for summarization.')
    rag_group.add_argument('--num-local-workers', type=int, default=default_workers,
                        help=f'Number of parallel workers for local LLMs/embedding models. (default: {default_workers})')
    rag_group.add_argument('--num-remote-workers', type=int, default=100,
                        help='Number of parallel workers for remote LLM/embedding APIs. (default: 100)')
    args = parser.parse_args()

    # Set default for ingest_batch_size if not provided
    if args.ingest_batch_size is None:
        args.ingest_batch_size = args.cypher_tx_size * args.num_parse_workers

    debugger = Debugger(turnon=args.debug_memory)
    span_provider = None  # Initialize variable to hold the span_provider instance

    try:
        # --- Phase 0: Load, Parse, and Link Symbols ---
        logger.info("\n--- Starting Phase 0: Loading, Parsing, and Linking Symbols ---")

        symbol_parser = SymbolParser(
            index_file_path=args.index_file,
            log_batch_size=args.log_batch_size,
            debugger=debugger
        )
        # This single call now handles YAML parsing, parallelization, and caching
        symbol_parser.parse(num_workers=args.num_parse_workers)

        logger.info("--- Finished Phase 0 ---")

        # --- Main Processing ---
        path_manager = PathManager(args.project_path)
        with Neo4jManager() as neo4j_mgr:
            if not neo4j_mgr.check_connection():
                return 1

            neo4j_mgr.reset_database()
            # Stamp the project node with the current commit hash.
            try:
                git_mgr = GitManager(args.project_path)
                commit_hash = git_mgr.repo.head.object.hexsha
                neo4j_mgr.update_project_node(path_manager.project_path, {"commit_hash": commit_hash})
                logger.info(f"Stamped PROJECT node with commit hash: {commit_hash}")
            except Exception as e:
                logger.warning(f"Could not get git commit hash: {e}. Proceeding without it.")
                neo4j_mgr.update_project_node(path_manager.project_path, {})
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
            symbol_processor.ingest_symbols_and_relationships(symbol_parser.symbols, neo4j_mgr, args.defines_generation)
            del symbol_processor
            gc.collect()
            logger.info("--- Finished Phase 2 ---")

            # --- Phase 3: Ingest Call Graph ---
            logger.info("\n--- Starting Phase 3: Ingesting Call Graph ---")

            if symbol_parser.has_container_field:
                extractor = ClangdCallGraphExtractorWithContainer(symbol_parser, args.log_batch_size, args.ingest_batch_size)
                logger.info("Using ClangdCallGraphExtractorWithContainer (new format detected).")
            else:
                logger.info("Using ClangdCallGraphExtractorWithoutContainer (old format detected).")
                from function_span_provider import FunctionSpanProvider
                # If created here, store the instance in our variable for reuse
                span_provider = FunctionSpanProvider(symbol_parser=symbol_parser, paths=[args.project_path], log_batch_size=args.log_batch_size)
                extractor = ClangdCallGraphExtractorWithoutContainer(symbol_parser, args.log_batch_size, args.ingest_batch_size)

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

            # --- Pass 5: Generate Summaries and Embeddings (if requested) ---
            if args.generate_summary:
                logger.info("\n--- Starting Pass 5: Generating Summaries and Embeddings ---")
                from code_graph_rag_generator import RagGenerator
                from llm_client import get_llm_client, get_embedding_client

                # Check if the provider was already created in Pass 3
                if span_provider is None:
                    logger.info("Creating new FunctionSpanProvider for summary generation.")
                    from function_span_provider import FunctionSpanProvider
                    span_provider = FunctionSpanProvider(symbol_parser, [args.project_path], log_batch_size=args.log_batch_size)
                else:
                    logger.info("Reusing FunctionSpanProvider created in Pass 3.")

                # Initialize clients
                llm_client = get_llm_client(args.llm_api)
                embedding_client = get_embedding_client(args.llm_api)

                # Use the guaranteed-to-exist span_provider
                rag_generator = RagGenerator(
                    neo4j_mgr=neo4j_mgr,
                    project_path=args.project_path,
                    span_provider=span_provider,
                    llm_client=llm_client,
                    embedding_client=embedding_client,
                    num_local_workers=args.num_local_workers,
                    num_remote_workers=args.num_remote_workers
                )
                rag_generator.summarize_code_graph()
                neo4j_mgr.create_vector_indices()
                logger.info("--- Finished Pass 5 ---")


        del symbol_parser, path_manager
        gc.collect()
        logger.info("\n✅ All passes complete. Code graph ingestion finished.")
        return 0

    finally:
        debugger.stop()

if __name__ == "__main__":
    sys.exit(main())
