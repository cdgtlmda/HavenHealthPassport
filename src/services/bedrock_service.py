"""Amazon Bedrock service for AI/ML capabilities."""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Tuple

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from src.config.loader import get_settings
from src.utils.logging import get_logger
from src.utils.monitoring import metrics_collector

logger = get_logger(__name__)


class BedrockException(Exception):
    """Base exception for Bedrock service errors."""


class BedrockRateLimitException(BedrockException):
    """Raised when rate limit is exceeded."""


class BedrockModelNotReadyException(BedrockException):
    """Raised when model is not ready."""


class BedrockModel(str):
    """Supported Bedrock models."""

    # Anthropic Claude models
    CLAUDE_V2 = "anthropic.claude-v2"
    CLAUDE_V2_1 = "anthropic.claude-v2:1"
    CLAUDE_INSTANT_V1 = "anthropic.claude-instant-v1"

    # Amazon Titan models
    TITAN_TEXT_EXPRESS = "amazon.titan-text-express-v1"
    TITAN_TEXT_LITE = "amazon.titan-text-lite-v1"

    # Meta Llama models
    LLAMA2_70B = "meta.llama2-70b-chat-v1"
    LLAMA2_13B = "meta.llama2-13b-chat-v1"


class BedrockService:
    """Service for interacting with Amazon Bedrock."""

    # Model-specific parameters
    MODEL_CONFIGS = {
        BedrockModel.CLAUDE_V2: {
            "max_tokens": 4096,
            "temperature_range": (0.0, 1.0),
            "supports_system_prompt": True,
            "input_format": "claude",
        },
        BedrockModel.CLAUDE_INSTANT_V1: {
            "max_tokens": 4096,
            "temperature_range": (0.0, 1.0),
            "supports_system_prompt": True,
            "input_format": "claude",
        },
        BedrockModel.TITAN_TEXT_EXPRESS: {
            "max_tokens": 8192,
            "temperature_range": (0.0, 1.0),
            "supports_system_prompt": False,
            "input_format": "titan",
        },
        BedrockModel.LLAMA2_70B: {
            "max_tokens": 2048,
            "temperature_range": (0.0, 1.0),
            "supports_system_prompt": True,
            "input_format": "llama",
        },
    }

    def __init__(self) -> None:
        """Initialize Bedrock service."""
        # Configure retry strategy
        retry_config = Config(
            region_name=get_settings().aws_region,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )

        # Initialize Bedrock runtime client
        self.bedrock_runtime = boto3.client(
            "bedrock-runtime",
            config=retry_config,
            aws_access_key_id=get_settings().aws_access_key_id,
            aws_secret_access_key=get_settings().aws_secret_access_key,
        )

        # Initialize Bedrock client for model info
        self.bedrock = boto3.client(
            "bedrock",
            config=retry_config,
            aws_access_key_id=get_settings().aws_access_key_id,
            aws_secret_access_key=get_settings().aws_secret_access_key,
        )

        # Thread pool for async operations
        self._executor = ThreadPoolExecutor(max_workers=5)

        # Cache for model availability
        self._model_cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, datetime] = {}

        # Performance tracking
        self._request_times: List[float] = []

        # Initialize model list - skip in test environment
        if get_settings().environment != "test":
            try:
                self._refresh_available_models()
            except (ClientError, ValueError, KeyError) as e:
                logger.warning(f"Failed to refresh available models: {e}")
                # Initialize with empty models list
                self._model_cache["available_models"] = []
                self._cache_expiry["available_models"] = datetime.utcnow()

    def _refresh_available_models(self) -> None:
        """Refresh the list of available models."""
        try:
            response = self.bedrock.list_foundation_models()
            self._model_cache["available_models"] = [
                model["modelId"] for model in response.get("modelSummaries", [])
            ]
            self._cache_expiry["available_models"] = datetime.utcnow()  # 1 hour

            logger.info(
                f"Available Bedrock models: {self._model_cache['available_models']}"
            )
        except (ClientError, ValueError, KeyError, AttributeError) as e:
            logger.error(f"Failed to refresh model list: {e}")
            self._model_cache["available_models"] = []

    def is_model_available(self, model_id: str) -> bool:
        """Check if a model is available."""
        # Check cache expiry (1 hour cache)
        cache_time = self._cache_expiry.get("available_models")
        if not cache_time or (datetime.utcnow() - cache_time).seconds > 3600:
            self._refresh_available_models()

        return model_id in self._model_cache.get("available_models", [])

    def format_prompt(
        self, prompt: str, model_id: str, system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format prompt based on model requirements."""
        config = self.MODEL_CONFIGS.get(model_id, {})
        input_format = config.get("input_format", "claude")

        if input_format == "claude":
            # Claude format
            formatted_prompt = f"\n\nHuman: {prompt}\n\nAssistant:"
            if system_prompt and config.get("supports_system_prompt"):
                formatted_prompt = f"{system_prompt}\n{formatted_prompt}"

            return {
                "prompt": formatted_prompt,
                "max_tokens_to_sample": config.get("max_tokens", 4096),
                "temperature": 0.3,
                "top_p": 0.9,
                "stop_sequences": ["\n\nHuman:"],
            }

        elif input_format == "titan":
            # Amazon Titan format
            text_prompt = prompt
            if system_prompt:
                text_prompt = f"{system_prompt}\n\n{prompt}"

            return {
                "inputText": text_prompt,
                "textGenerationConfig": {
                    "maxTokenCount": config.get("max_tokens", 4096),
                    "temperature": 0.3,
                    "topP": 0.9,
                    "stopSequences": [],
                },
            }

        elif input_format == "llama":
            # Llama 2 format
            formatted_prompt = f"<s>[INST] {prompt} [/INST]"
            if system_prompt:
                formatted_prompt = (
                    f"<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n{prompt} [/INST]"
                )

            return {
                "prompt": formatted_prompt,
                "max_gen_len": config.get("max_tokens", 2048),
                "temperature": 0.3,
                "top_p": 0.9,
            }

        else:
            # Default to Claude format
            return {
                "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
                "max_tokens_to_sample": 2048,
                "temperature": 0.3,
                "top_p": 0.9,
                "top_k": 50,
                "stop_sequences": ["\n\nHuman:"],
            }

    def parse_response(self, response_body: Dict[str, Any], model_id: str) -> str:
        """Parse response based on model format."""
        config = self.MODEL_CONFIGS.get(model_id, {})
        input_format = config.get("input_format", "claude")

        if input_format == "claude":
            return str(response_body.get("completion", "")).strip()
        elif input_format == "titan":
            results = response_body.get("results", [])
            return str(results[0].get("outputText", "")).strip() if results else ""
        elif input_format == "llama":
            return str(response_body.get("generation", "")).strip()
        else:
            # Try common fields
            return str(
                response_body.get("completion")
                or response_body.get("generation")
                or response_body.get("outputText", "")
            ).strip()

    def invoke_model(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Invoke a Bedrock model with the given prompt.

        Args:
            prompt: The input prompt
            model_id: Model to use (defaults to get_settings().bedrock_model_id)
            system_prompt: Optional system prompt
            temperature: Temperature for response generation
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model-specific parameters

        Returns:
            Tuple of (response_text, metadata)
        """
        model_id = model_id or get_settings().bedrock_model_id

        # Check model availability
        if not self.is_model_available(model_id):
            logger.warning(f"Model {model_id} not available, falling back to Claude V2")
            model_id = BedrockModel.CLAUDE_V2

        start_time = datetime.utcnow()

        try:
            # Format the request
            request_body = self.format_prompt(prompt, model_id, system_prompt)

            # Override temperature if provided
            if "temperature" in request_body:
                request_body["temperature"] = temperature
            elif "textGenerationConfig" in request_body:
                request_body["textGenerationConfig"]["temperature"] = temperature

            # Override max tokens if provided
            if max_tokens:
                if "max_tokens_to_sample" in request_body:
                    request_body["max_tokens_to_sample"] = max_tokens
                elif "textGenerationConfig" in request_body:
                    request_body["textGenerationConfig"]["maxTokenCount"] = max_tokens
                elif "max_gen_len" in request_body:
                    request_body["max_gen_len"] = max_tokens

            # Add any additional parameters
            request_body.update(kwargs)

            # Invoke the model
            response = self.bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json",
            )

            # Parse response
            response_body = json.loads(response["body"].read())
            response_text = self.parse_response(response_body, model_id)

            # Calculate metrics
            end_time = datetime.utcnow()
            latency = (end_time - start_time).total_seconds()

            # Track performance
            self._request_times.append(latency)
            if len(self._request_times) > 100:
                self._request_times.pop(0)

            # Prepare metadata
            metadata = {
                "model_id": model_id,
                "latency_seconds": latency,
                "prompt_length": len(prompt),
                "response_length": len(response_text),
                "temperature": temperature,
                "timestamp": start_time.isoformat(),
            }

            # Log metrics
            metrics_collector.record_bedrock_request(
                model_id=model_id, latency=latency, success=True
            )

            logger.info(
                f"Bedrock request completed - Model: {model_id}, Latency: {latency:.2f}s"
            )

            return response_text, metadata

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]

            logger.error(
                f"Bedrock ClientError - Code: {error_code}, Message: {error_message}"
            )

            # Track error metrics
            metrics_collector.record_bedrock_request(
                model_id=model_id,
                latency=(datetime.utcnow() - start_time).total_seconds(),
                success=False,
                error_code=error_code,
            )

            # Handle specific errors
            if error_code == "ThrottlingException":
                raise BedrockRateLimitException(
                    "Rate limit exceeded. Please retry later."
                ) from e
            elif error_code == "ModelNotReadyException":
                raise BedrockModelNotReadyException(
                    f"Model {model_id} is not ready. Please try again."
                ) from e
            else:
                raise BedrockException(f"Bedrock error: {error_message}") from e

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Unexpected Bedrock error: {e}")

            # Track error metrics
            metrics_collector.record_bedrock_request(
                model_id=model_id,
                latency=(datetime.utcnow() - start_time).total_seconds(),
                success=False,
            )

            raise

    async def invoke_model_async(
        self, prompt: str, model_id: Optional[str] = None, **kwargs: Any
    ) -> Tuple[str, Dict[str, Any]]:
        """Async wrapper for invoke_model."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, lambda: self.invoke_model(prompt, model_id, **kwargs)
        )

    def batch_invoke(
        self,
        prompts: List[str],
        model_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Invoke model for multiple prompts.

        Args:
            prompts: List of prompts to process
            model_id: Model to use
            system_prompt: Optional system prompt for all requests
            **kwargs: Additional parameters

        Returns:
            List of (response, metadata) tuples
        """
        results = []

        for i, prompt in enumerate(prompts):
            try:
                response, metadata = self.invoke_model(
                    prompt=prompt,
                    model_id=model_id,
                    system_prompt=system_prompt,
                    **kwargs,
                )
                results.append((response, metadata))

                # Add small delay to avoid throttling
                if i < len(prompts) - 1:
                    time.sleep(0.1)

            except (ClientError, ValueError, KeyError, AttributeError) as e:
                logger.error(f"Error processing prompt {i}: {e}")
                results.append(("", {"error": str(e)}))

        return results

    def stream_invoke(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """
        Stream responses from Bedrock (if supported by model).

        Note: Not all models support streaming.
        """
        model_id = model_id or get_settings().bedrock_model_id

        try:
            request_body = self.format_prompt(prompt, model_id, system_prompt)
            request_body.update(kwargs)

            response = self.bedrock_runtime.invoke_model_with_response_stream(
                modelId=model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json",
            )

            stream = response.get("body")
            if stream:
                for event in stream:
                    chunk = event.get("chunk")
                    if chunk:
                        chunk_data = json.loads(chunk.get("bytes").decode())
                        yield self.parse_response(chunk_data, model_id)

        except ClientError as e:
            if e.response["Error"]["Code"] == "ValidationException":
                logger.warning(f"Model {model_id} does not support streaming")
                # Fall back to regular invoke
                response, _ = self.invoke_model(
                    prompt, model_id, system_prompt, **kwargs
                )
                yield response
            else:
                raise

    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """Get information about a specific model."""
        try:
            response = self.bedrock.get_foundation_model(modelIdentifier=model_id)
            model_details = response.get("modelDetails", {})

            return {
                "model_id": model_id,
                "model_name": model_details.get("modelName"),
                "provider": model_details.get("providerName"),
                "input_modalities": model_details.get("inputModalities", []),
                "output_modalities": model_details.get("outputModalities", []),
                "supported_languages": model_details.get("supportedLanguages", []),
                "max_tokens": self.MODEL_CONFIGS.get(model_id, {}).get("max_tokens"),
                "supports_streaming": model_details.get(
                    "responseStreamingSupported", False
                ),
            }
        except (ClientError, ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error getting model info for {model_id}: {e}")
            return {"model_id": model_id, "error": str(e)}

    def get_performance_stats(self) -> Dict[str, float]:
        """Get performance statistics."""
        if not self._request_times:
            return {
                "avg_latency": 0.0,
                "min_latency": 0.0,
                "max_latency": 0.0,
                "p95_latency": 0.0,
            }

        sorted_times = sorted(self._request_times)

        return {
            "avg_latency": sum(sorted_times) / len(sorted_times),
            "min_latency": sorted_times[0],
            "max_latency": sorted_times[-1],
            "p95_latency": sorted_times[int(len(sorted_times) * 0.95)],
        }

    def health_check(self) -> Dict[str, Any]:
        """Check Bedrock service health."""
        try:
            # Try to list models as a health check (no maxResults parameter supported)
            self.bedrock.list_foundation_models()

            return {
                "status": "healthy",
                "available_models": len(self._model_cache.get("available_models", [])),
                "performance": self.get_performance_stats(),
            }
        except (ClientError, ValueError, KeyError, AttributeError) as e:
            return {"status": "unhealthy", "error": str(e)}

    def __del__(self) -> None:
        """Cleanup resources."""
        if hasattr(self, "_executor"):
            self._executor.shutdown(wait=False)


# Module-level singleton instance
_bedrock_service_instance = None


def get_bedrock_service() -> BedrockService:
    """Get the singleton BedrockService instance."""
    global _bedrock_service_instance
    if _bedrock_service_instance is None:
        _bedrock_service_instance = BedrockService()
    return _bedrock_service_instance


# For backward compatibility
bedrock_service = get_bedrock_service
