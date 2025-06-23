"""
Base Medical Entity Recognizer.

Base class for medical entity recognition.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    import spacy
except ImportError:
    spacy = None


@dataclass
class MedicalEntity:
    """Represents a medical entity."""

    text: str
    start: int
    end: int
    label: str
    confidence: float
    cui: Optional[str] = None  # UMLS Concept Unique Identifier
    preferred_term: Optional[str] = None
    semantic_types: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class MedicalEntityRecognizer(ABC):
    """Base class for medical entity recognition."""

    def __init__(
        self,
        model_name: str = "en_core_sci_md",
        enable_umls: bool = True,
        confidence_threshold: float = 0.7,
    ):
        """
        Initialize medical entity recognizer.

        Args:
            model_name: spaCy model to use
            enable_umls: Whether to enable UMLS linking
            confidence_threshold: Minimum confidence for entities
        """
        self.model_name = model_name
        self.enable_umls = enable_umls
        self.confidence_threshold = confidence_threshold
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Load spaCy model
        self._load_model()

    def _load_model(self) -> None:
        """Load spaCy model with medical extensions."""
        if spacy is None:
            self.logger.error("spacy is not installed")
            raise ImportError("spacy is required for medical entity recognition")

        try:
            self.nlp = spacy.load(self.model_name)

            # Add medical entity linker if enabled
            if self.enable_umls:
                try:
                    self.nlp.add_pipe(
                        "scispacy_linker", config={"resolve_abbreviations": True}
                    )
                except AttributeError as e:
                    self.logger.warning("Failed to load UMLS linker: %s", e)
                    self.enable_umls = False
                except ValueError as e:
                    self.logger.warning("Failed to load UMLS linker: %s", e)
                    self.enable_umls = False

            self.logger.info("Loaded model: %s", self.model_name)

        except (ImportError, OSError) as e:
            self.logger.error("Failed to load model: %s", e)
            # Fallback to basic model
            self.nlp = spacy.blank("en")

    @abstractmethod
    def extract_entities(self, text: str) -> List[MedicalEntity]:
        """
        Extract medical entities from text.

        Args:
            text: Input text

        Returns:
            List of medical entities
        """

    def process_text(self, text: str) -> Any:
        """Process text with spaCy pipeline."""
        return self.nlp(text)

    def _create_entity(
        self, span: Any, label: str, confidence: float = 1.0
    ) -> MedicalEntity:
        """Create MedicalEntity from spaCy span."""
        entity = MedicalEntity(
            text=span.text,
            start=span.start_char,
            end=span.end_char,
            label=label,
            confidence=confidence,
        )

        # Add UMLS information if available
        if self.enable_umls and hasattr(span, "_.kb_ents"):
            kb_ents = span._.kb_ents
            if kb_ents:
                top_ent = kb_ents[0]
                entity.cui = top_ent[0]
                entity.confidence = top_ent[1]

        return entity

    def filter_entities(
        self, entities: List[MedicalEntity], min_confidence: Optional[float] = None
    ) -> List[MedicalEntity]:
        """Filter entities by confidence threshold."""
        threshold = min_confidence or self.confidence_threshold
        return [e for e in entities if e.confidence >= threshold]

    def merge_overlapping_entities(
        self, entities: List[MedicalEntity]
    ) -> List[MedicalEntity]:
        """Merge overlapping entities, keeping highest confidence."""
        if not entities:
            return []

        # Sort by start position
        sorted_entities = sorted(entities, key=lambda e: e.start)
        merged = [sorted_entities[0]]

        for entity in sorted_entities[1:]:
            last_entity = merged[-1]

            # Check for overlap
            if entity.start < last_entity.end:
                # Keep the one with higher confidence
                if entity.confidence > last_entity.confidence:
                    merged[-1] = entity
            else:
                merged.append(entity)

        return merged

    def extract_entities_batch(
        self, texts: List[str], batch_size: int = 100
    ) -> List[List[MedicalEntity]]:
        """Extract entities from multiple texts."""
        results = []

        # Process in batches
        for doc in self.nlp.pipe(texts, batch_size=batch_size):
            # Extract entities for this document
            entities = self.extract_entities(doc.text)
            results.append(entities)

        return results
