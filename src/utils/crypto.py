"""Cryptographic utilities for the Haven Health Passport application.

Note: This module handles PHI-related cryptographic operations.
- Access Control: Implement strict access control for all cryptographic operations and key management
"""

import hashlib
import hmac
import secrets
from typing import Optional

import bcrypt
from cryptography.fernet import Fernet


class CryptoManager:
    """Manages cryptographic operations."""

    def __init__(self, master_key: Optional[bytes] = None):
        """Initialize crypto manager.

        Args:
            master_key: Master encryption key (if not provided, generates one)
        """
        self.master_key = master_key or Fernet.generate_key()
        self.fernet = Fernet(self.master_key)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plaintext password

    Returns:
        Hashed password
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hash.

    Args:
        password: Plaintext password
        hashed: Hashed password

    Returns:
        True if password matches
    """
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def hash_value(value: str) -> str:
    """Hash a value using SHA256 (for non-password values like codes).

    Args:
        value: Value to hash

    Returns:
        Hashed value
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_hash(value: str, hashed: str) -> bool:
    """Verify a value against a SHA256 hash.

    Args:
        value: Value to verify
        hashed: Hashed value

    Returns:
        True if value matches
    """
    return hash_value(value) == hashed


def generate_token(length: int = 32) -> str:
    """Generate a secure random token.

    Args:
        length: Token length in bytes

    Returns:
        Hex-encoded token
    """
    return secrets.token_hex(length)


def generate_secure_code(length: int = 6, digits_only: bool = True) -> str:
    """Generate a secure random code.

    Args:
        length: Code length
        digits_only: Use only digits (True) or alphanumeric (False)

    Returns:
        Random code
    """
    if digits_only:
        charset = "0123456789"
    else:
        charset = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Exclude confusing chars

    return "".join(secrets.choice(charset) for _ in range(length))


def constant_time_compare(val1: str, val2: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks.

    Args:
        val1: First value
        val2: Second value

    Returns:
        True if values match
    """
    return hmac.compare_digest(val1.encode("utf-8"), val2.encode("utf-8"))
