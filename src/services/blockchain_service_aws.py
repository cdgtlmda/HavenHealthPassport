"""AWS Managed Blockchain service for health record verification and integrity.

Provides blockchain validation for FHIR Resource integrity.
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from src.config import get_settings
from src.services.base import BaseService
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class AWSBlockchainService(BaseService):
    """Service for blockchain operations using AWS Managed Blockchain."""

    def __init__(self) -> None:
        """Initialize AWS blockchain service with Managed Blockchain connection."""
        # Initialize BaseService without session for blockchain service
        super().__init__(session=None)  # type: ignore[arg-type]

        # AWS configuration
        self.region = settings.AWS_REGION or "us-east-1"
        self.network_id = settings.MANAGED_BLOCKCHAIN_NETWORK_ID
        self.member_id = settings.MANAGED_BLOCKCHAIN_MEMBER_ID

        # Initialize AWS clients
        self.blockchain_client = boto3.client(
            "managedblockchain", region_name=self.region
        )
        self.lambda_client = boto3.client("lambda", region_name=self.region)

        # Channel and chaincode configuration
        self.channel_name = settings.BLOCKCHAIN_CHANNEL or "healthcare-channel"
        self.chaincode_name = settings.BLOCKCHAIN_CHAINCODE or "health-records"
        self.org_name = settings.BLOCKCHAIN_ORG or "HavenHealthOrg"

        # Verify connection
        self._verify_network_connection()

    def _verify_network_connection(self) -> None:
        """Verify connection to AWS Managed Blockchain network."""
        try:
            # Check if network exists and is available
            response = self.blockchain_client.get_network(NetworkId=self.network_id)
            network_status = response["Network"]["Status"]

            if network_status != "AVAILABLE":
                logger.error(
                    f"Blockchain network is not available. Status: {network_status}"
                )
                return

            # Check member status
            member_response = self.blockchain_client.get_member(
                NetworkId=self.network_id, MemberId=self.member_id
            )
            member_status = member_response["Member"]["Status"]

            if member_status != "AVAILABLE":
                logger.error(
                    f"Blockchain member is not available. Status: {member_status}"
                )
                return

            logger.info(
                f"Successfully connected to AWS Managed Blockchain network {self.network_id}"
            )

        except ClientError as e:
            logger.error(f"Failed to verify AWS blockchain connection: {e}")
            # Don't raise - allow fallback to ensure system remains operational

    def _invoke_chaincode(
        self,
        function_name: str,
        args: List[str],
        transient: Optional[Dict[Any, Any]] = None,
    ) -> Dict[str, Any]:
        """Invoke chaincode via AWS Lambda function."""
        try:
            # Prepare the payload for Lambda function
            payload: Dict[str, Any] = {
                "networkId": self.network_id,
                "memberId": self.member_id,
                "channel": self.channel_name,
                "chaincode": self.chaincode_name,
                "function": function_name,
                "args": args,
            }

            if transient is not None:
                payload["transient"] = transient

            # Invoke Lambda function that handles chaincode invocation
            lambda_function_name = f"haven-health-blockchain-{function_name}"

            response = self.lambda_client.invoke(
                FunctionName=lambda_function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload),
            )

            # Parse response
            result = json.loads(response["Payload"].read())

            if response["StatusCode"] == 200:
                return result if isinstance(result, dict) else {}
            else:
                logger.error(f"Chaincode invocation failed: {result}")
                return {}

        except (ClientError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error invoking chaincode: {e}")
            return {}

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
        except (TypeError, AttributeError) as e:
            logger.error(f"Error creating record hash: {e}")
            raise

    def verify_record(
        self, record_id: UUID, verification_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Verify a health record on the blockchain using AWS Managed Blockchain."""
        try:
            # Create hash of the verification data
            verification_hash = self.create_record_hash(verification_data)

            # Query blockchain for existing record
            result = self._invoke_chaincode("queryHealthRecord", [str(record_id)])

            if not result or result.get("error"):
                logger.error("Blockchain service temporarily unavailable")
                return {
                    "verified": False,
                    "error": "Blockchain service temporarily unavailable",
                    "status": "failed",
                    "fallback_mode": True,
                }

            if result.get("data"):
                blockchain_record = result["data"]
                stored_hash = blockchain_record.get("hash")

                # Verify hash matches
                is_verified = stored_hash == verification_hash

                # Record verification attempt on blockchain
                verification_result = self._invoke_chaincode(
                    "recordVerification",
                    [
                        str(record_id),
                        verification_hash,
                        str(self.current_user_id),
                        "verified" if is_verified else "failed",
                        json.dumps(
                            {
                                "timestamp": datetime.utcnow().isoformat(),
                                "verifier_org": self.org_name,
                                "verification_type": "health_record",
                                "patient_consent": verification_data.get(
                                    "patient_consent", False
                                ),
                            }
                        ),
                    ],
                )

                tx_id = verification_result.get("transactionId", "unknown")

                return {
                    "verified": is_verified,
                    "verification_hash": verification_hash,
                    "stored_hash": stored_hash,
                    "verification_timestamp": datetime.utcnow().isoformat(),
                    "verifier_id": str(self.current_user_id),
                    "blockchain_tx_id": tx_id,
                    "status": "verified" if is_verified else "hash_mismatch",
                    "blockchain_network": f"aws-{self.network_id}",
                }
            else:
                # Record not found on blockchain
                return {
                    "verified": False,
                    "error": "Record not found on blockchain",
                    "status": "not_found",
                    "verification_hash": verification_hash,
                }

        except (ClientError, json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.error(f"Error verifying record {record_id}: {e}")
            return {"verified": False, "error": str(e), "status": "failed"}

    def store_verification(
        self,
        record_id: UUID,
        verification_hash: str,
        record_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Store verification hash on blockchain using AWS Managed Blockchain."""
        try:
            # Prepare blockchain data
            blockchain_data = {
                "recordId": str(record_id),
                "hash": verification_hash,
                "timestamp": datetime.utcnow().isoformat(),
                "verifierOrg": self.org_name,
                "recordType": (
                    record_data.get("type", "health_record")
                    if record_data
                    else "health_record"
                ),
                "patientId": (
                    str(record_data.get("patient_id"))
                    if record_data and "patient_id" in record_data
                    else ""
                ),
                "metadata": {
                    "version": record_data.get("version", 1) if record_data else 1,
                    "encrypted": True,
                    "compressionType": "none",
                    "recordCategory": (
                        record_data.get("category", "general")
                        if record_data
                        else "general"
                    ),
                },
            }

            # Submit transaction to blockchain
            result = self._invoke_chaincode(
                "createHealthRecord", [json.dumps(blockchain_data)]
            )

            if not result or result.get("error"):
                logger.error(f"Failed to store verification on blockchain: {result}")
                return None

            tx_id = result.get("transactionId", "unknown")

            logger.info(
                "Successfully stored verification hash %s for record %s with tx_id %s",
                verification_hash,
                str(record_id),
                tx_id,
            )

            # Store cross-reference in local database for quick lookup
            self._store_blockchain_reference(record_id, tx_id, verification_hash)

            return tx_id  # type: ignore[no-any-return]

        except (ClientError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error storing verification on blockchain: {e}")
            return None

    def _store_blockchain_reference(
        self, record_id: UUID, tx_id: str, hash_value: str
    ) -> None:
        """Store blockchain reference in local database for performance."""
        try:
            from src.core.database import (  # pylint: disable=import-outside-toplevel
                get_db,
            )
            from src.models.blockchain import (  # pylint: disable=import-outside-toplevel
                BlockchainReference,
            )

            with get_db() as db:
                ref = BlockchainReference(
                    record_id=record_id,
                    transaction_id=tx_id,
                    hash_value=hash_value,
                    blockchain_network=f"aws-{self.network_id}",
                    created_at=datetime.utcnow(),
                )
                db.add(ref)
                db.commit()
        except (ImportError, AttributeError) as e:
            logger.warning(f"Failed to store blockchain reference locally: {e}")

    def get_verification_history(self, record_id: UUID) -> List[Dict[str, Any]]:
        """Get verification history from blockchain."""
        try:
            # Query blockchain for verification history
            result = self._invoke_chaincode("getVerificationHistory", [str(record_id)])

            if not result or result.get("error"):
                logger.error("Blockchain connection not available")
                return self._get_cached_verification_history(record_id)

            history_data = result.get("data", [])

            # Format history entries
            formatted_history = []
            for entry in history_data:
                formatted_entry = {
                    "tx_id": entry.get("transactionId"),
                    "timestamp": entry.get("timestamp"),
                    "verifier": entry.get("verifierId"),
                    "verifier_org": entry.get("verifierOrg"),
                    "status": entry.get("status"),
                    "hash": entry.get("hash"),
                    "verification_type": entry.get("verificationType", "health_record"),
                    "metadata": entry.get("metadata", {}),
                }
                formatted_history.append(formatted_entry)

            # Sort by timestamp (most recent first)
            formatted_history.sort(key=lambda x: x["timestamp"], reverse=True)

            return formatted_history

        except (ClientError, json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Error getting verification history from blockchain: {e}")
            # Try to get from local cache if blockchain is unavailable
            return self._get_cached_verification_history(record_id)

    def _get_cached_verification_history(self, record_id: UUID) -> List[Dict[str, Any]]:
        """Get verification history from local cache as fallback."""
        try:
            from src.core.database import (  # pylint: disable=import-outside-toplevel
                get_db,
            )
            from src.models.blockchain import (  # pylint: disable=import-outside-toplevel
                BlockchainReference,
            )

            with get_db() as db:
                refs = (
                    db.query(BlockchainReference)
                    .filter(BlockchainReference.record_id == record_id)
                    .order_by(BlockchainReference.created_at.desc())
                    .all()
                )

                return [
                    {
                        "tx_id": ref.transaction_id,
                        "timestamp": ref.created_at.isoformat(),
                        "verifier": "cached",
                        "status": "cached_verification",
                        "hash": ref.hash_value,
                    }
                    for ref in refs
                ]
        except (ImportError, AttributeError) as e:
            logger.error(f"Error getting cached verification history: {e}")
            return []

    def create_cross_border_verification(
        self,
        patient_id: UUID,
        destination_country: str,
        health_records: List[UUID],
        purpose: str = "medical_treatment",
        duration_days: int = 90,
    ) -> Dict[str, Any]:
        """Create cross-border verification request on blockchain."""
        try:
            # Generate unique verification ID
            verification_id = f"cbv_{patient_id}_{destination_country}_{int(datetime.utcnow().timestamp())}"

            # Prepare cross-border verification data
            verification_data = {
                "verificationId": verification_id,
                "patientId": str(patient_id),
                "originCountry": settings.DEPLOYMENT_COUNTRY or "UNKNOWN",
                "destinationCountry": destination_country,
                "healthRecords": [str(record_id) for record_id in health_records],
                "purpose": purpose,
                "validFrom": datetime.utcnow().isoformat(),
                "validUntil": (
                    datetime.utcnow() + timedelta(days=duration_days)
                ).isoformat(),
                "status": "pending",
                "requestingOrg": self.org_name,
                "consentProvided": True,
                "dataMinimization": True,
                "encryptionType": "AES-256",
                "metadata": {
                    "requestTime": datetime.utcnow().isoformat(),
                    "ipfsHash": None,
                    "smartContractVersion": "1.0",
                    "complianceFramework": "GDPR_HIPAA",
                },
            }

            # Submit to blockchain
            result = self._invoke_chaincode(
                "createCrossBorderVerification", [json.dumps(verification_data)]
            )

            if not result or result.get("error"):
                raise ValueError(
                    f"Failed to create cross-border verification: {result}"
                )

            tx_id = result.get("transactionId", "unknown")

            # Create verification package for destination country
            verification_package = self._create_verification_package(
                patient_id, health_records, destination_country
            )

            # Store verification package hash on blockchain
            package_hash = self.create_record_hash(verification_package)

            # Update verification with package hash
            _ = self._invoke_chaincode(
                "updateCrossBorderVerification",
                [
                    verification_id,
                    json.dumps(
                        {"packageHash": package_hash, "status": "package_created"}
                    ),
                ],
            )

            logger.info(
                f"Created cross-border verification {verification_id} with tx_id {tx_id}"
            )

            return {
                "verification_id": verification_id,
                "patient_id": str(patient_id),
                "destination_country": destination_country,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "valid_until": (
                    datetime.utcnow() + timedelta(days=duration_days)
                ).isoformat(),
                "blockchain_tx_id": tx_id,
                "package_hash": package_hash,
                "health_records_count": len(health_records),
            }

        except (ValueError, ClientError, json.JSONDecodeError) as e:
            logger.error(f"Error creating cross-border verification: {e}")
            raise

    def _create_verification_package(
        self, patient_id: UUID, health_records: List[UUID], destination_country: str
    ) -> Dict[str, Any]:
        """Create encrypted verification package for cross-border transfer."""
        try:
            from src.core.database import (  # pylint: disable=import-outside-toplevel
                get_db,
            )
            from src.models.health_record import (  # pylint: disable=import-outside-toplevel
                HealthRecord,
            )
            from src.models.patient import (  # pylint: disable=import-outside-toplevel
                Patient,
            )
            from src.services.encryption_service import (  # pylint: disable=import-outside-toplevel
                EncryptionService,
            )

            encryption_service = EncryptionService()

            with get_db() as db:
                # Get patient data (minimal required fields only)
                patient = db.query(Patient).filter(Patient.id == patient_id).first()
                if not patient:
                    raise ValueError(f"Patient {patient_id} not found")

                # Get health records
                records = (
                    db.query(HealthRecord)
                    .filter(HealthRecord.id.in_(health_records))
                    .all()
                )

                # Create minimal data package
                package = {
                    "patient": {
                        "id": str(patient.id),
                        "birth_year": (
                            patient.date_of_birth.year
                            if patient.date_of_birth
                            else None
                        ),
                        "gender": patient.gender,
                        "blood_type": patient.blood_type,
                    },
                    "health_records": [
                        {
                            "id": str(record.id),
                            "type": record.record_type,
                            "date": (
                                record.record_date.isoformat()
                                if record.record_date
                                else None
                            ),
                            "summary": record.summary,
                            "critical_info": record.critical_info,
                        }
                        for record in records
                    ],
                    "destination_country": destination_country,
                    "created_at": datetime.utcnow().isoformat(),
                }

                # Encrypt package for destination country's health authority
                encrypted_package = encryption_service.encrypt_for_recipient(
                    json.dumps(package),
                    recipient_public_key=self._get_country_public_key(
                        destination_country
                    ),
                )

                return {
                    "encrypted_data": encrypted_package,
                    "encryption_method": "RSA-4096/AES-256",
                    "package_version": "1.0",
                }

        except (ValueError, ImportError, AttributeError) as e:
            logger.error(f"Error creating verification package: {e}")
            raise

    def _get_country_public_key(self, country_code: str) -> str:
        """Get public key for country's health authority from blockchain."""
        try:
            result = self._invoke_chaincode("getCountryPublicKey", [country_code])

            if result and result.get("data"):
                key_data = result["data"]
                public_key = key_data.get("publicKey")
                if not public_key:
                    raise ValueError(f"Public key is empty for country {country_code}")
                return str(public_key)
            else:
                raise ValueError(f"Public key not found for country {country_code}")

        except (ValueError, ClientError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error getting country public key: {e}")
            raise

    def validate_cross_border_access(
        self, verification_id: str, accessing_country: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Validate cross-border access request against blockchain verification."""
        try:
            # Query blockchain for verification
            result = self._invoke_chaincode(
                "getCrossBorderVerification", [verification_id]
            )

            if not result or not result.get("data"):
                return False, {"error": "Verification not found"}

            verification = result["data"]

            # Validate access
            current_time = datetime.utcnow()
            valid_until = datetime.fromisoformat(
                verification["validUntil"].replace("Z", "+00:00")
            )

            if current_time > valid_until:
                return False, {"error": "Verification expired"}

            if verification["destinationCountry"] != accessing_country:
                return False, {"error": "Access not authorized for this country"}

            if verification["status"] != "active":
                return False, {
                    "error": f"Verification status: {verification['status']}"
                }

            # Log access attempt on blockchain
            self._invoke_chaincode(
                "logCrossBorderAccess",
                [verification_id, accessing_country, datetime.utcnow().isoformat()],
            )

            return True, {
                "verification_id": verification_id,
                "patient_id": verification["patientId"],
                "authorized_records": verification["healthRecords"],
                "valid_until": verification["validUntil"],
                "purpose": verification["purpose"],
            }

        except (
            ValueError,
            ClientError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
        ) as e:
            logger.error(f"Error validating cross-border access: {e}")
            return False, {"error": str(e)}

    def revoke_cross_border_verification(
        self, verification_id: str, reason: str
    ) -> bool:
        """Revoke a cross-border verification."""
        try:
            # Revoke on blockchain
            result = self._invoke_chaincode(
                "revokeCrossBorderVerification",
                [verification_id, reason, datetime.utcnow().isoformat()],
            )

            if result and not result.get("error"):
                logger.info(f"Revoked cross-border verification {verification_id}")
                return True
            else:
                logger.error(f"Failed to revoke verification: {result}")
                return False

        except (ClientError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error revoking verification: {e}")
            return False
