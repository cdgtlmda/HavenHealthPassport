"""Base Medical Model.

Abstract base class for medical NLP models.
"""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import torch

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer


class BaseMedicalModel(ABC):
    """Abstract base class for medical NLP models."""

    def __init__(
        self,
        model_name: str,
        device: Optional[str] = None,
        max_length: int = 512,
        batch_size: int = 32,
    ):
        """Initialize medical model.

        Args:
            model_name: Name or path of the pre-trained model
            device: Device to use (cuda/cpu)
            max_length: Maximum sequence length
            batch_size: Batch size for processing
        """
        self.model_name = model_name
        self.max_length = max_length
        self.batch_size = batch_size

        # Set device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Initialize model and tokenizer
        self.tokenizer: Optional["PreTrainedTokenizer"] = None
        self.model: Optional["PreTrainedModel"] = None
        self._load_model()

    @abstractmethod
    def _load_model(self) -> None:
        """Load the pre-trained model and tokenizer."""

    @abstractmethod
    def encode(self, texts: List[str], return_tensors: bool = True) -> Dict[str, Any]:
        """Encode texts into embeddings.

        Args:
            texts: List of texts to encode
            return_tensors: Whether to return PyTorch tensors

        Returns:
            Dictionary containing embeddings and metadata
        """

    @abstractmethod
    def predict(
        self, texts: List[str], task: str = "classification"
    ) -> List[Dict[str, Any]]:
        """Make predictions on texts.

        Args:
            texts: List of texts to process
            task: Task type (classification, ner, etc.)

        Returns:
            List of predictions
        """

    def preprocess_texts(self, texts: List[str]) -> List[str]:
        """Preprocess texts before encoding."""
        processed = []
        for text in texts:
            # Basic preprocessing
            text = text.strip()
            # Truncate if too long
            if len(text.split()) > self.max_length * 0.8:
                words = text.split()[: int(self.max_length * 0.8)]
                text = " ".join(words)
            processed.append(text)
        return processed
