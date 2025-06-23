"""ClinicalBERT Model.

Clinical BERT model for clinical text processing.

HIPAA Compliance Notes:
- All PHI data processed by this module must be encrypted at rest and in transit
- Access to this module should be restricted to authorized healthcare personnel only
- Implement role-based access control (RBAC) for all clinical BERT model operations
- Audit logs must be maintained for all PHI access and processing operations
"""

from typing import Any, Dict, List, Optional

import torch
from transformers import AutoModel, AutoTokenizer

from .base import BaseMedicalModel


class ClinicalBERTModel(BaseMedicalModel):
    """Clinical BERT model implementation.

    Pre-trained on MIMIC-III clinical notes.
    """

    def __init__(
        self,
        model_name: str = "emilyalsentzer/Bio_ClinicalBERT",
        device: Optional[str] = None,
        max_length: int = 512,
        batch_size: int = 32,
    ):
        """Initialize Clinical BERT model."""
        super().__init__(model_name, device, max_length, batch_size)

    def _load_model(self) -> None:
        """Load Clinical BERT model and tokenizer."""
        try:
            self.logger.info("Loading Clinical BERT model: %s", self.model_name)

            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)

            # Load base model
            self.model = AutoModel.from_pretrained(self.model_name)
            if self.model is not None:
                self.model.to(self.device)  # type: ignore[union-attr]
                self.model.eval()  # type: ignore[union-attr]

            self.logger.info("Clinical BERT model loaded successfully")

        except Exception as e:
            self.logger.error("Failed to load Clinical BERT model: %s", e)
            raise

    def encode(self, texts: List[str], return_tensors: bool = True) -> Dict[str, Any]:
        """Encode clinical texts into embeddings.

        Args:
            texts: List of clinical texts
            return_tensors: Whether to return PyTorch tensors

        Returns:
            Dictionary with embeddings
        """
        # Check if model is initialized
        if self.tokenizer is None:
            raise RuntimeError("Tokenizer not initialized")

        # Preprocess clinical texts
        texts = self._preprocess_clinical_texts(texts)

        # Tokenize
        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )

        # Move to device
        input_ids = encoded["input_ids"].to(self.device)
        attention_mask = encoded["attention_mask"].to(self.device)

        # Get embeddings
        with torch.no_grad():
            if self.model is None:
                raise RuntimeError("Model not loaded")
            outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)  # type: ignore[operator]

        # Extract embeddings
        embeddings = outputs.last_hidden_state.mean(dim=1)  # Mean pooling

        return {
            "embeddings": embeddings if return_tensors else embeddings.cpu().numpy(),
            "shape": embeddings.shape,
        }

    def predict(
        self, texts: List[str], task: str = "embeddings"
    ) -> List[Dict[str, Any]]:
        """Make predictions on clinical texts."""
        if task == "embeddings":
            embeddings = self.encode(texts, return_tensors=False)
            return [{"embedding": emb} for emb in embeddings["embeddings"]]
        else:
            self.logger.warning("Task %s not implemented for Clinical BERT", task)
            return []

    def _preprocess_clinical_texts(self, texts: List[str]) -> List[str]:
        """Preprocess clinical texts."""
        processed = []
        for text in texts:
            # Remove PHI markers
            text = text.replace("[**", "").replace("**]", "")
            # Basic cleaning
            text = text.strip()
            processed.append(text)
        return processed
