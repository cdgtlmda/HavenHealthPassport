# S3 Module

This module creates and configures S3 buckets for the Haven Health Passport application with comprehensive security settings.

## Features

- **KMS Encryption**: All buckets use KMS encryption for data at rest
- **Versioning**: Enabled for data protection and recovery
- **Access Logging**: All access is logged to a separate bucket
- **Public Access Block**: Prevents any public access to buckets
- **Lifecycle Rules**: Automatic archival to reduce costs
- **Object Lock**: Compliance mode retention for HIPAA requirements
- **SSL/TLS Only**: Enforces encrypted connections
- **Bucket Policies**: Additional security policies

## Usage

```hcl
module "s3" {
  source = "./modules/s3"

  environment    = "production"
  kms_key_id    = module.kms.s3_key_id
  kms_key_arn   = module.kms.s3_key_arn
  retention_days = 2555  # 7 years for HIPAA

  tags = {
    Project     = "Haven Health Passport"
    Environment = "production"
  }
}
```

## Security Features

1. **Encryption at Rest**: Uses AWS KMS customer-managed keys
2. **Encryption in Transit**: Enforces SSL/TLS connections
3. **Access Control**: No public access allowed
4. **Audit Trail**: Comprehensive access logging
5. **Data Retention**: Compliance mode object lock
6. **Versioning**: Protects against accidental deletion

## Compliance

- **HIPAA**: 7-year retention, encryption, access logging
- **GDPR**: Data protection and audit trails
- **ISO 27001**: Security controls and monitoring
