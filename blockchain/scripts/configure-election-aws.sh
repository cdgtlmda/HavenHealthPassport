#!/bin/bash

# Configure Election Parameters for AWS Managed Blockchain
# Haven Health Passport - Raft Consensus Configuration

set -e

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Haven Health Passport - Election Parameters Configuration${NC}"
echo "========================================================"
echo ""

# Configuration variables
NETWORK_ID="${HAVEN_NETWORK_ID}"
MEMBER_ID="${HAVEN_MEMBER_ID}"
CONFIG_PATH="../config/consensus/election-parameters.yaml"

# Election parameter values (in milliseconds)
ELECTION_TIMEOUT=5000
HEARTBEAT_INTERVAL=500
ELECTION_TICK=10
HEARTBEAT_TICK=1
MAX_INFLIGHT_BLOCKS=5

echo -e "${YELLOW}Configuring election parameters...${NC}"

# Function to update orderer environment variables
configure_orderer_env() {
    local ORDERER_ID=$1
    echo "Configuring orderer: $ORDERER_ID"

    # Set Raft election parameters via environment variables
    aws managedblockchain update-node \
        --network-id "$NETWORK_ID" \
        --member-id "$MEMBER_ID" \
        --node-id "$ORDERER_ID" \
        --node-configuration "{
            \"StateDB\": \"CouchDB\",
            \"LogPublishingConfiguration\": {
                \"Fabric\": {
                    \"PeerLogs\": {
                        \"Cloudwatch\": {
                            \"Enabled\": true
                        }
                    }
                }
            }
        }"
}
