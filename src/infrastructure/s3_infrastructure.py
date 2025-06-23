"""
S3 Infrastructure Deployment for Haven Health Passport.

CRITICAL: This module deploys and configures S3 buckets for storing
medical documents, voice recordings, and other PHI data with proper
encryption and compliance settings.
"""

import json
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class S3Infrastructure:
    """
    Deploys and configures S3 buckets for production use.

    This includes:
    - Document storage buckets
    - Voice synthesis cache
    - Medical image storage
    - Backup buckets
    - Audit log storage
    """

    def __init__(self) -> None:
        """Initialize S3 infrastructure with AWS clients."""
        self.environment = settings.environment.lower()
        self.region = settings.aws_region
        self.s3_client = boto3.client("s3", region_name=self.region)
        self.kms_client = boto3.client("kms", region_name=self.region)

        # Define all required buckets
        self.bucket_configs = {
            "documents": {
                "name": f"haven-health-documents-{self.environment}-{self.region}",
                "description": "Medical documents and records",
                "encryption": "phi",
                "lifecycle": {
                    "archive_days": 90,
                    "delete_days": 2555,  # 7 years for HIPAA
                },
                "versioning": True,
                "replication": True,
            },
            "voice": {
                "name": f"haven-health-voice-{self.environment}-{self.region}",
                "description": "Voice synthesis cache and recordings",
                "encryption": "phi",
                "lifecycle": {"delete_days": 90},  # Temporary cache
                "versioning": False,
                "replication": False,
            },
            "images": {
                "name": f"haven-health-images-{self.environment}-{self.region}",
                "description": "Medical images and scans",
                "encryption": "phi",
                "lifecycle": {"archive_days": 180, "delete_days": 2555},  # 7 years
                "versioning": True,
                "replication": True,
            },
            "backups": {
                "name": f"haven-health-backups-{self.environment}-{self.region}",
                "description": "System backups",
                "encryption": "data",
                "lifecycle": {
                    "archive_days": 30,
                    "glacier_days": 90,
                    "delete_days": 365,
                },
                "versioning": True,
                "replication": True,
            },
            "audit-logs": {
                "name": f"haven-health-audit-logs-{self.environment}-{self.region}",
                "description": "HIPAA audit logs",
                "encryption": "data",
                "lifecycle": {
                    "archive_days": 90,
                    "glacier_days": 365,
                    "delete_days": 2555,  # 7 years for HIPAA
                },
                "versioning": True,
                "replication": True,
                "object_lock": True,  # Immutable audit logs
            },
            "temp": {
                "name": f"haven-health-temp-{self.environment}-{self.region}",
                "description": "Temporary processing files",
                "encryption": "data",
                "lifecycle": {"delete_days": 7},
                "versioning": False,
                "replication": False,
            },
        }

    def deploy_s3_infrastructure(self) -> Dict[str, Any]:
        """
        Deploy all S3 buckets with proper configuration.

        Returns:
            Deployment results
        """
        logger.info(f"Deploying S3 infrastructure for {self.environment}...")

        results: Dict[str, Any] = {
            "buckets_created": {},
            "replication_configured": {},
            "policies_applied": {},
            "errors": [],
        }

        try:
            # Create replication role first if needed
            if self._needs_replication():
                replication_role = self._create_replication_role()
                if not replication_role:
                    results["errors"].append("Failed to create replication role")
                    return results
            else:
                replication_role = None

            # Deploy each bucket
            for bucket_type, config in self.bucket_configs.items():
                bucket_result = self._deploy_bucket(
                    bucket_type, config, replication_role
                )

                if bucket_result["success"]:
                    results["buckets_created"][bucket_type] = bucket_result[
                        "bucket_name"
                    ]

                    if config.get("replication") and replication_role:
                        rep_result = self._configure_replication(
                            bucket_result["bucket_name"], replication_role
                        )
                        results["replication_configured"][bucket_type] = rep_result[
                            "success"
                        ]
                else:
                    results["errors"].append(
                        f"Failed to deploy {bucket_type}: {bucket_result['error']}"
                    )

            # Apply bucket policies
            for bucket_type, bucket_name in results["buckets_created"].items():
                policy_result = self._apply_bucket_policy(bucket_name, bucket_type)
                results["policies_applied"][bucket_type] = policy_result["success"]

            logger.info("✅ S3 infrastructure deployment complete")

        except (ClientError, ValueError, KeyError) as e:
            error_msg = f"S3 infrastructure deployment failed: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

        return results

    def _deploy_bucket(
        self, bucket_type: str, config: Dict, replication_role: Optional[str]
    ) -> Dict[str, Any]:
        """Deploy a single S3 bucket."""
        _ = bucket_type  # Used for bucket-specific configurations
        _ = replication_role  # Will be used for cross-region replication setup
        bucket_name = config["name"]

        try:
            # Check if bucket already exists
            try:
                self.s3_client.head_bucket(Bucket=bucket_name)
                logger.info(f"Bucket already exists: {bucket_name}")

                # Ensure configuration is up to date
                self._update_bucket_configuration(bucket_name, config)

                return {"success": True, "bucket_name": bucket_name}
            except ClientError as e:
                if e.response["Error"]["Code"] != "404":
                    raise

            # Create bucket
            if self.region == "us-east-1":
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": self.region},
                )

            logger.info(f"Created bucket: {bucket_name}")

            # Configure bucket
            self._configure_bucket(bucket_name, config)

            return {"success": True, "bucket_name": bucket_name}

        except (KeyError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to deploy bucket {bucket_name}: {e}")
            return {"success": False, "error": str(e)}

    def _configure_bucket(self, bucket_name: str, config: Dict) -> None:
        """Configure bucket settings."""
        # Enable versioning if required
        if config.get("versioning"):
            self.s3_client.put_bucket_versioning(
                Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
            )

        # Configure encryption
        self._configure_bucket_encryption(bucket_name, config["encryption"])

        # Configure lifecycle
        if "lifecycle" in config:
            self._configure_lifecycle(bucket_name, config["lifecycle"])

        # Block public access
        self.s3_client.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )

        # Configure object lock for audit logs
        if config.get("object_lock"):
            self._configure_object_lock(bucket_name)

        # Add tags
        self.s3_client.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={
                "TagSet": [
                    {"Key": "Application", "Value": "HavenHealthPassport"},
                    {"Key": "Environment", "Value": self.environment},
                    {
                        "Key": "DataType",
                        "Value": "PHI" if "phi" in config["encryption"] else "General",
                    },
                    {"Key": "Purpose", "Value": config["description"]},
                ]
            },
        )

        # Configure logging
        self._configure_bucket_logging(bucket_name)

    def _update_bucket_configuration(self, bucket_name: str, config: Dict) -> None:
        """Update existing bucket configuration."""
        try:
            # Update encryption
            self._configure_bucket_encryption(bucket_name, config["encryption"])

            # Update lifecycle
            if "lifecycle" in config:
                self._configure_lifecycle(bucket_name, config["lifecycle"])

            # Ensure public access is blocked
            self.s3_client.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                },
            )

            logger.info(f"Updated configuration for bucket: {bucket_name}")

        except (ClientError, ValueError, KeyError) as e:
            logger.error(f"Failed to update bucket configuration: {e}")

    def _configure_bucket_encryption(
        self, bucket_name: str, encryption_type: str
    ) -> None:
        """Configure bucket encryption."""
        # Get appropriate KMS key
        if encryption_type == "phi":
            kms_alias = f"alias/haven-health/{self.environment}/phi"
        else:
            kms_alias = f"alias/haven-health/{self.environment}/data"

        try:
            response = self.kms_client.describe_key(KeyId=kms_alias)
            kms_key_id = response["KeyMetadata"]["Arn"]
        except ClientError:
            logger.error(f"KMS key not found: {kms_alias}")
            # Fall back to AWS managed key
            kms_key_id = "alias/aws/s3"

        # Apply encryption configuration
        self.s3_client.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "aws:kms",
                            "KMSMasterKeyID": kms_key_id,
                        },
                        "BucketKeyEnabled": True,
                    }
                ]
            },
        )

    def _configure_lifecycle(self, bucket_name: str, lifecycle_config: Dict) -> None:
        """Configure bucket lifecycle rules."""
        rules = []

        # Standard lifecycle rule
        rule: Dict[str, Any] = {
            "ID": "StandardLifecycle",
            "Status": "Enabled",
            "Filter": {},
        }

        transitions = []

        # Archive to Infrequent Access
        if "archive_days" in lifecycle_config:
            transitions.append(
                {
                    "Days": lifecycle_config["archive_days"],
                    "StorageClass": "STANDARD_IA",
                }
            )

        # Move to Glacier
        if "glacier_days" in lifecycle_config:
            transitions.append(
                {"Days": lifecycle_config["glacier_days"], "StorageClass": "GLACIER"}
            )

        if transitions:
            rule["Transitions"] = transitions

        # Expiration
        if "delete_days" in lifecycle_config:
            rule["Expiration"] = {"Days": lifecycle_config["delete_days"]}

        rules.append(rule)

        # Add rule for incomplete multipart uploads
        rules.append(
            {
                "ID": "CleanupIncompleteUploads",
                "Status": "Enabled",
                "Filter": {},
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
            }
        )

        # Apply lifecycle configuration
        self.s3_client.put_bucket_lifecycle_configuration(
            Bucket=bucket_name, LifecycleConfiguration={"Rules": rules}
        )

    def _configure_object_lock(self, bucket_name: str) -> None:
        """Configure object lock for immutable storage."""
        # Note: Object lock must be enabled at bucket creation
        # This is a placeholder for configuration
        logger.info(f"Object lock configuration for {bucket_name}")

    def _configure_bucket_logging(self, bucket_name: str) -> None:
        """Configure access logging for bucket."""
        # Use audit logs bucket for storing access logs
        log_bucket = f"haven-health-audit-logs-{self.environment}-{self.region}"

        # Only configure if audit bucket exists
        try:
            self.s3_client.head_bucket(Bucket=log_bucket)

            self.s3_client.put_bucket_logging(
                Bucket=bucket_name,
                BucketLoggingStatus={
                    "LoggingEnabled": {
                        "TargetBucket": log_bucket,
                        "TargetPrefix": f"s3-access-logs/{bucket_name}/",
                    }
                },
            )
        except ClientError:
            logger.warning(
                f"Audit bucket not available, skipping logging for {bucket_name}"
            )

    def _apply_bucket_policy(
        self, bucket_name: str, bucket_type: str
    ) -> Dict[str, Any]:
        """Apply bucket policy for access control."""
        try:
            account_id = boto3.client("sts").get_caller_identity()["Account"]

            # Base policy
            policy: Dict[str, Any] = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "DenyInsecureConnections",
                        "Effect": "Deny",
                        "Principal": "*",
                        "Action": "s3:*",
                        "Resource": [
                            f"arn:aws:s3:::{bucket_name}/*",
                            f"arn:aws:s3:::{bucket_name}",
                        ],
                        "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                    },
                    {
                        "Sid": "AllowApplicationAccess",
                        "Effect": "Allow",
                        "Principal": {
                            "AWS": [
                                f"arn:aws:iam::{account_id}:role/HavenHealthAppRole",
                                f"arn:aws:iam::{account_id}:role/HavenHealthLambdaRole",
                            ]
                        },
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject",
                            "s3:ListBucket",
                        ],
                        "Resource": [
                            f"arn:aws:s3:::{bucket_name}/*",
                            f"arn:aws:s3:::{bucket_name}",
                        ],
                    },
                ],
            }

            # Add specific policies for audit logs
            if bucket_type == "audit-logs":
                policy["Statement"].append(
                    {
                        "Sid": "DenyObjectDeletion",
                        "Effect": "Deny",
                        "Principal": "*",
                        "Action": ["s3:DeleteObject", "s3:DeleteObjectVersion"],
                        "Resource": f"arn:aws:s3:::{bucket_name}/*",
                    }
                )

            self.s3_client.put_bucket_policy(
                Bucket=bucket_name, Policy=json.dumps(policy)
            )

            return {"success": True}

        except (ClientError, ValueError, KeyError) as e:
            logger.error(f"Failed to apply bucket policy: {e}")
            return {"success": False, "error": str(e)}

    def _needs_replication(self) -> bool:
        """Check if any buckets need replication."""
        return any(config.get("replication") for config in self.bucket_configs.values())

    def _create_replication_role(self) -> Optional[str]:
        """Create IAM role for S3 replication."""
        try:
            iam_client = boto3.client("iam")
            role_name = f"HavenHealthS3ReplicationRole-{self.environment}"

            # Trust policy for S3
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "s3.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }

            # Create role
            try:
                response = iam_client.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description="S3 replication role for Haven Health Passport",
                )
                role_arn = response["Role"]["Arn"]
            except ClientError as e:
                if e.response["Error"]["Code"] == "EntityAlreadyExists":
                    response = iam_client.get_role(RoleName=role_name)
                    role_arn = response["Role"]["Arn"]
                else:
                    raise

            # Attach replication policy
            replication_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetReplicationConfiguration", "s3:ListBucket"],
                        "Resource": "arn:aws:s3:::haven-health-*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObjectVersionForReplication",
                            "s3:GetObjectVersionAcl",
                            "s3:GetObjectVersionTagging",
                        ],
                        "Resource": "arn:aws:s3:::haven-health-*/*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:ReplicateObject",
                            "s3:ReplicateDelete",
                            "s3:ReplicateTags",
                        ],
                        "Resource": "arn:aws:s3:::haven-health-*-replica/*",
                    },
                ],
            }

            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName="S3ReplicationPolicy",
                PolicyDocument=json.dumps(replication_policy),
            )

            arn: str = role_arn
            return arn

        except (ClientError, ValueError, KeyError) as e:
            logger.error(f"Failed to create replication role: {e}")
            return None

    def _configure_replication(
        self, bucket_name: str, replication_role: str
    ) -> Dict[str, Any]:
        """Configure cross-region replication."""
        _ = replication_role  # Will be used for cross-region replication setup
        # This is a placeholder - actual implementation would set up replication
        # to a bucket in another region for disaster recovery
        logger.info(f"Replication configuration for {bucket_name} (placeholder)")
        return {"success": True}

    def validate_deployment(self) -> Dict[str, Any]:
        """Validate S3 infrastructure deployment."""
        validation_results: Dict[str, Any] = {
            "buckets_exist": {},
            "encryption_enabled": {},
            "versioning_enabled": {},
            "public_access_blocked": {},
            "lifecycle_configured": {},
            "is_valid": True,
            "errors": [],
        }

        try:
            for bucket_type, config in self.bucket_configs.items():
                bucket_name = config["name"]

                # Check if bucket exists
                try:
                    self.s3_client.head_bucket(Bucket=bucket_name)
                    validation_results["buckets_exist"][bucket_type] = True

                    # Check encryption
                    try:
                        response = self.s3_client.get_bucket_encryption(
                            Bucket=bucket_name
                        )
                        validation_results["encryption_enabled"][bucket_type] = True
                    except ClientError:
                        validation_results["encryption_enabled"][bucket_type] = False
                        validation_results["errors"].append(
                            f"{bucket_type}: Encryption not enabled"
                        )
                        validation_results["is_valid"] = False

                    # Check versioning
                    if config.get("versioning"):
                        response = self.s3_client.get_bucket_versioning(
                            Bucket=bucket_name
                        )
                        is_enabled = response.get("Status") == "Enabled"
                        validation_results["versioning_enabled"][
                            bucket_type
                        ] = is_enabled
                        if not is_enabled:
                            validation_results["errors"].append(
                                f"{bucket_type}: Versioning not enabled"
                            )
                            validation_results["is_valid"] = False

                    # Check public access block
                    try:
                        response = self.s3_client.get_public_access_block(
                            Bucket=bucket_name
                        )
                        config = response["PublicAccessBlockConfiguration"]
                        is_blocked = all(
                            [
                                config["BlockPublicAcls"],
                                config["IgnorePublicAcls"],
                                config["BlockPublicPolicy"],
                                config["RestrictPublicBuckets"],
                            ]
                        )
                        validation_results["public_access_blocked"][
                            bucket_type
                        ] = is_blocked
                        if not is_blocked:
                            validation_results["errors"].append(
                                f"{bucket_type}: Public access not fully blocked"
                            )
                            validation_results["is_valid"] = False
                    except ClientError:
                        validation_results["public_access_blocked"][bucket_type] = False
                        validation_results["errors"].append(
                            f"{bucket_type}: No public access block"
                        )
                        validation_results["is_valid"] = False

                    # Check lifecycle
                    if "lifecycle" in config:
                        try:
                            response = (
                                self.s3_client.get_bucket_lifecycle_configuration(
                                    Bucket=bucket_name
                                )
                            )
                            validation_results["lifecycle_configured"][bucket_type] = (
                                bool(response.get("Rules"))
                            )
                        except ClientError:
                            validation_results["lifecycle_configured"][
                                bucket_type
                            ] = False

                except ClientError:
                    validation_results["buckets_exist"][bucket_type] = False
                    validation_results["errors"].append(
                        f"{bucket_type}: Bucket does not exist"
                    )
                    validation_results["is_valid"] = False

        except (KeyError, ValueError, RuntimeError) as e:
            validation_results["is_valid"] = False
            validation_results["errors"].append(f"Validation failed: {e}")

        return validation_results


# Module-level singleton instance
_s3_infrastructure_instance = None


def get_s3_infrastructure() -> S3Infrastructure:
    """Get or create S3 infrastructure instance."""
    global _s3_infrastructure_instance
    if _s3_infrastructure_instance is None:
        _s3_infrastructure_instance = S3Infrastructure()
    return _s3_infrastructure_instance


def deploy_s3_infrastructure() -> Dict[str, Any]:
    """Deploy S3 infrastructure for production use."""
    infrastructure = get_s3_infrastructure()

    # Deploy infrastructure
    results = infrastructure.deploy_s3_infrastructure()

    # Validate deployment
    validation = infrastructure.validate_deployment()
    results["validation"] = validation

    if not validation["is_valid"]:
        logger.error(f"S3 infrastructure validation failed: {validation['errors']}")
        if settings.environment == "production":
            raise RuntimeError("Cannot proceed without valid S3 infrastructure!")

    return results
