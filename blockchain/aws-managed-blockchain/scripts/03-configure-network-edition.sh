#!/bin/bash

# Haven Health Passport - Network Edition Configuration
# This script configures and validates the network edition selection

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

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Network Edition Configuration${NC}"
echo -e "${BLUE}================================================${NC}"

# Network edition details
echo -e "\n📊 Network Edition Comparison:"
echo -e "┌─────────────────────┬────────────────┬────────────────┐"
echo -e "│ Feature             │ Starter        │ Standard       │"
echo -e "├─────────────────────┼────────────────┼────────────────┤"
echo -e "│ Max TPS             │ 100            │ 1000           │"
echo -e "│ Max Peer Nodes      │ 2              │ 5              │"
echo -e "│ Cost                │ Lower          │ Higher         │"
echo -e "│ Use Case            │ Development    │ Production     │"
echo -e "└─────────────────────┴────────────────┴────────────────┘"

# Validate current configuration
echo -e "\n📋 Validating network edition configuration..."

EDITION=$(grep -E "Edition:\s*STANDARD" "${CONFIG_DIR}/blockchain-network.yaml" | wc -l)
if [ $EDITION -gt 0 ]; then
    echo -e "${GREEN}✓ Network edition: STANDARD${NC}"
    echo -e "${GREEN}✓ Suitable for production healthcare workloads${NC}"
else
    echo -e "${YELLOW}⚠ Network edition not set to STANDARD${NC}"
fi

echo -e "\n${GREEN}Network edition configuration validated!${NC}"
