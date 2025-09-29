# Clangd to Neo4j Code Graph Importer

## 1. Overview

This project provides a powerful and efficient pipeline for parsing a C/C++ project's `clangd` index file and source code to build a detailed and queryable code graph in a Neo4j database.

The resulting graph contains the project's file and folder structure, detailed information about symbols (functions, structs, classes), and a complete function call graph.

## 2. Architecture

The project uses a modular, multi-pass architecture orchestrated by a main script. Each module has a specific responsibility.

-   `clangd_code_graph_builder.py`: **(Main Orchestrator)**
    This is the main entry point for the entire pipeline. It manages the multi-pass ingestion process and coordinates the other library modules.

-   `tree_sitter_span_extractor.py`: **(Library Module)**
    Provides a `SpanExtractor` class that uses the `tree-sitter` parsing library to scan source files and find the precise start and end locations of function bodies. This is critical for determining the "caller" in a function call.

-   `clangd_symbol_nodes_builder.py`: **(Library Module)**
    Provides classes for building the structural foundation of the graph. Its `PathProcessor` discovers all project files and folders and efficiently creates the `:PROJECT`, `:FOLDER`, and `:FILE` nodes. Its `SymbolProcessor` creates the nodes for individual code symbols (`:FUNCTION`, `:DATA_STRUCTURE`) and links them to the files that define them.

-   `clangd_call_graph_builder.py`: **(Library Module)**
    Provides the `ClangdCallGraphExtractor` class. This module's responsibility is to process the symbol information and function spans to identify all `caller -> callee` relationships. It generates an efficient, parameterized Cypher query to merge these `:CALLS` relationships into the graph.

## 3. Prerequisites

This project requires the following Python libraries:

-   `neo4j`
-   `pyyaml`
-   `tree-sitter`
-   `tree-sitter-c`

Install them using pip:
```bash
pip install neo4j pyyaml tree-sitter tree-sitter-c
```

## 4. Usage

To run the full ingestion pipeline, execute the main orchestrator script and provide the path to your `clangd` index file and the root directory of the project that was indexed.

```bash
python clangd_code_graph_builder.py <path-to-your-index.yaml> <path-to-your-project-root>
```

**Example:**
```bash
python clangd_code_graph_builder.py example-clangd-index.yaml "/home/xli/Public/temp/ComPro_Project/"
```

## 5. Graph Schema

The script generates the following graph schema in Neo4j:

### Node Labels

-   `:PROJECT`: The root node of the project.
-   `:FOLDER`: Represents a directory in the project.
-   `:FILE`: Represents a source file in the project.
-   `:FUNCTION`: Represents a function, with properties for its signature, return type, definition location, etc.
-   `:DATA_STRUCTURE`: Represents a `struct`, `class`, `union`, or `enum`.

### Relationship Types

-   `[:CONTAINS]`: Connects `:PROJECT` to `:FOLDER`s/:`FILE`s, and `:FOLDER` to other `:FOLDER`s/:`FILE`s, building the file system hierarchy.
-   `[:DEFINES]`: Connects a `:FILE` node to the `:FUNCTION` or `:DATA_STRUCTURE` nodes it defines.
-   `[:CALLS]`: Connects one `:FUNCTION` node to another, representing a function call.
