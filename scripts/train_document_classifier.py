"""
Model Training Script for Document Classification

This script trains machine learning models for document classification
using labeled medical document data.
"""

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from src.ai.document_processing import DocumentType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def prepare_training_data():
    """
    Prepare training data for document classification.
    In production, this would load from a labeled dataset.
    """
    # Example training data structure
    training_samples = [
        {
            "text": "Prescription for Amoxicillin 500mg...",
            "type": DocumentType.PRESCRIPTION.value,
            "features": {
                "has_medication": True,
                "has_dosage": True,
                "has_signature": True,
            },
        },
        {
            "text": "Complete Blood Count results...",
            "type": DocumentType.LAB_REPORT.value,
            "features": {
                "has_test_results": True,
                "has_reference_ranges": True,
                "has_specimen_info": True,
            },
        },
        # Add more training samples
    ]

    return pd.DataFrame(training_samples)


def train_classifier(model_dir: Path):
    """Train the document classification model."""

    # Prepare data
    df = prepare_training_data()

    # Extract features
    texts = df["text"].values
    labels = df["type"].values

    # Encode labels
    label_encoder = LabelEncoder()
    encoded_labels = label_encoder.fit_transform(labels)

    # Create TF-IDF features
    vectorizer = TfidfVectorizer(
        max_features=1000, ngram_range=(1, 2), min_df=2, max_df=0.95
    )
    text_features = vectorizer.fit_transform(texts)

    # Extract numeric features
    numeric_features = np.array(
        [
            [
                int(row["features"].get("has_medication", False)),
                int(row["features"].get("has_test_results", False)),
                int(row["features"].get("has_signature", False)),
            ]
            for _, row in df.iterrows()
        ]
    )

    # Combine features
    combined_features = np.hstack([numeric_features, text_features.toarray()])

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        combined_features, encoded_labels, test_size=0.2, random_state=42
    )

    # Train model
    model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)

    # Print metrics
    print("Classification Report:")
    print(classification_report(y_test, y_pred, target_names=label_encoder.classes_))

    # Save model and components
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_dir / "classifier_model.pkl")
    joblib.dump(vectorizer, model_dir / "tfidf_vectorizer.pkl")
    joblib.dump(label_encoder, model_dir / "label_encoder.pkl")

    logger.info(f"Model saved to {model_dir}")


if __name__ == "__main__":
    model_dir = Path("models/document_classification")
    train_classifier(model_dir)
