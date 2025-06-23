#!/bin/bash

# Consenter Set Configuration Script
# Haven Health Passport - Blockchain Infrastructure
# This script configures the consenter set for Raft consensus

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration variables
NETWORK_ID="${HAVEN_NETWORK_ID}"
MEMBER_ID="${HAVEN_MEMBER_ID}"
CHANNEL_NAME="haven-system-channel"
ORDERER_CA="${ORDERER_CA_CERT}"
ORDERER_ENDPOINT="orderer0.havenhealthpassport.com:7050"

echo -e "${GREEN}Haven Health Passport - Consenter Set Configuration${NC}"
echo "====================================================="
echo ""

# Function to check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"

    # Check for required tools
    for tool in aws jq configtxlator peer; do
        if ! command -v $tool &> /dev/null; then
            echo -e "${RED}Error: $tool is required but not installed.${NC}"
            exit 1
        fi
    done

    # Check environment variables
    if [ -z "$NETWORK_ID" ] || [ -z "$MEMBER_ID" ]; then
        echo -e "${RED}Error: HAVEN_NETWORK_ID and HAVEN_MEMBER_ID must be set.${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ All prerequisites met${NC}"
}

# Function to fetch current channel configuration
fetch_channel_config() {
    echo -e "${YELLOW}Fetching current channel configuration...${NC}"

    peer channel fetch config config_block.pb \
        -o $ORDERER_ENDPOINT \
        -c $CHANNEL_NAME \
        --tls --cafile $ORDERER_CA

    # Decode the configuration
    configtxlator proto_decode \
        --input config_block.pb \
        --type common.Block | jq .data.data[0].payload.data.config > config.json

    echo -e "${GREEN}✓ Configuration fetched successfully${NC}"
}
