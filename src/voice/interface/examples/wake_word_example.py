#!/usr/bin/env python3
"""Wake Word Detection Example.

Demonstrates usage of the wake word detection system
for Haven Health Passport.

Security Note: All PHI data processed in wake word examples must be encrypted at rest
and in transit using AES-256 encryption standards.

Access Control: Wake word example implementations require proper authentication and authorization
to ensure PHI data is only accessible to authorized users.
"""

import time
from typing import Any, Iterator

import numpy as np

from src.voice.interface import (
    MultilingualWakeWordEngine,
    WakeWord,
    WakeWordConfig,
    WakeWordEngine,
)


def simulate_audio_stream(
    duration: int = 5, sample_rate: int = 16000
) -> Iterator[np.ndarray]:
    """Simulate audio stream with occasional 'wake word' patterns."""
    samples_per_chunk = 512
    chunks = int(duration * sample_rate / samples_per_chunk)

    for i in range(chunks):
        # Simulate different audio patterns
        if i % 20 == 0:  # Every ~0.64 seconds
            # Simulate wake word with higher energy
            audio = np.random.randn(samples_per_chunk) * 0.5
        else:
            # Normal background noise
            audio = np.random.randn(samples_per_chunk) * 0.05

        yield audio
        time.sleep(samples_per_chunk / sample_rate)


def main() -> None:
    """Run wake word detection examples."""
    print("=== Haven Health Passport Wake Word Detection Demo ===\n")

    # Example 1: Basic wake word detection
    print("1. Basic Wake Word Detection:")

    config = WakeWordConfig()
    engine = WakeWordEngine(config)

    # Show configured wake words
    print("Configured wake words:")
    for wake_word in config.wake_words:
        print(f"  - '{wake_word.phrase}' (sensitivity: {wake_word.sensitivity})")

    # Set up detection callback
    def on_detection(detection: Any) -> None:
        print("\n🎤 Wake word detected!")
        print(f"   Phrase: {detection.wake_word.phrase}")
        print(f"   Confidence: {detection.confidence:.2f}")
        print(f"   Time: {detection.timestamp.strftime('%H:%M:%S.%f')[:-3]}")
        print(f"   Energy level: {detection.energy_level:.3f}")

    engine.add_callback(on_detection)

    # Start detection
    print("\nStarting detection... (listening for 5 seconds)")
    engine.start()

    # Simulate audio input
    for audio_chunk in simulate_audio_stream(duration=5):
        engine.process_audio(audio_chunk)

    engine.stop()
    print("Detection stopped.\n")

    # Example 2: Custom wake words
    print("\n2. Custom Wake Words:")

    custom_config = WakeWordConfig(
        wake_words=[
            WakeWord("Emergency Haven", sensitivity=0.4),  # More sensitive
            WakeWord("Doctor Mode", sensitivity=0.7),  # Less sensitive
            WakeWord("Help Haven", sensitivity=0.5),
        ],
        min_confidence=0.6,
    )

    custom_engine = WakeWordEngine(custom_config)
    custom_engine.add_callback(on_detection)

    print("Custom wake words configured:")
    for wake_word in custom_config.wake_words:
        print(f"  - '{wake_word.phrase}' (sensitivity: {wake_word.sensitivity})")

    # Example 3: Multi-language wake words
    print("\n\n3. Multi-language Wake Words:")

    ml_config = WakeWordConfig(
        wake_words=[
            WakeWord("Hey Haven", language="en"),
            WakeWord("Hola Haven", language="es"),
            WakeWord("Bonjour Haven", language="fr"),
            WakeWord("Namaste Haven", language="hi"),
        ]
    )

    ml_engine = MultilingualWakeWordEngine(ml_config)

    print("Multi-language wake words:")
    for lang, _detector in ml_engine.language_models.items():
        words = [w.phrase for w in ml_config.wake_words if w.language == lang]
        print(f"  {lang}: {', '.join(words)}")

    # Example 4: Status monitoring
    print("\n\n4. Status Monitoring:")

    status_engine = WakeWordEngine(WakeWordConfig())

    print(f"Initial status: {status_engine.get_status().value}")

    status_engine.start()
    print(f"After start: {status_engine.get_status().value}")

    # Simulate detection
    def status_callback(detection: Any) -> None:
        print(f"Detection! Status: {status_engine.get_status().value}")

    status_engine.add_callback(status_callback)

    # Example 5: Integration with voice commands
    print("\n\n5. Integration Example:")
    print("In production, wake word detection would trigger command listening:")
    print("  1. User says: 'Hey Haven'")
    print("  2. System activates and listens for command")
    print("  3. User says: 'Check my medications'")
    print("  4. System processes command and responds")

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()
