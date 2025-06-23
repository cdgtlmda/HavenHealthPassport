"""Configuration for LangChain memory systems.

All memory systems containing PHI are encrypted and access controlled per HIPAA requirements.
"""

import os
from typing import Any, Dict

from cryptography.fernet import Fernet

# Import memory components
from .base import DynamoDBMemoryStore, EncryptedMemoryStore
from .conversation import (
    ConversationBufferMemory,
    ConversationBufferWindowMemory,
    ConversationTokenBufferMemory,
)
from .custom import EmergencyMemory, MedicalContextMemory


class MemoryConfig:
    """Central configuration for memory systems."""

    # DynamoDB settings
    DYNAMODB_TABLE_NAME = os.getenv(
        "LANGCHAIN_MEMORY_TABLE", "haven-health-langchain-memory"
    )
    DYNAMODB_REGION = os.getenv("AWS_REGION", "us-east-1")
    DYNAMODB_TTL_DAYS = int(os.getenv("MEMORY_TTL_DAYS", "90"))
    DYNAMODB_MAX_VERSIONS = int(os.getenv("MEMORY_MAX_VERSIONS", "10"))

    # Encryption settings
    ENCRYPTION_ENABLED = (
        os.getenv("MEMORY_ENCRYPTION_ENABLED", "true").lower() == "true"
    )
    ENCRYPTION_KEY = os.getenv("MEMORY_ENCRYPTION_KEY")  # Base64 encoded Fernet key

    # Memory limits
    CONVERSATION_MAX_TOKENS = int(os.getenv("CONVERSATION_MAX_TOKENS", "4000"))
    CONVERSATION_WINDOW_SIZE = int(os.getenv("CONVERSATION_WINDOW_SIZE", "20"))
    SUMMARY_TRIGGER_COUNT = int(os.getenv("SUMMARY_TRIGGER_COUNT", "10"))

    # Medical settings
    MEDICAL_ENTITY_TYPES = {
        "MEDICATION",
        "CONDITION",
        "SYMPTOM",
        "PROCEDURE",
        "ANATOMY",
        "PHYSICIAN",
        "FACILITY",
        "TEST_RESULT",
        "ALLERGY",
        "VACCINE",
        "VITAL_SIGN",
    }

    # Language settings
    DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en")
    SUPPORTED_LANGUAGES = [
        "en",
        "es",
        "fr",
        "de",
        "it",
        "pt",
        "ru",
        "ar",
        "zh",
        "ja",
        "ko",
        "hi",
        "ur",
        "bn",
        "pa",
        "ta",
        "te",
        "mr",
        "gu",
        "sw",
    ]

    @classmethod
    def get_encryption_key(cls) -> bytes:
        """Get or generate encryption key."""
        if cls.ENCRYPTION_KEY:
            return cls.ENCRYPTION_KEY.encode()
        else:
            # Generate new key
            key = Fernet.generate_key()
            print(f"Generated new encryption key: {key.decode()}")
            print("Save this key in MEMORY_ENCRYPTION_KEY environment variable")
            return key

    @classmethod
    def get_memory_store_config(cls) -> Dict[str, Any]:
        """Get DynamoDB memory store configuration."""
        return {
            "table_name": cls.DYNAMODB_TABLE_NAME,
            "region_name": cls.DYNAMODB_REGION,
            "ttl_days": cls.DYNAMODB_TTL_DAYS,
            "enable_versioning": True,
            "max_versions": cls.DYNAMODB_MAX_VERSIONS,
        }


class MemoryFactory:
    """Factory for creating configured memory instances."""

    @staticmethod
    def create_conversation_memory(
        session_id: str,
        user_id: str,
        memory_type: str = "buffer",
        **kwargs: Any,  # pylint: disable=unused-argument
    ) -> Any:
        """Create conversation memory instance."""
        # Create base store
        dynamo_store = DynamoDBMemoryStore(**MemoryConfig.get_memory_store_config())

        # Add encryption if enabled
        memory_store: Any
        if MemoryConfig.ENCRYPTION_ENABLED:
            memory_store = EncryptedMemoryStore(
                dynamo_store, MemoryConfig.get_encryption_key()
            )
        else:
            memory_store = dynamo_store

        # Set defaults
        kwargs["memory_store"] = memory_store
        kwargs["encrypt"] = False  # Already handled above
        kwargs["session_id"] = session_id
        kwargs["user_id"] = user_id

        # Create appropriate memory type
        if memory_type == "buffer":
            return ConversationBufferMemory(**kwargs)
        elif memory_type == "window":
            kwargs["window_size"] = kwargs.get(
                "window_size", MemoryConfig.CONVERSATION_WINDOW_SIZE
            )
            return ConversationBufferWindowMemory(**kwargs)
        elif memory_type == "token":
            kwargs["max_token_limit"] = kwargs.get(
                "max_token_limit", MemoryConfig.CONVERSATION_MAX_TOKENS
            )
            return ConversationTokenBufferMemory(**kwargs)
        else:
            raise ValueError(f"Unknown memory type: {memory_type}")

    @staticmethod
    def create_medical_memory(
        session_id: str, user_id: str, patient_id: str, llm: Any, **kwargs: Any
    ) -> Any:
        """Create medical context memory."""
        # Always use encryption for medical data
        dynamo_store = DynamoDBMemoryStore(**MemoryConfig.get_memory_store_config())
        memory_store = EncryptedMemoryStore(
            dynamo_store, MemoryConfig.get_encryption_key()
        )

        return MedicalContextMemory(
            patient_id=patient_id,
            session_id=session_id,
            user_id=user_id,
            llm=llm,
            memory_store=memory_store,
            **kwargs,
        )

    @staticmethod
    def create_emergency_memory(patient_id: str) -> Any:
        """Create emergency memory for rapid access."""
        # Emergency memory always encrypted
        dynamo_store = DynamoDBMemoryStore(**MemoryConfig.get_memory_store_config())
        memory_store = EncryptedMemoryStore(
            dynamo_store, MemoryConfig.get_encryption_key()
        )

        return EmergencyMemory(patient_id, memory_store)
