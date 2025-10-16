# Plan for Incremental Graph Updates

## 1. Objective

To implement an efficient, incremental update mechanism for the Neo4j code graph. This process will synchronize the graph with new code changes from a Git repository without requiring a costly full rebuild of the entire database.

## 2. Core Strategy: A Hybrid "Diff-and-Patch" Approach

The strategy is a multi-phase, hybrid approach that leverages different tools for what they do best:

1.  **Git**: To efficiently identify which source files have changed between commits.
2.  **`tree-sitter` + Graph Query**: To perform a very fast analysis of the changed files to determine which symbols (`:FUNCTION` and `:DATA_STRUCTURE`) were likely added, deleted, or textually modified.
3.  **New `clangd` Index**: To act as the ultimate "ground truth" for semantic information, providing stable Symbol IDs and definitive relationship data for the new state of the code.

This approach is designed to be **fast** by completely avoiding the need to parse the old `clangd.yaml` file. It remains **correct** by using the new `clangd.yaml` to verify changes and reconcile relationships, which avoids the pitfalls of a purely text-based analysis (e.g., missing macro-induced changes).

## 3. The Orchestrator: `graph_updater.py`

A new standalone script, `graph_updater.py`, will be created to orchestrate the entire update process. It will manage the execution of the phases described below.

## 4. Detailed Execution Phases

### Phase 1: Identify Changed Files & Folders

The script will first determine the scope of the changes.

1.  **Get Last Processed Commit**: The script will query the `:PROJECT` node in Neo4j to retrieve the commit hash of the last successfully processed update.
2.  **Find Changed Files**: Using `gitpython`, the script will get the list of added, deleted, and modified source files (`.c`, `.h`) between the last commit and the target commit.
3.  **Update File/Folder Structure**: Based on the lists from the previous step:
    *   For **added** files, `MERGE` the corresponding `:FILE` and parent `:FOLDER` nodes and their `:CONTAINS` relationships.
    *   For **deleted** files, `MATCH` the `:FILE` node by its path and `DETACH DELETE` it. A follow-up query will prune any newly-empty `:FOLDER` nodes.

### Phase 2: Reconciliation of Symbols

This phase identifies exactly which symbols have been added, deleted, or modified. It reuses logic from `FunctionSpanProvider` for maximum efficiency and correctness.

1.  **Get "Before" State**: The script queries the graph to get a single set of all symbol IDs (`:FUNCTION` and `:DATA_STRUCTURE`) defined within the files identified in Phase 1. This gives the `global_old_ids` set.

2.  **Get "After" State**:
    *   The script parses the **new `clangd.yaml`** file into a `symbol_parser` object.
    *   It then instantiates a modified `FunctionSpanProvider`, passing it the `symbol_parser` and the list of changed files that still exist.
    *   The provider matches `tree-sitter` results from the files against the `clangd` symbols, and we get back the `global_new_ids` set.

3.  **Determine Change Sets**: A simple set comparison gives us our final lists:
    *   `deleted_ids = global_old_ids - global_new_ids`
    *   `added_ids = global_new_ids - global_old_ids`
    *   `modified_ids = global_old_ids & global_new_ids` (pragmatically treating all persisted symbols as potentially modified).

### Phase 3: Surgical Graph Patching

With the definitive lists of symbol IDs, the script performs a surgical patch on the graph.

1.  **Handle `deleted_ids`**:
    *   For each ID, a `MATCH (s {id: $id}) DETACH DELETE s` query is executed. This removes the node and all its relationships (`:DEFINES`, `:CALLS`, etc.) automatically.

2.  **Handle `added_ids`**:
    *   For each ID, we look up its full `SymbolObject` from the parsed `clangd` data.
    *   We `CREATE` the new node with the correct label (`:FUNCTION` or `:DATA_STRUCTURE`).
    *   **`:DEFINES`**: We get the definition file path and `CREATE` the `(symbol)-[:DEFINES]->(file)` relationship.
    *   **`:CALLS`**: If it's a function, we find its incoming/outgoing calls from the `clangd` data and `CREATE` those relationships.

3.  **Handle `modified_ids`**:
    *   For each ID, we update its properties in-place: `MATCH (s {id: $id}) SET s += {new_properties}`.
    *   **`:DEFINES` (for moves)**: We compare the symbol's old definition file (from the graph) with its new one (from `clangd` data). If they differ, we `DELETE` the old `:DEFINES` relationship and `CREATE` the new one.
    *   **`:CALLS` (for functions)**: We surgically update `:CALLS` relationships by comparing the "before" state (from the graph) and the "after" state (from `clangd` data) and issuing targeted `CREATE` and `DELETE` queries for only the changed relationships.

### Phase 4: One-Step "Smart Summary" & Embedding Update

This phase updates the AI-generated data for all affected symbols.

1.  **Identify Scope**: The set of symbols needing a potential summary update includes all `added_ids`, `modified_ids`, and their direct 1-hop `:FUNCTION` neighbors.
2.  **Execute One-Step Prompt**: For each function in the scope, we use the single, efficient prompt that asks the LLM to either return `"No change needed"` or the new summary.
3.  **Apply Updates**: If a new summary is returned, we update the `summary` property on the node.
4.  **Roll-up Summaries**: For any files containing symbols whose summaries *were* changed, we trigger the roll-up summary generation for their parent files and folders.
5.  **Update Embeddings**: New vector embeddings are generated for any node whose `summary` property was updated.
