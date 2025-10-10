#!/usr/bin/env python3
import os
import sys
import argparse
import tree_sitter_c as tsc
from tree_sitter import Language, Parser
import yaml
import logging
import gc

logger = logging.getLogger(__name__)
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

    def get_function_spans_from_folder(self, folder, format="dict"):
        """Extract spans from multiple source files."""
        file_list = []
        for root, _, files in os.walk(folder):
            for f in files:
                if f.endswith((".c", ".h")):
                    file_list.append(os.path.join(root, f))
        
        all_docs = []
        logger.info("Processing source files for spans...")
        processed_files = 0
        for file_path in file_list:
            if not os.path.isfile(file_path):
                continue
            res = self.get_function_spans(file_path, format=format)
            if res:
                if format == "dict":
                    all_docs.append(res)
                else:  # yaml string
                    all_docs.append(res)
            processed_files += 1
            if processed_files % self.log_batch_size == 0:
                print(".", end="", flush=True)
        print(flush=True)
        logger.info(f"Finished processing {processed_files} source files for spans.")

        # Free memory
        del file_list
        gc.collect()

        if format == "dict":
            return all_docs
        else:
            return "\n".join(filter(None, all_docs))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    parser = argparse.ArgumentParser(
        description="Extract function spans from C source/header files"
    )
    parser.add_argument(
        "paths",
        nargs="+",
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
                res = extractor.get_function_spans_from_folder(p, format="dict")
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
                res = extractor.get_function_spans_from_folder(p, format="yaml")
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

