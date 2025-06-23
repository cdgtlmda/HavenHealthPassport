#!/bin/bash

# Haven Health Passport - Hyperledger Fabric Framework Configuration
# This script validates and configures the Hyperledger Fabric framework selection

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${SCRIPT_DIR}/../config"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Hyperledger Fabric Framework Configuration${NC}"
echo -e "${BLUE}================================================${NC}"

# Function to validate framework selection
validate_framework_selection() {
    echo -e "\n📋 Validating Hyperledger Fabric framework selection..."

    # Check if network-info.json exists
    if [ ! -f "${CONFIG_DIR}/network-info.json" ]; then
        echo -e "${RED}Error: Network info not found. Please run 01-create-blockchain-network.sh first.${NC}"
        exit 1
    fi

    # Validate framework in CloudFormation template
    FRAMEWORK=$(grep -E "Framework:\s*HYPERLEDGER_FABRIC" "${CONFIG_DIR}/blockchain-network.yaml" | wc -l)
    if [ $FRAMEWORK -gt 0 ]; then
        echo -e "${GREEN}✓ Hyperledger Fabric framework is correctly configured${NC}"
    else
        echo -e "${RED}✗ Framework configuration error${NC}"
        exit 1
    fi

    # Validate framework version
    FRAMEWORK_VERSION=$(grep -E "FrameworkVersion:\s*'2.2'" "${CONFIG_DIR}/blockchain-network.yaml" | wc -l)
    if [ $FRAMEWORK_VERSION -gt 0 ]; then
        echo -e "${GREEN}✓ Framework version 2.2 is correctly configured${NC}"
    else
        echo -e "${RED}✗ Framework version configuration error${NC}"
        exit 1
    fi
}

# Execute validation
validate_framework_selection

echo -e "\n${GREEN}Framework configuration validated successfully!${NC}"
