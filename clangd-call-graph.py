#!/usr/bin/env python3
"""
Extract function call relationships from clangd index YAML and create Neo4j knowledge graph.

This script parses a clangd index YAML file and infers function call relationships
by analyzing symbol references within function definition boundaries.

Key improvements:
1. Includes recursive function calls (self-references)
2. Filters references by Kind (only Kind 12 = actual usage/calls)
3. Uses spatial containment to determine if a reference is a call within a function
4. Handles edge cases like function signature references
"""

import yaml
import re
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
from pathlib import Path
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
class Symbol:
    id: str
    name: str
    kind: str  # Function, Variable, etc.
    declaration: Optional[Location]
    definition: Optional[Location]
    references: List[Reference]
    
    def is_function(self) -> bool:
        return self.kind == 'Function'

@dataclass
class CallRelation:
    caller_function: str
    called_function: str
    call_location: Location

class ClangdCallGraphExtractor:
    def __init__(self):
        self.symbols: Dict[str, Symbol] = {}
        self.functions: Dict[str, Symbol] = {}
        
    def parse_yaml(self, yaml_content: str) -> None:
        """Parse the clangd index YAML content."""
        documents = list(yaml.safe_load_all(yaml_content))
        
        for doc in documents:
            if doc is None:
                continue
                
            if 'ID' in doc and 'Name' in doc:
                # This is a symbol
                symbol = self._parse_symbol(doc)
                self.symbols[symbol.id] = symbol
                if symbol.is_function():
                    self.functions[symbol.id] = symbol
            elif 'ID' in doc and 'References' in doc:
                # This is a references entry
                self._parse_references(doc)
    
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
    
    def _is_location_within_function(self, call_loc: Location, func_def: Location) -> bool:
        """Check if a call location is within a function's definition boundaries."""
        if call_loc.file_uri != func_def.file_uri:
            return False
        
        # Simple line-based containment check with column consideration
        if func_def.start_line < call_loc.start_line < func_def.end_line:
            return True
        elif func_def.start_line == call_loc.start_line and func_def.start_column <= call_loc.start_column:
            if func_def.end_line > call_loc.start_line:
                return True
            elif func_def.end_line == call_loc.start_line and call_loc.end_column <= func_def.end_column:
                return True
        elif func_def.end_line == call_loc.end_line and call_loc.end_column <= func_def.end_column:
            return True
        
        return False
        
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
        
        # For each function symbol that has references
        for called_function_id, called_symbol in self.symbols.items():
            if not called_symbol.references or not called_symbol.is_function():
                continue
            
            # Check each reference to see if it's a function call (Kind 12) within a function definition
            for reference in called_symbol.references:
                # Only consider Kind 12 references (actual usage/calls)
                if reference.kind != 12:
                    continue
                    
                call_location = reference.location
                
                # Find which function (if any) contains this reference
                for caller_function_id, caller_symbol in self.functions.items():
                    if not caller_symbol.definition:
                        continue
                    
                    if self._is_location_within_function(call_location, caller_symbol.definition):
                        # Filter out declaration/definition references (not actual calls)
                        if self._is_declaration_reference(called_symbol, call_location):
                            continue
                        
                        # Include recursive calls but exclude function signature references
                        call_relations.append(CallRelation(
                            caller_function=caller_symbol.name,
                            called_function=called_symbol.name,
                            call_location=call_location
                        ))
                        break
        
        return call_relations
    
    def _is_declaration_reference(self, symbol: Symbol, location: Location) -> bool:
        """Check if a reference location is actually a declaration/definition, not a call."""
        # Check against function's own declaration
        if symbol.declaration and self._locations_match(location, symbol.declaration):
            return True
        
        # Check against function's own definition
        if symbol.definition and self._locations_match(location, symbol.definition):
            return True
        
        # Additional heuristic: if the reference is on the same line as the definition
        # but starts at or before the function definition, it's likely part of the function signature
        if symbol.definition and location.file_uri == symbol.definition.file_uri:
            if (location.start_line == symbol.definition.start_line and 
                location.start_column <= symbol.definition.start_column):
                return True
        
        return False
    
    def generate_neo4j_cypher(self, call_relations: List[CallRelation]) -> str:
        """Generate Cypher statements for Neo4j."""
        cypher_statements = []
        
        # Create unique function nodes
        functions = set()
        for relation in call_relations:
            functions.add(relation.caller_function)
            functions.add(relation.called_function)
        
        # Create function nodes
        cypher_statements.append("// Create function nodes")
        for func in sorted(functions):
            cypher_statements.append(
                f"MERGE (f_{self._sanitize_name(func)}:Function {{name: '{func}'}})"
            )
        
        cypher_statements.append("\n// Create call relationships")
        
        # Create call relationships
        for relation in call_relations:
            caller_var = f"f_{self._sanitize_name(relation.caller_function)}"
            called_var = f"f_{self._sanitize_name(relation.called_function)}"
            
            cypher_statements.append(
                f"MATCH ({caller_var}:Function {{name: '{relation.caller_function}'}}), "
                f"({called_var}:Function {{name: '{relation.called_function}'}}) "
                f"CREATE ({caller_var})-[:CALLS {{"
                f"start_line: {relation.call_location.start_line}, "
                f"start_column: {relation.call_location.start_column}, "
                f"end_line: {relation.call_location.end_line}, "
                f"end_column: {relation.call_location.end_column}, "
                f"file_uri: '{relation.call_location.file_uri}'"
                f"}}]->({called_var})"
            )
        
        return "\n".join(cypher_statements)
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize function name for use as Cypher variable."""
        return re.sub(r'[^a-zA-Z0-9_]', '_', name)
    
    def generate_statistics(self, call_relations: List[CallRelation]) -> str:
        """Generate statistics about the extracted call graph."""
        functions = set()
        callers = set()
        called = set()
        recursive_calls = 0
        
        for relation in call_relations:
            functions.add(relation.caller_function)
            functions.add(relation.called_function)
            callers.add(relation.caller_function)
            called.add(relation.called_function)
            
            if relation.caller_function == relation.called_function:
                recursive_calls += 1
        
        stats = f"""
Call Graph Statistics:
=====================
Total unique functions: {len(functions)}
Functions that call others: {len(callers)}
Functions that are called: {len(called)}
Total call relationships: {len(call_relations)}
Recursive calls: {recursive_calls}
Functions that only call (leaf callers): {len(callers - called)}
Functions that are only called (entry points): {len(called - callers)}
"""
        return stats

def main():
    """Main function to demonstrate usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract call graph from clangd index YAML')
    parser.add_argument('input_file', help='Path to clangd index YAML file')
    parser.add_argument('--output', '-o', help='Output Cypher file path')
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    
    args = parser.parse_args()
    
    # Read input file
    with open(args.input_file, 'r') as f:
        yaml_content = f.read()
    
    # Extract call relationships
    extractor = ClangdCallGraphExtractor()
    extractor.parse_yaml(yaml_content)
    call_relations = extractor.extract_call_relationships()
    
    # Generate Cypher
    cypher_code = extractor.generate_neo4j_cypher(call_relations)
    
    # Output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(cypher_code)
        print(f"Cypher code written to {args.output}")
    else:
        print(cypher_code)
    
    # Show statistics if requested
    if args.stats:
        print(extractor.generate_statistics(call_relations))

if __name__ == "__main__":
    main()

# Example usage without command line:
def extract_from_string(yaml_content: str) -> Tuple[List[CallRelation], str]:
    """Extract call relations and return both relations and Cypher code."""
    extractor = ClangdCallGraphExtractor()
    extractor.parse_yaml(yaml_content)
    call_relations = extractor.extract_call_relationships()
    cypher_code = extractor.generate_neo4j_cypher(call_relations)
    return call_relations, cypher_code