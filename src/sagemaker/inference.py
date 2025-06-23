#!/usr/bin/env python3
"""SageMaker inference script for cultural adaptation models.

CRITICAL: This handles real-time inference for refugee healthcare.
Low latency and high accuracy are essential.
"""

import json
import logging
import os
from typing import Any, Dict, List

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer

logger = logging.getLogger(__name__)


class CulturalPatternClassifier(nn.Module):
    """Neural network for cultural pattern classification."""

    def __init__(
        self,
        model_name: str = "bert-base-multilingual-cased",
        num_labels: int = 8,
        dropout: float = 0.3,
    ) -> None:
        """Initialize the model."""
        super().__init__()

        self.transformer = AutoModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(dropout)

        hidden_size = self.transformer.config.hidden_size
        self.classifiers = nn.ModuleList(
            [nn.Linear(hidden_size, 1) for _ in range(num_labels)]
        )
        self.cultural_attention = nn.MultiheadAttention(
            hidden_size, num_heads=8, dropout=dropout
        )
        self.cultural_norm = nn.LayerNorm(hidden_size)

    def forward(
        self, input_ids: torch.Tensor, attention_mask: torch.Tensor
    ) -> torch.Tensor:
        """Forward pass."""
        outputs = self.transformer(input_ids=input_ids, attention_mask=attention_mask)

        cls_output = outputs.last_hidden_state[:, 0, :]

        attended, _ = self.cultural_attention(
            cls_output.unsqueeze(0), cls_output.unsqueeze(0), cls_output.unsqueeze(0)
        )
        attended = self.cultural_norm(attended.squeeze(0) + cls_output)

        pooled = self.dropout(attended)

        predictions = []
        for classifier in self.classifiers:
            pred = classifier(pooled)
            predictions.append(pred)

        logits = torch.cat(predictions, dim=1)

        return logits


def model_fn(model_dir: str) -> Dict[str, Any]:
    """Load the model for inference."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Load config
    with open(os.path.join(model_dir, "config.json"), "r") as f:
        config = json.load(f)

    # Initialize model
    model = CulturalPatternClassifier(
        model_name=config["model_name"],
        num_labels=config["num_labels"],
        dropout=config["dropout"],
    )

    # Load weights
    model.load_state_dict(
        torch.load(
            os.path.join(model_dir, "model.pth"), map_location=device, weights_only=True
        )
    )
    model.to(device)
    model.eval()

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(config["model_name"])

    return {"model": model, "tokenizer": tokenizer, "device": device, "config": config}


def input_fn(
    request_body: str, content_type: str = "application/json"
) -> Dict[str, Any]:
    """Parse input data."""
    if content_type == "application/json":
        input_data: Dict[str, Any] = json.loads(request_body)
        return input_data
    else:
        raise ValueError(f"Unsupported content type: {content_type}")


def predict_fn(
    input_data: Dict[str, Any], model_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Make predictions."""
    model = model_dict["model"]
    tokenizer = model_dict["tokenizer"]
    device = model_dict["device"]
    config = model_dict["config"]

    # Extract text and metadata
    text = input_data.get("text", "")
    source_language = input_data.get("source_language", "en")
    target_language = input_data.get("target_language", "ar")
    cultural_region = input_data.get("cultural_region", "unknown")

    # Tokenize
    encoding = tokenizer(
        text, truncation=True, padding="max_length", max_length=512, return_tensors="pt"
    )

    # Move to device
    input_ids = encoding["input_ids"].to(device)
    attention_mask = encoding["attention_mask"].to(device)

    # Predict
    with torch.no_grad():
        logits = model(input_ids, attention_mask)
        probabilities = torch.sigmoid(logits).cpu().numpy()[0]

    # Create response
    patterns = config["cultural_patterns"]
    detected_patterns = []
    pattern_scores = {}

    for _i, (pattern, prob) in enumerate(zip(patterns, probabilities)):
        pattern_scores[pattern] = float(prob)
        if prob > 0.5:
            detected_patterns.append(pattern)

    # Calculate cultural sensitivity score
    critical_patterns = [
        "gender_specific",
        "family_involvement",
        "religious_references",
    ]
    critical_scores = [
        pattern_scores[p] for p in critical_patterns if p in pattern_scores
    ]
    cultural_sensitivity_score = (
        sum(critical_scores) / len(critical_scores) if critical_scores else 0.5
    )

    # Generate recommendations based on detected patterns
    recommendations = generate_cultural_recommendations(
        pattern_scores, cultural_region, source_language, target_language
    )

    return {
        "detected_patterns": detected_patterns,
        "pattern_scores": pattern_scores,
        "cultural_sensitivity_score": float(cultural_sensitivity_score),
        "cultural_region": cultural_region,
        "recommendations": recommendations,
        "confidence": float(max(probabilities)),
    }


def output_fn(
    prediction: Dict[str, Any], content_type: str = "application/json"
) -> str:
    """Format the output."""
    if content_type == "application/json":
        return json.dumps(prediction)
    else:
        raise ValueError(f"Unsupported content type: {content_type}")


def generate_cultural_recommendations(
    patterns: Dict[str, float], region: str, source_lang: str, target_lang: str
) -> List[str]:
    """Generate healthcare communication recommendations based on patterns."""
    recommendations = []

    if "formal" in patterns:
        recommendations.append(
            "Use formal titles and maintain professional distance in communications"
        )

    if "gender_specific" in patterns:
        recommendations.append(
            "Offer gender-concordant healthcare providers when possible"
        )

    if "family_involvement" in patterns:
        recommendations.append(
            "Include family members in healthcare discussions and decisions"
        )

    if "religious_references" in patterns:
        recommendations.append(
            "Respect religious practices and dietary restrictions in treatment plans"
        )

    if "indirect_communication" in patterns:
        recommendations.append(
            "Use indirect communication styles and avoid direct confrontation"
        )

    if "authority_deference" in patterns:
        recommendations.append(
            "Present medical advice as authoritative recommendations"
        )

    # Region-specific recommendations
    region_recommendations = {
        "middle_east": [
            "Schedule appointments considering prayer times",
            "Ensure modesty requirements are met during examinations",
        ],
        "south_asia": [
            "Be aware of dietary restrictions and fasting periods",
            "Consider extended family involvement in decisions",
        ],
        "east_africa": [
            "Discuss traditional medicine practices respectfully",
            "Provide visual aids for low-literacy patients",
        ],
        "latin_america": [
            "Use warm, personal communication style",
            "Allow extra time for relationship building",
        ],
    }

    if region in region_recommendations:
        recommendations.extend(region_recommendations[region])

    return recommendations
