# Source code graph RAG based on Clangd index

## Why This Project?
(Please skip this section if you know what clangd is.)

A Clangd index YAML file is an intermediate data format from [Clang](https://clangd.llvm.org/design/indexing.html) containing detailed syntactical information used by language servers for code navigation and completion. However, while powerful for IDEs, the raw index data doesn't expose the full graph structure of a codebase (especially the call graph) or integrate the semantic understanding that Large Language Models (LLMs) can leverage.

This project fills that gap. It ingests Clangd index data into a Neo4j graph database, reconstructing the complete file, symbol, and call graph hierarchy. It then enriches this structure with AI-generated summaries and vector embeddings, transforming the raw compiler index into a semantically rich knowledge graph. In essence, `clangd-graph-rag` extends Clangd's powerful foundation into an AI-ready code graph, enabling LLMs to reason about a codebase's structure and behavior for advanced tasks like in-depth code analysis, refactoring, and automated reviewing.

## What Clangd-graph-rag Does?

This project provides a pipeline to ingest `clangd` index YAML files into a Neo4j graph database, generate file structure hierarchy and function call graph, then use LLM to generate function/folder summaries and vector embeddings for the code graph, creating a rich knowledge graph RAG of a C/C++ codebase. This graph can then be used for various software engineering tasks like code search, dependency analysis, and refactoring.
What it does:
   * The project ingests clangd index files into a Neo4j graph database.
   * It builds a code graph with file/folder structure, symbol definitions, and a call graph.
   * Has a RAG generation pass enriches the graph with AI-generated summaries and embeddings.
   * The pipeline is designed for performance, with parallel processing and optimized database interactions.
   * The system is modular, with different Python scripts responsible for specific passes of the ingestion process.
   * It can adapt to different clangd indexer versions.

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
*   **Key Component**: `SymbolParser` class.
*   **Algorithm**: Uses a multi-process, map-reduce style approach to parse the file in chunks. Implements `.pkl` caching to skip parsing entirely on subsequent runs if the index file is unchanged.

### Pass 1: Ingest File & Folder Structure (`clangd_symbol_nodes_builder.py`)

*   **Purpose**: Creates `:PROJECT`, `:FOLDER`, and `:FILE` nodes in Neo4j, establishing the physical file system hierarchy.
*   **Key Component**: `PathProcessor` class.
*   **Algorithm**: Discovers all unique file and folder paths from symbol locations and uses efficient `UNWIND`-based `MERGE` queries to create the nodes and `:CONTAINS` relationships in bulk.

### Pass 2: Ingest Symbol Definitions (`clangd_symbol_nodes_builder.py`)

*   **Purpose**: Creates nodes for logical code symbols (`:FUNCTION`, `:DATA_STRUCTURE`) and their `:DEFINES` relationships to files.
*   **Key Component**: `SymbolProcessor` class.
*   **Algorithm**: First, `MERGE`s all `:FUNCTION` and `:DATA_STRUCTURE` nodes in batches. Then, creates `:DEFINES` relationships using a high-performance strategy (e.g., `parallel-create` with `apoc.periodic.iterate`) to avoid database deadlocks.

### Pass 3: Ingest Call Graph (`clangd_call_graph_builder.py`)

*   **Purpose**: Identifies and ingests function call relationships (`-[:CALLS]->`) into Neo4j.
*   **Key Component**: `ClangdCallGraphExtractor` classes.
*   **Algorithm**: Adaptively chooses the best extraction strategy. If the `clangd` index provides a `Container` field for references, it uses this for a direct, high-speed lookup. Otherwise, it falls back to using `tree-sitter`-generated function spans to spatially determine the caller for each call site.

### Pass 4: Cleanup Orphan Nodes

*   **Purpose**: Removes any nodes that were created but ended up without any relationships, ensuring a clean graph. Skipped with `--keep-orphans`.
*   **Key Component**: `Neo4jManager`.
*   **Algorithm**: Executes a Cypher query (`MATCH (n) WHERE size((n)--()) = 0 DELETE n`) to find and delete all nodes with a degree of zero.

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
