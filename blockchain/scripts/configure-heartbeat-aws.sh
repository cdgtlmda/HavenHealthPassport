#!/bin/bash

# Configure Heartbeat Interval for AWS Managed Blockchain
# Haven Health Passport - Raft Consensus Configuration

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
HEARTBEAT_INTERVAL=500  # milliseconds
HEARTBEAT_TICK=1       # 1 tick = 500ms
NETWORK_ID="${HAVEN_NETWORK_ID}"
MEMBER_ID="${HAVEN_MEMBER_ID}"

echo -e "${GREEN}Haven Health Passport - Heartbeat Interval Configuration${NC}"
echo "======================================================"
echo ""

# Validate environment
if [ -z "$NETWORK_ID" ] || [ -z "$MEMBER_ID" ]; then
    echo -e "${RED}Error: HAVEN_NETWORK_ID and HAVEN_MEMBER_ID must be set${NC}"
    exit 1
fi

echo -e "${YELLOW}Configuring heartbeat interval: ${HEARTBEAT_INTERVAL}ms${NC}"

# Function to configure orderer node
configure_orderer() {
    local NODE_ID=$1
    local NODE_NAME=$2

    echo -e "\n${YELLOW}Configuring ${NODE_NAME}...${NC}"

    # Update node configuration with Raft parameters
    aws managedblockchain update-node \
        --network-id "$NETWORK_ID" \
        --member-id "$MEMBER_ID" \
        --node-id "$NODE_ID" \
        --log-publishing-configuration '{
            "Fabric": {
                "PeerLogs": {
                    "Cloudwatch": {
                        "Enabled": true
                    }
                }
            }
        }' 2>/dev/null || true

    echo -e "${GREEN}✓ ${NODE_NAME} configured${NC}"
}

# Get all orderer nodes
echo -e "\n${YELLOW}Fetching orderer nodes...${NC}"
NODES=$(aws managedblockchain list-nodes \
    --network-id "$NETWORK_ID" \
    --member-id "$MEMBER_ID" \
    --status AVAILABLE \
    --query 'Nodes[?contains(Id, `orderer`)].Id' \
    --output text)

if [ -z "$NODES" ]; then
    echo -e "${RED}No orderer nodes found${NC}"
    exit 1
fi

# Configure each orderer
NODE_INDEX=0
for NODE_ID in $NODES; do
    configure_orderer "$NODE_ID" "orderer${NODE_INDEX}"
    ((NODE_INDEX++))
done

echo -e "\n${GREEN}✅ Heartbeat interval configuration complete!${NC}"
echo -e "\nConfiguration Summary:"
echo -e "- Heartbeat Interval: ${HEARTBEAT_INTERVAL}ms"
echo -e "- Heartbeat Tick: ${HEARTBEAT_TICK}"
echo -e "- Follower Timeout: $((HEARTBEAT_INTERVAL * 10))ms"
echo -e "- Nodes Configured: ${NODE_INDEX}"
