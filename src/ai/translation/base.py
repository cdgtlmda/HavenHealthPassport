"""
Base translation chain for medical text translation.

This module provides the foundation for translation chains that preserve
medical accuracy while supporting multiple languages.
"""

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
    Optional,
    TypeVar,
)

from langchain.callbacks.manager import (
    AsyncCallbackManagerForChainRun,
    CallbackManagerForChainRun,
)
from langchain.chains.base import Chain
from langchain_aws import ChatBedrock
from pydantic import Field

from ..langchain.bedrock import get_bedrock_model
from ..medical_nlp.abbreviations import MedicalAbbreviationHandler
from .config import Language, TranslationConfig, TranslationMode
from .exceptions import TranslationError
from .target_selection import TargetLanguageSelector
from .terminology import MedicalTerminologyPreserver
from .translation_validator import TranslationValidator

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class TranslationRequest:
    """Represents a translation request with metadata."""

    text: str
    source_language: Optional[Language] = None
    target_language: Language = Language.ENGLISH
    mode: TranslationMode = TranslationMode.GENERAL
    context: Optional[Dict[str, Any]] = None
    urgency: str = "routine"
    preserve_formatting: bool = True
    medical_specialty: Optional[str] = None
    patient_context: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TranslationResult:
    """Represents a translation result with quality metrics."""

    translated_text: str
    source_language: Language
    target_language: Language
    confidence_score: float
    preserved_terms: List[Dict[str, Any]]
    quality_metrics: Dict[str, float]
    warnings: List[str]
    processing_time_ms: float
    model_used: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class BaseTranslationChain(Chain, ABC):
    """
    Base class for medical translation chains.

    Provides:
    - Medical terminology preservation
    - Context-aware translation
    - Quality validation
    - Error handling with fallbacks
    - Performance monitoring
    """

    # Configuration
    config: TranslationConfig = Field(default_factory=TranslationConfig)

    # Core components
    llm: Optional[ChatBedrock] = Field(default=None)
    terminology_preserver: MedicalTerminologyPreserver = Field(
        default_factory=MedicalTerminologyPreserver
    )
    validator: TranslationValidator = Field(default_factory=TranslationValidator)
    target_selector: TargetLanguageSelector = Field(
        default_factory=TargetLanguageSelector
    )

    # Medical NLP components
    abbreviation_handler: MedicalAbbreviationHandler = Field(
        default_factory=MedicalAbbreviationHandler
    )

    # Chain configuration
    input_key: str = "translation_request"
    output_key: str = "translation_result"

    # Performance tracking
    _metrics: Dict[str, Any] = {}
    _cache: Dict[str, TranslationResult] = {}

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the translation chain."""
        super().__init__(**kwargs)
        if self.llm is None:
            # Access config attributes properly
            config = self.config
            self.llm = get_bedrock_model(
                model_id=config.default_model,  # pylint: disable=no-member
                temperature=config.temperature,  # pylint: disable=no-member
                max_tokens=config.max_tokens,  # pylint: disable=no-member
            )
        self._initialize_components()

    def _initialize_components(self) -> None:
        """Initialize chain components."""
        logger.info("Initializing base translation chain components")

        # Initialize terminology preserver with medical databases
        if hasattr(self.terminology_preserver, "load_medical_terms"):
            self.terminology_preserver.load_medical_terms()

        # Configure validator
        if hasattr(self.validator, "configure"):
            self.validator.configure(
                min_confidence=self.config.min_confidence_threshold,
                quality_checks=self.config.quality_checks_enabled,
            )

        # Set up metrics collection
        self._metrics = {
            "total_translations": 0,
            "successful_translations": 0,
            "failed_translations": 0,
            "average_confidence": 0.0,
            "average_processing_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

    @property
    def input_keys(self) -> List[str]:
        """Input keys for the chain."""
        return [self.input_key]

    @property
    def output_keys(self) -> List[str]:
        """Output keys for the chain."""
        return [self.output_key]

    @property
    def _chain_type(self) -> str:
        """Return the chain type."""
        return "medical_translation_chain"

    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, TranslationResult]:
        """
        Execute the translation chain.

        Args:
            inputs: Input dictionary containing translation request
            run_manager: Callback manager for chain execution

        Returns:
            Dictionary containing translation result
        """
        try:
            request = self._parse_request(inputs)

            # Check cache
            cache_key = self._generate_cache_key(request)
            # Access the actual config instance value
            if cache_key in self._cache and getattr(
                self.config, "enable_caching", False
            ):
                self._metrics["cache_hits"] += 1
                logger.debug("Cache hit for translation: %s", cache_key)
                return {self.output_key: self._cache[cache_key]}

            self._metrics["cache_misses"] += 1

            # Execute translation
            start_time = datetime.now()
            result = self._execute_translation(request, run_manager)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            result.processing_time_ms = processing_time

            # Validate result
            if (
                getattr(self.config, "quality_checks_enabled", True)
                and request.source_language is not None
            ):
                validation_result = (
                    self.validator.validate(  # pylint: disable=no-member
                        request.text,
                        result.translated_text,
                        request.source_language,
                        request.target_language,
                    )
                )
                result.quality_metrics.update(validation_result.metrics)
                result.warnings.extend(validation_result.warnings)

            # Update metrics
            self._update_metrics(result)

            # Cache result
            if getattr(self.config, "enable_caching", True):
                self._cache[cache_key] = result

            return {self.output_key: result}

        except Exception as e:
            self._metrics["failed_translations"] += 1
            logger.error("Translation failed: %s", str(e))
            raise TranslationError(f"Translation failed: {str(e)}") from e

    async def _acall(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[AsyncCallbackManagerForChainRun] = None,
    ) -> Dict[str, TranslationResult]:
        """Async version of _call."""
        # For now, wrap sync call in async
        return await asyncio.get_event_loop().run_in_executor(
            None, self._call, inputs, None
        )

    def _parse_request(self, inputs: Dict[str, Any]) -> TranslationRequest:
        """Parse input into TranslationRequest."""
        if self.input_key in inputs and isinstance(
            inputs[self.input_key], TranslationRequest
        ):
            # Type assertion for mypy
            request = inputs[self.input_key]
            assert isinstance(request, TranslationRequest)
            return request

        # Build request from raw inputs
        return TranslationRequest(
            text=inputs.get("text", ""),
            source_language=inputs.get("source_language"),
            target_language=inputs.get("target_language", Language.ENGLISH),
            mode=inputs.get("mode", TranslationMode.GENERAL),
            context=inputs.get("context"),
            urgency=inputs.get("urgency", "routine"),
            preserve_formatting=inputs.get("preserve_formatting", True),
            medical_specialty=inputs.get("medical_specialty"),
            patient_context=inputs.get("patient_context"),
            metadata=inputs.get("metadata", {}),
        )

    def _generate_cache_key(self, request: TranslationRequest) -> str:
        """Generate cache key for translation request."""
        key_parts = [
            request.text,
            str(request.source_language),
            str(request.target_language),
            str(request.mode),
            str(request.medical_specialty),
        ]

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()

    @abstractmethod
    def _execute_translation(
        self,
        request: TranslationRequest,
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> TranslationResult:
        """
        Execute the actual translation.

        Must be implemented by subclasses.
        """

    def _update_metrics(self, result: TranslationResult) -> None:
        """Update performance metrics."""
        self._metrics["total_translations"] += 1
        self._metrics["successful_translations"] += 1

        # Update running averages
        n = self._metrics["successful_translations"]
        self._metrics["average_confidence"] = (
            self._metrics["average_confidence"] * (n - 1) + result.confidence_score
        ) / n
        self._metrics["average_processing_time"] = (
            self._metrics["average_processing_time"] * (n - 1)
            + result.processing_time_ms
        ) / n

    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        return self._metrics.copy()

    def clear_cache(self) -> None:
        """Clear translation cache."""
        self._cache.clear()
        logger.info("Translation cache cleared")

    def translate(
        self,
        text: str,
        target_language: Language,
        source_language: Optional[Language] = None,
        **kwargs: Any,
    ) -> TranslationResult:
        """
        Translate text to target language.

        Args:
            text: Text to translate
            target_language: Target language
            source_language: Source language (auto-detect if None)
            **kwargs: Additional parameters

        Returns:
            Translation result
        """
        request = TranslationRequest(
            text=text,
            source_language=source_language,
            target_language=target_language,
            **kwargs,
        )

        result = self({self.input_key: request})
        translation_result = result[self.output_key]
        assert isinstance(translation_result, TranslationResult)
        return translation_result

    async def atranslate(
        self,
        text: str,
        target_language: Language,
        source_language: Optional[Language] = None,
        **kwargs: Any,
    ) -> TranslationResult:
        """Async version of translate."""
        request = TranslationRequest(
            text=text,
            source_language=source_language,
            target_language=target_language,
            **kwargs,
        )

        result = await self.acall({self.input_key: request})
        translation_result = result[self.output_key]
        assert isinstance(translation_result, TranslationResult)
        return translation_result

    def batch_translate(
        self,
        texts: List[str],
        target_language: Language,
        source_language: Optional[Language] = None,
        **kwargs: Any,
    ) -> List[TranslationResult]:
        """
        Translate multiple texts in batch.

        Args:
            texts: List of texts to translate
            target_language: Target language
            source_language: Source language (auto-detect if None)
            **kwargs: Additional parameters

        Returns:
            List of translation results
        """
        results = []
        for text in texts:
            try:
                result = self.translate(
                    text=text,
                    target_language=target_language,
                    source_language=source_language,
                    **kwargs,
                )
                results.append(result)
            except (TranslationError, ValueError) as e:
                logger.error("Batch translation error for text: %s", e)
                # Create error result
                error_result = TranslationResult(
                    translated_text="",
                    source_language=source_language or Language.UNKNOWN,
                    target_language=target_language,
                    confidence_score=0.0,
                    preserved_terms=[],
                    quality_metrics={},
                    warnings=[f"Translation failed: {str(e)}"],
                    processing_time_ms=0.0,
                    model_used="error",
                )
                results.append(error_result)

        return results
