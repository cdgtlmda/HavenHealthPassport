#!/usr/bin/env python3
"""
Training script for cultural adaptation model.
This script is executed by SageMaker during training.
"""

import argparse
import json
import logging
import os
import sys
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    EvalPrediction
)
from sklearn.metrics import accuracy_score, f1_score
import numpy as np

logger = logging.getLogger(__name__)


class CulturalAdaptationDataset(Dataset):
    """Dataset for cultural adaptation training."""
    
    def __init__(self, dataframe, tokenizer, max_length=512):
        self.data = dataframe
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        row = self.data.iloc[idx]
        
        # Combine original message with context and region
        text = f"[CONTEXT: {row['context']}] [REGION: {row['region']}] {row['original_message']}"
        
        # Tokenize
        encoding = self.tokenizer(
            text,
            row['adapted_message'],
            truncation=True,
            padding='max_length',
            max_length=self.max_length,
            return_tensors='pt'
        )
        
        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(row['label'], dtype=torch.long)
        }


def compute_metrics(eval_pred: EvalPrediction) -> dict:
    """Compute metrics for evaluation."""
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    
    return {
        'accuracy': accuracy_score(labels, predictions),
        'f1_score': f1_score(labels, predictions, average='weighted')
    }


def main():
    """Main training function."""
    parser = argparse.ArgumentParser()
    
    # SageMaker specific arguments
    parser.add_argument('--model_name', type=str, 
                       default='bert-base-multilingual-cased')
    parser.add_argument('--epochs', type=int, default=3)
    parser.add_argument('--train_batch_size', type=int, default=16)
    parser.add_argument('--eval_batch_size', type=int, default=16)
    parser.add_argument('--learning_rate', type=float, default=5e-5)
    parser.add_argument('--fp16', type=bool, default=True)
    
    # Data paths
    parser.add_argument('--train', type=str, default='/opt/ml/input/data/train')
    parser.add_argument('--validation', type=str, default='/opt/ml/input/data/validation')
    parser.add_argument('--model-dir', type=str, default='/opt/ml/model')
    parser.add_argument('--output-data-dir', type=str, default='/opt/ml/output/data')
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load data
    logger.info("Loading training data...")
    train_df = pd.read_csv(os.path.join(args.train, 'training_data.csv'))
    val_df = pd.read_csv(os.path.join(args.validation, 'validation_data.csv'))
    
    logger.info(f"Training samples: {len(train_df)}")
    logger.info(f"Validation samples: {len(val_df)}")
    
    # Load tokenizer and model
    logger.info(f"Loading model: {args.model_name}")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=2  # Binary classification: appropriate/not appropriate
    )
    
    # Create datasets
    train_dataset = CulturalAdaptationDataset(train_df, tokenizer)
    val_dataset = CulturalAdaptationDataset(val_df, tokenizer)
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=args.model_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.train_batch_size,
        per_device_eval_batch_size=args.eval_batch_size,
        learning_rate=args.learning_rate,
        warmup_steps=500,
        weight_decay=0.01,
        logging_dir=f'{args.output_data_dir}/logs',
        logging_steps=10,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_score",
        fp16=args.fp16,
    )
    
    # Create trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        tokenizer=tokenizer,
    )
    
    # Train
    logger.info("Starting training...")
    trainer.train()
    
    # Evaluate
    logger.info("Evaluating model...")
    eval_results = trainer.evaluate()
    
    # Log metrics for SageMaker
    for key, value in eval_results.items():
        print(f"{key}: {value}")
    
    # Save model
    logger.info(f"Saving model to {args.model_dir}")
    trainer.save_model(args.model_dir)
    tokenizer.save_pretrained(args.model_dir)
    
    # Save training info
    with open(os.path.join(args.model_dir, 'training_info.json'), 'w') as f:
        json.dump({
            'model_name': args.model_name,
            'epochs': args.epochs,
            'final_metrics': eval_results,
            'training_completed': True
        }, f)
    
    logger.info("Training complete!")


if __name__ == '__main__':
    main()