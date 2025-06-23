#!/usr/bin/env python3
"""SageMaker training script for cultural adaptation models.

CRITICAL: This trains models for refugee healthcare communication.
Accuracy and cultural sensitivity are life-critical.
"""

import argparse
import json
import logging
import os
from typing import Any, Dict, Tuple

import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CulturalPatternDataset(Dataset):
    """Dataset for cultural pattern recognition in healthcare texts."""

    def __init__(self, data_path: str, tokenizer: Any, max_length: int = 512) -> None:
        """Initialize dataset."""
        self.tokenizer = tokenizer
        self.max_length = max_length

        # Load data
        with open(data_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        logger.info(f"Loaded {len(self.data)} samples from {data_path}")

    def __len__(self) -> int:
        """Return the number of samples in the dataset."""
        return len(self.data)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """Get a single sample."""
        item = self.data[idx]
        # Tokenize text
        encoding = self.tokenizer(
            item["text"],
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )

        # Extract labels for cultural patterns
        labels = torch.tensor(
            [
                int(item.get("formal", False)),
                int(item.get("includes_honorific", False)),
                int(item.get("gender_specific", False)),
                int(item.get("indirect_communication", False)),
                int(item.get("family_involvement", False)),
                int(item.get("religious_references", False)),
                int(item.get("age_respectful", False)),
                int(item.get("authority_deference", False)),
            ],
            dtype=torch.float,
        )

        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "labels": labels,
            "cultural_region": item.get("cultural_region", "unknown"),
        }


class CulturalPatternClassifier(nn.Module):
    """Neural network for cultural pattern classification in healthcare texts."""

    def __init__(
        self,
        model_name: str = "bert-base-multilingual-cased",
        num_labels: int = 8,
        dropout: float = 0.3,
    ) -> None:
        """Initialize the model."""
        super().__init__()

        # Load pre-trained transformer
        self.transformer = AutoModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(dropout)

        # Classification heads for each cultural pattern
        hidden_size = self.transformer.config.hidden_size
        self.classifiers = nn.ModuleList(
            [nn.Linear(hidden_size, 1) for _ in range(num_labels)]
        )

        # Additional layers for cultural sensitivity
        self.cultural_attention = nn.MultiheadAttention(
            hidden_size, num_heads=8, dropout=dropout
        )
        self.cultural_norm = nn.LayerNorm(hidden_size)

    def forward(
        self, input_ids: torch.Tensor, attention_mask: torch.Tensor
    ) -> torch.Tensor:
        """Forward pass."""
        # Get transformer outputs
        outputs = self.transformer(input_ids=input_ids, attention_mask=attention_mask)
        # Use CLS token representation
        cls_output = outputs.last_hidden_state[:, 0, :]  # [batch_size, hidden_size]

        # Apply cultural attention
        attended, _ = self.cultural_attention(
            cls_output.unsqueeze(0), cls_output.unsqueeze(0), cls_output.unsqueeze(0)
        )
        attended = self.cultural_norm(attended.squeeze(0) + cls_output)

        # Apply dropout
        pooled = self.dropout(attended)

        # Get predictions for each cultural pattern
        predictions = []
        for classifier in self.classifiers:
            pred = classifier(pooled)
            predictions.append(pred)

        # Stack predictions [batch_size, num_labels]
        logits = torch.cat(predictions, dim=1)

        return logits


def train_epoch(
    model: nn.Module,
    dataloader: DataLoader,
    optimizer: Any,
    scheduler: Any,
    device: torch.device,
) -> Tuple[float, float]:
    """Train for one epoch."""
    model.train()
    total_loss = 0
    predictions = []
    true_labels = []
    criterion = nn.BCEWithLogitsLoss()

    for batch in dataloader:
        # Move to device
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["labels"].to(device)

        # Forward pass
        optimizer.zero_grad()
        logits = model(input_ids, attention_mask)

        # Calculate loss
        loss = criterion(logits, labels)
        total_loss += loss.item()

        # Backward pass
        loss.backward()
        optimizer.step()
        scheduler.step()

        # Store predictions
        with torch.no_grad():
            preds = torch.sigmoid(logits) > 0.5
            predictions.append(preds.cpu())
            true_labels.append(labels.cpu())

    # Calculate metrics
    all_predictions = torch.cat(predictions)
    all_true_labels = torch.cat(true_labels)

    avg_loss = total_loss / len(dataloader)
    accuracy = accuracy_score(all_true_labels.numpy(), all_predictions.numpy())

    return avg_loss, accuracy


def evaluate(
    model: torch.nn.Module, dataloader: DataLoader, device: torch.device
) -> Dict[str, float]:
    """Evaluate the model."""
    model.eval()
    predictions = []
    true_labels = []

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            logits = model(input_ids, attention_mask)
            preds = torch.sigmoid(logits) > 0.5

            predictions.append(preds.cpu())
            true_labels.append(labels.cpu())

    predictions_array = torch.cat(predictions).numpy()
    true_labels_array = torch.cat(true_labels).numpy()

    # Calculate metrics
    accuracy = accuracy_score(true_labels_array, predictions_array)
    precision, recall, f1, _ = precision_recall_fscore_support(
        true_labels_array, predictions_array, average="macro"
    )

    # Calculate cultural sensitivity score
    # Higher weight for critical patterns (religious, family, gender)
    critical_indices = [
        2,
        4,
        5,
    ]  # gender_specific, family_involvement, religious_references
    critical_f1 = f1_score(
        true_labels_array[:, critical_indices],
        predictions_array[:, critical_indices],
        average="macro",
    )
    cultural_sensitivity = 0.7 * critical_f1 + 0.3 * f1

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "cultural_sensitivity": cultural_sensitivity,
    }


def main() -> None:
    """Execute the cultural adaptation model training pipeline."""
    parser = argparse.ArgumentParser()

    # SageMaker specific arguments
    parser.add_argument("--model-dir", type=str, default=os.environ.get("SM_MODEL_DIR"))
    parser.add_argument("--train", type=str, default=os.environ.get("SM_CHANNEL_TRAIN"))
    parser.add_argument(
        "--validation", type=str, default=os.environ.get("SM_CHANNEL_VALIDATION")
    )

    # Hyperparameters
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument(
        "--model-name", type=str, default="bert-base-multilingual-cased"
    )
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--warmup-steps", type=int, default=1000)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--cultural-sensitivity-threshold", type=float, default=0.95)
    parser.add_argument("--enable-medical-validation", type=bool, default=True)

    args = parser.parse_args()

    # Set device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")

    # Initialize tokenizer and model
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = CulturalPatternClassifier(
        model_name=args.model_name, dropout=args.dropout
    ).to(device)

    # Load datasets
    train_dataset = CulturalPatternDataset(
        os.path.join(args.train, "train.json"), tokenizer, args.max_length
    )

    val_dataset = CulturalPatternDataset(
        os.path.join(args.validation, "validation.json"), tokenizer, args.max_length
    )
    # Create dataloaders
    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=4
    )

    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=4
    )

    # Setup optimizer and scheduler
    optimizer = optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=0.01
    )

    total_steps = len(train_loader) * args.epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=args.warmup_steps, num_training_steps=total_steps
    )

    # Training loop
    best_cultural_sensitivity = 0.0

    for epoch in range(args.epochs):
        logger.info(f"Epoch {epoch + 1}/{args.epochs}")

        # Train
        train_loss, train_acc = train_epoch(
            model, train_loader, optimizer, scheduler, device
        )

        # Evaluate
        val_metrics = evaluate(model, val_loader, device)

        # Log metrics
        logger.info(f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f}")
        logger.info(f"Val Metrics: {val_metrics}")

        # Log to CloudWatch (SageMaker will capture these)
        print(f"accuracy: {val_metrics['accuracy']:.4f}")
        print(f"f1_score: {val_metrics['f1_score']:.4f}")
        print(f"cultural_sensitivity: {val_metrics['cultural_sensitivity']:.4f}")

        # Save best model
        if val_metrics["cultural_sensitivity"] > best_cultural_sensitivity:
            best_cultural_sensitivity = val_metrics["cultural_sensitivity"]
            torch.save(
                model.state_dict(), os.path.join(args.model_dir, "best_model.pth")
            )
            logger.info(
                f"Saved best model with cultural sensitivity: {best_cultural_sensitivity:.4f}"
            )

    # Medical validation check
    if args.enable_medical_validation:
        if best_cultural_sensitivity < args.cultural_sensitivity_threshold:
            raise ValueError(
                f"Model failed to meet cultural sensitivity threshold: "
                f"{best_cultural_sensitivity:.4f} < {args.cultural_sensitivity_threshold}"
            )

    # Save final model
    torch.save(model.state_dict(), os.path.join(args.model_dir, "model.pth"))

    # Save model config for inference
    config = {
        "model_name": args.model_name,
        "dropout": args.dropout,
        "num_labels": 8,
        "cultural_patterns": [
            "formal",
            "includes_honorific",
            "gender_specific",
            "indirect_communication",
            "family_involvement",
            "religious_references",
            "age_respectful",
            "authority_deference",
        ],
        "cultural_sensitivity_score": best_cultural_sensitivity,
    }

    with open(os.path.join(args.model_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)

    logger.info("Training completed successfully!")


if __name__ == "__main__":
    main()
