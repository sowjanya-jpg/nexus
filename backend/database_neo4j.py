"""
NEXUS Forge — Neo4j Database Manager

Provides connections and dependency injection for the Neo4j graph database.
"""
import os
from neo4j import GraphDatabase, Driver
from dotenv import load_dotenv

load_dotenv()

# Neo4j configuration from docker-compose or .env
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

class Neo4jManager:
    def __init__(self):
        self.driver: Driver | None = None
        self.connect()

    def connect(self):
        try:
            self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            # Verify connectivity
            self.driver.verify_connectivity()
            print("Connected to Neo4j successfully.")
        except Exception as e:
            print(f"Warning: Failed to connect to Neo4j. Ensure it is running. Error: {e}")
            self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()

neo4j_manager = Neo4jManager()

def get_neo4j_session():
    """
    FastAPI dependency to yield a Neo4j session.
    """
    if not neo4j_manager.driver:
        raise Exception("Neo4j driver not initialized.")
    session = neo4j_manager.driver.session()
    try:
        yield session
    finally:
        session.close()
