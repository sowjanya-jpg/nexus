"""
NEXUS Forge — RAG Services

Business logic for embedding text, storing it in pgvector, and retrieving it for dynamic context.
"""
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.models.rag_models import ContextVector
from sentence_transformers import SentenceTransformer

# Load a lightweight model for the MVP (384 dimensions)
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
except Exception as e:
    print(f"Warning: Failed to load SentenceTransformer. Error: {e}")
    embedding_model = None

def generate_embeddings(text: str) -> List[float]:
    """Generate vector embedding for the given text."""
    if embedding_model:
        return embedding_model.encode(text).tolist()
    # Dummy vector if model fails to load
    return [0.0] * 384

def store_context(
    db: Session,
    reference_id: str,
    content_type: str,
    content: str,
    metadata: Dict[str, Any] = None
) -> ContextVector:
    """Embeds and stores context in Postgres."""
    # Ensure pgvector extension exists
    db.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
    db.commit()
    
    vec = generate_embeddings(content)
    
    context_vec = ContextVector(
        reference_id=reference_id,
        content_type=content_type,
        content=content,
        metadata_json=metadata or {},
        embedding=vec
    )
    db.add(context_vec)
    db.commit()
    db.refresh(context_vec)
    return context_vec

def retrieve_context(db: Session, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Performs vector similarity search in Postgres to find relevant context.
    Returns the top matching results.
    """
    query_vec = generate_embeddings(query)
    
    # We use L2 distance `<->` operator in pgvector
    results = db.query(ContextVector).order_by(
        ContextVector.embedding.l2_distance(query_vec)
    ).limit(limit).all()
    
    return [
        {
            "id": r.id,
            "reference_id": r.reference_id,
            "content_type": r.content_type,
            "content": r.content,
            "metadata": r.metadata_json
        }
        for r in results
    ]
