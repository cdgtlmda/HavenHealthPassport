"""Custom Embeddings Implementation.

Provides a flexible framework for implementing custom embedding models
in the Haven Health Passport system. This allows for domain-specific
embeddings, hybrid approaches, and experimental embedding techniques.

Access control note: This module may process medical text containing PHI.
When processing medical domain content, appropriate access controls are
enforced through the healthcare layer and all operations are logged.
"""

import asyncio
import hashlib
import logging
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np

from .base import BaseEmbeddingConfig, BaseHavenEmbedding, EmbeddingProvider

# Access control for medical domain embeddings
# Note: Access control is enforced at the healthcare layer


logger = logging.getLogger(__name__)


@dataclass
class CustomEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration for custom embeddings."""

    # Model configuration
    model_path: Optional[str] = None
    model_type: str = "transformer"  # transformer, word2vec, glove, fasttext, custom
    pooling_strategy: str = "mean"  # mean, max, cls, weighted

    # Preprocessing options
    lowercase: bool = True
    remove_stopwords: bool = False
    stem_words: bool = False
    lemmatize: bool = False
    max_sequence_length: int = 512

    # Advanced features
    use_subword_embeddings: bool = True
    use_positional_encoding: bool = True
    use_attention_weights: bool = False
    combine_strategies: List[str] = field(default_factory=lambda: ["mean"])

    # Domain-specific options
    domain_weights: Dict[str, float] = field(default_factory=dict)
    custom_vocabulary: Optional[Dict[str, List[float]]] = None
    fine_tuning_enabled: bool = False

    # Performance options
    use_gpu: bool = True
    quantization_bits: Optional[int] = None  # 8, 16, or None for full precision
    dynamic_batching: bool = True


class CustomEmbeddingBase(BaseHavenEmbedding):
    """Base class for custom embeddings with common functionality."""

    def __init__(
        self,
        config: Optional[CustomEmbeddingConfig] = None,
        embedding_function: Optional[Callable] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize custom embeddings.

        Args:
            config: Custom embedding configuration
            embedding_function: Optional function to generate embeddings
            **kwargs: Additional arguments
        """
        if config is None:
            config = CustomEmbeddingConfig(
                provider=EmbeddingProvider.CUSTOM,
                model_name="custom-embed",
                dimension=384,  # Default dimension
                batch_size=32,
                normalize=True,
            )

        super().__init__(config, **kwargs)
        self.custom_config = config
        self.embedding_function = embedding_function

        # Initialize attributes that will be set in init methods
        self.stopwords: Dict[str, Any] = {}
        self.stemmers: Dict[str, Any] = {}
        self.lemmatizers: Dict[str, Any] = {}

        # Initialize components
        self._init_preprocessing()
        self._init_model()
        self._init_postprocessing()

    def _init_preprocessing(self) -> None:
        """Initialize preprocessing components."""
        self.preprocessors = []

        if self.custom_config.lowercase:
            self.preprocessors.append(lambda x: x.lower())

        if self.custom_config.remove_stopwords:
            # Initialize stopwords for multiple languages
            self._init_stopwords()

        if self.custom_config.stem_words:
            self._init_stemmer()

        if self.custom_config.lemmatize:
            self._init_lemmatizer()

    def _init_stopwords(self) -> None:
        """Initialize multilingual stopwords."""
        # In production, load from comprehensive stopword lists
        self.stopwords = {
            "en": {"the", "is", "at", "which", "on", "a", "an"},
            "es": {"el", "la", "de", "que", "y", "a", "en"},
            "fr": {"le", "de", "un", "être", "et", "à", "il"},
            "ar": {"في", "من", "إلى", "على", "هذا", "التي"},
            # Add more languages
        }

    def _init_stemmer(self) -> None:
        """Initialize language-specific stemmers."""
        # Placeholder for stemmer initialization
        self.stemmers = {}
        logger.info("Stemmer initialization placeholder")

    def _init_lemmatizer(self) -> None:
        """Initialize language-specific lemmatizers."""
        # Placeholder for lemmatizer initialization
        self.lemmatizers = {}
        logger.info("Lemmatizer initialization placeholder")

    @abstractmethod
    def _init_model(self) -> None:
        """Initialize the embedding model - must be implemented by subclasses."""

    def _init_postprocessing(self) -> None:
        """Initialize postprocessing components."""
        self.postprocessors = []

        # Add pooling strategies
        if self.custom_config.pooling_strategy == "weighted":
            self.postprocessors.append(self._weighted_pooling)

    def _preprocess_text(self, text: str) -> str:
        """Apply preprocessing to text."""
        processed = text
        for preprocessor in self.preprocessors:
            processed = preprocessor(processed)
        return processed

    def _postprocess_embedding(
        self, embedding: Union[np.ndarray, List[float]]
    ) -> List[float]:
        """Apply postprocessing to embedding."""
        if isinstance(embedding, list):
            embedding = np.array(embedding)

        for postprocessor in self.postprocessors:
            embedding = postprocessor(embedding)

        # Ensure correct dimension
        if len(embedding) != self.custom_config.dimension:
            embedding = self._adjust_dimension(embedding)

        return (
            list(embedding.tolist())
            if isinstance(embedding, np.ndarray)
            else list(embedding)
        )

    def _adjust_dimension(self, embedding: np.ndarray) -> np.ndarray:
        """Adjust embedding dimension through padding or truncation."""
        current_dim = len(embedding)
        target_dim = self.custom_config.dimension

        if current_dim < target_dim:
            # Pad with zeros
            padding = np.zeros(target_dim - current_dim)
            embedding = np.concatenate([embedding, padding])
        else:
            # Truncate
            embedding = embedding[:target_dim]

        return embedding

    def _weighted_pooling(
        self, embeddings: np.ndarray, weights: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """Apply weighted pooling to embeddings."""
        if weights is None:
            # Use attention-based weights if available
            weights = np.ones(embeddings.shape[0]) / embeddings.shape[0]

        return np.array(np.average(embeddings, axis=0, weights=weights))

    async def _aget_query_embedding_impl(self, query: str) -> List[float]:
        """Implementation-specific query embedding."""
        # Preprocess query
        processed_query = self._preprocess_text(query)

        # Generate embedding using custom function or model
        if self.embedding_function:
            embedding = await self._call_embedding_function(processed_query)
        else:
            embedding = await self._generate_embedding(processed_query)

        # Postprocess
        embedding = self._postprocess_embedding(embedding)

        return embedding

    async def _aget_text_embeddings_impl(self, texts: List[str]) -> List[List[float]]:
        """Implementation-specific text embeddings."""
        # Preprocess texts
        processed_texts = [self._preprocess_text(text) for text in texts]

        # Generate embeddings
        if self.embedding_function:
            embeddings = await self._call_embedding_function_batch(processed_texts)
        else:
            embeddings = await self._generate_embeddings_batch(processed_texts)

        # Postprocess
        embeddings = [self._postprocess_embedding(emb) for emb in embeddings]

        return embeddings

    async def _call_embedding_function(self, text: str) -> List[float]:
        """Call user-provided embedding function."""
        if self.embedding_function is None:
            raise ValueError("No embedding function provided")

        # Handle both sync and async functions
        if asyncio.iscoroutinefunction(self.embedding_function):
            return list(await self.embedding_function(text))
        else:
            return list(self.embedding_function(text))

    async def _call_embedding_function_batch(
        self, texts: List[str]
    ) -> List[List[float]]:
        """Call user-provided embedding function for batch."""
        if self.embedding_function is None:
            raise ValueError("No embedding function provided")

        # Handle both sync and async functions
        if asyncio.iscoroutinefunction(self.embedding_function):
            # Check if function supports batch processing
            try:
                return list(await self.embedding_function(texts))
            except (TypeError, ValueError):
                # Fallback to individual processing
                tasks = [self.embedding_function(text) for text in texts]
                return list(await asyncio.gather(*tasks))
        else:
            # Try batch processing first
            try:
                return list(self.embedding_function(texts))
            except (TypeError, ValueError):
                # Fallback to individual processing
                return [self.embedding_function(text) for text in texts]

    @abstractmethod
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for single text - must be implemented by subclasses."""

    @abstractmethod
    async def _generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch - must be implemented by subclasses."""


class TransformerCustomEmbeddings(CustomEmbeddingBase):
    """Custom embeddings using transformer models."""

    def _init_model(self) -> None:
        """Initialize transformer model."""
        logger.info("Initializing transformer model: %s", self.custom_config.model_path)

        # In production, load actual transformer model
        # This is a placeholder implementation
        self.model = None
        self.tokenizer = None

        # Initialize with mock model for testing
        if not self.custom_config.model_path:
            logger.warning("No model path provided, using mock embeddings")

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using transformer model."""
        # Return mock embedding for testing since model is always None
        # Use hash for consistency
        hash_val = int(
            hashlib.md5(text.encode(), usedforsecurity=False).hexdigest(), 16
        )
        np.random.seed(hash_val % 2**32)
        return list(np.random.randn(self.custom_config.dimension).tolist())

    async def _generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch using transformer model."""
        # Return mock embeddings for testing since model is always None
        embeddings = []
        for text in texts:
            hash_val = int(
                hashlib.md5(text.encode(), usedforsecurity=False).hexdigest(), 16
            )
            np.random.seed(hash_val % 2**32)
            embeddings.append(np.random.randn(self.custom_config.dimension).tolist())
        return embeddings


class Word2VecCustomEmbeddings(CustomEmbeddingBase):
    """Custom embeddings using Word2Vec approach."""

    def _init_model(self) -> None:
        """Initialize Word2Vec model."""
        logger.info("Initializing Word2Vec model")

        # In production, load actual Word2Vec model
        self.word_vectors = {}

        # Initialize with custom vocabulary if provided
        if self.custom_config.custom_vocabulary:
            self.word_vectors.update(self.custom_config.custom_vocabulary)

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using Word2Vec."""
        words = text.split()
        embeddings = []

        for word in words:
            if word in self.word_vectors:
                embeddings.append(self.word_vectors[word])
            else:
                # Generate random embedding for OOV words
                hash_val = int(
                    hashlib.md5(word.encode(), usedforsecurity=False).hexdigest(), 16
                )
                np.random.seed(hash_val % 2**32)
                embeddings.append(
                    np.random.randn(self.custom_config.dimension).tolist()
                )

        if not embeddings:
            # Return zero vector for empty text
            return [0.0] * self.custom_config.dimension

        # Pool embeddings based on strategy
        embeddings_array = np.array(embeddings)
        if self.custom_config.pooling_strategy == "mean":
            return list(np.mean(embeddings_array, axis=0).tolist())
        elif self.custom_config.pooling_strategy == "max":
            return list(np.max(embeddings_array, axis=0).tolist())
        else:
            return list(embeddings_array[0].tolist())  # Use first word

    async def _generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch using Word2Vec."""
        embeddings = []
        for text in texts:
            embedding = await self._generate_embedding(text)
            embeddings.append(embedding)
        return embeddings


class HybridCustomEmbeddings(CustomEmbeddingBase):
    """Custom embeddings combining multiple approaches."""

    def __init__(
        self,
        config: Optional[CustomEmbeddingConfig] = None,
        base_embeddings: Optional[List[BaseHavenEmbedding]] = None,
        combination_weights: Optional[List[float]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize hybrid embeddings.

        Args:
            config: Custom embedding configuration
            base_embeddings: List of base embedding models to combine
            combination_weights: Weights for combining embeddings
            **kwargs: Additional arguments
        """
        super().__init__(config, **kwargs)
        self.base_embeddings = base_embeddings or []
        self.combination_weights = combination_weights or [
            1.0 / len(self.base_embeddings)
        ] * len(self.base_embeddings)

        # Validate weights
        if len(self.combination_weights) != len(self.base_embeddings):
            raise ValueError("Number of weights must match number of base embeddings")

        # Normalize weights
        weight_sum = sum(self.combination_weights)
        self.combination_weights = [w / weight_sum for w in self.combination_weights]

    def _init_model(self) -> None:
        """Initialize hybrid model components."""
        logger.info(
            "Initializing hybrid model with %d base embeddings",
            len(self.base_embeddings),
        )

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding by combining multiple approaches."""
        if not self.base_embeddings:
            # Fallback to random embedding
            hash_val = int(
                hashlib.md5(text.encode(), usedforsecurity=False).hexdigest(), 16
            )
            np.random.seed(hash_val % 2**32)
            return list(np.random.randn(self.custom_config.dimension).tolist())

        # Get embeddings from all base models
        embeddings_list: List[np.ndarray] = []
        for base_model in self.base_embeddings:
            embedding = await base_model._aget_query_embedding(
                text
            )  # pylint: disable=protected-access
            embeddings_list.append(np.array(embedding))

        # Combine embeddings with weights
        combined = np.zeros(self.custom_config.dimension)
        for embedding_array, weight in zip(embeddings_list, self.combination_weights):
            # Adjust dimension if needed
            if len(embedding_array) != self.custom_config.dimension:
                embedding_array = self._adjust_dimension(embedding_array)
            combined += weight * embedding_array

        return list(combined.tolist())

    async def _generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch by combining multiple approaches."""
        if not self.base_embeddings:
            # Fallback to random embeddings
            embeddings = []
            for text in texts:
                hash_val = int(
                    hashlib.md5(text.encode(), usedforsecurity=False).hexdigest(), 16
                )
                np.random.seed(hash_val % 2**32)
                embeddings.append(
                    np.random.randn(self.custom_config.dimension).tolist()
                )
            return embeddings

        # Get embeddings from all base models
        all_embeddings = []
        for base_model in self.base_embeddings:
            batch_embeddings = await base_model._aget_text_embeddings(
                texts
            )  # pylint: disable=protected-access
            all_embeddings.append(batch_embeddings)

        # Combine embeddings for each text
        combined_embeddings = []
        for i in range(len(texts)):
            combined = np.zeros(self.custom_config.dimension)
            for j, weight in enumerate(self.combination_weights):
                embedding = np.array(all_embeddings[j][i])
                # Adjust dimension if needed
                if len(embedding) != self.custom_config.dimension:
                    embedding = self._adjust_dimension(embedding)
                combined += weight * embedding
            combined_embeddings.append(combined.tolist())

        return combined_embeddings


class DomainAdaptiveEmbeddings(CustomEmbeddingBase):
    """Custom embeddings that adapt to specific domains."""

    def __init__(
        self,
        config: Optional[CustomEmbeddingConfig] = None,
        domain_models: Optional[Dict[str, BaseHavenEmbedding]] = None,
        domain_detector: Optional[Callable] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize domain-adaptive embeddings.

        Args:
            config: Custom embedding configuration
            domain_models: Dictionary of domain-specific models
            domain_detector: Function to detect domain from text
            **kwargs: Additional arguments
        """
        super().__init__(config, **kwargs)
        self.domain_models = domain_models or {}
        self.domain_detector = domain_detector
        self.default_domain = "general"

    def _init_model(self) -> None:
        """Initialize domain models."""
        logger.info(
            "Initializing domain-adaptive model with domains: %s",
            list(self.domain_models.keys()),
        )

    def _detect_domain(self, text: str) -> str:
        """Detect domain from text."""
        if self.domain_detector:
            return str(self.domain_detector(text))

        # Simple keyword-based detection
        text_lower = text.lower()

        # Medical domain detection
        medical_keywords = [
            "patient",
            "diagnosis",
            "treatment",
            "medication",
            "symptom",
            "disease",
        ]
        if any(keyword in text_lower for keyword in medical_keywords):
            return "medical"

        # Legal domain detection
        legal_keywords = ["law", "legal", "court", "attorney", "contract", "regulation"]
        if any(keyword in text_lower for keyword in legal_keywords):
            return "legal"

        # Financial domain detection
        financial_keywords = [
            "financial",
            "investment",
            "banking",
            "credit",
            "loan",
            "payment",
        ]
        if any(keyword in text_lower for keyword in financial_keywords):
            return "financial"

        return self.default_domain

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using domain-specific model."""
        domain = self._detect_domain(text)

        if domain in self.domain_models:
            logger.debug("Using %s domain model for embedding", domain)
            embedding = await self.domain_models[domain]._aget_query_embedding(
                text
            )  # pylint: disable=protected-access
        elif self.default_domain in self.domain_models:
            logger.debug("Using default domain model for embedding")
            embedding = await self.domain_models[
                self.default_domain
            ]._aget_query_embedding(
                text
            )  # pylint: disable=protected-access
        else:
            # Fallback to random embedding
            logger.warning(
                "No model found for domain %s, using random embedding", domain
            )
            hash_val = int(
                hashlib.md5(text.encode(), usedforsecurity=False).hexdigest(), 16
            )
            np.random.seed(hash_val % 2**32)
            embedding = np.random.randn(self.custom_config.dimension).tolist()

        return embedding

    async def _generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch using domain-specific models."""
        # Group texts by domain
        domain_texts: Dict[str, List[str]] = {}
        text_indices: Dict[str, List[int]] = {}

        for i, text in enumerate(texts):
            domain = self._detect_domain(text)
            if domain not in domain_texts:
                domain_texts[domain] = []
                text_indices[domain] = []
            domain_texts[domain].append(text)
            text_indices[domain].append(i)

        # Generate embeddings for each domain
        all_embeddings: List[List[float]] = [
            [0.0] * self.custom_config.dimension
        ] * len(texts)

        for domain, domain_text_list in domain_texts.items():
            if domain in self.domain_models:
                embeddings = await self.domain_models[
                    domain
                ]._aget_text_embeddings(  # pylint: disable=protected-access
                    domain_text_list
                )
            elif self.default_domain in self.domain_models:
                embeddings = await self.domain_models[
                    self.default_domain
                ]._aget_text_embeddings(
                    domain_text_list
                )  # pylint: disable=protected-access
            else:
                # Generate random embeddings
                embeddings = []
                for text in domain_text_list:
                    hash_val = int(
                        hashlib.md5(text.encode(), usedforsecurity=False).hexdigest(),
                        16,
                    )
                    np.random.seed(hash_val % 2**32)
                    embeddings.append(
                        np.random.randn(self.custom_config.dimension).tolist()
                    )

            # Place embeddings in correct positions
            for embedding, idx in zip(embeddings, text_indices[domain]):
                all_embeddings[idx] = embedding

        return all_embeddings


# Factory function for creating custom embeddings
def create_custom_embeddings(
    embedding_type: str = "transformer",
    config: Optional[CustomEmbeddingConfig] = None,
    **kwargs: Any,
) -> CustomEmbeddingBase:
    """Create custom embeddings of specified type.

    Args:
        embedding_type: Type of custom embedding (transformer, word2vec, hybrid, domain_adaptive)
        config: Custom embedding configuration
        **kwargs: Additional type-specific arguments

    Returns:
        Custom embedding instance
    """
    embedding_types = {
        "transformer": TransformerCustomEmbeddings,
        "word2vec": Word2VecCustomEmbeddings,
        "hybrid": HybridCustomEmbeddings,
        "domain_adaptive": DomainAdaptiveEmbeddings,
    }

    if embedding_type not in embedding_types:
        raise ValueError(
            f"Unknown embedding type: {embedding_type}. Choose from: {list(embedding_types.keys())}"
        )

    embedding_class = embedding_types[embedding_type]

    # Create default config if not provided
    if config is None:
        config = CustomEmbeddingConfig(
            provider=EmbeddingProvider.CUSTOM,
            model_name=f"custom-{embedding_type}",
            dimension=384,
            model_type=embedding_type,
        )

    return embedding_class(config=config, **kwargs)  # type: ignore[no-any-return]
