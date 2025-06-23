"""
Key Management Module for Haven Health Passport.

This module provides production-ready key management including:
- Key lifecycle management
- Automatic key rotation
- HIPAA-compliant encryption
- AWS KMS integration
"""

from .key_manager import KeyManager, KeyMetadata, KeyStatus, KeyType
from .production_key_initializer import (
    ProductionKeyInitializer,
    get_key_initializer,
    initialize_production_keys,
)

__all__ = [
    "KeyManager",
    "KeyType",
    "KeyStatus",
    "KeyMetadata",
    "ProductionKeyInitializer",
    "initialize_production_keys",
    "get_key_initializer",
]
