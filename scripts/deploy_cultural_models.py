#!/usr/bin/env python3
"""Deploy cultural adaptation models to SageMaker.

This script helps deploy pre-trained cultural adaptation models
to SageMaker endpoints for the Haven Health Passport system.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.translation.quality.aws_ai.sagemaker_cultural import (
    SageMakerCulturalTrainer,
    CulturalDataset,
    TrainingConfig
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_dataset():
    """Create a sample dataset for demonstration."""
    return CulturalDataset(
        language_pair="en-ar",
        cultural_region="middle_east",
        communication_patterns=[
            {
                "text": "The doctor will see you now.",
                "pattern_type": "medical_communication",
                "formal": True,
                "includes_honorific": False,
                "gender_specific": False,
                "indirect_communication": False,
                "family_involvement": False,
                "religious_references": False,
                "age_respectful": False,
                "authority_deference": True,
            },
            {
                "text": "Please have your family member present for the consultation.",
                "pattern_type": "medical_communication",
                "formal": True,
                "includes_honorific": False,
                "gender_specific": False,
                "indirect_communication": False,
                "family_involvement": True,
                "religious_references": False,
                "age_respectful": False,
                "authority_deference": False,
            },
            {
                "text": "Inshallah, your recovery will be swift.",
                "pattern_type": "medical_communication",
                "formal": True,
                "includes_honorific": False,
                "gender_specific": False,
                "indirect_communication": True,
                "family_involvement": False,
                "religious_references": True,
                "age_respectful": False,
                "authority_deference": False,
            }
        ],
        sensitive_topics=["mental_health", "reproductive_health"],
        preferred_expressions={
            "diabetes": "sugar disease",
            "hypertension": "high blood pressure"
        },
        sample_size=3
    )


async def deploy_models(args):
    """Deploy cultural adaptation models."""
    logger.info("Initializing cultural adaptation trainer...")
    
    trainer = SageMakerCulturalTrainer(
        region=args.region,
        role=args.role_arn if args.role_arn else None
    )
    
    if args.action == "train":
        logger.info("Training new cultural adaptation model...")
        
        # Create sample dataset
        dataset = create_sample_dataset()
        
        # Configure training
        config = TrainingConfig(
            model_name="cultural-pattern-classifier",
            instance_type=args.training_instance,
            instance_count=1,
            max_runtime=3600,
            hyperparameters={
                "epochs": args.epochs,
                "batch_size": 16,
                "learning_rate": 2e-5
            }
        )
        
        # Start training
        job_name = await trainer.train_cultural_sensitivity_classifier(dataset, config)
        logger.info(f"Training job started: {job_name}")
        
    elif args.action == "deploy":
        logger.info("Deploying cultural adaptation model...")
        
        if not args.model_path:
            logger.error("Model path is required for deployment")
            return
        
        # Deploy model
        endpoint_name = await trainer.deploy_cultural_model(
            model_name="cultural-pattern-classifier",
            model_artifact_path=args.model_path,
            instance_type=args.inference_instance,
            initial_instance_count=1
        )
        
        logger.info(f"Model deployed to endpoint: {endpoint_name}")
        
        # Test the endpoint
        if args.test:
            logger.info("Testing deployed endpoint...")
            result = await trainer.invoke_cultural_pattern_classifier(
                text="Please consult with your family before making this decision.",
                source_language="en",
                target_language="ar",
                region="middle_east"
            )
            logger.info(f"Test result: {json.dumps(result, indent=2)}")
            
    elif args.action == "list":
        logger.info("Listing cultural adaptation endpoints...")
        
        # List current endpoints
        logger.info(f"Configured endpoints:")
        for endpoint_type, endpoint_name in trainer.endpoints.items():
            status = "configured" if endpoint_name else "not configured"
            logger.info(f"  {endpoint_type}: {endpoint_name} ({status})")
            
    elif args.action == "test":
        logger.info("Testing cultural adaptation endpoints...")
        
        test_text = "The patient should follow up with their physician in two weeks."
        result = await trainer.invoke_cultural_pattern_classifier(
            text=test_text,
            source_language="en",
            target_language=args.target_language,
            region=args.cultural_region
        )
        
        logger.info(f"Test text: {test_text}")
        logger.info(f"Cultural patterns detected: {json.dumps(result, indent=2)}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Deploy cultural adaptation models to SageMaker"
    )
    
    parser.add_argument(
        "action",
        choices=["train", "deploy", "list", "test"],
        help="Action to perform"
    )
    
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)"
    )
    
    parser.add_argument(
        "--role-arn",
        help="SageMaker execution role ARN (auto-detected if not provided)"
    )
    
    parser.add_argument(
        "--model-path",
        help="S3 path to model artifacts (for deploy action)"
    )
    
    parser.add_argument(
        "--training-instance",
        default="ml.p3.2xlarge",
        help="Instance type for training (default: ml.p3.2xlarge)"
    )
    
    parser.add_argument(
        "--inference-instance",
        default="ml.m5.xlarge",
        help="Instance type for inference (default: ml.m5.xlarge)"
    )
    
    parser.add_argument(
        "--epochs",
        type=int,
        default=10,
        help="Number of training epochs (default: 10)"
    )
    
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test endpoint after deployment"
    )
    
    parser.add_argument(
        "--target-language",
        default="ar",
        help="Target language for testing (default: ar)"
    )
    
    parser.add_argument(
        "--cultural-region",
        default="middle_east",
        help="Cultural region for testing (default: middle_east)"
    )
    
    args = parser.parse_args()
    
    # Run async function
    import asyncio
    asyncio.run(deploy_models(args))


if __name__ == "__main__":
    main()