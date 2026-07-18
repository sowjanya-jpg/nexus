"""
NEXUS Forge — Data Steward AI (Governance Agent)

Logic for proactive governance scanning: PII detection, freshness checks, and automated remediations.
"""
import re
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from backend.models.lakehouse_models import LakehouseTable
from backend.services.approval_service import queue_action

# Simple mock PII patterns for MVP
PII_PATTERNS = {
    "email": r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
    "ssn": r"^\d{3}-\d{2}-\d{4}$",
    "phone": r"^\+?\d{10,14}$"
}

def scan_for_pii(data_sample: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Scans a sample of rows (dicts) for PII patterns.
    Returns a list of findings.
    """
    findings = []
    for row_idx, row in enumerate(data_sample):
        for col_name, value in row.items():
            if not isinstance(value, str):
                continue
            
            for pii_type, pattern in PII_PATTERNS.items():
                if re.match(pattern, str(value)):
                    findings.append({
                        "column": col_name,
                        "type": pii_type,
                        "risk": "high",
                        "description": f"Found potential {pii_type} in column '{col_name}'."
                    })
    # Deduplicate findings by column
    unique_findings = []
    seen_cols = set()
    for f in findings:
        if f["column"] not in seen_cols:
            unique_findings.append(f)
            seen_cols.add(f["column"])
            
    return unique_findings

def evaluate_freshness(db: Session, freshness_threshold_hours: int = 24) -> List[Dict[str, Any]]:
    """
    Checks Lakehouse tables for stale data.
    """
    stale_tables = []
    threshold_time = datetime.now(timezone.utc) - timedelta(hours=freshness_threshold_hours)
    
    tables = db.query(LakehouseTable).all()
    for table in tables:
        # Assuming freshness_timestamp is naive or UTC aware; for MVP we compare as naive if needed
        # but the model uses UTC.
        freshness = table.freshness_timestamp
        if freshness.tzinfo is None:
            freshness = freshness.replace(tzinfo=timezone.utc)
            
        if freshness < threshold_time:
            stale_tables.append({
                "table_name": table.table_name,
                "last_updated": str(freshness),
                "hours_stale": (datetime.now(timezone.utc) - freshness).total_seconds() / 3600
            })
            
    return stale_tables

def run_governance_scan(db: Session, sample_data: List[Dict[str, Any]], table_name: str) -> Dict[str, Any]:
    """
    Runs a full governance scan and queues remediations if necessary.
    """
    pii_findings = scan_for_pii(sample_data)
    stale_findings = evaluate_freshness(db)
    
    actions_queued = []
    
    if pii_findings:
        # PII is high risk, queue for human approval
        approval = queue_action(
            db=db,
            agent_name="Data Steward AI",
            action_type="mask_pii_columns",
            payload={"table": table_name, "columns_to_mask": [f["column"] for f in pii_findings]},
            reasoning=f"Detected PII in columns: {[f['column'] for f in pii_findings]}. Recommend applying dynamic data masking."
        )
        actions_queued.append({
            "type": "pii_masking",
            "approval_id": approval.id
        })
        
    # We could also automatically decrease trust scores for stale tables
    for stale in stale_findings:
        if stale["table_name"] == table_name:
            # Drop trust score slightly
            table = db.query(LakehouseTable).filter_by(table_name=table_name).first()
            if table:
                table.trust_score = max(0.0, table.trust_score - 5.0)
                db.commit()
                
    return {
        "status": "scan_complete",
        "pii_issues_found": len(pii_findings),
        "stale_tables_found": len(stale_findings),
        "actions_queued": actions_queued
    }
