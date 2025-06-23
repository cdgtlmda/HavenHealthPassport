"""
Backup Encryption Module for Haven Health Passport.

This module provides encryption functionality for database and file backups
to ensure data security even in backup storage.
"""

import gzip
import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime
from subprocess import run
from typing import Any, Dict, cast

import boto3
from botocore.exceptions import BotoCoreError as BotoCore
from botocore.exceptions import ClientError
from cryptography.exceptions import InvalidTag as InvalidToken

from .envelope_encryption import EnvelopeEncryption

logger = logging.getLogger(__name__)


class BackupEncryption:
    """Handles encryption of backup files with compression and integrity verification."""

    def __init__(self, kms_key_id: str, region: str = "us-east-1"):
        """
        Initialize backup encryption handler.

        Args:
            kms_key_id: KMS key ID for backup encryption
            region: AWS region
        """
        self.envelope_encryption = EnvelopeEncryption(kms_key_id, region)
        self.s3_client = boto3.client("s3", region_name=region)

    def encrypt_backup_file(
        self, input_file: str, output_file: str, compress: bool = True
    ) -> Dict[str, Any]:
        """
        Encrypt a backup file with optional compression.

        Args:
            input_file: Path to the backup file
            output_file: Path for the encrypted output
            compress: Whether to compress before encryption

        Returns:
            Metadata about the encrypted backup
        """
        metadata = {
            "original_file": input_file,
            "encrypted_file": output_file,
            "timestamp": datetime.utcnow().isoformat(),
            "compressed": compress,
        }

        try:
            # Read the backup file
            with open(input_file, "rb") as f:
                data = f.read()

            # Calculate checksum of original data
            original_checksum = hashlib.sha256(data).hexdigest()
            metadata["original_checksum"] = original_checksum
            metadata["original_size"] = len(data)

            # Compress if requested
            if compress:
                data = gzip.compress(data, compresslevel=9)
                metadata["compressed_size"] = len(data)
                logger.info(
                    "Compressed backup from %d to %d bytes",
                    metadata["original_size"],
                    metadata["compressed_size"],
                )

            # Create encryption context
            encryption_context: Dict[str, str] = {
                "backup_type": "file",
                "original_file": os.path.basename(input_file),
                "timestamp": str(metadata["timestamp"]),
            }

            # Encrypt the data
            encrypted_envelope = self.envelope_encryption.encrypt_data(
                data, encryption_context
            )

            # Add metadata to envelope
            encrypted_envelope["backup_metadata"] = metadata

            # Write encrypted file
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(encrypted_envelope, f)

            logger.info("Encrypted backup saved to %s", output_file)
            return metadata

        except (
            InvalidToken,
            OSError,
            TypeError,
            ValueError,
        ) as e:
            logger.error("Error encrypting backup: %s", e)
            raise

    def decrypt_backup_file(
        self, encrypted_file: str, output_file: str
    ) -> Dict[str, Any]:
        """
        Decrypt an encrypted backup file.

        Args:
            encrypted_file: Path to the encrypted backup
            output_file: Path for the decrypted output

        Returns:
            Metadata about the backup
        """
        try:
            # Read encrypted file
            with open(encrypted_file, "r", encoding="utf-8") as f:
                encrypted_envelope = json.load(f)

            # Extract metadata
            metadata = encrypted_envelope.get("backup_metadata", {})

            # Decrypt the data
            decrypted_data = self.envelope_encryption.decrypt_data(encrypted_envelope)

            # Decompress if needed
            if metadata.get("compressed", False):
                decrypted_data = gzip.decompress(decrypted_data)
                logger.info("Decompressed backup to %d bytes", len(decrypted_data))

            # Verify checksum
            checksum = hashlib.sha256(decrypted_data).hexdigest()
            if checksum != metadata.get("original_checksum"):
                raise ValueError("Checksum verification failed")

            # Write decrypted file
            with open(output_file, "wb") as f:
                f.write(decrypted_data)

            logger.info("Decrypted backup saved to %s", output_file)
            return cast(Dict[str, Any], metadata)

        except (
            InvalidToken,
            OSError,
            TypeError,
            ValueError,
        ) as e:
            logger.error("Error decrypting backup: %s", e)
            raise

    def encrypt_database_backup(
        self, connection_string: str, backup_bucket: str, backup_key: str
    ) -> str:
        """
        Create and encrypt a database backup directly to S3.

        Args:
            connection_string: Database connection string
            backup_bucket: S3 bucket for backup storage
            backup_key: S3 key (path) for the backup

        Returns:
            S3 URL of the encrypted backup
        """
        try:
            # Create temporary file for backup
            with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
                temp_backup = tmp.name

            # Run pg_dump for PostgreSQL backup
            result = run(
                ["pg_dump", connection_string, "-f", temp_backup],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                raise ValueError(f"Database backup failed: {result.stderr}")

            # Encrypt the backup
            encrypted_file = f"{temp_backup}.enc"
            metadata = self.encrypt_backup_file(temp_backup, encrypted_file)

            # Upload to S3 with server-side encryption
            with open(encrypted_file, "rb") as f:
                self.s3_client.put_object(
                    Bucket=backup_bucket,
                    Key=backup_key,
                    Body=f,
                    ServerSideEncryption="aws:kms",
                    Metadata={
                        "backup-timestamp": metadata["timestamp"],
                        "original-checksum": metadata["original_checksum"],
                    },
                )

            # Clean up temporary files
            os.unlink(temp_backup)
            os.unlink(encrypted_file)

            s3_url = f"s3://{backup_bucket}/{backup_key}"
            logger.info("Database backup uploaded to %s", s3_url)
            return s3_url

        except (
            BotoCore,
            ClientError,
            OSError,
            ValueError,
        ) as e:
            logger.error("Error creating database backup: %s", e)
            raise
