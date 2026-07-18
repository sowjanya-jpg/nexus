"""
Tests for Epic 2: Autonomous Data Engineering Layer

Covers:
- Transformation pipeline (clean, dedup, normalize, versioning)
- Drift detection (schema drift, value anomalies)
- Self-healing repairs (null backfill, outlier clamp, queue for approval)
- End-to-end pipeline API endpoint
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, get_db
from backend.services.transformation import (
    run_transformation_pipeline,
    step_clean,
    step_deduplicate,
    step_normalize,
    DEFAULT_PIPELINE_CONFIG,
)
from backend.services.drift_detection import (
    detect_schema_drift,
    detect_value_anomalies,
    run_drift_detection,
)
from backend.services.self_healing import (
    apply_repairs,
    select_repair_strategy,
)
from backend.models.pipeline_models import PipelineRun, DriftAlert, RepairAction

# ──────────────────────────── Test DB Setup ────────────────────────────

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_epic2.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def _get_db():
    db = TestingSessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


# ═══════════════════════════════════════════════════════════════════════
# Task 2.1: Transformation Pipeline Tests
# ═══════════════════════════════════════════════════════════════════════

class TestTransformationPipeline:

    def test_step_clean_fills_nulls_and_normalizes_headers(self):
        df = pd.DataFrame({
            "Machine ID": ["CNC-01", "CNC-02", None],
            "Motor Temp": [75.0, None, 68.0],
        })
        config = DEFAULT_PIPELINE_CONFIG.copy()
        cleaned, metrics = step_clean(df, config)

        # Headers normalized
        assert "machine_id" in cleaned.columns
        assert "motor_temp" in cleaned.columns

        # Nulls filled
        assert cleaned["machine_id"].isnull().sum() == 0
        assert cleaned["motor_temp"].isnull().sum() == 0
        assert metrics["null_cells_filled"] >= 1

    def test_step_deduplicate_removes_duplicates(self):
        df = pd.DataFrame({
            "id": [1, 2, 2, 3],
            "value": ["a", "b", "b", "c"],
        })
        config = DEFAULT_PIPELINE_CONFIG.copy()
        deduped, removed = step_deduplicate(df, config)

        assert removed == 1
        assert len(deduped) == 3

    def test_step_normalize_scales_and_lowercases(self):
        df = pd.DataFrame({
            "name": ["ALICE", "BOB"],
            "score": [10.0, 20.0],
        })
        config = DEFAULT_PIPELINE_CONFIG.copy()
        config["normalization"]["numeric_scaling"] = "minmax"
        result = step_normalize(df, config)

        assert result["name"].tolist() == ["alice", "bob"]
        assert result["score"].min() == 0.0
        assert result["score"].max() == 1.0

    def test_full_pipeline_records_versioned_run(self):
        db = _get_db()
        try:
            df = pd.DataFrame({
                "id": [1, 2, 2, 3],
                "value": [10.0, None, 20.0, 30.0],
            })

            # Run pipeline twice → versions should increment
            result1, run1 = run_transformation_pipeline(df.copy(), db, pipeline_name="test_pipe")
            result2, run2 = run_transformation_pipeline(df.copy(), db, pipeline_name="test_pipe")

            assert run1.version == 1
            assert run2.version == 2
            assert run1.status == "success"
            assert run2.status == "success"
            assert run1.rows_input == 4
            assert run1.rows_deduplicated == 1  # One duplicate row
        finally:
            db.close()


# ═══════════════════════════════════════════════════════════════════════
# Task 2.2: Drift & Anomaly Detection Tests
# ═══════════════════════════════════════════════════════════════════════

class TestDriftDetection:

    def _make_baseline(self):
        """Create a mock baseline schema."""
        return {
            "table_name": "test_table",
            "columns": [
                {"name": "timestamp", "data_type": "string", "statistics": {"distinct_values": 100}},
                {"name": "machine_id", "data_type": "string", "statistics": {"distinct_values": 5}},
                {"name": "temperature", "data_type": "float", "statistics": {"distinct_values": 80}},
                {"name": "status", "data_type": "string", "statistics": {"distinct_values": 3}},
            ],
        }

    def test_detects_new_column(self):
        db = _get_db()
        try:
            # Create a dummy pipeline run for FK
            run = PipelineRun(pipeline_name="drift_test", version=1, status="success",
                              source_table="src", target_table="tgt", rows_input=10)
            db.add(run)
            db.commit()
            db.refresh(run)

            df = pd.DataFrame({
                "timestamp": ["2026-01-01"],
                "machine_id": ["CNC-01"],
                "temperature": [72.5],
                "status": ["ACTIVE"],
                "new_sensor": [99.9],  # NEW column not in baseline
            })
            baseline = self._make_baseline()
            alerts = detect_schema_drift(df, baseline, run.id, db)

            new_col_alerts = [a for a in alerts if a.details.get("drift_kind") == "new_column"]
            assert len(new_col_alerts) == 1
            assert new_col_alerts[0].column_name == "new_sensor"
        finally:
            db.close()

    def test_detects_missing_column(self):
        db = _get_db()
        try:
            run = PipelineRun(pipeline_name="drift_test", version=1, status="success",
                              source_table="src", target_table="tgt", rows_input=10)
            db.add(run)
            db.commit()
            db.refresh(run)

            df = pd.DataFrame({
                "timestamp": ["2026-01-01"],
                "machine_id": ["CNC-01"],
                # "temperature" is MISSING
                # "status" is MISSING
            })
            baseline = self._make_baseline()
            alerts = detect_schema_drift(df, baseline, run.id, db)

            missing_alerts = [a for a in alerts if a.details.get("drift_kind") == "missing_column"]
            missing_cols = {a.column_name for a in missing_alerts}
            assert "temperature" in missing_cols
            assert "status" in missing_cols
            # Missing columns should be critical severity
            assert all(a.severity == "critical" for a in missing_alerts)
        finally:
            db.close()

    def test_detects_null_spike_anomaly(self):
        db = _get_db()
        try:
            run = PipelineRun(pipeline_name="drift_test", version=1, status="success",
                              source_table="src", target_table="tgt", rows_input=10)
            db.add(run)
            db.commit()
            db.refresh(run)

            # 50% nulls → should exceed 30% threshold
            df = pd.DataFrame({
                "temperature": [72.5, None, None, 68.0, None, None, 70.0, None, None, None],
            })
            baseline = self._make_baseline()
            alerts = detect_value_anomalies(df, baseline, run.id, db)

            null_alerts = [a for a in alerts if a.alert_type == "null_spike"]
            assert len(null_alerts) >= 1
            assert null_alerts[0].column_name == "temperature"
        finally:
            db.close()

    def test_detects_outlier_anomaly(self):
        db = _get_db()
        try:
            run = PipelineRun(pipeline_name="drift_test", version=1, status="success",
                              source_table="src", target_table="tgt", rows_input=100)
            db.add(run)
            db.commit()
            db.refresh(run)

            # 90 tightly clustered values + 10 extreme outliers
            # With values this far from the cluster, even with inflated std they should flag
            np.random.seed(42)
            normal = np.random.normal(70.0, 0.5, 90).tolist()  # Very tight cluster (std=0.5)
            outliers = [9999.0] * 10  # Massively beyond any reasonable σ boundary
            df = pd.DataFrame({"temperature": normal + outliers})

            baseline = self._make_baseline()
            # Use a lower outlier_pct threshold to be sure
            alerts = detect_value_anomalies(df, baseline, run.id, db, thresholds={
                "null_rate_max": 0.30,
                "zscore_outlier": 3.0,
                "outlier_pct_max": 0.02,  # Flag if >2% are outliers (we have 10%)
                "cardinality_change_pct": 0.50,
            })

            outlier_alerts = [a for a in alerts if a.alert_type == "value_anomaly"]
            assert len(outlier_alerts) >= 1
        finally:
            db.close()


# ═══════════════════════════════════════════════════════════════════════
# Task 2.3: Self-Healing Repair Tests
# ═══════════════════════════════════════════════════════════════════════

class TestSelfHealing:

    def test_null_backfill_applied_automatically(self):
        db = _get_db()
        try:
            run = PipelineRun(pipeline_name="repair_test", version=1, status="success",
                              source_table="src", target_table="tgt", rows_input=10)
            db.add(run)
            db.commit()
            db.refresh(run)

            # Create a null_spike alert
            alert = DriftAlert(
                pipeline_run_id=run.id,
                alert_type="null_spike",
                severity="warning",
                column_name="temperature",
                description="50% nulls",
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)

            df = pd.DataFrame({"temperature": [70.0, None, None, 80.0, None]})
            repaired_df, actions = apply_repairs(
                df, [alert], run.id, db, auto_apply_max_risk="low",
            )

            # Nulls should be filled
            assert repaired_df["temperature"].isnull().sum() == 0
            assert len(actions) == 1
            assert actions[0].status == "applied"
            assert actions[0].strategy == "null_backfill"

            # Alert should be marked resolved
            db.refresh(alert)
            assert alert.resolved is True
            assert alert.resolved_by == "auto_repair"
        finally:
            db.close()

    def test_high_risk_repair_queued_for_approval(self):
        db = _get_db()
        try:
            run = PipelineRun(pipeline_name="repair_test", version=1, status="success",
                              source_table="src", target_table="tgt", rows_input=10)
            db.add(run)
            db.commit()
            db.refresh(run)

            # Create a schema_drift alert (reroute strategy → high risk)
            alert = DriftAlert(
                pipeline_run_id=run.id,
                alert_type="schema_drift",
                severity="critical",
                column_name="missing_col",
                description="Missing column",
                details={"drift_kind": "missing_column"},
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)

            df = pd.DataFrame({"other_col": [1, 2, 3]})
            _, actions = apply_repairs(
                df, [alert], run.id, db, auto_apply_max_risk="low",
            )

            # Should be queued, not applied (schema_coercion is medium risk)
            assert len(actions) == 1
            assert actions[0].status == "queued_for_approval"
        finally:
            db.close()


# ═══════════════════════════════════════════════════════════════════════
# Task 2.4: End-to-End Pipeline API Test (Checkpoint)
# ═══════════════════════════════════════════════════════════════════════

class TestPipelineAPI:

    @patch("backend.services.ingestion.upload_file_bytes")
    def test_full_pipeline_endpoint(self, mock_upload):
        """
        End-to-end: upload CSV → transform → get pipeline runs list.
        """
        csv_data = (
            "timestamp,machine_id,temperature,status\n"
            "2026-07-17T10:00:00Z,CNC-01,75.5,ACTIVE\n"
            "2026-07-17T10:01:00Z,CNC-02,,IDLE\n"
            "2026-07-17T10:01:00Z,CNC-02,,IDLE\n"  # duplicate
            "2026-07-17T10:02:00Z,CNC-01,80.1,ACTIVE\n"
        )

        response = client.post(
            "/api/v1/pipeline/transform",
            data={
                "table_name": "machine_data",
                "file_format": "csv",
                "pipeline_name": "test_pipeline",
                "auto_heal": "true",
            },
            files={"file": ("test.csv", csv_data, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()

        assert "pipeline_run" in data
        run = data["pipeline_run"]
        assert run["status"] == "success"
        assert run["rows_input"] == 4
        assert run["rows_deduplicated"] == 1  # 1 duplicate removed
        assert run["version"] == 1

        # Check pipeline runs list endpoint
        runs_resp = client.get("/api/v1/pipeline/runs")
        assert runs_resp.status_code == 200
        runs = runs_resp.json()
        assert len(runs) >= 1
        assert runs[0]["pipeline_name"] == "test_pipeline"
