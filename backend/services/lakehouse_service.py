"""
NEXUS Forge — Lakehouse Services

Business logic for managing lakehouse metadata and causal scaffolding.
"""
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from backend.models.lakehouse_models import LakehouseTable, CausalRelationship

def register_lakehouse_table(
    db: Session,
    table_name: str,
    zone: str,
    storage_path: str,
    trust_score: float = 100.0
) -> LakehouseTable:
    """
    Register or update a table in the lakehouse metadata.
    """
    table = db.query(LakehouseTable).filter_by(table_name=table_name).first()
    if table:
        table.zone = zone
        table.storage_path = storage_path
        table.trust_score = trust_score
        table.freshness_timestamp = datetime.now(timezone.utc)
    else:
        table = LakehouseTable(
            table_name=table_name,
            zone=zone,
            storage_path=storage_path,
            trust_score=trust_score,
            freshness_timestamp=datetime.now(timezone.utc)
        )
        db.add(table)
    db.commit()
    db.refresh(table)
    return table

def get_all_lakehouse_tables(db: Session) -> List[LakehouseTable]:
    """
    Retrieve all registered lakehouse tables.
    """
    return db.query(LakehouseTable).all()

def update_trust_score(db: Session, table_name: str, new_score: float) -> LakehouseTable:
    """
    Update the trust score for a specific lakehouse table.
    """
    table = db.query(LakehouseTable).filter_by(table_name=table_name).first()
    if not table:
        raise ValueError(f"Table '{table_name}' not found.")
    
    table.trust_score = max(0.0, min(100.0, new_score))
    db.commit()
    db.refresh(table)
    return table

def add_causal_link(
    db: Session,
    source_event: str,
    target_metric: str,
    confidence_score: float,
    description: str
) -> CausalRelationship:
    """
    Add a new causal metadata link.
    """
    link = CausalRelationship(
        source_event=source_event,
        target_metric=target_metric,
        confidence_score=max(0.0, min(1.0, confidence_score)),
        description=description
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link

def get_causal_links(db: Session) -> List[CausalRelationship]:
    """
    Retrieve all causal metadata links.
    """
    return db.query(CausalRelationship).all()

def seed_demo_causal_data(db: Session) -> List[CausalRelationship]:
    """
    Populate a handful of hand-authored examples for the demo dataset.
    """
    # Clear existing to prevent duplicates during testing
    db.query(CausalRelationship).delete()
    
    demo_links = [
        {
            "source_event": "supply_disruptions",
            "target_metric": "revenue",
            "confidence_score": 0.85,
            "description": "A supply disruption in raw materials often leads to a decrease in Q3 revenue due to delayed manufacturing."
        },
        {
            "source_event": "transformer_maintenance",
            "target_metric": "production_uptime",
            "confidence_score": 0.92,
            "description": "Proactive transformer maintenance increases plant production uptime by preventing unexpected shutdowns."
        },
        {
            "source_event": "weather_anomaly_storm",
            "target_metric": "delivery_delay_hours",
            "confidence_score": 0.78,
            "description": "Severe storms in transit regions strongly correlate with increased delivery delays."
        }
    ]
    
    created_links = []
    for data in demo_links:
        link = CausalRelationship(
            source_event=data["source_event"],
            target_metric=data["target_metric"],
            confidence_score=data["confidence_score"],
            description=data["description"]
        )
        db.add(link)
        created_links.append(link)
        
    db.commit()
    
    for link in created_links:
        db.refresh(link)
        
    return created_links
