"""
NEXUS Forge — Transformation Pipeline Engine

Implements baseline data cleaning, deduplication, and normalization with
pipeline versioning and rollback support. Operates on pandas DataFrames 
(production would use Spark/dbt, but pandas gives us a working demo).
"""
import io
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from backend.models.pipeline_models import PipelineRun


# ──────────────────────────── Configuration ────────────────────────────

DEFAULT_PIPELINE_CONFIG = {
    "cleaning": {
        "drop_full_duplicates": True,
        "strip_whitespace": True,
        "normalize_column_names": True,  # lowercase, underscores
        "fill_strategy": {
            "numeric": "median",      # mean | median | zero | drop
            "string": "UNKNOWN",
            "datetime": "drop",
        },
    },
    "deduplication": {
        "enabled": True,
        "subset_columns": None,  # None = all columns; or list of column names
        "keep": "first",         # first | last | False (drop all)
    },
    "normalization": {
        "numeric_scaling": None,       # None | minmax | zscore
        "datetime_to_utc": True,
        "string_case": "lower",        # lower | upper | title | None
        "unit_conversions": {},         # e.g., {"temp_f": {"to": "temp_c", "formula": "fahrenheit_to_celsius"}}
    },
}

# ──────────────────────────── Pipeline Steps ────────────────────────────

def step_clean(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Step 1: Clean raw data — strip whitespace, normalize headers, fill nulls.
    Returns (cleaned_df, metrics_dict).
    """
    metrics = {"null_cells_filled": 0, "rows_cleaned": 0}
    clean_cfg = config.get("cleaning", {})

    # Normalize column names
    if clean_cfg.get("normalize_column_names", True):
        df.columns = [
            col.strip().lower().replace(" ", "_").replace("-", "_")
            for col in df.columns
        ]

    # Strip whitespace from string columns
    if clean_cfg.get("strip_whitespace", True):
        str_cols = df.select_dtypes(include=["object"]).columns
        for col in str_cols:
            df[col] = df[col].astype(str).str.strip()

    # Fill nulls based on strategy
    fill = clean_cfg.get("fill_strategy", {})
    for col in df.columns:
        null_count = int(df[col].isnull().sum())
        if null_count == 0:
            continue

        if pd.api.types.is_numeric_dtype(df[col]):
            strategy = fill.get("numeric", "median")
            if strategy == "median":
                df[col] = df[col].fillna(df[col].median())
            elif strategy == "mean":
                df[col] = df[col].fillna(df[col].mean())
            elif strategy == "zero":
                df[col] = df[col].fillna(0)
            elif strategy == "drop":
                df = df.dropna(subset=[col])
                metrics["rows_cleaned"] += null_count
                continue
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            strategy = fill.get("datetime", "drop")
            if strategy == "drop":
                df = df.dropna(subset=[col])
                metrics["rows_cleaned"] += null_count
                continue
        else:
            placeholder = fill.get("string", "UNKNOWN")
            df[col] = df[col].fillna(placeholder)

        metrics["null_cells_filled"] += null_count

    return df, metrics


def step_deduplicate(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, int]:
    """
    Step 2: Remove duplicate rows.
    Returns (deduped_df, rows_removed).
    """
    dedup_cfg = config.get("deduplication", {})
    if not dedup_cfg.get("enabled", True):
        return df, 0

    before = len(df)
    subset = dedup_cfg.get("subset_columns", None)
    keep = dedup_cfg.get("keep", "first")

    df = df.drop_duplicates(subset=subset, keep=keep).reset_index(drop=True)

    return df, before - len(df)


def step_normalize(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Step 3: Normalize values — scale numerics, standardize strings, convert datetimes.
    """
    norm_cfg = config.get("normalization", {})

    # Numeric scaling
    scaling = norm_cfg.get("numeric_scaling", None)
    if scaling:
        num_cols = df.select_dtypes(include=[np.number]).columns
        for col in num_cols:
            if scaling == "minmax":
                col_min, col_max = df[col].min(), df[col].max()
                if col_max != col_min:
                    df[col] = (df[col] - col_min) / (col_max - col_min)
            elif scaling == "zscore":
                mean, std = df[col].mean(), df[col].std()
                if std > 0:
                    df[col] = (df[col] - mean) / std

    # String case normalization
    str_case = norm_cfg.get("string_case", None)
    if str_case:
        str_cols = df.select_dtypes(include=["object"]).columns
        for col in str_cols:
            if str_case == "lower":
                df[col] = df[col].str.lower()
            elif str_case == "upper":
                df[col] = df[col].str.upper()
            elif str_case == "title":
                df[col] = df[col].str.title()

    # Datetime UTC normalization
    if norm_cfg.get("datetime_to_utc", True):
        dt_cols = df.select_dtypes(include=["datetime64"]).columns
        for col in dt_cols:
            if df[col].dt.tz is None:
                df[col] = df[col].dt.tz_localize("UTC")
            else:
                df[col] = df[col].dt.tz_convert("UTC")

    return df


# ──────────────────────────── Pipeline Orchestrator ────────────────────────────

def run_transformation_pipeline(
    df: pd.DataFrame,
    db: Session,
    pipeline_name: str = "default_transform",
    source_table: str = "raw_input",
    target_table: str = "clean_output",
    config: Optional[dict] = None,
) -> Tuple[pd.DataFrame, PipelineRun]:
    """
    Execute the full transformation pipeline: clean → deduplicate → normalize.
    Records the run in the database with metrics and versioning.
    
    Returns (transformed_df, pipeline_run_record).
    """
    if config is None:
        config = DEFAULT_PIPELINE_CONFIG.copy()

    # Determine version (increment from last run of same pipeline)
    last_run = (
        db.query(PipelineRun)
        .filter(PipelineRun.pipeline_name == pipeline_name)
        .order_by(PipelineRun.version.desc())
        .first()
    )
    version = (last_run.version + 1) if last_run else 1

    # Create pipeline run record
    run = PipelineRun(
        pipeline_name=pipeline_name,
        version=version,
        status="running",
        source_table=source_table,
        target_table=target_table,
        rows_input=len(df),
        config_snapshot=config,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        # Step 1: Clean
        df, clean_metrics = step_clean(df, config)
        run.null_cells_filled = clean_metrics["null_cells_filled"]
        run.rows_cleaned = clean_metrics["rows_cleaned"]

        # Step 2: Deduplicate
        df, rows_deduped = step_deduplicate(df, config)
        run.rows_deduplicated = rows_deduped

        # Step 3: Normalize
        df = step_normalize(df, config)

        # Finalize
        run.rows_output = len(df)
        run.status = "success"
        run.completed_at = datetime.now(timezone.utc)

    except Exception as e:
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise RuntimeError(f"Pipeline '{pipeline_name}' v{version} failed: {e}") from e

    db.commit()
    db.refresh(run)
    return df, run


def rollback_pipeline(db: Session, pipeline_name: str, to_version: int) -> PipelineRun:
    """
    Mark a pipeline run as rolled back and return the target version's config.
    In production this would re-materialize the target table from the raw source
    using the older config snapshot.
    """
    current_run = (
        db.query(PipelineRun)
        .filter(PipelineRun.pipeline_name == pipeline_name)
        .order_by(PipelineRun.version.desc())
        .first()
    )
    if current_run:
        current_run.status = "rolled_back"

    target_run = (
        db.query(PipelineRun)
        .filter(
            PipelineRun.pipeline_name == pipeline_name,
            PipelineRun.version == to_version,
        )
        .first()
    )
    if not target_run:
        raise ValueError(f"No pipeline run found for '{pipeline_name}' version {to_version}")

    db.commit()
    return target_run
