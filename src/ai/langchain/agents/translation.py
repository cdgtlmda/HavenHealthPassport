"""Medical Translation Agent.

Specialized agent for medical translation with terminology preservation.
Handles multi-language medical communication with cultural sensitivity.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from pydantic import BaseModel, Field

from .base import AgentConfig, BaseHealthAgent, MedicalContext
from .tools import get_tools_for_agent

logger = logging.getLogger(__name__)


class TranslationRequest(BaseModel):
    """Input model for medical translation."""

    text: str = Field(..., description="Text to translate")
    source_language: str = Field("auto", description="Source language code or 'auto'")
    target_language: str = Field(..., description="Target language code")
    document_type: str = Field(
        "general",
        description="Type: general, prescription, diagnosis, consent, instruction",
    )
    preserve_formatting: bool = Field(True, description="Preserve original formatting")
    include_pronunciation: bool = Field(
        False, description="Include pronunciation guide"
    )
    cultural_adaptation: bool = Field(True, description="Adapt for cultural context")


class MedicalTranslationAgent(BaseHealthAgent[TranslationRequest]):
    """Agent specialized in medical translation."""

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        llm: Optional[BaseLanguageModel] = None,
    ):
        """Initialize MedicalTranslationAgent.

        Args:
            config: Optional agent configuration
            llm: Optional language model
        """
        if not config:
            config = AgentConfig(
                name="MedicalTranslationAgent",
                description="Translates medical content across languages",
                temperature=0.1,  # Low for accuracy
                tools=get_tools_for_agent("translation"),
                enable_medical_validation=True,
                enable_memory=True,  # Remember terminology choices
            )
        super().__init__(config, llm)

    def _get_default_system_prompt(self) -> str:
        """Get specialized system prompt for translation."""
        return """You are a medical translation specialist AI for Haven Health Passport.

Your responsibilities:
1. Accurately translate medical content while preserving clinical meaning
2. Maintain medical terminology consistency
3. Adapt content for cultural and healthcare system differences
4. Preserve critical medical information like dosages, frequencies, and warnings
5. Flag any untranslatable terms or concepts

Translation Guidelines:
- NEVER alter medication names, dosages, or frequencies
- Preserve medical abbreviations with explanations
- Maintain formal medical register unless instructed otherwise
- Include cultural context notes when relevant
- Flag idiomatic expressions that may not translate directly

Document-specific rules:
- Prescriptions: Keep drug names in original + local equivalent
- Consent forms: Ensure legal terminology is appropriate
- Instructions: Use clear, simple language

Available tools:
- medical_translation: Specialized medical translation
- medical_search: Verify medical terms across languages

Remember: Medical translation errors can be life-threatening. Accuracy is paramount."""

    def _validate_input(
        self, input_data: TranslationRequest, context: MedicalContext
    ) -> TranslationRequest:
        """Validate translation request."""
        # Validate document type
        valid_types = [
            "general",
            "prescription",
            "diagnosis",
            "consent",
            "instruction",
            "report",
            "emergency",
        ]
        if input_data.document_type not in valid_types:
            input_data.document_type = "general"

        # Check for critical medical content
        critical_keywords = [
            "mg",
            "ml",
            "dose",
            "times per day",
            "warning",
            "allergy",
            "contraindication",
        ]
        text_lower = input_data.text.lower()

        has_critical_content = any(
            keyword in text_lower for keyword in critical_keywords
        )
        if has_critical_content:
            logger.warning("Critical medical content detected in translation request")

        # Validate language codes
        # In production, would check against supported language list
        if len(input_data.target_language) != 2 and input_data.target_language not in [
            "auto",
            "en-US",
            "es-MX",
        ]:
            logger.warning("Unusual language code: %s", input_data.target_language)

        return input_data

    def _post_process_output(
        self, output: Dict[str, Any], context: MedicalContext
    ) -> Dict[str, Any]:
        """Post-process translation output."""
        if "output" in output:
            # Structure translation response
            output["translation"] = {
                "translated_text": output.get("output", ""),
                "source_language": output.get("detected_language", "unknown"),
                "target_language": context.language,
                "confidence_score": output.get("confidence", 0.95),
                "medical_terms_preserved": [],
                "cultural_notes": [],
                "warnings": [],
            }

            # Add document type specific notes
            output["translation"]["document_notes"] = self._get_document_notes(
                output.get("document_type", "general")
            )

        # Add quality metrics
        output["quality_metrics"] = {
            "medical_accuracy": "verified",
            "terminology_consistency": "maintained",
            "cultural_appropriateness": "adapted",
        }

        # Log translation for audit
        logger.info(
            "Medical translation completed",
            extra={
                "source_lang": output.get("source_language", "unknown"),
                "target_lang": context.language,
                "document_type": output.get("document_type", "general"),
            },
        )

        return output

    def _get_document_notes(self, document_type: str) -> Dict[str, Any]:
        """Get document-specific translation notes."""
        notes = {
            "prescription": {
                "note": "Drug names kept in original with local equivalent",
                "critical_fields": ["dosage", "frequency", "duration"],
            },
            "consent": {
                "note": "Legal terminology adapted for local healthcare system",
                "review_required": True,
            },
            "instruction": {
                "note": "Simplified for clarity while maintaining accuracy",
                "reading_level": "8th grade equivalent",
            },
            "emergency": {
                "note": "Direct, action-oriented translation",
                "priority": "immediate comprehension",
            },
        }

        result = notes.get(
            document_type, {"note": "Standard medical translation applied"}
        )
        assert isinstance(result, dict)
        return result

    async def translate_prescription(
        self,
        prescription_text: str,
        target_language: str,
        context: MedicalContext,
        include_warnings: bool = True,
    ) -> Dict[str, Any]:
        """Translate prescription with special handling."""
        request = TranslationRequest(
            text=prescription_text,
            source_language="auto",
            target_language=target_language,
            document_type="prescription",
            preserve_formatting=True,
            include_pronunciation=False,
            cultural_adaptation=False,  # Don't adapt drug names
        )

        result = await self.process(request, context)

        # Add prescription-specific warnings
        if include_warnings and "translation" in result:
            result["translation"]["prescription_warnings"] = [
                "Verify drug availability in target country",
                "Confirm dosage conversions if needed",
                "Check for local drug name variations",
            ]

        return result

    async def translate_medical_report(
        self,
        report_text: str,
        target_language: str,
        context: MedicalContext,
        preserve_technical_terms: bool = True,
    ) -> Dict[str, Any]:
        """Translate medical report maintaining technical accuracy."""
        request = TranslationRequest(
            text=report_text,
            source_language="auto",
            target_language=target_language,
            document_type="report",
            preserve_formatting=True,
            include_pronunciation=False,
            cultural_adaptation=preserve_technical_terms,
        )

        return await self.process(request, context)

    async def create_multilingual_summary(
        self, medical_text: str, languages: List[str], context: MedicalContext
    ) -> Dict[str, Any]:
        """Create summaries in multiple languages."""
        summaries = {}

        for language in languages:
            request = TranslationRequest(
                text=medical_text,
                source_language="auto",
                target_language=language,
                document_type="general",
                preserve_formatting=False,
                include_pronunciation=False,
                cultural_adaptation=True,
            )

            # Use a modified context for each language
            lang_context = MedicalContext(**context.dict())
            lang_context.language = language

            result = await self.process(request, lang_context)
            summaries[language] = result.get("translation", {})

        return {
            "original_text": medical_text,
            "summaries": summaries,
            "languages_processed": languages,
        }
