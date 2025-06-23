"""
Key Management System for Haven Health Passport.

This module provides centralized key management functionality including:
- Key lifecycle management
- Key rotation
- Key versioning
- Secure key storage
- Key access auditing
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class KeyStatus(Enum):
    """Key lifecycle states."""

    ACTIVE = "active"
    ROTATING = "rotating"
    DEPRECATED = "deprecated"
    EXPIRED = "expired"
    COMPROMISED = "compromised"


class KeyType(Enum):
    """Types of encryption keys."""

    MASTER = "master"
    DATA = "data"
    SIGNING = "signing"
    TRANSPORT = "transport"


class KeyMetadata:
    """Metadata for encryption keys."""

    def __init__(
        self, key_id: str, key_type: KeyType, created_at: datetime, version: int = 1
    ):
        """Initialize key metadata."""
        self.key_id = key_id
        self.key_type = key_type
        self.created_at = created_at
        self.version = version
        self.status = KeyStatus.ACTIVE
        self.rotated_at: Optional[datetime] = None
        self.expires_at: Optional[datetime] = None
        self.usage_count = 0
        self.tags: Dict[str, str] = {}


class KeyManager:
    """
    Centralized key management system.

    Handles key lifecycle, rotation, and secure storage.
    """

    def __init__(self, region: str = "us-east-1"):
        """Initialize key manager."""
        self.kms_client = boto3.client("kms", region_name=region)
        self.secrets_client = boto3.client("secretsmanager", region_name=region)
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.key_table = self._get_or_create_key_table()

    def _get_or_create_key_table(self) -> Any:
        """Get or create DynamoDB table for key metadata."""
        table_name = "haven-key-metadata"

        try:
            table = self.dynamodb.Table(table_name)
            table.load()
            return table
        except ClientError:
            # Create table if it doesn't exist
            table = self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {"AttributeName": "key_id", "KeyType": "HASH"},
                    {"AttributeName": "version", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "key_id", "AttributeType": "S"},
                    {"AttributeName": "version", "AttributeType": "N"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            table.wait_until_exists()
            return table

    def create_key(
        self, key_purpose: str, key_type: KeyType, rotation_days: int = 90
    ) -> Tuple[str, KeyMetadata]:
        """
        Create a new encryption key.

        Args:
            key_purpose: Purpose/description of the key
            key_type: Type of key to create
            rotation_days: Days until key rotation

        Returns:
            Tuple of (key_id, metadata)
        """
        try:
            # Create KMS key
            response = self.kms_client.create_key(
                Description=f"Haven Health Passport - {key_purpose}",
                KeyUsage="ENCRYPT_DECRYPT",
                Origin="AWS_KMS",
                MultiRegion=False,
            )

            key_id = response["KeyMetadata"]["KeyId"]
            key_arn = response["KeyMetadata"]["Arn"]

            # Create key alias
            alias_name = f"alias/haven-{key_type.value}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            self.kms_client.create_alias(AliasName=alias_name, TargetKeyId=key_id)

            # Enable automatic rotation
            self.kms_client.enable_key_rotation(KeyId=key_id)

            # Create metadata
            metadata = KeyMetadata(
                key_id=key_id, key_type=key_type, created_at=datetime.utcnow()
            )
            if metadata.expires_at is None:
                metadata.expires_at = metadata.created_at + timedelta(
                    days=rotation_days
                )

            # Store metadata
            self._store_key_metadata(metadata, key_arn, alias_name, key_purpose)

            logger.info("Created key %s for %s", key_id, key_purpose)
            return key_id, metadata

        except ClientError as e:
            logger.error("Error creating key: %s", e)
            raise

    def _store_key_metadata(
        self, metadata: KeyMetadata, key_arn: str, alias_name: str, purpose: str
    ) -> None:
        """Store key metadata in DynamoDB."""
        self.key_table.put_item(
            Item={
                "key_id": metadata.key_id,
                "version": metadata.version,
                "key_arn": key_arn,
                "alias_name": alias_name,
                "key_type": metadata.key_type.value,
                "status": metadata.status.value,
                "purpose": purpose,
                "created_at": metadata.created_at.isoformat(),
                "expires_at": (
                    metadata.expires_at.isoformat() if metadata.expires_at else None
                ),
                "usage_count": 0,
            }
        )

    def rotate_key(self, key_id: str) -> Tuple[str, KeyMetadata]:
        """
        Rotate an existing key.

        Args:
            key_id: ID of the key to rotate

        Returns:
            Tuple of (new_key_id, new_metadata)
        """
        try:
            # Get current key metadata
            current_metadata = self._get_key_metadata(key_id)

            if current_metadata.status != KeyStatus.ACTIVE:
                raise ValueError(
                    f"Cannot rotate key in {current_metadata.status} status"
                )

            # Update current key status
            current_metadata.status = KeyStatus.ROTATING
            self._update_key_status(
                key_id, current_metadata.version, KeyStatus.ROTATING
            )

            # Create new key
            purpose = self._get_key_purpose(key_id)
            new_key_id, new_metadata = self.create_key(
                key_purpose=f"{purpose} (Rotation)", key_type=current_metadata.key_type
            )
            new_metadata.version = current_metadata.version + 1
            # Schedule old key deprecation
            self._schedule_key_deprecation(key_id, days=30)

            logger.info("Rotated key %s to %s", key_id, new_key_id)
            return new_key_id, new_metadata

        except ClientError as e:
            logger.error(
                "AWS KMS error rotating key",
                exc_info=True,
                extra={
                    "key_id": key_id,
                    "error_code": e.response["Error"]["Code"] if e.response else None,
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            raise RuntimeError(f"Failed to rotate encryption key: {str(e)}") from e
        except (ValueError, TypeError) as e:
            logger.error(
                "Invalid key rotation parameters",
                exc_info=True,
                extra={
                    "key_id": key_id,
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                },
            )
            raise

    def _get_key_metadata(self, key_id: str) -> KeyMetadata:
        """Retrieve key metadata from DynamoDB."""
        response = self.key_table.query(
            KeyConditionExpression="key_id = :kid",
            ExpressionAttributeValues={":kid": key_id},
            ScanIndexForward=False,
            Limit=1,
        )

        if not response["Items"]:
            raise ValueError(f"Key {key_id} not found")

        item = response["Items"][0]
        metadata = KeyMetadata(
            key_id=item["key_id"],
            key_type=KeyType(item["key_type"]),
            created_at=datetime.fromisoformat(item["created_at"]),
            version=item["version"],
        )
        metadata.status = KeyStatus(item["status"])
        metadata.usage_count = item.get("usage_count", 0)

        return metadata

    def _update_key_status(self, key_id: str, version: int, status: KeyStatus) -> None:
        """Update key status in DynamoDB."""
        self.key_table.update_item(
            Key={"key_id": key_id, "version": version},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": status.value},
        )

    def get_active_key(self, key_type: KeyType, purpose: Optional[str] = None) -> str:
        """
        Get the active key for a specific type and purpose.

        Args:
            key_type: Type of key needed
            purpose: Optional purpose filter

        Returns:
            Active key ID
        """
        # Query for active keys of the specified type
        response = self.key_table.scan(
            FilterExpression="key_type = :kt AND #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":kt": key_type.value,
                ":status": KeyStatus.ACTIVE.value,
            },
        )

        if not response["Items"]:
            # Create a new key if none exists
            key_id, _ = self.create_key(
                key_purpose=purpose or f"Auto-created {key_type.value} key",
                key_type=key_type,
            )
            return key_id

        # Return the most recent active key
        items = sorted(response["Items"], key=lambda x: x["created_at"], reverse=True)
        return str(items[0]["key_id"])

    def track_key_usage(self, key_id: str) -> None:
        """Track key usage for monitoring and rotation decisions."""
        try:
            self.key_table.update_item(
                Key={"key_id": key_id, "version": 1},
                UpdateExpression="ADD usage_count :inc",
                ExpressionAttributeValues={":inc": 1},
            )
        except ClientError:
            pass  # Don't fail operations due to tracking issues

    def _get_key_purpose(self, key_id: str) -> str:
        """Get the purpose of a key from metadata."""
        _ = self._get_key_metadata(key_id)
        # Extract purpose from key metadata or return default
        return "General"

    def _schedule_key_deprecation(self, key_id: str, days: int) -> None:
        """Schedule a key for deprecation."""
        # In production, this would schedule the key for deletion
        # For now, just update the metadata
        _ = days  # Will be used in actual implementation
        try:
            metadata = self._get_key_metadata(key_id)
            metadata.status = KeyStatus.DEPRECATED
            self._update_key_status(key_id, metadata.version, KeyStatus.DEPRECATED)
        except ClientError as e:
            logger.warning("Failed to schedule key deprecation: %s", e)
