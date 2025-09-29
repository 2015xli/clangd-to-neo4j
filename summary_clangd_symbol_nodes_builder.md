# Algorithm Summary: `clangd_symbol_nodes_builder.py`

## 1. Role in the Pipeline

This script acts as a **library module** for the main `clangd_code_graph_builder.py` orchestrator. Its primary responsibility is to build the structural foundation of the code graph in Neo4j. It does not create any behavioral relationships like function calls.

It provides two main classes:
-   `PathProcessor`: Creates the physical file system hierarchy of the project.
-   `SymbolProcessor`: Creates nodes for the logical code symbols within the files.

## 2. `PathProcessor`

This class is responsible for Pass 1 of the ingestion pipeline: creating all `:PROJECT`, `:FOLDER`, and `:FILE` nodes.

### Algorithm

1.  **Discover Paths**: It first reads through the entire `clangd` index file once with the sole purpose of discovering every unique, in-project file and folder path. It stores these in sets to de-duplicate them.
2.  **Create Folders**: It sorts the discovered folder paths by depth (e.g., `/src` comes before `/src/components`). This critical step ensures that parent folders are created in Neo4j before their children.
3.  **Create Files**: After all folders are created, it iterates through the set of discovered files and creates the `:FILE` nodes, connecting them to their parent folders.

This two-step process is highly efficient and guarantees that the file system hierarchy is built correctly and without redundant operations.

## 3. `SymbolProcessor`

This class is responsible for Pass 2 of the ingestion pipeline: creating the nodes for code symbols.

### Algorithm

1.  **Process Single Symbol**: Its main method, `process_symbol`, is called for each document in the `clangd` index file.
2.  **Node Creation**: It generates the Cypher to `MERGE` a node with the appropriate label (`:FUNCTION` or `:DATA_STRUCTURE`) and sets its properties (name, signature, scope, etc.). It uses a helper method, `_process_node`, to handle properties common to all symbols.
3.  **Add Location Properties**: For `:FUNCTION` nodes, it adds the `path` and `location` properties based on the logic determined during debugging (relative paths for in-project files, absolute for out-of-project, and location from the definition or declaration).
4.  **Define Relationship**: It also generates the Cypher to create a `[:DEFINES]` relationship between the file where a symbol is defined and the symbol node itself.
