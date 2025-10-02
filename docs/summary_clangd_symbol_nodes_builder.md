# Algorithm Summary: `clangd_symbol_nodes_builder.py`

## 1. Role in the Pipeline

This script acts as a **library module** for the main `clangd_code_graph_builder.py` orchestrator. Its primary responsibility is to build the structural foundation of the code graph in Neo4j. It does not create any behavioral relationships like function calls.

It is designed to work on a pre-parsed, in-memory collection of `Symbol` objects provided by the `SymbolParser`.

It provides two main classes:
-   `PathProcessor`: Creates the physical file system hierarchy of the project.
-   `SymbolProcessor`: Creates nodes for the logical code symbols within the files.

## 2. `PathProcessor`

This class is responsible for Pass 1 of the ingestion pipeline: creating all `:PROJECT`, `:FOLDER`, and `:FILE` nodes.

### Algorithm

1.  **Discover Paths**: Instead of reading the large index file, this class now operates on the in-memory collection of `Symbol` objects. It iterates through every symbol, inspects its declaration and definition locations, and discovers every unique, in-project file and folder path. It stores these in sets to de-duplicate them.
2.  **`UNWIND`-based Ingestion (Folders)**:
    *   It collects all folder data (path, name, parent path) into a list of maps.
    *   It then uses two `UNWIND` queries: one to `MERGE` all folder nodes, and another to `MATCH` parent nodes (either `PROJECT` or `FOLDER`) and `MERGE` the `CONTAINS` relationships. This approach is highly efficient for bulk ingestion.
3.  **`UNWIND`-based Ingestion (Files)**:
    *   Similarly, it collects all file data into a list of maps.
    *   It uses two `UNWIND` queries: one to `MERGE` all file nodes, and another to `MATCH` parent nodes (either `PROJECT` or `FOLDER`) and `MERGE` the `CONTAINS` relationships.

This `UNWIND`-based approach significantly reduces network round trips and improves ingestion performance.

## 3. `SymbolProcessor`

This class is responsible for Pass 2 of the ingestion pipeline: creating the nodes for code symbols.

### Algorithm

1.  **`process_symbol` Method**: This method is called for each `Symbol` object provided by the `SymbolParser`. It transforms the typed `Symbol` object into a flat dictionary containing all properties needed for a Neo4j node and its `DEFINES` relationship.
2.  **`UNWIND`-based Ingestion (`ingest_symbols_and_relationships`)**: 
    *   This method collects the data dictionaries for all symbols.
    *   It then separates them by `kind` (e.g., `FUNCTION`, `DATA_STRUCTURE`).
    *   It uses `UNWIND` queries to:
        *   `MERGE` all `FUNCTION` nodes.
        *   `MERGE` all `DATA_STRUCTURE` nodes.
        *   `MERGE` all `FIELD` nodes.
        *   `MERGE` all `VARIABLE` nodes.
        *   `MATCH` the file and symbol nodes and `MERGE` the `DEFINES` relationships.

This `UNWIND`-based approach for symbols and their relationships is highly efficient for bulk ingestion.

## 4. Memory Management

The script is designed for memory efficiency:
*   It operates on an in-memory collection of `Symbol` objects, avoiding repeated file I/O.
*   Large intermediate collections (like `project_files`, `project_folders`, and the various data lists for `UNWIND` queries) are explicitly deleted and `gc.collect()` is called as soon as they are no longer needed.
