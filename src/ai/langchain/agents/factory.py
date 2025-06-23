"""Agent Factory for Haven Health Passport.

Factory pattern for creating and managing different types of agents.
Provides centralized agent lifecycle management.
"""

import logging
from enum import Enum
from typing import Any, Dict, Optional, Type, Union, cast

from langchain_core.language_models import BaseLanguageModel

from .base import AgentConfig, BaseHealthAgent, MedicalContext
from .emergency import EmergencyResponseAgent
from .health_record import HealthRecordAnalysisAgent
from .medical import MedicalInformationAgent
from .translation import MedicalTranslationAgent

logger = logging.getLogger(__name__)


class AgentType(str, Enum):
    """Available agent types."""

    MEDICAL_INFO = "medical_information"
    EMERGENCY = "emergency_response"
    TRANSLATION = "medical_translation"
    HEALTH_RECORD = "health_record_analysis"


class AgentFactory:
    """Factory for creating and managing health agents."""

    # Agent type mapping
    _agent_classes: Dict[AgentType, Type[BaseHealthAgent]] = {
        AgentType.MEDICAL_INFO: MedicalInformationAgent,
        AgentType.EMERGENCY: EmergencyResponseAgent,
        AgentType.TRANSLATION: MedicalTranslationAgent,
        AgentType.HEALTH_RECORD: HealthRecordAnalysisAgent,
    }

    # Active agent instances
    _agents: Dict[str, BaseHealthAgent] = {}

    @classmethod
    def create_agent(
        cls,
        agent_type: Union[AgentType, str],
        config: Optional[AgentConfig] = None,
        llm: Optional[BaseLanguageModel] = None,
        agent_id: Optional[str] = None,
    ) -> BaseHealthAgent:
        """Create a new agent instance."""
        # Convert string to enum if needed
        if isinstance(agent_type, str):
            try:
                agent_type = AgentType(agent_type)
            except ValueError as exc:
                raise ValueError(f"Unknown agent type: {agent_type}") from exc

        # Get agent class
        agent_class = cls._agent_classes.get(agent_type)
        if not agent_class:
            raise ValueError(f"No implementation for agent type: {agent_type}")

        # Create agent
        try:
            agent = agent_class(
                config=config
                or AgentConfig(
                    name=f"{agent_type}_agent",
                    description=f"Agent for {agent_type} operations",
                ),
                llm=llm,
            )

            # Store agent if ID provided
            if agent_id:
                cls._agents[agent_id] = agent
                logger.info("Created and stored agent: %s (%s)", agent_id, agent_type)
            else:
                logger.info("Created agent: %s", agent_type)

            return agent

        except Exception as e:
            logger.error("Failed to create agent %s: %s", agent_type, e)
            raise

    @classmethod
    def get_agent(cls, agent_id: str) -> Optional[BaseHealthAgent]:
        """Get an existing agent by ID."""
        return cls._agents.get(agent_id)

    @classmethod
    def list_agents(cls) -> Dict[str, Dict[str, Any]]:
        """List all active agents."""
        return {
            agent_id: {
                "type": agent.__class__.__name__,
                "state": agent.state.value,
                "config": agent.config.name,
            }
            for agent_id, agent in cls._agents.items()
        }

    @classmethod
    def terminate_agent(cls, agent_id: str) -> bool:
        """Terminate and remove an agent."""
        agent = cls._agents.get(agent_id)
        if agent:
            agent.terminate()
            del cls._agents[agent_id]
            logger.info("Terminated agent: %s", agent_id)
            return True
        return False

    @classmethod
    def terminate_all_agents(cls) -> int:
        """Terminate all active agents."""
        count = len(cls._agents)
        for agent_id in list(cls._agents.keys()):
            cls.terminate_agent(agent_id)
        logger.info("Terminated all %d agents", count)
        return count

    @classmethod
    def create_agent_for_context(
        cls, context: MedicalContext, preferred_type: Optional[AgentType] = None
    ) -> BaseHealthAgent:
        """Create appropriate agent based on context."""
        # Determine best agent type based on context
        if context.urgency_level >= 4:
            agent_type = AgentType.EMERGENCY
        elif context.language != "en" and preferred_type != AgentType.EMERGENCY:
            agent_type = AgentType.TRANSLATION
        else:
            agent_type = preferred_type or AgentType.MEDICAL_INFO

        logger.info(
            "Creating %s agent for context (urgency: %d, lang: %s)",
            agent_type,
            context.urgency_level,
            context.language,
        )

        return cls.create_agent(agent_type)

    @classmethod
    def get_agent_capabilities(
        cls, agent_type: Union[AgentType, str]
    ) -> Dict[str, Any]:
        """Get capabilities of an agent type."""
        if isinstance(agent_type, str):
            agent_type = AgentType(agent_type)

        capabilities = {
            AgentType.MEDICAL_INFO: {
                "description": "Medical information retrieval and explanation",
                "capabilities": [
                    "Search medical databases",
                    "Explain conditions and treatments",
                    "Check drug interactions",
                    "Provide health education",
                ],
                "languages": ["all"],
                "response_time": "fast",
            },
            AgentType.EMERGENCY: {
                "description": "Emergency medical response guidance",
                "capabilities": [
                    "Provide immediate action steps",
                    "Emergency protocol guidance",
                    "Triage assessment",
                    "First aid instructions",
                ],
                "languages": ["all"],
                "response_time": "immediate",
            },
            AgentType.TRANSLATION: {
                "description": "Medical content translation",
                "capabilities": [
                    "Translate medical documents",
                    "Preserve medical terminology",
                    "Cultural adaptation",
                    "Multi-language summaries",
                ],
                "languages": ["50+ languages"],
                "response_time": "fast",
            },
            AgentType.HEALTH_RECORD: {
                "description": "Health record analysis and insights",
                "capabilities": [
                    "Analyze medical history",
                    "Identify health trends",
                    "Detect care gaps",
                    "Generate summaries",
                ],
                "languages": ["all"],
                "response_time": "moderate",
            },
        }

        return capabilities.get(agent_type, {})


# Convenience functions for common agent operations
def create_medical_agent(
    config: Optional[AgentConfig] = None,
) -> MedicalInformationAgent:
    """Create a medical information agent."""
    return cast(
        MedicalInformationAgent,
        AgentFactory.create_agent(AgentType.MEDICAL_INFO, config),
    )


def create_emergency_agent(
    config: Optional[AgentConfig] = None,
) -> EmergencyResponseAgent:
    """Create an emergency response agent."""
    return cast(
        EmergencyResponseAgent, AgentFactory.create_agent(AgentType.EMERGENCY, config)
    )


def create_translation_agent(
    config: Optional[AgentConfig] = None,
) -> MedicalTranslationAgent:
    """Create a medical translation agent."""
    return cast(
        MedicalTranslationAgent,
        AgentFactory.create_agent(AgentType.TRANSLATION, config),
    )


def create_health_record_agent(
    config: Optional[AgentConfig] = None,
) -> HealthRecordAnalysisAgent:
    """Create a health record analysis agent."""
    return cast(
        HealthRecordAnalysisAgent,
        AgentFactory.create_agent(AgentType.HEALTH_RECORD, config),
    )
