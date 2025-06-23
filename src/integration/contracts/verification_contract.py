"""Smart contract implementation for verification management.

This is a reference implementation of the chaincode that would be
deployed to Hyperledger Fabric for managing verifications.
"""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class FHIRResourceType(str, Enum):
    """FHIR resource types supported by verification contract."""

    PATIENT = "Patient"
    PRACTITIONER = "Practitioner"
    ORGANIZATION = "Organization"
    CONSENT = "Consent"
    VERIFICATION_RESULT = "VerificationResult"
    DOCUMENT_REFERENCE = "DocumentReference"


class VerificationContract:
    """Smart contract for verification management."""

    def __init__(self) -> None:
        """Initialize contract."""
        self.name = "VerificationContract"
        self.verified_documents: Dict[str, Any] = {}
        self.verification_history: List[Dict[str, Any]] = []

    def validate_fhir_resource(
        self, resource_type: str, resource_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Validate FHIR resource for verification."""
        validation_result: Dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
        }

        # Validate resource type
        try:
            fhir_type = FHIRResourceType(resource_type)
        except ValueError:
            validation_result["valid"] = False
            validation_result["errors"].append(
                f"Invalid FHIR resource type: {resource_type}"
            )
            return validation_result

        # Basic validation rules for each resource type
        if resource_data:
            if fhir_type == FHIRResourceType.PATIENT:
                if not resource_data.get("identifier"):
                    validation_result["warnings"].append(
                        "Patient should have identifier"
                    )
            elif fhir_type == FHIRResourceType.PRACTITIONER:
                if not resource_data.get("qualification"):
                    validation_result["warnings"].append(
                        "Practitioner should have qualification"
                    )
            elif fhir_type == FHIRResourceType.ORGANIZATION:
                if not resource_data.get("name"):
                    validation_result["errors"].append("Organization must have name")
                    validation_result["valid"] = False
            elif fhir_type == FHIRResourceType.CONSENT:
                if not resource_data.get("status"):
                    validation_result["errors"].append("Consent must have status")
                    validation_result["valid"] = False
            elif fhir_type == FHIRResourceType.DOCUMENT_REFERENCE:
                if not resource_data.get("status"):
                    validation_result["errors"].append(
                        "DocumentReference must have status"
                    )
                    validation_result["valid"] = False

        return validation_result

    async def create_verification(
        self,
        ctx: Any,
        verification_id: str,
        verification_hash: str,
        patient_id: str,
        verification_type: str,
        verifier_organization: str,
        verification_date: str,
        expires_at: str,
        fhir_resource_type: Optional[str] = None,
        fhir_resource_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new verification record.

        Args:
            ctx: Transaction context
            verification_id: Unique verification ID
            verification_hash: Hash of verification data
            patient_id: Patient ID (hashed)
            verification_type: Type of verification
            verifier_organization: Organization performing verification
            verification_date: Date of verification
            expires_at: Expiration date
            fhir_resource_type: FHIR resource type being verified
            fhir_resource_data: FHIR resource data for validation

        Returns:
            Success message
        """
        # Check if verification already exists
        existing = await ctx.stub.get_state(verification_id)
        if existing:
            raise ValueError(f"Verification {verification_id} already exists")

        # Validate FHIR resource type and data if provided
        if fhir_resource_type:
            validation_result = self.validate_fhir_resource(
                fhir_resource_type, fhir_resource_data
            )
            if not validation_result["valid"]:
                raise ValueError(
                    f"FHIR validation failed: {', '.join(validation_result['errors'])}"
                )

        # Create verification record
        verification = {
            "verification_id": verification_id,
            "verification_hash": verification_hash,
            "patient_id": patient_id,
            "verification_type": verification_type,
            "verifier_organization": verifier_organization,
            "verification_date": verification_date,
            "expires_at": expires_at,
            "fhir_resource_type": fhir_resource_type,
            "created_at": datetime.utcnow().isoformat(),
            "status": "active",
            "tx_id": ctx.stub.get_txid(),
            "timestamp": datetime.utcnow().isoformat(),
            "created_by": ctx.client_identity.get_id(),
        }

        # Store verification
        await ctx.stub.put_state(verification_id, json.dumps(verification).encode())

        # Create composite key for patient index
        patient_key = ctx.stub.create_composite_key(
            "patient~verification", [patient_id, verification_id]
        )
        await ctx.stub.put_state(patient_key, b"")

        # Create composite key for organization index
        org_key = ctx.stub.create_composite_key(
            "org~verification", [verifier_organization, verification_id]
        )
        await ctx.stub.put_state(org_key, b"")

        return f"Verification {verification_id} created successfully"

    async def query_verification(
        self,
        ctx: Any,
        verification_id: str,
    ) -> Dict[str, Any]:
        """Query a verification by ID.

        Args:
            ctx: Transaction context
            verification_id: Verification ID

        Returns:
            Verification data
        """
        verification_bytes = await ctx.stub.get_state(verification_id)

        if not verification_bytes:
            raise ValueError(f"Verification {verification_id} not found")

        from typing import cast

        verification_data = cast(
            Dict[str, Any], json.loads(verification_bytes.decode())
        )
        return verification_data

    async def revoke_verification(
        self,
        ctx: Any,
        verification_id: str,
        revocation_reason: str,
        revoked_by: str,
        revocation_date: str,
    ) -> str:
        """Revoke a verification.

        Args:
            ctx: Transaction context
            verification_id: Verification to revoke
            revocation_reason: Reason for revocation
            revoked_by: ID of user revoking
            revocation_date: Date of revocation

        Returns:
            Success message
        """
        # Get existing verification
        verification_bytes = await ctx.stub.get_state(verification_id)

        if not verification_bytes:
            raise ValueError(f"Verification {verification_id} not found")

        verification = json.loads(verification_bytes.decode())

        # Check if already revoked
        if verification.get("status") == "revoked":
            raise ValueError(f"Verification {verification_id} already revoked")

        # Update verification
        verification["status"] = "revoked"
        verification["revocation_reason"] = revocation_reason
        verification["revoked_by"] = revoked_by
        verification["revocation_date"] = revocation_date
        verification["revocation_tx_id"] = ctx.stub.get_txid()

        # Store updated verification
        await ctx.stub.put_state(verification_id, json.dumps(verification).encode())

        return f"Verification {verification_id} revoked successfully"

    async def get_patient_verifications(
        self,
        ctx: Any,
        patient_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all verifications for a patient.

        Args:
            ctx: Transaction context
            patient_id: Patient ID

        Returns:
            List of verifications
        """
        verifications = []

        # Query by composite key
        iterator = await ctx.stub.get_state_by_partial_composite_key(
            "patient~verification", [patient_id]
        )

        async for result in iterator:
            _, compositeKey = ctx.stub.split_composite_key(result.key)
            verification_id = compositeKey[1]

            # Get verification details
            verification_bytes = await ctx.stub.get_state(verification_id)
            if verification_bytes:
                verification = json.loads(verification_bytes.decode())
                verifications.append(verification)

        return verifications

    async def get_verifications_by_fhir_type(
        self,
        ctx: Any,
        fhir_resource_type: str,
    ) -> List[Dict[str, Any]]:
        """Get all verifications for a specific FHIR resource type.

        Args:
            ctx: Transaction context
            fhir_resource_type: FHIR resource type to filter by

        Returns:
            List of verifications for the specified FHIR resource type
        """
        # Validate FHIR resource type
        try:
            FHIRResourceType(fhir_resource_type)
        except ValueError:
            raise ValueError(f"Invalid FHIR resource type: {fhir_resource_type}")

        verifications = []

        # Query all verifications (in production, use CouchDB query)
        iterator = await ctx.stub.get_state_by_range("", "")

        async for result in iterator:
            try:
                verification = json.loads(result.value.decode())
                if verification.get("fhir_resource_type") == fhir_resource_type:
                    verifications.append(verification)
            except json.JSONDecodeError:
                continue

        return verifications

    async def validate_verification(
        self,
        ctx: Any,
        verification_id: str,
        verification_hash: str,
    ) -> bool:
        """Validate a verification hash.

        Args:
            ctx: Transaction context
            verification_id: Verification ID
            verification_hash: Hash to validate

        Returns:
            True if valid
        """
        verification = await self.query_verification(ctx, verification_id)

        # Check hash matches
        if verification.get("verification_hash") != verification_hash:
            return False

        # Check not revoked
        if verification.get("status") == "revoked":
            return False

        # Check not expired
        if verification.get("expires_at"):
            expires_at = datetime.fromisoformat(verification["expires_at"])
            if expires_at < datetime.utcnow():
                return False

        return True
