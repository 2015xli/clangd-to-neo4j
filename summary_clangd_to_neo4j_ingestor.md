# Algorithm Summary: `clangd_to_neo4j_ingestor.py`

## 1. Overview

This script acts as a streaming importer that reads a `clangd` index YAML file and directly populates a Neo4j database with the **structural elements** of a codebase. It parses symbols and their locations to build a graph representing the project's file hierarchy and where symbols are defined.

It is designed to be efficient for large index files by processing the input YAML as a stream and committing the generated Cypher operations to Neo4j in batches.

## 2. Key Features & Scope

This script is responsible for creating the foundational structure of the code graph.

#### What It Builds:

-   **Physical Structure**: Creates `:PROJECT`, `:FOLDER`, and `:FILE` nodes, connected by `:CONTAINS` relationships to model the directory structure.
-   **Symbol Nodes**: Creates nodes for major code constructs with specific labels:
    -   `:FUNCTION`
    -   `:DATA_STRUCTURE` (for Structs, Classes, Unions, Enums)
    -   `:FIELD` (for members of structs/classes)
    -   `:VARIABLE` (for global or local variables)
-   **Definition Relationships**: Connects `:FILE` nodes to the symbol nodes they define via a `:DEFINES` relationship (e.g., `(file)-[:DEFINES]->(function)`).

#### What It Does **NOT** Build:

-   It **does not** analyze symbol references (`!References` in the `clangd` index) to create a call graph with `[:CALLS]` relationships.
-   It **does not** use the function body span data from `tree_sitter_span_extractor.py`.

## 3. Core Components

The script is built around three main classes:

### `Neo4jManager`

This class handles all direct interaction with the Neo4j database.

-   **Connection**: Manages the database driver and connection settings.
-   **Setup**: Contains methods to `reset_database` (clearing all existing data) and `create_constraints` to enforce uniqueness for nodes like files, folders, and symbols, which is critical for data integrity and performance.
-   **Execution**: Provides a `process_batch` method that executes a list of Cypher queries within a single, efficient transaction.

### `PathManager`

This utility class is responsible for cleaning and normalizing file paths.

-   Its main purpose is to convert the absolute `file:///...` URIs found in the `clangd` index into project-relative paths.
-   This ensures the resulting graph is portable and not tied to the specific machine environment where the index was generated.

### `SymbolProcessor`

This is the core translator of the script.

-   Its main method, `process_symbol`, takes a single symbol dictionary parsed from the `clangd` YAML file.
-   It identifies the symbol's `Kind` (e.g., `Function`, `Struct`) and dispatches to specialized private methods (e.g., `_process_function`).
-   These methods generate a list of Cypher operations (query strings and parameter dictionaries) required to:
    1.  `MERGE` the symbol's node itself (e.g., create a `:FUNCTION` node with its properties).
    2.  `MERGE` the file/folder nodes where the symbol is defined.
    3.  `MERGE` the relationships between the project, folders, files, and the symbol definition.

## 4. Execution Flow

The `main` function orchestrates the entire import process:

1.  **Initialization**: It connects to Neo4j, completely wipes the existing database, creates a root `:PROJECT` node, and applies the necessary schema constraints.
2.  **Streaming**: It opens the `clangd` index file and reads it as a stream of YAML documents, which is memory-efficient.
3.  **Batching**: For each symbol document in the stream, it uses the `SymbolProcessor` to generate the corresponding Cypher operations. These operations are appended to a `batch` list.
4.  **Committing**: Once the number of operations in the `batch` list reaches a constant size (`BATCH_SIZE`), the entire batch is sent to the `Neo4jManager` to be executed in a single database transaction. The batch list is then cleared.
5.  **Finalizing**: After the file stream is exhausted, any remaining operations in the batch are committed to the database.
