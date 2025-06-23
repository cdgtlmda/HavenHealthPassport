"""Key rotation management for encryption keys."""

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, cast

import boto3
from cryptography.fernet import Fernet

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class KeyRotationManager:
    """Manage encryption key rotation."""

    def __init__(self) -> None:
        """Initialize key rotation manager."""
        settings = get_settings()
        self.rotation_interval_days = getattr(
            settings, "key_rotation_interval_days", 90
        )
        self.key_history_file = "keys/key_history.json"
        self.max_key_versions = 5

        # AWS KMS client for production key management
        if settings.environment == "production":
            self.kms_client = boto3.client(
                "kms",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
            self.kms_key_id = getattr(settings, "kms_master_key_id", None)
        else:
            self.kms_client = None
            self.kms_key_id = None

    def should_rotate_key(self) -> bool:
        """Check if key rotation is needed."""
        history = self._load_key_history()

        if not history:
            return True

        latest_key = history[-1]
        created_at = datetime.fromisoformat(latest_key["created_at"])
        rotation_due = created_at + timedelta(days=self.rotation_interval_days)

        return datetime.now() >= rotation_due

    def rotate_key(self) -> Tuple[str, str]:
        """
        Rotate encryption key.

        Returns:
            Tuple of (new_key_id, new_key)
        """
        # Generate new key
        new_key = Fernet.generate_key().decode()
        new_key_id = f"key-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Store in KMS if production
        if self.kms_client and self.kms_key_id:
            encrypted_key = self._encrypt_with_kms(new_key)
        else:
            encrypted_key = new_key  # For development, store as-is

        # Update key history
        history = self._load_key_history()
        history.append(
            {
                "key_id": new_key_id,
                "encrypted_key": encrypted_key,
                "created_at": datetime.now().isoformat(),
                "status": "active",
            }
        )

        # Mark previous key as rotated
        if len(history) > 1:
            history[-2]["status"] = "rotated"
            history[-2]["rotated_at"] = datetime.now().isoformat()

        # Keep only max versions
        if len(history) > self.max_key_versions:
            # Keep at least 2 keys for decryption of old data
            keys_to_remove = len(history) - self.max_key_versions
            for i in range(keys_to_remove):
                if history[i]["status"] != "active":
                    history[i]["status"] = "archived"

        self._save_key_history(history)

        logger.info(f"Key rotated successfully. New key ID: {new_key_id}")

        return new_key_id, new_key

    def get_active_key(self) -> Tuple[str, str]:
        """Get the currently active encryption key."""
        history = self._load_key_history()

        if not history:
            # No keys exist, create first one
            return self.rotate_key()

        # Find active key
        for key_entry in reversed(history):
            if key_entry["status"] == "active":
                key_id = key_entry["key_id"]
                encrypted_key = key_entry["encrypted_key"]

                # Decrypt key if using KMS
                if self.kms_client and self.kms_key_id:
                    key = self._decrypt_with_kms(encrypted_key)
                else:
                    key = encrypted_key

                return key_id, key

        # No active key found, rotate
        return self.rotate_key()

    def get_key_by_id(self, key_id: str) -> Optional[str]:
        """Get a specific key by ID for decryption."""
        history = self._load_key_history()

        for key_entry in history:
            if key_entry["key_id"] == key_id:
                encrypted_key = key_entry["encrypted_key"]

                # Decrypt key if using KMS
                if self.kms_client and self.kms_key_id:
                    return self._decrypt_with_kms(encrypted_key)
                else:
                    return str(encrypted_key)

        return None

    def _encrypt_with_kms(self, plaintext: str) -> str:
        """Encrypt data using AWS KMS."""
        response = self.kms_client.encrypt(
            KeyId=self.kms_key_id, Plaintext=plaintext.encode()
        )
        return str(response["CiphertextBlob"].hex())

    def _decrypt_with_kms(self, ciphertext_hex: str) -> str:
        """Decrypt data using AWS KMS."""
        ciphertext = bytes.fromhex(ciphertext_hex)
        response = self.kms_client.decrypt(CiphertextBlob=ciphertext)
        return str(response["Plaintext"].decode())

    def _load_key_history(self) -> List[Dict[Any, Any]]:
        """Load key history from file."""
        os.makedirs(os.path.dirname(self.key_history_file), exist_ok=True)

        if os.path.exists(self.key_history_file):
            with open(self.key_history_file, "r", encoding="utf-8") as f:
                return cast(List[Dict[Any, Any]], json.load(f))
        return []

    def _save_key_history(self, history: List[Dict]) -> None:
        """Save key history to file."""
        os.makedirs(os.path.dirname(self.key_history_file), exist_ok=True)

        with open(self.key_history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

    def cleanup_old_keys(self) -> None:
        """Clean up archived keys that are no longer needed."""
        history = self._load_key_history()
        updated_history = []

        for key_entry in history:
            if key_entry["status"] == "archived":
                # Check if any data still uses this key
                # In production, this would query the database
                if self._is_key_still_in_use(key_entry["key_id"]):
                    updated_history.append(key_entry)
                else:
                    logger.info(f"Removing archived key: {key_entry['key_id']}")
            else:
                updated_history.append(key_entry)

        self._save_key_history(updated_history)

    def _is_key_still_in_use(self, key_id: str) -> bool:
        """Check if any encrypted data still uses this key."""
        # Placeholder - in production this would check database
        # for any records encrypted with this key_id
        # For now, log the key_id being checked
        logger.debug(f"Checking if key {key_id} is still in use")
        return False

    def get_rotation_schedule(self) -> Dict[str, Any]:
        """Get key rotation schedule information."""
        history = self._load_key_history()

        if not history:
            return {
                "next_rotation": datetime.now().isoformat(),
                "rotation_interval_days": self.rotation_interval_days,
                "active_keys": 0,
            }

        active_key = None
        for key_entry in reversed(history):
            if key_entry["status"] == "active":
                active_key = key_entry
                break

        if active_key:
            created_at = datetime.fromisoformat(active_key["created_at"])
            next_rotation = created_at + timedelta(days=self.rotation_interval_days)
        else:
            next_rotation = datetime.now()

        return {
            "next_rotation": next_rotation.isoformat(),
            "rotation_interval_days": self.rotation_interval_days,
            "active_keys": len([k for k in history if k["status"] == "active"]),
            "total_keys": len(history),
        }


# Scheduled task for automatic key rotation
async def auto_rotate_keys() -> None:
    """Automatically rotate keys when needed."""
    manager = KeyRotationManager()

    if manager.should_rotate_key():
        logger.info("Starting automatic key rotation")
        key_id, _ = manager.rotate_key()

        # Update application configuration with new key
        # This would typically update environment variables or secrets manager
        logger.info(f"Key rotation completed. New key ID: {key_id}")

        # Clean up old archived keys
        manager.cleanup_old_keys()
