# Voice Error Correction Flows Documentation

## Overview

The Voice Error Correction Flows module provides intelligent error recovery mechanisms for voice interactions in the Haven Health Passport system. It implements adaptive strategies to help users correct mistakes, clarify ambiguous commands, and complete partial inputs.

## Key Features

### 1. Error Types Handled
- **No Speech Detected**: When the system doesn't capture any audio
- **Low Confidence**: Speech recognized but with low confidence scores
- **Ambiguous Command**: Multiple valid interpretations possible
- **Incomplete Command**: Missing required parameters
- **Invalid Parameter**: Recognized but invalid parameter values
- **Out of Context**: Command doesn't match current context
- **Multiple Interpretations**: Several equally likely meanings
- **Language Mismatch**: User speaks in unexpected language
- **Background Noise**: Environmental interference
- **Pronunciation Error**: Medical terms or names mispronounced
- **Timeout**: User takes too long to respond
- **System Error**: Technical failures

### 2. Correction Strategies

#### Clarification Strategy
- Used for ambiguous commands with multiple interpretations
- Presents numbered options for user selection
- Supports both numeric and verbal selection
- Example:
  ```
  User: "Add aspirin"
  System: "I understood 'add aspirin', but I need clarification. Did you mean:
  1. Add medication aspirin
  2. Add aspirin to shopping list
  3. Add aspirin reminder"
  ```

#### Repetition Strategy
- Used for low confidence recognition
- Progressive prompts based on attempt number
- Environmental awareness (noise detection)
- Example:
  ```
  Attempt 1: "I didn't quite catch that. Could you please repeat your command?"
  Attempt 2: "I'm still having trouble understanding. Please speak clearly and repeat:"
  Attempt 3: "Let me try once more. Please say your command slowly:"
  ```

#### Spelling Strategy
- Used for difficult medical terms or names
- Phonetic alphabet support (NATO)
- Letter-by-letter confirmation
- Example:
  ```
  System: "Please spell the medication name using the phonetic alphabet."
  User: "Mike Echo Tango Foxtrot Oscar Romeo Mike India November"
  System: "I understood: METFORMIN"
  ```

#### Guided Completion Strategy
- Used for incomplete commands
- Step-by-step parameter collection
- Context-aware prompting
- Example:
  ```
  User: "Schedule appointment"
  System: "What date? (today, tomorrow, or specific date)"
  User: "Tomorrow"
  System: "What time? (optional)"
  User: "2 PM"
  System: "Which doctor? (optional)"
  ```

### 3. Adaptive Learning

The system learns from user interactions to improve future error handling:

- **User Capability Assessment**: Tracks user proficiency (Beginner → Expert)
- **Strategy Success Rates**: Monitors which strategies work best
- **Personalized Preferences**: Learns individual user patterns
- **Context Awareness**: Adapts to environmental factors

## Architecture

### Core Components

1. **ErrorContext**: Captures comprehensive error information
   - Error type and severity
   - Original user input
   - Confidence scores
   - Environmental factors
   - User history

2. **CorrectionFlow**: Defines the correction process
   - Selected strategy
   - Prompts and options
   - Success criteria
   - Fallback mechanisms

3. **ErrorCorrectionFlowManager**: Orchestrates correction flows
   - Strategy selection
   - Flow execution
   - Learning updates
   - History tracking

### Flow Diagram

```
Error Detected
     ↓
Analyze Error Context
     ↓
Select Correction Strategy
     ↓
Create Correction Flow
     ↓
Present Correction Prompt
     ↓
Process User Response
     ↓
Validate Correction
     ↓
Success? → Execute Command
     ↓ No
Retry or Fallback Strategy
```

## Usage Examples

### Basic Error Correction

```python
# User says something unclear
error_context = ErrorContext(
    error_type=ErrorType.LOW_CONFIDENCE,
    original_input="abd meication aspirn",
    confidence_score=0.3
)

# System creates correction flow
flow = await manager.handle_error(error_context)
# Output: "I didn't quite catch that. Could you please repeat your command?"

# User repeats clearly
result = await manager.process_correction(flow.id, "add medication aspirin")
# Success: Command executed
```

### Multi-Step Clarification

```python
# Ambiguous command
error_context = ErrorContext(
    error_type=ErrorType.AMBIGUOUS_COMMAND,
    original_input="check blood pressure",
    possible_interpretations=[
        "View blood pressure history",
        "Record new blood pressure reading",
        "Check blood pressure medication"
    ]
)

flow = await manager.handle_error(error_context)
# System presents options

result = await manager.process_correction(flow.id, "2")
# User selected: "Record new blood pressure reading"
```

### Guided Command Completion

```python
# Incomplete command
error_context = ErrorContext(
    error_type=ErrorType.INCOMPLETE_COMMAND,
    original_input="schedule appointment"
)

flow = await manager.handle_error(error_context)
# System: "What date? (today, tomorrow, or specific date)"

# Multiple steps to complete
result1 = await manager.process_correction(flow.id, "next Tuesday")
result2 = await manager.process_correction(flow.id, "3 PM")
result3 = await manager.process_correction(flow.id, "Dr. Smith")
# Complete command: "Schedule appointment next Tuesday 3 PM Dr. Smith"
```

## Configuration

### Strategy Selection Rules

| Error Type | Primary Strategy | Fallback Strategy |
|-----------|-----------------|-------------------|
| Low Confidence | Repetition | Spelling |
| Ambiguous | Clarification | Guided Completion |
| Incomplete | Guided Completion | Clarification |
| Pronunciation | Spelling | Repetition |
| Background Noise | Repetition | Text Input |

### Adaptive Parameters

- **Learning Rate**: 0.1 (strategy success updates)
- **Capability Growth**: +0.02 per success
- **Strategy Switch Threshold**: <30% success rate
- **Max Attempts**: 3 per error
- **Timeout**: 30-60 seconds (varies by strategy)

## Best Practices

### 1. Progressive Disclosure
- Start with simple corrections
- Increase complexity only if needed
- Provide examples in later attempts

### 2. Context Preservation
- Maintain conversation context
- Reference previous attempts
- Build on partial successes

### 3. User Education
- Provide helpful hints
- Teach optimal speaking patterns
- Offer alternative input methods

### 4. Graceful Degradation
- Always have a fallback option
- Offer text input as last resort
- Provide human assistance option

## Integration Points

### Voice Command Grammar
- Integrates with command parser
- Uses grammar rules for validation
- Leverages command templates

### Confirmation Protocols
- Works with confirmation system
- Shares user capability assessment
- Coordinates timeout handling

### Multi-language Support
- Language-specific error messages
- Cultural adaptation of strategies
- Phonetic alphabet variations

## Performance Metrics

- **Average Correction Success Rate**: >85% target
- **Time to Correction**: <30 seconds average
- **User Satisfaction**: >4.0/5.0 rating
- **Strategy Effectiveness**: Continuously monitored
- **Abandonment Rate**: <10% target

## Accessibility Considerations

### Vision Impaired Users
- Detailed audio descriptions
- No visual-only corrections
- Extended timeouts

### Hearing Impaired Users
- Visual correction options
- Text-based alternatives
- Haptic feedback support

### Cognitive Support
- Simplified language
- One-step-at-a-time approach
- Patient repetition

### Motor Impaired Users
- Voice-only corrections
- No time pressure
- Flexible input acceptance

## Future Enhancements

1. **Machine Learning Integration**
   - Predictive error prevention
   - Personalized strategy selection
   - Acoustic model adaptation

2. **Multimodal Corrections**
   - Visual cues with voice
   - Touch gesture support
   - Eye tracking integration

3. **Proactive Assistance**
   - Anticipate common errors
   - Suggest before mistakes
   - Learn from community patterns

4. **Advanced NLP**
   - Better intent understanding
   - Context-aware corrections
   - Semantic similarity matching
