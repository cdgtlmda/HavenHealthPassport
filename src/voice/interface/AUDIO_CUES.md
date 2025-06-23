# Audio Cues System Documentation

## Overview

The Audio Cues System provides non-verbal audio feedback for the Haven Health Passport, using programmatically generated tones and pre-recorded sounds to enhance user experience, accessibility, and provide immediate feedback without speech.

## Key Features

### 1. Comprehensive Cue Types
- **Feedback Cues**: Success, error, warning, notification sounds
- **Interaction Cues**: Button press, navigation, selection, toggle feedback
- **Status Cues**: Loading, processing, complete, cancelled indicators
- **Medical Cues**: Medication reminders, vital alerts, appointment notifications
- **Ambient Cues**: Welcome, goodbye, idle, background sounds

### 2. Tone Generation
- **Waveform Types**: Sine, square, triangle, sawtooth
- **Customizable Parameters**: Frequency, duration, volume, attack, decay
- **Tone Sequences**: Multiple tones combined for complex cues
- **Real-time Generation**: No pre-recorded files needed for basic cues

### 3. Accessibility Adaptations
- **Hearing Impaired**: Increased volume, lower frequencies, haptic patterns
- **Low Vision**: More distinct cues, additional audio markers
- **Cognitive Support**: Simplified cues, slower sequences
- **Motor Impaired**: Extended durations for interaction feedback

### 4. Contextual Awareness
- **User Preferences**: Volume, style, quiet hours
- **Environmental Adaptation**: Noise level adjustments
- **Priority System**: Critical cues can interrupt others
- **Smart Selection**: Appropriate cue selection based on context

## Architecture

### Core Components

#### AudioCue
Represents a single audio cue with its properties and audio data.

```python
cue = AudioCue(
    id="success",
    type=CueType.SUCCESS,
    category=CueCategory.FEEDBACK,
    name="Success",
    description="Positive feedback",
    tone_sequence=[
        ToneParameters(frequency=523.25, duration=0.1),  # C5
        ToneParameters(frequency=659.25, duration=0.1),  # E5
        ToneParameters(frequency=783.99, duration=0.15)  # G5
    ]
)
```

#### ToneGenerator
Generates audio waveforms programmatically.

```python
generator = ToneGenerator(sample_rate=44100)
audio_data = generator.generate_tone(
    ToneParameters(
        frequency=440.0,  # A4
        duration=0.5,
        volume=0.7,
        waveform="sine"
    )
)
```

#### AudioCueLibrary
Manages collection of audio cues.

```python
library = AudioCueLibrary()
cue = library.get_cue("success")
cues_by_type = library.get_cues_by_type(CueType.NOTIFICATION)
```

#### AccessibilityAudioAdapter
Adapts cues for accessibility needs.

```python
adapter = AccessibilityAudioAdapter(library)
adapted_cue = adapter.adapt_cue(cue, ["hearing_impaired"])
```

## Audio Cue Design

### Frequency Guidelines

| Cue Type | Frequency Range | Character |
|----------|----------------|-----------|
| Success | 500-800 Hz | Rising pitch, bright |
| Error | 300-500 Hz | Falling pitch, harsh |
| Notification | 800-1200 Hz | Pleasant chime |
| Warning | 600-1000 Hz | Alternating tones |
| Medical | 400-700 Hz | Gentle, important |

### Duration Guidelines

| Context | Duration | Purpose |
|---------|----------|---------|
| Button Press | 20-50ms | Quick feedback |
| Success/Error | 200-500ms | Clear indication |
| Notification | 300-800ms | Get attention |
| Loading | Repeating 200ms | Progress indication |
| Emergency | 100ms pulses | Urgent attention |

### Volume Levels

```python
volume_presets = {
    "subtle": 0.3,      # Interaction feedback
    "normal": 0.5,      # Standard notifications
    "important": 0.7,   # Medical reminders
    "critical": 0.9     # Emergency alerts
}
```

## Default Audio Cues

### Success Cue
- **Pattern**: C5 → E5 → G5 (major triad)
- **Duration**: 350ms total
- **Character**: Rising, bright, positive

### Error Cue
- **Pattern**: A4 → F4 (falling)
- **Duration**: 350ms total
- **Character**: Falling, square wave

### Notification Cue
- **Pattern**: A5 → C#6 → A5
- **Duration**: 260ms total
- **Character**: Pleasant chime

### Emergency Cue
- **Pattern**: 880Hz ↔ 1760Hz (alternating)
- **Duration**: 400ms total
- **Character**: Urgent, attention-getting

## Accessibility Features

### Hearing Impaired Adaptations

```python
# Automatic adaptations applied:
- Volume increased by 50%
- Frequencies > 1kHz shifted down by 30%
- Duration increased by 50%
- Haptic patterns generated
```

### Haptic Pattern Generation

```python
haptic_pattern = [
    {
        "type": "vibration",
        "intensity": 0.8,  # Based on frequency
        "duration": 150,   # Milliseconds
        "pattern": "pulse"
    }
]
```

### Cognitive Support

```python
# Simplifications applied:
- Complex sequences reduced to 2 tones
- Duration increased by 30%
- Volume reduced by 20%
- Softer waveforms used
```

## Context Management

### User Preferences

```python
preferences = {
    "volume": 0.7,              # 0.0 to 1.0
    "cue_style": "modern",      # modern, classic, minimal
    "haptic_enabled": True,
    "accessibility_needs": ["low_vision"],
    "quiet_hours": {
        "start": 22,  # 10 PM
        "end": 7      # 7 AM
    }
}
```

### Environmental Context

```python
environment = {
    "noise_level": "high",     # quiet, normal, high
    "time_of_day": "evening",
    "location": "hospital",
    "device_type": "mobile"
}
```

### Contextual Adaptations

| Environment | Adaptation |
|------------|------------|
| High Noise | +30% volume, +20% pitch |
| Quiet | -40% volume |
| Night Time | Skip non-critical cues |
| Hospital | Use medical-appropriate tones |

## Usage Examples

### Basic Usage

```python
# Initialize system
cue_system = AudioCueSystem()
await cue_system.initialize()

# Play a cue
await cue_system.play_cue(CueType.SUCCESS, user_id="user123")
```

### Medical Context

```python
# Create medical cues provider
medical = MedicalAudioCues(cue_system)

# Play medication reminder
await medical.play_medication_reminder("user123", "Insulin")

# Play vital recorded confirmation
await medical.play_vital_recorded("user123", "blood_pressure")
```

### Custom Cues

```python
# Create custom cue
custom_cue = AudioCue(
    id="custom_alert",
    type=CueType.NOTIFICATION,
    category=CueCategory.MEDICAL,
    name="Custom Alert",
    description="Special medical alert",
    tone_sequence=[
        ToneParameters(frequency=600, duration=0.2),
        ToneParameters(frequency=900, duration=0.2),
        ToneParameters(frequency=600, duration=0.3)
    ]
)

# Add to system
cue_system.add_custom_cue(custom_cue)

# Play custom cue
await cue_system.play_cue(CueType.NOTIFICATION, override_params={
    "volume": 0.8,
    "speed": 1.2
})
```

### Accessibility Setup

```python
# Configure for hearing impaired user
cue_system.update_user_preferences("user123", {
    "accessibility_needs": ["hearing_impaired"],
    "volume": 1.0,
    "haptic_enabled": True
})

# All cues will now be automatically adapted
await cue_system.play_cue(CueType.SUCCESS, "user123")
```

## Priority and Interruption

### Priority Levels

1. **CRITICAL**: Emergency alerts (always interrupts)
2. **HIGH**: Important medical notifications
3. **NORMAL**: Regular feedback
4. **LOW**: Subtle interactions
5. **AMBIENT**: Background sounds

### Interruption Rules

```python
# Critical cues interrupt everything
if new_cue.priority == CuePriority.CRITICAL:
    await cue_system.stop_all_cues()
    await cue_system.play_cue(new_cue.type)
```

## Performance Optimization

### Audio Generation Caching
- Generated tones are cached in memory
- Cache key includes all tone parameters
- Reduces CPU usage for repeated cues

### Efficient Waveform Generation
```python
# Pre-calculated lookup tables for common frequencies
# Sample-accurate generation
# Optimized for real-time performance
```

### Resource Management
- Active cue tracking
- Automatic cleanup of completed playback
- Memory-efficient audio data handling

## Integration

### With Voice Feedback System
```python
# Coordinate with voice feedback
await voice_feedback.provide_success_feedback(user_id)
await cue_system.play_cue(CueType.SUCCESS, user_id)
```

### With Haptic Feedback
```python
# Haptic patterns generated from audio cues
haptic_pattern = cue.metadata.get("haptic_pattern")
await haptic_system.play_pattern(haptic_pattern)
```

### With Visual Feedback
```python
# Synchronize with visual indicators
await visual_system.flash_success()
await cue_system.play_cue(CueType.SUCCESS)
```

## Best Practices

### 1. Cue Design
- Keep cues short and distinct
- Use frequency to convey meaning
- Test with target user groups
- Consider cultural differences

### 2. Accessibility First
- Always provide haptic alternatives
- Test with assistive technologies
- Allow complete customization
- Never rely solely on audio

### 3. Context Awareness
- Respect quiet hours
- Adapt to environment
- Consider user state
- Prioritize appropriately

### 4. Performance
- Pre-generate common cues
- Use appropriate sample rates
- Optimize for battery life
- Monitor resource usage

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| No audio output | Check device volume and permissions |
| Delayed playback | Reduce sample rate or pre-generate |
| Distorted sound | Check volume levels and clipping |
| Missing cues | Verify priority and context settings |

### Debug Mode

```python
# Enable debug logging
logging.getLogger("audio_cues").setLevel(logging.DEBUG)

# Get system statistics
stats = cue_system.get_cue_statistics()
print(f"Total played: {stats['total_played']}")
print(f"Active cues: {stats['active_cues']}")
```

## Future Enhancements

1. **3D Spatial Audio**: Directional cues for navigation
2. **Adaptive Learning**: Learn user preferences over time
3. **Emotion Detection**: Adjust cues based on user emotion
4. **Musical Themes**: Customizable musical cue sets
5. **Binaural Beats**: Therapeutic frequency combinations
6. **AI Generation**: ML-generated cues for specific contexts
7. **Cross-Platform Sync**: Consistent cues across devices
8. **Community Sharing**: User-created cue libraries
