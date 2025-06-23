"""Privacy management module."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class ConsentType(Enum):
    """Types of user consent."""

    VOICE_RECORDING = "voice_recording"
    VOICE_BIOMETRICS = "voice_biometrics"
    DATA_SHARING = "data_sharing"
    ANALYTICS = "analytics"


class DataCategory(Enum):
    """Categories of data for privacy management."""

    PERSONAL = "personal"
    MEDICAL = "medical"
    BIOMETRIC = "biometric"
    BEHAVIORAL = "behavioral"


@dataclass
class PrivacySettings:
    """User privacy settings."""

    user_id: str
    consents: Dict[ConsentType, bool]
    data_retention_days: int = 365
    allow_anonymization: bool = True
    share_with_researchers: bool = False
