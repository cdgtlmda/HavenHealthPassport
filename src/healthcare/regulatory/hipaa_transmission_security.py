"""HIPAA Transmission Security Implementation.

This module implements HIPAA transmission security controls to protect PHI
during electronic transmission over networks.
"""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, cast

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import hipaa_access_control

logger = logging.getLogger(__name__)

# Default time window for monitoring
DEFAULT_MONITORING_WINDOW = timedelta(hours=24)


class EncryptionStandard(Enum):
    """Encryption standards for transmission security."""

    AES_256_GCM = "aes_256_gcm"
    AES_256_CBC = "aes_256_cbc"
    RSA_4096 = "rsa_4096"
    TLS_1_3 = "tls_1_3"
    TLS_1_2 = "tls_1_2"


class TransmissionProtocol(Enum):
    """Secure transmission protocols."""

    HTTPS = "https"
    SFTP = "sftp"
    SECURE_EMAIL = "secure_email"
    VPN = "vpn"
    DIRECT_MESSAGING = "direct_messaging"
    HL7_OVER_TLS = "hl7_over_tls"


class DataClassification(Enum):
    """PHI data classification levels."""

    HIGHLY_SENSITIVE = "highly_sensitive"  # SSN, financial, psych notes
    SENSITIVE = "sensitive"  # General PHI
    INTERNAL = "internal"  # De-identified data
    PUBLIC = "public"  # Non-PHI


class HIPAATransmissionSecurity:
    """Implements HIPAA transmission security controls."""

    # FHIR resource type
    __fhir_resource__ = "AuditEvent"

    def __init__(self) -> None:
        """Initialize transmission security system."""
        self.encryption_policies: Dict[str, Dict[str, Any]] = (
            self._initialize_policies()
        )
        self.transmission_log: List[Dict[str, Any]] = []
        self.keys: Dict[str, Any] = self._initialize_keys()
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.failed_transmissions: List[Dict[str, Any]] = []
        # Add FHIR validator
        self.fhir_validator = FHIRValidator()

    def _initialize_policies(self) -> Dict[str, Dict[str, Any]]:
        """Initialize transmission security policies."""
        return {
            "highly_sensitive_phi": {
                "policy_id": "TS-001",
                "classification": DataClassification.HIGHLY_SENSITIVE,
                "encryption_standard": EncryptionStandard.AES_256_GCM,
                "key_size": 256,
                "protocols": [TransmissionProtocol.HTTPS, TransmissionProtocol.VPN],
                "require_mutual_auth": True,
                "require_integrity_check": True,
                "session_timeout": 300,  # 5 minutes
                "max_retries": 3,
            },
            "general_phi": {
                "policy_id": "TS-002",
                "classification": DataClassification.SENSITIVE,
                "encryption_standard": EncryptionStandard.AES_256_CBC,
                "key_size": 256,
                "protocols": [TransmissionProtocol.HTTPS, TransmissionProtocol.SFTP],
                "require_mutual_auth": False,
                "require_integrity_check": True,
                "session_timeout": 900,  # 15 minutes
                "max_retries": 5,
            },
            "internal_data": {
                "policy_id": "TS-003",
                "classification": DataClassification.INTERNAL,
                "encryption_standard": EncryptionStandard.TLS_1_2,
                "key_size": 128,
                "protocols": [TransmissionProtocol.HTTPS],
                "require_mutual_auth": False,
                "require_integrity_check": False,
                "session_timeout": 3600,  # 1 hour
                "max_retries": 10,
            },
        }

    def _initialize_keys(self) -> Dict[str, Any]:
        """Initialize encryption keys."""
        # In production, these would be loaded from secure key management
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=4096, backend=default_backend()
        )
        public_key = private_key.public_key()

        return {
            "master_key": Fernet.generate_key(),
            "session_keys": {},
            "rsa_private_key": private_key,
            "rsa_public_key": public_key,
        }

    def encrypt_for_transmission(
        self,
        data: Dict[str, Any],
        classification: DataClassification,
        recipient_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Encrypt data for secure transmission.

        Args:
            data: Data to encrypt
            classification: Data classification level
            recipient_id: Recipient identifier
            metadata: Additional metadata

        Returns:
            Encrypted payload ready for transmission
        """
        # Get appropriate policy
        policy = self._get_policy_for_classification(classification)

        # Generate session key
        session_key = self._generate_session_key()
        session_id = self._generate_session_id()

        # Store session info
        self.active_sessions[session_id] = {
            "session_id": session_id,
            "created_at": datetime.now(),
            "recipient_id": recipient_id,
            "classification": classification.value,
            "policy_id": policy["policy_id"],
        }

        # Prepare data
        payload = {
            "data": data,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
            "sender_id": "SYSTEM",  # Would be actual sender
            "recipient_id": recipient_id,
        }

        # Encrypt based on standard
        if policy["encryption_standard"] == EncryptionStandard.AES_256_GCM:
            encrypted_data = self._encrypt_aes_gcm(payload, session_key)
        elif policy["encryption_standard"] == EncryptionStandard.AES_256_CBC:
            encrypted_data = self._encrypt_aes_cbc(payload, session_key)
        else:
            encrypted_data = self._encrypt_default(payload, session_key)

        # Add integrity check
        if policy["require_integrity_check"]:
            encrypted_data["integrity_hash"] = self._calculate_integrity_hash(
                encrypted_data["ciphertext"]
            )

        # Encrypt session key with recipient's public key
        encrypted_session_key = self._encrypt_session_key(session_key, recipient_id)

        # Build transmission package
        encryption_metadata = {
            "algorithm": policy["encryption_standard"].value,
            "key_size": policy["key_size"],
            "timestamp": datetime.now().isoformat(),
        }

        # Add integrity hash to metadata if present
        if policy["require_integrity_check"] and "integrity_hash" in encrypted_data:
            encryption_metadata["integrity_hash"] = encrypted_data["integrity_hash"]

        transmission_package = {
            "package_id": self._generate_package_id(),
            "session_id": session_id,
            "encrypted_data": encrypted_data,
            "encrypted_session_key": encrypted_session_key,
            "encryption_metadata": encryption_metadata,
            "classification": classification.value,
            "require_receipt": True,
        }

        # Log transmission preparation
        self._log_transmission(
            "encryption_complete",
            session_id,
            recipient_id,
            classification,
            len(json.dumps(data)),
        )

        return transmission_package

    def decrypt_transmission_package(
        self, transmission_package: Dict[str, Any], private_key: Optional[Any] = None
    ) -> Any:
        """Decrypt transmission package and return the original data.

        Args:
            transmission_package: Encrypted transmission package
            private_key: Private key for decryption

        Returns:
            Decrypted data (original format)
        """
        success, decrypted_data = self.decrypt_transmission(
            transmission_package, private_key
        )
        if success and decrypted_data:
            # Return the original data that was encrypted
            return decrypted_data.get("data", decrypted_data)
        else:
            raise ValueError("Failed to decrypt transmission package")

    def decrypt_transmission(
        self, transmission_package: Dict[str, Any], private_key: Optional[Any] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Decrypt received transmission.

        Args:
            transmission_package: Encrypted transmission package
            private_key: Private key for decryption

        Returns:
            Tuple of (success, decrypted_data)
        """
        try:
            session_id = transmission_package["session_id"]

            # Decrypt session key
            session_key = self._decrypt_session_key(
                transmission_package["encrypted_session_key"],
                private_key or self.keys["rsa_private_key"],
            )

            # Verify integrity if required
            encrypted_data = transmission_package["encrypted_data"]
            if "integrity_hash" in encrypted_data:
                if not self._verify_integrity(
                    encrypted_data["ciphertext"], encrypted_data["integrity_hash"]
                ):
                    logger.error("Integrity check failed for session %s", session_id)
                    return False, None

            # Decrypt data based on algorithm
            algorithm = transmission_package["encryption_metadata"]["algorithm"]

            if algorithm == EncryptionStandard.AES_256_GCM.value:
                decrypted = self._decrypt_aes_gcm(encrypted_data, session_key)
            elif algorithm == EncryptionStandard.AES_256_CBC.value:
                decrypted = self._decrypt_aes_cbc(encrypted_data, session_key)
            else:
                decrypted = self._decrypt_default(encrypted_data, session_key)

            # Log successful decryption
            self._log_transmission(
                "decryption_complete",
                session_id,
                decrypted.get("sender_id", "unknown"),
                DataClassification(transmission_package["classification"]),
                len(json.dumps(decrypted)),
            )

            return True, decrypted

        except (ValueError, KeyError, TypeError) as e:
            logger.error("Decryption failed: %s", str(e))
            self._log_failed_transmission(transmission_package, str(e))
            return False, None

    def establish_secure_channel(
        self, endpoint: str, protocol: TransmissionProtocol, mutual_auth: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """Establish secure communication channel.

        Args:
            endpoint: Target endpoint
            protocol: Transmission protocol
            mutual_auth: Whether to use mutual authentication

        Returns:
            Tuple of (success, channel_id)
        """
        channel_id = self._generate_channel_id()

        try:
            # Validate endpoint
            if not self._validate_endpoint(endpoint):
                return False, None

            # Check protocol support
            if protocol not in self._get_supported_protocols():
                logger.error("Unsupported protocol: %s", protocol)
                return False, None

            # Establish connection based on protocol
            if protocol == TransmissionProtocol.HTTPS:
                success = self._establish_https_channel(endpoint, mutual_auth)
            elif protocol == TransmissionProtocol.SFTP:
                success = self._establish_sftp_channel(endpoint)
            elif protocol == TransmissionProtocol.VPN:
                success = self._establish_vpn_channel(endpoint)
            else:
                success = False

            if success:
                logger.info("Secure channel established: %s", channel_id)
                return True, channel_id
            else:
                return False, None

        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.error("Failed to establish channel: %s", str(e))
            return False, None

    def validate_transmission_security(
        self, transmission_package: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate transmission security parameters.

        Args:
            transmission_package: Package to validate

        Returns:
            Validation results
        """
        results: Dict[str, Any] = {
            "valid": True,
            "checks": {},
            "warnings": [],
            "errors": [],
        }

        # Check encryption strength
        encryption_meta = transmission_package.get("encryption_metadata", {})
        key_size = encryption_meta.get("key_size", 0)

        if key_size < 128:
            results["errors"].append("Insufficient key size")
            results["valid"] = False
        elif key_size < 256:
            results["warnings"].append("Consider using 256-bit encryption")

        results["checks"]["encryption_strength"] = key_size >= 128

        # Check algorithm
        algorithm = encryption_meta.get("algorithm")
        approved_algorithms = [e.value for e in EncryptionStandard]

        if algorithm not in approved_algorithms:
            results["errors"].append(f"Unapproved algorithm: {algorithm}")
            results["valid"] = False

        results["checks"]["algorithm_approved"] = algorithm in approved_algorithms

        # Check session validity
        session_id = transmission_package.get("session_id")
        if session_id and session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            age = datetime.now() - session["created_at"]

            if age > timedelta(hours=1):
                results["warnings"].append("Session older than 1 hour")

        results["checks"]["session_valid"] = True

        return results

    def monitor_transmission_security(
        self, time_window: timedelta = DEFAULT_MONITORING_WINDOW
    ) -> Dict[str, Any]:
        """Monitor transmission security metrics.

        Args:
            time_window: Time window for monitoring

        Returns:
            Security metrics
        """
        cutoff_time = datetime.now() - time_window

        # Filter recent transmissions
        recent_transmissions = [
            t for t in self.transmission_log if t["timestamp"] >= cutoff_time
        ]

        # Calculate metrics
        total_transmissions = len(recent_transmissions)
        failed_transmissions = len(
            [t for t in self.failed_transmissions if t["timestamp"] >= cutoff_time]
        )

        # Group by classification
        by_classification = {}
        for trans in recent_transmissions:
            classification = trans["classification"]
            if classification not in by_classification:
                by_classification[classification] = 0
            by_classification[classification] += 1

        return {
            "monitoring_period": {"start": cutoff_time, "end": datetime.now()},
            "total_transmissions": total_transmissions,
            "successful_transmissions": total_transmissions - failed_transmissions,
            "failed_transmissions": failed_transmissions,
            "success_rate": (
                (
                    (total_transmissions - failed_transmissions)
                    / total_transmissions
                    * 100
                )
                if total_transmissions > 0
                else 100
            ),
            "transmissions_by_classification": by_classification,
            "active_sessions": len(self.active_sessions),
            "security_incidents": self._count_security_incidents(time_window),
        }

    def _encrypt_aes_gcm(self, data: Dict[str, Any], key: bytes) -> Dict[str, Any]:
        """Encrypt using AES-256-GCM."""
        # Generate nonce
        nonce = secrets.token_bytes(12)

        # Create cipher
        cipher = Cipher(
            algorithms.AES(key), modes.GCM(nonce), backend=default_backend()
        )
        encryptor = cipher.encryptor()

        # Encrypt data
        plaintext = json.dumps(data).encode()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()

        return {
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "tag": base64.b64encode(encryptor.tag).decode(),
            "algorithm": "AES-256-GCM",
        }

    def _decrypt_aes_gcm(
        self, encrypted_data: Dict[str, Any], key: bytes
    ) -> Dict[str, Any]:
        """Decrypt AES-256-GCM encrypted data."""
        # Decode components
        ciphertext = base64.b64decode(encrypted_data["ciphertext"])
        nonce = base64.b64decode(encrypted_data["nonce"])
        tag = base64.b64decode(encrypted_data["tag"])

        # Create cipher
        cipher = Cipher(
            algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend()
        )
        decryptor = cipher.decryptor()

        # Decrypt
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        data = json.loads(plaintext.decode())
        return cast(Dict[str, Any], data)

    def _encrypt_aes_cbc(self, data: Dict[str, Any], key: bytes) -> Dict[str, Any]:
        """Encrypt using AES-256-CBC."""
        # Generate IV
        iv = secrets.token_bytes(16)

        # Pad data to block size
        plaintext = json.dumps(data).encode()
        padder = sym_padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext) + padder.finalize()

        # Create cipher
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()

        # Encrypt
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        return {
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "iv": base64.b64encode(iv).decode(),
            "algorithm": "AES-256-CBC",
        }

    def _decrypt_aes_cbc(
        self, encrypted_data: Dict[str, Any], key: bytes
    ) -> Dict[str, Any]:
        """Decrypt AES-256-CBC encrypted data."""
        # Decode components
        ciphertext = base64.b64decode(encrypted_data["ciphertext"])
        iv = base64.b64decode(encrypted_data["iv"])

        # Create cipher
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()

        # Decrypt
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        # Remove padding
        unpadder = sym_padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

        data = json.loads(plaintext.decode())
        return cast(Dict[str, Any], data)

    def _encrypt_default(self, data: Dict[str, Any], key: bytes) -> Dict[str, Any]:
        """Encrypt data using Fernet algorithm."""
        f = Fernet(base64.urlsafe_b64encode(key[:32]))
        plaintext = json.dumps(data).encode()
        ciphertext = f.encrypt(plaintext)

        return {
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "algorithm": "Fernet",
        }

    def _decrypt_default(
        self, encrypted_data: Dict[str, Any], key: bytes
    ) -> Dict[str, Any]:
        """Decrypt data using Fernet algorithm."""
        f = Fernet(base64.urlsafe_b64encode(key[:32]))
        ciphertext = base64.b64decode(encrypted_data["ciphertext"])
        plaintext = f.decrypt(ciphertext)

        data = json.loads(plaintext.decode())
        return cast(Dict[str, Any], data)

    def _generate_session_key(self) -> bytes:
        """Generate new session key."""
        return secrets.token_bytes(32)

    def _encrypt_session_key(self, session_key: bytes, recipient_id: str) -> str:
        """Encrypt session key with recipient's public key."""
        # In production, would fetch recipient's public key using recipient_id
        # For now, use our own public key
        _ = recipient_id  # Will be used in production
        public_key = self.keys["rsa_private_key"].public_key()

        encrypted = public_key.encrypt(
            session_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        return base64.b64encode(encrypted).decode()

    def _decrypt_session_key(self, encrypted_key: str, private_key: Any) -> bytes:
        """Decrypt session key with private key."""
        encrypted = base64.b64decode(encrypted_key)

        decrypted = private_key.decrypt(
            encrypted,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        return cast(bytes, decrypted)

    def _calculate_integrity_hash(self, data: str) -> str:
        """Calculate integrity hash for data."""
        return hashlib.sha256(data.encode()).hexdigest()

    def _verify_integrity(self, data: str, expected_hash: str) -> bool:
        """Verify data integrity."""
        actual_hash = self._calculate_integrity_hash(data)
        return hmac.compare_digest(actual_hash, expected_hash)

    def _get_policy_for_classification(
        self, classification: DataClassification
    ) -> Dict[str, Any]:
        """Get policy for data classification."""
        for policy in self.encryption_policies.values():
            if policy["classification"] == classification:
                return policy
        # Default to highest security
        return self.encryption_policies["highly_sensitive_phi"]

    def _validate_endpoint(self, endpoint: str) -> bool:
        """Validate endpoint security."""
        # Check for secure protocols
        if endpoint.startswith(("https://", "sftp://", "ftps://")):
            return True
        return False

    def _get_supported_protocols(self) -> List[TransmissionProtocol]:
        """Get list of supported protocols."""
        return list(TransmissionProtocol)

    def _establish_https_channel(self, endpoint: str, mutual_auth: bool) -> bool:
        """Establish HTTPS channel."""
        # In production, would establish actual HTTPS connection
        # with mutual_auth configuration
        _ = mutual_auth  # Will be used in production
        logger.info("Establishing HTTPS channel to %s", endpoint)
        return True

    def _establish_sftp_channel(self, endpoint: str) -> bool:
        """Establish SFTP channel."""
        # In production, would establish actual SFTP connection
        logger.info("Establishing SFTP channel to %s", endpoint)
        return True

    def _establish_vpn_channel(self, endpoint: str) -> bool:
        """Establish VPN channel."""
        # In production, would establish actual VPN connection
        logger.info("Establishing VPN channel to %s", endpoint)
        return True

    def _log_transmission(
        self,
        event_type: str,
        session_id: str,
        party_id: str,
        classification: DataClassification,
        data_size: int,
    ) -> None:
        """Log transmission event."""
        log_entry = {
            "timestamp": datetime.now(),
            "event_type": event_type,
            "session_id": session_id,
            "party_id": party_id,
            "classification": classification.value,
            "data_size": data_size,
            "log_id": self._generate_log_id(),
        }

        self.transmission_log.append(log_entry)
        logger.info("Transmission logged: %s - %s", event_type, session_id)

    def _log_failed_transmission(
        self, transmission_package: Dict[str, Any], error: str
    ) -> None:
        """Log failed transmission."""
        failure_entry = {
            "timestamp": datetime.now(),
            "package_id": transmission_package.get("package_id"),
            "session_id": transmission_package.get("session_id"),
            "error": error,
            "failure_id": self._generate_failure_id(),
        }

        self.failed_transmissions.append(failure_entry)
        logger.error("Transmission failed: %s", failure_entry["failure_id"])

    def _count_security_incidents(self, time_window: timedelta) -> int:
        """Count security incidents in time window."""
        cutoff_time = datetime.now() - time_window

        incidents = [
            f
            for f in self.failed_transmissions
            if f["timestamp"] >= cutoff_time
            and "security" in f.get("error", "").lower()
        ]

        return len(incidents)

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        return f"TS-SESSION-{uuid.uuid4()}"

    def _generate_package_id(self) -> str:
        """Generate unique package ID."""
        return f"TS-PKG-{uuid.uuid4()}"

    def _generate_channel_id(self) -> str:
        """Generate unique channel ID."""
        return f"TS-CHAN-{uuid.uuid4()}"

    def _generate_log_id(self) -> str:
        """Generate unique log ID."""
        return f"TS-LOG-{uuid.uuid4()}"

    def _generate_failure_id(self) -> str:
        """Generate unique failure ID."""
        return f"TS-FAIL-{uuid.uuid4()}"

    def check_transmission_access(
        self,
        user_id: str,
        data_classification: DataClassification,
        protocol: TransmissionProtocol,
    ) -> bool:
        """Check if user has access to transmit data.

        Args:
            user_id: ID of user attempting transmission
            data_classification: Classification of data being transmitted
            protocol: Transmission protocol to be used

        Returns:
            True if access is allowed
        """
        # Check with HIPAA access control
        user = hipaa_access_control.users.get(user_id)
        if not user:
            return False

        # Check if user has appropriate role for data classification
        if data_classification == DataClassification.HIGHLY_SENSITIVE:
            # Only certain roles can transmit highly sensitive data
            allowed_roles = ["healthcare_provider", "admin", "privacy_officer"]
            if not any(role.name in allowed_roles for role in user.roles):
                return False

        # Check if protocol is allowed for classification
        policy = self._get_policy_for_classification(data_classification)
        if protocol not in policy["protocols"]:
            return False

        return True

    def validate_fhir_transmission_audit(
        self, transmission_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate transmission event as FHIR AuditEvent.

        Args:
            transmission_data: Transmission data to convert and validate

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        # Convert to FHIR AuditEvent format
        fhir_audit_event = {
            "resourceType": "AuditEvent",
            "type": {
                "system": "http://dicom.nema.org/resources/ontology/DCM",
                "code": "110106",
                "display": "Export",
            },
            "subtype": [
                {
                    "system": "http://hl7.org/fhir/restful-interaction",
                    "code": "transmit",
                    "display": "Transmit Record",
                }
            ],
            "action": "E",  # Execute
            "period": {
                "start": transmission_data.get("timestamp", datetime.now()).isoformat()
            },
            "recorded": datetime.now().isoformat(),
            "outcome": "0" if transmission_data.get("success", True) else "8",
            "outcomeDesc": (
                transmission_data.get("error")
                if not transmission_data.get("success", True)
                else None
            ),
            "agent": [
                {
                    "who": {
                        "identifier": {
                            "value": transmission_data.get("sender", "Unknown")
                        }
                    },
                    "requestor": True,
                    "network": {
                        "address": transmission_data.get("source_ip", "Unknown"),
                        "type": "2",  # IP Address
                    },
                }
            ],
            "source": {"observer": {"display": "HIPAA Transmission Security System"}},
            "entity": [
                {
                    "what": {
                        "identifier": {
                            "value": transmission_data.get("package_id", "Unknown")
                        }
                    },
                    "type": {
                        "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type",
                        "code": "2",
                        "display": "System Object",
                    },
                    "role": {
                        "system": "http://terminology.hl7.org/CodeSystem/object-role",
                        "code": "4",
                        "display": "Domain Resource",
                    },
                    "securityLabel": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
                            "code": self._map_classification_to_confidentiality(
                                transmission_data.get(
                                    "classification", DataClassification.SENSITIVE
                                )
                            ),
                        }
                    ],
                }
            ],
        }

        # Validate using FHIR validator
        return self.fhir_validator.validate_resource("AuditEvent", fhir_audit_event)

    def _map_classification_to_confidentiality(
        self, classification: DataClassification
    ) -> str:
        """Map data classification to FHIR confidentiality code."""
        mapping = {
            DataClassification.HIGHLY_SENSITIVE: "V",  # Very Restricted
            DataClassification.SENSITIVE: "R",  # Restricted
            DataClassification.INTERNAL: "N",  # Normal
            DataClassification.PUBLIC: "U",  # Unrestricted
        }
        return mapping.get(classification, "R")
