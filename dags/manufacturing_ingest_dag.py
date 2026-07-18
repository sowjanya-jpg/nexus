import os
import glob
import shutil
import requests
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Default arguments for DAG
default_args = {
    'owner': 'nexus_forge',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

BACKEND_API_URL = os.getenv("NEXUS_BACKEND_URL", "http://host.docker.internal:8000")
LANDING_DIR = "/opt/airflow/data_landing"
PROCESSED_DIR = "/opt/airflow/data_landing/processed"

def process_batch_files():
    """
    Scans the landing directory for batch CSV files and posts them to NEXUS Forge API.
    """
    print(f"Scanning for batch files in {LANDING_DIR}...")
    
    # Ensure processed dir exists
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    
    csv_files = glob.glob(os.path.join(LANDING_DIR, "machine_logs_*.csv"))
    if not csv_files:
        print("No CSV files found to ingest.")
        return
        
    print(f"Found {len(csv_files)} files. Starting batch ingestion...")
    
    for file_path in csv_files:
        file_name = os.path.basename(file_path)
        print(f"Processing file: {file_name}")
        
        # Prepare API request
        url = f"{BACKEND_API_URL}/api/v1/ingest/batch"
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (file_name, f, 'text/csv')}
                data = {
                    'table_name': 'machine_logs',
                    'file_format': 'csv'
                }
                
                print(f"Sending file to {url}...")
                response = requests.post(url, data=data, files=files, timeout=10.0)
                
            if response.status_code == 200:
                print(f"Successfully ingested {file_name}. API Response: {response.json().get('message')}")
                
                # Move to processed folder
                dest_path = os.path.join(PROCESSED_DIR, file_name)
                shutil.move(file_path, dest_path)
                print(f"Moved {file_name} to {dest_path}")
            else:
                print(f"Error ingesting {file_name}. API returned status {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"Failed to ingest {file_name}. Connection/execution error: {e}")

# Define the DAG
with DAG(
    'manufacturing_batch_ingest',
    default_args=default_args,
    description='Automated scheduled batch ingestion for NEXUS Forge Lakehouse',
    schedule_interval=None,  # Trigger manually or via orchestration API for demo purposes
    catchup=False,
    tags=['nexus', 'ingestion'],
) as dag:

    ingest_task = PythonOperator(
        task_id='process_batch_csv_files',
        python_callable=process_batch_files,
    )

    ingest_task
