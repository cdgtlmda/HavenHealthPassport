"""Bedrock Model Factory and Configurations.

Handles model-specific settings for different Bedrock models.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class BedrockModelType(str, Enum):
    """Supported Bedrock model types."""

    # Claude models
    CLAUDE_3_OPUS = "anthropic.claude-3-opus-20240229"
    CLAUDE_3_SONNET = "anthropic.claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "anthropic.claude-3-haiku-20240307"
    CLAUDE_2_1 = "anthropic.claude-v2:1"
    CLAUDE_2 = "anthropic.claude-v2"
    CLAUDE_INSTANT = "anthropic.claude-instant-v1"

    # Titan models
    TITAN_TEXT_EXPRESS = "amazon.titan-text-express-v1"
    TITAN_TEXT_LITE = "amazon.titan-text-lite-v1"
    TITAN_EMBED_TEXT_V1 = "amazon.titan-embed-text-v1"
    TITAN_EMBED_TEXT_V2 = "amazon.titan-embed-text-v2"

    # AI21 Labs models (Jamba)
    JAMBA_1_5_MINI = "ai21.jamba-1-5-mini"
    JAMBA_1_5_LARGE = "ai21.jamba-1-5-large"
    JAMBA_INSTRUCT = "ai21.jamba-instruct"

    # Cohere models
    COHERE_COMMAND = "cohere.command-text-v14"
    COHERE_COMMAND_LIGHT = "cohere.command-light-text-v14"

    # Meta Llama models
    LLAMA2_70B = "meta.llama2-70b-chat-v1"
    LLAMA2_13B = "meta.llama2-13b-chat-v1"


@dataclass
class ModelConfig:
    """Configuration for a specific model."""

    model_id: str
    max_tokens: int
    temperature: float
    top_p: float
    top_k: Optional[int]
    stop_sequences: list
    supports_streaming: bool
    supports_system_prompt: bool
    cost_per_1k_input_tokens: float
    cost_per_1k_output_tokens: float
    medical_optimized: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls."""
        return {
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "stop_sequences": self.stop_sequences,
        }


class BedrockModelFactory:
    """Factory for creating Bedrock model configurations."""

    def __init__(self) -> None:
        """Initialize the factory."""
        self._model_configs = self._initialize_model_configs()

    def _initialize_model_configs(self) -> Dict[BedrockModelType, ModelConfig]:
        """Initialize all model configurations."""
        configs = {
            # Claude 3 models
            BedrockModelType.CLAUDE_3_OPUS: ModelConfig(
                model_id=BedrockModelType.CLAUDE_3_OPUS,
                max_tokens=4096,
                temperature=0.3,  # Lower for medical accuracy
                top_p=0.9,
                top_k=250,
                stop_sequences=[],
                supports_streaming=True,
                supports_system_prompt=True,
                cost_per_1k_input_tokens=0.015,
                cost_per_1k_output_tokens=0.075,
                medical_optimized=True,
            ),
            BedrockModelType.CLAUDE_3_SONNET: ModelConfig(
                model_id=BedrockModelType.CLAUDE_3_SONNET,
                max_tokens=4096,
                temperature=0.5,
                top_p=0.95,
                top_k=250,
                stop_sequences=[],
                supports_streaming=True,
                supports_system_prompt=True,
                cost_per_1k_input_tokens=0.003,
                cost_per_1k_output_tokens=0.015,
            ),
            # Titan models
            BedrockModelType.TITAN_TEXT_EXPRESS: ModelConfig(
                model_id=BedrockModelType.TITAN_TEXT_EXPRESS,
                max_tokens=8192,
                temperature=0.5,
                top_p=0.9,
                top_k=None,
                stop_sequences=[],
                supports_streaming=True,
                supports_system_prompt=False,
                cost_per_1k_input_tokens=0.0008,
                cost_per_1k_output_tokens=0.0016,
            ),
            # Embeddings models
            BedrockModelType.TITAN_EMBED_TEXT_V2: ModelConfig(
                model_id=BedrockModelType.TITAN_EMBED_TEXT_V2,
                max_tokens=8192,  # Input token limit
                temperature=0,
                top_p=1,
                top_k=None,
                stop_sequences=[],
                supports_streaming=False,
                supports_system_prompt=False,
                cost_per_1k_input_tokens=0.0001,
                cost_per_1k_output_tokens=0,  # Embeddings have no output tokens
            ),
        }

        return configs

    def get_model_config(self, model_id: str) -> Dict[str, Any]:
        """Get configuration for a specific model."""
        # Convert string to BedrockModelType if it exists
        model_type = None
        for bedrock_model in BedrockModelType:
            if bedrock_model.value == model_id:
                model_type = bedrock_model
                break

        if model_type and model_type in self._model_configs:
            return self._model_configs[model_type].to_dict()

        # Return default configuration for unknown models
        return {
            "max_tokens": 4096,
            "temperature": 0.7,
            "top_p": 1.0,
            "stop_sequences": [],
        }

    def get_medical_optimized_models(self) -> list[str]:
        """Get list of models optimized for medical use cases."""
        return [
            model_id
            for model_id, config in self._model_configs.items()
            if config.medical_optimized
        ]

    def get_embedding_models(self) -> list[str]:
        """Get list of embedding models."""
        return [
            model_id for model_id in self._model_configs if "embed" in model_id.lower()
        ]

    def estimate_cost(
        self, model_id: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Estimate cost for a model invocation."""
        # Convert string to BedrockModelType if it exists
        model_type = None
        for bedrock_model in BedrockModelType:
            if bedrock_model.value == model_id:
                model_type = bedrock_model
                break

        if not model_type or model_type not in self._model_configs:
            return 0.0

        config = self._model_configs[model_type]
        input_cost = (input_tokens / 1000) * config.cost_per_1k_input_tokens
        output_cost = (output_tokens / 1000) * config.cost_per_1k_output_tokens

        return input_cost + output_cost
