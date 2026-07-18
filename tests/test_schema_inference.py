import pytest
import pandas as pd
from backend.services.schema_inference import infer_schema_from_df

def test_infer_schema_from_df():
    # 1. Arrange: Create a DataFrame with structured types
    data = {
        "timestamp": ["2026-07-17T10:00:00Z", "2026-07-17T10:01:00Z", "2026-07-17T10:02:00Z"],
        "machine_id": ["CNC-01", "CNC-01", "CNC-02"],
        "motor_temp_celsius": [75.2, 80.5, 68.1],
        "vibration_amplitude": [1.25, 2.30, 0.95],
        "error_count": [0, 1, 0],
        "is_operational": [True, True, False]
    }
    df = pd.DataFrame(data)
    
    # Convert timestamp to datetime as it might be done or parsed
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # 2. Act
    schema = infer_schema_from_df(df, "machine_telemetry")
    
    # 3. Assert
    assert schema["table_name"] == "machine_telemetry"
    assert schema["row_count"] == 3
    
    columns = {col["name"]: col for col in schema["columns"]}
    
    # Check types
    assert columns["timestamp"]["data_type"] == "datetime"
    assert columns["machine_id"]["data_type"] == "string"
    assert columns["motor_temp_celsius"]["data_type"] == "float"
    assert columns["vibration_amplitude"]["data_type"] == "float"
    assert columns["error_count"]["data_type"] == "integer"
    assert columns["is_operational"]["data_type"] == "boolean"
    
    # Check nullability
    for name, col in columns.items():
        assert col["nullable"] is False
        
    # Check statistics
    assert columns["machine_id"]["statistics"]["distinct_values"] == 2
    assert columns["motor_temp_celsius"]["statistics"]["min"] == 68.1
    assert columns["motor_temp_celsius"]["statistics"]["max"] == 80.5
    assert abs(columns["motor_temp_celsius"]["statistics"]["mean"] - 74.6) < 0.1
    
    # Check heuristics/tags
    assert "TIMESTAMP" in columns["timestamp"]["tags"]
    assert "IDENTIFIER" in columns["machine_id"]["tags"]
    assert "MEASUREMENT_TEMPERATURE" in columns["motor_temp_celsius"]["tags"]
    assert "METRIC_VIBRATION" in columns["vibration_amplitude"]["tags"]
    # is_operational doesn't match "status/state/code" heuristic, so falls back to METRIC_GENERAL
    assert "METRIC_GENERAL" in columns["is_operational"]["tags"]
