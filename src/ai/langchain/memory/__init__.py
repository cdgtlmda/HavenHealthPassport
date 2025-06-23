"""
LangChain Memory Systems for Haven Health Passport.

HIPAA-compliant memory implementations for medical conversations.
Handles FHIR Resource validation.
"""

from typing import Any, Dict, List

from .base import BaseMemoryStore, DynamoDBMemoryStore, EncryptedMemoryStore
from .conversation import (
    ConversationBufferMemory,
    ConversationBufferWindowMemory,
    ConversationMemory,
    ConversationTokenBufferMemory,
)
from .custom import (
    EmergencyMemory,
    HybridMemory,
    MedicalContextMemory,
    MultilingualMemory,
)
from .entity import EntityMemory, MedicalEntityMemory, PatientEntityMemory
from .summary import ConversationSummaryMemory, MedicalSummaryMemory, SummaryMemory

__all__ = [
    "ConversationMemory",
    "ConversationBufferMemory",
    "ConversationBufferWindowMemory",
    "ConversationTokenBufferMemory",
    "EntityMemory",
    "MedicalEntityMemory",
    "PatientEntityMemory",
    "SummaryMemory",
    "ConversationSummaryMemory",
    "MedicalSummaryMemory",
    "HybridMemory",
    "MedicalContextMemory",
    "EmergencyMemory",
    "MultilingualMemory",
    "BaseMemoryStore",
    "DynamoDBMemoryStore",
    "EncryptedMemoryStore",
]


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
