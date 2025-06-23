"""
PHI Protection Module.

Provides encryption and access control for Protected Health Information (PHI).
Ensures HIPAA compliance for all health data processing.
"""

import base64
import functools
import logging
import os
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class PHIEncryption:
    """Handles encryption/decryption of PHI data."""

    def __init__(self, key: Optional[bytes] = None):
        """Initialize encryption with provided or generated key."""
        if key is None:
            key = self._generate_key()
        self.cipher = Fernet(key)

    @staticmethod
    def _generate_key() -> bytes:
        """Generate a new encryption key."""
        # In production, this should use a proper key management service
        return Fernet.generate_key()

    @staticmethod
    def derive_key_from_password(password: str, salt: Optional[bytes] = None) -> bytes:
        """Derive encryption key from password."""
        if salt is None:
            salt = os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def encrypt_data(self, data: Union[str, bytes, dict, None]) -> bytes:
        """Encrypt PHI data."""
        if data is None:
            data = ""
        if isinstance(data, dict):
            data = str(data)
        if isinstance(data, str):
            data = data.encode("utf-8")
        return self.cipher.encrypt(data)

    def decrypt_data(self, encrypted_data: bytes) -> str:
        """Decrypt PHI data."""
        return self.cipher.decrypt(encrypted_data).decode("utf-8")


class PHIAccessControl:
    """Manages access control for PHI data."""

    def __init__(self) -> None:
        """Initialize PHI access control with empty authorized users and access log."""
        self.authorized_users: Set[Tuple[str, str]] = set()
        self.access_log: List[Dict[str, Any]] = []

    def add_authorized_user(self, user_id: str, role: str = "viewer") -> None:
        """Add user to authorized list."""
        self.authorized_users.add((user_id, role))
        logger.info("Added authorized user: %s with role: %s", user_id, role)

    def check_access(self, user_id: str, operation: str = "read") -> bool:
        """Check if user has access to perform operation."""
        # In production, this would check against a proper auth system
        has_access = any(u[0] == user_id for u in self.authorized_users)

        # Log access attempt
        self.access_log.append(
            {
                "user_id": user_id,
                "operation": operation,
                "granted": has_access,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        if not has_access:
            logger.warning(
                "Access denied for user %s attempting %s", user_id, operation
            )

        return has_access

    def get_access_log(self) -> list:
        """Return access log for audit purposes."""
        return self.access_log.copy()


# Global instances for consistent usage
# Thread-safe singleton for PHI protection
class PHIProtectionSingleton:
    """Thread-safe singleton for PHI protection services."""

    _instance = None
    _lock = threading.Lock()
    _encryption: PHIEncryption
    _access_control: PHIAccessControl

    def __new__(cls) -> "PHIProtectionSingleton":
        """Create a new instance or return the existing singleton instance."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._encryption = PHIEncryption()
                    cls._instance._access_control = PHIAccessControl()
        return cls._instance

    def get_encryption(self) -> PHIEncryption:
        """Get the encryption service."""
        return self._encryption

    def get_access_control(self) -> PHIAccessControl:
        """Get the access control service."""
        return self._access_control


def get_phi_protection() -> PHIProtectionSingleton:
    """Get the thread-safe PHI protection instance."""
    return PHIProtectionSingleton()


def encrypt_phi(data: Any) -> bytes:
    """Encrypt PHI data using thread-safe encryption instance."""
    protection = get_phi_protection()
    return protection.get_encryption().encrypt_data(data)


def decrypt_phi(encrypted_data: bytes) -> str:
    """Decrypt PHI data using thread-safe encryption instance."""
    protection = get_phi_protection()
    return protection.get_encryption().decrypt_data(encrypted_data)


def requires_phi_access(operation: str = "read") -> Callable[[Callable], Callable]:
    """Enforce PHI access control for decorated functions."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract user_id from kwargs or use default
            user_id = kwargs.get("user_id", "system")

            protection = get_phi_protection()
            if not protection.get_access_control().check_access(user_id, operation):
                raise PermissionError(
                    f"User {user_id} not authorized for {operation} operation"
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def protect_phi_field(field_name: str) -> Callable[[type], type]:
    """Automatically encrypt/decrypt a specific field in a class."""

    def decorator(cls: type) -> type:
        # Save references to original methods
        _original_init = cls.__init__  # type: ignore

        def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
            _original_init(self, *args, **kwargs)
            # Encrypt the field if it exists and is not None
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                if value is not None:
                    encrypted = encrypt_phi(value)
                    object.__setattr__(self, f"_encrypted_{field_name}", encrypted)
                    object.__setattr__(self, field_name, None)

        def new_getattr(self: Any, name: str) -> Any:
            if name == field_name:
                encrypted_field = f"_encrypted_{field_name}"
                if hasattr(self, encrypted_field):
                    encrypted = object.__getattribute__(self, encrypted_field)
                    return decrypt_phi(encrypted)
                else:
                    # Return None if no encrypted field exists
                    return None
            return object.__getattribute__(self, name)

        def new_setattr(self: Any, name: str, value: Any) -> None:
            if name == field_name:
                if value is not None:
                    encrypted = encrypt_phi(value)
                    object.__setattr__(self, f"_encrypted_{field_name}", encrypted)
                    object.__setattr__(self, name, None)
                else:
                    # If setting to None, remove encrypted field
                    if hasattr(self, f"_encrypted_{field_name}"):
                        delattr(self, f"_encrypted_{field_name}")
                    object.__setattr__(self, name, None)
            else:
                object.__setattr__(self, name, value)

        # Assign new methods directly
        cls.__init__ = new_init  # type: ignore[misc]
        cls.__getattribute__ = new_getattr  # type: ignore[assignment]
        cls.__setattr__ = new_setattr  # type: ignore[assignment]

        return cls

    return decorator


# Initialize with default authorized users for examples
# Note: Initialization moved to application startup
# get_phi_protection().get_access_control().add_authorized_user("system", "admin")
# get_phi_protection().get_access_control().add_authorized_user("demo_user", "viewer")
