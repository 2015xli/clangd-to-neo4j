# Algorithm Summary: `clangd_symbol_nodes_builder.py`

## 1. Role in the Pipeline

This script is responsible for Passes 1 and 2 of the ingestion pipeline. Its purpose is to build the structural foundation of the code graph in Neo4j. It creates the physical file system hierarchy (`:PROJECT`, `:FOLDER`, `:FILE`) and the logical code symbols (`:FUNCTION`, `:DATA_STRUCTURE`) defined within them, along with the crucial `:DEFINES` relationships connecting them.

It operates on the in-memory collection of `Symbol` objects provided by the `clangd_index_yaml_parser`.

## 2. Standalone Usage

The script can be run directly to perform a partial ingestion of file structure and symbol definitions, which is useful for debugging.

```bash
# Example: Ingest symbols using the default parallel-create strategy
python3 clangd_symbol_nodes_builder.py /path/to/index.yaml /path/to/project/
```

**All Options:**

*   `index_file`: Path to the clangd index YAML file (or a `.pkl` cache file).
*   `project_path`: Root path of the project.
*   `--defines-generation`: Strategy for ingesting `:DEFINES` relationships (`unwind-create`, `parallel-merge`, `parallel-create`). Default: `parallel-create`.
*   ... and other performance tuning arguments (`--num-parse-workers`, `--cypher-tx-size`, etc.).

---
*The following sections describe the library's internal logic.*

## 3. Pass 1: Ingesting File & Folder Structure (`PathProcessor`)

This pass builds the graph representation of the physical file system.

*   **Algorithm**:
    1.  **Path Discovery**: The `PathProcessor` iterates through every symbol from the parser and inspects its declaration and definition locations. From these file URIs, it derives a unique set of all file paths and, crucially, all of their parent folder paths, ensuring the entire directory tree is captured.
    2.  **Batched Ingestion**: It uses highly efficient, batched Cypher queries with `UNWIND` and `MERGE` to first create all `:FOLDER` and `:FILE` nodes, and then to create the `:CONTAINS` relationships between them. This minimizes network round trips and leverages Neo4j's bulk operation capabilities.

## 4. Pass 2: Ingesting Symbols and Relationships (`SymbolProcessor`)

This pass populates the graph with logical code constructs.

### Symbol Node Creation

*   **Filtering**: The processor first filters the full list of symbols. **A key design choice is that nodes are only created for `:FUNCTION` and `:DATA_STRUCTURE` (Struct, Class, Union, Enum) symbols.** Other symbols like variables are parsed but not materialized as nodes in the graph, as they are less critical for the primary call-graph analysis and RAG objectives.
*   **Ingestion**: It uses batched `UNWIND` + `MERGE` queries to efficiently create all `:FUNCTION` and `:DATA_STRUCTURE` nodes.

### The `:DEFINES` Relationship Challenge

Creating the `:DEFINES` relationships (linking a file to the symbols it defines) is a major performance challenge due to the sheer volume of relationships. The script uses several sophisticated strategies to handle this efficiently.

*   **Critical Performance Optimization**: A massive performance gain (from ~6 hours to ~1 minute on the Linux kernel) was achieved by pre-filtering the relationship data and making the Cypher `MATCH` clause more specific. Instead of a generic `MATCH (n {id: ...})`, the query now uses `MATCH (n:FUNCTION {id: ...})` or `MATCH (n:DATA_STRUCTURE {id: ...})`. This allows Neo4j to use its label-based indexes and dramatically speeds up node lookups.

Three strategies are available via the `--defines-generation` flag:

1.  **`parallel-create` (Default)**
    *   **Algorithm**: Uses `apoc.periodic.iterate` with a `CREATE` clause. This is the fastest method.
    *   **Subtlety**: This strategy is **not idempotent**. It assumes it is writing to a clean database and will create duplicate relationships if run again. It is the default because the main build pipeline always starts with a fresh database, making this a safe and optimal choice for the primary use case.

2.  **`parallel-merge` (Idempotent & Deadlock-Safe)**
    *   **Algorithm**: Uses `apoc.periodic.iterate` with a `MERGE` clause. This is the safest option for running on a partially-existing graph.
    *   **Deadlock Avoidance Subtlety**: A simple parallel `MERGE` can cause deadlocks when multiple threads try to lock the same `:FILE` node simultaneously. This strategy avoids this by first grouping all `:DEFINES` relationships by their target `:FILE` node on the client side. It then passes these *groups* to `apoc.periodic.iterate`. The APOC procedure processes the groups in parallel, but since all relationships for a given file are in a single group, no two threads will ever compete for a lock on the same file node, completely eliminating the cause of deadlocks.

3.  **`unwind-create`**
    *   **Algorithm**: A simpler, sequential strategy that uses client-side batching with `UNWIND` and `CREATE`. It does not use the APOC library. While now much faster due to the `MATCH` clause optimization, it is empirically slower than the parallel APOC-based methods for very large datasets.
