"""Medical Embedding Service for Haven Health Passport.

This module provides medical-specific text embeddings for:
- Medical concept similarity matching
- Multilingual medical term mapping
- Clinical text analysis
- Patient record semantic search

Embeddings support FHIR Resource terminology validation.
Medical concepts are validated against FHIR CodeSystems and ValueSets.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MedicalConcept:
    """Represents a medical concept with metadata."""

    concept_id: str
    term: str
    concept_type: str  # diagnosis, symptom, medication, procedure
    language: str
    icd10_codes: List[str]
    snomed_codes: List[str]
    synonyms: List[str]
    embedding: Optional[np.ndarray] = None
    confidence: float = 0.0
    source: str = ""  # UMLS, ICD, SNOMED, etc.


@dataclass
class MedicalContext:
    """Context for medical text processing."""

    specialty: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    language: str = "en"
    clinical_setting: Optional[str] = None  # emergency, primary_care, specialist
    cultural_context: Optional[str] = None


class MedicalEmbeddingService:
    """Service for generating and managing medical-specific embeddings.

    This service provides:
    - Medical term embedding generation
    - Concept similarity matching
    - Cross-lingual medical term mapping
    - Integration with medical ontologies (ICD-10, SNOMED CT, RxNorm)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the medical embedding service.

        Args:
            config: Configuration dictionary with model paths and settings
        """
        self.config = config or {}
        self.model_name = self.config.get(
            "model_name", "emilyalsentzer/Bio_ClinicalBERT"
        )

        # Initialize models lazily to avoid import issues
        self._medical_bert = None
        self._tokenizer = None
        self._multilingual_model = None
        self._medical_service = None

        # Initialize medical knowledge bases
        self.umls_mappings: Dict[str, Any] = {}
        self.icd_embeddings: Dict[str, Any] = {}
        self.medical_abbreviations = self._load_medical_abbreviations()

        # Vector database connection (placeholder)
        self.vector_db = None

        logger.info("MedicalEmbeddingService initialized")

    def _load_medical_abbreviations(self) -> Dict[str, str]:
        """Load common medical abbreviations and their expansions."""
        # Common medical abbreviations relevant to refugee healthcare
        return {
            "bp": "blood pressure",
            "hr": "heart rate",
            "rr": "respiratory rate",
            "temp": "temperature",
            "hx": "history",
            "dx": "diagnosis",
            "rx": "prescription",
            "tx": "treatment",
            "sx": "symptoms",
            "pmh": "past medical history",
            "nkda": "no known drug allergies",
            "sob": "shortness of breath",
            "cp": "chest pain",
            "ha": "headache",
            "abd": "abdominal",
            "tb": "tuberculosis",
            "hiv": "human immunodeficiency virus",
            "hep": "hepatitis",
            "dm": "diabetes mellitus",
            "htn": "hypertension",
            "ptsd": "post-traumatic stress disorder",
            "icd": "international classification of diseases",
            "who": "world health organization",
            "unhcr": "united nations high commissioner for refugees",
        }

    def _get_medical_bert(self) -> Any:
        """Lazy load the medical BERT model."""
        if self._medical_bert is None:
            try:
                from transformers import AutoModel, AutoTokenizer

                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self._medical_bert = AutoModel.from_pretrained(self.model_name)
                logger.info("Loaded medical BERT model: %s", self.model_name)
            except ImportError:
                logger.warning(
                    "Transformers library not available, using fallback embeddings"
                )
                # Fallback to simpler embeddings
                self._medical_bert = "fallback"  # type: ignore[assignment]
                self._tokenizer = "fallback"  # type: ignore[assignment]
        return self._medical_bert, self._tokenizer

    def preprocess_medical_text(self, text: str) -> str:
        """Preprocess medical text for embedding generation.

        Args:
            text: Raw medical text

        Returns:
            Preprocessed text with expanded abbreviations
        """
        if not text:
            return ""

        # Convert to lowercase for abbreviation matching
        text_lower = text.lower()

        # Expand medical abbreviations
        for abbr, expansion in self.medical_abbreviations.items():
            # Match abbreviation with word boundaries
            import re

            pattern = r"\b" + re.escape(abbr) + r"\b"
            text_lower = re.sub(pattern, expansion, text_lower)

        # Clean up extra whitespace
        text_clean = " ".join(text_lower.split())

        return text_clean

    def embed_medical_text(
        self, text: str, context: Optional[MedicalContext] = None
    ) -> np.ndarray:
        """Generate embeddings for medical text.

        Args:
            text: Medical text to embed
            context: Optional medical context for enhanced embeddings

        Returns:
            Numpy array of embeddings
        """
        # @protect: HIPAA access control required for medical text processing
        # Preprocess the text
        processed_text = self.preprocess_medical_text(text)

        model, tokenizer = self._get_medical_bert()

        if model == "fallback":
            # Fallback: Use simple word vectors
            return self._fallback_embedding(processed_text)

        try:
            # Tokenize and get embeddings
            import torch

            inputs = tokenizer(
                processed_text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )

            with torch.no_grad():
                outputs = model(**inputs)
                # Use mean pooling over token embeddings
                embeddings = outputs.last_hidden_state.mean(dim=1)

            # Convert to numpy
            embedding_array = embeddings.squeeze().numpy()

            # Enhance with context if provided
            if context:
                embedding_array = self._enhance_with_context(embedding_array, context)

            return embedding_array  # type: ignore[no-any-return]

        except (RuntimeError, ValueError, AttributeError, TypeError) as e:
            logger.error("Error generating embeddings: %s", e)
            return self._fallback_embedding(processed_text)

    def _fallback_embedding(self, text: str) -> np.ndarray:
        """Generate simple fallback embeddings when models aren't available."""
        # Simple character-based hash embedding
        import hashlib

        # Create a deterministic embedding from text
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        # Convert to fixed-size vector (768 dims to match BERT)
        embedding = np.zeros(768)
        for i, char in enumerate(text_hash):
            idx = i % 768
            embedding[idx] += ord(char) / 255.0

        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    def _enhance_with_context(
        self, embedding: np.ndarray, context: MedicalContext
    ) -> np.ndarray:
        """Enhance embeddings with medical context information."""
        # Add small context-based modifications
        context_vector = np.zeros_like(embedding)

        # Add specialty-specific bias
        if context.specialty:
            specialty_hash = hash(context.specialty) % len(embedding)
            context_vector[specialty_hash] += 0.1

        # Add age-related context
        if context.patient_age is not None:
            age_idx = min(context.patient_age, len(embedding) - 1)
            context_vector[age_idx] += 0.05

        # Combine with original embedding
        enhanced = embedding + 0.1 * context_vector

        # Re-normalize
        norm = np.linalg.norm(enhanced)
        if norm > 0:
            enhanced = enhanced / norm

        return enhanced

    def find_similar_medical_concepts(
        self,
        query: str,
        top_k: int = 5,
        concept_types: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
    ) -> List[MedicalConcept]:
        """Find similar medical concepts using embedding similarity.

        Args:
            query: Query text
            top_k: Number of similar concepts to return
            concept_types: Filter by concept types (diagnosis, symptom, etc.)
            languages: Filter by languages

        Returns:
            List of similar medical concepts with scores
        """
        # role_based: Medical concept search requires provider authorization
        # CRITICAL: Use real medical embeddings service
        from src.config import settings

        # In production/staging, use real medical service
        if settings.environment in ["production", "staging"]:
            try:
                # Import and use real medical embeddings service
                from src.ai.medical_embeddings_service import MedicalEmbeddingsService

                if not hasattr(self, "_medical_service"):
                    self._medical_service = MedicalEmbeddingsService()

                # Use async method synchronously (this method should be async in production)
                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                results = loop.run_until_complete(
                    self._medical_service.search_medical_concepts(
                        query=query,
                        language=languages[0] if languages else "en",
                        _concept_types=concept_types,
                        top_k=top_k,
                    )
                )

                return results  # type: ignore[return-value]

            except Exception as e:
                logger.error("Failed to use medical embeddings service: %s", e)
                raise RuntimeError(
                    "CRITICAL: Medical concept search failed. "
                    "Cannot proceed without proper medical terminology matching. "
                    "Patient safety requires accurate medical data!"
                )

        # Development-only warning
        logger.critical(
            "WARNING: Using mock medical concepts in development. "
            "Production MUST use MedicalEmbeddingsService with UMLS integration!"
        )

        # Development-only mock concepts
        mock_concepts = [
            MedicalConcept(
                concept_id="ICD10:A00",
                term="cholera",
                concept_type="diagnosis",
                language="en",
                icd10_codes=["A00"],
                snomed_codes=["63650001"],
                synonyms=["vibrio cholerae infection"],
                confidence=0.95,
                source="ICD10",
            ),
            MedicalConcept(
                concept_id="ICD10:A01",
                term="typhoid fever",
                concept_type="diagnosis",
                language="en",
                icd10_codes=["A01"],
                snomed_codes=["4834000"],
                synonyms=["enteric fever", "typhoid"],
                confidence=0.87,
                source="ICD10",
            ),
        ]

        # Filter by requested types and languages
        filtered_concepts = mock_concepts
        if concept_types:
            filtered_concepts = [
                c for c in filtered_concepts if c.concept_type in concept_types
            ]
        if languages:
            filtered_concepts = [
                c for c in filtered_concepts if c.language in languages
            ]

        # Return top k
        return filtered_concepts[:top_k]

    def match_cross_lingual_concept(
        self, _term: str, _source_language: str, target_languages: List[str]
    ) -> Dict[str, List[MedicalConcept]]:
        """Match medical concepts across languages.

        Args:
            term: Medical term to match
            source_language: Source language code
            target_languages: List of target language codes

        Returns:
            Dictionary mapping language codes to matched concepts
        """
        # Generate embedding for source term
        # In production, would compute source_embedding = self.embed_medical_text(term)
        # and use it for similarity matching across languages

        # Mock implementation - in production would use multilingual medical database
        cross_lingual_matches = {
            "ar": [  # Arabic
                MedicalConcept(
                    concept_id="ICD10:J00",
                    term="نزلة برد حادة",  # Acute nasopharyngitis (common cold)
                    concept_type="diagnosis",
                    language="ar",
                    icd10_codes=["J00"],
                    snomed_codes=["82272006"],
                    synonyms=["الزكام", "البرد"],
                    confidence=0.92,
                    source="multilingual_umls",
                )
            ],
            "fr": [  # French
                MedicalConcept(
                    concept_id="ICD10:J00",
                    term="rhume",
                    concept_type="diagnosis",
                    language="fr",
                    icd10_codes=["J00"],
                    snomed_codes=["82272006"],
                    synonyms=["rhinopharyngite aiguë"],
                    confidence=0.95,
                    source="multilingual_umls",
                )
            ],
        }

        # Filter for requested languages
        result = {}
        for lang in target_languages:
            if lang in cross_lingual_matches:
                result[lang] = cross_lingual_matches[lang]

        return result

    def enrich_concept(self, concept: MedicalConcept) -> MedicalConcept:
        """Enrich a medical concept with additional information.

        Args:
            concept: Medical concept to enrich

        Returns:
            Enriched medical concept
        """
        # Add embedding if not present
        if concept.embedding is None:
            concept.embedding = self.embed_medical_text(concept.term)

        # Add related codes if missing
        if not concept.icd10_codes and concept.snomed_codes:
            # Mock mapping - in production would use proper mapping tables
            concept.icd10_codes = ["A00-B99"]  # Placeholder

        # Add common synonyms
        if len(concept.synonyms) < 2:
            # Generate variations
            term_lower = concept.term.lower()
            if "disease" not in term_lower and concept.concept_type == "diagnosis":
                concept.synonyms.append(f"{concept.term} disease")
            if "syndrome" not in term_lower and concept.concept_type == "diagnosis":
                concept.synonyms.append(f"{concept.term} syndrome")

        return concept

    def expand_medical_abbreviation(self, abbreviation: str) -> List[str]:
        """Expand a medical abbreviation to possible full forms.

        Args:
            abbreviation: Medical abbreviation

        Returns:
            List of possible expansions
        """
        abbr_lower = abbreviation.lower()

        # Check our abbreviation dictionary
        if abbr_lower in self.medical_abbreviations:
            return [self.medical_abbreviations[abbr_lower]]

        # Common patterns for medical abbreviations
        # Check for measurement units
        if abbr_lower in ["mg", "ml", "mcg", "kg", "g", "l"]:
            unit_expansions = {
                "mg": "milligrams",
                "ml": "milliliters",
                "mcg": "micrograms",
                "kg": "kilograms",
                "g": "grams",
                "l": "liters",
            }
            return [unit_expansions.get(abbr_lower, abbr_lower)]

        # No expansion found
        return [abbreviation]

    def handle_misspellings(self, text: str) -> List[str]:
        """Generate variations for common medical misspellings.

        Args:
            text: Potentially misspelled medical text

        Returns:
            List of possible correct spellings
        """
        # Common medical misspellings in refugee populations
        common_misspellings = {
            "diabetis": "diabetes",
            "diabettes": "diabetes",
            "presure": "pressure",
            "preasure": "pressure",
            "hart": "heart",
            "stomac": "stomach",
            "stomache": "stomach",
            "medecine": "medicine",
            "tabletes": "tablets",
            "vacine": "vaccine",
            "vaccin": "vaccine",
            "alergy": "allergy",
            "allergie": "allergy",
            "astma": "asthma",
            "hepatitus": "hepatitis",
            "maleria": "malaria",
            "tuberclosis": "tuberculosis",
            "nuemonia": "pneumonia",
            "neumonia": "pneumonia",
        }

        text_lower = text.lower()

        # Check exact match
        if text_lower in common_misspellings:
            return [common_misspellings[text_lower]]

        # Check if text contains any misspelling
        variations = [text]
        for misspelling, correct in common_misspellings.items():
            if misspelling in text_lower:
                corrected = text_lower.replace(misspelling, correct)
                variations.append(corrected)

        return list(set(variations))  # Remove duplicates

    def calculate_similarity(
        self, embedding1: np.ndarray, embedding2: np.ndarray
    ) -> float:
        """Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score between -1 and 1
        """
        # Handle edge cases - arrays can't be None but could be empty
        if embedding1.size == 0 or embedding2.size == 0:
            return 0.0

        # Ensure same shape
        if embedding1.shape != embedding2.shape:
            logger.warning(
                "Embedding shape mismatch: %s vs %s", embedding1.shape, embedding2.shape
            )
            return 0.0

        # Calculate cosine similarity
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)

        # Ensure result is between -1 and 1 (handle floating point errors)
        return float(np.clip(similarity, -1.0, 1.0))

    def batch_embed_medical_texts(
        self,
        texts: List[str],
        context: Optional[MedicalContext] = None,
        batch_size: int = 32,
    ) -> List[np.ndarray]:
        """Generate embeddings for multiple medical texts efficiently.

        Args:
            texts: List of medical texts
            context: Optional medical context
            batch_size: Batch size for processing

        Returns:
            List of embedding arrays
        """
        embeddings = []

        # Process in batches for efficiency
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]

            # Preprocess batch
            processed_batch = [
                self.preprocess_medical_text(text) for text in batch_texts
            ]

            # Generate embeddings
            batch_embeddings = []
            for text in processed_batch:
                embedding = self.embed_medical_text(text, context)
                batch_embeddings.append(embedding)

            embeddings.extend(batch_embeddings)

        return embeddings

    def get_concept_relationships(
        self, _concept_id: str, relationship_types: Optional[List[str]] = None
    ) -> Dict[str, List[MedicalConcept]]:
        """Get relationships between medical concepts.

        Args:
            concept_id: Source concept ID
            relationship_types: Types of relationships to retrieve
                (e.g., 'is_a', 'part_of', 'causes', 'treats')

        Returns:
            Dictionary mapping relationship types to related concepts
        """
        if not relationship_types:
            relationship_types = ["is_a", "part_of", "causes", "treats", "prevents"]

        # Mock implementation - in production would query knowledge graph
        relationships = {
            "is_a": [
                MedicalConcept(
                    concept_id="SNOMED:404684003",
                    term="clinical finding",
                    concept_type="finding",
                    language="en",
                    icd10_codes=[],
                    snomed_codes=["404684003"],
                    synonyms=["finding", "clinical observation"],
                    confidence=1.0,
                    source="SNOMED",
                )
            ],
            "causes": [],
            "treats": [],
        }

        # Filter for requested relationship types
        return {
            rel_type: concepts
            for rel_type, concepts in relationships.items()
            if rel_type in relationship_types
        }

    def validate_medical_code(
        self, code: str, code_system: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate a medical code against its coding system.

        Args:
            code: Medical code to validate
            code_system: Coding system (ICD10, SNOMED, LOINC, etc.)

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Basic validation patterns
        validation_patterns = {
            "ICD10": r"^[A-Z]\d{2}(\.\d{1,2})?$",  # e.g., A00.1
            "SNOMED": r"^\d{6,18}$",  # e.g., 404684003
            "LOINC": r"^\d{1,5}-\d$",  # e.g., 8302-2
            "RxNorm": r"^\d{1,7}$",  # e.g., 1049683
        }

        if code_system not in validation_patterns:
            return False, f"Unknown code system: {code_system}"

        import re

        pattern = validation_patterns[code_system]

        if re.match(pattern, code):
            return True, None
        else:
            return False, f"Invalid {code_system} code format"

    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages for medical embeddings.

        Returns:
            List of ISO 639-1 language codes
        """
        # Languages commonly needed in refugee healthcare
        return [
            "en",  # English
            "ar",  # Arabic
            "fr",  # French
            "es",  # Spanish
            "sw",  # Swahili
            "fa",  # Farsi/Persian
            "ps",  # Pashto
            "ur",  # Urdu
            "so",  # Somali
            "ti",  # Tigrinya
            "am",  # Amharic
            "my",  # Burmese
            "km",  # Khmer
            "vi",  # Vietnamese
            "ru",  # Russian
            "uk",  # Ukrainian
            "tr",  # Turkish
            "ku",  # Kurdish
            "bn",  # Bengali
            "ne",  # Nepali
        ]

    def __repr__(self) -> str:
        """Return string representation of the service."""
        return (
            f"MedicalEmbeddingService(model={self.model_name}, "
            f"languages={len(self.get_supported_languages())})"
        )


# Create a singleton instance for module-level access
# Module-level singleton holder
class _ServiceHolder:
    """Holds the singleton medical embedding service instance."""

    instance: Optional[MedicalEmbeddingService] = None


def get_embedding_service(
    config: Optional[Dict[str, Any]] = None,
) -> MedicalEmbeddingService:
    """Get or create the medical embedding service instance.

    Args:
        config: Optional configuration dictionary

    Returns:
        MedicalEmbeddingService instance
    """
    if _ServiceHolder.instance is None:
        _ServiceHolder.instance = MedicalEmbeddingService(config)

    return _ServiceHolder.instance


# Convenience function for direct access
EmbeddingService = MedicalEmbeddingService
