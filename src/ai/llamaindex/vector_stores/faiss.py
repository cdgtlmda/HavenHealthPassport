"""FAISS Vector Store Implementation.

Efficient similarity search for Haven Health Passport.
"""

from dataclasses import dataclass
from typing import Optional

try:
    import faiss
except ImportError:
    faiss = None

try:
    from llama_index.core.vector_stores import VectorStore  # type: ignore[attr-defined]
except ImportError:
    try:
        from llama_index.vector_stores import VectorStore
    except ImportError:
        VectorStore = None

try:
    from llama_index.vector_stores.faiss import FaissVectorStore
except ImportError:
    FaissVectorStore = None

from .base import BaseVectorStoreConfig, BaseVectorStoreFactory


@dataclass
class FAISSConfig(BaseVectorStoreConfig):
    """Configuration for FAISS vector store."""

    index_type: str = "IndexFlatL2"  # or IndexIVFFlat, IndexHNSW
    nlist: int = 100  # For IVF indices
    persist_path: Optional[str] = "./faiss_index"


class FAISSFactory(BaseVectorStoreFactory):
    """Factory for creating FAISS vector stores."""

    def create(self, config: Optional[BaseVectorStoreConfig] = None) -> VectorStore:
        """Create FAISS vector store instance."""
        if config is None:
            config = self.get_default_config()

        # Ensure config is FAISSConfig
        if not isinstance(config, FAISSConfig):
            raise ValueError(f"Expected FAISSConfig, got {type(config)}")

        # Create FAISS index based on type
        if config.index_type == "IndexFlatL2":
            faiss_index = faiss.IndexFlatL2(config.embedding_dimension)
        elif config.index_type == "IndexIVFFlat":
            quantizer = faiss.IndexFlatL2(config.embedding_dimension)
            faiss_index = faiss.IndexIVFFlat(
                quantizer, config.embedding_dimension, config.nlist
            )
        else:
            faiss_index = faiss.IndexFlatL2(config.embedding_dimension)

        return FaissVectorStore(faiss_index=faiss_index)

    def validate_config(self, config: BaseVectorStoreConfig) -> bool:
        """Validate FAISS configuration."""
        if not isinstance(config, FAISSConfig):
            return False
        return config.embedding_dimension > 0

    def get_default_config(self) -> FAISSConfig:
        """Get default FAISS configuration."""
        return FAISSConfig()
