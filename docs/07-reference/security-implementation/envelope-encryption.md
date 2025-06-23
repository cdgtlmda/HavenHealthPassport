# Envelope Encryption Implementation

## Overview

This implementation provides envelope encryption functionality for the Haven Health Passport application. Envelope encryption is a secure method that uses two keys:

1. **Data Encryption Key (DEK)**: A symmetric key used to encrypt the actual data
2. **Key Encryption Key (KEK)**: The AWS KMS key used to encrypt the DEK

## Benefits

- **Performance**: Only the small DEK needs to be sent to KMS for encryption/decryption
- **Security**: Each piece of data can have its own unique DEK
- **Compliance**: Meets HIPAA requirements for encryption at rest
- **Audit Trail**: Encryption context provides traceable audit information

## Usage

### Basic Encryption/Decryption

```python
from src.security import EnvelopeEncryption

# Initialize with your KMS key
kms_key_id = "arn:aws:kms:us-east-1:123456789012:key/your-key-id"
envelope = EnvelopeEncryption(kms_key_id)

# Encrypt data
plaintext = "Sensitive patient information"
encrypted_envelope = envelope.encrypt_string(plaintext)

# Decrypt data
decrypted = envelope.decrypt_string(encrypted_envelope)
```
### Using Encryption Context

```python
# Add encryption context for audit trail
encryption_context = {
    'patient_id': '12345',
    'data_type': 'medical_record',
    'department': 'cardiology'
}

encrypted_envelope = envelope.encrypt_string(
    plaintext,
    encryption_context=encryption_context
)
```

### Secure Patient Data Storage

```python
from src.security import SecureDataStorage

# Initialize secure storage
storage = SecureDataStorage(kms_key_id)

# Store patient data
patient_data = {
    'name': 'John Doe',
    'dob': '1980-01-01',
    'conditions': ['hypertension', 'diabetes'],
    'medications': ['metformin', 'lisinopril']
}

encrypted_data = storage.store_patient_data(
    patient_id='12345',
    data=patient_data,
    data_type='medical_record'
)

# Retrieve patient data
decrypted_data = storage.retrieve_patient_data(encrypted_data)
```

## Security Features

1. **AES-256-CBC Encryption**: Uses strong symmetric encryption for data
2. **AWS KMS Integration**: Leverages AWS's secure key management
3. **Data Integrity**: SHA-256 hash verification ensures data hasn't been tampered
4. **Encryption Context**: Provides cryptographically authenticated audit information
5. **Memory Safety**: Clears plaintext keys from memory after use

## Best Practices

1. **Key Rotation**: Enable automatic key rotation in AWS KMS
2. **Least Privilege**: Grant minimal KMS permissions to applications
3. **Encryption Context**: Always use encryption context for audit trails
4. **Error Handling**: Implement proper error handling for KMS failures
5. **Monitoring**: Set up CloudWatch alarms for unusual KMS usage

## Compliance

This implementation meets the following compliance requirements:

- **HIPAA**: Encryption at rest using FIPS 140-2 validated encryption
- **GDPR**: Strong encryption for personal data protection
- **ISO 27001**: Cryptographic controls for information security
