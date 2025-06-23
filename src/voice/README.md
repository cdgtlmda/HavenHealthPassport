# Voice Processing Module

## Overview

The Voice Processing module provides comprehensive medical audio transcription capabilities using Amazon Transcribe Medical. This module includes advanced features for healthcare-specific voice processing, including multi-channel support, language detection, and medical vocabulary handling.

## Features

### ✅ Implemented Features

1. **Amazon Transcribe Medical Integration**
   - Medical specialty vocabularies (Primary Care, Cardiology, Neurology, etc.)
   - HIPAA-compliant PHI redaction
   - High accuracy for medical terminology
   - Custom medical vocabulary support

2. **Speaker Identification**
   - Multi-speaker support with up to 10 speakers
   - Speaker diarization
   - Speaker role assignment

3. **Channel Identification**
   - Multi-channel audio separation
   - Channel role mapping (physician, patient, nurse, etc.)
   - Cross-talk detection
   - Audio quality assessment per channel
   - Predefined configurations for common scenarios

4. **Language Detection**
   - Automatic language detection for 25+ languages
   - Multi-language segment detection
   - Code-switching identification
   - Medical context-aware detection
   - Language verification for transcripts

## Architecture

```
src/voice/
├── __init__.py
├── transcribe_medical.py           # Main service implementation
├── speaker_identification.py       # Speaker identification features
├── custom_vocabularies.py         # Custom medical vocabulary management
├── medical_vocabularies.py        # Medical term definitions
├── language_detection.py          # Language detection capabilities
├── channel_identification/        # Channel processing module
│   ├── __init__.py
│   ├── channel_config.py         # Channel configuration classes
│   ├── channel_processor.py      # Audio channel processing
│   └── channel_transcription.py  # Channel-specific transcription
├── examples/                      # Usage examples
│   ├── channel_identification_example.py
│   └── language_detection_example.py
└── tests/                        # Test cases
    ├── test_speaker_identification.py
    ├── test_channel_identification.py
    └── test_language_detection.py
```

## Usage Examples

### Basic Transcription

```python
from src.voice.transcribe_medical import TranscribeMedicalService, TranscribeMedicalConfig

# Initialize service
config = TranscribeMedicalConfig(
    region="us-east-1",
    specialty=MedicalSpecialty.PRIMARYCARE
)
service = TranscribeMedicalService(config)

# Transcribe audio
result = await service.transcribe_audio_file(
    "consultation.wav",
    job_name="consultation_001"
)
```

### Multi-Channel Transcription

```python
# Enable channel identification
service.enable_channel_identification(preset='doctor_patient')

# Transcribe multi-channel audio
results = await service.transcribe_multi_channel_audio(
    "stereo_consultation.wav",
    process_channels_separately=True
)

# Export results
service.export_channel_transcriptions("output/")
```

### Language Detection

```python
# Configure language detection
service.configure_language_detection(
    auto_detect=True,
    preferred_languages=[
        ExtendedLanguageCode.EN_US,
        ExtendedLanguageCode.ES_US,
        ExtendedLanguageCode.FR_FR
    ]
)

# Detect language before transcription
detection_result = await service.detect_language_before_transcription(
    "patient_audio.wav",
    medical_context=MedicalContext.CONSULTATION
)

# Transcribe with auto-detected language
result = await service.transcribe_audio_file_with_language_detection(
    "patient_audio.wav"
)
```

## Configuration Options

### TranscribeMedicalConfig

- `region`: AWS region (default: "us-east-1")
- `specialty`: Medical specialty for vocabulary
- `language_code`: Primary language for transcription
- `channel_identification`: Enable multi-channel support
- `auto_detect_language`: Enable automatic language detection
- `content_redaction`: Enable PHI redaction
- `output_bucket`: S3 bucket for outputs

### Channel Identification

Predefined configurations available:
- `doctor_patient`: 2-channel doctor-patient consultation
- `telemedicine`: 3-channel telemedicine with interpreter
- `emergency_room`: Multi-channel emergency room recording

### Language Support

**Medical Transcription Languages:**
- English (US/UK)
- Spanish (US)

**Language Detection Support:**
- 25+ languages including English, Spanish, French, German, Portuguese, Chinese, Japanese, Korean, Italian, Dutch, Russian, Arabic, Hindi, and more

## API Reference

### Main Classes

#### TranscribeMedicalService
Main service class for medical transcription.

Key methods:
- `transcribe_audio_file()`: Transcribe a single audio file
- `enable_channel_identification()`: Enable multi-channel support
- `configure_language_detection()`: Configure language detection
- `detect_language_before_transcription()`: Detect audio language
- `transcribe_multi_channel_audio()`: Process multi-channel audio
- `detect_multi_language_segments()`: Find language changes in audio

#### ChannelProcessor
Handles multi-channel audio processing.

Key methods:
- `process_file()`: Process and separate audio channels
- `export_channels()`: Export separated channels
- `get_channel_summary()`: Get channel statistics

#### LanguageDetectionManager
Manages language detection capabilities.

Key methods:
- `detect_language()`: Detect language from audio
- `detect_multi_language_segments()`: Find language segments
- `detect_language_from_text()`: Verify transcript language

## Testing

Run tests with:
```bash
pytest src/voice/test_*.py -v
```

## Requirements

- Python 3.8+
- boto3
- numpy
- AWS credentials with Transcribe Medical access
- S3 bucket for audio storage

## Future Enhancements

- [ ] Real-time streaming transcription
- [ ] Accent adaptation
- [ ] Advanced noise reduction
- [ ] Batch processing optimization
- [ ] Punctuation restoration
- [ ] Custom pronunciation guides
- [ ] Integration with translation services
