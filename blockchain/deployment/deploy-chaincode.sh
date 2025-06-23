#!/bin/bash
# Chaincode Deployment Script for Haven Health Passport
# This script handles the deployment of all smart contracts to AWS Managed Blockchain

set -e

# Configuration
NETWORK_ID="${AWS_BLOCKCHAIN_NETWORK_ID}"
MEMBER_ID="${AWS_BLOCKCHAIN_MEMBER_ID}"
CHANNEL_NAME="${CHANNEL_NAME:-havenchannel}"
CHAINCODE_VERSION="${CHAINCODE_VERSION:-1.0.0}"
SEQUENCE="${SEQUENCE:-1}"
LOG_DIR="./logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${2}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$LOG_DIR/deployment_${TIMESTAMP}.log"
}

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to check prerequisites
check_prerequisites() {
    log "Checking prerequisites..." "$YELLOW"

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log "AWS CLI not found. Please install AWS CLI." "$RED"
        exit 1
    fi

    # Check environment variables
    if [[ -z "$NETWORK_ID" || -z "$MEMBER_ID" ]]; then
        log "Missing required environment variables. Please set AWS_BLOCKCHAIN_NETWORK_ID and AWS_BLOCKCHAIN_MEMBER_ID" "$RED"
        exit 1
    fi

    log "Prerequisites check passed" "$GREEN"
}

# Function to package chaincode
package_chaincode() {
    local chaincode_name=$1
    local chaincode_path=$2

    log "Packaging chaincode: $chaincode_name" "$YELLOW"

    cd "$chaincode_path"

    # Build the chaincode
    go mod vendor

    # Create package
    peer lifecycle chaincode package "${chaincode_name}.tar.gz" \
        --path . \
        --lang golang \
        --label "${chaincode_name}_${CHAINCODE_VERSION}"

    # Move package to deployment directory
    mv "${chaincode_name}.tar.gz" "$OLDPWD/$LOG_DIR/"

    cd "$OLDPWD"

    log "Chaincode packaged successfully: ${chaincode_name}.tar.gz" "$GREEN"
}

# Function to install chaincode on peer
install_chaincode() {
    local chaincode_name=$1

    log "Installing chaincode: $chaincode_name on peer" "$YELLOW"

    # Get package ID
    PACKAGE_ID=$(peer lifecycle chaincode calculatepackageid "$LOG_DIR/${chaincode_name}.tar.gz")

    # Install chaincode
    peer lifecycle chaincode install "$LOG_DIR/${chaincode_name}.tar.gz"

    # Save package ID for later use
    echo "$PACKAGE_ID" > "$LOG_DIR/${chaincode_name}_package_id.txt"

    log "Chaincode installed. Package ID: $PACKAGE_ID" "$GREEN"
}

# Function to approve chaincode
approve_chaincode() {
    local chaincode_name=$1
    local package_id=$2

    log "Approving chaincode: $chaincode_name" "$YELLOW"

    peer lifecycle chaincode approveformyorg \
        --channelID "$CHANNEL_NAME" \
        --name "$chaincode_name" \
        --version "$CHAINCODE_VERSION" \
        --package-id "$package_id" \
        --sequence "$SEQUENCE" \
        --tls \
        --cafile "$ORDERER_CA"

    log "Chaincode approved for organization" "$GREEN"
}

# Function to commit chaincode
commit_chaincode() {
    local chaincode_name=$1

    log "Committing chaincode: $chaincode_name" "$YELLOW"

    peer lifecycle chaincode commit \
        --channelID "$CHANNEL_NAME" \
        --name "$chaincode_name" \
        --version "$CHAINCODE_VERSION" \
        --sequence "$SEQUENCE" \
        --tls \
        --cafile "$ORDERER_CA" \
        --peerAddresses "$PEER_ADDRESS" \
        --tlsRootCertFiles "$PEER_TLS_CERT"

    log "Chaincode committed to channel" "$GREEN"
}

# Function to verify deployment
verify_deployment() {
    local chaincode_name=$1

    log "Verifying deployment of: $chaincode_name" "$YELLOW"

    # Query committed chaincode
    peer lifecycle chaincode querycommitted \
        --channelID "$CHANNEL_NAME" \
        --name "$chaincode_name" \
        --output json > "$LOG_DIR/${chaincode_name}_deployment_info.json"

    # Test invoke
    peer chaincode invoke \
        --channelID "$CHANNEL_NAME" \
        --name "$chaincode_name" \
        --ctor '{"function":"InitLedger","Args":[]}' \
        --tls \
        --cafile "$ORDERER_CA" \
        --peerAddresses "$PEER_ADDRESS" \
        --tlsRootCertFiles "$PEER_TLS_CERT" \
        --waitForEvent

    log "Deployment verified successfully" "$GREEN"
}

# Function to deploy all contracts
deploy_all_contracts() {
    log "Starting deployment of all contracts" "$YELLOW"

    # Deploy each contract
    for contract in "health_record" "verification" "access_control"; do
        log "Deploying $contract Contract" "$YELLOW"
        package_chaincode "$contract" "../../contracts/chaincode/health-records"
        install_chaincode "$contract"
        PACKAGE_ID=$(cat "$LOG_DIR/${contract}_package_id.txt")
        approve_chaincode "$contract" "$PACKAGE_ID"
        commit_chaincode "$contract"
        verify_deployment "$contract"
    done
}

# Function to generate deployment report
generate_deployment_report() {
    log "Generating deployment report" "$YELLOW"

    cat > "$LOG_DIR/deployment_report_${TIMESTAMP}.json" <<EOF
{
    "deployment_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "network_id": "$NETWORK_ID",
    "member_id": "$MEMBER_ID",
    "channel_name": "$CHANNEL_NAME",
    "chaincode_version": "$CHAINCODE_VERSION",
    "sequence": "$SEQUENCE",
    "deployed_contracts": [
        {
            "name": "health_record",
            "package_id": "$(cat $LOG_DIR/health_record_package_id.txt 2>/dev/null || echo 'N/A')",
            "status": "deployed"
        },
        {
            "name": "verification",
            "package_id": "$(cat $LOG_DIR/verification_package_id.txt 2>/dev/null || echo 'N/A')",
            "status": "deployed"
        },
        {
            "name": "access_control",
            "package_id": "$(cat $LOG_DIR/access_control_package_id.txt 2>/dev/null || echo 'N/A')",
            "status": "deployed"
        }
    ],
    "deployment_logs": "deployment_${TIMESTAMP}.log"
}
EOF

    log "Deployment report generated: deployment_report_${TIMESTAMP}.json" "$GREEN"
}

# Main execution
main() {
    log "Haven Health Passport Chaincode Deployment Script" "$GREEN"
    log "================================================" "$GREEN"

    check_prerequisites
    deploy_all_contracts
    generate_deployment_report

    log "Deployment completed successfully!" "$GREEN"
    log "Check logs in: $LOG_DIR" "$YELLOW"
}

# Run main function
main "$@"
