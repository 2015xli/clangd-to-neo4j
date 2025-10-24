#!/usr/bin/env python3
"""
Orchestrates the incremental update of the code graph based on Git commits.
"""

import argparse
from urllib.parse import urlparse, unquote
import sys, math
import logging
import os
import gc
from typing import Optional, List, Dict, Set

import input_params
from git_manager import GitManager
from git.exc import InvalidGitRepositoryError
from neo4j_manager import Neo4jManager
from clangd_index_yaml_parser import SymbolParser
from clangd_symbol_nodes_builder import PathManager, PathProcessor, SymbolProcessor
from clangd_call_graph_builder import ClangdCallGraphExtractorWithContainer, ClangdCallGraphExtractorWithoutContainer
from function_span_provider import FunctionSpanProvider
from code_graph_rag_generator import RagGenerator
from llm_client import get_llm_client, get_embedding_client

logger = logging.getLogger(__name__)

class GraphUpdater:
    """Manages the incremental update process."""

    def __init__(self, project_path: str, index_file: str, old_commit: str, new_commit: str, num_parse_workers: int,
                 log_batch_size: int, ingest_batch_size: int, cypher_tx_size: int, defines_generation: str,
                 span_extractor: str, compile_commands: Optional[str],
                 generate_summary: bool, llm_api: str, num_local_workers: int, num_remote_workers: int):
        self.project_path = project_path
        self.index_file = index_file
        self.old_commit = old_commit
        self.new_commit = new_commit
        self.num_parse_workers = num_parse_workers
        self.log_batch_size = log_batch_size
        self.ingest_batch_size = ingest_batch_size
        self.cypher_tx_size = cypher_tx_size
        self.defines_generation = defines_generation
        self.span_extractor = span_extractor
        self.compile_commands = compile_commands
        self.neo4j_mgr = None
        self.generate_summary = generate_summary
        self.llm_api = llm_api
        self.num_local_workers = num_local_workers
        self.num_remote_workers = num_remote_workers
        self.changed_files: Dict[str, List[str]] = {} # To be populated in run_update
        self.seed_symbol_ids: Set[str] = set() # To be populated in _build_mini_index
        self.function_span_provider: Optional[FunctionSpanProvider] = None # To be populated in _build_mini_index

        logger.info(f"Initializing graph update for project: {project_path}")
        try:
            self.git_manager = GitManager(self.project_path)
        except InvalidGitRepositoryError:
            logger.error("Project path is not a valid Git repository. Aborting.")
            sys.exit(1)

    def update(self):

        with Neo4jManager() as neo4j_mgr:
            if not neo4j_mgr.check_connection():
                return 1

            self.neo4j_mgr = neo4j_mgr

            # Verify that the project path in the graph matches the one provided
            if not self.neo4j_mgr.verify_project_path(self.project_path):
                sys.exit(1)

            # Determine the commit range for the update.
            if self.new_commit is None:
                self.new_commit = self.git_manager.get_head_commit_hash()
                logger.info(f"No new-commit specified. Using current HEAD: {self.new_commit}")

            if self.old_commit is None:
                self.old_commit = self.neo4j_mgr.get_graph_commit_hash(self.project_path)
                if not self.old_commit:
                    logger.error("No old-commit specified and no commit hash found in the database. Cannot determine update range.")
                    sys.exit(1)
                logger.info(f"No old-commit specified. Using last processed commit from graph: {self.old_commit}")

            if self.old_commit == self.new_commit:
                logger.info("Database is already up-to-date. No update needed.")
                return

            logger.info(f"Processing changes from {self.old_commit} to {self.new_commit}")
            self.update_with_neo4jmanager()


    def update_with_neo4jmanager(self):

        """Executes the full incremental update pipeline."""
        logger.info("\n--- Starting Incremental Update ---")
        # Phase 1: Identify Changed Files
        changed_files = self._identify_changed_files()
        logger.info(f"Changed files between {self.old_commit} and {self.new_commit}:\n {changed_files} ")
        
        if not any(changed_files.values()):
            logger.info("No relevant source file changes detected. Update complete.")
            return
        self.changed_files = changed_files
        
        # Phase 2: Purge Stale Graph Data
        self._purge_stale_data(self.changed_files)

        # Phase 3: Build Self-Sufficient "Mini-Index"
        mini_index_parser = self._build_mini_index(self.changed_files)

        # Phase 4: Re-run Ingestion Pipeline on Mini-Index
        self._rerun_ingestion_pipeline(mini_index_parser)

        # Phase 5: RAG Summary Generation
        self._update_summaries(mini_index_parser, self.changed_files)

        # Final Step: Update the commit hash in the graph to the new version
        self.neo4j_mgr.update_project_node(self.project_path, {'commit_hash': self.new_commit})
        logger.info(f"Successfully updated PROJECT node to commit: {self.new_commit}")

        logger.info("\n✅ Incremental update complete.")

    def _identify_changed_files(self) -> dict:
        """Phase 1: Identifies added, modified, and deleted files using Git, treating renames as delete+add."""
        logger.info("\n--- Phase 1: Identifying Changed Files ---")
        changed_files = self.git_manager.get_categorized_changed_files(self.old_commit, self.new_commit)
        logger.info("Found changed files:")
        if changed_files['added']:
            logger.info(f"  Added: {len(changed_files['added'])}")
        if changed_files['modified']:
            logger.info(f"  Modified: {len(changed_files['modified'])}")
        if changed_files['deleted']:
            logger.info(f"  Deleted: {len(changed_files['deleted'])}")
        logger.info("Phase 1 complete.")
        return changed_files

    def _purge_stale_data(self, changed_files: dict):
        """Phase 2: Removes outdated data from the graph."""
        logger.info("\n--- Phase 2: Purging Stale Graph Data ---")
        
        # The 'deleted' list from GitManager already includes the original paths of renamed files.
        files_to_delete = changed_files['deleted']
        if files_to_delete:
            logger.info(f"Deleting {len(files_to_delete)} FILE nodes from the graph.")
            self.neo4j_mgr.purge_files(files_to_delete)

        # Files whose defined symbols need to be purged and re-ingested.
        # This includes modified files and the original paths of renamed/deleted files.
        files_to_purge_symbols_from = (
            changed_files['modified'] + 
            changed_files['deleted']
        )
        if files_to_purge_symbols_from:
            logger.info(f"Purging symbols from {len(files_to_purge_symbols_from)} changed/deleted files.")
            self.neo4j_mgr.purge_symbols_defined_in_files(files_to_purge_symbols_from)

        logger.info("Phase 2 complete.")

    def _build_mini_index(self, changed_files: dict) -> Optional[SymbolParser]:
        """Phase 3: Builds a self-sufficient, in-memory index for the changed data."""
        logger.info("\n--- Phase 3: Building Self-Sufficient \"Mini-Index\" ---")
        
        # Step 1: Parse the Full New Index
        logger.info(f"Parsing new clangd index file: {self.index_file}")
        full_symbol_parser = SymbolParser(
            index_file_path=self.index_file,
            log_batch_size=self.log_batch_size
        )
        full_symbol_parser.parse(num_workers=self.num_parse_workers) # Assuming default workers for now

        # Step 2: Identify Seed Symbols
        logger.info("Identifying seed symbols from changed files...")
        seed_symbol_ids = set()
        files_to_scan = (
            changed_files.get('added', []) + 
            changed_files.get('modified', [])
        )
        
        # Convert relative paths to file URIs for matching
        # Note: This assumes paths from git are relative to the project root.
        files_to_scan_uris = {f"file://{os.path.abspath(os.path.join(self.project_path, f))}" for f in files_to_scan}

        for symbol in full_symbol_parser.symbols.values():
            if symbol.definition and symbol.definition.file_uri in files_to_scan_uris:
                seed_symbol_ids.add(symbol.id)
        self.seed_symbol_ids = seed_symbol_ids # Store for later use in RAG update
        logger.info(f"Found {len(self.seed_symbol_ids)} seed symbols.")

        # Step 3: Grow to 1-Hop Neighbors
        logger.info("Finding 1-hop neighbors (callers and callees)...")
        final_symbol_ids = set(seed_symbol_ids)

        # Find Incoming Callers (functions that call the seed symbols)
        for seed_id in seed_symbol_ids:
            if seed_id in full_symbol_parser.symbols:
                callee_symbol = full_symbol_parser.symbols[seed_id]
                for ref in callee_symbol.references:
                    if ref.container_id and ref.container_id != '0000000000000000':
                        final_symbol_ids.add(ref.container_id)

        # Find Outgoing Callees (functions called by the seed symbols)
        for callee_symbol in full_symbol_parser.symbols.values():
            for ref in callee_symbol.references:
                if ref.container_id in seed_symbol_ids:
                    final_symbol_ids.add(callee_symbol.id)
                    break  # Optimization: move to the next symbol once one link is found
        
        logger.info(f"Total symbols in mini-index (seeds + neighbors): {len(final_symbol_ids)}")

        # Step 4: Create and Populate the Mini-Index
        logger.info("Creating the mini-index from the full symbol table...")
        mini_index_parser = full_symbol_parser.create_subset(final_symbol_ids)
        
        # The deletion is actually unnecessary because full_symbol_parser is local variable. But we just want to force gc to reclaim it.
        del full_symbol_parser
        gc.collect()

        logger.info("Phase 3 complete.")
        return mini_index_parser

    def _rerun_ingestion_pipeline(self, mini_index_parser: Optional[SymbolParser]):
        """Phase 4: Reuses existing components to ingest the mini-index."""
        logger.info("\n--- Phase 4: Re-running Ingestion Pipeline on Mini-Index ---")
        if not mini_index_parser or not mini_index_parser.symbols:
            logger.info("Mini-index is empty. Nothing to ingest. Skipping Phase 4.")
            return

        path_manager = PathManager(self.project_path)

        # Step 4a: Rebuild File Structure
        logger.info("Step 4a: Rebuilding file structure...")
        path_processor = PathProcessor(path_manager, self.neo4j_mgr, self.log_batch_size, self.ingest_batch_size)
        path_processor.ingest_paths(mini_index_parser.symbols)
        del path_processor

        # Step 4b: Rebuild Symbols and :DEFINES
        logger.info("Step 4b: Rebuilding symbols and DEFINES relationships...")
        symbol_processor = SymbolProcessor(
            path_manager,
            log_batch_size=self.log_batch_size,
            ingest_batch_size=self.ingest_batch_size,
            cypher_tx_size=self.cypher_tx_size
        )
        # Use the configured defines generation strategy 
        symbol_processor.ingest_symbols_and_relationships(mini_index_parser.symbols, self.neo4j_mgr, self.defines_generation)
        del symbol_processor

        # Step 4c: Rebuild Call Graph
        logger.info("Step 4c: Rebuilding call graph...")
        if mini_index_parser.has_container_field:
            extractor = ClangdCallGraphExtractorWithContainer(mini_index_parser, self.log_batch_size, self.ingest_batch_size)
            logger.info("Using ClangdCallGraphExtractorWithContainer (new format detected).")
        else:
            logger.info("Using ClangdCallGraphExtractorWithoutContainer (old format detected).")
            # Spans are needed for the old format. Get spans for added/modified files.
            self._get_function_span_provider(mini_index_parser)
            extractor = ClangdCallGraphExtractorWithoutContainer(mini_index_parser, self.log_batch_size, self.ingest_batch_size)

        call_relations = extractor.extract_call_relationships()
        extractor.ingest_call_relations(call_relations, neo4j_mgr=self.neo4j_mgr)
        del extractor, call_relations

        gc.collect()
        logger.info("Phase 4 complete.")

    def _update_summaries(self, mini_index_parser, changed_files):
        """Phase 5: Updates AI-generated summaries and embeddings."""
        logger.info("\n--- Phase 5: Updating RAG Summaries and Embeddings ---")
        if not self.generate_summary:
            logger.info("RAG summary generation not requested. Skipping Phase 5.")
            return

        if not mini_index_parser or not mini_index_parser.symbols:
            logger.info("Mini-index is empty. No summaries to update. Skipping Phase 5.")
            return

        logger.info("Initializing LLM and Embedding clients...")
        llm_client = get_llm_client(self.llm_api)
        embedding_client = get_embedding_client(self.llm_api)

        if self.function_span_provider is None:
            self.function_span_provider = self._get_function_span_provider(mini_index_parser)
            # Once the span provider is created, the mini-index is no longer needed for RAG generation
            del mini_index_parser
            gc.collect()

        rag_generator = RagGenerator(
            neo4j_mgr=self.neo4j_mgr,
            project_path=self.project_path,
            span_provider=self.function_span_provider,
            llm_client=llm_client,
            embedding_client=embedding_client,
            num_local_workers=self.num_local_workers,
            num_remote_workers=self.num_remote_workers,
        )

        if not self.seed_symbol_ids:
            logger.info("No seed symbols found for RAG update. Skipping targeted update.")
            return

        logger.info(f"Using {len(self.seed_symbol_ids)} seed symbols for RAG update.")

        rag_generator.summarize_targeted_update(self.seed_symbol_ids, self.changed_files)

        logger.info("Phase 5 complete.")

    def _get_function_span_provider(self, mini_index_parser: SymbolParser):
        if self.function_span_provider:
            return self.function_span_provider

        # For the clang extractor, we need to re-parse all translation units (.c files)
        # that are affected by the changes. The safest way to do this is to find all
        # unique source files referenced by any symbol in our mini-index (which contains
        # the changed symbols + their 1-hop neighbors).
        logger.info("Determining files to re-scan based on mini-index...")
        files_to_scan = set()
        for symbol in mini_index_parser.symbols.values():
            if symbol.definition:
                # The file URI is already absolute, so we just need to convert it to a path
                path = unquote(urlparse(symbol.definition.file_uri).path)
                files_to_scan.add(path)

        logger.info(f"Found {len(files_to_scan)} unique files referenced in the mini-index.")
        abs_file_list = [os.path.abspath(f) for f in files_to_scan]

        self.function_span_provider = FunctionSpanProvider(
            symbol_parser=mini_index_parser,
            project_path=self.project_path,
            paths=abs_file_list, # Pass ALL files from the mini-index
            log_batch_size=self.log_batch_size,
            extractor_type=self.span_extractor,
            compile_commands_path=self.compile_commands
        )
        return self.function_span_provider
        
import input_params

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser(description='Incrementally update the code graph based on Git commits.')

    # Add argument groups from the centralized module
    input_params.add_core_input_args(parser)
    input_params.add_git_update_args(parser)
    input_params.add_worker_args(parser)
    input_params.add_batching_args(parser)
    input_params.add_rag_args(parser)
    input_params.add_ingestion_strategy_args(parser)
    input_params.add_span_extractor_args(parser)
    # Set a different default for defines_generation for safety in updates
    parser.set_defaults(defines_generation='batched-parallel')

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

    updater = GraphUpdater(
        project_path=args.project_path,
        index_file=args.index_file,
        old_commit=args.old_commit,
        new_commit=args.new_commit,
        num_parse_workers=args.num_parse_workers,
        log_batch_size=args.log_batch_size,
        ingest_batch_size=args.ingest_batch_size,
        cypher_tx_size=args.cypher_tx_size,
        defines_generation=args.defines_generation,
        span_extractor=args.span_extractor,
        compile_commands=args.compile_commands,
        generate_summary=args.generate_summary,
        llm_api=args.llm_api,
        num_local_workers=args.num_local_workers,
        num_remote_workers=args.num_remote_workers
    )
    updater.update()

    return 0

if __name__ == "__main__":
    sys.exit(main())
