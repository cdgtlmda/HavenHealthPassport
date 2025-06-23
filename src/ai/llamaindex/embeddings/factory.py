"""Embedding Model Factory.

Provides factory methods for creating embedding models with
appropriate configurations for different use cases.
"""

import logging
import os
from typing import Any, Optional, Union

from .base import BaseEmbeddingConfig, BaseHavenEmbedding, EmbeddingProvider
from .bedrock import BedrockEmbeddings, BedrockMultimodalEmbeddings, TitanEmbeddingModel
from .custom import (
    CustomEmbeddingConfig,
    create_custom_embeddings,
)
from .medical import (
    MedicalEmbeddingConfig,
    MedicalEmbeddings,
    MultilingualMedicalEmbeddings,
)
from .openai import OpenAIEmbeddingModel, OpenAIEmbeddings

logger = logging.getLogger(__name__)


class EmbeddingFactory:
    """Factory for creating embedding models."""

    @staticmethod
    def create_embedding_model(
        provider: Union[str, EmbeddingProvider],
        config: Optional[BaseEmbeddingConfig] = None,
        **kwargs: Any,
    ) -> BaseHavenEmbedding:
        """Create an embedding model.

        Args:
            provider: Embedding provider
            config: Optional configuration
            **kwargs: Provider-specific arguments

        Returns:
            Configured embedding model
        """
        # Convert string to enum if needed
        if isinstance(provider, str):
            provider = EmbeddingProvider(provider)

        if provider == EmbeddingProvider.BEDROCK:
            return EmbeddingFactory._create_bedrock_embeddings(config, **kwargs)

        elif provider == EmbeddingProvider.OPENAI:
            return EmbeddingFactory._create_openai_embeddings(config, **kwargs)

        elif provider == EmbeddingProvider.MEDICAL:
            # Convert config to MedicalEmbeddingConfig if needed
            if config and not isinstance(config, MedicalEmbeddingConfig):
                medical_config = MedicalEmbeddingConfig(
                    provider=provider,
                    model_name=config.model_name,
                    dimension=config.dimension,
                    batch_size=config.batch_size,
                    normalize=config.normalize,
                )
            else:
                medical_config = config  # type: ignore[assignment]
            return EmbeddingFactory._create_medical_embeddings(medical_config, **kwargs)

        elif provider == EmbeddingProvider.CUSTOM:
            # Convert config to CustomEmbeddingConfig if needed
            if config and not isinstance(config, CustomEmbeddingConfig):
                custom_config = CustomEmbeddingConfig(
                    provider=provider,
                    model_name=config.model_name,
                    dimension=config.dimension,
                    batch_size=config.batch_size,
                    normalize=config.normalize,
                )
            else:
                custom_config = config  # type: ignore[assignment]
            return EmbeddingFactory._create_custom_embeddings(custom_config, **kwargs)

        else:
            raise ValueError(f"Unknown embedding provider: {provider}")

    @staticmethod
    def _create_bedrock_embeddings(
        config: Optional[BaseEmbeddingConfig] = None, **kwargs: Any
    ) -> BedrockEmbeddings:
        """Create Bedrock embeddings."""
        # Get model from kwargs or environment
        model_id = kwargs.get(
            "model_id",
            os.getenv(
                "BEDROCK_EMBEDDING_MODEL", TitanEmbeddingModel.TITAN_EMBED_TEXT_V2.value
            ),
        )

        # Get region
        region = kwargs.get("region_name", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

        logger.info("Creating Bedrock embeddings with model: %s", model_id)

        return BedrockEmbeddings(
            config=config, model_id=model_id, region_name=region, **kwargs
        )

    @staticmethod
    def _create_openai_embeddings(
        config: Optional[BaseEmbeddingConfig] = None, **kwargs: Any
    ) -> OpenAIEmbeddings:
        """Create OpenAI embeddings."""
        # Get model from kwargs or environment
        model = kwargs.get(
            "model",
            os.getenv(
                "OPENAI_EMBEDDING_MODEL",
                OpenAIEmbeddingModel.TEXT_EMBEDDING_3_SMALL.value,
            ),
        )

        # Get API key
        api_key = kwargs.get("api_key", os.getenv("OPENAI_API_KEY"))

        if not api_key:
            logger.warning("No OpenAI API key provided - using mock mode")

        logger.info("Creating OpenAI embeddings with model: %s", model)

        return OpenAIEmbeddings(config=config, model=model, api_key=api_key, **kwargs)

    @staticmethod
    def _create_medical_embeddings(
        config: Optional[MedicalEmbeddingConfig] = None, **kwargs: Any
    ) -> MedicalEmbeddings:
        """Create medical embeddings."""
        # Check if multilingual support is needed
        multilingual = kwargs.pop("multilingual", False)

        if multilingual:
            logger.info("Creating multilingual medical embeddings")
            return MultilingualMedicalEmbeddings(config=config, **kwargs)
        else:
            logger.info("Creating medical embeddings")
            return MedicalEmbeddings(config=config, **kwargs)

    @staticmethod
    def _create_custom_embeddings(
        config: Optional[CustomEmbeddingConfig] = None, **kwargs: Any
    ) -> BaseHavenEmbedding:
        """Create custom embeddings."""
        # Get embedding type
        embedding_type = kwargs.pop("embedding_type", "transformer")

        logger.info("Creating custom embeddings of type: %s", embedding_type)

        return create_custom_embeddings(
            embedding_type=embedding_type, config=config, **kwargs
        )

    @staticmethod
    def create_multimodal_embeddings(
        config: Optional[BaseEmbeddingConfig] = None, **kwargs: Any
    ) -> BedrockMultimodalEmbeddings:
        """Create multimodal embeddings for text and images."""
        logger.info("Creating multimodal embeddings")
        return BedrockMultimodalEmbeddings(config=config, **kwargs)


def get_embedding_model(use_case: str = "general", **kwargs: Any) -> BaseHavenEmbedding:
    """Get embedding model for specific use case.

    Args:
        use_case: One of 'general', 'medical', 'multilingual', 'multimodal'
        **kwargs: Additional arguments

    Returns:
        Configured embedding model
    """
    use_case_configs = {
        "general": {
            "provider": EmbeddingProvider.BEDROCK,
            "model_id": TitanEmbeddingModel.TITAN_EMBED_TEXT_V2,
        },
        "medical": {
            "provider": EmbeddingProvider.MEDICAL,
            "use_medical_tokenizer": True,
            "use_cui_augmentation": True,
        },
        "multilingual": {
            "provider": EmbeddingProvider.MEDICAL,
            "multilingual": True,
            "language_specific": True,
        },
        "multimodal": {
            "provider": EmbeddingProvider.BEDROCK,
            "model_id": TitanEmbeddingModel.TITAN_EMBED_IMAGE_V1,
        },
        "cost_optimized": {
            "provider": EmbeddingProvider.BEDROCK,
            "model_id": TitanEmbeddingModel.TITAN_EMBED_G1_TEXT,  # Smaller dimension
        },
        "custom_transformer": {
            "provider": EmbeddingProvider.CUSTOM,
            "embedding_type": "transformer",
            "dimension": 768,
        },
        "custom_word2vec": {
            "provider": EmbeddingProvider.CUSTOM,
            "embedding_type": "word2vec",
            "dimension": 300,
        },
        "custom_hybrid": {
            "provider": EmbeddingProvider.CUSTOM,
            "embedding_type": "hybrid",
            "dimension": 512,
        },
        "custom_domain_adaptive": {
            "provider": EmbeddingProvider.CUSTOM,
            "embedding_type": "domain_adaptive",
            "dimension": 768,
        },
    }

    if use_case not in use_case_configs:
        raise ValueError(
            f"Unknown use case: {use_case}. Choose from: {list(use_case_configs.keys())}"
        )

    # Get use case config
    use_case_config = use_case_configs[use_case]

    # Merge with provided kwargs
    merged_kwargs = {**use_case_config, **kwargs}  # type: ignore[dict-item]

    # Extract provider
    provider = merged_kwargs.pop("provider")

    # Handle special cases
    if use_case == "multimodal":
        return EmbeddingFactory.create_multimodal_embeddings(**merged_kwargs)

    return EmbeddingFactory.create_embedding_model(provider, **merged_kwargs)
