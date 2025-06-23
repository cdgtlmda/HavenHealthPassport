"""LocalStack AWS services setup for testing."""

from typing import Any, Dict

import boto3


class LocalStackAWSServices:
    """LocalStack AWS services configuration for testing."""

    def __init__(self):
        """Initialize LocalStack services."""
        self.endpoint_url = "http://localhost:4566"
        self.region_name = "us-east-1"
        self._clients: Dict[str, Any] = {}

    def _get_client(self, service_name: str) -> Any:
        """Get or create a boto3 client for the specified service."""
        if service_name not in self._clients:
            self._clients[service_name] = boto3.client(
                service_name,
                endpoint_url=self.endpoint_url,
                region_name=self.region_name,
                aws_access_key_id="test",
                aws_secret_access_key="test",
            )
        return self._clients[service_name]

    def setup_s3_bucket(self, bucket_name: str) -> None:
        """Create an S3 bucket in LocalStack."""
        s3_client = self._get_client("s3")
        try:
            s3_client.create_bucket(Bucket=bucket_name)
        except s3_client.exceptions.BucketAlreadyExists:
            pass

    def setup_kms_key(self, key_alias: str) -> str:
        """Create a KMS key in LocalStack."""
        kms_client = self._get_client("kms")
        response = kms_client.create_key(
            Description=f"Test key for {key_alias}",
            KeyUsage="ENCRYPT_DECRYPT",
            Origin="AWS_KMS",
        )
        key_id: str = response["KeyMetadata"]["KeyId"]

        kms_client.create_alias(AliasName=f"alias/{key_alias}", TargetKeyId=key_id)

        return key_id

    def initialize_all_services(self) -> None:
        """Initialize all LocalStack services needed for testing."""
        # Setup default test buckets
        self.setup_s3_bucket("test-medical-documents")
        self.setup_s3_bucket("test-health-records")

        # Setup default KMS keys
        self.setup_kms_key("test-master-key")
        self.setup_kms_key("test-data-key")
