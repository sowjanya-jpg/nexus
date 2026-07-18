"""
NEXUS Forge — Graph Services

Business logic for managing the Neo4j Knowledge Graph Core (Epic 4).
Includes ontology seeding, entity resolution, and ER diagram/glossary generation.
"""
from typing import Dict, Any, List

def seed_ontology(session) -> Dict[str, Any]:
    """
    Seeds the Neo4j graph with the initial ontology (nodes and relationships)
    and some demo data for entities, events, and metrics.
    """
    # 1. Clear existing demo data to prevent duplicates
    session.run("MATCH (n:Demo) DETACH DELETE n")

    # 2. Create base Entity nodes
    session.run("""
    CREATE (c1:Entity:Customer:Demo {id: 'CUST-100', name: 'Acme Corp', variant_keys: ['acme_corp', 'AcmeCorp']}),
           (c2:Entity:Customer:Demo {id: 'CUST-100-A', name: 'Acme', variant_keys: ['acme']}),
           (s1:Entity:Supplier:Demo {id: 'SUPP-50', name: 'Global Tech', variant_keys: ['global_tech']}),
           (e1:Event:Demo {id: 'EVT-1', type: 'supply_disruptions', description: 'Port strike delay'}),
           (m1:Metric:Demo {id: 'MET-1', name: 'revenue', type: 'financial'})
    """)

    # 3. Create Ownership and Lineage Relationships
    session.run("""
    MATCH (c:Customer {id: 'CUST-100'}), (m:Metric {name: 'revenue'})
    CREATE (c)-[:IMPACTS {confidence: 0.85}]->(m)
    """)

    return {"message": "Ontology seeded with base entities and relationships."}


def resolve_entities(session) -> Dict[str, Any]:
    """
    Implements deterministic entity resolution.
    Finds variant keys (e.g., 'CUST-100' and 'CUST-100-A') and creates a unified entity,
    linking the variants to it via RESOLVES_TO edges.
    """
    # 1. Create a unified Golden Entity if it doesn't exist
    session.run("""
    MERGE (g:Entity:Golden:Customer:Demo {id: 'GOLDEN-CUST-100', name: 'Acme Corp (Unified)'})
    """)

    # 2. Link variants to the Golden Entity
    result = session.run("""
    MATCH (c:Customer:Demo), (g:Golden:Customer:Demo {id: 'GOLDEN-CUST-100'})
    WHERE c.id IN ['CUST-100', 'CUST-100-A']
    MERGE (c)-[r:RESOLVES_TO]->(g)
    RETURN count(r) as resolved_count
    """)
    
    count = result.single()["resolved_count"]
    return {"message": f"Resolved {count} variants to golden entity."}


def generate_er_diagram(session) -> str:
    """
    Derives an ER diagram from the graph schema and formats it as a Mermaid.js diagram.
    For this MVP, we query the node labels and relationship types and map them to Mermaid.
    """
    # Query distinct relationships between node labels
    result = session.run("""
    MATCH (a)-[r]->(b)
    WITH labels(a)[0] AS source, type(r) AS rel, labels(b)[0] AS target
    RETURN DISTINCT source, rel, target
    """)
    
    mermaid_lines = ["erDiagram"]
    for record in result:
        source = record["source"]
        rel = record["rel"]
        target = record["target"]
        if source and target:
            # Format: Source ||--o{ Target : "rel"
            mermaid_lines.append(f"    {source} ||--o{{ {target} : \"{rel}\"")
            
    # Add some static ones if empty (for demo purposes)
    if len(mermaid_lines) == 1:
        mermaid_lines.extend([
            "    Entity ||--o{ Metric : \"IMPACTS\"",
            "    Entity ||--o{ Entity : \"RESOLVES_TO\"",
            "    Dataset ||--o{ Entity : \"CONTAINS\""
        ])
        
    return "\n".join(mermaid_lines)


def generate_glossary(session) -> List[Dict[str, str]]:
    """
    Queries metadata nodes to generate a structured business glossary.
    """
    # In a full implementation, this queries a specific 'GlossaryTerm' node.
    # For MVP, we extract the types of entities and metrics in the graph.
    result = session.run("""
    MATCH (n)
    WITH labels(n) AS lbls
    UNWIND lbls AS label
    RETURN DISTINCT label
    """)
    
    labels = [record["label"] for record in result if record["label"] not in ("Demo", "Golden")]
    
    glossary = []
    for label in labels:
        glossary.append({
            "term": label,
            "definition": f"Business entity or concept representing {label} within the enterprise context graph.",
            "source": "Graph Auto-Generated"
        })
        
    # Fallback demo data
    if not glossary:
        glossary = [
            {"term": "Customer", "definition": "A purchasing entity.", "source": "System"},
            {"term": "Metric", "definition": "A quantifiable measure.", "source": "System"}
        ]
        
    return glossary
