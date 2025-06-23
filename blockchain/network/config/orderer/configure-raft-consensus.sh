#!/bin/bash

# Copyright Haven Health Passport. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# Script to configure and initialize Raft consensus for Haven Health Passport blockchain

set -e

echo "=========================================="
echo "Configuring Raft Consensus for Haven Health Passport"
echo "=========================================="

# Set environment variables
export FABRIC_CFG_PATH=${PWD}/../config
export CHANNEL_NAME=healthcare-channel
export CORE_PEER_TLS_ENABLED=true

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
print_status "Checking prerequisites..."

if ! command_exists configtxgen; then
    print_error "configtxgen not found. Please ensure Fabric binaries are installed and in PATH."
    exit 1
fi
if ! command_exists docker; then
    print_error "Docker not found. Please install Docker."
    exit 1
fi

# Create necessary directories
print_status "Creating directory structure..."

mkdir -p ../genesis
mkdir -p ../channel-artifacts
mkdir -p ../crypto-config

# Generate genesis block for Raft ordering service
print_status "Generating genesis block with Raft configuration..."

configtxgen -profile RaftOrdererGenesis \
    -channelID system-channel \
    -outputBlock ../genesis/genesis.block \
    -configPath .

if [ $? -ne 0 ]; then
    print_error "Failed to generate genesis block"
    exit 1
fi

print_status "Genesis block created successfully"

# Generate channel configuration transaction
print_status "Generating channel configuration transaction..."

configtxgen -profile HealthcareChannel \
    -channelID $CHANNEL_NAME \
    -outputCreateChannelTx ../channel-artifacts/${CHANNEL_NAME}.tx \
    -configPath .

if [ $? -ne 0 ]; then
    print_error "Failed to generate channel configuration"
    exit 1
fi

print_status "Channel configuration created successfully"

# Generate anchor peer transactions for each organization
print_status "Generating anchor peer transactions..."

# Healthcare Provider 1
configtxgen -profile HealthcareChannel \
    -channelID $CHANNEL_NAME \
    -outputAnchorPeersUpdate ../channel-artifacts/HealthcareProvider1MSPanchors.tx \
    -asOrg HealthcareProvider1MSP \
    -configPath .
# Healthcare Provider 2
configtxgen -profile HealthcareChannel \
    -channelID $CHANNEL_NAME \
    -outputAnchorPeersUpdate ../channel-artifacts/HealthcareProvider2MSPanchors.tx \
    -asOrg HealthcareProvider2MSP \
    -configPath .

# Refugee Organization
configtxgen -profile HealthcareChannel \
    -channelID $CHANNEL_NAME \
    -outputAnchorPeersUpdate ../channel-artifacts/RefugeeOrgMSPanchors.tx \
    -asOrg RefugeeOrgMSP \
    -configPath .

# UNHCR Organization
configtxgen -profile HealthcareChannel \
    -channelID $CHANNEL_NAME \
    -outputAnchorPeersUpdate ../channel-artifacts/UNHCROrgMSPanchors.tx \
    -asOrg UNHCROrgMSP \
    -configPath .

print_status "Anchor peer transactions created successfully"

# Function to verify Raft configuration
verify_raft_config() {
    print_status "Verifying Raft consensus configuration..."

    # Check if configtx.yaml exists
    if [ ! -f "./configtx.yaml" ]; then
        print_error "configtx.yaml not found"
        return 1
    fi

    # Check if OrdererType is set to etcdraft
    if grep -q "OrdererType: etcdraft" ./configtx.yaml; then
        print_status "Raft consensus type confirmed in configuration"
    else
        print_error "Raft consensus type not found in configuration"
        return 1
    fi

    # Count number of consenters
    consenter_count=$(grep -c "Host:" ./configtx.yaml | head -5 | wc -l)
    print_status "Found $consenter_count Raft consenters configured"

    return 0
}
# Function to display Raft configuration summary
display_raft_summary() {
    echo ""
    echo "=========================================="
    echo "Raft Consensus Configuration Summary"
    echo "=========================================="
    echo "Consensus Type: etcdraft"
    echo "Number of Orderers: 5"
    echo "Election Tick: 10"
    echo "Heartbeat Tick: 1"
    echo "Max Inflight Blocks: 5"
    echo "Snapshot Interval: 100 MB"
    echo "Batch Timeout: 2s"
    echo "Max Message Count: 500"
    echo "Channel Name: $CHANNEL_NAME"
    echo "=========================================="
}

# Run verification
verify_raft_config

if [ $? -eq 0 ]; then
    print_status "Raft consensus configuration verified successfully"
else
    print_error "Raft consensus configuration verification failed"
    exit 1
fi

# Display configuration summary
display_raft_summary

# Create startup script for Raft orderers
print_status "Creating Raft orderer startup script..."

cat > start-raft-orderers.sh << 'EOF'
#!/bin/bash
# Start all Raft orderer nodes

echo "Starting Raft orderer cluster..."
docker-compose -f docker-compose-orderer-raft.yaml up -d

# Wait for orderers to start
sleep 5

# Check status
docker-compose -f docker-compose-orderer-raft.yaml ps

echo "Raft orderer cluster started"
EOF

chmod +x start-raft-orderers.sh

print_status "Configuration complete!"
print_status "To start the Raft orderer cluster, run: ./start-raft-orderers.sh"
