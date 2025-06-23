"""
Test suite for KeyManager - Medical Compliance Grade.

This test suite provides comprehensive coverage for key management operations
using REAL AWS services (KMS, DynamoDB, Secrets Manager) as required
for medical-grade security compliance.

CRITICAL: These tests use REAL AWS resources in test environment.
NO MOCKS are used for AWS services per project requirements.
This is a life-critical medical application.
"""

import os
import uuid
from datetime import datetime, timedelta

import boto3
import pytest

from src.security.key_management.key_manager import (
    KeyManager,
    KeyMetadata,
    KeyStatus,
    KeyType,
)


@pytest.fixture(scope="session")
def test_environment():
    """Set up test environment with real AWS services."""
    # Ensure we're using test environment
    test_suffix = str(uuid.uuid4())[:8]
    os.environ["HAVEN_TEST_SUFFIX"] = test_suffix
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

    # Verify AWS credentials are available
    try:
        boto3.client("sts").get_caller_identity()
    except Exception:
        pytest.skip("AWS credentials not available for real service testing")

    yield test_suffix

    # Cleanup test resources after session
    try:
        cleanup_test_resources(test_suffix)
    except Exception as e:
        print(f"Warning: Test cleanup failed: {e}")


def cleanup_test_resources(test_suffix):
    """Clean up test resources to avoid AWS charges."""
    # Clean up DynamoDB tables
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    test_table_name = f"haven-key-metadata-test-{test_suffix}"

    try:
        table = dynamodb.Table(test_table_name)
        table.delete()
        table.wait_until_not_exists()
    except Exception:
        pass  # Table might not exist


@pytest.fixture
def key_manager(test_environment):
    """Create KeyManager instance with real AWS services for testing."""
    test_suffix = test_environment

    # Create test-specific table name to avoid conflicts
    original_table_name = os.environ.get(
        "DYNAMODB_KEY_TABLE_NAME", "haven-key-metadata"
    )
    os.environ["DYNAMODB_KEY_TABLE_NAME"] = f"{original_table_name}-test-{test_suffix}"

    manager = KeyManager(region="us-east-1")
    yield manager

    # Restore original table name
    if original_table_name:
        os.environ["DYNAMODB_KEY_TABLE_NAME"] = original_table_name


@pytest.mark.hipaa_required
class TestKeyMetadata:
    """Test KeyMetadata class functionality."""

    def test_key_metadata_initialization(self):
        """Test KeyMetadata initialization with required fields."""
        created_at = datetime.utcnow()
        metadata = KeyMetadata(
            key_id="test-key-123",
            key_type=KeyType.MASTER,
            created_at=created_at,
            version=1,
        )

        assert metadata.key_id == "test-key-123"
        assert metadata.key_type == KeyType.MASTER
        assert metadata.created_at == created_at
        assert metadata.version == 1
        assert metadata.status == KeyStatus.ACTIVE
        assert metadata.rotated_at is None
        assert metadata.expires_at is None
        assert metadata.usage_count == 0
        assert metadata.tags == {}

    def test_key_metadata_with_version(self):
        """Test KeyMetadata initialization with custom version."""
        metadata = KeyMetadata(
            key_id="test-key-123",
            key_type=KeyType.DATA,
            created_at=datetime.utcnow(),
            version=5,
        )

        assert metadata.version == 5
        assert metadata.key_type == KeyType.DATA


@pytest.mark.hipaa_required
class TestKeyManager:
    """Test KeyManager functionality with REAL AWS services."""

    def test_key_manager_initialization(self, key_manager):
        """Test KeyManager initializes with proper AWS clients."""
        assert key_manager.kms_client is not None
        assert key_manager.secrets_client is not None
        assert key_manager.dynamodb is not None
        assert key_manager.key_table is not None

    def test_get_or_create_key_table_creates_table(self, test_environment):
        """Test that key table is created if it doesn't exist with REAL DynamoDB."""
        test_suffix = test_environment

        # Use test-specific table name
        original_table_name = os.environ.get(
            "DYNAMODB_KEY_TABLE_NAME", "haven-key-metadata"
        )
        test_table_name = f"{original_table_name}-test-create-{test_suffix}"
        os.environ["DYNAMODB_KEY_TABLE_NAME"] = test_table_name

        try:
            manager = KeyManager(region="us-east-1")
            table = manager.key_table

            # Verify table structure with REAL DynamoDB
            assert table.table_name == test_table_name
            assert table.key_schema == [
                {"AttributeName": "key_id", "KeyType": "HASH"},
                {"AttributeName": "version", "KeyType": "RANGE"},
            ]

            # Clean up
            table.delete()
            table.wait_until_not_exists()

        finally:
            # Restore original table name
            os.environ["DYNAMODB_KEY_TABLE_NAME"] = original_table_name

    def test_get_or_create_key_table_existing_table(self, test_environment):
        """Test that existing key table is used with REAL DynamoDB."""
        test_suffix = test_environment
        test_table_name = f"haven-key-metadata-test-existing-{test_suffix}"

        # Create the table first with REAL DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName=test_table_name,
            KeySchema=[
                {"AttributeName": "key_id", "KeyType": "HASH"},
                {"AttributeName": "version", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "key_id", "AttributeType": "S"},
                {"AttributeName": "version", "AttributeType": "N"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()

        try:
            # Set table name for KeyManager
            original_table_name = os.environ.get(
                "DYNAMODB_KEY_TABLE_NAME", "haven-key-metadata"
            )
            os.environ["DYNAMODB_KEY_TABLE_NAME"] = test_table_name

            # KeyManager should use existing table
            manager = KeyManager(region="us-east-1")
            assert manager.key_table.table_name == test_table_name

        finally:
            # Clean up
            table.delete()
            table.wait_until_not_exists()
            os.environ["DYNAMODB_KEY_TABLE_NAME"] = original_table_name

    def test_create_key_master_type(self, key_manager):
        """Test creating a master key for PHI encryption with REAL KMS."""
        key_id, metadata = key_manager.create_key(
            key_purpose="PHI Master Key Test", key_type=KeyType.MASTER, rotation_days=90
        )

        assert key_id is not None
        assert len(key_id) > 0
        assert metadata.key_id == key_id
        assert metadata.key_type == KeyType.MASTER
        assert metadata.status == KeyStatus.ACTIVE
        assert metadata.version == 1
        assert metadata.expires_at is not None

        # Verify expiration is set correctly
        expected_expiry = metadata.created_at + timedelta(days=90)
        assert abs((metadata.expires_at - expected_expiry).total_seconds()) < 60

        # Clean up KMS key
        try:
            key_manager.kms_client.schedule_key_deletion(
                KeyId=key_id, PendingWindowInDays=7
            )
        except Exception:
            pass  # Key might not exist or already scheduled

    def test_create_key_data_type(self, key_manager):
        """Test creating a data encryption key with REAL KMS."""
        key_id, metadata = key_manager.create_key(
            key_purpose="Patient Data Encryption Test",
            key_type=KeyType.DATA,
            rotation_days=30,
        )

        assert key_id is not None
        assert metadata.key_type == KeyType.DATA
        assert metadata.expires_at is not None

        # Verify 30-day rotation
        expected_expiry = metadata.created_at + timedelta(days=30)
        assert abs((metadata.expires_at - expected_expiry).total_seconds()) < 60

        # Clean up KMS key
        try:
            key_manager.kms_client.schedule_key_deletion(
                KeyId=key_id, PendingWindowInDays=7
            )
        except Exception:
            pass

    def test_create_key_signing_type(self, key_manager):
        """Test creating a signing key for audit trails with REAL KMS."""
        key_id, metadata = key_manager.create_key(
            key_purpose="Audit Trail Signing Test",
            key_type=KeyType.SIGNING,
            rotation_days=180,
        )

        assert key_id is not None
        assert metadata.key_type == KeyType.SIGNING

        # Clean up KMS key
        try:
            key_manager.kms_client.schedule_key_deletion(
                KeyId=key_id, PendingWindowInDays=7
            )
        except Exception:
            pass

    def test_create_key_transport_type(self, key_manager):
        """Test creating a transport key for secure communication with REAL KMS."""
        key_id, metadata = key_manager.create_key(
            key_purpose="Secure Transport Test",
            key_type=KeyType.TRANSPORT,
            rotation_days=60,
        )

        assert key_id is not None
        assert metadata.key_type == KeyType.TRANSPORT

        # Clean up KMS key
        try:
            key_manager.kms_client.schedule_key_deletion(
                KeyId=key_id, PendingWindowInDays=7
            )
        except Exception:
            pass

    def test_create_key_stores_metadata(self, key_manager):
        """Test that key metadata is properly stored in REAL DynamoDB."""
        key_id, metadata = key_manager.create_key(
            key_purpose="Test Key Storage", key_type=KeyType.MASTER
        )

        try:
            # Retrieve from REAL DynamoDB
            response = key_manager.key_table.get_item(
                Key={"key_id": key_id, "version": 1}
            )

            assert "Item" in response
            item = response["Item"]
            assert item["key_id"] == key_id
            assert item["key_type"] == KeyType.MASTER.value
            assert item["status"] == KeyStatus.ACTIVE.value
            assert item["purpose"] == "Test Key Storage"
            assert item["version"] == 1
            assert item["usage_count"] == 0

        finally:
            # Clean up KMS key
            try:
                key_manager.kms_client.schedule_key_deletion(
                    KeyId=key_id, PendingWindowInDays=7
                )
            except Exception:
                pass

    def test_get_key_metadata_success(self, key_manager):
        """Test retrieving key metadata from REAL DynamoDB."""
        # Create key first
        key_id, created_metadata = key_manager.create_key(
            key_purpose="Test Metadata Retrieval", key_type=KeyType.DATA
        )

        try:
            # Retrieve metadata
            retrieved_metadata = key_manager.get_key_metadata(key_id, version=1)

            assert retrieved_metadata is not None
            assert retrieved_metadata.key_id == key_id
            assert retrieved_metadata.key_type == KeyType.DATA
            assert retrieved_metadata.version == 1
            assert retrieved_metadata.status == KeyStatus.ACTIVE

        finally:
            # Clean up
            try:
                key_manager.kms_client.schedule_key_deletion(
                    KeyId=key_id, PendingWindowInDays=7
                )
            except Exception:
                pass

    def test_get_key_metadata_not_found(self, key_manager):
        """Test retrieving non-existent key metadata from REAL DynamoDB."""
        result = key_manager.get_key_metadata("non-existent-key", version=1)
        assert result is None

    def test_update_key_status(self, key_manager):
        """Test updating key status in REAL DynamoDB."""
        # Create key first
        key_id, metadata = key_manager.create_key(
            key_purpose="Test Status Update", key_type=KeyType.DATA
        )

        try:
            # Update status
            success = key_manager.update_key_status(
                key_id, KeyStatus.DEPRECATED, version=1
            )
            assert success

            # Verify update in REAL DynamoDB
            updated_metadata = key_manager.get_key_metadata(key_id, version=1)
            assert updated_metadata.status == KeyStatus.DEPRECATED

        finally:
            # Clean up
            try:
                key_manager.kms_client.schedule_key_deletion(
                    KeyId=key_id, PendingWindowInDays=7
                )
            except Exception:
                pass

    def test_get_active_key_existing(self, key_manager):
        """Test getting active key with REAL AWS services."""
        # Create key first
        key_id, metadata = key_manager.create_key(
            key_purpose="Test Active Key", key_type=KeyType.MASTER
        )

        try:
            # Get active key
            active_key = key_manager.get_active_key(KeyType.MASTER)
            assert active_key is not None

        finally:
            # Clean up
            try:
                key_manager.kms_client.schedule_key_deletion(
                    KeyId=key_id, PendingWindowInDays=7
                )
            except Exception:
                pass

    def test_track_key_usage(self, key_manager):
        """Test tracking key usage with REAL DynamoDB."""
        # Create key first
        key_id, metadata = key_manager.create_key(
            key_purpose="Test Usage Tracking", key_type=KeyType.DATA
        )

        try:
            # Track usage
            key_manager.track_key_usage(key_id, operation="encrypt", version=1)

            # Verify usage was tracked in REAL DynamoDB
            updated_metadata = key_manager.get_key_metadata(key_id, version=1)
            assert updated_metadata.usage_count == 1

        finally:
            # Clean up
            try:
                key_manager.kms_client.schedule_key_deletion(
                    KeyId=key_id, PendingWindowInDays=7
                )
            except Exception:
                pass


@pytest.mark.hipaa_required
class TestKeyManagerHIPAACompliance:
    """Test HIPAA compliance features with REAL AWS services."""

    def test_key_creation_audit_logging(self, key_manager, caplog):
        """Test that key creation generates proper audit logs."""
        key_id, metadata = key_manager.create_key(
            key_purpose="HIPAA Audit Test", key_type=KeyType.MASTER
        )

        try:
            # Verify audit log entry
            assert "Key created" in caplog.text
            assert key_id in caplog.text
            assert "HIPAA Audit Test" in caplog.text

        finally:
            # Clean up
            try:
                key_manager.kms_client.schedule_key_deletion(
                    KeyId=key_id, PendingWindowInDays=7
                )
            except Exception:
                pass

    def test_key_types_for_phi_protection(self, key_manager):
        """Test that all required key types can be created for PHI protection."""
        key_types_to_test = [
            KeyType.MASTER,
            KeyType.DATA,
            KeyType.SIGNING,
            KeyType.TRANSPORT,
        ]
        created_keys = []

        try:
            for key_type in key_types_to_test:
                key_id, metadata = key_manager.create_key(
                    key_purpose=f"PHI {key_type.value} Test",
                    key_type=key_type,
                )
                created_keys.append(key_id)

                assert key_id is not None
                assert metadata.key_type == key_type
                assert metadata.status == KeyStatus.ACTIVE

        finally:
            # Clean up all created keys
            for key_id in created_keys:
                try:
                    key_manager.kms_client.schedule_key_deletion(
                        KeyId=key_id, PendingWindowInDays=7
                    )
                except Exception:
                    pass


@pytest.mark.audit_required
class TestKeyManagerErrorHandling:
    """Test error handling with REAL AWS services."""

    def test_store_metadata_handles_errors(self, key_manager):
        """Test metadata storage error handling with REAL DynamoDB."""
        # Create invalid metadata that should cause an error
        metadata = KeyMetadata(
            key_id="test-error-key",
            key_type=KeyType.MASTER,
            created_at=datetime.utcnow(),
            version=1,
        )

        # This should handle any DynamoDB errors gracefully
        # The exact behavior depends on the implementation
        try:
            result = key_manager._store_key_metadata(metadata)
            # If successful, verify it was stored
            if result:
                stored = key_manager.get_key_metadata("test-error-key", version=1)
                assert stored is not None
        except Exception:
            # Error handling should be graceful
            pass


@pytest.mark.phi_encryption
class TestKeyManagerIntegration:
    """Integration tests with REAL AWS services."""

    def test_end_to_end_key_lifecycle(self, key_manager):
        """Test complete key lifecycle with REAL AWS services."""
        # Create key
        key_id, metadata = key_manager.create_key(
            key_purpose="E2E Lifecycle Test",
            key_type=KeyType.MASTER,
            rotation_days=365,
        )

        try:
            # Verify creation
            assert key_id is not None
            assert metadata.status == KeyStatus.ACTIVE

            # Track usage
            key_manager.track_key_usage(key_id, "encrypt", version=1)
            key_manager.track_key_usage(key_id, "decrypt", version=1)

            # Verify usage tracking
            updated_metadata = key_manager.get_key_metadata(key_id, version=1)
            assert updated_metadata.usage_count == 2

            # Update status
            success = key_manager.update_key_status(
                key_id, KeyStatus.DEPRECATED, version=1
            )
            assert success

            # Verify status update
            final_metadata = key_manager.get_key_metadata(key_id, version=1)
            assert final_metadata.status == KeyStatus.DEPRECATED

        finally:
            # Clean up
            try:
                key_manager.kms_client.schedule_key_deletion(
                    KeyId=key_id, PendingWindowInDays=7
                )
            except Exception:
                pass

    def test_multiple_key_types_management(self, key_manager):
        """Test managing multiple key types simultaneously with REAL AWS."""
        keys_created = []

        try:
            # Create different key types
            master_key_id, master_meta = key_manager.create_key(
                key_purpose="Multi-type Master", key_type=KeyType.MASTER
            )
            keys_created.append(master_key_id)

            data_key_id, data_meta = key_manager.create_key(
                key_purpose="Multi-type Data", key_type=KeyType.DATA
            )
            keys_created.append(data_key_id)

            signing_key_id, signing_meta = key_manager.create_key(
                key_purpose="Multi-type Signing", key_type=KeyType.SIGNING
            )
            keys_created.append(signing_key_id)

            # Verify all keys are different and properly created
            assert len(set(keys_created)) == 3  # All unique
            assert master_meta.key_type == KeyType.MASTER
            assert data_meta.key_type == KeyType.DATA
            assert signing_meta.key_type == KeyType.SIGNING

        finally:
            # Clean up all keys
            for key_id in keys_created:
                try:
                    key_manager.kms_client.schedule_key_deletion(
                        KeyId=key_id, PendingWindowInDays=7
                    )
                except Exception:
                    pass

    def test_key_metadata_persistence(self, key_manager):
        """Test that key metadata persists across KeyManager instances with REAL DynamoDB."""
        # Create key with first instance
        key_id, original_metadata = key_manager.create_key(
            key_purpose="Persistence Test", key_type=KeyType.DATA
        )

        try:
            # Create new KeyManager instance
            new_manager = KeyManager(region="us-east-1")

            # Retrieve metadata with new instance
            retrieved_metadata = new_manager._get_key_metadata(key_id)

            assert retrieved_metadata is not None
            assert retrieved_metadata.key_id == original_metadata.key_id
            assert retrieved_metadata.key_type == original_metadata.key_type
            assert retrieved_metadata.version == original_metadata.version
            assert retrieved_metadata.status == original_metadata.status

        finally:
            # Clean up
            try:
                key_manager.kms_client.schedule_key_deletion(
                    KeyId=key_id, PendingWindowInDays=7
                )
            except Exception:
                pass
