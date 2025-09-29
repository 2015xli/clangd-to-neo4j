#!/usr/bin/env python3
"""
Extract function call relationships from clangd index YAML and create Neo4j knowledge graph.

This script parses a clangd index YAML file and infers function call relationships
by analyzing symbol references within function definition boundaries using tree-sitter
to get accurate function body spans.

Key features:
1. Uses clangd index for symbol references and function metadata
2. Uses tree-sitter to get accurate function body spans for containment analysis
3. Filters references by Kind (only Kind 12 = actual usage/calls)
4. Matches functions between clangd and tree-sitter data by name and location
"""

import yaml
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------
# YAML tag handling
# -------------------------
def unknown_tag(loader, tag_suffix, node):
    return loader.construct_mapping(node)

yaml.SafeLoader.add_multi_constructor("!", unknown_tag)

@dataclass
class Location:
    file_uri: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Location':
        return cls(
            file_uri=data['FileURI'],
            start_line=data['Start']['Line'],
            start_column=data['Start']['Column'],
            end_line=data['End']['Line'],
            end_column=data['End']['Column']
        )

@dataclass
class Reference:
    kind: int
    location: Location
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Reference':
        return cls(
            kind=data['Kind'],
            location=Location.from_dict(data['Location'])
        )

@dataclass
class FunctionSpan:
    name: str
    name_location: Location
    body_location: Location
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FunctionSpan':
        return cls(
            name=data['Name'],
            name_location=Location.from_dict(data['NameLocation']),
            body_location=Location.from_dict(data['BodyLocation'])
        )

@dataclass
class Symbol:
    id: str
    name: str
    kind: str  # Function, Variable, etc.
    declaration: Optional[Location]
    definition: Optional[Location]
    references: List[Reference]
    body_location: Optional[Location] = None  # Added for function body span
    
    def is_function(self) -> bool:
        return self.kind == 'Function'

@dataclass
class CallRelation:
    caller_id: str
    caller_name: str
    callee_id: str
    callee_name: str
    call_location: Location

class ClangdCallGraphExtractor:
    def __init__(self, log_batch_size: int = 1000):
        self.symbols: Dict[str, Symbol] = {}
        self.functions: Dict[str, Symbol] = {}
        self.function_spans: List[FunctionSpan] = []
        self.log_batch_size = log_batch_size
        
    def parse_yaml(self, index_file: str) -> None:
        """Parse the clangd index YAML content from a file."""
        documents = list(load_yaml_stream(index_file))
        
        # First pass: collect all symbols
        total_documents_parsed = 0
        for doc in documents:
            if doc and 'ID' in doc and 'SymInfo' in doc:
                symbol = self._parse_symbol(doc)
                self.symbols[symbol.id] = symbol
                if symbol.is_function():
                    self.functions[symbol.id] = symbol
            total_documents_parsed += 1
            if total_documents_parsed % self.log_batch_size == 0:
                logger.info(f"Parsed {total_documents_parsed} YAML documents for symbols...")

        # Second pass: collect all references
        total_documents_parsed = 0
        for doc in documents:
            # A !References block is identified by having an ID and a References list,
            # but no SymInfo.
            if doc and 'ID' in doc and 'References' in doc and 'SymInfo' not in doc:
                self._parse_references(doc)
            total_documents_parsed += 1
            if total_documents_parsed % self.log_batch_size == 0:
                logger.info(f"Parsed {total_documents_parsed} YAML documents for references...")
    
    def parse_function_spans(self, spans_yaml: str) -> None:
        """Parse function spans from tree-sitter output."""
        documents = list(yaml.safe_load_all(spans_yaml))
        
        self.function_spans = []
        for doc in documents:
            if doc is None:
                continue
            if 'Name' in doc and 'Kind' in doc and doc['Kind'] == 'Function':
                span = FunctionSpan.from_dict(doc)
                self.function_spans.append(span)
    
    def match_function_spans(self) -> None:
        """Match clangd functions with tree-sitter spans and add body locations."""
        # Create lookup for spans by (name, file_uri, name_location)
        spans_lookup = {}
        for span in self.function_spans:
            key = (span.name, span.name_location.file_uri, 
                   span.name_location.start_line, span.name_location.start_column)
            spans_lookup[key] = span
        
        matched_count = 0
        for func_id, func_symbol in self.functions.items():
            if func_symbol.definition:
                key = (func_symbol.name, func_symbol.definition.file_uri,
                       func_symbol.definition.start_line, func_symbol.definition.start_column)
                
                if key in spans_lookup:
                    func_symbol.body_location = spans_lookup[key].body_location
                    matched_count += 1
                else:
                    logger.warning(f"No span match found for function {func_symbol.name} at {key}")
        
        logger.info(f"Matched {matched_count} functions with body spans out of {len(self.functions)}")
    
    def load_function_spans(self, spans_file: str) -> None:
        """Load function spans precomputed by tree-sitter."""
        
        try:
            with open(spans_file, 'r') as f:
                spans_yaml = f.read()
            if spans_yaml.strip():  # Only process non-empty results
                self.parse_function_spans(spans_yaml)
                self.match_function_spans()
        except Exception as e:
            logger.warning(f"Failed to extract spans from {spans_file}: {e}")
        
        # Combine all spans
        combined_spans = "\n".join(all_spans)
        if combined_spans.strip():
            self.parse_function_spans(combined_spans)
            self.match_function_spans()
    
    def _parse_symbol(self, doc: dict) -> Symbol:
        """Parse a symbol from YAML document."""
        symbol_id = doc['ID']
        name = doc['Name']
        kind = doc['SymInfo']['Kind']
        
        declaration = None
        if 'CanonicalDeclaration' in doc:
            declaration = Location.from_dict(doc['CanonicalDeclaration'])
        
        definition = None
        if 'Definition' in doc:
            definition = Location.from_dict(doc['Definition'])
        
        return Symbol(
            id=symbol_id,
            name=name,
            kind=kind,
            declaration=declaration,
            definition=definition,
            references=[]
        )
    
    def _parse_references(self, doc: dict) -> None:
        """Parse references and add them to the corresponding symbol."""
        symbol_id = doc['ID']
        if symbol_id not in self.symbols:
            return
            
        references = []
        for ref in doc['References']:
            if 'Location' in ref and 'Kind' in ref:
                reference = Reference.from_dict(ref)
                references.append(reference)
        
        self.symbols[symbol_id].references = references
    
    def _is_location_within_function_body(self, call_loc: Location, body_loc: Location) -> bool:
        """Check if a call location is within a function's body boundaries."""
        if call_loc.file_uri != body_loc.file_uri:
            return False
        
        # Check if call is within body boundaries
        # Start boundary check (line and column)
        if call_loc.start_line > body_loc.start_line:
            start_ok = True
        elif call_loc.start_line == body_loc.start_line:
            start_ok = call_loc.start_column >= body_loc.start_column
        else:
            start_ok = False
        
        # End boundary check (line and column)  
        if call_loc.end_line < body_loc.end_line:
            end_ok = True
        elif call_loc.end_line == body_loc.end_line:
            end_ok = call_loc.end_column <= body_loc.end_column
        else:
            end_ok = False
        
        return start_ok and end_ok
        
    def _locations_match(self, loc1: Location, loc2: Location) -> bool:
        """Check if two locations refer to the same position in the same file."""
        return (loc1.file_uri == loc2.file_uri and
                loc1.start_line == loc2.start_line and
                loc1.start_column == loc2.start_column and
                loc1.end_line == loc2.end_line and
                loc1.end_column == loc2.end_column)
    
    def extract_call_relationships(self) -> List[CallRelation]:
        """Extract function call relationships from the parsed data."""
        call_relations = []
        functions_with_bodies = {fid: f for fid, f in self.functions.items() if f.body_location}
        
        if not functions_with_bodies:
            logger.warning("No functions have body locations. Did you load function spans?")
            return call_relations
        
        logger.info(f"Analyzing calls for {len(functions_with_bodies)} functions with body spans")
        
        # For each function symbol that has references
        callees_processed = 0
        for callee_function_id, callee_symbol in self.symbols.items():
            if not callee_symbol.references or not callee_symbol.is_function():
                continue
            
            # Check each reference to see if it's a function call (Kind 12) within a function body
            for reference in callee_symbol.references:
                # Only consider Kind 12 references (actual usage/calls)
                if reference.kind != 12:
                    continue
                    
                call_location = reference.location
                
                # Find which function body (if any) contains this reference
                for caller_function_id, caller_symbol in functions_with_bodies.items():
                    if self._is_location_within_function_body(call_location, caller_symbol.body_location):
                        # Filter out declaration/definition references
                        # Since we use kind:12 to indicate function call, 
                        # we don't need to filter out declaration/definition references
                        #if self._is_declaration_reference(callee_symbol, call_location):
                        #    continue
                        
                        call_relations.append(CallRelation(
                            caller_id=caller_symbol.id,
                            caller_name=caller_symbol.name,
                            callee_id=callee_symbol.id,
                            callee_name=callee_symbol.name,
                            call_location=call_location
                        ))
                        break
            callees_processed += 1
            if callees_processed % self.log_batch_size == 0:
                logger.info(f"Processed call relationships for {callees_processed} callees...")
        
        logger.info(f"Extracted {len(call_relations)} call relationships")
        return call_relations
    
    def _is_declaration_reference(self, symbol: Symbol, location: Location) -> bool:
        """Check if a reference location is actually a declaration/definition, not a call."""
        # Check against function's own declaration
        if symbol.declaration and self._locations_match(location, symbol.declaration):
            return True
        
        # Check against function's own definition  
        if symbol.definition and self._locations_match(location, symbol.definition):
            return True
        
        return False
    
    def get_call_relation_ingest_query(self, call_relations: List[CallRelation]) -> Tuple[str, Dict]:
        """
        Generates a single, parameterized Cypher query for ingesting all call relations.
        Assumes all relevant FUNCTION nodes have already been created.
        """
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
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize function name for use as Cypher variable."""
        return re.sub(r'[^a-zA-Z0-9_]', '_', name)
    
    def generate_statistics(self, call_relations: List[CallRelation]) -> str:
        """Generate statistics about the extracted call graph."""
        functions = set()
        callers = set()
        callee = set()
        recursive_calls = 0
        
        for relation in call_relations:
            functions.add(relation.caller_name)
            functions.add(relation.callee_name)
            callers.add(relation.caller_name)
            callee.add(relation.callee_name)
            
            if relation.caller_id == relation.callee_id:
                recursive_calls += 1
        
        functions_with_bodies = len([f for f in self.functions.values() if f.body_location])
        
        stats = f"""
Call Graph Statistics:
=====================
Total functions in clangd index: {len(self.functions)}
Functions with body spans: {functions_with_bodies}
Total unique functions in call graph: {len(functions)}
Functions that call others: {len(callers)}
Functions that are callee: {len(callee)}
Total call relationships: {len(call_relations)}
Recursive calls: {recursive_calls}
Functions that only call (entry points): {len(callers - callee)}
Functions that are only called (leaf functions): {len(callee - callers)}
"""
        return stats

def main():
    """Main function to demonstrate usage."""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Extract call graph from clangd index YAML')
    parser.add_argument('input_file', help='Path to clangd index YAML file')
    parser.add_argument('spans_file', help='Pre-computed spans YAML file')
    parser.add_argument('--output', '-o', help='Output JSON file path')
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    parser.add_argument('--log-batch-size', type=int, default=1000, help='Log progress every N items (default: 1000)')
    args = parser.parse_args()
    
    # Read input file
    with open(args.input_file, 'r') as f:
        yaml_content = f.read()
    
    # Extract call relationships
    extractor = ClangdCallGraphExtractor(args.log_batch_size)
    extractor.parse_yaml(args.input_file)
    
    # Load function spans
    if args.spans_file:
        with open(args.spans_file, 'r') as f:
            spans_yaml = f.read()
        # Manually convert dicts to FunctionSpan objects
        span_dicts = list(yaml.safe_load_all(spans_yaml))
        extractor.function_spans = [FunctionSpan.from_dict(d) for d in span_dicts if d]
        extractor.match_function_spans()
    else:
        logger.error("spans-file must be provided")
        return
    
    call_relations = extractor.extract_call_relationships()
    
    # Get the ingest query and params
    query, params = extractor.get_call_relation_ingest_query(call_relations)
    
    # Output
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
    
    # Show statistics if requested
    if args.stats:
        logger.info(extractor.generate_statistics(call_relations))

if __name__ == "__main__":
    main()

# Example usage without command line:
def extract_from_string(yaml_content: str, source_files: List[str] = None, spans_yaml: str = None) -> Tuple[List[CallRelation], str]:
    """Extract call relations and return both relations and Cypher code."""
    extractor = ClangdCallGraphExtractor()
    extractor.parse_yaml(yaml_content)
    
    if spans_yaml:
        extractor.parse_function_spans(spans_yaml)
        extractor.match_function_spans()
    elif source_files:
        extractor.load_function_spans_from_files(source_files)
    else:
        raise ValueError("Either source_files or spans_yaml must be provided")
    
    call_relations = extractor.extract_call_relationships()
    cypher_code = extractor.generate_neo4j_cypher(call_relations)
    return call_relations, cypher_code