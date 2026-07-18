"""
NEXUS Forge — Self-Healing Repair Engine

A library of repair strategies that can be auto-applied (low-risk) or queued 
for human approval (medium/high-risk) when drift or anomalies are detected.
"""
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from backend.models.pipeline_models import DriftAlert, RepairAction


# ──────────────────────────── Repair Strategy Registry ────────────────────────────

REPAIR_STRATEGIES = {
    "null_backfill": {
        "risk": "low",
        "applicable_alerts": ["null_spike"],
        "description": "Fill null values with column median (numeric) or mode (categorical).",
    },
    "outlier_clamp": {
        "risk": "low",
        "applicable_alerts": ["value_anomaly"],
        "description": "Clamp extreme numeric outliers to ±3σ boundaries.",
    },
    "type_cast": {
        "risk": "medium",
        "applicable_alerts": ["type_mismatch"],
        "description": "Attempt safe type cast to expected type (e.g., string → int).",
    },
    "schema_coercion": {
        "risk": "medium",
        "applicable_alerts": ["schema_drift"],
        "description": "Add missing columns with default values or drop unexpected columns.",
    },
    "reroute": {
        "risk": "high",
        "applicable_alerts": ["schema_drift", "type_mismatch"],
        "description": "Route batch to quarantine zone for manual inspection.",
    },
}


# ──────────────────────────── Repair Implementations ────────────────────────────

def _repair_null_backfill(df: pd.DataFrame, column: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Fill nulls with median (numeric) or mode (string).
    """
    before_nulls = int(df[column].isnull().sum())
    
    if pd.api.types.is_numeric_dtype(df[column]):
        fill_value = df[column].median()
        df[column] = df[column].fillna(fill_value)
    else:
        mode_vals = df[column].mode()
        fill_value = mode_vals[0] if len(mode_vals) > 0 else "UNKNOWN"
        df[column] = df[column].fillna(fill_value)

    after_nulls = int(df[column].isnull().sum())
    return df, {
        "column": column,
        "fill_value": str(fill_value),
        "nulls_before": before_nulls,
        "nulls_after": after_nulls,
    }


def _repair_outlier_clamp(df: pd.DataFrame, column: str, sigma: float = 3.0) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Clamp numeric values beyond ±sigma standard deviations to the boundary.
    """
    if not pd.api.types.is_numeric_dtype(df[column]):
        return df, {"skipped": True, "reason": "non-numeric column"}

    mean = df[column].mean()
    std = df[column].std()
    lower = mean - sigma * std
    upper = mean + sigma * std

    clamped_low = int((df[column] < lower).sum())
    clamped_high = int((df[column] > upper).sum())

    df[column] = df[column].clip(lower=lower, upper=upper)

    return df, {
        "column": column,
        "bounds": {"lower": round(lower, 4), "upper": round(upper, 4)},
        "clamped_low": clamped_low,
        "clamped_high": clamped_high,
    }


def _repair_type_cast(df: pd.DataFrame, column: str, target_type: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Attempt safe type cast. Coerce errors to NaN for numeric types.
    """
    original_dtype = str(df[column].dtype)
    cast_errors = 0

    try:
        if target_type in ("integer", "int64"):
            df[column] = pd.to_numeric(df[column], errors="coerce")
            cast_errors = int(df[column].isnull().sum())
            df[column] = df[column].fillna(0).astype(int)
        elif target_type in ("float", "float64"):
            df[column] = pd.to_numeric(df[column], errors="coerce")
            cast_errors = int(df[column].isnull().sum())
        elif target_type == "datetime":
            df[column] = pd.to_datetime(df[column], errors="coerce")
            cast_errors = int(df[column].isnull().sum())
        elif target_type == "string":
            df[column] = df[column].astype(str)
    except Exception as e:
        return df, {"success": False, "error": str(e)}

    return df, {
        "column": column,
        "from_type": original_dtype,
        "to_type": target_type,
        "coercion_errors": cast_errors,
    }


def _repair_schema_coercion(
    df: pd.DataFrame, baseline_schema: Dict[str, Any]
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Add missing columns (with default values) and optionally flag extra columns.
    """
    baseline_cols = {col["name"]: col for col in baseline_schema.get("columns", [])}
    current_cols = set(df.columns)
    baseline_col_names = set(baseline_cols.keys())

    added = []
    extra = list(current_cols - baseline_col_names)

    for col_name in baseline_col_names - current_cols:
        col_meta = baseline_cols[col_name]
        dtype = col_meta.get("data_type", "string")
        if dtype in ("integer", "float"):
            df[col_name] = 0
        elif dtype == "boolean":
            df[col_name] = False
        elif dtype == "datetime":
            df[col_name] = pd.NaT
        else:
            df[col_name] = "UNKNOWN"
        added.append(col_name)

    return df, {
        "columns_added": added,
        "extra_columns_detected": extra,
    }


# ──────────────────────────── Orchestrator ────────────────────────────

def select_repair_strategy(alert: DriftAlert) -> Optional[str]:
    """
    Given a drift alert, select the best applicable repair strategy.
    """
    for strategy_name, meta in REPAIR_STRATEGIES.items():
        if alert.alert_type in meta["applicable_alerts"]:
            return strategy_name
    return None


def apply_repairs(
    df: pd.DataFrame,
    alerts: List[DriftAlert],
    pipeline_run_id: int,
    db: Session,
    baseline_schema: Optional[Dict[str, Any]] = None,
    auto_apply_max_risk: str = "low",
) -> Tuple[pd.DataFrame, List[RepairAction]]:
    """
    For each drift alert, select a repair strategy and either:
    - Auto-apply if risk ≤ auto_apply_max_risk
    - Queue for human approval otherwise
    
    Returns (repaired_df, list_of_repair_actions).
    """
    RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
    max_risk_level = RISK_ORDER.get(auto_apply_max_risk, 0)

    repair_actions: List[RepairAction] = []

    for alert in alerts:
        strategy_name = select_repair_strategy(alert)
        if not strategy_name:
            continue

        strategy_meta = REPAIR_STRATEGIES[strategy_name]
        risk = strategy_meta["risk"]
        risk_level = RISK_ORDER.get(risk, 2)

        # Create the repair action record
        action = RepairAction(
            pipeline_run_id=pipeline_run_id,
            drift_alert_id=alert.id,
            strategy=strategy_name,
            risk_level=risk,
            description=strategy_meta["description"],
        )

        if risk_level <= max_risk_level:
            # Auto-apply
            before_stats = _snapshot_column(df, alert.column_name) if alert.column_name else {}

            try:
                if strategy_name == "null_backfill" and alert.column_name:
                    df, details = _repair_null_backfill(df, alert.column_name)
                elif strategy_name == "outlier_clamp" and alert.column_name:
                    df, details = _repair_outlier_clamp(df, alert.column_name)
                elif strategy_name == "type_cast" and alert.column_name:
                    target_type = (alert.details or {}).get("expected_type", "string")
                    df, details = _repair_type_cast(df, alert.column_name, target_type)
                elif strategy_name == "schema_coercion" and baseline_schema:
                    df, details = _repair_schema_coercion(df, baseline_schema)
                else:
                    details = {"skipped": True, "reason": "no applicable handler"}

                after_stats = _snapshot_column(df, alert.column_name) if alert.column_name else {}
                action.status = "applied"
                action.before_snapshot = before_stats
                action.after_snapshot = {**after_stats, **details}
                action.applied_at = datetime.now(timezone.utc)

                # Mark the alert as resolved
                alert.resolved = True
                alert.resolved_by = "auto_repair"

            except Exception as e:
                action.status = "failed"
                action.after_snapshot = {"error": str(e)}
        else:
            # Queue for human approval
            action.status = "queued_for_approval"

        db.add(action)
        repair_actions.append(action)

    if repair_actions:
        db.commit()

    return df, repair_actions


def _snapshot_column(df: pd.DataFrame, column: Optional[str]) -> Dict[str, Any]:
    """
    Capture a quick statistical snapshot of a column for before/after comparison.
    """
    if column is None or column not in df.columns:
        return {}

    series = df[column]
    snapshot = {
        "null_count": int(series.isnull().sum()),
        "distinct_values": int(series.nunique()),
        "dtype": str(series.dtype),
    }

    if pd.api.types.is_numeric_dtype(series):
        non_null = series.dropna()
        if len(non_null) > 0:
            snapshot["min"] = round(float(non_null.min()), 4)
            snapshot["max"] = round(float(non_null.max()), 4)
            snapshot["mean"] = round(float(non_null.mean()), 4)
            snapshot["std"] = round(float(non_null.std()), 4)

    return snapshot
