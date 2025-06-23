"""AWS service integration module."""

import io
import json
import os
import zipfile
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from src.config import get_settings
from src.healthcare.fhir_validator import FHIRValidator
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class AWSServiceManager:
    """Manager for AWS service integrations."""

    def __init__(self) -> None:
        """Initialize AWS service clients."""
        self.region = settings.aws_region
        self.account_id = None

        # Initialize FHIR validator
        self.fhir_validator = FHIRValidator()

        # Initialize AWS SDK with proper configuration
        self._configure_aws_sdk()

        # Initialize service clients
        self._init_service_clients()

        # Get account ID
        self._get_account_id()

    def _configure_aws_sdk(self) -> None:
        """Configure AWS SDK with credentials and region."""
        # Set AWS configuration
        boto3.setup_default_session(
            region_name=self.region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

        logger.info(f"Configured AWS SDK for region: {self.region}")

    def _init_service_clients(self) -> None:
        """Initialize all AWS service clients."""
        try:
            # Core services
            self.s3_client = boto3.client("s3")
            self.dynamodb_client = boto3.client("dynamodb")
            self.dynamodb_resource = boto3.resource("dynamodb")
            self.healthlake_client = boto3.client("healthlake")
            self.cognito_client = boto3.client("cognito-idp")
            self.secrets_manager_client = boto3.client("secretsmanager")
            self.cloudwatch_client = boto3.client("cloudwatch")
            self.logs_client = boto3.client("logs")
            self.lambda_client = boto3.client("lambda")
            self.apigateway_client = boto3.client("apigateway")
            self.cloudfront_client = boto3.client("cloudfront")

            logger.info("Initialized all AWS service clients")

        except ClientError as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            raise

    def _get_account_id(self) -> None:
        """Get AWS account ID."""
        try:
            sts_client = boto3.client("sts")
            response = sts_client.get_caller_identity()
            self.account_id = response["Account"]
            logger.info(f"AWS Account ID: {self.account_id}")
        except ClientError as e:
            logger.error(f"Failed to get account ID: {e}")

    # S3 Operations for Document Storage

    def create_s3_bucket(self, bucket_name: str) -> bool:
        """Create S3 bucket for document storage."""
        try:
            if self.region == "us-east-1":
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": self.region},
                )

            # Enable versioning
            self.s3_client.put_bucket_versioning(
                Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
            )

            # Enable encryption
            self.s3_client.put_bucket_encryption(
                Bucket=bucket_name,
                ServerSideEncryptionConfiguration={
                    "Rules": [
                        {
                            "ApplyServerSideEncryptionByDefault": {
                                "SSEAlgorithm": "AES256"
                            }
                        }
                    ]
                },
            )

            # Set lifecycle policy for compliance
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=bucket_name,
                LifecycleConfiguration={
                    "Rules": [
                        {
                            "ID": "7YearRetention",
                            "Status": "Enabled",
                            "Transitions": [
                                {"Days": 90, "StorageClass": "STANDARD_IA"},
                                {"Days": 365, "StorageClass": "GLACIER"},
                                {"Days": 730, "StorageClass": "DEEP_ARCHIVE"},
                            ],
                            "NoncurrentVersionTransitions": [
                                {"NoncurrentDays": 30, "StorageClass": "STANDARD_IA"}
                            ],
                            "AbortIncompleteMultipartUpload": {
                                "DaysAfterInitiation": 7
                            },
                        }
                    ]
                },
            )

            logger.info(f"Created S3 bucket: {bucket_name}")
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "BucketAlreadyExists":
                logger.info(f"Bucket already exists: {bucket_name}")
                return True
            logger.error(f"Failed to create S3 bucket: {e}")
            return False

    # DynamoDB Tables for Metadata

    def create_dynamodb_tables(self) -> bool:
        """Create DynamoDB tables for metadata storage."""
        tables = [
            {
                "TableName": "haven-metadata",
                "KeySchema": [
                    {"AttributeName": "id", "KeyType": "HASH"},
                    {"AttributeName": "type", "KeyType": "RANGE"},
                ],
                "AttributeDefinitions": [
                    {"AttributeName": "id", "AttributeType": "S"},
                    {"AttributeName": "type", "AttributeType": "S"},
                    {"AttributeName": "patient_id", "AttributeType": "S"},
                    {"AttributeName": "created_at", "AttributeType": "N"},
                ],
                "GlobalSecondaryIndexes": [
                    {
                        "IndexName": "patient-index",
                        "Keys": [
                            {"AttributeName": "patient_id", "KeyType": "HASH"},
                            {"AttributeName": "created_at", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5,
                        },
                    }
                ],
                "BillingMode": "PAY_PER_REQUEST",
                "StreamSpecification": {
                    "StreamEnabled": True,
                    "StreamViewType": "NEW_AND_OLD_IMAGES",
                },
                "SSESpecification": {"Enabled": True},
                "PointInTimeRecoverySpecification": {
                    "PointInTimeRecoveryEnabled": True
                },
            },
            {
                "TableName": "haven-cache",
                "KeySchema": [{"AttributeName": "cache_key", "KeyType": "HASH"}],
                "AttributeDefinitions": [
                    {"AttributeName": "cache_key", "AttributeType": "S"}
                ],
                "BillingMode": "PAY_PER_REQUEST",
                "TimeToLiveSpecification": {"Enabled": True, "AttributeName": "ttl"},
                "SSESpecification": {"Enabled": True},
            },
        ]

        for table_config in tables:
            try:
                table_name = table_config["TableName"]

                # Check if table exists
                try:
                    self.dynamodb_client.describe_table(TableName=table_name)
                    logger.info(f"DynamoDB table already exists: {table_name}")
                    continue
                except ClientError as e:
                    if e.response["Error"]["Code"] != "ResourceNotFoundException":
                        raise

                # Create table
                self.dynamodb_client.create_table(**table_config)

                # Wait for table to be active
                waiter = self.dynamodb_client.get_waiter("table_exists")
                waiter.wait(TableName=table_name)

                logger.info(f"Created DynamoDB table: {table_name}")

            except ClientError as e:
                logger.error(f"Failed to create DynamoDB table {table_name}: {e}")
                return False

        return True

    # HealthLake Integration

    def create_healthlake_datastore(self) -> Optional[str]:
        """Create AWS HealthLake datastore for FHIR resources."""
        try:
            datastore_name = f"haven-health-{self.region}"

            # Check if datastore exists
            response = self.healthlake_client.list_fhir_datastores()
            for datastore in response.get("DatastorePropertiesList", []):
                if datastore["DatastoreName"] == datastore_name:
                    logger.info(
                        f"HealthLake datastore already exists: {datastore_name}"
                    )
                    return str(datastore["DatastoreId"])

            # Create datastore
            response = self.healthlake_client.create_fhir_datastore(
                DatastoreName=datastore_name,
                DatastoreTypeVersion="R4",
                PreloadDataConfig={"PreloadDataType": "SYNTHEA"},
                SseConfiguration={
                    "KmsEncryptionConfig": {"CmkType": "AWS_OWNED_KMS_KEY"}
                },
            )

            datastore_id = str(response["DatastoreId"])
            logger.info(f"Created HealthLake datastore: {datastore_id}")

            # Wait for datastore to be active
            waiter = self.healthlake_client.get_waiter("fhir_datastore_active")
            waiter.wait(DatastoreId=datastore_id)

            return datastore_id

        except ClientError as e:
            logger.error(f"Failed to create HealthLake datastore: {e}")
            return None

    def store_fhir_resource(
        self, datastore_id: str, resource_type: str, resource_data: Dict[str, Any]
    ) -> Optional[str]:
        """Store FHIR resource in HealthLake with validation.

        Args:
            datastore_id: HealthLake datastore ID
            resource_type: FHIR resource type (e.g., 'Patient', 'Observation')
            resource_data: FHIR resource data to store

        Returns:
            Resource ID if successful, None otherwise
        """
        try:
            # Validate FHIR resource
            validation_result = self.fhir_validator.validate_resource(
                resource_type, resource_data
            )

            if not validation_result["valid"]:
                logger.error(
                    f"FHIR validation failed for {resource_type}: {validation_result['errors']}"
                )
                return None

            # Log warnings if any
            if validation_result.get("warnings"):
                logger.warning(
                    f"FHIR validation warnings for {resource_type}: {validation_result['warnings']}"
                )

            # Store resource in HealthLake
            # Note: This is a placeholder - actual HealthLake API call would go here
            logger.info(
                f"Storing {resource_type} resource in HealthLake datastore {datastore_id}"
            )

            # In a real implementation, you would use boto3 to call HealthLake API
            # response = self.healthlake_client.create_resource(
            #     DatastoreId=datastore_id,
            #     ResourceType=resource_type,
            #     Resource=json.dumps(resource_data)
            # )

            return f"{resource_type}/{datastore_id}"  # Placeholder return

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Failed to store FHIR resource: {e}")
            return None

    # Cognito Authentication

    def create_cognito_user_pool(self) -> Optional[str]:
        """Create Cognito user pool for authentication."""
        try:
            pool_name = "haven-health-users"

            # Check if pool exists
            response = self.cognito_client.list_user_pools(MaxResults=50)
            for pool in response.get("UserPools", []):
                if pool["Name"] == pool_name:
                    logger.info(f"Cognito user pool already exists: {pool_name}")
                    return str(pool["Id"])

            # Create user pool
            response = self.cognito_client.create_user_pool(
                PoolName=pool_name,
                Policies={
                    "PasswordPolicy": {
                        "MinimumLength": 8,
                        "RequireUppercase": True,
                        "RequireLowercase": True,
                        "RequireNumbers": True,
                        "RequireSymbols": True,
                        "TemporaryPasswordValidityDays": 7,
                    }
                },
                AutoVerifiedAttributes=["email", "phone_number"],
                MfaConfiguration="OPTIONAL",
                EnabledMfas=["SMS_MFA", "SOFTWARE_TOKEN_MFA"],
                UserAttributeUpdateSettings={
                    "AttributesRequireVerificationBeforeUpdate": [
                        "email",
                        "phone_number",
                    ]
                },
                Schema=[
                    {"Name": "email", "Required": True, "Mutable": True},
                    {"Name": "phone_number", "Required": False, "Mutable": True},
                    {
                        "Name": "patient_id",
                        "AttributeDataType": "String",
                        "Required": False,
                        "Mutable": True,
                    },
                ],
                AccountRecoverySetting={
                    "RecoveryMechanisms": [
                        {"Priority": 1, "Name": "verified_email"},
                        {"Priority": 2, "Name": "verified_phone_number"},
                    ]
                },
            )

            user_pool_id = str(response["UserPool"]["Id"])

            # Create app client
            self.cognito_client.create_user_pool_client(
                UserPoolId=user_pool_id,
                ClientName="haven-health-app",
                GenerateSecret=True,
                RefreshTokenValidity=30,
                AccessTokenValidity=60,
                IdTokenValidity=60,
                TokenValidityUnits={
                    "AccessToken": "minutes",
                    "IdToken": "minutes",
                    "RefreshToken": "days",
                },
                ExplicitAuthFlows=[
                    "ALLOW_USER_PASSWORD_AUTH",
                    "ALLOW_REFRESH_TOKEN_AUTH",
                    "ALLOW_USER_SRP_AUTH",
                ],
                PreventUserExistenceErrors="ENABLED",
                EnableTokenRevocation=True,
            )

            logger.info(f"Created Cognito user pool: {user_pool_id}")
            return user_pool_id

        except ClientError as e:
            logger.error(f"Failed to create Cognito user pool: {e}")
            return None

    # Secrets Manager for Keys

    def setup_secrets_manager(self) -> bool:
        """Set up AWS Secrets Manager for encryption keys."""
        secrets = [
            {
                "name": "haven/encryption/master-key",
                "description": "Master encryption key for health records",
                "value": os.urandom(32).hex(),
            },
            {
                "name": "haven/jwt/secret-key",
                "description": "JWT signing key",
                "value": os.urandom(64).hex(),
            },
            {
                "name": "haven/api/keys",
                "description": "API keys for external services",
                "value": json.dumps(
                    {
                        "bedrock_api_key": os.environ.get("BEDROCK_API_KEY", ""),
                        "twilio_auth_token": os.environ.get("TWILIO_AUTH_TOKEN", ""),
                        "sendgrid_api_key": os.environ.get("SENDGRID_API_KEY", ""),
                    }
                ),
            },
        ]

        for secret in secrets:
            try:
                # Check if secret exists
                try:
                    self.secrets_manager_client.describe_secret(SecretId=secret["name"])
                    logger.info(f"Secret already exists: {secret['name']}")
                    continue
                except ClientError as e:
                    if e.response["Error"]["Code"] != "ResourceNotFoundException":
                        raise

                # Create secret
                self.secrets_manager_client.create_secret(
                    Name=secret["name"],
                    Description=secret["description"],
                    SecretString=secret["value"],
                    KmsKeyId="alias/aws/secretsmanager",
                )

                logger.info(f"Created secret: {secret['name']}")

            except ClientError as e:
                logger.error(f"Failed to create secret {secret['name']}: {e}")
                return False

        return True

    def get_secret(self, secret_name: str) -> Optional[str]:
        """Retrieve secret from Secrets Manager."""
        try:
            response = self.secrets_manager_client.get_secret_value(
                SecretId=secret_name
            )
            return str(response["SecretString"])
        except ClientError as e:
            logger.error(f"Failed to get secret {secret_name}: {e}")
            return None

    # CloudWatch Logging

    def setup_cloudwatch_logging(self) -> bool:
        """Set up CloudWatch log groups and streams."""
        log_groups = [
            "/aws/haven/api",
            "/aws/haven/authentication",
            "/aws/haven/health-records",
            "/aws/haven/verification",
            "/aws/haven/translation",
            "/aws/haven/sync",
            "/aws/haven/audit",
        ]

        for log_group in log_groups:
            try:
                # Create log group
                try:
                    self.logs_client.create_log_group(
                        logGroupName=log_group,
                        kmsKeyId=f"arn:aws:kms:{self.region}:{self.account_id}:alias/aws/logs",
                    )

                    # Set retention policy (7 years)
                    self.logs_client.put_retention_policy(
                        logGroupName=log_group, retentionInDays=2557  # 7 years
                    )

                    logger.info(f"Created log group: {log_group}")

                except ClientError as e:
                    if e.response["Error"]["Code"] == "ResourceAlreadyExistsException":
                        logger.info(f"Log group already exists: {log_group}")
                    else:
                        raise

                # Create metric filters
                self._create_metric_filters(log_group)

            except ClientError as e:
                logger.error(f"Failed to create log group {log_group}: {e}")
                return False

        return True

    def _create_metric_filters(self, log_group: str) -> None:
        """Create CloudWatch metric filters for monitoring."""
        filters = [
            {
                "filterName": "ErrorCount",
                "filterPattern": "[timestamp, level=ERROR, ...]",
                "metricNamespace": "HavenHealth",
                "metricName": "ErrorCount",
                "metricValue": "1",
            },
            {
                "filterName": "UnauthorizedAccess",
                "filterPattern": '[timestamp, level, msg="*401*" || msg="*403*", ...]',
                "metricNamespace": "HavenHealth",
                "metricName": "UnauthorizedAccess",
                "metricValue": "1",
            },
            {
                "filterName": "HighLatency",
                "filterPattern": "[timestamp, level, msg, latency > 1000, ...]",
                "metricNamespace": "HavenHealth",
                "metricName": "HighLatency",
                "metricValue": "$latency",
            },
        ]

        for filter_config in filters:
            try:
                self.logs_client.put_metric_filter(
                    logGroupName=log_group,
                    filterName=f"{log_group}/{filter_config['filterName']}",
                    filterPattern=filter_config["filterPattern"],
                    metricTransformations=[
                        {
                            "metricName": filter_config["metricName"],
                            "metricNamespace": filter_config["metricNamespace"],
                            "metricValue": filter_config["metricValue"],
                            "defaultValue": 0,
                        }
                    ],
                )
            except ClientError as e:
                if e.response["Error"]["Code"] != "ResourceAlreadyExistsException":
                    logger.error(f"Failed to create metric filter: {e}")

    # Lambda Functions for Processing

    def create_lambda_functions(self) -> bool:
        """Create Lambda functions for background processing."""
        # First create IAM role for Lambda
        iam = boto3.client("iam")
        role_name = "haven-lambda-role"

        try:
            # Create execution role
            try:
                iam.get_role(RoleName=role_name)
            except ClientError:
                trust_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                }

                iam.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                )

                # Attach policies
                policies = [
                    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                    "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
                ]

                for policy in policies:
                    iam.attach_role_policy(RoleName=role_name, PolicyArn=policy)

            role_arn = f"arn:aws:iam::{self.account_id}:role/{role_name}"

            # Lambda functions to create
            functions = [
                {
                    "name": "haven-image-processor",
                    "handler": "index.handler",
                    "description": "Process medical images and documents",
                    "timeout": 300,
                    "memory": 512,
                },
                {
                    "name": "haven-translation-queue",
                    "handler": "index.handler",
                    "description": "Process translation queue items",
                    "timeout": 60,
                    "memory": 256,
                },
                {
                    "name": "haven-verification-processor",
                    "handler": "index.handler",
                    "description": "Process verification requests",
                    "timeout": 120,
                    "memory": 512,
                },
                {
                    "name": "haven-notification-sender",
                    "handler": "index.handler",
                    "description": "Send notifications via email/SMS",
                    "timeout": 30,
                    "memory": 128,
                },
            ]

            for func in functions:
                try:
                    # Check if function exists
                    try:
                        self.lambda_client.get_function(FunctionName=func["name"])
                        logger.info(f"Lambda function already exists: {func['name']}")
                        continue
                    except ClientError:
                        pass

                    # Create deployment package
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(
                        zip_buffer, "w", zipfile.ZIP_DEFLATED
                    ) as zip_file:
                        # Add basic handler code
                        handler_code = """
import json
import boto3
import os

def handler(event, context):
    print(f"Processing event: {{json.dumps(event)}}")

    # Process based on function
    function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', '')

    if 'image-processor' in function_name:
        return process_image(event)
    elif 'translation-queue' in function_name:
        return process_translation(event)
    elif 'verification-processor' in function_name:
        return process_verification(event)
    elif 'notification-sender' in function_name:
        return send_notification(event)

    return {{
        'statusCode': 200,
        'body': json.dumps({{'message': 'Processed successfully'}})
    }}

def process_image(event):
    # Image processing logic
    return {{'statusCode': 200, 'body': 'Image processed'}}

def process_translation(event):
    # Translation processing logic
    return {{'statusCode': 200, 'body': 'Translation processed'}}

def process_verification(event):
    # Verification processing logic
    return {{'statusCode': 200, 'body': 'Verification processed'}}

def send_notification(event):
    # Notification sending logic
    return {{'statusCode': 200, 'body': 'Notification sent'}}
"""
                        zip_file.writestr("index.py", handler_code)

                    # Create function
                    self.lambda_client.create_function(
                        FunctionName=func["name"],
                        Runtime="python3.9",
                        Role=role_arn,
                        Handler=func["handler"],
                        Code={"ZipFile": zip_buffer.getvalue()},
                        Description=func["description"],
                        Timeout=func["timeout"],
                        MemorySize=func["memory"],
                        Environment={
                            "Variables": {
                                "ENVIRONMENT": settings.environment,
                                "REGION": self.region,
                            }
                        },
                    )

                    logger.info(f"Created Lambda function: {func['name']}")

                except ClientError as e:
                    logger.error(
                        f"Failed to create Lambda function {func['name']}: {e}"
                    )
                    return False

            return True

        except ClientError as e:
            logger.error(f"Failed to create Lambda functions: {e}")
            return False

    # API Gateway Setup

    def setup_api_gateway(self) -> Optional[str]:
        """Set up API Gateway for REST endpoints."""
        try:
            api_name = "haven-health-api"

            # Check if API exists
            response = self.apigateway_client.get_rest_apis()
            for api in response.get("items", []):
                if api["name"] == api_name:
                    logger.info(f"API Gateway already exists: {api_name}")
                    return str(api["id"])

            # Create REST API
            response = self.apigateway_client.create_rest_api(
                name=api_name,
                description="Haven Health Passport API",
                version="2.0",
                endpointConfiguration={"types": ["REGIONAL"]},
            )

            api_id = str(response["id"])

            # Get root resource
            resources = self.apigateway_client.get_resources(restApiId=api_id)
            root_id = resources["items"][0]["id"]

            # Create resources and methods
            endpoints = [
                {"path": "health", "methods": ["GET"]},
                {"path": "auth", "methods": ["POST"]},
                {"path": "patients", "methods": ["GET", "POST", "PUT", "DELETE"]},
                {"path": "records", "methods": ["GET", "POST", "PUT", "DELETE"]},
                {"path": "files", "methods": ["GET", "POST"]},
            ]

            for endpoint in endpoints:
                # Create resource
                resource_response = self.apigateway_client.create_resource(
                    restApiId=api_id, parentId=root_id, pathPart=endpoint["path"]
                )

                resource_id = resource_response["id"]

                # Create methods
                for method in endpoint["methods"]:
                    self.apigateway_client.put_method(
                        restApiId=api_id,
                        resourceId=resource_id,
                        httpMethod=method,
                        authorizationType="AWS_IAM",
                        apiKeyRequired=True,
                    )

                    # Create mock integration for now
                    self.apigateway_client.put_integration(
                        restApiId=api_id,
                        resourceId=resource_id,
                        httpMethod=method,
                        type="MOCK",
                        requestTemplates={"application/json": '{"statusCode": 200}'},
                    )

                    # Create method response
                    self.apigateway_client.put_method_response(
                        restApiId=api_id,
                        resourceId=resource_id,
                        httpMethod=method,
                        statusCode="200",
                        responseModels={"application/json": "Empty"},
                    )

                    # Create integration response
                    self.apigateway_client.put_integration_response(
                        restApiId=api_id,
                        resourceId=resource_id,
                        httpMethod=method,
                        statusCode="200",
                        responseTemplates={"application/json": ""},
                    )

            # Create deployment
            self.apigateway_client.create_deployment(
                restApiId=api_id, stageName="prod", description="Production deployment"
            )

            # Create API key and usage plan
            key_response = self.apigateway_client.create_api_key(
                name="haven-api-key",
                description="Default API key for Haven Health",
                enabled=True,
            )

            plan_response = self.apigateway_client.create_usage_plan(
                name="haven-basic-plan",
                description="Basic usage plan",
                apiStages=[{"apiId": api_id, "stage": "prod"}],
                throttle={"rateLimit": 100, "burstLimit": 200},
                quota={"limit": 10000, "period": "DAY"},
            )

            # Associate key with plan
            self.apigateway_client.create_usage_plan_key(
                usagePlanId=plan_response["id"],
                keyId=key_response["id"],
                keyType="API_KEY",
            )

            logger.info(f"Created API Gateway: {api_id}")
            return api_id

        except ClientError as e:
            logger.error(f"Failed to set up API Gateway: {e}")
            return None

    # CloudFront CDN Setup

    def setup_cloudfront_cdn(self, s3_bucket_name: str) -> Optional[str]:
        """Create CloudFront distribution for static content and API caching."""
        try:
            # Check if distribution exists
            response = self.cloudfront_client.list_distributions()
            for dist in response.get("DistributionList", {}).get("Items", []):
                if "haven-health-cdn" in dist.get("Comment", ""):
                    logger.info("CloudFront distribution already exists")
                    return str(dist["Id"])

            # Create Origin Access Identity
            oai_response = (
                self.cloudfront_client.create_cloud_front_origin_access_identity(
                    CloudFrontOriginAccessIdentityConfig={
                        "CallerReference": f"haven-oai-{datetime.utcnow().isoformat()}",
                        "Comment": "Haven Health Origin Access Identity",
                    }
                )
            )

            oai_id = oai_response["CloudFrontOriginAccessIdentity"]["Id"]

            # Create distribution
            distribution_config = {
                "CallerReference": f"haven-dist-{datetime.utcnow().isoformat()}",
                "Comment": "haven-health-cdn",
                "DefaultRootObject": "index.html",
                "Origins": {
                    "Quantity": 2,
                    "Items": [
                        {
                            "Id": "s3-origin",
                            "DomainName": f"{s3_bucket_name}.s3.amazonaws.com",
                            "S3OriginConfig": {
                                "OriginAccessIdentity": f"origin-access-identity/cloudfront/{oai_id}"
                            },
                        },
                        {
                            "Id": "api-origin",
                            "DomainName": "api.havenhealthpassport.org",
                            "CustomOriginConfig": {
                                "HTTPPort": 80,
                                "HTTPSPort": 443,
                                "OriginProtocolPolicy": "https-only",
                                "OriginSslProtocols": {
                                    "Quantity": 3,
                                    "Items": ["TLSv1", "TLSv1.1", "TLSv1.2"],
                                },
                            },
                        },
                    ],
                },
                "DefaultCacheBehavior": {
                    "TargetOriginId": "s3-origin",
                    "ViewerProtocolPolicy": "redirect-to-https",
                    "AllowedMethods": {
                        "Quantity": 2,
                        "Items": ["GET", "HEAD"],
                        "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
                    },
                    "ForwardedValues": {
                        "QueryString": False,
                        "Cookies": {"Forward": "none"},
                        "Headers": {"Quantity": 1, "Items": ["Origin"]},
                    },
                    "TrustedSigners": {"Enabled": False, "Quantity": 0},
                    "MinTTL": 0,
                    "DefaultTTL": 86400,
                    "MaxTTL": 31536000,
                    "Compress": True,
                },
                "CacheBehaviors": {
                    "Quantity": 1,
                    "Items": [
                        {
                            "PathPattern": "/api/*",
                            "TargetOriginId": "api-origin",
                            "ViewerProtocolPolicy": "https-only",
                            "AllowedMethods": {
                                "Quantity": 7,
                                "Items": [
                                    "GET",
                                    "HEAD",
                                    "OPTIONS",
                                    "PUT",
                                    "POST",
                                    "PATCH",
                                    "DELETE",
                                ],
                                "CachedMethods": {
                                    "Quantity": 2,
                                    "Items": ["GET", "HEAD"],
                                },
                            },
                            "ForwardedValues": {
                                "QueryString": True,
                                "Cookies": {"Forward": "all"},
                                "Headers": {
                                    "Quantity": 4,
                                    "Items": [
                                        "Authorization",
                                        "Content-Type",
                                        "Accept",
                                        "Origin",
                                    ],
                                },
                            },
                            "TrustedSigners": {"Enabled": False, "Quantity": 0},
                            "MinTTL": 0,
                            "DefaultTTL": 0,
                            "MaxTTL": 0,
                            "Compress": True,
                        }
                    ],
                },
                "Enabled": True,
                "PriceClass": "PriceClass_100",
                "CustomErrorResponses": {
                    "Quantity": 2,
                    "Items": [
                        {
                            "ErrorCode": 403,
                            "ResponsePagePath": "/error-403.html",
                            "ResponseCode": "403",
                            "ErrorCachingMinTTL": 300,
                        },
                        {
                            "ErrorCode": 404,
                            "ResponsePagePath": "/error-404.html",
                            "ResponseCode": "404",
                            "ErrorCachingMinTTL": 300,
                        },
                    ],
                },
            }

            response = self.cloudfront_client.create_distribution(
                DistributionConfig=distribution_config
            )

            distribution_id = str(response["Distribution"]["Id"])
            logger.info(f"Created CloudFront distribution: {distribution_id}")

            return distribution_id

        except ClientError as e:
            logger.error(f"Failed to set up CloudFront CDN: {e}")
            return None

    def initialize_all_services(self) -> Dict[str, bool]:
        """Initialize all AWS services."""
        results = {}

        # S3 buckets
        results["s3_documents"] = self.create_s3_bucket("haven-health-documents")
        results["s3_backups"] = self.create_s3_bucket("haven-health-backups")

        # DynamoDB tables
        results["dynamodb"] = self.create_dynamodb_tables()

        # HealthLake
        results["healthlake"] = bool(self.create_healthlake_datastore())

        # Cognito
        results["cognito"] = bool(self.create_cognito_user_pool())

        # Secrets Manager
        results["secrets"] = self.setup_secrets_manager()

        # CloudWatch
        results["cloudwatch"] = self.setup_cloudwatch_logging()

        # Lambda
        results["lambda"] = self.create_lambda_functions()

        # API Gateway
        results["api_gateway"] = bool(self.setup_api_gateway())

        # CloudFront
        results["cloudfront"] = bool(
            self.setup_cloudfront_cdn("haven-health-documents")
        )

        # Summary
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)

        logger.info(
            f"AWS services initialization complete: {success_count}/{total_count} successful"
        )

        return results


# Singleton instance
aws_services = AWSServiceManager()
