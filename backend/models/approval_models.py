"""
NEXUS Forge — Approval Models

ORM models for human-in-the-loop approval gates.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from backend.database import Base


class AgentActionApproval(Base):
    """
    Tracks actions proposed by agents that require human approval before execution.
    """
    __tablename__ = "nexus_agent_approvals"

    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String, nullable=False) # e.g., 'Manufacturing Agent'
    action_type = Column(String, nullable=False) # e.g., 'adjust_production'
    proposed_payload = Column(JSON, nullable=False)
    reasoning = Column(Text, nullable=False)
    
    status = Column(String, default="pending") # pending | approved | rejected | executed | failed
    feedback = Column(Text, nullable=True) # Optional feedback from human

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)
