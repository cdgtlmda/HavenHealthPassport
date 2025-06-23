#!/usr/bin/env python3
"""
Train and Deploy Cultural Adaptation Models for Haven Health Passport.

This script trains ML models for cultural adaptation in healthcare communication
and deploys them to Amazon SageMaker for real-time inference.

CRITICAL: This is for refugee healthcare - proper cultural adaptation is essential.
"""

import os
import sys
import json
import boto3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import asyncio

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logging import get_logger
from src.config import get_settings

logger = get_logger(__name__)


class CulturalAdaptationModelTrainer:
    """Train and deploy cultural adaptation models for healthcare communication."""
    
    def __init__(self):
        """Initialize the model trainer."""
        settings = get_settings()
        self.region = settings.AWS_REGION or "us-east-1"
        
        # Initialize AWS clients
        self.sagemaker = boto3.client("sagemaker", region_name=self.region)
        self.s3 = boto3.client("s3", region_name=self.region)
        self.comprehend = boto3.client("comprehendmedical", region_name=self.region)
        
        # Model configuration
        self.model_name = "haven-health-cultural-adaptation"
        self.instance_type = "ml.m5.xlarge"
        self.framework_version = "1.12.0"
        
        logger.info("Initialized Cultural Adaptation Model Trainer")
    
    def prepare_training_data(self) -> Tuple[str, str]:
        """
        Prepare training data for cultural adaptation models.
        
        Returns:
            Tuple of (training_data_path, validation_data_path) in S3
        """
        logger.info("Preparing training data for cultural adaptation models...")
        
        # Create synthetic training data for cultural patterns
        # In production, this would use real anonymized healthcare communications
        training_data = []
        
        # Cultural communication patterns by region
        cultural_patterns = {
            "middle_east": {
                "formal_greetings": ["Peace be upon you", "May God grant you health"],
                "indirect_communication": True,
                "family_involvement": "high",
                "gender_considerations": True,
                "religious_context": ["Inshallah", "Alhamdulillah"],
            },
            "east_asia": {
                "formal_greetings": ["Honored to meet you", "Thank you for your care"],
                "indirect_communication": True,
                "family_involvement": "high",
                "respect_hierarchy": True,
                "holistic_health": True,
            },
            "sub_saharan_africa": {
                "formal_greetings": ["How is your family?", "Greetings to you"],
                "community_context": True,
                "family_involvement": "high",
                "traditional_medicine": True,
                "oral_tradition": True,
            },
            "latin_america": {
                "formal_greetings": ["Good day", "How are you and your family?"],
                "family_involvement": "high",
                "personal_warmth": True,
                "religious_context": ["Thanks to God", "God willing"],
            }
        }
        
        # Generate training examples
        for region, patterns in cultural_patterns.items():
            # Healthcare scenarios
            scenarios = [
                {
                    "context": "diagnosis_delivery",
                    "message": "You have been diagnosed with diabetes",
                    "cultural_adaptation": self._adapt_message_for_culture(
                        "You have been diagnosed with diabetes", region, patterns
                    )
                },
                {
                    "context": "medication_instructions",
                    "message": "Take this medication twice daily with food",
                    "cultural_adaptation": self._adapt_message_for_culture(
                        "Take this medication twice daily with food", region, patterns
                    )
                },
                {
                    "context": "appointment_scheduling",
                    "message": "Please arrive 15 minutes before your appointment",
                    "cultural_adaptation": self._adapt_message_for_culture(
                        "Please arrive 15 minutes before your appointment", region, patterns
                    )
                }
            ]
            
            for scenario in scenarios:
                training_data.append({
                    "region": region,
                    "context": scenario["context"],
                    "original_message": scenario["message"],
                    "adapted_message": scenario["cultural_adaptation"],
                    "patterns": json.dumps(patterns),
                    "label": 1  # Appropriate adaptation
                })
        
        # Convert to DataFrame and split
        df = pd.DataFrame(training_data)
        train_df = df.sample(frac=0.8, random_state=42)
        val_df = df.drop(train_df.index)
        
        # Save to S3
        bucket_name = "haven-health-models"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        train_path = f"cultural-adaptation/training_data_{timestamp}.csv"
        val_path = f"cultural-adaptation/validation_data_{timestamp}.csv"
        
        # Upload to S3
        self.s3.put_object(
            Bucket=bucket_name,
            Key=train_path,
            Body=train_df.to_csv(index=False)
        )
        
        self.s3.put_object(
            Bucket=bucket_name,
            Key=val_path,
            Body=val_df.to_csv(index=False)
        )
        
        logger.info(f"Training data uploaded to s3://{bucket_name}/{train_path}")
        logger.info(f"Validation data uploaded to s3://{bucket_name}/{val_path}")
        
        return f"s3://{bucket_name}/{train_path}", f"s3://{bucket_name}/{val_path}"
    
    def _adapt_message_for_culture(
        self, 
        message: str, 
        region: str, 
        patterns: Dict
    ) -> str:
        """Adapt a healthcare message for cultural context."""
        adapted = message
        
        # Add appropriate greeting if needed
        if patterns.get("formal_greetings"):
            adapted = f"{patterns['formal_greetings'][0]}. {adapted}"
        
        # Add religious context if appropriate
        if patterns.get("religious_context"):
            adapted = f"{adapted}, {patterns['religious_context'][0]}"
        
        # Consider family involvement
        if patterns.get("family_involvement") == "high":
            adapted = adapted.replace("you", "you and your family")
        
        # Make communication more indirect if needed
        if patterns.get("indirect_communication"):
            adapted = adapted.replace(
                "You have been diagnosed", 
                "The tests indicate that you may have"
            )
            adapted = adapted.replace(
                "You must", 
                "It would be beneficial if you could"
            )
        
        return adapted
    
    def train_model(self, train_path: str, val_path: str) -> str:
        """
        Train cultural adaptation model using SageMaker.
        
        Returns:
            Model artifact path in S3
        """
        logger.info("Starting model training on SageMaker...")
        
        # Use Hugging Face estimator for transformer-based model
        from sagemaker.huggingface import HuggingFace
        
        # Training script
        hyperparameters = {
            "model_name": "bert-base-multilingual-cased",
            "epochs": 3,
            "train_batch_size": 16,
            "eval_batch_size": 16,
            "learning_rate": 5e-5,
            "fp16": True,
        }
        
        # Create estimator
        huggingface_estimator = HuggingFace(
            entry_point="train_cultural_model.py",
            source_dir=str(project_root / "scripts" / "ml"),
            instance_type=self.instance_type,
            instance_count=1,
            role=self._get_sagemaker_role(),
            transformers_version="4.26",
            pytorch_version="1.13",
            py_version="py39",
            hyperparameters=hyperparameters,
            output_path=f"s3://haven-health-models/cultural-adaptation/models/",
        )
        
        # Start training
        huggingface_estimator.fit({
            "train": train_path,
            "validation": val_path
        })
        
        # Get model artifact location
        model_artifact = huggingface_estimator.model_data
        logger.info(f"Model training complete. Artifact: {model_artifact}")
        
        return model_artifact
    
    def deploy_model(self, model_artifact: str) -> str:
        """
        Deploy trained model to SageMaker endpoint.
        
        Returns:
            Endpoint name
        """
        logger.info("Deploying model to SageMaker endpoint...")
        
        from sagemaker.huggingface import HuggingFaceModel
        
        # Create model
        huggingface_model = HuggingFaceModel(
            model_data=model_artifact,
            role=self._get_sagemaker_role(),
            transformers_version="4.26",
            pytorch_version="1.13",
            py_version="py39",
            entry_point="inference.py",
            source_dir=str(project_root / "scripts" / "ml"),
        )
        
        # Deploy to endpoint
        endpoint_name = f"{self.model_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        predictor = huggingface_model.deploy(
            initial_instance_count=1,
            instance_type=self.instance_type,
            endpoint_name=endpoint_name,
        )
        
        logger.info(f"Model deployed to endpoint: {endpoint_name}")
        
        # Update configuration
        self._update_endpoint_config(endpoint_name)
        
        return endpoint_name
    
    def _get_sagemaker_role(self) -> str:
        """Get SageMaker execution role."""
        try:
            from sagemaker import get_execution_role
            return get_execution_role()
        except:
            # Use role from environment or config
            return os.environ.get(
                "SAGEMAKER_ROLE",
                "arn:aws:iam::123456789012:role/HavenHealthSageMakerRole"
            )
    
    def _update_endpoint_config(self, endpoint_name: str):
        """Update application configuration with new endpoint."""
        config_path = project_root / ".env.aws"
        
        with open(config_path, "a") as f:
            f.write(f"\n# Cultural Adaptation Model Endpoint\n")
            f.write(f"CULTURAL_ADAPTATION_ENDPOINT={endpoint_name}\n")
        
        logger.info(f"Updated configuration with endpoint: {endpoint_name}")
    
    async def run_full_pipeline(self):
        """Run the complete training and deployment pipeline."""
        logger.info("="*80)
        logger.info("CULTURAL ADAPTATION MODEL TRAINING PIPELINE")
        logger.info("="*80)
        
        try:
            # Step 1: Prepare training data
            logger.info("\nStep 1: Preparing training data...")
            train_path, val_path = self.prepare_training_data()
            
            # Step 2: Train model
            logger.info("\nStep 2: Training model on SageMaker...")
            model_artifact = self.train_model(train_path, val_path)
            
            # Step 3: Deploy model
            logger.info("\nStep 3: Deploying model to endpoint...")
            endpoint_name = self.deploy_model(model_artifact)
            
            # Step 4: Test endpoint
            logger.info("\nStep 4: Testing deployed endpoint...")
            test_success = await self.test_endpoint(endpoint_name)
            
            if test_success:
                logger.info("\n✅ CULTURAL ADAPTATION MODEL PIPELINE COMPLETE!")
                logger.info(f"Endpoint: {endpoint_name}")
                return True
            else:
                logger.error("\n❌ Endpoint testing failed")
                return False
                
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            return False
    
    async def test_endpoint(self, endpoint_name: str) -> bool:
        """Test the deployed endpoint."""
        try:
            runtime = boto3.client("sagemaker-runtime", region_name=self.region)
            
            # Test input
            test_input = {
                "text": "You need to take your medication",
                "target_culture": "middle_east",
                "context": "medication_instructions"
            }
            
            # Invoke endpoint
            response = runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType="application/json",
                Body=json.dumps(test_input)
            )
            
            result = json.loads(response["Body"].read())
            logger.info(f"Test result: {result}")
            
            return "adapted_text" in result
            
        except Exception as e:
            logger.error(f"Endpoint test failed: {e}")
            return False


def main():
    """Main entry point."""
    logger.info("Starting Cultural Adaptation Model Training...")
    
    trainer = CulturalAdaptationModelTrainer()
    
    # Run async pipeline
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    success = loop.run_until_complete(trainer.run_full_pipeline())
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()