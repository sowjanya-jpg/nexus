"""
NEXUS Forge — Telemetry & Observability Services

Simulates monitoring pipeline status, execution latency, and agent trust metrics.
"""
from typing import Dict, Any, List
import time

# In-memory telemetry cache for the MVP
TELEMETRY_LOGS = [
    {"timestamp": time.time() - 3600, "metric": "pipeline_execution_latency_ms", "value": 1420.5, "tags": {"pipeline": "clean_sensor_logs"}},
    {"timestamp": time.time() - 1800, "metric": "agent_query_cost_tokens", "value": 312, "tags": {"agent": "Executive Agent"}},
    {"timestamp": time.time(), "metric": "trust_score_aggregate", "value": 87.0, "tags": {"fabric": "curated"}}
]

def record_metric(metric_name: str, value: float, tags: Dict[str, str] = None) -> Dict[str, Any]:
    """Records a single telemetry metric."""
    log = {
        "timestamp": time.time(),
        "metric": metric_name,
        "value": value,
        "tags": tags or {}
    }
    TELEMETRY_LOGS.append(log)
    return log

def get_telemetry_metrics() -> List[Dict[str, Any]]:
    """Returns the recorded telemetry metrics."""
    return TELEMETRY_LOGS
