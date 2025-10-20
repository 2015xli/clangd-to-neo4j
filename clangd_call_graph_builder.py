#!/usr/bin/env python3
"""
This module consumes parsed clangd symbol data and function span data
to produce a function-level call graph.
"""

import yaml
import re
from typing import Dict, List, Tuple, Optional, Any
import logging
import gc
import os
import argparse
import json
import math

import input_params
from tree_sitter_span_extractor import SpanExtractor
from clangd_index_yaml_parser import (
    SymbolParser, Symbol, Location, Reference, FunctionSpan, RelativeLocation, CallRelation
)
from neo4j_manager import Neo4jManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Base Extractor Class ---
class BaseClangdCallGraphExtractor:
    def __init__(self, symbol_parser: SymbolParser, log_batch_size: int = 1000, ingest_batch_size: int = 1000):
        self.symbol_parser = symbol_parser
        self.log_batch_size = log_batch_size
        self.ingest_batch_size = ingest_batch_size

    def get_call_relation_ingest_query(self, call_relations: List[CallRelation]) -> Tuple[str, Dict]:
        """Generates a single, parameterized Cypher query for ingesting all call relations."""
        if not call_relations:
            return ("", {})
        query = """
        UNWIND $relations as relation
        MATCH (caller:FUNCTION {id: relation.caller_id})
        MATCH (callee:FUNCTION {id: relation.callee_id})
        MERGE (caller)-[:CALLS]->(callee)
        """
        params = {
            "relations": [
                {"caller_id": r.caller_id, "callee_id": r.callee_id} for r in call_relations
            ]
        }
        return (query, params)
    
    def generate_statistics(self, call_relations: List[CallRelation]) -> str:
        """Generate statistics about the extracted call graph."""
        functions_in_graph = set()
        callers = set()
        callees = set()
        recursive_calls = 0
        
        for relation in call_relations:
            functions_in_graph.add(relation.caller_name)
            functions_in_graph.add(relation.callee_name)
            callers.add(relation.caller_name)
            callees.add(relation.callee_name)
            if relation.caller_id == relation.callee_id:
                recursive_calls += 1
        
        functions_with_bodies = len([f for f in self.symbol_parser.functions.values() if f.body_location])
        
        stats = f"""
Call Graph Statistics:
=====================
Total functions in clangd index: {len(self.symbol_parser.functions)}
Functions with body spans: {functions_with_bodies}
Total unique functions in call graph: {len(functions_in_graph)}
Functions that call others: {len(callers)}
Functions that are called: {len(callees)}
Total call relationships: {len(call_relations)}
Recursive calls: {recursive_calls}
Functions that only call (entry points): {len(callers - callees)}
Functions that are only called (leaf functions): {len(callees - callers)}
"""
        return stats

    def ingest_call_relations(self, call_relations: List[CallRelation], neo4j_manager: Optional[Neo4jManager] = None) -> None:
        """
        Ingests call relations into Neo4j in batches, or writes them to a CQL file.
        """
        if not call_relations:
            logger.info("No call relations to ingest.")
            return

        total_relations = len(call_relations)
        logger.info(f"Preparing {total_relations} call relationships for batched ingestion (batch size: {self.ingest_batch_size}).")

        output_file_path = "generated_call_graph_cypher_queries.cql"
        file_mode = 'w'
        
        total_rels_created = 0

        for i in range(0, total_relations, self.ingest_batch_size):
            batch = call_relations[i:i + self.ingest_batch_size]
            query_template, params = self.get_call_relation_ingest_query(batch)

            if neo4j_manager:
                all_counters = neo4j_manager.process_batch([(query_template, params)])
                for counters in all_counters:
                    total_rels_created += counters.relationships_created
            else:
                formatted_query = query_template.strip()
                formatted_params = json.dumps(params, indent=2)
                with open(output_file_path, file_mode) as f:
                    f.write(f"// Batch {i // self.ingest_batch_size + 1} \n")
                    f.write(f"{formatted_query};\n")
                    f.write(f"// PARAMS: {formatted_params}\n")
                file_mode = 'a'

            print(".", end="", flush=True)

        print(flush=True)
        logger.info(f"Finished processing {total_relations} call relationships in batches.")
        if neo4j_manager:
            logger.info(f"  Total CALLS relationships created: {total_rels_created}")
        else:
            logger.info(f"Batched Cypher queries written to {output_file_path}")

# --- Extractor Without Container ---
class ClangdCallGraphExtractorWithoutContainer(BaseClangdCallGraphExtractor):
    def __init__(self, symbol_parser: SymbolParser, log_batch_size: int = 1000, ingest_batch_size: int = 1000):
        super().__init__(symbol_parser, log_batch_size, ingest_batch_size)

    def _is_location_within_function_body(self, call_loc: Location, body_loc: RelativeLocation, body_file_uri: str) -> bool:
        if call_loc.file_uri != body_file_uri:
            return False
        
        start_ok = (call_loc.start_line > body_loc.start_line) or \
                   (call_loc.start_line == body_loc.start_line and call_loc.start_column >= body_loc.start_column)
        
        end_ok = (call_loc.end_line < body_loc.end_line) or \
                 (call_loc.end_line == body_loc.end_line and call_loc.end_column <= body_loc.end_column)
        
        return start_ok and end_ok

    def extract_call_relationships(self) -> List[CallRelation]:
        """Extract function call relationships from the parsed data using spatial indexing."""
        call_relations = []
        functions_with_bodies = {fid: f for fid, f in self.symbol_parser.functions.items() if f.body_location}
        
        if not functions_with_bodies:
            logger.warning("No functions have body locations. Did you load function spans?")
            return call_relations
        
        logger.info(f"Analyzing calls for {len(functions_with_bodies)} functions with body spans using optimized lookup")

        file_to_function_bodies_index: Dict[str, List[Tuple[RelativeLocation, Symbol]]] = {}
        for caller_symbol in functions_with_bodies.values():
            if caller_symbol.body_location and caller_symbol.definition:
                file_uri = caller_symbol.definition.file_uri
                file_to_function_bodies_index.setdefault(file_uri, []).append((caller_symbol.body_location, caller_symbol))

        for file_uri in file_to_function_bodies_index:
            file_to_function_bodies_index[file_uri].sort(key=lambda item: item[0].start_line)
        logger.info(f"Built spatial index for {len(file_to_function_bodies_index)} files.")
        del functions_with_bodies
        gc.collect()

        # Determine the correct call kinds to look for based on the clangd version.
        if self.symbol_parser.has_call_kind:
            # Kind 20: Call | Reference
            # Kind 28: Call | Reference | Spelled
            valid_call_kinds = [20, 28]
        else:
            # Kind 4: Reference
            # Kind 12: Reference | Spelled
            valid_call_kinds = [4, 12]
        
        logger.info(f"Using call kinds for detection: {valid_call_kinds}")

        logger.info("Processing call relationships for callees...")
        for callee_symbol in self.symbol_parser.symbols.values():
            if not callee_symbol.references or not callee_symbol.is_function():
                continue
            
            for reference in callee_symbol.references:
                if reference.kind not in valid_call_kinds:
                    continue
                
                call_location = reference.location
                if call_location.file_uri in file_to_function_bodies_index:
                    for body_loc, caller_symbol in file_to_function_bodies_index[call_location.file_uri]:
                        if self._is_location_within_function_body(call_location, body_loc, call_location.file_uri):
                            call_relations.append(CallRelation(
                                caller_id=caller_symbol.id,
                                caller_name=caller_symbol.name,
                                callee_id=callee_symbol.id,
                                callee_name=callee_symbol.name,
                                call_location=call_location
                            ))
                            break

        logger.info(f"Extracted {len(call_relations)} call relationships")
        del file_to_function_bodies_index
        gc.collect()

        return call_relations
    
class ClangdCallGraphExtractorWithContainer(BaseClangdCallGraphExtractor):
    def extract_call_relationships(self) -> List[CallRelation]:
        call_relations = []
        logger.info("Extracting call relationships using Container field...")

        for callee_symbol in self.symbol_parser.symbols.values():
            if not callee_symbol.references or not callee_symbol.is_function():
                continue
            
            for reference in callee_symbol.references:
                if reference.container_id and reference.container_id != '0000000000000000' and reference.kind in [20, 28]:
                    caller_id = reference.container_id
                    caller_symbol = self.symbol_parser.symbols.get(caller_id)
                    
                    if caller_symbol and caller_symbol.is_function():
                        call_relations.append(CallRelation(
                            caller_id=caller_symbol.id,
                            caller_name=caller_symbol.name,
                            callee_id=callee_symbol.id,
                            callee_name=callee_symbol.name,
                            call_location=reference.location
                        ))
        
        logger.info(f"Extracted {len(call_relations)} call relationships")
        return call_relations

import input_params
from pathlib import Path

def main():
    """Main function to demonstrate usage."""
    parser = argparse.ArgumentParser(description='Extract call graph from clangd index YAML')

    # Add arguments specific to this script
    # 'index_file', type=Path, help='Path to clangd index YAML file (or a .pkl cache file).'
    # 'project_path', type=Path, help='Path to a project directory to scan for function spans.'
    input_params.add_core_input_args(parser)
    
    # Add argument groups from the centralized module
    input_params.add_worker_args(parser)
    input_params.add_batching_args(parser)
    input_params.add_logistic_args(parser)

    args = parser.parse_args()

    # Resolve paths and convert back to strings
    args.index_file = str(args.index_file.resolve())
    args.project_path = str(args.project_path.resolve())

    # Set default for ingest_batch_size if not provided
    if args.ingest_batch_size is None:
        args.ingest_batch_size = args.cypher_tx_size # A sensible default for this script
    
    # --- Phase 0: Load, Parse, and Link Symbols ---
    logger.info("\n--- Starting Phase 0: Loading, Parsing, and Linking Symbols ---")
    symbol_parser = SymbolParser(
        index_file_path=args.index_file,
        log_batch_size=args.log_batch_size
    )
    symbol_parser.parse(num_workers=args.num_parse_workers)
    logger.info("--- Finished Phase 0 ---")

    # 2. Create extractor based on available features
    if symbol_parser.has_container_field:
        extractor = ClangdCallGraphExtractorWithContainer(symbol_parser, args.log_batch_size, args.ingest_batch_size)
        logger.info("Using ClangdCallGraphExtractorWithContainer (new format detected).")
    else:
        extractor = ClangdCallGraphExtractorWithoutContainer(symbol_parser, args.log_batch_size, args.ingest_batch_size)
        logger.info("Using ClangdCallGraphExtractorWithoutContainer (old format detected).")
        from function_span_provider import FunctionSpanProvider
        if os.path.isdir(args.project_path):
            # The provider runs tree-sitter and enriches the symbol_parser object in place.
            FunctionSpanProvider(symbol_parser=symbol_parser, paths=[args.project_path], log_batch_size=args.log_batch_size)
        else:
            logger.error(f"Project path for span extraction not found or not a directory: {args.project_path}")
            return
    
    # 3. Extract call relationships
    call_relations = extractor.extract_call_relationships()
    
    # 4. Ingest or write to file
    if args.ingest:
        with Neo4jManager() as neo4j_mgr:
            if neo4j_mgr.check_connection():
                if not neo4j_mgr.verify_project_path(args.project_path):
                    return
                extractor.ingest_call_relations(call_relations, neo4j_manager=neo4j_mgr)
    else:
        # When not ingesting, write to a default CQL file.
        # The ingest_call_relations method handles this logic.
        extractor.ingest_call_relations(call_relations, neo4j_manager=None)
    
    # 5. Generate statistics
    if args.stats:
        stats = extractor.generate_statistics(call_relations)
        logger.info(stats)

if __name__ == "__main__":
    main()
