"""
NEXUS Forge — Drift & Anomaly Detection Service

Detects schema drift (new/missing/type-changed columns) and value anomalies
(null spikes, statistical outliers, cardinality shifts) by comparing the current
batch against a registered baseline schema and historical statistics.
"""
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from backend.models.pipeline_models import DriftAlert


# ──────────────────────────── Configuration ────────────────────────────

ANOMALY_THRESHOLDS = {
    "null_rate_max": 0.30,           # Flag if >30% of column values are null
    "zscore_outlier": 3.0,           # Flag individual rows beyond 3 standard deviations
    "outlier_pct_max": 0.05,         # Flag column if >5% of rows are statistical outliers
    "cardinality_change_pct": 0.50,  # Flag if distinct count changes >50% vs baseline
}


# ──────────────────────────── Schema Drift Detection ────────────────────────────

def detect_schema_drift(
    df: pd.DataFrame,
    baseline_schema: Dict[str, Any],
    pipeline_run_id: int,
    db: Session,
) -> List[DriftAlert]:
    """
    Compare the current dataframe's schema against a registered baseline.
    Detects: new columns, missing columns, and type mismatches.
    """
    alerts: List[DriftAlert] = []

    # Build baseline column map
    baseline_cols = {}
    for col_meta in baseline_schema.get("columns", []):
        baseline_cols[col_meta["name"]] = col_meta

    current_cols = set(df.columns)
    baseline_col_names = set(baseline_cols.keys())

    # 1. New columns not in baseline
    new_cols = current_cols - baseline_col_names
    for col in new_cols:
        alert = DriftAlert(
            pipeline_run_id=pipeline_run_id,
            alert_type="schema_drift",
            severity="warning",
            column_name=col,
            description=f"New column '{col}' detected that is not in the registered baseline schema.",
            details={"drift_kind": "new_column", "column": col, "current_dtype": str(df[col].dtype)},
        )
        alerts.append(alert)

    # 2. Missing columns from baseline
    missing_cols = baseline_col_names - current_cols
    for col in missing_cols:
        alert = DriftAlert(
            pipeline_run_id=pipeline_run_id,
            alert_type="schema_drift",
            severity="critical",
            column_name=col,
            description=f"Expected column '{col}' is missing from the current batch.",
            details={"drift_kind": "missing_column", "column": col, "expected_type": baseline_cols[col].get("data_type")},
        )
        alerts.append(alert)

    # 3. Type mismatches for shared columns
    TYPE_MAP = {
        "integer": ["int64", "int32", "Int64", "Int32"],
        "float": ["float64", "float32", "Float64"],
        "string": ["object", "string"],
        "boolean": ["bool", "boolean"],
        "datetime": ["datetime64[ns]", "datetime64[ns, UTC]"],
    }

    for col in current_cols & baseline_col_names:
        expected_type = baseline_cols[col].get("data_type", "string")
        actual_dtype = str(df[col].dtype)

        acceptable = TYPE_MAP.get(expected_type, [expected_type])
        if actual_dtype not in acceptable:
            alert = DriftAlert(
                pipeline_run_id=pipeline_run_id,
                alert_type="type_mismatch",
                severity="warning",
                column_name=col,
                description=(
                    f"Column '{col}' type mismatch: expected '{expected_type}' "
                    f"(accepting {acceptable}), but got '{actual_dtype}'."
                ),
                details={
                    "drift_kind": "type_mismatch",
                    "column": col,
                    "expected_type": expected_type,
                    "actual_dtype": actual_dtype,
                },
            )
            alerts.append(alert)

    # Persist all alerts
    for alert in alerts:
        db.add(alert)
    if alerts:
        db.commit()

    return alerts


# ──────────────────────────── Value Anomaly Detection ────────────────────────────

def detect_value_anomalies(
    df: pd.DataFrame,
    baseline_schema: Dict[str, Any],
    pipeline_run_id: int,
    db: Session,
    thresholds: Optional[Dict[str, float]] = None,
) -> List[DriftAlert]:
    """
    Detect statistical value anomalies across all columns:
    - Null rate spikes
    - Z-score outliers in numeric columns
    - Cardinality shifts vs baseline
    """
    if thresholds is None:
        thresholds = ANOMALY_THRESHOLDS

    alerts: List[DriftAlert] = []
    total_rows = len(df)
    if total_rows == 0:
        return alerts

    # Build baseline stats map
    baseline_stats = {}
    for col_meta in baseline_schema.get("columns", []):
        baseline_stats[col_meta["name"]] = col_meta.get("statistics", {})

    for col in df.columns:
        col_series = df[col]
        col_baseline = baseline_stats.get(col, {})

        # ── Null rate check ──
        null_rate = col_series.isnull().sum() / total_rows
        if null_rate > thresholds.get("null_rate_max", 0.30):
            alert = DriftAlert(
                pipeline_run_id=pipeline_run_id,
                alert_type="null_spike",
                severity="critical" if null_rate > 0.60 else "warning",
                column_name=col,
                description=(
                    f"Column '{col}' has {null_rate:.1%} null values "
                    f"(threshold: {thresholds['null_rate_max']:.0%})."
                ),
                details={
                    "null_rate": round(null_rate, 4),
                    "null_count": int(col_series.isnull().sum()),
                    "threshold": thresholds["null_rate_max"],
                },
            )
            alerts.append(alert)

        # ── Numeric outlier check (IQR-based, robust to contamination) ──
        if pd.api.types.is_numeric_dtype(col_series):
            non_null = col_series.dropna()
            if len(non_null) > 2:
                q1 = non_null.quantile(0.25)
                q3 = non_null.quantile(0.75)
                iqr = q3 - q1

                if iqr > 0:
                    iqr_multiplier = thresholds.get("zscore_outlier", 3.0)  # reuse threshold name
                    lower_fence = q1 - iqr_multiplier * iqr
                    upper_fence = q3 + iqr_multiplier * iqr
                    outlier_mask = (non_null < lower_fence) | (non_null > upper_fence)
                    outlier_count = int(outlier_mask.sum())
                    outlier_pct = outlier_count / len(non_null)

                    if outlier_pct > thresholds.get("outlier_pct_max", 0.05):
                        alert = DriftAlert(
                            pipeline_run_id=pipeline_run_id,
                            alert_type="value_anomaly",
                            severity="warning",
                            column_name=col,
                            description=(
                                f"Column '{col}' has {outlier_pct:.1%} statistical outliers "
                                f"(IQR method, {iqr_multiplier}×IQR). "
                                f"Count: {outlier_count}/{len(non_null)}."
                            ),
                            details={
                                "outlier_count": outlier_count,
                                "outlier_pct": round(outlier_pct, 4),
                                "q1": round(float(q1), 4),
                                "q3": round(float(q3), 4),
                                "iqr": round(float(iqr), 4),
                                "lower_fence": round(float(lower_fence), 4),
                                "upper_fence": round(float(upper_fence), 4),
                            },
                        )
                        alerts.append(alert)

        # ── Cardinality shift check ──
        baseline_distinct = col_baseline.get("distinct_values")
        if baseline_distinct and baseline_distinct > 0:
            current_distinct = int(col_series.nunique())
            change_pct = abs(current_distinct - baseline_distinct) / baseline_distinct

            if change_pct > thresholds.get("cardinality_change_pct", 0.50):
                alert = DriftAlert(
                    pipeline_run_id=pipeline_run_id,
                    alert_type="value_anomaly",
                    severity="info",
                    column_name=col,
                    description=(
                        f"Column '{col}' cardinality shifted: "
                        f"baseline={baseline_distinct}, current={current_distinct} "
                        f"({change_pct:.0%} change)."
                    ),
                    details={
                        "baseline_distinct": baseline_distinct,
                        "current_distinct": current_distinct,
                        "change_pct": round(change_pct, 4),
                    },
                )
                alerts.append(alert)

    # Persist all alerts
    for alert in alerts:
        db.add(alert)
    if alerts:
        db.commit()

    return alerts


# ──────────────────────────── Combined Runner ────────────────────────────

def run_drift_detection(
    df: pd.DataFrame,
    baseline_schema: Dict[str, Any],
    pipeline_run_id: int,
    db: Session,
    thresholds: Optional[Dict[str, float]] = None,
) -> List[DriftAlert]:
    """
    Run full drift + anomaly detection suite and return all alerts.
    """
    schema_alerts = detect_schema_drift(df, baseline_schema, pipeline_run_id, db)
    value_alerts = detect_value_anomalies(df, baseline_schema, pipeline_run_id, db, thresholds)
    return schema_alerts + value_alerts
