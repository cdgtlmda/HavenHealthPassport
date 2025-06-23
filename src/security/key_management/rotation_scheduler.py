"""
Key Rotation Scheduler for Haven Health Passport.

This module handles automatic key rotation scheduling and execution.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List

import boto3
from botocore.exceptions import ClientError

from .key_manager import KeyManager, KeyStatus

logger = logging.getLogger(__name__)


class KeyRotationScheduler:
    """Manages automatic key rotation based on policies."""

    def __init__(self, key_manager: KeyManager):
        """Initialize rotation scheduler."""
        self.key_manager = key_manager
        self.eventbridge = boto3.client("events")

    def check_keys_for_rotation(self) -> List[Dict]:
        """
        Check all keys and identify those needing rotation.

        Returns:
            List of keys requiring rotation
        """
        keys_to_rotate = []

        # Scan all active keys
        table = self.key_manager.key_table
        response = table.scan(
            FilterExpression="#status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": KeyStatus.ACTIVE.value},
        )

        current_time = datetime.utcnow()

        for item in response["Items"]:
            expires_at = item.get("expires_at")
            if expires_at:
                expiry_time = datetime.fromisoformat(expires_at)

                # Rotate if within 7 days of expiry
                if expiry_time - current_time <= timedelta(days=7):
                    keys_to_rotate.append(
                        {
                            "key_id": item["key_id"],
                            "key_type": item["key_type"],
                            "expires_at": expires_at,
                        }
                    )

        logger.info("Found %d keys requiring rotation", len(keys_to_rotate))
        return keys_to_rotate

    def execute_rotations(self, keys_to_rotate: List[Dict]) -> Dict[str, str]:
        """
        Execute key rotations for identified keys.

        Args:
            keys_to_rotate: List of keys to rotate

        Returns:
            Mapping of old key IDs to new key IDs
        """
        rotation_map = {}

        for key_info in keys_to_rotate:
            try:
                old_key_id = key_info["key_id"]
                new_key_id, _ = self.key_manager.rotate_key(old_key_id)
                rotation_map[old_key_id] = new_key_id

                logger.info("Successfully rotated key %s to %s", old_key_id, new_key_id)

            except ClientError as e:
                logger.error("Failed to rotate key %s: %s", key_info["key_id"], e)

        return rotation_map

    def schedule_rotation_check(self, schedule_expression: str = "rate(1 day)") -> None:
        """
        Schedule periodic rotation checks using EventBridge.

        Args:
            schedule_expression: CloudWatch Events schedule expression
        """
        rule_name = "haven-key-rotation-check"

        # Create or update the rule
        self.eventbridge.put_rule(
            Name=rule_name,
            ScheduleExpression=schedule_expression,
            State="ENABLED",
            Description="Periodic key rotation check for Haven Health Passport",
        )
