#!/usr/bin/env python3
"""
ML Model Deployment for Haven Health Passport
Deploys medical ML models to Amazon SageMaker for production use
CRITICAL: These models make medical predictions for real patients
"""

import os
import sys
import json
import boto3
import argparse
import logging
from datetime import datetime
import tarfile
import shutil
from typing import Dict, List

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MLModelDeployer:
    """Deploys ML models to SageMaker for Haven Health Passport"""
    
    MODELS = {
        'risk-prediction': {
            'name': 'PatientRiskPrediction',
            'framework': 'pytorch',
            'instance_type': 'ml.m5.xlarge',
            'model_data': 's3://haven-health-ml-models/risk-prediction/model.tar.gz',
            'description': 'Predicts patient health risk scores'
        },
        'treatment-recommendation': {
            'name': 'TreatmentRecommendation',
            'framework': 'tensorflow',
            'instance_type': 'ml.m5.2xlarge',
            'model_data': 's3://haven-health-ml-models/treatment-rec/model.tar.gz',
            'description': 'Recommends treatment options based on patient history'
        },
        'pubmedbert': {
            'name': 'PubMedBERT',
            'framework': 'huggingface',
            'instance_type': 'ml.g4dn.xlarge',
            'model_data': 's3://haven-health-ml-models/pubmedbert/model.tar.gz',
            'description': 'Medical text understanding and entity extraction'
        },
        'bioclinicalbert': {
            'name': 'BioClinicalBERT',
            'framework': 'huggingface',
            'instance_type': 'ml.g4dn.xlarge',
            'model_data': 's3://haven-health-ml-models/bioclinicalbert/model.tar.gz',
            'description': 'Clinical note analysis and information extraction'
        }
    }
    
    def __init__(self, environment: str, region: str = 'us-east-1'):
        self.environment = environment
        self.region = region
        self.sagemaker_client = boto3.client('sagemaker', region_name=region)
        self.s3_client = boto3.client('s3', region_name=region)
        self.iam_client = boto3.client('iam')
        self.role_arn = None
    
    def create_sagemaker_role(self) -> str:
        """Create or get SageMaker execution role"""
        role_name = f"HavenHealthSageMaker{self.environment.capitalize()}Role"
        
        try:
            # Check if role exists
            response = self.iam_client.get_role(RoleName=role_name)
            self.role_arn = response['Role']['Arn']
            logger.info(f"Using existing SageMaker role: {role_name}")
            return self.role_arn
            
        except self.iam_client.exceptions.NoSuchEntityException:
            # Create new role
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "sagemaker.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }
            
            response = self.iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f"SageMaker execution role for Haven Health {self.environment}",
                Tags=[
                    {'Key': 'Environment', 'Value': self.environment},
                    {'Key': 'Service', 'Value': 'haven-health-passport'}
                ]
            )
            
            # Attach policies
            policies = [
                'arn:aws:iam::aws:policy/AmazonSageMakerFullAccess',
                'arn:aws:iam::aws:policy/AmazonS3FullAccess',
                'arn:aws:iam::aws:policy/CloudWatchLogsFullAccess'
            ]
            
            for policy_arn in policies:
                self.iam_client.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn=policy_arn
                )
            
            self.role_arn = response['Role']['Arn']
            logger.info(f"Created SageMaker role: {role_name}")
            
            # Wait for role to be available
            import time
            time.sleep(10)
            
            return self.role_arn
    
    def create_model(self, model_key: str) -> str:
        """Create SageMaker model"""
        model_config = self.MODELS[model_key]
        model_name = f"haven-health-{self.environment}-{model_key}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Get appropriate container image
        if model_config['framework'] == 'pytorch':
            image_uri = f"763104351884.dkr.ecr.{self.region}.amazonaws.com/pytorch-inference:1.13.1-gpu-py39-cu117-ubuntu20.04-sagemaker"
        elif model_config['framework'] == 'tensorflow':
            image_uri = f"763104351884.dkr.ecr.{self.region}.amazonaws.com/tensorflow-inference:2.11.0-gpu"
        elif model_config['framework'] == 'huggingface':
            image_uri = f"763104351884.dkr.ecr.{self.region}.amazonaws.com/huggingface-pytorch-inference:1.13.1-transformers4.26.0-gpu-py39-cu117-ubuntu20.04"
        else:
            raise ValueError(f"Unsupported framework: {model_config['framework']}")
        
        try:
            response = self.sagemaker_client.create_model(
                ModelName=model_name,
                PrimaryContainer={
                    'Image': image_uri,
                    'ModelDataUrl': model_config['model_data'],
                    'Environment': {
                        'SAGEMAKER_PROGRAM': 'inference.py',
                        'SAGEMAKER_SUBMIT_DIRECTORY': model_config['model_data'],
                        'SAGEMAKER_REGION': self.region
                    }
                },
                ExecutionRoleArn=self.role_arn,
                Tags=[
                    {'Key': 'Environment', 'Value': self.environment},
                    {'Key': 'Service', 'Value': 'haven-health-passport'},
                    {'Key': 'Model', 'Value': model_config['name']}
                ]
            )
            
            logger.info(f"Created model: {model_name}")
            return model_name
            
        except Exception as e:
            logger.error(f"Failed to create model {model_key}: {str(e)}")
            raise
    
    def create_endpoint_config(self, model_name: str, model_key: str) -> str:
        """Create endpoint configuration"""
        model_config = self.MODELS[model_key]
        config_name = f"{model_name}-config"
        
        try:
            response = self.sagemaker_client.create_endpoint_config(
                EndpointConfigName=config_name,
                ProductionVariants=[{
                    'VariantName': 'primary',
                    'ModelName': model_name,
                    'InstanceType': model_config['instance_type'],
                    'InitialInstanceCount': 1,
                    'InitialVariantWeight': 1.0
                }],
                DataCaptureConfig={
                    'EnableCapture': True,
                    'InitialSamplingPercentage': 100,
                    'DestinationS3Uri': f"s3://haven-health-{self.environment}-ml-models/data-capture",
                    'CaptureOptions': [
                        {'CaptureMode': 'Input'},
                        {'CaptureMode': 'Output'}
                    ]
                },
                Tags=[
                    {'Key': 'Environment', 'Value': self.environment},
                    {'Key': 'Service', 'Value': 'haven-health-passport'}
                ]
            )
            
            logger.info(f"Created endpoint config: {config_name}")
            return config_name
            
        except Exception as e:
            logger.error(f"Failed to create endpoint config: {str(e)}")
            raise
    
    def deploy_endpoint(self, config_name: str, model_key: str) -> str:
        """Deploy model endpoint"""
        endpoint_name = f"haven-health-{self.environment}-{model_key}"
        
        try:
            # Check if endpoint exists
            try:
                self.sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
                logger.info(f"Endpoint already exists: {endpoint_name}")
                
                # Update endpoint with new config
                self.sagemaker_client.update_endpoint(
                    EndpointName=endpoint_name,
                    EndpointConfigName=config_name
                )
                logger.info(f"Updated endpoint: {endpoint_name}")
                
            except self.sagemaker_client.exceptions.EndpointNotFound:
                # Create new endpoint
                response = self.sagemaker_client.create_endpoint(
                    EndpointName=endpoint_name,
                    EndpointConfigName=config_name,
                    Tags=[
                        {'Key': 'Environment', 'Value': self.environment},
                        {'Key': 'Service', 'Value': 'haven-health-passport'},
                        {'Key': 'Model', 'Value': self.MODELS[model_key]['name']}
                    ]
                )
                logger.info(f"Created endpoint: {endpoint_name}")
            
            # Wait for endpoint to be in service
            print(f"Waiting for endpoint {endpoint_name} to be in service...")
            waiter = self.sagemaker_client.get_waiter('endpoint_in_service')
            waiter.wait(
                EndpointName=endpoint_name,
                WaiterConfig={'Delay': 30, 'MaxAttempts': 30}
            )
            
            return endpoint_name
            
        except Exception as e:
            logger.error(f"Failed to deploy endpoint: {str(e)}")
            raise
    
    def setup_model_monitoring(self, endpoint_name: str, model_key: str) -> bool:
        """Set up model monitoring for drift detection"""
        try:
            monitoring_schedule_name = f"{endpoint_name}-monitoring"
            
            # Create monitoring schedule
            self.sagemaker_client.create_model_quality_job_definition(
                JobDefinitionName=f"{monitoring_schedule_name}-quality",
                ModelQualityBaselineConfig={
                    'ConstraintsResource': {
                        'S3Uri': f"s3://haven-health-{self.environment}-ml-models/monitoring/constraints.json"
                    }
                },
                ModelQualityAppSpecification={
                    'ImageUri': f"246618743249.dkr.ecr.{self.region}.amazonaws.com/sagemaker-model-monitor-analyzer",
                    'ProblemType': 'BinaryClassification' if 'risk' in model_key else 'MulticlassClassification'
                },
                ModelQualityJobInput={
                    'EndpointInput': {
                        'EndpointName': endpoint_name,
                        'LocalPath': '/opt/ml/processing/input',
                        'S3InputMode': 'File',
                        'S3DataDistributionType': 'FullyReplicated'
                    }
                },
                ModelQualityJobOutputConfig={
                    'MonitoringOutputs': [{
                        'S3Output': {
                            'S3Uri': f"s3://haven-health-{self.environment}-ml-models/monitoring/output",
                            'LocalPath': '/opt/ml/processing/output'
                        }
                    }]
                },
                JobResources={
                    'ClusterConfig': {
                        'InstanceCount': 1,
                        'InstanceType': 'ml.m5.xlarge',
                        'VolumeSizeInGB': 30
                    }
                },
                RoleArn=self.role_arn
            )
            
            logger.info(f"Set up model monitoring for: {endpoint_name}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to set up monitoring: {str(e)}")
            return False
    
    def deploy_model(self, model_key: str) -> bool:
        """Deploy a single model"""
        model_config = self.MODELS[model_key]
        print(f"\n{'='*60}")
        print(f"Deploying {model_config['name']}")
        print(f"Description: {model_config['description']}")
        print(f"{'='*60}")
        
        try:
            # Create model
            model_name = self.create_model(model_key)
            
            # Create endpoint configuration
            config_name = self.create_endpoint_config(model_name, model_key)
            
            # Deploy endpoint
            endpoint_name = self.deploy_endpoint(config_name, model_key)
            
            # Set up monitoring
            self.setup_model_monitoring(endpoint_name, model_key)
            
            # Store endpoint name in parameter store
            ssm_client = boto3.client('ssm', region_name=self.region)
            ssm_client.put_parameter(
                Name=f"/haven-health/{self.environment}/ml/endpoints/{model_key}",
                Value=endpoint_name,
                Type='String',
                Overwrite=True
            )
            
            print(f"✅ Successfully deployed {model_config['name']}")
            print(f"Endpoint: {endpoint_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to deploy {model_key}: {str(e)}")
            print(f"❌ Failed to deploy {model_config['name']}")
            return False
    
    def deploy_all_models(self) -> None:
        """Deploy all ML models"""
        print("\n" + "="*80)
        print("Haven Health Passport - ML Model Deployment")
        print(f"Environment: {self.environment.upper()}")
        print(f"Region: {self.region}")
        print("="*80)
        print("\n⚠️  CRITICAL: These models make medical predictions for real patients.")
        print("Ensure models have been properly validated before deployment.\n")
        
        # Create SageMaker role
        print("Setting up SageMaker execution role...")
        self.create_sagemaker_role()
        
        # Deploy models
        deployed = []
        failed = []
        
        for model_key in self.MODELS:
            try:
                if self.deploy_model(model_key):
                    deployed.append(model_key)
                else:
                    failed.append(model_key)
            except KeyboardInterrupt:
                print("\n\n⚠️  Deployment interrupted by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error deploying {model_key}: {str(e)}")
                failed.append(model_key)
        
        # Summary
        print("\n" + "="*80)
        print("Deployment Summary")
        print("="*80)
        print(f"✅ Successfully deployed: {len(deployed)}")
        for model_key in deployed:
            print(f"   - {self.MODELS[model_key]['name']}")
        
        if failed:
            print(f"\n❌ Failed to deploy: {len(failed)}")
            for model_key in failed:
                print(f"   - {self.MODELS[model_key]['name']}")
            print("\n⚠️  WARNING: Some models failed to deploy!")
        else:
            print("\n✅ All models deployed successfully!")
            print("\nNext steps:")
            print("1. Test model endpoints with sample data")
            print("2. Set up monitoring alerts")
            print("3. Configure auto-scaling policies")
            print("4. Validate model predictions with medical team")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Deploy ML models for Haven Health Passport'
    )
    parser.add_argument(
        '--environment',
        choices=['development', 'staging', 'production'],
        required=True,
        help='Target environment for deployment'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region for deployment (default: us-east-1)'
    )
    parser.add_argument(
        '--model',
        choices=list(MLModelDeployer.MODELS.keys()),
        help='Deploy specific model only'
    )
    
    args = parser.parse_args()
    
    # Production safety check
    if args.environment == 'production':
        print("\n⚠️  WARNING: Deploying models to PRODUCTION!")
        print("These models will make predictions for real patients.")
        confirm = input("Type 'DEPLOY PRODUCTION' to continue: ")
        if confirm != 'DEPLOY PRODUCTION':
            print("Deployment cancelled.")
            sys.exit(0)
    
    # Check AWS credentials
    try:
        boto3.client('sts').get_caller_identity()
    except Exception as e:
        print(f"\n❌ AWS credentials not configured: {str(e)}")
        print("Please configure AWS credentials before running this script.")
        sys.exit(1)
    
    # Run deployment
    deployer = MLModelDeployer(args.environment, args.region)
    
    if args.model:
        # Deploy specific model
        success = deployer.deploy_model(args.model)
        sys.exit(0 if success else 1)
    else:
        # Deploy all models
        deployer.deploy_all_models()


if __name__ == '__main__':
    main()
