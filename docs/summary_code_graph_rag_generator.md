# Algorithm Summary: `code_graph_rag_generator.py`

## 1. Role in the Pipeline

This script has a dual role. It can act as a **standalone orchestrator** to enrich an existing Neo4j code graph, or it can be invoked as the **final stage (Pass 5)** of the main `clangd_code_graph_builder.py` pipeline when the `--generate-summary` flag is used.

Its responsibility is to populate the graph with AI-generated summaries and vector embeddings, implementing the multi-pass strategy from `docs/code_rag_generation_plan.md` to create a knowledge base suitable for Retrieval-Augmented Generation (RAG) systems.

## 2. Core Logic: Parallel, Multi-Pass Summarization and Embedding

The `RagGenerator` class orchestrates the entire process. To significantly speed up the I/O-bound tasks of calling LLM and embedding APIs, the script now processes items in parallel using a `ThreadPoolExecutor`.

### Parallelism Strategy

- **Worker Pools:** The script intelligently uses different concurrency limits based on the nature of the API being called. This is controlled by two command-line arguments:
    - `--num-local-workers`: For locally-hosted models (`Ollama`, `SentenceTransformer`) that are CPU-bound. Defaults to half the system's CPU cores.
    - `--num-remote-workers`: For remote, network-bound APIs (`OpenAI`, `DeepSeek`). Defaults to a higher value (e.g., 100).
- **Client-Side Detection:** The `LlmClient` and `EmbeddingClient` classes have an `is_local` attribute, allowing the generator to automatically select the appropriate worker limit.
- **Progress Bars:** The `tqdm` library is used to display progress for each parallel pass, providing clear user feedback.

### The Passes

The process is now divided into five main passes:

#### Pass 1: Initial Code-Only Function Summary (`summarize_functions_individually`)
- **Goal**: Generate a baseline summary for each function based solely on its source code.
- **Process**: All functions requiring a summary are processed in parallel. For each function, the script retrieves its source code, sends it to the configured LLM, and stores the resulting `codeSummary` property.

#### Pass 2: Context-Aware Function Summary (`summarize_functions_with_context`)
- **Goal**: Refine the initial function summaries by incorporating contextual information from the call graph.
- **Process**: All functions with a `codeSummary` but no final `summary` are processed in parallel. For each function, it queries for caller/callee summaries and sends the enriched context to the LLM to generate the final `summary` property.

#### Pass 3: File "Roll-Up" Summaries (`_summarize_all_files`)
- **Goal**: Generate summaries for all `:FILE` nodes.
- **Process**: All files requiring a summary are processed in parallel. For each file, the script gathers the final `summary` of all functions it defines and sends them to the LLM to generate an overall file summary.

#### Pass 4: Folder "Roll-Up" Summaries (`_summarize_all_folders`)
- **Goal**: Generate summaries for all `:FOLDER` nodes.
- **Process**: This pass respects the hierarchical dependency (children must be summarized before parents). 
    1. Folders are grouped by their directory depth.
    2. The script iterates from the deepest level to the shallowest.
    3. At each level, all folders are processed in parallel.

#### Pass 5: Embedding Generation (`generate_embeddings`)
- **Goal**: Create vector embeddings for all final summaries.
- **Process**: All nodes (`:FUNCTION`, `:FILE`, `:FOLDER`, `:PROJECT`) with a `summary` but no `summaryEmbedding` are processed in parallel. The summary text is sent to the configured embedding API, and the resulting vector is stored.
- **Final Step**: After all embeddings are generated, it calls `neo4j_mgr.create_vector_indices()` to build the vector search indices in Neo4j.

## 3. Key Components & Dependencies

- **`Neo4jManager`**: Manages the connection and interaction with the Neo4j database.
- **`FunctionSpanProvider`**: Provides the precise source code spans for functions, used in Pass 1 to extract function bodies.
- **`LlmClient`**: An abstraction for interacting with LLM APIs. It now includes an `is_local` flag to determine the appropriate concurrency limit.
- **`EmbeddingClient`**: An abstraction for interacting with embedding APIs, which also has an `is_local` flag.
- **`SymbolParser` / `ParallelSymbolParser`**: Used to parse the `clangd` index file and provide symbol information, which is then used by `FunctionSpanProvider`.

## 4. Execution

The script can be run standalone or as part of the main pipeline.

- **Standalone:**
  ```bash
  python3 code_graph_rag_generator.py <index.yaml> <project_path/> --num-local-workers 4 --num-remote-workers 50
  ```
- **Integrated:**
  ```bash
  python3 clangd_code_graph_builder.py <index.yaml> <project_path/> --generate-summary --num-local-workers 4
  ```
