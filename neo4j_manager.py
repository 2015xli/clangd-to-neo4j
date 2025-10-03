import os
from neo4j import GraphDatabase
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

# Neo4j connection settings
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")

class Neo4jManager:
    """Manages Neo4j database operations."""
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD) -> None:
        self.uri, self.user, self.password = uri, user, password
        self.driver = None
        
    def __enter__(self):
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver: self.driver.close()
    
    def check_connection(self) -> bool:
        try:
            self.driver.verify_connectivity()
            logger.info("✅ Connection established!")
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
        
    def reset_database(self) -> None:
        with self.driver.session() as session:
            logger.info("Deleting existing data...")
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("Database cleared.")
    
    def create_constraints(self) -> None:
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:FILE) REQUIRE f.path IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:FOLDER) REQUIRE f.path IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (fn:FUNCTION) REQUIRE fn.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (ds:DATA_STRUCTURE) REQUIRE ds.id IS UNIQUE",
        ]
        with self.driver.session() as session:
            for constraint in constraints:
                session.run(constraint)
    
    def create_project_node(self, project_path: str) -> None:
        with self.driver.session() as session:
            session.run(
                "MERGE (p:PROJECT:FOLDER {path: $path}) SET p.name = $name",
                {"path": project_path, "name": os.path.basename(project_path) or "Project"}
            )
    
    def process_batch(self, batch: List[Tuple[str, Dict]]) -> None:
        with self.driver.session() as session:
            with session.begin_transaction() as tx:
                for cypher, params in batch:
                    tx.run(cypher, **params)

    def cleanup_orphan_nodes(self) -> int:
        query = "MATCH (n) WHERE COUNT { (n)--() } = 0 DETACH DELETE n"
        with self.driver.session() as session:
            result = session.run(query)
            return result.consume().counters.nodes_deleted
