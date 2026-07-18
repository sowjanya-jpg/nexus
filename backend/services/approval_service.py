"""
NEXUS Forge — Approval Services

Logic for queuing agent actions and resolving human approvals.
"""
from datetime import datetime, timezone
from typing import List
from sqlalchemy.orm import Session
from backend.models.approval_models import AgentActionApproval

def queue_action(
    db: Session,
    agent_name: str,
    action_type: str,
    payload: dict,
    reasoning: str
) -> AgentActionApproval:
    """Queues an action for human approval."""
    approval = AgentActionApproval(
        agent_name=agent_name,
        action_type=action_type,
        proposed_payload=payload,
        reasoning=reasoning
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval

def get_pending_approvals(db: Session) -> List[AgentActionApproval]:
    """Fetch all pending actions."""
    return db.query(AgentActionApproval).filter(AgentActionApproval.status == "pending").all()

def resolve_approval(db: Session, approval_id: int, decision: str, feedback: str = "") -> AgentActionApproval:
    """Approves or rejects an action."""
    approval = db.query(AgentActionApproval).filter(AgentActionApproval.id == approval_id).first()
    if not approval:
        raise ValueError("Approval not found")
        
    if decision not in ["approved", "rejected"]:
        raise ValueError("Decision must be 'approved' or 'rejected'")
        
    approval.status = decision
    approval.feedback = feedback
    approval.resolved_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(approval)
    
    # In a full system, 'approved' actions would then trigger execution logic
    if decision == "approved":
        # Simulate execution
        approval.status = "executed"
        db.commit()
        db.refresh(approval)
        
    return approval
