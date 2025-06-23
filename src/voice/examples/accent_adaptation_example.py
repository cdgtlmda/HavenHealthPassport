#!/usr/bin/env python3
"""
Example: Accent Adaptation in Medical Transcription.

This example demonstrates how to use accent adaptation features
to improve transcription accuracy for speakers with various accents.
"""

import asyncio
import logging
from pathlib import Path

from src.voice.accent_adaptation import AccentRegion, AdaptationStrategy
from src.voice.transcribe_medical import (
    MedicalSpecialty,
    TranscribeMedicalConfig,
    TranscribeMedicalService,
    TranscriptionStatus,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def basic_accent_detection_example() -> None:
    """
    Demonstrate basic accent detection and adaptation.

    This example shows how to detect a speaker's accent and
    apply appropriate adaptations for better transcription.
    """
    logger.info("=== Basic Accent Detection Example ===")

    # Initialize service with accent adaptation
    config = TranscribeMedicalConfig(
        region="us-east-1",
        specialty=MedicalSpecialty.PRIMARYCARE,
        enable_accent_adaptation=True,
        accent_detection_enabled=True,
    )

    service = TranscribeMedicalService(config)

    # Path to audio file
    audio_file = Path("path/to/patient_consultation.wav")

    try:
        # Detect accent
        accent_result = await service.detect_accent(audio_file)

        # Display results
        logger.info(f"Detected Accent: {accent_result.primary_accent.value}")
        logger.info(f"Accent Strength: {accent_result.accent_strength.value}")
        logger.info(f"Confidence: {accent_result.confidence:.2%}")

        if accent_result.acoustic_features:
            features = accent_result.acoustic_features
            logger.info(f"Speaking Rate: {features.speaking_rate:.2f} syllables/sec")
            logger.info(f"Pitch Mean: {features.pitch_mean:.1f} Hz")

        # Transcribe with accent adaptation
        result = await service.transcribe_with_accent_adaptation(
            audio_file, job_name="consultation_with_accent"
        )

        logger.info("Transcription started with accent adaptations")

        # Wait for completion
        result = await service.wait_for_completion(result.job_name)

        if result.status == TranscriptionStatus.COMPLETED:
            logger.info("Transcription completed successfully")
            if "detected_accent" in result.metadata:
                logger.info(
                    f"Applied adaptations for: {result.metadata['detected_accent']}"
                )

    except Exception as e:
        logger.error(f"Error in accent detection: {e}")


async def medical_pronunciation_example() -> None:
    """
    Demonstrate medical term pronunciation variants.

    This example shows how accent adaptation handles medical
    terminology pronunciation variations.
    """
    logger.info("\n=== Medical Pronunciation Variants Example ===")

    # Initialize service
    config = TranscribeMedicalConfig(
        region="us-east-1",
        enable_accent_adaptation=True,
        apply_medical_pronunciation_variants=True,
    )

    service = TranscribeMedicalService(config)

    # Common medical terms with accent variations
    medical_terms = [
        "diabetes",
        "laboratory",
        "medicine",
        "vitamin",
        "anesthesia",
        "prescription",
        "hospital",
    ]

    # Check pronunciation variants for different accents
    for term in medical_terms:
        logger.info(f"\nPronunciation variants for '{term}':")

        # US variants
        us_variants = service.get_medical_pronunciation_variants(
            term, AccentRegion.US_GENERAL
        )
        if us_variants:
            logger.info(f"  US: {', '.join(us_variants)}")

        # UK variants
        uk_variants = service.get_medical_pronunciation_variants(
            term, AccentRegion.UK_RP
        )
        if uk_variants:
            logger.info(f"  UK: {', '.join(uk_variants)}")

        # Other accent variants
        for accent in [AccentRegion.INDIAN, AccentRegion.SPANISH_ACCENT]:
            variants = service.get_medical_pronunciation_variants(term, accent)
            if variants:
                logger.info(f"  {accent.value}: {', '.join(variants)}")


async def custom_accent_adaptation_example() -> None:
    """
    Demonstrate custom accent adaptation strategies.

    This example demonstrates different adaptation strategies
    and their effects on transcription.
    """
    logger.info("\n=== Custom Accent Adaptation Example ===")

    # Initialize service
    config = TranscribeMedicalConfig(region="us-east-1", enable_accent_adaptation=True)

    service = TranscribeMedicalService(config)

    # Test different adaptation strategies
    strategies = [
        AdaptationStrategy.ACOUSTIC_MODEL,
        AdaptationStrategy.PRONUNCIATION,
        AdaptationStrategy.CONFIDENCE,
        AdaptationStrategy.VOCABULARY,
        AdaptationStrategy.COMBINED,
    ]

    # Path to test audio
    audio_file = Path("path/to/accented_speech.wav")

    for strategy in strategies:
        logger.info(f"\n--- Testing {strategy.value} strategy ---")

        # Configure adaptation with specific strategy
        service.configure_accent_adaptation(
            enable=True,
            detection_enabled=True,
            strategy=strategy,
            confidence_threshold=0.6,
        )

        # Get accent profile info
        southern_profile = service.get_accent_profile(AccentRegion.US_SOUTHERN)
        if southern_profile:
            logger.info(
                f"Accent profile loaded: {southern_profile.accent_region.value}"
            )
            logger.info(f"  - R-dropping: {southern_profile.r_dropping}")
            logger.info(f"  - G-dropping: {southern_profile.g_dropping}")
            logger.info(
                f"  - Speaking rate adjustment: {southern_profile.speaking_rate_adjustment}"
            )

        # Simulate transcription with forced accent
        try:
            await service.transcribe_with_accent_adaptation(
                audio_file,
                job_name=f"test_{strategy.value}",
                force_accent=AccentRegion.US_SOUTHERN,
                detect_language=False,
            )
            logger.info(f"Transcription started with {strategy.value} adaptations")

        except Exception as e:
            logger.error(f"Error with {strategy.value} strategy: {e}")


async def accent_profiles_overview() -> None:
    """
    Show overview of available accent profiles.

    This example shows all available accent profiles and their
    characteristics for medical transcription.
    """
    logger.info("\n=== Accent Profiles Overview ===")

    # Initialize service
    config = TranscribeMedicalConfig(region="us-east-1")
    service = TranscribeMedicalService(config)

    # Get accent adaptation info
    info = service.get_accent_adaptation_info()

    logger.info("Accent adaptation system info:")
    logger.info(f"  - Enabled: {info['enabled']}")
    logger.info(f"  - Supported accents: {len(info['supported_accents'])}")
    logger.info(f"  - Accent profiles loaded: {info['accent_profiles_loaded']}")
    logger.info(
        f"  - Medical terms with variants: {info['medical_terms_with_variants']}"
    )

    # List some supported accents
    logger.info("\nSupported accent regions:")
    for i, accent in enumerate(info["supported_accents"][:10]):
        logger.info(f"  {i+1}. {accent}")

    # Show accent database profiles
    logger.info("\nLoaded accent profiles:")
    db = service.accent_database
    for region, profile in list(db.profiles.items())[:5]:
        logger.info(f"\n{region.value}:")
        logger.info(f"  - Strength: {profile.accent_strength.value}")
        logger.info(
            f"  - Confidence adjustment: {profile.base_confidence_adjustment:+.2f}"
        )
        logger.info(f"  - Medical variants: {len(profile.medical_term_variants)}")


async def main() -> None:
    """Run all accent adaptation examples."""
    await basic_accent_detection_example()
    await medical_pronunciation_example()
    await custom_accent_adaptation_example()
    await accent_profiles_overview()


if __name__ == "__main__":
    asyncio.run(main())
