"""
Stress Level Analysis Demo for Medical Voice Processing

This demonstrates comprehensive stress detection and analysis
from voice recordings in medical contexts.
"""

import asyncio
from datetime import datetime, timedelta

import numpy as np

from src.voice.stress_analysis import (
    StressAnalysisConfig,
    StressAnalyzer,
    StressIndicator,
    StressLevel,
    StressType,
)


async def demonstrate_stress_analysis():
    """Demonstrate stress analysis on simulated voice patterns."""
    print("Medical Voice Stress Analysis Demo")
    print("=" * 50)

    # Configure stress analyzer
    config = StressAnalysisConfig(
        sample_rate=16000,
        enable_temporal_analysis=True,
        enable_breathing_analysis=True,
        acute_stress_threshold=0.7,
        chronic_stress_min_duration=30.0
    )

    analyzer = StressAnalyzer(config)

    # Test scenarios
    scenarios = [
        {
            "name": "Baseline (Calm)",
            "audio": generate_calm_voice(),
            "description": "Relaxed speaking, normal parameters"
        },
        {
            "name": "Acute Stress",
            "audio": generate_acute_stress_voice(),
            "description": "Sudden stress response, elevated pitch"
        }        {
            "name": "Chronic Stress",
            "audio": generate_chronic_stress_voice(),
            "description": "Long-term stress patterns, vocal fatigue"
        },
        {
            "name": "Physical Stress (Pain)",
            "audio": generate_physical_stress_voice(),
            "description": "Voice under physical distress"
        },
        {
            "name": "High Anxiety",
            "audio": generate_anxiety_voice(),
            "description": "Anxiety-induced vocal changes"
        }
    ]

    # First, establish baseline
    print("\nEstablishing baseline from calm samples...")
    baseline_samples = [generate_calm_voice() for _ in range(3)]
    baseline = await analyzer.establish_baseline(baseline_samples)
    print(f"Baseline F0: {baseline.fundamental_frequency_mean:.1f} Hz")
    print(f"Baseline HNR: {baseline.harmonic_to_noise_ratio:.1f} dB")

    # Analyze each scenario
    results = []
    for scenario in scenarios:
        print(f"\n\nScenario: {scenario['name']}")
        print("-" * 40)
        print(f"Description: {scenario['description']}")

        # Analyze stress
        result = await analyzer.analyze_stress(scenario['audio'], baseline)
        results.append(result)

        # Display results
        print(f"\nStress Level: {result.stress_level.value.upper()}")
        print(f"Stress Score: {result.stress_score:.1%}")
        print(f"Confidence: {result.confidence_score:.2f}")

        if result.stress_types:
            print(f"\nStress Types Detected:")
            for stress_type in result.stress_types:
                print(f"  - {stress_type.value}")

        if result.active_indicators:
            print(f"\nActive Stress Indicators:")
            for indicator in result.active_indicators[:5]:  # Top 5
                print(f"  - {indicator.value.replace('_', ' ').title()}")
        print(f"\nClinical Significance:")
        print(f"  {result.clinical_significance}")

        if result.risk_factors:
            print(f"\nRisk Factors:")
            for risk in result.risk_factors[:3]:
                print(f"  - {risk}")

        if result.recommendations:
            print(f"\nRecommendations:")
            for rec in result.recommendations[:3]:
                print(f"  - {rec}")

        # Show key features
        if result.features:
            print(f"\nKey Voice Metrics:")
            print(f"  - F0 Mean: {result.features.fundamental_frequency_mean:.1f} Hz")
            print(f"  - Jitter: {result.features.jitter_local:.3f}")
            print(f"  - Shimmer: {result.features.shimmer_local:.3f}")
            print(f"  - HNR: {result.features.harmonic_to_noise_ratio:.1f} dB")
            print(f"  - Breathing Rate: {result.features.breath_rate:.1f} bpm")

    # Create stress profile
    print("\n\nCreating Stress Profile from All Samples...")
    print("=" * 50)

    profile = analyzer.create_stress_profile(results)

    print(f"\nStress Profile Summary:")
    print(f"  Average Stress Score: {profile['average_stress_score']:.1%}")
    print(f"  Score Range: {profile['stress_score_range'][0]:.1%} - {profile['stress_score_range'][1]:.1%}")
    print(f"  Predominant Level: {profile['predominant_level']}")
    print(f"  Trend: {profile['trend']}")

    print(f"\nStress Type Distribution:")
    for stress_type, count in profile['stress_types'].items():
        print(f"  - {stress_type}: {count} occurrences")

    print(f"\nMost Common Indicators:")
    sorted_indicators = sorted(profile['common_indicators'].items(),
                             key=lambda x: x[1], reverse=True)
    for indicator, count in sorted_indicators[:5]:
        print(f"  - {indicator.replace('_', ' ').title()}: {count} occurrences")

async def demonstrate_temporal_stress():
    """Demonstrate stress changes over time."""
    print("\n\nTemporal Stress Analysis Demo")
    print("=" * 50)

    analyzer = StressAnalyzer()

    # Simulate escalating stress over 30 seconds
    print("\nSimulating stress escalation over time...")

    # Create audio with increasing stress
    segments = []
    stress_levels = [0.2, 0.4, 0.6, 0.8, 0.95]  # Increasing stress

    for level in stress_levels:
        segment = generate_stress_voice_with_level(level, duration=6)
        segments.append(segment)

    combined_audio = np.concatenate(segments)

    # Analyze
    result = await analyzer.analyze_stress(combined_audio)

    print(f"\nOverall Stress Level: {result.stress_level.value}")
    print(f"Stress Variability: {result.stress_variability:.2f}")

    print("\nStress Timeline:")
    for timestamp, score in result.stress_timeline[::2]:  # Every other point
        bar = "█" * int(score * 20)
        print(f"  {timestamp:5.1f}s: {bar} {score:.1%}")

    if result.peak_stress_moments:
        print(f"\nPeak Stress Moments: {[f'{t:.1f}s' for t in result.peak_stress_moments]}")

    # Analyze recovery
    print("\n\nSimulating stress recovery...")
    recovery_audio = generate_stress_recovery_pattern()
    recovery_result = await analyzer.analyze_stress(recovery_audio)

    print(f"Recovery Pattern Detected: {recovery_result.stress_level.value}")
    print(f"Final Stress Score: {recovery_result.stress_score:.1%}")

# Voice generation functions for stress patterns

def generate_calm_voice(duration=5, sample_rate=16000):
    """Generate calm, relaxed voice pattern."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Stable F0 around 120 Hz (male) or 200 Hz (female)
    f0 = 120 + 5 * np.sin(2 * np.pi * 0.2 * t)  # Slow variation

    # Generate harmonics
    voice = np.sin(2 * np.pi * f0 * t)
    voice += 0.5 * np.sin(2 * np.pi * f0 * 2 * t)
    voice += 0.3 * np.sin(2 * np.pi * f0 * 3 * t)
    voice += 0.2 * np.sin(2 * np.pi * f0 * 4 * t)

    # Add minimal noise (good HNR)
    voice += 0.02 * np.random.randn(len(t))

    # Regular breathing pattern
    breathing = 0.1 * np.sin(2 * np.pi * 0.25 * t)  # 15 breaths/min
    voice *= (1 + breathing)

    return voice / np.max(np.abs(voice))


def generate_acute_stress_voice(duration=5, sample_rate=16000):
    """Generate acute stress voice pattern."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Elevated and variable F0
    f0_base = 180  # Elevated
    f0_variation = 30 * np.sin(2 * np.pi * 1.5 * t)  # Fast variation
    f0_tremor = 10 * np.sin(2 * np.pi * 8 * t)  # Tremor
    f0 = f0_base + f0_variation + f0_tremor

    # Generate voice with instability
    voice = np.sin(2 * np.pi * f0 * t)
    voice += 0.3 * np.sin(2 * np.pi * f0 * 2 * t)

    # Higher jitter and shimmer
    jitter = 0.02 * np.random.randn(len(t))
    voice *= (1 + jitter)
    # Increased noise (lower HNR)
    voice += 0.1 * np.random.randn(len(t))

    # Irregular breathing
    breathing = 0.15 * np.sin(2 * np.pi * 0.4 * t) * (1 + 0.3 * np.random.randn(len(t)))
    voice *= (1 + breathing)

    return voice / np.max(np.abs(voice))


def generate_chronic_stress_voice(duration=5, sample_rate=16000):
    """Generate chronic stress voice pattern."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Lower energy, rough voice
    f0 = 110 + 15 * np.sin(2 * np.pi * 0.3 * t)

    # Reduced harmonics (vocal fatigue)
    voice = 0.7 * np.sin(2 * np.pi * f0 * t)
    voice += 0.2 * np.sin(2 * np.pi * f0 * 2 * t)

    # High jitter and shimmer
    jitter = 0.03 * np.cumsum(np.random.randn(len(t))) / np.sqrt(len(t))
    shimmer = 0.05 * np.sin(2 * np.pi * 3 * t) * np.random.randn(len(t))
    voice *= (1 + jitter + shimmer)

    # Voice breaks
    for i in range(0, len(voice), sample_rate//2):
        if np.random.rand() > 0.7:
            voice[i:i+sample_rate//10] *= 0.1

    # High noise (poor voice quality)
    voice += 0.15 * np.random.randn(len(t))

    return voice / (np.max(np.abs(voice)) + 1e-10)


def generate_physical_stress_voice(duration=5, sample_rate=16000):
    """Generate voice pattern under physical stress/pain."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Variable pitch with sudden changes
    f0_base = 150
    f0 = np.ones_like(t) * f0_base
    # Add sudden pitch changes (pain spikes)
    for i in range(5):
        spike_pos = int(np.random.rand() * len(t))
        spike_len = int(0.2 * sample_rate)
        if spike_pos + spike_len < len(t):
            f0[spike_pos:spike_pos+spike_len] *= 1.5

    voice = np.sin(2 * np.pi * f0 * t)

    # Irregular amplitude (muscle tension)
    tension = 1 + 0.3 * np.abs(np.sin(2 * np.pi * 2 * t))
    voice *= tension

    # Glottal irregularities
    voice += 0.1 * np.sign(voice) * np.random.randn(len(t))

    # Strained breathing
    breathing = 0.2 * np.sin(2 * np.pi * 0.5 * t) * (1 + 0.5 * np.abs(np.random.randn(len(t))))
    voice *= (1 + breathing)

    return voice / np.max(np.abs(voice))


def generate_anxiety_voice(duration=5, sample_rate=16000):
    """Generate high anxiety voice pattern."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # High, unstable pitch
    f0 = 220 + 40 * np.sin(2 * np.pi * 2 * t) + 20 * np.random.randn(len(t))

    voice = np.sin(2 * np.pi * f0 * t)

    # Rapid amplitude modulation (trembling)
    trembling = 1 + 0.2 * np.sin(2 * np.pi * 10 * t)
    voice *= trembling

    # Fast, shallow breathing
    breathing = 0.3 * np.sin(2 * np.pi * 0.5 * t)  # 30 breaths/min
    voice *= (1 + breathing)

    # Add speech rushes and pauses
    for i in range(0, len(voice), sample_rate):
        if np.random.rand() > 0.6:
            voice[i:i+sample_rate//4] *= 2  # Speech rush
        elif np.random.rand() > 0.8:
            voice[i:i+sample_rate//4] *= 0.1  # Pause

    return voice / (np.max(np.abs(voice)) + 1e-10)

def generate_stress_voice_with_level(stress_level, duration=6, sample_rate=16000):
    """Generate voice with specific stress level (0-1)."""
    # Interpolate between calm and stressed voice
    calm = generate_calm_voice(duration, sample_rate)
    stressed = generate_acute_stress_voice(duration, sample_rate)

    return calm * (1 - stress_level) + stressed * stress_level


def generate_stress_recovery_pattern(duration=10, sample_rate=16000):
    """Generate pattern showing stress recovery."""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Start stressed, gradually calm down
    segments = []
    stress_curve = 0.9 * np.exp(-t / 3)  # Exponential decay

    for i in range(10):
        segment_start = i * sample_rate
        segment_end = (i + 1) * sample_rate

        if segment_end <= len(t):
            stress_level = stress_curve[segment_start]
            segment = generate_stress_voice_with_level(stress_level, 1, sample_rate)
            segments.append(segment)

    return np.concatenate(segments)


async def main():
    """Run all demonstrations."""
    print("HAVEN HEALTH PASSPORT")
    print("Voice Stress Analysis System")
    print("=" * 60)
    print("\nThis demo shows comprehensive stress detection from voice,")
    print("including acute stress, chronic stress, and physical distress.\n")

    # Basic stress analysis
    await demonstrate_stress_analysis()

    # Temporal stress analysis
    await demonstrate_temporal_stress()

    print("\n\nDemo completed!")
    print("\nNote: This demo uses simulated voice patterns.")
    print("Real implementation would process actual voice recordings")
    print("and integrate with medical monitoring systems.")


if __name__ == "__main__":
    # Set up logging
    import logging
    logging.basicConfig(level=logging.INFO)

    # Run demo
    asyncio.run(main())
