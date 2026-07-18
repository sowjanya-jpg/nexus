
"""
NEXUS Forge — Reasoning Chain

Implements the NL to Action BI pipeline:
SQL Gen -> Visualization -> Causal Explanation -> Recommended Action.
"""
from typing import Dict, Any
from backend.services.nl_router import parse_intent

def run_nl_to_action_pipeline(query: str) -> Dict[str, Any]:
    """
    Executes the full reasoning chain for a user query.
    """
    intent = parse_intent(query)
    
    # For MVP, we mock the generation steps to ensure it runs without external LLMs.
    
    # 1. Mock SQL Generation
    mock_sql = f"SELECT region, sum(revenue) FROM sales WHERE category = 'transformers' GROUP BY region;"
    
    # 2. Mock Visualization Config (e.g., Plotly JSON payload)
    mock_viz = {
        "type": "bar",
        "data": [
            {"x": ["West", "East", "North", "South"], "y": [120, 90, 150, 80], "type": "bar"}
        ],
        "layout": {"title": "Transformer Revenue by Region"}
    }
    
    # 3. Causal Explanation
    # In a real system, this queries the neo4j graph or causal metadata table.
    causal_explanation = "The graph indicates that 'transformer_maintenance' directly impacts 'production_uptime', which correlates heavily with 'revenue' in the Western plants."
    
    # 4. Recommended Action
    recommendation = {
        "action": "Increase preventative maintenance budget by 10% in Western plants.",
        "confidence": 0.88,
        "risk_level": "low"
    }
    
    return {
        "intent_detected": intent,
        "sql_query": mock_sql,
        "visualization": mock_viz,
        "causal_explanation": causal_explanation,
        "recommendation": recommendation
    }
