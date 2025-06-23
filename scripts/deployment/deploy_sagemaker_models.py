#!/usr/bin/env python3
"""
Deploy ML Models to AWS SageMaker for Haven Health Passport.

CRITICAL: This script deploys medical AI models for translation,
clinical validation, and patient data analysis. Model accuracy
directly impacts patient care quality.
"""

import os
import sys
import time
import boto3
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import tarfile
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SageMakerDeployment:
    """Deploy and configure ML models on AWS SageMaker."""
    
    def __init__(self, environment: str = "production"):
        self.environment = environment
        self.region = os.getenv("AWS_REGION", "us-east-1")
        
        # Initialize AWS clients
        self.sagemaker_client = boto3.client("sagemaker", region_name=self.region)
        self.s3_client = boto3.client("s3", region_name=self.region)
        self.iam_client = boto3.client("iam", region_name=self.region)
        
        # Configuration
        self.model_bucket = f"haven-health-{environment}-models"
        self.execution_role_name = f"haven-health-{environment}-sagemaker-role"
        
        logger.info(f"Initialized SageMaker deployment for {environment} in {self.region}")
    
    def create_execution_role(self) -> str:
        """Create SageMaker execution role."""
        try:
            # Check if role exists
            try:
                response = self.iam_client.get_role(RoleName=self.execution_role_name)
                role_arn = response["Role"]["Arn"]
                logger.info(f"Using existing role: {role_arn}")
                return role_arn
            except self.iam_client.exceptions.NoSuchEntityException:
                pass
            
            # Create role
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "sagemaker.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }
            
            response = self.iam_client.create_role(
                RoleName=self.execution_role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="SageMaker execution role for Haven Health Passport",
                Tags=[
                    {"Key": "Environment", "Value": self.environment},
                    {"Key": "Application", "Value": "haven-health-passport"}
                ]
            )
            
            role_arn = response["Role"]["Arn"]
            
            # Attach policies
            policies = [
                "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess",
                "arn:aws:iam::aws:policy/AmazonS3FullAccess",
                "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
            ]
            
            for policy in policies:
                self.iam_client.attach_role_policy(
                    RoleName=self.execution_role_name,
                    PolicyArn=policy
                )
            
            logger.info(f"Created SageMaker execution role: {role_arn}")
            
            # Wait for role to be available
            time.sleep(10)
            
            return role_arn
            
        except Exception as e:
            logger.error(f"Failed to create execution role: {e}")
            raise
    
    def prepare_model_artifacts(self, model_name: str, model_path: str) -> str:
        """Prepare and upload model artifacts to S3."""
        try:
            # Create tarball of model
            tar_filename = f"{model_name}.tar.gz"
            with tarfile.open(tar_filename, "w:gz") as tar:
                tar.add(model_path, arcname=os.path.basename(model_path))
            
            # Upload to S3
            s3_key = f"models/{model_name}/{datetime.utcnow().strftime('%Y%m%d%H%M%S')}/model.tar.gz"
            
            self.s3_client.upload_file(
                tar_filename,
                self.model_bucket,
                s3_key,
                ExtraArgs={
                    "ServerSideEncryption": "aws:kms",
                    "Metadata": {
                        "model_name": model_name,
                        "environment": self.environment,
                        "upload_timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            
            # Clean up local file
            os.remove(tar_filename)
            
            s3_uri = f"s3://{self.model_bucket}/{s3_key}"
            logger.info(f"Uploaded model artifacts to: {s3_uri}")
            
            return s3_uri
            
        except Exception as e:
            logger.error(f"Failed to prepare model artifacts: {e}")
            raise
    
    def deploy_medical_translation_model(self) -> Dict[str, Any]:
        """Deploy medical translation model."""
        model_name = f"haven-medical-translation-{self.environment}"
        
        try:
            # Get execution role
            role_arn = self.create_execution_role()
            
            # Model configuration
            model_config = {
                "model_name": model_name,
                "framework": "pytorch",
                "framework_version": "1.13.1",
                "py_version": "py39",
                "model_data": f"s3://{self.model_bucket}/pretrained/medical-translation/model.tar.gz",
                "environment": {
                    "MODEL_SERVER_WORKERS": "4",
                    "MODEL_SERVER_TIMEOUT": "3600",
                    "SAGEMAKER_MODEL_SERVER_WORKERS": "4"
                }
            }
            
            # Create model
            logger.info(f"Creating SageMaker model: {model_name}")
            
            primary_container = {
                "Image": f"763104351884.dkr.ecr.{self.region}.amazonaws.com/pytorch-inference:1.13.1-gpu-py39",
                "ModelDataUrl": model_config["model_data"],
                "Environment": model_config["environment"]
            }
            
            response = self.sagemaker_client.create_model(
                ModelName=model_name,
                PrimaryContainer=primary_container,
                ExecutionRoleArn=role_arn,
                Tags=[
                    {"Key": "Environment", "Value": self.environment},
                    {"Key": "Purpose", "Value": "medical-translation"},
                    {"Key": "ModelType", "Value": "transformer"}
                ]
            )
            
            logger.info(f"Created model: {response['ModelArn']}")
            
            # Create endpoint configuration
            endpoint_config_name = f"{model_name}-config"
            
            self.sagemaker_client.create_endpoint_config(
                EndpointConfigName=endpoint_config_name,
                ProductionVariants=[
                    {
                        "VariantName": "primary",
                        "ModelName": model_name,
                        "InitialInstanceCount": 1,
                        "InstanceType": "ml.g4dn.xlarge",  # GPU instance for translation
                        "InitialVariantWeight": 1.0
                    }
                ],
                DataCaptureConfig={
                    "EnableCapture": True,
                    "InitialSamplingPercentage": 10,
                    "DestinationS3Uri": f"s3://{self.model_bucket}/data-capture",
                    "CaptureOptions": [
                        {"CaptureMode": "Input"},
                        {"CaptureMode": "Output"}
                    ]
                }
            )
            
            # Create endpoint
            endpoint_name = f"{model_name}-endpoint"
            
            logger.info(f"Creating endpoint: {endpoint_name}")
            
            response = self.sagemaker_client.create_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=endpoint_config_name,
                Tags=[
                    {"Key": "Environment", "Value": self.environment},
                    {"Key": "AutoScaling", "Value": "enabled"}
                ]
            )
            
            # Wait for endpoint to be in service
            self._wait_for_endpoint(endpoint_name)
            
            # Configure auto-scaling
            self._configure_autoscaling(endpoint_name, "primary")
            
            return {
                "model_name": model_name,
                "endpoint_name": endpoint_name,
                "endpoint_arn": response["EndpointArn"],
                "status": "InService"
            }
            
        except Exception as e:
            logger.error(f"Failed to deploy medical translation model: {e}")
            raise
    
    def deploy_clinical_validation_model(self) -> Dict[str, Any]:
        """Deploy clinical validation model."""
        model_name = f"haven-clinical-validation-{self.environment}"
        
        try:
            # Get execution role
            role_arn = self.create_execution_role()
            
            # Create model for clinical text validation
            primary_container = {
                "Image": f"763104351884.dkr.ecr.{self.region}.amazonaws.com/huggingface-pytorch-inference:1.13.1-transformers4.26.0-gpu-py39",
                "ModelDataUrl": f"s3://{self.model_bucket}/pretrained/biobert/model.tar.gz",
                "Environment": {
                    "SAGEMAKER_PROGRAM": "inference.py",
                    "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/code",
                    "MODEL_CACHE_ROOT": "/opt/ml/model",
                    "SAGEMAKER_MODEL_SERVER_TIMEOUT": "3600"
                }
            }
            
            response = self.sagemaker_client.create_model(
                ModelName=model_name,
                PrimaryContainer=primary_container,
                ExecutionRoleArn=role_arn
            )
            
            # Create endpoint configuration
            endpoint_config_name = f"{model_name}-config"
            
            self.sagemaker_client.create_endpoint_config(
                EndpointConfigName=endpoint_config_name,
                ProductionVariants=[
                    {
                        "VariantName": "primary",
                        "ModelName": model_name,
                        "InitialInstanceCount": 2,  # Higher availability
                        "InstanceType": "ml.m5.xlarge",
                        "InitialVariantWeight": 1.0
                    }
                ]
            )
            
            # Create endpoint
            endpoint_name = f"{model_name}-endpoint"
            
            response = self.sagemaker_client.create_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=endpoint_config_name
            )
            
            # Wait for endpoint
            self._wait_for_endpoint(endpoint_name)
            
            return {
                "model_name": model_name,
                "endpoint_name": endpoint_name,
                "endpoint_arn": response["EndpointArn"],
                "status": "InService"
            }
            
        except Exception as e:
            logger.error(f"Failed to deploy clinical validation model: {e}")
            raise
    
    def deploy_embedding_model(self) -> Dict[str, Any]:
        """Deploy medical embedding model."""
        model_name = f"haven-medical-embeddings-{self.environment}"
        
        try:
            # Get execution role
            role_arn = self.create_execution_role()
            
            # Create model for medical embeddings
            primary_container = {
                "Image": f"763104351884.dkr.ecr.{self.region}.amazonaws.com/pytorch-inference:1.13.1-cpu-py39",
                "ModelDataUrl": f"s3://{self.model_bucket}/pretrained/biobert-embeddings/model.tar.gz",
                "Environment": {
                    "MODEL_CACHE_ROOT": "/opt/ml/model",
                    "SAGEMAKER_MODEL_SERVER_WORKERS": "2"
                }
            }
            
            response = self.sagemaker_client.create_model(
                ModelName=model_name,
                PrimaryContainer=primary_container,
                ExecutionRoleArn=role_arn
            )
            
            # Create endpoint configuration
            endpoint_config_name = f"{model_name}-config"
            
            self.sagemaker_client.create_endpoint_config(
                EndpointConfigName=endpoint_config_name,
                ProductionVariants=[
                    {
                        "VariantName": "primary",
                        "ModelName": model_name,
                        "InitialInstanceCount": 2,
                        "InstanceType": "ml.m5.large",
                        "InitialVariantWeight": 1.0
                    }
                ]
            )
            
            # Create endpoint
            endpoint_name = f"{model_name}-endpoint"
            
            response = self.sagemaker_client.create_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=endpoint_config_name
            )
            
            # Wait for endpoint
            self._wait_for_endpoint(endpoint_name)
            
            return {
                "model_name": model_name,
                "endpoint_name": endpoint_name,
                "endpoint_arn": response["EndpointArn"],
                "status": "InService"
            }
            
        except Exception as e:
            logger.error(f"Failed to deploy embedding model: {e}")
            raise
    
    def _wait_for_endpoint(self, endpoint_name: str, timeout: int = 1800):
        """Wait for endpoint to be in service."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = self.sagemaker_client.describe_endpoint(
                EndpointName=endpoint_name
            )
            
            status = response["EndpointStatus"]
            
            if status == "InService":
                logger.info(f"Endpoint {endpoint_name} is in service")
                return
            elif status == "Failed":
                raise RuntimeError(f"Endpoint creation failed: {response.get('FailureReason')}")
            else:
                logger.info(f"Endpoint status: {status}, waiting...")
                time.sleep(30)
        
        raise TimeoutError(f"Endpoint did not become active within {timeout} seconds")
    
    def _configure_autoscaling(self, endpoint_name: str, variant_name: str):
        """Configure auto-scaling for endpoint."""
        try:
            autoscaling_client = boto3.client("application-autoscaling", region_name=self.region)
            
            # Register scalable target
            resource_id = f"endpoint/{endpoint_name}/variant/{variant_name}"
            
            autoscaling_client.register_scalable_target(
                ServiceNamespace="sagemaker",
                ResourceId=resource_id,
                ScalableDimension="sagemaker:variant:DesiredInstanceCount",
                MinCapacity=1,
                MaxCapacity=5
            )
            
            # Create scaling policy
            autoscaling_client.put_scaling_policy(
                PolicyName=f"{endpoint_name}-scaling-policy",
                ServiceNamespace="sagemaker",
                ResourceId=resource_id,
                ScalableDimension="sagemaker:variant:DesiredInstanceCount",
                PolicyType="TargetTrackingScaling",
                TargetTrackingScalingPolicyConfiguration={
                    "TargetValue": 70.0,
                    "PredefinedMetricSpecification": {
                        "PredefinedMetricType": "SageMakerVariantInvocationsPerInstance"
                    },
                    "ScaleInCooldown": 300,
                    "ScaleOutCooldown": 60
                }
            )
            
            logger.info(f"Configured auto-scaling for {endpoint_name}")
            
        except Exception as e:
            logger.error(f"Failed to configure auto-scaling: {e}")
            # Non-critical error
    
    def generate_deployment_config(self, deployment_info: Dict[str, Any]) -> None:
        """Generate deployment configuration file."""
        config = {
            "sagemaker": {
                "region": self.region,
                "environment": self.environment,
                "models": deployment_info
            },
            "deployment": {
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            }
        }
        
        config_filename = f"sagemaker_{self.environment}_config.json"
        with open(config_filename, "w") as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Deployment configuration saved to: {config_filename}")
    
    def test_endpoints(self, endpoints: List[Dict[str, Any]]) -> None:
        """Test deployed endpoints."""
        runtime_client = boto3.client("sagemaker-runtime", region_name=self.region)
        
        for endpoint in endpoints:
            endpoint_name = endpoint["endpoint_name"]
            
            try:
                # Test payload based on model type
                if "translation" in endpoint_name:
                    test_payload = {
                        "text": "The patient has hypertension",
                        "source_language": "en",
                        "target_language": "es"
                    }
                elif "validation" in endpoint_name:
                    test_payload = {
                        "text": "Patient presents with fever and cough",
                        "validate": True
                    }
                else:  # embeddings
                    test_payload = {
                        "text": "diabetes mellitus type 2"
                    }
                
                response = runtime_client.invoke_endpoint(
                    EndpointName=endpoint_name,
                    ContentType="application/json",
                    Body=json.dumps(test_payload)
                )
                
                result = json.loads(response["Body"].read())
                logger.info(f"Endpoint {endpoint_name} test successful")
                
            except Exception as e:
                logger.error(f"Endpoint {endpoint_name} test failed: {e}")


def main():
    """Main deployment function."""
    # Get environment
    environment = os.getenv("ENVIRONMENT", "staging")
    
    if environment == "production" and not os.getenv("CONFIRM_PRODUCTION"):
        print("CRITICAL: Deploying ML models to production!")
        print("Set CONFIRM_PRODUCTION=true to proceed")
        sys.exit(1)
    
    # Deploy models
    deployer = SageMakerDeployment(environment)
    
    try:
        logger.info("Starting SageMaker deployment...")
        
        deployed_models = []
        
        # Deploy medical translation model
        logger.info("Deploying medical translation model...")
        translation_model = deployer.deploy_medical_translation_model()
        deployed_models.append(translation_model)
        
        # Deploy clinical validation model
        logger.info("Deploying clinical validation model...")
        validation_model = deployer.deploy_clinical_validation_model()
        deployed_models.append(validation_model)
        
        # Deploy embedding model
        logger.info("Deploying medical embedding model...")
        embedding_model = deployer.deploy_embedding_model()
        deployed_models.append(embedding_model)
        
        # Test endpoints
        logger.info("Testing deployed endpoints...")
        deployer.test_endpoints(deployed_models)
        
        # Generate configuration
        deployer.generate_deployment_config(deployed_models)
        
        logger.info("SageMaker deployment completed successfully!")
        
        for model in deployed_models:
            logger.info(f"Model: {model['model_name']}")
            logger.info(f"Endpoint: {model['endpoint_name']}")
            logger.info(f"Status: {model['status']}")
            logger.info("-" * 50)
        
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
