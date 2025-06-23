"""AWS Bedrock Client for Haven Health Passport.

This module provides a client interface for AWS Bedrock services.
"""

import logging
from typing import Any, Dict, cast

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class BedrockClient:
    """Client for interacting with AWS Bedrock services."""

    def __init__(self, region_name: str = "us-east-1"):
        """Initialize Bedrock client.

        Args:
            region_name: AWS region name
        """
        self.region_name = region_name
        self.client = boto3.client("bedrock-runtime", region_name=region_name)
        self.model_client = boto3.client("bedrock", region_name=region_name)

    def invoke_model(
        self,
        model_id: str,
        body: Dict[str, Any],
        content_type: str = "application/json",
        accept: str = "application/json",
    ) -> Dict[str, Any]:
        """Invoke a Bedrock model.

        Args:
            model_id: The model identifier
            body: The request body
            content_type: Content type for the request
            accept: Accept header for the response

        Returns:
            Model response
        """
        try:
            response = self.client.invoke_model(
                modelId=model_id, body=body, contentType=content_type, accept=accept
            )
            return cast(Dict[str, Any], response)
        except ClientError as e:
            logger.error("Error invoking model %s: %s", model_id, e)
            raise

    def list_foundation_models(self) -> Dict[str, Any]:
        """List available foundation models.

        Returns:
            List of available models
        """
        try:
            response = self.model_client.list_foundation_models()
            return cast(Dict[str, Any], response)
        except ClientError as e:
            logger.error("Error listing models: %s", e)
            raise


# Create a default client instance
default_client = BedrockClient()
