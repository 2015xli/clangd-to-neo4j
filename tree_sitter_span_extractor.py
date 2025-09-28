#!/usr/bin/env python3
import os
import sys
import argparse
import tree_sitter_c as tsc
from tree_sitter import Language, Parser
import yaml
"""
Extract function spans from C source/header files using tree-sitter.
Output: YAML string or Python list of function spans
--- !Span
Name: foo
Kind: Function
NameLocation:
  FileURI: file:///home/user/demo.c
  Start:
    Line: 1
    Column: 19
  End:
    Line: 1
    Column: 22
BodyLocation:
  FileURI: file:///home/user/demo.c
  Start:
    Line: 1
    Column: 26
  End:
    Line: 3
    Column: 1

--- !Span
Name: bar
Kind: Function
NameLocation:
  FileURI: file:///home/user/demo.c
  Start:
    Line: 5
    Column: 6
  End:
    Line: 5
    Column: 9
BodyLocation:
  FileURI: file:///home/user/demo.c
  Start:
    Line: 5
    Column: 14
  End:
    Line: 7
    Column: 1

"""

class SpanExtractor:
    def __init__(self):
        # Initialize tree-sitter C parser
        self.language = Language(tsc.language())
        self.parser = Parser(self.language)

    def _find_identifier(self, node):
        """Recursively find the identifier node inside a declarator subtree."""
        if node.type == "identifier":
            return node
        for child in node.children:
            ident = self._find_identifier(child)
            if ident:
                return ident
        return None

    def _extract_functions(self, tree, source_lines, file_uri):
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

                body = node.child_by_field_name("body")

                functions.append({
                    "Name": name,
                    "Kind": "Function",
                    "NameLocation": {
                        "FileURI": file_uri,
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
                        "FileURI": file_uri,
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
            str | list: YAML string if format="yaml", else list of dicts
        """
        file_uri = f"file://{os.path.abspath(file_path)}"

        with open(file_path, "rb") as f:
            source = f.read()

        tree = self.parser.parse(source)
        source_lines = source.decode("utf-8", errors="ignore").splitlines()

        functions = self._extract_functions(tree, source_lines, file_uri)

        if format == "dict":
            return functions
        elif format == "yaml":
            docs = []
            for fn in functions:
                docs.append("--- !Span\n" + yaml.safe_dump(fn, sort_keys=False))
            return "\n".join(docs)
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
            if format == "dict":
                all_docs.extend(res)
            else:  # yaml string
                all_docs.append(res)
        if format == "dict":
            return all_docs
        else:
            return "\n".join(all_docs)

    def get_function_spans_from_folder(self, folder, format="yaml"):
        """Recursively extract spans from a folder of .c/.h files."""
        file_list = []
        for root, _, files in os.walk(folder):
            for f in files:
                if f.endswith((".c", ".h")):
                    file_list.append(os.path.join(root, f))
        return self.get_function_spans_from_files(file_list, format=format)


# ---- CLI entry ----
if __name__ == "__main__":
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
    args = parser.parse_args()

    extractor = SpanExtractor()

    # Collect results
    results = []
    if args.format == "dict":
        all_results = []
        for p in args.paths:
            if os.path.isdir(p):
                res = extractor.get_function_spans_from_folder(p, format="dict")
            else:
                res = extractor.get_function_spans(p, format="dict")
            all_results.extend(res)
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
        results = "\n".join(yaml_docs)

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
