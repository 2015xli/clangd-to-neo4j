# Algorithm Summary: `clangd_call_graph_builder.py`

## 1. Role in the Pipeline

This script acts as both a **library module** and a **standalone tool**. Its primary responsibility is to perform Pass 3 of the ingestion pipeline: identifying all function call relationships (`:CALLS`) and either ingesting them into Neo4j or generating the Cypher queries to do so.

As a library, it's used by the main `clangd_code_graph_builder.py` orchestrator. It provides a set of classes (`BaseClangdCallGraphExtractor`, `ClangdCallGraphExtractorWithContainer`, `ClangdCallGraphExtractorWithoutContainer`) that encapsulate the extraction logic.

As a standalone tool, it can be used to extract the call graph from a `clangd` index and either ingest it directly into an existing Neo4j database or save the Cypher queries to a file for later use. See the "Standalone Usage" section for details.

## 2. Standalone Usage

The script can be run directly to perform call graph extraction. This is useful for debugging the call graph logic or for regenerating only the `:CALLS` relationships in the database.

```bash
# Example: Extract call graph and ingest directly into Neo4j
python3 clangd_call_graph_builder.py /path/to/index.yaml /path/to/project/ --ingest

# Example: Extract call graph and save the Cypher queries to a .cql file
python3 clangd_call_graph_builder.py /path/to/index.yaml /path/to/project/
```

**All Options:**

*   `input_file`: Path to the clangd index YAML file (or a `.pkl` cache file).
*   `span_path`: Path to a pre-computed spans YAML file, or a project directory to scan for spans (required for older clangd index formats).
*   `--ingest`: If set, ingest the call graph directly into Neo4j. Otherwise, a `generated_call_graph_cypher_queries.cql` file will be created.
*   `--stats`: Show detailed statistics about the extracted call graph.
*   `--num-parse-workers`: Number of parallel workers for parsing the YAML index.
*   `--ingest-batch-size`: Batch size for ingesting call relations.

---
*The following sections describe the library's internal logic.*

## 3. Core Logic

The fundamental challenge in building a call graph is that the `clangd` index provides call sites, but doesn't explicitly link them to the function that contains them (the caller). This module addresses this by offering two distinct strategies, adapting to the format of the clangd index.

### Architecture

The module employs an inheritance-based architecture for clarity and code reuse:

*   **`BaseClangdCallGraphExtractor`**: This is the base class that holds common attributes (`symbol_parser`, `log_batch_size`) and shared methods like `get_call_relation_ingest_query` and `generate_statistics`.
*   **`ClangdCallGraphExtractorWithContainer`**: This class is used when the clangd index (version 21.x and later) provides the `Container` field in `!Refs` documents. It directly uses this field for efficient call graph extraction.
*   **`ClangdCallGraphExtractorWithoutContainer`**: This class is used for older clangd index formats (pre-21.x) that lack the `Container` field. It falls back to using `tree-sitter` generated function spans and spatial lookup.

### Algorithm Details

Both extractor classes are initialized with a `SymbolParser` object, which provides the pre-parsed symbols and functions from the clangd index.

#### `ClangdCallGraphExtractorWithContainer` (New Format Strategy)

This strategy is used when `symbol_parser.has_container_field` is `True`.

1.  **Direct Call Relationship Extraction**: The `extract_call_relationships` method directly iterates through all `Symbol` objects and their `references` (from the `SymbolParser`).
2.  **Leveraging `Container` Field**: If a `reference.container_id` is present (and not the '0' placeholder ID) and the `reference.kind` indicates a call (e.g., `28` or `20`), it directly identifies the `caller_id`.
3.  **Caller Validation**: It then looks up the `caller_symbol` using `caller_id` and asserts that it exists and is a function.
4.  **Relation Recording**: A `(caller, callee)` `CallRelation` object is recorded. This method is highly efficient as it bypasses `tree-sitter` span extraction entirely.

#### `ClangdCallGraphExtractorWithoutContainer` (Legacy Format Strategy)

This strategy is used when `symbol_parser.has_container_field` is `False`.

1.  **Span Loading**: This class can acquire function span data in two ways:
    *   `load_spans_from_project(project_path)`: This is the primary method used by the orchestrator. It encapsulates the `SpanExtractor` logic, running it on a project directory to generate function spans on the fly.
    *   `load_function_spans(spans_file)`: This method can be used to load a pre-computed YAML file containing function spans.
2.  **Span Matching**: After loading the spans, it matches the `clangd` function symbols (from the `SymbolParser` object) to the `tree-sitter` function spans. This uses a composite key of `(function_name, file_uri, start_line, start_column)` and enriches the `Symbol` objects with a memory-efficient `RelativeLocation` for their function body.
3.  **Call Relationship Extraction**: The `extract_call_relationships` method uses an optimized, spatially-indexed approach to find call relationships.
    *   **Spatial Index Creation**: It builds an in-memory "spatial index" from the function symbols that have a body location. This is a dictionary where keys are file URIs, and values are lists of function bodies in that file.
    *   **Optimized Lookup**: It iterates through every symbol's references (`Kind: 12` or `4`). For each call site, it uses the index to efficiently find the containing function body (the caller).
    *   **Relation Recording**: Once the containing function is found, it records a `(caller, callee)` `CallRelation` object.

### Memory Management

Both classes are designed to be memory-efficient. They delete large intermediate data structures (like the span data and the spatial index) as soon as they are no longer needed, and trigger the garbage collector to keep the memory footprint low.

## 4. Output

Once all call relations have been discovered, the `get_call_relation_ingest_query` method (from the base class) is called.

-   **Efficient Query Generation**: This method generates a single, highly performant, parameterized Cypher query using the `UNWIND` clause.
-   **Return Value**: It returns a tuple containing the Cypher query string and a dictionary of parameters.

This output is then passed back to the main orchestrator, which executes the query to merge all `:CALLS` relationships into the graph.