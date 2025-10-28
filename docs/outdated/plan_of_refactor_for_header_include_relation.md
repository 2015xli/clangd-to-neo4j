# Plan: Refactoring for Header Include Relation Processing

## 1. Objective

To refactor the code-parsing and data-providing layer of the project to correctly handle C/C++ header file dependencies. This will fix the fundamental flaw in the incremental updater and create a cleaner, more robust, and more efficient architecture for future development.

## 2. Core Strategy

The refactoring is based on four main pillars:

1.  **Enrich the Graph Schema**: Introduce a new `[:INCLUDES]` relationship between `:FILE` nodes in Neo4j. This makes file dependencies a queryable part of the graph.
2.  **Separate Parsing from Management**: Create a dedicated parsing layer (`CompilationParser`) responsible only for parsing files and extracting data. A separate management layer (`CompilationManager`) will handle orchestration, strategy selection, and caching.
3.  **Create a Dedicated Provider**: A new `IncludeRelationProvider` will be created to encapsulate all logic related to the `:INCLUDES` relationship, including ingestion and graph traversal.
4.  **Update Core Pipelines**: The full builder and incremental updater will be modified to use these new components, resulting in a slower but more comprehensive initial build and a correct, fast incremental update.

---

## 3. New & Refactored Components

### `compilation_parser.py` (New File)

This file will contain the low-level parsing logic.

*   **`CompilationParser` (Abstract Base Class)**:
    *   Defines a common interface for all parsing strategies.
    *   Must define methods like `parse(file_paths)`, `get_function_spans()`, and `get_include_relations()`.

*   **`ClangParser(CompilationParser)`**:
    *   The primary implementation using `clang.cindex`.
    *   Its `parse()` method will iterate through the given source files, parse each one as a Translation Unit, and extract **both** function spans and include relations in a single pass to avoid redundant parsing.
    *   The extracted data will be stored internally.

*   **`TreesitterParser(CompilationParser)`**:
    *   A wrapper for the legacy `tree-sitter` logic.
    *   It will fulfill the `CompilationParser` interface but will only provide function span data. The `get_include_relations()` method will return an empty structure.

### `compilation_manager.py` (Rename of `function_span_extractor.py`)

This file will manage the parsing process.

*   **`CompilationManager` (Class)**:
    *   This is the refactored and renamed `SpanExtractor` class.
    *   It will instantiate the chosen parser strategy (`ClangParser` or `TreesitterParser`).
    *   It will be responsible for caching the parsed data (e.g., saving the populated `ClangParser` object to a `.pkl` file) to avoid re-parsing on subsequent runs.
    *   It will act as the central, high-level service that other parts of the application query to get span or include data.

### `include_relation_provider.py` (New File)

This component will own all logic related to the `:INCLUDES` relationship.

*   **`IncludeRelationProvider` (Class)**:
    *   **For the Builder**: It will contain a method like `ingest_include_relations()`. This method will get the full set of include data from the `CompilationManager` and execute the Cypher queries to create all `(:FILE)-[:INCLUDES]->(:FILE)` relationships in the graph.
    *   **For the Updater**: It will contain a method like `get_impacted_files_from_graph(headers)`. This method will take a list of changed/deleted headers and run a transitive Cypher query against the Neo4j graph to find all source files that depend on them.

### Deprecated Components

*   **`function_span_provider.py`**: This module will be deprecated and its logic fully absorbed into the new `CompilationManager` / `ClangParser` structure.

---

## 4. Updated Execution Workflows

### Full Build Workflow (`clangd_graph_rag_builder.py`)

The pipeline will be extended with a new pass.

1.  **Pass 0: Parse Clangd Index**: No change.
2.  **Pass 1: Ingest File/Folder Structure**: No change.
3.  **Pass 2: Ingest Symbol Definitions**: No change.
4.  **New Pass 3: Parse Sources & Ingest Includes**:
    *   The builder will instantiate `CompilationManager` to parse all source files from the `compile_commands.json` database. This happens only once.
    *   The builder will then instantiate `IncludeRelationProvider` and use it to ingest all `[:INCLUDES]` relationships into Neo4j.
5.  **Pass 4 (was 3): Ingest Call Graph**: The `ClangdCallGraphBuilder` will now request function span data from the `CompilationManager` if needed.
6.  **Pass 5 (was 4): Cleanup**: No change.
7.  **Pass 6 (was 5): RAG Generation**: The `RagGenerator` will now request function span data from the `CompilationManager`.

### Incremental Update Workflow (`clangd_graph_rag_updater.py`)

The updater workflow will be completely replaced with this more robust algorithm.

1.  **Phase 1: Identify Git Changes**: Get `added`, `modified`, `deleted` file lists from Git.
2.  **Phase 2: Analyze Impact via Graph Query**:
    *   Instantiate `IncludeRelationProvider`.
    *   Identify all `modified` and `deleted` headers from the Git changes.
    *   Call `provider.get_impacted_files_from_graph()` with these headers. This method queries the existing `:INCLUDES` relationships in Neo4j to find all transitively affected source files.
3.  **Phase 3: Define Full Scope**: The complete set of "dirty files" is the union of (all `added` and `modified` files from Git) + (all impacted files from the graph query).
4.  **Phase 4: Purge Graph**: `DETACH DELETE` all data related to the `deleted` files and the `dirty files`. This includes `:FILE` nodes, symbol nodes, and their `[:DEFINES]` and `[:INCLUDES]` relationships.
5.  **Phase 5: Re-Parse and Re-Ingest**:
    *   Instantiate `CompilationManager` and instruct it to parse **only the dirty files**.
    *   Use the data from the manager to re-ingest all symbols, `:DEFINES` relationships, `:CALLS` relationships, and the new/updated `[:INCLUDES]` relationships for the dirty files.
6.  **Phase 6: RAG Update**: Run the existing targeted RAG update process, using the function symbols from the `dirty files` as the initial seeds.

---

## 5. Action Plan

1.  Create the new file `compilation_parser.py` and define the `CompilationParser`, `ClangParser`, and `TreesitterParser` class skeletons.
2.  Migrate the core parsing logic from `function_span_extractor.py` into `ClangParser`.
3.  Rename `function_span_extractor.py` to `compilation_manager.py` and refactor the `SpanExtractor` class into the new `CompilationManager`, updating it to manage the new parser classes.
4.  Create the new file `include_relation_provider.py` and define the `IncludeRelationProvider` class skeleton.
5.  Modify `clangd_graph_rag_builder.py` to implement the new "Parse Sources & Ingest Includes" pass.
6.  Rewrite `clangd_graph_rag_updater.py` to implement the new, correct incremental update algorithm.
7.  Update all calls to the old `FunctionSpanProvider` or `SpanExtractor` to use the new `CompilationManager`.
8.  Delete the now-empty `function_span_provider.py` file.
