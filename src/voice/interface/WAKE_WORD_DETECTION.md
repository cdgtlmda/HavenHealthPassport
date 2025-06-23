# Wake Word Detection Documentation

## Overview

The Wake Word Detection system enables hands-free activation of the Haven Health Passport voice interface. It listens for specific trigger phrases (wake words) and activates the system when detected with sufficient confidence.

## Key Features

- **Multiple Wake Words**: Support for multiple wake word phrases
- **Multi-language Support**: Different wake words for different languages
- **Configurable Sensitivity**: Adjustable detection thresholds
- **Real-time Processing**: Low-latency detection for responsive activation
- **Noise Tolerance**: Robust detection in noisy environments
- **Callback System**: Event-driven architecture for handling detections

## Default Wake Words

The system comes with these default wake words:
- "Haven Health" (primary)
- "Hey Haven" (casual)
- "Haven Passport" (full name)

## Architecture

### Core Components

1. **WakeWord**: Configuration for a single wake word
   - Phrase and phonetic variations
   - Sensitivity settings
   - Language specification

2. **WakeWordDetector**: Abstract base for detection algorithms
   - Currently supports Porcupine (mock implementation)
   - Extensible for other engines (Snowboy, custom models)

3. **WakeWordEngine**: Main processing engine
   - Audio buffering and frame processing
   - Multi-threaded detection
   - Callback management

4. **MultilingualWakeWordEngine**: Extended engine with language support
   - Language-specific models
   - Automatic language routing

## Usage Examples

### Basic Usage

```python
from src.voice.interface.wake_word_detection import (
    WakeWordEngine,
    WakeWordConfig,
    WakeWord
)

# Initialize with default configuration
config = WakeWordConfig()
engine = WakeWordEngine(config)

# Add detection callback
def on_wake_word(detection):
    print(f"Wake word detected: {detection.wake_word.phrase}")
    print(f"Confidence: {detection.confidence:.2f}")

engine.add_callback(on_wake_word)

# Start listening
engine.start()

# Process audio (from microphone, file, etc.)
audio_data = get_audio_from_source()  # Your audio source
engine.process_audio(audio_data)

# Stop when done
engine.stop()
```

### Custom Wake Words

```python
# Create custom wake words
custom_config = WakeWordConfig(
    wake_words=[
        WakeWord(
            phrase="Doctor Haven",
            sensitivity=0.7,
            language="en",
            phonetic_variations=["Doc Haven", "Dr Haven"]
        ),
        WakeWord(
            phrase="Medical Assistant",
            sensitivity=0.8,
            language="en"
        )
    ],
    min_confidence=0.75
)

engine = WakeWordEngine(custom_config)
```

### Multi-language Support

```python
# Configure multi-language wake words
ml_config = WakeWordConfig(
    wake_words=[
        WakeWord("Hey Haven", language="en"),
        WakeWord("Hola Haven", language="es"),
        WakeWord("Bonjour Haven", language="fr"),
        WakeWord("Hallo Haven", language="de")
    ]
)

ml_engine = MultilingualWakeWordEngine(ml_config)

# Detect with language preference
detection = ml_engine.detect_multilingual(audio_frame, language="es")
```

## Configuration Options

### WakeWordConfig Parameters

- `wake_words`: List of wake word configurations
- `model_type`: Detection model (PORCUPINE, SNOWBOY, CUSTOM)
- `sample_rate`: Audio sample rate (default: 16000 Hz)
- `frame_length`: Samples per processing frame (default: 512)
- `buffer_duration`: Audio buffer length in seconds (default: 2.0)
- `min_confidence`: Minimum confidence threshold (default: 0.7)
- `activation_timeout`: Time window after detection (default: 0.5s)
- `noise_suppression`: Enable noise reduction (default: True)
- `voice_activity_detection`: Enable VAD (default: True)

## Integration with Voice Commands

```python
# Combine wake word detection with command parsing
from src.voice.interface import CommandGrammarEngine

command_engine = CommandGrammarEngine()
wake_engine = WakeWordEngine(WakeWordConfig())

def handle_wake_word(detection):
    print(f"Activated! Listening for command...")

    # Start recording for command
    command_audio = record_command_audio()  # Your recording logic

    # Transcribe and parse
    transcription = transcribe_audio(command_audio)
    parsed = command_engine.parse_command(transcription)

    if parsed:
        execute_command(parsed)

wake_engine.add_callback(handle_wake_word)
wake_engine.start()
```

## Performance Considerations

1. **Sample Rate**: 16kHz is optimal for wake word detection
2. **Frame Size**: 512 samples (32ms) provides good latency/accuracy balance
3. **Buffer Size**: 2 seconds allows for context while limiting memory
4. **Threading**: Background processing prevents UI blocking

## Best Practices

1. **Sensitivity Tuning**:
   - Start with 0.5 sensitivity
   - Increase for quiet environments
   - Decrease for noisy settings

2. **Multiple Wake Words**:
   - Provide variations for accessibility
   - Include formal and casual options
   - Support multiple languages

3. **Feedback**:
   - Provide immediate visual/audio confirmation
   - Show detection confidence to users
   - Log detections for improvement

4. **Privacy**:
   - Process audio locally when possible
   - Clear buffers after detection
   - Allow users to disable/customize

## Future Enhancements

- Integration with actual Porcupine SDK
- Custom wake word training
- Speaker verification
- Contextual activation
- Edge device optimization
- Wake word personalization
