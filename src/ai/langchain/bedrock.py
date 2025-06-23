"""Bedrock integration for LangChain."""

from typing import Any, List, Optional

from langchain.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain.llms.base import LLM

# Import the Bedrock service
from src.services.bedrock_service import bedrock_service

# Additional exports for backward compatibility
from .aws import (
    get_bedrock_embeddings,
    get_bedrock_llm,
)
from .aws.bedrock_models import BedrockModelFactory, BedrockModelType, ModelConfig


class BedrockLLM(LLM):
    """Bedrock LLM wrapper for LangChain compatibility."""

    model_id: str
    temperature: float = 0.7
    max_tokens: int = 4000

    @property
    def _llm_type(self) -> str:
        """Return type of LLM."""
        return "bedrock"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call Bedrock model."""
        # Get the bedrock service instance
        service = bedrock_service()

        # Invoke the model and get the response tuple
        response_text, _metadata = service.invoke_model(
            prompt=prompt,
            model_id=self.model_id,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response_text

    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Async call to Bedrock model."""
        # For now, just use sync version
        return self._call(prompt, stop, None, **kwargs)


# Alias for backward compatibility
get_bedrock_chat_model = get_bedrock_llm
get_bedrock_model = get_bedrock_llm

# Legacy mapping for backward compatibility
BEDROCK_MODEL_MAPPING = {
    model_type.value: model_type for model_type in BedrockModelType
}

# Legacy config alias
BedrockModelConfig = ModelConfig

__all__ = [
    "BedrockLLM",
    "BedrockModelFactory",
    "BedrockModelType",
    "ModelConfig",
    "BedrockModelConfig",
    "BEDROCK_MODEL_MAPPING",
    "get_bedrock_chat_model",
    "get_bedrock_model",
    "get_bedrock_embeddings",
]
