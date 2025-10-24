#!/usr/bin/env python3
"""
This library module provides a class to extract and map function body spans
from a C/C++ project using tree-sitter.
"""

import logging
import os, gc
from collections import defaultdict
from typing import List, Optional

from urllib.parse import urlparse, unquote

from clangd_index_yaml_parser import SymbolParser, FunctionSpan
from function_span_extractor import SpanExtractor

logger = logging.getLogger(__name__)

class FunctionSpanProvider:
    """
    Runs a selected span extraction strategy (clang or treesitter) and maps the
    results to the Symbol objects from a SymbolParser.
    """
    def __init__(self, symbol_parser: SymbolParser, project_path: str, paths: List[str], 
                 log_batch_size: int = 1000, extractor_type: str = 'clang', 
                 compile_commands_path: Optional[str] = None):
        if not paths:
            raise ValueError("The 'paths' list cannot be empty.")

        self.symbol_parser = symbol_parser
        self.project_path = project_path
        self.paths = paths
        self.log_batch_size = log_batch_size
        self.extractor_type = extractor_type
        self.compile_commands_path = compile_commands_path
        
        self.function_spans_by_file: dict[str, list[FunctionSpan]] = {}
        self._body_spans_by_id: dict[str, dict] = {}

        # Automatically run the process on initialization
        self._extract_spans()
        self._match_function_spans()

    def _extract_spans(self):
        """
        Extracts function spans using the selected strategy, handling both
        full project scans and specific file/folder lists.
        """
        logger.info(f"Extracting function spans with '{self.extractor_type}' strategy...")
        span_extractor = SpanExtractor(
            log_batch_size=self.log_batch_size,
            extractor_type=self.extractor_type,
            project_path=self.project_path,
            compile_commands_path=self.compile_commands_path
        )

        # Case 1: Fast path for a single, full project directory (uses caching)
        is_full_project_scan = (
            len(self.paths) == 1 and 
            os.path.isdir(self.paths[0]) and 
            os.path.abspath(self.paths[0]) == os.path.abspath(self.project_path)
        )

        if is_full_project_scan:
            logger.info(f"Processing single project folder (full build path): {self.project_path}")
            function_span_file_dicts = span_extractor.extract_from_folder(
                self.project_path,
                format="dict",
                cache_path_spec=self.symbol_parser.index_file_path
            )
        # Case 2: A specific list of files/folders is provided (no caching)
        else:
            logger.info(f"Processing custom list of {len(self.paths)} paths (updater/partial build path)...")
            unique_files = set()
            for path in self.paths:
                if os.path.isfile(path):
                    unique_files.add(os.path.abspath(path))
                elif os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        for f in files:
                            if f.endswith(('.c', '.h')):
                                unique_files.add(os.path.join(root, f))
            
            file_list = sorted(list(unique_files))
            logger.info(f"Normalized to {len(file_list)} unique source files.")
            function_span_file_dicts = span_extractor.extract_from_files(file_list, format="dict")

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

    def _match_function_spans(self) -> None:
        """Match clangd functions with tree-sitter spans and enrich Symbol objects."""
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
                    # Enrich the Symbol object directly
                    # We don't need extra data structure to pass the body location to the call graph extractor
                    # The call graph extractor will use the body location to extract the function body
                    # But for RAG generation, we use the _body_spans_by_id map to pass the body location to the RAG generator
                    # It is actually unnecessary to have the extra map data structure, but for convienience.
                    func_symbol.body_location = spans_lookup[key].body_location
                    
                    # Also build the map for direct lookup
                    body_loc = spans_lookup[key].body_location
                    clean_path = unquote(urlparse(func_symbol.definition.file_uri).path)
                    self._body_spans_by_id[func_id] = {
                        'file_path': clean_path,
                        'start_line': body_loc.start_line,
                        'start_column': body_loc.start_column,
                        'end_line': body_loc.end_line,
                        'end_column': body_loc.end_column
                    }
                    matched_count += 1
        
        logger.info(f"Matched {matched_count} functions with body spans out of {len(self.symbol_parser.functions)} total functions.")

        # Clean up intermediate data
        # We don't need the symbol parser anymore, since we keep a dedicated data structure for the function spans in _body_spans_by_id.
        # More importantly, if the program decides to delete the symbol parser, it will not be retained by this reference.
        self.symbol_parser = None
        del self.function_spans_by_file, spans_lookup
        gc.collect()

    def get_body_span(self, function_id: str) -> dict | None:
        """
        Public method to retrieve the body span for a given function ID.
        """
        return self._body_spans_by_id.get(function_id)

    def get_matched_function_ids(self) -> list[str]:
        """Returns a list of all function IDs that have a matched body span."""
        return list(self._body_spans_by_id.keys())
