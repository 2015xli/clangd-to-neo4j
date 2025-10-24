# Project Documentation

This directory contains detailed design documents for the `clangd-graph-rag` project. 

For a comprehensive high-level overview of the project's architecture, design principles, and pipelines, please start with the main presentation summary.

---

### Comprehensive Overview

-   **[Building_an_AI-Ready_Code_Graph_RAG_based_on_Clangd_index.md](./Building_an_AI-Ready_Code_Graph_RAG_based_on_Clangd_index.md)**: A detailed, slide-by-slide breakdown of the entire project, covering high-level concepts, pipeline designs, architecture, and performance optimizations. A [PDF version](./Building_an_AI-Ready_Code_Graph_RAG_based_on_Clangd_index.pdf) is also available.

### Pipeline Orchestrators

These documents describe the high-level scripts that orchestrate the end-to-end workflows.

-   **[summary_clangd_graph_rag_builder.md](./summary_clangd_graph_rag_builder.md)**: Describes the main pipeline for building the graph from scratch.
-   **[summary_clangd_graph_rag_updater.md](./summary_clangd_graph_rag_updater.md)**: Describes the incremental update pipeline that processes changes from Git.

### Major Pipeline Components

These documents detail the core modules responsible for each major stage of the ingestion and enrichment process.

-   **[summary_clangd_index_yaml_parser.md](./summary_clangd_index_yaml_parser.md)**: Explains the high-performance, parallel parsing of the raw `clangd` index file.
-   **[summary_clangd_symbol_nodes_builder.md](./summary_clangd_symbol_nodes_builder.md)**: Details the creation of the graph's structural backbone (files, folders, symbols).
-   **[summary_clangd_call_graph_builder.md](./summary_clangd_call_graph_builder.md)**: Covers the adaptive strategies for constructing the function call graph.
-   **[summary_code_graph_rag_generator.md](./summary_code_graph_rag_generator.md)**: Describes the multi-pass process for generating AI summaries and embeddings.
-   **[summary_function_span_provider.md](./summary_function_span_provider.md)**: Explains how function source code locations are acquired and cached.
-   **[summary_function_span_extractor.md](./summary_function_span_extractor.md)**: Details the low-level parsing logic, supporting both `tree-sitter` and `clang.cindex` strategies.

### Supporting Modules

These documents describe the helper modules that provide essential services like database access, Git integration, and argument parsing.

-   **[summary_neo4j_manager.md](./summary_neo4j_manager.md)**: The Data Access Layer for Neo4j.
-   **[summary_git_manager.md](./summary_git_manager.md)**: The abstraction layer for Git operations.
-   **[summary_llm_client.md](./summary_llm_client.md)**: The factory for providing model-agnostic LLM and embedding clients.
-   **[summary_input_params.md](./summary_input_params.md)**: The centralized module for handling command-line arguments.
-   **[summary_memory_debugger.md](./summary_memory_debugger.md)**: A simple utility for debugging memory usage.

### External Specifications

-   **[clangd-index-yaml-spec.txt](./clangd-index-yaml-spec.txt)**: Keep some Clangd index format info for reference.
