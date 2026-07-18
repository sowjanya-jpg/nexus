import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Create a local test SQLITE database for validation
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_endpoints.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="module")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in ["healthy", "unhealthy"]

def test_lakehouse_tables(client):
    # Test Register
    payload = {
        "table_name": "test_table",
        "zone": "raw",
        "storage_path": "s3://nexus/raw/test_table"
    }
    response = client.post("/api/v1/lakehouse/tables", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Test List
    response = client.get("/api/v1/lakehouse/tables")
    assert response.status_code == 200
    assert len(response.json()) > 0

def test_causal_links(client):
    # Test Seed
    response = client.post("/api/v1/lakehouse/causal-links/seed")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Test List
    response = client.get("/api/v1/lakehouse/causal-links")
    assert response.status_code == 200
    assert len(response.json()) > 0

def test_bi_query(client):
    payload = {"query": "Optimize transformer maintenance in western plants"}
    response = client.post("/api/v1/bi/query", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "recommendation" in response.json()["data"]

def test_governance_scan(client):
    payload = {
        "table_name": "raw_logs",
        "sample_data": [
            {"id": 1, "email": "admin@nexus.ai", "ssn": "123-45-6789"}
        ]
    }
    response = client.post("/api/v1/governance/scan", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["data"]["pii_issues_found"] > 0

def test_literacy_learning_path(client):
    response = client.get("/api/v1/literacy/learning-path?role=Analyst")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_novelty_privacy(client):
    payload = {
        "data": [{"id": 1, "value": 100.0}],
        "epsilon": 0.5
    }
    response = client.post("/api/v1/novelty/privacy", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["masked_data"][0]["value"] != 100.0

def test_telemetry_metrics(client):
    # Write Metric
    payload = {"name": "test_latency", "value": 120.5}
    response = client.post("/api/v1/metrics", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Get Metrics
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
