#!/usr/bin/env python3
"""
This module provides the FunctionSpanProvider class. 

In the refactored architecture, this class acts as an ADAPTER. It takes the
pre-parsed data from a CompilationManager and uses it to enrich the in-memory
Symbol objects from a SymbolParser. 

This provides backward compatibility for components like the call graph extractor
that expect the SymbolParser object to be modified in-place.
"""

import logging
import os, gc
from typing import List, Optional

from urllib.parse import urlparse, unquote

from clangd_index_yaml_parser import SymbolParser, FunctionSpan
from compilation_manager import CompilationManager

logger = logging.getLogger(__name__)

class FunctionSpanProvider:
    """
    Acts as an adapter to match pre-parsed span data from a CompilationManager
    with Symbol objects from a SymbolParser, enriching them in-place.
    """
    def __init__(self, symbol_parser: Optional[SymbolParser], compilation_manager: CompilationManager):
        self.symbol_parser = symbol_parser
        self.compilation_manager = compilation_manager
        
        self.function_spans_by_file: dict[str, list[FunctionSpan]] = {}
        self._body_spans_by_id: dict[str, dict] = {}

        # Get pre-parsed data and immediately process it
        function_span_file_dicts = self.compilation_manager.parser.get_function_spans()
        self._process_span_dicts(function_span_file_dicts)
        self._match_function_spans()

    def _process_span_dicts(self, function_span_file_dicts: List[dict]):
        """Converts raw span dictionaries into FunctionSpan objects."""
        num_functions = sum(len(d.get('Functions', [])) for d in function_span_file_dicts)
        logger.info(f"Processing {num_functions} function definitions from {len(function_span_file_dicts)} files.")

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
        """Match clangd functions with parsed spans and enrich Symbol objects."""
        if not self.symbol_parser:
            logger.warning("No SymbolParser provided to FunctionSpanProvider; cannot enrich symbols.")
            return

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
                    # 1. Enrich the Symbol object directly for backward compatibility
                    func_symbol.body_location = spans_lookup[key].body_location
                    
                    # 2. Also build the internal map for direct lookup via get_body_span()
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
