# Algorithm Summary: `clangd_index_yaml_parser.py`

## 1. Role in the Pipeline

This script serves as the **centralized parser** for the clangd index YAML files. It is a foundational library module for the entire ingestion pipeline, providing a single source of truth for interpreting the raw clangd data.

It defines all the common data structures used throughout the system and offers flexible parsing strategies.

## 2. Core Logic: `SymbolParser` Class

The `SymbolParser` class is the heart of this module. Its primary responsibility is to read a clangd index YAML file and transform its contents into an in-memory collection of structured `Symbol` objects.

### Data Classes

This module defines all the essential data classes that represent the elements of the clangd index, ensuring type safety and consistency across the pipeline:

*   **`Location`**: Represents a precise location in a source file (FileURI, line, column).
*   **`RelativeLocation`**: A memory-optimized version of `Location` that stores only line and column, with `FileURI` handled by context.
*   **`Reference`**: Represents a usage of a symbol, including its `Kind`, `Location`, and optionally a `container_id`.
*   **`FunctionSpan`**: Stores the name and `RelativeLocation` of a function's name and body, typically derived from `tree-sitter`.
*   **`Symbol`**: The core entity, representing a function, variable, class, etc., with its ID, name, kind, declaration/definition locations, references, and other properties.
*   **`CallRelation`**: Represents a directed call relationship between two functions.

### Parsing Strategies

The `SymbolParser` offers two distinct strategies for parsing the YAML content, controlled by the `nonstream_parsing` flag:

1.  **Streaming (Single-Pass) Parsing (Default)**:
    *   **Method**: `parse_yaml_content_streaming`
    *   **Behavior**: This is the default and most memory-efficient strategy. It iterates directly over the `yaml.safe_load_all` generator, processing one document at a time.
    *   **Assumption**: It assumes that `!Symbol` documents appear in the YAML stream before any `!Refs` documents that refer to them.
    *   **Benefit**: Avoids loading the entire YAML file into a large list in memory, significantly reducing memory footprint for huge index files.

2.  **Non-Streaming (Two-Pass) Parsing**:
    *   **Method**: `parse_yaml_content_nonstreaming`
    *   **Behavior**: This strategy first loads *all* YAML documents into a Python list in memory. Then, it performs two passes over this list:
        *   **Pass 1**: Collects all `!Symbol` documents to build the `self.symbols` and `self.functions` dictionaries.
        *   **Pass 2**: Collects all `!Refs` documents and attaches their references to the already collected `Symbol` objects.
    *   **Benefit**: More robust if the YAML document order is not strictly guaranteed (i.e., a reference might appear before its symbol's definition).
    *   **Control**: Activated by passing `nonstream_parsing=True` to the `SymbolParser` constructor (typically via the `--nonstream-parsing` command-line argument).

### `Container` Field Detection

The `SymbolParser` automatically detects the presence of the `Container` field in `!Refs` documents (introduced in clangd-indexer 21.x).

*   It sets an internal flag, `self.has_container_field`, to `True` if any `Reference` object successfully extracts a `container_id`.
*   This flag is then used by downstream components (like the `ClangdCallGraphExtractor`) to determine which call graph extraction strategy to use.

## 3. Memory Management

The `SymbolParser` is designed with memory efficiency in mind:
*   The default streaming parsing avoids loading the entire YAML file into memory.
*   Data classes like `RelativeLocation` are used to minimize redundant data storage.
*   The `self.symbols` and `self.functions` dictionaries are the primary in-memory representation of the clangd index, which are then passed to other components.
