#!/bin/bash
# Bootstrap AWS CDK using environment variables from .env.aws

echo "🚀 Bootstrapping AWS CDK..."

# Load AWS credentials from .env.aws
if [ -f .env.aws ]; then
    export $(cat .env.aws | grep -v '^#' | xargs)
    echo "✅ Loaded AWS credentials from .env.aws"
else
    echo "❌ .env.aws file not found"
    exit 1
fi

# Verify AWS credentials
echo "🔍 Verifying AWS credentials..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "✅ AWS Account: $AWS_ACCOUNT_ID"
    echo "📍 Region: $AWS_REGION"
else
    echo "❌ Failed to verify AWS credentials"
    echo "Please check your .env.aws file"
    exit 1
fi

# Check if CDK is installed
if ! command -v cdk &> /dev/null; then
    echo "❌ AWS CDK is not installed"
    echo "Please install it with: npm install -g aws-cdk"
    exit 1
fi

echo "✅ CDK Version: $(cdk --version)"

# Bootstrap CDK
echo ""
echo "🔧 Bootstrapping CDK in $AWS_REGION..."
cdk bootstrap aws://$AWS_ACCOUNT_ID/$AWS_REGION \
    --cloudformation-execution-policies arn:aws:iam::aws:policy/AdministratorAccess

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ CDK bootstrap completed successfully!"
else
    echo ""
    echo "❌ CDK bootstrap failed"
    exit 1
fi
