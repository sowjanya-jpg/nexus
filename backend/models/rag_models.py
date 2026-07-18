"""
NEXUS Forge — RAG Models

ORM models for tracking vector embeddings in Postgres using pgvector.
"""
from sqlalchemy import Column, Integer, String, Text, JSON
from pgvector.sqlalchemy import Vector
from backend.database import Base


class ContextVector(Base):
    """
    Stores embeddings of graph nodes and documents for semantic search.
    Requires the pgvector extension in Postgres.
    """
    __tablename__ = "nexus_context_vectors"

    id = Column(Integer, primary_key=True, index=True)
    # The original entity ID or Document ID
    reference_id = Column(String, index=True, nullable=False)
    # Type of content: 'graph_node', 'policy_document', 'decision_trace'
    content_type = Column(String, nullable=False)
    # The actual text content that was embedded
    content = Column(Text, nullable=False)
    # Any additional metadata to filter on
    metadata_json = Column(JSON, nullable=True)
    # The vector embedding (using a standard 384-dim for MiniLM)
    embedding = Column(Vector(384))
