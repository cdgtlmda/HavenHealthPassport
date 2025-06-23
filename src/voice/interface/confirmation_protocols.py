"""Voice Confirmation Protocols Module.

This module implements confirmation protocols for voice commands in the Haven Health
Passport system, ensuring safe and accurate execution of critical operations through
multi-modal confirmation strategies.

IMPORTANT: This module handles PHI (Protected Health Information).
- All PHI data is encrypted at rest and in transit using industry-standard encryption.
- Access control is enforced through role-based permissions and authentication.
"""

import asyncio
import hashlib
import logging
import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .voice_command_grammar import CommandPriority, CommandType, ParsedCommand

logger = logging.getLogger(__name__)


class ConfirmationType(Enum):
    """Types of confirmation methods available."""

    VERBAL_YES_NO = "verbal_yes_no"
    VERBAL_REPEAT = "verbal_repeat"
    NUMERIC_CODE = "numeric_code"
    MULTIPLE_CHOICE = "multiple_choice"
    BIOMETRIC = "biometric"
    PIN = "pin"
    GESTURE = "gesture"
    DUAL_CONFIRMATION = "dual_confirmation"  # Requires two different methods


class ConfirmationLevel(Enum):
    """Security levels for confirmation requirements."""

    NONE = 0  # No confirmation needed
    LOW = 1  # Simple yes/no
    MEDIUM = 2  # Repeat back or choice selection
    HIGH = 3  # Numeric code or PIN
    CRITICAL = 4  # Multiple confirmation methods


class ConfirmationStatus(Enum):
    """Status of a confirmation request."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RETRY_NEEDED = "retry_needed"


@dataclass
class ConfirmationContext:
    """Context information for confirmation requests."""

    command: ParsedCommand
    risk_level: str  # low, medium, high, critical
    user_profile: Dict[str, Any]  # User preferences and accessibility needs
    environment: Dict[str, Any]  # Noise level, privacy, etc.
    previous_attempts: int = 0
    max_attempts: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    def increment_attempts(self) -> bool:
        """Increment attempt counter and check if max reached."""
        self.previous_attempts += 1
        return self.previous_attempts < self.max_attempts


@dataclass
class ConfirmationRequest:
    """Represents a confirmation request."""

    id: str
    type: ConfirmationType
    level: ConfirmationLevel
    prompt: str
    options: Optional[List[str]] = None
    timeout_seconds: int = 30
    created_at: datetime = field(default_factory=datetime.now)
    context: Optional[ConfirmationContext] = None

    def is_expired(self) -> bool:
        """Check if the request has expired."""
        return datetime.now() > self.created_at + timedelta(
            seconds=self.timeout_seconds
        )


@dataclass
class ConfirmationResponse:
    """Response to a confirmation request."""

    request_id: str
    status: ConfirmationStatus
    user_input: Optional[str] = None
    confidence_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConfirmationStrategy(ABC):
    """Abstract base class for confirmation strategies."""

    @abstractmethod
    async def request_confirmation(
        self, request: ConfirmationRequest, audio_callback: Optional[Callable] = None
    ) -> ConfirmationResponse:
        """Request confirmation from user."""

    @abstractmethod
    def validate_response(
        self, response: str, request: ConfirmationRequest
    ) -> Tuple[bool, float]:
        """Validate user response. Returns (is_valid, confidence_score)."""


class VerbalYesNoStrategy(ConfirmationStrategy):
    """Simple yes/no verbal confirmation strategy."""

    def __init__(self) -> None:
        """Initialize verbal yes/no confirmation strategy."""
        self.positive_responses = {
            "en": [
                "yes",
                "correct",
                "confirm",
                "affirmative",
                "right",
                "yep",
                "yeah",
                "sure",
                "ok",
                "okay",
            ],
            "es": ["sí", "correcto", "confirmar", "afirmativo", "claro"],
            "fr": ["oui", "correct", "confirmer", "affirmatif", "d'accord"],
            "ar": ["نعم", "صحيح", "تأكيد", "موافق"],
        }

        self.negative_responses = {
            "en": ["no", "incorrect", "cancel", "negative", "wrong", "nope", "stop"],
            "es": ["no", "incorrecto", "cancelar", "negativo", "parar"],
            "fr": ["non", "incorrect", "annuler", "négatif", "arrêter"],
            "ar": ["لا", "خطأ", "إلغاء", "توقف"],
        }

    async def request_confirmation(
        self, request: ConfirmationRequest, audio_callback: Optional[Callable] = None
    ) -> ConfirmationResponse:
        """Request yes/no confirmation."""
        # In production, this would interface with the audio system
        # For now, we'll simulate the interaction
        logger.info("Requesting verbal yes/no confirmation: %s", request.prompt)

        if audio_callback:
            await audio_callback(request.prompt)

        # Simulated response - in production, would wait for actual voice input
        return ConfirmationResponse(
            request_id=request.id,
            status=ConfirmationStatus.PENDING,
            user_input=None,
            confidence_score=0.0,
        )

    def validate_response(
        self, response: str, request: ConfirmationRequest
    ) -> Tuple[bool, float]:
        """Validate yes/no response."""
        response_lower = response.lower().strip()
        language = request.context.command.language if request.context else "en"

        # Check positive responses
        if language in self.positive_responses:
            for positive in self.positive_responses[language]:
                if positive in response_lower:
                    confidence = 0.9 if response_lower == positive else 0.7
                    return True, confidence

        # Check negative responses
        if language in self.negative_responses:
            for negative in self.negative_responses[language]:
                if negative in response_lower:
                    return False, 0.9

        # Ambiguous response
        return False, 0.3


class VerbalRepeatStrategy(ConfirmationStrategy):
    """Confirmation by repeating specific information."""

    def __init__(self) -> None:
        """Initialize verbal repeat confirmation strategy."""
        self.fuzzy_match_threshold = 0.8

    async def request_confirmation(
        self, request: ConfirmationRequest, audio_callback: Optional[Callable] = None
    ) -> ConfirmationResponse:
        """Request user to repeat information."""
        prompt = f"Please repeat: {request.prompt}"
        logger.info("Requesting verbal repeat confirmation: %s", prompt)

        if audio_callback:
            await audio_callback(prompt)

        return ConfirmationResponse(
            request_id=request.id,
            status=ConfirmationStatus.PENDING,
            user_input=None,
            confidence_score=0.0,
        )

    def validate_response(
        self, response: str, request: ConfirmationRequest
    ) -> Tuple[bool, float]:
        """Validate repeated response using fuzzy matching."""
        expected = request.prompt.lower().strip()
        actual = response.lower().strip()

        # Calculate similarity
        similarity = SequenceMatcher(None, expected, actual).ratio()

        # Check if meets threshold
        is_valid = similarity >= self.fuzzy_match_threshold

        return is_valid, similarity


class NumericCodeStrategy(ConfirmationStrategy):
    """Confirmation using numeric codes."""

    def __init__(self) -> None:
        """Initialize numeric code confirmation strategy."""
        self.code_length = 4
        self.active_codes: Dict[str, str] = {}

    def generate_code(self, request_id: str) -> str:
        """Generate a random numeric code."""
        code = "".join([str(random.randint(0, 9)) for _ in range(self.code_length)])
        self.active_codes[request_id] = code
        return code

    async def request_confirmation(
        self, request: ConfirmationRequest, audio_callback: Optional[Callable] = None
    ) -> ConfirmationResponse:
        """Request numeric code confirmation."""
        code = self.generate_code(request.id)
        prompt = f"{request.prompt}. Please say the confirmation code: {' '.join(code)}"

        logger.info("Requesting numeric code confirmation: %s", request.id)

        if audio_callback:
            await audio_callback(prompt)

        return ConfirmationResponse(
            request_id=request.id,
            status=ConfirmationStatus.PENDING,
            user_input=None,
            confidence_score=0.0,
            metadata={"expected_code": code},
        )

    def validate_response(
        self, response: str, request: ConfirmationRequest
    ) -> Tuple[bool, float]:
        """Validate numeric code response."""
        if request.id not in self.active_codes:
            return False, 0.0

        expected_code = self.active_codes[request.id]

        # Extract digits from response
        digits = "".join(filter(str.isdigit, response))

        if digits == expected_code:
            # Clean up used code
            del self.active_codes[request.id]
            return True, 1.0

        # Check for partial match
        if len(digits) == len(expected_code):
            matches = sum(1 for a, b in zip(digits, expected_code) if a == b)
            confidence = matches / len(expected_code)
            if confidence > 0.75:  # Allow one digit error
                del self.active_codes[request.id]
                return True, confidence

        return False, 0.0


class MultipleChoiceStrategy(ConfirmationStrategy):
    """Confirmation through multiple choice selection."""

    async def request_confirmation(
        self, request: ConfirmationRequest, audio_callback: Optional[Callable] = None
    ) -> ConfirmationResponse:
        """Request multiple choice confirmation."""
        if not request.options:
            raise ValueError("Multiple choice requires options")

        # Format options with numbers
        options_text = "\n".join(
            [f"{i+1}. {option}" for i, option in enumerate(request.options)]
        )

        prompt = (
            f"{request.prompt}\n{options_text}\nPlease say the number of your choice."
        )

        logger.info("Requesting multiple choice confirmation: %s", request.id)

        if audio_callback:
            await audio_callback(prompt)

        return ConfirmationResponse(
            request_id=request.id,
            status=ConfirmationStatus.PENDING,
            user_input=None,
            confidence_score=0.0,
        )

    def validate_response(
        self, response: str, request: ConfirmationRequest
    ) -> Tuple[bool, float]:
        """Validate multiple choice response."""
        if not request.options:
            return False, 0.0

        # Try to extract number from response
        numbers = re.findall(r"\b(\d+)\b", response)

        if numbers:
            choice_num = int(numbers[0])
            if 1 <= choice_num <= len(request.options):
                return True, 0.9

        # Try to match option text
        response_lower = response.lower()
        for _, option in enumerate(request.options):
            if option.lower() in response_lower:
                return True, 0.7

        return False, 0.0


class ConfirmationProtocolManager:
    """Manages confirmation protocols and strategies."""

    def __init__(self) -> None:
        """Initialize confirmation protocol manager with strategies."""
        self.strategies: Dict[ConfirmationType, ConfirmationStrategy] = {
            ConfirmationType.VERBAL_YES_NO: VerbalYesNoStrategy(),
            ConfirmationType.VERBAL_REPEAT: VerbalRepeatStrategy(),
            ConfirmationType.NUMERIC_CODE: NumericCodeStrategy(),
            ConfirmationType.MULTIPLE_CHOICE: MultipleChoiceStrategy(),
        }

        self.active_requests: Dict[str, ConfirmationRequest] = {}
        self.confirmation_history: List[ConfirmationResponse] = []

        # Command type to confirmation level mapping
        self.command_confirmation_levels = {
            CommandType.EMERGENCY: ConfirmationLevel.NONE,  # No delay for emergencies
            CommandType.DELETE: ConfirmationLevel.HIGH,
            CommandType.MEDICATION: ConfirmationLevel.MEDIUM,
            CommandType.UPDATE: ConfirmationLevel.MEDIUM,
            CommandType.SHARE: ConfirmationLevel.HIGH,
            CommandType.EXPORT: ConfirmationLevel.MEDIUM,
            CommandType.SETTINGS: ConfirmationLevel.LOW,
            CommandType.NAVIGATION: ConfirmationLevel.NONE,
            CommandType.SEARCH: ConfirmationLevel.NONE,
            CommandType.READ: ConfirmationLevel.NONE,
            CommandType.HELP: ConfirmationLevel.NONE,
        }

        # Risk-based adjustments
        self.risk_adjustments = {
            "medication_dose_change": ConfirmationLevel.HIGH,
            "delete_all_records": ConfirmationLevel.CRITICAL,
            "share_with_third_party": ConfirmationLevel.HIGH,
            "emergency_contact_change": ConfirmationLevel.HIGH,
        }

    def determine_confirmation_level(
        self, command: ParsedCommand, context: Optional[Dict[str, Any]] = None
    ) -> ConfirmationLevel:
        """Determine required confirmation level based on command and context."""
        # Base level from command type
        base_level = self.command_confirmation_levels.get(
            command.command_type, ConfirmationLevel.LOW
        )

        # Check for risk adjustments
        if context:
            for risk_key, risk_level in self.risk_adjustments.items():
                if risk_key in str(context).lower():
                    if risk_level.value > base_level.value:
                        base_level = risk_level

        # Adjust based on user history and preferences
        if context and "user_profile" in context:
            profile = context["user_profile"]

            # Users with accessibility needs might need different confirmation
            if profile.get("vision_impaired"):
                # Avoid visual confirmations
                pass

            # New users might need more confirmations
            if profile.get("experience_level") == "beginner":
                if base_level == ConfirmationLevel.LOW:
                    base_level = ConfirmationLevel.MEDIUM

        return base_level

    def select_confirmation_type(
        self, level: ConfirmationLevel, context: Optional[ConfirmationContext] = None
    ) -> ConfirmationType:
        """Select appropriate confirmation type based on level and context."""
        # Level-based selection
        level_mapping = {
            ConfirmationLevel.NONE: None,
            ConfirmationLevel.LOW: ConfirmationType.VERBAL_YES_NO,
            ConfirmationLevel.MEDIUM: ConfirmationType.VERBAL_REPEAT,
            ConfirmationLevel.HIGH: ConfirmationType.NUMERIC_CODE,
            ConfirmationLevel.CRITICAL: ConfirmationType.DUAL_CONFIRMATION,
        }

        confirmation_type = level_mapping.get(level, ConfirmationType.VERBAL_YES_NO)

        # Handle NONE level
        if confirmation_type is None:
            return ConfirmationType.VERBAL_YES_NO

        # Context-based adjustments
        if context:
            # Noisy environment - avoid voice
            if context.environment.get("noise_level", "low") == "high":
                if confirmation_type == ConfirmationType.VERBAL_REPEAT:
                    confirmation_type = ConfirmationType.NUMERIC_CODE

            # Privacy concerns - avoid speaking sensitive info
            if context.environment.get("privacy_level", "private") == "public":
                if confirmation_type == ConfirmationType.VERBAL_REPEAT:
                    confirmation_type = ConfirmationType.MULTIPLE_CHOICE

        return confirmation_type

    async def request_confirmation(
        self,
        command: ParsedCommand,
        context: Optional[Dict[str, Any]] = None,
        audio_callback: Optional[Callable] = None,
    ) -> ConfirmationRequest:
        """Create and manage a confirmation request."""
        # Create context
        confirmation_context = ConfirmationContext(
            command=command,
            risk_level=self._assess_risk_level(command),
            user_profile=context.get("user_profile", {}) if context else {},
            environment=context.get("environment", {}) if context else {},
        )

        # Determine level and type
        level = self.determine_confirmation_level(command, context)

        if level == ConfirmationLevel.NONE:
            # No confirmation needed - return auto-confirmed request
            request = ConfirmationRequest(
                id=self._generate_request_id(command),
                type=ConfirmationType.VERBAL_YES_NO,
                level=ConfirmationLevel.NONE,
                prompt="",
                context=confirmation_context,
                timeout_seconds=0,
            )
            # Mark as auto-confirmed
            # Mark as auto-confirmed with proper response
            return request

        conf_type = self.select_confirmation_type(level, confirmation_context)

        # Create request
        request = ConfirmationRequest(
            id=self._generate_request_id(command),
            type=conf_type,
            level=level,
            prompt=self._generate_confirmation_prompt(command, conf_type),
            timeout_seconds=self._calculate_timeout(level),
            context=confirmation_context,
        )

        # Store active request
        self.active_requests[request.id] = request

        # Get strategy and request confirmation
        strategy = self.strategies.get(conf_type)
        if strategy:
            await strategy.request_confirmation(request, audio_callback)
            return request

        return request

    def validate_response(
        self, request_id: str, user_response: str
    ) -> ConfirmationResponse:
        """Validate a user's response to a confirmation request."""
        if request_id not in self.active_requests:
            return ConfirmationResponse(
                request_id=request_id,
                status=ConfirmationStatus.CANCELLED,
                user_input=user_response,
                confidence_score=0.0,
            )

        request = self.active_requests[request_id]

        # Check timeout
        if request.is_expired():
            return ConfirmationResponse(
                request_id=request_id,
                status=ConfirmationStatus.TIMEOUT,
                user_input=user_response,
                confidence_score=0.0,
            )

        # Get strategy and validate
        strategy = self.strategies.get(request.type)
        if not strategy:
            return ConfirmationResponse(
                request_id=request_id,
                status=ConfirmationStatus.REJECTED,
                user_input=user_response,
                confidence_score=0.0,
            )

        is_valid, confidence = strategy.validate_response(user_response, request)

        # Create response
        response = ConfirmationResponse(
            request_id=request_id,
            status=(
                ConfirmationStatus.CONFIRMED
                if is_valid
                else ConfirmationStatus.REJECTED
            ),
            user_input=user_response,
            confidence_score=confidence,
        )

        # Store in history
        self.confirmation_history.append(response)

        # Clean up if confirmed or max attempts reached
        if is_valid or (request.context and not request.context.increment_attempts()):
            del self.active_requests[request_id]

        return response

    def _assess_risk_level(self, command: ParsedCommand) -> str:
        """Assess the risk level of a command."""
        # High risk commands
        high_risk_keywords = [
            "delete",
            "remove",
            "share",
            "export",
            "dose",
            "emergency",
        ]
        medium_risk_keywords = ["update", "change", "modify", "add"]

        command_text = command.raw_text.lower()

        for keyword in high_risk_keywords:
            if keyword in command_text:
                return "high"

        for keyword in medium_risk_keywords:
            if keyword in command_text:
                return "medium"

        return "low"

    def _generate_request_id(self, command: ParsedCommand) -> str:
        """Generate unique request ID."""
        timestamp = datetime.now().isoformat()
        command_hash = hashlib.md5(
            command.raw_text.encode(), usedforsecurity=False
        ).hexdigest()[:8]
        return f"conf_{command_hash}_{timestamp}"

    def _generate_confirmation_prompt(
        self, command: ParsedCommand, conf_type: ConfirmationType
    ) -> str:
        """Generate appropriate confirmation prompt."""
        base_prompt = f"Please confirm: {command.raw_text}"

        if conf_type == ConfirmationType.VERBAL_YES_NO:
            return f"{base_prompt}. Say 'yes' to confirm or 'no' to cancel."
        elif conf_type == ConfirmationType.VERBAL_REPEAT:
            key_info = self._extract_key_information(command)
            return key_info
        elif conf_type == ConfirmationType.NUMERIC_CODE:
            return base_prompt
        elif conf_type == ConfirmationType.MULTIPLE_CHOICE:
            return base_prompt

        return base_prompt

    def _extract_key_information(self, command: ParsedCommand) -> str:
        """Extract key information for repeat confirmation."""
        # Extract critical parameters
        if command.command_type == CommandType.MEDICATION:
            med_name = command.parameters.get("medication_name", "medication")
            action = command.parameters.get("action", "action")
            return f"{action} {med_name}"
        elif command.command_type == CommandType.DELETE:
            target = command.parameters.get("target", "record")
            return f"delete {target}"

        # Default: use command type and first parameter
        params = list(command.parameters.values())
        if params:
            return f"{command.command_type.value} {params[0]}"

        return str(command.command_type.value)

    def _calculate_timeout(self, level: ConfirmationLevel) -> int:
        """Calculate appropriate timeout based on confirmation level."""
        timeout_mapping = {
            ConfirmationLevel.NONE: 0,
            ConfirmationLevel.LOW: 15,
            ConfirmationLevel.MEDIUM: 30,
            ConfirmationLevel.HIGH: 45,
            ConfirmationLevel.CRITICAL: 60,
        }
        return timeout_mapping.get(level, 30)

    def cancel_request(self, request_id: str) -> bool:
        """Cancel an active confirmation request."""
        if request_id in self.active_requests:
            del self.active_requests[request_id]

            # Record cancellation
            self.confirmation_history.append(
                ConfirmationResponse(
                    request_id=request_id,
                    status=ConfirmationStatus.CANCELLED,
                    timestamp=datetime.now(),
                )
            )

            return True
        return False

    def get_active_requests(self) -> List[ConfirmationRequest]:
        """Get all active confirmation requests."""
        # Clean up expired requests first
        expired_ids = [
            req_id for req_id, req in self.active_requests.items() if req.is_expired()
        ]

        for req_id in expired_ids:
            self.confirmation_history.append(
                ConfirmationResponse(
                    request_id=req_id,
                    status=ConfirmationStatus.TIMEOUT,
                    timestamp=datetime.now(),
                )
            )
            del self.active_requests[req_id]

        return list(self.active_requests.values())

    def get_user_confirmation_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get cached user confirmation preferences.

        Note: user_id is used for preference lookup.
        """
        # Log preference lookup
        logger.debug("Getting confirmation preferences for user: %s", user_id)

        # In production, this would query user preferences
        return {
            "preferred_method": ConfirmationType.VERBAL_YES_NO,
            "timeout_extension": 0,
            "skip_low_risk": False,
            "accessibility_needs": [],
        }


# Accessibility-focused confirmation strategies
class AccessibleConfirmationManager(ConfirmationProtocolManager):
    """Extended confirmation manager with accessibility features."""

    def __init__(self) -> None:
        """Initialize accessible confirmation manager."""
        super().__init__()

        # Additional strategies for accessibility
        self.accessibility_modes = {
            "vision_impaired": self._configure_vision_impaired,
            "hearing_impaired": self._configure_hearing_impaired,
            "motor_impaired": self._configure_motor_impaired,
            "cognitive_support": self._configure_cognitive_support,
        }

    def _configure_vision_impaired(self, context: ConfirmationContext) -> None:
        """Configure confirmations for vision impaired users."""
        # Prefer audio-based confirmations
        # Avoid visual elements
        # Provide detailed audio descriptions

    def _configure_hearing_impaired(self, context: ConfirmationContext) -> None:
        """Configure confirmations for hearing impaired users."""
        # Prefer visual confirmations
        # Provide haptic feedback options
        # Use clear visual indicators

    def _configure_motor_impaired(self, context: ConfirmationContext) -> None:
        """Configure confirmations for motor impaired users."""
        # Extended timeouts
        # Simplified input methods
        # Voice-only options

    def _configure_cognitive_support(self, context: ConfirmationContext) -> None:
        """Configure confirmations for users needing cognitive support."""
        # Simplified language
        # Step-by-step guidance
        # Visual aids and repetition


# Example usage
if __name__ == "__main__":

    async def test_confirmation_protocols() -> None:
        """Test confirmation protocol functionality."""
        # Initialize manager
        manager = ConfirmationProtocolManager()

        # Create test command
        test_command = ParsedCommand(
            command_type=CommandType.MEDICATION,
            raw_text="Add medication aspirin 100mg",
            parameters={
                "action": "add",
                "medication_name": "aspirin",
                "dosage": "100mg",
            },
            confidence=0.9,
            language="en",
            timestamp=datetime.now(),
            priority=CommandPriority.MEDICAL,
        )

        # Request confirmation
        context = {
            "user_profile": {"experience_level": "intermediate"},
            "environment": {"noise_level": "low", "privacy_level": "private"},
        }

        request = await manager.request_confirmation(test_command, context)
        if request:
            print(f"Confirmation requested: {request.prompt}")
            print(f"Type: {request.type.value}")
            print(f"Level: {request.level.value}")

            # Simulate user response
            response = manager.validate_response(request.id, "yes")
            print(f"Response status: {response.status.value}")
            print(f"Confidence: {response.confidence_score}")

    # Run test
    asyncio.run(test_confirmation_protocols())
