# Clangd to Neo4j Code Knowledge Graph Ingestion

This project provides a pipeline to ingest `clangd` index YAML files into a Neo4j graph database, creating a rich knowledge graph of a C/C++ codebase. This graph can then be used for various software engineering tasks like code search, dependency analysis, and refactoring.

## Architecture Overview

The ingestion process is orchestrated by `clangd_code_graph_builder.py` and proceeds through several passes, leveraging a modular design for efficiency and maintainability.

### Key Design Principles

*   **Modular Processors**: Each stage of the ingestion is handled by a dedicated processor class.
*   **High-Performance Parallel Parsing**: The initial, expensive parsing of the YAML index is heavily parallelized using a multi-process, chunking architecture to leverage all available CPU cores.
*   **"Parse Once, Use Many"**: The large `clangd` index YAML file is parsed only once into an in-memory representation, which is then reused by all subsequent passes.
*   **Advanced Parallel Ingestion**: Utilizes `apoc.periodic.iterate` with sophisticated, deadlock-safe batching strategies for high-performance data ingestion into Neo4j.
*   **Memory Efficiency**: Aggressive memory management and optimized data structures are employed to handle large codebases.

## Ingestion Pipeline Passes

The `clangd_code_graph_builder.py` orchestrates the following passes:

### Pass 0: Parallel Parse Clangd Index (`clangd_index_yaml_parser.py`)

*   **Purpose**: To parse the massive `clangd` index YAML file into an in-memory collection of `Symbol` objects as quickly as possible.
*   **Key Component**: `ParallelSymbolParser` and `SymbolParser` classes.
*   **Algorithm**: For large codebases, parsing the YAML file is a major bottleneck. This pipeline uses a sophisticated multi-process approach by default (controlled by `--num-parse-workers`):
    1.  **Chunking**: The main process first scans the file to determine the number of YAML documents and divides the file into large, in-memory string chunks.
    2.  **Parallel Parsing**: It then uses a `ProcessPoolExecutor` to send these raw string chunks to separate worker processes.
    3.  **Map-Reduce**: Each worker process parses its chunk of YAML into `Symbol` objects and raw `Reference` documents.
    4.  **Merge & Link**: The main process gathers the results from all workers and merges them. Finally, it performs a sequential pass to link all the references to their corresponding symbols, creating a complete and consistent in-memory view of the index.

### Pass 1: Ingest File & Folder Structure (`clangd_symbol_nodes_builder.py` - `PathProcessor`)

*   **Purpose**: Creates `:PROJECT`, `:FOLDER`, and `:FILE` nodes in Neo4j, establishing the physical file system hierarchy.
*   **Key Component**: `PathProcessor` class.
*   **Features**:
    *   Discovers paths by iterating over the in-memory `Symbol` objects from Pass 0.
    *   Uses `UNWIND`-based batch processing for efficient creation of folder and file nodes, and their `CONTAINS` relationships.

### Pass 2: Ingest Symbol Definitions (`clangd_symbol_nodes_builder.py` - `SymbolProcessor`)

*   **Purpose**: Creates nodes for logical code symbols (`:FUNCTION`, `:DATA_STRUCTURE`) and their `:DEFINES` relationships to files.
*   **Key Component**: `SymbolProcessor` class.
*   **Features**:
    *   Processes typed `Symbol` objects from Pass 0.
    *   Uses `UNWIND`-based batch processing for efficient creation of symbol nodes.
    *   Employs two distinct, highly-tuned strategies for relationship ingestion to balance speed and correctness (see Performance Tuning section below).

### Pass 3: Ingest Call Graph (`clangd_call_graph_builder.py`)

*   **Purpose**: Identifies and ingests function call relationships (`-[:CALLS]->`) into Neo4j.
*   **Features**:
    *   **Adaptive Strategy**: Automatically selects the most efficient call graph extraction method based on whether the `Container` field is detected in the `clangd` index.
    *   **`function_span_provider.py`**: For older `clangd` index formats (without the `Container` field), this module is used to extract precise function body spans via `tree-sitter`, enabling spatial lookup to determine calling functions.

### Pass 4: Cleanup Orphan Nodes

*   **Purpose**: Removes any nodes that were created but ended up without any relationships, ensuring a clean graph.
*   **Features**: This optional step can be skipped with the `--keep-orphans` flag.

## RAG Data Generation Pipeline (`code_graph_rag_generator.py`)

This pipeline runs *after* the main ingestion process to enrich the code graph with AI-generated summaries and vector embeddings, preparing it for Retrieval-Augmented Generation (RAG) queries. It follows a multi-pass approach to build context-aware knowledge.

### Passes:

*   **Pass 1: Initial Code-Only Function Summary**: Generates a baseline summary for each function based solely on its source code.
*   **Pass 2: Context-Aware Function Summary**: Refines function summaries by incorporating contextual information from its callers and callees in the graph.
*   **Pass 3: File and Folder "Roll-Up" Summaries**: Aggregates function summaries to create higher-level summaries for files, folders, and the entire project.
*   **Pass 4: Embedding Generation**: Creates vector embeddings for all generated summaries, enabling semantic search within the graph.

## Usage (`clangd_code_graph_builder.py`)

```bash
# Example with default (fast, parallel-create) settings on a multi-core machine
python3 clangd_code_graph_builder.py <path_to_index.yaml> <path_to_project/>

# Example using the deadlock-safe, parallel-merge strategy
python3 clangd_code_graph_builder.py <path_to_index.yaml> <path_to_project/> --defines-generation parallel-merge

# Example using the unwind-create strategy
python3 clangd_code_graph_builder.py <path_to_index.yaml> <path_to_project/> --defines-generation unwind-create
```

**All Options for `clangd_code_graph_builder.py`:**
*   `--num-parse-workers <int>`: Number of parallel workers for parsing the YAML index. Defaults to half the CPU cores. Set to `1` to disable parallel parsing.
*   `--defines-generation <strategy>`: Strategy for ingesting `:DEFINES` relationships. Choices: `unwind-create`, `parallel-merge`, `parallel-create`. Default: `parallel-create`.
    *   `parallel-create`: (Default) Uses `apoc.periodic.iterate` with `CREATE`. Fast but non-idempotent. Empirically found to be the fastest for large projects.
    *   `parallel-merge`: Uses `apoc.periodic.iterate` with `MERGE`. Idempotent and deadlock-safe, but slightly slower than `parallel-create`.
    *   `unwind-create`: Uses direct `UNWIND` with `CREATE`. Now highly performant due to recent optimizations.
*   `--cypher-tx-size <int>`: Target number of items (nodes/relationships) per server-side transaction. Default: `2000`.
*   `--ingest-batch-size <int>`: Target number of items per client-side submission. Controls progress indicator frequency and the amount of work submitted at once. Defaults to `(cypher-tx-size * num-parse-workers)`.
*   `--log-batch-size <int>`: Log progress every N items (default: 1000).
*   `--keep-orphans`: Skip Pass 4 and keep orphan nodes in the graph.

### `neo4j_manager.py` CLI Tool and Library

The `neo4j_manager.py` script serves as both a command-line utility for managing the Neo4j database (schema inspection, property deletion) and a library module providing the core interface for other parts of the ingestion pipeline to interact with Neo4j.

#### `dump_schema`

Fetches and prints the graph schema, including node labels, their properties, and relationships.

```bash
python3 neo4j_manager.py dump_schema [OPTIONS]
```

**Options:**
*   `-o, --output <path>`: Optional path to save the output text or JSON file.
*   `--only-relations`: Only show relationships, skip node properties.
*   `--with-node-counts`: Include node and relationship counts in the output.
*   `--json-format`: Output raw JSON from APOC meta procedures instead of formatted text.

**Output Enhancements:**
*   **Consolidated Relationships**: Relationships are grouped by their starting node and type, displayed as `(StartLabel) -[:REL_TYPE]-> (EndLabelA|EndLabelB)`.
*   **Property Explanations**: A separate section at the end provides brief explanations for common node properties, aiding in understanding the schema.

#### `delete_property`

Deletes a specified property from nodes. Can target nodes by label or all nodes.

```bash
python3 neo4j_manager.py delete_property --key <property_key> [--label <node_label> | --all-labels] [--rebuild-indexes]
```

**Options:**
*   `--key <property_key>`: The property key to remove (e.g., `summaryEmbedding`).
*   `--label <node_label>`: The node label to target (e.g., `FUNCTION`). Required unless `--all-labels` is used.
*   `--all-labels`: Delete the property from all nodes that have it, regardless of label.
*   `--rebuild-indexes`: If deleting embedding properties, this will drop and recreate vector indexes after deletion.

#### `dump-schema-types`

Recursively checks and prints the Python types of the raw schema data returned by Neo4j, useful for debugging.

```bash
python3 neo4j_manager.py dump-schema-types [-o <path>]
```

**Options:**
*   `-o, --output <path>`: Optional path to save the output text file.

## Performance Tuning & Ingestion Strategy

*Note: All performance observations and comparisons were made on a system with 8 processors.*

This pipeline has been highly optimized for both speed and correctness, particularly regarding the creation of `:DEFINES` relationships.

### The Previous `:DEFINES` Ingestion Bottleneck and Its Solution

Initially, ingesting `:DEFINES` relationships was a significant bottleneck, taking approximately 6 hours for large codebases like the Linux kernel. This was primarily due to two factors:
1.  **Generic `MATCH` Clause**: The Cypher query used a generic `MATCH (n {id: data.id})` to find the target symbol node. This was less efficient than specifying the node's label.
2.  **Over-inclusion of Symbols**: The source data for relationships included all symbols with a definition location, even those for which no corresponding `:FUNCTION` or `:DATA_STRUCTURE` node was created (e.g., `Variable`, `Field`). This led to many wasted `MATCH` attempts for non-existent nodes.

**Solution**: The optimization involved:
1.  **Pre-filtering**: The source data is now pre-filtered into separate lists for `FUNCTION` and `DATA_STRUCTURE` symbols, ensuring that only relevant symbols are processed for relationship creation.
2.  **Type-Specific `MATCH`**: The Cypher queries now use type-specific `MATCH (n:FUNCTION {id: data.id})` or `MATCH (n:DATA_STRUCTURE {id: data.id})`. This provides the Neo4j query planner with precise information, leading to much faster node lookups.

This optimization dramatically reduced the ingestion time for `:DEFINES` relationships from **~6 hours to ~1 minute**, making all three strategies highly performant.

### The Concurrency Problem: Deadlocks

When ingesting millions of relationships in parallel, a common problem is database deadlocks. This happens when two parallel database transactions try to acquire locks on the same nodes (e.g., the same `:FILE` node) in a conflicting order. The database aborts one transaction to resolve the deadlock, resulting in an incomplete graph where some relationships are silently dropped. Our investigation confirmed this was happening with a naive parallel `MERGE` approach.

To solve this, the pipeline offers three distinct strategies for `:DEFINES` relationship ingestion, controlled by the `--defines-generation` flag.

### `parallel-create` (Default and Fastest for `:DEFINES`)

-   **When it's used**: By default, or when `--defines-generation parallel-create` is specified.
-   **Algorithm**: This strategy prioritizes maximum speed. It uses `apoc.periodic.iterate` with the `CREATE` Cypher clause for relationships. This approach has simpler locking behavior and avoids the specific type of deadlocks encountered with `MERGE`.
-   **Trade-off**: This method is **not idempotent**. It assumes the database is clean. If run on a graph that already contains data, it will create duplicate relationships. This is the default because the main pipeline scripts always reset the database, making this a safe and fast choice for the primary use case. **Empirically, this has been found to be the fastest strategy for ingesting `:DEFINES` relationships in large projects.**

### `parallel-merge` (Idempotent and Deadlock-Safe)

-   **When it's used**: When `--defines-generation parallel-merge` is specified.
-   **Algorithm**: This strategy prioritizes correctness and idempotency, for use cases where the script might be run on an existing database. It uses a highly sophisticated, two-level batching system with `apoc.periodic.iterate` and the `MERGE` Cypher clause to prevent deadlocks while still leveraging parallelism.
    1.  **File-based Grouping**: First, all `:DEFINES` relationships are grouped by their target `:FILE` node.
    2.  **Two-Level Batching**: The script then uses a clever batching model:
        *   **Client Batch (`--ingest-batch-size`)**: The script creates a "query batch" of file-groups to submit to the database. This allows for a client-side progress indicator and controls how much data is sent over the network at once.
        *   **Server Batch (`--cypher-tx-size`)**: Each query batch is processed by `apoc.periodic.iterate`. The `batchSize` for this procedure is dynamically calculated based on the average number of relationships per file and the `--cypher-tx-size` argument. This ensures the server-side transactions are well-sized and predictable.
    3.  **Deadlock Avoidance**: The key to this design is that the `apoc` procedure parallelizes the processing of *file-groups*. Since all relationships for `fileA.c` are in one group and all for `fileB.c` are in another, the database's parallel workers never operate on the same `:FILE` node at the same time. This **completely eliminates the cause of the deadlocks** while still allowing for high performance.

### `unwind-create` (Experimental)

-   **When it's used**: When `--defines-generation unwind-create` is specified.
-   **Algorithm**: This strategy uses direct `UNWIND` with the `CREATE` Cypher clause for relationships, batching at the client side. It avoids `apoc.periodic.iterate`.
-   **Performance Note**: While initially slower before the type-specific `MATCH` optimization, this strategy is now also highly performant. **Empirically, (before separating the label type specific matching) this strategy had been found to be  significantly slower (approximately 5 times slower on a 8-core system) than `parallel-create` or "paralle-merge" for ingesting `:DEFINES` relationships in large projects like the Linux kernel.** This is likely due to the overhead of repeated `MATCH` operations within each `UNWIND` transaction, which can be less efficient than `apoc.periodic.iterate`'s parallel sub-transactions for this specific type of relationship and data volume.
