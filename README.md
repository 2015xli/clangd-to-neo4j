# Clangd to Neo4j Code Knowledge Graph Ingestion

This project provides a pipeline to ingest `clangd` index YAML files into a Neo4j graph database, creating a rich knowledge graph of a C/C++ codebase. This graph can then be used for various software engineering tasks like code search, dependency analysis, and refactoring.

## Architecture Overview

The ingestion process is orchestrated by `clangd_code_graph_builder.py` and proceeds through several passes, leveraging a modular design for efficiency and maintainability.

### Key Design Principles

*   **Modular Processors**: Each stage of the ingestion is handled by a dedicated processor class.
*   **"Parse Once, Use Many"**: The large `clangd` index YAML file is parsed only once into an in-memory representation, which is then reused by all subsequent passes.
*   **Memory Efficiency**: Aggressive memory management (explicit `del` and `gc.collect()`) and optimized data structures (e.g., `RelativeLocation`, streaming YAML parsing) are employed to handle large codebases like the Linux kernel.
*   **Flexible Call Graph Extraction**: Supports both older `clangd` index formats (using `tree-sitter` for span extraction) and newer formats (leveraging the `Container` field for direct call site identification).
*   **Batch Processing with `UNWIND`**: All Neo4j ingestion operations (nodes and relationships) utilize Cypher's `UNWIND` clause for highly efficient batch processing, minimizing network round trips.

## Ingestion Pipeline Passes

The `clangd_code_graph_builder.py` orchestrates the following passes:

### Pass 0: Parse Clangd Index (`clangd_index_yaml_parser.py`)

*   **Purpose**: Centralized parsing of the `clangd` index YAML file into an in-memory collection of `Symbol` objects.
*   **Key Component**: `SymbolParser` class.
*   **Features**:
    *   Defines common data classes (`Symbol`, `Location`, `Reference`, etc.).
    *   Supports **streaming (single-pass)** parsing by default for memory efficiency, assuming symbols appear before their references.
    *   Provides a `--nonstream-parsing` option for robust **non-streaming (two-pass)** parsing if YAML order is not guaranteed.
    *   Detects the presence of the `Container` field in `!Refs` documents (clangd 21.x+) to enable optimized call graph extraction.

### Pass 1: Ingest File & Folder Structure (`clangd_symbol_nodes_builder.py` - `PathProcessor`)

*   **Purpose**: Creates `:PROJECT`, `:FOLDER`, and `:FILE` nodes in Neo4j, establishing the physical file system hierarchy.
*   **Key Component**: `PathProcessor` class.
*   **Features**:
    *   Discovers paths by iterating over the in-memory `Symbol` objects from Pass 0.
    *   Uses `UNWIND`-based batch processing for efficient creation of folder and file nodes, and their `CONTAINS` relationships.
    *   Simplified Cypher queries for relationships, leveraging the pre-creation of the `PROJECT` node.

### Pass 2: Ingest Symbol Definitions (`clangd_symbol_nodes_builder.py` - `SymbolProcessor`)

*   **Purpose**: Creates nodes for logical code symbols (`:FUNCTION`, `:DATA_STRUCTURE`) and their `DEFINES` relationships to files.
*   **Key Component**: `SymbolProcessor` class.
*   **Features**:
    *   Processes typed `Symbol` objects from Pass 0.
    *   Uses `UNWIND`-based batch processing for efficient creation of symbol nodes and their `DEFINES` relationships.

### Pass 3: Ingest Call Graph (`clangd_call_graph_builder.py`)

*   **Purpose**: Identifies and ingests function call relationships (`-[:CALLS]->`) into Neo4j.
*   **Key Components**: `BaseClangdCallGraphExtractor`, `ClangdCallGraphExtractorWithContainer`, `ClangdCallGraphExtractorWithoutContainer`.
*   **Features**:
    *   **Adaptive Strategy**: Automatically selects the most efficient call graph extraction method based on whether the `Container` field is detected in the `clangd` index.
    *   **`WithContainer` Strategy (New Format)**: Directly uses the `Container` field from `!Refs` documents for highly efficient call graph extraction, bypassing `tree-sitter`. Includes validation for caller symbols.
    *   **`WithoutContainer` Strategy (Legacy Format)**: Falls back to `tree-sitter` based span extraction and spatial lookup for older index formats.
    *   Uses `UNWIND` for efficient ingestion of `CALLS` relationships.

### Pass 4: Cleanup Orphan Nodes

*   **Purpose**: Removes any nodes that were created but ended up without any relationships, ensuring a clean graph.
*   **Features**: Uses an `UNWIND`-compatible Cypher query for efficient cleanup.

## Usage

To run the ingestion pipeline:

```bash
python3 clangd_code_graph_builder.py <path_to_clangd_index.yaml> <path_to_project_root> [options]
```

**Options:**
*   `--log-batch-size <int>`: Log progress every N items (default: 1000).
*   `--keep-orphans`: Skip Pass 4 and keep orphan nodes in the graph.
*   `--nonstream-parsing`: Use non-streaming (two-pass) YAML parsing for the `SymbolParser`. (Default is streaming for memory efficiency).

## Development Notes

*   **Memory Management**: Explicit `del` statements and `gc.collect()` calls are strategically placed throughout the pipeline to manage memory aggressively, crucial for large codebases.
*   **Error Handling**: Robust error handling is implemented for Neo4j operations and file parsing.