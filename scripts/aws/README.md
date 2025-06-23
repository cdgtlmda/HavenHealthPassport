# AWS Scripts

This directory contains utility scripts for AWS setup and management.

## Scripts

### bootstrap-cdk.py
Python script to bootstrap AWS CDK in your account/region.

**Usage:**
```bash
./venv/bin/python scripts/aws/bootstrap-cdk.py
```

**Features:**
- Automatically loads AWS credentials from .env.aws
- Verifies AWS credentials before bootstrapping
- Checks CDK installation
- Provides clear error messages

### bootstrap-cdk.sh
Shell script alternative for CDK bootstrapping.

**Usage:**
```bash
./scripts/aws/bootstrap-cdk.sh
```

**Requirements:**
- AWS CLI installed and configured
- CDK installed globally (`npm install -g aws-cdk`)
- Valid .env.aws file with credentials

## CDK Bootstrap

CDK bootstrapping is required once per AWS account/region combination before deploying any CDK applications. It creates:

- S3 bucket for CDK assets
- IAM roles for deployment
- CloudFormation stack for CDK toolkit

## Troubleshooting

If bootstrap fails with permissions error:
1. Ensure your IAM user has CloudFormation permissions
2. Verify the user can create S3 buckets and IAM roles
3. Check AWS credentials are valid with: `./venv/bin/python scripts/verify-aws.py`
