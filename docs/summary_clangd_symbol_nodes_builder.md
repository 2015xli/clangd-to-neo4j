# Algorithm Summary: `clangd_symbol_nodes_builder.py`

## 1. Role in the Pipeline

This script acts as a **library module** for the main `clangd_code_graph_builder.py` orchestrator. Its primary responsibility is to build the structural foundation of the code graph in Neo4j. It does not create any behavioral relationships like function calls.

It is designed to work on a pre-parsed, in-memory collection of `Symbol` objects provided by the `SymbolParser`.

It provides two main classes:
-   `PathProcessor`: Creates the physical file system hierarchy of the project.
-   `SymbolProcessor`: Creates nodes for the logical code symbols within the files.

## 2. `PathProcessor`

This class is responsible for Pass 1 of the ingestion pipeline: creating all `:PROJECT`, `:FOLDER`, and `:FILE` nodes.

### Algorithm

1.  **Discover Paths**: Instead of reading the large index file, this class now operates on the in-memory collection of `Symbol` objects. It iterates through every symbol, inspects its declaration and definition locations, and discovers every unique, in-project file and folder path. It stores these in sets to de-duplicate them.
2.  **Create Folders**: It sorts the discovered folder paths by depth (e.g., `/src` comes before `/src/components`). This critical step ensures that parent folders are created in Neo4j before their children.
3.  **Create Files**: After all folders are created, it iterates through the set of discovered files and creates the `:FILE` nodes, connecting them to their parent folders.

This in-memory approach is highly efficient and guarantees that the file system hierarchy is built correctly.

## 3. `SymbolProcessor`

This class is responsible for Pass 2 of the ingestion pipeline: creating the nodes for code symbols.

### Algorithm

1.  **Process Single Symbol**: Its main method, `process_symbol`, is called for each `Symbol` object provided by the `SymbolParser`.
2.  **Node Creation**: It works with the typed `Symbol` object to generate the Cypher to `MERGE` a node with the appropriate label (`:FUNCTION` or `:DATA_STRUCTURE`) and sets its properties (name, signature, scope, etc.).
3.  **Define Relationship**: It also generates the Cypher to create a `[:DEFINES]` relationship between the file where a symbol is defined and the symbol node itself.