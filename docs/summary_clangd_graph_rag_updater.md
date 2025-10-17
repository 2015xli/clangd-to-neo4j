# Summary: `clangd_graph_rag_updater.py` - Incremental Code Graph RAG Updater

This document summarizes the design and functionality of `clangd_graph_rag_updater.py`, a script responsible for incrementally updating the Neo4j code graph with RAG (Retrieval Augmented Generation) data based on changes in a Git repository. It leverages a "Mini-Index Approach" to efficiently synchronize the graph without requiring a full rebuild.

## 1. Purpose

The primary purpose of `clangd_graph_rag_updater.py` is to provide an efficient mechanism for keeping the Neo4j code graph, including its AI-generated summaries and vector embeddings, synchronized with an evolving C/C++ codebase. This avoids the computationally expensive process of re-ingesting the entire codebase for minor changes.

## 2. Architecture Overview

The `clangd_graph_rag_updater.py` script orchestrates a multi-phase incremental update process. It reuses existing ingestion pipeline components where possible, focusing on processing only the changed portions of the codebase.

## 3. Key Design Principles

*   **Incremental Processing**: Only processes files and symbols affected by recent Git commits.
*   **"Mini-Index" Approach**: Constructs a small, in-memory `SymbolParser` (mini-index) containing only the relevant symbols and their 1-hop neighbors for efficient re-ingestion.
*   **Reusability**: Maximizes reuse of existing `clangd_index_yaml_parser`, `clangd_symbol_nodes_builder`, `clangd_call_graph_builder`, and `code_graph_rag_generator` components.
*   **Modularity**: Each phase of the update is handled by dedicated methods within the `GraphUpdater` class.
*   **Git-Driven**: Relies on Git to accurately identify changed files between commits.

## 4. Ingestion Pipeline Phases (Orchestrated by `GraphUpdater.run_update()`)

The update process is divided into five main phases:

### Phase 1: Identify Changed Files (`_identify_changed_files`)

*   **Purpose**: Determines which source files (`.c`, `.h`) have been added, modified, or deleted between a specified `old_commit` and `new_commit`.
*   **Mechanism**: Utilizes `git_manager.GitManager.get_categorized_changed_files()` to obtain a consolidated list of `added`, `modified`, and `deleted` files. Renamed files are treated as a deletion of the original path and an addition of the new path.
*   **Output**: A dictionary containing lists for `added`, `modified`, and `deleted` files.

### Phase 2: Purge Stale Graph Data (`_purge_stale_data`)

*   **Purpose**: Removes outdated nodes and relationships from the Neo4j graph corresponding to the identified changes.
*   **Mechanism**: 
    *   Deletes `:FILE` nodes for files that were deleted or were the original path of a renamed file.
    *   Deletes `:FUNCTION` and `:DATA_STRUCTURE` nodes that were defined in modified, deleted, or original renamed files using a `DETACH DELETE` to also remove their relationships.
*   **Output**: A "hole" in the graph, ready for new data.

### Phase 3: Build Self-Sufficient "Mini-Index" (`_build_mini_index`)

*   **Purpose**: Creates a focused, in-memory representation of the `clangd` index data relevant to the changes.
*   **Mechanism**: 
    *   Parses the entire new `clangd` index YAML file into a `full_symbol_parser` object.
    *   Identifies "seed symbols" (symbols defined in `added` or `modified` files).
    *   **Correctly expands this set to include 1-hop neighbors** by iterating through the `full_symbol_parser.symbols` data structure:
        *   **Finds Callers**: For each seed symbol, it inspects its `references` list to find the `container_id` of any incoming calls.
        *   **Finds Callees**: It iterates through all symbols in the parser, checking their `references` list to see if any are called by a seed symbol.
    *   Creates a `mini_index_parser` (a subset `SymbolParser`) containing only these relevant symbols (seeds + neighbors).
    *   Stores the initial `seed_symbol_ids` for use in the targeted RAG update in Phase 5.
*   **Output**: A `SymbolParser` object representing the mini-index.

### Phase 4: Re-run Ingestion Pipeline on Mini-Index (`_rerun_ingestion_pipeline`)

*   **Purpose**: Re-ingests the data from the mini-index into Neo4j, patching the "hole" created in Phase 2.
*   **Mechanism**: Reuses existing processors with idempotent `MERGE` operations:
    *   `PathProcessor`: Rebuilds file and folder structure.
    *   `SymbolProcessor`: Rebuilds symbol nodes and `:DEFINES` relationships.
    *   `ClangdCallGraphExtractor`: Rebuilds `:CALLS` relationships.

### Phase 5: RAG Summary Generation (`_update_summaries`)

*   **Purpose**: Updates AI-generated summaries and vector embeddings for the affected parts of the graph.
*   **Mechanism**: 
    *   Initializes the `RagGenerator`.
    *   Calls `rag_generator.summarize_targeted_update()` with the `seed_symbol_ids` saved from Phase 3.
*   **Result-Driven Workflow Subtlety**: This triggers a highly efficient, multi-pass process within the `RagGenerator`. The key to its efficiency is that it's a result-driven workflow. Pass 1 (code-only summaries) returns the precise set of functions that were actually updated. This set is then used to define the scope for Pass 2 (context-aware summaries). Pass 2, in turn, returns the precise set of functions whose final `summary` property changed. This final set is then used to determine the exact files and folders that require their "roll-up" summaries to be recalculated. This prevents unnecessary processing of functions, files, or folders that were not affected by the initial code changes.

## 5. Command-Line Arguments

The script accepts the following arguments:

*   `project_path`: Root path of the project being indexed.
*   `index_file`: Path to the NEW `clangd` index YAML file for the target commit.
*   `--old-commit`: The old commit hash or reference (defaults to `HEAD^`).
*   `--new-commit`: The new commit hash or reference (defaults to `HEAD`).
*   `--generate-summary`: Flag to enable RAG summary and embedding generation.
*   `--llm-api`: The LLM API to use (`openai`, `deepseek`, `ollama`).
*   `--num-local-workers`: Number of parallel workers for local LLMs/embedding models.
*   `--num-remote-workers`: Number of parallel workers for remote LLM/embedding APIs.

## 6. Dependencies

*   `git_manager.py`: For Git operations.
*   `neo4j_manager.py`: For Neo4j database interactions.
*   `clangd_index_yaml_parser.py`: For parsing `clangd` index YAML files.
*   `clangd_symbol_nodes_builder.py`: For ingesting file structure and symbol definitions.
*   `clangd_call_graph_builder.py`: For ingesting call graph relationships.
*   `function_span_provider.py`: For extracting function source code spans.
*   `code_graph_rag_generator.py`: For AI-generated summaries and embeddings.
*   `llm_client.py`: For LLM and embedding API interactions.
*   `GitPython`: Python library for Git.
*   `neo4j`: Python driver for Neo4j.
*   `PyYAML`: For YAML parsing.
*   `tqdm`: For progress bars.
