"""Punctuation Restoration Module for Medical Transcriptions.

This module handles intelligent punctuation restoration for
medical transcriptions, including sentence boundaries and
medical-specific punctuation rules.

Note: Medical transcriptions contain PHI. Ensure all processed text is
encrypted both in transit and at rest. Implement proper access control
to restrict punctuation restoration operations to authorized users only.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from src.security import requires_phi_access

logger = logging.getLogger(__name__)


class PunctuationType(Enum):
    """Types of punctuation marks."""

    PERIOD = "."
    COMMA = ","
    QUESTION = "?"
    EXCLAMATION = "!"
    COLON = ":"
    SEMICOLON = ";"
    DASH = "-"
    PARENTHESIS_OPEN = "("
    PARENTHESIS_CLOSE = ")"


class SentenceType(Enum):
    """Types of sentences in medical context."""

    STATEMENT = "statement"
    QUESTION = "question"
    INSTRUCTION = "instruction"
    LIST_ITEM = "list_item"
    MEASUREMENT = "measurement"


@dataclass
class PunctuationRule:
    """Rule for applying punctuation."""

    pattern: str  # Regex pattern
    punctuation: PunctuationType
    position: str  # "before", "after", or "replace"
    context: Optional[str] = None  # Medical context
    confidence_threshold: float = 0.8

    def __post_init__(self) -> None:
        """Compile regex pattern."""
        self.compiled_pattern = re.compile(self.pattern, re.IGNORECASE)


@dataclass
class PunctuationConfig:
    """Configuration for punctuation restoration."""

    # General settings
    enable_sentence_boundaries: bool = True
    enable_commas: bool = True
    enable_medical_punctuation: bool = True

    # Sentence ending
    min_sentence_length: int = 3
    max_sentence_length: int = 50

    # Medical-specific
    preserve_medical_abbreviations: bool = True
    format_measurements: bool = True
    format_lists: bool = True

    # Machine learning
    use_ml_model: bool = False
    ml_model_path: Optional[str] = None
    ml_confidence_threshold: float = 0.7

    # Style
    oxford_comma: bool = True
    space_before_colon: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enable_sentence_boundaries": self.enable_sentence_boundaries,
            "enable_commas": self.enable_commas,
            "enable_medical_punctuation": self.enable_medical_punctuation,
            "min_sentence_length": self.min_sentence_length,
            "max_sentence_length": self.max_sentence_length,
            "preserve_medical_abbreviations": self.preserve_medical_abbreviations,
            "format_measurements": self.format_measurements,
            "format_lists": self.format_lists,
            "use_ml_model": self.use_ml_model,
            "ml_confidence_threshold": self.ml_confidence_threshold,
            "oxford_comma": self.oxford_comma,
            "space_before_colon": self.space_before_colon,
        }


class PunctuationRestorer:
    """Restores punctuation in medical transcriptions using rule-based and ML approaches."""

    def __init__(self, config: Optional[PunctuationConfig] = None):
        """
        Initialize the punctuation restorer.

        Args:
            config: Punctuation configuration
        """
        self.config = config or PunctuationConfig()

        # Medical abbreviations that should keep their periods
        self.medical_abbreviations = {
            "Dr.",
            "M.D.",
            "Ph.D.",
            "R.N.",
            "B.P.",
            "H.R.",
            "R.R.",
            "a.m.",
            "p.m.",
            "q.d.",
            "b.i.d.",
            "t.i.d.",
            "q.i.d.",
            "p.r.n.",
            "p.o.",
            "i.v.",
            "i.m.",
            "subq.",
            "mg.",
            "ml.",
            "cc.",
            "mcg.",
            "U.",
            "IU.",
            "mEq.",
            "vs.",
            "c/o",
            "s/p",
        }

        # Initialize rules
        self.rules = self._initialize_rules()

        # Sentence ending indicators
        self.sentence_endings = {
            "period": [
                "diagnosed",
                "prescribed",
                "recommended",
                "noted",
                "observed",
                "reported",
                "completed",
                "normal",
            ],
            "question": [
                "what",
                "when",
                "where",
                "why",
                "how",
                "is",
                "are",
                "does",
                "do",
                "can",
                "could",
                "should",
            ],
            "colon": [
                "following",
                "includes",
                "such as",
                "namely",
                "as follows",
                "revealed",
                "showed",
            ],
        }

        # Medical context patterns
        self.medical_patterns = {
            "vitals": re.compile(
                r"(blood pressure|bp|heart rate|hr|temperature|temp|respiratory rate|rr)\s*(\d+)",
                re.I,
            ),
            "medication": re.compile(r"(\w+)\s+(\d+)\s*(mg|mcg|ml|units?)", re.I),
            "measurement": re.compile(
                r"(\d+\.?\d*)\s*(cm|mm|kg|lbs?|degrees?|percent|%)", re.I
            ),
            "list_marker": re.compile(
                r"(first|second|third|next|then|finally|also|additionally)", re.I
            ),
        }

        logger.info("PunctuationRestorer initialized")

    def _initialize_rules(self) -> List[PunctuationRule]:
        """Initialize punctuation rules."""
        rules = []

        # Medical measurement rules
        rules.append(
            PunctuationRule(
                pattern=r"(\d+)\s+(over)\s+(\d+)",
                punctuation=PunctuationType.DASH,
                position="replace",
                context="blood_pressure",
            )
        )

        # List item rules
        rules.append(
            PunctuationRule(
                pattern=r"(first|second|third|number \w+)\s+",
                punctuation=PunctuationType.COMMA,
                position="after",
                context="list",
            )
        )

        # Medical abbreviation rules
        rules.append(
            PunctuationRule(
                pattern=r"\b(mg|ml|mcg|cc)\b",
                punctuation=PunctuationType.PERIOD,
                position="after",
                context="dosage",
            )
        )

        # Time expression rules
        rules.append(
            PunctuationRule(
                pattern=r"(\d{1,2})\s+(am|pm)",
                punctuation=PunctuationType.PERIOD,
                position="after",
                context="time",
            )
        )

        return rules

    @requires_phi_access("read")
    def restore_punctuation(
        self,
        text: str,
        word_confidences: Optional[List[float]] = None,
        _user_id: str = "system",
    ) -> str:
        """
        Restore punctuation in the given text.

        Note: Text may contain PHI - handle with appropriate security measures.

        Args:
            text: Input text without punctuation
            word_confidences: Optional confidence scores for each word

        Returns:
            Text with restored punctuation
        """
        # Preprocess text
        text = self._preprocess_text(text)
        words = text.split()

        if not words:
            return text
        # Apply rule-based punctuation
        if not self.config.use_ml_model:
            punctuated_text = self._apply_rules(words)
        else:
            # Use ML model if configured
            punctuated_text = self._apply_ml_punctuation(words, word_confidences)

        # Post-process
        punctuated_text = self._postprocess_text(punctuated_text)

        return punctuated_text

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text before punctuation restoration."""
        # Normalize whitespace
        text = " ".join(text.split())

        # Preserve medical abbreviations
        if self.config.preserve_medical_abbreviations:
            for abbr in self.medical_abbreviations:
                # Protect abbreviations from modification
                text = text.replace(abbr.replace(".", ""), abbr)

        return text

    def _apply_rules(self, words: List[str]) -> str:
        """Apply rule-based punctuation."""
        result = []

        for i, word in enumerate(words):
            # Check for sentence boundaries
            if self.config.enable_sentence_boundaries:
                if self._is_sentence_end(words, i):
                    word = word + "."

            # Check for commas
            if self.config.enable_commas:
                if self._needs_comma(words, i):
                    word = word + ","

            # Check for medical-specific punctuation
            if self.config.enable_medical_punctuation:
                word = self._apply_medical_punctuation(word, words, i)

            result.append(word)

        return " ".join(result)

    def _is_sentence_end(self, words: List[str], index: int) -> bool:
        """Determine if current position is a sentence end."""
        if index >= len(words) - 1:
            return True

        current_word = words[index].lower()
        next_word = words[index + 1].lower() if index + 1 < len(words) else ""

        # Check if current word is a sentence ending indicator
        if current_word in self.sentence_endings["period"]:
            return True

        # Check sentence length
        words_since_start = index - self._find_last_sentence_end(words, index)
        if words_since_start >= self.config.max_sentence_length:
            return True

        # Check if next word starts new sentence (capitalized)
        if next_word and next_word[0].isupper() and index > 0:
            if words_since_start >= self.config.min_sentence_length:
                return True

        return False

    def _needs_comma(self, words: List[str], index: int) -> bool:
        """Determine if current position needs a comma."""
        if index >= len(words) - 1:
            return False

        current_word = words[index].lower()

        # List items
        if self._is_list_item(words, index):
            return True

        # Before conjunctions in compound sentences
        if index > 0 and current_word in ["and", "but", "or", "yet"]:
            # Check if it's connecting two clauses
            if self._is_clause_boundary(words, index):
                return True

        # After introductory phrases
        if index > 2 and current_word in ["however", "therefore", "moreover"]:
            return True

        return False

    def _apply_medical_punctuation(
        self, word: str, words: List[str], index: int
    ) -> str:
        """Apply medical-specific punctuation rules."""
        # Check measurement patterns
        if index < len(words) - 1:
            current_next = f"{word} {words[index + 1]}"

            # Blood pressure format (e.g., "120 over 80" -> "120/80")
            bp_match = re.match(r"(\d+)\s+over\s+(\d+)", current_next, re.I)
            if bp_match:
                return f"{bp_match.group(1)}/{bp_match.group(2)}"

            # Dosage format
            dose_match = self.medical_patterns["medication"].match(current_next)
            if dose_match:
                # Already formatted correctly
                pass

        # Apply custom rules
        for rule in self.rules:
            if rule.compiled_pattern.match(word):
                if rule.position == "after":
                    word = word + rule.punctuation.value
                elif rule.position == "before":
                    word = rule.punctuation.value + word

        return word

    def _postprocess_text(self, text: str) -> str:
        """Post-process the punctuated text."""
        # Fix spacing around punctuation
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)
        text = re.sub(r"([.,;:!?])(\w)", r"\1 \2", text)

        # Capitalize first letter of sentences
        text = re.sub(
            r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text
        )

        # Format measurements
        if self.config.format_measurements:
            text = self._format_measurements(text)

        # Format lists
        if self.config.format_lists:
            text = self._format_lists(text)

        return text

    def _find_last_sentence_end(self, words: List[str], current_index: int) -> int:
        """Find the index of the last sentence end before current position."""
        for i in range(current_index - 1, -1, -1):
            if words[i].endswith((".", "!", "?")):
                return i
        return -1

    def _is_list_item(self, words: List[str], index: int) -> bool:
        """Check if current position is a list item."""
        if index >= len(words):
            return False

        word = words[index].lower()
        return bool(self.medical_patterns["list_marker"].match(word))

    def _is_clause_boundary(self, words: List[str], index: int) -> bool:
        """Check if position is a clause boundary."""
        # Simplified check - would use more sophisticated NLP in production
        if index < 3 or index >= len(words) - 3:
            return False

        # Check for subject-verb patterns before and after
        return True  # Placeholder

    def _format_measurements(self, text: str) -> str:
        """Format medical measurements."""
        # Blood pressure
        text = re.sub(r"(\d+)\s*/\s*(\d+)", r"\1/\2", text)

        # Temperature
        text = re.sub(r"(\d+\.?\d*)\s*degrees?\s*([CF])", r"\1°\2", text)

        # Percentages
        text = re.sub(r"(\d+)\s*percent", r"\1%", text)

        return text

    def _format_lists(self, text: str) -> str:
        """Format numbered or bulleted lists."""
        # Simple numbered list detection
        lines = text.split(". ")
        formatted_lines = []

        for line in lines:
            if self.medical_patterns["list_marker"].match(line):
                line = f"\n• {line}"
            formatted_lines.append(line)

        return ". ".join(formatted_lines)

    def _apply_ml_punctuation(
        self, words: List[str], confidences: Optional[List[float]]
    ) -> str:
        """Apply ML-based punctuation using transformer model and confidence scores.

        This uses a pre-trained punctuation restoration model that considers:
        - Word context and semantics
        - Confidence scores from ASR
        - Sentence boundaries
        - Medical terminology patterns
        """
        try:
            # Try to use a transformer-based punctuation model
            from transformers import (  # noqa: PLC0415
                AutoModelForTokenClassification,
                AutoTokenizer,
                pipeline,
            )

            # Initialize punctuation restoration pipeline
            # Using a model fine-tuned for punctuation restoration
            model_name = "oliverguhr/fullstop-punctuation-multilang-large"

            # Check if model is cached, otherwise download
            try:
                tokenizer = AutoTokenizer.from_pretrained(
                    model_name, local_files_only=True
                )
                model = AutoModelForTokenClassification.from_pretrained(
                    model_name, local_files_only=True
                )
                logger.info("Using cached punctuation model")
            except (AttributeError, ImportError, OSError, ValueError):
                logger.info("Downloading punctuation restoration model...")
                tokenizer = AutoTokenizer.from_pretrained(model_name)
                model = AutoModelForTokenClassification.from_pretrained(model_name)

            # Create pipeline
            punct_pipeline = pipeline(
                "token-classification",
                model=model,
                tokenizer=tokenizer,
                aggregation_strategy="none",
                device=-1,  # CPU, use 0 for GPU if available
            )

            # Join words for processing
            text = " ".join(words)

            # If we have confidence scores, use them to identify uncertain regions
            if confidences and len(confidences) == len(words):
                # Create confidence-weighted text segments
                segments: List[Tuple[str, float]] = []
                current_segment: List[str] = []
                current_confidence: List[float] = []

                for word, conf in zip(words, confidences):
                    if conf < 0.5:  # Low confidence threshold
                        if current_segment:
                            segments.append(
                                (
                                    " ".join(current_segment),
                                    float(np.mean(current_confidence)),
                                )
                            )
                            current_segment = []
                            current_confidence = []
                        segments.append((word, conf))
                    else:
                        current_segment.append(word)
                        current_confidence.append(conf)

                if current_segment:
                    segments.append(
                        (" ".join(current_segment), float(np.mean(current_confidence)))
                    )

                # Process each segment
                punctuated_segments = []
                for segment_text, segment_conf in segments:
                    if segment_conf < 0.5:
                        # Keep low confidence segments as-is
                        punctuated_segments.append(segment_text)
                    else:
                        # Apply ML punctuation to high confidence segments
                        result = punct_pipeline(segment_text)
                        punctuated = self._reconstruct_from_predictions(result)
                        punctuated_segments.append(punctuated)

                return " ".join(punctuated_segments)
            else:
                # Process entire text if no confidence scores
                result = punct_pipeline(text)
                return self._reconstruct_from_predictions(result)

        except (AttributeError, ImportError, OSError, ValueError) as e:
            logger.error("ML punctuation failed: %s, falling back to rules", e)
            return self._apply_rules(words)

    def _reconstruct_from_predictions(self, predictions: List[Dict]) -> str:
        """Reconstruct punctuated text from model predictions."""
        # Model predicts punctuation after each token
        tokens = []

        for i, pred in enumerate(predictions):
            token = pred["word"].replace("▁", " ").strip()

            # Get the highest scoring punctuation prediction
            label = pred["entity"]

            # Map model labels to punctuation
            punct_map = {
                "LABEL_0": "",  # No punctuation
                "LABEL_1": ".",  # Period
                "LABEL_2": ",",  # Comma
                "LABEL_3": "?",  # Question mark
                "LABEL_4": "-",  # Dash
                "LABEL_5": ":",  # Colon
                "LABEL_6": ";",  # Semicolon
                "LABEL_7": "!",  # Exclamation
                "0": "",
                ".": ".",
                ",": ",",
                "?": "?",
                ":": ":",
                ";": ";",
                "!": "!",
                "-": "-",
            }

            # Add token
            if i == 0 or predictions[i - 1]["end"] != pred["start"]:
                tokens.append(" ")
            tokens.append(token)

            # Add punctuation if predicted
            punct = punct_map.get(label, "")
            if punct:
                tokens.append(punct)

        # Clean up and return
        result = "".join(tokens).strip()
        result = " ".join(result.split())  # Normalize whitespace

        # Capitalize sentences
        sentences = result.split(". ")
        sentences = [s[0].upper() + s[1:] if s else s for s in sentences]
        return ". ".join(sentences)

    def _apply_confidence_based_rules(
        self, words: List[str], confidences: List[float]
    ) -> str:
        """Apply rule-based punctuation with confidence-based adjustments."""
        punctuated_words = []

        for i, (word, conf) in enumerate(zip(words, confidences)):
            # Add word
            punctuated_words.append(word)

            # Decide on punctuation based on confidence and context
            if i < len(words) - 1:
                # next_word = words[i + 1]  # Reserved for future use
                next_conf = confidences[i + 1]

                # High confidence boundary detection
                if conf > 0.9 and next_conf < 0.6:
                    # Likely sentence boundary
                    punctuated_words.append(".")
                elif conf > 0.8:
                    # Check for comma placement
                    if word.lower() in [
                        "however",
                        "therefore",
                        "moreover",
                        "furthermore",
                    ]:
                        punctuated_words.append(",")
                    elif i < len(words) - 2 and words[i + 2].lower() in [
                        "and",
                        "or",
                        "but",
                    ]:
                        if conf > 0.85:
                            punctuated_words.append(",")

            # End of text
            elif i == len(words) - 1 and conf > 0.7:
                if not word[-1] in ".!?":
                    punctuated_words.append(".")

        text = " ".join(punctuated_words)

        # Clean up spacing around punctuation
        text = text.replace(" .", ".")
        text = text.replace(" ,", ",")
        text = text.replace(" ?", "?")
        text = text.replace(" !", "!")

        # Capitalize sentences
        sentences = text.split(". ")
        sentences = [s[0].upper() + s[1:] if s else s for s in sentences]

        return ". ".join(sentences)

    def restore_from_segments(
        self, segments: List[Dict[str, Any]], join_segments: bool = True
    ) -> Union[str, List[str]]:
        """
        Restore punctuation from transcription segments.

        Args:
            segments: List of transcription segments with text and metadata
            join_segments: Whether to join segments into single text

        Returns:
            Punctuated text or list of punctuated segments
        """
        punctuated_segments = []

        for segment in segments:
            text = segment.get("text", "")
            confidence = segment.get("confidence", 1.0)

            # Only process if confidence meets threshold
            if confidence >= self.config.ml_confidence_threshold:
                punctuated_text = self.restore_punctuation(text)
            else:
                # Keep original for low confidence
                punctuated_text = text

            punctuated_segments.append(punctuated_text)

        if join_segments:
            return " ".join(punctuated_segments)

        return punctuated_segments

    def get_statistics(
        self, original_text: str, punctuated_text: str
    ) -> Dict[str, Any]:
        """Get statistics about punctuation restoration."""
        original_words = original_text.split()
        punctuated_words = punctuated_text.split()

        # Count punctuation marks
        punctuation_counts = {
            "periods": punctuated_text.count("."),
            "commas": punctuated_text.count(","),
            "questions": punctuated_text.count("?"),
            "exclamations": punctuated_text.count("!"),
            "colons": punctuated_text.count(":"),
            "semicolons": punctuated_text.count(";"),
        }

        return {
            "original_word_count": len(original_words),
            "punctuated_word_count": len(punctuated_words),
            "sentences_created": punctuation_counts["periods"]
            + punctuation_counts["questions"]
            + punctuation_counts["exclamations"],
            "punctuation_counts": punctuation_counts,
            "avg_sentence_length": len(punctuated_words)
            / max(1, punctuation_counts["periods"]),
        }
