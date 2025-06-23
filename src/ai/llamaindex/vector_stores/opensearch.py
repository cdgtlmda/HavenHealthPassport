"""
OpenSearch Vector Store Implementation.

Primary vector store for production use with AWS OpenSearch.
Provides enterprise-grade search with medical optimizations.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    import boto3
except ImportError:
    boto3 = None

try:
    from llama_index.core.vector_stores import VectorStore  # type: ignore[attr-defined]
except ImportError:
    try:
        from llama_index.vector_stores import VectorStore
    except ImportError:
        VectorStore = None

try:
    from llama_index.vector_stores.opensearch import OpensearchVectorStore
except ImportError:
    OpensearchVectorStore = None

try:
    from opensearchpy import OpenSearch, RequestsHttpConnection
except ImportError:
    OpenSearch = None
    RequestsHttpConnection = None

try:
    from requests_aws4auth import AWS4Auth
except ImportError:
    AWS4Auth = None

from .base import BaseVectorStoreConfig, BaseVectorStoreFactory, SimilarityMetric

logger = logging.getLogger(__name__)


@dataclass
class OpenSearchConfig(BaseVectorStoreConfig):
    """Configuration for OpenSearch vector store."""

    # Connection settings
    endpoint: str = ""  # OpenSearch domain endpoint
    port: int = 443
    use_ssl: bool = True
    verify_certs: bool = True

    # AWS settings
    aws_region: str = "us-east-1"
    use_aws_auth: bool = True

    # Index settings
    index_name: str = "haven-health-medical-vectors"
    shards: int = 2
    replicas: int = 1

    # OpenSearch specific
    engine: str = "faiss"  # nmslib, faiss, or lucene
    space_type: str = "l2"  # l2, cosinesimil, or ip
    ef_construction: int = 512  # HNSW construction parameter
    m: int = 16  # HNSW M parameter

    # Medical optimizations
    enable_medical_analyzer: bool = True
    enable_synonym_expansion: bool = True
    custom_analyzers: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.custom_analyzers is None:
            self.custom_analyzers = self._get_medical_analyzers()

    def _get_medical_analyzers(self) -> Dict[str, Any]:
        """Get medical-specific analyzers for OpenSearch."""
        return {
            "medical_analyzer": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": [
                    "lowercase",
                    "medical_synonyms",
                    "medical_abbreviations",
                    "stop",
                ],
            },
            "medical_code_analyzer": {
                "type": "custom",
                "tokenizer": "keyword",
                "filter": ["uppercase"],
            },
        }


class OpenSearchFactory(BaseVectorStoreFactory):
    """Factory for creating OpenSearch vector stores."""

    def __init__(self) -> None:
        """Initialize OpenSearch factory."""
        self.client: Optional[OpenSearch] = None

    def create(self, config: Optional[BaseVectorStoreConfig] = None) -> VectorStore:
        """Create OpenSearch vector store instance."""
        if config is None:
            config = self.get_default_config()

        # Ensure config is OpenSearchConfig
        if not isinstance(config, OpenSearchConfig):
            raise ValueError(f"Expected OpenSearchConfig, got {type(config)}")

        if not self.validate_config(config):
            raise ValueError("Invalid OpenSearch configuration")

        # Create OpenSearch client
        client = self._create_client(config)

        # Ensure index exists with proper settings
        self._ensure_index(client, config)

        # Create vector store
        vector_store = OpensearchVectorStore(
            client=client,
            index_name=config.index_name,
            embedding_field="embedding_vector",
            text_field="content",
            metadata_field="metadata",
            dim=config.embedding_dimension,
            embedding_dict={
                "engine": config.engine,
                "space_type": config.space_type,
                "parameters": {
                    "ef_construction": config.ef_construction,
                    "m": config.m,
                },
            },
        )

        logger.info("Created OpenSearch vector store with index: %s", config.index_name)
        return vector_store

    def validate_config(self, config: BaseVectorStoreConfig) -> bool:
        """Validate OpenSearch configuration."""
        if not isinstance(config, OpenSearchConfig):
            return False

        if not config.endpoint:
            logger.error("OpenSearch endpoint not specified")
            return False

        if config.shards < 1 or config.replicas < 0:
            logger.error("Invalid shard/replica configuration")
            return False

        if config.embedding_dimension < 1:
            logger.error("Invalid embedding dimension")
            return False

        return True

    def get_default_config(self) -> OpenSearchConfig:
        """Get default OpenSearch configuration."""
        return OpenSearchConfig(
            endpoint=os.getenv("OPENSEARCH_ENDPOINT", ""),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            embedding_dimension=1536,  # Default for text-embedding-ada-002
            similarity_metric=SimilarityMetric.COSINE,
        )

    def _create_client(self, config: OpenSearchConfig) -> OpenSearch:
        """Create OpenSearch client with authentication."""
        if config.use_aws_auth:
            # Get AWS credentials
            credentials = boto3.Session().get_credentials()
            awsauth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                config.aws_region,
                "es",
                session_token=credentials.token,
            )

            client = OpenSearch(
                hosts=[{"host": config.endpoint, "port": config.port}],
                http_auth=awsauth,
                use_ssl=config.use_ssl,
                verify_certs=config.verify_certs,
                connection_class=RequestsHttpConnection,
                timeout=config.connection_timeout,
            )
        else:
            # Basic authentication
            client = OpenSearch(
                hosts=[{"host": config.endpoint, "port": config.port}],
                use_ssl=config.use_ssl,
                verify_certs=config.verify_certs,
                timeout=config.connection_timeout,
            )

        # Test connection
        info = client.info()
        logger.info("Connected to OpenSearch version: %s", info["version"]["number"])

        return client

    def _ensure_index(self, client: OpenSearch, config: OpenSearchConfig) -> None:
        """Ensure index exists with proper settings."""
        if client.indices.exists(index=config.index_name):
            logger.info("Index %s already exists", config.index_name)
            return

        # Create index with medical-optimized settings
        index_body = {
            "settings": {
                "number_of_shards": config.shards,
                "number_of_replicas": config.replicas,
                "index.knn": True,
                "analysis": {
                    "filter": {
                        "medical_synonyms": {
                            "type": "synonym",
                            "synonyms": [
                                "heart attack, myocardial infarction, MI",
                                "high blood pressure, hypertension, HTN",
                                "diabetes, diabetes mellitus, DM",
                                "shortness of breath, dyspnea, SOB",
                            ],
                        },
                        "medical_abbreviations": {
                            "type": "synonym",
                            "synonyms": [
                                "BP => blood pressure",
                                "HR => heart rate",
                                "RR => respiratory rate",
                                "T => temperature",
                            ],
                        },
                    },
                    "analyzer": (
                        config.custom_analyzers
                        if config.enable_medical_analyzer
                        else {}
                    ),
                },
            },
            "mappings": {
                "properties": {
                    "content": {
                        "type": "text",
                        "analyzer": (
                            "medical_analyzer"
                            if config.enable_medical_analyzer
                            else "standard"
                        ),
                    },
                    "embedding_vector": {
                        "type": "knn_vector",
                        "dimension": config.embedding_dimension,
                        "method": {
                            "name": "hnsw",
                            "space_type": config.space_type,
                            "engine": config.engine,
                            "parameters": {
                                "ef_construction": config.ef_construction,
                                "m": config.m,
                            },
                        },
                    },
                    "metadata": {"type": "object", "enabled": True},
                }
            },
        }

        client.indices.create(index=config.index_name, body=index_body)
        logger.info("Created index %s with medical optimizations", config.index_name)
