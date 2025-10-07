# Algorithm Summary: `code_graph_rag_generator.py`

## 1. Role in the Pipeline

This script is a **standalone orchestrator** responsible for enriching the Neo4j code graph with AI-generated summaries and vector embeddings. It implements the multi-pass strategy outlined in `docs/code_rag_generation_plan.md` to create a knowledge base suitable for Retrieval-Augmented Generation (RAG) systems.

It connects to an existing Neo4j database (populated by the ingestion pipeline) and interacts with an LLM (Large Language Model) and an embedding API to generate and store these enhanced properties on graph nodes.

## 2. Core Logic: Multi-Pass Summarization and Embedding

The `RagGenerator` class orchestrates the entire process, ensuring a separation of concerns between graph traversal and single-item processing. The process is divided into four main passes:

### Pass 1: Initial Code-Only Function Summary (`summarize_functions_individually`)

-   **Goal**: Generate a baseline summary for each function based solely on its source code.
-   **Process**:
    1.  Identifies functions that have a body span (provided by `FunctionSpanProvider`) but no `codeSummary` yet.
    2.  For each such function, it retrieves its source code using the body span information.
    3.  Sends the source code to the configured LLM with a prompt to summarize its purpose.
    4.  Stores the generated summary in the `codeSummary` property of the `:FUNCTION` node.

### Pass 2: Context-Aware Function Summary (`summarize_functions_with_context`)

-   **Goal**: Refine the initial function summaries by incorporating contextual information from the call graph.
-   **Process**:
    1.  Identifies functions that have a `codeSummary` but no final `summary` yet.
    2.  For each function, it queries the graph to find the `codeSummary` of its callers and callees.
    3.  Constructs a prompt that includes the function's `codeSummary` and the summaries of its related functions.
    4.  Sends this contextual prompt to the LLM to generate a more high-level, purposeful summary.
    5.  Stores the refined summary in the `summary` property of the `:FUNCTION` node.

### Pass 3: File and Folder "Roll-Up" Summaries (`summarize_files_and_folders`)

-   **Goal**: Generate summaries for `:FILE`, `:FOLDER`, and `:PROJECT` nodes by aggregating the summaries of their contained elements.
-   **Process**:
    1.  **Files**: Iterates through `:FILE` nodes, gathers the final `summary` of all `:FUNCTION` nodes they define, and sends these to the LLM to generate an overall file summary.
    2.  **Folders**: Iterates through `:FOLDER` nodes in a bottom-up manner (deepest first). For each folder, it gathers the `summary` of all `:FILE` and child `:FOLDER` nodes it directly contains. These are sent to the LLM to generate a collective folder summary.
    3.  **Project**: Finally, it summarizes the top-level `:PROJECT` node based on the summaries of its direct child components.
    4.  Stores the generated summaries in the `summary` property of the respective nodes.

### Pass 4: Embedding Generation (`generate_embeddings`)

-   **Goal**: Create vector embeddings for all final summaries to enable similarity search.
-   **Process**:
    1.  Identifies all `:FUNCTION`, `:FILE`, `:FOLDER`, and `:PROJECT` nodes that have a `summary` but no `summaryEmbedding` yet.
    2.  For each such node, it sends its `summary` text to the configured embedding API.
    3.  Stores the returned vector in the `summaryEmbedding` property of the node.
    4.  After all embeddings are generated, it calls `neo4j_mgr.create_vector_indexes()` to ensure fast similarity searches in Neo4j.

## 3. Key Components & Dependencies

-   **`Neo4jManager`**: Manages the connection and interaction with the Neo4j database.
-   **`FunctionSpanProvider`**: Provides the precise source code spans for functions, used in Pass 1 to extract function bodies.
-   **`LlmClient`**: An abstraction for interacting with various LLM APIs (e.g., OpenAI, DeepSeek, Ollama) for summarization.
-   **`EmbeddingClient`**: An abstraction for interacting with embedding APIs to generate vector representations of text.
-   **`SymbolParser` / `ParallelSymbolParser`**: Used to parse the `clangd` index file and provide symbol information, which is then used by `FunctionSpanProvider`.

## 4. Execution

The script is executed via the `main()` function, which parses command-line arguments for the `clangd` index file, project path, LLM API choice, and number of parallel workers for parsing. It then initializes the necessary clients and managers and orchestrates the `RagGenerator` to run all passes sequentially.