"""Training script for cultural adaptation models.

This script trains models to detect cultural communication patterns
in healthcare contexts for refugee populations.
"""

import argparse
import json
import logging
import os
from typing import Any, Dict, List, Tuple

import boto3
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CulturalPatternDataset(Dataset):
    """Dataset for cultural pattern detection."""

    def __init__(
        self,
        texts: List[str],
        labels: List[List[int]],
        tokenizer: Any,
        max_length: int = 512,
    ) -> None:
        """Initialize the cultural pattern dataset."""
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        """Return the length of the dataset."""
        return len(self.texts)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """Get a single item from the dataset."""
        text = self.texts[idx]
        labels = self.labels[idx]

        # Tokenize text
        encoding = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )

        return {
            "input_ids": encoding["input_ids"].flatten(),
            "attention_mask": encoding["attention_mask"].flatten(),
            "labels": torch.tensor(labels, dtype=torch.float),
        }


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


def load_data(data_path: str) -> Tuple[List[str], List[List[int]], str]:
    """Load training data from S3."""
    s3 = boto3.client("s3")

    # Parse S3 path
    bucket, key = data_path.replace("s3://", "").split("/", 1)

    # Download data
    obj = s3.get_object(Bucket=bucket, Key=key)
    data = json.loads(obj["Body"].read().decode("utf-8"))

    # Extract texts and labels
    texts = []
    labels = []

    for pattern in data["patterns"]:
        texts.append(pattern["text"])

        # Multi-label encoding
        label = [
            1 if pattern.get("formal", False) else 0,
            1 if pattern.get("includes_honorific", False) else 0,
            1 if pattern.get("gender_specific", False) else 0,
            1 if pattern.get("indirect_communication", False) else 0,
            1 if pattern.get("family_involvement", False) else 0,
            1 if pattern.get("religious_references", False) else 0,
            1 if pattern.get("age_respectful", False) else 0,
            1 if pattern.get("authority_deference", False) else 0,
        ]
        labels.append(label)

    return texts, labels, data.get("language_pair", "en-ar")


def train_model(
    model: CulturalPatternClassifier,
    train_loader: DataLoader,
    val_loader: DataLoader,
    epochs: int,
    device: torch.device,
) -> CulturalPatternClassifier:
    """Train the cultural pattern classifier."""
    criterion = nn.BCELoss()
    optimizer = optim.AdamW(model.parameters(), lr=2e-5)

    best_val_loss = float("inf")

    for epoch in range(epochs):
        # Training phase
        model.train()
        train_loss = 0

        for batch in train_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            optimizer.zero_grad()
            outputs = model(input_ids, attention_mask)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item()

        # Validation phase
        model.eval()
        val_loss = 0
        correct_predictions = 0
        total_predictions = 0

        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)

                outputs = model(input_ids, attention_mask)
                loss = criterion(outputs, labels)
                val_loss += loss.item()

                # Calculate accuracy
                predictions = (outputs > 0.5).float()
                correct_predictions += (predictions == labels).sum().item()
                total_predictions += labels.numel()

        avg_train_loss = train_loss / len(train_loader)
        avg_val_loss = val_loss / len(val_loader)
        accuracy = correct_predictions / total_predictions

        logger.info("Epoch %d/%d", epoch + 1, epochs)
        logger.info("Train Loss: %.4f", avg_train_loss)
        logger.info("Validation Loss: %.4f", avg_val_loss)
        logger.info("Validation Accuracy: %.4f", accuracy)
        logger.info("Cultural Adaptation Score: %.4f", 1 - avg_val_loss)

        # Save best model
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            torch.save(model.state_dict(), "/opt/ml/model/best_model.pth")

    return model


def save_model(model: CulturalPatternClassifier, model_dir: str) -> None:
    """Save the trained model."""
    logger.info("Saving model to %s", model_dir)

    # Save model architecture and weights
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "model_config": {
                "num_labels": 8,
                "label_names": [
                    "formal",
                    "includes_honorific",
                    "gender_specific",
                    "indirect_communication",
                    "family_involvement",
                    "religious_references",
                    "age_respectful",
                    "authority_deference",
                ],
            },
        },
        os.path.join(model_dir, "model.pth"),
    )

    # Save tokenizer info
    with open(
        os.path.join(model_dir, "tokenizer_config.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(
            {"tokenizer_name": "bert-base-multilingual-cased", "max_length": 512}, f
        )


def main() -> None:
    """Execute the training pipeline for cultural adaptation model."""
    parser = argparse.ArgumentParser()

    # SageMaker specific arguments
    parser.add_argument(
        "--model-dir", type=str, default=os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
    )
    parser.add_argument(
        "--training",
        type=str,
        default=os.environ.get("SM_CHANNEL_TRAINING", "/opt/ml/input/data/training"),
    )

    # Hyperparameters
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--language-pair", type=str, default="en-ar")
    parser.add_argument("--cultural-region", type=str, default="middle_east")
    parser.add_argument("--sample-size", type=int, default=1000)

    args = parser.parse_args()

    # Set device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Using device: %s", device)

    # Load data
    data_path = os.path.join(args.training, "data.json")
    if data_path.startswith("/opt/ml/"):
        # Local mode, load from file
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            texts = [p["text"] for p in data["patterns"]]
            labels = [
                [
                    1 if p.get("formal", False) else 0,
                    1 if p.get("includes_honorific", False) else 0,
                    1 if p.get("gender_specific", False) else 0,
                    1 if p.get("indirect_communication", False) else 0,
                    1 if p.get("family_involvement", False) else 0,
                    1 if p.get("religious_references", False) else 0,
                    1 if p.get("age_respectful", False) else 0,
                    1 if p.get("authority_deference", False) else 0,
                ]
                for p in data["patterns"]
            ]
    else:
        # S3 mode
        texts, labels, _ = load_data(args.training)

    # Split data
    train_texts, val_texts, train_labels, val_labels = train_test_split(
        texts, labels, test_size=0.2, random_state=42
    )

    # Load tokenizer and model
    from transformers import AutoModel, AutoTokenizer  # noqa: PLC0415

    tokenizer = AutoTokenizer.from_pretrained("bert-base-multilingual-cased")
    base_model = AutoModel.from_pretrained("bert-base-multilingual-cased")

    # Create datasets
    train_dataset = CulturalPatternDataset(train_texts, train_labels, tokenizer)
    val_dataset = CulturalPatternDataset(val_texts, val_labels, tokenizer)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size)

    # Initialize model
    model = CulturalPatternClassifier(base_model, num_labels=8)
    model.to(device)

    # Train model
    trained_model = train_model(model, train_loader, val_loader, args.epochs, device)

    # Save model
    save_model(trained_model, args.model_dir)

    logger.info("Training completed successfully!")


if __name__ == "__main__":
    main()
