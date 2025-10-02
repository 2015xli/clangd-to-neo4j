#!/usr/bin/env python3
"""
This module consumes parsed clangd symbol data and function span data
to produce a function-level call graph.
"""

import yaml
import re
from typing import Dict, List, Tuple, Optional
import logging
import gc
import os
import argparse
import json

from tree_sitter_span_extractor import SpanExtractor
from clangd_index_yaml_parser import (
    SymbolParser, Symbol, Location, Reference, FunctionSpan, RelativeLocation, CallRelation
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Base Extractor Class ---
class BaseClangdCallGraphExtractor:
    def __init__(self, symbol_parser: SymbolParser, log_batch_size: int = 1000):
        self.symbol_parser = symbol_parser
        self.log_batch_size = log_batch_size

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

# --- Extractor Without Container ---
class ClangdCallGraphExtractorWithoutContainer(BaseClangdCallGraphExtractor):
    def __init__(self, symbol_parser: SymbolParser, log_batch_size: int = 1000):
        super().__init__(symbol_parser, log_batch_size)
        self.function_spans_by_file: Dict[str, List[FunctionSpan]] = {}

    def parse_function_spans(self, spans_yaml: str) -> None:
        """Parse function spans from tree-sitter output (new format)."""
        documents = list(yaml.safe_load_all(spans_yaml))
        
        self.function_spans_by_file = {}
        for doc in documents:
            if doc is None or 'FileURI' not in doc or 'Functions' not in doc:
                continue
            
            file_uri = doc['FileURI']
            spans_in_file = []
            
            for func_data in doc['Functions']:
                if 'BodyLocation' in func_data and func_data['BodyLocation']:
                    span = FunctionSpan.from_dict(func_data)
                    spans_in_file.append(span)

            if spans_in_file:
                self.function_spans_by_file[file_uri] = spans_in_file

    def match_function_spans(self) -> None:
        """Match clangd functions with tree-sitter spans and add body locations."""
        spans_lookup = {}
        for file_uri, spans_in_file in self.function_spans_by_file.items():
            for span in spans_in_file:
                key = (span.name, file_uri, 
                       span.name_location.start_line, span.name_location.start_column)
                spans_lookup[key] = span
        
        matched_count = 0
        for func_id, func_symbol in self.symbol_parser.functions.items():
            if func_symbol.definition:
                key = (func_symbol.name, func_symbol.definition.file_uri,
                       func_symbol.definition.start_line, func_symbol.definition.start_column)
                
                if key in spans_lookup:
                    func_symbol.body_location = spans_lookup[key].body_location
                    matched_count += 1
                else:
                    logger.warning(f"No span match found for function {func_symbol.name} at {key}")
        
        logger.info(f"Matched {matched_count} functions with body spans out of {len(self.symbol_parser.functions)}")

        # Free memory
        del self.function_spans_by_file
        del spans_lookup
        gc.collect()

    def load_function_spans(self, spans_file: str) -> None:
        """Load function spans precomputed by tree-sitter."""
        try:
            with open(spans_file, 'r') as f:
                spans_yaml = f.read()
            if spans_yaml.strip():
                self.parse_function_spans(spans_yaml)
                self.match_function_spans()
        except Exception as e:
            logger.warning(f"Failed to extract spans from {spans_file}: {e}")

    def load_spans_from_project(self, project_path: str) -> None:
        """
        Extracts function spans directly from a project folder, then matches them.
        """
        logger.info("Extracting function spans with tree-sitter...")
        span_extractor = SpanExtractor(self.log_batch_size)
        function_span_file_dicts = span_extractor.get_function_spans_from_folder(project_path, format="dict")
        del span_extractor
        gc.collect()

        num_functions = sum(len(d.get('Functions', [])) for d in function_span_file_dicts)
        logger.info(f"Found {num_functions} function definitions in {len(function_span_file_dicts)} files.")

        spans_by_file = {}
        for file_dict in function_span_file_dicts:
            file_uri = file_dict.get('FileURI')
            if not file_uri or 'Functions' not in file_dict:
                continue
            
            spans_in_file = [FunctionSpan.from_dict(func_data) for func_data in file_dict['Functions'] if func_data]
            if spans_in_file:
                spans_by_file[file_uri] = spans_in_file
        
        self.function_spans_by_file = spans_by_file
        del function_span_file_dicts
        gc.collect()
        
        self.match_function_spans()

    def _is_location_within_function_body(self, call_loc: Location, body_loc: RelativeLocation, body_file_uri: str) -> bool:
        """Check if a call location is within a function's body boundaries."""
        if call_loc.file_uri != body_file_uri:
            return False
        
        if call_loc.start_line > body_loc.start_line:
            start_ok = True
        elif call_loc.start_line == body_loc.start_line:
            start_ok = call_loc.start_column >= body_loc.start_column
        else:
            start_ok = False
        
        if call_loc.end_line < body_loc.end_line:
            end_ok = True
        elif call_loc.end_line == body_loc.end_line:
            end_ok = call_loc.end_column <= body_loc.end_column
        else:
            end_ok = False
        
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
        for caller_function_id, caller_symbol in functions_with_bodies.items():
            if caller_symbol.body_location is not None and caller_symbol.definition is not None:
                file_uri = caller_symbol.definition.file_uri
                if file_uri not in file_to_function_bodies_index:
                    file_to_function_bodies_index[file_uri] = []
                file_to_function_bodies_index[file_uri].append( (caller_symbol.body_location, caller_symbol) )

        for file_uri in file_to_function_bodies_index:
            file_to_function_bodies_index[file_uri].sort(key=lambda item: item[0].start_line)
        logger.info(f"Built spatial index for {len(file_to_function_bodies_index)} files.")
        del functions_with_bodies
        gc.collect()

        logger.info("Processing call relationships for callees...")
        callees_processed = 0
        for callee_function_id, callee_symbol in self.symbol_parser.symbols.items():
            if not callee_symbol.references or not callee_symbol.is_function():
                continue
            
            for reference in callee_symbol.references:
                if reference.kind != 12 and reference.kind != 4:
                    continue
                call_location = reference.location
                found_caller_symbol = None
                if call_location.file_uri in file_to_function_bodies_index:
                    potential_callers_in_file = file_to_function_bodies_index[call_location.file_uri]
                    for body_loc, caller_symbol in potential_callers_in_file:
                        if self._is_location_within_function_body(call_location, body_loc, call_location.file_uri):
                            found_caller_symbol = caller_symbol
                            break
                
                if found_caller_symbol is not None:
                    call_relations.append(CallRelation(
                        caller_id=found_caller_symbol.id,
                        caller_name=found_caller_symbol.name,
                        callee_id=callee_symbol.id,
                        callee_name=callee_symbol.name,
                        call_location=call_location
                    ))

            callees_processed += 1
            if callees_processed % self.log_batch_size == 0:
                print(".", end="", flush=True)
        print(flush=True)
        logger.info(f"Processed call relationships for {callees_processed} callees.")
        
        logger.info(f"Extracted {len(call_relations)} call relationships")
        del file_to_function_bodies_index
        gc.collect()

        return call_relations
    

class ClangdCallGraphExtractorWithContainer(BaseClangdCallGraphExtractor):
    def __init__(self, symbol_parser: SymbolParser, log_batch_size: int = 1000):
        super().__init__(symbol_parser, log_batch_size)

    def extract_call_relationships(self) -> List[CallRelation]:
        call_relations = []
        logger.info("Extracting call relationships using Container field...")

        logger.info("Processing call relationships for callees...")
        callees_processed = 0
        for callee_function_id, callee_symbol in self.symbol_parser.symbols.items():
            if not callee_symbol.references or not callee_symbol.is_function():
                continue
            
            for reference in callee_symbol.references:
                if reference.container_id == '0000000000000000': # Skip if container is '0'
                    continue
                # Check for new RefKind::Call values (28 or 20) and Container field
                if reference.container_id and (reference.kind == 28 or reference.kind == 20):
                    caller_id = reference.container_id
                    caller_symbol = self.symbol_parser.symbols.get(caller_id)
                    
                    assert caller_symbol and caller_symbol.is_function(), \
                        f"Container ID {caller_id} for callee {callee_symbol.id} is not a valid function symbol."

                    if caller_symbol and caller_symbol.is_function():
                        call_relations.append(CallRelation(
                            caller_id=caller_symbol.id,
                            caller_name=caller_symbol.name,
                            callee_id=callee_symbol.id,
                            callee_name=callee_symbol.name,
                            call_location=reference.location
                        ))

            callees_processed += 1
            if callees_processed % self.log_batch_size == 0:
                print(".", end="", flush=True)
        print(flush=True)
        logger.info(f"Processed call relationships for {callees_processed} callees.")
        
        logger.info(f"Extracted {len(call_relations)} call relationships")
        return call_relations

def main():
    """Main function to demonstrate usage."""
    parser = argparse.ArgumentParser(description='Extract call graph from clangd index YAML')
    parser.add_argument('input_file', help='Path to clangd index YAML file')
    parser.add_argument('span_path', help='Path to a pre-computed spans YAML file, or a project directory to scan')
    parser.add_argument('--nonstream-parsing', action='store_true',
                        help='Use non-streaming (two-pass) YAML parsing for SymbolParser')
    parser.add_argument('--output', '-o', help='Output JSON file path')
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    parser.add_argument('--log-batch-size', type=int, default=1000, help='Log progress every N items (default: 1000)')
    args = parser.parse_args()
    
    # 1. Parse the clangd index file
    symbol_parser = SymbolParser(args.log_batch_size)
    symbol_parser.parse_yaml_file(args.input_file)

    # 2. Create extractor based on available features
    if symbol_parser.has_container_field:
        extractor = ClangdCallGraphExtractorWithContainer(symbol_parser, args.log_batch_size)
        logger.info("Using ClangdCallGraphExtractorWithContainer (new format detected).")
    else:
        extractor = ClangdCallGraphExtractorWithoutContainer(symbol_parser, args.log_batch_size)
        logger.info("Using ClangdCallGraphExtractorWithoutContainer (old format detected).")
        # Load function spans only if needed
        if os.path.isdir(args.span_path):
            extractor.load_spans_from_project(args.span_path)
        elif os.path.isfile(args.span_path):
            extractor.load_function_spans(args.span_path)
        else:
            logger.error(f"Span path not found or is not a valid file/directory: {args.span_path}")
            return
    
    # 3. Extract call relationships
    call_relations = extractor.extract_call_relationships()
    
    # 4. Get the ingest query and clean up
    query, params = extractor.get_call_relation_ingest_query(call_relations)
    stats = extractor.generate_statistics(call_relations)
    del symbol_parser
    del extractor
    gc.collect()

    # 5. Output
    output_data = {
        "query": query,
        "params": params
    }
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        logger.info(f"Cypher query and parameters written to {args.output}")
    else:
        logger.info(json.dumps(output_data, indent=2))
    
    if args.stats:
        logger.info(stats)

if __name__ == "__main__":
    main()