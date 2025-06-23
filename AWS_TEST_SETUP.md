# AWS Test Environment Setup for Medical Compliance

## CRITICAL: Real AWS Services Required

Per medical compliance requirements, this project **CANNOT use mocks** for AWS services. All tests must use real AWS infrastructure.

## Required AWS Setup

### 1. AWS Test Account

```bash
# Configure AWS credentials for testing
aws configure
# Enter your test account credentials:
# AWS Access Key ID: [your-test-key]
# AWS Secret Access Key: [your-test-secret]
# Default region name: us-east-1
# Default output format: json
```

### 2. Create Test KMS Key

```bash
# Create a KMS key for encryption testing
aws kms create-key \
    --description "HavenHealthPassport Test Encryption Key" \
    --usage ENCRYPT_DECRYPT \
    --key-spec SYMMETRIC_DEFAULT

# Create an alias for easier reference
aws kms create-alias \
    --alias-name alias/haven-health-test-key \
    --target-key-id [KEY-ID-FROM-ABOVE]
```

### 3. Create Test S3 Bucket

```bash
# Create S3 bucket for backup testing
aws s3 mb s3://haven-health-test-backups-$(date +%s)
```

### 4. Set Environment Variables

```bash
# Add to your shell profile (.bashrc, .zshrc, etc.)
export TEST_KMS_KEY_ID="alias/haven-health-test-key"
export TEST_S3_BUCKET="haven-health-test-backups-[your-suffix]"
export AWS_DEFAULT_REGION="us-east-1"
```

### 5. Required IAM Permissions

Your test user needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:GenerateDataKey",
        "kms:DescribeKey"
      ],
      "Resource": "arn:aws:kms:*:*:key/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::haven-health-test-*/*"
    }
  ]
}
```

## Running Tests with Real AWS

```bash
# Verify AWS setup
aws sts get-caller-identity

# Run encryption tests with real AWS services
python -m pytest tests/unit/security/test_backup_encryption.py -v

# Verify 100% coverage as required for encryption files
python -m coverage run -m pytest tests/unit/security/test_backup_encryption.py
python -m coverage report --include="*backup_encryption.py" --show-missing --fail-under=100
```

## Cost Considerations

- KMS operations: ~$0.03 per 10,000 requests
- S3 storage: ~$0.023 per GB per month
- Estimated test cost: <$1/month for typical testing

## Security Notes

- Use dedicated test account (not production)
- Rotate test credentials regularly
- Delete test resources when not needed
- Never commit AWS credentials to code
