# Voice Command Grammar Documentation

## Overview

The Voice Command Grammar system provides a robust framework for parsing and interpreting voice commands in the Haven Health Passport application. It supports medical-specific commands, multi-language processing, and emergency handling.

## Key Components

### 1. Command Types

The system supports the following command types:
- **NAVIGATION**: Moving between app screens
- **SEARCH**: Finding information
- **CREATE/UPDATE/DELETE**: Data management
- **MEDICATION**: Medicine-related commands
- **APPOINTMENT**: Scheduling and management
- **VITALS**: Recording vital signs
- **SYMPTOM**: Logging symptoms
- **EMERGENCY**: Urgent assistance
- **TRANSLATION**: Language services
- **SETTINGS**: Configuration changes

### 2. Command Structure

Commands are parsed into structured data containing:
- Command type
- Parameters with validation
- Confidence score
- Priority level
- Language
- Confirmation requirements

### 3. Grammar Definition

Each command grammar includes:
- **Keywords**: Primary triggers (e.g., "medication", "medicine")
- **Aliases**: Alternative phrasings (e.g., "meds", "pills")
- **Parameters**: Required and optional inputs
- **Priority**: Execution priority (Emergency > Medical > Normal > Low)
- **Examples**: Sample commands for reference

## Usage Examples

### Basic Usage

```python
from src.voice.interface import CommandGrammarEngine

# Initialize the engine
engine = CommandGrammarEngine()

# Parse a command
parsed = engine.parse_command("Add medication aspirin")

if parsed:
    print(f"Command type: {parsed.command_type.value}")
    print(f"Parameters: {parsed.parameters}")
    print(f"Priority: {parsed.priority.value}")
```

### Medical Commands

```python
# Medication management
"Add medication aspirin"
"Take my morning medication"
"Refill prescription for insulin"

# Vital signs recording
"Record blood pressure 120 over 80"
"Temperature 98.6"
"Heart rate 72"

# Symptom logging
"I have a headache severity 7"
"Experiencing dizziness"
"My stomach hurts"
```

### Emergency Commands

Emergency commands have the highest priority and bypass confirmation:

```python
"Emergency"
"I need help"
"Call ambulance"
"Urgent medical assistance"
```

### Multi-language Support

```python
from src.voice.interface import MultilingualGrammarEngine

# Initialize multilingual engine
engine = MultilingualGrammarEngine()

# Add Spanish patterns
engine.add_language_patterns(
    "es",
    CommandType.MEDICATION,
    ["medicamento", "medicina", "pastilla"]
)

# Parse in Spanish
parsed = engine.parse_multilingual("Agregar medicamento", "es")
```

## Custom Grammar Creation

You can add custom grammars for specific use cases:

```python
from src.voice.interface import CommandGrammar, CommandParameter, ParameterType

custom_grammar = CommandGrammar(
    command_type=CommandType.APPOINTMENT,
    keywords=["appointment", "schedule", "book"],
    aliases=["meeting", "visit", "consultation"],
    parameters=[
        CommandParameter(
            name="doctor_name",
            type=ParameterType.PERSON,
            required=True
        ),
        CommandParameter(
            name="date",
            type=ParameterType.DATE,
            required=True
        )
    ],
    priority=CommandPriority.NORMAL,
    confirmation_required=True
)

engine.add_grammar(custom_grammar)
```

## Parameter Validation

Parameters support validation constraints:

```python
severity_param = CommandParameter(
    name="severity",
    type=ParameterType.NUMBER,
    constraints={"min": 1, "max": 10}
)

medication_param = CommandParameter(
    name="medication",
    type=ParameterType.MEDICATION_NAME,
    constraints={"allowed_values": ["aspirin", "ibuprofen", "acetaminophen"]}
)
```

## Best Practices

1. **Clear Keywords**: Use unambiguous keywords that users naturally say
2. **Multiple Aliases**: Support various ways users might express commands
3. **Appropriate Priority**: Set priority based on medical urgency
4. **Validation**: Always validate parameters before execution
5. **Confirmation**: Require confirmation for critical actions
6. **Error Handling**: Provide clear feedback when commands aren't understood

## Integration with Voice Processing

The grammar engine integrates with other voice components:

```python
# With transcription
from src.voice import TranscribeMedicalService
from src.voice.interface import CommandGrammarEngine

# Transcribe audio
transcription = await transcribe_service.transcribe(audio_data)

# Parse command from transcription
engine = CommandGrammarEngine()
parsed = engine.parse_command(transcription.text, transcription.language)

# Execute based on command type
if parsed and parsed.command_type == CommandType.EMERGENCY:
    # Handle emergency immediately
    await handle_emergency(parsed)
```

## Performance Considerations

- Grammar matching is optimized for real-time processing
- Confidence scores help prioritize ambiguous matches
- Language detection can be performed before parsing
- Caching frequently used grammars improves performance

## Future Enhancements

- Context-aware parsing based on conversation history
- Machine learning for improved command recognition
- Voice biometric integration for personalized commands
- Dialect and accent-specific grammar variations
