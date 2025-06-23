#!/bin/bash

# Haven Health Passport - Deploy Peer Nodes Script
# This script deploys peer nodes for the AWS Managed Blockchain network

set -e

# Configuration
STACK_PREFIX="haven-health-peer-node"
REGION="${AWS_REGION:-us-east-1}"
TEMPLATE_FILE="./config/peer-node.yaml"
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
MEMBER_ID=$(jq -r '.memberId' $NETWORK_CONFIG)

print_status "Network ID: $NETWORK_ID"
print_status "Member ID: $MEMBER_ID"

# Get available zones
print_status "Fetching available zones..."
ZONES=$(aws ec2 describe-availability-zones \
    --region $REGION \
    --query 'AvailabilityZones[?State==`available`].ZoneName' \
    --output json)

echo "Available zones:"
echo $ZONES | jq -r '.[]' | nl
# Get user input
read -p "Select availability zone number: " ZONE_NUM
SELECTED_ZONE=$(echo $ZONES | jq -r ".[$((ZONE_NUM-1))]")

print_status "Selected zone: $SELECTED_ZONE"

# Instance type selection
echo "Available instance types:"
echo "1) bc.t3.small (Development)"
echo "2) bc.t3.medium (Testing)"
echo "3) bc.t3.large (Production - Small)"
echo "4) bc.m5.xlarge (Production - Medium)"
echo "5) bc.c5.2xlarge (Production - High Performance)"

read -p "Select instance type (1-5): " INSTANCE_CHOICE

case $INSTANCE_CHOICE in
    1) INSTANCE_TYPE="bc.t3.small" ;;
    2) INSTANCE_TYPE="bc.t3.medium" ;;
    3) INSTANCE_TYPE="bc.t3.large" ;;
    4) INSTANCE_TYPE="bc.m5.xlarge" ;;
    5) INSTANCE_TYPE="bc.c5.2xlarge" ;;
    *) INSTANCE_TYPE="bc.t3.small" ;;
esac

print_status "Selected instance type: $INSTANCE_TYPE"

# Deploy peer node
STACK_NAME="${STACK_PREFIX}-${SELECTED_ZONE}"
print_status "Deploying peer node..."

aws cloudformation create-stack \
    --stack-name $STACK_NAME \
    --template-body file://$TEMPLATE_FILE \
    --parameters \
        ParameterKey=NetworkId,ParameterValue=$NETWORK_ID \
        ParameterKey=MemberId,ParameterValue=$MEMBER_ID \
        ParameterKey=AvailabilityZone,ParameterValue=$SELECTED_ZONE \
        ParameterKey=InstanceType,ParameterValue=$INSTANCE_TYPE \
    --region $REGION

print_status "Waiting for peer node deployment..."
aws cloudformation wait stack-create-complete \
    --stack-name $STACK_NAME \
    --region $REGION

print_status "Peer node deployed successfully!"

# Save peer node configuration
PEER_NODE_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`PeerNodeId`].OutputValue' \
    --output text)
PEER_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`PeerNodeEndpoint`].OutputValue' \
    --output text)

# Save configuration
cat > ./deployed-config/peer-node-${SELECTED_ZONE}.json <<EOF
{
  "peerNodeId": "$PEER_NODE_ID",
  "peerEndpoint": "$PEER_ENDPOINT",
  "availabilityZone": "$SELECTED_ZONE",
  "instanceType": "$INSTANCE_TYPE",
  "deploymentTime": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

print_status "==================================="
print_status "Peer Node Deployed Successfully!"
print_status "==================================="
print_status "Peer Node ID: $PEER_NODE_ID"
print_status "Peer Endpoint: $PEER_ENDPOINT"
print_status "Instance Type: $INSTANCE_TYPE"
print_status "Availability Zone: $SELECTED_ZONE"
print_status "==================================="

chmod +x deploy-peer-nodes.sh
