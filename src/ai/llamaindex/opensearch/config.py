"""
OpenSearch Configuration Management.

Handles environment-specific configurations for OpenSearch deployments.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OpenSearchEnvironment(str, Enum):
    """Deployment environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    LOCAL = "local"


@dataclass
class OpenSearchConnectionConfig:
    """OpenSearch connection configuration."""

    # Connection details
    endpoint: str
    port: int = 443
    use_ssl: bool = True
    verify_certs: bool = True

    # AWS authentication
    aws_region: str = "us-east-1"
    use_aws_auth: bool = True
    aws_profile: Optional[str] = None

    # Connection pool
    max_connections: int = 10
    connection_timeout: int = 30
    max_retries: int = 3
    retry_on_timeout: bool = True

    # Performance
    batch_size: int = 100
    scroll_timeout: str = "2m"

    @classmethod
    def from_environment(
        cls, env: OpenSearchEnvironment
    ) -> "OpenSearchConnectionConfig":
        """Create configuration based on environment."""
        if env == OpenSearchEnvironment.PRODUCTION:
            return cls(
                endpoint=os.getenv("OPENSEARCH_PROD_ENDPOINT", ""),
                use_ssl=True,
                verify_certs=True,
                use_aws_auth=True,
                max_connections=50,
                batch_size=500,
            )
        elif env == OpenSearchEnvironment.STAGING:
            return cls(
                endpoint=os.getenv("OPENSEARCH_STAGING_ENDPOINT", ""),
                use_ssl=True,
                verify_certs=True,
                use_aws_auth=True,
                max_connections=20,
            )
        elif env == OpenSearchEnvironment.DEVELOPMENT:
            return cls(
                endpoint=os.getenv("OPENSEARCH_DEV_ENDPOINT", "localhost"),
                port=9200,
                use_ssl=False,
                verify_certs=False,
                use_aws_auth=False,
                max_connections=5,
            )
        else:  # LOCAL
            return cls(
                endpoint="localhost",
                port=9200,
                use_ssl=False,
                verify_certs=False,
                use_aws_auth=False,
                max_connections=5,
            )


@dataclass
class IndexConfig:
    """Configuration for OpenSearch indices."""

    name: str
    shards: int = 2
    replicas: int = 1
    refresh_interval: str = "1s"

    # Medical-specific settings
    enable_medical_analyzers: bool = True
    enable_phi_masking: bool = True
    enable_audit_logging: bool = True
    # Language support
    supported_languages: List[str] = field(
        default_factory=lambda: ["en", "es", "fr", "ar", "zh"]
    )
    default_language: str = "en"

    # Vector settings
    vector_dimension: int = 1536
    vector_similarity: str = "cosine"

    # Mappings
    custom_mappings: Dict[str, Any] = field(default_factory=dict)

    def get_index_settings(self) -> Dict[str, Any]:
        """Get complete index settings."""
        settings = {
            "number_of_shards": self.shards,
            "number_of_replicas": self.replicas,
            "refresh_interval": self.refresh_interval,
            "index.knn": True,
            "index.knn.space_type": self.vector_similarity,
        }

        if self.enable_audit_logging:
            settings["index.audit.enabled"] = True

        return settings


# Predefined index configurations
MEDICAL_DOCUMENT_INDEX = IndexConfig(
    name="haven-health-medical-documents",
    shards=3,
    replicas=2,
    enable_medical_analyzers=True,
    enable_phi_masking=True,
    vector_dimension=1536,
)

PATIENT_RECORD_INDEX = IndexConfig(
    name="haven-health-patient-records",
    shards=5,
    replicas=2,
    enable_medical_analyzers=True,
    enable_phi_masking=True,
    enable_audit_logging=True,
    vector_dimension=1536,
)

TRANSLATION_CACHE_INDEX = IndexConfig(
    name="haven-health-translation-cache",
    shards=2,
    replicas=1,
    enable_medical_analyzers=False,
    supported_languages=["en", "es", "fr", "ar", "zh", "hi", "pt", "ru", "ja", "de"],
)
