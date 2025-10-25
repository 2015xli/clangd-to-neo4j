#!/usr/bin/env python3
"""
This module provides a configurable, caching extractor for function spans using different strategies.

It supports:
- 'treesitter': A fast, syntax-only parser.
- 'clang': A slower, semantically-accurate parser using libclang.
"""
import os
import sys
import argparse
import yaml
import logging
import gc
import pickle
import subprocess
import tempfile
import shutil
from typing import Optional, List, Dict
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm

# Optional Git import
try:
    import git
except ImportError:
    git = None

# Tree-sitter imports
import tree_sitter_c as tsc
from tree_sitter import Language, Parser as TreeSitterParser

# Clang imports
import clang.cindex


logger = logging.getLogger(__name__)

"""
Extract function spans from C source/header files using clang.cindex (or tree-sitter for syntactical results).
Output: Python list of function spans, grouped by file. (Or YAML string with doc separator --- !FileFunctionSpans)
Note, all the numbers are 0-based throughout the project
--- !FileFunctionSpans
FileURI: file:///home/user/demo.c
Functions:
  - Name: foo
    Kind: Function
    NameLocation:
      Start:
        Line: 1
        Column: 19
      End:
        Line: 1
        Column: 22
    BodyLocation:
      Start:
        Line: 1
        Column: 26
      End:
        Line: 3
        Column: 1
  - Name: bar
    Kind: Function
    NameLocation:
      Start:
        Line: 5
        Column: 6
      End:
        Line: 5
        Column: 9
    BodyLocation:
      Start:
        Line: 5
        Column: 14
      End:
        Line: 7
        Column: 1
"""

# --- Base Strategy Definition ---

class BaseExtractorStrategy:
    """Abstract base class for a span extraction strategy."""
    def extract_spans_from_files(self, files: list[str]) -> list[dict]:
        """Parses a list of files and returns a list of span data dictionaries."""
        raise NotImplementedError

# --- Tree-sitter Implementation ---

class TreeSitterStrategy(BaseExtractorStrategy):
    """Extracts function spans using the tree-sitter library."""
    def __init__(self, log_batch_size: int = 1000):
        self.language = Language(tsc.language())
        self.parser = TreeSitterParser(self.language)
        self.log_batch_size = log_batch_size

    def _find_identifier(self, node):
        if node.type == "identifier":
            return node
        for child in node.children:
            ident = self._find_identifier(child)
            if ident:
                return ident
        return None

    def _extract_functions(self, tree, source_lines):
        functions = []
        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            if node.type == "function_definition":
                declarator = node.child_by_field_name("declarator")
                ident = self._find_identifier(declarator)
                if not ident:
                    continue
                name = source_lines[ident.start_point[0]][ident.start_point[1]:ident.end_point[1]]
                body = node # Use the whole node for the body span
                functions.append({
                    "Name": name,
                    "Kind": "Function",
                    "NameLocation": {
                        "Start": {"Line": ident.start_point[0], "Column": ident.start_point[1]},
                        "End": {"Line": ident.end_point[0], "Column": ident.end_point[1]}
                    },
                    "BodyLocation": {
                        "Start": {"Line": body.start_point[0], "Column": body.start_point[1]},
                        "End": {"Line": body.end_point[0], "Column": body.end_point[1]}
                    }
                })
            stack.extend(node.children)
        return functions

    def get_function_spans_for_file(self, file_path: str) -> dict:
        file_uri = f"file://{os.path.abspath(file_path)}"
        with open(file_path, "rb") as f:
            source = f.read()
        tree = self.parser.parse(source)
        source_lines = source.decode("utf-8", errors="ignore").splitlines()
        functions = self._extract_functions(tree, source_lines)
        if not functions:
            return {}
        return {"FileURI": file_uri, "Functions": functions}

    def extract_spans_from_files(self, files: list[str]) -> list[dict]:
        all_docs = []
        for file_path in tqdm(files, desc="Parsing spans (treesitter)"):
            if not os.path.isfile(file_path):
                continue
            res = self.get_function_spans_for_file(file_path)
            if res:
                all_docs.append(res)
        return all_docs

# --- Clang Implementation ---

class ClangExtractorStrategy(BaseExtractorStrategy):
    """Extracts function spans using clang.cindex and a compilation database."""
    def __init__(self, compile_commands_path: str, project_path: str):
        self.project_path = os.path.abspath(project_path)
        db_dir = self._get_db_dir(compile_commands_path)
        try:
            self.db = clang.cindex.CompilationDatabase.fromDirectory(db_dir)
        except clang.cindex.CompilationDatabaseError as e:
            logger.critical(f"Error loading compilation database from '{db_dir}': {e}")
            sys.exit(1)

        self.index = clang.cindex.Index.create()
        self.clang_include_path = self._get_clang_resource_dir()
        self.processed_header_functions = set()

    def _get_db_dir(self, compile_commands_path: str) -> str:
        path = Path(compile_commands_path).resolve()
        if path.is_dir():
            if not (path / "compile_commands.json").exists():
                raise FileNotFoundError(f"No compile_commands.json found in directory {path}. Please put/link it there or use --compile-commands to specify the path.")
            return str(path)
        elif path.is_file():
            if path.name != "compile_commands.json":
                tmpdir = tempfile.mkdtemp(prefix="clangdb_")
                shutil.copy(str(path), os.path.join(tmpdir, "compile_commands.json"))
                return tmpdir
            else:
                return str(path.parent)
        else:
            raise FileNotFoundError(f"{compile_commands_path} not found")

    def _get_clang_resource_dir(self):
        try:
            resource_dir = subprocess.check_output(['clang', '-print-resource-dir']).decode('utf-8').strip()
            return os.path.join(resource_dir, 'include')
        except (FileNotFoundError, subprocess.CalledProcessError):
            logger.warning("Could not find clang resource directory via 'clang -print-resource-dir'. Internal includes may be missing.")
            return None

    def _find_function_name_token_pos(self, node):
        try:
            for tok in node.get_tokens():
                if tok.spelling == node.spelling:
                    loc = tok.location
                    if loc.file and loc.file.name.startswith(self.project_path):
                        return (loc.line - 1, loc.column - 1)
            return (node.location.line - 1, node.location.column - 1) # Fallback
        except Exception:
            return (node.location.line - 1, node.location.column - 1)

    def _walk_ast(self, node, results_dict):
        file_name = node.location.file.name if node.location.file else node.translation_unit.spelling
        if not file_name or not file_name.startswith(self.project_path):
            return
        
        try:
            if node.kind == clang.cindex.CursorKind.FUNCTION_DECL and node.is_definition():
                is_header_file = file_name.endswith('.h')
                func_signature = (file_name, node.spelling, node.location.line, node.location.column)

                if is_header_file and func_signature in self.processed_header_functions:
                    pass # Skip already processed header function
                else:
                    if is_header_file:
                        self.processed_header_functions.add(func_signature)
                    
                    name_start_line, name_start_col = self._find_function_name_token_pos(node)
                    body_start_line, body_start_col = node.extent.start.line - 1, node.extent.start.column - 1
                    body_end_line, body_end_col = node.extent.end.line - 1, node.extent.end.column - 1
                    
                    span_data = {
                        "Name": node.spelling,
                        "Kind": "Function",
                        "NameLocation": {
                            "Start": {"Line": name_start_line, "Column": name_start_col},
                            "End": {"Line": name_start_line, "Column": name_start_col + len(node.spelling)}
                        },
                        "BodyLocation": {
                            "Start": {"Line": body_start_line, "Column": body_start_col},
                            "End": {"Line": body_end_line, "Column": body_end_col}
                        }
                    }
                    file_uri = f"file://{os.path.abspath(file_name)}"
                    results_dict[file_uri].append(span_data)

            for c in node.get_children():
                self._walk_ast(c, results_dict)
        except Exception as e:
            logger.warning(f"Error processing clang AST node {node.spelling}: {e}")

    def extract_spans_from_files(self, files: list[str]) -> list[dict]:
        self.processed_header_functions.clear()
        aggregated_results = defaultdict(list)
        source_files = [f for f in files if f.endswith('.c')]
        
        if not source_files:
            logger.warning("Clang extractor did not find any .c source files to parse from the provided paths.")
            return []

        for file_path in tqdm(source_files, desc="Parsing TUs (clang)"):
            args = []
            try:
                cmds = self.db.getCompileCommands(file_path)
                if cmds:
                    raw_args = list(cmds[0].arguments)[1:]
                    skip_flags = {'-c', '-o', '-MMD', '-MF', '-MT', '-fcolor-diagnostics', '-fdiagnostics-color'}
                    skip_next = False
                    for a in raw_args:
                        if skip_next: skip_next = False; continue
                        if a in skip_flags: skip_next = True; continue
                        if a == file_path or os.path.basename(a) == os.path.basename(file_path): continue
                        args.append(a)
            except Exception:
                logger.warning(f"Could not get compile commands for {file_path}")

            if self.clang_include_path: args.append(f'-I{self.clang_include_path}')

            try:
                tu = self.index.parse(file_path, args=args, options=clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)
                self._walk_ast(tu.cursor, aggregated_results)
                del tu # Free memory promptly
            except clang.cindex.TranslationUnitLoadError as e:
                logger.error(f"Failed to parse {file_path}: {e}")
        
        # Convert the aggregated dictionary to the final list format
        final_docs = []
        for file_uri, functions in aggregated_results.items():
            final_docs.append({"FileURI": file_uri, "Functions": functions})
    
        # Collect the freed TUs of all files
        gc.collect()
        return final_docs

# --- Main Context Class ---

class SpanExtractor:
    """Manages span extraction, caching, and strategy selection."""
    def __init__(self, log_batch_size: int = 1000, extractor_type: str = 'clang', 
                 project_path: str = '.', compile_commands_path: Optional[str] = None):
        self.log_batch_size = log_batch_size
        if extractor_type == 'clang':
            if not compile_commands_path:
                inferred_path = os.path.join(project_path, 'compile_commands.json')
                if not os.path.exists(inferred_path):
                    raise ValueError("Clang extractor requires a path to compile_commands.json via --compile-commands")
                compile_commands_path = inferred_path
            self.strategy: BaseExtractorStrategy = ClangExtractorStrategy(compile_commands_path, project_path)
        else: # 'treesitter'
            self.strategy: BaseExtractorStrategy = TreeSitterStrategy(log_batch_size)

    def extract_from_folder(self, folder, format="dict", cache_path_spec=None):
        """Extracts spans from a full folder, using a cache if possible."""
        cache = SpanCache(folder, cache_path_spec)
        if cache.is_valid():
            all_docs = cache.load()
        else:
            logger.info("No valid cache found or cache is stale. Parsing source files...")
            source_files = cache.get_source_files()
            all_docs = self.strategy.extract_spans_from_files(source_files)
            logger.info(f"Finished processing {len(source_files)} source files for spans.")
            cache.save(all_docs)
        gc.collect()

        if format == "dict":
            return all_docs
        else:
            yaml_docs = ["--- !FileFunctionSpans\n" + yaml.safe_dump(doc, sort_keys=False) for doc in all_docs]
            return "\n".join(filter(None, yaml_docs))

    def extract_from_files(self, file_list, format="dict"):
        """Extracts spans from a specific list of files without caching."""
        logger.info(f"Parsing spans from {len(file_list)} specific files...")
        all_docs = self.strategy.extract_spans_from_files(file_list)
        gc.collect()

        if format == "dict":
            return all_docs
        else:
            yaml_docs = ["--- !FileFunctionSpans\n" + yaml.safe_dump(doc, sort_keys=False) for doc in all_docs]
            return "\n".join(filter(None, yaml_docs))

# --- Caching Logic ---

def get_git_repo(folder: str) -> Optional[git.Repo]:
    if not git: return None
    try:
        repo = git.Repo(folder, search_parent_directories=True)
        if not os.path.abspath(folder).startswith(os.path.abspath(repo.working_tree_dir)):
            return None
        return repo
    except (git.InvalidGitRepositoryError, git.NoSuchPathError):
        return None

class SpanCache:
    def __init__(self, folder: str, cache_path_spec: Optional[str] = None):
        self.folder = folder
        self.repo = get_git_repo(folder)
        self.cache_path = self._get_cache_path(cache_path_spec)
        self.source_files: Optional[list[str]] = None

    def _get_cache_path(self, cache_path_spec: Optional[str]) -> str:
        if cache_path_spec is None:
            base_name = os.path.basename(os.path.normpath(self.folder))
            return f"span_cache_{base_name}.pkl"
        if os.path.isdir(cache_path_spec):
            base_name = os.path.basename(os.path.normpath(self.folder))
            return os.path.join(cache_path_spec, f"span_cache_{base_name}.pkl")
        base_path, _ = os.path.splitext(cache_path_spec)
        return base_path + ".function_spans.pkl"

    def get_source_files(self) -> list[str]:
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
        if not os.path.exists(self.cache_path): return False
        try:
            with open(self.cache_path, "rb") as f: cached_data = pickle.load(f)
        except (pickle.UnpicklingError, EOFError):
            logger.warning("Cache file %s is corrupted. Ignoring.", self.cache_path); return False
        if self.repo and not self.repo.is_dirty():
            if cached_data.get("type") == "git" and cached_data.get("commit_hash") == self.repo.head.object.hexsha:
                logger.info("Git-based span cache is valid."); return True
        else: # Fallback to mtime
            cache_mtime = os.path.getmtime(self.cache_path)
            for file_path in self.get_source_files():
                if os.path.getmtime(file_path) > cache_mtime:
                    logger.info(f"Cache is stale due to modified file: {file_path}"); return False
            logger.info("Mtime-based span cache is valid."); return True
        return False

    def load(self) -> list:
        logger.info(f"Loading from cache: {self.cache_path}")
        with open(self.cache_path, "rb") as f: return pickle.load(f).get("data", [])

    def save(self, data: list):
        logger.info(f"Saving new span data to cache: {self.cache_path}")
        cache_obj = {"data": data}
        if self.repo: cache_obj["type"] = "git"; cache_obj["commit_hash"] = self.repo.head.object.hexsha
        else: cache_obj["type"] = "mtime"
        with open(self.cache_path, "wb") as f: pickle.dump(cache_obj, f)

# --- Main CLI ---

if __name__ == "__main__":
    import input_params

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    parser = argparse.ArgumentParser(description="Extract function spans from C/C++ source files using different strategies.")
    
    input_params.add_span_extractor_args(parser)
    parser.add_argument("paths", nargs='+', type=Path, help="One or more source files or folders to process")
    parser.add_argument("--output", type=Path, help="Output YAML file path (default: stdout)")
    parser.add_argument('--log-batch-size', type=int, default=1000, help='Log progress every N items (default: 1000)')

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

    # --- Extractor Initialization ---
    # Find the common base path for all provided files to use as the project root.
    project_path_for_init = os.path.commonpath(file_list) if file_list else os.getcwd()
    if os.path.isfile(project_path_for_init):
        project_path_for_init = os.path.dirname(project_path_for_init)

    compile_commands_path = args.compile_commands

    try:
        extractor = SpanExtractor(
            log_batch_size=args.log_batch_size,
            extractor_type=args.span_extractor,
            project_path=project_path_for_init,
            compile_commands_path=compile_commands_path
        )
    except (ValueError, FileNotFoundError) as e:
        logger.critical(e)
        sys.exit(1)
 
    # --- Extraction and Output ---
    # For standalone execution, we use the non-caching method.
    results = extractor.extract_from_files(file_list)

    yaml_output = yaml.dump(results, sort_keys=False, allow_unicode=True)

    if args.output:
        output_path = str(args.output.resolve())
        with open(output_path, "w", encoding="utf-8") as out:
            out.write(yaml_output)
        print(f"Output saved to {output_path}")
    else:
        print(yaml_output)
