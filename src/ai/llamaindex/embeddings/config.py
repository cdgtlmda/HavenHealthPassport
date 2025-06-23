"""Embedding Configuration Presets.

Defines optimized embedding configurations for different use cases
in the Haven Health Passport system.
"""

from dataclasses import asdict
from typing import Any, Dict

from .base import BaseEmbeddingConfig, EmbeddingProvider
from .medical import MedicalEmbeddingConfig

# General-purpose embedding configuration
GENERAL_EMBEDDING_CONFIG = BaseEmbeddingConfig(
    provider=EmbeddingProvider.BEDROCK,
    model_name="amazon.titan-embed-text-v2:0",
    dimension=1024,
    batch_size=10,
    normalize=True,
    cache_embeddings=True,
    metadata={"use_case": "general", "description": "General-purpose text embeddings"},
)

# Medical document embedding configuration
MEDICAL_EMBEDDING_CONFIG = MedicalEmbeddingConfig(
    provider=EmbeddingProvider.MEDICAL,
    model_name="haven-medical-embed",
    dimension=768,
    batch_size=32,
    normalize=True,
    cache_embeddings=True,
    use_medical_tokenizer=True,
    preserve_medical_terms=True,
    use_cui_augmentation=True,
    use_semantic_types=True,
    language_specific=False,
    metadata={
        "use_case": "medical",
        "description": "Medical document embeddings with CUI augmentation",
    },
)

# Multilingual medical embedding configuration
MULTILINGUAL_MEDICAL_CONFIG = MedicalEmbeddingConfig(
    provider=EmbeddingProvider.MEDICAL,
    model_name="haven-multilingual-medical",
    dimension=768,
    batch_size=16,
    normalize=True,
    cache_embeddings=True,
    use_medical_tokenizer=True,
    preserve_medical_terms=True,
    use_cui_augmentation=True,
    use_semantic_types=True,
    language_specific=True,
    metadata={
        "use_case": "multilingual_medical",
        "description": "Multilingual medical embeddings for 50+ languages",
        "supported_languages": [
            "en",
            "es",
            "fr",
            "ar",
            "zh",
            "hi",
            "pt",
            "ru",
            "de",
            "ja",
        ],
    },
)

# High-performance embedding configuration
HIGH_PERFORMANCE_CONFIG = BaseEmbeddingConfig(
    provider=EmbeddingProvider.BEDROCK,
    model_name="amazon.titan-embed-g1-text-02",
    dimension=384,  # Smaller dimension for speed
    batch_size=50,
    normalize=True,
    cache_embeddings=True,
    metadata={
        "use_case": "high_performance",
        "description": "Optimized for speed with smaller dimensions",
    },
)

# Cost-optimized embedding configuration
COST_OPTIMIZED_CONFIG = BaseEmbeddingConfig(
    provider=EmbeddingProvider.BEDROCK,
    model_name="amazon.titan-embed-g1-text-02",
    dimension=384,
    batch_size=100,  # Large batches to reduce API calls
    normalize=True,
    cache_embeddings=True,
    metadata={
        "use_case": "cost_optimized",
        "description": "Optimized for low cost with caching and batching",
    },
)

# Research-grade embedding configuration
RESEARCH_CONFIG = BaseEmbeddingConfig(
    provider=EmbeddingProvider.BEDROCK,
    model_name="amazon.titan-embed-text-v2:0",
    dimension=1024,
    batch_size=1,  # Process one at a time for accuracy
    normalize=False,  # Keep raw embeddings
    cache_embeddings=False,  # Always fresh embeddings
    metadata={
        "use_case": "research",
        "description": "High-accuracy embeddings for research",
    },
)

# Multimodal embedding configuration
MULTIMODAL_CONFIG = BaseEmbeddingConfig(
    provider=EmbeddingProvider.BEDROCK,
    model_name="amazon.titan-embed-image-v1",
    dimension=1024,
    batch_size=5,
    normalize=True,
    cache_embeddings=True,
    metadata={
        "use_case": "multimodal",
        "description": "Text and image embeddings",
        "supports": ["text", "image", "text+image"],
    },
)

# Emergency response embedding configuration
EMERGENCY_CONFIG = BaseEmbeddingConfig(
    provider=EmbeddingProvider.BEDROCK,
    model_name="amazon.titan-embed-text-v2:0",
    dimension=1024,
    batch_size=1,
    max_retries=5,  # More retries for critical operations
    timeout=10.0,  # Shorter timeout for urgency
    normalize=True,
    cache_embeddings=False,  # Always fresh for emergency
    metadata={
        "use_case": "emergency",
        "description": "Optimized for emergency medical situations",
        "priority": "critical",
    },
)

# All predefined configurations
EMBEDDING_CONFIGS: Dict[str, BaseEmbeddingConfig] = {
    "general": GENERAL_EMBEDDING_CONFIG,
    "medical": MEDICAL_EMBEDDING_CONFIG,
    "multilingual_medical": MULTILINGUAL_MEDICAL_CONFIG,
    "high_performance": HIGH_PERFORMANCE_CONFIG,
    "cost_optimized": COST_OPTIMIZED_CONFIG,
    "research": RESEARCH_CONFIG,
    "multimodal": MULTIMODAL_CONFIG,
    "emergency": EMERGENCY_CONFIG,
}

# Default configuration
DEFAULT_EMBEDDING_CONFIG = GENERAL_EMBEDDING_CONFIG


def get_embedding_config(
    use_case: str = "general", **overrides: Any
) -> BaseEmbeddingConfig:
    """Get embedding configuration for use case.

    Args:
        use_case: Name of the use case
        **overrides: Override specific config values

    Returns:
        Embedding configuration
    """
    if use_case not in EMBEDDING_CONFIGS:
        raise ValueError(
            f"Unknown use case '{use_case}'. "
            f"Available: {list(EMBEDDING_CONFIGS.keys())}"
        )

    # Get base config
    base_config = EMBEDDING_CONFIGS[use_case]

    # Apply overrides if any
    if overrides:
        config_dict = asdict(base_config)
        config_dict.update(overrides)

        # Determine config class
        if use_case in ["medical", "multilingual_medical"]:
            return MedicalEmbeddingConfig(**config_dict)
        else:
            return BaseEmbeddingConfig(**config_dict)

    return base_config


def get_recommended_config(
    document_type: str, language: str = "en", urgency: int = 1
) -> BaseEmbeddingConfig:
    """Get recommended config based on document characteristics.

    Args:
        document_type: Type of document (medical, legal, general)
        language: Language code
        urgency: 1-5 urgency scale

    Returns:
        Recommended configuration
    """
    # Emergency situations
    if urgency >= 4:
        return EMERGENCY_CONFIG

    # Medical documents
    if document_type == "medical":
        if language != "en":
            return MULTILINGUAL_MEDICAL_CONFIG
        else:
            return MEDICAL_EMBEDDING_CONFIG

    # General documents
    return GENERAL_EMBEDDING_CONFIG
