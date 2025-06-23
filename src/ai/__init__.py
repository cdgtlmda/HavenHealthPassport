"""AI module for Haven Health Passport.

This module provides AI/ML capabilities including:
- Medical text embeddings
- Natural language processing for healthcare
- Machine learning models for clinical decision support
"""

from .embeddings import (
    EmbeddingService,
    MedicalConcept,
    MedicalContext,
    MedicalEmbeddingService,
    get_embedding_service,
)

__all__ = [
    "MedicalEmbeddingService",
    "EmbeddingService",
    "MedicalConcept",
    "MedicalContext",
    "get_embedding_service",
]
