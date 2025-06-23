#!/bin/bash

# Haven Health Passport - Peer Node Configuration Script
# This script handles peer node deployment and configuration

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
echo -e "${BLUE}Peer Node Configuration${NC}"
echo -e "${BLUE}================================================${NC}"

# Function to check prerequisites
check_prerequisites() {
    echo -e "\n📋 Checking prerequisites..."

    # Check for network info
    if [ ! -f "${CONFIG_DIR}/network-info.json" ]; then
        echo -e "${RED}Error: Network info not found. Run network creation first.${NC}"
        exit 1
    fi

    # Extract network and member IDs
    NETWORK_ID=$(jq -r '.NetworkId' "${CONFIG_DIR}/network-info.json")
    MEMBER_ID=$(jq -r '.MemberId' "${CONFIG_DIR}/network-info.json")

    echo -e "${GREEN}✓ Network ID: ${NETWORK_ID}${NC}"
    echo -e "${GREEN}✓ Member ID: ${MEMBER_ID}${NC}"
}

# Function to select instance type
select_instance_type() {
    echo -e "\n📊 Peer Node Instance Types:"
    echo -e "┌─────────────────┬────────┬────────┬─────────────┐"
    echo -e "│ Instance Type   │ vCPUs  │ Memory │ Use Case    │"
    echo -e "├─────────────────┼────────┼────────┼─────────────┤"
    echo -e "│ bc.t3.small     │ 2      │ 2 GB   │ Development │"
    echo -e "│ bc.t3.medium    │ 2      │ 4 GB   │ Development │"
    echo -e "│ bc.t3.large     │ 2      │ 8 GB   │ Testing     │"
    echo -e "│ bc.m5.large     │ 2      │ 8 GB   │ Production  │"
    echo -e "│ bc.m5.xlarge    │ 4      │ 16 GB  │ Production  │"
    echo -e "│ bc.m5.2xlarge   │ 8      │ 32 GB  │ High Load   │"
    echo -e "└─────────────────┴────────┴────────┴─────────────┘"

    # Default to bc.m5.large for production
    INSTANCE_TYPE="${PEER_INSTANCE_TYPE:-bc.m5.large}"
    echo -e "\n${GREEN}Selected: ${INSTANCE_TYPE}${NC}"
}
# Function to deploy peer node
deploy_peer_node() {
    echo -e "\n🚀 Deploying peer node..."

    # Get availability zones
    echo -e "\n📍 Available zones in current region:"
    aws ec2 describe-availability-zones --query "AvailabilityZones[].ZoneName" --output table

    # Use first available zone by default
    AZ=$(aws ec2 describe-availability-zones --query "AvailabilityZones[0].ZoneName" --output text)
    AZ="${PEER_AVAILABILITY_ZONE:-$AZ}"

    echo -e "\n${GREEN}Deploying peer node with:${NC}"
    echo -e "  Network ID: ${NETWORK_ID}"
    echo -e "  Member ID: ${MEMBER_ID}"
    echo -e "  Instance Type: ${INSTANCE_TYPE}"
    echo -e "  Availability Zone: ${AZ}"
    echo -e "  Logging: Enabled"

    # Deploy peer node stack
    PEER_STACK_NAME="${BLOCKCHAIN_STACK_NAME}-peer-1"

    aws cloudformation deploy \
        --template-file "${CONFIG_DIR}/peer-node.yaml" \
        --stack-name "${PEER_STACK_NAME}" \
        --parameter-overrides \
            NetworkId="${NETWORK_ID}" \
            MemberId="${MEMBER_ID}" \
            InstanceType="${INSTANCE_TYPE}" \
            AvailabilityZone="${AZ}" \
            EnableLogging="true" \
        --capabilities CAPABILITY_IAM \
        2>&1 | tee -a "${LOGS_DIR}/peer_deployment_${TIMESTAMP}.log"

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        echo -e "${GREEN}✓ Peer node stack deployed successfully${NC}"
    else
        echo -e "${RED}✗ Peer node deployment failed${NC}"
        exit 1
    fi
}

# Function to verify peer node
verify_peer_node() {
    echo -e "\n🔍 Verifying peer node deployment..."

    # Get peer node ID
    PEER_NODE_ID=$(aws cloudformation describe-stacks \
        --stack-name "${PEER_STACK_NAME}" \
        --query "Stacks[0].Outputs[?OutputKey=='PeerNodeId'].OutputValue" \
        --output text)

    if [ -n "${PEER_NODE_ID}" ]; then
        echo -e "${GREEN}✓ Peer Node ID: ${PEER_NODE_ID}${NC}"

        # Save peer node info
        echo "{\"PeerNodeId\": \"${PEER_NODE_ID}\", \"AvailabilityZone\": \"${AZ}\"}" > "${CONFIG_DIR}/peer-node-info.json"
    else
        echo -e "${RED}✗ Failed to retrieve peer node ID${NC}"
        exit 1
    fi
}

# Main execution
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "${LOGS_DIR}"

check_prerequisites
select_instance_type
deploy_peer_node
verify_peer_node

echo -e "\n${GREEN}Peer node configuration completed!${NC}"
