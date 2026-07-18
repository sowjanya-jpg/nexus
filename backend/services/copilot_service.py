"""
NEXUS Forge — Copilot Services

Handles conversational grounding with context graph references,
SQL/pipeline explanations, and execution tasks with approvals.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session
from backend.services.approval_service import queue_action

def generate_grounded_answer(query: str) -> Dict[str, Any]:
    """
    Simulates a query over the Context Graph.
    Extracts relevant context references (nodes, metrics, schema names).
    """
    query_lower = query.lower()
    
    if "transformer" in query_lower:
        return {
            "answer": "I found a 'transformer_maintenance' event node in the context graph. It is owned by 'Operations Team' and has a lineage link showing it directly impacts the 'production_uptime' metric with 92% confidence.",
            "references": ["Entity:transformer_maintenance", "Metric:production_uptime", "Relation:IMPACTS"]
        }
    elif "revenue" in query_lower:
        return {
            "answer": "The context graph links 'supply_disruptions' events directly to the 'revenue' metric in your clean lakehouse tables. This relationship has an estimated impact confidence of 85%.",
            "references": ["Entity:supply_disruptions", "Metric:revenue", "Relation:IMPACTS"]
        }
    else:
        return {
            "answer": "Based on the enterprise ontology, I see 4 active data zones, 3 registered schemas, and 2 active specialists (Manufacturing, Finance). Let me know if you want to inspect a specific lineage path.",
            "references": ["Schema:nexus_schemas", "Zone:clean", "Zone:raw"]
        }

def explain_sql_pipeline(sql_query: str) -> str:
    """
    Generates a step-by-step breakdown of how a query is executed.
    """
    return (
        f"1. **Filter Categories**: Restricts search scope to rows where category equals 'transformers'.\n"
        f"2. **Group by Region**: Combines rows matching specific geographic zones (West, East, North, South).\n"
        f"3. **Aggregate Revenue**: Calculates the total revenue sum per region.\n"
        f"4. **Lineage**: Source data comes directly from `clean_sales_logs` in the curated lakehouse tier."
    )

def trigger_external_action(db: Session, task_name: str) -> Dict[str, Any]:
    """
    Triggers an action. If it is external-facing/high-risk, queues an approval ticket.
    """
    task_lower = task_name.lower()
    
    if "board summary" in task_lower or "send" in task_lower or "export" in task_lower:
        # High-risk: queue approval
        approval = queue_action(
            db=db,
            agent_name="Copilot Agent",
            action_type="external_report_dispatch",
            payload={"task": task_name, "recipient": "Board of Directors"},
            reasoning="Proposed generating and emailing the Q2 Board Summary report. Gated for explicit human review."
        )
        return {
            "status": "queued_for_approval",
            "message": "Task queued for approval. A steward or admin must sign off on this report release.",
            "approval_id": approval.id
        }
        
    return {
        "status": "executed",
        "message": f"Successfully completed local task: {task_name}."
    }
