"""Inference script for cultural adaptation models.

This script handles real-time inference for cultural pattern detection
in healthcare communications.
"""

import json
import logging
import os
from typing import Any, Dict

import torch
import torch.nn as nn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CulturalPatternClassifier(nn.Module):
    """Multi-label classifier for cultural patterns."""

    def __init__(self, base_model: Any, num_labels: int) -> None:
        """Initialize the cultural pattern classifier."""
        super().__init__()
        self.base_model = base_model
        self.dropout = nn.Dropout(0.3)
        self.classifier = nn.Linear(base_model.config.hidden_size, num_labels)
        self.sigmoid = nn.Sigmoid()

    def forward(
        self, input_ids: torch.Tensor, attention_mask: torch.Tensor
    ) -> torch.Tensor:
        """Forward pass through the model."""
        outputs = self.base_model(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.pooler_output
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)
        return torch.as_tensor(self.sigmoid(logits))


def model_fn(model_dir: str) -> Dict[str, Any]:
    """Load the model for inference."""
    logger.info("Loading model from %s", model_dir)

    # Load model configuration
    model_path = os.path.join(model_dir, "model.pth")
    checkpoint = torch.load(model_path, map_location="cpu", weights_only=True)

    # Load tokenizer
    from transformers import AutoModel, AutoTokenizer  # noqa: PLC0415

    tokenizer = AutoTokenizer.from_pretrained("bert-base-multilingual-cased")
    base_model = AutoModel.from_pretrained("bert-base-multilingual-cased")

    # Initialize model
    model = CulturalPatternClassifier(base_model, num_labels=8)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    return {
        "model": model,
        "tokenizer": tokenizer,
        "config": checkpoint.get("model_config", {}),
    }


def input_fn(request_body: str, request_content_type: str) -> Dict[str, Any]:
    """Process input data for inference."""
    if request_content_type == "application/json":
        data = json.loads(request_body)
        return dict(data)
    else:
        raise ValueError(f"Unsupported content type: {request_content_type}")


def predict_fn(
    input_data: Dict[str, Any], model_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Run inference on the input data."""
    model = model_dict["model"]
    tokenizer = model_dict["tokenizer"]
    config = model_dict["config"]

    # Extract input fields
    text = input_data.get("text", "")
    # source_language = input_data.get("source_language", "en")
    # target_language = input_data.get("target_language", "ar")
    region = input_data.get("region", "middle_east")

    # Tokenize input
    encoding = tokenizer(
        text, truncation=True, padding="max_length", max_length=512, return_tensors="pt"
    )

    # Run inference
    with torch.no_grad():
        outputs = model(
            input_ids=encoding["input_ids"], attention_mask=encoding["attention_mask"]
        )

    # Convert outputs to predictions
    predictions = outputs.squeeze().cpu().numpy()

    # Map predictions to labels
    label_names = config.get(
        "label_names",
        [
            "formal",
            "includes_honorific",
            "gender_specific",
            "indirect_communication",
            "family_involvement",
            "religious_references",
            "age_respectful",
            "authority_deference",
        ],
    )

    # Create result dictionary
    result = {
        "formality": "formal" if predictions[0] > 0.5 else "informal",
        "directness": "indirect" if predictions[3] > 0.5 else "direct",
        "family_involvement": bool(predictions[4] > 0.5),
        "religious_references": bool(predictions[5] > 0.5),
        "age_hierarchy": bool(predictions[6] > 0.5),
        "gender_considerations": {
            "gender_specific": bool(predictions[2] > 0.5),
            "separate_sections": False,  # Would need additional logic
        },
        "confidence": float(predictions.max()),
        "raw_scores": {
            label: float(score) for label, score in zip(label_names, predictions)
        },
    }

    # Add region-specific adjustments
    if region == "middle_east":
        # Adjust for Middle Eastern cultural patterns
        raw_scores = result["raw_scores"]
        if (
            isinstance(raw_scores, dict)
            and raw_scores.get("includes_honorific", 0) > 0.3
        ):
            result["formality"] = "formal"
    elif region == "south_asia":
        # Adjust for South Asian patterns
        raw_scores = result["raw_scores"]
        if isinstance(raw_scores, dict) and raw_scores.get("age_respectful", 0) > 0.4:
            result["age_hierarchy"] = True

    return result


def output_fn(prediction: Dict[str, Any], content_type: str) -> str:
    """Format the prediction output."""
    if content_type == "application/json":
        return json.dumps(prediction)
    else:
        raise ValueError(f"Unsupported content type: {content_type}")
