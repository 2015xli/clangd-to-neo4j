#!/usr/bin/env python3
import os
import sys
import argparse
import tree_sitter_c as tsc
from tree_sitter import Language, Parser
import yaml
import logging
import gc
import pickle
from typing import Optional
from tqdm import tqdm

try:
    import git
except ImportError:
    git = None

logger = logging.getLogger(__name__)

def get_git_repo(folder: str) -> Optional[git.Repo]:
    """
    Safely initializes a git.Repo object. Returns None if the folder is not a
    valid Git repository or if gitpython is not installed.
    """
    if not git:
        return None
    try:
        repo = git.Repo(folder, search_parent_directories=True)
        # Ensure the provided folder is actually within the git repo's working tree
        if not os.path.abspath(folder).startswith(os.path.abspath(repo.working_tree_dir)):
            return None
        return repo
    except (git.InvalidGitRepositoryError, git.NoSuchPathError):
        return None

class SpanCache:
    """Handles all caching logic for function spans."""
    def __init__(self, folder: str, cache_path_spec: Optional[str] = None):
        self.folder = folder
        self.repo = get_git_repo(folder)
        self.cache_path = self._get_cache_path(cache_path_spec)
        self.source_files: Optional[list[str]] = None  # Lazy loaded

    def _get_cache_path(self, cache_path_spec: Optional[str]) -> str:
        """
        Constructs the cache file path with flexible input.
        - If cache_path_spec is None, defaults to a file in the CWD.
        - If cache_path_spec is a directory, creates the cache file inside it.
        - If cache_path_spec is a file, creates the cache file alongside it.
        """
        # Default case: No path provided, use CWD.
        if cache_path_spec is None:
            cache_dir = "."
            project_name = os.path.basename(os.path.normpath(self.folder))
            cache_filename = f"span_cache_{project_name}.pkl"
            return os.path.join(cache_dir, cache_filename)

        # Case 2: A directory is provided.
        if os.path.isdir(cache_path_spec):
            cache_dir = cache_path_spec
            project_name = os.path.basename(os.path.normpath(self.folder))
            cache_filename = f"span_cache_{project_name}.pkl"
            os.makedirs(cache_dir, exist_ok=True)
            return os.path.join(cache_dir, cache_filename)
        
        # Case 3: A file path is provided (or a path that looks like a file).
        base_path, _ = os.path.splitext(cache_path_spec)
        final_path = base_path + ".function_spans.pkl"
        
        # Ensure the directory for the final path exists.
        final_dir = os.path.dirname(final_path)
        if final_dir:
            os.makedirs(final_dir, exist_ok=True)
            
        return final_path

    def get_source_files(self) -> list[str]:
        """Walks the directory to get all .c and .h files, caching the result."""
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
        """Check if the cache is valid using Git or file modification times."""
        if not os.path.exists(self.cache_path):
            return False

        try:
            with open(self.cache_path, "rb") as f:
                cached_data = pickle.load(f)
        except (pickle.UnpicklingError, EOFError):
            logger.warning("Cache file %s is corrupted. Ignoring.", self.cache_path)
            return False

        if self.repo:
            if cached_data.get("type") != "git":
                logger.info("Cache type mismatch (expected git). Regenerating.")
                return False
            if cached_data.get("commit_hash") != self.repo.head.object.hexsha:
                logger.info("Git commit hash changed. Regenerating cache.")
                return False
            if self.repo.is_dirty():
                logger.info("Git working tree is dirty. Forcing cache regeneration.")
                return False
            logger.info("Git-based span cache is valid.")
            return True
        else:  # Fallback to mtime
            if cached_data.get("type") != "mtime":
                logger.info("Cache type mismatch (expected mtime). Regenerating.")
                return False
            cache_mtime = os.path.getmtime(self.cache_path)
            for file_path in self.get_source_files():
                if os.path.getmtime(file_path) > cache_mtime:
                    logger.info(f"Cache is stale due to modified file: {file_path}")
                    return False
            logger.info("Mtime-based span cache is valid.")
            return True

    def load(self) -> list:
        """Load span data from the cache file."""
        logger.info(f"Loading from cache: {self.cache_path}")
        with open(self.cache_path, "rb") as f:
            return pickle.load(f).get("data", [])

    def save(self, data: list):
        """Save span data and validation metadata to the cache file."""
        logger.info(f"Saving new span data to cache: {self.cache_path}")
        cache_obj = {"data": data}
        if self.repo:
            cache_obj["type"] = "git"
            cache_obj["commit_hash"] = self.repo.head.object.hexsha
        else:
            cache_obj["type"] = "mtime"
        
        with open(self.cache_path, "wb") as f:
            pickle.dump(cache_obj, f)


"""
Extract function spans from C source/header files using tree-sitter.
Output: YAML string or Python list of function spans, grouped by file.
Note, the numbers are 0-based, the same as in clangd index.
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

class SpanExtractor:
    def __init__(self, log_batch_size: int = 1000):
        # Initialize tree-sitter C parser
        self.language = Language(tsc.language())
        self.parser = Parser(self.language)
        self.log_batch_size = log_batch_size

    def _find_identifier(self, node):
        """Recursively find the identifier node inside a declarator subtree."""
        if node.type == "identifier":
            return node
        for child in node.children:
            ident = self._find_identifier(child)
            if ident:
                return ident
        return None

    def _extract_functions(self, tree, source_lines):
        """Traverse the AST to extract all function definitions with spans."""
        functions = []
        stack = [tree.root_node]

        while stack:
            node = stack.pop()

            if node.type == "function_definition":
                declarator = node.child_by_field_name("declarator")
                ident = self._find_identifier(declarator)
                if not ident:
                    continue

                name = source_lines[ident.start_point[0]][
                    ident.start_point[1]:ident.end_point[1]
                ]

                #body = node.child_by_field_name("body")
                # 
                # Function body including "{ statements }"
                # Full function body including "return_type name(signature) { statements }"
                # This is the smallest change to keep the code functional, using full body to replace real body.
                # 
                # BodyLocation is used in two places:
                # 1. In call graph builder when clangd yaml index file !Refs does not have container field.
                #    We use body location (scope) to check if a callsite (callee's name) stays within the function body.
                #    With this change, the function body includes not only "{ statements }", but also the leading type-name-sig.
                #    This is not ideal, but ok, because a callee's location can never appear in the leading part.
                #    Ideal solution is to keep the original real body location.
                # 2. In code rag generator when we need to extract function body code for llm to summarize.
                #    We use body location start/end lines (no columns) to get the function body source code.
                #    With original real body location, this function source may miss the leading part, like in "int foo()\n{...}"
                #    That's not desirable for llm to have a full picture. This is why I made this change.
                #    There are three solutions:
                #    2.a. If we keep the original body location here, we need introduce another location property, such as,
                #    FunctionFullLocation = node.start_point, node.end_point. or FunctionHeadLocation
                #    2.b. We introduce a seperata Source property that keeps the source code of full function.
                #    This is not a bad solution, but may bloat the database with virtually a full copy of the project source.
                #    Will do it as an option --include-source if we really want, like,
                #    function_source = source[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
                #    Including source code needs to exclude any access permission or copyright issue.
                #    We can then have:
                #    if include_source:
                #        body = node.child_by_field_name("body")
                #    else: 
                #        body = node
                body = node 


                functions.append({
                    "Name": name,
                    "Kind": "Function",
                    "NameLocation": {
                        "Start": {
                            "Line": ident.start_point[0],
                            "Column": ident.start_point[1]
                        },
                        "End": {
                            "Line": ident.end_point[0],
                            "Column": ident.end_point[1]
                        }
                    },
                    "BodyLocation": {
                        "Start": {
                            "Line": body.start_point[0],
                            "Column": body.start_point[1]
                        },
                        "End": {
                            "Line": body.end_point[0],
                            "Column": body.end_point[1]
                        }
                    } if body else None
                })

            stack.extend(node.children)

        return functions

    def get_function_spans(self, file_path, format="yaml"):
        """
        Extract function spans from a C source/header file.

        Args:
            file_path (str): Path to .c or .h file
            format (str): "yaml" (default) or "dict"

        Returns:
            str | dict: YAML string if format="yaml", else a dict for the file.
        """
        file_uri = f"file://{os.path.abspath(file_path)}"

        with open(file_path, "rb") as f:
            source = f.read()

        tree = self.parser.parse(source)
        source_lines = source.decode("utf-8", errors="ignore").splitlines()

        functions = self._extract_functions(tree, source_lines)

        # Free memory
        del source
        del tree
        del source_lines
        # gc.collect()  # to slow if lots of files. Should be fine to collect later together.

        if not functions:
            return "" if format == "yaml" else {}

        file_spans = {
            "FileURI": file_uri,
            "Functions": functions
        }

        if format == "dict":
            return file_spans
        elif format == "yaml":
            return "--- !FileFunctionSpans\n" + yaml.safe_dump(file_spans, sort_keys=False)
        else:
            raise ValueError("format must be 'yaml' or 'dict'")

    # ---- New helpers ----

    def get_function_spans_from_files(self, file_list, format="yaml"):
        """Extract spans from multiple source files."""
        all_docs = []
        for file_path in file_list:
            if not os.path.isfile(file_path):
                continue
            res = self.get_function_spans(file_path, format=format)
            if res:
                if format == "dict":
                    all_docs.append(res)
                else:  # yaml string
                    all_docs.append(res)
        if format == "dict":
            return all_docs
        else:
            return "\n".join(filter(None, all_docs))

    def get_function_spans_from_folder(self, folder, format="dict", cache_path_spec=None):
        """Extract spans from a folder, using a cache if possible."""
        cache = SpanCache(folder, cache_path_spec)

        if cache.is_valid():
            all_docs = cache.load()
        else:
            logger.info("No valid cache found. Parsing source files for spans...")
            all_docs = []
            source_files = cache.get_source_files()
            for file_path in tqdm(source_files, desc="Parsing source files for spans"):
                res = self.get_function_spans(file_path, format="dict")
                if res:
                    all_docs.append(res)
            
            logger.info(f"Finished processing {len(source_files)} source files for spans.")
            cache.save(all_docs)

        gc.collect()

        if format == "dict":
            return all_docs
        else:
            yaml_docs = ["--- !FileFunctionSpans\n" + yaml.safe_dump(doc, sort_keys=False) for doc in all_docs]
            return "\n".join(filter(None, yaml_docs))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    parser = argparse.ArgumentParser(
        description="Extract function spans from C source/header files"
    )
    parser.add_argument(
        "paths",
        nargs= "+",
        help="One or more source files or folders"
    )
    parser.add_argument(
        "--format",
        choices=["yaml", "dict"],
        default="yaml",
        help="Output format (default: yaml)"
    )
    parser.add_argument(
        "--output",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        '--log-batch-size',
        type=int,
        default=1000,
        help='Log progress every N items (default: 1000)'
    )
    args = parser.parse_args()
 
    extractor = SpanExtractor(args.log_batch_size)
 
    # Collect results
    results = []
    if args.format == "dict":
        all_results = []
        for p in args.paths:
            if os.path.isdir(p):
                res = extractor.get_function_spans_from_folder(p, format="dict", cache_path_spec=args.output)
                all_results.extend(res)
            else:
                res = extractor.get_function_spans(p, format="dict")
                if res:
                    all_results.append(res)
        results = all_results
    else:  # yaml
        yaml_docs = []
        for p in args.paths:
            if os.path.isdir(p):
                res = extractor.get_function_spans_from_folder(p, format="yaml", cache_path_spec=args.output)
            else:
                res = extractor.get_function_spans(p, format="yaml")
            if res:
                yaml_docs.append(res)
        results = "\n".join(filter(None, yaml_docs))
 
    # Output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as out:
            if args.format == "yaml":
                out.write(results)
            else:
                yaml.safe_dump(results, out, sort_keys=False)
    else:
        if args.format == "yaml":
            print(results)
        else:
            import pprint
            pprint.pprint(results)

    # Final cleanup
    del results
    gc.collect()
