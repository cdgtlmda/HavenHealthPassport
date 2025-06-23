# Haven Health Passport - Terraform Infrastructure

This directory contains the Terraform configuration for managing AWS infrastructure for the Haven Health Passport project.

## Prerequisites

1. **AWS CLI** installed and configured
2. **Terraform** >= 1.0
3. AWS credentials with appropriate permissions
4. Access to request Bedrock models in your AWS account

## Directory Structure

```
infrastructure/terraform/
├── main.tf                 # Main Terraform configuration
├── variables.tf            # Variable definitions
├── outputs.tf              # Output definitions
├── environments/           # Environment-specific configurations
│   ├── development.tfvars
│   ├── staging.tfvars
│   └── production.tfvars
└── modules/               # Reusable modules
    └── bedrock/           # Bedrock-specific configuration
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

## Initial Setup

### 1. Enable Amazon Bedrock in AWS Account

1. Sign in to the AWS Management Console
2. Navigate to Amazon Bedrock service
3. Click "Get started" if this is your first time using Bedrock
4. Review and accept the service terms

### 2. Request Model Access

1. In the Bedrock console, go to "Model access"
2. Click "Manage model access"
3. Select the following models:
   - Anthropic Claude (all variants)
   - Amazon Titan (all variants)
   - Meta Llama 2 (if available in your region)
   - AI21 Labs Jurassic (if needed)
4. Submit the access request
5. Wait for approval (usually instant for most models)

### 3. Configure Terraform Backend

Create an S3 bucket and DynamoDB table for Terraform state:

```bash
# Create S3 bucket for state
aws s3api create-bucket \
  --bucket haven-health-terraform-state \
  --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket haven-health-terraform-state \
  --versioning-configuration Status=Enabled

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name haven-health-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
  --region us-east-1
```

### 4. Initialize Terraform

```bash
cd infrastructure/terraform

# Initialize with backend configuration
terraform init \
  -backend-config="bucket=haven-health-terraform-state" \
  -backend-config="key=terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=haven-health-terraform-locks"
```

## Deployment

### Development Environment

```bash
terraform plan -var-file=environments/development.tfvars
terraform apply -var-file=environments/development.tfvars
```

### Staging Environment

```bash
terraform plan -var-file=environments/staging.tfvars
terraform apply -var-file=environments/staging.tfvars
```

### Production Environment

```bash
terraform plan -var-file=environments/production.tfvars
terraform apply -var-file=environments/production.tfvars
```

## Outputs

After successful deployment, Terraform will output:

- `bedrock_iam_role_arn`: IAM role ARN for Bedrock access
- `bedrock_policy_arn`: IAM policy ARN for Bedrock permissions
- `bedrock_model_access_status`: URL to check model access status
- `bedrock_monitoring_dashboard_url`: CloudWatch dashboard URL

## Service Quotas

Default Bedrock service quotas:
- Requests per minute: 60
- Concurrent requests: 10

To increase quotas, use AWS Service Quotas console.

## Cost Management

The infrastructure includes:
- AWS Budget alerts at 80% and 100% of monthly budget
- CloudWatch dashboards for usage monitoring
- Cost allocation tags for tracking

## Security

- All IAM roles follow least-privilege principle
- CloudWatch logs are encrypted at rest
- Sensitive data is never logged

## Troubleshooting

1. **Model Access Denied**: Ensure models are approved in Bedrock console
2. **Throttling Errors**: Check service quotas and request increases
3. **Permission Errors**: Verify IAM role has necessary permissions

## Next Steps

After infrastructure deployment:
1. Update application configuration with IAM role ARN
2. Test Bedrock connectivity
3. Configure monitoring alerts
4. Set up cost budgets
