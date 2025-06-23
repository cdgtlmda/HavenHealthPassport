"""
OpenSearch Connector Implementation.

Main connector class for Haven Health Passport OpenSearch integration.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast

import boto3
from llama_index.core import Document

try:
    from llama_index.vector_stores.opensearch import OpensearchVectorStore
except ImportError:
    OpensearchVectorStore = None

try:
    from opensearchpy import OpenSearch, RequestsHttpConnection, exceptions
except ImportError:
    OpenSearch = None
    RequestsHttpConnection = None
    exceptions = None

try:
    from opensearchpy.helpers import bulk
except ImportError:
    bulk = None

try:
    from requests_aws4auth import AWS4Auth
except ImportError:
    AWS4Auth = None

from .analyzers import MedicalAnalyzerConfig
from .config import IndexConfig, OpenSearchConnectionConfig, OpenSearchEnvironment

logger = logging.getLogger(__name__)


class OpenSearchConnector:
    """Main connector for OpenSearch operations."""

    def __init__(
        self,
        config: OpenSearchConnectionConfig,
        environment: OpenSearchEnvironment = OpenSearchEnvironment.DEVELOPMENT,
    ):
        """Initialize OpenSearch connector."""
        self.config = config
        self.environment = environment
        self.client: Optional[OpenSearch] = None
        self._vector_store: Optional[OpensearchVectorStore] = None
        self._analyzer_config = MedicalAnalyzerConfig()

    def connect(self) -> None:
        """Establish connection to OpenSearch."""
        logger.info("Connecting to OpenSearch (%s)...", self.environment.value)

        if self.config.use_aws_auth:
            # AWS authentication
            credentials = (
                boto3.Session(profile_name=self.config.aws_profile).get_credentials()
                if self.config.aws_profile
                else boto3.Session().get_credentials()
            )

            awsauth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                self.config.aws_region,
                "es",
                session_token=credentials.token,
            )

            self.client = OpenSearch(
                hosts=[{"host": self.config.endpoint, "port": self.config.port}],
                http_auth=awsauth,
                use_ssl=self.config.use_ssl,
                verify_certs=self.config.verify_certs,
                connection_class=RequestsHttpConnection,
                timeout=self.config.connection_timeout,
                max_retries=self.config.max_retries,
                retry_on_timeout=self.config.retry_on_timeout,
            )
        else:
            # Basic connection
            self.client = OpenSearch(
                hosts=[{"host": self.config.endpoint, "port": self.config.port}],
                use_ssl=self.config.use_ssl,
                verify_certs=self.config.verify_certs,
                timeout=self.config.connection_timeout,
            )

        # Verify connection
        info = self.client.info()
        logger.info("Connected to OpenSearch version: %s", info["version"]["number"])

    def create_index(self, index_config: IndexConfig) -> bool:
        """Create an index with medical-optimized settings."""
        if not self.client:
            raise RuntimeError("Not connected to OpenSearch")

        index_name = index_config.name

        # Check if index exists
        if self.client.indices.exists(index=index_name):
            logger.warning("Index %s already exists", index_name)
            return False
        # Get analyzer configuration
        analyzer_config = self._analyzer_config.get_analyzer_config()

        # Build index body
        index_body = {
            "settings": {
                **index_config.get_index_settings(),
                "analysis": analyzer_config,
            },
            "mappings": {
                "properties": {
                    "content": {
                        "type": "text",
                        "analyzer": (
                            "medical_standard"
                            if index_config.enable_medical_analyzers
                            else "standard"
                        ),
                    },
                    "embedding_vector": {
                        "type": "knn_vector",
                        "dimension": index_config.vector_dimension,
                        "method": {
                            "name": "hnsw",
                            "space_type": index_config.vector_similarity,
                            "engine": "nmslib",
                            "parameters": {"ef_construction": 512, "m": 16},
                        },
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "document_type": {"type": "keyword"},
                            "specialty": {"type": "keyword"},
                            "icd_codes": {"type": "keyword"},
                            "language": {"type": "keyword"},
                            "patient_id": {"type": "keyword"},
                            "date_created": {"type": "date"},
                            "is_encrypted": {"type": "boolean"},
                            "compliance_level": {"type": "keyword"},
                        },
                    },
                    "timestamp": {"type": "date"},
                }
            },
        }

        # Add custom mappings if provided
        if index_config.custom_mappings:
            index_body["mappings"]["properties"].update(index_config.custom_mappings)
        # Create the index
        try:
            self.client.indices.create(index=index_name, body=index_body)
            logger.info("Created index %s with medical optimizations", index_name)
            return True
        except Exception as e:
            logger.error("Failed to create index %s: %s", index_name, e)
            raise

    def delete_index(self, index_name: str) -> bool:
        """Delete an index."""
        if not self.client:
            raise RuntimeError("Not connected to OpenSearch")

        try:
            self.client.indices.delete(index=index_name)
            logger.info("Deleted index %s", index_name)
            return True
        except exceptions.NotFoundError:
            logger.warning("Index %s not found", index_name)
            return False
        except Exception as e:
            logger.error("Failed to delete index %s: %s", index_name, e)
            raise

    def get_vector_store(self, index_name: str) -> OpensearchVectorStore:
        """Get vector store for the specified index."""
        if not self.client:
            raise RuntimeError("Not connected to OpenSearch")

        if (
            not self._vector_store
            or getattr(self._vector_store, "index_name", None) != index_name
        ):
            self._vector_store = OpensearchVectorStore(
                client=self.client,
                index_name=index_name,
                embedding_field="embedding_vector",
                text_field="content",
                metadata_field="metadata",
            )

        return self._vector_store

    def bulk_index_documents(
        self,
        documents: List[Document],
        index_name: str,
        batch_size: Optional[int] = None,
    ) -> Tuple[int, List[Dict]]:
        """Bulk index documents with medical metadata."""
        if not self.client:
            raise RuntimeError("Not connected to OpenSearch")

        batch_size = batch_size or self.config.batch_size
        indexed_count = 0
        errors = []

        # Process documents in batches
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            actions = []

            for doc in batch:
                # Prepare document for indexing
                doc_dict = {
                    "_index": index_name,
                    "_source": {
                        "content": doc.text,
                        "metadata": doc.metadata or {},
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                }

                # Add embedding if available
                if hasattr(doc, "embedding") and doc.embedding is not None:
                    source = doc_dict["_source"]
                    if isinstance(source, dict):
                        source["embedding_vector"] = doc.embedding

                actions.append(doc_dict)

            # Bulk index
            try:
                success, failed = bulk(self.client, actions)
                indexed_count += success

                if failed:
                    errors.extend(failed)
                    logger.warning("Failed to index %d documents in batch", len(failed))

            except (ValueError, TypeError) as e:
                logger.error("Bulk indexing error: %s", e)
                errors.append({"error": str(e), "batch_start": i})

        logger.info("Indexed %d documents to %s", indexed_count, index_name)
        return indexed_count, errors

    def search(
        self,
        index_name: str,
        query: str,
        size: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        highlight: bool = True,
    ) -> Dict[str, Any]:
        """Search documents with medical query optimization."""
        if not self.client:
            raise RuntimeError("Not connected to OpenSearch")

        # Build query
        query_body: Dict[str, Any] = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": [
                                    "content^2",
                                    "metadata.document_type",
                                    "metadata.specialty",
                                ],
                                "type": "best_fields",
                                "analyzer": "medical_standard",
                            }
                        }
                    ]
                }
            },
            "size": size,
        }

        # Add filters if provided
        if filters:
            bool_query = query_body["query"]["bool"]
            if isinstance(bool_query, dict):
                bool_query["filter"] = []
                for field, value in filters.items():
                    bool_query["filter"].append({"term": {field: value}})

        # Add highlighting
        if highlight:
            query_body["highlight"] = {
                "fields": {"content": {"fragment_size": 150, "number_of_fragments": 3}}
            }

        # Execute search
        try:
            response = self.client.search(index=index_name, body=query_body)
            return cast(Dict[str, Any], response)
        except Exception as e:
            logger.error("Search error: %s", e)
            raise

    def vector_search(
        self,
        index_name: str,
        embedding_vector: List[float],
        size: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform vector similarity search."""
        if not self.client:
            raise RuntimeError("Not connected to OpenSearch")

        # Build k-NN query
        query_body = {
            "size": size,
            "query": {
                "knn": {"embedding_vector": {"vector": embedding_vector, "k": size}}
            },
        }

        # Add filters if provided
        if filters:
            query_body["query"] = {
                "bool": {
                    "must": [query_body["query"]],
                    "filter": [{"term": {k: v}} for k, v in filters.items()],
                }
            }

        # Execute search
        try:
            response = self.client.search(index=index_name, body=query_body)
            return cast(Dict[str, Any], response)
        except Exception as e:
            logger.error("Vector search error: %s", e)
            raise

    def get_index_stats(self, index_name: str) -> Dict[str, Any]:
        """Get statistics for an index."""
        if not self.client:
            raise RuntimeError("Not connected to OpenSearch")

        try:
            stats = self.client.indices.stats(index=index_name)
            return cast(Dict[str, Any], stats)
        except Exception as e:
            logger.error("Failed to get index stats: %s", e)
            raise

    def close(self) -> None:
        """Close the connection."""
        if self.client:
            self.client.close()
            self.client = None
            logger.info("Closed OpenSearch connection")
