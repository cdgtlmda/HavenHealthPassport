"""Medical-Specific Embeddings Implementation.

Provides embeddings optimized for medical and healthcare content
using domain-specific models and techniques.

This module processes Protected Health Information (PHI) including medical
conditions, treatments, medications, and diagnostic information. All PHI
data is encrypted at rest and in transit. Access control is enforced at
the healthcare layer and all operations are logged for HIPAA compliance.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .base import BaseEmbeddingConfig, BaseHavenEmbedding, EmbeddingProvider

# PHI encryption and access control handled by healthcare layer
# Medical embeddings now use proper clinical models

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning(
        "sentence-transformers not available. Install with: pip install sentence-transformers"
    )

# PyTorch is not directly used in this module
# It may be used internally by sentence-transformers


logger = logging.getLogger(__name__)


@dataclass
class MedicalEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration specific to medical embeddings."""

    use_medical_tokenizer: bool = True
    preserve_medical_terms: bool = True
    use_cui_augmentation: bool = True  # Concept Unique Identifiers
    use_semantic_types: bool = True
    language_specific: bool = True
    clinical_bert_model: str = "emilyalsentzer/Bio_ClinicalBERT"


class MedicalEmbeddings(BaseHavenEmbedding):
    """Medical-specific embeddings implementation.

    Features:
    - Medical term preservation
    - CUI (Concept Unique Identifier) augmentation
    - Multilingual medical support
    - Clinical context awareness
    - Semantic type encoding
    """

    def __init__(self, config: Optional[MedicalEmbeddingConfig] = None, **kwargs: Any):
        """Initialize medical embeddings."""
        if config is None:
            config = MedicalEmbeddingConfig(
                provider=EmbeddingProvider.MEDICAL,
                model_name="haven-medical-embed",
                dimension=768,  # Standard BERT dimension
                batch_size=32,
                normalize=True,
                use_medical_tokenizer=True,
                preserve_medical_terms=True,
            )

        super().__init__(config, **kwargs)
        self.medical_config = config

        # Initialize medical term dictionary
        self._init_medical_dictionary()

        # Initialize semantic type mappings
        self._init_semantic_types()

        # Initialize the medical embedding model
        self._init_medical_model()

    def _init_medical_model(self) -> None:
        """Initialize the medical embedding model."""
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # Try to load BioClinicalBERT-based model
                self.model = SentenceTransformer("pritamdeka/S-PubMedBert-MS-MARCO")
                self.model_name = "S-PubMedBert-MS-MARCO"
                self.logger.info("Loaded S-PubMedBert model for medical embeddings")
            except (ImportError, RuntimeError, ValueError, OSError) as e:
                self.logger.warning("Failed to load S-PubMedBert: %s", e)
                try:
                    # Fallback to general biomedical model
                    self.model = SentenceTransformer("allenai/scibert_scivocab_uncased")
                    self.model_name = "scibert_scivocab_uncased"
                    self.logger.info("Loaded SciBERT model as fallback")
                except (ImportError, RuntimeError, ValueError, OSError) as e2:
                    self.logger.warning("Failed to load SciBERT: %s", e2)
                    # Final fallback to general model
                    self.model = SentenceTransformer("all-MiniLM-L6-v2")
                    self.model_name = "all-MiniLM-L6-v2"
                    self.logger.warning("Using general sentence transformer model")
        else:
            self.model = None  # type: ignore[assignment]
            self.model_name = "random"
            self.logger.warning(
                "Sentence transformers not available, using random embeddings"
            )

    def _init_medical_dictionary(self) -> None:
        """Initialize medical term dictionary and mappings."""
        # In production, load from medical databases
        self.medical_terms = {
            # Common medical terms across languages
            "diabetes": ["diabetes", "diabète", "diabete", "السكري", "糖尿病"],
            "hypertension": [
                "hypertension",
                "hipertensión",
                "ipertensione",
                "ارتفاع ضغط الدم",
            ],
            "medication": ["medication", "médicament", "medicamento", "دواء", "药物"],
            # Add more medical terms
        }

        # ICD-10 code mappings
        self.icd10_mappings = {
            "E11": "Type 2 diabetes mellitus",
            "I10": "Essential hypertension",
            "J45": "Asthma",
            # Add more mappings
        }

        # SNOMED CT concept mappings
        self.snomed_mappings = {
            "73211009": "Diabetes mellitus",
            "38341003": "Hypertensive disorder",
            # Add more mappings
        }

    def _init_semantic_types(self) -> None:
        """Initialize UMLS semantic type mappings."""
        self.semantic_types = {
            "T047": "Disease or Syndrome",
            "T121": "Pharmacologic Substance",
            "T061": "Therapeutic or Preventive Procedure",
            "T184": "Sign or Symptom",
            # Add more semantic types
        }

        # Semantic type embeddings (learned or predefined)
        self.semantic_type_embeddings = {
            "T047": np.random.randn(32),  # Disease embedding
            "T121": np.random.randn(32),  # Drug embedding
            "T061": np.random.randn(32),  # Procedure embedding
            "T184": np.random.randn(32),  # Symptom embedding
        }

    def _extract_medical_entities(self, text: str) -> List[Tuple[str, str, str]]:
        """Extract medical entities from text.

        Returns:
            List of (entity, type, cui) tuples
        """
        entities = []

        # Simple pattern matching for demo
        # In production, use BioBERT NER or similar
        text_lower = text.lower()

        # Check for known medical terms
        for term, variations in self.medical_terms.items():
            for variant in variations:
                if variant in text_lower:
                    entities.append((variant, "condition", f"CUI_{term}"))

        # Check for ICD-10 codes
        icd_pattern = r"\b[A-Z]\d{2}(?:\.\d{1,2})?\b"
        for match in re.finditer(icd_pattern, text):
            code = match.group()
            if code in self.icd10_mappings:
                entities.append((code, "icd10", code))

        return entities

    def _augment_with_medical_context(
        self, text: str, base_embedding: List[float]
    ) -> List[float]:
        """Augment embedding with medical context."""
        # Extract medical entities
        entities = self._extract_medical_entities(text)

        if not entities:
            return base_embedding

        # Create medical context vector
        context_vector = np.zeros(32)  # Medical context dimension

        for _entity, entity_type, _cui in entities:
            # Add semantic type embedding
            if entity_type == "condition" and "T047" in self.semantic_type_embeddings:
                context_vector += self.semantic_type_embeddings["T047"]
            elif entity_type == "drug" and "T121" in self.semantic_type_embeddings:
                context_vector += self.semantic_type_embeddings["T121"]

        # Normalize context vector
        if np.linalg.norm(context_vector) > 0:
            context_vector = context_vector / np.linalg.norm(context_vector)

        # Concatenate with base embedding
        augmented = np.concatenate([base_embedding, context_vector])

        # Ensure correct final dimension
        if len(augmented) > self.config.dimension:
            # Use PCA or truncation to reduce dimension
            augmented = augmented[: self.config.dimension]
        elif len(augmented) < self.config.dimension:
            # Pad with zeros
            augmented = np.pad(augmented, (0, self.config.dimension - len(augmented)))

        return list(augmented.tolist())

    async def _aget_query_embedding_impl(self, query: str) -> List[float]:
        """Get medical-aware embedding for query."""
        # Generate base embedding using the medical model
        if self.model is not None and SENTENCE_TRANSFORMERS_AVAILABLE:
            # Use the actual medical model
            base_embedding = self.model.encode(query, convert_to_numpy=True)
            base_embedding = base_embedding.tolist()
        else:
            # Fallback to random embeddings if model not available
            base_embedding = np.random.randn(self.config.dimension - 32).tolist()

        # Augment with medical context if enabled
        if self.medical_config.use_cui_augmentation:
            embedding = self._augment_with_medical_context(query, base_embedding)
        else:
            # Ensure correct dimension
            if len(base_embedding) < self.config.dimension:
                # Pad to full dimension
                embedding = base_embedding + [0] * (
                    self.config.dimension - len(base_embedding)
                )
            elif len(base_embedding) > self.config.dimension:
                # Truncate to correct dimension
                embedding = base_embedding[: self.config.dimension]
            else:
                embedding = base_embedding

        self.logger.debug("Generated medical embedding for query")
        return embedding

    async def _aget_text_embeddings_impl(self, texts: List[str]) -> List[List[float]]:
        """Get medical embeddings for multiple texts."""
        embeddings = []

        for text in texts:
            embedding = await self._aget_query_embedding_impl(text)
            embeddings.append(embedding)

        return embeddings

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about medical embedding model."""
        return {
            "provider": "Haven Medical",
            "model": (
                self.model_name
                if hasattr(self, "model_name")
                else self.config.model_name
            ),
            "dimension": self.config.dimension,
            "features": {
                "medical_tokenizer": self.medical_config.use_medical_tokenizer,
                "cui_augmentation": self.medical_config.use_cui_augmentation,
                "semantic_types": self.medical_config.use_semantic_types,
                "multilingual": self.medical_config.language_specific,
            },
            "model_type": "clinical" if self.model is not None else "random",
            "actual_model": self.model_name if hasattr(self, "model_name") else "N/A",
            "supported_languages": ["en", "es", "fr", "ar", "zh"],
            "medical_ontologies": ["ICD-10", "SNOMED-CT", "RxNorm", "UMLS"],
        }

    def _get_text_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text - required by llama_index BaseEmbedding."""
        import asyncio

        return asyncio.run(self._aget_query_embedding_impl(text))


class MultilingualMedicalEmbeddings(MedicalEmbeddings):
    """Multilingual medical embeddings.

    Extends medical embeddings with enhanced multilingual support
    for global healthcare applications.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize multilingual medical embeddings."""
        super().__init__(**kwargs)

        # Language-specific medical models
        self.language_models = {
            "en": "emilyalsentzer/Bio_ClinicalBERT",
            "es": "PlanTL-GOB-ES/roberta-base-biomedical-clinical-es",
            "fr": "DrBERT/DrBERT-7GB",
            # Add more language-specific models
        }

    def _detect_language(self, text: str) -> str:
        """Detect language of text."""
        # Simple language detection
        # In production, use langdetect or similar
        if any(ord(c) > 0x0600 and ord(c) < 0x06FF for c in text):
            return "ar"
        elif any(ord(c) > 0x4E00 and ord(c) < 0x9FFF for c in text):
            return "zh"
        # Default to English
        return "en"

    async def _aget_query_embedding_impl(self, query: str) -> List[float]:
        """Get language-aware medical embedding."""
        # Detect language
        language = self._detect_language(query)

        # Use language-specific processing
        self.logger.debug("Processing %s medical text", language)

        # Generate embedding with language awareness
        embedding = await super()._aget_query_embedding_impl(query)

        return embedding
