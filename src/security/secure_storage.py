"""
Secure Data Storage Implementation using Envelope Encryption.

This module provides secure storage capabilities for sensitive data
using envelope encryption with AWS KMS.
"""

import hashlib
import json
import logging
from datetime import datetime
from json import JSONDecodeError
from typing import TYPE_CHECKING, Any, Dict, cast

from cryptography.fernet import InvalidToken

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.security.encryption import EncryptionService

from .envelope_encryption import EnvelopeEncryption

# FHIR Resource type imports
if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SecureDataStorage:
    """Provides secure storage for sensitive healthcare data using envelope encryption."""

    def __init__(self, kms_key_id: str, region: str = "us-east-1"):
        """
        Initialize secure data storage.

        Args:
            kms_key_id: KMS key ID for envelope encryption
            region: AWS region
        """
        self._encryption_service = EncryptionService(kms_key_id, region)
        self.envelope_encryption = EnvelopeEncryption(kms_key_id, region)
        self.fhir_resource_types = [
            "Patient",
            "Observation",
            "MedicationRequest",
            "Condition",
            "Procedure",
            "Encounter",
        ]

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("store_patient_data")
    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("store_patient_data")
    def store_patient_data(
        self, patient_id: str, data: Dict[str, Any], data_type: str
    ) -> Dict[str, Any]:
        """
        Securely store patient data with envelope encryption.

        Args:
            patient_id: Unique patient identifier
            data: Patient data to encrypt
            data_type: Type of data (e.g., 'medical_record', 'test_result')

        Returns:
            Encrypted data envelope with metadata
        """
        # Create encryption context for audit trail
        encryption_context = {
            "patient_id": patient_id,
            "data_type": data_type,
        }
        # Serialize the data
        serialized_data = json.dumps(data, default=str)

        # Encrypt the data
        encrypted_envelope = self.envelope_encryption.encrypt_string(
            serialized_data, encryption_context
        )

        # Add metadata
        encrypted_envelope["metadata"] = {
            "patient_id": patient_id,
            "data_type": data_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data_hash": hashlib.sha256(serialized_data.encode()).hexdigest(),
        }

        logger.info("Encrypted data for patient %s, type: %s", patient_id, data_type)

        return encrypted_envelope

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("retrieve_patient_data")
    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("retrieve_patient_data")
    def retrieve_patient_data(
        self, encrypted_envelope: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Retrieve and decrypt patient data.

        Args:
            encrypted_envelope: The encrypted data envelope

        Returns:
            Decrypted patient data
        """
        try:
            # Decrypt the data
            decrypted_json = self.envelope_encryption.decrypt_string(encrypted_envelope)

            # Parse the JSON
            data = json.loads(decrypted_json)
            data_typed: Dict[str, Any] = data

            # Verify data integrity
            data_hash = hashlib.sha256(decrypted_json.encode()).hexdigest()
            stored_hash = encrypted_envelope["metadata"].get("data_hash")

            if data_hash != stored_hash:
                raise ValueError("Data integrity check failed")

            logger.info(
                "Successfully decrypted data for patient %s",
                encrypted_envelope["metadata"]["patient_id"],
            )

            return data_typed

        except (
            AttributeError,
            InvalidToken,
            JSONDecodeError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as e:
            logger.error("Failed to retrieve patient data: %s", e)
            raise

    def validate_fhir_resource(self, resource_data: Dict[str, Any]) -> bool:
        """
        Validate FHIR resource structure before storage.

        Args:
            resource_data: FHIR resource data as dictionary

        Returns:
            Boolean indicating if resource is valid
        """
        # Check if resourceType is present
        if "resourceType" not in resource_data:
            logger.error("Missing resourceType in FHIR resource")
            return False

        resource_type = resource_data["resourceType"]

        # Check if it's a known FHIR resource type
        if resource_type not in self.fhir_resource_types:
            logger.error("Unknown FHIR resource type: %s", resource_type)
            return False

        # Basic validation based on resource type
        if resource_type == "Patient":
            # Patient must have at least identifier or name
            if not ("identifier" in resource_data or "name" in resource_data):
                logger.error("Patient resource must have identifier or name")
                return False

        elif resource_type == "Observation":
            # Observation must have status, code, and subject
            required_fields = ["status", "code", "subject"]
            for field in required_fields:
                if field not in resource_data:
                    logger.error(
                        "Observation resource missing required field: %s", field
                    )
                    return False

        elif resource_type == "MedicationRequest":
            # MedicationRequest must have status, intent, medication, and subject
            required_fields = [
                "status",
                "intent",
                "medicationCodeableConcept",
                "subject",
            ]
            for field in required_fields:
                if field not in resource_data:
                    logger.error(
                        "MedicationRequest resource missing required field: %s", field
                    )
                    return False

        return True

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("store_fhir_resource")
    def store_fhir_resource(
        self, resource_data: Dict[str, Any], patient_id: str
    ) -> Dict[str, Any]:
        """
        Store a FHIR resource with validation.

        Args:
            resource_data: FHIR resource as dictionary
            patient_id: Patient identifier

        Returns:
            Encrypted envelope
        """
        # Validate FHIR resource
        if not self.validate_fhir_resource(resource_data):
            raise ValueError("Invalid FHIR resource")

        # Store with resource type as data type
        resource_type = resource_data.get("resourceType", "Unknown")
        result = self.store_patient_data(
            patient_id, resource_data, f"fhir_{resource_type}"
        )
        return cast(Dict[str, Any], result)
