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
import gc
from utils import Debugger # Import Debugger

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
    container_id: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Reference':
        return cls(
            kind=data['Kind'],
            location=Location.from_dict(data['Location']),
            container_id=data.get('Container', {}).get('ID') # Extraction logic
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
    def __init__(self, log_batch_size: int = 1000, nonstream_parsing: bool = False, debugger: Optional[Debugger] = None):
        self.symbols: Dict[str, Symbol] = {}
        self.functions: Dict[str, Symbol] = {}
        self.log_batch_size = log_batch_size
        self.has_container_field: bool = False
        self.nonstream_parsing = nonstream_parsing
        self.debugger = debugger

    def parse_yaml_file(self, index_file_path: str):
        """Reads a YAML file and parses its content using the selected strategy."""
        logger.info(f"Reading clangd index file: {index_file_path}")
        with open(index_file_path, 'r', errors='ignore') as f:
            yaml_content = f.read()
        if self.debugger:
            self.debugger.memory_snapshot("Memory after reading entire YAML file into string")
        
        if self.nonstream_parsing:
            self.parse_yaml_content_nonstreaming(yaml_content)
        else:
            self.parse_yaml_content_streaming(yaml_content)

        # Explicitly free memory of the raw YAML content string
        del yaml_content
        gc.collect()

    def parse_yaml_content_nonstreaming(self, yaml_content: str):
        """
        Parses the string content of a clangd index YAML using a two-pass approach.
        This loads all documents into memory first.
        """
        logger.info("Parsing YAML content (non-streaming, two-pass)...")
        documents = list(yaml.safe_load_all(yaml_content))
        if self.debugger:
            self.debugger.memory_snapshot("Memory after loading all YAML documents into list of Python objects (non-streaming)")

        # Free memory from the raw YAML string as it's no longer needed
        del yaml_content
        gc.collect()
        
        # Pass 1: Collect all symbols
        logger.info("Pass 1: Parsing symbols...")
        total_documents_parsed = 0
        for doc in documents:
            if doc and 'ID' in doc and 'SymInfo' in doc:
                symbol = self._parse_symbol(doc)
                self.symbols[symbol.id] = symbol
                if symbol.is_function():
                    self.functions[symbol.id] = symbol
            total_documents_parsed += 1
            if total_documents_parsed % self.log_batch_size == 0:
                print(".", end="", flush=True)
        print(flush=True)
        logger.info(f"Parsed {total_documents_parsed} YAML documents for symbols.")

        # Pass 2: Collect all references
        logger.info("Pass 2: Parsing references...")
        total_documents_parsed = 0
        for doc in documents:
            if doc and 'ID' in doc and 'References' in doc and 'SymInfo' not in doc:
                self._parse_references(doc)
            total_documents_parsed += 1
            if total_documents_parsed % self.log_batch_size == 0:
                print(".", end="", flush=True)
        print(flush=True)
        logger.info(f"Parsed {total_documents_parsed} YAML documents for references.")
        
        logger.info(f"Finished parsing. Found {len(self.symbols)} symbols and {len(self.functions)} functions.")
        if self.debugger:
            self.debugger.memory_snapshot("Memory after populating self.symbols and self.functions (non-streaming)")

    def parse_yaml_content_streaming(self, yaml_content: str):
        """
        Parses the string content of a clangd index YAML in a single pass (streaming).
        Assumes !Symbol documents appear before !Refs documents that refer to them.
        """
        logger.info("Parsing YAML content (streaming, single-pass)...")
        
        documents_generator = yaml.safe_load_all(yaml_content)
        
        total_documents_processed = 0
        for doc in documents_generator:
            if not doc:
                continue
            
            # Process Symbols
            if 'ID' in doc and 'SymInfo' in doc:
                symbol = self._parse_symbol(doc)
                self.symbols[symbol.id] = symbol
                if symbol.is_function():
                    self.functions[symbol.id] = symbol
            # Process References
            elif 'ID' in doc and 'References' in doc and 'SymInfo' not in doc:
                self._parse_references(doc)
            
            total_documents_processed += 1
            if total_documents_processed % self.log_batch_size == 0:
                print(".", end="", flush=True)
        print(flush=True)
        logger.info(f"Processed {total_documents_processed} YAML documents.")
        
        logger.info(f"Finished parsing. Found {len(self.symbols)} symbols and {len(self.functions)} functions.")
        if self.debugger:
            self.debugger.memory_snapshot("Memory after populating self.symbols and self.functions (streaming)")

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
                if not self.has_container_field and reference.container_id: # Condition to set the flag
                    self.has_container_field = True
    
        self.symbols[symbol_id].references = references