#!/bin/bash

# Haven Health Passport - CloudWatch Logging Configuration
# This script configures CloudWatch logging for blockchain components

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${SCRIPT_DIR}/../config"
LOG_RETENTION_DAYS=${LOG_RETENTION_DAYS:-30}

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}CloudWatch Logging Configuration${NC}"
echo -e "${BLUE}================================================${NC}"

# Function to configure log groups
configure_log_groups() {
    echo -e "\n📋 Configuring CloudWatch log groups..."

    # Load network info
    if [ ! -f "${CONFIG_DIR}/network-info.json" ]; then
        echo -e "${RED}Error: Network info not found${NC}"
        exit 1
    fi

    NETWORK_ID=$(jq -r '.NetworkId' "${CONFIG_DIR}/network-info.json")
    MEMBER_ID=$(jq -r '.MemberId' "${CONFIG_DIR}/network-info.json")

    # Define log groups
    LOG_GROUPS=(
        "/aws/managedblockchain/${NETWORK_ID}/${MEMBER_ID}/ca"
        "/aws/managedblockchain/${NETWORK_ID}/${MEMBER_ID}/peer"
        "/aws/managedblockchain/${NETWORK_ID}/${MEMBER_ID}/chaincode"
    )

    # Create log groups
    for LOG_GROUP in "${LOG_GROUPS[@]}"; do
        echo -e "\n📁 Creating log group: ${LOG_GROUP}"

        # Check if log group exists
        if aws logs describe-log-groups --log-group-name-prefix "${LOG_GROUP}" | grep -q "${LOG_GROUP}"; then
            echo -e "${YELLOW}Log group already exists${NC}"
        else
            aws logs create-log-group --log-group-name "${LOG_GROUP}"
            echo -e "${GREEN}✓ Log group created${NC}"
        fi

        # Set retention policy
        aws logs put-retention-policy \
            --log-group-name "${LOG_GROUP}" \
            --retention-in-days ${LOG_RETENTION_DAYS}

        echo -e "${GREEN}✓ Retention policy set to ${LOG_RETENTION_DAYS} days${NC}"
    done
}

# Create logging configuration file
create_logging_config() {
    cat > "${CONFIG_DIR}/logging-configuration.json" <<EOF
{
    "logGroups": {
        "ca": "/aws/managedblockchain/${NETWORK_ID}/${MEMBER_ID}/ca",
        "peer": "/aws/managedblockchain/${NETWORK_ID}/${MEMBER_ID}/peer",
        "chaincode": "/aws/managedblockchain/${NETWORK_ID}/${MEMBER_ID}/chaincode"
    },
    "retentionDays": ${LOG_RETENTION_DAYS},
    "logLevels": {
        "ca": "INFO",
        "peer": "INFO",
        "chaincode": "DEBUG"
    }
}
EOF
    echo -e "\n${GREEN}✓ Logging configuration saved${NC}"
}

# Execute functions
configure_log_groups
create_logging_config

echo -e "\n${GREEN}CloudWatch logging configuration completed!${NC}"
