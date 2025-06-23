"""Hyperledger Fabric integration for verification anchoring.

This module handles encrypted PHI data for blockchain verification
with proper access control and audit logging.
"""

import hashlib
import json
import os
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from hfc.fabric import Client as FabricClient
except ImportError:
    FabricClient = None  # Handle missing dependency

from src.healthcare.fhir_validator import FHIRValidator
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class FHIRResourceType(str, Enum):
    """FHIR resource types for blockchain verification."""

    PATIENT = "Patient"
    PRACTITIONER = "Practitioner"
    ORGANIZATION = "Organization"
    CONSENT = "Consent"
    VERIFICATION_RESULT = "VerificationResult"
    DOCUMENT_REFERENCE = "DocumentReference"
    AUDIT_EVENT = "AuditEvent"


class HyperledgerFabricClient:
    """Client for interacting with Hyperledger Fabric blockchain."""

    def __init__(self) -> None:
        """Initialize Hyperledger Fabric client."""
        if FabricClient is None:
            raise ImportError(
                "hfc.fabric module is not available. Please install the required dependencies."
            )

        self.network_config_path = os.getenv(
            "FABRIC_NETWORK_CONFIG", "/etc/hyperledger/fabric/network-config.yaml"
        )
        self.channel_name = os.getenv("FABRIC_CHANNEL", "healthchannel")
        self.chaincode_name = os.getenv("FABRIC_CHAINCODE", "verificationcc")

        # Initialize Fabric client
        self.fabric_client = FabricClient(net_profile=self.network_config_path)

        # Set up organizations
        self.org_name = os.getenv("FABRIC_ORG", "RefugeeHealthOrg")
        self.peer_name = os.getenv("FABRIC_PEER", "peer0.refugeehealth.org")
        self.orderer_name = os.getenv("FABRIC_ORDERER", "orderer.refugeehealth.org")

        # Set up user context
        self.user_name = os.getenv("FABRIC_USER", "Admin")
        self.user_cert_path = os.getenv("FABRIC_USER_CERT")
        self.user_key_path = os.getenv("FABRIC_USER_KEY")

        # KMS configuration
        self.kms_key_id = os.getenv("KMS_KEY_ID", "alias/haven-health-key")
        self.region = os.getenv("AWS_REGION", "us-east-1")

        # Initialize FHIR validator
        self.fhir_validator = FHIRValidator()

        # Initialize connection
        self._setup_connection()

    def _setup_connection(self) -> None:
        """Set up connection to Fabric network."""
        self._encryption_service = EncryptionService(self.kms_key_id, self.region)
        try:
            # Get organization
            self.org = self.fabric_client.get_organization(self.org_name)

            # Get user credentials
            self.user = self.fabric_client.get_user(
                org_name=self.org_name, name=self.user_name
            )

            # Get channel
            self.channel = self.fabric_client.new_channel(self.channel_name)

            logger.info(f"Connected to Fabric network: {self.org_name}")

        except (AttributeError, KeyError, ValueError) as e:
            logger.error(f"Failed to setup Fabric connection: {e}")
            raise

    def create_verification_hash(
        self,
        verification_data: Dict[str, Any],
    ) -> str:
        """Create hash for verification data.

        Args:
            verification_data: Verification data to hash

        Returns:
            SHA256 hash of data
        """
        # Remove sensitive data before hashing
        hash_data = {
            "patient_id": verification_data.get("patient_id"),
            "verification_type": verification_data.get("verification_type"),
            "verification_method": verification_data.get("verification_method"),
            "verifier_id": verification_data.get("verifier_id"),
            "verifier_organization": verification_data.get("verifier_organization"),
            "verification_date": verification_data.get("verification_date"),
            "verification_level": verification_data.get("verification_level"),
            "expires_at": verification_data.get("expires_at"),
        }

        # Create deterministic JSON string
        json_str = json.dumps(hash_data, sort_keys=True)

        # Generate SHA256 hash
        return hashlib.sha256(json_str.encode()).hexdigest()

    def validate_fhir_resource(
        self, resource_type: FHIRResourceType, resource_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate FHIR resource before blockchain anchoring.

        Args:
            resource_type: FHIR resource type
            resource_data: Resource data to validate

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        return self.fhir_validator.validate_resource(resource_type.value, resource_data)

    async def anchor_verification(
        self,
        verification_id: str,
        verification_hash: str,
        verification_data: Dict[str, Any],
        fhir_resource_type: Optional[FHIRResourceType] = None,
        fhir_resource_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Anchor verification to blockchain.

        Args:
            verification_id: Unique verification ID
            verification_hash: Hash of verification data
            verification_data: Verification metadata (no PII)
            fhir_resource_type: FHIR resource type if applicable
            fhir_resource_data: FHIR resource data for validation

        Returns:
            Transaction ID or None
        """
        try:
            # Validate FHIR resource if provided
            if fhir_resource_type and fhir_resource_data:
                validation_result = self.validate_fhir_resource(
                    fhir_resource_type, fhir_resource_data
                )
                if not validation_result["valid"]:
                    logger.error(
                        f"FHIR validation failed: {validation_result['errors']}"
                    )
                    raise ValueError(
                        f"FHIR validation failed: {', '.join(validation_result['errors'])}"
                    )

            # Prepare chaincode arguments
            args = [
                verification_id,
                verification_hash,
                verification_data.get("patient_id", ""),
                verification_data.get("verification_type", ""),
                verification_data.get("verifier_organization", ""),
                str(verification_data.get("verification_date", "")),
                str(verification_data.get("expires_at", "")),
            ]

            # Add FHIR resource type if provided
            if fhir_resource_type:
                args.append(fhir_resource_type.value)

            # Invoke chaincode
            response = await self.fabric_client.chaincode_invoke(
                requestor=self.user,
                channel_name=self.channel_name,
                peers=[self.peer_name],
                fcn="createVerification",
                args=args,
                cc_name=self.chaincode_name,
                wait_for_event=True,
            )

            # Extract transaction ID
            if response and hasattr(response, "tx_id"):
                tx_id = str(response.tx_id) if response.tx_id else None
                if tx_id:
                    logger.info(
                        f"Anchored verification {verification_id} with tx: {tx_id}"
                    )
                return tx_id

            return None

        except (AttributeError, KeyError, ValueError) as e:
            logger.error(f"Failed to anchor verification: {e}")
            return None

    async def query_verification(
        self,
        verification_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Query verification from blockchain.

        Args:
            verification_id: Verification ID to query

        Returns:
            Verification data or None
        """
        try:
            # Query chaincode
            response = await self.fabric_client.chaincode_query(
                requestor=self.user,
                channel_name=self.channel_name,
                peers=[self.peer_name],
                fcn="queryVerification",
                args=[verification_id],
                cc_name=self.chaincode_name,
            )

            if response:
                # Parse response
                data = json.loads(response)
                return {
                    "verification_id": data.get("verification_id"),
                    "verification_hash": data.get("verification_hash"),
                    "patient_id": data.get("patient_id"),
                    "verification_type": data.get("verification_type"),
                    "verifier_organization": data.get("verifier_organization"),
                    "verification_date": data.get("verification_date"),
                    "expires_at": data.get("expires_at"),
                    "tx_id": data.get("tx_id"),
                    "timestamp": data.get("timestamp"),
                }

            return None

        except (AttributeError, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to query verification: {e}")
            return None

    async def revoke_verification(
        self,
        verification_id: str,
        revocation_reason: str,
        revoked_by: str,
    ) -> Optional[str]:
        """Revoke a verification on blockchain.

        Args:
            verification_id: Verification to revoke
            revocation_reason: Reason for revocation
            revoked_by: ID of user revoking

        Returns:
            Transaction ID or None
        """
        try:
            args = [
                verification_id,
                revocation_reason,
                revoked_by,
                datetime.utcnow().isoformat(),
            ]

            response = await self.fabric_client.chaincode_invoke(
                requestor=self.user,
                channel_name=self.channel_name,
                peers=[self.peer_name],
                fcn="revokeVerification",
                args=args,
                cc_name=self.chaincode_name,
                wait_for_event=True,
            )

            if response and hasattr(response, "tx_id"):
                tx_id = str(response.tx_id) if response.tx_id else None
                if tx_id:
                    logger.info(
                        f"Revoked verification {verification_id} with tx: {tx_id}"
                    )
                return tx_id

            return None

        except (AttributeError, KeyError, ValueError) as e:
            logger.error(f"Failed to revoke verification: {e}")
            return None

    async def get_verification_history(
        self,
        patient_id: str,
    ) -> List[Dict[str, Any]]:
        """Get verification history for a patient.

        Args:
            patient_id: Patient ID

        Returns:
            List of verifications
        """
        try:
            response = await self.fabric_client.chaincode_query(
                requestor=self.user,
                channel_name=self.channel_name,
                peers=[self.peer_name],
                fcn="getPatientVerifications",
                args=[patient_id],
                cc_name=self.chaincode_name,
            )

            if response:
                data = json.loads(response)
                return data if isinstance(data, list) else []

            return []

        except (AttributeError, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get verification history: {e}")
            return []
