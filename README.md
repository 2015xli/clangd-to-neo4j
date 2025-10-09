# Source code graph RAG based on Clangd index

This project provides a pipeline to ingest `clangd` index YAML files into a Neo4j graph database, generate file structure hierarchy and function call graph, then use LLM to generate function/folder summaries and vector embeddings for the code graph, creating a rich knowledge graph RAG of a C/C++ codebase. This graph can then be used for various software engineering tasks like code search, dependency analysis, and refactoring.

## Architecture Overview

The ingestion process is orchestrated by `clangd_code_graph_builder.py` and proceeds through several passes, leveraging a modular design for efficiency and maintainability.

### Key Design Principles

*   **Modular Processors**: Each stage of the ingestion is handled by a dedicated processor class.
*   **High-Performance Parallelism**: The initial YAML parsing and the final RAG generation are heavily parallelized to leverage all available CPU cores and maximize I/O throughput.
*   **"Parse Once, Use Many"**: The large `clangd` index YAML file is parsed only once into an in-memory representation, which is then reused by all subsequent passes.
*   **Advanced Parallel Ingestion**: Utilizes `apoc.periodic.iterate` with sophisticated, deadlock-safe batching strategies for high-performance data ingestion into Neo4j.
*   **Memory Efficiency**: Aggressive memory management and optimized data structures are employed to handle large codebases.

## Ingestion Pipeline Passes

The `clangd_code_graph_builder.py` orchestrates the following passes:

### Pass 0: Parallel Parse Clangd Index (`clangd_index_yaml_parser.py`)

*   **Purpose**: To parse the massive `clangd` index YAML file into an in-memory collection of `Symbol` objects as quickly as possible.
*   **Key Component**: `ParallelSymbolParser` and `SymbolParser` classes.
*   **Algorithm**: Uses a multi-process, map-reduce style approach to parse the file in chunks, controlled by `--num-parse-workers`.

### Pass 1: Ingest File & Folder Structure (`clangd_symbol_nodes_builder.py`)

*   **Purpose**: Creates `:PROJECT`, `:FOLDER`, and `:FILE` nodes in Neo4j, establishing the physical file system hierarchy.

### Pass 2: Ingest Symbol Definitions (`clangd_symbol_nodes_builder.py`)

*   **Purpose**: Creates nodes for logical code symbols (`:FUNCTION`, `:DATA_STRUCTURE`) and their `:DEFINES` relationships to files.

### Pass 3: Ingest Call Graph (`clangd_call_graph_builder.py`)

*   **Purpose**: Identifies and ingests function call relationships (`-[:CALLS]->`) into Neo4j.
*   **Features**: Adaptively chooses the best extraction strategy based on the `clangd` index version.

### Pass 4: Cleanup Orphan Nodes

*   **Purpose**: Removes any nodes that were created but ended up without any relationships, ensuring a clean graph. Skipped with `--keep-orphans`.

### Pass 5: RAG Data Generation (Optional)

*   **Purpose**: Enriches the graph with AI-generated summaries and vector embeddings. This pass is executed when the `--generate-summary` flag is provided.
*   **Key Component**: `code_graph_rag_generator.py`
*   **Algorithm**: This process is multi-threaded and broken into its own series of sub-passes:
    *   **Pass 5.1: Code-Only Function Summary**: Generates a baseline summary for each function based on its source code.
    *   **Pass 5.2: Context-Aware Function Summary**: Refines function summaries by incorporating context from callers and callees.
    *   **Pass 5.3: File "Roll-Up" Summaries**: Aggregates function summaries to create summaries for files.
    *   **Pass 5.4: Folder "Roll-Up" Summaries**: Aggregates file and sub-folder summaries to create summaries for folders in a bottom-up fashion.
    *   **Pass 5.5: Embedding Generation**: Creates vector embeddings for all generated summaries, enabling semantic search.

## Usage (`clangd_code_graph_builder.py`)

```bash
# Example: Basic ingestion for a project
python3 clangd_code_graph_builder.py <path_to_index.yaml> <path_to_project/>

# Example: Full pipeline including RAG generation with custom remote workers
python3 clangd_code_graph_builder.py <path_to_index.yaml> <path_to_project/> \
    --generate-summary \
    --llm-api deepseek \
    --num-remote-workers 150
```

**All Options for `clangd_code_graph_builder.py`:**

*   `--num-parse-workers <int>`: Number of parallel workers for parsing the YAML index. Defaults to half the CPU cores.
*   `--defines-generation <strategy>`: Strategy for ingesting `:DEFINES` relationships. Choices: `unwind-create`, `parallel-merge`, `parallel-create`. Default: `parallel-create`.
*   `--cypher-tx-size <int>`: Target items (nodes/relationships) per server-side transaction. Default: `2000`.
*   `--ingest-batch-size <int>`: Target items per client-side submission. Controls progress indicator frequency. Defaults to `(cypher-tx-size * num-parse-workers)`.
*   `--log-batch-size <int>`: Log progress every N items (default: 1000).
*   `--keep-orphans`: Skip Pass 4 and keep orphan nodes in the graph.

**RAG Generation (Optional):**
*   `--generate-summary`: Generate AI summaries and embeddings for the code graph.
*   `--llm-api <api>`: The LLM API to use for summarization. Choices: `openai`, `deepseek`, `ollama`. Default: `deepseek`.
*   `--num-local-workers <int>`: Number of parallel workers for local LLMs/embedding models. Defaults to half the CPU cores.
*   `--num-remote-workers <int>`: Number of parallel workers for remote LLM/embedding APIs. Default: `100`.

### `neo4j_manager.py` CLI Tool and Library

The `neo4j_manager.py` script serves as both a command-line utility for managing the Neo4j database (schema inspection, property deletion) and a library module providing the core interface for other parts of the ingestion pipeline to interact with Neo4j.

#### `dump_schema`

Fetches and prints the graph schema, including node labels, their properties, and relationships.

```bash
python3 neo4j_manager.py dump_schema [OPTIONS]
```

#### `delete_property`

Deletes a specified property from nodes. Can target nodes by label or all nodes.

```bash
python3 neo4j_manager.py delete_property --key <property_key> [--label <node_label> | --all-labels] [--rebuild-indexes]
```

#### `dump-schema-types`

Recursively checks and prints the Python types of the raw schema data returned by Neo4j, useful for debugging.

```bash
python3 neo4j_manager.py dump-schema-types [-o <path>]
```

## Performance Tuning & Ingestion Strategy

*Note: All performance observations and comparisons were made on a system with 8 processors.*

This pipeline has been highly optimized for both speed and correctness, particularly regarding the creation of `:DEFINES` relationships.

### The Previous `:DEFINES` Ingestion Bottleneck and Its Solution

Initially, ingesting `:DEFINES` relationships was a significant bottleneck, taking approximately 6 hours for large codebases like the Linux kernel. This was primarily due to two factors:
1.  **Generic `MATCH` Clause**: The Cypher query used a generic `MATCH (n {id: data.id})` to find the target symbol node.
2.  **Over-inclusion of Symbols**: The source data for relationships included all symbols with a definition location, even those for which no corresponding node was created.

**Solution**: The optimization involved:
1.  **Pre-filtering**: The source data is now pre-filtered into separate lists for `FUNCTION` and `DATA_STRUCTURE` symbols.
2.  **Type-Specific `MATCH`**: The Cypher queries now use type-specific `MATCH (n:FUNCTION {id: data.id})` or `MATCH (n:DATA_STRUCTURE {id: data.id})`.

This optimization dramatically reduced the ingestion time for `:DEFINES` relationships from **~6 hours to ~1 minute**, making all three strategies highly performant.

### The Concurrency Problem: Deadlocks

When ingesting millions of relationships in parallel, a common problem is database deadlocks. This happens when two parallel database transactions try to acquire locks on the same nodes (e.g., the same `:FILE` node) in a conflicting order. The database aborts one transaction to resolve the deadlock, resulting in an incomplete graph where some relationships are silently dropped. Our investigation confirmed this was happening with a naive parallel `MERGE` approach.

To solve this, the pipeline offers three distinct strategies for `:DEFINES` relationship ingestion, controlled by the `--defines-generation` flag.

### `parallel-create` (Default and Fastest for `:DEFINES`)

-   **When it's used**: By default, or when `--defines-generation parallel-create` is specified.
-   **Algorithm**: This strategy prioritizes maximum speed. It uses `apoc.periodic.iterate` with the `CREATE` Cypher clause for relationships. This approach has simpler locking behavior and avoids the specific type of deadlocks encountered with `MERGE`.
-   **Trade-off**: This method is **not idempotent**. It assumes the database is clean. If run on a graph that already contains data, it will create duplicate relationships. This is the default because the main pipeline scripts always reset the database, making this a safe and fast choice for the primary use case.

### `parallel-merge` (Idempotent and Deadlock-Safe)

-   **When it's used**: When `--defines-generation parallel-merge` is specified.
-   **Algorithm**: This strategy prioritizes correctness and idempotency. It uses a highly sophisticated, two-level batching system with `apoc.periodic.iterate` and the `MERGE` Cypher clause to prevent deadlocks while still leveraging parallelism by grouping all relationships by their target `:FILE` node.

### `unwind-create` (Experimental)

-   **When it's used**: When `--defines-generation unwind-create` is specified.
-   **Algorithm**: This strategy uses direct `UNWIND` with the `CREATE` Cypher clause for relationships, batching at the client side. It avoids `apoc.periodic.iterate`. It is now also highly performant due to the type-specific `MATCH` optimization.