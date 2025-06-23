"""LlamaIndex Configuration Management.

Handles configuration for document indexing, retrieval, and medical-specific settings.

Security Note: This module processes PHI data. All configuration data must be:
- Encrypted at rest using AES-256 encryption
- Subject to role-based access control (RBAC) for PHI protection
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LlamaIndexConfig:
    """Main configuration for LlamaIndex integration."""

    # Storage settings
    storage_type: str = "local"  # local, s3, opensearch
    storage_path: str = "./storage/llamaindex"
    persist_enabled: bool = True

    # Indexing settings
    chunk_size: int = 512
    chunk_overlap: int = 128
    sentence_splitter_enabled: bool = True

    # Embedding settings
    embedding_provider: str = "bedrock"  # bedrock, openai, huggingface
    embedding_model: str = "amazon.titan-embed-text-v1"
    embedding_dimension: int = 1536
    embedding_batch_size: int = 10

    # LLM settings
    llm_provider: str = "bedrock"  # bedrock, openai, anthropic
    llm_model: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048

    # Medical-specific settings
    medical_ner_enabled: bool = True
    phi_detection_enabled: bool = True
    medical_term_extraction: bool = True
    icd10_mapping_enabled: bool = True
    snomed_integration: bool = True

    # Retrieval settings
    similarity_top_k: int = 5
    similarity_cutoff: float = 0.7
    rerank_enabled: bool = True
    rerank_top_k: int = 3

    # Similarity metrics settings
    similarity_metric: str = "cosine"  # cosine, euclidean, dot_product, medical, hybrid
    similarity_normalize_scores: bool = True
    similarity_score_threshold: float = 0.0
    similarity_consider_metadata: bool = True
    similarity_boost_medical_terms: bool = True
    similarity_medical_term_weight: float = 1.5
    similarity_use_semantic_types: bool = True
    similarity_use_cui_matching: bool = True

    # Hybrid similarity settings
    hybrid_base_metrics: List[str] = field(
        default_factory=lambda: ["cosine", "medical"]
    )
    hybrid_metric_weights: List[float] = field(default_factory=lambda: [0.7, 0.3])
    hybrid_aggregation_method: str = "weighted_mean"

    # Re-ranking settings
    reranker_type: str = "medical"  # medical, cross_encoder
    reranker_consider_clinical_priority: bool = True
    reranker_consider_evidence_level: bool = True
    reranker_urgency_boost_factor: float = 2.0

    # Vector store settings
    vector_store_type: str = "simple"  # simple, opensearch, pinecone, weaviate
    vector_store_config: Dict[str, Any] = field(default_factory=dict)

    # Document processing
    supported_file_types: List[str] = field(
        default_factory=lambda: [
            ".pdf",
            ".txt",
            ".md",
            ".docx",
            ".html",
            ".json",
            ".csv",
        ]
    )
    max_file_size_mb: int = 100
    extract_images: bool = True
    ocr_enabled: bool = True

    # Performance settings
    batch_processing_enabled: bool = True
    batch_size: int = 10
    max_workers: int = 4
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600

    # Monitoring
    metrics_enabled: bool = True
    log_level: str = "INFO"
    trace_indexing: bool = True
    trace_retrieval: bool = True


@dataclass
class DocumentTypeConfig:
    """Configuration for specific document types."""

    document_type: str
    chunk_size: int
    chunk_overlap: int
    metadata_extractors: List[str]
    preprocessing_steps: List[str]
    special_handling: Dict[str, Any] = field(default_factory=dict)


# Predefined configurations for medical document types
MEDICAL_DOCUMENT_CONFIGS = {
    "clinical_notes": DocumentTypeConfig(
        document_type="clinical_notes",
        chunk_size=512,
        chunk_overlap=128,
        metadata_extractors=["date", "provider", "patient_id", "visit_type"],
        preprocessing_steps=["remove_headers", "normalize_terminology"],
        special_handling={"preserve_structure": True},
    ),
    "lab_reports": DocumentTypeConfig(
        document_type="lab_reports",
        chunk_size=256,
        chunk_overlap=64,
        metadata_extractors=["test_date", "test_type", "lab_name", "reference_ranges"],
        preprocessing_steps=["extract_tables", "normalize_units"],
        special_handling={"table_extraction": True},
    ),
    "prescriptions": DocumentTypeConfig(
        document_type="prescriptions",
        chunk_size=256,
        chunk_overlap=32,
        metadata_extractors=["medication", "dosage", "frequency", "prescriber"],
        preprocessing_steps=["extract_medications", "validate_dosages"],
        special_handling={"strict_validation": True},
    ),
    "imaging_reports": DocumentTypeConfig(
        document_type="imaging_reports",
        chunk_size=512,
        chunk_overlap=128,
        metadata_extractors=["study_date", "modality", "body_part", "findings"],
        preprocessing_steps=["extract_impressions", "link_images"],
        special_handling={"image_correlation": True},
    ),
    "discharge_summaries": DocumentTypeConfig(
        document_type="discharge_summaries",
        chunk_size=1024,
        chunk_overlap=256,
        metadata_extractors=[
            "admission_date",
            "discharge_date",
            "diagnoses",
            "procedures",
        ],
        preprocessing_steps=["section_extraction", "medication_reconciliation"],
        special_handling={"comprehensive_extraction": True},
    ),
}


class ConfigManager:
    """Manages LlamaIndex configuration with environment variable support."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize config manager."""
        self.config_path = config_path or os.getenv(
            "LLAMAINDEX_CONFIG_PATH", "./config/llamaindex_config.json"
        )
        self.config = self._load_config()

    def _load_config(self) -> LlamaIndexConfig:
        """Load configuration from file or environment."""
        config_dict = {}

        # Try to load from file
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config_dict = json.load(f)
                logger.info("Loaded LlamaIndex config from %s", self.config_path)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.warning("Failed to load config file: %s", e)

        # Override with environment variables
        env_mappings = {
            "LLAMAINDEX_STORAGE_TYPE": "storage_type",
            "LLAMAINDEX_STORAGE_PATH": "storage_path",
            "LLAMAINDEX_CHUNK_SIZE": "chunk_size",
            "LLAMAINDEX_EMBEDDING_PROVIDER": "embedding_provider",
            "LLAMAINDEX_EMBEDDING_MODEL": "embedding_model",
            "LLAMAINDEX_LLM_PROVIDER": "llm_provider",
            "LLAMAINDEX_LLM_MODEL": "llm_model",
            "LLAMAINDEX_VECTOR_STORE_TYPE": "vector_store_type",
        }

        for env_var, config_key in env_mappings.items():
            if env_value := os.getenv(env_var):
                config_dict[config_key] = env_value
                logger.debug("Override %s from environment: %s", config_key, env_value)

        # Create config object
        return LlamaIndexConfig(**config_dict)

    def save_config(self) -> None:
        """Save current configuration to file."""
        if not self.config_path:
            logger.warning("No config path specified, cannot save configuration")
            return

        config_dir = os.path.dirname(self.config_path)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)

        config_dict = {
            k: v for k, v in self.config.__dict__.items() if not k.startswith("_")
        }

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2)

        logger.info("Saved LlamaIndex config to %s", self.config_path)

    def get_document_config(self, document_type: str) -> DocumentTypeConfig:
        """Get configuration for specific document type."""
        return MEDICAL_DOCUMENT_CONFIGS.get(
            document_type,
            DocumentTypeConfig(
                document_type=document_type,
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                metadata_extractors=[],
                preprocessing_steps=[],
            ),
        )

    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update configuration with new values."""
        for key, value in updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info("Updated config: %s = %s", key, value)
            else:
                logger.warning("Unknown config key: %s", key)

    def validate_config(self) -> List[str]:
        """Validate configuration and return any issues."""
        issues = []

        # Check storage path
        if self.config.storage_type == "local":
            storage_path = Path(self.config.storage_path)
            if not storage_path.exists():
                try:
                    storage_path.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    issues.append(f"Cannot create storage path: {e}")

        # Validate chunk settings
        if self.config.chunk_overlap >= self.config.chunk_size:
            issues.append("Chunk overlap must be less than chunk size")

        # Validate embedding dimension
        valid_dimensions = [384, 768, 1024, 1536, 3072]
        if self.config.embedding_dimension not in valid_dimensions:
            issues.append(
                f"Embedding dimension {self.config.embedding_dimension} not standard"
            )

        # Validate file size
        if self.config.max_file_size_mb > 500:
            issues.append("Max file size exceeds recommended limit of 500MB")

        return issues


# Global config instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> LlamaIndexConfig:
    """Get the global LlamaIndex configuration."""
    global _config_manager  # pylint: disable=global-statement # Singleton pattern for configuration
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.config


def get_config_manager() -> ConfigManager:
    """Get the configuration manager instance."""
    global _config_manager  # pylint: disable=global-statement # Singleton pattern for configuration
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
