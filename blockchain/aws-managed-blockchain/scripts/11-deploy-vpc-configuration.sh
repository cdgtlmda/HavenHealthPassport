#!/bin/bash

# Haven Health Passport - VPC Configuration Deployment
# This script deploys VPC endpoint, security groups, and network ACLs

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${SCRIPT_DIR}/../config"
LOGS_DIR="${SCRIPT_DIR}/../logs"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}VPC Configuration Deployment${NC}"
echo -e "${BLUE}================================================${NC}"

# Function to check prerequisites
check_vpc_prerequisites() {
    echo -e "\n📋 Checking VPC prerequisites..."

    # Check for network info
    if [ ! -f "${CONFIG_DIR}/network-info.json" ]; then
        echo -e "${RED}Error: Network info not found${NC}"
        exit 1
    fi

    NETWORK_ID=$(jq -r '.NetworkId' "${CONFIG_DIR}/network-info.json")
    echo -e "${GREEN}✓ Network ID: ${NETWORK_ID}${NC}"
}

# Function to get VPC configuration
get_vpc_config() {
    echo -e "\n🔍 Getting VPC configuration..."

    # Get default VPC if not specified
    if [ -z "${VPC_ID:-}" ]; then
        VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text)
        echo -e "${YELLOW}Using default VPC: ${VPC_ID}${NC}"
    fi

    # Get subnets for the VPC
    if [ -z "${SUBNET_IDS:-}" ]; then
        SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=${VPC_ID}" --query "Subnets[0:2].SubnetId" --output text | tr '\t' ',')
        echo -e "${YELLOW}Using subnets: ${SUBNET_IDS}${NC}"
    fi
}

# Function to deploy VPC configuration
deploy_vpc_config() {
    echo -e "\n🚀 Deploying VPC configuration..."

    VPC_STACK_NAME="${BLOCKCHAIN_STACK_NAME:-HavenHealthPassportBlockchain}-vpc"

    aws cloudformation deploy \
        --template-file "${CONFIG_DIR}/vpc-configuration.yaml" \
        --stack-name "${VPC_STACK_NAME}" \
        --parameter-overrides \
            VpcId="${VPC_ID}" \
            SubnetIds="${SUBNET_IDS}" \
            NetworkId="${NETWORK_ID}" \
        --capabilities CAPABILITY_IAM \
        2>&1 | tee -a "${LOGS_DIR}/vpc_deployment_$(date +%Y%m%d_%H%M%S).log"

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        echo -e "${GREEN}✓ VPC configuration deployed successfully${NC}"
    else
        echo -e "${RED}✗ VPC configuration deployment failed${NC}"
        exit 1
    fi
}

# Function to save VPC info
save_vpc_info() {
    echo -e "\n💾 Saving VPC configuration info..."

    # Get stack outputs
    SECURITY_GROUP_ID=$(aws cloudformation describe-stacks \
        --stack-name "${VPC_STACK_NAME}" \
        --query "Stacks[0].Outputs[?OutputKey=='SecurityGroupId'].OutputValue" \
        --output text)

    VPC_ENDPOINT_ID=$(aws cloudformation describe-stacks \
        --stack-name "${VPC_STACK_NAME}" \
        --query "Stacks[0].Outputs[?OutputKey=='VPCEndpointId'].OutputValue" \
        --output text)

    # Save VPC info
    cat > "${CONFIG_DIR}/vpc-info.json" <<EOF
{
    "VpcId": "${VPC_ID}",
    "SubnetIds": "${SUBNET_IDS}",
    "SecurityGroupId": "${SECURITY_GROUP_ID}",
    "VpcEndpointId": "${VPC_ENDPOINT_ID}",
    "NetworkId": "${NETWORK_ID}"
}
EOF

    echo -e "${GREEN}✓ VPC configuration saved${NC}"
}

# Main execution
mkdir -p "${LOGS_DIR}"

check_vpc_prerequisites
get_vpc_config
deploy_vpc_config
save_vpc_info

echo -e "\n${GREEN}VPC configuration completed!${NC}"
echo -e "✓ VPC endpoint created"
echo -e "✓ Security groups configured"
echo -e "✓ Network ACLs set up"
echo -e "✓ VPC flow logs enabled"
