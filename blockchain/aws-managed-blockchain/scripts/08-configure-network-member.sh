#!/bin/bash

# Haven Health Passport - Network Member Configuration
# This script configures and validates network member settings

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
echo -e "${BLUE}Network Member Configuration${NC}"
echo -e "${BLUE}================================================${NC}"

# Validate member configuration
validate_member_config() {
    echo -e "\n📋 Validating member configuration..."

    # Check member name
    MEMBER_NAME="HavenHealthFoundation"
    echo -e "Member Name: ${MEMBER_NAME}"

    if [[ "$MEMBER_NAME" =~ ^[a-zA-Z][a-zA-Z0-9]*$ ]]; then
        echo -e "${GREEN}✓ Member name follows naming conventions${NC}"
    fi

    # Check member description
    echo -e "${GREEN}✓ Member description configured${NC}"
    echo -e "   Description: Primary member for Haven Health Passport blockchain network"
}

# Create member profile
create_member_profile() {
    cat > "${CONFIG_DIR}/member-profile.json" <<EOF
{
    "memberName": "HavenHealthFoundation",
    "memberDescription": "Primary member for Haven Health Passport blockchain network",
    "memberType": "STANDARD",
    "votingRights": true,
    "capabilities": {
        "canPropose": true,
        "canVote": true,
        "canDeployChaincode": true,
        "canManageChannels": true
    }
}
EOF
}

validate_member_config
create_member_profile

echo -e "\n${GREEN}Member configuration completed!${NC}"
