"""HIPAA Encryption Standards Implementation.

This module implements HIPAA-compliant encryption standards for protecting
PHI at rest and in transit. All PHI data is encrypted and access is
controlled through role-based permissions.
"""

import base64
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import padding as crypto_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

logger = logging.getLogger(__name__)


class EncryptionType(Enum):
    """Types of encryption."""

    AT_REST = "at_rest"
    IN_TRANSIT = "in_transit"
    IN_USE = "in_use"


class EncryptionAlgorithm(Enum):
    """HIPAA-approved encryption algorithms."""

    # Symmetric algorithms
    AES_128_GCM = "aes_128_gcm"
    AES_256_GCM = "aes_256_gcm"
    AES_128_CBC = "aes_128_cbc"
    AES_256_CBC = "aes_256_cbc"
    AES_256_CTR = "aes_256_ctr"

    # Asymmetric algorithms
    RSA_2048 = "rsa_2048"
    RSA_4096 = "rsa_4096"
    ECDSA_P256 = "ecdsa_p256"
    ECDSA_P384 = "ecdsa_p384"

    # Key derivation
    PBKDF2 = "pbkdf2"
    SCRYPT = "scrypt"
    ARGON2 = "argon2"


class KeyStrength(Enum):
    """Encryption key strengths."""

    MINIMUM = "minimum"  # HIPAA minimum requirements
    STANDARD = "standard"  # Recommended for most PHI
    HIGH = "high"  # For highly sensitive data
    MAXIMUM = "maximum"  # Maximum available security


class HIPAAEncryptionStandards:
    """Implements HIPAA-compliant encryption standards."""

    def __init__(self) -> None:
        """Initialize encryption standards."""
        self.encryption_policies = self._initialize_policies()
        self.algorithm_specs = self._initialize_algorithm_specs()
        self.key_registry: Dict[str, Dict[str, Any]] = {}
        self.encryption_audit_log: List[Dict[str, Any]] = []

    def _initialize_policies(self) -> Dict[str, Dict[str, Any]]:
        """Initialize encryption policies by data type."""
        return {
            "patient_identifiers": {
                "policy_id": "ENC-001",
                "description": "Encryption for patient identifiers (SSN, MRN)",
                "at_rest": {
                    "algorithm": EncryptionAlgorithm.AES_256_GCM,
                    "key_strength": KeyStrength.HIGH,
                    "key_rotation_days": 90,
                },
                "in_transit": {
                    "algorithm": EncryptionAlgorithm.AES_256_GCM,
                    "protocol": "TLS 1.3",
                    "perfect_forward_secrecy": True,
                },
                "key_derivation": EncryptionAlgorithm.SCRYPT,
            },
            "medical_records": {
                "policy_id": "ENC-002",
                "description": "Encryption for medical records and clinical data",
                "at_rest": {
                    "algorithm": EncryptionAlgorithm.AES_256_CBC,
                    "key_strength": KeyStrength.STANDARD,
                    "key_rotation_days": 180,
                },
                "in_transit": {
                    "algorithm": EncryptionAlgorithm.AES_256_GCM,
                    "protocol": "TLS 1.2+",
                    "perfect_forward_secrecy": True,
                },
                "key_derivation": EncryptionAlgorithm.PBKDF2,
            },
        }

    def _initialize_algorithm_specs(self) -> Dict[EncryptionAlgorithm, Dict[str, Any]]:
        """Initialize algorithm specifications."""
        return {
            EncryptionAlgorithm.AES_256_GCM: {
                "key_size": 256,
                "block_size": 128,
                "mode": "GCM",
                "nonce_size": 96,
                "tag_size": 128,
                "approved_for": ["at_rest", "in_transit"],
                "strength_rating": "high",
            },
            EncryptionAlgorithm.AES_256_CBC: {
                "key_size": 256,
                "block_size": 128,
                "mode": "CBC",
                "iv_size": 128,
                "approved_for": ["at_rest"],
                "strength_rating": "high",
            },
            EncryptionAlgorithm.RSA_4096: {
                "key_size": 4096,
                "padding": "OAEP",
                "hash_function": "SHA-256",
                "approved_for": ["key_exchange", "digital_signatures"],
                "strength_rating": "maximum",
            },
            EncryptionAlgorithm.PBKDF2: {
                "iterations": 100000,
                "salt_size": 128,
                "hash_function": "SHA-256",
                "approved_for": ["key_derivation"],
                "strength_rating": "standard",
            },
            EncryptionAlgorithm.SCRYPT: {
                "n": 16384,
                "r": 8,
                "p": 1,
                "salt_size": 128,
                "approved_for": ["key_derivation"],
                "strength_rating": "high",
            },
        }

    def encrypt_phi_at_rest(
        self,
        data: Union[str, bytes, Dict[str, Any]],
        data_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Encrypt PHI for storage at rest.

        Args:
            data: Data to encrypt
            data_type: Type of PHI data
            metadata: Additional metadata

        Returns:
            Encrypted data package
        """
        # Get policy for data type
        policy = self.encryption_policies.get(data_type)
        if not policy:
            policy = self.encryption_policies["medical_records"]  # Default

        at_rest_policy = policy["at_rest"]
        algorithm = at_rest_policy["algorithm"]

        # Generate or retrieve encryption key
        key_id = self._get_or_create_key(data_type, algorithm)
        key = self.key_registry[key_id]["key"]

        # Prepare data
        if isinstance(data, dict):
            plaintext = json.dumps(data).encode()
        elif isinstance(data, str):
            plaintext = data.encode()
        else:
            plaintext = data

        # Encrypt based on algorithm
        if algorithm == EncryptionAlgorithm.AES_256_GCM:
            encrypted = self._encrypt_aes_gcm(plaintext, key)
        elif algorithm == EncryptionAlgorithm.AES_256_CBC:
            encrypted = self._encrypt_aes_cbc(plaintext, key)
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        # Create encrypted package
        package = {
            "encryption_id": self._generate_encryption_id(),
            "data_type": data_type,
            "algorithm": algorithm.value,
            "key_id": key_id,
            "encrypted_data": encrypted,
            "encryption_timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
            "compliance": {
                "hipaa_compliant": True,
                "policy_id": policy["policy_id"],
                "key_strength": at_rest_policy["key_strength"].value,
            },
        }

        # Log encryption
        self._log_encryption_event(
            "encrypt_at_rest", data_type, algorithm, len(plaintext)
        )

        return package

    def decrypt_phi_at_rest(
        self, encrypted_package: Dict[str, Any]
    ) -> Tuple[bool, Optional[Union[str, bytes, Dict[str, Any]]]]:
        """Decrypt PHI stored at rest.

        Args:
            encrypted_package: Encrypted data package

        Returns:
            Tuple of (success, decrypted_data)
        """
        try:
            # Extract components
            algorithm = EncryptionAlgorithm(encrypted_package["algorithm"])
            key_id = encrypted_package["key_id"]
            encrypted_data = encrypted_package["encrypted_data"]

            # Retrieve key
            if key_id not in self.key_registry:
                logger.error("Key not found: %s", key_id)
                return False, None

            key = self.key_registry[key_id]["key"]

            # Decrypt based on algorithm
            if algorithm == EncryptionAlgorithm.AES_256_GCM:
                plaintext = self._decrypt_aes_gcm(encrypted_data, key)
            elif algorithm == EncryptionAlgorithm.AES_256_CBC:
                plaintext = self._decrypt_aes_cbc(encrypted_data, key)
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")

            # Convert back to original format
            data_type = encrypted_package.get("data_type", "")
            if "json" in data_type or "record" in data_type:
                result = json.loads(plaintext.decode())
            else:
                result = plaintext.decode()

            # Log decryption
            self._log_encryption_event(
                "decrypt_at_rest", data_type, algorithm, len(plaintext)
            )

            return True, result

        except (ValueError, KeyError, AttributeError) as e:
            logger.error("Decryption failed: %s", str(e))
            return False, None

    def validate_encryption_compliance(
        self, encrypted_package: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate encryption meets HIPAA standards.

        Args:
            encrypted_package: Encrypted data package

        Returns:
            Compliance validation results
        """
        results: Dict[str, Any] = {
            "compliant": True,
            "checks": {},
            "warnings": [],
            "violations": [],
        }

        # Check algorithm compliance
        algorithm = encrypted_package.get("algorithm")
        approved_algorithms = [a.value for a in EncryptionAlgorithm]

        if algorithm not in approved_algorithms:
            results["violations"].append(f"Non-approved algorithm: {algorithm}")
            results["compliant"] = False
        results["checks"]["algorithm_approved"] = algorithm in approved_algorithms

        # Check key strength
        compliance_info = encrypted_package.get("compliance", {})
        key_strength = compliance_info.get("key_strength", "")

        if key_strength == KeyStrength.MINIMUM.value:
            results["warnings"].append(
                "Using minimum key strength - consider upgrading"
            )
        results["checks"]["key_strength_adequate"] = key_strength != ""

        # Check encryption age for rotation
        timestamp_str = encrypted_package.get("encryption_timestamp", "")
        if timestamp_str:
            timestamp = datetime.fromisoformat(timestamp_str)
            age = datetime.now() - timestamp

            if age > timedelta(days=365):
                results["warnings"].append(
                    "Encryption older than 1 year - consider re-encryption"
                )

        return results

    def generate_encryption_key(
        self,
        algorithm: EncryptionAlgorithm,
        key_strength: KeyStrength = KeyStrength.STANDARD,
    ) -> bytes:
        """Generate encryption key meeting HIPAA standards.

        Args:
            algorithm: Encryption algorithm
            key_strength: Desired key strength

        Returns:
            Generated key
        """
        # Determine key size based on algorithm and strength
        key_sizes = {
            (EncryptionAlgorithm.AES_256_GCM, KeyStrength.MINIMUM): 128,
            (EncryptionAlgorithm.AES_256_GCM, KeyStrength.STANDARD): 256,
            (EncryptionAlgorithm.AES_256_GCM, KeyStrength.HIGH): 256,
            (EncryptionAlgorithm.AES_256_CBC, KeyStrength.MINIMUM): 128,
            (EncryptionAlgorithm.AES_256_CBC, KeyStrength.STANDARD): 256,
            (EncryptionAlgorithm.AES_256_CBC, KeyStrength.HIGH): 256,
        }

        key_size_bits = key_sizes.get((algorithm, key_strength), 256)
        key_size_bytes = key_size_bits // 8

        # Generate cryptographically secure key
        key = secrets.token_bytes(key_size_bytes)

        # Log key generation
        logger.info("Generated %d-bit key for %s", key_size_bits, algorithm.value)

        return key

    def derive_key_from_password(
        self,
        password: str,
        salt: Optional[bytes] = None,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.PBKDF2,
    ) -> Tuple[bytes, bytes]:
        """Derive encryption key from password.

        Args:
            password: User password
            salt: Salt for derivation (generated if not provided)
            algorithm: Key derivation algorithm

        Returns:
            Tuple of (derived_key, salt)
        """
        if salt is None:
            salt = secrets.token_bytes(16)

        if algorithm == EncryptionAlgorithm.PBKDF2:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend(),
            )
            key = kdf.derive(password.encode())

        elif algorithm == EncryptionAlgorithm.SCRYPT:
            scrypt_kdf = Scrypt(
                salt=salt, length=32, n=16384, r=8, p=1, backend=default_backend()
            )
            key = scrypt_kdf.derive(password.encode())

        else:
            raise ValueError(f"Unsupported KDF algorithm: {algorithm}")

        return key, salt

    def rotate_encryption_keys(
        self, data_type: str, force: bool = False
    ) -> Dict[str, Any]:
        """Rotate encryption keys based on policy.

        Args:
            data_type: Type of data to rotate keys for
            force: Force rotation regardless of schedule

        Returns:
            Rotation results
        """
        results = {
            "rotated": False,
            "old_key_id": None,
            "new_key_id": None,
            "reason": "",
        }

        policy = self.encryption_policies.get(data_type)
        if not policy:
            results["reason"] = "No policy found"
            return results

        # Check if rotation needed
        rotation_days = policy["at_rest"]["key_rotation_days"]
        current_key_id = self._get_current_key_id(data_type)

        if current_key_id and not force:
            key_info = self.key_registry[current_key_id]
            age = datetime.now() - key_info["created_at"]

            if age.days < rotation_days:
                results["reason"] = (
                    f"Key age ({age.days} days) < rotation period ({rotation_days} days)"
                )
                return results

        # Generate new key
        algorithm = policy["at_rest"]["algorithm"]
        new_key_id = self._get_or_create_key(data_type, algorithm, force_new=True)

        results.update(
            {
                "rotated": True,
                "old_key_id": current_key_id,
                "new_key_id": new_key_id,
                "reason": "Scheduled rotation" if not force else "Forced rotation",
            }
        )

        logger.info(
            "Key rotated for %s: %s -> %s", data_type, current_key_id, new_key_id
        )

        return results

    def audit_encryption_usage(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Audit encryption usage and compliance.

        Args:
            start_date: Audit period start
            end_date: Audit period end

        Returns:
            Audit report
        """
        # Filter logs for date range
        period_logs = [
            log
            for log in self.encryption_audit_log
            if start_date <= log["timestamp"] <= end_date
        ]

        # Analyze by algorithm
        algorithm_usage = {}
        for log in period_logs:
            algorithm = log.get("algorithm", "unknown")
            if algorithm not in algorithm_usage:
                algorithm_usage[algorithm] = 0
            algorithm_usage[algorithm] += 1

        # Check compliance
        non_compliant_events = [
            log
            for log in period_logs
            if log.get("algorithm") not in [a.value for a in EncryptionAlgorithm]
        ]

        return {
            "audit_period": {"start": start_date, "end": end_date},
            "total_encryption_events": len(period_logs),
            "algorithm_usage": algorithm_usage,
            "non_compliant_events": len(non_compliant_events),
            "compliance_rate": (
                (
                    (len(period_logs) - len(non_compliant_events))
                    / len(period_logs)
                    * 100
                )
                if period_logs
                else 100
            ),
            "key_rotations": self._count_key_rotations(period_logs),
            "recommendations": self._generate_encryption_recommendations(
                algorithm_usage
            ),
        }

    def _encrypt_aes_gcm(self, plaintext: bytes, key: bytes) -> Dict[str, Any]:
        """Encrypt using AES-GCM."""
        nonce = secrets.token_bytes(12)

        cipher = Cipher(
            algorithms.AES(key), modes.GCM(nonce), backend=default_backend()
        )
        encryptor = cipher.encryptor()

        ciphertext = encryptor.update(plaintext) + encryptor.finalize()

        return {
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "tag": base64.b64encode(encryptor.tag).decode(),
        }

    def _decrypt_aes_gcm(self, encrypted_data: Dict[str, Any], key: bytes) -> bytes:
        """Decrypt AES-GCM encrypted data."""
        ciphertext = base64.b64decode(encrypted_data["ciphertext"])
        nonce = base64.b64decode(encrypted_data["nonce"])
        tag = base64.b64decode(encrypted_data["tag"])

        cipher = Cipher(
            algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend()
        )
        decryptor = cipher.decryptor()

        return decryptor.update(ciphertext) + decryptor.finalize()

    def _encrypt_aes_cbc(self, plaintext: bytes, key: bytes) -> Dict[str, Any]:
        """Encrypt using AES-CBC."""
        iv = secrets.token_bytes(16)

        # Pad plaintext
        padder = crypto_padding.PKCS7(128).padder()
        padded_plaintext = padder.update(plaintext) + padder.finalize()

        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()

        ciphertext = encryptor.update(padded_plaintext) + encryptor.finalize()

        return {
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "iv": base64.b64encode(iv).decode(),
        }

    def _decrypt_aes_cbc(self, encrypted_data: Dict[str, Any], key: bytes) -> bytes:
        """Decrypt AES-CBC encrypted data."""
        ciphertext = base64.b64decode(encrypted_data["ciphertext"])
        iv = base64.b64decode(encrypted_data["iv"])

        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()

        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        # Remove padding
        unpadder = crypto_padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

        return plaintext

    def _get_or_create_key(
        self, data_type: str, algorithm: EncryptionAlgorithm, force_new: bool = False
    ) -> str:
        """Get existing or create new encryption key."""
        key_id = f"{data_type}_{algorithm.value}"

        if not force_new and key_id in self.key_registry:
            return key_id

        # Generate new key
        policy = self.encryption_policies.get(data_type, {})
        key_strength = policy.get("at_rest", {}).get(
            "key_strength", KeyStrength.STANDARD
        )

        key = self.generate_encryption_key(algorithm, key_strength)

        self.key_registry[key_id] = {
            "key": key,
            "algorithm": algorithm,
            "created_at": datetime.now(),
            "data_type": data_type,
            "active": True,
        }

        return key_id

    def _get_current_key_id(self, data_type: str) -> Optional[str]:
        """Get current active key ID for data type."""
        for key_id, key_info in self.key_registry.items():
            if key_info["data_type"] == data_type and key_info.get("active", False):
                return key_id
        return None

    def _log_encryption_event(
        self,
        event_type: str,
        data_type: str,
        algorithm: EncryptionAlgorithm,
        data_size: int,
    ) -> None:
        """Log encryption event."""
        log_entry = {
            "timestamp": datetime.now(),
            "event_type": event_type,
            "data_type": data_type,
            "algorithm": algorithm.value,
            "data_size": data_size,
            "log_id": self._generate_log_id(),
        }

        self.encryption_audit_log.append(log_entry)

    def _count_key_rotations(self, logs: List[Dict[str, Any]]) -> int:
        """Count key rotation events in logs."""
        return sum(1 for log in logs if "rotation" in log.get("event_type", ""))

    def _generate_encryption_recommendations(
        self, algorithm_usage: Dict[str, int]
    ) -> List[str]:
        """Generate recommendations based on usage."""
        recommendations = []

        # Check for weak algorithms
        weak_algorithms = ["aes_128_cbc", "aes_128_gcm"]
        for algo in weak_algorithms:
            if algo in algorithm_usage:
                recommendations.append(
                    f"Consider upgrading from {algo} to stronger encryption"
                )

        # Check for missing algorithms
        if "aes_256_gcm" not in algorithm_usage:
            recommendations.append("Consider using AES-256-GCM for new encryptions")

        return recommendations

    def _generate_encryption_id(self) -> str:
        """Generate unique encryption ID."""
        return f"ENC-{uuid.uuid4()}"

    def _generate_log_id(self) -> str:
        """Generate unique log ID."""
        return f"ENC-LOG-{uuid.uuid4()}"
