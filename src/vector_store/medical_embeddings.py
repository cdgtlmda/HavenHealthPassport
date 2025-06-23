"""Medical Embedding Service for healthcare domain-specific embeddings."""

import hashlib
from typing import Any, Dict, List, Optional, TypedDict

import numpy as np
import torch

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.utils.logging import get_logger

from .base import BaseEmbeddingService

logger = get_logger(__name__)

# Try to import transformers and sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    from transformers import AutoModel, AutoTokenizer

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning(
        "Transformers/Sentence-transformers not available. Install with: pip install transformers sentence-transformers torch"
    )


class MedicalModelInfo(TypedDict):
    """Type definition for medical model information."""

    name: str
    type: str
    dimension: int
    description: str


class MedicalEmbeddingService(BaseEmbeddingService):
    """Service for generating medical domain-specific embeddings."""

    # Ranked list of models to try
    MEDICAL_MODELS: List[MedicalModelInfo] = [
        {
            "name": "pritamdeka/S-PubMedBert-MS-MARCO",
            "type": "sentence-transformer",
            "dimension": 768,
            "description": "Sentence transformer fine-tuned on medical text",
        },
        {
            "name": "emilyalsentzer/Bio_ClinicalBERT",
            "type": "transformer",
            "dimension": 768,
            "description": "BERT trained on clinical notes from MIMIC-III",
        },
        {
            "name": "dmis-lab/biobert-v1.1",
            "type": "transformer",
            "dimension": 768,
            "description": "BERT trained on PubMed abstracts and PMC full texts",
        },
        {
            "name": "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext",
            "type": "transformer",
            "dimension": 768,
            "description": "Microsoft's PubMedBERT trained on biomedical literature",
        },
    ]

    def __init__(
        self,
        model_name: Optional[str] = None,
        cache_enabled: bool = True,
        device: Optional[str] = None,
    ):
        """Initialize the medical embedding service.

        Args:
            model_name: Specific model name to use (optional)
            cache_enabled: Whether to cache embeddings
            device: Device to use ('cuda', 'cpu', or None for auto-detect)
        """
        self.cache_enabled = cache_enabled
        self._embedding_cache: Dict[str, np.ndarray] = {}
        self._model: Optional[Any] = None
        self._tokenizer: Optional[Any] = None
        self.model_type: Optional[str] = None
        self.model_name = model_name
        self._dimension = 768  # Default, will be updated based on model
        self._model_initialized = False  # Track initialization status

        # Set device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # Initialize the medical BERT model
        self._initialize_model()

    def _initialize_model(self) -> None:
        """Initialize the medical BERT model."""
        if not TRANSFORMERS_AVAILABLE:
            logger.error("Transformers not available. Using fallback embeddings.")
            self._model_initialized = False
            return

        # If specific model requested, try to load it
        if self.model_name:
            success = self._try_load_model(self.model_name)
            if success:
                return
            else:
                logger.warning(
                    f"Failed to load requested model: {self.model_name}. Trying alternatives..."
                )

        # Try loading models in order of preference
        for model_info in self.MEDICAL_MODELS:
            if self._try_load_model(str(model_info["name"]), str(model_info["type"])):
                self._dimension = int(model_info["dimension"])
                logger.info(f"Successfully loaded: {model_info['description']}")
                return

        # If all models fail, set flag
        logger.error("Failed to load any medical embedding model. Using fallback.")
        self._model_initialized = False

    def _try_load_model(
        self, model_name: str, model_type: Optional[str] = None
    ) -> bool:
        """Try to load a specific model.

        Args:
            model_name: Model name/path
            model_type: Type of model ('sentence-transformer' or 'transformer')

        Returns:
            True if successful, False otherwise
        """
        try:
            # Auto-detect model type if not specified
            if model_type is None:
                if "sentence" in model_name.lower() or "S-" in model_name:
                    model_type = "sentence-transformer"
                else:
                    model_type = "transformer"

            if model_type == "sentence-transformer":
                # Load sentence transformer
                self._model = SentenceTransformer(model_name, device=self.device)
                self.model_type = "sentence-transformer"
                self.model_name = model_name
                self._model_initialized = True
                logger.info(f"Loaded sentence transformer: {model_name}")
                return True

            else:
                # Load standard transformer
                self._tokenizer = AutoTokenizer.from_pretrained(model_name)
                self._model = AutoModel.from_pretrained(model_name)
                self._model.to(self.device)
                self._model.eval()
                self.model_type = "transformer"
                self.model_name = model_name
                self._model_initialized = True
                logger.info(f"Loaded transformer model: {model_name}")
                return True

        except (TypeError, ValueError) as e:
            # Catch all exceptions during model loading to prevent crashes
            logger.debug(f"Failed to load {model_name}: {e}")
            return False

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.sha256(text.encode()).hexdigest()

    @require_phi_access(AccessLevel.READ)
    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for medical text.

        Args:
            text: Medical text to embed

        Returns:
            Embedding vector
        """
        if not text:
            raise ValueError("Text cannot be empty")

        # Check cache if enabled
        if self.cache_enabled:
            cache_key = self._get_cache_key(text)
            if cache_key in self._embedding_cache:
                logger.debug(f"Using cached embedding for text hash: {cache_key}")
                return self._embedding_cache[cache_key].copy()

        try:
            # Preprocess medical text
            processed_text = self._preprocess_medical_text(text)

            # Generate embedding based on model type
            if hasattr(self, "_model_initialized") and self._model_initialized:
                embedding = self._generate_real_embedding(processed_text)
            else:
                # Fallback to deterministic embedding if no model loaded
                logger.warning("Using fallback embedding generation")
                embedding = self._generate_fallback_embedding(processed_text)

            # Cache if enabled
            if self.cache_enabled:
                self._embedding_cache[cache_key] = embedding.copy()

            return embedding

        except (RuntimeError, TypeError, ValueError) as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def _preprocess_medical_text(self, text: str) -> str:
        """Preprocess medical text for embedding.

        Args:
            text: Raw medical text

        Returns:
            Preprocessed text
        """
        # Basic preprocessing - keep original case for BERT models
        text = text.strip()

        # Expand common medical abbreviations
        abbreviations = {
            " bp ": " blood pressure ",
            " hr ": " heart rate ",
            " temp ": " temperature ",
            " rx ": " prescription ",
            " hx ": " history ",
            " dx ": " diagnosis ",
            " tx ": " treatment ",
            " sx ": " symptoms ",
            " pt ": " patient ",
            " w/ ": " with ",
            " w/o ": " without ",
            " yo ": " year old ",
            " y/o ": " year old ",
            " htn ": " hypertension ",
            " dm ": " diabetes mellitus ",
            " copd ": " chronic obstructive pulmonary disease ",
            " chf ": " congestive heart failure ",
            " mi ": " myocardial infarction ",
            " cva ": " cerebrovascular accident ",
            " uti ": " urinary tract infection ",
            " uri ": " upper respiratory infection ",
            " gi ": " gastrointestinal ",
            " cv ": " cardiovascular ",
        }

        # Apply abbreviation expansion (case insensitive)
        text_lower = text.lower()
        for abbr, full in abbreviations.items():
            if abbr in text_lower:
                # Find and replace preserving case where possible
                text = text.replace(abbr.strip(), full.strip())
                text = text.replace(abbr.strip().upper(), full.strip())

        return text

    def _generate_real_embedding(self, text: str) -> np.ndarray:
        """Generate embedding using the loaded model.

        Args:
            text: Preprocessed text

        Returns:
            Embedding vector
        """
        with torch.no_grad():
            if self.model_type == "sentence-transformer" and self._model:
                # Use sentence transformer encode method
                embedding = self._model.encode(
                    text, convert_to_numpy=True, normalize_embeddings=True
                )
                return embedding.astype(np.float32)  # type: ignore[no-any-return]

            # Use standard transformer
            # Tokenize
            inputs = self._tokenizer(  # type: ignore[misc]
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True,
            ).to(self.device)

            # Get model outputs
            outputs = self._model(**inputs)  # type: ignore[misc]

            # Use CLS token embedding (first token)
            cls_embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()[0]

            # Normalize
            cls_embedding = cls_embedding / np.linalg.norm(cls_embedding)

            return cls_embedding.astype(np.float32)  # type: ignore[no-any-return]

    def _generate_fallback_embedding(self, text: str) -> np.ndarray:
        """Generate fallback embedding when no model is available.

        Args:
            text: Preprocessed text

        Returns:
            Deterministic embedding vector
        """
        # Generate deterministic embedding based on text
        # This ensures same text always produces same embedding
        np.random.seed(hash(text) % 2**32)
        embedding = np.random.randn(self._dimension).astype(np.float32)

        # Add some text-based features
        # Length feature
        embedding[0] = len(text) / 1000.0

        # Character diversity
        unique_chars = len(set(text.lower()))
        embedding[1] = unique_chars / 100.0

        # Medical term presence
        medical_terms = [
            "diagnosis",
            "treatment",
            "patient",
            "symptoms",
            "medication",
            "disease",
            "condition",
            "therapy",
            "clinical",
            "medical",
        ]
        medical_count = sum(1 for term in medical_terms if term in text.lower())
        embedding[2] = medical_count / 10.0

        # Normalize to unit vector
        embedding = embedding / np.linalg.norm(embedding)

        return embedding

    @require_phi_access(AccessLevel.READ)
    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of medical texts

        Returns:
            List of embedding vectors
        """
        if (
            hasattr(self, "_model_initialized")
            and self._model_initialized
            and self.model_type == "sentence-transformer"
            and self._model
        ):
            # Use efficient batch encoding for sentence transformers
            try:
                processed_texts = [
                    self._preprocess_medical_text(text) for text in texts
                ]
                embeddings = self._model.encode(
                    processed_texts,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    batch_size=32,
                    show_progress_bar=False,
                )
                return [emb.astype(np.float32) for emb in embeddings]
            except (AttributeError, TypeError, ValueError) as e:
                logger.error(f"Batch encoding failed: {e}")
                # Fall through to individual encoding

        # Default: encode individually
        embeddings = []
        for text in texts:
            try:
                embedding = self.embed(text)
                embeddings.append(embedding)
            except (
                AttributeError,
                TypeError,
                ValueError,
            ) as e:
                logger.error(f"Failed to embed text in batch: {e}")
                # Return zero vector for failed embeddings
                embeddings.append(np.zeros(self._dimension, dtype=np.float32))

        return embeddings

    def get_dimension(self) -> int:
        """Get the dimension of embeddings produced.

        Returns:
            Embedding dimension
        """
        return self._dimension

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        if self.cache_enabled:
            self._embedding_cache.clear()
            logger.info("Embedding cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        return {
            "cache_enabled": self.cache_enabled,
            "cache_size": len(self._embedding_cache),
            "model_name": self.model_name,
            "model_type": self.model_type,
            "dimension": self._dimension,
            "device": self.device,
            "model_loaded": hasattr(self, "_model_initialized")
            and self._model_initialized,
        }

    def get_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Cosine similarity score (0-1)
        """
        # Ensure unit vectors
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Calculate cosine similarity
        similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)

        # Ensure in valid range
        return float(np.clip(similarity, -1.0, 1.0))
