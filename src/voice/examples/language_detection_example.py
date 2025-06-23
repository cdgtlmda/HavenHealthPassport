#!/usr/bin/env python3
"""
Example: Language Detection in Medical Transcription.

This example demonstrates how to use language detection features
for medical audio transcription in multi-language healthcare settings.
"""

import asyncio
import logging
from pathlib import Path

from src.voice.language_detection import ExtendedLanguageCode, MedicalContext
from src.voice.transcribe_medical import (
    TranscribeMedicalConfig,
    TranscribeMedicalService,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def basic_language_detection_example() -> None:
    """
    Perform basic language detection before transcription.

    This example shows how to detect the language of an audio file
    before transcribing it.
    """
    logger.info("=== Basic Language Detection Example ===")

    # Initialize service with language detection
    config = TranscribeMedicalConfig(
        region="us-east-1",
        auto_detect_language=True,
        preferred_languages=[
            ExtendedLanguageCode.EN_US,
            ExtendedLanguageCode.ES_US,
            ExtendedLanguageCode.FR_FR,
            ExtendedLanguageCode.ZH_CN,
        ],
        language_detection_confidence_threshold=0.75,
    )

    TranscribeMedicalService(config)

    # Path to audio file
    Path("path/to/patient_consultation.wav")

    try:
        # Detect language
        # TODO: Implement detect_language_before_transcription method
        # detection_result = await service.detect_language_before_transcription(
        #     audio_file, medical_context=MedicalContext.CONSULTATION
        # )
        logger.warning("detect_language_before_transcription not implemented")
        return

    except Exception as e:
        logger.error(f"Error in language detection: {e}")


async def multi_language_detection_example() -> None:
    """
    Detect and transcribe multi-language audio.

    This example handles audio files containing multiple languages,
    such as consultations with interpreters or code-switching scenarios.
    """
    logger.info("\n=== Multi-Language Detection Example ===")

    # Initialize service with multi-language support
    config = TranscribeMedicalConfig(
        region="us-east-1",
        auto_detect_language=True,
        enable_multi_language_detection=True,
        preferred_languages=[
            ExtendedLanguageCode.EN_US,
            ExtendedLanguageCode.ES_US,
            ExtendedLanguageCode.ZH_CN,
        ],
    )

    service = TranscribeMedicalService(config)

    # Enable language detection with specific settings
    # TODO: Implement configure_language_detection method
    # service.configure_language_detection(
    #     auto_detect=True,
    #     preferred_languages=[
    #         ExtendedLanguageCode.EN_US,
    #         ExtendedLanguageCode.ES_US,
    #         ExtendedLanguageCode.ZH_CN,
    #     ],
    #     confidence_threshold=0.7,
    #     enable_multi_language=True,
    # )

    # Path to multi-language audio
    audio_file = Path("path/to/multilingual_consultation.wav")

    try:
        # Detect language segments
        segments = await service.detect_multi_language_segments(
            audio_file,
            window_size=30.0,  # 30-second windows
            overlap=5.0,  # 5-second overlap
        )

        logger.info(f"Found {len(segments)} language segments:")

        for i, segment in enumerate(segments):
            logger.info(
                f"  Segment {i+1}: {segment.primary_language.value} "
                f"({segment.start_time:.1f}s - {segment.end_time:.1f}s) "
                f"[confidence: {segment.confidence:.2%}]"
            )
            if segment.is_code_switching:
                logger.info("    ⚡ Code-switching detected!")
                if segment.mixed_languages:
                    logger.info(
                        f"    Mixed languages: {[lang.value for lang in segment.mixed_languages]}"
                    )

        # Transcribe multi-language audio
        results = await service.transcribe_multi_language_audio(
            audio_file,
            job_name_prefix="multi_lang_consult",
            medical_context=MedicalContext.CONSULTATION,
        )

        # Display results
        logger.info("\nTranscription Results:")
        logger.info(f"Total segments: {results['total_segments']}")
        logger.info(f"Languages detected: {', '.join(results['languages_detected'])}")
        logger.info(f"Successful segments: {results['summary']['successful_segments']}")

        if results["summary"]["code_switching_detected"]:
            logger.info("Code-switching was detected in the audio")

        # Show sample of merged transcript
        if results["merged_transcript"]:
            logger.info("\nMerged transcript preview:")
            logger.info(results["merged_transcript"][:500] + "...")

    except Exception as e:
        logger.error(f"Error in multi-language detection: {e}")


async def transcript_verification_example() -> None:
    """
    Verify language of transcribed text.

    This example shows how to verify that a transcript is in the
    expected language, useful for quality assurance.
    """
    logger.info("\n=== Transcript Language Verification Example ===")

    # Initialize service
    config = TranscribeMedicalConfig(region="us-east-1")
    service = TranscribeMedicalService(config)

    # Sample transcripts in different languages
    transcripts = {
        "english": "The patient reports chest pain and shortness of breath. "
        "Blood pressure is elevated at 150/90.",
        "spanish": "El paciente presenta dolor torácico y dificultad respiratoria. "
        "La presión arterial está elevada a 150/90.",
        "french": "Le patient signale des douleurs thoraciques et un essoufflement. "
        "La pression artérielle est élevée à 150/90.",
        "mixed": "The patient dice que tiene chest pain y shortness of breath. "
        "La blood pressure está elevated.",
    }

    for lang_name, transcript in transcripts.items():
        logger.info(f"\nVerifying {lang_name} transcript:")
        logger.info(f"Text: {transcript[:100]}...")

        # Verify language
        matches, result = service.verify_language_from_transcript(transcript)

        logger.info(f"Detected language: {result.primary_language.value}")
        logger.info(f"Confidence: {result.confidence:.2%}")

        # Check for medical terminology
        lang_info = service.language_detection_manager.get_language_info(
            result.primary_language
        )
        logger.info(f"Medical terms available: {lang_info['medical_terms_available']}")

        # For mixed language, check alternatives
        if lang_name == "mixed" and result.alternative_languages:
            logger.info("Also detected:")
            for alt_lang, conf in result.alternative_languages[:2]:
                logger.info(f"  - {alt_lang.value}: {conf:.2%}")


async def language_support_info_example() -> None:
    """
    Get language support information.

    This example shows how to query supported languages and capabilities.
    """
    logger.info("\n=== Language Support Information Example ===")

    # Initialize service
    config = TranscribeMedicalConfig(region="us-east-1")
    service = TranscribeMedicalService(config)

    # Get language detection info
    info = service.get_language_detection_info()

    logger.info(f"Language detection enabled: {info['enabled']}")
    logger.info(f"Multi-language enabled: {info['multi_language_enabled']}")
    logger.info(f"Confidence threshold: {info['confidence_threshold']}")

    # List supported languages
    logger.info(
        f"\nTotal supported languages: {len(info['supported_languages']['all'])}"
    )
    logger.info("Languages supported for medical transcription:")
    for lang in info["supported_languages"]["medical_transcription"]:
        logger.info(f"  - {lang}")

    # Get detailed info for specific languages
    logger.info("\nDetailed language information:")
    for lang_code in [
        ExtendedLanguageCode.EN_US,
        ExtendedLanguageCode.ES_US,
        ExtendedLanguageCode.ZH_CN,
    ]:
        lang_info = service.language_detection_manager.get_language_info(lang_code)
        logger.info(f"\n{lang_code.value}:")
        logger.info(f"  Name: {lang_info['name']}")
        logger.info(f"  Family: {lang_info['family']}")
        logger.info(
            f"  Medical transcription: {lang_info['medical_transcription_supported']}"
        )
        logger.info(f"  Medical terms: {lang_info['medical_terms_available']}")
        if lang_info["dialect"]:
            logger.info(f"  Dialect: {lang_info['dialect']}")


async def main() -> None:
    """Run all language detection examples."""
    await basic_language_detection_example()
    await multi_language_detection_example()
    await transcript_verification_example()
    await language_support_info_example()


if __name__ == "__main__":
    asyncio.run(main())
