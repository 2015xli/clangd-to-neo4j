# Plan for Incremental Graph Updates (Mini-Index Approach)

## 1. Objective

To implement an efficient, incremental update mechanism for the Neo4j code graph. This process will synchronize the graph with new code changes from a Git repository without requiring a costly full rebuild of the entire database.

## 2. Core Strategy: A "File-Centric Re-ingestion" Approach

This strategy is based on deleting all graph data corresponding to changed files and then re-ingesting a small, self-sufficient subset of the new `clangd` index to rebuild the affected area.

1.  **Git**: To efficiently identify which source files have been added, modified, deleted, or renamed.
2.  **Graph Purge**: To create a "hole" in the graph by deleting all symbols and files related to the changes.
3.  **Mini-Index Creation**: To build a small, in-memory, self-sufficient index containing all the symbols and relationships needed to correctly refill the hole, including 1-hop neighbors from unchanged files.
4.  **Pipeline Reuse**: To re-run the existing, optimized ingestion pipeline on the mini-index to patch the graph.

This approach prioritizes high code reuse and a conceptually simple data flow.

## 3. The Orchestrator: `graph_updater.py`

A new standalone script, `graph_updater.py`, will be created to orchestrate the entire update process.

## 4. Detailed Execution Phases

### Phase 1: Identify Changed Files (via Git)

The script will first determine the scope of the changes.

1.  **Get Last Processed Commit**: The script will query the `:PROJECT` node in Neo4j to retrieve the commit hash of the last successfully processed update.
2.  **Find Changed Files**: Using `gitpython`, the script will get the lists of `added`, `modified`, `deleted`, and `renamed` source files (`.c`, `.h`) between the last commit and the target commit.

### Phase 2: Purge Stale Graph Data

This phase is focused only on deletion to create a clean "hole" in the graph for the new data.

1.  **Delete Stale Files**: `MATCH` and `DETACH DELETE` the `:FILE` nodes corresponding to files in the `deleted` and `renamed` (source) lists. A follow-up query can then prune any folders that become empty.
2.  **Delete Stale Symbols**: `MATCH` and `DETACH DELETE` all `:FUNCTION` and `:DATA_STRUCTURE` nodes that were defined in any of the `modified`, `deleted`, or `renamed` (source) files.

### Phase 3: Build Self-Sufficient "Mini-Index"

This is the core data preparation step. Instead of working with the full `clangd` index, we build a small, relevant subset.

1.  **Parse New `clangd.yaml`**: The script parses the entire new `clangd` index file into a `full_symbol_parser` object one time.
2.  **Identify Seed Symbols**: From the `full_symbol_parser` data, create a "seed set" of all symbols that are defined in the `added`, `modified`, and `renamed` (destination) files.
3.  **Grow to 1-Hop Neighbors**: Perform a graph traversal *on the parsed YAML data* to find all symbols that are direct callers or callees of the seed symbols. This ensures that symbols from unchanged files that are part of a new relationship are included.
4.  **Collect Data**: Gather all the `!Symbol` and `!Refs` documents for the complete set (seeds + neighbors).
5.  **Create Mini-Index**: Represent this self-sufficient dataset as a new, in-memory `SymbolParser` object. This object is the "mini-index."

### Phase 4: Re-run Ingestion Pipeline on Mini-Index

This phase reuses the existing, optimized ingestion components in the correct order.

1.  **Rebuild File Structure**: Instantiate `PathProcessor` and call its `ingest_paths` method with the symbols from the mini-index. This will discover and `MERGE` all necessary `:FILE` and `:FOLDER` nodes and their `:CONTAINS` relationships.
2.  **Rebuild Symbols and `:DEFINES`**: Instantiate `SymbolProcessor` and call its `ingest_symbols_and_relationships` method. This will `MERGE` the `:FUNCTION` and `:DATA_STRUCTURE` nodes and their `:DEFINES` relationships.
3.  **Rebuild Call Graph**: Instantiate `ClangdCallGraphExtractor` to `MERGE` all the `:CALLS` relationships for the functions in the mini-index.
4.  **Idempotency Note**: All relationship creation logic used in this phase must use `MERGE` instead of `CREATE` to prevent duplicates.

### Phase 5: RAG Summary Generation

The scope of this phase is naturally limited to the symbols present in the mini-index.

1.  **Identify Scope**: The set of symbols needing a potential summary update includes all symbols in the `added` and `modified` sets, plus their direct `:FUNCTION` neighbors.
2.  **Execute One-Step Prompt**: For each function in the scope, use the single, efficient prompt that asks the LLM to either return `"No change needed"` or the new summary.
3.  **Apply & Roll-up**: Apply new summaries and roll them up the file/folder hierarchy as needed.