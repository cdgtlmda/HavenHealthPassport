"""
Base memory store implementations for Haven Health Passport.

Provides DynamoDB persistence and encryption for HIPAA compliance.
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class BaseMemoryStore(ABC):
    """Abstract base class for memory storage implementations."""

    @abstractmethod
    def save(self, key: str, value: Dict[str, Any]) -> None:
        """Save memory data."""

    @abstractmethod
    def load(self, key: str) -> Optional[Dict[str, Any]]:
        """Load memory data."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete memory data."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if memory exists."""

    @abstractmethod
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all keys with optional prefix."""


class DynamoDBMemoryStore(BaseMemoryStore):
    """DynamoDB-backed memory store with automatic TTL and versioning."""

    def __init__(
        self,
        table_name: str = "haven-health-langchain-memory",
        region_name: str = "us-east-1",
        ttl_days: int = 90,
        enable_versioning: bool = True,
        max_versions: int = 10,
    ):
        """Initialize DynamoDB memory store."""
        self.table_name = table_name
        self.ttl_days = ttl_days
        self.enable_versioning = enable_versioning
        self.max_versions = max_versions

        self.dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self.table = self.dynamodb.Table(table_name)

        # Ensure table exists
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """Create table if it doesn't exist."""
        try:
            self.table.load()
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                self._create_table()

    def _create_table(self) -> None:
        """Create DynamoDB table with proper schema."""
        try:
            self.dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {"AttributeName": "memory_key", "KeyType": "HASH"},
                    {"AttributeName": "version", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "memory_key", "AttributeType": "S"},
                    {"AttributeName": "version", "AttributeType": "N"},
                    {"AttributeName": "user_id", "AttributeType": "S"},
                    {"AttributeName": "created_at", "AttributeType": "N"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "user_id_index",
                        "Keys": [
                            {"AttributeName": "user_id", "KeyType": "HASH"},
                            {"AttributeName": "created_at", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5,
                        },
                    }
                ],
                BillingMode="PAY_PER_REQUEST",
                StreamSpecification={
                    "StreamEnabled": True,
                    "StreamViewType": "NEW_AND_OLD_IMAGES",
                },
            )
            logger.info("Created DynamoDB table: %s", self.table_name)
            self.table.wait_until_exists()
        except ClientError as e:
            logger.error("Error creating table: %s", e)
            raise

    def save(self, key: str, value: Dict[str, Any]) -> None:
        """Save memory with versioning and TTL."""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        ttl = timestamp + (self.ttl_days * 24 * 60 * 60)

        item = {
            "memory_key": key,
            "version": timestamp if self.enable_versioning else 0,
            "data": json.dumps(value),
            "created_at": timestamp,
            "ttl": ttl,
            "checksum": self._calculate_checksum(value),
        }

        # Add user_id if present
        if "user_id" in value:
            item["user_id"] = value["user_id"]

        try:
            self.table.put_item(Item=item)

            # Clean up old versions
            if self.enable_versioning:
                self._cleanup_old_versions(key)

        except ClientError as e:
            logger.error("Error saving memory: %s", e)
            raise

    def load(self, key: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Load memory with optional version."""
        try:
            if version is not None:
                response = self.table.get_item(
                    Key={"memory_key": key, "version": version}
                )
            else:
                # Get latest version
                response = self.table.query(
                    KeyConditionExpression=Key("memory_key").eq(key),
                    ScanIndexForward=False,
                    Limit=1,
                )
                if response["Items"]:
                    item = response["Items"][0]
                    return cast(Dict[str, Any], json.loads(item["data"]))
                return None

            if "Item" in response:
                data = json.loads(response["Item"]["data"])
                # Verify checksum
                if self._calculate_checksum(data) != response["Item"]["checksum"]:
                    logger.warning("Checksum mismatch for key: %s", key)
                return cast(dict[str, Any], data)
            return None

        except ClientError as e:
            logger.error("Error loading memory: %s", e)
            return None

    def delete(self, key: str) -> None:
        """Delete all versions of a memory key."""
        try:
            # Query all versions
            response = self.table.query(
                KeyConditionExpression=Key("memory_key").eq(key)
            )

            # Delete each version
            with self.table.batch_writer() as batch:
                for item in response["Items"]:
                    batch.delete_item(
                        Key={"memory_key": key, "version": item["version"]}
                    )
        except ClientError as e:
            logger.error("Error deleting memory: %s", e)
            raise

    def exists(self, key: str) -> bool:
        """Check if memory key exists."""
        try:
            response = self.table.query(
                KeyConditionExpression=Key("memory_key").eq(key), Limit=1
            )
            return len(response["Items"]) > 0
        except ClientError as e:
            logger.error("Error checking existence: %s", e)
            return False

    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all unique memory keys."""
        keys = set()
        try:
            scan_kwargs = {}
            if prefix:
                scan_kwargs["FilterExpression"] = Key("memory_key").begins_with(prefix)

            response = self.table.scan(**scan_kwargs)
            for item in response["Items"]:
                keys.add(item["memory_key"])

            # Handle pagination
            while "LastEvaluatedKey" in response:
                scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                response = self.table.scan(**scan_kwargs)
                for item in response["Items"]:
                    keys.add(item["memory_key"])

            return sorted(list(keys))

        except ClientError as e:
            logger.error("Error listing keys: %s", e)
            return []

    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate SHA-256 checksum of data."""
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def _cleanup_old_versions(self, key: str) -> None:
        """Remove old versions beyond max_versions limit."""
        try:
            response = self.table.query(
                KeyConditionExpression=Key("memory_key").eq(key),
                ScanIndexForward=False,
                ProjectionExpression="version",
            )

            versions = [item["version"] for item in response["Items"]]

            if len(versions) > self.max_versions:
                # Delete old versions
                versions_to_delete = versions[self.max_versions :]
                with self.table.batch_writer() as batch:
                    for version in versions_to_delete:
                        batch.delete_item(Key={"memory_key": key, "version": version})

        except ClientError as e:
            logger.error("Error cleaning up versions: %s", e)


class EncryptedMemoryStore(BaseMemoryStore):
    """Encrypted memory store wrapper for HIPAA compliance."""

    def __init__(
        self, base_store: BaseMemoryStore, encryption_key: Optional[bytes] = None
    ):
        """Initialize with base store and encryption."""
        self.base_store = base_store

        if encryption_key:
            self.fernet = Fernet(encryption_key)
        else:
            # Generate new key if not provided
            self.fernet = Fernet(Fernet.generate_key())
            logger.warning("Generated new encryption key - save for future use")

    def save(self, key: str, value: Dict[str, Any]) -> None:
        """Save encrypted memory."""
        # Encrypt the data
        json_data = json.dumps(value)
        encrypted_data = self.fernet.encrypt(json_data.encode()).decode()

        # Save encrypted wrapper
        encrypted_value = {
            "encrypted": True,
            "data": encrypted_data,
            "algorithm": "Fernet",
        }
        self.base_store.save(key, encrypted_value)

    def load(self, key: str) -> Optional[Dict[str, Any]]:
        """Load and decrypt memory."""
        encrypted_value = self.base_store.load(key)

        if not encrypted_value:
            return None

        if encrypted_value.get("encrypted") and encrypted_value.get("data"):
            try:
                # Decrypt the data
                decrypted_data = self.fernet.decrypt(
                    encrypted_value["data"].encode()
                ).decode()
                return cast(Dict[str, Any], json.loads(decrypted_data))
            except (ValueError, KeyError, AttributeError) as e:
                logger.error("Error decrypting memory: %s", e)
                return None
        else:
            # Not encrypted, return as-is
            return encrypted_value

    def delete(self, key: str) -> None:
        """Delete encrypted memory."""
        self.base_store.delete(key)

    def exists(self, key: str) -> bool:
        """Check if encrypted memory exists."""
        return self.base_store.exists(key)

    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List encrypted memory keys."""
        return self.base_store.list_keys(prefix)
