"""Mock blockchain service for testing and development."""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.services.base import BaseService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MockBlockchainService(BaseService):
    """Mock blockchain service for testing when real blockchain is not available."""

    def __init__(self, session: Optional[Session] = None) -> None:
        """Initialize mock blockchain service."""
        # Mock service doesn't need a real session
        if session:
            super().__init__(session)
        # In-memory storage for mock blockchain
        self._records: Dict[str, Any] = {}
        self._verifications: Dict[str, Any] = {}
        self._cross_border: Dict[str, Any] = {}
        self._country_keys = {
            "US": "mock_us_public_key",
            "UK": "mock_uk_public_key",
            "CA": "mock_ca_public_key",
            "AU": "mock_au_public_key",
            "EU": "mock_eu_public_key",
        }
        logger.info("Initialized mock blockchain service")

    def create_record_hash(self, record_data: Dict[str, Any]) -> str:
        """Create a SHA-256 hash of record data for blockchain storage."""
        try:
            # Remove any non-deterministic fields
            clean_data = {
                k: v
                for k, v in record_data.items()
                if k not in ["created_at", "updated_at", "id"]
            }

            # Serialize the data deterministically
            data_string = json.dumps(clean_data, sort_keys=True, default=str)
            return hashlib.sha256(data_string.encode()).hexdigest()
        except (TypeError, ValueError, AttributeError) as e:
            logger.error(f"Error creating record hash: {e}")
            raise

    def verify_record(
        self, record_id: UUID, verification_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Mock verify a health record."""
        try:
            # Create hash of the verification data
            verification_hash = self.create_record_hash(verification_data)

            # Check if record exists in mock storage
            str_record_id = str(record_id)
            if str_record_id in self._records:
                stored_hash = self._records[str_record_id]["hash"]
                is_verified = stored_hash == verification_hash

                # Store verification attempt
                tx_id = f"mock_tx_{uuid4().hex[:12]}"
                self._verifications[str_record_id] = self._verifications.get(
                    str_record_id, []
                )
                self._verifications[str_record_id].append(
                    {
                        "tx_id": tx_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "verifier_id": str(self.current_user_id),
                        "status": "verified" if is_verified else "failed",
                        "hash": verification_hash,
                    }
                )

                return {
                    "verified": is_verified,
                    "verification_hash": verification_hash,
                    "stored_hash": stored_hash,
                    "verification_timestamp": datetime.utcnow().isoformat(),
                    "verifier_id": str(self.current_user_id),
                    "blockchain_tx_id": tx_id,
                    "status": "verified" if is_verified else "hash_mismatch",
                    "blockchain_network": "mock",
                }
            else:
                return {
                    "verified": False,
                    "error": "Record not found on blockchain",
                    "status": "not_found",
                    "verification_hash": verification_hash,
                }

        except (KeyError, ValueError, AttributeError) as e:
            logger.error(f"Error verifying record {record_id}: {e}")
            return {"verified": False, "error": str(e), "status": "failed"}

    def store_verification(
        self,
        record_id: UUID,
        verification_hash: str,
        record_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Mock store verification hash."""
        try:
            tx_id = f"mock_tx_{uuid4().hex[:12]}"
            str_record_id = str(record_id)

            self._records[str_record_id] = {
                "hash": verification_hash,
                "timestamp": datetime.utcnow().isoformat(),
                "tx_id": tx_id,
                "data": record_data,  # Store optional record data
                # _ = record_data  # Mark as used
            }

            logger.info(
                f"Successfully stored verification hash {verification_hash} for record {record_id} with tx_id {tx_id}"
            )

            return tx_id

        except (KeyError, ValueError, AttributeError) as e:
            logger.error(f"Error storing verification: {e}")
            return None

    def get_verification_history(self, record_id: UUID) -> List[Dict[str, Any]]:
        """Get mock verification history."""
        try:
            str_record_id = str(record_id)
            history = self._verifications.get(str_record_id, [])

            # Sort by timestamp (most recent first)
            history.sort(key=lambda x: x["timestamp"], reverse=True)

            return [
                {
                    "tx_id": entry["tx_id"],
                    "timestamp": entry["timestamp"],
                    "verifier": entry.get("verifier_id", "mock"),
                    "verifier_org": "MockOrg",
                    "status": entry.get("status", "verified"),
                    "hash": entry.get("hash", ""),
                    "verification_type": "health_record",
                    "metadata": {},
                }
                for entry in history
            ]

        except (KeyError, ValueError, AttributeError) as e:
            logger.error(f"Error getting verification history: {e}")
            return []

    def create_cross_border_verification(
        self,
        patient_id: UUID,
        destination_country: str,
        health_records: List[UUID],
        purpose: str = "medical_treatment",
        duration_days: int = 90,
    ) -> Dict[str, Any]:
        """Mock create cross-border verification."""
        try:
            verification_id = f"cbv_{patient_id}_{destination_country}_{int(datetime.utcnow().timestamp())}"
            tx_id = f"mock_tx_{uuid4().hex[:12]}"

            verification_data = {
                "verification_id": verification_id,
                "patient_id": str(patient_id),
                "destination_country": destination_country,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "valid_until": (
                    datetime.utcnow() + timedelta(days=duration_days)
                ).isoformat(),
                "blockchain_tx_id": tx_id,
                "package_hash": hashlib.sha256(
                    f"{verification_id}{tx_id}".encode()
                ).hexdigest(),
                "health_records_count": len(health_records),
                "health_records": [str(r) for r in health_records],
                "purpose": purpose,
            }

            self._cross_border[verification_id] = verification_data

            logger.info(f"Created mock cross-border verification {verification_id}")

            return verification_data

        except (ValueError, AttributeError, TypeError) as e:
            logger.error(f"Error creating cross-border verification: {e}")
            raise

    def _create_verification_package(
        self, patient_id: UUID, health_records: List[UUID], destination_country: str
    ) -> Dict[str, Any]:
        """Mock create verification package."""
        # Mark parameters as used
        _ = patient_id
        _ = health_records
        return {
            "encrypted_data": f"mock_encrypted_data_for_{destination_country}",
            "encryption_method": "MOCK-RSA-4096/AES-256",
            "package_version": "1.0",
        }

    def _get_country_public_key(self, country_code: str) -> str:
        """Mock get country public key."""
        return self._country_keys.get(country_code, f"mock_{country_code}_public_key")

    def validate_cross_border_access(
        self, verification_id: str, accessing_country: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Mock validate cross-border access."""
        try:
            if verification_id not in self._cross_border:
                return False, {"error": "Verification not found"}

            verification = self._cross_border[verification_id]

            # Validate access
            current_time = datetime.utcnow()
            valid_until = datetime.fromisoformat(verification["valid_until"])

            if current_time > valid_until:
                return False, {"error": "Verification expired"}

            if verification["destination_country"] != accessing_country:
                return False, {"error": "Access not authorized for this country"}

            if verification["status"] != "active":
                # Auto-activate for mock
                verification["status"] = "active"

            return True, {
                "verification_id": verification_id,
                "patient_id": verification["patient_id"],
                "authorized_records": verification["health_records"],
                "valid_until": verification["valid_until"],
                "purpose": verification["purpose"],
            }

        except (KeyError, ValueError, AttributeError) as e:
            logger.error(f"Error validating cross-border access: {e}")
            return False, {"error": str(e)}

    def revoke_cross_border_verification(
        self, verification_id: str, reason: str
    ) -> bool:
        """Mock revoke cross-border verification."""
        try:
            if verification_id in self._cross_border:
                self._cross_border[verification_id]["status"] = "revoked"
                self._cross_border[verification_id][
                    "revoked_at"
                ] = datetime.utcnow().isoformat()
                self._cross_border[verification_id][
                    "revoke_reason"
                ] = reason  # Store revocation reason
                logger.info(f"Revoked mock cross-border verification {verification_id}")
                return True
            return False

        except (KeyError, ValueError, AttributeError) as e:
            logger.error(f"Error revoking verification: {e}")
            return False
