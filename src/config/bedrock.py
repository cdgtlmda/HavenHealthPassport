"""Amazon Bedrock configuration settings."""

from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

from src.services.bedrock_service import BedrockModel

# Load .env.aws file if it exists
env_aws_path = Path(__file__).parent.parent.parent / ".env.aws"
if env_aws_path.exists():
    load_dotenv(env_aws_path)


class BedrockConfig(BaseSettings):
    """Bedrock-specific configuration.

    Note: AI models processing PHI must ensure proper access control
    and encryption of patient data.
    """

    # Model selection
    default_model: str = Field(
        default=BedrockModel.CLAUDE_V2,
        description="Default Bedrock model for general use",
    )

    translation_model: str = Field(
        default=BedrockModel.CLAUDE_V2,
        description="Preferred model for translation tasks",
    )

    medical_nlp_model: str = Field(
        default=BedrockModel.CLAUDE_V2,
        description="Preferred model for medical NLP tasks",
    )

    # Model parameters
    default_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Default temperature for model responses",
    )

    translation_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Temperature for translation (lower = more consistent)",
    )

    max_retries: int = Field(
        default=3, ge=1, le=5, description="Maximum number of retry attempts"
    )

    timeout_seconds: int = Field(
        default=30, ge=10, le=300, description="Request timeout in seconds"
    )

    # Rate limiting
    max_requests_per_minute: int = Field(
        default=60, ge=1, description="Maximum requests per minute per model"
    )

    # Caching
    enable_response_cache: bool = Field(
        default=True, description="Enable caching of Bedrock responses"
    )

    cache_ttl_seconds: int = Field(
        default=3600, ge=60, description="Cache TTL in seconds"
    )

    # Model fallback chain
    model_fallback_chain: List[str] = Field(
        default=[
            BedrockModel.CLAUDE_V2,
            BedrockModel.CLAUDE_INSTANT_V1,
            BedrockModel.TITAN_TEXT_EXPRESS,
        ],
        description="Fallback chain for model unavailability",
    )

    # Cost optimization
    use_instant_for_simple_tasks: bool = Field(
        default=True, description="Use Claude Instant for simple tasks to reduce costs"
    )

    simple_task_patterns: List[str] = Field(
        default=["language_detection", "simple_translation", "keyword_extraction"],
        description="Task patterns that can use instant models",
    )

    # Medical context
    medical_system_prompts: Dict[str, str] = Field(
        default={
            "translation": (
                "You are a professional medical translator with extensive knowledge of healthcare "
                "terminology, clinical procedures, and medical documentation. You understand the "
                "importance of accuracy in medical translation and maintain cultural sensitivity. "
                "Always preserve medical measurements, drug names, and clinical terms exactly."
            ),
            "summarization": (
                "You are a medical professional experienced in creating clear, accurate summaries "
                "of medical records and clinical documentation. Focus on key clinical findings, "
                "diagnoses, treatments, and relevant patient history."
            ),
            "extraction": (
                "You are a medical data analyst skilled at extracting structured information from "
                "unstructured medical text. Identify and extract key medical entities such as "
                "conditions, medications, procedures, and vital signs."
            ),
        },
        description="System prompts for medical contexts",
    )

    # Regional settings
    bedrock_regions: List[str] = Field(
        default=["us-east-1", "us-west-2", "eu-west-1"],
        description="AWS regions with Bedrock availability",
    )

    preferred_region: str = Field(
        default="us-east-1", description="Preferred AWS region for Bedrock"
    )

    # Feature flags
    enable_streaming: bool = Field(
        default=False, description="Enable streaming responses where supported"
    )

    enable_model_switching: bool = Field(
        default=True, description="Enable automatic model switching based on task"
    )

    enable_cost_tracking: bool = Field(
        default=True, description="Track estimated costs for Bedrock usage"
    )

    # Monitoring
    log_prompts: bool = Field(
        default=False, description="Log prompts for debugging (disable in production)"
    )

    log_responses: bool = Field(
        default=False,
        description="Log model responses for debugging (disable in production)",
    )

    # PHI Protection Settings
    encrypt_phi_in_prompts: bool = Field(
        default=True, description="Encrypt PHI before sending to Bedrock"
    )

    phi_detection_enabled: bool = Field(
        default=True, description="Detect and handle PHI in prompts"
    )

    phi_anonymization_enabled: bool = Field(
        default=False, description="Anonymize PHI instead of encrypting"
    )

    phi_access_level_required: str = Field(
        default="READ", description="Minimum access level for PHI operations"
    )

    class Config:
        """Pydantic config."""

        env_prefix = "BEDROCK_"
        case_sensitive = False


# Create a function to get Bedrock config
def get_bedrock_config() -> BedrockConfig:
    """Get Bedrock configuration."""
    return BedrockConfig()
