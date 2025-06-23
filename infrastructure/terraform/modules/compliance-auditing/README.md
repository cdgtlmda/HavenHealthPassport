# Compliance and Auditing Module

This Terraform module implements comprehensive compliance and auditing capabilities for the Haven Health Passport application.

## Features

- **Audit Trail**: Immutable audit logs with tamper protection
- **Compliance Monitoring**: AWS Config rules for continuous compliance
- **Automated Reporting**: Scheduled compliance and audit reports
- **Drift Detection**: Automated detection of configuration drift
- **Log Analysis**: Real-time analysis of audit events
- **Compliance Archival**: Long-term retention of compliance data

## Components

1. **Audit Trail Implementation**
   - DynamoDB table with streams
   - Tamper-proof storage
   - Hash validation
   - Point-in-time recovery

2. **Compliance Automation**
   - AWS Config recorder
   - Config rules (HIPAA, encryption, MFA)
   - Automated compliance checks
   - Drift detection

3. **Audit Reports**
   - Scheduled report generation
   - Multiple output formats
   - Stakeholder distribution
   - Trend analysis

4. **Tamper Protection**
   - Object Lock on S3
   - Hash validation
   - Immutable archives

## Usage

```hcl
module "compliance_auditing" {
  source = "./modules/compliance-auditing"

  project_name        = "haven-health-passport"
  kms_key_arn        = module.kms.key_arn
  sns_alert_topic_arn = module.monitoring.sns_topic_arn
  audit_hash_secret  = var.audit_hash_secret
}
```
