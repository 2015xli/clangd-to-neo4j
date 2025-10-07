# Code RAG Summary and Embedding Generation Plan

## 1. Objective

To build a system that automatically generates meaningful summaries and corresponding vector embeddings for key entities within the codebase (`:PROJECT`, `:FOLDER`, `:FILE`, `:FUNCTION`). These summaries and embeddings will form the knowledge base for a Retrieval-Augmented Generation (RAG) system capable of answering questions about the code.

## 2. Core Challenge: Context

A naive approach of summarizing code entities in isolation is ineffective. The meaning and purpose of a function, for example, are derived not just from its own code but from its relationship with the rest of the system: who calls it, what functions it calls, and what role it plays in its parent file and module.

A simple bottom-up summarization (`Function -> File -> Folder`) fails because the initial function summaries lack this crucial context, leading to a weak foundation for all subsequent, higher-level summaries.

## 3. Proposed Architecture: A Hybrid, Multi-Pass Approach

To solve the context problem, we will use a hybrid, multi-pass architecture. This approach builds up context iteratively, using the graph to enrich the data at each stage before moving to the next level of abstraction. This ensures that high-level summaries are built upon a foundation of contextually-aware, meaningful low-level summaries.

The pipeline will be executed by a new script and will proceed in the following passes:

### Pass 1: Initial Code-Only Function Summary

*   **Goal**: Generate a baseline, literal summary of what each function's code does, ignoring its wider context for now.
*   **Process**:
    1.  For each `:FUNCTION` node in the graph, extract its full source code using the location information stored on the node.
    2.  Send the function's signature and source code (including any preceding comments) to an LLM API.
*   **Example Prompt**: `"Summarize the purpose and implementation of the following C function in one or two sentences. Focus on what it does with its inputs and what it returns. Be concise. Function signature: {signature}. Source code: {code}"`
*   **Result**: The generated text is stored in a new `codeSummary` property on each `:FUNCTION` node.

### Pass 2: Context-Aware Function Summary

*   **Goal**: This is the most critical pass. We enrich the baseline summary from Pass 1 with contextual information from the call graph.
*   **Process**:
    1.  For each `:FUNCTION` node, fetch its `codeSummary` from Pass 1.
    2.  Using the graph, find the `codeSummary` of all functions that **call it** (callers) and all functions that **it calls** (callees).
    3.  Send this collection of summaries to the LLM.
*   **Example Prompt**: `"A function is described as: '{codeSummary}'. It is called by functions responsible for [{caller_summaries}]. It calls functions to perform [{callee_summaries}]. Based on this context, what is the high-level purpose of this function in the overall system? Describe it in one sentence."`
*   **Result**: The refined, context-aware description is stored in the final `summary` property on the `:FUNCTION` node. This upgrades a literal description (e.g., "Sums an array") into a purposeful one (e.g., "Calculates total shopping cart price").

### Pass 3: File and Folder "Roll-Up" Summaries

*   **Goal**: With high-quality function summaries now available, we can effectively "roll them up" to describe their parent files and folders.
*   **Process**: This pass proceeds bottom-up from files to the project root.
    1.  **For each `:FILE` node**: Gather the final `summary` of all functions it `:DEFINES` and send them to the LLM.
        *   **Prompt**: `"A file named {file_name} contains functions with the following responsibilities: [{list_of_function_summaries}]. What is the overall purpose of this file?"`
        *   **Result**: The output is stored in the `summary` property of the `:FILE` node.
    2.  **For each `:FOLDER` node** (iterating from the deepest level upwards):
        *   Gather the `summary` of all `:FILE` and `:FOLDER` nodes it directly `:CONTAINS`.
        *   **Prompt**: `"A folder named {folder_name} contains components with these roles: [{list_of_child_summaries}]. What is the collective responsibility of this folder?"`
        *   **Result**: The output is stored in the `summary` property of the `:FOLDER` node.
    3.  This process continues until the root `:PROJECT` node is summarized.

### Pass 4: Embedding Generation

*   **Goal**: Generate vector embeddings for the final, high-quality summaries to enable similarity search for the RAG system.
*   **Process**: Traverse the graph a final time.
    1.  For every `:PROJECT`, `:FOLDER`, `:FILE`, and `:FUNCTION` node that has a final `summary` property, send this summary text to an embedding API.
    2.  Store the returned vector in a `summaryEmbedding` property on the same node.
    3.  Create a vector index in Neo4j on the `summaryEmbedding` property for all relevant node labels to enable fast and efficient similarity searches.
