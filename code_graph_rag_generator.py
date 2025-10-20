#!/usr/bin/env python3
"""
This script generates summaries and embeddings for nodes in a code graph.

It connects to an existing Neo4j database populated by the ingestion pipeline
and executes a multi-pass process to enrich the graph with AI-generated
summaries and vector embeddings, as outlined in docs/code_rag_generation_plan.md.
"""

import argparse
import logging
import os
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, Callable, List
from tqdm import tqdm

import input_params
from neo4j_manager import Neo4jManager
from clangd_index_yaml_parser import SymbolParser
from function_span_provider import FunctionSpanProvider
from llm_client import get_llm_client, LlmClient, get_embedding_client, EmbeddingClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Main RAG Generation Logic ---

class RagGenerator:
    """Orchestrates the generation of RAG data.
    
    Designed with a separation of concerns:
    - Graph traversal methods are separate from
    - Single-item processing methods.
    """

    def __init__(self, neo4j_mgr: Neo4jManager, project_path: str, span_provider: FunctionSpanProvider, 
                 llm_client: LlmClient, embedding_client: EmbeddingClient, 
                 num_local_workers: int, num_remote_workers: int):
        self.neo4j_mgr = neo4j_mgr
        self.project_path = os.path.abspath(project_path)
        self.span_provider = span_provider
        self.llm_client = llm_client
        self.embedding_client = embedding_client
        self.num_local_workers = num_local_workers
        self.num_remote_workers = num_remote_workers

    def _parallel_process(self, items: Iterable, process_func: Callable, max_workers: int, desc: str) -> list:
        """
        Processes items in parallel using a thread pool, shows a progress bar,
        and returns a list of the non-None results from the process_func.
        """
        if not items:
            return []

        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_func, item): item for item in items}
            
            for future in tqdm(as_completed(futures), total=len(items), desc=desc):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    item = futures[future]
                    logging.error(f"Error processing item {item}: {e}", exc_info=True)
        return results

    def summarize_code_graph(self):
        """Main orchestrator method to run all summarization passes for a full build."""
        self.summarize_functions_individually()
        self.summarize_functions_with_context()
        logging.info("--- Starting File and Folder Summarization ---")
        self._summarize_all_files()
        self._summarize_all_folders()
        self._summarize_project()
        logging.info("--- Finished File and Folder Summarization ---")
        self.generate_embeddings()

    def summarize_targeted_update(self, seed_symbol_ids: set, structurally_changed_files: dict):
        """
        Runs a targeted, multi-pass summarization handling both content and structural changes.
        """
        if not seed_symbol_ids and not any(structurally_changed_files.values()):
            logging.info("No seed symbols or structural changes provided for targeted update. Skipping.")
            return

        logging.info(f"\n--- Starting Targeted RAG Update for {len(seed_symbol_ids)} seed symbols and {sum(len(v) for v in structurally_changed_files.values())} structural file changes ---")

        # --- Function Summary Passes (Content Changes) ---
        logging.info("Targeted Update - Pass 1: Summarizing changed functions individually...")
        updated_code_summary_ids = self._summarize_functions_individually_with_ids(list(seed_symbol_ids))
        logging.info(f"{len(updated_code_summary_ids)} functions received a new code summary.")

        logging.info("Targeted Update - Pass 2: Summarizing functions with context...")
        neighbor_ids = self._get_neighbor_ids(updated_code_summary_ids)
        all_function_ids_to_process = seed_symbol_ids.union(neighbor_ids)
        logging.info(f"Expanded scope for Pass 2 to {len(all_function_ids_to_process)} total functions.")
        
        updated_final_summary_ids = self._summarize_functions_with_context_with_ids(list(all_function_ids_to_process))
        logging.info(f"{len(updated_final_summary_ids)} functions received a new final summary.")

        # --- File & Folder Roll-up Passes (Content + Structural Changes) ---
        
        # 1. Identify files that trigger a file-level re-summary
        files_with_summary_changes = self._find_files_for_updated_symbols(updated_final_summary_ids)
        added_files = set(structurally_changed_files.get('added', []))
        modified_files = set(structurally_changed_files.get('modified', []))
        files_to_resummarize = files_with_summary_changes.union(added_files).union(modified_files)
        self._summarize_files_with_paths(files_to_resummarize)

        # 2. Identify all folders that need their summaries rolled up
        deleted_files = set(structurally_changed_files.get('deleted', []))
        all_trigger_files = files_to_resummarize.union(deleted_files)
        if not all_trigger_files:
            logging.info("No file or folder roll-up needed.")
        else:
            all_affected_folders_paths = set()
            for file_path in all_trigger_files:
                parent = os.path.dirname(file_path)
                while parent and parent != '.':
                    all_affected_folders_paths.add(parent)
                    parent = os.path.dirname(parent)
            
            self._summarize_folders_with_paths(all_affected_folders_paths)
            self._summarize_project()

        # --- Final Pass ---
        self.generate_embeddings()
        logging.info("--- Finished Targeted RAG Update ---")

    def _get_neighbor_ids(self, seed_symbol_ids: set) -> set:
        """Finds the 1-hop callers and callees of the seed symbols."""
        if not seed_symbol_ids:
            return set()
        
        query = """
        UNWIND $seed_ids AS seedId
        MATCH (n) WHERE n.id = seedId
        // Match direct callers and callees
        OPTIONAL MATCH (neighbor:FUNCTION)-[:CALLS*1]-(n)
        WITH collect(DISTINCT n.id) + collect(DISTINCT neighbor.id) AS allIds
        UNWIND allIds as id
        RETURN collect(DISTINCT id) as ids
        """
        result = self.neo4j_mgr.execute_read_query(query, {"seed_ids": list(seed_symbol_ids)})
        if result and result[0] and result[0]['ids']:
            return set(result[0]['ids'])
        return seed_symbol_ids

    def _find_files_for_updated_symbols(self, symbol_ids: set) -> set:
        """Finds the file paths that define a given set of symbols."""
        if not symbol_ids:
            return set()
        # Optimized query with DISTINCT and a label hint on the symbol node.
        query = """
        UNWIND $symbol_ids as symbolId
        MATCH (f:FILE)-[:DEFINES]->(s:FUNCTION {id: symbolId})
        RETURN DISTINCT f.path AS path
        """
        results = self.neo4j_mgr.execute_read_query(query, {"symbol_ids": list(symbol_ids)})
        return {r['path'] for r in results}

    # --- Pass 1 Methods ---
    def summarize_functions_individually(self):
        """PASS 1: Generates a code-only summary for all functions in the graph."""
        logging.info("\n--- Starting Pass 1: Summarizing Functions Individually ---")
        
        matched_ids = self.span_provider.get_matched_function_ids()
        if not matched_ids:
            logging.warning("Span provider found no functions to process. Exiting Pass 1.")
            return
        
        self._summarize_functions_individually_with_ids(matched_ids)
        logging.info("--- Finished Pass 1 ---")

    def _summarize_functions_individually_with_ids(self, function_ids: list[str]) -> set:
        """
        Core logic for Pass 1, operating on a specific list of function IDs.
        Returns the set of function IDs that were actually updated.
        """
        if not function_ids:
            return set()
            
        functions_to_process = self._get_functions_for_code_summary(function_ids)
        if not functions_to_process:
            logging.info("No functions from the provided list require a code summary.")
            return set()
            
        logging.info(f"Found {len(functions_to_process)} functions that need code summaries.")
        max_workers = self.num_local_workers if self.llm_client.is_local else self.num_remote_workers
        logging.info(f"Using {max_workers} parallel workers for Pass 1.")

        updated_ids = self._parallel_process(
            items=functions_to_process,
            process_func=self._process_one_function_for_code_summary,
            max_workers=max_workers,
            desc="Pass 1: Code Summaries"
        )
        return set(updated_ids)

    def _get_functions_for_code_summary(self, function_ids: list[str]) -> list[dict]:
        query = """
        MATCH (n:FUNCTION)
        WHERE n.id IN $function_ids AND n.codeSummary IS NULL AND n.has_definition
        RETURN n.id AS id, n.path AS path, n.location as location
        """
        return self.neo4j_mgr.execute_read_query(query, {"function_ids": function_ids})

    def _process_one_function_for_code_summary(self, func: dict) -> str | None:
        """
        Processes a single function for a code-only summary.
        Returns the function ID if a summary was successfully generated, otherwise None.
        """
        func_id = func['id']
        body_span = self.span_provider.get_body_span(func_id)
        if not body_span: return None
        source_code = self._get_source_code_from_span(body_span)
        if not source_code: return None
        logger.info(f"Summarize function {source_code}...")

        prompt = f"Summarize the purpose of this C function based on its code:\n\n```c\n{source_code}```"
        summary = self.llm_client.generate_summary(prompt)
        if not summary: return None

        update_query = "MATCH (n:FUNCTION {id: $id}) SET n.codeSummary = $summary"
        self.neo4j_mgr.execute_autocommit_query(update_query, {"id": func_id, "summary": summary})
        return func_id

    # --- Pass 2 Methods ---
    def summarize_functions_with_context(self):
        """PASS 2: Generates a final, context-aware summary for all functions in the graph."""
        logging.info("\n--- Starting Pass 2: Summarizing Functions With Context ---")
        
        functions_to_process = self._get_functions_for_contextual_summary()
        if not functions_to_process:
            logging.info("No functions require summarization in Pass 2.")
            return
        
        func_ids = [func['id'] for func in functions_to_process]
        self._summarize_functions_with_context_with_ids(func_ids)
        logging.info("--- Finished Pass 2 ---")

    def _summarize_functions_with_context_with_ids(self, function_ids: list[str]) -> set:
        """
        Core logic for Pass 2, operating on a specific list of function IDs.
        Returns the set of function IDs that were actually updated.
        """
        if not function_ids:
            return set()

        logging.info(f"Found {len(function_ids)} functions that need a final summary.")
        max_workers = self.num_local_workers if self.llm_client.is_local else self.num_remote_workers
        logging.info(f"Using {max_workers} parallel workers for Pass 2.")

        updated_ids = self._parallel_process(
            items=function_ids,
            process_func=self._process_one_function_for_contextual_summary,
            max_workers=max_workers,
            desc="Pass 2: Context Summaries"
        )
        return set(updated_ids)

    def _get_functions_for_contextual_summary(self) -> list[dict]:
        query = "MATCH (n:FUNCTION) WHERE n.codeSummary IS NOT NULL AND n.summary IS NULL RETURN n.id AS id"
        return self.neo4j_mgr.execute_read_query(query)

    def _process_one_function_for_contextual_summary(self, func_id: str) -> str | None:
        """
        Processes a single function for a contextual summary.
        Returns the function ID if the final summary was generated or changed, otherwise None.
        """
        context_query = """
        MATCH (n:FUNCTION {id: $id})
        OPTIONAL MATCH (caller:FUNCTION)-[:CALLS]->(n)
        OPTIONAL MATCH (n)-[:CALLS]->(callee:FUNCTION)
        RETURN n.codeSummary AS codeSummary,
               n.summary AS old_summary,
               collect(DISTINCT caller.codeSummary) AS callerSummaries,
               collect(DISTINCT callee.codeSummary) AS calleeSummaries
        """
        results = self.neo4j_mgr.execute_read_query(context_query, {"id": func_id})
        if not results: return None

        context = results[0]
        code_summary = context.get('codeSummary')
        old_summary = context.get('old_summary')
        
        if not code_summary: return None

        prompt = self._build_contextual_prompt(
            code_summary,
            context.get('callerSummaries', []),
            context.get('calleeSummaries', [])
        )
        final_summary = self.llm_client.generate_summary(prompt)
        if not final_summary: return None

        if final_summary != old_summary:
            update_query = "MATCH (n:FUNCTION {id: $id}) SET n.summary = $summary REMOVE n.summaryEmbedding"
            self.neo4j_mgr.execute_autocommit_query(update_query, {"id": func_id, "summary": final_summary})
            return func_id
        
        return None

    def _build_contextual_prompt(self, code_summary, caller_summaries, callee_summaries) -> str:
        caller_text = ", ".join([s for s in caller_summaries if s]) or "none"
        callee_text = ", ".join([s for s in callee_summaries if s]) or "none"
        return (
            f"A C function is described as: '{code_summary}'.\n"
            f"It is called by functions with these responsibilities: [{caller_text}].\n"
            f"It calls other functions to do the following: [{callee_text}].\n\n"
            f"Based on this context, what is the high-level purpose of this function in the overall system? "
            f"Describe it in one concise sentence."
        )

    # --- Pass 3 Methods ---
    def _summarize_all_files(self):
        logging.info("\n--- Starting Pass 3: Summarizing All Files ---")
        # Query for all files, not just ones with summary is null, to ensure correctness on re-runs
        files_to_process = self.neo4j_mgr.execute_read_query("MATCH (f:FILE) RETURN f.path AS path")
        if not files_to_process:
            logging.info("No files found to summarize.")
            return
        
        file_paths = {f['path'] for f in files_to_process}
        self._summarize_files_with_paths(file_paths)

    def _summarize_files_with_paths(self, file_paths: set):
        """Core logic for summarizing a specific set of FILE nodes."""
        if not file_paths:
            return
        logging.info(f"Summarizing {len(file_paths)} FILE nodes...")
        max_workers = self.num_local_workers if self.llm_client.is_local else self.num_remote_workers
        self._parallel_process(
            items=list(file_paths),
            process_func=self._summarize_one_file,
            max_workers=max_workers,
            desc="File Summaries"
        )

    def _summarize_one_file(self, file_path: str):
        query = """
        MATCH (f:FILE {path: $path})-[:DEFINES]->(func:FUNCTION)
        WHERE func.summary IS NOT NULL
        RETURN func.summary AS summary
        """
        results = self.neo4j_mgr.execute_read_query(query, {"path": file_path})
        func_summaries = [r['summary'] for r in results if r['summary']]
        if not func_summaries: return

        prompt = f"A file named '{os.path.basename(file_path)}' contains functions with the following responsibilities: [{ '; '.join(func_summaries)}]. What is the overall purpose of this file?"
        summary = self.llm_client.generate_summary(prompt)
        if not summary: return

        update_query = "MATCH (f:FILE {path: $path}) SET f.summary = $summary REMOVE f.summaryEmbedding"
        self.neo4j_mgr.execute_autocommit_query(update_query, {"path": file_path, "summary": summary})

    # --- Pass 4 Methods ---
    def _summarize_all_folders(self):
        logging.info("\n--- Starting Pass 4: Summarizing All Folders (bottom-up) ---")
        folders_to_process = self.neo4j_mgr.execute_read_query("MATCH (f:FOLDER) RETURN f.path AS path")
        if not folders_to_process:
            logging.info("No folders found to summarize.")
            return

        folder_paths = {f['path'] for f in folders_to_process}
        self._summarize_folders_with_paths(folder_paths)

    def _summarize_folders_with_paths(self, folder_paths: set):
        """Core logic for summarizing a specific set of FOLDER nodes."""
        if not folder_paths:
            return

        logging.info(f"Found {len(folder_paths)} potentially affected FOLDER nodes. Verifying existence in graph...")
        folder_details_query = "UNWIND $paths as path MATCH (f:FOLDER {path: path}) RETURN f.path as path, f.name as name"
        folder_details = self.neo4j_mgr.execute_read_query(folder_details_query, {"paths": list(folder_paths)})

        if not folder_details:
            logging.info("No affected folders exist in the graph. No roll-up needed.")
            return

        logging.info(f"Rolling up summaries for {len(folder_details)} existing FOLDER nodes...")
        folders_by_depth = {}
        for folder in folder_details:
            depth = folder['path'].count(os.sep)
            if depth not in folders_by_depth:
                folders_by_depth[depth] = []
            folders_by_depth[depth].append(folder)

        max_workers = self.num_local_workers if self.llm_client.is_local else self.num_remote_workers
        for depth in sorted(folders_by_depth.keys(), reverse=True):
            self._parallel_process(
                items=folders_by_depth[depth],
                process_func=lambda f: self._summarize_one_folder(f['path'], f['name']),
                max_workers=max_workers,
                desc=f"Folder Roll-up (Depth {depth})"
            )

    def _summarize_one_folder(self, folder_path: str, folder_name: str):
        query = """
        MATCH (parent:FOLDER {path: $path})-[:CONTAINS]->(child)
        WHERE child.summary IS NOT NULL
        RETURN labels(child)[0] as label, child.name as name, child.summary as summary
        """
        results = self.neo4j_mgr.execute_read_query(query, {"path": folder_path})
        child_summaries = [f"{r['label'].lower()} '{r['name']}' is responsible for: {r['summary']}" for r in results]
        if not child_summaries: return

        prompt = f"A folder named '{folder_name}' contains the following components: [{ '; '.join(child_summaries)}]. What is this folder's collective role in the project?"
        summary = self.llm_client.generate_summary(prompt)
        if not summary: return

        update_query = "MATCH (f:FOLDER {path: $path}) SET f.summary = $summary REMOVE f.summaryEmbedding"
        self.neo4j_mgr.execute_autocommit_query(update_query, {"path": folder_path, "summary": summary})

    def _summarize_project(self):
        """Summarizes the top-level PROJECT node."""
        logging.info("Summarizing the PROJECT node...")
        query = """
        MATCH (p:PROJECT)-[:CONTAINS]->(child)
        WHERE child.summary IS NOT NULL
        RETURN labels(child)[-1] as label, child.name as name, child.summary as summary
        """
        results = self.neo4j_mgr.execute_read_query(query)
        if not results: 
            logging.warning("No summarized children found for PROJECT node. Skipping.")
            return

        child_summaries = [f"The {r['label'].lower()} '{r['name']}' is responsible for: {r['summary']}" for r in results]
        prompt = f"A software project contains the following top-level components: [{ '; '.join(child_summaries)}]. What is the overall purpose and architecture of this project?"
        summary = self.llm_client.generate_summary(prompt)
        if not summary: return

        update_query = "MATCH (p:PROJECT) SET p.summary = $summary REMOVE p.summaryEmbedding"
        self.neo4j_mgr.execute_autocommit_query(update_query, {"summary": summary})
        logging.info("-> Stored summary for PROJECT node.")

    # --- Pass 5 Methods ---
    def generate_embeddings(self):
        """PASS 5: Generates and stores embeddings for all generated summaries in batches."""
        logging.info("\n--- Starting Pass 5: Generating Embeddings ---")
        nodes_to_embed = self._get_nodes_for_embedding()
        if not nodes_to_embed:
            logging.info("No nodes require embedding.")
            return

        logging.info(f"Found {len(nodes_to_embed)} nodes with summaries to embed.")

        # Step 1: Batch generate embeddings
        # The sentence-transformer library will show its own progress bar here.
        summaries = [node['summary'] for node in nodes_to_embed]
        embeddings = self.embedding_client.generate_embeddings(summaries)

        # Step 2: Prepare data for batch database update
        update_params = []
        for node, embedding in zip(nodes_to_embed, embeddings):
            if embedding:
                update_params.append({
                    'elementId': node['elementId'],
                    'embedding': embedding
                })

        if not update_params:
            logging.warning("Embedding generation resulted in no data to update.")
            return

        # Step 3: Batch update the database
        ingest_batch_size = 1000  # Sensible batch size for DB updates
        logging.info(f"Updating {len(update_params)} nodes in the database in batches of {ingest_batch_size}...")
        
        update_query = """
        UNWIND $batch AS data
        MATCH (n) WHERE elementId(n) = data.elementId
        SET n.summaryEmbedding = data.embedding
        """
        
        for i in tqdm(range(0, len(update_params), ingest_batch_size), desc="Updating DB"):
            batch = update_params[i:i + ingest_batch_size]
            self.neo4j_mgr.execute_autocommit_query(update_query, params={'batch': batch})

        logging.info("--- Finished Pass 5 ---")

    def _get_nodes_for_embedding(self) -> list[dict]:
        # This query finds any node with a final summary but no embedding yet.
        query = """
        MATCH (n)
        WHERE (n:FUNCTION OR n:FILE OR n:FOLDER OR n:PROJECT)
          AND n.summary IS NOT NULL 
          AND n.summaryEmbedding IS NULL
        RETURN elementId(n) AS elementId, n.summary AS summary
        """
        return self.neo4j_mgr.execute_read_query(query)

    

    # --- Utility Methods ---
    def _get_source_code_from_span(self, span: dict) -> str:
        full_path = span['file_path']
        start_line = span['start_line']
        end_line = span['end_line']

        if not os.path.exists(full_path):
            logging.warning(f"File not found when trying to extract source: {full_path}")
            return ""
        
        try:
            with open(full_path, 'r', errors='ignore') as f:
                lines = f.readlines()
            code_lines = lines[start_line : end_line + 1]
            return "".join(code_lines)
        except Exception as e:
            logging.error(f"Error reading file {full_path}: {e}")
            return ""

import input_params
from pathlib import Path

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser(description='Generate summaries and embeddings for a code graph.')
    
    # Add argument groups from the centralized module
    input_params.add_core_input_args(parser)
    input_params.add_rag_args(parser)
    input_params.add_worker_args(parser)

    args = parser.parse_args()

    # Resolve paths and convert back to strings
    args.index_file = str(args.index_file.resolve())
    args.project_path = str(args.project_path.resolve())

    try:
        # Use the standardized 'llm_api' argument name
        llm_client = get_llm_client(args.llm_api)
        embedding_client = get_embedding_client(args.llm_api)

        with Neo4jManager() as neo4j_mgr:
            if not neo4j_mgr.check_connection(): return 1

            # Verify that the project path in the graph matches the one provided
            if not neo4j_mgr.verify_project_path(args.project_path):
                return 1
            
            logger.info("Parsing YAML index or loading from cache...")
            symbol_parser = SymbolParser(index_file_path=args.index_file)
            symbol_parser.parse(num_workers=args.num_parse_workers)

            span_provider = FunctionSpanProvider(symbol_parser, [args.project_path])
            generator = RagGenerator(
                neo4j_mgr, 
                args.project_path, 
                span_provider, 
                llm_client, 
                embedding_client,
                args.num_local_workers,
                args.num_remote_workers
            )
            
            generator.summarize_code_graph()

            neo4j_mgr.create_vector_indices()

    except Exception as e:
        logging.critical(f"A critical error occurred: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    main()
