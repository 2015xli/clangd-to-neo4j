#!/usr/bin/env python3
"""
Main entry point for the code graph ingestion pipeline.

This script orchestrates the different processors to build a complete code graph:
0. Parses the clangd YAML index into an in-memory object.
1. Ingests the code's file/folder structure.
2. Ingests symbol definitions (functions, structs, etc.).
3. Ingests the function call graph.
4. Cleans up orphan nodes.
5. Generates RAG data (summaries and embeddings).
"""

import argparse
import sys
import logging
import os
from pathlib import Path
import gc
import math

import input_params
# Import processors and managers from the library scripts
from clangd_symbol_nodes_builder import PathManager, PathProcessor, SymbolProcessor
from clangd_call_graph_builder import ClangdCallGraphExtractorWithContainer, ClangdCallGraphExtractorWithoutContainer
from clangd_index_yaml_parser import SymbolParser
from neo4j_manager import Neo4jManager
from memory_debugger import Debugger
from git_manager import GitManager
from compilation_manager import CompilationManager
from include_relation_provider import IncludeRelationProvider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GraphBuilder:
    """Orchestrates the full build of the code graph from a clangd index."""

    def __init__(self, args):
        """Initializes the builder with command-line arguments."""
        self.args = args
        self.debugger = Debugger(turnon=self.args.debug_memory)
        
        # State variables to be managed by the pipeline methods
        self.symbol_parser = None
        self.compilation_manager = None

    def build(self):
        """Runs the entire graph building pipeline."""
        try:
            self._pass_0_parse_symbols()
            self._pass_3_parse_sources()

            with Neo4jManager() as neo4j_mgr:
                if not neo4j_mgr.check_connection():
                    return 1

                self._setup_database(neo4j_mgr)
                self._pass_1_ingest_paths(neo4j_mgr)
                self._pass_2_ingest_symbols(neo4j_mgr)
                self._pass_4_ingest_includes(neo4j_mgr)
                self._pass_5_ingest_call_graph(neo4j_mgr)
                self._pass_6_cleanup_orphans(neo4j_mgr)
                self._pass_7_generate_rag(neo4j_mgr)

            logger.info("\n✅ All passes complete. Code graph ingestion finished.")
            return 0
        finally:
            self.debugger.stop()

    def _pass_0_parse_symbols(self):
        logger.info("\n--- Starting Pass 0: Loading, Parsing, and Linking Symbols ---")
        self.symbol_parser = SymbolParser(
            index_file_path=self.args.index_file,
            log_batch_size=self.args.log_batch_size,
            debugger=self.debugger
        )
        self.symbol_parser.parse(num_workers=self.args.num_parse_workers)
        logger.info("--- Finished Pass 0 ---")

    def _setup_database(self, neo4j_mgr):
        neo4j_mgr.reset_database()
        try:
            git_mgr = GitManager(self.args.project_path)
            commit_hash = git_mgr.repo.head.object.hexsha
            neo4j_mgr.update_project_node(self.args.project_path, {"commit_hash": commit_hash})
            logger.info(f"Stamped PROJECT node with commit hash: {commit_hash}")
        except Exception as e:
            logger.warning(f"Could not get git commit hash: {e}. Proceeding without it.")
            neo4j_mgr.update_project_node(self.args.project_path, {})
        neo4j_mgr.create_constraints()

    def _pass_1_ingest_paths(self, neo4j_mgr):
        logger.info("\n--- Starting Pass 1: Ingesting File & Folder Structure ---")
        path_manager = PathManager(self.args.project_path)
        path_processor = PathProcessor(path_manager, neo4j_mgr, self.args.log_batch_size, self.args.ingest_batch_size)
        path_processor.ingest_paths(self.symbol_parser.symbols)
        del path_processor, path_manager
        gc.collect()
        logger.info("--- Finished Pass 1 ---")

    def _pass_2_ingest_symbols(self, neo4j_mgr):
        logger.info("\n--- Starting Pass 2: Ingesting Symbol Definitions ---")
        path_manager = PathManager(self.args.project_path)
        symbol_processor = SymbolProcessor(
            path_manager,
            log_batch_size=self.args.log_batch_size,
            ingest_batch_size=self.args.ingest_batch_size,
            cypher_tx_size=self.args.cypher_tx_size
        )
        symbol_processor.ingest_symbols_and_relationships(self.symbol_parser.symbols, neo4j_mgr, self.args.defines_generation)
        del symbol_processor, path_manager
        gc.collect()
        logger.info("--- Finished Pass 2 ---")

    def _pass_3_parse_sources(self):
        logger.info("\n--- Starting Pass 3: Parsing Source Code ---")
        self.compilation_manager = CompilationManager(
            parser_type=self.args.source_parser,
            project_path=self.args.project_path,
            compile_commands_path=self.args.compile_commands
        )
        # The parse_folder method handles caching internally
        self.compilation_manager.parse_folder(self.args.project_path)
        logger.info("--- Finished Pass 3 ---")

    def _pass_4_ingest_includes(self, neo4j_mgr):
        logger.info("\n--- Starting Pass 4: Ingesting Include Relations ---")
        include_provider = IncludeRelationProvider(neo4j_mgr, self.args.project_path)
        include_provider.ingest_include_relations(self.compilation_manager)
        del include_provider
        gc.collect()
        logger.info("--- Finished Pass 4 ---")

    def _pass_5_ingest_call_graph(self, neo4j_mgr):
        logger.info("\n--- Starting Pass 5: Ingesting Call Graph ---")
        # TODO: This pass needs to be fully refactored to use CompilationManager
        # The ClangdCallGraphExtractorWithoutContainer class will need to be updated
        # to get span data from the manager instead of an enriched SymbolParser object.
        if self.symbol_parser.has_container_field:
            extractor = ClangdCallGraphExtractorWithContainer(self.symbol_parser, self.args.log_batch_size, self.args.ingest_batch_size)
            logger.info("Using ClangdCallGraphExtractorWithContainer (new format detected).")
        else:
            logger.info("Using ClangdCallGraphExtractorWithoutContainer (old format detected).")
            # This is a temporary adapter step. The extractor will need to be refactored.
            from function_span_provider import FunctionSpanProvider
            span_provider = FunctionSpanProvider(self.symbol_parser, self.compilation_manager)
            extractor = ClangdCallGraphExtractorWithoutContainer(self.symbol_parser, self.args.log_batch_size, self.args.ingest_batch_size, span_provider)
        
        call_relations = extractor.extract_call_relationships()
        extractor.ingest_call_relations(call_relations, neo4j_mgr=neo4j_mgr)
        del extractor, call_relations
        gc.collect()
        logger.info("--- Finished Pass 5 ---")

    def _pass_6_cleanup_orphans(self, neo4j_mgr):
        if not self.args.keep_orphans:
            logger.info("\n--- Starting Pass 6: Cleaning up Orphan Nodes ---")
            deleted_nodes_count = neo4j_mgr.cleanup_orphan_nodes()
            logger.info(f"Removed {deleted_nodes_count} orphan nodes.")
            logger.info("--- Finished Pass 6 ---")
        else:
            logger.info("\n--- Skipping Pass 6: Keeping orphan nodes as requested ---")

    def _pass_7_generate_rag(self, neo4j_mgr):
        if not self.args.generate_summary:
            return

        logger.info("\n--- Starting Pass 7: Generating Summaries and Embeddings ---")
        from code_graph_rag_generator import RagGenerator
        from llm_client import get_llm_client, get_embedding_client

        llm_client = get_llm_client(self.args.llm_api)
        embedding_client = get_embedding_client(self.args.llm_api)

        # TODO: Refactor RagGenerator to accept CompilationManager directly
        from function_span_provider import FunctionSpanProvider
        span_provider = FunctionSpanProvider(self.symbol_parser, self.compilation_manager)

        # The symbol_parser is large; delete it before the memory-intensive RAG process
        del self.symbol_parser
        gc.collect()

        rag_generator = RagGenerator(
            neo4j_mgr=neo4j_mgr,
            project_path=self.args.project_path,
            span_provider=span_provider, # Pass the adapter
            llm_client=llm_client,
            embedding_client=embedding_client,
            num_local_workers=self.args.num_local_workers,
            num_remote_workers=self.args.num_remote_workers
        )
        rag_generator.summarize_code_graph()
        neo4j_mgr.create_vector_indices()
        logger.info("--- Finished Pass 7 ---")

import input_params
from pathlib import Path

def main():
    """Parses arguments and runs the graph builder."""
    parser = argparse.ArgumentParser(description='Build a code graph from a clangd index.')
    
    # Add argument groups from the centralized module
    input_params.add_core_input_args(parser)
    input_params.add_worker_args(parser)
    input_params.add_batching_args(parser)
    input_params.add_rag_args(parser)
    input_params.add_ingestion_strategy_args(parser)
    input_params.add_source_parser_args(parser)
    input_params.add_logistic_args(parser) # For --debug-memory
    
    args = parser.parse_args()

    # Resolve paths and convert back to strings
    args.index_file = str(args.index_file.resolve())
    args.project_path = str(args.project_path.resolve())

    # Set default for ingest_batch_size if not provided
    if args.ingest_batch_size is None:
        try:
            default_workers = math.ceil(os.cpu_count() / 2)
        except (NotImplementedError, TypeError):
            default_workers = 2
        args.ingest_batch_size = args.cypher_tx_size * (args.num_parse_workers or default_workers)

    builder = GraphBuilder(args)
    return builder.build()

if __name__ == "__main__":
    sys.exit(main())
