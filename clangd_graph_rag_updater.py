#!/usr/bin/env python3
"""
Orchestrates the incremental update of the code graph based on Git commits.
"""

import argparse
import sys, math
import logging
import os
from pathlib import Path
import gc
from typing import Optional, List, Dict, Set, Tuple

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
                 generate_summary: bool, llm_api: str, num_local_workers: int, num_remote_workers: int):
        self.project_path = project_path
        self.index_file = index_file
        self.old_commit = old_commit
        self.new_commit = new_commit
        self.num_parse_workers = num_parse_workers
        self.neo4j_manager = None
        self.generate_summary = generate_summary
        self.llm_api = llm_api
        self.num_local_workers = num_local_workers
        self.num_remote_workers = num_remote_workers
        self.changed_files: Dict[str, List[str]] = {} # To be populated in run_update
        self.seed_symbol_ids: Set[str] = set() # To be populated in _build_mini_index

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

            self.neo4j_manager = neo4j_mgr

            # Determine the commit range for the update.
            if self.new_commit is None:
                self.new_commit = self.git_manager.get_head_commit_hash()
                logger.info(f"No new-commit specified. Using current HEAD: {self.new_commit}")

            if self.old_commit is None:
                self.old_commit = self.neo4j_manager.get_graph_commit_hash(self.project_path)
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
        self.neo4j_manager.update_project_node(self.project_path, {'commit_hash': self.new_commit})
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
            self.neo4j_manager.purge_files(files_to_delete)

        # Files whose defined symbols need to be purged and re-ingested.
        # This includes modified files and the original paths of renamed/deleted files.
        files_to_purge_symbols_from = (
            changed_files['modified'] + 
            changed_files['deleted']
        )
        if files_to_purge_symbols_from:
            logger.info(f"Purging symbols from {len(files_to_purge_symbols_from)} changed/deleted files.")
            self.neo4j_manager.purge_symbols_defined_in_files(files_to_purge_symbols_from)

        logger.info("Phase 2 complete.")

    def _build_mini_index(self, changed_files: dict) -> Optional[SymbolParser]:
        """Phase 3: Builds a self-sufficient, in-memory index for the changed data."""
        logger.info("\n--- Phase 3: Building Self-Sufficient \"Mini-Index\" ---")
        
        # Step 1: Parse the Full New Index
        logger.info(f"Parsing new clangd index file: {self.index_file}")
        full_symbol_parser = SymbolParser(index_file_path=self.index_file)
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
        
        logger.info("Phase 3 complete.")
        return mini_index_parser

    def _rerun_ingestion_pipeline(self, mini_index_parser: Optional[SymbolParser]):
        """Phase 4: Reuses existing components to ingest the mini-index."""
        logger.info("\n--- Phase 4: Re-running Ingestion Pipeline on Mini-Index ---")
        if not mini_index_parser or not mini_index_parser.symbols:
            logger.info("Mini-index is empty. Nothing to ingest. Skipping Phase 4.")
            return

        # The ingestion components need various arguments, let's define them
        # These could be exposed as CLI args for the updater script in the future
        log_batch_size = 1000
        ingest_batch_size = 2000
        cypher_tx_size = 1000

        path_manager = PathManager(self.project_path)

        # Step 4a: Rebuild File Structure
        logger.info("Step 4a: Rebuilding file structure...")
        path_processor = PathProcessor(path_manager, self.neo4j_manager, log_batch_size, ingest_batch_size)
        path_processor.ingest_paths(mini_index_parser.symbols)
        del path_processor

        # Step 4b: Rebuild Symbols and :DEFINES
        logger.info("Step 4b: Rebuilding symbols and DEFINES relationships...")
        symbol_processor = SymbolProcessor(
            path_manager,
            log_batch_size=log_batch_size,
            ingest_batch_size=ingest_batch_size,
            cypher_tx_size=cypher_tx_size
        )
        # Use 'parallel-merge' for idempotent relationship creation
        symbol_processor.ingest_symbols_and_relationships(mini_index_parser.symbols, self.neo4j_manager, 'parallel-merge')
        del symbol_processor

        # Step 4c: Rebuild Call Graph
        logger.info("Step 4c: Rebuilding call graph...")
        if mini_index_parser.has_container_field:
            extractor = ClangdCallGraphExtractorWithContainer(mini_index_parser, log_batch_size, ingest_batch_size)
            logger.info("Using ClangdCallGraphExtractorWithContainer (new format detected).")
        else:
            logger.info("Using ClangdCallGraphExtractorWithoutContainer (old format detected).")
            files_for_span_provider = (
                changed_files.get('added', []) + 
                changed_files.get('modified', []) + 
                [p['new'] for p in changed_files.get('renamed', [])]
            )
            # The provider needs a list of absolute file paths
            abs_file_list = [os.path.abspath(os.path.join(self.project_path, f)) for f in files_for_span_provider]
            span_provider = FunctionSpanProvider(symbol_parser=mini_index_parser, paths=abs_file_list)
            extractor = ClangdCallGraphExtractorWithoutContainer(mini_index_parser, log_batch_size, ingest_batch_size, function_span_provider=span_provider)

        call_relations = extractor.extract_call_relationships()
        extractor.ingest_call_relations(call_relations, neo4j_manager=self.neo4j_manager)
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

        # Instantiate FunctionSpanProvider
        # The paths argument should be the project_path, as FunctionSpanProvider will read files from there.
        # Store the list of files that exist in the new commit for the span provider
        files_for_span_provider = (
            changed_files.get('added', []) + 
            changed_files.get('modified', []) + 
            [p['new'] for p in changed_files.get('renamed', [])]
        )
        abs_file_list = [os.path.abspath(os.path.join(self.project_path, f)) for f in files_for_span_provider]
        span_provider = FunctionSpanProvider(symbol_parser=mini_index_parser, paths=abs_file_list)

        rag_generator = RagGenerator(
            neo4j_mgr=self.neo4j_manager,
            project_path=self.project_path,
            span_provider=span_provider,
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


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    try:
        default_workers = math.ceil(os.cpu_count() / 2)
    except (NotImplementedError, TypeError):
        default_workers = 1

    parser = argparse.ArgumentParser(description='Incrementally update the code graph based on Git commits.')
    parser.add_argument('index_file', help='Path to the NEW clangd index YAML file for the target commit')
    parser.add_argument('project_path', help='Root path of the project being indexed')
    parser.add_argument('--old-commit', default=None, help='The old commit hash or reference. Defaults to graph commit_hash')
    parser.add_argument('--new-commit', default=None, help='The new commit hash or reference. Defaults to repo HEAD')
    parser.add_argument('--num-parse-workers', type=int, default=default_workers,
                        help=f'Number of parallel workers for parsing. Set to 1 for single-threaded mode. (default: {default_workers})')

    # RAG generation arguments
    rag_group = parser.add_argument_group('RAG Generation (Optional)')
    rag_group.add_argument('--generate-summary', action='store_true',
                        help='Generate AI summaries and embeddings for the code graph.')
    rag_group.add_argument('--llm-api', choices=['openai', 'deepseek', 'ollama'], default='deepseek',
                        help='The LLM API to use for summarization.')
    rag_group.add_argument('--num-local-workers', type=int, default=4, # A sensible default
                        help='Number of parallel workers for local LLMs/embedding models. (default: 4)')
    rag_group.add_argument('--num-remote-workers', type=int, default=100,
                        help='Number of parallel workers for remote LLM/embedding APIs. (default: 100)')

    args = parser.parse_args()

    updater = GraphUpdater(
        project_path=str(Path(args.project_path).resolve()),
        index_file=args.index_file,
        old_commit=args.old_commit,
        new_commit=args.new_commit,
        num_parse_workers=args.num_parse_workers,
        generate_summary=args.generate_summary,
        llm_api=args.llm_api,
        num_local_workers=args.num_local_workers,
        num_remote_workers=args.num_remote_workers
    )
    updater.update()

    return 0

if __name__ == "__main__":
    sys.exit(main())
