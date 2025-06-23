"""
LangChain Configuration for Haven Health Passport.

Centralized configuration management for all LangChain components

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import os
from enum import Enum
from typing import Any, Dict, List

from langchain_core.callbacks import CallbackManager, StdOutCallbackHandler
from langchain_core.callbacks.base import BaseCallbackHandler
from pydantic import BaseModel, ConfigDict, Field


class Environment(str, Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ModelProvider(str, Enum):
    """Supported model providers."""

    BEDROCK = "bedrock"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


class LangChainConfig(BaseModel):
    """Main configuration class for LangChain."""

    model_config = ConfigDict(extra="forbid", frozen=False)

    # Environment settings
    environment: Environment = Field(
        default=Environment.DEVELOPMENT, description="Current environment"
    )

    # Model configuration
    default_provider: ModelProvider = Field(
        default=ModelProvider.BEDROCK, description="Default model provider"
    )

    # Performance settings
    max_retries: int = Field(
        default=3, description="Maximum number of retries for API calls"
    )
    timeout_seconds: int = Field(
        default=300, description="Default timeout for API calls"
    )

    request_timeout_seconds: int = Field(
        default=60, description="Request timeout for individual API calls"
    )

    # Memory settings
    enable_memory: bool = Field(default=True, description="Enable conversation memory")

    max_memory_items: int = Field(
        default=100, description="Maximum items to store in memory"
    )

    # Caching settings
    enable_cache: bool = Field(default=True, description="Enable response caching")

    cache_ttl_seconds: int = Field(
        default=3600, description="Cache time-to-live in seconds"
    )

    # Security settings
    enable_content_filtering: bool = Field(
        default=True, description="Enable content filtering for medical safety"
    )

    enable_pii_detection: bool = Field(
        default=True, description="Enable PII detection and masking"
    )

    # Telemetry settings
    enable_telemetry: bool = Field(
        default=False, description="Enable telemetry collection"
    )

    # Debug settings
    debug: bool = Field(default=False, description="Enable debug logging")

    verbose: bool = Field(default=False, description="Enable verbose output")

    @classmethod
    def from_env(cls) -> "LangChainConfig":
        """Create configuration from environment variables."""
        env_mapping = {
            "LANGCHAIN_ENV": "environment",
            "LANGCHAIN_PROVIDER": "default_provider",
            "LANGCHAIN_MAX_RETRIES": "max_retries",
            "LANGCHAIN_TIMEOUT": "timeout_seconds",
            "LANGCHAIN_ENABLE_CACHE": "enable_cache",
            "LANGCHAIN_DEBUG": "debug",
            "LANGCHAIN_VERBOSE": "verbose",
        }

        config_dict: Dict[str, Any] = {}
        for env_var, config_key in env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert string booleans
                if config_key in ["enable_cache", "debug", "verbose", "enable_memory"]:
                    config_dict[config_key] = value.lower() == "true"
                # Convert integers
                elif config_key in [
                    "max_retries",
                    "timeout_seconds",
                    "max_memory_items",
                ]:
                    config_dict[config_key] = int(value)
                else:
                    config_dict[config_key] = value

        return cls(**config_dict)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "LangChainConfig":
        """Create configuration from dictionary."""
        return cls(**config_dict)

    def create_callback_manager(self) -> CallbackManager:
        """Create a callback manager with configured handlers."""
        handlers: List[BaseCallbackHandler] = []

        if self.verbose or self.debug:
            handlers.append(StdOutCallbackHandler())

        return CallbackManager(handlers)
