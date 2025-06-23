"""Confidence Thresholds - Manages confidence thresholds for machine translation."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.translation.quality.quality_scoring import QualityMetrics
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ConfidenceThreshold:
    """Confidence threshold configuration."""

    domain: str
    language_pair: str  # e.g., "en-es"
    min_confidence: float  # Minimum acceptable confidence
    require_human_review_below: float  # Always require human review below this
    auto_approve_above: float  # Can auto-approve above this
    factors: Dict[str, float]  # Adjustment factors


class ConfidenceThresholdManager:
    """Manages confidence thresholds for translation quality."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize confidence threshold manager."""
        self.thresholds: Dict[str, ConfidenceThreshold] = {}
        self.default_thresholds = self._get_default_thresholds()

        if config_path:
            self._load_config(config_path)
        else:
            self._initialize_defaults()

    def _get_default_thresholds(self) -> Dict[str, ConfidenceThreshold]:
        """Get default confidence thresholds."""
        defaults = {}

        # Medical domain - highest thresholds
        defaults["medical_*"] = ConfidenceThreshold(
            domain="medical",
            language_pair="*",
            min_confidence=0.85,
            require_human_review_below=0.9,
            auto_approve_above=0.95,
            factors={"length": 0.1, "complexity": 0.2},
        )

        # Legal domain - high thresholds
        defaults["legal_*"] = ConfidenceThreshold(
            domain="legal",
            language_pair="*",
            min_confidence=0.8,
            require_human_review_below=0.85,
            auto_approve_above=0.9,
            factors={"terminology": 0.3, "accuracy": 0.3},
        )

        # General domain - moderate thresholds
        defaults["general_*"] = ConfidenceThreshold(
            domain="general",
            language_pair="*",
            min_confidence=0.7,
            require_human_review_below=0.75,
            auto_approve_above=0.85,
            factors={"fluency": 0.3, "completeness": 0.2},
        )

        # UI/Interface - lower thresholds for simple text
        defaults["ui_*"] = ConfidenceThreshold(
            domain="ui",
            language_pair="*",
            min_confidence=0.6,
            require_human_review_below=0.65,
            auto_approve_above=0.8,
            factors={"brevity": 0.2, "clarity": 0.3},
        )

        return defaults

    def _initialize_defaults(self) -> None:
        """Initialize with default thresholds."""
        self.thresholds = self.default_thresholds.copy()

    def _load_config(self, config_path: str) -> None:
        """Load thresholds from configuration file."""
        path = Path(config_path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)

            for key, threshold_data in config.get("thresholds", {}).items():
                self.thresholds[key] = ConfidenceThreshold(**threshold_data)
        else:
            logger.warning(f"Config file not found: {config_path}")
            self._initialize_defaults()

    def get_threshold(self, domain: str, language_pair: str) -> ConfidenceThreshold:
        """Get confidence threshold for domain and language pair."""
        # Try exact match
        key = f"{domain}_{language_pair}"
        if key in self.thresholds:
            return self.thresholds[key]

        # Try domain wildcard
        domain_key = f"{domain}_*"
        if domain_key in self.thresholds:
            return self.thresholds[domain_key]

        # Try language pair wildcard
        lang_key = f"general_{language_pair}"
        if lang_key in self.thresholds:
            return self.thresholds[lang_key]

        # Default to general
        return self.thresholds.get("general_*", self.default_thresholds["general_*"])

    def requires_human_review(
        self,
        confidence_score: float,
        domain: str,
        language_pair: str,
        quality_metrics: Optional[QualityMetrics] = None,
    ) -> Tuple[bool, str]:
        """Determine if human review is required."""
        threshold = self.get_threshold(domain, language_pair)

        # Always require review below threshold
        if confidence_score < threshold.require_human_review_below:
            return (
                True,
                f"Confidence {confidence_score:.2f} below threshold {threshold.require_human_review_below:.2f}",
            )

        # Check quality metrics if provided
        if quality_metrics:
            # Medical domain special checks
            if domain == "medical" and quality_metrics.terminology_score < 0.9:
                return (
                    True,
                    f"Medical terminology score {quality_metrics.terminology_score:.2f} too low",
                )

            # Check overall quality
            if quality_metrics.overall_score < threshold.min_confidence:
                return (
                    True,
                    f"Overall quality {quality_metrics.overall_score:.2f} below minimum {threshold.min_confidence:.2f}",
                )

        return False, "Meets quality requirements"

    def can_auto_approve(
        self,
        confidence_score: float,
        domain: str,
        language_pair: str,
        quality_metrics: Optional[QualityMetrics] = None,
    ) -> bool:
        """Check if translation can be auto-approved."""
        threshold = self.get_threshold(domain, language_pair)

        # Must exceed auto-approve threshold
        if confidence_score < threshold.auto_approve_above:
            return False

        # Additional checks for quality metrics
        if quality_metrics:
            # All individual scores must be good
            if any(
                [
                    quality_metrics.fluency_score < 0.8,
                    quality_metrics.accuracy_score < 0.85,
                    quality_metrics.completeness_score < 0.9,
                    quality_metrics.terminology_score < 0.85,
                    quality_metrics.formatting_score < 0.8,
                ]
            ):
                return False

        return True

    def adjust_threshold(
        self, domain: str, language_pair: str, adjustment: float
    ) -> None:
        """Adjust thresholds based on performance."""
        key = f"{domain}_{language_pair}"
        threshold = self.get_threshold(domain, language_pair)

        # Create adjusted threshold
        adjusted = ConfidenceThreshold(
            domain=threshold.domain,
            language_pair=language_pair,
            min_confidence=min(1.0, threshold.min_confidence + adjustment),
            require_human_review_below=min(
                1.0, threshold.require_human_review_below + adjustment
            ),
            auto_approve_above=min(1.0, threshold.auto_approve_above + adjustment),
            factors=threshold.factors.copy(),
        )

        self.thresholds[key] = adjusted

        logger.info(f"Adjusted thresholds for {key} by {adjustment}")

    def save_config(self, output_path: str) -> None:
        """Save current thresholds to configuration file."""
        thresholds_data: Dict[str, Dict[str, Any]] = {}
        config: Dict[str, Any] = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "thresholds": thresholds_data,
        }

        for key, threshold in self.thresholds.items():
            thresholds_data[key] = {
                "domain": threshold.domain,
                "language_pair": threshold.language_pair,
                "min_confidence": threshold.min_confidence,
                "require_human_review_below": threshold.require_human_review_below,
                "auto_approve_above": threshold.auto_approve_above,
                "factors": threshold.factors,
            }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        logger.info(f"Saved threshold configuration to {output_path}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about configured thresholds."""
        by_domain: Dict[str, int] = {}
        average_thresholds: Dict[str, float] = {
            "min_confidence": 0.0,
            "require_human_review": 0.0,
            "auto_approve": 0.0,
        }
        stats: Dict[str, Any] = {
            "total_configurations": len(self.thresholds),
            "by_domain": by_domain,
            "average_thresholds": average_thresholds,
        }

        # Calculate statistics
        for threshold in self.thresholds.values():
            domain = threshold.domain
            by_domain[domain] = by_domain.get(domain, 0) + 1

            average_thresholds["min_confidence"] += threshold.min_confidence
            average_thresholds[
                "require_human_review"
            ] += threshold.require_human_review_below
            average_thresholds["auto_approve"] += threshold.auto_approve_above

        # Calculate averages
        count = len(self.thresholds)
        if count > 0:
            for key in average_thresholds:
                average_thresholds[key] /= count

        return stats
