"""Medical Index Manager for OpenSearch.

Manages medical document indices with specialized configurations.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from .config import (
    MEDICAL_DOCUMENT_INDEX,
    PATIENT_RECORD_INDEX,
    TRANSLATION_CACHE_INDEX,
    IndexConfig,
)
from .connector import OpenSearchConnector

logger = logging.getLogger(__name__)


class MedicalIndexManager:
    """Manages medical indices in OpenSearch."""

    def __init__(self, connector: OpenSearchConnector):
        """Initialize medical index manager."""
        self.connector = connector
        self.predefined_indices = {
            "medical_documents": MEDICAL_DOCUMENT_INDEX,
            "patient_records": PATIENT_RECORD_INDEX,
            "translation_cache": TRANSLATION_CACHE_INDEX,
        }

    def initialize_all_indices(self) -> Dict[str, bool]:
        """Initialize all predefined medical indices."""
        results = {}
        for name, config in self.predefined_indices.items():
            try:
                success = self.connector.create_index(config)
                results[name] = success
                if success:
                    logger.info("Initialized index: %s", config.name)
            except (ValueError, TypeError, AttributeError) as e:
                logger.error("Failed to initialize %s: %s", name, e)
                results[name] = False

        return results

    def create_medical_document_index(
        self,
        index_name: Optional[str] = None,
        custom_settings: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Create index optimized for medical documents."""
        config = MEDICAL_DOCUMENT_INDEX
        if index_name:
            config.name = index_name

        if custom_settings:
            # Apply custom settings
            for key, value in custom_settings.items():
                if hasattr(config, key):
                    setattr(config, key, value)

        return self.connector.create_index(config)

    def create_patient_record_index(
        self, index_name: Optional[str] = None, enable_encryption: bool = True
    ) -> bool:
        """Create index for patient records with enhanced security."""
        config = PATIENT_RECORD_INDEX
        if index_name:
            config.name = index_name

        # Add encryption mapping if enabled
        if enable_encryption:
            config.custom_mappings["encrypted_data"] = {"type": "binary"}
            config.custom_mappings["encryption_key_id"] = {"type": "keyword"}

        return self.connector.create_index(config)

    def create_temporal_index(self, base_name: str, retention_days: int = 30) -> str:
        """Create temporal index with automatic cleanup."""
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        index_name = f"{base_name}-{timestamp}"

        config = IndexConfig(
            name=index_name, shards=1, replicas=0, refresh_interval="30s"
        )
        # Add lifecycle policy for automatic cleanup
        config.custom_mappings["retention_date"] = {"type": "date"}

        self.connector.create_index(config)

        # Set up index lifecycle policy
        self._setup_lifecycle_policy(index_name, retention_days)

        return index_name

    def _setup_lifecycle_policy(self, index_name: str, retention_days: int) -> None:
        """Set up lifecycle policy for index."""
        # This would integrate with OpenSearch ISM (Index State Management)
        # For now, we'll log the intent
        logger.info("Would set up %d day retention for %s", retention_days, index_name)

    def get_index_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all managed indices."""
        health_status = {}

        for name, config in self.predefined_indices.items():
            try:
                if self.connector.client and self.connector.client.indices.exists(
                    index=config.name
                ):
                    stats = self.connector.get_index_stats(config.name)
                    health_status[name] = {
                        "exists": True,
                        "health": stats["_all"]["primaries"]["health"],
                        "docs_count": stats["_all"]["primaries"]["docs"]["count"],
                        "size_bytes": stats["_all"]["primaries"]["store"][
                            "size_in_bytes"
                        ],
                    }
                else:
                    health_status[name] = {"exists": False}
            except (ConnectionError, ValueError) as e:
                health_status[name] = {"error": str(e)}

        return health_status

    def optimize_indices(self) -> Dict[str, bool]:
        """Optimize all indices for better performance."""
        results = {}

        for name, config in self.predefined_indices.items():
            try:
                if self.connector.client and self.connector.client.indices.exists(
                    index=config.name
                ):
                    # Force merge for optimization
                    if self.connector.client:
                        self.connector.client.indices.forcemerge(
                            index=config.name, max_num_segments=1
                        )
                    results[name] = True
                    logger.info("Optimized index: %s", config.name)
            except (ConnectionError, ValueError) as e:
                logger.error("Failed to optimize %s: %s", name, e)
                results[name] = False

        return results
