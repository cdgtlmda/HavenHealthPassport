# Column-Level Encryption Implementation

## Overview

Column-level encryption provides field-specific encryption for sensitive healthcare data in the Haven Health Passport database. This implementation ensures HIPAA compliance while maintaining searchability for certain fields.

## Encryption Types

### 1. Deterministic Encryption (Searchable)
- Used for fields that need to be searchable (SSN, MRN, email)
- Same input always produces same ciphertext
- Allows database indexing and exact match queries

### 2. Randomized Encryption (Non-searchable)
- Used for highly sensitive fields (names, addresses, medical data)
- Same input produces different ciphertext each time
- Maximum security but no searching capability

### 3. Field Classifications

| Sensitivity Level | Encryption Type | Use Case |
|-------------------|-----------------|----------|
| PUBLIC | None | IDs, timestamps |
| PROTECTED | Randomized | Semi-sensitive data |
| SENSITIVE | Randomized | PII, medical records |
| SEARCHABLE_SENSITIVE | Deterministic | Searchable PII |

## Usage Examples

### Basic Column Encryption

```python
from src.security import ColumnEncryption

# Initialize encryptor
encryptor = ColumnEncryption(
    kms_key_id="your-kms-key-id",
    table_name="patients"
)

# Encrypt a value
encrypted_ssn = encryptor.encrypt_value(
    value="123-45-6789",
    column_name="ssn",
    deterministic=True  # For searching
)
```
### Healthcare Field Encryption

```python
from src.security import HealthcareFieldEncryption

# Initialize healthcare encryptor
healthcare_enc = HealthcareFieldEncryption(
    kms_key_id="your-kms-key-id"
)

# Encrypt a patient record
patient_data = {
    'ssn': '123-45-6789',
    'first_name': 'John',
    'last_name': 'Doe',
    'email': 'john.doe@example.com',
    'blood_type': 'O+',
    'patient_id': 12345
}

encrypted_data = healthcare_enc.encrypt_row('patients', patient_data)

# Decrypt the record
decrypted_data = healthcare_enc.decrypt_row('patients', encrypted_data)
```

### SQLAlchemy Integration

```python
from sqlalchemy import create_engine
from src.security.models_example import Patient

# Create a patient record
patient = Patient(
    ssn='123-45-6789',  # Automatically encrypted
    first_name='Jane',   # Automatically encrypted
    last_name='Smith',   # Automatically encrypted
    email='jane@example.com',  # Automatically encrypted
    blood_type='A+'      # Automatically encrypted
)

# Save to database
session.add(patient)
session.commit()

# Query by encrypted field
found_patient = session.query(Patient).filter_by(
    ssn='123-45-6789'  # Automatically encrypted for comparison
).first()
```
## Database Schema

The column encryption implementation includes:

1. **Encryption Keys Table**: Stores encrypted data keys for each column
2. **Audit Table**: Tracks all encryption operations
3. **Key Rotation Function**: Supports periodic key rotation

## Security Considerations

1. **Key Management**: All data keys are encrypted with AWS KMS
2. **Audit Trail**: All encryption operations are logged
3. **Access Control**: Column-level permissions can be implemented
4. **Key Rotation**: Support for periodic key rotation without data loss
5. **Performance**: Deterministic encryption allows indexing for searchable fields

## Compliance

- **HIPAA**: All PII and PHI fields are encrypted
- **GDPR**: Personal data is protected with strong encryption
- **Data Residency**: Keys can be region-specific for compliance
