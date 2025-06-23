#!/bin/bash

# Haven Health Passport - AWS Managed Blockchain Deployment Script
# This script deploys the AWS Managed Blockchain network using CloudFormation

set -e

# Configuration Variables
STACK_NAME="haven-health-passport-blockchain"
REGION="${AWS_REGION:-us-east-1}"
TEMPLATE_FILE="./config/blockchain-network.yaml"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check if template file exists
if [ ! -f "$TEMPLATE_FILE" ]; then
    print_error "CloudFormation template not found: $TEMPLATE_FILE"
    exit 1
fi
# Validate the CloudFormation template
print_status "Validating CloudFormation template..."
if aws cloudformation validate-template --template-body file://$TEMPLATE_FILE --region $REGION &> /dev/null; then
    print_status "Template validation successful"
else
    print_error "Template validation failed"
    exit 1
fi

# Get parameters from user
print_status "Please provide the following parameters:"
read -p "Admin Password (min 8 characters): " -s ADMIN_PASSWORD
echo
read -p "Network Name (default: HavenHealthPassportNetwork): " NETWORK_NAME
NETWORK_NAME=${NETWORK_NAME:-HavenHealthPassportNetwork}
read -p "Member Name (default: HavenHealthFoundation): " MEMBER_NAME
MEMBER_NAME=${MEMBER_NAME:-HavenHealthFoundation}

# Deploy the stack
print_status "Deploying AWS Managed Blockchain network..."
print_status "Stack Name: $STACK_NAME"
print_status "Region: $REGION"
print_status "Network Name: $NETWORK_NAME"

aws cloudformation create-stack \
    --stack-name $STACK_NAME \
    --template-body file://$TEMPLATE_FILE \
    --parameters \
        ParameterKey=AdminPassword,ParameterValue=$ADMIN_PASSWORD \
        ParameterKey=NetworkName,ParameterValue=$NETWORK_NAME \
        ParameterKey=MemberName,ParameterValue=$MEMBER_NAME \
    --capabilities CAPABILITY_IAM \
    --region $REGION

print_status "Stack creation initiated. Waiting for completion..."

# Wait for stack creation to complete
aws cloudformation wait stack-create-complete \
    --stack-name $STACK_NAME \
    --region $REGION

print_status "Stack creation completed successfully!"

# Get outputs
print_status "Retrieving network information..."
NETWORK_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`NetworkId`].OutputValue' \
    --output text)
MEMBER_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`MemberId`].OutputValue' \
    --output text)

print_status "==================================="
print_status "Blockchain Network Deployed Successfully!"
print_status "==================================="
print_status "Network ID: $NETWORK_ID"
print_status "Member ID: $MEMBER_ID"
print_status "Framework: Hyperledger Fabric 2.2"
print_status "Edition: Standard"
print_status "==================================="

# Save configuration
CONFIG_DIR="./deployed-config"
mkdir -p $CONFIG_DIR

cat > $CONFIG_DIR/network-info.json <<EOF
{
  "networkId": "$NETWORK_ID",
  "memberId": "$MEMBER_ID",
  "networkName": "$NETWORK_NAME",
  "memberName": "$MEMBER_NAME",
  "region": "$REGION",
  "framework": "HYPERLEDGER_FABRIC",
  "frameworkVersion": "2.2",
  "edition": "STANDARD",
  "deploymentTime": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

print_status "Configuration saved to $CONFIG_DIR/network-info.json"
print_warning "Please save the admin credentials securely!"
