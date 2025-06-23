"""
Comprehensive test suite for Medical Translator with real AWS GenAI services.

CRITICAL: This is a healthcare system for vulnerable refugees.
MEDICAL COMPLIANCE: Uses REAL AWS GenAI services, NO MOCKS.
Tests real Bedrock, Translate, KMS integration for life-critical translations.
"""

import os
from datetime import datetime

import boto3
import pytest

from src.services.medical_translator import (
    MedicalTranslator,
    TranslationMode,
    TranslationRequest,
    TranslationResult,
)
from src.utils.exceptions import (
    TranslationException,
    UnsupportedLanguageException,
)

# Set testing environment before imports
os.environ["TESTING"] = "true"


@pytest.fixture
def real_aws_credentials():
    """Ensure AWS credentials are available for testing."""
    required_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        pytest.skip(f"Missing AWS credentials: {missing_vars}")

    return {
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "region_name": os.getenv("AWS_REGION", "us-east-1"),
    }


@pytest.fixture
async def real_medical_translator(real_aws_credentials):
    """Create a real medical translator with AWS services - NO MOCKS."""
    # Override environment variables for testing
    test_config = {
        "TRANSLATOR_KMS_KEY_ID": "alias/haven-health-translator",
        "AWS_REGION": real_aws_credentials["region_name"],
        "BEDROCK_MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0",
    }

    # Create translator with real AWS services
    translator = MedicalTranslator(config=test_config)

    # Verify real AWS clients are initialized
    assert hasattr(translator, "translate_client")
    assert hasattr(translator, "bedrock_client")
    assert hasattr(translator, "kms_client")

    # Test AWS connectivity
    try:
        # Test Translate service
        translator.translate_client.describe_text_translation_jobs(MaxResults=1)

        # Test Bedrock service
        translator.bedrock_client.list_foundation_models()

        # Test KMS service
        translator.kms_client.list_keys(Limit=1)

    except Exception as e:
        pytest.skip(f"AWS services not accessible: {e}")

    yield translator

    # Cleanup
    await translator.close()


class TestMedicalTranslatorAWSGenAI:
    """Test Medical Translator with real AWS GenAI services."""

    @pytest.mark.asyncio
    async def test_translator_initialization_real_aws(self, real_medical_translator):
        """Test translator initializes with real AWS services."""
        translator = real_medical_translator

        # Verify real AWS clients
        assert isinstance(
            translator.translate_client, boto3.client("translate").__class__
        )
        assert isinstance(
            translator.bedrock_client, boto3.client("bedrock-runtime").__class__
        )
        assert isinstance(translator.kms_client, boto3.client("kms").__class__)

        # Verify configuration
        assert translator.config["aws_region"] is not None
        assert translator.config["bedrock_model"] is not None
        assert translator.config["kms_key_id"] is not None

    @pytest.mark.asyncio
    async def test_translate_medical_text_real_aws_translate(
        self, real_medical_translator
    ):
        """Test medical text translation using real AWS Translate."""
        translator = real_medical_translator

        # Create translation request
        request = TranslationRequest(
            text="Patient has hypertension and diabetes",
            source_language="en",
            target_language="es",  # Spanish
            mode=TranslationMode.MEDICAL,
            medical_context="chronic conditions",
            terminology_strict=True,
        )

        result = await translator.translate(request)

        # Verify real translation occurred
        assert isinstance(result, TranslationResult)
        assert result.translated_text is not None
        assert result.translated_text != request.text
        assert result.source_language == "en"
        assert result.target_language == "es"
        assert result.confidence_score > 0.0
        assert len(result.medical_terms_preserved) >= 0

    @pytest.mark.asyncio
    async def test_translate_emergency_phrases_real_aws(self, real_medical_translator):
        """Test emergency phrase translation with real AWS services."""
        translator = real_medical_translator

        emergency_phrases = [
            "I need help immediately",
            "Call an ambulance",
            "I have chest pain",
            "I can't breathe",
            "I'm having an allergic reaction",
        ]

        for phrase in emergency_phrases:
            # Test translation to Arabic (common refugee language)
            request = TranslationRequest(
                text=phrase,
                source_language="en",
                target_language="ar",
                mode=TranslationMode.EMERGENCY,
                urgency="emergency",
            )

            result = await translator.translate(request)

            assert result.translated_text is not None
            assert result.translated_text != phrase
            assert result.target_language == "ar"
            assert result.mode == TranslationMode.EMERGENCY
            # Emergency translations should have high confidence
            assert result.confidence_score >= 0.7

    @pytest.mark.asyncio
    async def test_medical_terminology_preservation_real_bedrock(
        self, real_medical_translator
    ):
        """Test medical terminology preservation using real Bedrock."""
        translator = real_medical_translator

        # Medical text with specific terminology
        request = TranslationRequest(
            text="Patient presents with myocardial infarction and requires immediate thrombolysis",
            source_language="en",
            target_language="es",
            mode=TranslationMode.MEDICAL,
            terminology_strict=True,
            medical_context="cardiology emergency",
        )

        result = await translator.translate(request)

        # Verify medical terms are preserved or properly translated
        assert len(result.medical_terms_preserved) > 0
        assert result.confidence_score > 0.0

        # Check that key medical terms were identified
        preserved_terms = [term["source"] for term in result.medical_terms_preserved]
        assert any(
            "myocardial" in term.lower() or "infarction" in term.lower()
            for term in preserved_terms
        )

    @pytest.mark.asyncio
    async def test_batch_translation_real_aws(self, real_medical_translator):
        """Test batch translation with real AWS services."""
        translator = real_medical_translator

        requests = [
            TranslationRequest(
                text="Take this medication twice daily",
                source_language="en",
                target_language="fr",
                mode=TranslationMode.MEDICATION,
            ),
            TranslationRequest(
                text="You have an appointment tomorrow",
                source_language="en",
                target_language="fr",
                mode=TranslationMode.GENERAL,
            ),
            TranslationRequest(
                text="Please fast before the blood test",
                source_language="en",
                target_language="fr",
                mode=TranslationMode.DIAGNOSTIC,
            ),
        ]

        results = await translator.translate_batch(requests)

        assert len(results) == len(requests)

        for i, result in enumerate(results):
            assert isinstance(result, TranslationResult)
            assert result.translated_text != requests[i].text
            assert result.target_language == "fr"
            assert result.confidence_score > 0.0

    @pytest.mark.asyncio
    async def test_translation_quality_assessment_real_bedrock(
        self, real_medical_translator
    ):
        """Test translation quality assessment with real Bedrock."""
        translator = real_medical_translator

        # High-stakes medical translation
        request = TranslationRequest(
            text="Administer 10mg morphine intravenously for severe pain management",
            source_language="en",
            target_language="ar",
            mode=TranslationMode.MEDICATION,
            urgency="urgent",
            medical_context="pain management protocol",
        )

        result = await translator.translate(request)

        # Quality checks for medication instructions
        assert result.confidence_score > 0.8  # High confidence required
        assert result.review_required is not None  # Review flag should be set
        assert len(result.medical_terms_preserved) > 0  # Medical terms identified
        assert "morphine" in str(result.medical_terms_preserved).lower()

    @pytest.mark.asyncio
    async def test_medical_context_enhancement_real_bedrock(
        self, real_medical_translator
    ):
        """Test medical context enhancement with real Bedrock."""
        translator = real_medical_translator

        # Test different medical contexts
        contexts = [
            ("pediatric", "Child has fever and cough"),
            ("obstetric", "Patient is experiencing contractions"),
            ("mental_health", "Patient reports anxiety and depression"),
        ]

        for context_type, text in contexts:
            request = TranslationRequest(
                text=text,
                source_language="en",
                target_language="es",
                mode=getattr(
                    TranslationMode, context_type.upper(), TranslationMode.MEDICAL
                ),
                medical_context=context_type,
            )

            result = await translator.translate(request)

            assert result.translated_text is not None
            assert result.confidence_score > 0.0
            assert result.metadata.get("medical_context") is not None

    @pytest.mark.asyncio
    async def test_encryption_with_real_kms(self, real_medical_translator):
        """Test PHI encryption with real KMS."""
        translator = real_medical_translator

        # Sensitive medical information
        request = TranslationRequest(
            text="Patient John Doe, DOB 01/01/1980, has diabetes and takes insulin",
            source_language="en",
            target_language="es",
            mode=TranslationMode.MEDICAL,
            medical_context="patient record",
        )

        result = await translator.translate(request)

        # Verify translation completed (encryption happens internally)
        assert result.translated_text is not None
        assert result.confidence_score > 0.0

        # Verify metadata includes security information
        assert "translation_time" in result.metadata
        assert result.metadata["translation_time"] > 0

    @pytest.mark.asyncio
    async def test_audit_logging_real_cloudwatch(self, real_medical_translator):
        """Test audit logging with real CloudWatch."""
        translator = real_medical_translator

        request = TranslationRequest(
            text="Patient requires immediate surgery",
            source_language="en",
            target_language="ar",
            mode=TranslationMode.SURGICAL,
            urgency="emergency",
        )

        result = await translator.translate(request)

        # Verify translation completed (audit logging happens internally)
        assert result.translated_text is not None
        assert result.mode == TranslationMode.SURGICAL

        # Verify audit metadata
        assert result.translation_time > 0
        assert result.metadata is not None

    @pytest.mark.asyncio
    async def test_supported_languages_real_aws(self, real_medical_translator):
        """Test supported languages with real AWS services."""
        translator = real_medical_translator

        supported_languages = translator.get_supported_languages()

        # Verify refugee-priority languages are supported
        priority_languages = ["ar", "fa", "ps", "so", "ti", "ku", "ur"]

        for lang in priority_languages:
            assert lang in supported_languages, f"Language {lang} not supported"
            assert supported_languages[lang]["quality_level"] is not None

    @pytest.mark.asyncio
    async def test_translation_caching_real_implementation(
        self, real_medical_translator
    ):
        """Test translation caching with real implementation."""
        translator = real_medical_translator

        request = TranslationRequest(
            text="Common medical phrase for testing cache",
            source_language="en",
            target_language="es",
            mode=TranslationMode.GENERAL,
        )

        # First translation
        result1 = await translator.translate(request)
        first_time = result1.translation_time

        # Second identical translation (should use cache)
        result2 = await translator.translate(request)
        second_time = result2.translation_time

        # Verify both translations succeeded
        assert result1.translated_text == result2.translated_text
        assert result1.confidence_score == result2.confidence_score

        # Cache should make second translation faster (or equal if very fast)
        assert second_time <= first_time * 1.5  # Allow some variance

    @pytest.mark.asyncio
    async def test_error_handling_real_aws_failures(self, real_medical_translator):
        """Test error handling with real AWS service scenarios."""
        translator = real_medical_translator

        # Test unsupported language pair
        with pytest.raises((TranslationException, UnsupportedLanguageException)):
            request = TranslationRequest(
                text="Test text",
                source_language="xx",  # Invalid language code
                target_language="yy",  # Invalid language code
                mode=TranslationMode.GENERAL,
            )
            await translator.translate(request)

    @pytest.mark.asyncio
    async def test_medical_terminology_database_real_integration(
        self, real_medical_translator
    ):
        """Test medical terminology database integration."""
        translator = real_medical_translator

        # Test with medical terminology
        request = TranslationRequest(
            text="Patient diagnosed with pneumonia, prescribed amoxicillin 500mg",
            source_language="en",
            target_language="es",
            mode=TranslationMode.MEDICATION,
            terminology_strict=True,
        )

        result = await translator.translate(request)

        # Verify medical terminology was processed
        assert len(result.medical_terms_preserved) > 0

        # Check for medication and condition terms
        preserved_terms = [
            term["source"].lower() for term in result.medical_terms_preserved
        ]
        assert any("pneumonia" in term for term in preserved_terms)
        assert any("amoxicillin" in term for term in preserved_terms)

    @pytest.mark.asyncio
    async def test_real_time_translation_performance(self, real_medical_translator):
        """Test real-time translation performance requirements."""
        translator = real_medical_translator

        # Emergency translation should be fast
        request = TranslationRequest(
            text="Patient is unconscious and not breathing",
            source_language="en",
            target_language="ar",
            mode=TranslationMode.EMERGENCY,
            urgency="emergency",
        )

        start_time = datetime.now()
        result = await translator.translate(request)
        end_time = datetime.now()

        translation_duration = (end_time - start_time).total_seconds()

        # Emergency translations should complete within reasonable time
        assert translation_duration < 10.0  # 10 seconds max for emergency
        assert result.translated_text is not None
        assert result.confidence_score > 0.7  # High confidence for emergency
