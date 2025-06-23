"""LlamaIndex Embeddings Module for Haven Health Passport.

Provides embedding models optimized for medical document processing
and multilingual healthcare content.
"""

from .base import BaseEmbeddingConfig, BaseHavenEmbedding, EmbeddingProvider
from .bedrock import BedrockEmbeddings, TitanEmbeddingModel
from .config import DEFAULT_EMBEDDING_CONFIG, EMBEDDING_CONFIGS, get_embedding_config
from .custom import (
    CustomEmbeddingConfig,
    DomainAdaptiveEmbeddings,
    HybridCustomEmbeddings,
    TransformerCustomEmbeddings,
    Word2VecCustomEmbeddings,
    create_custom_embeddings,
)
from .factory import EmbeddingFactory, get_embedding_model
from .medical import MedicalEmbeddingConfig, MedicalEmbeddings
from .openai import OpenAIEmbeddings

__all__ = [
    "BaseEmbeddingConfig",
    "BaseHavenEmbedding",
    "EmbeddingProvider",
    "BedrockEmbeddings",
    "TitanEmbeddingModel",
    "OpenAIEmbeddings",
    "MedicalEmbeddings",
    "MedicalEmbeddingConfig",
    "CustomEmbeddingConfig",
    "TransformerCustomEmbeddings",
    "Word2VecCustomEmbeddings",
    "HybridCustomEmbeddings",
    "DomainAdaptiveEmbeddings",
    "create_custom_embeddings",
    "EmbeddingFactory",
    "get_embedding_model",
    "EMBEDDING_CONFIGS",
    "DEFAULT_EMBEDDING_CONFIG",
    "get_embedding_config",
]
