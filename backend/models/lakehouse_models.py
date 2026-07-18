"""
NEXUS Forge — Lakehouse Models

ORM models for tracking lakehouse tables, metadata (trust, freshness),
and causal relationships for the Data Fabric.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from backend.database import Base


class LakehouseTable(Base):
    """
    Tracks metadata for a table in the lakehouse storage (e.g., Delta/Iceberg abstraction).
    """
    __tablename__ = "nexus_lakehouse_tables"

    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String, unique=True, index=True, nullable=False)
    zone = Column(String, nullable=False)  # raw | clean | curated
    storage_path = Column(String, nullable=False)  # e.g., s3://lakehouse/clean/my_table

    # Metadata metrics
    trust_score = Column(Float, default=100.0)  # 0 to 100 based on data quality
    freshness_timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CausalRelationship(Base):
    """
    Tracks causal scaffolding: linking events to downstream metric impacts.
    """
    __tablename__ = "nexus_causal_metadata"

    id = Column(Integer, primary_key=True, index=True)
    source_event = Column(String, nullable=False, index=True)   # e.g., 'supply_disruptions'
    target_metric = Column(String, nullable=False, index=True)  # e.g., 'revenue'
    confidence_score = Column(Float, default=0.0)               # 0 to 1 confidence
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
