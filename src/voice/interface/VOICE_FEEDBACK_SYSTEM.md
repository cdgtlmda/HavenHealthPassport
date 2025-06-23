# Voice Feedback System Documentation

## Overview

The Voice Feedback System provides comprehensive audio feedback for the Haven Health Passport, using Amazon Polly for text-to-speech synthesis with adaptive, context-aware responses that enhance user experience and accessibility.

## Key Features

### 1. Multi-Type Feedback Support
- **Success**: Positive confirmations for completed actions
- **Error**: Clear error messages with guidance
- **Warning**: Cautionary messages for risky actions
- **Info**: General information and status updates
- **Question**: Interactive queries requiring response
- **Confirmation**: Action verification prompts
- **Progress**: Status updates for long operations
- **Notification**: Time-sensitive alerts
- **Tutorial**: Educational guidance
- **Encouragement**: Motivational support

### 2. Adaptive Voice Synthesis
- **Amazon Polly Integration**: Neural and standard voices
- **Multi-language Support**: 50+ languages and dialects
- **Voice Personas**: Professional, friendly, assistant, emergency, child
- **Prosody Control**: Speaking rate, pitch, volume adjustments
- **SSML Support**: Advanced speech markup for natural delivery

### 3. Context-Aware Adaptation
- **User Level Adjustment**: Beginner to expert adaptations
- **Accessibility Support**: Special needs accommodations
- **Emotional Intelligence**: Stress and frustration detection
- **Environmental Awareness**: Noise level adaptations
- **Learning Patterns**: Personalized feedback based on history

### 4. Priority Queue Management
- **5 Priority Levels**: Critical → Ambient
- **Intelligent Interruption**: Higher priority can interrupt
- **Queue Optimization**: Priority-based ordering
- **Playback Control**: Pause, resume, skip functionality

## Architecture

### Core Components

#### FeedbackTemplateLibrary
Manages reusable feedback templates with multi-language support and variations.

```python
template = FeedbackTemplate(
    id="medication_added",
    type=FeedbackType.SUCCESS,
    templates={
        "en": ["Medication {name} added.", "Added {name} to your list."],
        "es": ["Medicamento {name} agregado.", "Agregué {name} a tu lista."]
    },
    priority=FeedbackPriority.HIGH
)
```

#### VoiceSynthesizer
Handles AWS Polly integration for speech synthesis.

```python
synthesizer = VoiceSynthesizer(aws_region="us-east-1")
audio = await synthesizer.synthesize(
    text="Hello, how can I help you?",
    voice_params=VoiceParameters(
        voice_id="Joanna",
        language="en-US",
        engine="neural",
        speaking_rate=0.9
    )
)
```

#### AdaptiveFeedbackGenerator
Generates context-appropriate feedback with personalization.

```python
context = FeedbackContext(
    user_id="user123",
    user_level="Beginner",
    interaction_count=10,
    success_rate=0.7,
    accessibility_needs=["hearing_impaired"]
)

feedback = generator.generate_feedback(
    template_id="command_success",
    context=context,
    variables={"action": "medication added"}
)
```

#### FeedbackQueueManager
Manages playback queue with priority handling.

```python
queue_manager = FeedbackQueueManager()
await queue_manager.add_feedback(audio_feedback)
status = queue_manager.get_queue_status()
```

## Voice Parameters

### Basic Parameters
| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| speaking_rate | 0.25-4.0 | 1.0 | Speech speed multiplier |
| pitch | -20 to +20 | 0.0 | Voice pitch in semitones |
| volume | 0.0-1.0 | 1.0 | Audio volume level |

### Voice Selection
```python
voice_mapping = {
    "en-US": {
        "professional": "Joanna",   # Clear, professional
        "friendly": "Matthew",      # Warm, approachable
        "assistant": "Amy",         # Helpful, efficient
        "emergency": "Joey",        # Clear, urgent
        "child": "Ivy"             # Simple, cheerful
    }
}
```

## Feedback Templates

### Built-in Templates

#### Success Feedback
```python
"command_success": {
    "en": ["Done!", "Command completed.", "All set!"],
    "es": ["¡Hecho!", "Comando completado.", "¡Listo!"]
}
```

#### Error Feedback
```python
"command_error": {
    "en": ["Sorry, there was an error: {error_message}"],
    "es": ["Lo siento, hubo un error: {error_message}"]
}
```

#### Medical Templates
```python
"medication_reminder": {
    "en": ["Time to take your {medication_name}. The dose is {dosage}."]
}

"vital_recorded": {
    "en": ["Your {vital_type} of {value} has been recorded."]
}
```

### Custom Templates
```python
custom_template = FeedbackTemplate(
    id="custom_alert",
    type=FeedbackType.NOTIFICATION,
    templates={
        "en": ["Custom alert: {message}"]
    },
    sound_effects=["custom_sound.mp3"]
)

feedback_system.add_custom_template(custom_template)
```

## Adaptive Features

### User Level Adaptation
- **Beginners**: Slower speech, more detailed explanations, encouragement
- **Intermediate**: Normal pace, balanced detail
- **Advanced**: Faster speech, concise responses
- **Expert**: Minimal feedback, quick confirmations

### Accessibility Adaptations

#### Hearing Impaired
```python
if "hearing_impaired" in context.accessibility_needs:
    params.speaking_rate *= 0.8  # 20% slower
    params.volume = 1.0          # Maximum volume
    params.pitch += 2            # Higher pitch for clarity
```

#### Cognitive Support
```python
if "cognitive_support" in context.accessibility_needs:
    params.speaking_rate *= 0.6  # 40% slower
    # Use simplest template variations
    # Add pauses between sentences
```

#### Motor Impaired
- Extended timeouts for responses
- Confirmation of understanding
- Repetition allowed

### Environmental Adaptation
```python
if context.environment.get("noisy", False):
    params.volume = 1.0      # Maximum volume
    params.pitch += 2        # Higher pitch cuts through noise
    # Use clear, simple vocabulary
```

### Emotional Support
```python
if context.emotional_state == "stressed":
    params.speaking_rate *= 0.9  # Slightly slower
    params.pitch -= 1           # Lower, calming tone
    # Add reassuring language
```

## Priority System

### Priority Levels
1. **CRITICAL**: Emergency alerts, system failures
2. **HIGH**: Important updates, medication reminders
3. **NORMAL**: Regular confirmations, status updates
4. **LOW**: Optional feedback, tips
5. **AMBIENT**: Background sounds, music

### Interruption Rules
```python
def should_interrupt(new_feedback, current_feedback):
    # Critical always interrupts
    if new_feedback.priority == CRITICAL:
        return True

    # Higher priority interrupts if current is interruptible
    if (new_feedback.priority < current_feedback.priority and
        current_feedback.interruptible):
        return True

    return False
```

## Usage Examples

### Basic Usage
```python
# Initialize system
feedback_system = VoiceFeedbackSystem()
await feedback_system.initialize()

# Provide simple feedback
await feedback_system.provide_success_feedback(
    user_id="user123",
    action="medication added"
)
```

### Medical Context
```python
# Create medical feedback provider
medical = MedicalFeedbackProvider(feedback_system)

# Medication reminder
await medical.medication_reminder(
    user_id="user123",
    medication_name="Insulin",
    dosage="10 units"
)

# Vital signs recorded
await medical.vital_recorded(
    user_id="user123",
    vital_type="blood pressure",
    value="120/80"
)
```

### Advanced Usage
```python
# Update user context
feedback_system.update_user_context("user123", {
    "user_level": "Advanced",
    "interaction_count": 100,
    "success_rate": 0.92,
    "accessibility_needs": ["low_vision"],
    "emotional_state": "confident"
})

# Custom feedback with variables
await feedback_system.provide_feedback(
    user_id="user123",
    template_id="appointment_scheduled",
    variables={
        "doctor": "Dr. Smith",
        "date": "tomorrow at 2 PM",
        "location": "Main Clinic"
    },
    priority_override=FeedbackPriority.HIGH
)
```

### Queue Management
```python
# Check queue status
status = feedback_system.queue_manager.get_queue_status()
print(f"Queue length: {status['queue_length']}")

# Clear low priority items
feedback_system.queue_manager.clear_queue(
    priority_threshold=FeedbackPriority.NORMAL
)

# Stop all feedback
await feedback_system.stop_all_feedback()
```

## Sound Effects

### Built-in Effects
- `success_chime.mp3`: Positive completion sound
- `error_tone.mp3`: Error indication
- `notification.mp3`: Alert sound
- `warning.mp3`: Caution sound

### Adding Custom Effects
```python
# Load custom sound effect
feedback_system.sound_effects["custom_beep.mp3"] = audio_data

# Use in template
template.sound_effects = ["custom_beep.mp3"]
```

## Performance Optimization

### Caching
- Audio synthesis results are cached by content + voice parameters
- Cache key includes text, voice, rate, pitch, and format
- Reduces Polly API calls and latency

### Queue Optimization
- Priority-based insertion for O(n) complexity
- Batch similar feedback when possible
- Preload common feedback during idle time

### Resource Management
```python
# Get system status
status = feedback_system.get_system_status()
# Returns: queue_status, active_users, cached_audio, templates

# Clear old cache entries
feedback_system.synthesizer.cache.clear()
```

## Error Handling

### Polly Errors
```python
try:
    audio = await synthesizer.synthesize(text, params)
except BotoCore3Error as e:
    # Fallback to default voice
    # Log error for monitoring
    # Provide text-only fallback
```

### Queue Errors
- Failed playback removes item from queue
- Errors logged but don't stop queue processing
- Critical feedback retried once

## Monitoring and Analytics

### Metrics to Track
- Average synthesis time
- Cache hit rate
- Queue depth over time
- Feedback type distribution
- User satisfaction (implicit from interactions)

### User Feedback Patterns
```python
# Analyze feedback history
history = generator.user_feedback_history[user_id]
# Track: frequency, types, success correlation
```

## Best Practices

### 1. Template Design
- Keep messages concise and clear
- Provide multiple variations to avoid repetition
- Include all supported languages
- Use appropriate sound effects sparingly

### 2. Priority Assignment
- Reserve CRITICAL for true emergencies
- Use HIGH for time-sensitive medical information
- Default to NORMAL for most feedback
- Use LOW for optional enhancements

### 3. Accessibility First
- Always consider users with disabilities
- Test with screen readers
- Provide visual alternatives when needed
- Allow customization of voice parameters

### 4. Context Awareness
- Update user context regularly
- Consider environmental factors
- Adapt to user's emotional state
- Learn from interaction patterns

### 5. Performance
- Pre-synthesize common feedback
- Use appropriate cache strategies
- Monitor queue depth
- Optimize template variations

## Future Enhancements

1. **Emotion Detection**: Analyze user voice for emotional state
2. **Multilingual Mixing**: Code-switching support
3. **Custom Voice Training**: User-specific voice models
4. **Haptic Integration**: Vibration patterns with audio
5. **3D Spatial Audio**: Directional feedback for AR/VR
6. **Voice Cloning**: Familiar voices for comfort
7. **Music Therapy**: Therapeutic background music
8. **Predictive Feedback**: Anticipate user needs
