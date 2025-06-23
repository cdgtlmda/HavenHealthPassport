"""
LangChain Chain Manager for Haven Health Passport.

This module manages LangChain chains for various AI operations.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR resource typing and validation for healthcare data.
"""

import json
import logging
from typing import Any, Dict, Optional, cast

try:
    from langchain.chains import LLMChain
except ImportError:
    # For newer versions of langchain
    from langchain.chains.llm import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain.schema import BaseOutputParser

# Use Bedrock integration
from src.ai.langchain.bedrock import BedrockLLM
from src.healthcare.fhir.validators import FHIRValidator
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService

logger = logging.getLogger(__name__)


class MedicalOutputParser(BaseOutputParser[Dict[str, Any]]):
    """Parse medical AI outputs to structured format."""

    def parse(self, text: str) -> Dict[str, Any]:
        """Parse the output text."""
        try:
            # Try to parse as JSON first
            return cast(Dict[str, Any], json.loads(text))
        except json.JSONDecodeError:
            # Fallback to structured parsing
            return {"text": text, "parsed": False}


class ChainManager:
    """Manages LangChain chains for AI operations with FHIR Resource support."""

    def __init__(self) -> None:
        """Initialize the chain manager."""
        self.chains: Dict[str, Any] = {}
        self.default_models = {
            "text_generation": "anthropic.claude-3-haiku-20240307-v1:0",
            "embeddings": "amazon.titan-embed-text-v1",
            "translation": "anthropic.claude-3-haiku-20240307-v1:0",
            "medical_analysis": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        }
        # Don't initialize chains on import to avoid API key issues
        self._chains_initialized = False
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

    def validate_fhir_resource(self, resource: dict) -> bool:
        """Validate FHIR resource structure and requirements."""
        return self.fhir_validator.validate_resource(resource)

    @audit_phi_access("process_phi_data")
    @require_permission(AccessPermission.READ_PHI)
    def process_with_phi_protection(self, data: dict) -> dict:
        """Process data with PHI protection and audit logging."""
        # Encrypt sensitive fields
        sensitive_fields = ["name", "birthDate", "ssn", "address"]
        encrypted_data = data.copy()

        for field in sensitive_fields:
            if field in encrypted_data:
                encrypted_data[field] = self.encryption_service.encrypt(
                    str(encrypted_data[field]).encode("utf-8")
                )

        return encrypted_data

    def _ensure_initialized(self) -> None:
        """Lazy initialization of chains."""
        if not self._chains_initialized:
            try:
                self._initialize_chains()
                self._chains_initialized = True
            except Exception as e:
                logger.warning(f"Failed to initialize chains: {e}")

    def _initialize_chains(self) -> None:
        """Initialize commonly used chains."""
        # Medical translation chain
        self.chains["medical_translation"] = self._create_medical_translation_chain()

        # Health record analysis chain
        self.chains["health_analysis"] = self._create_health_analysis_chain()

        # Risk assessment chain
        self.chains["risk_assessment"] = self._create_risk_assessment_chain()

    def _create_medical_translation_chain(self) -> LLMChain:
        """Create medical translation chain."""
        system_template = """You are a medical translator specializing in refugee healthcare.
        Translate medical terms accurately while preserving critical health information.
        Consider cultural context and health literacy levels.
        Always maintain medical accuracy and include important warnings."""

        human_template = """Translate the following medical text from {source_lang} to {target_lang}:

        Text: {text}

        Medical Context: {medical_context}
        Cultural Context: {cultural_context}

        Provide the translation in JSON format with:
        - translation: the translated text
        - warnings: any critical medical warnings
        - notes: cultural or medical notes
        """

        messages = [
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template(human_template),
        ]

        prompt = ChatPromptTemplate.from_messages(messages)
        llm = BedrockLLM(model_id=self.default_models["translation"], temperature=0.1)

        return LLMChain(
            llm=llm,
            prompt=prompt,
            output_parser=MedicalOutputParser(),
            memory=ConversationBufferMemory(),
        )

    def _create_health_analysis_chain(self) -> LLMChain:
        """Create health record analysis chain."""
        system_template = """You are a medical AI assistant analyzing health records for refugees.
        Identify key health indicators, potential risks, and care recommendations.
        Consider the unique challenges of displaced populations including:
        - Interrupted care
        - Limited medical history
        - Language barriers
        - Cultural health practices"""

        human_template = """Analyze the following health record:

        Patient Demographics: {demographics}
        Medical History: {medical_history}
        Current Conditions: {conditions}
        Medications: {medications}
        Recent Vitals: {vitals}

        Provide analysis in JSON format with:
        - summary: brief health summary
        - risks: identified health risks
        - recommendations: care recommendations
        - follow_up: suggested follow-up actions
        - cultural_considerations: relevant cultural factors
        """

        messages = [
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template(human_template),
        ]

        prompt = ChatPromptTemplate.from_messages(messages)
        llm = BedrockLLM(
            model_id=self.default_models["medical_analysis"], temperature=0.2
        )

        return LLMChain(llm=llm, prompt=prompt, output_parser=MedicalOutputParser())

    def _create_risk_assessment_chain(self) -> LLMChain:
        """Create health risk assessment chain."""
        system_template = """You are a medical risk assessment AI for refugee healthcare.
        Evaluate health risks based on available data, considering:
        - Endemic diseases in origin/transit countries
        - Vaccination gaps
        - Nutritional deficiencies
        - Mental health factors
        - Access to care limitations"""

        human_template = """Assess health risks for:

        Origin Country: {origin_country}
        Transit Route: {transit_route}
        Current Location: {current_location}
        Age: {age}
        Gender: {gender}
        Known Conditions: {conditions}
        Symptoms: {symptoms}

        Provide risk assessment in JSON format with:
        - immediate_risks: urgent health risks
        - medium_term_risks: 1-6 month risks
        - preventive_measures: recommended preventive care
        - screening_needed: recommended health screenings
        - confidence_level: assessment confidence (0-1)
        """

        messages = [
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template(human_template),
        ]

        prompt = ChatPromptTemplate.from_messages(messages)
        llm = BedrockLLM(
            model_id=self.default_models["medical_analysis"], temperature=0.15
        )

        return LLMChain(llm=llm, prompt=prompt, output_parser=MedicalOutputParser())

    def create_chain(
        self, chain_type: str, model: Optional[str] = None, **kwargs: Any
    ) -> Any:
        """Create a new chain.

        Args:
            chain_type: Type of chain to create
            model: Model to use (optional)
            **kwargs: Additional chain configuration

        Returns:
            Created chain instance
        """
        self._ensure_initialized()

        if chain_type in self.chains:
            return self.chains[chain_type]

        if not model:
            model = self.default_models.get(
                chain_type, self.default_models["text_generation"]
            )

        logger.info("Creating %s chain with model %s", chain_type, model)

        # Create custom chain based on type
        if chain_type == "medical_translation":
            return self._create_medical_translation_chain()
        elif chain_type == "health_analysis":
            return self._create_health_analysis_chain()
        elif chain_type == "risk_assessment":
            return self._create_risk_assessment_chain()
        else:
            # Generic chain creation
            llm = BedrockLLM(model_id=model, **kwargs)
            return LLMChain(llm=llm)

    def get_chain(self, chain_name: str) -> Optional[Any]:
        """Get an existing chain by name.

        Args:
            chain_name: Name of the chain

        Returns:
            Chain instance if found, None otherwise
        """
        self._ensure_initialized()
        return self.chains.get(chain_name)


# Don't create default manager on import - let services create as needed
default_manager = None
