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
        self.summarize_files_and_folders()
        self.generate_embeddings()

    def summarize_targeted_update(self, seed_symbol_ids: set):
        """Runs a targeted, multi-pass summarization starting from a set of seed symbols."""
        if not seed_symbol_ids:
            logging.info("No seed symbols provided for targeted update. Skipping.")
            return

        logging.info(f"\n--- Starting Targeted RAG Update for {len(seed_symbol_ids)} seed symbols ---")

        # Pass 1: Code-only summary for the functions directly changed.
        logging.info("Targeted Update - Pass 1: Summarizing changed functions individually...")
        updated_code_summary_ids = self._summarize_functions_individually_with_ids(list(seed_symbol_ids))
        logging.info(f"{len(updated_code_summary_ids)} functions received a new code summary.")

        # Pass 2: Context-aware summary for changed functions and their neighbors.
        logging.info("Targeted Update - Pass 2: Summarizing functions with context...")
        neighbor_ids = self._get_neighbor_ids(seed_symbol_ids)
        all_function_ids_to_process = seed_symbol_ids.union(neighbor_ids)
        logging.info(f"Expanded scope for Pass 2 to {len(all_function_ids_to_process)} total functions (seeds + neighbors).")
        
        updated_final_summary_ids = self._summarize_functions_with_context_with_ids(list(all_function_ids_to_process))
        
        if not updated_final_summary_ids:
            logging.info("No function final summaries were updated. Targeted update complete.")
            return
        
        logging.info(f"Completed function summaries. {len(updated_final_summary_ids)} functions received a new final summary in Pass 2.")

        # Passes 3 & 4: Find the files containing these updated functions and roll up summaries.
        starting_file_paths = self._find_files_for_updated_symbols(updated_final_summary_ids)
        if starting_file_paths:
            self._rollup_summaries_from_files(starting_file_paths)

        # Pass 5: Generate embeddings for all nodes that have a new summary.
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
        query = """
        UNWIND $symbol_ids as symbolId
        MATCH (f:FILE)-[:DEFINES]->(s) WHERE s.id = symbolId
        RETURN f.path AS path
        """
        results = self.neo4j_mgr.execute_read_query(query, {"symbol_ids": list(symbol_ids)})
        return {r['path'] for r in results}

    def _rollup_summaries_from_files(self, starting_file_paths: set):
        """For a given set of files, re-summarizes them and all their parent folders."""
        if not starting_file_paths:
            return
        
        logging.info(f"Rolling up summaries starting from {len(starting_file_paths)} files.")
        max_workers = self.num_local_workers if self.llm_client.is_local else self.num_remote_workers

        self._parallel_process(
            items=list(starting_file_paths),
            process_func=self._summarize_one_file,
            max_workers=max_workers,
            desc="Targeted Update: File Roll-up"
        )

        query = """
        UNWIND $paths as filePath
        MATCH (f:FILE {path: filePath})<-[:CONTAINS*]-(folder:FOLDER)
        RETURN DISTINCT folder.path as path, folder.name as name
        """
        parent_folders = self.neo4j_mgr.execute_read_query(query, {"paths": list(starting_file_paths)})
        if not parent_folders: return

        folders_by_depth = {}
        for folder in parent_folders:
            depth = folder['path'].count(os.sep)
            if depth not in folders_by_depth:
                folders_by_depth[depth] = []
            folders_by_depth[depth].append(folder)

        for depth in sorted(folders_by_depth.keys(), reverse=True):
            self._parallel_process(
                items=folders_by_depth[depth],
                process_func=lambda f: self._summarize_one_folder(f['path'], f['name']),
                max_workers=max_workers,
                desc=f"Targeted Update: Folder Roll-up (Depth {depth})"
            )
        
        self._summarize_project()

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
        WHERE n.id IN $function_ids AND n.codeSummary IS NULL
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
            update_query = "MATCH (n:FUNCTION {id: $id}) SET n.summary = $summary"
            self.neo4j_mgr.execute_autocommit_query(update_query, {"id": func_id, "summary": final_summary})
            return func_id
        
        return None

    # --- Pass 3 & 4 Methods ---
    def summarize_files_and_folders(self):
        """Generates summaries for files and folders via roll-up."""
        logging.info("\n--- Starting File and Folder Summarization ---")
        self._summarize_all_files()    # Pass 3
        self._summarize_all_folders()  # Pass 4
        self._summarize_project()
        logging.info("--- Finished File and Folder Summarization ---")

    def _summarize_all_files(self):
        logging.info("\n--- Starting Pass 3: Summarizing Files ---")
        files_to_process = self.neo4j_mgr.execute_read_query("MATCH (f:FILE) WHERE f.summary IS NULL RETURN f.path AS path")
        if not files_to_process:
            logging.info("No files require summarization.")
            return

        max_workers = self.num_local_workers if self.llm_client.is_local else self.num_remote_workers
        logging.info(f"Using {max_workers} parallel workers for file summarization.")

        file_paths = [file['path'] for file in files_to_process]

        self._parallel_process(
            items=file_paths,
            process_func=self._summarize_one_file,
            max_workers=max_workers,
            desc="Pass 3: File Summaries"
        )
        logging.info("--- Finished Pass 3 ---")

    def _summarize_one_file(self, file_path: str):
        # logging.info(f"Summarizing file: {file_path}")
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

        update_query = "MATCH (f:FILE {path: $path}) SET f.summary = $summary"
        self.neo4j_mgr.execute_autocommit_query(update_query, {"path": file_path, "summary": summary})
        # logging.info(f"-> Stored summary for file {file_path}")

    def _summarize_all_folders(self):
        logging.info("\n--- Starting Pass 4: Summarizing Folders (bottom-up) ---")
        query = "MATCH (f:FOLDER) WHERE f.summary IS NULL RETURN f.path AS path, f.name as name"
        folders_to_process = self.neo4j_mgr.execute_read_query(query)
        if not folders_to_process:
            logging.info("No folders require summarization.")
            return

        # Group folders by depth for level-by-level parallel processing
        folders_by_depth = {}
        for folder in folders_to_process:
            depth = folder['path'].count(os.sep)
            if depth not in folders_by_depth:
                folders_by_depth[depth] = []
            folders_by_depth[depth].append(folder)

        max_workers = self.num_local_workers if self.llm_client.is_local else self.num_remote_workers
        logging.info(f"Using {max_workers} parallel workers for folder summarization.")

        # Process level by level, from deepest to shallowest
        for depth in sorted(folders_by_depth.keys(), reverse=True):
            folders_at_this_level = folders_by_depth[depth]
            self._parallel_process(
                items=folders_at_this_level,
                process_func=lambda f: self._summarize_one_folder(f['path'], f['name']),
                max_workers=max_workers,
                desc=f"Pass 4: Folder Summaries (Depth {depth})"
            )
        logging.info("--- Finished Pass 4 ---")

    def _summarize_one_folder(self, folder_path: str, folder_name: str):
        # logging.info(f"Summarizing folder: {folder_path}")
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

        update_query = "MATCH (f:FOLDER {path: $path}) SET f.summary = $summary"
        self.neo4j_mgr.execute_autocommit_query(update_query, {"path": folder_path, "summary": summary})
        # logging.info(f"-> Stored summary for folder {folder_path}")

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
        """PASS 5: Generates and stores embeddings for all generated summaries."""
        logging.info("\n--- Starting Pass 5: Generating Embeddings ---")
        nodes_to_embed = self._get_nodes_for_embedding()
        if not nodes_to_embed:
            logging.info("No nodes require embedding.")
            return

        logging.info(f"Found {len(nodes_to_embed)} nodes with summaries to embed.")

        max_workers = self.num_local_workers if self.embedding_client.is_local else self.num_remote_workers
        logging.info(f"Using {max_workers} parallel workers for Pass 5.")

        self._parallel_process(
            items=nodes_to_embed,
            process_func=self._embed_one_node,
            max_workers=max_workers,
            desc="Pass 5: Embeddings"
        )

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

    def _embed_one_node(self, node: dict):
        element_id = node['elementId']
        summary = node['summary']
        # logging.info(f"Generating embedding for node: {element_id}")

        embedding = self.embedding_client.generate_embedding(summary)
        if not embedding:
            logging.warning(f"Failed to generate embedding for node {element_id}. Skipping.")
            return

        update_query = """
        MATCH (n) WHERE elementId(n) = $elementId
        SET n.summaryEmbedding = $embedding
        """
        self.neo4j_mgr.execute_autocommit_query(update_query, {"elementId": element_id, "embedding": embedding})
        # logging.info(f"-> Stored summaryEmbedding for node {element_id}")

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

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    try:
        default_workers = math.ceil(os.cpu_count() / 2)
    except (NotImplementedError, TypeError):
        default_workers = 1

    parser = argparse.ArgumentParser(description='Generate summaries and embeddings for a code graph, as per docs/code_rag_generation_plan.md.')
    parser.add_argument('index_file', help='Path to the clangd index YAML file (or a .pkl cache file).')
    parser.add_argument('project_path', help='The absolute path to the project root, used to resolve relative file paths.')
    parser.add_argument('--api', choices=['openai', 'deepseek', 'ollama'], default='deepseek', help='The LLM API to use for summarization.')
    parser.add_argument('--num-parse-workers', type=int, default=default_workers,
                        help=f'Number of parallel workers for parsing. Set to 1 for single-threaded mode. (default: {default_workers})')
    parser.add_argument('--num-local-workers', type=int, default=default_workers,
                        help=f'Number of parallel workers for local LLMs/embedding models. (default: {default_workers})')
    parser.add_argument('--num-remote-workers', type=int, default=100,
                        help='Number of parallel workers for remote LLM/embedding APIs. (default: 100)')
    args = parser.parse_args()

    try:
        llm_client = get_llm_client(args.api)
        embedding_client = get_embedding_client(args.api) # Using same API choice for now

        with Neo4jManager() as neo4j_mgr:
            if not neo4j_mgr.check_connection(): return 1
            
            # This single block now handles YAML parsing, parallelization, and caching
            logger.info("Parsing YAML index or loading from cache...")
            symbol_parser = SymbolParser(index_file_path=args.index_file)
            symbol_parser.parse(num_workers=args.num_parse_workers)

            span_provider = FunctionSpanProvider(args.project_path, symbol_parser)
            generator = RagGenerator(
                neo4j_mgr, 
                args.project_path, 
                span_provider, 
                llm_client, 
                embedding_client,
                args.num_local_workers,
                args.num_remote_workers
            )
            
            # Run all summarization and embedding passes
            generator.summarize_code_graph()

            # Finally, create the vector indices
            neo4j_mgr.create_vector_indices()

    except Exception as e:
        logging.critical(f"A critical error occurred: {e}")
        return 1

if __name__ == "__main__":
    main()
