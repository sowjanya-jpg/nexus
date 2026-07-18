import json
from datetime import datetime
from sqlalchemy.orm import Session
from backend.database import RegisteredSchema
from backend.services.schema_inference import infer_schema_from_bytes
from backend.utils.minio_helper import upload_file_bytes

RAW_BUCKET = "nexus-raw"
METADATA_BUCKET = "nexus-metadata"

def ingest_batch_data(db: Session, table_name: str, data_bytes: bytes, file_name: str, file_format: str):
    """
    Ingests raw batch file (CSV/JSON), uploads it to MinIO raw zone,
    infers the schema, and saves it to Postgres as a draft.
    """
    # 1. Generate path and upload raw data to MinIO
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    object_key = f"raw/{table_name}/{timestamp}_{file_name}"
    
    content_type = "text/csv" if file_format.lower() == "csv" else "application/json"
    upload_file_bytes(RAW_BUCKET, object_key, data_bytes, content_type)
    
    # 2. Run schema inference
    schema = infer_schema_from_bytes(data_bytes, file_format, table_name)
    schema["raw_s3_path"] = f"s3://{RAW_BUCKET}/{object_key}"
    
    # 3. Store draft schema in Postgres
    db_schema = db.query(RegisteredSchema).filter(RegisteredSchema.table_name == table_name).first()
    if not db_schema:
        db_schema = RegisteredSchema(
            table_name=table_name,
            status="draft",
            schema_json=schema
        )
        db.add(db_schema)
    else:
        db_schema.status = "draft"
        db_schema.schema_json = schema
        
    db.commit()
    db.refresh(db_schema)
    
    return db_schema.schema_json

def confirm_schema(db: Session, table_name: str, schema_override: dict = None):
    """
    Confirms or overrides a draft schema, changing status to confirmed 
    and publishing it to the metadata bucket in MinIO.
    """
    db_schema = db.query(RegisteredSchema).filter(RegisteredSchema.table_name == table_name).first()
    if not db_schema:
        raise ValueError(f"No schema found for table '{table_name}' to confirm. Please run batch ingestion first.")
        
    final_schema = schema_override if schema_override else db_schema.schema_json
    
    # 1. Update database record
    db_schema.status = "confirmed"
    db_schema.schema_json = final_schema
    db_schema.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_schema)
    
    # 2. Write schema definition as a metadata artifact to MinIO
    metadata_key = f"schemas/{table_name}.json"
    schema_bytes = json.dumps(final_schema, indent=2).encode('utf-8')
    upload_file_bytes(METADATA_BUCKET, metadata_key, schema_bytes, "application/json")
    
    return final_schema
