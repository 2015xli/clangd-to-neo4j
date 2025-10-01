#!/usr/bin/env python3
"""
This module provides a parser for clangd's YAML index format.

It defines the common data classes for symbols, references, and locations,
and provides a SymbolParser class to read a clangd index file into an
in-memory collection of symbol objects.
"""

import yaml
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# --- YAML tag handling ---
def unknown_tag(loader, tag_suffix, node):
    return loader.construct_mapping(node)

yaml.SafeLoader.add_multi_constructor("!", unknown_tag)

# --- Common Data Classes ---

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
class RelativeLocation:
    start_line: int
    start_column: int
    end_line: int
    end_column: int

    @classmethod
    def from_dict(cls, data: dict) -> 'RelativeLocation':
        return cls(
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
    name_location: RelativeLocation
    body_location: RelativeLocation
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FunctionSpan':
        return cls(
            name=data['Name'],
            name_location=RelativeLocation.from_dict(data['NameLocation']),
            body_location=RelativeLocation.from_dict(data['BodyLocation'])
        )

@dataclass
class Symbol:
    id: str
    name: str
    kind: str
    declaration: Optional[Location]
    definition: Optional[Location]
    references: List[Reference]
    scope: str = ""
    language: str = ""
    signature: str = ""
    return_type: str = ""
    type: str = ""
    body_location: Optional[RelativeLocation] = None
    
    def is_function(self) -> bool:
        return self.kind == 'Function'

@dataclass
class CallRelation:
    caller_id: str
    caller_name: str
    callee_id: str
    callee_name: str
    call_location: Location

# --- Symbol Parser ---

class SymbolParser:
    """
    Parses a clangd YAML index file into an in-memory dictionary of symbols.
    """
    def __init__(self, log_batch_size: int = 1000):
        self.symbols: Dict[str, Symbol] = {}
        self.functions: Dict[str, Symbol] = {}
        self.log_batch_size = log_batch_size

    def parse_yaml_file(self, index_file_path: str):
        """Reads a YAML file and parses its content."""
        logger.info(f"Reading clangd index file: {index_file_path}")
        with open(index_file_path, 'r', errors='ignore') as f:
            yaml_content = f.read()
        self.parse_yaml_content(yaml_content)

    def parse_yaml_content(self, yaml_content: str):
        """
        Parses the string content of a clangd index YAML.
        This is a two-pass process to handle forward references.
        """
        logger.info("Parsing YAML content...")
        documents = list(yaml.safe_load_all(yaml_content))
        
        # Pass 1: Collect all symbols
        logger.info("Starting Pass 1: Parsing Symbols")
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

        # Pass 2: Collect all references
        logger.info("Starting Pass 2: Parsing References")
        total_documents_parsed = 0
        for doc in documents:
            if doc and 'ID' in doc and 'References' in doc and 'SymInfo' not in doc:
                self._parse_references(doc)
            total_documents_parsed += 1
            if total_documents_parsed % self.log_batch_size == 0:
                logger.info(f"Parsed {total_documents_parsed} YAML documents for references...")
        
        logger.info(f"Finished parsing. Found {len(self.symbols)} symbols and {len(self.functions)} functions.")

    def _parse_symbol(self, doc: dict) -> Symbol:
        """Parse a symbol from YAML document."""
        symbol_id = doc['ID']
        name = doc['Name']
        sym_info = doc.get('SymInfo', {})
        
        declaration = None
        if 'CanonicalDeclaration' in doc:
            declaration = Location.from_dict(doc['CanonicalDeclaration'])
        
        definition = None
        if 'Definition' in doc:
            definition = Location.from_dict(doc['Definition'])
        
        return Symbol(
            id=symbol_id,
            name=name,
            kind=sym_info.get('Kind', ''),
            declaration=declaration,
            definition=definition,
            references=[],
            scope=doc.get('Scope', ''),
            language=sym_info.get('Lang', ''),
            signature=doc.get('Signature', ''),
            return_type=doc.get('ReturnType', ''),
            type=doc.get('Type', '')
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
