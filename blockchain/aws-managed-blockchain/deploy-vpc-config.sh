#!/bin/bash

# Haven Health Passport - Deploy VPC Configuration for Blockchain

set -e

# Configuration
STACK_NAME="haven-blockchain-vpc-config"
REGION="${AWS_REGION:-us-east-1}"
TEMPLATE_FILE="./config/vpc-configuration.yaml"
NETWORK_CONFIG="./deployed-config/network-info.json"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if network config exists
if [ ! -f "$NETWORK_CONFIG" ]; then
    print_error "Network configuration not found. Please deploy the network first."
    exit 1
fi

# Read network configuration
NETWORK_ID=$(jq -r '.networkId' $NETWORK_CONFIG)
print_status "Network ID: $NETWORK_ID"

# Get VPC information
print_status "Please provide VPC configuration:"
read -p "VPC ID: " VPC_ID

# Get subnet IDs
print_status "Enter subnet IDs (comma-separated): "
read -p "Subnet IDs: " SUBNET_IDS_INPUT

# Convert comma-separated to space-separated for CloudFormation
SUBNET_IDS=$(echo $SUBNET_IDS_INPUT | tr ',' ' ')

# Deploy VPC configuration
print_status "Deploying VPC configuration..."
aws cloudformation create-stack \
    --stack-name $STACK_NAME \
    --template-body file://$TEMPLATE_FILE \
    --parameters \
        ParameterKey=VpcId,ParameterValue=$VPC_ID \
        ParameterKey=SubnetIds,ParameterValue=\"$SUBNET_IDS\" \
        ParameterKey=NetworkId,ParameterValue=$NETWORK_ID \
    --capabilities CAPABILITY_IAM \
    --region $REGION

print_status "Waiting for VPC configuration deployment..."
aws cloudformation wait stack-create-complete \
    --stack-name $STACK_NAME \
    --region $REGION

# Get outputs
SECURITY_GROUP_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`SecurityGroupId`].OutputValue' \
    --output text)

VPC_ENDPOINT_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`VPCEndpointId`].OutputValue' \
    --output text)

# Save VPC configuration
cat > ./deployed-config/vpc-config.json <<EOF
{
  "vpcId": "$VPC_ID",
  "securityGroupId": "$SECURITY_GROUP_ID",
  "vpcEndpointId": "$VPC_ENDPOINT_ID",
  "subnetIds": "$SUBNET_IDS_INPUT",
  "deploymentTime": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

print_status "==================================="
print_status "VPC Configuration Deployed!"
print_status "==================================="
print_status "Security Group ID: $SECURITY_GROUP_ID"
print_status "VPC Endpoint ID: $VPC_ENDPOINT_ID"
print_status "==================================="

chmod +x deploy-vpc-config.sh
