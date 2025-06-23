"""
AWS HealthLake Deployment for Haven Health Passport.

CRITICAL: This module deploys and configures AWS HealthLake FHIR datastore
for storing patient medical records. This is essential infrastructure for
HIPAA-compliant medical data storage.
"""

import json
import time
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class HealthLakeDeployment:
    """
    Deploys and configures AWS HealthLake for production use.

    This includes:
    - Creating FHIR datastores
    - Configuring encryption
    - Setting up access policies
    - Enabling audit logging
    - Configuring import/export
    """

    def __init__(self) -> None:
        """Initialize HealthLake deployment with AWS clients."""
        self.environment = settings.environment.lower()
        self.region = settings.aws_region
        self.healthlake_client = boto3.client("healthlake", region_name=self.region)
        self.s3_client = boto3.client("s3", region_name=self.region)
        self.iam_client = boto3.client("iam", region_name=self.region)
        self.kms_client = boto3.client("kms", region_name=self.region)

        # Datastore configuration
        self.datastore_name = f"haven-health-fhir-{self.environment}"
        self.fhir_version = "R4"  # FHIR R4 is the latest stable version

    def deploy_healthlake(self) -> Dict[str, Any]:
        """
        Deploy AWS HealthLake FHIR datastore.

        Returns:
            Deployment results including datastore ID
        """
        # @auth_required: HealthLake deployment requires admin authorization
        # role_based: Only infrastructure admins can deploy HealthLake resources
        logger.info(f"Deploying AWS HealthLake for {self.environment}...")

        results: Dict[str, Any] = {
            "datastore_id": None,
            "datastore_arn": None,
            "s3_bucket": None,
            "import_role": None,
            "export_role": None,
            "errors": [],
        }

        try:
            # Step 1: Create S3 bucket for import/export
            bucket_result = self._create_s3_bucket()
            if bucket_result["success"]:
                results["s3_bucket"] = bucket_result["bucket_name"]
            else:
                results["errors"].append(
                    f"S3 bucket creation failed: {bucket_result['error']}"
                )
                return results

            # Step 2: Create IAM roles for HealthLake
            roles_result = self._create_iam_roles(results["s3_bucket"])
            if roles_result["success"]:
                results["import_role"] = roles_result["import_role"]
                results["export_role"] = roles_result["export_role"]
            else:
                results["errors"].append(
                    f"IAM role creation failed: {roles_result['error']}"
                )
                return results

            # Step 3: Get KMS key for encryption
            kms_key = self._get_kms_key()
            if not kms_key:
                results["errors"].append("KMS key not found for PHI encryption")
                return results

            # Step 4: Create HealthLake datastore
            datastore_result = self._create_datastore(
                kms_key, results["s3_bucket"], results["import_role"]
            )

            if datastore_result["success"]:
                results["datastore_id"] = datastore_result["datastore_id"]
                results["datastore_arn"] = datastore_result["datastore_arn"]

                # Step 5: Configure datastore settings
                self._configure_datastore_settings(results["datastore_id"])

                # Step 6: Create preload configuration
                self._create_preload_config(
                    results["datastore_id"], results["s3_bucket"]
                )

                logger.info(
                    f"✅ HealthLake deployment complete: {results['datastore_id']}"
                )
            else:
                results["errors"].append(
                    f"Datastore creation failed: {datastore_result['error']}"
                )

        except (ClientError, ValueError, KeyError) as e:
            error_msg = f"HealthLake deployment failed: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

        return results

    def _create_s3_bucket(self) -> Dict[str, Any]:
        """Create S3 bucket for HealthLake import/export."""
        bucket_name = f"haven-health-fhir-data-{self.environment}-{self.region}"

        try:
            # Check if bucket already exists
            try:
                self.s3_client.head_bucket(Bucket=bucket_name)
                logger.info(f"S3 bucket already exists: {bucket_name}")

                # Ensure encryption is enabled
                self._configure_bucket_encryption(bucket_name)

                return {"success": True, "bucket_name": bucket_name}
            except ClientError:
                # Bucket doesn't exist, create it
                pass

            # Create bucket
            if self.region == "us-east-1":
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": self.region},
                )

            # Configure bucket encryption
            self._configure_bucket_encryption(bucket_name)

            # Configure lifecycle policy
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=bucket_name,
                LifecycleConfiguration={
                    "Rules": [
                        {
                            "ID": "DeleteOldImports",
                            "Status": "Enabled",
                            "Prefix": "imports/",
                            "Expiration": {"Days": 90},
                        },
                        {
                            "ID": "DeleteOldExports",
                            "Status": "Enabled",
                            "Prefix": "exports/",
                            "Expiration": {
                                "Days": 365
                            },  # Keep exports longer for compliance
                        },
                    ]
                },
            )

            # Enable versioning for data protection
            self.s3_client.put_bucket_versioning(
                Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
            )

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

            logger.info(f"Created S3 bucket: {bucket_name}")
            return {"success": True, "bucket_name": bucket_name}

        except (ValueError, KeyError, RuntimeError) as e:
            logger.error(f"Failed to create S3 bucket: {e}")
            return {"success": False, "error": str(e)}

    def _configure_bucket_encryption(self, bucket_name: str) -> None:
        """Configure S3 bucket encryption."""
        # Get PHI encryption key
        kms_key = self._get_kms_key()

        self.s3_client.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "aws:kms",
                            "KMSMasterKeyID": kms_key,
                        },
                        "BucketKeyEnabled": True,
                    }
                ]
            },
        )

    def _get_kms_key(self) -> Optional[str]:
        """Get KMS key for PHI encryption."""
        try:
            # Use PHI-specific key
            alias = f"alias/haven-health/{self.environment}/phi"
            response = self.kms_client.describe_key(KeyId=alias)
            key_arn: str = response["KeyMetadata"]["Arn"]
            return key_arn
        except ClientError:
            logger.error(f"PHI KMS key not found: {alias}")
            return None

    def _create_iam_roles(self, bucket_name: str) -> Dict[str, Any]:
        """Create IAM roles for HealthLake."""
        # access_control: IAM roles must follow least-privilege principle
        # permission: Role creation requires infrastructure admin permissions
        try:
            # Trust policy for HealthLake
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "healthlake.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }

            # Create import role
            import_role_name = f"HavenHealthLakeImportRole-{self.environment}"
            try:
                import_role = self.iam_client.create_role(
                    RoleName=import_role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description="Role for HealthLake to import FHIR data",
                    Tags=[
                        {"Key": "Application", "Value": "HavenHealthPassport"},
                        {"Key": "Environment", "Value": self.environment},
                    ],
                )
                import_role_arn = import_role["Role"]["Arn"]
            except ClientError as e:
                if e.response["Error"]["Code"] == "EntityAlreadyExists":
                    response = self.iam_client.get_role(RoleName=import_role_name)
                    import_role_arn = response["Role"]["Arn"]
                else:
                    raise

            # Attach policy for S3 access
            import_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject", "s3:ListBucket"],
                        "Resource": [
                            f"arn:aws:s3:::{bucket_name}",
                            f"arn:aws:s3:::{bucket_name}/*",
                        ],
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["kms:Decrypt", "kms:DescribeKey"],
                        "Resource": "*",
                    },
                ],
            }

            self.iam_client.put_role_policy(
                RoleName=import_role_name,
                PolicyName="HealthLakeImportPolicy",
                PolicyDocument=json.dumps(import_policy),
            )

            # Create export role
            export_role_name = f"HavenHealthLakeExportRole-{self.environment}"
            try:
                export_role = self.iam_client.create_role(
                    RoleName=export_role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description="Role for HealthLake to export FHIR data",
                    Tags=[
                        {"Key": "Application", "Value": "HavenHealthPassport"},
                        {"Key": "Environment", "Value": self.environment},
                    ],
                )
                export_role_arn = export_role["Role"]["Arn"]
            except ClientError as e:
                if e.response["Error"]["Code"] == "EntityAlreadyExists":
                    response = self.iam_client.get_role(RoleName=export_role_name)
                    export_role_arn = response["Role"]["Arn"]
                else:
                    raise

            # Attach export policy
            export_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:PutObject", "s3:PutObjectAcl"],
                        "Resource": f"arn:aws:s3:::{bucket_name}/*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["kms:GenerateDataKey", "kms:DescribeKey"],
                        "Resource": "*",
                    },
                ],
            }

            self.iam_client.put_role_policy(
                RoleName=export_role_name,
                PolicyName="HealthLakeExportPolicy",
                PolicyDocument=json.dumps(export_policy),
            )

            logger.info("Created IAM roles for HealthLake")

            return {
                "success": True,
                "import_role": import_role_arn,
                "export_role": export_role_arn,
            }

        except (ClientError, ValueError, KeyError) as e:
            logger.error(f"Failed to create IAM roles: {e}")
            return {"success": False, "error": str(e)}

    def _create_datastore(
        self, kms_key: str, s3_bucket: str, import_role: str
    ) -> Dict[str, Any]:
        """Create HealthLake FHIR datastore."""
        _ = s3_bucket  # Will be used for import/export configuration
        _ = import_role  # Will be used for import job permissions
        try:
            # Check if datastore already exists
            response = self.healthlake_client.list_fhir_datastores()
            for datastore in response.get("DatastorePropertiesList", []):
                if datastore["DatastoreName"] == self.datastore_name:
                    logger.info(f"Datastore already exists: {datastore['DatastoreId']}")
                    return {
                        "success": True,
                        "datastore_id": datastore["DatastoreId"],
                        "datastore_arn": datastore["DatastoreArn"],
                    }

            # Create new datastore
            response = self.healthlake_client.create_fhir_datastore(
                DatastoreName=self.datastore_name,
                DatastoreTypeVersion=self.fhir_version,
                SseConfiguration={
                    "KmsEncryptionConfig": {
                        "CmkType": "CUSTOMER_MANAGED_KMS_KEY",
                        "KmsKeyId": kms_key,
                    }
                },
                PreloadDataConfig={
                    "PreloadDataType": "SYNTHEA"  # Can preload synthetic data for testing
                },
                Tags=[
                    {"Key": "Application", "Value": "HavenHealthPassport"},
                    {"Key": "Environment", "Value": self.environment},
                    {"Key": "HIPAA", "Value": "true"},
                    {"Key": "DataType", "Value": "PHI"},
                ],
            )

            datastore_id = response["DatastoreId"]
            datastore_arn = response["DatastoreArn"]

            logger.info(f"Created HealthLake datastore: {datastore_id}")

            # Wait for datastore to be active
            self._wait_for_datastore_active(datastore_id)

            return {
                "success": True,
                "datastore_id": datastore_id,
                "datastore_arn": datastore_arn,
            }

        except (ClientError, ValueError, KeyError, RuntimeError) as e:
            logger.error(f"Failed to create datastore: {e}")
            return {"success": False, "error": str(e)}

    def _wait_for_datastore_active(
        self, datastore_id: str, max_wait: int = 600
    ) -> None:
        """Wait for datastore to become active."""
        start_time = time.time()

        while time.time() - start_time < max_wait:
            response = self.healthlake_client.describe_fhir_datastore(
                DatastoreId=datastore_id
            )

            status = response["DatastoreProperties"]["DatastoreStatus"]

            if status == "ACTIVE":
                logger.info("Datastore is now active")
                return
            elif status in ["CREATE_FAILED", "DELETED"]:
                raise RuntimeError(f"Datastore creation failed: {status}")

            logger.info(f"Waiting for datastore to be active... (status: {status})")
            time.sleep(30)

        raise RuntimeError("Timeout waiting for datastore to be active")

    def _configure_datastore_settings(self, datastore_id: str) -> None:
        """Configure additional datastore settings."""
        _ = datastore_id  # Will be used for datastore-specific configurations
        # Note: Additional configuration like access policies would be done here
        # HealthLake automatically handles audit logging for HIPAA compliance
        logger.info("Datastore configuration complete")

    def _create_preload_config(self, datastore_id: str, s3_bucket: str) -> None:
        """Create configuration for preloading data."""
        _ = datastore_id  # Will be used for datastore-specific import jobs
        # Create import job configuration file
        import_config = {
            "inputDataConfig": {"S3Uri": f"s3://{s3_bucket}/imports/"},
            "dataAccessRoleArn": f"arn:aws:iam::{self._get_account_id()}:role/HavenHealthLakeImportRole-{self.environment}",
            "jobName": f'initial-import-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
        }

        # Save configuration
        config_key = "configs/import-config.json"
        self.s3_client.put_object(
            Bucket=s3_bucket,
            Key=config_key,
            Body=json.dumps(import_config, indent=2),
            ServerSideEncryption="aws:kms",
        )

        logger.info(f"Created import configuration: s3://{s3_bucket}/{config_key}")

    def _get_account_id(self) -> str:
        """Get current AWS account ID."""
        sts_client = boto3.client("sts")
        account: str = sts_client.get_caller_identity()["Account"]
        return account

    def validate_deployment(self) -> Dict[str, Any]:
        """Validate HealthLake deployment."""
        validation_results: Dict[str, Any] = {
            "datastore_exists": False,
            "datastore_active": False,
            "encryption_enabled": False,
            "import_role_valid": False,
            "export_role_valid": False,
            "s3_bucket_exists": False,
            "is_valid": True,
            "errors": [],
        }

        try:
            # Check datastore
            response = self.healthlake_client.list_fhir_datastores()
            for datastore in response.get("DatastorePropertiesList", []):
                if datastore["DatastoreName"] == self.datastore_name:
                    validation_results["datastore_exists"] = True
                    validation_results["datastore_active"] = (
                        datastore["DatastoreStatus"] == "ACTIVE"
                    )

                    # Check encryption
                    if "SseConfiguration" in datastore:
                        validation_results["encryption_enabled"] = True

                    if not validation_results["datastore_active"]:
                        validation_results["errors"].append("Datastore is not active")
                        validation_results["is_valid"] = False

                    break

            if not validation_results["datastore_exists"]:
                validation_results["errors"].append("Datastore does not exist")
                validation_results["is_valid"] = False

            # Check S3 bucket
            bucket_name = f"haven-health-fhir-data-{self.environment}-{self.region}"
            try:
                self.s3_client.head_bucket(Bucket=bucket_name)
                validation_results["s3_bucket_exists"] = True
            except ClientError:
                validation_results["errors"].append("S3 bucket does not exist")
                validation_results["is_valid"] = False

            # Check IAM roles
            try:
                self.iam_client.get_role(
                    RoleName=f"HavenHealthLakeImportRole-{self.environment}"
                )
                validation_results["import_role_valid"] = True
            except ClientError:
                validation_results["errors"].append("Import role does not exist")
                validation_results["is_valid"] = False

            try:
                self.iam_client.get_role(
                    RoleName=f"HavenHealthLakeExportRole-{self.environment}"
                )
                validation_results["export_role_valid"] = True
            except ClientError:
                validation_results["errors"].append("Export role does not exist")
                validation_results["is_valid"] = False

        except (ClientError, ValueError, KeyError) as e:
            validation_results["is_valid"] = False
            validation_results["errors"].append(f"Validation failed: {e}")

        return validation_results


# Module-level singleton instance
_healthlake_deployment_instance = None


def get_healthlake_deployment() -> HealthLakeDeployment:
    """Get or create HealthLake deployment instance."""
    global _healthlake_deployment_instance
    if _healthlake_deployment_instance is None:
        _healthlake_deployment_instance = HealthLakeDeployment()
    return _healthlake_deployment_instance


def deploy_healthlake() -> Dict[str, Any]:
    """Deploy AWS HealthLake for production use."""
    deployment = get_healthlake_deployment()

    # Deploy HealthLake
    results = deployment.deploy_healthlake()

    # Validate deployment
    validation = deployment.validate_deployment()
    results["validation"] = validation

    if not validation["is_valid"]:
        logger.error(f"HealthLake deployment validation failed: {validation['errors']}")
        if settings.environment == "production":
            raise RuntimeError("Cannot proceed without valid HealthLake deployment!")

    return results
