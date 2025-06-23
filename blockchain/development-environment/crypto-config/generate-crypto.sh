#!/bin/bash

# Haven Health Passport - Generate Crypto Material Script
# This script generates certificates and keys for the blockchain network

set -e

# Configuration
FABRIC_CFG_PATH=${FABRIC_CFG_PATH:-$HOME/fabric-samples/config}
CRYPTOGEN_PATH=${CRYPTOGEN_PATH:-$HOME/fabric-samples/bin/cryptogen}

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# Change to script directory
cd "$(dirname "$0")"

print_header "Generating Crypto Material for Haven Health Passport"

# Check if cryptogen exists
if [ ! -f "$CRYPTOGEN_PATH" ]; then
    print_error "cryptogen not found at $CRYPTOGEN_PATH"
    print_error "Please run ./install-fabric.sh first"
    exit 1
fi

# Clean up old crypto material
if [ -d "peerOrganizations" ]; then    print_warning "Removing existing crypto material..."
    rm -rf peerOrganizations ordererOrganizations
fi

# Generate crypto material
print_status "Generating crypto material using crypto-config.yaml..."
$CRYPTOGEN_PATH generate --config=crypto-config.yaml

# Verify generation
print_header "Verifying Crypto Material Generation"

# Check orderer organizations
if [ -d "ordererOrganizations" ]; then
    print_status "Orderer organizations created:"
    ls -la ordererOrganizations/
else
    print_error "Orderer organizations not created"
    exit 1
fi

# Check peer organizations
if [ -d "peerOrganizations" ]; then
    print_status "Peer organizations created:"
    ls -la peerOrganizations/
else
    print_error "Peer organizations not created"
    exit 1
fi

# Display MSP structure
print_header "MSP Structure for HavenHealthFoundation"
tree -L 3 peerOrganizations/havenhealthfoundation.com/msp/ 2>/dev/null || {
    print_warning "tree command not found, using ls instead"
    find peerOrganizations/havenhealthfoundation.com/msp/ -type d | head -20
}

# Create summary report
print_header "Creating Crypto Material Report"
cat > crypto-material-report.txt <<EOF
Crypto Material Generation Report
Generated: $(date)

Orderer Organizations:
$(ls ordererOrganizations/ 2>/dev/null | sed 's/^/  - /')

Peer Organizations:
$(ls peerOrganizations/ 2>/dev/null | sed 's/^/  - /')

Orderer Nodes:$(find ordererOrganizations/*/orderers -type d -maxdepth 1 -mindepth 1 2>/dev/null | xargs -I {} basename {} | sed 's/^/  - /')

Peer Nodes:
$(find peerOrganizations/*/peers -type d -maxdepth 1 -mindepth 1 2>/dev/null | xargs -I {} basename {} | sed 's/^/  - /')

Admin Users:
$(find . -name "Admin@*" -type d 2>/dev/null | xargs -I {} basename {} | sed 's/^/  - /')

Certificate Types Generated:
  - TLS CA certificates
  - MSP CA certificates
  - Admin certificates
  - Peer certificates
  - Orderer certificates

Configuration Used: crypto-config.yaml
EOF

print_status "Report saved to crypto-material-report.txt"

# Set permissions
print_header "Setting Appropriate Permissions"
find . -name "*_sk" -type f -exec chmod 600 {} \;
find . -name "*.pem" -type f -exec chmod 644 {} \;

print_header "Crypto Material Generation Complete"
print_status "Crypto material generated in:"
print_status "  - ordererOrganizations/"
print_status "  - peerOrganizations/"
print_warning "Keep the private keys secure and never commit them to version control!"
print_status "Next step: Configure channel artifacts"
