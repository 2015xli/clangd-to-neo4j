# C/C++ AST Processing Utilities

This directory contains Python scripts for parsing C/C++ source code using `tree-sitter` to generate Abstract Syntax Tree (AST) representations and perform related analyses.

## Scripts

1.  **`c_ast_to_dot.py`**: A tool to parse a C source file and generate a DOT graph representation of its AST. It can also render this graph into an image file (e.g., PNG, SVG) and save a textual representation of the tree.
2.  **`check_if_c_header.py`**: A utility to heuristically determine if a `.h` header file should be treated as a C header or a C++ header. This is used by `c_ast_to_dot.py` to avoid incorrectly parsing C++ headers.

---

## `c_ast_to_dot.py`

This script is the main utility for visualizing the AST of a C source file.

### Prerequisites

-   Python 3.6+
-   **Graphviz**: Required for generating image files from DOT graphs.

    -   **On Debian/Ubuntu**: `sudo apt-get install graphviz`
    -   **On macOS (using Homebrew)**: `brew install graphviz`
    -   **On Windows (using Chocolatey)**: `choco install graphviz`

-   **Python Packages**:

    ```sh
    pip install tree-sitter tree-sitter-c tree-sitter-cpp
    ```

### Usage

The script takes a C source file as input and generates three output files by default:
1.  A `.ast` file with a textual tree structure.
2.  A `.dot` file in Graphviz format.
3.  An image file (e.g., `.png`) rendered from the `.dot` file.

```sh
python c_ast_to_dot.py [OPTIONS] <input_file>
```

**Arguments:**

-   `input_file`: Path to the input C source file (e.g., `hello.c`).

**Options:**

-   `-o, --output <file>`: Specify the name for the output DOT file.
-   `-f, --format <format>`: Set the output image format. Choices: `png`, `svg`, `pdf`, `jpg`. Default is `png`.
-   `--no-image`: Suppress the generation of the image file; only the `.ast` and `.dot` files will be created.
-   `--debug`: Enable detailed debug logging to the console.

### Example

```sh
# Process a C file named 'test.c'
python c_ast_to_dot.py test.c

# This will generate:
# - test.c.ast   (Textual AST)
# - test.c.dot   (DOT graph file)
# - test.c.png   (PNG image of the AST)

# Generate an SVG image instead of a PNG
python c_ast_to_dot.py test.c -f svg
```

---

## `check_if_c_header.py`

This script is a helper utility designed to distinguish between C and C++ header files. It is intended to be used by other tools to decide which parser (C or C++) to use for a given `.h` file.

It uses two main heuristics:
1.  **Sibling File Check**: It checks if there are any files with common C++ extensions (e.g., `.cpp`, `.cxx`, `.hpp`) in the same directory as the header file.
2.  **Content Analysis**: It parses the header file using `tree-sitter-cpp` and looks for AST nodes that correspond to C++-only language features (e.g., `class`, `template`, `namespace`).

If either of these checks is positive, the file is considered a C++ header.

**Note**: A bug in tree-setter-cpp
When it meets the following code snippet, it parses the "class" as class_specifier, a C++-only node type.
That means, if this header file has no sibling .c or .cpp-like files, our heuristics will treat it as C++ header file.
Hopefully the case never happens in my projects.

```
static inline enum hfsplus_btree_mutex_classes
hfsplus_btree_lock_class(struct hfs_btree *tree)
{
        enum hfsplus_btree_mutex_classes class;

        switch (tree->cnid) {
        case HFSPLUS_CAT_CNID:
                class = CATALOG_BTREE_MUTEX;
                break;
        case HFSPLUS_EXT_CNID:
                class = EXTENTS_BTREE_MUTEX;
                break;
        case HFSPLUS_ATTR_CNID:
                class = ATTR_BTREE_MUTEX;
                break;
        default:
                BUG();
        }
        return class;
}
``` 

### Usage

```sh
python check_if_c_header.py <path_to_header.h>
```

The script will print whether the file is a C header or not and exit.
