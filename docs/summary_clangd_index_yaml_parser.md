# Algorithm Summary: `clangd_index_yaml_parser.py`

## 1. Role in the Pipeline

This script serves as the **centralized parser** for the clangd index YAML files. It is a foundational library module for the entire ingestion pipeline, providing a single source of truth for interpreting the raw clangd data.

Its primary responsibility is to read a clangd index YAML file and transform its contents into an in-memory collection of structured `Symbol` objects, ready for the subsequent ingestion passes.

## 2. Core Logic and Parsing Strategies

The module provides two main classes to handle different performance needs: `SymbolParser` for single-threaded parsing and `ParallelSymbolParser` for high-performance, multi-process parsing.

### Data Classes

This module defines all the essential data classes that represent the elements of the clangd index, ensuring type safety and consistency across the pipeline:

*   **`Location`**: Represents a precise location in a source file (FileURI, line, column).
*   **`Reference`**: Represents a usage of a symbol, including its `Kind`, `Location`, and optionally a `container_id`.
*   **`Symbol`**: The core entity, representing a function, variable, class, etc., with its ID, name, kind, declaration/definition locations, and other properties.
*   ... and other helper data classes.

### Strategy 1: `SymbolParser` (Single-Threaded)

-   **Use Case**: Simpler projects, or when multi-processing is not desired (i.e., `--num-parse-workers=1`).
-   **Algorithm**:
    1.  Reads the entire YAML file into an in-memory string, sanitizing content (e.g., replacing tabs) along the way.
    2.  Uses `yaml.safe_load_all` to parse the string into a list of documents.
    3.  It performs two passes over this list:
        *   **Pass 1**: Collects all `!Symbol` documents to build a dictionary of `Symbol` objects.
        *   **Pass 2**: Collects all `!Refs` documents into a temporary list (`unlinked_refs`).
    4.  Finally, `build_cross_references()` is called to link the references to the symbols.

### Strategy 2: `ParallelSymbolParser` (Multi-Process, Default)

-   **Use Case**: Large codebases (like the Linux kernel) where parsing is a significant bottleneck. This is the default strategy when `--num-parse-workers` > 1.
-   **Algorithm**: This class uses a sophisticated "map-reduce" style approach with a `ProcessPoolExecutor` to dramatically speed up parsing. The process is carefully designed to be both fast and correct.

    1.  **Phase 1: Chunking (Main Process)**
        *   The `_sanitize_and_chunk_in_memory` method first performs a quick scan of the entire index file just to count the number of YAML documents (`---`).
        *   Based on this count and the number of workers, it calculates the optimal number of documents per chunk.
        *   It then reads the file a second time, creating large in-memory string chunks, each containing a set number of YAML documents. This avoids parsing the YAML in the main process.

    2.  **Phase 2: Parallel Parsing (Worker Processes)**
        *   The main process uses a `ProcessPoolExecutor` to distribute the YAML string chunks to a pool of worker processes.
        *   The `_parse_worker` function runs in each worker. It instantiates a simple `SymbolParser` and parses only the chunk of text it received.
        *   Each worker returns its own collection of parsed `Symbol` objects and a list of raw `!Refs` documents.

    3.  **Phase 3: Merging (Main Process)**
        *   The main process collects the results from all workers.
        *   It merges the dictionaries of `Symbol` objects and extends the central list of `unlinked_refs`.

    4.  **Phase 4: Cross-Reference Linking (Main Process)**
        *   After all parallel work is complete, the `build_cross_references()` method is called **sequentially** in the main process.
        *   This final, crucial step iterates through the complete list of `unlinked_refs` and attaches them to the appropriate `Symbol` objects in the master dictionary, creating the final, fully-linked in-memory representation of the code graph.

### `Container` Field Detection

Both parsers automatically detect the presence of the `Container` field in `!Refs` documents (introduced in clangd-indexer 21.x). This is used by the `ClangdCallGraphExtractor` to select the most efficient call graph extraction strategy.