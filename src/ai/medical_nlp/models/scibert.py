"""SciBERT Model.

SciBERT model for scientific text processing.
"""

from typing import Any, Dict, List, Optional

import torch
from transformers import AutoModel, AutoTokenizer

from .base import BaseMedicalModel


class SciBERTModel(BaseMedicalModel):
    """SciBERT model implementation.

    Pre-trained on scientific literature from Semantic Scholar.
    """

    def __init__(
        self,
        model_name: str = "allenai/scibert_scivocab_uncased",
        device: Optional[str] = None,
        max_length: int = 512,
        batch_size: int = 32,
    ):
        """Initialize SciBERT model.

        Args:
            model_name: SciBERT model variant
            device: Device to use
            max_length: Maximum sequence length
            batch_size: Batch size
        """
        super().__init__(model_name, device, max_length, batch_size)

    def _load_model(self) -> None:
        """Load SciBERT model and tokenizer."""
        try:
            self.logger.info("Loading SciBERT model: %s", self.model_name)

            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)

            # Load base model
            self.model = AutoModel.from_pretrained(self.model_name)
            if self.model is not None:
                self.model.to(self.device)  # type: ignore[union-attr]
                self.model.eval()  # type: ignore[union-attr]

            self.logger.info("SciBERT model loaded successfully")

        except Exception as e:
            self.logger.error("Failed to load SciBERT model: %s", e)
            raise

    def encode(self, texts: List[str], return_tensors: bool = True) -> Dict[str, Any]:
        """Encode scientific texts into embeddings.

        Args:
            texts: List of scientific texts
            return_tensors: Whether to return PyTorch tensors

        Returns:
            Dictionary with embeddings
        """
        # Preprocess texts
        texts = self.preprocess_texts(texts)

        all_embeddings: List[Any] = []

        # Check if model is initialized
        if self.tokenizer is None:
            raise RuntimeError("Tokenizer not initialized")

        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]

            # Tokenize
            encoded = self.tokenizer(
                batch_texts,
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

                # Use CLS token embeddings
                batch_embeddings = outputs.last_hidden_state[:, 0, :]
            all_embeddings.append(batch_embeddings)

        # Concatenate all embeddings
        embeddings = torch.cat(all_embeddings, dim=0)

        return {
            "embeddings": embeddings if return_tensors else embeddings.cpu().numpy(),
            "shape": embeddings.shape,
        }

    def predict(
        self, texts: List[str], task: str = "classification"
    ) -> List[Dict[str, Any]]:
        """Make predictions on scientific texts.

        Args:
            texts: List of texts to process
            task: Task type

        Returns:
            List of predictions
        """
        if task == "embeddings":
            embeddings = self.encode(texts, return_tensors=False)
            return [{"embedding": emb} for emb in embeddings["embeddings"]]
        elif task == "similarity":
            return self._predict_similarity(texts)
        else:
            # For other tasks, use base BERT approach
            self.logger.warning(
                "Task %s not specifically implemented for SciBERT", task
            )
            return []

    def _predict_similarity(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Calculate pairwise similarity between texts."""
        if len(texts) < 2:
            return []

        # Get embeddings
        embeddings_dict = self.encode(texts, return_tensors=True)
        embeddings = embeddings_dict["embeddings"]

        # Normalize embeddings
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

        # Calculate cosine similarity
        similarity_matrix = torch.mm(embeddings, embeddings.t())

        results = []
        for i, _ in enumerate(texts):
            for j in range(i + 1, len(texts)):
                results.append(
                    {
                        "text1": texts[i],
                        "text2": texts[j],
                        "similarity": float(similarity_matrix[i, j]),
                        "indices": (i, j),
                    }
                )

        return results
