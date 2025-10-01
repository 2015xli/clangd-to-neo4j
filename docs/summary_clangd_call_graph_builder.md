# Algorithm Summary: `clangd_call_graph_builder.py`

## 1. Role in the Pipeline

This script acts as a **library module** for the main `clangd_code_graph_builder.py` orchestrator. Its sole responsibility is to perform Pass 3 of the ingestion pipeline: identifying all function call relationships and generating the query to create them in Neo4j.

It provides the `ClangdCallGraphExtractor` class, which encapsulates this logic.

## 2. Core Logic

The fundamental challenge in building a call graph is that the `clangd` index provides call sites, but doesn't explicitly link them to the function that contains them (the caller). This module solves this by bridging the `clangd` data with function body spans extracted by `tree-sitter`.

### Algorithm

1.  **Initialization**: The class is initialized with a `SymbolParser` object that contains the pre-parsed symbols and functions from the clangd index. This avoids re-parsing the large index file.

2.  **Span Loading**: The class can acquire function span data in two ways:
    *   `load_spans_from_project(project_path)`: This is the primary method used by the orchestrator. It encapsulates the `SpanExtractor` logic, running it on a project directory to generate function spans on the fly.
    *   `load_function_spans(spans_file)`: This method can be used to load a pre-computed YAML file containing function spans.

3.  **Span Matching**: After loading the spans, it matches the `clangd` function symbols (from the `SymbolParser` object) to the `tree-sitter` function spans. This uses a composite key of `(function_name, file_uri, start_line, start_column)` and enriches the `Symbol` objects with a memory-efficient `RelativeLocation` for their function body.

4.  **Call Relationship Extraction**: The `extract_call_relationships` method uses an optimized, spatially-indexed approach to find call relationships.
    *   **Spatial Index Creation**: It builds an in-memory "spatial index" from the function symbols that have a body location. This is a dictionary where keys are file URIs, and values are lists of function bodies in that file.
    *   **Optimized Lookup**: It iterates through every symbol's references (`Kind: 12`). For each call site, it uses the index to efficiently find the containing function body (the caller).
    *   **Relation Recording**: Once the containing function is found, it records a `(caller, callee)` `CallRelation` object.

5.  **Memory Management**: The class is designed to be memory-efficient. It deletes large intermediate data structures (like the span data and the spatial index) as soon as they are no longer needed, and triggers the garbage collector to keep the memory footprint low.

## 3. Output

Once all call relations have been discovered, the static method `get_call_relation_ingest_query(call_relations)` is called.

-   **Efficient Query Generation**: This method generates a single, highly performant, parameterized Cypher query using the `UNWIND` clause.
-   **Return Value**: It returns a tuple containing the Cypher query string and a dictionary of parameters.

This output is then passed back to the main orchestrator, which executes the query to merge all `:CALLS` relationships into the graph.