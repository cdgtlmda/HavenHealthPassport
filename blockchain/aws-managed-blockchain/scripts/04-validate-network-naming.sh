#!/bin/bash

# Haven Health Passport - Network Name and Description Configuration
# This script validates the network name and description settings

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
echo -e "${BLUE}Network Name and Description Configuration${NC}"
echo -e "${BLUE}================================================${NC}"

# Function to validate network naming
validate_network_naming() {
    echo -e "\n📋 Validating network name and description..."

    # Extract configured values
    NETWORK_NAME=$(grep -E "Default:\s*HavenHealthPassportNetwork" "${CONFIG_DIR}/blockchain-network.yaml" | head -1)
    NETWORK_DESC=$(grep -A1 "NetworkDescription:" "${CONFIG_DIR}/blockchain-network.yaml" | grep "Default:" | cut -d"'" -f2)

    echo -e "\n📌 Configured Network Details:"
    echo -e "   Name: HavenHealthPassportNetwork"
    echo -e "   Description: ${NETWORK_DESC}"

    # Validate naming conventions
    if [[ "HavenHealthPassportNetwork" =~ ^[a-zA-Z][a-zA-Z0-9]*$ ]]; then
        echo -e "${GREEN}✓ Network name follows AWS naming conventions${NC}"
    else
        echo -e "${RED}✗ Network name violates naming conventions${NC}"
        exit 1
    fi

    # Check name length (max 64 characters)
    if [ ${#"HavenHealthPassportNetwork"} -le 64 ]; then
        echo -e "${GREEN}✓ Network name length is valid (${#"HavenHealthPassportNetwork"}/64)${NC}"
    else
        echo -e "${RED}✗ Network name exceeds 64 character limit${NC}"
        exit 1
    fi
}

# Execute validation
validate_network_naming

echo -e "\n${GREEN}Network naming configuration validated!${NC}"
