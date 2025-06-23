#!/bin/bash
# Deploy Lambda functions for AWS Managed Blockchain chaincode invocation

set -e

# Configuration
FUNCTION_PREFIX="haven-health-blockchain"
REGION="${AWS_REGION:-us-east-1}"
RUNTIME="python3.9"
TIMEOUT=60
MEMORY_SIZE=512

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Deploying AWS Lambda functions for blockchain chaincode invocation${NC}"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}AWS CLI is required but not installed. Please install it first.${NC}"
    exit 1
fi

# Get directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Create deployment package
echo -e "${YELLOW}Creating deployment package...${NC}"
rm -rf package/
mkdir -p package/

# Copy Lambda function
cp chaincode_invoker.py package/

# Install dependencies
if [ -f requirements.txt ]; then
    pip install -r requirements.txt -t package/ --quiet
fi

# Create ZIP file
cd package
zip -r ../chaincode_invoker.zip . -q
cd ..

# Get network and member IDs from environment or prompt
if [ -z "$MANAGED_BLOCKCHAIN_NETWORK_ID" ]; then
    read -p "Enter Managed Blockchain Network ID: " MANAGED_BLOCKCHAIN_NETWORK_ID
fi

if [ -z "$MANAGED_BLOCKCHAIN_MEMBER_ID" ]; then
    read -p "Enter Managed Blockchain Member ID: " MANAGED_BLOCKCHAIN_MEMBER_ID
fi

# Create IAM role for Lambda (if it doesn't exist)
ROLE_NAME="HavenHealthBlockchainLambdaRole"
ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text 2>/dev/null || echo "")

if [ -z "$ROLE_ARN" ]; then
    echo -e "${YELLOW}Creating IAM role for Lambda...${NC}"
    
    # Create trust policy
    cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Create role
    ROLE_ARN=$(aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file://trust-policy.json \
        --query 'Role.Arn' \
        --output text)
    
    # Attach policies
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonManagedBlockchainFullAccess
    
    # Wait for role to be available
    echo -e "${YELLOW}Waiting for IAM role to be available...${NC}"
    sleep 10
fi

# Define Lambda functions to deploy
declare -A FUNCTIONS
FUNCTIONS["queryHealthRecord"]="Query health record from blockchain"
FUNCTIONS["createHealthRecord"]="Create health record on blockchain"
FUNCTIONS["recordVerification"]="Record verification on blockchain"
FUNCTIONS["getVerificationHistory"]="Get verification history"
FUNCTIONS["createCrossBorderVerification"]="Create cross-border verification"
FUNCTIONS["getCrossBorderVerification"]="Get cross-border verification"
FUNCTIONS["updateCrossBorderVerification"]="Update cross-border verification"
FUNCTIONS["revokeCrossBorderVerification"]="Revoke cross-border verification"
FUNCTIONS["getCountryPublicKey"]="Get country public key"
FUNCTIONS["logCrossBorderAccess"]="Log cross-border access"

# Deploy or update each function
for FUNCTION_NAME in "${!FUNCTIONS[@]}"; do
    FULL_FUNCTION_NAME="${FUNCTION_PREFIX}-${FUNCTION_NAME}"
    DESCRIPTION="${FUNCTIONS[$FUNCTION_NAME]}"
    
    echo -e "${YELLOW}Deploying function: $FULL_FUNCTION_NAME${NC}"
    
    # Check if function exists
    if aws lambda get-function --function-name $FULL_FUNCTION_NAME --region $REGION &>/dev/null; then
        # Update existing function
        aws lambda update-function-code \
            --function-name $FULL_FUNCTION_NAME \
            --zip-file fileb://chaincode_invoker.zip \
            --region $REGION \
            --output text > /dev/null
        
        aws lambda update-function-configuration \
            --function-name $FULL_FUNCTION_NAME \
            --environment "Variables={NETWORK_ID=$MANAGED_BLOCKCHAIN_NETWORK_ID,MEMBER_ID=$MANAGED_BLOCKCHAIN_MEMBER_ID}" \
            --timeout $TIMEOUT \
            --memory-size $MEMORY_SIZE \
            --region $REGION \
            --output text > /dev/null
    else
        # Create new function
        aws lambda create-function \
            --function-name $FULL_FUNCTION_NAME \
            --runtime $RUNTIME \
            --role $ROLE_ARN \
            --handler chaincode_invoker.lambda_handler \
            --description "$DESCRIPTION" \
            --timeout $TIMEOUT \
            --memory-size $MEMORY_SIZE \
            --environment "Variables={NETWORK_ID=$MANAGED_BLOCKCHAIN_NETWORK_ID,MEMBER_ID=$MANAGED_BLOCKCHAIN_MEMBER_ID}" \
            --zip-file fileb://chaincode_invoker.zip \
            --region $REGION \
            --output text > /dev/null
    fi
    
    echo -e "${GREEN}✓ Deployed: $FULL_FUNCTION_NAME${NC}"
done

# Clean up
rm -rf package/
rm -f chaincode_invoker.zip
rm -f trust-policy.json

echo -e "${GREEN}✅ All Lambda functions deployed successfully!${NC}"
echo -e "${YELLOW}Functions are available with prefix: ${FUNCTION_PREFIX}-*${NC}"
echo -e "${YELLOW}Network ID: $MANAGED_BLOCKCHAIN_NETWORK_ID${NC}"
echo -e "${YELLOW}Member ID: $MANAGED_BLOCKCHAIN_MEMBER_ID${NC}"
