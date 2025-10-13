#!/usr/bin/env python3
"""
This library module provides a class to extract and map function body spans
from a C/C++ project using tree-sitter.
"""

import logging
import gc
from collections import defaultdict

from urllib.parse import urlparse, unquote

from clangd_index_yaml_parser import SymbolParser, FunctionSpan
from tree_sitter_span_extractor import SpanExtractor

logger = logging.getLogger(__name__)

class FunctionSpanProvider:
    """
    Runs tree-sitter to parse an entire project, finds the precise body
    locations of all functions, and enriches the Symbol objects from a
    SymbolParser with this information.
    """
    def __init__(self, project_path: str, symbol_parser: SymbolParser, log_batch_size: int = 1000):
        self.project_path = project_path
        self.symbol_parser = symbol_parser
        self.log_batch_size = log_batch_size
        self.function_spans_by_file: dict[str, list[FunctionSpan]] = {}
        self._body_spans_by_id: dict[str, dict] = {}

        # Automatically run the process on initialization
        self._extract_spans_from_project()
        self._match_function_spans()

    def _extract_spans_from_project(self):
        """
        Extracts function spans directly from a project folder.
        """
        logger.info("Extracting function spans with tree-sitter...")
        span_extractor = SpanExtractor(self.log_batch_size)
        function_span_file_dicts = span_extractor.get_function_spans_from_folder(
            self.project_path,
            format="dict",
            cache_path_spec=self.symbol_parser.index_file_path
        )
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
