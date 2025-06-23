"""
PostgreSQL + pgvector Store Implementation.

Hybrid SQL/vector storage for Haven Health Passport.
"""

from dataclasses import dataclass
from typing import Optional

try:
    from llama_index.core.vector_stores import VectorStore  # type: ignore[attr-defined]
except ImportError:
    try:
        from llama_index.vector_stores import VectorStore
    except ImportError:
        VectorStore = None

try:
    from llama_index.vector_stores.postgres import PGVectorStore
except ImportError:
    PGVectorStore = None

from .base import BaseVectorStoreConfig, BaseVectorStoreFactory


@dataclass
class PostgresConfig(BaseVectorStoreConfig):
    """Configuration for PostgreSQL vector store."""

    connection_string: str = ""
    table_name: str = "haven_health_embeddings"
    embed_dim: int = 1536
    hybrid_search: bool = True
    text_search_config: str = "english"


class PostgresFactory(BaseVectorStoreFactory):
    """Factory for creating PostgreSQL vector stores."""

    def create(self, config: Optional[BaseVectorStoreConfig] = None) -> VectorStore:
        """Create PostgreSQL vector store instance."""
        if config is None:
            config = self.get_default_config()

        # Ensure config is PostgresConfig
        if not isinstance(config, PostgresConfig):
            raise ValueError(f"Expected PostgresConfig, got {type(config)}")

        return PGVectorStore.from_params(
            connection_string=config.connection_string,
            table_name=config.table_name,
            embed_dim=config.embed_dim,
            hybrid_search=config.hybrid_search,
            text_search_config=config.text_search_config,
        )

    def validate_config(self, config: BaseVectorStoreConfig) -> bool:
        """Validate PostgreSQL configuration."""
        if not isinstance(config, PostgresConfig):
            return False
        return bool(config.connection_string)

    def get_default_config(self) -> PostgresConfig:
        """Get default PostgreSQL configuration."""
        return PostgresConfig(
            connection_string="postgresql://user:password@localhost:5432/haven_health"
        )
