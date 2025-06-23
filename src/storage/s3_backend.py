"""AWS S3 storage backend implementation.

Note: This module handles PHI-related file storage in S3.
- Access Control: Implement strict access control for S3 operations and bucket management
"""

# pylint: disable=too-many-lines

import io
import json
from datetime import datetime, timedelta
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# Use more specific exceptions from cryptography
from cryptography.exceptions import InvalidKey, InvalidSignature

from src.storage.base import (
    FileCategory,
    FileMetadata,
    StorageBackend,
    StorageException,
    StorageFileNotFoundError,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class S3StorageBackend(StorageBackend):
    """AWS S3 implementation of storage backend."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize S3 storage backend.

        Config should include:
        - bucket_name: S3 bucket name
        - region: AWS region
        - access_key_id: AWS access key ID (optional if using IAM role)
        - secret_access_key: AWS secret access key (optional if using IAM role)
        - encryption: Server-side encryption type (AES256, aws:kms)
        - kms_key_id: KMS key ID if using KMS encryption
        - storage_class: S3 storage class (STANDARD, STANDARD_IA, etc.)
        - lifecycle_rules: Whether to apply lifecycle rules
        - cloudfront_distribution_id: CloudFront distribution ID for CDN
        - cloudfront_domain: CloudFront domain name
        """
        super().__init__(config)

        # Initialize S3 client
        self._init_s3_client()

        # Ensure bucket exists and is configured
        self._setup_bucket()

        # Initialize CloudFront client if CDN is configured
        if self.config.get("cloudfront_distribution_id"):
            self._init_cloudfront_client()

    def _validate_config(self) -> None:
        """Validate S3 backend configuration."""
        required = ["bucket_name", "region"]
        for field in required:
            if field not in self.config:
                raise StorageException(f"Missing required config field: {field}")

        # Validate storage class
        valid_storage_classes = [
            "STANDARD",
            "REDUCED_REDUNDANCY",
            "STANDARD_IA",
            "ONEZONE_IA",
            "INTELLIGENT_TIERING",
            "GLACIER",
            "DEEP_ARCHIVE",
        ]
        storage_class = self.config.get("storage_class", "STANDARD")
        if storage_class not in valid_storage_classes:
            raise StorageException(f"Invalid storage class: {storage_class}")

    def _init_s3_client(self) -> None:
        """Initialize S3 client."""
        try:
            # Build client config
            client_config = {"region_name": self.config["region"]}

            # Add credentials if provided
            if "access_key_id" in self.config and "secret_access_key" in self.config:
                client_config["aws_access_key_id"] = self.config["access_key_id"]
                client_config["aws_secret_access_key"] = self.config[
                    "secret_access_key"
                ]

            # Create S3 client
            self.s3_client = boto3.client("s3", **client_config)

            # Create S3 resource for some operations
            self.s3_resource = boto3.resource("s3", **client_config)

            logger.info(
                f"Initialized S3 client for bucket: {self.config['bucket_name']}"
            )

        except (
            BotoCoreError,
            ClientError,
            ConnectionError,
            TypeError,
            ValueError,
        ) as e:
            raise StorageException(f"Failed to initialize S3 client: {e}") from e

    def _init_cloudfront_client(self) -> None:
        """Initialize CloudFront client for CDN integration."""
        try:
            client_config = {"region_name": self.config["region"]}

            if "access_key_id" in self.config and "secret_access_key" in self.config:
                client_config["aws_access_key_id"] = self.config["access_key_id"]
                client_config["aws_secret_access_key"] = self.config[
                    "secret_access_key"
                ]

            self.cloudfront_client = boto3.client("cloudfront", **client_config)

            logger.info(
                f"Initialized CloudFront client for distribution: {self.config['cloudfront_distribution_id']}"
            )

        except (ClientError, KeyError, ValueError) as e:
            logger.warning(f"CloudFront initialization failed: {e}")
            self.cloudfront_client = None

    def _setup_bucket(self) -> None:
        """Ensure bucket exists and is properly configured."""
        try:
            # Check if bucket exists
            self.s3_client.head_bucket(Bucket=self.config["bucket_name"])

            # Configure bucket policies if needed
            self._configure_bucket_policies()

            # Set up lifecycle rules if enabled
            if self.config.get("lifecycle_rules", True):
                self._configure_lifecycle_rules()

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                # Bucket doesn't exist, create it
                self._create_bucket()
            else:
                raise StorageException(f"Error accessing bucket: {e}") from e

    def _create_bucket(self) -> None:
        """Create S3 bucket with proper configuration."""
        try:
            # Create bucket with location constraint
            if self.config["region"] == "us-east-1":
                self.s3_client.create_bucket(Bucket=self.config["bucket_name"])
            else:
                self.s3_client.create_bucket(
                    Bucket=self.config["bucket_name"],
                    CreateBucketConfiguration={
                        "LocationConstraint": self.config["region"]
                    },
                )

            # Enable versioning
            self.s3_client.put_bucket_versioning(
                Bucket=self.config["bucket_name"],
                VersioningConfiguration={"Status": "Enabled"},
            )

            # Enable server-side encryption by default
            encryption_config = {
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": self.config.get("encryption", "AES256")
                        }
                    }
                ]
            }

            if (
                self.config.get("encryption") == "aws:kms"
                and "kms_key_id" in self.config
            ):
                encryption_config["Rules"][0]["ApplyServerSideEncryptionByDefault"][
                    "KMSMasterKeyID"
                ] = self.config["kms_key_id"]

            self.s3_client.put_bucket_encryption(
                Bucket=self.config["bucket_name"],
                ServerSideEncryptionConfiguration=encryption_config,
            )

            # Block public access
            self.s3_client.put_public_access_block(
                Bucket=self.config["bucket_name"],
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                },
            )

            logger.info(f"Created S3 bucket: {self.config['bucket_name']}")

        except (InvalidKey, InvalidSignature, ValueError) as e:
            raise StorageException(f"Failed to create bucket: {e}") from e

    def _configure_bucket_policies(self) -> None:
        """Configure bucket policies for security."""
        try:
            # Add bucket policy for HTTPS-only access
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "DenyInsecureConnections",
                        "Effect": "Deny",
                        "Principal": "*",
                        "Action": "s3:*",
                        "Resource": [
                            f"arn:aws:s3:::{self.config['bucket_name']}/*",
                            f"arn:aws:s3:::{self.config['bucket_name']}",
                        ],
                        "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                    }
                ],
            }

            self.s3_client.put_bucket_policy(
                Bucket=self.config["bucket_name"], Policy=json.dumps(policy)
            )

        except ClientError as e:
            # Policy might already exist
            logger.warning(f"Could not set bucket policy: {e}")

    def _configure_lifecycle_rules(self) -> None:
        """Configure lifecycle rules for cost optimization and compliance."""
        try:
            lifecycle_config = {
                "Rules": [
                    {
                        "ID": "MoveToIA",
                        "Status": "Enabled",
                        "Transitions": [{"Days": 30, "StorageClass": "STANDARD_IA"}],
                        "Filter": {"Prefix": ""},
                    },
                    {
                        "ID": "DeleteOldVersions",
                        "Status": "Enabled",
                        "NoncurrentVersionExpiration": {"NoncurrentDays": 90},
                        "Filter": {"Prefix": ""},
                    },
                    {
                        "ID": "AbortIncompleteMultipartUploads",
                        "Status": "Enabled",
                        "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
                        "Filter": {"Prefix": ""},
                    },
                ]
            }

            # Add 7-year retention rule for medical records
            lifecycle_config["Rules"].append(
                {
                    "ID": "MedicalRecordRetention",
                    "Status": "Enabled",
                    "Transitions": [
                        {"Days": 365, "StorageClass": "GLACIER"},
                        {"Days": 730, "StorageClass": "DEEP_ARCHIVE"},  # 2 years
                    ],
                    "Filter": {
                        "And": {
                            "Prefix": "",
                            "Tags": [{"Key": "category", "Value": "medical_record"}],
                        }
                    },
                }
            )

            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=self.config["bucket_name"],
                LifecycleConfiguration=lifecycle_config,
            )

            logger.info("Configured S3 lifecycle rules")

        except (ClientError, ValueError) as e:
            logger.warning(f"Could not set lifecycle rules: {e}")

    def put(
        self,
        file_id: str,
        file_data: BinaryIO,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        encryption_key: Optional[str] = None,
    ) -> FileMetadata:
        """Store a file in S3."""
        try:
            # Calculate checksum
            checksum = self.calculate_checksum(file_data)

            # Get file size
            file_data.seek(0, 2)
            size = file_data.tell()
            file_data.seek(0)

            # Prepare put parameters
            put_params = {
                "Bucket": self.config["bucket_name"],
                "Key": file_id,
                "Body": file_data,
                "ContentType": content_type or "application/octet-stream",
                "StorageClass": self.config.get("storage_class", "STANDARD"),
                "Metadata": {},
            }

            # Add server-side encryption
            if (
                self.config.get("encryption") == "aws:kms"
                and "kms_key_id" in self.config
            ):
                put_params["ServerSideEncryption"] = "aws:kms"
                put_params["SSEKMSKeyId"] = self.config["kms_key_id"]
            elif self.config.get("encryption") == "AES256":
                put_params["ServerSideEncryption"] = "AES256"

            # Add client-side encryption if provided
            if encryption_key:
                put_params["SSECustomerAlgorithm"] = "AES256"
                put_params["SSECustomerKey"] = encryption_key

            # Add metadata
            if metadata:
                # S3 metadata must be string values
                for key, value in metadata.items():
                    put_params["Metadata"][key] = (
                        json.dumps(value) if not isinstance(value, str) else value
                    )

            # Add checksum
            put_params["Metadata"]["checksum"] = checksum

            # Upload file
            response = self.s3_client.put_object(**put_params)

            # Apply tags if provided
            if tags:
                tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]
                self.s3_client.put_object_tagging(
                    Bucket=self.config["bucket_name"],
                    Key=file_id,
                    Tagging={"TagSet": tag_set},
                )

            # Determine category from metadata or tags
            category = FileCategory.OTHER
            if metadata and "category" in metadata:
                try:
                    category = FileCategory(metadata["category"])
                except ValueError:
                    pass

            # Create file metadata
            file_metadata = FileMetadata(
                file_id=file_id,
                filename=(
                    metadata.get("original_filename", file_id) if metadata else file_id
                ),
                content_type=content_type or "application/octet-stream",
                size=size,
                checksum=checksum,
                category=category,
                created_at=datetime.utcnow(),
                modified_at=datetime.utcnow(),
                version=response.get("VersionId", 1),
                tags=tags,
                custom_metadata=metadata,
            )

            logger.info(f"Uploaded file to S3: {file_id}")

            return file_metadata

        except ClientError as e:
            raise StorageException(f"Failed to upload to S3: {e}") from e

    def get(
        self,
        file_id: str,
        version: Optional[int] = None,
        decryption_key: Optional[str] = None,
    ) -> Tuple[BinaryIO, FileMetadata]:
        """Retrieve a file from S3."""
        try:
            # Prepare get parameters
            get_params = {"Bucket": self.config["bucket_name"], "Key": file_id}

            # Add version if specified
            if version:
                get_params["VersionId"] = str(version)

            # Add decryption key if provided
            if decryption_key:
                get_params["SSECustomerAlgorithm"] = "AES256"
                get_params["SSECustomerKey"] = decryption_key

            # Download file
            response = self.s3_client.get_object(**get_params)

            # Extract metadata
            s3_metadata = response.get("Metadata", {})
            custom_metadata = {}
            for key, value in s3_metadata.items():
                try:
                    custom_metadata[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    custom_metadata[key] = value

            # Get tags
            tags = {}
            try:
                tag_response = self.s3_client.get_object_tagging(
                    Bucket=self.config["bucket_name"], Key=file_id
                )
                tags = {
                    tag["Key"]: tag["Value"] for tag in tag_response.get("TagSet", [])
                }
            except (ClientError, KeyError):
                pass

            # Determine category
            category = FileCategory.OTHER
            if "category" in custom_metadata:
                try:
                    category = FileCategory(custom_metadata["category"])
                except ValueError:
                    pass

            # Create file metadata
            file_metadata = FileMetadata(
                file_id=file_id,
                filename=custom_metadata.get("original_filename", file_id),
                content_type=response.get("ContentType", "application/octet-stream"),
                size=response.get("ContentLength", 0),
                checksum=custom_metadata.get("checksum", ""),
                category=category,
                created_at=response.get("LastModified", datetime.utcnow()),
                modified_at=response.get("LastModified", datetime.utcnow()),
                version=response.get("VersionId", 1),
                tags=tags,
                custom_metadata=custom_metadata,
            )

            # Return file data as BytesIO
            file_data = io.BytesIO(response["Body"].read())

            return file_data, file_metadata

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                raise StorageFileNotFoundError(f"File not found: {file_id}") from e
            raise StorageException(f"Failed to download from S3: {e}") from e

    def exists(self, file_id: str) -> bool:
        """Check if a file exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.config["bucket_name"], Key=file_id)
            return True
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404" or error_code == "NoSuchKey":
                return False
            raise StorageException(f"Error checking file existence: {e}") from e

    def delete(
        self, file_id: str, version: Optional[int] = None, permanent: bool = False
    ) -> bool:
        """Delete a file from S3."""
        try:
            if permanent and version:
                # Delete specific version
                self.s3_client.delete_object(
                    Bucket=self.config["bucket_name"],
                    Key=file_id,
                    VersionId=str(version),
                )
            elif permanent:
                # Delete all versions
                # List all versions
                versions_response = self.s3_client.list_object_versions(
                    Bucket=self.config["bucket_name"], Prefix=file_id
                )

                # Delete each version
                for version in versions_response.get("Versions", []):
                    if isinstance(version, dict) and version.get("Key") == file_id:
                        self.s3_client.delete_object(
                            Bucket=self.config["bucket_name"],
                            Key=file_id,
                            VersionId=version["VersionId"],
                        )

                # Delete delete markers
                for marker in versions_response.get("DeleteMarkers", []):
                    if isinstance(marker, dict) and marker.get("Key") == file_id:
                        self.s3_client.delete_object(
                            Bucket=self.config["bucket_name"],
                            Key=file_id,
                            VersionId=marker["VersionId"],
                        )
            else:
                # Soft delete - just add a delete marker
                self.s3_client.delete_object(
                    Bucket=self.config["bucket_name"], Key=file_id
                )

            logger.info(f"Deleted file from S3: {file_id} (permanent={permanent})")
            return True

        except ClientError as e:
            logger.error(
                "Failed to delete from S3: %s", str(e)
            )  # nosec B608 - Not SQL, just error logging
            return False

    def list(
        self,
        prefix: Optional[str] = None,
        category: Optional[FileCategory] = None,
        tags: Optional[Dict[str, str]] = None,
        limit: int = 1000,
        continuation_token: Optional[str] = None,
    ) -> Tuple[List[FileMetadata], Optional[str]]:
        """List files in S3."""
        try:
            # Prepare list parameters
            list_params = {
                "Bucket": self.config["bucket_name"],
                "MaxKeys": min(limit, 1000),  # S3 max is 1000
            }

            if prefix:
                list_params["Prefix"] = prefix

            if continuation_token:
                list_params["ContinuationToken"] = continuation_token

            # List objects
            response = self.s3_client.list_objects_v2(**list_params)

            files = []
            for obj in response.get("Contents", []):
                # Skip if object is a folder marker
                if obj["Key"].endswith("/"):
                    continue

                # Get metadata for each object
                try:
                    metadata = self.get_metadata(obj["Key"])

                    if metadata:
                        # Filter by category if specified
                        if category and metadata.category != category:
                            continue

                        # Filter by tags if specified
                        if tags:
                            match = all(
                                metadata.tags.get(k) == v for k, v in tags.items()
                            )
                            if not match:
                                continue

                        files.append(metadata)

                except (ClientError, ValueError, KeyError) as e:
                    logger.warning(f"Could not get metadata for {obj['Key']}: {e}")

            # Get next continuation token
            next_token = response.get("NextContinuationToken")

            return files, next_token

        except ClientError as e:
            raise StorageException(f"Failed to list files: {e}") from e

    def get_metadata(self, file_id: str) -> FileMetadata:
        """Get metadata for a file without downloading it."""
        try:
            # Get object metadata
            response = self.s3_client.head_object(
                Bucket=self.config["bucket_name"], Key=file_id
            )

            # Extract custom metadata
            s3_metadata = response.get("Metadata", {})
            custom_metadata = {}
            for key, value in s3_metadata.items():
                try:
                    custom_metadata[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    custom_metadata[key] = value

            # Get tags
            tags = {}
            try:
                tag_response = self.s3_client.get_object_tagging(
                    Bucket=self.config["bucket_name"], Key=file_id
                )
                tags = {
                    tag["Key"]: tag["Value"] for tag in tag_response.get("TagSet", [])
                }
            except (ClientError, KeyError):
                pass

            # Determine category
            category = FileCategory.OTHER
            if "category" in custom_metadata:
                try:
                    category = FileCategory(custom_metadata["category"])
                except ValueError:
                    pass

            # Create metadata object
            metadata = FileMetadata(
                file_id=file_id,
                filename=custom_metadata.get("original_filename", file_id),
                content_type=response.get("ContentType", "application/octet-stream"),
                size=response.get("ContentLength", 0),
                checksum=custom_metadata.get("checksum", ""),
                category=category,
                created_at=response.get("LastModified", datetime.utcnow()),
                modified_at=response.get("LastModified", datetime.utcnow()),
                version=response.get("VersionId", 1),
                tags=tags,
                custom_metadata=custom_metadata,
            )

            return metadata

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404" or error_code == "NoSuchKey":
                raise StorageFileNotFoundError(f"File not found: {file_id}") from e
            raise StorageException(f"Failed to get metadata: {e}") from e

    def update_metadata(
        self,
        file_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> FileMetadata:
        """Update metadata for a file."""
        try:
            # Get current object info
            current_metadata = self.get_metadata(file_id)

            # Update tags if provided
            if tags is not None:
                tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]
                self.s3_client.put_object_tagging(
                    Bucket=self.config["bucket_name"],
                    Key=file_id,
                    Tagging={"TagSet": tag_set},
                )
                current_metadata.tags = tags

            # Update metadata requires copying the object
            if metadata is not None:
                # Merge with existing metadata
                merged_metadata = current_metadata.custom_metadata.copy()
                merged_metadata.update(metadata)

                # Convert to S3 metadata format
                s3_metadata = {}
                for key, value in merged_metadata.items():
                    s3_metadata[key] = (
                        json.dumps(value) if not isinstance(value, str) else value
                    )

                # Copy object with new metadata
                copy_source = {"Bucket": self.config["bucket_name"], "Key": file_id}

                self.s3_client.copy_object(
                    CopySource=copy_source,
                    Bucket=self.config["bucket_name"],
                    Key=file_id,
                    Metadata=s3_metadata,
                    MetadataDirective="REPLACE",
                    StorageClass=self.config.get("storage_class", "STANDARD"),
                )

                current_metadata.custom_metadata = merged_metadata

            return current_metadata

        except (ClientError, ValueError) as e:
            raise StorageException(f"Failed to update metadata: {e}") from e

    def generate_presigned_url(
        self,
        file_id: str,
        operation: str = "get",
        expiration: Optional[timedelta] = None,
        content_type: Optional[str] = None,
        content_disposition: Optional[str] = None,
    ) -> str:
        """Generate a pre-signed URL."""
        if expiration is None:
            expiration = timedelta(hours=1)
        try:
            # Map operation to S3 client method
            if operation == "get":
                client_method = "get_object"
                params = {"Bucket": self.config["bucket_name"], "Key": file_id}

                if content_disposition:
                    params["ResponseContentDisposition"] = content_disposition

            elif operation == "put":
                client_method = "put_object"
                params = {"Bucket": self.config["bucket_name"], "Key": file_id}

                if content_type:
                    params["ContentType"] = content_type

            else:
                raise ValueError(f"Invalid operation: {operation}")

            # Generate URL
            url = self.s3_client.generate_presigned_url(
                ClientMethod=client_method,
                Params=params,
                ExpiresIn=int(expiration.total_seconds()),
            )

            return url  # type: ignore[no-any-return]

        except (TypeError, ValueError) as e:
            raise StorageException(f"Failed to generate presigned URL: {e}") from e

    def copy(
        self,
        source_file_id: str,
        destination_file_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileMetadata:
        """Copy a file within S3."""
        try:
            # Get source metadata
            source_metadata = self.get_metadata(source_file_id)

            # Prepare copy parameters
            copy_source = {"Bucket": self.config["bucket_name"], "Key": source_file_id}

            # Merge metadata
            if metadata:
                merged_metadata = source_metadata.custom_metadata.copy()
                merged_metadata.update(metadata)
            else:
                merged_metadata = source_metadata.custom_metadata

            # Convert to S3 metadata format
            s3_metadata = {}
            for key, value in merged_metadata.items():
                s3_metadata[key] = (
                    json.dumps(value) if not isinstance(value, str) else value
                )

            # Copy object
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.config["bucket_name"],
                Key=destination_file_id,
                Metadata=s3_metadata,
                MetadataDirective="REPLACE",
                StorageClass=self.config.get("storage_class", "STANDARD"),
            )

            # Copy tags
            if source_metadata.tags:
                tag_set = [
                    {"Key": k, "Value": v} for k, v in source_metadata.tags.items()
                ]
                self.s3_client.put_object_tagging(
                    Bucket=self.config["bucket_name"],
                    Key=destination_file_id,
                    Tagging={"TagSet": tag_set},
                )

            # Get new metadata
            return self.get_metadata(destination_file_id)

        except OSError as e:
            raise StorageException(f"Failed to copy file: {e}") from e

    def create_multipart_upload(
        self,
        file_id: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Initiate a multipart upload."""
        try:
            # Prepare parameters
            params = {
                "Bucket": self.config["bucket_name"],
                "Key": file_id,
                "StorageClass": self.config.get("storage_class", "STANDARD"),
            }

            if content_type:
                params["ContentType"] = content_type

            # Add metadata
            if metadata:
                s3_metadata = {}
                for key, value in metadata.items():
                    s3_metadata[key] = (
                        json.dumps(value) if not isinstance(value, str) else value
                    )
                params["Metadata"] = s3_metadata

            # Add encryption
            if (
                self.config.get("encryption") == "aws:kms"
                and "kms_key_id" in self.config
            ):
                params["ServerSideEncryption"] = "aws:kms"
                params["SSEKMSKeyId"] = self.config["kms_key_id"]
            elif self.config.get("encryption") == "AES256":
                params["ServerSideEncryption"] = "AES256"

            # Create multipart upload
            response = self.s3_client.create_multipart_upload(**params)

            return response["UploadId"]  # type: ignore[no-any-return]

        except (
            BotoCoreError,
            ClientError,
            InvalidKey,
            InvalidSignature,
            OSError,
            TypeError,
            ValueError,
        ) as e:
            raise StorageException(f"Failed to create multipart upload: {e}") from e

    def upload_part(
        self, file_id: str, upload_id: str, part_number: int, data: BinaryIO
    ) -> str:
        """Upload a part in a multipart upload."""
        try:
            response = self.s3_client.upload_part(
                Bucket=self.config["bucket_name"],
                Key=file_id,
                UploadId=upload_id,
                PartNumber=part_number,
                Body=data,
            )

            return response["ETag"]  # type: ignore[no-any-return]

        except (TypeError, ValueError) as e:
            raise StorageException(f"Failed to upload part: {e}") from e

    def complete_multipart_upload(
        self, file_id: str, upload_id: str, parts: List[Dict[str, Any]]
    ) -> FileMetadata:
        """Complete a multipart upload."""
        try:
            # Format parts for S3
            multipart_parts = []
            for part in parts:
                multipart_parts.append(
                    {"ETag": part["etag"], "PartNumber": part["part_number"]}
                )

            # Complete upload
            self.s3_client.complete_multipart_upload(
                Bucket=self.config["bucket_name"],
                Key=file_id,
                UploadId=upload_id,
                MultipartUpload={"Parts": multipart_parts},
            )

            # Get metadata for completed upload
            return self.get_metadata(file_id)

        except OSError as e:
            raise StorageException(f"Failed to complete multipart upload: {e}") from e

    def abort_multipart_upload(self, file_id: str, upload_id: str) -> bool:
        """Abort a multipart upload."""
        try:
            self.s3_client.abort_multipart_upload(
                Bucket=self.config["bucket_name"], Key=file_id, UploadId=upload_id
            )

            return True

        except (ClientError, ValueError) as e:
            logger.error(f"Failed to abort multipart upload: {e}")
            return False

    def get_cdn_url(self, file_id: str) -> Optional[str]:
        """Get CDN URL for a file if CloudFront is configured."""
        if not self.config.get("cloudfront_domain"):
            return None

        # Return CloudFront URL
        return f"https://{self.config['cloudfront_domain']}/{file_id}"

    def invalidate_cdn_cache(self, file_ids: List[str]) -> bool:
        """Invalidate CloudFront cache for specific files."""
        if not self.cloudfront_client or not self.config.get(
            "cloudfront_distribution_id"
        ):
            return False

        try:
            # Create invalidation batch
            paths = [f"/{file_id}" for file_id in file_ids]

            response = self.cloudfront_client.create_invalidation(
                DistributionId=self.config["cloudfront_distribution_id"],
                InvalidationBatch={
                    "Paths": {"Quantity": len(paths), "Items": paths},
                    "CallerReference": f"invalidation-{datetime.utcnow().isoformat()}",
                },
            )

            logger.info(
                f"Created CloudFront invalidation: {response['Invalidation']['Id']}"
            )
            return True

        except (ClientError, KeyError) as e:
            logger.error(f"Failed to invalidate CDN cache: {e}")
            return False

    def setup_backup_replication(self) -> bool:
        """Set up cross-region replication for backups."""
        try:
            # Get backup region from config
            backup_region = self.config.get("backup_region", "us-west-2")

            if backup_region == self.config["region"]:
                logger.warning("Backup region same as primary region")
                return False

            # Create IAM role for replication if not exists
            iam = boto3.client("iam")
            role_name = f"s3-replication-{self.config['bucket_name']}"

            try:
                # Check if role exists
                iam.get_role(RoleName=role_name)
            except ClientError:
                # Create role
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

                iam.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                )

                # Attach policy
                replication_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "s3:GetReplicationConfiguration",
                                "s3:ListBucket",
                            ],
                            "Resource": f"arn:aws:s3:::{self.config['bucket_name']}",
                        },
                        {
                            "Effect": "Allow",
                            "Action": [
                                "s3:GetObjectVersionForReplication",
                                "s3:GetObjectVersionAcl",
                            ],
                            "Resource": f"arn:aws:s3:::{self.config['bucket_name']}/*",
                        },
                        {
                            "Effect": "Allow",
                            "Action": [
                                "s3:ReplicateObject",
                                "s3:ReplicateDelete",
                                "s3:ReplicateTags",
                            ],
                            "Resource": f"arn:aws:s3:::{self.config['bucket_name']}-backup/*",
                        },
                    ],
                }

                iam.put_role_policy(
                    RoleName=role_name,
                    PolicyName="ReplicationPolicy",
                    PolicyDocument=json.dumps(replication_policy),
                )

            # Create backup bucket if not exists
            backup_bucket = f"{self.config['bucket_name']}-backup"
            backup_s3 = boto3.client("s3", region_name=backup_region)

            try:
                backup_s3.head_bucket(Bucket=backup_bucket)
            except ClientError:
                backup_s3.create_bucket(
                    Bucket=backup_bucket,
                    CreateBucketConfiguration={"LocationConstraint": backup_region},
                )

                # Enable versioning on backup bucket
                backup_s3.put_bucket_versioning(
                    Bucket=backup_bucket, VersioningConfiguration={"Status": "Enabled"}
                )

            # Set up replication configuration
            replication_config = {
                "Role": f"arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:role/{role_name}",
                "Rules": [
                    {
                        "ID": "BackupReplication",
                        "Priority": 1,
                        "Status": "Enabled",
                        "Filter": {},
                        "DeleteMarkerReplication": {"Status": "Enabled"},
                        "Destination": {
                            "Bucket": f"arn:aws:s3:::{backup_bucket}",
                            "ReplicationTime": {
                                "Status": "Enabled",
                                "Time": {"Minutes": 15},
                            },
                            "Metrics": {
                                "Status": "Enabled",
                                "EventThreshold": {"Minutes": 15},
                            },
                            "StorageClass": "STANDARD_IA",
                        },
                    }
                ],
            }

            self.s3_client.put_bucket_replication(
                Bucket=self.config["bucket_name"],
                ReplicationConfiguration=replication_config,
            )

            logger.info(
                f"Set up backup replication to {backup_bucket} in {backup_region}"
            )
            return True

        except (ClientError, ValueError) as e:
            logger.error(f"Failed to set up backup replication: {e}")
            return False
