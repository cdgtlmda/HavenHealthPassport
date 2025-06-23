"""Registry of available Bedrock models with their configurations."""

from .models import ModelCategory, ModelInfo, ModelUsageType

# Common usage types for language models
LANGUAGE_MODEL_USAGE = [
    ModelUsageType.TRANSLATION,
    ModelUsageType.SUMMARIZATION,
    ModelUsageType.EXTRACTION,
    ModelUsageType.GENERATION,
    ModelUsageType.QA,
]

# Model registry with all available Bedrock models
MODEL_REGISTRY = {
    # Claude models
    "anthropic.claude-v2": ModelInfo(
        model_id="anthropic.claude-v2",
        name="Claude 2",
        provider="Anthropic",
        category=ModelCategory.GENERAL,
        supported_usage_types=LANGUAGE_MODEL_USAGE,
        max_tokens=100000,
        cost_per_1k_tokens=0.008,
        regions=["us-east-1", "us-west-2"],
    ),
    "anthropic.claude-instant-v1": ModelInfo(
        model_id="anthropic.claude-instant-v1",
        name="Claude Instant",
        provider="Anthropic",
        category=ModelCategory.GENERAL,
        supported_usage_types=LANGUAGE_MODEL_USAGE,
        max_tokens=100000,
        cost_per_1k_tokens=0.0016,
        regions=["us-east-1", "us-west-2"],
    ),
    "anthropic.claude-3-sonnet-20240229-v1:0": ModelInfo(
        model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        name="Claude 3 Sonnet",
        provider="Anthropic",
        category=ModelCategory.MEDICAL,
        supported_usage_types=LANGUAGE_MODEL_USAGE,
        max_tokens=200000,
        cost_per_1k_tokens=0.003,
        is_medical_specialized=True,
        regions=["us-east-1", "us-west-2", "eu-west-1"],
    ),
}
