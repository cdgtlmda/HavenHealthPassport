#!/usr/bin/env python3
"""Evaluation script for cultural adaptation models.

CRITICAL: This validates models meet healthcare standards for
refugee communication. Accuracy is life-critical.
"""

import argparse
import json
import logging
import os
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_recall_fscore_support,
)
from torch.utils.data import DataLoader

# Import model architecture from training script
from train_cultural_model import CulturalPatternClassifier, CulturalPatternDataset
from transformers import AutoTokenizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def evaluate_healthcare_compliance(
    predictions: np.ndarray, labels: np.ndarray, pattern_names: List[str]
) -> Dict[str, Dict[str, float]]:
    """Evaluate model compliance with healthcare communication standards."""
    compliance_metrics = {}

    # Critical patterns for healthcare
    critical_patterns = {
        "gender_specific": 2,
        "family_involvement": 4,
        "religious_references": 5,
    }

    for pattern_name, idx in critical_patterns.items():
        pattern_pred = predictions[:, idx]
        pattern_true = labels[:, idx]

        # Calculate metrics for critical patterns
        precision, recall, f1, _ = precision_recall_fscore_support(
            pattern_true, pattern_pred, average="binary"
        )

        compliance_metrics[pattern_name] = {
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1),
            "accuracy": float(accuracy_score(pattern_true, pattern_pred)),
        }

        # Check if meets minimum threshold
        if f1 < 0.90:  # 90% F1 score minimum for critical patterns
            logger.warning(
                f"Critical pattern '{pattern_name}' below threshold: {f1:.3f} < 0.90"
            )
    return compliance_metrics


def evaluate_cultural_sensitivity(
    predictions: np.ndarray, labels: np.ndarray, test_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Evaluate cultural sensitivity of the model."""
    sensitivity_scores = {}

    # Group by cultural region
    regions: Dict[str, Dict[str, List[int]]] = {}
    for i, sample in enumerate(test_data):
        region = sample.get("cultural_region", "unknown")
        if region not in regions:
            regions[region] = {"predictions": [], "labels": []}
        regions[region]["predictions"].append(predictions[i])
        regions[region]["labels"].append(labels[i])

    # Calculate sensitivity score per region
    for region, data in regions.items():
        region_preds = np.array(data["predictions"])
        region_labels = np.array(data["labels"])

        # Overall accuracy for region
        accuracy = accuracy_score(region_labels, region_preds)

        # F1 score with higher weight on critical patterns
        f1_weighted = calculate_weighted_f1(region_preds, region_labels)

        # Cultural sensitivity score
        sensitivity_score = 0.4 * accuracy + 0.6 * f1_weighted

        sensitivity_scores[region] = {
            "accuracy": float(accuracy),
            "f1_weighted": float(f1_weighted),
            "sensitivity_score": float(sensitivity_score),
            "sample_count": len(region_preds),
        }

    return sensitivity_scores


def calculate_weighted_f1(predictions: np.ndarray, labels: np.ndarray) -> float:
    """Calculate F1 score with higher weights for critical patterns."""
    # Pattern weights (higher for critical healthcare patterns)
    weights = np.array(
        [
            0.8,  # formal
            0.9,  # includes_honorific
            1.0,  # gender_specific (critical)
            0.8,  # indirect_communication
            1.0,  # family_involvement (critical)
            1.0,  # religious_references (critical)
            0.9,  # age_respectful
            0.9,  # authority_deference
        ]
    )

    # Calculate F1 for each pattern
    f1_scores = []
    for i in range(predictions.shape[1]):
        f1 = f1_score(labels[:, i], predictions[:, i], average="binary")
        f1_scores.append(f1 * weights[i])

    # Weighted average
    return float(np.sum(f1_scores) / np.sum(weights))


def generate_evaluation_report(
    all_metrics: Dict[str, Any], output_path: str
) -> Dict[str, Any]:
    """Generate comprehensive evaluation report."""
    report = {
        "overall_metrics": all_metrics["overall"],
        "compliance_metrics": all_metrics["compliance"],
        "cultural_sensitivity": all_metrics["sensitivity"],
        "pattern_analysis": all_metrics["pattern_analysis"],
        "recommendations": [],
        "approval_status": "pending",
    }

    # Check if model meets healthcare standards
    cultural_sensitivity_avg = np.mean(
        [region["sensitivity_score"] for region in all_metrics["sensitivity"].values()]
    )

    if cultural_sensitivity_avg >= 0.95:
        report["approval_status"] = "approved"
        report["recommendations"].append(
            "Model meets healthcare communication standards for refugee populations"
        )
    else:
        report["approval_status"] = "requires_improvement"
        report["recommendations"].append(
            f"Model cultural sensitivity ({cultural_sensitivity_avg:.3f}) "
            f"below required threshold (0.95)"
        )

    # Pattern-specific recommendations
    for pattern, metrics in all_metrics["compliance"].items():
        if metrics["f1_score"] < 0.90:
            report["recommendations"].append(
                f"Improve {pattern} detection: current F1 {metrics['f1_score']:.3f}"
            )

    # Save report
    with open(os.path.join(output_path, "evaluation_report.json"), "w") as f:
        json.dump(report, f, indent=2)

    # Save detailed metrics for analysis
    pd.DataFrame(all_metrics["pattern_analysis"]).to_csv(
        os.path.join(output_path, "pattern_analysis.csv"), index=False
    )

    return report


def main() -> None:
    """Execute the model evaluation pipeline."""
    parser = argparse.ArgumentParser()

    # SageMaker paths
    parser.add_argument("--model-path", type=str, default="/opt/ml/processing/model")
    parser.add_argument("--test-path", type=str, default="/opt/ml/processing/test")
    parser.add_argument(
        "--output-path", type=str, default="/opt/ml/processing/evaluation"
    )

    args = parser.parse_args()

    # Create output directory
    os.makedirs(args.output_path, exist_ok=True)

    # Set device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")

    # Load model config
    with open(os.path.join(args.model_path, "config.json"), "r") as f:
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
            os.path.join(args.model_path, "model.pth"),
            map_location=device,
            weights_only=True,
        )
    )
    model.to(device)
    model.eval()

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(config["model_name"])

    # Load test dataset
    test_dataset = CulturalPatternDataset(
        os.path.join(args.test_path, "test.json"), tokenizer, max_length=512
    )

    test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False, num_workers=4)

    # Evaluate model
    all_predictions: List[torch.Tensor] = []
    all_labels = []
    test_samples = []

    with torch.no_grad():
        for batch in test_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"]

            logits = model(input_ids, attention_mask)
            predictions = (torch.sigmoid(logits) > 0.5).cpu().numpy()

            all_predictions.extend(predictions)
            all_labels.extend(labels.numpy())

            # Store sample data for region analysis
            for i in range(len(predictions)):
                test_samples.append({"cultural_region": batch["cultural_region"][i]})

    all_predictions_array = np.array(all_predictions)
    all_labels_array = np.array(all_labels)

    # Calculate overall metrics
    overall_metrics = {
        "accuracy": float(accuracy_score(all_labels_array, all_predictions_array)),
        "macro_f1": float(
            f1_score(all_labels_array, all_predictions_array, average="macro")
        ),
        "micro_f1": float(
            f1_score(all_labels_array, all_predictions_array, average="micro")
        ),
        "weighted_f1": float(
            calculate_weighted_f1(all_predictions_array, all_labels_array)
        ),
    }

    # Healthcare compliance metrics
    compliance_metrics = evaluate_healthcare_compliance(
        all_predictions_array, all_labels_array, config["cultural_patterns"]
    )

    # Cultural sensitivity evaluation
    sensitivity_scores = evaluate_cultural_sensitivity(
        all_predictions_array, all_labels_array, test_samples
    )

    # Pattern-level analysis
    pattern_analysis = []
    for i, pattern in enumerate(config["cultural_patterns"]):
        pattern_metrics = {
            "pattern": pattern,
            "accuracy": float(
                accuracy_score(all_labels_array[:, i], all_predictions_array[:, i])
            ),
            "precision": float(
                precision_recall_fscore_support(
                    all_labels_array[:, i],
                    all_predictions_array[:, i],
                    average="binary",
                )[0]
            ),
            "recall": float(
                precision_recall_fscore_support(
                    all_labels_array[:, i],
                    all_predictions_array[:, i],
                    average="binary",
                )[1]
            ),
            "f1_score": float(
                f1_score(all_labels_array[:, i], all_predictions_array[:, i])
            ),
        }
        pattern_analysis.append(pattern_metrics)

    # Compile all metrics
    all_metrics = {
        "overall": overall_metrics,
        "compliance": compliance_metrics,
        "sensitivity": sensitivity_scores,
        "pattern_analysis": pattern_analysis,
    }

    # Generate evaluation report
    report = generate_evaluation_report(all_metrics, args.output_path)

    # Log summary
    logger.info("Evaluation Summary:")
    logger.info(f"Overall Accuracy: {overall_metrics['accuracy']:.3f}")
    logger.info(f"Weighted F1 Score: {overall_metrics['weighted_f1']:.3f}")
    logger.info(f"Model Status: {report['approval_status']}")

    # Log to CloudWatch for SageMaker monitoring
    print(f"evaluation_accuracy: {overall_metrics['accuracy']:.4f}")
    print(f"evaluation_f1: {overall_metrics['weighted_f1']:.4f}")
    print(f"evaluation_status: {report['approval_status']}")

    # Exit with error if model doesn't meet standards
    if report["approval_status"] != "approved":
        logger.error("Model does not meet healthcare standards")
        exit(1)


if __name__ == "__main__":
    main()
