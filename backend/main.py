import os
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from backend.database import init_db, get_db, RegisteredSchema, text
from backend.services.ingestion import ingest_batch_data, confirm_schema
from backend.services.transformation import run_transformation_pipeline, rollback_pipeline, DEFAULT_PIPELINE_CONFIG
from backend.services.drift_detection import run_drift_detection
from backend.services.self_healing import apply_repairs
from backend.utils.kafka_helper import init_kafka_topics, produce_message
from backend.utils.minio_helper import get_s3_client
from backend.models.pipeline_models import PipelineRun, DriftAlert, RepairAction
from backend.models.lakehouse_models import LakehouseTable, CausalRelationship
from backend.services.lakehouse_service import (
    register_lakehouse_table,
    get_all_lakehouse_tables,
    update_trust_score,
    add_causal_link,
    get_causal_links,
    seed_demo_causal_data
)
from backend.database_neo4j import get_neo4j_session
from backend.services.graph_service import (
    seed_ontology,
    resolve_entities,
    generate_er_diagram,
    generate_glossary
)
from backend.models.rag_models import ContextVector
from backend.services.rag_service import store_context, retrieve_context
from backend.models.approval_models import AgentActionApproval
from backend.services.approval_service import queue_action, get_pending_approvals, resolve_approval
from backend.agents.orchestrator import process_chat
from backend.agents.steward_agent import run_governance_scan
from backend.services.reasoning_chain import run_nl_to_action_pipeline
from backend.services.dashboard_service import generate_dashboard_config, generate_narrative
from backend.services.decision_engine import run_causal_simulation, generate_recommendation
from backend.services.copilot_service import explain_sql_pipeline, trigger_external_action
from backend.services.literacy_service import get_learning_path, get_sandbox_dataset, grade_literacy_exercise
from backend.services.novelty_service import apply_feedback_loop, apply_privacy_mask, run_cross_enterprise_simulation
from backend.services.telemetry_service import record_metric, get_telemetry_metrics

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize systems on startup: create tables, configure S3 buckets, and init Kafka topics.
    """
    print("Booting NEXUS Forge Backend Services...")
    init_db()
    
    # Auto-seed the demo causal data so simulations react to the slider!
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        seed_demo_causal_data(db)
        print("Demo causal data seeded successfully.")
    except Exception as e:
        print(f"Warning: Failed to seed demo causal metadata: {e}")
    finally:
        db.close()

    # Try to initialize Kafka topics
    kafka_ok = init_kafka_topics()
    if kafka_ok:
        print("Kafka initialization complete.")
    else:
        print("Kafka initialization skipped/failed. Running in hybrid standalone database mode.")
    yield

app = FastAPI(
    title="NEXUS Forge - Data Intelligence Fabric API",
    description="Intelligent ingestion, streaming, and metadata APIs for the NEXUS Forge platform.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Check downstream system health (Postgres, MinIO, Kafka).
    """
    health = {
        "status": "healthy",
        "services": {
            "postgres": "unknown",
            "minio": "unknown",
            "kafka": "unknown"
        }
    }
    
    # 1. Test Postgres
    try:
        db.execute(text("SELECT 1"))
        health["services"]["postgres"] = "online"
    except Exception as e:
        health["services"]["postgres"] = f"offline: {e}"
        health["status"] = "unhealthy"

    # 2. Test MinIO
    try:
        s3 = get_s3_client()
        s3.list_buckets()
        health["services"]["minio"] = "online"
    except Exception as e:
        health["services"]["minio"] = f"offline: {e}"
        health["status"] = "unhealthy"

    # 3. Test Kafka
    # Since we might not want to block health check on heavy kafka timeouts:
    from confluent_kafka.admin import AdminClient
    try:
        KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
        admin_client = AdminClient({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})
        admin_client.list_topics(timeout=1.0)
        health["services"]["kafka"] = "online"
    except Exception:
        health["services"]["kafka"] = "offline (or starting up)"
        # Do not mark overall status unhealthy solely on streaming if batch ingestion works
        
    return health

@app.post("/api/v1/ingest/batch")
async def api_ingest_batch(
    table_name: str = Form(...),
    file_format: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a batch CSV or JSON dataset, profile it, and save the raw file and draft schema.
    """
    if file_format.lower() not in ["csv", "json"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Must be 'csv' or 'json'."
        )
        
    try:
        content = await file.read()
        draft_schema = ingest_batch_data(
            db=db,
            table_name=table_name,
            data_bytes=content,
            file_name=file.filename,
            file_format=file_format
        )
        return {
            "message": f"Successfully ingested batch file for '{table_name}'. Draft schema generated.",
            "draft_schema": draft_schema
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {e}"
        )

@app.post("/api/v1/ingest/schema-confirm")
def api_confirm_schema(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Confirm or override the draft schema for a table.
    """
    table_name = payload.get("table_name")
    schema_override = payload.get("schema_override")
    
    if not table_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="table_name is required in payload."
        )
        
    try:
        confirmed_schema = confirm_schema(db, table_name, schema_override)
        return {
            "message": f"Schema for table '{table_name}' confirmed and registered.",
            "schema": confirmed_schema
        }
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schema confirmation failed: {e}"
        )

@app.get("/api/v1/ingest/schemas")
def api_list_schemas(db: Session = Depends(get_db)):
    """
    Get all registered schemas (both draft and confirmed).
    """
    schemas = db.query(RegisteredSchema).all()
    return [
        {
            "id": s.id,
            "table_name": s.table_name,
            "status": s.status,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
            "schema": s.schema_json
        }
        for s in schemas
    ]

@app.post("/api/v1/ingest/stream")
def api_ingest_stream(
    payload: Dict[str, Any],
    topic: str = "iot-sensor-stream"
):
    """
    Endpoint for real-time IoT events to stream directly into the Kafka topic.
    """
    try:
        produce_message(topic, payload)
        return {
            "status": "success",
            "message": f"Event streamed to Kafka topic '{topic}'"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Streaming ingestion failed: {e}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Epic 2: Autonomous Data Engineering Layer
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/pipeline/transform")
async def api_run_pipeline(
    table_name: str = Form(...),
    file_format: str = Form("csv"),
    file: UploadFile = File(...),
    pipeline_name: str = Form("default_transform"),
    auto_heal: bool = Form(True),
    db: Session = Depends(get_db),
):
    """
    Run the full autonomous data engineering pipeline on an uploaded file:
    1. Parse file into DataFrame
    2. Run transformation (clean → deduplicate → normalize)
    3. Run drift detection against registered baseline schema
    4. Auto-apply self-healing repairs for low-risk issues
    Returns pipeline run metrics, drift alerts, and repair actions taken.
    """
    import io
    import pandas as pd

    if file_format.lower() not in ["csv", "json"]:
        raise HTTPException(status_code=400, detail="Unsupported format. Use 'csv' or 'json'.")

    try:
        content = await file.read()

        # Parse
        if file_format.lower() == "csv":
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_json(io.BytesIO(content))

        # Step 1: Transform
        transformed_df, pipeline_run = run_transformation_pipeline(
            df=df, db=db,
            pipeline_name=pipeline_name,
            source_table=f"raw_{table_name}",
            target_table=f"clean_{table_name}",
        )

        # Step 2: Drift detection (compare against confirmed schema if available)
        drift_alerts = []
        repair_actions = []
        baseline = db.query(RegisteredSchema).filter(
            RegisteredSchema.table_name == table_name,
            RegisteredSchema.status == "confirmed",
        ).first()

        if baseline and baseline.schema_json:
            drift_alerts = run_drift_detection(
                df=transformed_df,
                baseline_schema=baseline.schema_json,
                pipeline_run_id=pipeline_run.id,
                db=db,
            )

            # Step 3: Self-healing
            if auto_heal and drift_alerts:
                transformed_df, repair_actions = apply_repairs(
                    df=transformed_df,
                    alerts=drift_alerts,
                    pipeline_run_id=pipeline_run.id,
                    db=db,
                    baseline_schema=baseline.schema_json,
                    auto_apply_max_risk="low",
                )

        return {
            "message": f"Pipeline '{pipeline_name}' v{pipeline_run.version} completed.",
            "pipeline_run": {
                "id": pipeline_run.id,
                "version": pipeline_run.version,
                "status": pipeline_run.status,
                "rows_input": pipeline_run.rows_input,
                "rows_output": pipeline_run.rows_output,
                "rows_deduplicated": pipeline_run.rows_deduplicated,
                "rows_cleaned": pipeline_run.rows_cleaned,
                "null_cells_filled": pipeline_run.null_cells_filled,
            },
            "drift_alerts": [
                {
                    "id": a.id,
                    "type": a.alert_type,
                    "severity": a.severity,
                    "column": a.column_name,
                    "description": a.description,
                    "resolved": a.resolved,
                }
                for a in drift_alerts
            ],
            "repair_actions": [
                {
                    "id": r.id,
                    "strategy": r.strategy,
                    "risk_level": r.risk_level,
                    "status": r.status,
                    "description": r.description,
                }
                for r in repair_actions
            ],
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")


@app.get("/api/v1/pipeline/runs")
def api_list_pipeline_runs(
    pipeline_name: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    List pipeline runs, optionally filtered by pipeline name.
    """
    query = db.query(PipelineRun)
    if pipeline_name:
        query = query.filter(PipelineRun.pipeline_name == pipeline_name)
    runs = query.order_by(PipelineRun.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "pipeline_name": r.pipeline_name,
            "version": r.version,
            "status": r.status,
            "source_table": r.source_table,
            "target_table": r.target_table,
            "rows_input": r.rows_input,
            "rows_output": r.rows_output,
            "rows_deduplicated": r.rows_deduplicated,
            "null_cells_filled": r.null_cells_filled,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
        }
        for r in runs
    ]


@app.get("/api/v1/pipeline/drift-alerts")
def api_list_drift_alerts(
    pipeline_run_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    List drift alerts, optionally filtered by pipeline run.
    """
    query = db.query(DriftAlert)
    if pipeline_run_id:
        query = query.filter(DriftAlert.pipeline_run_id == pipeline_run_id)
    alerts = query.order_by(DriftAlert.created_at.desc()).all()
    return [
        {
            "id": a.id,
            "pipeline_run_id": a.pipeline_run_id,
            "type": a.alert_type,
            "severity": a.severity,
            "column": a.column_name,
            "description": a.description,
            "details": a.details,
            "resolved": a.resolved,
            "resolved_by": a.resolved_by,
        }
        for a in alerts
    ]


@app.get("/api/v1/pipeline/repair-actions")
def api_list_repair_actions(
    pipeline_run_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    List repair actions, optionally filtered by pipeline run.
    """
    query = db.query(RepairAction)
    if pipeline_run_id:
        query = query.filter(RepairAction.pipeline_run_id == pipeline_run_id)
    actions = query.order_by(RepairAction.created_at.desc()).all()
    return [
        {
            "id": a.id,
            "pipeline_run_id": a.pipeline_run_id,
            "strategy": a.strategy,
            "risk_level": a.risk_level,
            "status": a.status,
            "description": a.description,
            "before_snapshot": a.before_snapshot,
            "after_snapshot": a.after_snapshot,
            "applied_at": a.applied_at,
        }
        for a in actions
    ]


@app.post("/api/v1/pipeline/rollback")
def api_rollback_pipeline(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """
    Roll back a pipeline to a previous version.
    """
    pipeline_name = payload.get("pipeline_name")
    to_version = payload.get("to_version")
    if not pipeline_name or to_version is None:
        raise HTTPException(status_code=400, detail="pipeline_name and to_version are required.")
    try:
        target_run = rollback_pipeline(db, pipeline_name, to_version)
        return {
            "message": f"Pipeline '{pipeline_name}' rolled back to version {to_version}.",
            "target_config": target_run.config_snapshot,
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))

# ═══════════════════════════════════════════════════════════════════════
# Epic 3: AI-Native Data Fabric
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/lakehouse/tables")
def api_register_lakehouse_table(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Register or update a table in the lakehouse storage.
    """
    table_name = payload.get("table_name")
    zone = payload.get("zone", "raw")
    storage_path = payload.get("storage_path")
    trust_score = payload.get("trust_score", 100.0)
    
    if not table_name or not storage_path:
        raise HTTPException(status_code=400, detail="table_name and storage_path are required.")
        
    try:
        table = register_lakehouse_table(db, table_name, zone, storage_path, trust_score)
        return {"status": "success", "table": table}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/lakehouse/tables")
def api_get_lakehouse_tables(db: Session = Depends(get_db)):
    """
    Get all registered lakehouse tables.
    """
    tables = get_all_lakehouse_tables(db)
    return tables

@app.post("/api/v1/lakehouse/causal-links")
def api_add_causal_link(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Add a new causal metadata link.
    """
    source_event = payload.get("source_event")
    target_metric = payload.get("target_metric")
    confidence_score = payload.get("confidence_score", 0.0)
    description = payload.get("description", "")
    
    if not source_event or not target_metric:
        raise HTTPException(status_code=400, detail="source_event and target_metric are required.")
        
    try:
        link = add_causal_link(db, source_event, target_metric, confidence_score, description)
        return {"status": "success", "causal_link": link}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/lakehouse/causal-links")
def api_get_causal_links(db: Session = Depends(get_db)):
    """
    Get all causal metadata links.
    """
    links = get_causal_links(db)
    return links

@app.post("/api/v1/lakehouse/causal-links/seed")
def api_seed_causal_links(db: Session = Depends(get_db)):
    """
    Populate a handful of hand-authored examples for the demo dataset.
    """
    try:
        links = seed_demo_causal_data(db)
        return {"status": "success", "message": f"Seeded {len(links)} causal relationships.", "links": links}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Epic 4: Knowledge Graph Core
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/graph/seed")
def api_seed_graph_ontology(session = Depends(get_neo4j_session)):
    """
    Seeds the Neo4j graph with the initial ontology and demo data.
    """
    try:
        result = seed_ontology(session)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/graph/resolve-entities")
def api_resolve_entities(session = Depends(get_neo4j_session)):
    """
    Implements entity resolution by finding variant keys and linking them to a golden entity.
    """
    try:
        result = resolve_entities(session)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/graph/er-diagram")
def api_generate_er_diagram(session = Depends(get_neo4j_session)):
    """
    Auto-generates an ER diagram (Mermaid format) from the graph schema.
    """
    try:
        mermaid_str = generate_er_diagram(session)
        return {"status": "success", "diagram": mermaid_str}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/graph/glossary")
def api_generate_glossary(session = Depends(get_neo4j_session)):
    """
    Auto-generates a business glossary from the graph metadata.
    """
    try:
        glossary = generate_glossary(session)
        return {"status": "success", "glossary": glossary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Epic 5: Context Layer & RAG
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/rag/index")
def api_rag_index(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Embeds and stores context in Postgres via pgvector.
    """
    reference_id = payload.get("reference_id")
    content_type = payload.get("content_type", "document")
    content = payload.get("content")
    metadata = payload.get("metadata", {})
    
    if not reference_id or not content:
        raise HTTPException(status_code=400, detail="reference_id and content are required.")
        
    try:
        vec = store_context(db, reference_id, content_type, content, metadata)
        return {"status": "success", "message": "Context stored.", "id": vec.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/rag/query")
def api_rag_query(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Performs vector similarity search in Postgres.
    """
    query = payload.get("query")
    limit = payload.get("limit", 5)
    
    if not query:
        raise HTTPException(status_code=400, detail="query is required.")
        
    try:
        results = retrieve_context(db, query, limit)
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Epic 6: Agent Orchestration
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/agents/chat")
def api_agent_chat(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Interact with the Executive Agent which may route to specialists.
    """
    message = payload.get("message")
    
    if not message:
        raise HTTPException(status_code=400, detail="message is required.")
        
    try:
        result = process_chat(message)
        
        # If the specialist determined an action needs approval, queue it.
        if result["requires_approval"]:
            approval = queue_action(
                db=db,
                agent_name=result["agent"],
                action_type="agent_proposed_action",
                payload={"simulated": True, "message": message},
                reasoning=result["response"]
            )
            result["approval_id"] = approval.id
            result["response"] += f" (Approval Ticket #{approval.id})"
            
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/agents/approvals")
def api_get_approvals(db: Session = Depends(get_db)):
    """
    View pending actions awaiting human approval.
    """
    approvals = get_pending_approvals(db)
    return [
        {
            "id": a.id,
            "agent": a.agent_name,
            "action": a.action_type,
            "reasoning": a.reasoning,
            "status": a.status,
            "created_at": a.created_at
        }
        for a in approvals
    ]

@app.post("/api/v1/agents/approvals/{approval_id}")
def api_resolve_approval(
    approval_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Approve or reject a pending action.
    """
    decision = payload.get("decision")
    feedback = payload.get("feedback", "")
    
    if decision not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Decision must be 'approved' or 'rejected'.")
        
    try:
        approval = resolve_approval(db, approval_id, decision, feedback)
        return {"status": "success", "message": f"Action {decision}.", "approval_id": approval.id}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Epic 7: Data Steward AI (Governance)
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/governance/scan")
def api_governance_scan(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Runs a proactive governance scan (PII, freshness) on a sample dataset.
    """
    table_name = payload.get("table_name", "unknown_table")
    sample_data = payload.get("sample_data", [])
    
    try:
        result = run_governance_scan(db, sample_data, table_name)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════
# Epic 8: NL to Action BI
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/bi/query")
def api_bi_query(
    payload: Dict[str, Any]
):
    """
    Executes the full NL to Action BI reasoning chain.
    """
    query = payload.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="query is required.")
        
    try:
        result = run_nl_to_action_pipeline(query)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════
# Epic 9: Adaptive Intelligent Dashboard Studio
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/dashboard/generate")
def api_generate_dashboard(
    payload: Dict[str, Any]
):
    """
    Generate an AI layout config from a stated goal.
    """
    goal = payload.get("goal")
    if not goal:
        raise HTTPException(status_code=400, detail="goal is required.")
    try:
        config = generate_dashboard_config(goal)
        return {"status": "success", "config": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/dashboard/narrative")
def api_generate_dashboard_narrative(
    payload: Dict[str, Any]
):
    """
    Generate dynamic narrative summary of the current dashboard configuration.
    """
    config = payload.get("config")
    if not config:
        raise HTTPException(status_code=400, detail="config is required.")
    try:
        narrative = generate_narrative(config)
        return {"status": "success", "narrative": narrative}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════
# Epic 10: AI Decision Intelligence Engine
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/decision/simulate")
def api_simulate_decision(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Simulate decision scenarios using causal metadata.
    """
    scenario = payload.get("scenario")
    interventions = payload.get("interventions", [])
    if not scenario:
        raise HTTPException(status_code=400, detail="scenario is required.")
    try:
        results = run_causal_simulation(db, scenario, interventions)
        return {"status": "success", "simulation": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/decision/recommend")
def api_recommend_decision(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Generate a governance-aware recommendation for a scenario.
    """
    scenario = payload.get("scenario")
    if not scenario:
        raise HTTPException(status_code=400, detail="scenario is required.")
    try:
        recommendation = generate_recommendation(db, scenario)
        return {"status": "success", "recommendation": recommendation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════
# Epic 11: Enterprise Knowledge & Action Copilot
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/copilot/explain")
def api_copilot_explain(
    payload: Dict[str, Any]
):
    """
    Explain SQL query pipeline or schema definition.
    """
    sql_query = payload.get("sql_query")
    if not sql_query:
        raise HTTPException(status_code=400, detail="sql_query is required.")
    try:
        explanation = explain_sql_pipeline(sql_query)
        return {"status": "success", "explanation": explanation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/copilot/execute")
def api_copilot_execute(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Execute task (gated behind explicit approval for high-risk actions).
    """
    task_name = payload.get("task_name")
    if not task_name:
        raise HTTPException(status_code=400, detail="task_name is required.")
    try:
        result = trigger_external_action(db, task_name)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════
# Epic 12: Data Democratization & Literacy Hub
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/v1/literacy/learning-path")
def api_get_learning_path(
    role: str = "Analyst"
):
    """
    Fetch lessons tailored to user's role.
    """
    try:
        path = get_learning_path(role)
        return {"status": "success", "learning_path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/literacy/sandbox")
def api_get_sandbox(
    sandbox_id: str = "maintenance_sandbox"
):
    """
    Fetch sandbox dataset for sandbox play.
    """
    try:
        dataset = get_sandbox_dataset(sandbox_id)
        return {"status": "success", "dataset": dataset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/literacy/exercise/submit")
def api_submit_exercise(
    payload: Dict[str, Any]
):
    """
    Grade user's response to an exercise.
    """
    lesson_id = payload.get("lesson_id")
    answer = payload.get("answer")
    if not lesson_id or not answer:
        raise HTTPException(status_code=400, detail="lesson_id and answer are required.")
    try:
        result = grade_literacy_exercise(lesson_id, answer)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════
# Epic 13: Additional Novelty Features
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/novelty/privacy")
def api_privacy_masking(
    payload: Dict[str, Any]
):
    """
    Applies differential privacy noise mask to numerical payload.
    """
    data = payload.get("data", [])
    epsilon = payload.get("epsilon", 0.5)
    try:
        masked_data = apply_privacy_mask(data, epsilon)
        return {"status": "success", "masked_data": masked_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/novelty/cross-simulate")
def api_cross_simulate(
    payload: Dict[str, Any]
):
    """
    Runs a cross-enterprise simulation sharing key metrics with partner Supplier X.
    """
    scenario = payload.get("scenario", "Lead time reduction")
    supplier_id = payload.get("supplier_id", "Supplier X")
    try:
        result = run_cross_enterprise_simulation(scenario, supplier_id)
        return {"status": "success", "simulation": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/novelty/feedback")
def api_apply_feedback(
    payload: Dict[str, Any]
):
    """
    Self-improving feedback loop adjusts trust score.
    """
    table_name = payload.get("table_name")
    approval_status = payload.get("status")
    current_trust = payload.get("current_trust", 90.0)
    if not table_name or not approval_status:
        raise HTTPException(status_code=400, detail="table_name and status are required.")
    try:
        new_trust = apply_feedback_loop(table_name, approval_status, current_trust)
        return {"status": "success", "new_trust_score": new_trust}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════
# Epic 14: Observability, Telemetry & Testing
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/v1/metrics")
def api_get_metrics():
    """
    Returns recorded Prometheus / OpenTelemetry telemetry logs.
    """
    try:
        metrics = get_telemetry_metrics()
        return {"status": "success", "metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/metrics")
def api_record_metric(
    payload: Dict[str, Any]
):
    """
    Logs a new operational performance metric.
    """
    name = payload.get("name")
    value = payload.get("value")
    tags = payload.get("tags", {})
    if not name or value is None:
        raise HTTPException(status_code=400, detail="name and value are required.")
    try:
        log = record_metric(name, value, tags)
        return {"status": "success", "recorded_metric": log}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

