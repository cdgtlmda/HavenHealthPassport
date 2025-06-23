#!/bin/bash
# Haven Health Passport - Generate Channel Artifacts Script
# This script generates the genesis block and channel configuration

set -e

# Configuration
FABRIC_CFG_PATH=${FABRIC_CFG_PATH:-$HOME/fabric-samples/config}
CONFIGTXGEN_PATH=${CONFIGTXGEN_PATH:-$HOME/fabric-samples/bin/configtxgen}
CHANNEL_NAME="havenhealthchannel"

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

print_header "Generating Channel Artifacts for Haven Health Passport"

# Check if configtxgen exists
if [ ! -f "$CONFIGTXGEN_PATH" ]; then
    print_error "configtxgen not found at $CONFIGTXGEN_PATH"
    print_error "Please run ./install-fabric.sh first"
    exit 1
fi

# Export FABRIC_CFG_PATH to current directory
export FABRIC_CFG_PATH=$PWD
print_status "FABRIC_CFG_PATH set to: $FABRIC_CFG_PATH"

# Create artifacts directory if it doesn't exist
mkdir -p artifacts

# Generate genesis block
print_header "Generating Genesis Block"
print_status "Creating genesis block for HavenHealthGenesis profile..."

$CONFIGTXGEN_PATH -profile HavenHealthGenesis -channelID system-channel -outputBlock ./artifacts/genesis.block

if [ -f "./artifacts/genesis.block" ]; then
    print_status "Genesis block created successfully"
else
    print_error "Failed to create genesis block"
    exit 1
fi

# Generate channel configuration transaction
print_header "Generating Channel Configuration Transaction"
print_status "Creating channel configuration for $CHANNEL_NAME..."

$CONFIGTXGEN_PATH -profile HavenHealthChannel -outputCreateChannelTx ./artifacts/${CHANNEL_NAME}.tx -channelID $CHANNEL_NAME

if [ -f "./artifacts/${CHANNEL_NAME}.tx" ]; then
    print_status "Channel configuration transaction created successfully"
else
    print_error "Failed to create channel configuration transaction"
    exit 1
fi

# Generate anchor peer updates
print_header "Generating Anchor Peer Updates"
print_status "Creating anchor peer update for HavenHealthFoundation..."

$CONFIGTXGEN_PATH -profile HavenHealthChannel -outputAnchorPeersUpdate ./artifacts/HavenHealthFoundationMSPanchors.tx -channelID $CHANNEL_NAME -asOrg HavenHealthFoundationMSP

if [ -f "./artifacts/HavenHealthFoundationMSPanchors.tx" ]; then
    print_status "Anchor peer update created successfully"
else
    print_error "Failed to create anchor peer update"
    exit 1
fi

# List generated artifacts
print_header "Generated Artifacts"
ls -la ./artifacts/
# Create summary report
cat > channel-artifacts-report.txt <<EOF
Channel Artifacts Generation Report
Generated: $(date)

Channel Name: $CHANNEL_NAME
Genesis Profile: HavenHealthGenesis
Channel Profile: HavenHealthChannel

Generated Files:
- genesis.block: System channel genesis block
- ${CHANNEL_NAME}.tx: Channel creation transaction
- HavenHealthFoundationMSPanchors.tx: Anchor peer configuration

Configuration Used:
- configtx.yaml
- FABRIC_CFG_PATH: $FABRIC_CFG_PATH

Next Steps:
1. Use genesis.block to bootstrap orderer nodes
2. Use ${CHANNEL_NAME}.tx to create the application channel
3. Use anchor peer updates after joining peers to channel
EOF

print_status "Report saved to channel-artifacts-report.txt"

print_header "Channel Artifacts Generation Complete"
print_status "All artifacts generated in ./artifacts/"
print_warning "Keep these files secure - they contain network configuration"
print_status "Next step: Set up anchor peers and configure gossip protocol"
