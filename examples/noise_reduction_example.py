"""
Example usage of the noise reduction system for medical audio processing.

This demonstrates how to use the noise reduction components
with Amazon Transcribe Medical.
"""

import asyncio
from pathlib import Path

import numpy as np

from src.voice.noise_reduction import (
    NoiseDetector,
    NoiseLevel,
    NoiseReductionConfig,
    NoiseReductionMethod,
    NoiseReductionProcessor,
)
from src.voice.transcribe_integration import (
    TranscribeConfig,
    TranscribeMedicalIntegration,
)


async def main():
    """Demonstrate noise reduction for medical audio."""

    # 1. Initialize components
    print("Initializing noise reduction system...")

    # Configure noise reduction
    noise_config = NoiseReductionConfig(
        method=NoiseReductionMethod.SPECTRAL_SUBTRACTION,
        aggressiveness=1.0,
        preserve_voice=True,
        formant_protection=True,
    )

    # Configure Transcribe Medical
    transcribe_config = TranscribeConfig(
        region="us-east-1",
        language_code="en-US",
        medical_specialty="PRIMARYCARE",
        enable_noise_reduction=True,
        noise_reduction_config=noise_config,
    )

    # Initialize integration
    transcribe_integration = TranscribeMedicalIntegration(transcribe_config)
    # 2. Simulate audio data (in real use, load from file)
    print("\nGenerating simulated audio data...")
    sample_rate = 16000
    duration = 5  # seconds
    t = np.linspace(0, duration, sample_rate * duration)

    # Simulate voice (sine waves at speech frequencies)
    voice = (
        0.3 * np.sin(2 * np.pi * 200 * t)  # Fundamental
        + 0.2 * np.sin(2 * np.pi * 400 * t)  # Harmonics
        + 0.1 * np.sin(2 * np.pi * 800 * t)
    )

    # Add noise
    background_noise = 0.05 * np.random.randn(len(t))  # Background noise
    electrical_noise = 0.02 * np.sin(2 * np.pi * 60 * t)  # 60Hz hum

    noisy_audio = voice + background_noise + electrical_noise

    # 3. Analyze audio quality
    print("\nAnalyzing audio quality...")
    quality_report = await transcribe_integration.analyze_audio_quality(noisy_audio)

    print(f"Noise Level: {quality_report['noise_level']}")
    print(f"SNR: {quality_report['signal_to_noise_ratio']:.2f} dB")
    print(f"Noise Types: {', '.join(quality_report['noise_types'])}")
    print(f"Confidence: {quality_report['confidence_score']:.2f}")

    if quality_report["recommendations"]:
        print("\nRecommendations:")
        for rec in quality_report["recommendations"]:
            print(f"  - {rec}")

    # 4. Process with noise reduction
    print("\n\nProcessing audio with noise reduction...")

    # Direct noise reduction
    processor = NoiseReductionProcessor(sample_rate=sample_rate, config=noise_config)

    result = await processor.process_audio(noisy_audio, detect_noise=True)

    print(f"\nNoise Reduction Results:")
    print(f"  Original SNR: {result.original_snr:.2f} dB")
    print(f"  Processed SNR: {result.processed_snr:.2f} dB")
    print(f"  SNR Improvement: {result.snr_improvement:.2f} dB")
    print(f"  Processing Time: {result.processing_time_ms:.2f} ms")
    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    # 5. Create and save noise profile
    print("\n\nCreating noise profile...")

    # Extract noise samples (first second of audio)
    noise_samples = [noisy_audio[:sample_rate]]

    noise_profile = await processor.create_noise_profile_from_samples(
        noise_samples, profile_name="clinic_background"
    )

    # Save profile
    profile_path = Path("noise_profiles/clinic_background.json")
    processor.save_noise_profile(noise_profile, profile_path)
    print(f"Saved noise profile to {profile_path}")

    # 6. Transcribe with noise reduction (mock)
    print("\n\nTranscribing audio with noise reduction...")
    print("Note: Actual transcription requires AWS credentials and S3 bucket")

    # This would perform actual transcription:
    # result = await transcribe_integration.transcribe_medical_audio(
    #     noisy_audio,
    #     job_name="medical-consultation-001"
    # )

    print("\nExample complete!")


if __name__ == "__main__":
    asyncio.run(main())
