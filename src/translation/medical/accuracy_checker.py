"""Medical Translation Accuracy Checker.

This module provides automated accuracy checking for medical translations
using AI models, medical dictionaries, and rule-based validation.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AccuracyCheckType(str, Enum):
    """Types of accuracy checks."""

    SEMANTIC_SIMILARITY = "semantic_similarity"
    MEDICAL_TERM_MAPPING = "medical_term_mapping"
    BACK_TRANSLATION = "back_translation"
    CONTEXT_PRESERVATION = "context_preservation"
    CLINICAL_EQUIVALENCE = "clinical_equivalence"
    SAFETY_CRITICAL = "safety_critical"
    NUMERICAL_ACCURACY = "numerical_accuracy"
    UNIT_CONSISTENCY = "unit_consistency"


@dataclass
class AccuracyScore:
    """Accuracy score for a translation."""

    overall_score: float  # 0-100
    component_scores: Dict[AccuracyCheckType, float]
    confidence: float  # 0-1
    issues_found: List[str]
    suggestions: List[str]


@dataclass
class AccuracyCheckResult:
    """Result of accuracy checking."""

    translation_id: str
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    accuracy_score: AccuracyScore
    is_acceptable: bool
    requires_human_review: bool
    checked_at: datetime = field(default_factory=datetime.utcnow)


class MedicalAccuracyChecker:
    """Checks accuracy of medical translations."""

    # Thresholds for different check types
    ACCURACY_THRESHOLDS = {
        AccuracyCheckType.SEMANTIC_SIMILARITY: 0.85,
        AccuracyCheckType.MEDICAL_TERM_MAPPING: 0.95,
        AccuracyCheckType.BACK_TRANSLATION: 0.80,
        AccuracyCheckType.CONTEXT_PRESERVATION: 0.90,
        AccuracyCheckType.CLINICAL_EQUIVALENCE: 0.95,
        AccuracyCheckType.SAFETY_CRITICAL: 0.99,
        AccuracyCheckType.NUMERICAL_ACCURACY: 1.0,
        AccuracyCheckType.UNIT_CONSISTENCY: 1.0,
    }

    # Critical medical contexts requiring higher accuracy
    CRITICAL_CONTEXTS = {
        "dosage_instructions",
        "allergy_warnings",
        "contraindications",
        "emergency_procedures",
        "surgical_consent",
        "medication_errors",
        "life_threatening_conditions",
    }

    def __init__(self, embedding_service: Optional[Any] = None):
        """Initialize accuracy checker."""
        self.embedding_service = embedding_service
        self.check_functions: Dict[AccuracyCheckType, Callable] = {
            AccuracyCheckType.SEMANTIC_SIMILARITY: self._check_semantic_similarity,
            AccuracyCheckType.MEDICAL_TERM_MAPPING: self._check_medical_terms,
            AccuracyCheckType.BACK_TRANSLATION: self._check_back_translation,
            AccuracyCheckType.CONTEXT_PRESERVATION: self._check_context_preservation,
            AccuracyCheckType.CLINICAL_EQUIVALENCE: self._check_clinical_equivalence,
            AccuracyCheckType.SAFETY_CRITICAL: self._check_safety_critical,
            AccuracyCheckType.NUMERICAL_ACCURACY: self._check_numerical_accuracy,
            AccuracyCheckType.UNIT_CONSISTENCY: self._check_unit_consistency,
        }
        self.medical_term_cache: Dict[str, Any] = {}
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self.back_translation_cache: Dict[str, Any] = {}

    async def check_accuracy(
        self,
        source_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
        context: Optional[Dict[str, Any]] = None,
        check_types: Optional[List[AccuracyCheckType]] = None,
    ) -> AccuracyCheckResult:
        """Perform comprehensive accuracy checking."""
        context = context or {}
        translation_id = context.get("translation_id", "unknown")

        # Determine which checks to run
        if check_types is None:
            check_types = self._determine_required_checks(context)

        # Run accuracy checks
        component_scores = {}
        issues = []
        suggestions: List[str] = []

        for check_type in check_types:
            check_func = self.check_functions.get(check_type)
            if check_func:
                try:
                    score, check_issues, check_suggestions = await check_func(
                        source_text,
                        translated_text,
                        source_language,
                        target_language,
                        context,
                    )
                    component_scores[check_type] = score
                    issues.extend(check_issues)
                    suggestions.extend(check_suggestions)
                except (KeyError, ValueError, AttributeError, TypeError) as e:
                    logger.error(f"Error in {check_type} check: {e}")
                    component_scores[check_type] = 0.0
                    issues.append(f"Failed to perform {check_type} check")

        # Calculate overall score
        overall_score, confidence = self._calculate_overall_score(
            component_scores, context
        )

        # Determine if acceptable
        is_acceptable = self._is_acceptable(overall_score, component_scores, context)

        # Check if human review needed
        requires_review = self._requires_human_review(
            overall_score, component_scores, issues, context
        )

        accuracy_score = AccuracyScore(
            overall_score=overall_score,
            component_scores=component_scores,
            confidence=confidence,
            issues_found=issues,
            suggestions=suggestions,
        )

        return AccuracyCheckResult(
            translation_id=translation_id,
            source_text=source_text,
            translated_text=translated_text,
            source_language=source_language,
            target_language=target_language,
            accuracy_score=accuracy_score,
            is_acceptable=is_acceptable,
            requires_human_review=requires_review,
        )

    def _determine_required_checks(
        self, context: Dict[str, Any]
    ) -> List[AccuracyCheckType]:
        """Determine which accuracy checks are required based on context."""
        required_checks = [
            AccuracyCheckType.SEMANTIC_SIMILARITY,
            AccuracyCheckType.MEDICAL_TERM_MAPPING,
            AccuracyCheckType.NUMERICAL_ACCURACY,
            AccuracyCheckType.UNIT_CONSISTENCY,
        ]

        # Add critical checks for sensitive contexts
        if any(
            ctx in context.get("medical_context", "") for ctx in self.CRITICAL_CONTEXTS
        ):
            required_checks.extend(
                [
                    AccuracyCheckType.SAFETY_CRITICAL,
                    AccuracyCheckType.CLINICAL_EQUIVALENCE,
                    AccuracyCheckType.BACK_TRANSLATION,
                ]
            )

        # Add context preservation for complex texts
        if len(context.get("source_text", "").split()) > 50:
            required_checks.append(AccuracyCheckType.CONTEXT_PRESERVATION)

        return list(set(required_checks))

    async def _check_semantic_similarity(
        self,
        source: str,
        translation: str,
        _source_lang: str,
        _target_lang: str,
        _context: Dict[str, Any],
    ) -> Tuple[float, List[str], List[str]]:
        """Check semantic similarity using embeddings."""
        issues = []
        suggestions: List[str] = []

        try:
            # Check if embedding service is available
            if not self.embedding_service:
                return 0.0, ["Embedding service not available"], []

            # Get embeddings for both texts with language-specific models
            source_embedding = await self.embedding_service.get_embedding(
                source,
                model="multilingual-medical",
                language=_source_lang,  # Use source language for better embedding
            )
            trans_embedding = await self.embedding_service.get_embedding(
                translation,
                model="multilingual-medical",
                language=_target_lang,  # Use target language for better embedding
            )

            # Calculate cosine similarity
            similarity = self._cosine_similarity(source_embedding, trans_embedding)

            # Adjust threshold based on context complexity
            threshold = self.ACCURACY_THRESHOLDS[AccuracyCheckType.SEMANTIC_SIMILARITY]
            if _context.get("medical_context") in self.CRITICAL_CONTEXTS:
                threshold = min(
                    0.95, threshold + 0.05
                )  # Higher threshold for critical context

            if similarity < threshold:
                issues.append(f"Low semantic similarity: {similarity:.2f}")
                suggestions.append("Review translation for meaning preservation")
                if _context.get("medical_context"):
                    suggestions.append(
                        f"Pay special attention to {_context['medical_context']} terminology"
                    )

            return similarity, issues, suggestions

        except (KeyError, ValueError, AttributeError, TypeError) as e:
            logger.error(f"Semantic similarity check failed: {e}")
            return 0.0, ["Failed to compute semantic similarity"], []

    async def _check_medical_terms(
        self,
        source: str,
        translation: str,
        _source_lang: str,
        _target_lang: str,
        _context: Dict[str, Any],
    ) -> Tuple[float, List[str], List[str]]:
        """Check medical term mapping accuracy."""
        issues = []
        suggestions: List[str] = []

        # Extract medical terms from source
        source_terms = self._extract_medical_terms(source, _source_lang)

        if not source_terms:
            return 1.0, [], []  # No medical terms to check

        # Check each term in translation
        correctly_mapped = 0
        for term in source_terms:
            # Look up correct translation
            correct_translation = self._get_medical_term_translation(
                term, _source_lang, _target_lang
            )

            if (
                correct_translation
                and correct_translation.lower() in translation.lower()
            ):
                correctly_mapped += 1
            else:
                issues.append(f"Medical term '{term}' may be incorrectly translated")
                if correct_translation:
                    suggestions.append(f"Use '{correct_translation}' for '{term}'")

        accuracy = correctly_mapped / len(source_terms)

        return accuracy, issues, suggestions

    async def _check_back_translation(
        self,
        source: str,
        translation: str,
        _source_lang: str,
        _target_lang: str,
        _context: Dict[str, Any],
    ) -> Tuple[float, List[str], List[str]]:
        """Check accuracy using back-translation."""
        issues = []
        suggestions: List[str] = []

        # This would integrate with translation service
        # For now, return placeholder
        cache_key = f"{translation}:{_target_lang}:{_source_lang}"

        if cache_key in self.back_translation_cache:
            back_translation = self.back_translation_cache[cache_key]
        else:
            # Would call translation service
            back_translation = source  # Placeholder
            self.back_translation_cache[cache_key] = back_translation

        # Compare with original
        similarity = self._text_similarity(source, back_translation)

        if similarity < self.ACCURACY_THRESHOLDS[AccuracyCheckType.BACK_TRANSLATION]:
            issues.append("Back-translation differs significantly from original")
            suggestions.append("Review translation for accuracy")

        return similarity, issues, suggestions

    async def _check_context_preservation(
        self,
        source: str,
        translation: str,
        _source_lang: str,
        _target_lang: str,
        _context: Dict[str, Any],
    ) -> Tuple[float, List[str], List[str]]:
        """Check if medical context is preserved."""
        issues = []
        suggestions: List[str] = []

        # Check key contextual elements
        context_elements = {
            "temporal": ["before", "after", "during", "while"],
            "conditional": ["if", "unless", "when", "in case"],
            "causal": ["because", "due to", "caused by", "results in"],
        }

        preserved_count = 0
        total_count = 0

        for element_type, keywords in context_elements.items():
            for keyword in keywords:
                if keyword in source.lower():
                    total_count += 1
                    # Check if equivalent exists in translation
                    # This would use language-specific mappings
                    if self._has_equivalent_context(
                        keyword, translation, element_type, _target_lang
                    ):
                        preserved_count += 1
                    else:
                        issues.append(f"Context element '{keyword}' may be missing")

        accuracy = preserved_count / total_count if total_count > 0 else 1.0

        return accuracy, issues, suggestions

    async def _check_clinical_equivalence(
        self,
        source: str,
        translation: str,
        _source_lang: str,
        _target_lang: str,
        _context: Dict[str, Any],
    ) -> Tuple[float, List[str], List[str]]:
        """Check clinical equivalence of translation."""
        issues = []
        suggestions: List[str] = []

        # Check if clinical meaning is preserved
        clinical_concepts = self._extract_clinical_concepts(source)

        if not clinical_concepts:
            return 1.0, [], []

        # Verify each concept in translation
        preserved = 0
        for concept in clinical_concepts:
            if self._is_concept_preserved(concept, translation, _target_lang):
                preserved += 1
            else:
                issues.append(f"Clinical concept '{concept}' may not be preserved")

        accuracy = preserved / len(clinical_concepts)

        return accuracy, issues, suggestions

    async def _check_safety_critical(
        self,
        source: str,
        translation: str,
        _source_lang: str,
        _target_lang: str,
        _context: Dict[str, Any],
    ) -> Tuple[float, List[str], List[str]]:
        """Check safety-critical elements."""
        issues = []
        suggestions: List[str] = []

        # Safety-critical patterns
        safety_patterns = {
            "warnings": ["do not", "avoid", "stop", "discontinue"],
            "urgency": ["immediately", "urgent", "emergency", "call 911"],
            "dosage": ["maximum", "exceed", "overdose", "toxic"],
        }

        critical_found = 0
        critical_preserved = 0

        for category, patterns in safety_patterns.items():
            for pattern in patterns:
                if pattern in source.lower():
                    critical_found += 1
                    if self._is_safety_term_preserved(
                        pattern, translation, category, _target_lang
                    ):
                        critical_preserved += 1
                    else:
                        issues.append(
                            f"Safety-critical term '{pattern}' must be accurately translated"
                        )
                        suggestions.append(
                            f"Ensure '{pattern}' is clearly expressed in translation"
                        )

        accuracy = critical_preserved / critical_found if critical_found > 0 else 1.0

        return accuracy, issues, suggestions

    async def _check_numerical_accuracy(
        self,
        source: str,
        translation: str,
        _source_lang: str,
        _target_lang: str,
        _context: Dict[str, Any],
    ) -> Tuple[float, List[str], List[str]]:
        """Check numerical accuracy."""
        issues = []
        suggestions: List[str] = []

        # Extract numbers from both texts
        # re imported at module level

        source_numbers = re.findall(r"\d+\.?\d*", source)
        trans_numbers = re.findall(r"\d+\.?\d*", translation)

        # Check if all numbers are preserved
        source_set = set(source_numbers)
        trans_set = set(trans_numbers)

        missing = source_set - trans_set
        extra = trans_set - source_set

        if missing:
            issues.append(f"Missing numbers: {', '.join(missing)}")
            suggestions.append("Ensure all numerical values are preserved")

        if extra:
            issues.append(f"Extra numbers found: {', '.join(extra)}")
            suggestions.append("Remove numbers not in source text")

        accuracy = 1.0 if not missing and not extra else 0.0

        return accuracy, issues, suggestions

    async def _check_unit_consistency(
        self,
        source: str,
        translation: str,
        _source_lang: str,
        _target_lang: str,
        _context: Dict[str, Any],
    ) -> Tuple[float, List[str], List[str]]:
        """Check unit consistency."""
        issues = []
        suggestions: List[str] = []

        # Medical units that should not be converted
        medical_units = {
            "mg",
            "g",
            "kg",
            "mcg",
            "μg",
            "ml",
            "L",
            "dL",
            "mmol",
            "mEq",
            "IU",
            "units",
        }

        # Extract units
        # re imported at module level

        unit_pattern = r"\b(" + "|".join(medical_units) + r")\b"
        source_units = re.findall(unit_pattern, source, re.IGNORECASE)
        trans_units = re.findall(unit_pattern, translation, re.IGNORECASE)

        # Check consistency
        if sorted(source_units) != sorted(trans_units):
            issues.append("Medical units appear to be changed")
            suggestions.append("Preserve original medical units without conversion")
            return 0.0, issues, suggestions

        return 1.0, issues, suggestions

    def _calculate_overall_score(
        self, component_scores: Dict[AccuracyCheckType, float], _context: Dict[str, Any]
    ) -> Tuple[float, float]:
        """Calculate overall accuracy score and confidence."""
        if not component_scores:
            return 0.0, 0.0

        # Weight scores based on importance
        weights = {
            AccuracyCheckType.SAFETY_CRITICAL: 3.0,
            AccuracyCheckType.NUMERICAL_ACCURACY: 2.5,
            AccuracyCheckType.UNIT_CONSISTENCY: 2.5,
            AccuracyCheckType.MEDICAL_TERM_MAPPING: 2.0,
            AccuracyCheckType.CLINICAL_EQUIVALENCE: 2.0,
            AccuracyCheckType.SEMANTIC_SIMILARITY: 1.5,
            AccuracyCheckType.CONTEXT_PRESERVATION: 1.0,
            AccuracyCheckType.BACK_TRANSLATION: 1.0,
        }

        # Calculate weighted average
        total_weight: float = 0.0
        weighted_sum: float = 0.0

        for check_type, score in component_scores.items():
            weight = weights.get(check_type, 1.0)
            weighted_sum += score * weight * 100  # Convert to 0-100 scale
            total_weight += weight

        overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Calculate confidence based on number of checks performed
        confidence = min(1.0, len(component_scores) / len(AccuracyCheckType))

        return round(overall_score, 1), round(confidence, 2)

    def _is_acceptable(
        self,
        overall_score: float,
        component_scores: Dict[AccuracyCheckType, float],
        _context: Dict[str, Any],
    ) -> bool:
        """Determine if translation accuracy is acceptable."""
        # Check overall threshold
        min_acceptable = 85.0  # Base threshold

        # Higher threshold for critical contexts
        if any(
            ctx in _context.get("medical_context", "") for ctx in self.CRITICAL_CONTEXTS
        ):
            min_acceptable = 95.0

        if overall_score < min_acceptable:
            return False

        # Check critical components
        critical_checks = [
            AccuracyCheckType.SAFETY_CRITICAL,
            AccuracyCheckType.NUMERICAL_ACCURACY,
            AccuracyCheckType.UNIT_CONSISTENCY,
        ]

        for check in critical_checks:
            if check in component_scores:
                threshold = self.ACCURACY_THRESHOLDS[check]
                if component_scores[check] < threshold:
                    return False

        return True

    def _requires_human_review(
        self,
        overall_score: float,
        component_scores: Dict[AccuracyCheckType, float],
        issues: List[str],
        _context: Dict[str, Any],
    ) -> bool:
        """Determine if human review is required."""
        # Always require review for critical contexts with any issues
        if (
            any(
                ctx in _context.get("medical_context", "")
                for ctx in self.CRITICAL_CONTEXTS
            )
            and issues
        ):
            return True

        # Require review for low scores
        if overall_score < 90.0:
            return True

        # Require review for failed critical checks
        critical_checks = [
            AccuracyCheckType.SAFETY_CRITICAL,
            AccuracyCheckType.MEDICAL_TERM_MAPPING,
            AccuracyCheckType.CLINICAL_EQUIVALENCE,
        ]

        for check in critical_checks:
            if check in component_scores:
                if component_scores[check] < self.ACCURACY_THRESHOLDS[check]:
                    return True

        return False

    # Helper methods
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between vectors."""
        # numpy imported at module level

        vec1_array = np.array(vec1)
        vec2_array = np.array(vec2)

        dot_product = np.dot(vec1_array, vec2_array)
        norm1 = np.linalg.norm(vec1_array)
        norm2 = np.linalg.norm(vec2_array)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using simple metrics."""
        # SequenceMatcher imported at module level

        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    @audit_phi_access("phi_access__extract_medical_terms")
    @require_permission(AccessPermission.READ_PHI)
    def _extract_medical_terms(self, text: str, language: str) -> List[str]:
        """Extract medical terms from text."""
        # This would use medical NER or dictionary lookup
        # Placeholder implementation
        medical_keywords = {
            "en": ["blood pressure", "heart rate", "temperature", "medication"],
            "es": [
                "presión arterial",
                "frecuencia cardíaca",
                "temperatura",
                "medicamento",
            ],
        }

        terms = []
        keywords = medical_keywords.get(language, [])
        text_lower = text.lower()

        for keyword in keywords:
            if keyword in text_lower:
                terms.append(keyword)

        return terms

    def _get_medical_term_translation(
        self, term: str, source_lang: str, target_lang: str
    ) -> Optional[str]:
        """Get correct medical term translation."""
        # This would use medical dictionary
        # Placeholder implementation
        translations = {
            ("blood pressure", "en", "es"): "presión arterial",
            ("heart rate", "en", "es"): "frecuencia cardíaca",
            ("temperature", "en", "es"): "temperatura",
        }

        return translations.get((term, source_lang, target_lang))

    def _has_equivalent_context(
        self, keyword: str, translation: str, _element_type: str, target_lang: str
    ) -> bool:
        """Check if contextual element has equivalent in translation."""
        # Language-specific context mappings
        context_mappings = {
            "es": {
                "before": "antes",
                "after": "después",
                "if": "si",
                "because": "porque",
            }
        }

        mappings = context_mappings.get(target_lang, {})
        equivalent = mappings.get(keyword)

        return bool(equivalent and equivalent in translation.lower())

    @audit_phi_access("phi_access__extract_clinical_concepts")
    @require_permission(AccessPermission.READ_PHI)
    def _extract_clinical_concepts(self, text: str) -> List[str]:
        """Extract clinical concepts from text."""
        # Would use clinical NLP
        # Placeholder implementation
        concepts = []

        clinical_patterns = [
            "diagnosis",
            "treatment",
            "symptom",
            "procedure",
            "medication",
            "allergy",
            "condition",
        ]

        for pattern in clinical_patterns:
            if pattern in text.lower():
                concepts.append(pattern)

        return concepts

    def _is_concept_preserved(
        self, _concept: str, _translation: str, _target_lang: str
    ) -> bool:
        """Check if clinical concept is preserved in translation."""
        # Would check against clinical ontologies
        return True  # Placeholder

    def _is_safety_term_preserved(
        self, term: str, translation: str, _category: str, target_lang: str
    ) -> bool:
        """Check if safety-critical term is preserved."""
        # Language-specific safety term mappings
        safety_mappings = {
            "es": {
                "do not": "no",
                "immediately": "inmediatamente",
                "emergency": "emergencia",
            }
        }

        mappings = safety_mappings.get(target_lang, {})
        equivalent = mappings.get(term)

        return bool(equivalent and equivalent in translation.lower())


# Global accuracy checker instance
accuracy_checker = MedicalAccuracyChecker()
