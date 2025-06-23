#!/bin/bash
# Create Crypto Material for Hyperledger Fabric
# Haven Health Passport - Development Environment Setup

set -e  # Exit on error

echo "================================================"
echo "Haven Health Passport - Crypto Material Setup"
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
if ! command_exists cryptogen; then
    print_error "cryptogen not found. Please run ./install-fabric.sh first"
    exit 1
fi

# Configuration directory
CONFIG_DIR="$HOME/fabric/haven-health-config"
cd $CONFIG_DIR

# Clean up existing crypto material
if [ -d "crypto-config" ]; then
    print_info "Removing existing crypto material..."
    rm -rf crypto-config
fi

print_info "Creating crypto configuration..."

# Create cryptogen configuration file
cat > crypto-config.yaml << 'EOF'
# Crypto Config for Haven Health Passport
# This file contains the configuration for cryptogen tool

# OrdererOrgs defines the organizations that will serve as orderers
OrdererOrgs:
  - Name: Orderer
    Domain: havenhealth.com
    EnableNodeOUs: true

    # Specs is an array of Orderer Specs
    Specs:
      - Hostname: orderer
        SANS:
          - localhost
          - 127.0.0.1

# PeerOrgs defines the peer organizations
PeerOrgs:
  - Name: HavenHealth
    Domain: havenhealth.com
    EnableNodeOUs: true

    # CA defines the certificate authority
    CA:
      Hostname: ca
      Country: US
      Province: California
      Locality: San Francisco
      OrganizationalUnit: Haven Health Passport
      StreetAddress: 123 Blockchain Ave
      PostalCode: 94102

    # Template defines how many peers to generate
    Template:
      Count: 2
      SANS:
        - localhost
        - 127.0.0.1
        - havenhealth.com

    # Users defines additional users for the organization
    Users:
      Count: 3  # In addition to Admin user
EOF

print_status "Crypto configuration created"

# Generate certificates
print_info "Generating certificates..."
cryptogen generate --config=crypto-config.yaml --output=crypto-config

if [ $? -eq 0 ]; then
    print_status "Certificates generated successfully"
else
    print_error "Certificate generation failed"
    exit 1
fi

# Set up MSP structure
print_info "Setting up MSP structure..."

# Function to setup MSP
setup_msp() {
    local org_path=$1
    local org_name=$2

    print_info "Setting up MSP for $org_name..."

    # Create config.yaml for NodeOUs
    for msp_path in $(find $org_path -name msp -type d); do
        cat > $msp_path/config.yaml << EEOF
NodeOUs:
  Enable: true
  ClientOUIdentifier:
    Certificate: cacerts/ca.havenhealth.com-cert.pem
    OrganizationalUnitIdentifier: client
  PeerOUIdentifier:
    Certificate: cacerts/ca.havenhealth.com-cert.pem
    OrganizationalUnitIdentifier: peer
  AdminOUIdentifier:
    Certificate: cacerts/ca.havenhealth.com-cert.pem
    OrganizationalUnitIdentifier: admin
  OrdererOUIdentifier:
    Certificate: cacerts/ca.havenhealth.com-cert.pem
    OrganizationalUnitIdentifier: orderer
EEOF
    done
}

# Set up MSP for peer organizations
setup_msp "crypto-config/peerOrganizations/havenhealth.com" "HavenHealth"

# Set up MSP for orderer organizations
setup_msp "crypto-config/ordererOrganizations/havenhealth.com" "Orderer"

print_status "MSP structure configured"

# Create directory structure documentation
print_info "Creating MSP structure documentation..."

cat > msp-structure.md << 'EOF'
# MSP Directory Structure

## Peer Organization MSP Structure
```
crypto-config/peerOrganizations/havenhealth.com/
├── ca/                      # Certificate Authority certificates
├── msp/                     # Organization MSP
│   ├── admincerts/         # Admin certificates
│   ├── cacerts/            # Root CA certificates
│   ├── config.yaml         # NodeOU configuration
│   ├── intermediatecerts/  # Intermediate CA certificates (if any)
│   ├── keystore/           # Private keys (CA)
│   ├── signcerts/          # Signing certificates
│   └── tlscacerts/         # TLS CA certificates
├── peers/                   # Peer nodes
│   ├── peer0.havenhealth.com/
│   │   ├── msp/            # Peer MSP
│   │   └── tls/            # Peer TLS certificates
│   └── peer1.havenhealth.com/
│       ├── msp/
│       └── tls/
├── tlsca/                  # TLS Certificate Authority
└── users/                  # User identities
    ├── Admin@havenhealth.com/
    │   ├── msp/
    │   └── tls/
    └── User1@havenhealth.com/
        ├── msp/
        └── tls/
```

## Orderer Organization MSP Structure
```
crypto-config/ordererOrganizations/havenhealth.com/
├── ca/
├── msp/
├── orderers/
│   └── orderer.havenhealth.com/
│       ├── msp/
│       └── tls/
├── tlsca/
└── users/
    └── Admin@havenhealth.com/
        ├── msp/
        └── tls/
```
EOF

print_status "MSP documentation created"

# Verify crypto material
print_info "Verifying crypto material..."

# Check key directories
DIRS_TO_CHECK=(
    "crypto-config/peerOrganizations/havenhealth.com/ca"
    "crypto-config/peerOrganizations/havenhealth.com/peers"
    "crypto-config/peerOrganizations/havenhealth.com/users"
    "crypto-config/ordererOrganizations/havenhealth.com/orderers"
)

for dir in "${DIRS_TO_CHECK[@]}"; do
    if [ -d "$dir" ]; then
        print_status "$dir exists"
    else
        print_error "$dir missing"
    fi
done

# Display summary
echo ""
print_status "Crypto material generation complete!"
echo ""
print_info "Generated artifacts:"
echo "  - Crypto configuration: crypto-config.yaml"
echo "  - Certificates: crypto-config/"
echo "  - MSP structure documentation: msp-structure.md"
echo ""
print_info "Certificate Summary:"
find crypto-config -name "*.pem" -type f | wc -l | xargs echo "  Total certificates generated:"
find crypto-config -name "*_sk" -type f | wc -l | xargs echo "  Total private keys generated:"
echo ""
echo "Next step: Run ./configure-channel-artifacts.sh to create channel configuration"

# Make next script executable
chmod +x configure-channel-artifacts.sh 2>/dev/null || true
