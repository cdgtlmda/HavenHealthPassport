#!/bin/bash

# Haven Health Passport - Voting Policy Configuration
# This script configures and validates the voting policy for network governance

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
DOCS_DIR="${SCRIPT_DIR}/../docs"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Voting Policy Configuration${NC}"
echo -e "${BLUE}================================================${NC}"

# Create voting policy documentation
create_voting_policy_doc() {
    cat > "${DOCS_DIR}/voting-policy.md" <<'EOF'
# Haven Health Passport - Blockchain Voting Policy

## Overview
This document defines the voting policy for network governance in the Haven Health Passport blockchain.

## Policy Configuration

### Approval Threshold
- **Threshold Percentage**: 50%
- **Threshold Comparator**: GREATER_THAN
- **Meaning**: Proposals require more than 50% of member votes to pass

### Proposal Duration
- **Duration**: 24 hours
- **Rationale**: Provides sufficient time for review across time zones

### Voting Rights
- All network members have equal voting rights
- One member = one vote
- No proxy voting allowed

### Proposal Types Requiring Votes
1. Adding new network members
2. Removing existing members
3. Network configuration changes
4. Chaincode deployment/upgrade
5. Channel configuration updates

### Emergency Procedures
- Critical security updates: 6-hour voting window
- Emergency member removal: Immediate with 75% threshold
EOF
}

# Validate voting policy
validate_voting_policy() {
    echo -e "\n📋 Validating voting policy configuration..."

    # Check threshold percentage
    THRESHOLD=$(grep -E "ThresholdPercentage:\s*50" "${CONFIG_DIR}/blockchain-network.yaml" | wc -l)
    if [ $THRESHOLD -gt 0 ]; then
        echo -e "${GREEN}✓ Threshold percentage: 50%${NC}"
    fi

    # Check proposal duration
    DURATION=$(grep -E "ProposalDurationInHours:\s*24" "${CONFIG_DIR}/blockchain-network.yaml" | wc -l)
    if [ $DURATION -gt 0 ]; then
        echo -e "${GREEN}✓ Proposal duration: 24 hours${NC}"
    fi

    # Check comparator
    COMPARATOR=$(grep -E "ThresholdComparator:\s*GREATER_THAN" "${CONFIG_DIR}/blockchain-network.yaml" | wc -l)
    if [ $COMPARATOR -gt 0 ]; then
        echo -e "${GREEN}✓ Threshold comparator: GREATER_THAN${NC}"
    fi
}

# Create documentation directory if needed
mkdir -p "${DOCS_DIR}"

# Execute functions
create_voting_policy_doc
validate_voting_policy

echo -e "\n${GREEN}Voting policy configuration completed!${NC}"
echo -e "${GREEN}Documentation created at: ${DOCS_DIR}/voting-policy.md${NC}"
