# AWS KMS Module

This module creates and configures AWS Key Management Service (KMS) keys for the Haven Health Passport application.

## Overview

The module creates separate KMS keys for different purposes:
- **Main Key**: General purpose encryption
- **S3 Key**: S3 bucket encryption
- **RDS Key**: Database encryption
- **Secrets Key**: AWS Secrets Manager encryption
- **App Key**: Application-level encryption

## Features

- Automatic key rotation enabled
- CloudWatch monitoring and alarms
- IAM policy for key usage
- Key policies with proper access controls
- Multi-region support (optional)
- CloudWatch Logs encryption

## Usage

```hcl
module "kms" {
  source = "./modules/kms"

  environment          = "production"
  project_name        = "haven-health-passport"
  deletion_window_days = 30
  multi_region        = true

  admin_arns = [
    "arn:aws:iam::123456789012:role/AdminRole"
  ]

  user_arns = [
    "arn:aws:iam::123456789012:role/ApplicationRole"
  ]

  alarm_actions = [
    "arn:aws:sns:us-east-1:123456789012:security-alerts"
  ]
}
```
## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| project_name | Name of the project | string | "haven-health-passport" | no |
| environment | Environment name | string | n/a | yes |
| deletion_window_days | KMS key deletion window in days | number | 30 | no |
| multi_region | Whether to create multi-region KMS keys | bool | false | no |
| admin_arns | List of ARNs that can administer the KMS keys | list(string) | [] | no |
| user_arns | List of ARNs that can use the KMS keys | list(string) | [] | no |
| log_retention_days | CloudWatch log retention in days | number | 90 | no |
| kms_usage_threshold | Threshold for KMS usage alarm | number | 1000 | no |
| alarm_actions | List of ARNs to notify when alarm triggers | list(string) | [] | no |
| tags | Additional tags to apply to all resources | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| main_key_id | ID of the main KMS key |
| main_key_arn | ARN of the main KMS key |
| s3_key_id | ID of the S3 KMS key |
| s3_key_arn | ARN of the S3 KMS key |
| rds_key_id | ID of the RDS KMS key |
| rds_key_arn | ARN of the RDS KMS key |
| secrets_key_id | ID of the Secrets Manager KMS key |
| secrets_key_arn | ARN of the Secrets Manager KMS key |
| app_key_id | ID of the application KMS key |
| app_key_arn | ARN of the application KMS key |
| kms_usage_policy_arn | ARN of the IAM policy for KMS usage |
| all_key_arns | List of all KMS key ARNs |

## Security Considerations

1. **Key Rotation**: All keys have automatic rotation enabled (yearly)
2. **Key Policies**: Restrictive key policies that follow least privilege principle
3. **Service Integration**: Keys are restricted to specific AWS services via conditions
4. **Monitoring**: CloudWatch alarms monitor unusual key usage patterns
5. **Audit Trail**: All key usage is logged to CloudWatch Logs
