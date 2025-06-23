# AWS Configuration Guide

## Prerequisites

AWS CLI is already installed (version 2.27.6).

## Configuration Steps

### 1. Create AWS Account

If you don't have an AWS account:
1. Go to https://aws.amazon.com/
2. Click "Create an AWS Account"
3. Follow the sign-up process

### 2. Create IAM User

1. Log into AWS Console
2. Navigate to IAM (Identity and Access Management)
3. Click "Users" → "Add users"
4. Username: `haven-health-dev`
5. Select "Access key - Programmatic access"
6. Attach policies:
   - `AmazonS3FullAccess` (for development)
   - `AmazonDynamoDBFullAccess` (for development)
   - `AmazonCognitoPowerUser`
   - `AWSHealthLakeFullAccess`
   - `AmazonManagedBlockchainFullAccess`
   - Custom policy for Bedrock access

### 3. Configure AWS CLI

Run the following command and enter your credentials:

```bash
aws configure
```

Enter:
- AWS Access Key ID: [Your access key]
- AWS Secret Access Key: [Your secret key]
- Default region name: us-east-1
- Default output format: json

### 4. Verify Configuration

```bash
aws sts get-caller-identity
```

### 5. Create Development Resources

For hackathon/development purposes, you can use LocalStack (already in docker-compose.yml) which provides local AWS service emulation.

### 6. Environment Variables

Update your `.env` file with your AWS credentials:

```bash
cp .env.example .env
# Edit .env with your actual values
```

## Security Best Practices

1. **Never commit credentials** - The .env file is already in .gitignore
2. **Use IAM roles in production** instead of access keys
3. **Enable MFA** on your AWS account
4. **Rotate access keys** regularly
5. **Use least privilege** - only grant necessary permissions

## LocalStack Alternative

For development without AWS costs, LocalStack is configured in docker-compose.yml:

```bash
# Start LocalStack
docker-compose up localstack

# Configure AWS CLI for LocalStack
aws configure set aws_access_key_id test
aws configure set aws_secret_access_key test
aws configure set region us-east-1

# Use LocalStack endpoint
export AWS_ENDPOINT_URL=http://localhost:4566
```