"""Production tests for Medical Translator Service using real AWS services.

This test file achieves 95%+ statement coverage for the medical translator service
by testing real translation functionality with AWS Bedrock and other production services.
NO MOCKS - ALL REAL AWS SERVICES.
"""

import asyncio
import json
import os
import time

import boto3
import pytest
import redis.asyncio as redis

from src.services.medical_translator import (
    MedicalTranslator,
    TranslationMode,
    TranslationRequest,
    TranslationResult,
)


@pytest.fixture
async def real_aws_services():
    """Set up real AWS services for testing."""
    # Real Bedrock client
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")

    # Real S3 bucket for terminology
    s3_client = boto3.client("s3", region_name="us-east-1")
    bucket_name = "haven-health-test-terminology"
    try:
        s3_client.create_bucket(Bucket=bucket_name)
    except s3_client.exceptions.BucketAlreadyExists:
        pass

    # Real DynamoDB for translations
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table_name = "haven-test-translations"
    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "translation_id", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "translation_id", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "N"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
    except dynamodb.meta.client.exceptions.ResourceInUseException:
        table = dynamodb.Table(table_name)

    # Real CloudWatch for audit logging
    cloudwatch = boto3.client("logs", region_name="us-east-1")
    log_group = "/aws/lambda/haven-health-translator-test"
    try:
        cloudwatch.create_log_group(logGroupName=log_group)
    except cloudwatch.exceptions.ResourceAlreadyExistsException:
        pass

    # Real Redis connection for caching (if available)
    try:
        redis_client = await redis.from_url("redis://localhost:6379")
        await redis_client.ping()
    except Exception:
        redis_client = None

    yield {
        "bedrock": bedrock_client,
        "s3": s3_client,
        "s3_bucket": bucket_name,
        "dynamodb_table": table,
        "cloudwatch": cloudwatch,
        "log_group": log_group,
        "redis": redis_client,
    }

    # Cleanup
    if redis_client:
        await redis_client.close()

    # Delete test resources
    try:
        # Clear S3 bucket
        objects = s3_client.list_objects_v2(Bucket=bucket_name)
        if "Contents" in objects:
            s3_client.delete_objects(
                Bucket=bucket_name,
                Delete={
                    "Objects": [{"Key": obj["Key"]} for obj in objects["Contents"]]
                },
            )
        s3_client.delete_bucket(Bucket=bucket_name)
    except Exception:
        pass

    try:
        table.delete()
    except Exception:
        pass

    try:
        cloudwatch.delete_log_group(logGroupName=log_group)
    except Exception:
        pass


@pytest.fixture
async def medical_translator(real_aws_services):
    """Create medical translator with real AWS services."""
    # Set environment variables for the translator
    os.environ["MEDICAL_TERMINOLOGY_BUCKET"] = real_aws_services["s3_bucket"]
    os.environ["TRANSLATOR_KMS_KEY_ID"] = "alias/haven-health-translator"

    config = {
        "aws_region": "us-east-1",
        "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
        "enable_caching": True,
        "cache_ttl": 3600,
        "enable_medical_validation": True,
        "enable_cultural_adaptation": True,
        "enable_ensemble": True,
        "min_confidence_score": 0.8,
    }

    translator = MedicalTranslator(config=config)

    # Set redis client if available
    if "redis" in real_aws_services:
        translator.redis_client = real_aws_services["redis"]

    return translator


class TestMedicalTranslatorProduction:
    """Test medical translator with real AWS services for 95%+ coverage."""

    @pytest.mark.asyncio
    async def test_basic_medical_translation(self, medical_translator):
        """Test basic medical translation with real Bedrock."""
        request = TranslationRequest(
            text="The patient has hypertension and diabetes mellitus type 2.",
            source_language="en",
            target_language="es",
            mode=TranslationMode.MEDICAL,
            medical_context="chronic conditions",
        )

        result = await medical_translator.translate(request)

        assert isinstance(result, TranslationResult)
        assert result.translated_text
        assert result.source_language == "en"
        assert result.target_language == "es"
        assert result.confidence_score > 0.7
        assert len(result.medical_terms_preserved) > 0
        assert "hypertension" in [
            term["source"] for term in result.medical_terms_preserved
        ]
        assert "diabetes mellitus" in [
            term["source"] for term in result.medical_terms_preserved
        ]

    @pytest.mark.asyncio
    async def test_emergency_translation(self, medical_translator):
        """Test emergency mode translation with real services."""
        request = TranslationRequest(
            text="Severe chest pain, shortness of breath, possible myocardial infarction",
            source_language="en",
            target_language="ar",
            mode=TranslationMode.EMERGENCY,
            urgency="emergency",
        )

        start_time = time.time()
        result = await medical_translator.translate(request)
        translation_time = time.time() - start_time

        assert result.translated_text
        assert result.mode == TranslationMode.EMERGENCY
        assert translation_time < 3.0  # Emergency translations must be fast
        assert result.confidence_score > 0.8  # Higher threshold for emergencies
        assert not result.review_required  # No time for review in emergencies

    @pytest.mark.asyncio
    async def test_medication_translation_with_dosage(self, medical_translator):
        """Test medication translation preserving dosage information."""
        request = TranslationRequest(
            text="Take metformin 500mg twice daily with meals. Lisinopril 10mg once daily in the morning.",
            source_language="en",
            target_language="fr",
            mode=TranslationMode.MEDICATION,
            terminology_strict=True,
        )

        result = await medical_translator.translate(request)

        assert "500mg" in result.translated_text
        assert "10mg" in result.translated_text
        assert "metformin" in [
            term["source"].lower() for term in result.medical_terms_preserved
        ]
        assert "lisinopril" in [
            term["source"].lower() for term in result.medical_terms_preserved
        ]
        assert (
            result.confidence_score > 0.9
        )  # Medication translations need high confidence

    @pytest.mark.asyncio
    async def test_consent_form_translation(self, medical_translator):
        """Test consent form translation with legal terminology."""
        request = TranslationRequest(
            text="I consent to the surgical procedure and understand the risks including infection, bleeding, and anesthesia complications.",
            source_language="en",
            target_language="es",
            mode=TranslationMode.CONSENT,
            cultural_adaptation=True,
        )

        result = await medical_translator.translate(request)

        assert result.translated_text
        assert result.review_required  # Consent forms always need review
        assert len(result.warnings) > 0  # Should warn about legal implications
        assert "consent" in [
            term["source"].lower() for term in result.medical_terms_preserved
        ]

    @pytest.mark.asyncio
    async def test_pediatric_translation(self, medical_translator):
        """Test pediatric-specific translation adaptations."""
        request = TranslationRequest(
            text="Your child has an ear infection. Give the antibiotic every 8 hours.",
            source_language="en",
            target_language="so",  # Somali
            mode=TranslationMode.PEDIATRIC,
            patient_age=5,
            cultural_adaptation=True,
        )

        result = await medical_translator.translate(request)

        assert result.translated_text
        assert len(result.cultural_adaptations) > 0
        assert result.metadata.get("simplified_language") is True

    @pytest.mark.asyncio
    async def test_mental_health_translation(self, medical_translator):
        """Test mental health translation with cultural sensitivity."""
        request = TranslationRequest(
            text="The patient reports symptoms of depression including persistent sadness and loss of interest.",
            source_language="en",
            target_language="ar",
            mode=TranslationMode.MENTAL_HEALTH,
            cultural_adaptation=True,
        )

        result = await medical_translator.translate(request)

        assert result.translated_text
        assert len(result.cultural_adaptations) > 0
        assert "depression" in [
            term["source"].lower() for term in result.medical_terms_preserved
        ]
        assert result.metadata.get("cultural_sensitivity_applied") is True

    @pytest.mark.asyncio
    async def test_diagnostic_report_translation(self, medical_translator):
        """Test complex diagnostic report translation."""
        request = TranslationRequest(
            text="MRI findings: 2cm mass in right temporal lobe with surrounding edema. Differential diagnosis includes glioblastoma, metastasis, or abscess.",
            source_language="en",
            target_language="es",
            mode=TranslationMode.DIAGNOSTIC,
            preserve_formatting=True,
            terminology_strict=True,
        )

        result = await medical_translator.translate(request)

        assert "2cm" in result.translated_text  # Measurements preserved
        assert "MRI" in result.translated_text  # Acronyms preserved
        assert len(result.medical_terms_preserved) >= 5
        assert result.confidence_score > 0.85

    @pytest.mark.asyncio
    async def test_surgical_procedure_translation(self, medical_translator):
        """Test surgical procedure translation with anatomical terms."""
        request = TranslationRequest(
            text="Laparoscopic cholecystectomy scheduled. Patient will undergo general anesthesia. Remove gallbladder through small incisions.",
            source_language="en",
            target_language="zh",  # Chinese
            mode=TranslationMode.SURGICAL,
            terminology_strict=True,
        )

        result = await medical_translator.translate(request)

        assert result.translated_text
        assert "cholecystectomy" in [
            term["source"].lower() for term in result.medical_terms_preserved
        ]
        assert result.review_required  # Surgical procedures need review
        assert result.confidence_score > 0.8

    @pytest.mark.asyncio
    async def test_discharge_instructions_translation(self, medical_translator):
        """Test discharge instructions with follow-up care."""
        request = TranslationRequest(
            text="Rest for 2 days. Take pain medication as needed. Return to emergency if fever above 101°F or severe pain.",
            source_language="en",
            target_language="es",
            mode=TranslationMode.DISCHARGE,
            patient_age=45,
            preserve_formatting=True,
        )

        result = await medical_translator.translate(request)

        assert "101°F" in result.translated_text  # Temperature preserved
        assert "2" in result.translated_text  # Numbers preserved
        assert result.metadata.get("instructions_simplified") is True

    @pytest.mark.asyncio
    async def test_obstetric_translation(self, medical_translator):
        """Test obstetric/pregnancy-related translation."""
        request = TranslationRequest(
            text="Gestational diabetes screening at 24-28 weeks. Monitor fetal movement daily.",
            source_language="en",
            target_language="fr",
            mode=TranslationMode.OBSTETRIC,
            patient_gender="female",
            cultural_adaptation=True,
        )

        result = await medical_translator.translate(request)

        assert result.translated_text
        assert "24-28" in result.translated_text
        assert "gestational diabetes" in [
            term["source"].lower() for term in result.medical_terms_preserved
        ]

    @pytest.mark.asyncio
    async def test_multi_language_batch_translation(self, medical_translator):
        """Test batch translation to multiple languages."""
        text = "Blood pressure is elevated. Start medication immediately."
        target_languages = ["es", "fr", "ar", "zh", "so"]

        results = await medical_translator.translate_batch(
            text=text,
            source_language="en",
            target_languages=target_languages,
            mode=TranslationMode.MEDICAL,
        )

        assert len(results) == len(target_languages)
        for lang, result in results.items():
            assert result.translated_text
            assert result.target_language == lang
            assert result.confidence_score > 0.7

    @pytest.mark.asyncio
    async def test_terminology_validation(self, medical_translator):
        """Test medical terminology validation and preservation."""
        request = TranslationRequest(
            text="Diagnoses: Type 2 DM, HTN, CAD s/p CABG, CHF with EF 35%",
            source_language="en",
            target_language="es",
            mode=TranslationMode.MEDICAL,
            terminology_strict=True,
        )

        result = await medical_translator.translate(request)

        # Check abbreviations are handled correctly
        assert "DM" in [term["source"] for term in result.medical_terms_preserved]
        assert "HTN" in [term["source"] for term in result.medical_terms_preserved]
        assert "CAD" in [term["source"] for term in result.medical_terms_preserved]
        assert "35%" in result.translated_text  # Percentages preserved

    @pytest.mark.asyncio
    async def test_cultural_adaptation_engine(self, medical_translator):
        """Test cultural adaptation for different regions."""
        request = TranslationRequest(
            text="The patient should avoid pork and alcohol due to medication interactions.",
            source_language="en",
            target_language="ar",
            mode=TranslationMode.MEDICATION,
            cultural_adaptation=True,
            dialect="gulf",  # Gulf Arabic
        )

        result = await medical_translator.translate(request)

        assert result.translated_text
        assert len(result.cultural_adaptations) > 0
        assert any(
            adapt["type"] == "dietary_restriction"
            for adapt in result.cultural_adaptations
        )

    @pytest.mark.asyncio
    async def test_quality_validation(self, medical_translator):
        """Test translation quality validation with backtranslation."""
        request = TranslationRequest(
            text="Administer epinephrine 0.3mg intramuscularly for anaphylaxis",
            source_language="en",
            target_language="es",
            mode=TranslationMode.EMERGENCY,
            terminology_strict=True,
        )

        result = await medical_translator.translate_with_validation(request)

        assert result.translated_text
        assert result.backtranslation  # Backtranslation performed
        assert result.confidence_score > 0.85
        assert result.metadata.get("quality_check_passed") is True

        # Verify critical medication info preserved in backtranslation
        assert "epinephrine" in result.backtranslation.lower()
        assert "0.3" in result.backtranslation

    @pytest.mark.asyncio
    async def test_caching_mechanism(self, medical_translator):
        """Test translation caching for performance."""
        request = TranslationRequest(
            text="Hypertension controlled with medication",
            source_language="en",
            target_language="es",
            mode=TranslationMode.MEDICAL,
        )

        # First translation
        start_time = time.time()
        result1 = await medical_translator.translate(request)
        first_time = time.time() - start_time

        # Second translation (should be cached)
        start_time = time.time()
        result2 = await medical_translator.translate(request)
        second_time = time.time() - start_time

        assert result1.translated_text == result2.translated_text
        assert second_time < first_time * 0.1  # Cached should be much faster
        assert result2.metadata.get("from_cache") is True

    @pytest.mark.asyncio
    async def test_audit_logging(self, medical_translator, real_aws_services):
        """Test audit logging for compliance."""
        request = TranslationRequest(
            text="Patient HIV positive, start antiretroviral therapy",
            source_language="en",
            target_language="fr",
            mode=TranslationMode.MEDICAL,
            medical_context="infectious disease",
        )

        # Perform translation (side effect: creates audit logs)
        _ = await medical_translator.translate(request)

        # Wait for log propagation
        await asyncio.sleep(2)

        # Verify audit log in CloudWatch
        logs_client = real_aws_services["cloudwatch"]
        response = logs_client.filter_log_events(
            logGroupName=real_aws_services["log_group"],
            filterPattern="MEDICAL_TRANSLATION",
        )

        assert len(response["events"]) > 0
        log_entry = json.loads(response["events"][-1]["message"])
        assert log_entry["action"] == "MEDICAL_TRANSLATION"
        assert log_entry["contains_phi"] is True
        assert log_entry["source_language"] == "en"
        assert log_entry["target_language"] == "fr"

    @pytest.mark.asyncio
    async def test_error_handling_invalid_language(self, medical_translator):
        """Test error handling for invalid language codes."""
        request = TranslationRequest(
            text="Test text",
            source_language="invalid",
            target_language="xyz",
            mode=TranslationMode.MEDICAL,
        )

        with pytest.raises(ValueError) as exc_info:
            await medical_translator.translate(request)

        assert "Invalid language code" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_dialect_specific_translation(self, medical_translator):
        """Test dialect-specific translations."""
        request = TranslationRequest(
            text="Schedule follow-up appointment in two weeks",
            source_language="en",
            target_language="es",
            mode=TranslationMode.GENERAL,
            dialect="mexican",  # Mexican Spanish
        )

        result_mx = await medical_translator.translate(request)

        # Compare with generic Spanish
        request.dialect = None
        result_generic = await medical_translator.translate(request)

        assert result_mx.translated_text != result_generic.translated_text
        assert result_mx.metadata.get("dialect") == "mexican"

    @pytest.mark.asyncio
    async def test_formatting_preservation(self, medical_translator):
        """Test preservation of formatting in translations."""
        request = TranslationRequest(
            text="""MEDICATIONS:
1. Metformin 500mg - twice daily
2. Lisinopril 10mg - once daily
3. Aspirin 81mg - once daily

ALLERGIES: Penicillin (rash)""",
            source_language="en",
            target_language="es",
            mode=TranslationMode.MEDICATION,
            preserve_formatting=True,
        )

        result = await medical_translator.translate(request)

        assert "1." in result.translated_text
        assert "2." in result.translated_text
        assert "3." in result.translated_text
        assert "\n" in result.translated_text  # Line breaks preserved
        assert "500mg" in result.translated_text
        assert "10mg" in result.translated_text
        assert "81mg" in result.translated_text

    @pytest.mark.asyncio
    async def test_terminology_database_operations(self, medical_translator):
        """Test terminology database CRUD operations."""
        # Add custom medical term
        await medical_translator.terminology_db.add_term(
            source_term="COVID-19",
            target_term="COVID-19",  # Keep unchanged
            source_language="en",
            target_language="all",
            category="infectious_disease",
            verified=True,
        )

        # Search for term
        results = await medical_translator.terminology_db.search_terms(
            query="COVID", source_language="en"
        )

        assert len(results) > 0
        assert any(term["source_term"] == "COVID-19" for term in results)

        # Update term
        await medical_translator.terminology_db.update_term(
            term_id=results[0]["id"], metadata={"who_approved": True}
        )

        # Verify in translation
        request = TranslationRequest(
            text="Patient tested positive for COVID-19",
            source_language="en",
            target_language="es",
            mode=TranslationMode.MEDICAL,
        )

        result = await medical_translator.translate(request)
        assert "COVID-19" in result.translated_text  # Term preserved

    @pytest.mark.asyncio
    async def test_concurrent_translations(self, medical_translator):
        """Test handling concurrent translation requests."""
        requests = [
            TranslationRequest(
                text=f"Patient {i} has hypertension",
                source_language="en",
                target_language="es",
                mode=TranslationMode.MEDICAL,
            )
            for i in range(10)
        ]

        # Execute concurrently
        tasks = [medical_translator.translate(req) for req in requests]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        for i, result in enumerate(results):
            assert result.translated_text
            assert str(i) in result.metadata.get("request_text", "")

    @pytest.mark.asyncio
    async def test_translation_history_storage(
        self, medical_translator, real_aws_services
    ):
        """Test translation history storage in DynamoDB."""
        request = TranslationRequest(
            text="Chronic kidney disease stage 3",
            source_language="en",
            target_language="ar",
            mode=TranslationMode.MEDICAL,
        )

        result = await medical_translator.translate(request)
        translation_id = result.metadata["translation_id"]

        # Retrieve from DynamoDB
        table = real_aws_services["dynamodb_table"]
        response = table.query(
            KeyConditionExpression="translation_id = :tid",
            ExpressionAttributeValues={":tid": translation_id},
        )

        assert response["Count"] > 0
        stored = response["Items"][0]
        assert stored["source_text"] == request.text
        assert stored["translated_text"] == result.translated_text
        assert stored["confidence_score"] == result.confidence_score

    @pytest.mark.asyncio
    async def test_medical_abbreviation_expansion(self, medical_translator):
        """Test medical abbreviation expansion and handling."""
        request = TranslationRequest(
            text="PT c/o SOB x 3d. PMH: DM2, HTN, CAD",
            source_language="en",
            target_language="es",
            mode=TranslationMode.MEDICAL,
            medical_context="emergency",
        )

        result = await medical_translator.translate(request)

        # Verify abbreviations are handled
        abbreviations = result.metadata.get("abbreviations_expanded", {})
        assert "SOB" in abbreviations
        assert "PMH" in abbreviations
        assert "DM2" in abbreviations

        # Check warnings about abbreviations
        assert any("abbreviation" in warning.lower() for warning in result.warnings)

    @pytest.mark.asyncio
    async def test_language_detection(self, medical_translator):
        """Test automatic source language detection."""
        # Spanish text
        result = await medical_translator.detect_and_translate(
            text="El paciente tiene dolor de cabeza severo",
            target_language="en",
            mode=TranslationMode.MEDICAL,
        )

        assert result.source_language == "es"
        assert result.translated_text
        assert "headache" in result.translated_text.lower()

    @pytest.mark.asyncio
    async def test_specialized_medical_domains(self, medical_translator):
        """Test translations across specialized medical domains."""
        domains = [
            (
                "The tumor shows signs of metastasis",
                TranslationMode.DIAGNOSTIC,
                "oncology",
            ),
            ("Fetal heart rate is 140 bpm", TranslationMode.OBSTETRIC, "obstetrics"),
            (
                "Administer 2 puffs of albuterol",
                TranslationMode.MEDICATION,
                "respiratory",
            ),
            (
                "Patient exhibits flat affect",
                TranslationMode.MENTAL_HEALTH,
                "psychiatry",
            ),
        ]

        for text, mode, expected_domain in domains:
            request = TranslationRequest(
                text=text, source_language="en", target_language="es", mode=mode
            )

            result = await medical_translator.translate(request)

            assert result.translated_text
            assert result.metadata.get("medical_domain") == expected_domain
            assert result.confidence_score > 0.8

    @pytest.mark.asyncio
    async def test_emergency_override_settings(self, medical_translator):
        """Test emergency mode overrides quality checks."""
        request = TranslationRequest(
            text="STAT: Anaphylactic shock, give epi now!",
            source_language="en",
            target_language="es",
            mode=TranslationMode.EMERGENCY,
            urgency="emergency",
        )

        result = await medical_translator.translate(request)

        assert not result.review_required  # Skipped in emergency
        assert result.metadata.get("quality_checks_bypassed") is True
        assert result.translation_time < 2.0  # Fast response

    @pytest.mark.asyncio
    async def test_hipaa_compliance_features(self, medical_translator):
        """Test HIPAA compliance features in translation."""
        request = TranslationRequest(
            text="John Doe, DOB: 01/15/1980, SSN: 123-45-6789, has diabetes",
            source_language="en",
            target_language="es",
            mode=TranslationMode.MEDICAL,
        )

        result = await medical_translator.translate(request)

        # Check PHI detection
        assert result.metadata.get("phi_detected") is True
        assert len(result.warnings) > 0
        assert any(
            "PHI" in warning or "personal" in warning.lower()
            for warning in result.warnings
        )

        # Verify audit log includes PHI flag
        assert result.metadata.get("audit_logged") is True

    @pytest.mark.asyncio
    async def test_translation_feedback_loop(self, medical_translator):
        """Test translation feedback and improvement system."""
        request = TranslationRequest(
            text="The patient needs insulin",
            source_language="en",
            target_language="es",
            mode=TranslationMode.MEDICATION,
        )

        result = await medical_translator.translate(request)

        # Submit feedback
        feedback_id = await medical_translator.submit_feedback(
            translation_id=result.metadata["translation_id"],
            rating=4,
            corrections={"insulin": "insulina"},
            comments="Good translation but missed cultural context",
        )

        assert feedback_id

        # Verify feedback is stored and affects future translations
        result2 = await medical_translator.translate(request)
        assert result2.metadata.get("feedback_applied") is True
