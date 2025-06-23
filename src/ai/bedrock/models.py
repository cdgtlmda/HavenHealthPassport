"""Model definitions for Bedrock access control."""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ModelAccessLevel(str, Enum):
    """Access levels for Bedrock models."""

    NONE = "none"
    READ_ONLY = "read_only"
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"
    UNLIMITED = "unlimited"


class ModelCategory(str, Enum):
    """Categories of AI models."""

    GENERAL = "general"
    MEDICAL = "medical"
    TRANSLATION = "translation"
    EMBEDDING = "embedding"
    VISION = "vision"
    CODE = "code"


class ModelUsageType(str, Enum):
    """Types of model usage."""

    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    EXTRACTION = "extraction"
    GENERATION = "generation"
    EMBEDDING = "embedding"
    CLASSIFICATION = "classification"
    QA = "question_answering"


@dataclass
class ModelInfo:
    """Information about a Bedrock model."""

    model_id: str
    name: str
    provider: str
    category: ModelCategory
    supported_usage_types: List[ModelUsageType]
    max_tokens: int
    cost_per_1k_tokens: float
    is_medical_specialized: bool = False
    requires_approval: bool = False
    regions: Optional[List[str]] = None

    def __post_init__(self) -> None:
        """Initialize default regions if not provided."""
        if self.regions is None:
            self.regions = ["us-east-1"]
