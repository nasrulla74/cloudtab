"""S3-compatible storage service for backup uploads and downloads."""

import logging
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_s3_client():
    """Create a boto3 S3 client from application settings."""
    kwargs = {
        "service_name": "s3",
        "region_name": settings.S3_REGION,
        "aws_access_key_id": settings.S3_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.S3_SECRET_ACCESS_KEY,
    }
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return boto3.client(**kwargs)


def upload_file_to_s3(
    local_path: str,
    bucket: str,
    s3_key: str,
) -> str:
    """Upload a local file to S3 and return the S3 URI (s3://bucket/key).

    Args:
        local_path: Path to the local file.
        bucket: Target S3 bucket name.
        s3_key: Object key in S3.

    Returns:
        S3 URI in the format s3://bucket/key
    """
    client = _get_s3_client()
    logger.info("Uploading %s -> s3://%s/%s", local_path, bucket, s3_key)
    client.upload_file(local_path, bucket, s3_key)
    uri = f"s3://{bucket}/{s3_key}"
    logger.info("Upload complete: %s", uri)
    return uri


def upload_fileobj_to_s3(
    file_obj: BinaryIO,
    bucket: str,
    s3_key: str,
) -> str:
    """Upload a file-like object to S3.

    Args:
        file_obj: File-like object with read() method.
        bucket: Target S3 bucket name.
        s3_key: Object key in S3.

    Returns:
        S3 URI in the format s3://bucket/key
    """
    client = _get_s3_client()
    logger.info("Uploading stream -> s3://%s/%s", bucket, s3_key)
    client.upload_fileobj(file_obj, bucket, s3_key)
    uri = f"s3://{bucket}/{s3_key}"
    logger.info("Upload complete: %s", uri)
    return uri


def download_file_from_s3(
    bucket: str,
    s3_key: str,
    local_path: str,
) -> str:
    """Download a file from S3 to a local path.

    Args:
        bucket: S3 bucket name.
        s3_key: Object key in S3.
        local_path: Local file path to write to.

    Returns:
        The local_path for convenience.
    """
    client = _get_s3_client()
    logger.info("Downloading s3://%s/%s -> %s", bucket, s3_key, local_path)
    client.download_file(bucket, s3_key, local_path)
    logger.info("Download complete: %s", local_path)
    return local_path


def delete_from_s3(bucket: str, s3_key: str) -> bool:
    """Delete an object from S3.

    Args:
        bucket: S3 bucket name.
        s3_key: Object key in S3.

    Returns:
        True if deletion succeeded or object didn't exist, False on error.
    """
    client = _get_s3_client()
    try:
        logger.info("Deleting s3://%s/%s", bucket, s3_key)
        client.delete_object(Bucket=bucket, Key=s3_key)
        return True
    except ClientError as e:
        logger.error("Failed to delete s3://%s/%s: %s", bucket, s3_key, e)
        return False


def get_s3_object_size(bucket: str, s3_key: str) -> int | None:
    """Get the size of an S3 object in bytes, or None if not found."""
    client = _get_s3_client()
    try:
        resp = client.head_object(Bucket=bucket, Key=s3_key)
        return resp.get("ContentLength")
    except ClientError:
        return None


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Parse an s3://bucket/key URI into (bucket, key).

    Args:
        uri: S3 URI like s3://my-bucket/path/to/file.tar.gz

    Returns:
        Tuple of (bucket_name, object_key)

    Raises:
        ValueError: If the URI is not a valid s3:// URI.
    """
    if not uri.startswith("s3://"):
        raise ValueError(f"Not a valid S3 URI: {uri}")
    without_prefix = uri[5:]  # Remove "s3://"
    parts = without_prefix.split("/", 1)
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid S3 URI (missing bucket or key): {uri}")
    return parts[0], parts[1]
