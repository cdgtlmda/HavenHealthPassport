"""AWS Bedrock Embeddings Implementation.

Uses Amazon Bedrock's Titan embedding models for text vectorization.
"""

import base64
import json
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

import boto3
import numpy as np

from src.utils.retry import retry_with_backoff

from .base import BaseEmbeddingConfig, BaseHavenEmbedding, EmbeddingProvider

logger = logging.getLogger(__name__)


class TitanEmbeddingModel(str, Enum):
    """Available Titan embedding models."""

    TITAN_EMBED_TEXT_V1 = "amazon.titan-embed-text-v1"
    TITAN_EMBED_TEXT_V2 = "amazon.titan-embed-text-v2:0"
    TITAN_EMBED_G1_TEXT = "amazon.titan-embed-g1-text-02"
    TITAN_EMBED_IMAGE_V1 = "amazon.titan-embed-image-v1"


class BedrockEmbeddings(BaseHavenEmbedding):
    """AWS Bedrock embeddings using Titan models.

    Features:
    - Multiple Titan model support
    - Automatic dimension detection
    - Retry logic with exponential backoff
    - Regional failover support
    """

    def __init__(
        self,
        config: Optional[BaseEmbeddingConfig] = None,
        model_id: str = TitanEmbeddingModel.TITAN_EMBED_TEXT_V2,
        region_name: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Bedrock embeddings.

        Args:
            config: Embedding configuration
            model_id: Titan model ID
            region_name: AWS region
            aws_access_key_id: AWS access key (optional)
            aws_secret_access_key: AWS secret key (optional)
        """
        # Create default config if not provided
        if config is None:
            config = BaseEmbeddingConfig(
                provider=EmbeddingProvider.BEDROCK,
                model_name=model_id,
                dimension=self._get_model_dimension(model_id),
                batch_size=10,
                normalize=True,
            )

        super().__init__(config, **kwargs)

        # Initialize Bedrock client
        self.model_id = model_id
        self.region_name = region_name
        self._client = self._create_bedrock_client(
            region_name, aws_access_key_id, aws_secret_access_key
        )

        # Set up retry configuration
        # Note: Using retry_with_backoff decorator instead of RetryConfig
        self._max_retries = 3
        self._initial_delay = 1.0
        self._max_delay = 10.0

    def _create_bedrock_client(
        self,
        region_name: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ) -> boto3.client:
        """Create Bedrock runtime client."""
        client_kwargs = {"service_name": "bedrock-runtime", "region_name": region_name}

        if aws_access_key_id and aws_secret_access_key:
            client_kwargs.update(
                {
                    "aws_access_key_id": aws_access_key_id,
                    "aws_secret_access_key": aws_secret_access_key,
                }
            )

        return boto3.client(**client_kwargs)

    def _get_model_dimension(self, model_id: str) -> int:
        """Get embedding dimension for model."""
        dimensions = {
            TitanEmbeddingModel.TITAN_EMBED_TEXT_V1: 1536,
            TitanEmbeddingModel.TITAN_EMBED_TEXT_V2: 1024,
            TitanEmbeddingModel.TITAN_EMBED_G1_TEXT: 384,
            TitanEmbeddingModel.TITAN_EMBED_IMAGE_V1: 1024,
        }
        return int(dimensions.get(TitanEmbeddingModel(model_id), 1536))

    @property
    def _model_kwargs(self) -> Dict[str, Any]:
        """Get model-specific kwargs."""
        return {}

    async def _aget_query_embedding_impl(self, query: str) -> List[float]:
        """Get embedding for a single query."""

        @retry_with_backoff(
            max_retries=self._max_retries,
            initial_delay=self._initial_delay,
            max_delay=self._max_delay,
        )
        async def _invoke_model() -> List[float]:
            # Prepare request
            body = json.dumps({"inputText": query, **self._model_kwargs})

            # Invoke model
            response = self._client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )

            # Parse response
            response_body = json.loads(response["body"].read())

            # Extract embedding based on model
            if self.model_id == TitanEmbeddingModel.TITAN_EMBED_TEXT_V1:
                return response_body["embedding"]  # type: ignore[no-any-return]
            else:  # V2 and G1 models
                return response_body.get(  # type: ignore[no-any-return]
                    "embedding", response_body.get("embeddings", [])[0]
                )

        try:
            embedding = await _invoke_model()
            self.logger.debug("Generated embedding for query using %s", self.model_id)
            return embedding
        except Exception as e:
            self.logger.error("Failed to generate embedding: %s", e)
            raise

    async def _aget_text_embeddings_impl(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts."""
        embeddings = []

        # Titan models don't support batch embedding, so process one by one
        for text in texts:
            embedding = await self._aget_query_embedding_impl(text)
            embeddings.append(embedding)

        return embeddings

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        return {
            "provider": "AWS Bedrock",
            "model_id": self.model_id,
            "dimension": self.config.dimension,
            "region": self.region_name,
            "supports_batch": False,
            "max_input_length": 8192 if "v2" in self.model_id else 512,
        }

    def _get_text_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text - required by llama_index BaseEmbedding."""
        import asyncio

        return asyncio.run(self._aget_query_embedding_impl(text))


class BedrockMultimodalEmbeddings(BedrockEmbeddings):
    """Bedrock embeddings with multimodal support (text + image).

    Uses Titan Multimodal Embeddings for medical images and documents.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize multimodal embeddings."""
        kwargs["model_id"] = TitanEmbeddingModel.TITAN_EMBED_IMAGE_V1
        super().__init__(**kwargs)

    async def _aget_image_embedding(self, image_data: bytes) -> List[float]:
        """Get embedding for an image."""
        # Encode image to base64
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        # Prepare request
        body = json.dumps({"inputImage": image_base64, **self._model_kwargs})

        # Invoke model
        response = self._client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )

        # Parse response
        response_body = json.loads(response["body"].read())
        return list(response_body["embedding"])

    async def get_multimodal_embedding(
        self, text: Optional[str] = None, image_data: Optional[bytes] = None
    ) -> List[float]:
        """Get embedding for text, image, or both."""
        if text and image_data:
            # Combine text and image embeddings
            text_emb = await self._aget_query_embedding_impl(text)
            image_emb = await self._aget_image_embedding(image_data)

            # Average the embeddings (simple fusion)
            combined = np.mean([text_emb, image_emb], axis=0)
            return list(combined.tolist())

        elif text:
            return await self._aget_query_embedding_impl(text)

        elif image_data:
            return await self._aget_image_embedding(image_data)

        else:
            raise ValueError("Either text or image_data must be provided")
