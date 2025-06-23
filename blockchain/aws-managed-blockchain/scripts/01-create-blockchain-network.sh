#!/bin/bash

# Haven Health Passport - AWS Managed Blockchain Network Creation Script
# This script implements the complete network creation process as per checklist item 1.1

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${SCRIPT_DIR}/../config"
LOGS_DIR="${SCRIPT_DIR}/../logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOGS_DIR}/network_creation_${TIMESTAMP}.log"

# Create logs directory if it doesn't exist
mkdir -p "${LOGS_DIR}"

# Function to log messages
log() {
    echo -e "${1}" | tee -a "${LOG_FILE}"
}

# Function to log errors
log_error() {
    echo -e "${RED}[ERROR] ${1}${NC}" | tee -a "${LOG_FILE}"
}

# Function to log success
log_success() {
    echo -e "${GREEN}[SUCCESS] ${1}${NC}" | tee -a "${LOG_FILE}"
}

# Function to log warnings
log_warning() {
    echo -e "${YELLOW}[WARNING] ${1}${NC}" | tee -a "${LOG_FILE}"
}

# Checklist item validation function
validate_checklist_item() {
    local item_name="$1"
    local validation_command="$2"

    log "\n📋 Validating: ${item_name}"

    if eval "${validation_command}"; then
        log_success "✓ ${item_name} - Validated"
        return 0
    else
        log_error "✗ ${item_name} - Validation failed"
        return 1
    fi
}

# Main function to create blockchain network
create_blockchain_network() {
    log "=========================================="
    log "Haven Health Passport - Blockchain Network Creation"
    log "Started at: $(date)"
    log "=========================================="

    # Check AWS CLI installation
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install AWS CLI first."
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Please configure AWS credentials."
        exit 1
    fi

    # Load configuration
    STACK_NAME="${BLOCKCHAIN_STACK_NAME:-HavenHealthPassportBlockchain}"
    NETWORK_NAME="${NETWORK_NAME:-HavenHealthPassportNetwork}"
    ADMIN_USERNAME="${ADMIN_USERNAME:-HavenAdmin}"
    MEMBER_NAME="${MEMBER_NAME:-HavenHealthFoundation}"

    # Prompt for admin password if not set
    if [ -z "${ADMIN_PASSWORD:-}" ]; then
        read -s -p "Enter admin password (min 8 characters): " ADMIN_PASSWORD
        echo
    fi

    # Validate password length
    if [ ${#ADMIN_PASSWORD} -lt 8 ]; then
        log_error "Password must be at least 8 characters long"
        exit 1
    fi

    log "\n📋 Starting AWS Managed Blockchain Network Creation"
    log "Stack Name: ${STACK_NAME}"
    log "Network Name: ${NETWORK_NAME}"

    # Deploy CloudFormation stack
    log "\n🚀 Deploying CloudFormation stack..."

    aws cloudformation deploy \
        --template-file "${CONFIG_DIR}/blockchain-network.yaml" \
        --stack-name "${STACK_NAME}" \
        --parameter-overrides \
            NetworkName="${NETWORK_NAME}" \
            AdminUsername="${ADMIN_USERNAME}" \
            AdminPassword="${ADMIN_PASSWORD}" \
            MemberName="${MEMBER_NAME}" \
        --capabilities CAPABILITY_IAM \
        2>&1 | tee -a "${LOG_FILE}"

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        log_success "CloudFormation stack deployed successfully"
    else
        log_error "CloudFormation stack deployment failed"
        exit 1
    fi

    # Get stack outputs
    log "\n📊 Retrieving network information..."

    NETWORK_ID=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --query "Stacks[0].Outputs[?OutputKey=='NetworkId'].OutputValue" \
        --output text)

    MEMBER_ID=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --query "Stacks[0].Outputs[?OutputKey=='MemberId'].OutputValue" \
        --output text)

    log "Network ID: ${NETWORK_ID}"
    log "Member ID: ${MEMBER_ID}"

    # Save network information
    cat > "${CONFIG_DIR}/network-info.json" <<EOF
{
    "NetworkId": "${NETWORK_ID}",
    "NetworkName": "${NETWORK_NAME}",
    "MemberId": "${MEMBER_ID}",
    "MemberName": "${MEMBER_NAME}",
    "StackName": "${STACK_NAME}",
    "CreatedAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

    log_success "Network information saved to ${CONFIG_DIR}/network-info.json"

    # Verify network creation
    log "\n🔍 Verifying network creation..."

    NETWORK_STATUS=$(aws managedblockchain get-network \
        --network-id "${NETWORK_ID}" \
        --query "Network.Status" \
        --output text 2>/dev/null || echo "NOT_FOUND")

    if [ "${NETWORK_STATUS}" = "AVAILABLE" ]; then
        log_success "Network is AVAILABLE and ready to use"
    elif [ "${NETWORK_STATUS}" = "CREATING" ]; then
        log_warning "Network is still being created. Please wait for it to become AVAILABLE."
    else
        log_error "Network status: ${NETWORK_STATUS}"
        exit 1
    fi

    log "\n=========================================="
    log "Network creation process completed"
    log "Completed at: $(date)"
    log "=========================================="
}

# Execute main function
create_blockchain_network
