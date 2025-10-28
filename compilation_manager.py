#!/usr/bin/env python3
"""
This module provides the CompilationManager, a class responsible for orchestrating
the parsing of source code, managing different parsing strategies (e.g., clang vs.
treesitter), and handling the caching of parsing results.
"""

import os
import logging
import gc
import pickle
from typing import Optional, List, Tuple, Dict, Set

# Optional Git import
try:
    import git
except ImportError:
    git = None

from compilation_parser import CompilationParser, ClangParser, TreesitterParser
from git_manager import get_git_repo

logger = logging.getLogger(__name__)

# --- Caching Logic ---

class ParserCache:
    """Handles caching of extracted data (function spans and include relations)."""
    def __init__(self, folder: str, cache_path_spec: Optional[str] = None):
        self.folder = folder
        self.repo = get_git_repo(folder)
        self.cache_path = self._get_cache_path(cache_path_spec)
        self.source_files: Optional[list[str]] = None

    def _get_cache_path(self, cache_path_spec: Optional[str]) -> str:
        if cache_path_spec is None:
            base_name = os.path.basename(os.path.normpath(self.folder))
            return f"parser_cache_{base_name}.pkl"
        if os.path.isdir(cache_path_spec):
            base_name = os.path.basename(os.path.normpath(self.folder))
            return os.path.join(cache_path_spec, f"parser_cache_{base_name}.pkl")
        base_path, _ = os.path.splitext(cache_path_spec)
        return base_path + ".compilation_parser.pkl"

    def get_source_files(self) -> list[str]:
        """Scans the project folder to get all .c and .h files."""
        if self.source_files is None:
            logger.info("Scanning project folder for source files...")
            files = []
            for root, _, fs in os.walk(self.folder):
                for f in fs:
                    if f.endswith((".c", ".h")):
                        files.append(os.path.join(root, f))
            self.source_files = files
        return self.source_files

    def is_valid(self) -> bool:
        """Checks if the cache is present and still valid (via git hash or mtime)."""
        if not os.path.exists(self.cache_path): return False
        try:
            with open(self.cache_path, "rb") as f: cached_data = pickle.load(f)
        except (pickle.UnpicklingError, EOFError):
            logger.warning("Cache file %s is corrupted. Ignoring.", self.cache_path); return False
        
        if self.repo and not self.repo.is_dirty():
            if cached_data.get("type") == "git" and cached_data.get("commit_hash") == self.repo.head.object.hexsha:
                logger.info("Git-based parser cache is valid."); return True
        else: # Fallback to mtime
            cache_mtime = os.path.getmtime(self.cache_path)
            for file_path in self.get_source_files():
                if os.path.getmtime(file_path) > cache_mtime:
                    logger.info(f"Cache is stale due to modified file: {file_path}"); return False
            logger.info("Mtime-based parser cache is valid."); return True
        return False

    def load(self) -> Tuple[List[Dict], Set[Tuple[str, str]]]:
        """Loads extracted data (function spans, include relations) from the cache."""
        logger.info(f"Loading extracted data from cache: {self.cache_path}")
        with open(self.cache_path, "rb") as f: 
            loaded_data = pickle.load(f)
            return loaded_data.get("function_spans", []), loaded_data.get("include_relations", set())

    def save(self, function_spans: List[Dict], include_relations: Set[Tuple[str, str]]):
        """Saves extracted data to the cache."""
        logger.info(f"Saving new extracted data to cache: {self.cache_path}")
        cache_obj = {
            "function_spans": function_spans,
            "include_relations": include_relations
        }
        if self.repo: 
            cache_obj["type"] = "git"
            cache_obj["commit_hash"] = self.repo.head.object.hexsha
        else: 
            cache_obj["type"] = "mtime"
        with open(self.cache_path, "wb") as f: pickle.dump(cache_obj, f)

# --- Main Manager Class ---

class CompilationManager:
    """Manages parsing, caching, and strategy selection."""
    def __init__(self, parser_type: str = 'clang', 
                 project_path: str = '.', compile_commands_path: Optional[str] = None):
        self.parser_type = parser_type
        self.project_path = project_path
        self.compile_commands_path = compile_commands_path

        if self.parser_type == 'clang' and not self.compile_commands_path:
            inferred_path = os.path.join(project_path, 'compile_commands.json')
            if not os.path.exists(inferred_path):
                raise ValueError("Clang parser requires a path to compile_commands.json via --compile-commands")
            self.compile_commands_path = inferred_path

    def _create_parser(self) -> CompilationParser:
        """Factory method to create the appropriate parser instance."""
        if self.parser_type == 'clang':
            return ClangParser(self.project_path, self.compile_commands_path)
        else: # 'treesitter'
            return TreesitterParser(self.project_path)

    def parse_folder(self, folder: str, cache_path_spec: Optional[str] = None):
        """Parses a full folder, using a cache if possible, and returns the populated manager itself."""
        cache = ParserCache(folder, cache_path_spec)
        if cache.is_valid():
            function_spans, include_relations = cache.load()
            self.parser = self._create_parser()
            self.parser.function_spans = function_spans
            self.parser.include_relations = include_relations
            return self
        
        logger.info("No valid parser cache found or cache is stale. Parsing source files...")
        self.parser = self._create_parser()
        source_files = cache.get_source_files()
        self.parser.parse(source_files)
        logger.info(f"Finished parsing {len(source_files)} source files.")
        cache.save(self.parser.get_function_spans(), self.parser.get_include_relations())
        gc.collect()
        return

    def parse_files(self, file_list: List[str]):
        """Parses a specific list of files without caching and returns the populated manager itself."""
        logger.info(f"Parsing {len(file_list)} specific files (no cache)...")
        self.parser = self._create_parser()
        self.parser.parse(file_list)
        gc.collect()
        return

    def get_function_spans(self) -> List[Dict]:
        if not hasattr(self, 'parser') or self.parser is None:
            raise RuntimeError("CompilationManager has not parsed any files yet.")
        return self.parser.get_function_spans()

    def get_include_relations(self) -> Set[Tuple[str, str]]:
        if not hasattr(self, 'parser') or self.parser is None:
            raise RuntimeError("CompilationManager has not parsed any files yet.")
        return self.parser.get_include_relations()

if __name__ == "__main__":
    import argparse
    import sys
    import yaml
    from pathlib import Path
    from collections import defaultdict
    import input_params
    # Need to import the provider to use its analysis function
    from include_relation_provider import IncludeRelationProvider
    # Dummy Neo4jManager for type hinting, not actually used to connect to DB
    from neo4j_manager import Neo4jManager

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser(description="Parse C/C++ source files to extract function spans and include relations.")
    
    parser.add_argument("paths", nargs='+', type=Path, help="One or more source files or folders to process.")
    parser.add_argument("--output", type=Path, help="Output YAML file path (default: stdout).")

    parser_group = parser.add_argument_group('Parser Configuration')
    input_params.add_source_parser_args(parser_group)

    analysis_group = parser.add_argument_group('Analysis Mode')
    analysis_group.add_argument("--impacting-header", 
                                help="Analyze which source files are impacted by a change in this single header file.")

    args = parser.parse_args()

    # --- Path Normalization ---
    logger.info(f"Scanning {len(args.paths)} input path(s)...")
    unique_files = set()
    for p in args.paths:
        resolved_p = p.resolve()
        if resolved_p.is_file():
            if str(resolved_p).endswith(('.c', '.h')):
                unique_files.add(str(resolved_p))
        elif resolved_p.is_dir():
            for root, _, files in os.walk(resolved_p):
                for f in files:
                    if f.endswith(('.c', '.h')):
                        unique_files.add(os.path.join(root, f))
    
    file_list = sorted(list(unique_files))
    if not file_list:
        logger.error("No .c or .h files found in the provided paths. Aborting.")
        sys.exit(1)

    logger.info(f"Found {len(file_list)} unique source files to process.")

    # --- Manager Initialization ---
    project_path_for_init = os.path.abspath(os.path.commonpath(file_list) if file_list else os.getcwd())
    if os.path.isfile(project_path_for_init):
        project_path_for_init = os.path.dirname(project_path_for_init)

    try:
        manager = CompilationManager(
            parser_type=args.source_parser,
            project_path=project_path_for_init,
            compile_commands_path=args.compile_commands
        )
    except (ValueError, FileNotFoundError) as e:
        logger.critical(e)
        sys.exit(1)
 
    # --- Extraction ---
    manager.parse_files(file_list)
    results = {}

    # --- Output Formatting ---
    # Mode 1: Analyze impact of a specific header
    if args.impacting_header:
        logger.info("Running in impact analysis mode...")
        # We can pass a dummy Neo4jManager since it's not used for in-memory analysis
        provider = IncludeRelationProvider(neo4j_manager=None, project_path=project_path_for_init)
        all_relations = manager.get_include_relations()
        
        # Resolve input header to an absolute path for matching
        header_to_check = os.path.abspath(args.impacting_header)

        impact_results = provider.analyze_impact_from_memory(all_relations, [header_to_check])
        results = {'impact_analysis': impact_results}

    # Mode 2: Default mode, dump all parsed data
    else:
        logger.info("Running in default dump mode...")
        # Requirement 2: Filter "including" files to be within the project path
        project_relations = [
            rel for rel in manager.get_include_relations()
            if rel[0].startswith(project_path_for_init)
        ]

        # Requirement 1: Group include output by including file
        grouped_includes = defaultdict(list)
        for including, included in project_relations:
            grouped_includes[including].append(included)
        
        # Sort for consistent output
        for key in grouped_includes:
            grouped_includes[key].sort()

        results = {
            'function_spans': parser_instance.get_function_spans(),
            'grouped_include_relations': dict(sorted(grouped_includes.items()))
        }

    yaml_output = yaml.dump(results, sort_keys=False, allow_unicode=True)

    if args.output:
        output_path = str(args.output.resolve())
        with open(output_path, "w", encoding="utf-8") as out:
            out.write(yaml_output)
        print(f"Output saved to {output_path}")
    else:
        print(yaml_output)
