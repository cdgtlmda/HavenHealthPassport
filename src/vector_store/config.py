"""Configuration for vector store module."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class VectorStoreConfig:
    """Configuration for vector store operations."""

    # Model settings
    embedding_model: str = "medical-bert-embeddings"
    embedding_dimension: int = 768

    # Storage settings
    persist_path: Optional[Path] = None
    enable_cache: bool = True
    cache_size: int = 10000

    # Search settings
    default_k: int = 10
    similarity_threshold: float = 0.7

    # Performance settings
    batch_size: int = 32
    max_vectors_in_memory: int = 1000000

    # Security settings
    enable_encryption: bool = True
    audit_access: bool = True
