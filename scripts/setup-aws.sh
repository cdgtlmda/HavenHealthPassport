#!/bin/bash

# Haven Health Passport - AWS Setup Script
# This script sets up the minimal required AWS resources

set -e  # Exit on error

echo "======================================"
echo "Haven Health Passport - AWS Setup"
echo "======================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI not found${NC}"
    exit 1
fi

# Check credentials
echo "Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: AWS credentials not configured${NC}"
    echo "Run: aws configure"
    exit 1
fi

# Get account info
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)
echo -e "${GREEN}✓${NC} Using AWS Account: $ACCOUNT_ID"
echo -e "${GREEN}✓${NC} Region: $REGION"
echo ""

# Generate unique suffix
SUFFIX=$(date +%s | tail -c 5)
BUCKET_NAME="haven-health-passport-${SUFFIX}"

echo "Creating AWS resources..."
echo ""

# 1. Create S3 Bucket
echo "1. Creating S3 bucket: $BUCKET_NAME"
if aws s3 mb "s3://${BUCKET_NAME}" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} S3 bucket created"
    
    # Enable versioning
    aws s3api put-bucket-versioning \
        --bucket "${BUCKET_NAME}" \
        --versioning-configuration Status=Enabled
    echo -e "${GREEN}✓${NC} Versioning enabled"
    
    # Enable encryption
    aws s3api put-bucket-encryption \
        --bucket "${BUCKET_NAME}" \
        --server-side-encryption-configuration '{
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                }
            }]
        }'
    echo -e "${GREEN}✓${NC} Encryption enabled"
else
    echo -e "${YELLOW}!${NC} S3 bucket creation failed (may already exist)"
fi
echo ""

# 2. Create DynamoDB Tables
echo "2. Creating DynamoDB tables..."

# Sessions table
if aws dynamodb create-table \
    --table-name haven-health-sessions \
    --attribute-definitions \
        AttributeName=session_id,AttributeType=S \
    --key-schema \
        AttributeName=session_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "${REGION}" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Sessions table created"
else
    echo -e "${YELLOW}!${NC} Sessions table may already exist"
fi

# Audit logs table
if aws dynamodb create-table \
    --table-name haven-health-audit-logs \
    --attribute-definitions \
        AttributeName=log_id,AttributeType=S \
        AttributeName=timestamp,AttributeType=N \
    --key-schema \
        AttributeName=log_id,KeyType=HASH \
        AttributeName=timestamp,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region "${REGION}" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Audit logs table created"
else
    echo -e "${YELLOW}!${NC} Audit logs table may already exist"
fi
echo ""

# 3. Create Cognito User Pool
echo "3. Creating Cognito User Pool..."
COGNITO_RESPONSE=$(aws cognito-idp create-user-pool \
    --pool-name haven-health-users-${SUFFIX} \
    --policies '{
        "PasswordPolicy": {
            "MinimumLength": 12,
            "RequireUppercase": true,
            "RequireLowercase": true,
            "RequireNumbers": true,
            "RequireSymbols": true
        }
    }' \
    --mfa-configuration OPTIONAL \
    --auto-verified-attributes email \
    --region "${REGION}" 2>/dev/null || true)

if [ -n "$COGNITO_RESPONSE" ]; then
    USER_POOL_ID=$(echo "$COGNITO_RESPONSE" | grep -o '"Id": "[^"]*' | grep -o '[^"]*$')
    echo -e "${GREEN}✓${NC} User pool created: $USER_POOL_ID"
    
    # Create app client
    CLIENT_RESPONSE=$(aws cognito-idp create-user-pool-client \
        --user-pool-id "$USER_POOL_ID" \
        --client-name haven-health-client \
        --generate-secret \
        --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH \
        --region "${REGION}")
    
    CLIENT_ID=$(echo "$CLIENT_RESPONSE" | grep -o '"ClientId": "[^"]*' | grep -o '[^"]*$')
    echo -e "${GREEN}✓${NC} App client created: $CLIENT_ID"
else
    echo -e "${YELLOW}!${NC} User pool creation skipped (may already exist)"
    USER_POOL_ID="UPDATE_ME"
    CLIENT_ID="UPDATE_ME"
fi
echo ""

# 4. Check Bedrock Access
echo "4. Checking Bedrock access..."
if aws bedrock list-foundation-models --region "${REGION}" &>/dev/null; then
    echo -e "${GREEN}✓${NC} Bedrock access available"
else
    echo -e "${YELLOW}!${NC} Bedrock not available in ${REGION}"
    echo "   Please enable Bedrock models in the AWS Console:"
    echo "   https://console.aws.amazon.com/bedrock/"
fi
echo ""

# 5. Create .env.local file
echo "5. Creating .env.local file..."
cat > .env.local << EOF
# AWS Configuration (Generated by setup script)
AWS_REGION=${REGION}
AWS_ACCOUNT_ID=${ACCOUNT_ID}

# S3 Configuration
S3_BUCKET=${BUCKET_NAME}

# DynamoDB Tables
DYNAMODB_SESSIONS_TABLE=haven-health-sessions
DYNAMODB_AUDIT_TABLE=haven-health-audit-logs

# Cognito Configuration
COGNITO_USER_POOL_ID=${USER_POOL_ID}
COGNITO_CLIENT_ID=${CLIENT_ID}
COGNITO_REGION=${REGION}

# Bedrock Configuration
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_REGION=${REGION}

# Application Settings
ENVIRONMENT=development
DEBUG=true
EOF

echo -e "${GREEN}✓${NC} Created .env.local"
echo ""

# 6. Summary
echo "======================================"
echo "Setup Summary"
echo "======================================"
echo ""
echo "S3 Bucket: ${BUCKET_NAME}"
echo "DynamoDB Tables: haven-health-sessions, haven-health-audit-logs"
echo "Cognito User Pool ID: ${USER_POOL_ID}"
echo "Cognito Client ID: ${CLIENT_ID}"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "1. Copy your AWS credentials to .env file"
echo "2. Enable Bedrock models in AWS Console if not done"
echo "3. Review and update .env.local as needed"
echo ""
echo -e "${GREEN}Setup complete!${NC}"