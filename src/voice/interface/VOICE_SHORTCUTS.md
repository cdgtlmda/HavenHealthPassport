# Voice Shortcuts Documentation

## Overview

The Voice Shortcuts system provides quick access to frequently used commands in the Haven Health Passport application. Instead of speaking full commands, users can use abbreviated shortcuts for common actions.

## Key Features

- **Pre-configured Shortcuts**: Common medical and navigation shortcuts
- **Custom Shortcuts**: Users can create personalized shortcuts
- **Fuzzy Matching**: Intelligent matching for variations
- **Scope Awareness**: Context-sensitive shortcuts
- **Usage Tracking**: Learn from user patterns
- **Multi-language Support**: Shortcuts in different languages

## Default Shortcuts

### Navigation
- `home` → "go to home"
- `back` → "go back"
- `meds` → "show my medications" (aliases: pills, medicines)

### Quick Actions
- `vitals` → "record vitals"
- `pain` → "record pain level"
- `refill` → "refill prescriptions"

### Emergency
- `help` → "emergency help" (Priority: EMERGENCY)
- `911` → "call emergency services" (aliases: emergency)

### Medical Records
- `records` → "show medical records"
- `allergies` → "show my allergies"

### Status Checks
- `status` → "health status summary"
- `appointments` → "show upcoming appointments" (aliases: schedule)

## Usage Examples

### Basic Usage

```python
from src.voice.interface import ShortcutEngine, ShortcutConfig

# Initialize with default shortcuts
config = ShortcutConfig()
engine = ShortcutEngine(config)

# Find and execute shortcut
match = engine.find_shortcut("meds")
if match:
    full_command = match.to_command()
    print(f"Executing: {full_command}")
    # Output: "Executing: show my medications"
```

### Custom Shortcuts

```python
from src.voice.interface import VoiceShortcut, ShortcutCategory

# Create custom shortcut
custom = VoiceShortcut(
    phrase="bp",
    full_command="record blood pressure",
    category=ShortcutCategory.QUICK_ACTION,
    description="Quick blood pressure check"
)

# Add to engine
engine.add_custom_shortcut(custom)

# Use custom shortcut
match = engine.find_shortcut("bp")
print(match.to_command())  # "record blood pressure"
```

### Scope-Based Shortcuts

```python
from src.voice.interface import ShortcutScope

# Find shortcuts in specific context
match = engine.find_shortcut("diagnose", scope=ShortcutScope.MEDICAL)

# Get all shortcuts for current screen
medical_shortcuts = engine.get_all_shortcuts(scope=ShortcutScope.MEDICAL)
```

### Personalized Shortcuts

```python
from src.voice.interface import PersonalizedShortcutEngine

# Create personalized engine
engine = PersonalizedShortcutEngine(config, user_id="user123")

# Learn from user patterns
engine.learn_pattern("check bp", "record blood pressure")
engine.learn_pattern("my bp", "record blood pressure")

# Get suggestions based on usage
suggestion = engine.suggest_shortcut("record blood pressure")
if suggestion:
    print(f"Suggested shortcut: '{suggestion.phrase}'")
```

## Configuration Options

### ShortcutConfig Parameters

- `shortcuts`: List of pre-configured shortcuts
- `fuzzy_matching`: Enable intelligent matching (default: True)
- `min_confidence`: Minimum confidence for fuzzy matches (default: 0.8)
- `max_shortcuts_per_category`: Limit per category (default: 10)
- `allow_custom_shortcuts`: Allow user customization (default: True)

## Integration with Voice Commands

```python
# Combine shortcuts with command grammar
from src.voice.interface import CommandGrammarEngine

shortcut_engine = ShortcutEngine(ShortcutConfig())
command_engine = CommandGrammarEngine()

def process_voice_input(text):
    # First check for shortcuts
    shortcut_match = shortcut_engine.find_shortcut(text)

    if shortcut_match:
        # Expand to full command
        full_command = shortcut_match.to_command()
    else:
        full_command = text

    # Parse full command
    parsed = command_engine.parse_command(full_command)
    return parsed
```

## Usage Statistics

```python
# Track most used shortcuts
most_used = engine.get_most_used_shortcuts(limit=5)
for phrase, count in most_used:
    print(f"{phrase}: used {count} times")

# Export configuration with stats
export_data = engine.export_shortcuts()
print(f"Custom shortcuts: {len(export_data['custom_shortcuts'])}")
print(f"Usage patterns: {export_data['usage_stats']}")
```

## Best Practices

1. **Keep shortcuts short**: 1-2 words maximum
2. **Use memorable phrases**: Related to the action
3. **Avoid ambiguity**: Each shortcut should have clear intent
4. **Consider context**: Use scoped shortcuts appropriately
5. **Monitor usage**: Adjust based on actual patterns
6. **Provide discovery**: Help users learn available shortcuts

## Accessibility Features

- Voice feedback for shortcut recognition
- Alternative input methods supported
- Customizable for individual needs
- Clear confirmation of actions
