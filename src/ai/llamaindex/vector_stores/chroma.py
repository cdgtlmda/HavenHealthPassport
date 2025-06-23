"""Chroma Vector Store Implementation.

Local development vector store for Haven Health Passport.
"""

from dataclasses import dataclass
from typing import Optional

try:
    import chromadb
except ImportError:
    chromadb = None

try:
    from llama_index.core.vector_stores import VectorStore  # type: ignore[attr-defined]
except ImportError:
    try:
        from llama_index.vector_stores import VectorStore
    except ImportError:
        VectorStore = None

try:
    from llama_index.vector_stores.chroma import ChromaVectorStore
except ImportError:
    ChromaVectorStore = None

from .base import BaseVectorStoreConfig, BaseVectorStoreFactory


@dataclass
class ChromaConfig(BaseVectorStoreConfig):
    """Configuration for Chroma vector store."""

    persist_dir: str = "./chroma_db"
    collection_name: str = "haven_health_medical"


class ChromaFactory(BaseVectorStoreFactory):
    """Factory for creating Chroma vector stores."""

    def create(self, config: Optional[BaseVectorStoreConfig] = None) -> VectorStore:
        """Create Chroma vector store instance."""
        if config is None:
            config = self.get_default_config()

        # Ensure config is ChromaConfig
        if not isinstance(config, ChromaConfig):
            raise ValueError(f"Expected ChromaConfig, got {type(config)}")

        chroma_client = chromadb.PersistentClient(path=config.persist_dir)
        chroma_collection = chroma_client.get_or_create_collection(
            config.collection_name
        )

        return ChromaVectorStore(chroma_collection=chroma_collection)

    def validate_config(self, config: BaseVectorStoreConfig) -> bool:
        """Validate Chroma configuration."""
        if not isinstance(config, ChromaConfig):
            return False
        return True

    def get_default_config(self) -> ChromaConfig:
        """Get default Chroma configuration."""
        return ChromaConfig()
