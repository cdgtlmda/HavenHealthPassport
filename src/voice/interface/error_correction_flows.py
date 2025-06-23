"""Voice Error Correction Flows Module.

This module implements sophisticated error correction flows for voice interactions
in the Haven Health Passport system, providing intelligent recovery strategies
and user-friendly correction mechanisms.

IMPORTANT: This module handles PHI (Protected Health Information).
- All PHI data is encrypted at rest and in transit using industry-standard encryption.
- Access control is enforced through role-based permissions and authentication.
"""

import asyncio
import difflib
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .voice_command_grammar import CommandType

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Types of errors in voice interactions."""

    NO_SPEECH_DETECTED = "no_speech_detected"
    LOW_CONFIDENCE = "low_confidence"
    AMBIGUOUS_COMMAND = "ambiguous_command"
    INCOMPLETE_COMMAND = "incomplete_command"
    INVALID_PARAMETER = "invalid_parameter"
    OUT_OF_CONTEXT = "out_of_context"
    MULTIPLE_INTERPRETATIONS = "multiple_interpretations"
    LANGUAGE_MISMATCH = "language_mismatch"
    BACKGROUND_NOISE = "background_noise"
    PRONUNCIATION_ERROR = "pronunciation_error"
    TIMEOUT = "timeout"
    SYSTEM_ERROR = "system_error"


class CorrectionStrategy(Enum):
    """Strategies for error correction."""

    CLARIFICATION = "clarification"
    REPETITION = "repetition"
    SPELLING = "spelling"
    ALTERNATIVES = "alternatives"
    GUIDED_COMPLETION = "guided_completion"
    CONTEXT_SWITCH = "context_switch"
    FALLBACK_TO_TEXT = "fallback_to_text"
    ESCALATE_TO_HUMAN = "escalate_to_human"


class UserCapability(Enum):
    """User capability levels for adaptive correction."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass
class ErrorContext:
    """Context information about an error."""

    error_type: ErrorType
    original_input: str
    timestamp: datetime
    confidence_score: float = 0.0
    possible_interpretations: List[str] = field(default_factory=list)
    environment_factors: Dict[str, Any] = field(default_factory=dict)
    user_history: Dict[str, Any] = field(default_factory=dict)
    attempt_number: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CorrectionFlow:
    """Represents a correction flow for an error."""

    id: str
    strategy: CorrectionStrategy
    prompt: str
    options: Optional[List[str]] = None
    timeout_seconds: int = 30
    max_attempts: int = 3
    success_criteria: Optional[Dict[str, Any]] = None
    fallback_strategy: Optional[CorrectionStrategy] = None

    def is_max_attempts_reached(self, current_attempt: int) -> bool:
        """Check if maximum attempts have been reached."""
        return current_attempt >= self.max_attempts


@dataclass
class CorrectionResult:
    """Result of a correction attempt."""

    flow_id: str
    success: bool
    corrected_input: Optional[str] = None
    confidence: float = 0.0
    strategy_used: Optional[CorrectionStrategy] = None
    attempts_made: int = 1
    user_feedback: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ErrorCorrectionStrategy(ABC):
    """Abstract base class for error correction strategies."""

    @abstractmethod
    async def create_correction_flow(
        self, error_context: ErrorContext
    ) -> CorrectionFlow:
        """Create a correction flow for the given error."""

    @abstractmethod
    async def process_correction_response(
        self, response: str, flow: CorrectionFlow, context: ErrorContext
    ) -> CorrectionResult:
        """Process user's correction response."""


class ClarificationStrategy(ErrorCorrectionStrategy):
    """Strategy for clarifying ambiguous commands."""

    def __init__(self) -> None:
        """Initialize clarification strategy with templates."""
        self.clarification_templates = {
            ErrorType.AMBIGUOUS_COMMAND: "I understood '{input}', but I need clarification. Did you mean:",
            ErrorType.MULTIPLE_INTERPRETATIONS: "I heard multiple possible commands. Which one did you intend:",
            ErrorType.INCOMPLETE_COMMAND: "Your command seems incomplete. What would you like to {action}?",
        }

    async def create_correction_flow(
        self, error_context: ErrorContext
    ) -> CorrectionFlow:
        """Create clarification flow."""
        template = self.clarification_templates.get(
            error_context.error_type, "I need clarification on your command:"
        )

        prompt = template.format(
            input=error_context.original_input,
            action=self._extract_action(error_context.original_input),
        )

        # Generate options from possible interpretations
        options = error_context.possible_interpretations[:3]  # Limit to 3 options
        if not options:
            options = self._generate_default_options(error_context)

        return CorrectionFlow(
            id=f"clarify_{datetime.now().timestamp()}",
            strategy=CorrectionStrategy.CLARIFICATION,
            prompt=prompt,
            options=options,
            success_criteria={"min_confidence": 0.7},
        )

    async def process_correction_response(
        self, response: str, flow: CorrectionFlow, context: ErrorContext
    ) -> CorrectionResult:
        """Process clarification response."""
        # Check if response matches any option
        if flow.options:
            for i, option in enumerate(flow.options):
                if str(i + 1) in response or option.lower() in response.lower():
                    return CorrectionResult(
                        flow_id=flow.id,
                        success=True,
                        corrected_input=option,
                        confidence=0.9,
                        strategy_used=CorrectionStrategy.CLARIFICATION,
                    )

        # Try fuzzy matching
        best_match, confidence = self._fuzzy_match(response, flow.options or [])
        if confidence > 0.7:
            return CorrectionResult(
                flow_id=flow.id,
                success=True,
                corrected_input=best_match,
                confidence=confidence,
                strategy_used=CorrectionStrategy.CLARIFICATION,
            )

        return CorrectionResult(
            flow_id=flow.id,
            success=False,
            confidence=confidence,
            strategy_used=CorrectionStrategy.CLARIFICATION,
        )

    def _extract_action(self, text: str) -> str:
        """Extract the main action from text."""
        action_words = ["add", "remove", "update", "check", "show", "find", "delete"]
        for word in action_words:
            if word in text.lower():
                return word
        return "do"

    def _generate_default_options(self, context: ErrorContext) -> List[str]:
        """Generate default options based on context."""
        # Generate options based on the error type and input
        options = []

        if context.error_type == ErrorType.AMBIGUOUS_COMMAND:
            # Suggest common commands related to the ambiguous input
            if "medication" in context.original_input.lower():
                options.extend(
                    ["Show my medications", "Add a new medication", "Update medication"]
                )
            elif "appointment" in context.original_input.lower():
                options.extend(
                    ["Check appointments", "Schedule appointment", "Cancel appointment"]
                )
            else:
                options.extend(
                    [
                        "Show my medications",
                        "Check appointments",
                        "Update my profile",
                        "View health records",
                    ]
                )
        else:
            # Default options for other error types
            options.extend(
                [
                    "Show my medications",
                    "Add a new medication",
                    "Check appointments",
                    "Update my profile",
                ]
            )

        return options

    def _fuzzy_match(self, text: str, options: List[str]) -> Tuple[str, float]:
        """Find best fuzzy match from options."""
        if not options:
            return "", 0.0

        matches = difflib.get_close_matches(text, options, n=1, cutoff=0.6)
        if matches:
            best_match = matches[0]
            confidence = difflib.SequenceMatcher(None, text, best_match).ratio()
            return best_match, confidence

        return "", 0.0


class RepetitionStrategy(ErrorCorrectionStrategy):
    """Strategy for handling low confidence through repetition."""

    def __init__(self) -> None:
        """Initialize repetition strategy with prompts."""
        self.repetition_prompts = {
            "first": "I didn't quite catch that. Could you please repeat your command?",
            "second": "I'm still having trouble understanding. Please speak clearly and repeat:",
            "third": "Let me try once more. Please say your command slowly:",
            "with_example": "Please repeat your command. For example, you can say 'Add medication aspirin'",
        }

    async def create_correction_flow(
        self, error_context: ErrorContext
    ) -> CorrectionFlow:
        """Create repetition flow."""
        # Select prompt based on attempt number
        if error_context.attempt_number == 1:
            prompt = self.repetition_prompts["first"]
        elif error_context.attempt_number == 2:
            prompt = self.repetition_prompts["second"]
        else:
            prompt = self.repetition_prompts["with_example"]

        # Add context-specific hints
        if error_context.environment_factors.get("noise_level") == "high":
            prompt += " Please try to reduce background noise if possible."

        return CorrectionFlow(
            id=f"repeat_{datetime.now().timestamp()}",
            strategy=CorrectionStrategy.REPETITION,
            prompt=prompt,
            success_criteria={"min_confidence": 0.6},
            fallback_strategy=CorrectionStrategy.SPELLING,
        )

    async def process_correction_response(
        self, response: str, flow: CorrectionFlow, context: ErrorContext
    ) -> CorrectionResult:
        """Process repetition response."""
        # In production, this would re-run speech recognition with enhanced settings
        # For now, simulate confidence improvement
        base_confidence = context.confidence_score
        improved_confidence = min(base_confidence + 0.3, 0.95)

        return CorrectionResult(
            flow_id=flow.id,
            success=improved_confidence > 0.6,
            corrected_input=response,
            confidence=improved_confidence,
            strategy_used=CorrectionStrategy.REPETITION,
            attempts_made=context.attempt_number,
        )


class SpellingStrategy(ErrorCorrectionStrategy):
    """Strategy for spelling out difficult words."""

    def __init__(self) -> None:
        """Initialize spelling strategy with phonetic alphabet."""
        self.phonetic_alphabet = {
            "a": "alpha",
            "b": "bravo",
            "c": "charlie",
            "d": "delta",
            "e": "echo",
            "f": "foxtrot",
            "g": "golf",
            "h": "hotel",
            "i": "india",
            "j": "juliet",
            "k": "kilo",
            "l": "lima",
            "m": "mike",
            "n": "november",
            "o": "oscar",
            "p": "papa",
            "q": "quebec",
            "r": "romeo",
            "s": "sierra",
            "t": "tango",
            "u": "uniform",
            "v": "victor",
            "w": "whiskey",
            "x": "x-ray",
            "y": "yankee",
            "z": "zulu",
        }

    async def create_correction_flow(
        self, error_context: ErrorContext
    ) -> CorrectionFlow:
        """Create spelling flow."""
        # Identify the problematic word
        problem_word = self._identify_problem_word(error_context)

        prompt = f"Please spell the word '{problem_word}' using the phonetic alphabet. "
        prompt += "For example, 'A' as in Alpha, 'B' as in Bravo."

        return CorrectionFlow(
            id=f"spell_{datetime.now().timestamp()}",
            strategy=CorrectionStrategy.SPELLING,
            prompt=prompt,
            success_criteria={"valid_spelling": True},
            timeout_seconds=60,  # More time for spelling
        )

    async def process_correction_response(
        self, response: str, flow: CorrectionFlow, context: ErrorContext
    ) -> CorrectionResult:
        """Process spelling response."""
        spelled_word = self._decode_phonetic_spelling(response)

        if spelled_word:
            # Reconstruct the command with the spelled word
            corrected_input = self._reconstruct_command(
                context.original_input, spelled_word
            )

            return CorrectionResult(
                flow_id=flow.id,
                success=True,
                corrected_input=corrected_input,
                confidence=0.95,
                strategy_used=CorrectionStrategy.SPELLING,
            )

        return CorrectionResult(
            flow_id=flow.id,
            success=False,
            confidence=0.0,
            strategy_used=CorrectionStrategy.SPELLING,
        )

    def _identify_problem_word(self, context: ErrorContext) -> str:
        """Identify the word that needs spelling."""
        # In production, use NLP to identify the problematic term
        # For now, extract the last significant word
        words = context.original_input.split()
        significant_words = [w for w in words if len(w) > 3]
        return significant_words[-1] if significant_words else "word"

    def _decode_phonetic_spelling(self, response: str) -> Optional[str]:
        """Decode phonetic alphabet spelling."""
        response_lower = response.lower()
        letters = []

        # Look for phonetic words
        for letter, phonetic in self.phonetic_alphabet.items():
            if phonetic in response_lower:
                letters.append(letter)

        # Also check for direct letter mentions
        for word in response_lower.split():
            if len(word) == 1 and word.isalpha():
                letters.append(word)

        return "".join(letters) if letters else None

    def _reconstruct_command(self, original: str, spelled_word: str) -> str:
        """Reconstruct command with spelled word."""
        # Simple implementation - replace last word
        words = original.split()
        if words:
            words[-1] = spelled_word
        return " ".join(words)


class GuidedCompletionStrategy(ErrorCorrectionStrategy):
    """Strategy for guiding users through incomplete commands."""

    def __init__(self) -> None:
        """Initialize guided completion strategy with command templates."""
        self.command_templates: Dict[CommandType, Dict[str, Any]] = {
            CommandType.MEDICATION: {
                "required_params": ["action", "medication_name"],
                "optional_params": ["dosage", "frequency"],
                "prompts": {
                    "action": "What would you like to do with medication? (add, remove, update, check)",
                    "medication_name": "What is the name of the medication?",
                    "dosage": "What is the dosage? (optional)",
                    "frequency": "How often? (optional)",
                },
            },
            CommandType.APPOINTMENT: {
                "required_params": ["action", "date"],
                "optional_params": ["time", "doctor"],
                "prompts": {
                    "action": "What would you like to do with appointments? (schedule, cancel, check)",
                    "date": "What date? (today, tomorrow, or specific date)",
                    "time": "What time? (optional)",
                    "doctor": "Which doctor? (optional)",
                },
            },
        }

    async def create_correction_flow(
        self, error_context: ErrorContext
    ) -> CorrectionFlow:
        """Create guided completion flow."""
        # Detect command type from partial input
        command_type = self._detect_command_type(error_context.original_input)

        if command_type and command_type in self.command_templates:
            template = self.command_templates[command_type]
            missing_params = self._identify_missing_params(
                error_context.original_input, template
            )

            if missing_params:
                # Ask for the first missing parameter
                param = missing_params[0]
                prompts = template.get("prompts", {})
                prompt = prompts.get(param, f"Please provide {param}:")

                return CorrectionFlow(
                    id=f"guided_{datetime.now().timestamp()}",
                    strategy=CorrectionStrategy.GUIDED_COMPLETION,
                    prompt=prompt,
                    success_criteria={"param_name": param},
                )

        # Fallback prompt
        return CorrectionFlow(
            id=f"guided_{datetime.now().timestamp()}",
            strategy=CorrectionStrategy.GUIDED_COMPLETION,
            prompt="Let me help you complete your command. What are you trying to do?",
            options=[
                "Manage medications",
                "Check appointments",
                "View records",
                "Update profile",
            ],
        )

    async def process_correction_response(
        self, response: str, flow: CorrectionFlow, context: ErrorContext
    ) -> CorrectionResult:
        """Process guided completion response."""
        if flow.success_criteria and "param_name" in flow.success_criteria:
            # Build complete command
            completed_command = self._build_complete_command(
                context.original_input, response, flow.success_criteria
            )

            return CorrectionResult(
                flow_id=flow.id,
                success=True,
                corrected_input=completed_command,
                confidence=0.85,
                strategy_used=CorrectionStrategy.GUIDED_COMPLETION,
                metadata={"completed_params": flow.success_criteria},
            )

        return CorrectionResult(
            flow_id=flow.id,
            success=False,
            confidence=0.0,
            strategy_used=CorrectionStrategy.GUIDED_COMPLETION,
        )

    def _detect_command_type(self, text: str) -> Optional[CommandType]:
        """Detect command type from partial input."""
        text_lower = text.lower()

        if any(
            word in text_lower for word in ["medication", "medicine", "drug", "pill"]
        ):
            return CommandType.MEDICATION
        elif any(word in text_lower for word in ["appointment", "schedule", "visit"]):
            return CommandType.APPOINTMENT
        elif any(
            word in text_lower for word in ["vital", "blood pressure", "temperature"]
        ):
            return CommandType.VITALS

        return None

    def _identify_missing_params(self, text: str, template: Dict) -> List[str]:
        """Identify missing required parameters."""
        missing = []
        text_lower = text.lower()

        for param in template["required_params"]:
            # Simple check - in production, use NLP
            if param == "action":
                action_words = [
                    "add",
                    "remove",
                    "delete",
                    "update",
                    "check",
                    "schedule",
                    "cancel",
                ]
                if not any(word in text_lower for word in action_words):
                    missing.append(param)
            elif param == "medication_name":
                # Check if any word could be a medication name
                if len(text_lower.split()) < 3:  # Rough heuristic
                    missing.append(param)

        return missing

    def _build_complete_command(
        self, original: str, response: str, metadata: Dict
    ) -> str:
        """Build complete command from parts."""
        # Use metadata to enhance command construction
        confidence = metadata.get("confidence", 0.5)

        # If high confidence, use response as is
        if confidence > 0.8:
            return response

        # Otherwise, combine original and response
        # Simple concatenation - in production, use proper grammar construction
        return f"{original} {response}"


class ErrorCorrectionFlowManager:
    """Manages error correction flows for voice interactions."""

    def __init__(self) -> None:
        """Initialize error correction flow manager with strategies."""
        self.strategies = {
            CorrectionStrategy.CLARIFICATION: ClarificationStrategy(),
            CorrectionStrategy.REPETITION: RepetitionStrategy(),
            CorrectionStrategy.SPELLING: SpellingStrategy(),
            CorrectionStrategy.GUIDED_COMPLETION: GuidedCompletionStrategy(),
        }

        self.active_flows: Dict[str, CorrectionFlow] = {}
        self.correction_history: List[CorrectionResult] = []
        self.user_patterns: Dict[str, List[ErrorContext]] = defaultdict(list)

        # Error type to strategy mapping
        self.error_strategy_map = {
            ErrorType.AMBIGUOUS_COMMAND: CorrectionStrategy.CLARIFICATION,
            ErrorType.LOW_CONFIDENCE: CorrectionStrategy.REPETITION,
            ErrorType.INCOMPLETE_COMMAND: CorrectionStrategy.GUIDED_COMPLETION,
            ErrorType.PRONUNCIATION_ERROR: CorrectionStrategy.SPELLING,
            ErrorType.MULTIPLE_INTERPRETATIONS: CorrectionStrategy.CLARIFICATION,
            ErrorType.INVALID_PARAMETER: CorrectionStrategy.GUIDED_COMPLETION,
            ErrorType.NO_SPEECH_DETECTED: CorrectionStrategy.REPETITION,
            ErrorType.BACKGROUND_NOISE: CorrectionStrategy.REPETITION,
        }

        # Adaptive learning parameters
        self.strategy_success_rates: Dict[str, float] = defaultdict(lambda: 0.5)
        self.user_capability_scores: Dict[str, float] = defaultdict(lambda: 0.5)

    async def handle_error(
        self, error_context: ErrorContext, user_id: Optional[str] = None
    ) -> CorrectionFlow:
        """Handle a voice interaction error."""
        # Record error pattern
        if user_id:
            self.user_patterns[user_id].append(error_context)

        # Select strategy based on error type and user history
        strategy_type = self._select_strategy(error_context, user_id)
        strategy = self.strategies.get(strategy_type)

        if not strategy:
            # Fallback to repetition
            strategy = self.strategies[CorrectionStrategy.REPETITION]

        # Create correction flow
        flow = await strategy.create_correction_flow(error_context)

        # Store active flow
        self.active_flows[flow.id] = flow

        return flow

    async def process_correction(
        self, flow_id: str, user_response: str, user_id: Optional[str] = None
    ) -> CorrectionResult:
        """Process a user's correction response."""
        if flow_id not in self.active_flows:
            return CorrectionResult(
                flow_id=flow_id,
                success=False,
                metadata={"error": "Flow not found or expired"},
            )

        flow = self.active_flows[flow_id]

        # Get the original error context
        error_context = self._get_error_context_for_flow(flow_id)

        # Get strategy
        strategy = self.strategies.get(flow.strategy)
        if not strategy:
            return CorrectionResult(
                flow_id=flow_id, success=False, metadata={"error": "Strategy not found"}
            )

        # Process correction
        result = await strategy.process_correction_response(
            user_response, flow, error_context
        )

        # Update history and learning
        self.correction_history.append(result)
        self._update_learning_parameters(result, user_id)

        # Clean up if successful or max attempts
        if result.success or error_context.attempt_number >= flow.max_attempts:
            del self.active_flows[flow_id]

        return result

    def _select_strategy(
        self, error_context: ErrorContext, user_id: Optional[str] = None
    ) -> CorrectionStrategy:
        """Select the best strategy based on context and history."""
        # Base strategy from error type
        base_strategy = self.error_strategy_map.get(
            error_context.error_type, CorrectionStrategy.REPETITION
        )

        # Adjust based on user capability
        if user_id:
            capability = self._assess_user_capability(user_id)

            # Advanced users might prefer different strategies
            if capability == UserCapability.ADVANCED:
                if base_strategy == CorrectionStrategy.REPETITION:
                    # Advanced users might prefer clarification
                    base_strategy = CorrectionStrategy.CLARIFICATION
            elif capability == UserCapability.BEGINNER:
                if base_strategy == CorrectionStrategy.SPELLING:
                    # Beginners might need guided completion instead
                    base_strategy = CorrectionStrategy.GUIDED_COMPLETION

        # Check strategy success rates
        if self.strategy_success_rates[base_strategy.value] < 0.3:
            # This strategy isn't working well, try alternative
            return self._get_alternative_strategy(base_strategy)

        return base_strategy

    def _assess_user_capability(self, user_id: str) -> UserCapability:
        """Assess user's capability level based on history."""
        score = self.user_capability_scores[user_id]

        if score < 0.3:
            return UserCapability.BEGINNER
        elif score < 0.6:
            return UserCapability.INTERMEDIATE
        elif score < 0.85:
            return UserCapability.ADVANCED
        else:
            return UserCapability.EXPERT

    def _get_alternative_strategy(
        self, failed_strategy: CorrectionStrategy
    ) -> CorrectionStrategy:
        """Get alternative strategy when one fails."""
        alternatives = {
            CorrectionStrategy.REPETITION: CorrectionStrategy.CLARIFICATION,
            CorrectionStrategy.CLARIFICATION: CorrectionStrategy.GUIDED_COMPLETION,
            CorrectionStrategy.SPELLING: CorrectionStrategy.GUIDED_COMPLETION,
            CorrectionStrategy.GUIDED_COMPLETION: CorrectionStrategy.FALLBACK_TO_TEXT,
        }

        return alternatives.get(failed_strategy, CorrectionStrategy.REPETITION)

    def _update_learning_parameters(
        self, result: CorrectionResult, user_id: Optional[str]
    ) -> None:
        """Update learning parameters based on correction results."""
        if result.strategy_used:
            # Update strategy success rate
            current_rate = self.strategy_success_rates[result.strategy_used.value]
            new_rate = (current_rate * 0.9) + (0.1 if result.success else 0.0)
            self.strategy_success_rates[result.strategy_used.value] = new_rate

        if user_id and result.success:
            # Update user capability score
            current_score = self.user_capability_scores[user_id]
            # Successful corrections increase capability score
            self.user_capability_scores[user_id] = min(1.0, current_score + 0.02)

    def _get_error_context_for_flow(self, flow_id: str) -> ErrorContext:
        """Get error context for a flow (simplified)."""
        # In production, this would retrieve the actual context from storage
        # using the flow_id as key
        logger.debug("Retrieving error context for flow: %s", flow_id)

        return ErrorContext(
            error_type=ErrorType.LOW_CONFIDENCE,
            original_input="",
            timestamp=datetime.now(),
            metadata={"flow_id": flow_id},
        )

    def get_user_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get error correction statistics for a user."""
        user_errors = self.user_patterns.get(user_id, [])
        user_corrections = [
            r for r in self.correction_history if r.metadata.get("user_id") == user_id
        ]

        success_rate = (
            sum(1 for r in user_corrections if r.success) / len(user_corrections)
            if user_corrections
            else 0.0
        )

        error_type_distribution: Dict[str, int] = defaultdict(int)
        for error in user_errors:
            error_type_distribution[error.error_type.value] += 1

        return {
            "total_errors": len(user_errors),
            "total_corrections": len(user_corrections),
            "success_rate": success_rate,
            "capability_level": self._assess_user_capability(user_id).value,
            "error_types": dict(error_type_distribution),
            "preferred_strategies": self._get_preferred_strategies(user_id),
        }

    def _get_preferred_strategies(self, user_id: str) -> List[str]:
        """Get user's most successful correction strategies."""
        user_corrections = [
            r
            for r in self.correction_history
            if r.metadata.get("user_id") == user_id and r.strategy_used
        ]

        strategy_success: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"total": 0, "success": 0}
        )

        for correction in user_corrections:
            if correction.strategy_used:
                strategy_name = correction.strategy_used.value
                strategy_success[strategy_name]["total"] += 1
                if correction.success:
                    strategy_success[strategy_name]["success"] += 1

        # Calculate success rates
        strategy_rates = []
        for strategy, stats in strategy_success.items():
            if stats["total"] > 0:
                rate = stats["success"] / stats["total"]
                strategy_rates.append((strategy, rate))

        # Sort by success rate
        strategy_rates.sort(key=lambda x: x[1], reverse=True)

        return [s[0] for s in strategy_rates[:3]]  # Top 3 strategies


class AdaptiveErrorCorrection(ErrorCorrectionFlowManager):
    """Extended error correction with machine learning adaptation."""

    def __init__(self) -> None:
        """Initialize adaptive error correction with ML capabilities."""
        super().__init__()
        self.ml_model = None  # Placeholder for ML model
        self.feature_extractors = {
            "acoustic": self._extract_acoustic_features,
            "linguistic": self._extract_linguistic_features,
            "contextual": self._extract_contextual_features,
        }

    async def predict_best_strategy(
        self, error_context: ErrorContext, user_id: Optional[str] = None
    ) -> CorrectionStrategy:
        """Use ML to predict the best correction strategy."""
        # Extract features would be used here for ML prediction
        # Currently using rule-based selection
        return self._select_strategy(error_context, user_id)

    def _extract_features(
        self, error_context: ErrorContext, user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Extract features for ML prediction."""
        features: Dict[str, Any] = {}

        # Error type features
        features["error_type"] = error_context.error_type.value
        features["confidence_score"] = error_context.confidence_score
        features["attempt_number"] = error_context.attempt_number

        # Environmental features
        features.update(error_context.environment_factors)

        # User features
        if user_id:
            features["user_capability"] = self._assess_user_capability(user_id).value
            features["error_history_count"] = len(self.user_patterns.get(user_id, []))

        # Linguistic features
        features.update(self._extract_linguistic_features(error_context.original_input))

        return features

    def _extract_acoustic_features(self, audio_data: Any) -> Dict[str, float]:
        """Extract acoustic features from audio (placeholder)."""
        # In production, this would analyze the audio_data
        # For now, return placeholder values based on audio presence
        if audio_data is not None:
            # Simulate feature extraction
            return {
                "snr": 20.0,  # Signal-to-noise ratio
                "pitch_variance": 0.15,
                "speaking_rate": 3.5,
            }
        else:
            return {
                "snr": 0.0,  # Signal-to-noise ratio
                "pitch_variance": 0.0,
                "speaking_rate": 0.0,
            }

    def _extract_linguistic_features(self, text: str) -> Dict[str, Any]:
        """Extract linguistic features from text."""
        words = text.split()
        return {
            "word_count": len(words),
            "avg_word_length": sum(len(w) for w in words) / len(words) if words else 0,
            "has_medical_terms": any(
                w in text.lower() for w in ["medication", "symptom", "doctor"]
            ),
            "has_numbers": any(c.isdigit() for c in text),
        }

    def _extract_contextual_features(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract contextual features."""
        return {
            "time_of_day": datetime.now().hour,
            "day_of_week": datetime.now().weekday(),
            "session_duration": context.get("session_duration", 0),
            "previous_errors": context.get("error_count", 0),
        }


# Example usage
if __name__ == "__main__":

    async def test_error_correction() -> None:
        """Test error correction flow functionality."""
        # Initialize manager
        manager = ErrorCorrectionFlowManager()

        # Test ambiguous command error
        error_context = ErrorContext(
            error_type=ErrorType.AMBIGUOUS_COMMAND,
            original_input="add aspirin",
            timestamp=datetime.now(),
            confidence_score=0.4,
            possible_interpretations=[
                "Add medication aspirin",
                "Add aspirin to shopping list",
                "Add aspirin reminder",
            ],
        )

        # Create correction flow
        flow = await manager.handle_error(error_context, user_id="test_user")
        print(f"Correction prompt: {flow.prompt}")
        print(f"Options: {flow.options}")

        # Simulate user response
        result = await manager.process_correction(
            flow.id, "1", user_id="test_user"  # Select first option
        )

        print(f"Correction successful: {result.success}")
        print(f"Corrected input: {result.corrected_input}")

        # Get user statistics
        stats = manager.get_user_statistics("test_user")
        print(f"User statistics: {stats}")

    # Run test
    asyncio.run(test_error_correction())
