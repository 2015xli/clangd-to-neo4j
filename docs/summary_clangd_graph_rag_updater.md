# Summary: `clangd_graph_rag_updater.py` - Incremental Code Graph RAG Updater

This document summarizes the design and functionality of `clangd_graph_rag_updater.py`. This script is responsible for incrementally updating the Neo4j code graph based on changes in a Git repository.

The logic was significantly refactored to correctly handle header file dependencies, overcoming a flaw in the original "mini-index" approach.

## 1. Purpose

The primary purpose of `clangd_graph_rag_updater.py` is to provide an efficient mechanism for keeping the Neo4j code graph synchronized with an evolving C/C++ codebase. This avoids the computationally expensive process of re-ingesting the entire project for minor changes.

## 2. Core Design: Graph-Based Dependency Analysis

The updater's core logic revolves around a robust, multi-stage process to determine the full impact of any code change. It no longer relies on a simple 1-hop call graph expansion, but instead uses the `[:INCLUDES]` relationships in the graph to find all files affected by a change.

## 3. The Incremental Update Pipeline

The update process is divided into a sequence of phases orchestrated by the `GraphUpdater` class.

### Phase 1: Identify Git Changes

*   **Component**: `git_manager.GitManager`
*   **Purpose**: To determine which source files (`.c`, `.h`, etc.) have been `added`, `modified`, or `deleted` between two Git commits. This provides the initial set of changed files.

### Phase 2: Analyze Header Impact via Graph Query

*   **Component**: `include_relation_provider.IncludeRelationProvider`
*   **Purpose**: To find all source files that are indirectly affected by header file changes. This is the key to correctly handling cascading updates from macros or type definitions.
*   **Mechanism**:
    1.  It takes the list of `modified` and `deleted` headers from Phase 1.
    2.  It queries the Neo4j graph, asking, "Find all `:FILE` nodes that have a transitive `[:INCLUDES]` relationship to any of these headers."
    3.  The result is a set of all source files that depend on the changed headers.
*   **Limitation**: This process is only effective if the modified header already exists as a node in the graph. If an "invisible header" is modified, this step will not find its dependents.

### Phase 3: Purge Stale Graph Data

*   **Purpose**: To remove all outdated information from the graph, creating a clean slate for the new data.
*   **Mechanism**:
    1.  First, it determines the complete set of **"dirty files"**: the union of textually changed files from Git (Phase 1) and impacted files found from the graph query (Phase 2).
    2.  It then runs a series of targeted `DELETE` queries to remove all data originating from these files:
        *   `DETACH DELETE` is used on `:FUNCTION` and `:DATA_STRUCTURE` nodes defined in the dirty/deleted files.
        *   `[:INCLUDES]` relationships originating from dirty files are deleted.
        *   `:FILE` nodes for deleted files are deleted, along with any newly-empty parent folders.

### Phase 4: Re-ingest Dirty Files

*   **Purpose**: To surgically "patch" the graph with the new, updated information.
*   **Mechanism**: This phase re-runs the core ingestion logic, but on a much smaller scope.
    1.  **Parse Sources**: It calls the `CompilationManager` to parse *only the dirty files*, gathering their fresh include relationships and function spans.
    2.  **Parse Symbols**: It parses the **entire new `clangd` index file** to get the most up-to-date information for all symbols.
    3.  **Create Mini-Parser**: It creates a small, in-memory `SymbolParser` containing only the symbols whose definitions are located within one of the dirty files.
    4.  **Re-run Processors**: It re-runs the standard `PathProcessor`, `SymbolProcessor`, `IncludeRelationProvider`, and `ClangdCallGraphExtractor` using the data from the mini-parser and the compilation manager. This repopulates the graph with the correct nodes and relationships for the updated files.

### Phase 5: Targeted RAG Update

*   **Purpose**: To efficiently update AI-generated summaries and embeddings.
*   **Component**: `code_graph_rag_generator.RagGenerator`
*   **Mechanism**: It calls the `summarize_targeted_update()` method, providing the set of all function IDs from the "mini-parser" as the initial "seed" for the update. The RAG generator then intelligently re-summarizes these functions and their immediate neighbors, and rolls the changes up the file hierarchy.

### Final Step: Update Commit Hash

*   After all phases are complete, the `:PROJECT` node in the graph is updated with the new commit hash, bringing the database's recorded state in sync with the codebase.