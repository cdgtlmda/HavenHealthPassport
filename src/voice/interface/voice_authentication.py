"""
Voice Authentication Module.

This module implements voice biometric authentication for the Haven Health Passport system,
providing secure voice-based user identification and verification using speaker recognition,
voice print analysis, and anti-spoofing measures.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


class AuthenticationMethod(Enum):
    """Types of voice authentication methods."""

    PASSPHRASE = "passphrase"  # Fixed passphrase
    TEXT_DEPENDENT = "text_dependent"  # Specific prompted text
    TEXT_INDEPENDENT = "text_independent"  # Any speech
    CHALLENGE_RESPONSE = "challenge_response"  # Dynamic challenge
    CONTINUOUS = "continuous"  # Ongoing verification
    MULTI_FACTOR = "multi_factor"  # Combined with other factors


class EnrollmentStatus(Enum):
    """Voice enrollment status."""

    NOT_ENROLLED = "not_enrolled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    LOCKED = "locked"


class AuthenticationResult(Enum):
    """Authentication result types."""

    SUCCESS = "success"
    FAILURE = "failure"
    INCONCLUSIVE = "inconclusive"
    SPOOFING_DETECTED = "spoofing_detected"
    QUALITY_INSUFFICIENT = "quality_insufficient"
    NOT_ENROLLED = "not_enrolled"
    ACCOUNT_LOCKED = "account_locked"
    EXPIRED = "expired"


class LevelOfAssurance(Enum):
    """Authentication assurance levels."""

    LOW = 1  # Basic voice match
    MEDIUM = 2  # Voice match + quality checks
    HIGH = 3  # Voice match + liveness + anti-spoofing
    VERY_HIGH = 4  # All checks + behavioral analysis


@dataclass
class VoicePrint:
    """Represents a user's voice biometric template."""

    user_id: str
    print_id: str
    embedding: np.ndarray  # Voice embedding vector
    method: AuthenticationMethod
    passphrase: Optional[str] = None  # For passphrase method
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    quality_score: float = 0.0
    sample_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding sensitive data)."""
        return {
            "user_id": self.user_id,
            "print_id": self.print_id,
            "method": self.method.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "quality_score": self.quality_score,
        }
