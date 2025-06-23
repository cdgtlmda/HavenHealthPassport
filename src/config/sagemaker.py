"""SageMaker configuration settings."""

import os
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError as BotoCore
from botocore.exceptions import ClientError

from src.config.loader import get_settings


class SageMakerConfig:
    """SageMaker configuration management."""

    def __init__(self) -> None:
        """Initialize SageMaker configuration."""
        self.settings = get_settings()
        self.environment = os.getenv("ENVIRONMENT", "development")

    @property
    def execution_role_arn(self) -> str:
        """Get SageMaker execution role ARN."""
        # First check environment variable
        role_arn = os.getenv("SAGEMAKER_EXECUTION_ROLE_ARN")
        if role_arn:
            return role_arn

        # Construct role ARN based on environment
        account_id = os.getenv("AWS_ACCOUNT_ID", "")
        if account_id:
            return f"arn:aws:iam::{account_id}:role/haven-health-sagemaker-role-{self.environment}"

        # Try to get from STS
        try:
            # boto3 imported at module level

            sts = boto3.client("sts")
            account_id = sts.get_caller_identity()["Account"]
            return f"arn:aws:iam::{account_id}:role/haven-health-sagemaker-role-{self.environment}"
        except (BotoCore, ClientError, ConnectionError):
            # Fallback for local development
            return "arn:aws:iam::123456789012:role/SageMakerRole"

    @property
    def cultural_adaptation_endpoint(self) -> Optional[str]:
        """Get cultural adaptation model endpoint name."""
        endpoint = os.getenv("CULTURAL_ADAPTATION_ENDPOINT")
        if endpoint:
            return endpoint

        # Check for pattern-based endpoints
        base_endpoint = os.getenv("SAGEMAKER_ENDPOINT_NAME", "haven-health-ml-endpoint")
        return f"{base_endpoint}-cultural-pattern-{self.environment}"

    @property
    def communication_style_endpoint(self) -> Optional[str]:
        """Get communication style detector endpoint name."""
        endpoint = os.getenv("COMMUNICATION_STYLE_ENDPOINT")
        if endpoint:
            return endpoint

        base_endpoint = os.getenv("SAGEMAKER_ENDPOINT_NAME", "haven-health-ml-endpoint")
        return f"{base_endpoint}-style-detector-{self.environment}"

    @property
    def sensitivity_analyzer_endpoint(self) -> Optional[str]:
        """Get sensitivity analyzer endpoint name."""
        endpoint = os.getenv("SENSITIVITY_ANALYZER_ENDPOINT")
        if endpoint:
            return endpoint

        base_endpoint = os.getenv("SAGEMAKER_ENDPOINT_NAME", "haven-health-ml-endpoint")
        return f"{base_endpoint}-sensitivity-{self.environment}"

    @property
    def model_bucket(self) -> str:
        """Get S3 bucket for model artifacts."""
        bucket = os.getenv("SAGEMAKER_MODEL_BUCKET")
        if bucket:
            return bucket

        # Use main S3 bucket with prefix
        return os.getenv("S3_BUCKET", "haven-health-passport-models")

    @property
    def model_prefix(self) -> str:
        """Get S3 prefix for model artifacts."""
        return f"sagemaker/models/{self.environment}"

    @property
    def training_instance_type(self) -> str:
        """Get instance type for training."""
        return os.getenv("SAGEMAKER_TRAINING_INSTANCE", "ml.p3.2xlarge")

    @property
    def inference_instance_type(self) -> str:
        """Get instance type for inference."""
        return os.getenv("SAGEMAKER_INFERENCE_INSTANCE", "ml.m5.xlarge")

    @property
    def enable_data_capture(self) -> bool:
        """Check if data capture is enabled for endpoints."""
        return os.getenv("SAGEMAKER_ENABLE_DATA_CAPTURE", "true").lower() == "true"

    @property
    def enable_model_monitoring(self) -> bool:
        """Check if model monitoring is enabled."""
        return os.getenv("SAGEMAKER_ENABLE_MONITORING", "true").lower() == "true"

    def get_endpoint_config(self, _model_type: str) -> dict:
        """Get endpoint configuration for a specific model type."""
        return {
            "instance_type": self.inference_instance_type,
            "initial_instance_count": 1,
            "variant_name": "primary",
            "data_capture_config": (
                {
                    "enable_capture": self.enable_data_capture,
                    "initial_sampling_percentage": 100,
                    "destination_s3_uri": f"s3://{self.model_bucket}/{self.model_prefix}/data-capture",
                }
                if self.enable_data_capture
                else None
            ),
        }


# Singleton instance
sagemaker_config = SageMakerConfig()
