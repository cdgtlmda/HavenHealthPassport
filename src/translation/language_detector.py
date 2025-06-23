"""Language Detection Module - detects languages in text content."""

import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)


class LanguageDetector:
    """Detect language from text."""

    def __init__(self) -> None:
        """Initialize language detector with language indicators."""
        # Common words/patterns for major languages
        self.language_indicators = {
            "en": ["the", "and", "is", "in", "to", "of", "for", "with"],
            "es": ["el", "la", "de", "en", "y", "los", "las", "por"],
            "fr": ["le", "de", "et", "la", "les", "pour", "dans", "avec"],
            "de": ["der", "die", "das", "und", "ist", "für", "mit", "von"],
            "ar": ["في", "من", "على", "إلى", "هذا", "التي", "ذلك"],
            "zh": ["的", "是", "在", "有", "和", "了", "不", "我"],
            "ja": ["の", "は", "を", "に", "が", "と", "で", "た"],
            "hi": ["है", "की", "के", "में", "और", "को", "से", "पर"],
            "pt": ["o", "a", "de", "e", "do", "da", "em", "para"],
            "ru": ["и", "в", "на", "с", "по", "для", "это", "как"],
        }

    async def detect_language(self, text: str) -> Tuple[str, float]:
        """Detect the primary language of text."""
        if not text:
            return ("en", 0.0)

        # Simple detection based on common words
        scores = {}
        text_lower = text.lower()

        for lang, indicators in self.language_indicators.items():
            score = sum(1 for word in indicators if word in text_lower)
            if score > 0:
                scores[lang] = score

        if not scores:
            return ("en", 0.5)  # Default to English

        # Get the language with highest score
        best_lang = max(scores, key=lambda x: scores[x])
        confidence = min(scores[best_lang] / 10.0, 1.0)

        return (best_lang, confidence)

    async def detect_languages(self, text: str) -> List[Tuple[str, float]]:
        """Detect multiple languages in text."""
        # For now, just detect primary language
        primary = await self.detect_language(text)
        return [primary] if primary[1] > 0 else [("en", 0.5)]

    def detect_script(self, text: str) -> str:
        """Detect the script type of text."""
        if re.search(r"[\u0600-\u06FF]", text):
            return "Arabic"
        elif re.search(r"[\u4E00-\u9FFF]", text):
            return "Chinese"
        elif re.search(r"[\u3040-\u309F\u30A0-\u30FF]", text):
            return "Japanese"
        elif re.search(r"[\u0400-\u04FF]", text):
            return "Cyrillic"
        elif re.search(r"[\u0590-\u05FF]", text):
            return "Hebrew"
        elif re.search(r"[\u0900-\u097F]", text):
            return "Devanagari"
        else:
            return "Latin"
