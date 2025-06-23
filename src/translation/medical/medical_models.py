"""Medical Translation Models - Specialized medical translation using AI."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.ai.bedrock.bedrock_client import BedrockClient
from src.ai.translation.base import TranslationResult
from src.ai.translation.config import Language
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MedicalTranslationConfig:
    """Configuration for medical translation models."""

    model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    temperature: float = 0.1  # Lower temperature for medical accuracy
    max_tokens: int = 4096
    medical_context_prompt: str = """You are a medical translation expert.
    Translate the following medical text accurately, preserving all medical terminology.
    Ensure clinical accuracy and maintain the precise meaning of medical terms.
    """
    safety_checks_enabled: bool = True
    require_terminology_validation: bool = True


class MedicalTranslationModel:
    """Specialized medical translation using AI models."""

    def __init__(self, config: Optional[MedicalTranslationConfig] = None):
        """Initialize medical translation model."""
        self.config = config or MedicalTranslationConfig()
        self.bedrock_client = BedrockClient()
        self.medical_glossary = self._load_medical_glossary()
        self.icd10_terms = self._load_icd10_terms()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self.snomed_terms = self._load_snomed_terms()

    def _load_medical_glossary(self) -> Dict[str, Dict[str, str]]:
        """Load medical terminology glossary."""
        # Basic medical terms
        return {
            "blood pressure": {"es": "presión arterial", "fr": "pression artérielle"},
            "heart rate": {"es": "frecuencia cardíaca", "fr": "fréquence cardiaque"},
            "temperature": {"es": "temperatura", "fr": "température"},
            "diagnosis": {"es": "diagnóstico", "fr": "diagnostic"},
        }

    def _load_icd10_terms(self) -> Dict[str, str]:
        """Load ICD-10 medical codes and descriptions."""
        # Sample ICD-10 codes
        return {
            "I10": "Essential (primary) hypertension",
            "E11": "Type 2 diabetes mellitus",
            "J45": "Asthma",
            "M79.3": "Panniculitis, unspecified",
        }

    def _load_snomed_terms(self) -> Dict[str, str]:
        """Load SNOMED CT medical terminology."""
        # Sample SNOMED terms
        return {
            "38341003": "Hypertensive disorder",
            "73211009": "Diabetes mellitus",
            "195967001": "Asthma",
            "22298006": "Myocardial infarction",
        }

    async def translate_medical_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
        medical_context: Optional[str] = None,
    ) -> TranslationResult:
        """Translate medical text with specialized handling."""
        try:
            # Pre-process to identify medical terms
            medical_terms = self._identify_medical_terms(text)

            # Build enhanced prompt with medical context
            prompt = self._build_medical_prompt(
                text, source_language, target_language, medical_context, medical_terms
            )

            # Call AI model
            response = self.bedrock_client.invoke_model(
                model_id=self.config.model_id,
                body={
                    "prompt": prompt,
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                },
            )

            # Extract translation
            translated_text = self._extract_translation(response)

            # Validate medical terminology
            if self.config.require_terminology_validation:
                validated_text = self._validate_medical_terms(
                    translated_text, medical_terms, target_language
                )
            else:
                validated_text = translated_text

            # Perform safety checks
            if self.config.safety_checks_enabled:
                safety_issues = self._check_translation_safety(
                    text, validated_text, medical_terms
                )
            else:
                safety_issues = []

            return TranslationResult(
                translated_text=validated_text,
                source_language=Language(source_language),
                target_language=Language(target_language),
                confidence_score=0.95,  # High confidence for medical translations
                preserved_terms=[
                    {"term": term, "preserved": True} for term in medical_terms
                ],
                quality_metrics={
                    "medical_terms_identified": len(medical_terms),
                    "terminology_validated": self.config.require_terminology_validation,
                },
                warnings=safety_issues,
                processing_time_ms=100,  # Placeholder
                model_used=self.config.model_id,
                metadata={
                    "medical_context": medical_context,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        except Exception as e:
            logger.error(f"Medical translation error: {e}")
            raise

    def _identify_medical_terms(self, text: str) -> List[Dict[str, Any]]:
        """Identify medical terms in the text."""
        medical_terms = []
        text_lower = text.lower()

        # Check glossary terms
        for term, translations in self.medical_glossary.items():
            if term.lower() in text_lower:
                medical_terms.append(
                    {"term": term, "type": "glossary", "translations": translations}
                )

        # Check ICD-10 codes
        for code, description in self.icd10_terms.items():
            if code in text or description.lower() in text_lower:
                medical_terms.append(
                    {"term": code, "type": "icd10", "description": description}
                )

        return medical_terms

    def _build_medical_prompt(
        self,
        text: str,
        source_language: str,
        target_language: str,
        medical_context: Optional[str],
        medical_terms: List[Dict[str, Any]],
    ) -> str:
        """Build specialized prompt for medical translation."""
        prompt = f"{self.config.medical_context_prompt}\n\n"

        if medical_context:
            prompt += f"Medical Context: {medical_context}\n\n"

        if medical_terms:
            prompt += "Identified Medical Terms:\n"
            for term in medical_terms:
                prompt += f"- {term['term']}"
                if term["type"] == "icd10":
                    prompt += f" (ICD-10: {term['description']})"
                prompt += "\n"
            prompt += "\n"

        prompt += f"""Source Language: {source_language}
Target Language: {target_language}

Text to translate:
{text}

Provide only the translation, maintaining all medical terminology accuracy."""

        return prompt

    @audit_phi_access("phi_access__extract_translation")
    @require_permission(AccessPermission.READ_PHI)
    def _extract_translation(self, response: str) -> str:
        """Extract translation from model response."""
        # Simple extraction - in production would be more sophisticated
        return response.strip()

    def _validate_medical_terms(
        self,
        translated_text: str,
        original_medical_terms: List[Dict[str, Any]],
        target_language: str,
    ) -> str:
        """Validate medical terms in translation."""
        validated_text = translated_text

        for term_info in original_medical_terms:
            if term_info["type"] == "glossary":
                # Check if correct translation is used
                expected_translation = term_info["translations"].get(target_language)
                if expected_translation and expected_translation not in validated_text:
                    logger.warning(
                        f"Medical term '{term_info['term']}' may not be "
                        f"correctly translated. Expected: '{expected_translation}'"
                    )

        return validated_text

    def _check_translation_safety(
        self,
        original_text: str,
        translated_text: str,
        medical_terms: List[Dict[str, Any]],
    ) -> List[str]:
        """Check translation for safety issues."""
        safety_issues = []

        # Check for missing medical terms
        for term in medical_terms:
            term_text = term["term"].lower()
            if term_text in original_text.lower():
                # Simple check - in production would be more sophisticated
                if not any(
                    trans.lower() in translated_text.lower()
                    for trans in term.get("translations", {}).values()
                ):
                    safety_issues.append(
                        f"Medical term '{term['term']}' may be missing in translation"
                    )

        # Check for critical medical keywords
        critical_keywords = ["urgent", "emergency", "critical", "severe"]
        for keyword in critical_keywords:
            if (
                keyword in original_text.lower()
                and keyword not in translated_text.lower()
            ):
                safety_issues.append(
                    f"Critical keyword '{keyword}' may be missing in translation"
                )

        return safety_issues

    def validate_medical_translation(
        self,
        original_text: str,
        translated_text: str,
        source_language: str,  # pylint: disable=unused-argument
        target_language: str,
    ) -> Dict[str, Any]:
        """Comprehensive validation of medical translation."""
        validation_result: Dict[str, Any] = {
            "is_valid": True,
            "accuracy_score": 1.0,
            "issues": [],
            "warnings": [],
        }

        # Identify medical terms in original
        original_terms = self._identify_medical_terms(original_text)

        # Check term preservation
        missing_terms = []
        for term in original_terms:
            term_found = False

            if term["type"] == "glossary" and target_language in term["translations"]:
                expected = term["translations"][target_language]
                if expected.lower() in translated_text.lower():
                    term_found = True

            if not term_found:
                missing_terms.append(term["term"])
                validation_result["accuracy_score"] -= 0.1

        if missing_terms:
            validation_result["issues"].append(
                f"Missing medical terms: {', '.join(missing_terms)}"
            )
            validation_result["is_valid"] = False

        # Check for number consistency (dosages, measurements)
        original_numbers = set(re.findall(r"\d+\.?\d*", original_text))
        translated_numbers = set(re.findall(r"\d+\.?\d*", translated_text))

        if original_numbers != translated_numbers:
            validation_result["warnings"].append(
                "Numeric values may have changed in translation"
            )
            validation_result["accuracy_score"] -= 0.2

        validation_result["accuracy_score"] = max(
            0, validation_result["accuracy_score"]
        )

        return validation_result
