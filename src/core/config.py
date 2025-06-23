"""AWS Configuration Module.

This module provides AWS-related configuration settings for the Haven Health Passport system.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class AWSConfig:
    """AWS configuration settings."""

    # AWS credentials and region
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    aws_region: str = "us-east-1"

    # S3 settings
    s3_bucket_name: str = "haven-health-passport"
    s3_endpoint_url: Optional[str] = None

    # DynamoDB settings
    dynamodb_table_prefix: str = "haven_"
    dynamodb_endpoint_url: Optional[str] = None

    # Textract settings
    textract_endpoint_url: Optional[str] = None

    # Bedrock settings
    bedrock_endpoint_url: Optional[str] = None
    bedrock_region: str = "us-east-1"

    # Transcribe settings
    transcribe_endpoint_url: Optional[str] = None

    # CloudWatch settings
    cloudwatch_log_group: str = "/aws/lambda/haven-health-passport"
    cloudwatch_metrics_namespace: str = "HavenHealthPassport"

    def __post_init__(self) -> None:
        """Load AWS configuration from environment variables."""
        # Load from environment if not explicitly set
        if not self.aws_access_key_id:
            self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        if not self.aws_secret_access_key:
            self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        if not self.aws_session_token:
            self.aws_session_token = os.getenv("AWS_SESSION_TOKEN")

        # Override with environment variables if present
        self.aws_region = os.getenv("AWS_DEFAULT_REGION", self.aws_region)
        self.s3_bucket_name = os.getenv("S3_BUCKET_NAME", self.s3_bucket_name)
        self.dynamodb_table_prefix = os.getenv(
            "DYNAMODB_TABLE_PREFIX", self.dynamodb_table_prefix
        )

        # Endpoint URLs for local development/testing
        self.s3_endpoint_url = os.getenv("S3_ENDPOINT_URL", self.s3_endpoint_url)
        self.dynamodb_endpoint_url = os.getenv(
            "DYNAMODB_ENDPOINT_URL", self.dynamodb_endpoint_url
        )
        self.textract_endpoint_url = os.getenv(
            "TEXTRACT_ENDPOINT_URL", self.textract_endpoint_url
        )
        self.bedrock_endpoint_url = os.getenv(
            "BEDROCK_ENDPOINT_URL", self.bedrock_endpoint_url
        )
        self.transcribe_endpoint_url = os.getenv(
            "TRANSCRIBE_ENDPOINT_URL", self.transcribe_endpoint_url
        )

        # CloudWatch settings
        self.cloudwatch_log_group = os.getenv(
            "CLOUDWATCH_LOG_GROUP", self.cloudwatch_log_group
        )
        self.cloudwatch_metrics_namespace = os.getenv(
            "CLOUDWATCH_METRICS_NAMESPACE", self.cloudwatch_metrics_namespace
        )

    def get_boto3_kwargs(self, service_name: str) -> dict:
        """Get boto3 client kwargs for a specific service."""
        kwargs = {"region_name": self.aws_region}

        # Add credentials if available
        if self.aws_access_key_id and self.aws_secret_access_key:
            kwargs.update(
                {
                    "aws_access_key_id": self.aws_access_key_id,
                    "aws_secret_access_key": self.aws_secret_access_key,
                }
            )

        if self.aws_session_token:
            kwargs["aws_session_token"] = self.aws_session_token

        # Add endpoint URL for specific services (useful for local development)
        endpoint_mapping = {
            "s3": self.s3_endpoint_url,
            "dynamodb": self.dynamodb_endpoint_url,
            "textract": self.textract_endpoint_url,
            "bedrock": self.bedrock_endpoint_url,
            "bedrock-runtime": self.bedrock_endpoint_url,
            "transcribe": self.transcribe_endpoint_url,
        }

        endpoint_url = endpoint_mapping.get(service_name)
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url

        return kwargs


# Create a default instance
default_aws_config = AWSConfig()
