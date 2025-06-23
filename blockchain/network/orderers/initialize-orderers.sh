#!/bin/bash

# Copyright Haven Health Passport. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# Initialize orderer nodes with genesis block

set -e

echo "=========================================="
echo "Initializing Orderer Nodes"
echo "=========================================="

# Check if genesis block exists
if [ ! -f "../config/genesis/genesis.block" ]; then
    echo "Error: Genesis block not found!"
    echo "Please run the configuration script first."
    exit 1
fi

# Initialize each orderer
for i in $(seq 1 5); do
    ORDERER_NAME="orderer${i}"
    ORDERER_PORT=$((7050 + (i-1)*1000))
    ADMIN_PORT=$((7053 + (i-1)*1000))

    echo "Initializing ${ORDERER_NAME}..."

    # Create channel participation request
    cat > ${ORDERER_NAME}/join-channel.json << EOF
{
    "channelID": "healthcare-channel",
    "consensusType": "etcdraft",
    "configBlock": "genesis.block"
}
EOF

    # Copy genesis block
    cp ../config/genesis/genesis.block ${ORDERER_NAME}/

    echo "${ORDERER_NAME} initialized"
done

echo "All orderer nodes initialized successfully!"
