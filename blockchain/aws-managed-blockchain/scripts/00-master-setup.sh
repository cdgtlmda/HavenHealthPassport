#!/bin/bash

# Haven Health Passport - Master Setup Script
# This script runs all AWS Managed Blockchain configuration scripts in order

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Haven Health Passport - Blockchain Setup${NC}"
echo -e "${BLUE}================================================${NC}"

# Make all scripts executable
echo -e "\n📋 Making scripts executable..."
chmod +x "${SCRIPT_DIR}"/*.sh
chmod +x "${SCRIPT_DIR}"/*.py

# Function to run a script with confirmation
run_script() {
    local script_name="$1"
    local description="$2"

    echo -e "\n${YELLOW}────────────────────────────────────────${NC}"
    echo -e "${BLUE}Script: ${script_name}${NC}"
    echo -e "${BLUE}Purpose: ${description}${NC}"
    echo -e "${YELLOW}────────────────────────────────────────${NC}"

    read -p "Run this script? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}Running ${script_name}...${NC}\n"
        "${SCRIPT_DIR}/${script_name}"
        echo -e "\n${GREEN}✓ Completed${NC}"
    else
        echo -e "${YELLOW}Skipped${NC}"
    fi
}

# Display checklist status
echo -e "\n${BLUE}AWS Managed Blockchain Configuration Checklist:${NC}"
echo -e "[ ] Create AWS Managed Blockchain network"
echo -e "[ ] Select Hyperledger Fabric framework"
echo -e "[ ] Configure network edition (Standard or Starter)"
echo -e "[ ] Set network name and description"
echo -e "[ ] Configure voting policy for network"
echo -e "[ ] Set approval threshold percentage"
echo -e "[ ] Define proposal duration in hours"
echo -e "[ ] Create admin user and password"
echo -e "[ ] Configure certificate authority"
echo -e "[ ] Set up network member configuration"
echo -e "[ ] Define member name and description"
echo -e "[ ] Configure admin user for member"
echo -e "[ ] Create peer node configuration"
echo -e "[ ] Select instance type for peer nodes"
echo -e "[ ] Configure availability zone"
echo -e "[ ] Enable peer node logging"
echo -e "[ ] Set up CloudWatch log groups"
echo -e "[ ] Configure log retention period"
echo -e "[ ] Create VPC endpoint for network"
echo -e "[ ] Set up security groups"
echo -e "[ ] Configure network ACLs"
echo -e "[ ] Enable VPC flow logs"
echo -e "[ ] Document network configuration"
echo -e "[ ] Create network diagram"
echo -e "[ ] Record all configuration decisions"

echo -e "\n${YELLOW}This master script will guide you through each step.${NC}"
echo -e "${YELLOW}You can skip scripts that have already been run.${NC}"

# Run scripts in order
run_script "01-create-blockchain-network.sh" "Create AWS Managed Blockchain network with initial configuration"
run_script "02-validate-framework-selection.sh" "Validate Hyperledger Fabric framework selection"
run_script "03-configure-network-edition.sh" "Configure and validate network edition (STANDARD)"
run_script "04-validate-network-naming.sh" "Validate network name and description"
run_script "05-configure-voting-policy.sh" "Configure voting policy and governance rules"
run_script "06-configure-admin-user.sh" "Set up admin user configuration and security"
run_script "07-configure-certificate-authority.sh" "Document certificate authority configuration"
run_script "08-configure-network-member.sh" "Configure network member settings"
run_script "09-configure-peer-node.sh" "Deploy and configure peer nodes"
run_script "10-configure-cloudwatch-logging.sh" "Set up CloudWatch logging and retention"
run_script "11-deploy-vpc-configuration.sh" "Deploy VPC endpoint, security groups, and ACLs"
run_script "12-document-network-configuration.sh" "Generate comprehensive network documentation"
run_script "13-create-network-diagram.py" "Create visual network architecture diagrams"
run_script "14-record-configuration-decisions.sh" "Record all configuration decisions"

echo -e "\n${GREEN}================================================${NC}"
echo -e "${GREEN}AWS Managed Blockchain Configuration Complete!${NC}"
echo -e "${GREEN}================================================${NC}"

echo -e "\n${BLUE}Next Steps:${NC}"
echo -e "1. Review generated documentation in the docs/ directory"
echo -e "2. Verify network is in AVAILABLE state"
echo -e "3. Proceed to Development Environment Setup"
echo -e "4. Begin smart contract development"

echo -e "\n${BLUE}Verification Commands:${NC}"
echo -e "aws managedblockchain list-networks"
echo -e "aws managedblockchain list-members --network-id <NETWORK_ID>"
echo -e "aws managedblockchain list-nodes --network-id <NETWORK_ID> --member-id <MEMBER_ID>"
