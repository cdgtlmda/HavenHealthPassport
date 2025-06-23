"""BioBERT Model.

BioBERT model for biomedical text processing.
"""

from typing import Any, Dict, List, Optional

import torch
from transformers import (
    AutoModel,
    AutoModelForSequenceClassification,
    AutoModelForTokenClassification,
    AutoTokenizer,
)

from .base import BaseMedicalModel


class BioBERTModel(BaseMedicalModel):
    """BioBERT model implementation.

    Pre-trained on biomedical literature (PubMed abstracts, PMC full texts).
    """

    def __init__(
        self,
        model_name: str = "dmis-lab/biobert-v1.1",
        device: Optional[str] = None,
        max_length: int = 512,
        batch_size: int = 32,
    ):
        """Initialize BioBERT model.

        Args:
            model_name: BioBERT model variant
            device: Device to use
            max_length: Maximum sequence length
            batch_size: Batch size
        """
        super().__init__(model_name, device, max_length, batch_size)
        self.classification_model: Optional[AutoModelForSequenceClassification] = None
        self.ner_model: Optional[AutoModelForTokenClassification] = None

    def _load_model(self) -> None:
        """Load BioBERT model and tokenizer."""
        try:
            self.logger.info("Loading BioBERT model: %s", self.model_name)

            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name, do_lower_case=True
            )

            # Load base model for embeddings
            self.model = AutoModel.from_pretrained(self.model_name)
            if self.model is not None:
                self.model.to(self.device)  # type: ignore[union-attr]
                self.model.eval()  # type: ignore[union-attr]

            self.logger.info("BioBERT model loaded successfully")

        except Exception as e:
            self.logger.error("Failed to load BioBERT model: %s", e)
            raise

    def encode(self, texts: List[str], return_tensors: bool = True) -> Dict[str, Any]:
        """Encode texts into embeddings using BioBERT.

        Args:
            texts: List of biomedical texts
            return_tensors: Whether to return PyTorch tensors

        Returns:
            Dictionary with embeddings and attention masks
        """
        # Check if model is initialized
        if self.tokenizer is None:
            raise RuntimeError("Tokenizer not initialized")

        # Preprocess texts
        texts = self.preprocess_texts(texts)

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

        # Extract embeddings (CLS token)
        embeddings = outputs.last_hidden_state[:, 0, :]

        result = {
            "embeddings": embeddings if return_tensors else embeddings.cpu().numpy(),
            "attention_mask": (
                attention_mask if return_tensors else attention_mask.cpu().numpy()
            ),
            "shape": embeddings.shape,
        }

        return result

    def predict(
        self, texts: List[str], task: str = "classification"
    ) -> List[Dict[str, Any]]:
        """Make predictions on biomedical texts.

        Args:
            texts: List of texts to process
            task: Task type (classification, ner)

        Returns:
            List of predictions
        """
        if task == "classification":
            return self._predict_classification(texts)
        elif task == "ner":
            return self._predict_ner(texts)
        elif task == "embeddings":
            embeddings = self.encode(texts, return_tensors=False)
            return [{"embedding": emb} for emb in embeddings["embeddings"]]
        else:
            raise ValueError(f"Unsupported task: {task}")

    def _predict_classification(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Predict document classification."""
        # Load classification model if not loaded
        if self.classification_model is None:
            self.classification_model = (
                AutoModelForSequenceClassification.from_pretrained(
                    self.model_name, num_labels=2  # Binary classification by default
                )
            )
            if hasattr(self.classification_model, "to"):
                self.classification_model.to(self.device)
            if hasattr(self.classification_model, "eval"):
                self.classification_model.eval()

        # Check if tokenizer is initialized
        if self.tokenizer is None:
            raise RuntimeError("Tokenizer not initialized")

        results: List[Dict[str, Any]] = []
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

            # Predict
            with torch.no_grad():
                if self.classification_model is None:
                    raise RuntimeError("Classification model not initialized")
                if hasattr(self.classification_model, "__call__"):
                    outputs = self.classification_model(
                        input_ids=input_ids, attention_mask=attention_mask
                    )
                else:
                    raise RuntimeError("Classification model is not callable")

                # Process predictions
                predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)

                for j, pred in enumerate(predictions):
                    results.append(
                        {
                            "text": batch_texts[j],
                            "label": int(torch.argmax(pred)),
                            "confidence": float(torch.max(pred)),
                            "probabilities": pred.cpu().numpy().tolist(),
                        }
                    )

        return results

    def _predict_ner(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Predict named entity recognition."""
        # Load NER model if not loaded
        if self.ner_model is None:
            # Use biomedical NER model
            ner_model_name = "dmis-lab/biobert-base-cased-v1.2-ner"
            self.ner_model = AutoModelForTokenClassification.from_pretrained(
                ner_model_name
            )
            if hasattr(self.ner_model, "to"):
                self.ner_model.to(self.device)
            if hasattr(self.ner_model, "eval"):
                self.ner_model.eval()

        # Check if tokenizer is initialized
        if self.tokenizer is None:
            raise RuntimeError("Tokenizer not initialized")

        results: List[Dict[str, Any]] = []
        for text in texts:
            # Tokenize
            encoded = self.tokenizer(
                text,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
                return_offsets_mapping=True,
            )

            # Move to device
            input_ids = encoded["input_ids"].to(self.device)
            attention_mask = encoded["attention_mask"].to(self.device)

            # Predict
            with torch.no_grad():
                if self.ner_model is None:
                    raise RuntimeError("NER model not initialized")
                if hasattr(self.ner_model, "__call__"):
                    outputs = self.ner_model(
                        input_ids=input_ids, attention_mask=attention_mask
                    )
                else:
                    raise RuntimeError("NER model is not callable")

                # Process predictions
                predictions = torch.argmax(outputs.logits, dim=2)

                # Convert to entities
                entities: List[Dict[str, Any]] = []
                if self.tokenizer is None:
                    raise RuntimeError("Tokenizer not initialized")
                tokens = self.tokenizer.convert_ids_to_tokens(input_ids[0])

                for idx, (token, pred) in enumerate(zip(tokens, predictions[0])):
                    if pred != 0:  # Non-O tag
                        entities.append(
                            {"token": token, "label": int(pred), "position": idx}
                        )

                results.append(
                    {"text": text, "entities": entities, "token_count": len(tokens)}
                )

        return results
