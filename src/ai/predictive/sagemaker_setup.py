"""SageMaker setup and management module."""

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import boto3

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Types of ML models."""

    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    ANOMALY_DETECTION = "anomaly_detection"
    TIME_SERIES = "time_series"


@dataclass
class SageMakerConfig:
    """Configuration for SageMaker."""

    domain_name: str = "haven-health-ml"
    region: str = "us-east-1"
    role_arn: str = ""
    instance_type: str = "ml.t3.medium"
    max_runtime_seconds: int = 3600
    enable_monitoring: bool = True
    enable_autoscaling: bool = True
    min_instances: int = 1
    max_instances: int = 5


class SageMakerManager:
    """Manage SageMaker resources for Haven Health Passport."""

    def __init__(self, config: Optional[SageMakerConfig] = None):
        """Initialize SageMaker manager."""
        self.config = config or SageMakerConfig()
        self.sagemaker_client = boto3.client(
            "sagemaker", region_name=self.config.region
        )
        self.runtime_client = boto3.client(
            "sagemaker-runtime", region_name=self.config.region
        )

    def create_domain(self) -> Dict[str, Any]:
        """Create SageMaker domain."""
        try:
            response = self.sagemaker_client.create_domain(
                DomainName=self.config.domain_name,
                AuthMode="IAM",
                DefaultUserSettings={"ExecutionRole": self.config.role_arn},
                SubnetIds=["subnet-12345"],  # Replace with actual subnet
                VpcId="vpc-12345",  # Replace with actual VPC
            )
            logger.info("Created SageMaker domain: %s", self.config.domain_name)
            return dict(response)
        except Exception as e:
            logger.error("Failed to create domain: %s", e)
            raise

    def setup_model_registry(self) -> None:
        """Set up model registry for versioning."""
        try:
            self.sagemaker_client.create_model_package_group(
                ModelPackageGroupName=f"{self.config.domain_name}-models",
                ModelPackageGroupDescription="Haven Health ML models",
            )
            logger.info("Model registry created")
        except Exception as e:  # pylint: disable=broad-exception-caught
            if "already exists" in str(e):
                logger.info("Model registry already exists")
            else:
                raise

    def configure_endpoints(
        self, model_name: str, model_type: ModelType
    ) -> Dict[str, Any]:
        """Configure model endpoints with auto-scaling."""
        endpoint_config_name = f"{model_name}-{model_type.value}-config"
        endpoint_name = f"{model_name}-{model_type.value}-endpoint"

        # Create endpoint configuration
        self.sagemaker_client.create_endpoint_config(
            EndpointConfigName=endpoint_config_name,
            ProductionVariants=[
                {
                    "VariantName": "primary",
                    "ModelName": model_name,
                    "InitialInstanceCount": self.config.min_instances,
                    "InstanceType": self.config.instance_type,
                }
            ],
        )

        # Create endpoint
        response = self.sagemaker_client.create_endpoint(
            EndpointName=endpoint_name, EndpointConfigName=endpoint_config_name
        )

        # Configure auto-scaling if enabled
        if self.config.enable_autoscaling:
            self._configure_autoscaling(endpoint_name)

        return dict(response)

    def _configure_autoscaling(self, endpoint_name: str) -> None:
        """Configure auto-scaling for endpoint."""
        autoscaling = boto3.client(
            "application-autoscaling", region_name=self.config.region
        )

        # Register scalable target
        autoscaling.register_scalable_target(
            ServiceNamespace="sagemaker",
            ResourceId=f"endpoint/{endpoint_name}/variant/primary",
            ScalableDimension="sagemaker:variant:DesiredInstanceCount",
            MinCapacity=self.config.min_instances,
            MaxCapacity=self.config.max_instances,
        )

    def setup_monitoring(self, endpoint_name: str) -> None:
        """Set up monitoring dashboards for model performance."""
        cloudwatch = boto3.client("cloudwatch", region_name=self.config.region)

        # Create CloudWatch dashboard
        dashboard_body = {
            "widgets": [
                {
                    "type": "metric",
                    "properties": {
                        "metrics": [
                            [
                                "AWS/SageMaker",
                                "Invocations",
                                {"EndpointName": endpoint_name},
                            ],
                            [".", "ModelLatency", {"EndpointName": endpoint_name}],
                            [".", "4XXError", {"EndpointName": endpoint_name}],
                            [".", "5XXError", {"EndpointName": endpoint_name}],
                        ],
                        "period": 300,
                        "stat": "Average",
                        "region": self.config.region,
                        "title": f"Model Performance - {endpoint_name}",
                    },
                }
            ]
        }

        cloudwatch.put_dashboard(
            DashboardName=f"{endpoint_name}-monitoring",
            DashboardBody=json.dumps(dashboard_body),
        )

    def create_feature_store(
        self, feature_group_name: str, features: List[Dict[str, Any]]
    ) -> None:
        """Create feature store for model features."""
        try:
            self.sagemaker_client.create_feature_group(
                FeatureGroupName=feature_group_name,
                RecordIdentifierFeatureName="patient_id",
                EventTimeFeatureName="event_time",
                FeatureDefinitions=features,
                OnlineStoreConfig={"EnableOnlineStore": True},
                RoleArn=self.config.role_arn,
            )
            logger.info("Created feature group: %s", feature_group_name)
        except Exception as e:
            logger.error("Failed to create feature group: %s", e)
            raise
