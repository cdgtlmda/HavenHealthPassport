"""LangChain Agents for Haven Health Passport.

This module provides intelligent agents for medical AI tasks including:
- Medical Information Retrieval
- Health Record Analysis
- Treatment Recommendation
- Emergency Response Coordination
- Multi-language Medical Translation
"""

from .base import AgentConfig, BaseHealthAgent
from .emergency import EmergencyResponseAgent
from .factory import AgentFactory, AgentType
from .health_record import HealthRecordAnalysisAgent
from .medical import MedicalInformationAgent
from .translation import MedicalTranslationAgent

__all__ = [
    "BaseHealthAgent",
    "AgentConfig",
    "MedicalInformationAgent",
    "EmergencyResponseAgent",
    "MedicalTranslationAgent",
    "HealthRecordAnalysisAgent",
    "AgentFactory",
    "AgentType",
]
