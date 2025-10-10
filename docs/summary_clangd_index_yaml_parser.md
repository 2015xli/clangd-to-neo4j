# Algorithm Summary: `clangd_index_yaml_parser.py`

## 1. Role in the Pipeline

This script serves as the **centralized parser** for the clangd index YAML files. It is a foundational library module for the entire ingestion pipeline, providing a single source of truth for interpreting the raw clangd data.

Its primary responsibility is to read a clangd index YAML file and transform its contents into an in-memory collection of structured `Symbol` objects, ready for the subsequent ingestion passes.

## 2. Core Logic and Unified Parser

The module has been refactored to use a single, unified `SymbolParser` class that intelligently handles both single-threaded and parallel parsing. This significantly simplifies the API for all callers.

### Simplified API

Previously, callers had to choose between `SymbolParser` and `ParallelSymbolParser`. Now, they simply instantiate the `SymbolParser` class and call the `parse()` method. The parser automatically uses a parallel, multi-process approach if the `--num-parse-workers` argument is greater than 1.

### Caching Mechanism

To dramatically improve performance on subsequent runs, the `SymbolParser` now implements a caching mechanism.

*   **How it works**: After a YAML file is successfully parsed, the resulting collection of `Symbol` objects is serialized to a `.pkl` (pickle) file in the same directory as the source YAML file.
*   **Cache Invalidation**: The parser checks the modification time of the source YAML file. If the `.pkl` cache file exists and is newer than the YAML file, the parser loads the data directly from the cache, bypassing the expensive parsing process entirely.
*   **Benefit**: This makes re-running the ingestion pipeline on the same codebase almost instantaneous after the initial parse.

### Data Classes

This module defines all the essential data classes that represent the elements of the clangd index, ensuring type safety and consistency across the pipeline:

*   **`Location`**: Represents a precise location in a source file (FileURI, line, column).
*   **`Reference`**: Represents a usage of a symbol, including its `Kind`, `Location`, and optionally a `container_id`.
*   **`Symbol`**: The core entity, representing a function, variable, class, etc., with its ID, name, kind, declaration/definition locations, and other properties.
*   ... and other helper data classes.

### Parsing Strategy (Internal)

Internally, the `SymbolParser` uses a sophisticated "map-reduce" style approach with a `ProcessPoolExecutor` when parallelism is enabled.

1.  **Phase 1: Chunking (Main Process)**
    *   The parser first performs a quick scan of the entire index file to count the number of YAML documents (`---`).
    *   Based on this count and the number of workers, it calculates the optimal number of documents per chunk.
    *   It then reads the file, creating large in-memory string chunks, each containing a set number of YAML documents.

2.  **Phase 2: Parallel Parsing (Worker Processes)**
    *   The main process distributes the YAML string chunks to a pool of worker processes.
    *   Each worker parses its chunk and returns its own collection of `Symbol` objects and raw `!Refs` documents.

3.  **Phase 3: Merging (Main Process)**
    *   The main process collects the results from all workers, merging the dictionaries of `Symbol` objects and the lists of `!Refs` documents.

4.  **Phase 4: Cross-Reference Linking (Main Process)**
    *   After all parsing is complete, this final, crucial step iterates through the complete list of `!Refs` and attaches them to the appropriate `Symbol` objects, creating the final, fully-linked in-memory representation of the code graph.

### `Container` Field Detection

The parser automatically detects the presence of the `Container` field in `!Refs` documents (introduced in clangd-indexer 21.x). This is used by the `ClangdCallGraphExtractor` to select the most efficient call graph extraction strategy.
