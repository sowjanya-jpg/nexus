import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, get_db

# Setup in-memory SQLite database for testing APIs
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables in test database
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Override FastAPI dependency
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

@patch("backend.services.ingestion.upload_file_bytes")
def test_api_health_check(mock_upload):
    # Verify health check structure
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data

@patch("backend.services.ingestion.upload_file_bytes")
def test_batch_ingestion_and_schema_flow(mock_upload_bytes):
    # 1. Post a sample CSV file
    csv_data = "timestamp,machine_id,motor_temp\n2026-07-17T10:00:00Z,CNC-01,75.5\n"
    response = client.post(
        "/api/v1/ingest/batch",
        data={"table_name": "test_table", "file_format": "csv"},
        files={"file": ("test.csv", csv_data, "text/csv")}
    )
    
    assert response.status_code == 200
    res_data = response.json()
    assert "Draft schema generated" in res_data["message"]
    draft_schema = res_data["draft_schema"]
    assert draft_schema["table_name"] == "test_table"
    
    columns = {col["name"]: col for col in draft_schema["columns"]}
    assert "timestamp" in columns
    assert "machine_id" in columns
    assert "motor_temp" in columns
    
    # 2. Retrieve schemas list
    response = client.get("/api/v1/ingest/schemas")
    assert response.status_code == 200
    schemas = response.json()
    assert len(schemas) == 1
    assert schemas[0]["table_name"] == "test_table"
    assert schemas[0]["status"] == "draft"

    # 3. Confirm Schema
    response = client.post(
        "/api/v1/ingest/schema-confirm",
        json={"table_name": "test_table"}
    )
    assert response.status_code == 200
    res_confirm = response.json()
    assert "confirmed and registered" in res_confirm["message"]
    assert res_confirm["schema"]["table_name"] == "test_table"

    # 4. Check list again
    response = client.get("/api/v1/ingest/schemas")
    schemas = response.json()
    assert schemas[0]["status"] == "confirmed"

@patch("backend.main.produce_message")
def test_stream_ingestion(mock_produce):
    # Verify stream ingest pushes to kafka helper
    payload = {"timestamp": "2026-07-17T10:00:00Z", "machine_id": "CNC-01", "vibration": 1.2}
    response = client.post(
        "/api/v1/ingest/stream",
        json=payload,
        params={"topic": "test-topic"}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_produce.assert_called_once_with("test-topic", payload)
