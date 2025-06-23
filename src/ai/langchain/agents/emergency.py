"""Emergency Response Agent.

Specialized agent for handling medical emergencies.
Provides immediate guidance and coordinates emergency responses.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from pydantic import BaseModel, Field

from .base import AgentConfig, BaseHealthAgent, MedicalContext
from .tools import get_tools_for_agent

logger = logging.getLogger(__name__)


class EmergencyRequest(BaseModel):
    """Input model for emergency response."""

    emergency_type: str = Field(..., description="Type of emergency")
    symptoms: List[str] = Field(..., description="Observed symptoms")
    victim_conscious: bool = Field(..., description="Is the victim conscious")
    victim_breathing: bool = Field(..., description="Is the victim breathing")
    location: Optional[str] = Field(None, description="Current location")
    resources_available: List[str] = Field(
        default_factory=list, description="Available resources"
    )
    responder_training: str = Field(
        "basic", description="Responder training level: none, basic, advanced"
    )


class EmergencyResponseAgent(BaseHealthAgent[EmergencyRequest]):
    """Agent specialized in emergency medical response."""

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        llm: Optional[BaseLanguageModel] = None,
    ):
        """Initialize EmergencyResponseAgent.

        Args:
            config: Optional agent configuration
            llm: Optional language model
        """
        if not config:
            config = AgentConfig(
                name="EmergencyResponseAgent",
                description="Provides emergency medical guidance",
                temperature=0.0,  # Zero for maximum consistency
                max_iterations=5,  # Faster response for emergencies
                max_execution_time=10.0,  # 10 seconds max
                tools=get_tools_for_agent("emergency_response"),
                enable_memory=False,  # No memory for privacy in emergencies
                enable_medical_validation=True,
            )
        super().__init__(config, llm)

    def _get_default_system_prompt(self) -> str:
        """Get specialized system prompt for emergencies."""
        return """You are an emergency medical response AI for Haven Health Passport.

CRITICAL GUIDELINES:
1. ALWAYS start with "Call emergency services immediately" for life-threatening situations
2. Provide clear, step-by-step instructions
3. Use simple, direct language
4. Prioritize immediate life-saving actions
5. Never delay emergency service contact for assessment

Response Structure:
1. Immediate actions (first 30 seconds)
2. While waiting for help (ongoing care)
3. Information to give emergency services
4. Do NOT do list (common mistakes)

Available tools:
- emergency_protocol: Get specific emergency procedures
- symptom_analysis: Quick assessment of severity

Remember: You are providing emergency guidance to potentially save lives."""

    def _validate_input(
        self, input_data: EmergencyRequest, context: MedicalContext
    ) -> EmergencyRequest:
        """Validate emergency request."""
        # Force maximum urgency for emergencies
        context.urgency_level = 5

        # Log emergency for audit
        logger.critical(
            "Emergency response initiated",
            extra={
                "emergency_type": input_data.emergency_type,
                "victim_conscious": input_data.victim_conscious,
                "victim_breathing": input_data.victim_breathing,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        # Validate responder training level
        valid_training = ["none", "basic", "advanced"]
        if input_data.responder_training not in valid_training:
            input_data.responder_training = "basic"

        return input_data

    def _post_process_output(
        self, output: Dict[str, Any], context: MedicalContext
    ) -> Dict[str, Any]:
        """Post-process emergency response."""
        # Structure the response for clarity
        if "output" in output:
            response_text = output["output"]

            # Extract key sections
            output["emergency_response"] = {
                "immediate_actions": self._extract_immediate_actions(response_text),
                "ongoing_care": self._extract_ongoing_care(response_text),
                "emergency_info": self._extract_emergency_info(response_text),
                "warnings": self._extract_warnings(response_text),
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Add emergency numbers based on location
        output["emergency_contacts"] = self._get_emergency_contacts(context)

        # Log response for audit
        logger.critical(
            "Emergency response provided",
            extra={
                "response_id": output.get("response_id", "unknown"),
                "language": context.language,
            },
        )

        return output

    def _extract_immediate_actions(self, text: str) -> List[str]:
        """Extract immediate action steps."""
        # In production, use NLP to extract structured steps
        # For now, return placeholder
        _ = text  # Mark as intentionally unused
        return [
            "Call emergency services immediately",
            "Ensure scene safety",
            "Check responsiveness",
            "Follow dispatcher instructions",
        ]

    def _extract_ongoing_care(self, text: str) -> List[str]:
        """Extract ongoing care instructions."""
        _ = text  # Mark as intentionally unused
        return [
            "Monitor breathing and pulse",
            "Keep person comfortable",
            "Document changes in condition",
        ]

    def _extract_emergency_info(self, text: str) -> Dict[str, str]:
        """Extract information for emergency services."""
        _ = text  # Mark as intentionally unused
        return {
            "what": "Type and severity of emergency",
            "where": "Exact location with landmarks",
            "who": "Number and condition of victims",
            "when": "When it started/happened",
        }

    def _extract_warnings(self, text: str) -> List[str]:
        """Extract warning actions to avoid."""
        _ = text  # Mark as intentionally unused
        return [
            "Do not move victim unless in immediate danger",
            "Do not give food or water",
            "Do not leave victim alone",
        ]

    def _get_emergency_contacts(self, context: MedicalContext) -> Dict[str, str]:
        """Get emergency contacts based on location."""
        # In production, would use location services
        _ = context  # Mark as intentionally unused
        return {
            "general_emergency": "911",
            "poison_control": "1-800-222-1222",
            "crisis_hotline": "988",
            "non_emergency": "Local non-emergency number",
        }

    async def handle_cardiac_emergency(
        self,
        victim_conscious: bool,
        victim_breathing: bool,
        context: MedicalContext,
        aed_available: bool = False,
    ) -> Dict[str, Any]:
        """Handle cardiac emergency."""
        request = EmergencyRequest(
            emergency_type="cardiac arrest",
            symptoms=[
                "no pulse",
                "not breathing" if not victim_breathing else "difficulty breathing",
            ],
            victim_conscious=victim_conscious,
            victim_breathing=victim_breathing,
            location=None,
            resources_available=["AED"] if aed_available else [],
            responder_training="basic",
        )

        return await self.process(request, context)

    async def handle_trauma_emergency(
        self,
        injury_type: str,
        bleeding_severity: str,
        context: MedicalContext,
        first_aid_available: bool = True,
    ) -> Dict[str, Any]:
        """Handle trauma emergency."""
        request = EmergencyRequest(
            emergency_type=f"trauma - {injury_type}",
            symptoms=[f"{bleeding_severity} bleeding", "physical trauma"],
            victim_conscious=True,
            victim_breathing=True,
            location=None,
            resources_available=["first aid kit"] if first_aid_available else [],
            responder_training="basic",
        )

        return await self.process(request, context)
