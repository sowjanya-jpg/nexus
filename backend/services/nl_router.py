"""
NEXUS Forge — NL Router

Parses natural language requests into structured intents.
"""

def parse_intent(query: str) -> str:
    """
    Determines the intent of an NL query.
    Returns: 'sql_generation', 'graph_query', 'agent_workflow', or 'unknown'
    """
    query_lower = query.lower()
    
    # Graph queries usually ask about relationships or lineage
    if any(kw in query_lower for kw in ["how is", "related to", "depends on", "lineage of", "owner of"]):
        return "graph_query"
        
    # Agent workflows usually ask for actions, plans, or optimizations
    if any(kw in query_lower for kw in ["optimize", "plan", "fix", "adjust", "recommend"]):
        return "agent_workflow"
        
    # SQL generation usually asks for aggregations, counts, or specific data
    if any(kw in query_lower for kw in ["how many", "show me", "total", "average", "list", "revenue"]):
        return "sql_generation"
        
    return "unknown"
