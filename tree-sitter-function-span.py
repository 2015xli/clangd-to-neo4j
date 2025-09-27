#!/usr/bin/env python3
import os
import sys
import argparse
import tree_sitter_c as tsc
from tree_sitter import Language, Parser
import yaml


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
                    "FileURI": file_uri,
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract function spans from C source/header files"
    )
    parser.add_argument("file", help="Path to .c or .h file")
    parser.add_argument(
        "--format",
        choices=["yaml", "dict"],
        default="yaml",
        help="Output format (default: yaml)",
    )
    args = parser.parse_args()

    extractor = SpanExtractor()
    result = extractor.get_function_spans(args.file, format=args.format)

    if args.format == "yaml":
        print(result)
    else:  # dict
        import pprint
        pprint.pprint(result)
