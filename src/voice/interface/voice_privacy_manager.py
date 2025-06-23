"""Voice Privacy Manager Module.

This module manages privacy aspects of voice authentication for the Haven Health Passport.
"""

import secrets
from datetime import datetime
from typing import Any, Dict

import numpy as np

from src.security.encryption import EncryptionService
from src.voice.interface.voice_authentication import VoicePrint


class VoicePrivacyManager:
    """Manages privacy aspects of voice authentication."""

    def __init__(self, encryption_service: EncryptionService):
        """Initialize the voice privacy manager.

        Args:
            encryption_service: Service for encrypting voice data
        """
        self.encryption_service = encryption_service

    async def encrypt_voice_print(self, voice_print: VoicePrint) -> Dict[str, Any]:
        """Encrypt voice print for storage."""
        # Serialize embedding
        embedding_bytes = voice_print.embedding.tobytes()

        # Encrypt
        encrypted = await self.encryption_service.encrypt(
            embedding_bytes, context={"user_id": voice_print.user_id}
        )

        return encrypted

    async def decrypt_voice_print(
        self, encrypted_data: Dict[str, Any], user_id: str
    ) -> np.ndarray:
        """Decrypt voice print from storage."""
        # Decrypt
        decrypted = await self.encryption_service.decrypt(
            encrypted_data, context={"user_id": user_id}
        )

        # Deserialize embedding
        embedding = np.frombuffer(decrypted, dtype=np.float32)

        return embedding

    def generate_consent_record(self, user_id: str) -> Dict[str, Any]:
        """Generate consent record for voice biometric collection."""
        return {
            "user_id": user_id,
            "consent_type": "voice_biometric",
            "timestamp": datetime.now().isoformat(),
            "purpose": "authentication",
            "retention_period_days": 365,
            "rights": ["access", "deletion", "portability", "correction"],
            "consent_id": secrets.token_urlsafe(16),
        }
