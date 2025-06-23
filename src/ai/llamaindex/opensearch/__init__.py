"""
OpenSearch Connector for Haven Health Passport.

Production-ready OpenSearch integration with medical-specific optimizations.
Provides connection management, index configuration, and health monitoring.
"""

from .analyzers import MedicalAnalyzerConfig
from .config import OpenSearchConnectionConfig, OpenSearchEnvironment
from .connector import OpenSearchConnector
from .health import OpenSearchHealthCheck
from .indices import MedicalIndexManager

__all__ = [
    "OpenSearchConnector",
    "OpenSearchEnvironment",
    "OpenSearchConnectionConfig",
    "MedicalIndexManager",
    "MedicalAnalyzerConfig",
    "OpenSearchHealthCheck",
]
