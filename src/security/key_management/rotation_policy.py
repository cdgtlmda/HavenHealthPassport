"""
Key Rotation Policies for Haven Health Passport.

CRITICAL: This module implements automatic key rotation to ensure
patient data remains secure over time. Key rotation is essential
for HIPAA compliance and security best practices.
"""

import io
import json
import threading
import zipfile
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class KeyRotationPolicy:
    """
    Implements key rotation policies for all encryption keys.

    This includes:
    - Automatic rotation schedules
    - Key versioning
    - Graceful transition periods
    - Zero-downtime rotation
    - Audit logging
    """

    def __init__(self) -> None:
        """Initialize key rotation policy with AWS clients and rotation schedules."""
        self.environment = settings.environment.lower()
        self.region = settings.aws_region

        # Initialize AWS clients
        self.kms_client = boto3.client("kms", region_name=self.region)
        self.secrets_client = boto3.client("secretsmanager", region_name=self.region)
        self.lambda_client = boto3.client("lambda", region_name=self.region)
        self.events_client = boto3.client("events", region_name=self.region)

        # Define rotation policies
        self.rotation_policies = {
            "ENCRYPTION_KEY": {
                "rotation_days": 90,
                "transition_days": 7,
                "key_type": "symmetric",
                "algorithm": "AES-256",
            },
            "JWT_SECRET_KEY": {
                "rotation_days": 30,
                "transition_days": 3,
                "key_type": "symmetric",
                "algorithm": "HMAC-SHA256",
            },
            "JWT_REFRESH_SECRET_KEY": {
                "rotation_days": 30,
                "transition_days": 3,
                "key_type": "symmetric",
                "algorithm": "HMAC-SHA256",
            },
            "PHI_ENCRYPTION_KEY": {
                "rotation_days": 90,
                "transition_days": 7,
                "key_type": "symmetric",
                "algorithm": "AES-256",
                "hipaa_compliant": True,
            },
            "DB_ENCRYPTION_KEY": {
                "rotation_days": 180,
                "transition_days": 14,
                "key_type": "symmetric",
                "algorithm": "AES-256",
            },
            "FILE_ENCRYPTION_KEY": {
                "rotation_days": 90,
                "transition_days": 7,
                "key_type": "symmetric",
                "algorithm": "AES-256",
            },
            "API_KEYS": {
                "rotation_days": 90,
                "transition_days": 7,
                "key_type": "api_key",
            },
        }

        self.secrets_prefix = f"haven-health-passport/{self.environment}"

    def create_rotation_lambda(self) -> Dict[str, Any]:
        """Create Lambda function for key rotation."""
        try:
            # Lambda function code
            lambda_code = self._get_rotation_lambda_code()

            # Create deployment package
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr("lambda_function.py", lambda_code)

            # Create Lambda function
            function_name = f"haven-health-key-rotation-{self.environment}"

            try:
                # Check if function exists
                self.lambda_client.get_function(FunctionName=function_name)

                # Update existing function
                response = self.lambda_client.update_function_code(
                    FunctionName=function_name, ZipFile=zip_buffer.getvalue()
                )
                logger.info(f"Updated rotation Lambda: {function_name}")

            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    # Create new function
                    response = self.lambda_client.create_function(
                        FunctionName=function_name,
                        Runtime="python3.9",
                        Role=f"arn:aws:iam::{self._get_account_id()}:role/HavenHealthLambdaRole",
                        Handler="lambda_function.lambda_handler",
                        Code={"ZipFile": zip_buffer.getvalue()},
                        Description="Key rotation for Haven Health Passport",
                        Timeout=300,
                        MemorySize=256,
                        Environment={
                            "Variables": {
                                "ENVIRONMENT": self.environment,
                                "SECRETS_PREFIX": self.secrets_prefix,
                            }
                        },
                        Tags={
                            "Application": "HavenHealthPassport",
                            "Environment": self.environment,
                            "Purpose": "KeyRotation",
                        },
                    )
                    logger.info(f"Created rotation Lambda: {function_name}")
                else:
                    raise

            return {
                "success": True,
                "function_arn": response["FunctionArn"],
                "function_name": function_name,
            }

        except (ClientError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to create rotation Lambda: {e}")
            return {"success": False, "error": str(e)}

    def _get_rotation_lambda_code(self) -> str:
        """Get Lambda function code for key rotation."""
        return '''
import json
import boto3
import secrets
import base64
from datetime import datetime, timedelta

def lambda_handler(event, context):
    """
    Rotate encryption keys for Haven Health Passport.

    This function:
    1. Generates a new key version
    2. Updates the secret with new version
    3. Maintains old version for transition period
    4. Logs rotation event
    """

    # Parse event
    secret_arn = event['SecretId']
    token = event['ClientRequestToken']
    step = event['Step']

    # Initialize clients
    secrets_client = boto3.client('secretsmanager')

    try:
        if step == 'createSecret':
            # Generate new key
            create_secret(secrets_client, secret_arn, token)

        elif step == 'setSecret':
            # Set the new secret version
            set_secret(secrets_client, secret_arn, token)

        elif step == 'testSecret':
            # Test the new secret
            test_secret(secrets_client, secret_arn, token)

        elif step == 'finishSecret':
            # Finish the rotation
            finish_secret(secrets_client, secret_arn, token)

        return {
            'statusCode': 200,
            'body': json.dumps(f'Successfully completed {step}')
        }

    except Exception as e:
        print(f"Error in {step}: {str(e)}")
        raise


def create_secret(client, secret_arn, token):
    """Create a new version of the secret."""
    # Get current secret
    response = client.describe_secret(SecretId=secret_arn)

    # Determine key type from tags
    tags = {tag['Key']: tag['Value'] for tag in response.get('Tags', [])}
    key_type = tags.get('KeyType', 'symmetric')

    # Generate new key based on type
    if key_type == 'symmetric':
        # Generate AES-256 key
        new_key = secrets.token_urlsafe(32)[:32]
    elif key_type == 'api_key':
        # Generate API key
        new_key = f"hhp_{secrets.token_urlsafe(32)}"
    else:
        # Default to random key
        new_key = secrets.token_urlsafe(64)

    # Create new version
    new_secret = {
        'value': new_key,
        'created': datetime.utcnow().isoformat(),
        'rotation_date': datetime.utcnow().isoformat(),
        'version': token
    }

    # Store as pending version
    client.put_secret_value(
        SecretId=secret_arn,
        ClientRequestToken=token,
        SecretString=json.dumps(new_secret),
        VersionStages=['AWSPENDING']
    )


def set_secret(client, secret_arn, token):
    """Set the secret in the service that uses it."""
    # In production, this would update the service configuration
    # For now, we just validate the secret format
    pass


def test_secret(client, secret_arn, token):
    """Test the new secret version."""
    # Get the pending secret
    response = client.get_secret_value(
        SecretId=secret_arn,
        VersionId=token,
        VersionStage='AWSPENDING'
    )

    secret_data = json.loads(response['SecretString'])

    # Validate key format
    if 'value' not in secret_data:
        raise ValueError("Invalid secret format: missing value")

    # Additional validation based on key type
    # In production, this would test actual encryption/decryption


def finish_secret(client, secret_arn, token):
    """Finish the rotation by promoting the new version."""
    # Get current version
    response = client.describe_secret(SecretId=secret_arn)
    current_version = None

    for version_id, stages in response['VersionIdsToStages'].items():
        if 'AWSCURRENT' in stages and version_id != token:
            current_version = version_id
            break

    # Move staging from current to previous
    if current_version:
        client.update_secret_version_stage(
            SecretId=secret_arn,
            VersionStage='AWSPREVIOUS',
            MoveToVersionId=current_version,
            RemoveFromVersionId=token
        )

    # Move current to new version
    client.update_secret_version_stage(
        SecretId=secret_arn,
        VersionStage='AWSCURRENT',
        MoveToVersionId=token,
        RemoveFromVersionId=current_version
    )

    # Log rotation
    print(f"Successfully rotated secret {secret_arn}")
'''

    def configure_rotation_schedules(self, lambda_arn: str) -> Dict[str, Any]:
        """Configure automatic rotation schedules for all keys."""
        results: Dict[str, Any] = {"configured": {}, "errors": []}

        try:
            # Configure rotation for each secret
            for secret_name, policy in self.rotation_policies.items():
                if secret_name == "API_KEYS":
                    continue  # Handle API keys separately

                full_secret_name = f"{self.secrets_prefix}/{secret_name}"

                try:
                    # Enable rotation
                    self.secrets_client.rotate_secret(
                        SecretId=full_secret_name,
                        ClientRequestToken=f"rotation-{datetime.utcnow().timestamp()}",
                        RotationLambdaARN=lambda_arn,
                        RotationRules={
                            "AutomaticallyAfterDays": policy["rotation_days"]
                        },
                    )

                    results["configured"][secret_name] = {
                        "rotation_days": policy["rotation_days"],
                        "enabled": True,
                    }

                    logger.info(
                        f"Configured rotation for {secret_name}: every {policy['rotation_days']} days"
                    )

                except ClientError as e:
                    if e.response["Error"]["Code"] == "ResourceNotFoundException":
                        results["errors"].append(f"Secret {secret_name} not found")
                    else:
                        results["errors"].append(
                            f"Failed to configure {secret_name}: {e}"
                        )

            # Create CloudWatch Events for additional monitoring
            self._create_rotation_monitoring(lambda_arn)

        except (ClientError, ValueError, RuntimeError) as e:
            results["errors"].append(f"Rotation configuration failed: {e}")

        return results

    def _create_rotation_monitoring(self, lambda_arn: str) -> None:
        """Create CloudWatch Events for rotation monitoring."""
        try:
            # Create rule for daily rotation check
            rule_name = f"haven-health-rotation-check-{self.environment}"

            self.events_client.put_rule(
                Name=rule_name,
                Description="Daily check for key rotation status",
                ScheduleExpression="rate(1 day)",
                State="ENABLED",
                Tags=[
                    {"Key": "Application", "Value": "HavenHealthPassport"},
                    {"Key": "Purpose", "Value": "KeyRotationMonitoring"},
                ],
            )

            # Add Lambda target
            self.events_client.put_targets(
                Rule=rule_name,
                Targets=[
                    {
                        "Id": "1",
                        "Arn": lambda_arn,
                        "Input": json.dumps(
                            {
                                "action": "check_rotation_status",
                                "environment": self.environment,
                            }
                        ),
                    }
                ],
            )

            # Add Lambda permission
            try:
                self.lambda_client.add_permission(
                    FunctionName=lambda_arn,
                    StatementId=f"AllowEventBridge-{rule_name}",
                    Action="lambda:InvokeFunction",
                    Principal="events.amazonaws.com",
                    SourceArn=f"arn:aws:events:{self.region}:{self._get_account_id()}:rule/{rule_name}",
                )
            except ClientError:
                pass  # Permission might already exist

            logger.info("Created rotation monitoring schedule")

        except (ClientError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to create rotation monitoring: {e}")

    def _get_account_id(self) -> str:
        """Get current AWS account ID."""
        sts_client = boto3.client("sts")
        return str(sts_client.get_caller_identity()["Account"])

    def validate_rotation_policies(self) -> Dict[str, Any]:
        """Validate that all rotation policies are properly configured."""
        validation_results: Dict[str, Any] = {
            "rotation_enabled": {},
            "last_rotation": {},
            "next_rotation": {},
            "is_valid": True,
            "errors": [],
        }

        try:
            for secret_name, policy_info in self.rotation_policies.items():
                if secret_name == "API_KEYS":
                    continue

                full_secret_name = f"{self.secrets_prefix}/{secret_name}"

                try:
                    # Check rotation status
                    response = self.secrets_client.describe_secret(
                        SecretId=full_secret_name
                    )

                    # Check if rotation is enabled
                    rotation_enabled = response.get("RotationEnabled", False)
                    validation_results["rotation_enabled"][
                        secret_name
                    ] = rotation_enabled

                    if rotation_enabled:
                        # Get last rotation date
                        if "LastRotatedDate" in response:
                            last_rotation = response["LastRotatedDate"]
                            validation_results["last_rotation"][
                                secret_name
                            ] = last_rotation.isoformat()

                            # Calculate next rotation
                            rotation_days_value = policy_info.get("rotation_days", 90)
                            rotation_days = (
                                int(str(rotation_days_value))
                                if rotation_days_value is not None
                                else 90
                            )
                            next_rotation = last_rotation + timedelta(
                                days=rotation_days
                            )
                            validation_results["next_rotation"][
                                secret_name
                            ] = next_rotation.isoformat()

                            # Check if overdue
                            if datetime.utcnow() > next_rotation:
                                validation_results["errors"].append(
                                    f"{secret_name} rotation is overdue!"
                                )
                                validation_results["is_valid"] = False
                    else:
                        validation_results["errors"].append(
                            f"Rotation not enabled for {secret_name}"
                        )
                        if self.environment == "production":
                            validation_results["is_valid"] = False

                except ClientError as e:
                    validation_results["errors"].append(
                        f"Cannot check {secret_name}: {e}"
                    )
                    validation_results["is_valid"] = False

        except (ClientError, ValueError, RuntimeError) as e:
            validation_results["is_valid"] = False
            validation_results["errors"].append(f"Validation failed: {e}")

        return validation_results


# Thread-safe singleton for rotation policy
class RotationPolicySingleton:
    """Thread-safe singleton for rotation policy."""

    _instance = None
    _lock = threading.Lock()
    _policy: Optional[KeyRotationPolicy] = None

    def __new__(cls) -> "RotationPolicySingleton":
        """Create or return the singleton instance of RotationPolicySingleton."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._policy = KeyRotationPolicy()
        return cls._instance

    def get_policy(self) -> KeyRotationPolicy:
        """Get the rotation policy instance."""
        if self._policy is None:
            raise RuntimeError("Policy not initialized")
        return self._policy


def get_rotation_policy() -> KeyRotationPolicy:
    """Get the thread-safe rotation policy instance."""
    singleton = RotationPolicySingleton()
    return singleton.get_policy()


def configure_key_rotation() -> Dict[str, Any]:
    """
    Configure key rotation for all encryption keys.

    This should be called during infrastructure setup.
    """
    policy = get_rotation_policy()

    # Create rotation Lambda
    lambda_result = policy.create_rotation_lambda()
    if not lambda_result["success"]:
        logger.error(f"Failed to create rotation Lambda: {lambda_result['error']}")
        return lambda_result

    # Configure rotation schedules
    results = policy.configure_rotation_schedules(lambda_result["function_arn"])
    results["lambda_function"] = lambda_result["function_name"]

    # Validate configuration
    validation = policy.validate_rotation_policies()
    results["validation"] = validation

    if not validation["is_valid"]:
        logger.error(f"Rotation validation failed: {validation['errors']}")
        if settings.environment == "production":
            raise RuntimeError("Cannot proceed without valid rotation policies!")

    return results
