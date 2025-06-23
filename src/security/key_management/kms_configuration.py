"""
AWS KMS Configuration for Haven Health Passport.

CRITICAL: This module configures AWS Key Management Service for production use.
Patient data security depends on proper key management and encryption.
PHI Protection: Manages encryption keys for PHI with hardware-backed crypto operations.
Access Control: KMS key policies enforce role-based access control for key usage.
"""

import json
import threading
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class KMSConfiguration:
    """
    Configures and manages AWS KMS for Haven Health Passport.

    This includes:
    - Creating Customer Master Keys (CMKs) with proper policies
    - Setting up key hierarchies
    - Configuring automatic key rotation
    - Managing key aliases
    - Implementing least-privilege access policies
    """

    def __init__(self) -> None:
        """Initialize KMS configuration with AWS clients and key hierarchy."""
        self.environment = settings.environment.lower()
        self.region = settings.aws_region
        self.kms_client = boto3.client("kms", region_name=self.region)
        self.iam_client = boto3.client("iam", region_name=self.region)

        # Key hierarchy configuration
        self.key_hierarchy = {
            "master": {
                "description": "Haven Health Passport Master Key",
                "usage": "ENCRYPT_DECRYPT",
                "multi_region": True,
                "rotation_enabled": True,
                "rotation_days": 365,
            },
            "data": {
                "description": "Data Encryption Keys",
                "usage": "ENCRYPT_DECRYPT",
                "multi_region": False,
                "rotation_enabled": True,
                "rotation_days": 90,
            },
            "phi": {
                "description": "PHI Encryption Key (HIPAA Compliant)",
                "usage": "ENCRYPT_DECRYPT",
                "multi_region": False,
                "rotation_enabled": True,
                "rotation_days": 90,
                "hipaa_compliant": True,
            },
            "signing": {
                "description": "Digital Signature Keys",
                "usage": "SIGN_VERIFY",
                "key_spec": "RSA_4096",
                "multi_region": False,
                "rotation_enabled": False,  # Signing keys typically don't rotate
            },
        }

    def configure_kms(self) -> Dict[str, Any]:
        """
        Configure all KMS resources for production use.

        Returns:
            Dictionary with configuration results
        """
        logger.info("Configuring AWS KMS for Haven Health Passport...")

        results: Dict[str, Any] = {
            "keys_created": {},
            "policies_applied": {},
            "aliases_created": {},
            "rotation_configured": {},
            "errors": [],
        }

        try:
            # Step 1: Create or validate master keys
            for key_type, config in self.key_hierarchy.items():
                key_result = self._configure_key(key_type, config)
                if key_result["success"]:
                    results["keys_created"][key_type] = key_result["key_id"]
                else:
                    results["errors"].append(
                        f"Failed to configure {key_type} key: {key_result['error']}"
                    )

            # Step 2: Configure key policies
            for key_type, key_id in results["keys_created"].items():
                policy_result = self._apply_key_policy(key_type, key_id)
                results["policies_applied"][key_type] = policy_result["success"]
                if not policy_result["success"]:
                    results["errors"].append(
                        f"Failed to apply policy for {key_type}: {policy_result['error']}"
                    )

            # Step 3: Create key aliases
            for key_type, key_id in results["keys_created"].items():
                alias_result = self._create_key_alias(key_type, key_id)
                results["aliases_created"][key_type] = alias_result["alias"]

            # Step 4: Configure rotation
            for key_type, key_id in results["keys_created"].items():
                if self.key_hierarchy[key_type].get("rotation_enabled", False):
                    rotation_result = self._configure_rotation(key_id)
                    results["rotation_configured"][key_type] = rotation_result[
                        "success"
                    ]

            # Step 5: Set up monitoring
            self._configure_cloudwatch_monitoring(results["keys_created"])

            logger.info(
                f"KMS configuration complete. Created {len(results['keys_created'])} keys"
            )

        except (ClientError, BotoCoreError, ValueError, TypeError) as e:
            error_msg = f"KMS configuration failed: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

        return results

    def _configure_key(self, key_type: str, config: Dict) -> Dict[str, Any]:
        """Configure a single KMS key."""
        try:
            # Check if key already exists
            alias_name = f"alias/haven-health/{self.environment}/{key_type}"
            existing_key = self._get_key_by_alias(alias_name)

            if existing_key:
                logger.info(f"Key {key_type} already exists: {existing_key}")
                return {"success": True, "key_id": existing_key}

            # Create new key
            create_params = {
                "Description": f"{config['description']} ({self.environment})",
                "KeyUsage": config.get("usage", "ENCRYPT_DECRYPT"),
                "Origin": "AWS_KMS",
                "MultiRegion": config.get("multi_region", False),
                "Tags": [
                    {"TagKey": "Application", "TagValue": "HavenHealthPassport"},
                    {"TagKey": "Environment", "TagValue": self.environment},
                    {"TagKey": "KeyType", "TagValue": key_type},
                    {"TagKey": "ManagedBy", "TagValue": "KMSConfiguration"},
                    {"TagKey": "CreatedAt", "TagValue": datetime.utcnow().isoformat()},
                ],
            }

            # Add key spec for asymmetric keys
            if "key_spec" in config:
                create_params["KeySpec"] = config["key_spec"]

            # Add HIPAA compliance tag
            if config.get("hipaa_compliant", False):
                create_params["Tags"].append({"TagKey": "HIPAA", "TagValue": "true"})
                create_params["Tags"].append(
                    {"TagKey": "Compliance", "TagValue": "HIPAA"}
                )

            response = self.kms_client.create_key(**create_params)
            key_id = response["KeyMetadata"]["KeyId"]

            logger.info(f"Created KMS key {key_type}: {key_id}")
            return {"success": True, "key_id": key_id}

        except ClientError as e:
            error_msg = f"Failed to create key {key_type}: {e}"
            logger.error(error_msg)
            return {"success": False, "error": str(e)}

    def _apply_key_policy(self, key_type: str, key_id: str) -> Dict[str, Any]:
        """Apply least-privilege key policy."""
        try:
            # Get current account ID
            sts_client = boto3.client("sts")
            account_id = sts_client.get_caller_identity()["Account"]

            # Define key policy based on key type
            policy: Dict[str, Any] = {
                "Version": "2012-10-17",
                "Id": f"haven-health-{key_type}-policy",
                "Statement": [
                    {
                        "Sid": "Enable IAM User Permissions",
                        "Effect": "Allow",
                        "Principal": {"AWS": f"arn:aws:iam::{account_id}:root"},
                        "Action": "kms:*",
                        "Resource": "*",
                    },
                    {
                        "Sid": "Allow use of the key for encryption",
                        "Effect": "Allow",
                        "Principal": {
                            "AWS": [
                                f"arn:aws:iam::{account_id}:role/HavenHealthAppRole",
                                f"arn:aws:iam::{account_id}:role/HavenHealthLambdaRole",
                            ]
                        },
                        "Action": [
                            "kms:Encrypt",
                            "kms:Decrypt",
                            "kms:ReEncrypt*",
                            "kms:GenerateDataKey*",
                            "kms:DescribeKey",
                        ],
                        "Resource": "*",
                    },
                ],
            }

            # Add specific conditions for PHI keys
            if key_type == "phi":
                policy["Statement"].append(
                    {
                        "Sid": "Require encryption context for PHI",
                        "Effect": "Deny",
                        "Principal": {"AWS": "*"},
                        "Action": ["kms:Decrypt", "kms:GenerateDataKey*"],
                        "Resource": "*",
                        "Condition": {
                            "StringNotEquals": {"kms:EncryptionContext:DataType": "PHI"}
                        },
                    }
                )

            # Apply the policy
            self.kms_client.put_key_policy(
                KeyId=key_id, PolicyName="default", Policy=json.dumps(policy)
            )

            logger.info(f"Applied key policy for {key_type}")
            return {"success": True}

        except (ClientError, BotoCoreError, ValueError, TypeError) as e:
            logger.error(f"Failed to apply key policy: {e}")
            return {"success": False, "error": str(e)}

    def _create_key_alias(self, key_type: str, key_id: str) -> Dict[str, Any]:
        """Create alias for easy key reference."""
        try:
            alias_name = f"alias/haven-health/{self.environment}/{key_type}"

            # Delete existing alias if it exists
            try:
                self.kms_client.delete_alias(AliasName=alias_name)
            except ClientError:
                pass  # Alias doesn't exist

            # Create new alias
            self.kms_client.create_alias(AliasName=alias_name, TargetKeyId=key_id)

            logger.info(f"Created alias {alias_name} for key {key_id}")
            return {"success": True, "alias": alias_name}

        except (ClientError, BotoCoreError, ValueError, TypeError) as e:
            logger.error(f"Failed to create alias: {e}")
            return {"success": False, "error": str(e), "alias": None}

    def _configure_rotation(self, key_id: str) -> Dict[str, Any]:
        """Configure automatic key rotation."""
        try:
            # Enable key rotation
            self.kms_client.enable_key_rotation(KeyId=key_id)

            # Get rotation status
            rotation_status = self.kms_client.get_key_rotation_status(KeyId=key_id)

            logger.info(
                f"Rotation enabled for key {key_id}: {rotation_status['KeyRotationEnabled']}"
            )
            return {
                "success": True,
                "rotation_enabled": rotation_status["KeyRotationEnabled"],
            }

        except (ClientError, BotoCoreError, ValueError, TypeError) as e:
            logger.error(f"Failed to configure rotation: {e}")
            return {"success": False, "error": str(e)}

    def _get_key_by_alias(self, alias_name: str) -> Optional[str]:
        """Get key ID by alias name."""
        try:
            response = self.kms_client.describe_key(KeyId=alias_name)
            return str(response["KeyMetadata"]["KeyId"])
        except ClientError as e:
            if e.response["Error"]["Code"] == "NotFoundException":
                return None
            raise

    def _configure_cloudwatch_monitoring(self, keys: Dict[str, str]) -> None:
        """Configure CloudWatch monitoring for KMS keys."""
        try:
            cloudwatch = boto3.client("cloudwatch", region_name=self.region)

            # Create alarms for each key
            for key_type, key_id in keys.items():
                # Alarm for key usage
                cloudwatch.put_metric_alarm(
                    AlarmName=f"haven-health-{self.environment}-{key_type}-key-usage",
                    ComparisonOperator="GreaterThanThreshold",
                    EvaluationPeriods=1,
                    MetricName="NumberOfOperations",
                    Namespace="AWS/KMS",
                    Period=300,
                    Statistic="Sum",
                    Threshold=1000.0,
                    ActionsEnabled=True,
                    AlarmDescription=f"Alert on high KMS key usage for {key_type}",
                    Dimensions=[{"Name": "KeyId", "Value": key_id}],
                )

                # Alarm for key errors
                cloudwatch.put_metric_alarm(
                    AlarmName=f"haven-health-{self.environment}-{key_type}-key-errors",
                    ComparisonOperator="GreaterThanThreshold",
                    EvaluationPeriods=1,
                    MetricName="NumberOfOperations",
                    Namespace="AWS/KMS",
                    Period=300,
                    Statistic="Sum",
                    Threshold=10.0,
                    ActionsEnabled=True,
                    AlarmDescription=f"Alert on KMS key errors for {key_type}",
                    Dimensions=[
                        {"Name": "KeyId", "Value": key_id},
                        {"Name": "Operation", "Value": "Decrypt"},
                    ],
                )

            logger.info("CloudWatch monitoring configured for KMS keys")

        except (ClientError, BotoCoreError, ValueError, TypeError) as e:
            logger.error(f"Failed to configure monitoring: {e}")
            # Non-fatal error

    def validate_kms_configuration(self) -> Dict[str, Any]:
        """Validate that KMS is properly configured."""
        validation_results: Dict[str, Any] = {
            "keys_accessible": {},
            "rotation_enabled": {},
            "policies_valid": {},
            "is_valid": True,
            "errors": [],
        }

        try:
            for key_type, _key_config in self.key_hierarchy.items():
                alias_name = f"alias/haven-health/{self.environment}/{key_type}"

                # Check if key exists and is accessible
                try:
                    key_id = self._get_key_by_alias(alias_name)
                    if key_id:
                        validation_results["keys_accessible"][key_type] = True

                        # Check rotation status
                        if self.key_hierarchy[key_type].get("rotation_enabled", False):
                            rotation_status = self.kms_client.get_key_rotation_status(
                                KeyId=key_id
                            )
                            validation_results["rotation_enabled"][key_type] = (
                                rotation_status["KeyRotationEnabled"]
                            )

                        # Validate key policy
                        policy = self.kms_client.get_key_policy(
                            KeyId=key_id, PolicyName="default"
                        )
                        validation_results["policies_valid"][key_type] = bool(
                            policy["Policy"]
                        )
                    else:
                        validation_results["keys_accessible"][key_type] = False
                        validation_results["is_valid"] = False
                        validation_results["errors"].append(f"Key {key_type} not found")

                except (ClientError, BotoCoreError, ValueError, TypeError) as e:
                    validation_results["keys_accessible"][key_type] = False
                    validation_results["is_valid"] = False
                    validation_results["errors"].append(
                        f"Cannot access key {key_type}: {e}"
                    )

            # Check for HIPAA compliance
            if (
                "phi" in validation_results["keys_accessible"]
                and validation_results["keys_accessible"]["phi"]
            ):
                if not validation_results["rotation_enabled"].get("phi", False):
                    validation_results["errors"].append(
                        "PHI key rotation not enabled (HIPAA requirement)"
                    )
                    validation_results["is_valid"] = False

        except (ClientError, BotoCoreError, ValueError, TypeError) as e:
            validation_results["is_valid"] = False
            validation_results["errors"].append(f"Validation failed: {e}")

        return validation_results


# Thread-safe singleton for KMS configuration
class KMSConfigurationSingleton:
    """Thread-safe singleton for KMS configuration."""

    _instance = None
    _lock = threading.Lock()
    _config: Optional[KMSConfiguration] = None

    def __new__(cls) -> "KMSConfigurationSingleton":
        """Create a new instance or return existing singleton instance."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._config = KMSConfiguration()
        return cls._instance

    def get_config(self) -> KMSConfiguration:
        """Get the KMS configuration instance."""
        if self._config is None:
            raise RuntimeError("Config not initialized")
        return self._config


def get_kms_configuration() -> KMSConfiguration:
    """Get the thread-safe KMS configuration instance."""
    singleton = KMSConfigurationSingleton()
    return singleton.get_config()


def configure_kms_for_production() -> Dict[str, Any]:
    """
    Configure KMS for production use.

    This should be called during infrastructure setup.
    """
    config = get_kms_configuration()

    # Configure KMS
    results = config.configure_kms()

    # Validate configuration
    validation = config.validate_kms_configuration()
    results["validation"] = validation

    if not validation["is_valid"]:
        logger.error(f"KMS configuration validation failed: {validation['errors']}")
        if settings.environment == "production":
            raise RuntimeError("Cannot proceed without valid KMS configuration!")

    return results
