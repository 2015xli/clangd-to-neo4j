#!/usr/bin/env python3
"""
Streaming importer: clangd YAML index -> Neo4j
Handles multi-document YAML with !Symbol tags.
"""
import os
import sys
import argparse
import yaml
from pathlib import Path
from urllib.parse import urlparse, unquote
from typing import List, Dict, Any, Tuple, Optional
from neo4j import GraphDatabase

# -------------------------
# Constants
# -------------------------
BATCH_SIZE = 500

# -------------------------
# Neo4j connection settings
# -------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")

# -------------------------
# YAML tag handling
# -------------------------
def unknown_tag(loader, tag_suffix, node):
    return loader.construct_mapping(node)

yaml.SafeLoader.add_multi_constructor("!", unknown_tag)

# -------------------------
# Helper functions
# -------------------------
class PathManager:
    """Manages file paths and their relationships within the project."""
    
    def __init__(self, project_path: str) -> None:
        """Initialize with the project root path.
        
        Args:
            project_path: The root path of the project
        """
        self.project_path = str(Path(project_path).resolve())
        
    def uri_to_relative_path(self, uri: str) -> str:
        """Convert file:// URI to project-relative path.
        
        Args:
            uri: The file URI to convert
            
        Returns:
            Relative path if within project, or original path if not
        """
        parsed = urlparse(uri)
        if parsed.scheme != 'file':
            return uri
            
        path = unquote(parsed.path)
        try:
            return str(Path(path).relative_to(self.project_path))
        except ValueError:
            return path
    
    def get_relative_folder_path(self, file_path: str) -> str:
        """Get project-relative folder path from a file path.
        
        Args:
            file_path: The file path to get the parent folder from
            
        Returns:
            Relative folder path
        """
        try:
            return str(Path(file_path).parent.relative_to(self.project_path))
        except ValueError:
            return str(Path(file_path).parent)
    
    def is_within_project(self, path: str) -> bool:
        """Check if a path is within the project.
        
        Args:
            path: Path to check
            
        Returns:
            True if path is within project, False otherwise
        """
        try:
            Path(path).relative_to(self.project_path)
            return True
        except ValueError:
            return False

class Neo4jManager:
    """Manages Neo4j database operations."""
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD) -> None:
        """Initialize the Neo4j manager.
        
        Args:
            uri: Neo4j connection URI
            user: Database username
            password: Database password
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        
    def __enter__(self):
        """Context manager entry."""
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.driver:
            self.driver.close()
    
    def check_connection(self) -> bool:
        """Check if the Neo4j connection is working.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            self.driver.verify_connectivity()
            print("✅ Connection established!")
            with self.driver.session() as session:
                result = session.run("RETURN 1 AS result").single()
                print("Test query result:", result["result"])
            return True
        except Exception as e:
            print("❌ Connection failed:", e)
            return False
        
    def reset_database(self) -> None:
        """Clear all data from the Neo4j database."""
        with self.driver.session() as session:
            print("Deleting existing data...")
            session.run("MATCH (n) DETACH DELETE n")
            print("Database cleared.")
    
    def create_constraints(self) -> None:
        """Create necessary constraints in Neo4j."""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:FILE) REQUIRE f.path IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:FOLDER) REQUIRE f.path IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (fn:FUNCTION) REQUIRE fn.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (ds:DATA_STRUCTURE) REQUIRE ds.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (fld:FIELD) REQUIRE fld.id IS UNIQUE"
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    print(f"Error creating constraint: {e}")
                    raise
    
    def create_project_node(self, project_path: str) -> None:
        """Create a project node in Neo4j.
        
        Args:
            project_path: Path to the project root
        """
        with self.driver.session() as session:
            session.run(
                """
                MERGE (p:PROJECT:FOLDER {path: $path}) 
                SET p.name = $name
                """,
                {
                    "path": project_path,
                    "name": Path(project_path).name or "Project"
                }
            )
    
    def process_batch(self, batch: List[Tuple[str, Dict]]) -> None:
        """Process a batch of Cypher operations in a single transaction.
        
        Args:
            batch: List of (cypher_query, params) tuples
        """
        with self.driver.session() as session:
            with session.begin_transaction() as tx:
                for cypher, params in batch:
                    try:
                        tx.run(cypher, **params)
                    except Exception as e:
                        print(f"Error executing: {cypher}")
                        print(f"Params: {params}")
                        print(f"Error: {e}")
                        raise

# -------------------------
# Symbol processing
# -------------------------
    
class SymbolProcessor:
    """Processes Clangd symbols and generates Neo4j operations."""
    
    def __init__(self, path_manager: PathManager):
        """Initialize with a PathManager instance.
        
        Args:
            path_manager: PathManager instance for path operations
        """
        self.path_manager = path_manager
    
    def process_symbol(self, sym: Dict) -> List[Tuple[str, Dict]]:
        """Process a single symbol and return a list of Cypher operations.
        
        Args:
            sym: The symbol dictionary from Clangd
            
        Returns:
            List of (cypher_query, params) tuples
        """
        ops = []
        sid = sym.get("ID")
        kind = sym.get("SymInfo", {}).get("Kind")

        if not sid or not kind:
            return []

        # Handle different node types
        if kind == "Function":
            ops.extend(self._process_function(sym))
        elif kind in ("Struct", "Class", "Union", "Enum"):
            ops.extend(self._process_data_structure(sym))
        #elif kind == "Field":
        #    ops.extend(self._process_field(sym))
        #elif kind == "Variable":
        #    ops.extend(self._process_variable(sym))

        # Process file and folder relationships
        ops.extend(self._process_file_relationships(sym, sid, kind))
        
        return ops
    
    def _process_node(self, sym: Dict, label: str) -> List[Tuple[str, Dict]]:
        """Process a node symbol."""
        sid = sym["ID"]
        props = {
            "id": sid,
            "name": sym["Name"],
            "scope": sym.get("Scope", ""),
            "language": sym.get("SymInfo", {}).get("Lang", ""),
        }
        
        return [(
            f"MERGE (n:{label} {{id: $id}}) SET n += $props",
            {"id": sid, "props": props}
        )]
    
    def _process_function(self, sym: Dict) -> List[Tuple[str, Dict]]:
        """Process a function symbol."""
        ops = self._process_node(sym, "FUNCTION")
        props = ops[0][1]["props"]

        props["signature"] = sym.get("Signature", "")
        props["return_type"] = sym.get("ReturnType", "")
        props["type"] = sym.get("Type", "")
        props["has_definition"] = "Definition" in sym

        # Determine the primary location (Definition > Declaration)
        primary_location = None
        if "Definition" in sym:
            primary_location = sym["Definition"]
        elif "CanonicalDeclaration" in sym:
            primary_location = sym["CanonicalDeclaration"]

        if primary_location and "FileURI" in primary_location:
            file_uri = primary_location["FileURI"]
            
            parsed_uri = urlparse(file_uri)
            if parsed_uri.scheme == 'file':
                abs_file_path = unquote(parsed_uri.path)

                # Set path to relative if in-project, otherwise absolute
                if self.path_manager.is_within_project(abs_file_path):
                    props["path"] = self.path_manager.uri_to_relative_path(file_uri)
                else:
                    props["path"] = abs_file_path
                
                # Add location details
                if "Start" in primary_location:
                    props["location"] = [
                        primary_location["Start"]["Line"],
                        primary_location["Start"]["Column"]
                    ]

        return ops
    
    def _process_data_structure(self, sym: Dict) -> List[Tuple[str, Dict]]:
        """Process a data structure symbol (class/struct/union/enum)."""
        ops = self._process_node(sym, "DATA_STRUCTURE")
        props = ops[0][1]["props"]
        props["kind"] = sym.get("SymInfo", {}).get("Kind", "")
        props["has_definition"] = "Definition" in sym
        return ops
    
    def _process_field(self, sym: Dict) -> List[Tuple[str, Dict]]:
        """Process a field/member variable symbol."""
        ops = self._process_node(sym, "FIELD")
        ops[0][1]["props"]["type"] = sym.get("Type", "")
        return ops
    
    def _process_variable(self, sym: Dict) -> List[Tuple[str, Dict]]:
        """Process a global or local variable symbol."""
        ops = self._process_node(sym, "VARIABLE")
        ops[0][1]["props"]["type"] = sym.get("Type", "")
        return ops
    
    def _process_file_relationships(self, sym: Dict, node_id: str, node_kind: str) -> List[Tuple[str, Dict]]:
        """Process file and folder relationships for a symbol."""
        ops = []
        
        # We only care about the definition location for creating a DEFINES relationship
        if "Definition" not in sym:
            return []
            
        loc = sym["Definition"]
        if not loc or "FileURI" not in loc:
            return []
                
        file_uri = loc["FileURI"]

        # Get absolute path and check if it's in the project
        parsed_uri = urlparse(file_uri)
        if parsed_uri.scheme != 'file':
            return []
        abs_file_path = unquote(parsed_uri.path)

        if not self.path_manager.is_within_project(abs_file_path):
            return []

        # Get relative path for the relationship
        file_path = self.path_manager.uri_to_relative_path(file_uri)

        # Create file defines symbol relationship for definitions
        if node_kind in ["Function", "Struct", "Class", "Union", "Enum"]:
            label = "FUNCTION" if node_kind == "Function" else "DATA_STRUCTURE"
            ops.append((
                f"""
                MATCH (f:FILE {{path: $file_path}})
                MATCH (n:{label} {{id: $node_id}})
                MERGE (f)-[:DEFINES]->(n)
                """,
                {"file_path": file_path, "node_id": node_id}
            ))
        
        return ops


# -------------------------
# Main processing
# -------------------------

def process_batch(session, batch):
    """Process a batch of Cypher operations in a single transaction"""
    with session.begin_transaction() as tx:
        for cypher, params in batch:
            try:
                tx.run(cypher, **params)
            except Exception as e:
                print(f"Error executing: {cypher}")
                print(f"Params: {params}")
                print(f"Error: {e}")
                raise


class PathProcessor:
    """Discovers and ingests file/folder structure into Neo4j."""

    def __init__(self, path_manager: PathManager, neo4j_mgr: Neo4jManager):
        self.path_manager = path_manager
        self.neo4j_mgr = neo4j_mgr

    def _discover_paths(self, index_file: str) -> Tuple[set, set]:
        """First pass: discover all unique in-project files and folders."""
        project_files = set()
        project_folders = set()

        print("Pass 1: Discovering project file structure...")
        with open(index_file, "r") as f:
            for sym in yaml.safe_load_all(f):
                if not sym:
                    continue

                locations = []
                if "Definition" in sym:
                    locations.append(sym["Definition"])
                if "CanonicalDeclaration" in sym:
                    locations.append(sym["CanonicalDeclaration"])

                for loc in locations:
                    if not loc or "FileURI" not in loc:
                        continue
                    
                    file_uri = loc["FileURI"]
                    parsed_uri = urlparse(file_uri)
                    if parsed_uri.scheme != 'file':
                        continue
                    
                    abs_file_path = unquote(parsed_uri.path)
                    if self.path_manager.is_within_project(abs_file_path):
                        relative_path = self.path_manager.uri_to_relative_path(file_uri)
                        project_files.add(relative_path)
                        
                        # Add all parent folders
                        parent = Path(relative_path).parent
                        while str(parent) != '.':
                            project_folders.add(str(parent))
                            parent = parent.parent
        
        print(f"Discovered {len(project_files)} files and {len(project_folders)} folders.")
        return project_files, project_folders

    def ingest_paths(self, index_file: str):
        """Discover and create all folder and file nodes."""
        project_files, project_folders = self._discover_paths(index_file)
        batch = []

        # A. Create Folders
        sorted_folders = sorted(list(project_folders), key=lambda p: len(Path(p).parts))
        for folder_path in sorted_folders:
            parent_path = str(Path(folder_path).parent)
            if parent_path == '.':
                batch.append((
                    """
                    MATCH (p:PROJECT {path: $project_path})
                    MERGE (f:FOLDER {path: $path})
                    SET f.name = $name
                    MERGE (p)-[:CONTAINS]->(f)
                    """,
                    {
                        "project_path": self.path_manager.project_path,
                        "path": folder_path,
                        "name": Path(folder_path).name
                    }
                ))
            else:
                batch.append((
                    """
                    MERGE (child:FOLDER {path: $path})
                    SET child.name = $name
                    WITH child
                    MATCH (parent:FOLDER {path: $parent_path})
                    MERGE (parent)-[:CONTAINS]->(child)
                    """,
                    {
                        "path": folder_path,
                        "name": Path(folder_path).name,
                        "parent_path": parent_path
                    }
                ))
        if batch:
            print("Creating folder structure...")
            self.neo4j_mgr.process_batch(batch)
            batch = []

        # B. Create Files
        for file_path in project_files:
            parent_path = str(Path(file_path).parent)
            if parent_path == '.':
                batch.append((
                    """
                    MATCH (p:PROJECT {path: $project_path})
                    MERGE (f:FILE {path: $path})
                    SET f.name = $name
                    MERGE (p)-[:CONTAINS]->(f)
                    """,
                    {
                        "project_path": self.path_manager.project_path,
                        "path": file_path,
                        "name": Path(file_path).name
                    }
                ))
            else:
                batch.append((
                    """
                    MATCH (p:FOLDER {path: $parent_path})
                    MERGE (f:FILE {path: $path})
                    SET f.name = $name
                    MERGE (p)-[:CONTAINS]->(f)
                    """,
                    {
                        "parent_path": parent_path,
                        "path": file_path,
                        "name": Path(file_path).name
                    }
                ))
        if batch:
            print("Creating file nodes...")
            self.neo4j_mgr.process_batch(batch)
            batch = []

# -------------------------
# Main processing
# -------------------------

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Import Clangd index into Neo4j')
    parser.add_argument('index_file', help='Path to the clangd index YAML file')
    parser.add_argument('project_path', help='Root path of the project')
    args = parser.parse_args()
    
    path_manager = PathManager(args.project_path)
    
    with Neo4jManager() as neo4j_mgr:
        if not neo4j_mgr.check_connection():
            print("Failed to connect to Neo4j. Exiting.")
            return 1
            
        # Setup database
        neo4j_mgr.reset_database()
        neo4j_mgr.create_project_node(path_manager.project_path)
        neo4j_mgr.create_constraints()
        
        # Pass 1: Create file system structure
        path_processor = PathProcessor(path_manager, neo4j_mgr)
        path_processor.ingest_paths(args.index_file)

        # Pass 2: Create symbols and relationships
        print("Pass 2: Processing symbols and relationships...")
        symbol_processor = SymbolProcessor(path_manager)
        batch, count, total_symbols = [], 0, 0

        with open(args.index_file, "r") as f:
            for sym in yaml.safe_load_all(f):
                if not sym:
                    continue
                total_symbols += 1
                if total_symbols % 500 == 0:
                    print(f"Processed {total_symbols} symbols...")
                
                ops = symbol_processor.process_symbol(sym)
                batch.extend(ops)
                
                if len(batch) >= BATCH_SIZE:
                    neo4j_mgr.process_batch(batch)
                    count += len(batch)
                    print(f"Committed {count} total operations...")
                    batch = []
        
        if batch:
            neo4j_mgr.process_batch(batch)
            count += len(batch)
        
        print(f"Done. Processed {total_symbols} symbols with {count} total operations.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
