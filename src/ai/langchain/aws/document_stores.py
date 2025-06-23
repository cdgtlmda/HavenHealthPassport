"""
S3 Document Store for LangChain.

Provides document storage and retrieval using S3
"""

import logging
from typing import Any, Dict, List, Optional, cast

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3DocumentStore:
    """S3-backed document store for LangChain."""

    def __init__(self, bucket_name: str, prefix: str = "documents"):
        """Initialize S3 document store."""
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.s3 = boto3.client("s3")

    def store_document(
        self, document_id: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a document in S3."""
        key = f"{self.prefix}/{document_id}"

        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=content,
                Metadata=metadata or {},
                ContentType="text/plain",
            )
            return key
        except ClientError as e:
            logger.error("Failed to store document: %s", str(e))
            raise

    def get_document(self, document_id: str) -> Optional[str]:
        """Retrieve a document from S3."""
        key = f"{self.prefix}/{document_id}"

        try:
            response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
            return cast(str, response["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise

    def list_documents(self, max_results: int = 100) -> List[str]:
        """List all document IDs."""
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name, Prefix=self.prefix, MaxKeys=max_results
            )

            if "Contents" not in response:
                return []

            # Extract document IDs from keys
            document_ids = []
            for obj in response["Contents"]:
                key = obj["Key"]
                if key.startswith(self.prefix + "/"):
                    doc_id = key[len(self.prefix) + 1 :]
                    document_ids.append(doc_id)

            return document_ids

        except ClientError as e:
            logger.error("Failed to list documents: %s", str(e))
            return []

    def delete_document(self, document_id: str) -> bool:
        """Delete a document from S3."""
        key = f"{self.prefix}/{document_id}"

        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            logger.error("Failed to delete document: %s", str(e))
            return False
