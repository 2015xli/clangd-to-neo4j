#!/usr/bin/env python3
"""
This module defines the parser layer for extracting data from source code.

It provides an abstract base class `CompilationParser` and concrete implementations
like `ClangParser` and `TreesitterParser`.
"""

import os
import logging
import subprocess
import tempfile
import shutil
from typing import List, Dict, Set, Tuple
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm

# Optional imports for concrete implementations
try:
    import clang.cindex
except ImportError:
    clang = None

try:
    import tree_sitter_c as tsc
    from tree_sitter import Language, Parser as TreeSitterParser
except ImportError:
    tsc = None
    TreeSitterParser = None

logger = logging.getLogger(__name__)

# --- Abstract Base Class ---

class CompilationParser:
    """An abstract base class for source code parsers."""

    def __init__(self, project_path: str):
        """
        Initializes the parser.

        Args:
            project_path (str): The absolute path to the root of the project.
        """
        self.project_path = project_path
        self.function_spans: List[Dict] = []
        self.include_relations: Set[Tuple[str, str]] = set()

    def parse(self, files_to_parse: List[str]):
        """Parses a specific list of files and populates internal data structures."""
        raise NotImplementedError

    def get_function_spans(self) -> List[Dict]:
        """Returns the extracted function span data."""
        return self.function_spans

    def get_include_relations(self) -> Set[Tuple[str, str]]:
        """Returns a set of include relations as (including_file, included_file) tuples."""
        return self.include_relations

# --- Concrete Implementations ---

class ClangParser(CompilationParser):
    """A parser that uses clang.cindex for semantic analysis."""

    def __init__(self, project_path: str, compile_commands_path: str):
        super().__init__(project_path)
        if not clang:
            raise ImportError("clang library is not installed. Please install it with `pip install libclang`")
        
        db_dir = self._get_db_dir(compile_commands_path)
        try:
            self.db = clang.cindex.CompilationDatabase.fromDirectory(db_dir)
        except clang.cindex.CompilationDatabaseError as e:
            logger.critical(f"Error loading compilation database from '{db_dir}': {e}")
            raise

        self.index = clang.cindex.Index.create()
        self.clang_include_path = self._get_clang_resource_dir()
        self.processed_header_functions = set()

    def _get_db_dir(self, compile_commands_path: str) -> str:
        path = Path(compile_commands_path).resolve()
        if path.is_dir():
            if not (path / "compile_commands.json").exists():
                raise FileNotFoundError(f"No compile_commands.json found in directory {path}.")
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
            logger.warning("Could not find clang resource directory. Internal includes may be missing.")
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

                if not (is_header_file and func_signature in self.processed_header_functions):
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

    def parse(self, files_to_parse: List[str]):
        self.processed_header_functions.clear()
        self.include_relations.clear()
        
        span_results_dict = defaultdict(list)
        source_files = [f for f in files_to_parse if f.endswith(('.c', '.cpp', '.cc', '.cxx'))]
        
        if not source_files:
            logger.warning("ClangParser did not find any source files (.c, .cpp, etc.) to parse.")
            return

        original_dir = os.getcwd()
        for file_path in tqdm(source_files, desc="Parsing TUs (clang)"):
            cmds = self.db.getCompileCommands(file_path)
            if not cmds:
                logger.warning(f"Could not get compile commands for {file_path}")
                continue

            compile_dir = cmds[0].directory
            args = list(cmds[0].arguments)[1:]

            try:
                os.chdir(compile_dir)
                
                # Sanitize arguments
                skip_flags = {'-c', '-o', '-MMD', '-MF', '-MT', '-fcolor-diagnostics', '-fdiagnostics-color'}
                sanitized_args = []
                skip_next = False
                for a in args:
                    if skip_next: skip_next = False; continue
                    if a in skip_flags: skip_next = True; continue
                    if a == file_path or os.path.basename(a) == os.path.basename(file_path): continue
                    sanitized_args.append(a)

                if self.clang_include_path: sanitized_args.append(f'-I{self.clang_include_path}')

                tu = self.index.parse(file_path, args=sanitized_args, options=clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)
                self._walk_ast(tu.cursor, span_results_dict)
                
                for inc in tu.get_includes():
                    if inc.source and inc.include:
                        including_file = os.path.abspath(inc.source.name)
                        included_file = os.path.abspath(inc.include.name)
                        self.include_relations.add((including_file, included_file))

            except clang.cindex.TranslationUnitLoadError as e:
                logger.error(f"Failed to parse {file_path}: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred while parsing {file_path}: {e}")
            finally:
                os.chdir(original_dir) # Ensure we always change back
        
        self.function_spans = [
            {"FileURI": file_uri, "Functions": functions}
            for file_uri, functions in span_results_dict.items()
        ]

class TreesitterParser(CompilationParser):
    """A parser that uses Tree-sitter for syntactic analysis."""

    def __init__(self, project_path: str):
        super().__init__(project_path)
        if not tsc or not TreeSitterParser:
            raise ImportError("tree-sitter is not installed. Please install it with `pip install tree-sitter tree-sitter-c`")
        
        self.language = Language(tsc.language())
        self.parser = TreeSitterParser(self.language)

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
                body = node
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

    def _get_function_spans_for_file(self, file_path: str) -> dict:
        file_uri = f"file://{os.path.abspath(file_path)}"
        try:
            with open(file_path, "rb") as f:
                source = f.read()
            tree = self.parser.parse(source)
            source_lines = source.decode("utf-8", errors="ignore").splitlines()
            functions = self._extract_functions(tree, source_lines)
            if not functions:
                return {}
            return {"FileURI": file_uri, "Functions": functions}
        except Exception as e:
            logger.error(f"Treesitter failed to parse {file_path}: {e}")
            return {}

    def parse(self, files_to_parse: List[str]):
        all_docs = []
        for file_path in tqdm(files_to_parse, desc="Parsing spans (treesitter)"):
            if not os.path.isfile(file_path):
                continue
            res = self._get_function_spans_for_file(file_path)
            if res:
                all_docs.append(res)
        self.function_spans = all_docs

    def get_include_relations(self) -> Set[Tuple[str, str]]:
        logger.warning("Include relation extraction is not supported by TreesitterParser.")
        return set()
