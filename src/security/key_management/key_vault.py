"""
Key Vault Integration for Haven Health Passport.

This module provides secure key storage using AWS Secrets Manager
and implements key access controls.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Tuple, cast

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class KeyVault:
    """Secure key storage using AWS Secrets Manager."""

    def __init__(self, region: str = "us-east-1"):
        """Initialize key vault."""
        self.secrets_client = boto3.client("secretsmanager", region_name=region)
        self.kms_client = boto3.client("kms", region_name=region)

    def store_key(
        self, key_name: str, key_value: Any, key_metadata: Dict, kms_key_id: str
    ) -> str:
        """
        Store a key in Secrets Manager.

        Args:
            key_name: Name/identifier for the key
            key_value: The key value to store
            key_metadata: Additional metadata about the key
            kms_key_id: KMS key to use for encryption

        Returns:
            Secret ARN
        """
        secret_name = f"haven/keys/{key_name}"

        secret_data = {
            "key": key_value,
            "metadata": key_metadata,
            "stored_at": datetime.utcnow().isoformat(),
        }
        try:
            response = self.secrets_client.create_secret(
                Name=secret_name,
                SecretString=json.dumps(secret_data),
                KmsKeyId=kms_key_id,
                Tags=[
                    {"Key": "Purpose", "Value": "key-storage"},
                    {"Key": "System", "Value": "haven-health-passport"},
                ],
            )

            logger.info("Stored key %s in vault", key_name)
            return cast(str, response["ARN"])

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceExistsException":
                # Update existing secret
                return self.update_key(key_name, key_value, key_metadata)
            else:
                logger.error("Error storing key: %s", e)
                raise

    def retrieve_key(self, key_name: str) -> Tuple[Any, Dict]:
        """
        Retrieve a key from Secrets Manager.

        Args:
            key_name: Name of the key to retrieve

        Returns:
            Tuple of (key_value, metadata)
        """
        secret_name = f"haven/keys/{key_name}"

        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_name)

            secret_data = json.loads(response["SecretString"])

            logger.info("Retrieved key %s from vault", key_name)
            return secret_data["key"], secret_data["metadata"]

        except ClientError as e:
            logger.error("Error retrieving key: %s", e)
            raise

    def update_key(self, key_name: str, key_value: Any, key_metadata: Dict) -> str:
        """
        Update an existing key in Secrets Manager.

        Args:
            key_name: Name of the key
            key_value: The key material to update
            key_metadata: Metadata about the key

        Returns:
            ARN of the updated secret
        """
        try:
            secret_name = f"haven/keys/{key_name}"

            secret_data = json.dumps(
                {
                    "key": key_value,
                    "metadata": key_metadata,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )

            response = self.secrets_client.update_secret(
                SecretId=secret_name, SecretString=secret_data
            )

            logger.info("Updated key %s in vault", key_name)
            return cast(str, response["ARN"])

        except ClientError as e:
            logger.error("Error updating key: %s", e)
            raise
