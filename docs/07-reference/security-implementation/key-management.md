# Key Management System

## Overview

The Haven Health Passport Key Management System provides centralized, secure management of encryption keys with automatic rotation, versioning, and comprehensive auditing.

## Architecture

### Components

1. **Key Manager**: Core key lifecycle management
2. **Key Vault**: Secure storage using AWS Secrets Manager
3. **Rotation Scheduler**: Automatic key rotation based on policies
4. **Metadata Store**: DynamoDB table for key metadata and versioning

### Key Types

- **Master Keys**: Top-level encryption keys
- **Data Keys**: Keys for encrypting data at rest
- **Signing Keys**: Keys for digital signatures
- **Transport Keys**: Keys for data in transit

## Usage

### Creating Keys

```python
from src.security.key_management import KeyManager, KeyType

# Initialize key manager
km = KeyManager()

# Create a new data encryption key
key_id, metadata = km.create_key(
    key_purpose="Patient data encryption",
    key_type=KeyType.DATA,
    rotation_days=90
)
```

### Key Rotation

```python
# Manual rotation
new_key_id, new_metadata = km.rotate_key(old_key_id)

# Automatic rotation
scheduler = KeyRotationScheduler(km)
scheduler.schedule_rotation_check("rate(1 day)")
```
### Secure Key Storage

```python
from src.security.key_management import KeyVault

vault = KeyVault()

# Store a key
arn = vault.store_key(
    key_name="api-signing-key",
    key_value=generated_key,
    key_metadata={
        'algorithm': 'RSA-2048',
        'purpose': 'API request signing',
        'created_by': 'system'
    },
    kms_key_id=master_key_id
)

# Retrieve a key
key_value, metadata = vault.retrieve_key("api-signing-key")
```

## Key Lifecycle

1. **Creation**: Keys are created with specific purposes and rotation schedules
2. **Active**: Keys in use for encryption/decryption operations
3. **Rotating**: Transition period where both old and new keys are valid
4. **Deprecated**: Old keys that can only decrypt, not encrypt
5. **Expired**: Keys past their lifetime, scheduled for deletion
6. **Compromised**: Keys marked as compromised, immediately revoked

## Security Features

- **Automatic Rotation**: Keys rotate based on configured schedules
- **Version Control**: All key versions are tracked and audited
- **Access Control**: IAM policies control who can use which keys
- **Audit Trail**: All key operations are logged to CloudTrail
- **Secure Storage**: Keys stored encrypted in AWS Secrets Manager

## Best Practices

1. **Rotation Schedule**: Rotate keys every 90 days for compliance
2. **Key Separation**: Use different keys for different data types
3. **Access Control**: Implement least privilege for key access
4. **Monitoring**: Set up alerts for unusual key usage patterns
5. **Backup**: Ensure key metadata is backed up regularly
