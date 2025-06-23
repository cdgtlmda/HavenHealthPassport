# Backup Encryption Implementation

## Overview

The Haven Health Passport backup encryption system ensures all backups are encrypted at rest and in transit, meeting HIPAA compliance requirements for data protection.

## Features

- **Envelope Encryption**: All backups use envelope encryption with AWS KMS
- **Compression**: Optional compression before encryption to reduce storage costs
- **Integrity Verification**: SHA-256 checksums ensure backup integrity
- **Automated Policies**: Predefined backup policies for different data types
- **S3 Integration**: Direct upload to encrypted S3 buckets
- **AWS Backup Integration**: Additional protection layer using AWS Backup

## Backup Policies

| Data Type | Frequency | Retention | Encryption |
|-----------|-----------|-----------|------------|
| Patient Data | Daily | 7 years | Required |
| Medical Records | Hourly | 7 years | Required |
| Audit Logs | Daily | 1 year | Required |
| System Config | Weekly | 90 days | Required |
| Blockchain Data | Daily | Permanent | Required |

## Usage Examples

### File Backup Encryption

```python
from src.security import BackupEncryption

# Initialize backup encryption
backup_enc = BackupEncryption(kms_key_id="your-kms-key-id")

# Encrypt a backup file
metadata = backup_enc.encrypt_backup_file(
    input_file="/path/to/backup.sql",
    output_file="/path/to/backup.sql.enc",
    compress=True
)

# Decrypt a backup file
restored_metadata = backup_enc.decrypt_backup_file(
    encrypted_file="/path/to/backup.sql.enc",
    output_file="/path/to/restored.sql"
)
```
### Database Backup to S3

```python
# Create and encrypt database backup directly to S3
s3_url = backup_enc.encrypt_database_backup(
    connection_string="postgresql://user:pass@host/db",
    backup_bucket="haven-backups",
    backup_key="database/backup-2024-01-15.sql.enc"
)
```

## Infrastructure

The backup infrastructure includes:

1. **Encrypted S3 Bucket**: All backups stored with KMS encryption
2. **AWS Backup Vault**: Additional protection for critical resources
3. **Lifecycle Policies**: Automatic retention management
4. **Access Controls**: Strict IAM policies for backup access

## Security Features

1. **Encryption at Rest**: All backups encrypted with customer-managed KMS keys
2. **Encryption in Transit**: TLS 1.3 for all backup transfers
3. **Key Rotation**: Automatic key rotation for backup encryption keys
4. **Access Logging**: All backup access is logged and monitored
5. **Versioning**: S3 versioning prevents accidental deletion
6. **MFA Delete**: Multi-factor authentication required for backup deletion

## Compliance

- **HIPAA**: 7-year retention for patient data backups
- **GDPR**: Encrypted backups support data portability
- **ISO 27001**: Comprehensive backup and recovery procedures

## Best Practices

1. **Test Restores**: Regularly test backup restoration procedures
2. **Monitor Failures**: Set up alerts for backup job failures
3. **Cross-Region**: Replicate critical backups to another region
4. **Immutability**: Use S3 Object Lock for compliance backups
5. **Documentation**: Maintain detailed backup/restore procedures
