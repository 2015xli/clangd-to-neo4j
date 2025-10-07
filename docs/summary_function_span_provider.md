# Algorithm Summary: `function_span_provider.py`

## 1. Role in the Pipeline

This script acts as a **library module** that centralizes the functionality of extracting precise function body locations (spans) from C/C++ source files. It uses `tree-sitter` to parse the code and then maps these spans to the `Symbol` objects obtained from the `clangd` index parser.

This module is crucial for scenarios where the `clangd` index (older versions) does not provide `Container` information for references, making it necessary to determine the calling function based on spatial location.

## 2. Core Logic

The `FunctionSpanProvider` class orchestrates the process of span extraction and matching.

### Architecture

1.  **Initialization**: Upon instantiation, it automatically triggers the span extraction and matching process.
2.  **`tree-sitter` Integration**: It leverages the `SpanExtractor` (from `tree_sitter_span_extractor.py`) to perform the actual parsing of source files and identification of function definition spans.
3.  **Symbol Enrichment**: It takes a `SymbolParser` instance and enriches its `Symbol` objects (specifically functions) with `body_location` information, which includes the file path and start/end line/column of the function's body.

### Algorithm Details

#### `_extract_spans_from_project()`

-   Initializes a `SpanExtractor` and calls its `get_function_spans_from_folder` method to recursively scan the project directory for `.c` and `.h` files.
-   Parses each file using `tree-sitter` to identify `function_definition` nodes and extract their name and body locations.
-   Stores these extracted spans, grouped by `FileURI`, in an internal dictionary (`function_spans_by_file`).
-   Includes memory optimization by explicitly deleting the `SpanExtractor` and invoking garbage collection after span extraction.

#### `_match_function_spans()`

-   This method links the `tree-sitter` generated spans to the `clangd` `Symbol` objects.
-   It creates a lookup dictionary (`spans_lookup`) using a composite key of `(function_name, file_uri, start_line, start_column)` from the `tree-sitter` spans.
-   It then iterates through all function `Symbol` objects provided by the `SymbolParser`.
-   For each `Symbol` that has a definition location, it constructs a matching key and attempts to find a corresponding span in the `spans_lookup`.
-   If a match is found, the `body_location` property of the `Symbol` object is updated with the precise body span.
-   Additionally, it builds an internal map (`_body_spans_by_id`) for quick retrieval of body spans by `function_id`.
-   Performs cleanup of intermediate data structures and garbage collection to manage memory.

## 3. Key Methods & Output

-   **`get_body_span(function_id: str)`**: A public method to retrieve the body span (file path, start/end lines/columns) for a given function ID.
-   **`get_matched_function_ids()`**: Returns a list of all function IDs for which a body span was successfully matched.

The module ensures that `Symbol` objects are enriched with accurate body location data, which is then used by other parts of the pipeline (e.g., `clangd_call_graph_builder.py` for legacy `clangd` index formats, and `code_graph_rag_generator.py` for extracting source code).