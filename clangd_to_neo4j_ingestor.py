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
        elif kind == "Field":
            ops.extend(self._process_field(sym))
        elif kind == "Variable":
            ops.extend(self._process_variable(sym))

        # Process file and folder relationships
        ops.extend(self._process_file_relationships(sym, sid, kind))
        
        return ops
    
    def _process_node(self, sym: Dict, label: str) -> List[Tuple[str, Dict]]:
        """Process a node symbol."""
        sid = sym["ID"]
        props = {
            "id": sid,
            "name": sym["Name"],
            "type": sym.get("Type", ""),
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
        ops[0][1]["props"]["signature"] = sym.get("Signature", "")
        ops[0][1]["props"]["return_type"] = sym.get("ReturnType", "")
        ops[0][1]["props"]["has_definition"] = "Definition" in sym
        return ops
    
    def _process_data_structure(self, sym: Dict) -> List[Tuple[str, Dict]]:
        """Process a data structure symbol (class/struct/union/enum)."""
        sid = sym["ID"]
        props = {
            "id": sid,
            "name": sym["Name"],
            "kind": sym.get("SymInfo", {}).get("Kind", ""),
            "has_definition": "Definition" in sym,
            "scope": sym.get("Scope", ""),
            "language": sym.get("SymInfo", {}).get("Lang", ""),
        }
        
        return [(
            "MERGE (n:DATA_STRUCTURE {id: $id}) SET n += $props",
            {"id": sid, "props": props}
        )]
    
    def _process_field(self, sym: Dict) -> List[Tuple[str, Dict]]:
        """Process a field/member variable symbol."""
        sid = sym["ID"]
        props = {
            "id": sid,
            "name": sym["Name"],
            "type": sym.get("Type", ""),
            "scope": sym.get("Scope", ""),
            "language": sym.get("SymInfo", {}).get("Lang", ""),
        }
        
        return [(
            "MERGE (n:FIELD {id: $id}) SET n += $props",
            {"id": sid, "props": props}
        )]
    
    def _process_variable(self, sym: Dict) -> List[Tuple[str, Dict]]:
        """Process a global or local variable symbol."""
        sid = sym["ID"]
        props = {
            "id": sid,
            "name": sym["Name"],
            "type": sym.get("Type", ""),
            "scope": sym.get("Scope", ""),
            "language": sym.get("SymInfo", {}).get("Lang", ""),
        }
        
        return [(
            "MERGE (n:VARIABLE {id: $id}) SET n += $props",
            {"id": sid, "props": props}
        )]
    
    def _process_file_relationships(self, sym: Dict, node_id: str, node_kind: str) -> List[Tuple[str, Dict]]:
        """Process file and folder relationships for a symbol."""
        ops = []
        
        # Handle both definition and declaration locations
        locations = []
        if "Definition" in sym:
            locations.append(("Definition", sym["Definition"]))
        if "CanonicalDeclaration" in sym:
            locations.append(("Declaration", sym["CanonicalDeclaration"]))
        
        for loc_type, loc in locations:
            if not loc or "FileURI" not in loc:
                continue
                
            file_uri = loc["FileURI"]
            file_path = self.path_manager.uri_to_relative_path(file_uri)
            folder_path = self.path_manager.get_relative_folder_path(file_path)
            
            # Skip if not within project
            if not self.path_manager.is_within_project(file_path):
                continue
            
            # Create file node
            ops.append((
                """
                MATCH (p:PROJECT {path: $project_path})
                MERGE (f:FILE {path: $file_path}) 
                SET f.name = $name
                MERGE (p)-[:CONTAINS]->(f)
                """,
                {
                    "project_path": self.path_manager.project_path,
                    "file_path": file_path,
                    "name": Path(file_path).name
                }
            ))
            
            # Create folder hierarchy if needed
            if folder_path and folder_path != '.':
                # Split path into components and create each level
                path_components = []
                current_path = Path(folder_path)
                
                # Build list of all parent folders that need to be created
                while str(current_path) != '.':
                    path_components.append(str(current_path))
                    current_path = current_path.parent
                
                # Create folders from top to bottom
                for path in reversed(path_components):
                    parent_path = str(Path(path).parent) if Path(path).parent != Path('.') else None
                    
                    if parent_path:
                        # Nested folder - connect to parent folder
                        ops.append((
                            """
                            MERGE (child:FOLDER {path: $path})
                            SET child.name = $name
                            WITH child
                            MATCH (parent:FOLDER {path: $parent_path})
                            MERGE (parent)-[:CONTAINS]->(child)
                            """,
                            {
                                "path": path,
                                "name": Path(path).name,
                                "parent_path": parent_path
                            }
                        ))
                    else:
                        # Top-level folder - connect to project
                        ops.append((
                            """
                            MATCH (p:PROJECT {path: $project_path})
                            MERGE (f:FOLDER {path: $path})
                            SET f.name = $name
                            MERGE (p)-[:CONTAINS]->(f)
                            """,
                            {
                                "project_path": self.path_manager.project_path,
                                "path": path,
                                "name": Path(path).name
                            }
                        ))
            
            # Create file defines symbol relationship for definitions
            if loc_type == "Definition" and node_kind in ["Function", "Struct", "Class", "Union", "Enum"]:
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


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Import Clangd index into Neo4j')
    parser.add_argument('index_file', help='Path to the clangd index YAML file')
    parser.add_argument('project_path', help='Root path of the project')
    args = parser.parse_args()
    
    # Initialize path manager and symbol processor
    path_manager = PathManager(args.project_path)
    
    # Initialize Neo4j manager
    with Neo4jManager() as neo4j_mgr:
        # Check connection and reset database
        if not neo4j_mgr.check_connection():
            print("Failed to connect to Neo4j. Exiting.")
            return 1
            
        neo4j_mgr.reset_database()
        
        # Create project node and constraints
        neo4j_mgr.create_project_node(args.project_path)
        neo4j_mgr.create_constraints()
        
        # Initialize symbol processor
        symbol_processor = SymbolProcessor(path_manager)
        
        # Process the YAML file
        batch, count = [], 0
        total_symbols = 0
        
        print(f"Processing {args.index_file}...")
        
        try:
            with open(args.index_file, "r") as f:
                for i, sym in enumerate(yaml.safe_load_all(f)):
                    if not sym:
                        continue
                        
                    total_symbols += 1
                    if total_symbols % 100 == 0:
                        print(f"Processed {total_symbols} symbols...")
                    
                    # Process the symbol and add operations to batch
                    ops = symbol_processor.process_symbol(sym)
                    batch.extend(ops)
                    
                    # Process batch if it reaches the size limit
                    if len(batch) >= BATCH_SIZE:
                        neo4j_mgr.process_batch(batch)
                        count += len(batch)
                        print(f"Committed {count} total operations...")
                        batch = []
            
            # Process any remaining operations in the batch
            if batch:
                neo4j_mgr.process_batch(batch)
                count += len(batch)
            
            print(f"Done. Processed {total_symbols} symbols with {count} total operations.")
            return 0
            
        except Exception as e:
            print(f"Error during processing: {e}")
            return 1


if __name__ == "__main__":
    sys.exit(main())
