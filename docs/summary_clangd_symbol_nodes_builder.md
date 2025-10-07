# Algorithm Summary: `clangd_symbol_nodes_builder.py`

## 1. Role in the Pipeline

This script acts as a **library module** for the main `clangd_code_graph_builder.py` orchestrator. Its primary responsibility is to build the structural foundation of the code graph in Neo4j. It creates the physical file system hierarchy and the logical code symbols defined within them.

It is designed to work on a pre-parsed, in-memory collection of `Symbol` objects provided by the `SymbolParser`.

It provides two main classes:
-   `PathProcessor`: Creates all `:PROJECT`, `:FOLDER`, and `:FILE` nodes.
-   `SymbolProcessor`: Creates nodes for code symbols (e.g., `:FUNCTION`, `:DATA_STRUCTURE`) and the `:DEFINES` relationships connecting them to their files.

## 2. `PathProcessor`

This class is responsible for Pass 1 of the ingestion pipeline. Its algorithm is straightforward:

1.  **Discover Paths**: It iterates through every symbol from the `SymbolParser`, inspects its declaration and definition locations, and discovers every unique, in-project file and folder path.
2.  **`UNWIND`-based Ingestion**: It uses highly efficient, `UNWIND`-based Cypher queries to first `MERGE` all folder and file nodes in bulk, and then `MERGE` the `CONTAINS` relationships between them. This minimizes network round trips to the database.

## 3. `SymbolProcessor`

This class is responsible for Pass 2 of the ingestion pipeline. It first creates the nodes for code symbols and then creates the `:DEFINES` relationships. The relationship creation logic is highly sophisticated to balance performance with correctness.

### Symbol Node Ingestion

1.  **Filtering**: The processor first filters the full list of symbols from the parser into lists of supported types. **Crucially, only nodes for `:FUNCTION` and `:DATA_STRUCTURE` (Struct, Class, Union, Enum) are currently created.** Other symbol kinds like `Variable` or `Field` are parsed but do not have nodes created for them, as they were deemed less critical for the project's RAG objectives.
2.  **`UNWIND`-based Ingestion**: It uses `UNWIND` queries to `MERGE` all `:FUNCTION` and `:DATA_STRUCTURE` nodes in separate, efficient batches.

### `:DEFINES` Relationship Ingestion

This is the most complex part of the script, designed to handle the high volume of relationships efficiently while avoiding database concurrency issues. The script offers three distinct strategies, controlled by the `--defines-generation` command-line flag.

#### The Original Performance Bottleneck and Its Solution

Initially, ingesting `:DEFINES` relationships was a significant bottleneck, taking approximately 6 hours for large codebases like the Linux kernel. This was primarily due to two factors:
1.  **Generic `MATCH` Clause**: The Cypher query used a generic `MATCH (n {id: data.id})` to find the target symbol node. This was less efficient than specifying the node's label.
2.  **Over-inclusion of Symbols**: The `defines_data_list` (the source data for relationships) included all symbols with a definition location, even those for which no corresponding `:FUNCTION` or `:DATA_STRUCTURE` node was created (e.g., `Variable`, `Field`). This led to many wasted `MATCH` attempts for non-existent nodes.

**Solution**: The optimization involved:
1.  **Pre-filtering**: The `defines_data_list` is now pre-filtered into `defines_function_list` and `defines_data_structure_list`, ensuring that only relevant symbols are processed for relationship creation.
2.  **Type-Specific `MATCH`**: The Cypher queries now use type-specific `MATCH (n:FUNCTION {id: data.id})` or `MATCH (n:DATA_STRUCTURE {id: data.id})`. This provides the Neo4j query planner with precise information, leading to much faster node lookups.

This optimization dramatically reduced the ingestion time for `:DEFINES` relationships from **~6 hours to ~1 minute**, making all three strategies highly performant.

#### `parallel-create` (Default and Fastest)

-   **Command**: By default, or when `--defines-generation parallel-create` is specified.
-   **Algorithm**: This strategy prioritizes maximum speed. It uses `apoc.periodic.iterate` with the `CREATE` Cypher clause for relationships. This approach has simpler locking behavior and avoids the specific type of deadlocks encountered with `MERGE`.
-   **Trade-off**: This method is **not idempotent**. It assumes the database is clean. If run on a graph that already contains data, it will create duplicate relationships. This is the default because the main pipeline always resets the database, making this a safe and fast choice for the primary use case.

#### `parallel-merge` (Idempotent and Deadlock-Safe)

-   **Command**: When `--defines-generation parallel-merge` is specified.
-   **Algorithm**: This strategy prioritizes correctness and idempotency, for use cases where the script might be run on an existing database. It uses a highly sophisticated, two-level batching system with `apoc.periodic.iterate` and the `MERGE` Cypher clause to prevent deadlocks while still leveraging parallelism.
    1.  **File-based Grouping**: First, all `:DEFINES` relationships are grouped by their target `:FILE` node.
    2.  **Client-Side Batching**: The script creates a "query batch" of these file-groups. The target size of this batch is controlled by `--ingest-batch-size`, which represents the approximate number of *relationships* to include in one client submission. This allows for a client-side progress indicator.
    3.  **Server-Side Batching**: Each "query batch" is sent to a single `apoc.periodic.iterate` call. This call processes the file-groups in parallel. Because all relationships for `fileA` are in one group and all for `fileB` are in another, the database's parallel workers never operate on the same `:FILE` node, **completely eliminating the cause of the deadlocks**.
    4.  **Dynamic Transaction Sizing**: The `batchSize` for the `apoc` call is dynamically calculated based on the average number of relationships per file and the `--cypher-tx-size` argument. This makes the tuning parameters more predictable, as they consistently relate to the number of relationships per operation, not the number of files.

#### `unwind-create` (Experimental)

-   **Command**: When `--defines-generation unwind-create` is specified.
-   **Algorithm**: This strategy uses direct `UNWIND` with the `CREATE` Cypher clause for relationships, batching at the client side. It avoids `apoc.periodic.iterate`.
-   **Performance Note**: While initially slower before the type-specific `MATCH` optimization, this strategy is now also highly performant.

## 4. Performance Tuning Arguments

The script's behavior can be fine-tuned with several arguments:
-   `--defines-generation`: Specifies the strategy for ingesting `:DEFINES` relationships.
-   `--cypher-tx-size`: Sets the target number of items for a server-side transaction. Default is `2000`.
-   `--ingest-batch-size`: Sets the target number of items for a single client-side submission, which corresponds to one progress "dot". Defaults to `cypher-tx-size * num-parse-workers` to provide a reasonable degree of parallelism.