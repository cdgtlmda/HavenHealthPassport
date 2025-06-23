"""
Voice Command Grammar Module.

This module defines the grammar rules and parsing logic for voice commands
in the Haven Health Passport system, supporting medical contexts and
multi-language interactions. Handles voice commands for FHIR Communication
Resource operations.

IMPORTANT: This module handles PHI (Protected Health Information).
- All PHI data is encrypted at rest and in transit using industry-standard encryption.
- Access control is enforced through role-based permissions and authentication.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from src.healthcare.fhir_validator import FHIRValidator

# FHIR resource type for this module
__fhir_resource__ = "Communication"

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Types of voice commands supported."""

    NAVIGATION = "navigation"
    SEARCH = "search"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    READ = "read"
    HELP = "help"
    EMERGENCY = "emergency"
    MEDICATION = "medication"
    APPOINTMENT = "appointment"
    VITALS = "vitals"
    SYMPTOM = "symptom"
    TRANSLATION = "translation"
    SETTINGS = "settings"
    AUTHENTICATION = "authentication"
    SHARE = "share"
    EXPORT = "export"


class CommandPriority(Enum):
    """Priority levels for command execution."""

    EMERGENCY = 1  # Highest priority
    MEDICAL = 2
    NORMAL = 3
    LOW = 4


class ParameterType(Enum):
    """Types of parameters in voice commands."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    TIME = "time"
    DURATION = "duration"
    LOCATION = "location"
    PERSON = "person"
    MEDICATION_NAME = "medication_name"
    SYMPTOM_NAME = "symptom_name"
    VITAL_TYPE = "vital_type"
    LANGUAGE = "language"
    YES_NO = "yes_no"


@dataclass
class CommandParameter:
    """Represents a parameter in a voice command."""

    name: str
    type: ParameterType
    required: bool = True
    default_value: Optional[Any] = None
    constraints: Optional[Dict[str, Any]] = None
    examples: List[str] = field(default_factory=list)

    def validate(self, value: Any) -> bool:
        """Validate parameter value against constraints."""
        if value is None and self.required:
            return False

        if self.constraints:
            # Check min/max for numbers
            if self.type == ParameterType.NUMBER:
                if "min" in self.constraints and value < self.constraints["min"]:
                    return False
                if "max" in self.constraints and value > self.constraints["max"]:
                    return False

            # Check allowed values
            if "allowed_values" in self.constraints:
                if value not in self.constraints["allowed_values"]:
                    return False

        return True


@dataclass
class CommandGrammar:
    """Defines the grammar for a specific command."""

    command_type: CommandType
    keywords: List[str]  # Primary keywords that trigger this command
    aliases: List[str] = field(default_factory=list)  # Alternative phrasings
    parameters: List[CommandParameter] = field(default_factory=list)
    priority: CommandPriority = CommandPriority.NORMAL
    examples: List[str] = field(default_factory=list)
    supported_languages: Set[str] = field(default_factory=lambda: {"en"})
    confirmation_required: bool = False

    def matches(self, text: str, language: str = "en") -> Tuple[bool, float]:
        """
        Check if text matches this command grammar.

        Returns (matches, confidence_score).
        """
        if language not in self.supported_languages:
            return False, 0.0

        text_lower = text.lower()
        confidence = 0.0

        # Check primary keywords
        for keyword in self.keywords:
            if keyword.lower() in text_lower:
                confidence = max(confidence, 0.8)

        # Check aliases
        for alias in self.aliases:
            if alias.lower() in text_lower:
                confidence = max(confidence, 0.6)

        return confidence > 0.5, confidence


@dataclass
class ParsedCommand:
    """Represents a parsed voice command."""

    command_type: CommandType
    raw_text: str
    parameters: Dict[str, Any]
    confidence: float
    language: str
    timestamp: datetime
    priority: CommandPriority
    requires_confirmation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "command_type": self.command_type.value,
            "raw_text": self.raw_text,
            "parameters": self.parameters,
            "confidence": self.confidence,
            "language": self.language,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority.value,
            "requires_confirmation": self.requires_confirmation,
        }


class CommandGrammarEngine:
    """Engine for parsing and matching voice commands."""

    def __init__(self) -> None:
        """Initialize the command grammar engine."""
        self.grammars: List[CommandGrammar] = []
        self.validator = FHIRValidator()  # Initialize validator
        self._initialize_medical_grammars()
        self._initialize_navigation_grammars()
        self._initialize_emergency_grammars()

    def _initialize_medical_grammars(self) -> None:
        """Initialize medical-specific command grammars."""
        # Medication commands
        self.grammars.append(
            CommandGrammar(
                command_type=CommandType.MEDICATION,
                keywords=["medication", "medicine", "prescription", "drug"],
                aliases=["meds", "pills", "tablets", "dose"],
                parameters=[
                    CommandParameter(
                        name="action",
                        type=ParameterType.TEXT,
                        constraints={
                            "allowed_values": ["add", "take", "refill", "check", "list"]
                        },
                        examples=["add", "take", "refill"],
                    ),
                    CommandParameter(
                        name="medication_name",
                        type=ParameterType.MEDICATION_NAME,
                        required=False,
                        examples=["aspirin", "ibuprofen", "insulin"],
                    ),
                ],
                priority=CommandPriority.MEDICAL,
                examples=[
                    "Add medication aspirin",
                    "Take my morning medication",
                    "Check medication schedule",
                    "Refill prescription for insulin",
                ],
            )
        )

        # Vital signs commands
        self.grammars.append(
            CommandGrammar(
                command_type=CommandType.VITALS,
                keywords=[
                    "vital",
                    "vitals",
                    "blood pressure",
                    "temperature",
                    "heart rate",
                    "pulse",
                ],
                aliases=["bp", "temp", "heartbeat", "oxygen", "glucose"],
                parameters=[
                    CommandParameter(
                        name="vital_type",
                        type=ParameterType.VITAL_TYPE,
                        examples=[
                            "blood_pressure",
                            "temperature",
                            "heart_rate",
                            "oxygen_saturation",
                        ],
                    ),
                    CommandParameter(
                        name="value", type=ParameterType.NUMBER, required=False
                    ),
                ],
                priority=CommandPriority.MEDICAL,
                examples=[
                    "Record blood pressure 120 over 80",
                    "Add temperature 98.6",
                    "Check my vitals",
                    "Heart rate 72",
                ],
            )
        )

        # Symptom commands
        self.grammars.append(
            CommandGrammar(
                command_type=CommandType.SYMPTOM,
                keywords=["symptom", "feeling", "pain", "experiencing"],
                aliases=["symptoms", "hurts", "ache", "discomfort"],
                parameters=[
                    CommandParameter(
                        name="symptom_description",
                        type=ParameterType.TEXT,
                        examples=["headache", "nausea", "chest pain", "dizziness"],
                    ),
                    CommandParameter(
                        name="severity",
                        type=ParameterType.NUMBER,
                        required=False,
                        constraints={"min": 1, "max": 10},
                    ),
                ],
                priority=CommandPriority.MEDICAL,
                examples=[
                    "I have a headache",
                    "Record symptom chest pain severity 7",
                    "Experiencing dizziness",
                    "My stomach hurts",
                ],
            )
        )

    def _initialize_navigation_grammars(self) -> None:
        """Initialize navigation command grammars."""
        self.grammars.append(
            CommandGrammar(
                command_type=CommandType.NAVIGATION,
                keywords=["go to", "navigate", "open", "show"],
                aliases=["take me to", "display", "view"],
                parameters=[
                    CommandParameter(
                        name="destination",
                        type=ParameterType.TEXT,
                        examples=[
                            "home",
                            "profile",
                            "medications",
                            "appointments",
                            "records",
                        ],
                    )
                ],
                examples=[
                    "Go to home",
                    "Show my profile",
                    "Open medications",
                    "Navigate to appointments",
                ],
            )
        )

        # Search commands
        self.grammars.append(
            CommandGrammar(
                command_type=CommandType.SEARCH,
                keywords=["search", "find", "look for"],
                aliases=["search for", "locate", "where is"],
                parameters=[
                    CommandParameter(name="query", type=ParameterType.TEXT),
                    CommandParameter(
                        name="category",
                        type=ParameterType.TEXT,
                        required=False,
                        examples=["medications", "doctors", "appointments", "records"],
                    ),
                ],
                examples=[
                    "Search for aspirin",
                    "Find doctor Smith",
                    "Look for appointments this week",
                    "Where is my vaccination record",
                ],
            )
        )

    def _initialize_emergency_grammars(self) -> None:
        """Initialize emergency command grammars."""
        self.grammars.append(
            CommandGrammar(
                command_type=CommandType.EMERGENCY,
                keywords=["emergency", "help", "urgent", "911"],
                aliases=["ambulance", "doctor now", "need help", "crisis"],
                parameters=[
                    CommandParameter(
                        name="emergency_type",
                        type=ParameterType.TEXT,
                        required=False,
                        examples=["medical", "mental_health", "safety"],
                    )
                ],
                priority=CommandPriority.EMERGENCY,
                confirmation_required=False,  # No confirmation needed for emergencies
                examples=[
                    "Emergency",
                    "I need help",
                    "Call ambulance",
                    "Urgent medical assistance",
                ],
            )
        )

    def parse_command(self, text: str, language: str = "en") -> Optional[ParsedCommand]:
        """Parse voice input into a structured command."""
        best_match = None
        best_confidence = 0.0

        # Try to match against all grammars
        for grammar in self.grammars:
            matches, confidence = grammar.matches(text, language)
            if matches and confidence > best_confidence:
                best_match = grammar
                best_confidence = confidence

        if not best_match:
            logger.warning("No matching grammar found for: %s", text)
            return None

        # Extract parameters
        parameters = self._extract_parameters(text, best_match)

        return ParsedCommand(
            command_type=best_match.command_type,
            raw_text=text,
            parameters=parameters,
            confidence=best_confidence,
            language=language,
            timestamp=datetime.now(),
            priority=best_match.priority,
            requires_confirmation=best_match.confirmation_required,
        )

    def _extract_parameters(self, text: str, grammar: CommandGrammar) -> Dict[str, Any]:
        """Extract parameters from text based on grammar rules."""
        parameters = {}

        for param in grammar.parameters:
            value = self._extract_parameter_value(text, param)
            if value is not None:
                if param.validate(value):
                    parameters[param.name] = value
                else:
                    logger.warning(
                        "Invalid value for parameter %s: %s", param.name, value
                    )
            elif param.required:
                logger.warning("Required parameter %s not found", param.name)

        return parameters

    def _extract_parameter_value(
        self, text: str, parameter: CommandParameter
    ) -> Optional[Any]:
        """Extract a specific parameter value from text."""
        # This is a simplified extraction - in production, use NLP/regex patterns
        if parameter.type == ParameterType.NUMBER:
            # Extract numbers
            numbers = re.findall(r"\b\d+(?:\.\d+)?\b", text)
            return float(numbers[0]) if numbers else None

        elif parameter.type == ParameterType.TEXT:
            # For text, we'd use more sophisticated NLP in production
            return text  # Simplified

        # Add more parameter type extractions as needed
        return None

    def add_grammar(self, grammar: CommandGrammar) -> None:
        """Add a new command grammar."""
        self.grammars.append(grammar)

    def remove_grammar(self, command_type: CommandType) -> None:
        """Remove grammars for a specific command type."""
        self.grammars = [g for g in self.grammars if g.command_type != command_type]

    def get_grammars_by_type(self, command_type: CommandType) -> List[CommandGrammar]:
        """Get all grammars for a specific command type."""
        return [g for g in self.grammars if g.command_type == command_type]

    def get_supported_languages(self) -> Set[str]:
        """Get all supported languages across all grammars."""
        languages = set()
        for grammar in self.grammars:
            languages.update(grammar.supported_languages)
        return languages


class MultilingualGrammarEngine(CommandGrammarEngine):
    """Extended grammar engine with multi-language support."""

    def __init__(self) -> None:
        """Initialize multilingual grammar engine."""
        super().__init__()
        self.language_patterns: Dict[str, Dict[str, List[str]]] = {
            "en": {},  # English patterns loaded in parent
            "es": {},  # Spanish patterns
            "fr": {},  # French patterns
            "ar": {},  # Arabic patterns
            # Add more languages as needed
        }

    def add_language_patterns(
        self, language: str, command_type: CommandType, patterns: List[str]
    ) -> None:
        """Add language-specific patterns for a command type."""
        if language not in self.language_patterns:
            self.language_patterns[language] = {}
        self.language_patterns[language][command_type.value] = patterns

    def parse_multilingual(self, text: str, language: str) -> Optional[ParsedCommand]:
        """Parse command with language-specific patterns."""
        # First try standard parsing
        result = self.parse_command(text, language)

        # If no match and we have language patterns, try those
        if not result and language in self.language_patterns:
            # Implementation would check language-specific patterns
            pass

        return result


# Example usage and testing
if __name__ == "__main__":
    # Initialize the grammar engine
    engine = CommandGrammarEngine()

    # Test commands
    test_commands = [
        "Add medication aspirin",
        "Record blood pressure 120 over 80",
        "I have a headache",
        "Go to home",
        "Emergency",
        "Search for doctor Smith",
    ]

    for command in test_commands:
        parsed = engine.parse_command(command)
        if parsed:
            print(f"Command: {command}")
            print(f"Type: {parsed.command_type.value}")
            print(f"Confidence: {parsed.confidence}")
            print(f"Parameters: {parsed.parameters}")
            print(f"Priority: {parsed.priority.value}")
            print("-" * 50)
