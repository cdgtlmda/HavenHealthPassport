"""
Demonstration of real AWS service usage in tests - NO MOCKS.

This shows how tests should use real AWS services per medical compliance requirements.
"""

import json
import time
from datetime import datetime

import boto3
import pytest
from botocore.exceptions import ClientError


class TestRealAWSServicesDemo:
    """Demo tests showing real AWS service usage without mocks."""

    def test_real_kms_encryption(self):
        """Test using real AWS KMS for encryption - NO MOCKS."""
        # Skip if AWS credentials not available
        try:
            kms_client = boto3.client("kms", region_name="us-east-1")
            kms_client.list_keys(Limit=1)
        except ClientError as e:
            pytest.skip(f"AWS credentials not configured: {e}")

        # Use real KMS to encrypt data
        plaintext = b"Sensitive patient data - PHI"

        try:
            # Real KMS encryption
            response = kms_client.encrypt(
                KeyId="alias/aws/kms", Plaintext=plaintext  # Default AWS managed key
            )

            ciphertext = response["CiphertextBlob"]

            # Real KMS decryption
            decrypt_response = kms_client.decrypt(CiphertextBlob=ciphertext)
            decrypted = decrypt_response["Plaintext"]

            assert decrypted == plaintext
            print("✓ Real KMS encryption/decryption successful")

        except ClientError as e:
            if "InvalidKeyId" in str(e):
                pytest.skip("KMS key not available")
            raise

    def test_real_dynamodb_operations(self):
        """Test using real DynamoDB - NO MOCKS."""
        # Skip if AWS credentials not available
        try:
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            dynamodb.meta.client.list_tables(Limit=1)
        except ClientError as e:
            pytest.skip(f"AWS credentials not configured: {e}")

        table_name = f"haven-test-{int(time.time())}"

        try:
            # Create real DynamoDB table
            table = dynamodb.create_table(
                TableName=table_name,
                KeySchema=[{"AttributeName": "patient_id", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "patient_id", "AttributeType": "S"}
                ],
                BillingMode="PAY_PER_REQUEST",
                Tags=[
                    {"Key": "Environment", "Value": "test"},
                    {"Key": "Purpose", "Value": "medical-compliance-testing"},
                ],
            )

            # Wait for table to be created
            table.wait_until_exists()

            # Real data operations
            patient_data = {
                "patient_id": "test-patient-123",
                "name": "Test Patient",
                "created_at": datetime.utcnow().isoformat(),
                "encrypted_ssn": "vault:v1:encrypted_data_here",
            }

            # Put item
            table.put_item(Item=patient_data)

            # Get item
            response = table.get_item(Key={"patient_id": "test-patient-123"})

            assert "Item" in response
            assert response["Item"]["name"] == "Test Patient"
            print("✓ Real DynamoDB operations successful")

        finally:
            # Cleanup
            try:
                table.delete()
            except ClientError:
                pass

    def test_real_s3_operations(self):
        """Test using real S3 - NO MOCKS."""
        # Skip if AWS credentials not available
        try:
            s3_client = boto3.client("s3", region_name="us-east-1")
            s3_client.list_buckets()
        except ClientError as e:
            pytest.skip(f"AWS credentials not configured: {e}")

        bucket_name = f"haven-test-{int(time.time())}"

        try:
            # Create real S3 bucket
            if "us-east-1" == "us-east-1":
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": "us-east-1"},
                )

            # Upload encrypted file
            test_data = b"Medical document content"
            s3_client.put_object(
                Bucket=bucket_name,
                Key="patient-docs/test-doc.pdf",
                Body=test_data,
                ServerSideEncryption="AES256",
                Metadata={"patient-id": "test-123", "document-type": "medical-record"},
            )

            # Download and verify
            response = s3_client.get_object(
                Bucket=bucket_name, Key="patient-docs/test-doc.pdf"
            )

            downloaded_data = response["Body"].read()
            assert downloaded_data == test_data
            assert response["ServerSideEncryption"] == "AES256"
            print("✓ Real S3 operations with encryption successful")

        finally:
            # Cleanup
            try:
                # Delete all objects
                objects = s3_client.list_objects_v2(Bucket=bucket_name)
                if "Contents" in objects:
                    for obj in objects["Contents"]:
                        s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])

                # Delete bucket
                s3_client.delete_bucket(Bucket=bucket_name)
            except ClientError:
                pass

    def test_real_cloudwatch_logging(self):
        """Test using real CloudWatch for audit logging - NO MOCKS."""
        # Skip if AWS credentials not available
        try:
            logs_client = boto3.client("logs", region_name="us-east-1")
            logs_client.describe_log_groups(limit=1)
        except ClientError as e:
            pytest.skip(f"AWS credentials not configured: {e}")

        log_group = f"/aws/haven-test/{int(time.time())}"
        log_stream = "audit-stream"

        try:
            # Create real log group
            logs_client.create_log_group(
                logGroupName=log_group,
                tags={"Environment": "test", "Purpose": "hipaa-audit-testing"},
            )

            # Create log stream
            logs_client.create_log_stream(
                logGroupName=log_group, logStreamName=log_stream
            )

            # Log PHI access event
            audit_event = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": "PHI_ACCESS",
                "user_id": "test-provider-123",
                "patient_id": "test-patient-456",
                "action": "VIEW_MEDICAL_RECORD",
                "ip_address": "10.0.0.1",
                "success": True,
            }

            # Put log event
            logs_client.put_log_events(
                logGroupName=log_group,
                logStreamName=log_stream,
                logEvents=[
                    {
                        "timestamp": int(time.time() * 1000),
                        "message": json.dumps(audit_event),
                    }
                ],
            )

            # Wait for log propagation
            time.sleep(2)

            # Query logs
            response = logs_client.filter_log_events(
                logGroupName=log_group, logStreamNames=[log_stream]
            )

            assert len(response["events"]) > 0
            logged_event = json.loads(response["events"][0]["message"])
            assert logged_event["event_type"] == "PHI_ACCESS"
            print("✓ Real CloudWatch audit logging successful")

        finally:
            # Cleanup
            try:
                logs_client.delete_log_group(logGroupName=log_group)
            except ClientError:
                pass

    def test_real_secrets_manager(self):
        """Test using real Secrets Manager - NO MOCKS."""
        # Skip if AWS credentials not available
        try:
            secrets_client = boto3.client("secretsmanager", region_name="us-east-1")
            secrets_client.list_secrets(MaxResults=1)
        except ClientError as e:
            pytest.skip(f"AWS credentials not configured: {e}")

        secret_name = f"haven-test-{int(time.time())}"

        try:
            # Create real secret
            secret_value = {
                "database_url": "postgresql://test:test@localhost/haven",
                "api_key": "test-api-key-12345",
                "encryption_key": "test-encryption-key",
            }

            secrets_client.create_secret(
                Name=secret_name,
                SecretString=json.dumps(secret_value),
                Tags=[
                    {"Key": "Environment", "Value": "test"},
                    {"Key": "Purpose", "Value": "medical-compliance"},
                ],
            )

            # Retrieve secret
            response = secrets_client.get_secret_value(SecretId=secret_name)
            retrieved_value = json.loads(response["SecretString"])

            assert retrieved_value == secret_value
            print("✓ Real Secrets Manager operations successful")

        finally:
            # Cleanup
            try:
                secrets_client.delete_secret(
                    SecretId=secret_name, ForceDeleteWithoutRecovery=True
                )
            except ClientError:
                pass


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_aws_real_services_demo.py -v
    pytest.main([__file__, "-v"])
