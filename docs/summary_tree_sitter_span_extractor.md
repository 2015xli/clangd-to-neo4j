# Algorithm Summary: `tree_sitter_span_extractor.py`

## 1. Role in the Pipeline

This script is a low-level library module that serves as the primary interface to the `tree-sitter` parsing framework. Its sole responsibility is to parse C/C++ source files and extract the precise start and end coordinates (spans) of every function definition it finds.

This information is fundamental to the entire pipeline, as it provides the ground-truth physical location of code constructs, which is then used by the `FunctionSpanProvider` to link `clangd` symbols to their source code.

## 2. Core Algorithm: AST Traversal

The script uses the `tree-sitter-c` grammar to build a concrete syntax tree (CST), which it then traverses to find all function definitions.

*   **Node Identification**: The core logic walks the tree, looking for nodes of the type `function_definition`.
*   **Finding the Name (Subtlety)**: Extracting the function name is not trivial because of the complexity of C declarations (e.g., `int * (*foo(void))(void)`). The name (`foo`) is deeply nested within a `declarator` node. The script uses a recursive helper function, `_find_identifier`, to reliably navigate the declarator subtree and find the correct `identifier` node corresponding to the function's name.
*   **Defining the "Body" (Subtlety)**: A key design decision was made in what the script considers the function "body". Instead of just the compound statement (`{ ... }`), the `BodyLocation` span covers the *entire* `function_definition` node, from the return type to the final closing brace. This was done intentionally so that when this span is used to extract source code for an LLM, the model receives the full context of the function, including its signature and return type, leading to much higher-quality summaries.

## 3. Caching for Performance (`SpanCache`)

Parsing thousands of source files can be time-consuming. To make subsequent runs faster, the script implements a robust caching mechanism via the `SpanCache` class.

*   **Mechanism**: After successfully parsing a project, the extractor saves the resulting list of function spans to a binary `.pkl` file. On the next run, it checks if this cache is valid. If it is, it loads the data directly from the cache, skipping all parsing.
*   **Cache Naming**: The cache file is intelligently named. For example, if the main clangd index is `/path/to/index.yaml`, the span cache will be saved as `/path/to/index.function_spans.pkl`.

### Cache Validation Strategies

The most important subtlety is how the cache is validated. The script uses two different strategies:

1.  **Git-based (Primary)**: If the project folder is a Git repository, the script stores the current commit hash in the cache file. The cache is considered **invalid** if the current commit hash is different from the cached one, or if the working tree is dirty (`git status` is not clean). This is the most reliable method, as it correctly handles branch switches and new commits.
2.  **Modification Time (Fallback)**: If the project is not a Git repository, the script falls back to a simpler strategy. It compares the modification time of the cache file against the modification time of every single source file in the project. If any source file is newer than the cache, the cache is considered **invalid**.

## 4. Output

The final output is a list of dictionaries, where each dictionary represents a single source file and contains the file's URI and a list of all `FunctionSpan` objects found within it. This file-grouped structure is an efficient format for downstream consumers like the `FunctionSpanProvider`.
