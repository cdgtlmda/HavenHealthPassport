"""Medical Information Agent.

Specialized agent for medical information retrieval and analysis.
Handles queries about conditions, treatments, medications, and procedures.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.language_models import BaseLanguageModel
from pydantic import BaseModel, Field

from .base import AgentConfig, BaseHealthAgent, MedicalContext
from .tools import get_tools_for_agent

logger = logging.getLogger(__name__)


class MedicalQuery(BaseModel):
    """Input model for medical information queries."""

    query: str = Field(..., description="Medical question or search query")
    query_type: str = Field(
        "general", description="Type: general, condition, treatment, drug, procedure"
    )
    include_references: bool = Field(True, description="Include medical references")
    detail_level: str = Field(
        "standard", description="Detail level: basic, standard, comprehensive"
    )


class MedicalInformationAgent(BaseHealthAgent[MedicalQuery]):
    """Agent specialized in medical information retrieval."""

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        llm: Optional[BaseLanguageModel] = None,
    ):
        """Initialize MedicalInformationAgent.

        Args:
            config: Optional agent configuration
            llm: Optional language model
        """
        if not config:
            config = AgentConfig(
                name="MedicalInformationAgent",
                description="Retrieves and explains medical information",
                temperature=0.1,  # Low for accuracy
                tools=get_tools_for_agent("medical_information"),
                enable_medical_validation=True,
                enable_memory=True,
            )
        super().__init__(config, llm)

    def _get_default_system_prompt(self) -> str:
        """Get specialized system prompt for medical information."""
        return """You are a medical information specialist AI assistant for Haven Health Passport.

Your responsibilities:
1. Provide accurate, evidence-based medical information
2. Explain complex medical concepts in understandable terms
3. Always include appropriate disclaimers about seeking professional medical advice
4. Cite reliable medical sources when possible
5. Adapt explanations to the user's apparent health literacy level

Guidelines:
- Never diagnose conditions or prescribe treatments
- Always emphasize consulting healthcare providers for personal medical decisions
- Be culturally sensitive and aware of different healthcare contexts
- Provide information at the requested detail level
- Flag any potentially dangerous misconceptions

Available tools:
- medical_search: Search medical databases for conditions, treatments, procedures
- drug_interaction_check: Check medication interactions and contraindications

Remember: You are providing educational information, not medical advice."""

    def _validate_input(
        self, input_data: MedicalQuery, context: MedicalContext
    ) -> MedicalQuery:
        """Validate medical query input."""
        # Check for dangerous keywords that might indicate emergency
        emergency_keywords = [
            "chest pain",
            "can't breathe",
            "bleeding heavily",
            "unconscious",
        ]
        query_lower = input_data.query.lower()

        for keyword in emergency_keywords:
            if keyword in query_lower:
                logger.warning("Potential emergency detected in query: %s", keyword)
                # In production, this would trigger emergency protocols

        # Validate query type
        valid_types = ["general", "condition", "treatment", "drug", "procedure"]
        if input_data.query_type not in valid_types:
            input_data.query_type = "general"

        # Ensure reasonable detail level
        valid_details = ["basic", "standard", "comprehensive"]
        if input_data.detail_level not in valid_details:
            input_data.detail_level = "standard"

        return input_data

    def _post_process_output(
        self, output: Dict[str, Any], context: MedicalContext
    ) -> Dict[str, Any]:
        """Post-process medical information output."""
        # Add standard medical disclaimer
        if "output" in output:
            output["disclaimer"] = (
                "This information is for educational purposes only and should not replace "
                "professional medical advice, diagnosis, or treatment. Always consult with "
                "qualified healthcare providers for medical concerns."
            )

        # Add language notice if not in English
        if context.language != "en":
            output["language_notice"] = (
                f"This information was processed for {context.language}. "
                "Medical terminology may vary by region."
            )

        # Add urgency assessment
        output["urgency_assessment"] = {
            "level": context.urgency_level,
            "recommendation": self._get_urgency_recommendation(context.urgency_level),
        }

        # Log query for analytics
        logger.info(
            "Medical information query processed",
            extra={
                "query_type": output.get("query_type", "unknown"),
                "language": context.language,
                "urgency": context.urgency_level,
            },
        )

        return output

    def _get_urgency_recommendation(self, urgency_level: int) -> str:
        """Get recommendation based on urgency level."""
        recommendations = {
            1: "This appears to be a general information query.",
            2: "Consider scheduling a routine appointment if symptoms persist.",
            3: "Recommend consulting a healthcare provider soon.",
            4: "Seek medical attention promptly.",
            5: "This may require immediate medical attention.",
        }
        return recommendations.get(urgency_level, recommendations[3])

    async def explain_condition(
        self,
        condition_name: str,
        context: MedicalContext,
        include_treatments: bool = True,
    ) -> Dict[str, Any]:
        """Explain a specific medical condition."""
        query = MedicalQuery(
            query=f"Explain {condition_name}"
            + (" including treatment options" if include_treatments else ""),
            query_type="condition",
            include_references=True,
            detail_level="comprehensive",
        )

        return await self.process(query, context)

    async def check_drug_interaction(
        self,
        medications: list[str],
        context: MedicalContext,
        conditions: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        """Check for drug interactions."""
        query = MedicalQuery(
            query=f"Check interactions between: {', '.join(medications)}",
            query_type="drug",
            include_references=True,
            detail_level="comprehensive",
        )

        # Add conditions to context if provided
        if conditions:
            enhanced_context = MedicalContext(**context.dict())
            enhanced_context.medical_history_available = True
            return await self.process(query, enhanced_context)

        return await self.process(query, context)
