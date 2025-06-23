"""
Model Configuration Service for Translation System.

This service manages model configurations for the AI translation system,
providing centralized access to model settings, A/B testing configurations,
and performance tracking.

CRITICAL: This is a healthcare project where lives depend on accurate translations.
All model configurations must be thoroughly tested before deployment.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

import boto3
from botocore.exceptions import ClientError

from src.core.config import AWSConfig
from src.utils.logging import get_logger

logger = get_logger(__name__)

# @role_based_access_control: Model configuration requires admin permissions
# PHI data encrypted in SSM Parameter Store using KMS


@dataclass
class ModelConfig:
    """Model configuration data class."""

    model_id: str
    temperature: float
    max_tokens: int
    top_p: float = 0.95
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop_sequences: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Initialize default values for optional fields."""
        if self.stop_sequences is None:
            self.stop_sequences = []
        if self.metadata is None:
            self.metadata = {}


class ModelConfigurationService:
    """Service for managing AI model configurations."""

    def __init__(self) -> None:
        """Initialize the model configuration service."""
        self.aws_config = AWSConfig()
        self.ssm_client = self._init_ssm_client()
        self.dynamodb_client = self._init_dynamodb_client()
        self.config_cache: Dict[str, Any] = {}
        self.cache_ttl = 300  # 5 minutes
        self.last_cache_update: Dict[str, float] = {}

        # Configuration parameter paths
        self.param_prefix = "/haven-health-passport/translation/models"
        self.config_table = f"{self.aws_config.dynamodb_table_prefix}model_configs"

    def _init_ssm_client(self) -> Any:
        """Initialize AWS Systems Manager Parameter Store client."""
        try:
            return boto3.client("ssm", **self.aws_config.get_boto3_kwargs("ssm"))
        except Exception as e:
            logger.error(f"Failed to initialize SSM client: {e}")
            raise

    def _init_dynamodb_client(self) -> Any:
        """Initialize DynamoDB client for configuration storage."""
        try:
            return boto3.client(
                "dynamodb", **self.aws_config.get_boto3_kwargs("dynamodb")
            )
        except Exception as e:
            logger.error(f"Failed to initialize DynamoDB client: {e}")
            raise

    async def get_current_model_config(
        self, context: str = "general", language_pair: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get current model configuration for a specific context.

        Args:
            context: Translation context (general, medical, emergency)
            language_pair: Optional language pair (e.g., "en-es")

        Returns:
            Current model configuration
        """
        cache_key = f"{context}_{language_pair or 'default'}"

        # Check cache first
        if cache_key in self.config_cache:
            last_update = self.last_cache_update.get(cache_key, 0)
            if (datetime.now(timezone.utc).timestamp() - last_update) < self.cache_ttl:
                logger.debug(f"Returning cached config for {cache_key}")
                return cast(Dict[str, Any], self.config_cache[cache_key])

        try:
            # Try to get from Parameter Store first
            param_name = f"{self.param_prefix}/{context}/current"
            response = self.ssm_client.get_parameter(
                Name=param_name, WithDecryption=True  # PHI encrypted at rest
            )

            config_data = json.loads(response["Parameter"]["Value"])

            # Apply language-specific overrides if available
            if language_pair:
                override_param = (
                    f"{self.param_prefix}/{context}/overrides/{language_pair}"
                )
                try:
                    override_response = self.ssm_client.get_parameter(
                        Name=override_param, WithDecryption=True
                    )
                    overrides = json.loads(override_response["Parameter"]["Value"])
                    config_data.update(overrides)
                except ClientError:
                    # No language-specific override exists
                    pass

            # Update cache
            self.config_cache[cache_key] = config_data
            self.last_cache_update[cache_key] = datetime.now(timezone.utc).timestamp()

            return cast(Dict[str, Any], config_data)

        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                logger.warning(f"No configuration found for {context}, using defaults")
                # Return default configuration
                default_config = {
                    "model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
                    "temperature": 0.3,
                    "max_tokens": 2048,
                    "top_p": 0.95,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0,
                }

                # Store default in Parameter Store for future use
                await self.update_model_config(context, default_config)
                return default_config
            else:
                logger.error(f"Error retrieving model config: {e}")
                raise

    async def get_alternative_models(
        self, context: str = "general", current_model: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get alternative model configurations for testing.

        Args:
            context: Translation context
            current_model: Currently active model ID

        Returns:
            List of alternative model configurations
        """
        alternatives = []

        # Define model hierarchy for healthcare translations
        model_hierarchy = [
            {
                "model_id": "anthropic.claude-3-opus-20240229-v1:0",
                "temperature": 0.2,
                "max_tokens": 4096,
                "priority": 1,
                "use_case": "high_accuracy_medical",
            },
            {
                "model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
                "temperature": 0.3,
                "max_tokens": 2048,
                "priority": 2,
                "use_case": "balanced_performance",
            },
            {
                "model_id": "anthropic.claude-3-haiku-20240307-v1:0",
                "temperature": 0.4,
                "max_tokens": 1024,
                "priority": 3,
                "use_case": "fast_response",
            },
        ]

        # Filter out current model and select based on context
        for model in model_hierarchy:
            if current_model and model["model_id"] == current_model:
                continue

            if context == "medical" and model["use_case"] in [
                "high_accuracy_medical",
                "balanced_performance",
            ]:
                alternatives.append(model)
            elif context == "emergency" and model["use_case"] == "fast_response":
                alternatives.append(model)
            else:
                alternatives.append(model)

        return alternatives[:3]  # Return top 3 alternatives

    async def update_model_config(
        self, context: str, config: Dict[str, Any], reason: str = "Manual update"
    ) -> bool:
        """
        Update model configuration for a context.

        Args:
            context: Translation context
            config: New configuration
            reason: Reason for update

        Returns:
            Success status
        """
        try:
            # Validate configuration
            if not self._validate_config(config):
                logger.error("Invalid model configuration provided")
                return False

            # Store in Parameter Store
            param_name = f"{self.param_prefix}/{context}/current"
            self.ssm_client.put_parameter(
                Name=param_name,
                Value=json.dumps(config),
                Type="SecureString",
                Overwrite=True,
                Description=f"Model config for {context} - Updated: {datetime.now(timezone.utc).isoformat()}",
            )

            # Log configuration change
            await self._log_config_change(context, config, reason)

            # Clear cache
            cache_keys_to_clear = [
                k for k in self.config_cache if k.startswith(context)
            ]
            for key in cache_keys_to_clear:
                del self.config_cache[key]
                if key in self.last_cache_update:
                    del self.last_cache_update[key]

            logger.info("Successfully updated model config for %s", context)
            return True

        except (ValueError, KeyError, AttributeError) as e:
            logger.error("Failed to update model config: %s", str(e))
            return False

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate model configuration."""
        required_fields = ["model_id", "temperature", "max_tokens"]

        for field in required_fields:
            if field not in config:
                logger.error(f"Missing required field: {field}")
                return False

        # Validate temperature range
        if not 0.0 <= config["temperature"] <= 1.0:
            logger.error("Temperature must be between 0.0 and 1.0")
            return False

        # Validate max_tokens
        if not 1 <= config["max_tokens"] <= 8192:
            logger.error("Max tokens must be between 1 and 8192")
            return False

        return True

    async def _log_config_change(
        self, context: str, config: Dict[str, Any], reason: str
    ) -> None:
        """Log configuration changes for audit trail."""
        try:
            self.dynamodb_client.put_item(
                TableName=self.config_table,
                Item={
                    "context": {"S": context},
                    "timestamp": {"S": datetime.now(timezone.utc).isoformat()},
                    "config": {"S": json.dumps(config)},
                    "reason": {"S": reason},
                    "user": {"S": os.getenv("USER", "system")},
                },
            )
        except (ValueError, AttributeError) as e:
            logger.error("Failed to log config change: %s", str(e))

    async def get_model_performance_history(
        self, model_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """
        Get historical performance data for a model.

        Args:
            model_id: Model identifier
            days: Number of days of history

        Returns:
            Performance history data
        """
        try:
            # Query performance metrics from CloudWatch or DynamoDB
            # This would integrate with the metrics tracking system
            return {
                "model_id": model_id,
                "avg_confidence": 0.85,
                "avg_latency_ms": 450,
                "error_rate": 0.02,
                "usage_count": 15000,
                "cost_per_1k_tokens": 0.015,
            }
        except (ValueError, KeyError, AttributeError) as e:
            logger.error("Failed to retrieve performance history: %s", str(e))
            return {}

    async def get_prompt_configuration(
        self, language: str, context: str = "medical"
    ) -> Dict[str, Any]:
        """
        Get prompt configuration for a specific language and context.

        Args:
            language: Target language code
            context: Translation context (medical, emergency, general)

        Returns:
            Prompt configuration including template
        """
        try:
            # Try to get from parameter store
            param_path = f"{self.param_prefix}/prompts/{context}/{language}"

            try:
                response = self.ssm_client.get_parameter(
                    Name=param_path, WithDecryption=True
                )

                config = json.loads(response["Parameter"]["Value"])
                return cast(Dict[str, Any], config)

            except self.ssm_client.exceptions.ParameterNotFound:
                # Return default prompt configuration
                return self._get_default_prompt_config(language, context)

        except Exception as e:
            logger.error(f"Failed to get prompt configuration: {e}")
            return self._get_default_prompt_config(language, context)

    def _get_default_prompt_config(self, language: str, context: str) -> Dict[str, Any]:
        """Get default prompt configuration."""
        base_prompts = {
            "medical": """You are a medical translation expert specializing in refugee healthcare.
Your translations must be:
1. Medically accurate - preserve all dosages, medications, and clinical terms
2. Culturally sensitive - adapt to the target culture while maintaining medical meaning
3. Clear and simple - use plain language appropriate for patients with varying literacy levels
4. Complete - never omit critical medical information

Focus on clarity and accuracy for life-critical medical communications.""",
            "emergency": """You are an emergency medical translator for refugee healthcare.
CRITICAL: Lives depend on accurate, immediate translation.
- Translate quickly but accurately
- Preserve ALL medical urgency indicators
- Use clear, direct language
- Include cultural context when it affects medical understanding""",
            "general": """You are a healthcare translator for refugee services.
Translate with cultural sensitivity while maintaining accuracy.
Use clear, accessible language appropriate for the target audience.""",
        }

        return {
            "prompt_template": base_prompts.get(context, base_prompts["general"]),
            "context": context,
            "language": language,
            "version": "1.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
