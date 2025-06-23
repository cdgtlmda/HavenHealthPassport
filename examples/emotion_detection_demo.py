"""
Emotion Detection Demo for Medical Voice Analysis

This demonstrates emotion detection from voice recordings
in medical contexts.
"""

import asyncio
from datetime import datetime

import numpy as np

from src.voice.emotion_detection import (
    EmotionDetectionConfig,
    EmotionDetector,
    EmotionIntensity,
    EmotionType,
)


async def demonstrate_emotion_detection():
    """Demonstrate emotion detection on simulated audio."""
    print("Medical Voice Emotion Detection Demo")
    print("=" * 50)

    # Configure emotion detector
    config = EmotionDetectionConfig(
        sample_rate=16000,
        enable_medical_emotions=True,
        enable_temporal_analysis=True,
        pain_detection_sensitivity=0.8,
        distress_detection_sensitivity=0.85,
    )

    detector = EmotionDetector(config)

    # Simulate different emotional voice patterns
    scenarios = [
        {
            "name": "Neutral Patient",
            "audio": generate_neutral_voice(),
            "description": "Calm, steady voice",
        },
        {
            "name": "Anxious Patient",
            "audio": generate_anxious_voice(),
            "description": "Elevated pitch, fast speaking",
        },
        {
            "name": "Patient in Pain",
            "audio": generate_pain_voice(),
            "description": "Irregular pitch, voice breaks",
        },
        {
            "name": "Depressed Patient",
            "audio": generate_sad_voice(),
            "description": "Low energy, slow speech",
        },
    ]

    # Process each scenario
    for scenario in scenarios:
        print(f"\n\nScenario: {scenario['name']}")
        print("-" * 40)
        print(f"Description: {scenario['description']}")

        # Detect emotions
        result = await detector.detect_emotions(scenario["audio"])

        # Display results
        print(f"\nPrimary Emotion: {result.primary_emotion.value}")
        print(f"Confidence: {result.confidence_score:.2f}")

        print("\nEmotion Scores:")
        for score in result.emotion_scores[:3]:  # Top 3 emotions
            print(
                f"  - {score.emotion.value}: {score.confidence:.2f} "
                f"(intensity: {score.intensity.name})"
            )

        print(f"\nMedical Indicators:")
        print(f"  - Distress Level: {result.distress_level:.2f}")
        print(f"  - Pain Indicators: {result.pain_indicators:.2f}")
        print(f"  - Anxiety Markers: {result.anxiety_markers:.2f}")

        if result.clinical_notes:
            print("\nClinical Notes:")
            for note in result.clinical_notes:
                print(f"  - {note}")

        if result.features:
            print(f"\nVoice Characteristics:")
            print(
                f"  - Pitch: {result.features.pitch_mean:.1f} Hz "
                f"(±{result.features.pitch_std:.1f})"
            )
            print(f"  - Speaking Rate: {result.features.speaking_rate:.1f} syl/sec")
            print(f"  - Voice Quality (HNR): {result.features.hnr:.1f} dB")


async def demonstrate_temporal_analysis():
    """Demonstrate emotion changes over time."""
    print("\n\nTemporal Emotion Analysis Demo")
    print("=" * 50)

    detector = EmotionDetector()

    # Simulate audio with changing emotions
    # First 3 seconds: neutral
    # Next 3 seconds: increasing anxiety
    # Last 3 seconds: high distress

    audio_segments = [
        generate_neutral_voice(duration=3),
        generate_anxious_voice(duration=3, intensity=0.7),
        generate_pain_voice(duration=3, intensity=0.9),
    ]

    combined_audio = np.concatenate(audio_segments)

    # Analyze with temporal tracking
    result = await detector.detect_emotions(combined_audio, segment_emotions=True)

    print("\nEmotion Timeline:")
    for timestamp, emotion in result.emotion_timeline:
        print(f"  {timestamp:.1f}s: {emotion.value}")

    print(f"\nEmotional Stability: {result.emotion_stability:.2f}")
    print("(1.0 = stable, 0.0 = highly variable)")

    # Create emotion profile from multiple samples
    print("\n\nCreating Patient Emotion Profile...")

    # Simulate multiple consultations
    results = []
    for i in range(3):
        audio = generate_mixed_emotions()
        result = await detector.detect_emotions(audio)
        results.append(result)

    profile = detector.get_emotion_profile(results)

    print("\nPatient Emotion Profile:")
    print(f"  Dominant Emotion: {profile['dominant_emotion']}")
    print(f"  Average Distress: {profile['average_distress']:.2f}")
    print(f"  Average Pain Indicators: {profile['average_pain_indicators']:.2f}")
    print(f"  Emotional Stability: {profile['emotional_stability']:.2f}")


# Voice generation functions (simulated audio patterns)


def generate_neutral_voice(duration=5, sample_rate=16000):
    """Generate neutral voice pattern."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Stable pitch around 150 Hz
    pitch = 150 + 10 * np.sin(2 * np.pi * 0.1 * t)
    voice = np.sin(2 * np.pi * pitch * t)

    # Add harmonics
    voice += 0.3 * np.sin(2 * np.pi * pitch * 2 * t)
    voice += 0.1 * np.sin(2 * np.pi * pitch * 3 * t)

    # Moderate noise
    voice += 0.05 * np.random.randn(len(t))

    return voice / np.max(np.abs(voice))


def generate_anxious_voice(duration=5, sample_rate=16000, intensity=0.8):
    """Generate anxious voice pattern."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Elevated and variable pitch
    base_pitch = 200 + 50 * intensity
    pitch_variation = 30 * intensity * np.sin(2 * np.pi * 2 * t)
    pitch = base_pitch + pitch_variation + 20 * np.random.randn(len(t))

    voice = np.sin(2 * np.pi * pitch * t)

    # Increased speaking rate (more modulation)
    voice *= 1 + 0.3 * np.sin(2 * np.pi * 5 * t)

    # Higher noise (tension)
    voice += 0.1 * intensity * np.random.randn(len(t))

    return voice / np.max(np.abs(voice))


def generate_pain_voice(duration=5, sample_rate=16000, intensity=0.8):
    """Generate voice pattern indicating pain."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Variable pitch with sudden changes (voice breaks)
    base_pitch = 180
    voice = np.zeros_like(t)

    # Create segments with voice breaks
    segment_length = int(0.5 * sample_rate)
    for i in range(0, len(t), segment_length):
        segment = t[i : i + segment_length]
        if np.random.rand() > 0.3:  # Voice present
            pitch = base_pitch + 40 * np.random.randn()
            voice[i : i + len(segment)] = np.sin(2 * np.pi * pitch * segment)

            # Add tremor (jitter)
            tremor = 0.1 * intensity * np.sin(2 * np.pi * 8 * segment)
            voice[i : i + len(segment)] *= 1 + tremor

    # High noise (poor voice quality)
    voice += 0.15 * intensity * np.random.randn(len(t))

    return voice / (np.max(np.abs(voice)) + 1e-10)


def generate_sad_voice(duration=5, sample_rate=16000):
    """Generate sad/depressed voice pattern."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Low pitch and energy
    pitch = 100 + 5 * np.sin(2 * np.pi * 0.2 * t)
    voice = 0.5 * np.sin(2 * np.pi * pitch * t)

    # Slow modulation (low speaking rate)
    voice *= 1 + 0.1 * np.sin(2 * np.pi * 0.5 * t)

    # Low noise
    voice += 0.02 * np.random.randn(len(t))

    return voice


def generate_mixed_emotions(duration=10, sample_rate=16000):
    """Generate voice with mixed emotions."""
    # Random mixture of emotions
    weights = np.random.rand(4)
    weights /= weights.sum()

    neutral = generate_neutral_voice(duration, sample_rate) * weights[0]
    anxious = generate_anxious_voice(duration, sample_rate, 0.6) * weights[1]
    pain = generate_pain_voice(duration, sample_rate, 0.5) * weights[2]
    sad = generate_sad_voice(duration, sample_rate) * weights[3]

    return neutral + anxious + pain + sad


async def main():
    """Run all demonstrations."""
    print("HAVEN HEALTH PASSPORT")
    print("Voice Emotion Detection System")
    print("=" * 60)
    print("\nThis demo shows emotion detection capabilities for")
    print("medical voice analysis, including pain and distress detection.\n")

    # Basic emotion detection
    await demonstrate_emotion_detection()

    # Temporal analysis
    await demonstrate_temporal_analysis()

    print("\n\nDemo completed!")
    print("\nNote: This demo uses simulated audio patterns.")
    print("Real implementation would process actual voice recordings.")


if __name__ == "__main__":
    # Set up basic logging
    import logging

    logging.basicConfig(level=logging.INFO)

    # Run demo
    asyncio.run(main())
