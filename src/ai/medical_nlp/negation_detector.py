"""Medical Negation Detector.

Main class for detecting negated medical concepts in clinical text.
"""

import logging
import re
from typing import Any, List, Optional, Tuple

try:
    import spacy

    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None

from .negation_patterns import (
    MEDICAL_CONCEPT_INDICATORS,
    get_english_negation_triggers,
    get_multilingual_triggers,
    get_pseudo_negation_patterns,
    get_scope_terminators,
)
from .negation_types import NegatedConcept, NegationScope, NegationTrigger

logger = logging.getLogger(__name__)


class MedicalNegationDetector:
    """Comprehensive medical negation detection system.

    Features:
    - Pre and post negation detection
    - Pseudo-negation handling
    - Scope termination
    - Conditional and uncertain concepts
    - Multi-language support
    """

    def __init__(
        self,
        language: str = "en",
        use_spacy: bool = True,
        spacy_model: Optional[str] = None,
        custom_triggers: Optional[List[NegationTrigger]] = None,
    ):
        """Initialize negation detector.

        Args:
            language: Language for negation patterns
            use_spacy: Use spaCy for enhanced detection
            spacy_model: Specific spaCy model to use
            custom_triggers: Custom negation triggers
        """
        self.language = language
        self.use_spacy = use_spacy and SPACY_AVAILABLE
        self.nlp: Optional[Any] = None

        # Initialize negation triggers
        self.negation_triggers = self._load_negation_triggers()
        if custom_triggers:
            self.negation_triggers.extend(custom_triggers)

        # Scope terminators
        self.scope_terminators = get_scope_terminators()

        # Pseudo-negation patterns
        self.pseudo_negation_patterns = get_pseudo_negation_patterns()

        # Load spaCy model if requested
        if self.use_spacy:
            self._load_spacy_model(spacy_model)

        # Compile regex patterns
        self._compile_patterns()

        logger.info(
            "Initialized MedicalNegationDetector with %s triggers",
            len(self.negation_triggers),
        )

    def _load_negation_triggers(self) -> List[NegationTrigger]:
        """Load negation triggers for the language."""
        if self.language == "en":
            return get_english_negation_triggers()
        else:
            return get_multilingual_triggers(self.language)

    def _load_spacy_model(self, model_name: Optional[str] = None) -> None:
        """Load spaCy model for enhanced processing."""
        if not SPACY_AVAILABLE:
            logger.warning("spaCy not available, using rule-based detection only")
            self.use_spacy = False
            return

        try:
            if model_name:
                self.nlp = spacy.load(model_name)
            else:
                # Try to load medical model first, fallback to general
                try:
                    self.nlp = spacy.load("en_core_sci_md")
                    logger.info("Loaded medical spaCy model")
                except (ImportError, OSError):
                    try:
                        self.nlp = spacy.load("en_core_web_sm")
                        logger.info("Loaded general spaCy model")
                    except (ImportError, OSError):
                        logger.warning("No spaCy model found, using rule-based only")
                        self.use_spacy = False
        except (ImportError, OSError) as e:
            logger.warning("Failed to load spaCy model: %s", e)
            self.use_spacy = False

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        # Create pattern for all negation triggers
        trigger_patterns = []
        for trigger in self.negation_triggers:
            # Escape special regex characters
            escaped = re.escape(trigger.text)
            trigger_patterns.append(escaped)

        # Combined pattern for all triggers
        self.trigger_pattern = re.compile(
            r"\b(" + "|".join(trigger_patterns) + r")\b", re.IGNORECASE
        )

        # Compile pseudo-negation patterns
        self.pseudo_patterns = [
            (re.compile(pattern, re.IGNORECASE), reason)
            for pattern, reason in self.pseudo_negation_patterns
        ]

        # Medical concept pattern (simplified)
        self.concept_pattern = re.compile(
            r"\b(\w+(?:\s+\w+){0,3})\b"  # 1-4 word concepts
        )

    def detect_negations(
        self, text: str, concepts: Optional[List[str]] = None
    ) -> List[NegatedConcept]:
        """Detect negated concepts in text.

        Args:
            text: Medical text to analyze
            concepts: Optional list of specific concepts to check

        Returns:
            List of negated concepts found
        """
        negated_concepts = []

        # Use spaCy if available and loaded
        if self.nlp is not None:
            try:
                doc = self.nlp(text)
                negated_concepts.extend(self._spacy_negation_detection(doc, concepts))
            except (RuntimeError, ValueError, AttributeError) as e:
                logger.warning("SpaCy processing failed: %s", e)
                # Fall through to rule-based detection

        # Always run rule-based detection
        negated_concepts.extend(self._rule_based_detection(text, concepts))

        # Remove duplicates and merge results
        negated_concepts = self._merge_results(negated_concepts)

        # Check for pseudo-negations
        negated_concepts = self._filter_pseudo_negations(text, negated_concepts)

        return negated_concepts

    def _rule_based_detection(
        self, text: str, concepts: Optional[List[str]] = None
    ) -> List[NegatedConcept]:
        """Rule-based negation detection."""
        negated = []

        # Find all negation triggers
        for match in self.trigger_pattern.finditer(text):
            trigger_text = match.group(0)
            trigger_start = match.start()
            trigger_end = match.end()

            # Find matching trigger object
            trigger = next(
                t
                for t in self.negation_triggers
                if t.text.lower() == trigger_text.lower()
            )

            # Determine scope based on trigger type
            if trigger.scope_type in [
                NegationScope.PRE_NEGATION,
                NegationScope.CONDITIONAL,
                NegationScope.UNCERTAIN,
            ]:
                # Look forward for concepts
                scope_text = self._get_forward_scope(
                    text, trigger_end, trigger.max_scope
                )
                scope_start = trigger_end
            else:
                # Look backward for concepts
                scope_text = self._get_backward_scope(
                    text, trigger_start, trigger.max_scope
                )
                scope_start = max(0, trigger_start - len(scope_text))

            # Find concepts in scope
            negated.extend(
                self._find_concepts_in_scope(
                    scope_text,
                    scope_start,
                    trigger,
                    trigger_text,
                    trigger_start,
                    trigger_end,
                    text,
                    concepts,
                )
            )

        return negated

    def _find_concepts_in_scope(
        self,
        scope_text: str,
        scope_start: int,
        trigger: NegationTrigger,
        trigger_text: str,
        trigger_start: int,
        trigger_end: int,
        full_text: str,
        specific_concepts: Optional[List[str]] = None,
    ) -> List[NegatedConcept]:
        """Find negated concepts within scope."""
        negated = []

        if specific_concepts:
            # Check specific concepts
            for concept in specific_concepts:
                if concept.lower() in scope_text.lower():
                    concept_match = re.search(
                        r"\b" + re.escape(concept) + r"\b", scope_text, re.IGNORECASE
                    )
                    if concept_match:
                        negated.append(
                            NegatedConcept(
                                concept=concept,
                                start=scope_start + concept_match.start(),
                                end=scope_start + concept_match.end(),
                                negation_trigger=trigger_text,
                                trigger_start=trigger_start,
                                trigger_end=trigger_end,
                                scope_type=trigger.scope_type,
                                confidence=0.8,
                                context=full_text[
                                    max(0, trigger_start - 20) : min(
                                        len(full_text), trigger_end + 20
                                    )
                                ],
                            )
                        )
        else:
            # Find all medical-looking concepts
            for concept_match in self.concept_pattern.finditer(scope_text):
                concept = concept_match.group(0)
                # Filter out common non-medical words
                if self._is_medical_concept(concept):
                    negated.append(
                        NegatedConcept(
                            concept=concept,
                            start=scope_start + concept_match.start(),
                            end=scope_start + concept_match.end(),
                            negation_trigger=trigger_text,
                            trigger_start=trigger_start,
                            trigger_end=trigger_end,
                            scope_type=trigger.scope_type,
                            confidence=0.6,
                            context=full_text[
                                max(0, trigger_start - 20) : min(
                                    len(full_text), trigger_end + 20
                                )
                            ],
                        )
                    )

        return negated

    def _get_forward_scope(self, text: str, start_pos: int, max_tokens: int) -> str:
        """Get forward scope from position."""
        remaining_text = text[start_pos:]
        tokens = remaining_text.split()

        scope_tokens = []
        for token in tokens[:max_tokens]:
            # Check for scope terminator
            if token.lower() in self.scope_terminators:
                break
            scope_tokens.append(token)

        return " ".join(scope_tokens)

    def _get_backward_scope(self, text: str, end_pos: int, max_tokens: int) -> str:
        """Get backward scope from position."""
        previous_text = text[:end_pos]
        tokens = previous_text.split()

        # Look backward from end
        scope_tokens: List[str] = []
        for i in range(min(max_tokens, len(tokens))):
            token = tokens[-(i + 1)]
            # Check for scope terminator
            if token.lower() in self.scope_terminators:
                break
            scope_tokens.insert(0, token)

        return " ".join(scope_tokens)

    def _spacy_negation_detection(
        self, doc: Any, concepts: Optional[List[str]] = None
    ) -> List[NegatedConcept]:
        """SpaCy-based negation detection."""
        negated = []

        # Use dependency parsing to find negations
        for token in doc:
            if token.dep_ == "neg":
                # Found negation - check what it modifies
                head = token.head

                # Get the span that includes the negated concept
                if head.pos_ in ["NOUN", "VERB", "ADJ"]:
                    # Check if it's a medical concept
                    if concepts and head.text in concepts:
                        negated.append(
                            NegatedConcept(
                                concept=head.text,
                                start=head.idx,
                                end=head.idx + len(head.text),
                                negation_trigger=token.text,
                                trigger_start=token.idx,
                                trigger_end=token.idx + len(token.text),
                                scope_type=NegationScope.PRE_NEGATION,
                                confidence=0.9,
                                context=doc.text[
                                    max(0, token.idx - 20) : min(
                                        len(doc.text), head.idx + 20
                                    )
                                ],
                            )
                        )

        return negated

    def _is_medical_concept(self, text: str) -> bool:
        """Check if text is likely a medical concept."""
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in MEDICAL_CONCEPT_INDICATORS)

    def _merge_results(
        self, negated_concepts: List[NegatedConcept]
    ) -> List[NegatedConcept]:
        """Merge duplicate detections."""
        merged = []
        seen = set()

        for concept in negated_concepts:
            key = (concept.concept, concept.start, concept.end)
            if key not in seen:
                seen.add(key)
                merged.append(concept)
            else:
                # Update confidence if higher
                for m in merged:
                    if (m.concept, m.start, m.end) == key:
                        m.confidence = max(m.confidence, concept.confidence)

        return merged

    def _filter_pseudo_negations(
        self, text: str, negated_concepts: List[NegatedConcept]
    ) -> List[NegatedConcept]:
        """Filter out pseudo-negations."""
        filtered = []

        for concept in negated_concepts:
            # Check against pseudo-negation patterns
            context = text[
                max(0, concept.trigger_start - 10) : min(len(text), concept.end + 10)
            ]

            for pattern, reason in self.pseudo_patterns:
                if pattern.search(context):
                    concept.is_pseudo_negation = True
                    concept.confidence *= 0.3  # Reduce confidence
                    logger.debug("Pseudo-negation detected: %s", reason)
                    break

            # Special cases
            if (
                "no significant" in concept.negation_trigger.lower()
                or "no change" in concept.negation_trigger.lower()
            ):
                concept.is_pseudo_negation = True
                concept.confidence *= 0.5

            filtered.append(concept)

        return filtered

    def get_negation_status(
        self, text: str, concept: str
    ) -> Tuple[bool, float, Optional[str]]:
        """Check if a specific concept is negated in text.

        Returns:
            Tuple of (is_negated, confidence, negation_phrase)
        """
        negated_concepts = self.detect_negations(text, [concept])

        for neg_concept in negated_concepts:
            if neg_concept.concept.lower() == concept.lower():
                return (
                    not neg_concept.is_pseudo_negation,
                    neg_concept.confidence,
                    neg_concept.negation_trigger,
                )

        return (False, 1.0, None)

    def annotate_negations(self, text: str) -> str:
        """Annotate text with negation markers.

        Returns:
            Annotated text with [NEG] and [/NEG] markers
        """
        negated_concepts = self.detect_negations(text)

        # Sort by position (reverse to avoid offset issues)
        negated_concepts.sort(key=lambda x: x.start, reverse=True)

        annotated = text
        for concept in negated_concepts:
            if not concept.is_pseudo_negation:
                annotated = (
                    annotated[: concept.start]
                    + "[NEG]"
                    + annotated[concept.start : concept.end]
                    + "[/NEG]"
                    + annotated[concept.end :]
                )

        return annotated
