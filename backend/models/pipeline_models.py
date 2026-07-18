"""
NEXUS Forge — Pipeline Models

ORM models for tracking transformation pipeline runs, versions, and audit history.
"""
import os
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.database import Base


class PipelineRun(Base):
    """
    Tracks each execution of a transformation pipeline (clean → deduplicate → normalize).
    """
    __tablename__ = "nexus_pipeline_runs"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_name = Column(String, nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="running")  # running | success | failed | rolled_back
    source_table = Column(String, nullable=False)
    target_table = Column(String, nullable=False)

    # Metrics
    rows_input = Column(Integer, default=0)
    rows_output = Column(Integer, default=0)
    rows_deduplicated = Column(Integer, default=0)
    rows_cleaned = Column(Integer, default=0)
    null_cells_filled = Column(Integer, default=0)

    # Versioned snapshot of transformation config applied
    config_snapshot = Column(JSON, nullable=True)

    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship to drift alerts
    drift_alerts = relationship("DriftAlert", back_populates="pipeline_run")
    repair_actions = relationship("RepairAction", back_populates="pipeline_run")


class DriftAlert(Base):
    """
    Records schema drift or value anomaly detections during a pipeline run.
    """
    __tablename__ = "nexus_drift_alerts"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_run_id = Column(Integer, ForeignKey("nexus_pipeline_runs.id"), nullable=False)
    alert_type = Column(String, nullable=False)  # schema_drift | value_anomaly | null_spike | type_mismatch
    severity = Column(String, nullable=False, default="warning")  # info | warning | critical
    column_name = Column(String, nullable=True)
    description = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)  # Statistical evidence payload
    resolved = Column(Boolean, default=False)
    resolved_by = Column(String, nullable=True)  # auto_repair | manual | ignored
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    pipeline_run = relationship("PipelineRun", back_populates="drift_alerts")


class RepairAction(Base):
    """
    Tracks self-healing repair actions attempted or applied during a pipeline run.
    """
    __tablename__ = "nexus_repair_actions"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_run_id = Column(Integer, ForeignKey("nexus_pipeline_runs.id"), nullable=False)
    drift_alert_id = Column(Integer, ForeignKey("nexus_drift_alerts.id"), nullable=True)
    strategy = Column(String, nullable=False)  # schema_coercion | null_backfill | outlier_clamp | type_cast | reroute
    risk_level = Column(String, nullable=False, default="low")  # low | medium | high
    status = Column(String, nullable=False, default="pending")  # pending | applied | queued_for_approval | rejected
    description = Column(Text, nullable=False)
    before_snapshot = Column(JSON, nullable=True)  # Column stats before repair
    after_snapshot = Column(JSON, nullable=True)   # Column stats after repair
    applied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    pipeline_run = relationship("PipelineRun", back_populates="repair_actions")
