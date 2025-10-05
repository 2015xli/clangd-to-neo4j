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
import math
import concurrent.futures
import itertools
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
class Reference:
    kind: int
    location: Location
    container_id: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Reference':
        return cls(
            kind=data['Kind'],
            location=Location.from_dict(data['Location']),
            container_id=data.get('Container', {}).get('ID')
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
    Parses a clangd YAML index file. This class separates loading from linking.
    """
    def __init__(self, log_batch_size: int = 1000, debugger: Optional[Debugger] = None):
        self.symbols: Dict[str, Symbol] = {}
        self.functions: Dict[str, Symbol] = {}
        self.unlinked_refs: List[Dict] = []
        self.log_batch_size = log_batch_size
        self.has_container_field: bool = False
        self.debugger = debugger

    def parse_yaml_file(self, index_file_path: str):
        """Phase 1: Reads and sanitizes a YAML file, then loads the data."""
        logger.info(f"Reading and sanitizing index file: {index_file_path}")
        # Read file and sanitize content into an in-memory string
        with open(index_file_path, 'r', errors='ignore') as f:
            yaml_content = f.read().replace('\t', '  ')
        
        self._load_from_string(yaml_content)

    def _load_from_string(self, yaml_content: str):
        """Loads symbols and unlinked refs from a YAML content string."""
        documents = list(yaml.safe_load_all(yaml_content))
        for doc in documents:
            if not doc:
                continue
            if 'ID' in doc and 'SymInfo' in doc:
                symbol = self._parse_symbol_doc(doc)
                self.symbols[symbol.id] = symbol
            elif 'ID' in doc and 'References' in doc:
                self.unlinked_refs.append(doc)

    def build_cross_references(self):
        """Phase 2: Links loaded references and builds the functions table."""
        logger.info("Building cross-references and populating functions table...")
        
        for ref_doc in self.unlinked_refs:
            symbol_id = ref_doc['ID']
            if symbol_id not in self.symbols:
                continue
            
            for ref_data in ref_doc['References']:
                if 'Location' in ref_data and 'Kind' in ref_data:
                    reference = Reference.from_dict(ref_data)
                    self.symbols[symbol_id].references.append(reference)
                    if not self.has_container_field and reference.container_id:
                        self.has_container_field = True

        for symbol in self.symbols.values():
            if symbol.is_function():
                self.functions[symbol.id] = symbol

        del self.unlinked_refs
        gc.collect()
        logger.info(f"Cross-referencing complete. Found {len(self.symbols)} symbols and {len(self.functions)} functions.")

    def _parse_symbol_doc(self, doc: dict) -> Symbol:
        """Parses a YAML document into a Symbol object."""
        sym_info = doc.get('SymInfo', {})
        return Symbol(
            id=doc['ID'],
            name=doc['Name'],
            kind=sym_info.get('Kind', ''),
            declaration=Location.from_dict(doc['CanonicalDeclaration']) if 'CanonicalDeclaration' in doc else None,
            definition=Location.from_dict(doc['Definition']) if 'Definition' in doc else None,
            references=[],
            scope=doc.get('Scope', ''),
            language=sym_info.get('Lang', ''),
            signature=doc.get('Signature', ''),
            return_type=doc.get('ReturnType', ''),
            type=doc.get('Type', '')
        )

# --- Parallel Parser ---

def _parse_worker(yaml_content_chunk: str, log_batch_size: int) -> Tuple[Dict[str, Symbol], List[Dict], bool]:
    """
    Worker function to parse a YAML content string chunk.
    This function is executed in a separate process.
    """
    parser = SymbolParser(log_batch_size=log_batch_size)
    parser._load_from_string(yaml_content_chunk)
    return parser.symbols, parser.unlinked_refs, parser.has_container_field

class ParallelSymbolParser(SymbolParser):
    """
    Reads and parses a clangd YAML index in parallel by chunking it in memory.
    """
    def __init__(self, index_file_path: str, log_batch_size: int = 1000, debugger: Optional[Debugger] = None):
        super().__init__(log_batch_size, debugger)
        self.index_file_path = index_file_path

    def _sanitize_and_chunk_in_memory(self, num_chunks: int) -> List[str]:
        """Reads the source file once, returning a list of sanitized in-memory chunk strings."""
        if num_chunks <= 0:
            raise ValueError("Number of chunks must be positive.")

        logger.info(f"Reading and chunking '{self.index_file_path}' into {num_chunks} in-memory chunks...")
        
        # First, count the documents to determine chunk size
        total_docs = 0
        with open(self.index_file_path, 'r', errors='ignore') as f:
            for line in f:
                if line.startswith('---'):
                    total_docs += 1
        
        if total_docs == 0:
            docs_per_chunk = 0
        else:
            docs_per_chunk = math.ceil(total_docs / num_chunks)

        if docs_per_chunk == 0:
            logger.warning("No YAML documents found. Proceeding with a single chunk.")
            with open(self.index_file_path, 'r', errors='ignore') as f:
                return [f.read().replace('\t', '  ')]

        # Now, read the file again and create the in-memory chunks
        chunks = []
        current_chunk_lines = []
        doc_count_in_chunk = 0
        with open(self.index_file_path, 'r', errors='ignore') as f_in:
            for line in f_in:
                sanitized_line = line.replace('\t', '  ')
                if sanitized_line.startswith('---'):
                    if doc_count_in_chunk >= docs_per_chunk and len(chunks) < num_chunks -1:
                        chunks.append("".join(current_chunk_lines))
                        current_chunk_lines = []
                        doc_count_in_chunk = 0
                    doc_count_in_chunk += 1
                current_chunk_lines.append(sanitized_line)
        
        if current_chunk_lines:
            chunks.append("".join(current_chunk_lines))

        logger.info(f"Successfully created {len(chunks)} in-memory chunks.")
        return chunks

    def parse(self, num_workers: int):
        """
        Phase 1 (Parallel): Reads and loads raw data from the index file in parallel.
        """
        # Create in-memory chunks from the main file
        content_chunks = self._sanitize_and_chunk_in_memory(num_workers)

        logger.info(f"Starting parallel parsing of {len(content_chunks)} chunks with {num_workers} workers...")
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
            results = executor.map(_parse_worker, content_chunks, itertools.repeat(self.log_batch_size))
            
            for i, (symbols_chunk, refs_chunk, has_container_chunk) in enumerate(results):
                logger.info(f"Merging results from chunk {i+1}/{len(content_chunks)}...")
                self.symbols.update(symbols_chunk)
                self.unlinked_refs.extend(refs_chunk)
                if has_container_chunk:
                    self.has_container_field = True
        
        logger.info("All chunks processed and merged.")