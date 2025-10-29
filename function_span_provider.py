#!/usr/bin/env python3
"""
This module provides the FunctionSpanProvider class. 

In the refactored architecture, this class acts as an ADAPTER and ENRICHER. It
takes a SymbolParser and a CompilationManager and its primary purpose is to
enrich the in-memory Symbol objects with `body_location` data.
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
    Matches pre-parsed span data from a CompilationManager with Symbol objects
    from a SymbolParser, enriching them in-place with `body_location` data.
    """
    def __init__(self, symbol_parser: Optional[SymbolParser], compilation_manager: CompilationManager):
        """
        Initializes the provider with the necessary data sources.
        No actual work is done in the constructor.
        """
        self.symbol_parser = symbol_parser
        self.compilation_manager = compilation_manager
        self.matched_symbols_count = 0

    def enrich_symbols_with_span(self):
        """
        Performs the main enrichment process. It gets function span data from the
        compilation manager, matches it against the symbols in the symbol parser,
        and attaches the `body_location` attribute to the matched Symbol objects.
        """
        if not self.symbol_parser:
            logger.warning("No SymbolParser provided to FunctionSpanProvider; cannot enrich symbols.")
            return

        function_span_file_dicts = self.compilation_manager.get_function_spans()
        
        # 1. Process raw span dictionaries into a lookup table
        spans_lookup = {}
        num_functions = sum(len(d.get('Functions', [])) for d in function_span_file_dicts)
        logger.info(f"Processing {num_functions} function definitions from {len(function_span_file_dicts)} files for enrichment.")

        for file_dict in function_span_file_dicts:
            file_uri = file_dict.get('FileURI')
            if not file_uri or 'Functions' not in file_dict:
                continue
            
            for func_data in file_dict['Functions']:
                if not func_data: continue
                span = FunctionSpan.from_dict(func_data)
                key = (span.name, file_uri, 
                       span.name_location.start_line, span.name_location.start_column)
                spans_lookup[key] = span
        
        # 2. Match symbols against the lookup table and enrich
        matched_count = 0
        for func_symbol in self.symbol_parser.functions.values():
            if func_symbol.definition:
                key = (func_symbol.name, func_symbol.definition.file_uri,
                       func_symbol.definition.start_line, func_symbol.definition.start_column)
                
                if key in spans_lookup:
                    # Enrich the Symbol object directly in-place
                    func_symbol.body_location = spans_lookup[key].body_location
                    matched_count += 1
        
        self.matched_symbols_count = matched_count
        logger.info(f"Matched and enriched {self.matched_symbols_count} functions with body spans.")

        # 3. Clean up references to free memory
        self.symbol_parser = None
        del function_span_file_dicts, spans_lookup
        gc.collect()

    def get_matched_count(self) -> int:
        """Returns the number of symbols that were successfully enriched."""
        return self.matched_symbols_count