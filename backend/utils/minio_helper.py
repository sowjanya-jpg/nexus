import os
import boto3
from botocore.client import Config
from dotenv import load_dotenv

load_dotenv()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")

def get_s3_client():
    """
    Get configured S3 client for MinIO.
    """
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1"
    )

def ensure_bucket_exists(bucket_name: str):
    """
    Creates S3 bucket if it doesn't exist.
    """
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=bucket_name)
    except Exception:
        s3.create_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' created successfully.")

def upload_file_bytes(bucket_name: str, object_key: str, data: bytes, content_type: str = "application/octet-stream"):
    """
    Upload raw bytes to MinIO bucket.
    """
    ensure_bucket_exists(bucket_name)
    s3 = get_s3_client()
    s3.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=data,
        ContentType=content_type
    )
    print(f"Successfully uploaded {object_key} to {bucket_name}")

def read_file_bytes(bucket_name: str, object_key: str) -> bytes:
    """
    Read bytes from MinIO bucket.
    """
    s3 = get_s3_client()
    response = s3.get_object(Bucket=bucket_name, Key=object_key)
    return response["Body"].read()
