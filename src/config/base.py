"""Base configuration settings."""

import base64
import os
import secrets
import warnings
from typing import TYPE_CHECKING, Dict, List, Optional

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# FHIR Resource type imports
if TYPE_CHECKING:
    pass


class Settings(BaseSettings):
    """Application settings.

    Note: Configuration that may contain PHI requires proper access control
    and should be encrypted when stored or transmitted.
    """

    model_config = SettingsConfigDict(
        env_file=[".env", ".env.aws"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
    )

    # Application
    app_name: str = "Haven Health Passport"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    testing: bool = False
    log_format: str = "console"  # Added for logging configuration
    BASE_DIR: str = Field(
        default_factory=lambda: os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ),
        description="Base directory of the application",
    )

    # API
    api_v1_prefix: str = "/api/v1"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    allowed_origins: list[str] = ["*"]

    # Database
    database_url: str = "postgresql+asyncpg://user:pass@localhost/havenhealth"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_pool_size: int = 10

    # AWS
    aws_region: str = "us-east-1"
    AWS_REGION: str = Field(
        default="us-east-1", description="AWS region (alias)"
    )  # Add alias for compatibility
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_bucket_name: str = "haven-health-files"  # Default S3 bucket for file storage

    # HealthLake Configuration
    HEALTHLAKE_DATASTORE_ID: Optional[str] = Field(
        default=None, description="AWS HealthLake FHIR datastore ID"
    )

    @property
    def healthlake_datastore_id(self) -> Optional[str]:
        """Lowercase alias for HEALTHLAKE_DATASTORE_ID."""
        return self.HEALTHLAKE_DATASTORE_ID

    # Security
    secret_key: str = Field(
        default_factory=lambda: os.getenv("SECRET_KEY", ""),
        description="Application secret key - MUST be set in production",
    )
    encryption_key: str = Field(
        default_factory=lambda: os.getenv("ENCRYPTION_KEY", ""),
        description="Encryption key for data at rest - MUST be 32 chars",
    )
    jwt_secret_key: str = Field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY", ""),
        description="JWT signing key - MUST be set in production",
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    @field_validator("secret_key", "jwt_secret_key")
    @classmethod
    def validate_secret_keys(cls, v: str, info: ValidationInfo) -> str:
        """Validate that secret keys are not default values in production."""
        if not v or v == "" or "change-me" in v.lower():
            # In production, this MUST raise an error - lives depend on security
            env = os.getenv("ENVIRONMENT", "development").lower()
            if env in ["production", "staging"]:
                raise ValueError(
                    f"CRITICAL SECURITY ERROR: {info.field_name} must be set to a secure value in {env} environment. "
                    f"This is a healthcare system - patient data security is non-negotiable!"
                )
            # In development, generate a secure key but warn
            secure_key = secrets.token_urlsafe(64)
            warnings.warn(
                f"SECURITY WARNING: {info.field_name} is not set. "
                f"Generated temporary key for development: {secure_key[:8]}... "
                f"NEVER use this in production!",
                stacklevel=2,
            )
            return secure_key
        return v

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        """Validate encryption key length and generate if needed."""
        env = os.getenv("ENVIRONMENT", "development").lower()

        if not v:
            if env in ["production", "staging"]:
                raise ValueError(
                    "CRITICAL SECURITY ERROR: encryption_key MUST be set in production. "
                    "This is required for HIPAA compliance and patient data protection!"
                )
            # Generate a secure development key
            # Generate a cryptographically secure 32-byte key
            secure_key = base64.urlsafe_b64encode(secrets.token_bytes(24)).decode()[:32]
            warnings.warn(
                f"SECURITY WARNING: encryption_key not set. "
                f"Generated temporary key for development: {secure_key[:8]}... "
                f"NEVER use this in production! Store production keys in AWS Secrets Manager or similar.",
                stacklevel=2,
            )
            return secure_key
        elif len(v) != 32:
            raise ValueError(
                f"encryption_key must be exactly 32 characters, got {len(v)}. "
                f"For AES-256 encryption as required by HIPAA."
            )
        return v

    # Blockchain Configuration
    BLOCKCHAIN_PROVIDER: str = Field(
        default="aws_managed_blockchain",
        description="Blockchain provider (aws_managed_blockchain, hyperledger_fabric, local_development)",
    )
    ENABLE_BLOCKCHAIN: bool = Field(
        default=True, description="Enable blockchain functionality"
    )
    BLOCKCHAIN_FALLBACK_MODE: bool = Field(
        default=True,
        description="Allow system to continue if blockchain is unavailable",
    )

    # AWS Managed Blockchain Configuration
    MANAGED_BLOCKCHAIN_NETWORK_ID: Optional[str] = Field(
        default=None, description="AWS Managed Blockchain network ID"
    )

    @property
    def managed_blockchain_network_id(self) -> Optional[str]:
        """Lowercase alias for MANAGED_BLOCKCHAIN_NETWORK_ID."""
        return self.MANAGED_BLOCKCHAIN_NETWORK_ID

    MANAGED_BLOCKCHAIN_MEMBER_ID: Optional[str] = Field(
        default=None, description="AWS Managed Blockchain member ID"
    )

    # Blockchain - Hyperledger Fabric Configuration
    blockchain_network_id: Optional[str] = None
    blockchain_api_endpoint: Optional[str] = None
    BLOCKCHAIN_CHANNEL: str = Field(
        default="healthcare-channel", description="Hyperledger Fabric channel name"
    )
    BLOCKCHAIN_CHAINCODE: str = Field(
        default="health-records", description="Chaincode (smart contract) name"
    )
    BLOCKCHAIN_ORG: str = Field(
        default="Org1", description="Organization name in the blockchain network"
    )
    BLOCKCHAIN_USER: str = Field(
        default="User1", description="Blockchain user identity"
    )
    BLOCKCHAIN_PEER: str = Field(
        default="peer0.org1.havenhealthpassport.org:7051",
        description="Peer endpoint for blockchain transactions",
    )
    FABRIC_CFG_PATH: str = Field(
        default="/opt/hyperledger/fabric/config",
        description="Path to Fabric configuration files",
    )

    # Encryption keys for blockchain
    ENCRYPTION_KEY: Optional[str] = Field(
        default=None, description="Fernet encryption key for general encryption"
    )
    AES_ENCRYPTION_KEY: Optional[str] = Field(
        default=None,
        description="Base64 encoded AES-256 key for authenticated encryption",
    )

    # Deployment location for cross-border verification
    DEPLOYMENT_COUNTRY: str = Field(
        default="US",
        description="ISO 3166-1 alpha-2 country code where system is deployed",
    )

    # Healthcare
    fhir_server_url: str = "http://localhost:8080/fhir"
    fhir_validation_enabled: bool = True

    # FHIR Validation Settings
    fhir_strict_validation: bool = True
    fhir_profile_validation: bool = True
    fhir_terminology_validation: bool = True
    fhir_reference_validation: bool = True
    fhir_cardinality_validation: bool = True
    fhir_invariant_validation: bool = True

    # FHIR Resource Validation Rules
    fhir_validation_rules: Dict[str, Dict[str, bool]] = {
        "Patient": {
            "require_identifier": True,
            "require_name": True,
            "validate_telecom": True,
            "validate_address": True,
            "validate_birthDate": True,
        },
        "Observation": {
            "require_status": True,
            "require_code": True,
            "require_subject": True,
            "validate_value": True,
            "validate_effectiveDateTime": True,
        },
        "MedicationRequest": {
            "require_status": True,
            "require_intent": True,
            "require_medication": True,
            "require_subject": True,
            "validate_dosageInstruction": True,
        },
        "Condition": {
            "require_code": True,
            "require_subject": True,
            "validate_clinicalStatus": True,
            "validate_verificationStatus": True,
        },
    }

    # FHIR Profiles
    fhir_profiles: List[str] = [
        "http://hl7.org/fhir/StructureDefinition/Patient",
        "http://hl7.org/fhir/StructureDefinition/Observation",
        "http://hl7.org/fhir/StructureDefinition/MedicationRequest",
        "http://hl7.org/fhir/StructureDefinition/Condition",
        "http://hl7.org/fhir/StructureDefinition/Procedure",
    ]

    # FHIR Terminology
    fhir_terminology_server_url: Optional[str] = None
    fhir_validate_code_systems: bool = True
    fhir_validate_value_sets: bool = True
    fhir_supported_code_systems: List[str] = [
        "http://loinc.org",
        "http://snomed.info/sct",
        "http://www.nlm.nih.gov/research/umls/rxnorm",
        "http://hl7.org/fhir/sid/icd-10",
        "http://hl7.org/fhir/sid/cpt",
    ]

    # AI/ML
    bedrock_model_id: str = "anthropic.claude-v2"
    translation_cache_ttl: int = 3600

    # NORMRX API Configuration
    normrx_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("NORMRX_API_KEY"),
        description="NORMRX API key for medication normalization",
    )
    normrx_api_url: str = Field(
        default="https://api.normrx.com/v1", description="NORMRX API base URL"
    )
    normrx_timeout: int = Field(
        default=30, description="NORMRX API request timeout in seconds"
    )

    # Monitoring
    prometheus_enabled: bool = True
    opentelemetry_enabled: bool = True
    tracing_enabled: bool = True
    log_level: str = "INFO"

    # PHI Protection Settings
    phi_encryption_enabled: bool = True
    phi_access_audit_enabled: bool = True
    phi_access_level_default: str = "READ"
    phi_retention_days: int = 365 * 7  # 7 years for medical records
    phi_anonymization_enabled: bool = False
    phi_minimum_access_level: str = "READ"
    phi_data_classification_enabled: bool = True

    # Access Control Settings
    require_mfa_for_phi_access: bool = True
    session_timeout_minutes: int = 15
    max_failed_login_attempts: int = 5
    account_lockout_duration_minutes: int = 30

    # File Management
    max_file_size_mb: int = 50
    allowed_file_extensions: list[str] = [
        ".pdf",
        ".jpg",
        ".png",
        ".doc",
        ".docx",
        ".txt",
    ]
    virus_scan_endpoint: Optional[str] = None
    virus_scan_api_key: Optional[str] = None
    file_retention_days: int = 365 * 7  # 7 years by default
    cdn_base_url: str = "https://cdn.havenhealthpassport.org"
    file_encryption_enabled: bool = True

    # Email Configuration
    email_provider: str = "console"  # Options: "console", "aws_ses", "resend"
    from_email: str = "noreply@havenhealthpassport.org"
    from_name: str = "Haven Health Passport"
    email_verification_enabled: bool = True

    # AWS SES settings (if using AWS SES)
    ses_configuration_set: Optional[str] = None

    # Resend settings (if using Resend)
    resend_api_key: Optional[str] = None

    # Email template settings
    email_template_dir: str = "src/templates/emails"

    # Frontend URL for email links
    frontend_url: str = "http://localhost:3000"

    # Voice Synthesis Configuration
    VOICE_SYNTHESIS_ENGINE: str = Field(
        default="aws_polly",
        description="Voice synthesis engine (aws_polly, google_tts, mock)",
    )
    VOICE_SYNTHESIS_CACHE_TTL: int = Field(
        default=3600, description="Cache duration for synthesized audio in seconds"
    )
    VOICE_SYNTHESIS_DEFAULT_LANGUAGE: str = Field(
        default="en-US", description="Default language for voice synthesis"
    )
    VOICE_SYNTHESIS_S3_BUCKET: Optional[str] = Field(
        default=None, description="S3 bucket for storing synthesized audio files"
    )
    ENABLE_VOICE_SYNTHESIS: bool = Field(
        default=True, description="Enable voice synthesis functionality"
    )
    POLLY_LEXICON_NAMES: List[str] = Field(
        default_factory=lambda: [
            "HavenHealthMedicalEN",
            "HavenHealthMedicalES",
            "HavenHealthMedicalAR",
        ],
        description="Medical pronunciation lexicons for Amazon Polly",
    )

    # Data storage
    data_dir: str = "./data"
    # Security - HTTPS enforcement
    FORCE_HTTPS: bool = Field(
        default=True,
        description="Force HTTPS in production - REQUIRED for HIPAA compliance",
    )

    @field_validator("FORCE_HTTPS")
    @classmethod
    def validate_https_enforcement(
        cls, v: bool, _info: ValidationInfo
    ) -> bool:  # noqa: ARG002
        """Ensure HTTPS is enforced in production."""
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env in ["production", "staging"] and not v:
            raise ValueError(
                "CRITICAL: FORCE_HTTPS must be True in production/staging! "
                "HTTPS is mandatory for HIPAA compliance and patient data protection."
            )
        return v
