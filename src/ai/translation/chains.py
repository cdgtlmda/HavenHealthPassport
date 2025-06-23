"""
Translation chain implementations and factory.

This module provides concrete implementations of translation chains
for different use cases and a factory to create them.
 Handles FHIR Resource validation.
"""

import logging
from typing import Any, Dict, Optional

from langchain.callbacks.manager import CallbackManagerForChainRun
from langchain.schema import HumanMessage, SystemMessage

from .base import BaseTranslationChain, TranslationRequest, TranslationResult
from .config import Language, TranslationConfig, TranslationMode
from .exceptions import TranslationError, UnsupportedLanguageError
from .language_detection import LanguageDetector
from .terminology import MedicalTerminologyPreserver

logger = logging.getLogger(__name__)


class StandardTranslationChain(BaseTranslationChain):
    """
    Standard medical translation chain.

    Handles general medical translation with terminology preservation.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the standard translation chain."""
        super().__init__(**kwargs)
        self.language_detector = LanguageDetector(llm=self.llm)

    def _execute_translation(
        self,
        request: TranslationRequest,
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> TranslationResult:
        """Execute the translation using LLM."""
        try:
            # Detect source language if not provided
            if request.source_language is None:
                request.source_language = self._detect_language(request.text)

            # Validate languages
            self._validate_languages(request.source_language, request.target_language)

            # Preserve medical terms
            terminology_preserver = MedicalTerminologyPreserver()
            preservation_result = terminology_preserver.preserve_terms(
                request.text, request.source_language, request.target_language
            )

            # Create translation prompt
            prompt = self._create_translation_prompt(
                text=preservation_result.processed_text,
                source_language=request.source_language,
                target_language=request.target_language,
                mode=request.mode,
                context=request.context,
            )

            # Execute translation
            messages = [
                SystemMessage(content=prompt["system"]),
                HumanMessage(content=prompt["human"]),
            ]

            if not self.llm:
                raise ValueError("LLM not initialized")
            response = self.llm.invoke(
                messages, callbacks=run_manager.get_child() if run_manager else None
            )

            # Extract translated text
            translated_text = (
                response.content.strip()
                if hasattr(response, "content") and isinstance(response.content, str)
                else str(response).strip()
            )

            # Restore medical terms
            terminology_preserver = MedicalTerminologyPreserver()
            final_text = terminology_preserver.restore_terms(
                translated_text, preservation_result, request.target_language
            )

            # Calculate confidence
            confidence_score = self._calculate_translation_confidence(
                request.text, final_text, preservation_result
            )

            # Create result
            result = TranslationResult(
                translated_text=final_text,
                source_language=request.source_language,
                target_language=request.target_language,
                confidence_score=confidence_score,
                preserved_terms=preservation_result.preserved_terms,
                quality_metrics={
                    "term_preservation_rate": len(preservation_result.preserved_terms)
                    / max(len(request.text.split()), 1)
                },
                warnings=preservation_result.warnings,
                processing_time_ms=0.0,  # Set by parent
                model_used=self.llm.model_id if self.llm else "unknown",
                metadata={
                    "mode": request.mode.name,
                    "specialty": request.medical_specialty,
                },
            )

            return result

        except Exception as e:
            logger.error("Translation execution failed: %s", str(e))
            raise TranslationError(f"Translation failed: {str(e)}") from e

    def _detect_language(self, text: str) -> Language:
        """Detect the source language of text."""
        try:
            result = self.language_detector.detect(text)

            if result.confidence < self.config.auto_detect_confidence_threshold:
                logger.warning(
                    "Low confidence (%.2f) in language detection for language: %s",
                    result.confidence,
                    result.detected_language.value,
                )

            return result.detected_language

        except (ValueError, AttributeError) as e:
            logger.warning("Language detection failed: %s", e)
            return Language.UNKNOWN

    def _validate_languages(
        self, source_language: Language, target_language: Language
    ) -> None:
        """Validate that languages are supported."""
        # Get supported languages from config
        supported_langs = self.config.supported_languages  # pylint: disable=no-member

        if source_language == Language.UNKNOWN:
            raise UnsupportedLanguageError(
                "unknown",
                [lang.value for lang in supported_langs],
            )

        if source_language not in supported_langs:
            raise UnsupportedLanguageError(
                source_language.value,
                [lang.value for lang in supported_langs],
            )

        if target_language not in supported_langs:
            raise UnsupportedLanguageError(
                target_language.value,
                [lang.value for lang in supported_langs],
            )

    # pylint: disable=too-many-positional-arguments
    def _create_translation_prompt(
        self,
        text: str,
        source_language: Language,
        target_language: Language,
        mode: TranslationMode,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """Create translation prompt based on mode and context."""
        # Base system prompt
        system_prompt = f"""You are an expert medical translator specializing in
        {source_language.name_human_readable} to {target_language.name_human_readable} translation.

        Your translation must:
        1. Preserve all medical terminology, codes, and measurements exactly
        2. Maintain clinical accuracy and meaning
        3. Use appropriate medical terminology in the target language
        4. Preserve formatting and structure
        5. Keep all placeholders like [[MEDICAL_...]] unchanged

        Translation mode: {mode.name}"""

        # Add mode-specific instructions
        if mode == TranslationMode.EMERGENCY:
            system_prompt += (
                "\n\nThis is an EMERGENCY translation. Prioritize clarity and speed."
            )
        elif mode == TranslationMode.CLINICAL:
            system_prompt += "\n\nThis is a clinical document. Maintain professional medical language."
        elif mode == TranslationMode.PATIENT_EDUCATION:
            system_prompt += "\n\nThis is patient education material. Use clear, simple language while maintaining accuracy."
        elif mode == TranslationMode.CONSENT_FORMS:
            system_prompt += "\n\nThis is a legal medical document. Preserve all legal and medical terminology precisely."

        # Add context if provided
        if context:
            if "medical_specialty" in context:
                system_prompt += (
                    f"\n\nMedical specialty: {context['medical_specialty']}"
                )
            if "patient_age" in context:
                system_prompt += f"\n\nPatient age: {context['patient_age']}"

        human_prompt = f"Translate the following text from {source_language.name_human_readable} to {target_language.name_human_readable}:\n\n{text}"

        return {"system": system_prompt, "human": human_prompt}

    def _calculate_translation_confidence(
        self, source_text: str, translated_text: str, preservation_result: Any
    ) -> float:
        """Calculate confidence score for translation."""
        # Base confidence
        confidence = 0.9

        # Adjust based on text length ratio
        length_ratio = len(translated_text) / max(len(source_text), 1)
        if length_ratio < 0.5 or length_ratio > 2.0:
            confidence -= 0.1

        # Adjust based on preservation success
        if preservation_result.warnings:
            confidence -= 0.05 * len(preservation_result.warnings)

        # Adjust based on text complexity
        if len(preservation_result.preserved_terms) > 10:
            confidence -= 0.05

        return max(confidence, 0.5)


class TranslationChainFactory:
    """
    Factory for creating translation chains.

    Provides appropriate chain implementations based on
    translation requirements and modes.
    """

    @staticmethod
    def create_chain(
        mode: TranslationMode = TranslationMode.GENERAL,
        config: Optional[TranslationConfig] = None,
        **kwargs: Any,
    ) -> BaseTranslationChain:
        """
        Create a translation chain for the specified mode.

        Args:
            mode: Translation mode
            config: Optional translation configuration
            **kwargs: Additional chain parameters

        Returns:
            Configured translation chain
        """
        config = config or TranslationConfig()

        # Update config based on mode
        if mode == TranslationMode.EMERGENCY:
            config.temperature = 0.1
            config.quality_checks_enabled = False  # Skip for speed
        elif mode == TranslationMode.CLINICAL:
            config.temperature = 0.2
            config.validate_medical_accuracy = True
        elif mode == TranslationMode.CONSENT_FORMS:
            config.temperature = 0.1
            config.preserve_medical_terms = True
            config.back_translation_enabled = True

        # Create appropriate chain
        if mode in [TranslationMode.EMERGENCY]:
            # Could create specialized emergency chain
            return StandardTranslationChain(config=config, **kwargs)
        return StandardTranslationChain(config=config, **kwargs)

    @staticmethod
    def create_batch_chain(
        mode: TranslationMode = TranslationMode.GENERAL,
        config: Optional[TranslationConfig] = None,
        **kwargs: Any,
    ) -> BaseTranslationChain:
        """Create a chain optimized for batch translation."""
        config = config or TranslationConfig()
        config.enable_caching = True
        config.batch_size = 20

        return TranslationChainFactory.create_chain(mode, config, **kwargs)
