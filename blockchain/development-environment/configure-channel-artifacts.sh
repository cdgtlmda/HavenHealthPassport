#!/bin/bash
# Configure Channel Artifacts for Hyperledger Fabric
# Haven Health Passport - Development Environment Setup

set -e  # Exit on error

echo "================================================"
echo "Haven Health Passport - Channel Artifacts Setup"
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
if ! command_exists configtxgen; then
    print_error "configtxgen not found. Please run ./install-fabric.sh first"
    exit 1
fi

# Configuration directory
CONFIG_DIR="$HOME/fabric/haven-health-config"
cd $CONFIG_DIR

# Clean up existing channel artifacts
if [ -d "channel-artifacts" ]; then
    print_info "Cleaning existing channel artifacts..."
    rm -rf channel-artifacts/*
else
    mkdir -p channel-artifacts
fi

print_info "Creating channel configuration..."

# Create configtx.yaml
cat > configtx.yaml << 'EOF'
# Configuration for Haven Health Passport Blockchain Network
---
################################################################################
#   ORGANIZATIONS
################################################################################
Organizations:
    - &OrdererOrg
        Name: OrdererOrg
        ID: OrdererMSP
        MSPDir: crypto-config/ordererOrganizations/havenhealth.com/msp

        Policies:
            Readers:
                Type: Signature
                Rule: "OR('OrdererMSP.member')"
            Writers:
                Type: Signature
                Rule: "OR('OrdererMSP.member')"
            Admins:
                Type: Signature
                Rule: "OR('OrdererMSP.admin')"

    - &HavenHealth
        Name: HavenHealthMSP
        ID: HavenHealthMSP
        MSPDir: crypto-config/peerOrganizations/havenhealth.com/msp

        Policies:
            Readers:
                Type: Signature
                Rule: "OR('HavenHealthMSP.admin', 'HavenHealthMSP.peer', 'HavenHealthMSP.client')"
            Writers:
                Type: Signature
                Rule: "OR('HavenHealthMSP.admin', 'HavenHealthMSP.client')"
            Admins:
                Type: Signature
                Rule: "OR('HavenHealthMSP.admin')"
            Endorsement:
                Type: Signature
                Rule: "OR('HavenHealthMSP.peer')"

        # Anchor peers for gossip protocol
        AnchorPeers:
            - Host: peer0.havenhealth.com
              Port: 7051

################################################################################
#   CAPABILITIES
################################################################################
Capabilities:
    Channel: &ChannelCapabilities
        V2_0: true

    Orderer: &OrdererCapabilities
        V2_0: true

    Application: &ApplicationCapabilities
        V2_0: true

################################################################################
#   APPLICATION
################################################################################
Application: &ApplicationDefaults
    Organizations:

    Policies:
        Readers:
            Type: ImplicitMeta
            Rule: "ANY Readers"
        Writers:
            Type: ImplicitMeta
            Rule: "ANY Writers"
        Admins:
            Type: ImplicitMeta
            Rule: "MAJORITY Admins"
        LifecycleEndorsement:
            Type: ImplicitMeta
            Rule: "MAJORITY Endorsement"
        Endorsement:
            Type: ImplicitMeta
            Rule: "MAJORITY Endorsement"

    Capabilities:
        <<: *ApplicationCapabilities

################################################################################
#   ORDERER
################################################################################
Orderer: &OrdererDefaults
    OrdererType: etcdraft

    Addresses:
        - orderer.havenhealth.com:7050

    # Batch Timeout and Size
    BatchTimeout: 2s
    BatchSize:
        MaxMessageCount: 10
        AbsoluteMaxBytes: 99 MB
        PreferredMaxBytes: 512 KB

    EtcdRaft:
        Consenters:
            - Host: orderer.havenhealth.com
              Port: 7050
              ClientTLSCert: crypto-config/ordererOrganizations/havenhealth.com/orderers/orderer.havenhealth.com/tls/server.crt
              ServerTLSCert: crypto-config/ordererOrganizations/havenhealth.com/orderers/orderer.havenhealth.com/tls/server.crt

    Organizations:

    Policies:
        Readers:
            Type: ImplicitMeta
            Rule: "ANY Readers"
        Writers:
            Type: ImplicitMeta
            Rule: "ANY Writers"
        Admins:
            Type: ImplicitMeta
            Rule: "MAJORITY Admins"
        BlockValidation:
            Type: ImplicitMeta
            Rule: "ANY Writers"

    Capabilities:
        <<: *OrdererCapabilities

################################################################################
#   CHANNEL
################################################################################
Channel: &ChannelDefaults
    Policies:
        Readers:
            Type: ImplicitMeta
            Rule: "ANY Readers"
        Writers:
            Type: ImplicitMeta
            Rule: "ANY Writers"
        Admins:
            Type: ImplicitMeta
            Rule: "MAJORITY Admins"

    Capabilities:
        <<: *ChannelCapabilities

################################################################################
#   PROFILES
################################################################################
Profiles:
    # Genesis block for ordering service
    HavenHealthGenesis:
        <<: *ChannelDefaults
        Orderer:
            <<: *OrdererDefaults
            Organizations:
                - *OrdererOrg
            Capabilities:
                <<: *OrdererCapabilities
        Consortiums:
            HealthConsortium:
                Organizations:
                    - *HavenHealth

    # Channel creation profile
    HealthChannel:
        Consortium: HealthConsortium
        <<: *ChannelDefaults
        Application:
            <<: *ApplicationDefaults
            Organizations:
                - *HavenHealth
            Capabilities:
                <<: *ApplicationCapabilities
EOF

print_status "Channel configuration created"

# Create genesis block
print_info "Creating genesis block..."
configtxgen -profile HavenHealthGenesis -channelID system-channel -outputBlock ./channel-artifacts/genesis.block

if [ $? -eq 0 ]; then
    print_status "Genesis block created successfully"
else
    print_error "Genesis block creation failed"
    exit 1
fi

# Generate channel configuration transaction
CHANNEL_NAME="healthchannel"
print_info "Generating channel configuration for $CHANNEL_NAME..."
configtxgen -profile HealthChannel -outputCreateChannelTx ./channel-artifacts/${CHANNEL_NAME}.tx -channelID $CHANNEL_NAME

if [ $? -eq 0 ]; then
    print_status "Channel configuration created successfully"
else
    print_error "Channel configuration creation failed"
    exit 1
fi

# Set up anchor peers
print_info "Setting up anchor peer configuration..."
configtxgen -profile HealthChannel -outputAnchorPeersUpdate ./channel-artifacts/HavenHealthMSPanchors.tx -channelID $CHANNEL_NAME -asOrg HavenHealthMSP

if [ $? -eq 0 ]; then
    print_status "Anchor peer configuration created successfully"
else
    print_error "Anchor peer configuration creation failed"
    exit 1
fi

# Configure gossip protocol settings
print_info "Creating gossip protocol configuration..."
cat > core.yaml << 'EOF'
# Gossip Protocol Configuration
peer:
    gossip:
        bootstrap: peer0.havenhealth.com:7051
        useLeaderElection: true
        orgLeader: false
        membershipTrackerInterval: 5s
        endpoint:
        maxBlockCountToStore: 100
        maxPropagationBurstLatency: 10ms
        maxPropagationBurstSize: 10
        propagateIterations: 1
        propagatePeerNum: 3
        pullInterval: 4s
        pullPeerNum: 3
        requestStateInfoInterval: 4s
        publishStateInfoInterval: 4s
        stateInfoRetentionInterval:
        publishCertPeriod: 10s
        skipBlockVerification: false
        dialTimeout: 3s
        connTimeout: 2s
        recvBuffSize: 20
        sendBuffSize: 200
        digestWaitTime: 1s
        requestWaitTime: 1500ms
        responseWaitTime: 2s
        aliveTimeInterval: 5s
        aliveExpirationTimeout: 25s
        reconnectInterval: 25s
        externalEndpoint:
        election:
            startupGracePeriod: 15s
            membershipSampleInterval: 1s
            leaderAliveThreshold: 10s
            leaderElectionDuration: 5s
EOF

print_status "Gossip protocol configuration created"

# Create development network configuration
print_info "Creating development network docker-compose file..."
cat > docker-compose-dev.yaml << 'EOF'
version: '3.7'

volumes:
  orderer.havenhealth.com:
  peer0.havenhealth.com:
  peer1.havenhealth.com:

networks:
  haven-health:
    name: haven-health-network

services:
  orderer.havenhealth.com:
    container_name: orderer.havenhealth.com
    image: hyperledger/fabric-orderer:latest
    environment:
      - FABRIC_LOGGING_SPEC=INFO
      - ORDERER_GENERAL_LISTENADDRESS=0.0.0.0
      - ORDERER_GENERAL_LISTENPORT=7050
      - ORDERER_GENERAL_GENESISMETHOD=file
      - ORDERER_GENERAL_GENESISFILE=/var/hyperledger/orderer/orderer.genesis.block
      - ORDERER_GENERAL_LOCALMSPID=OrdererMSP
      - ORDERER_GENERAL_LOCALMSPDIR=/var/hyperledger/orderer/msp
      - ORDERER_GENERAL_TLS_ENABLED=true
      - ORDERER_GENERAL_TLS_PRIVATEKEY=/var/hyperledger/orderer/tls/server.key
      - ORDERER_GENERAL_TLS_CERTIFICATE=/var/hyperledger/orderer/tls/server.crt
      - ORDERER_GENERAL_TLS_ROOTCAS=[/var/hyperledger/orderer/tls/ca.crt]
      - ORDERER_GENERAL_CLUSTER_CLIENTCERTIFICATE=/var/hyperledger/orderer/tls/server.crt
      - ORDERER_GENERAL_CLUSTER_CLIENTPRIVATEKEY=/var/hyperledger/orderer/tls/server.key
      - ORDERER_GENERAL_CLUSTER_ROOTCAS=[/var/hyperledger/orderer/tls/ca.crt]
    working_dir: /opt/gopath/src/github.com/hyperledger/fabric
    command: orderer
    volumes:
      - ./channel-artifacts/genesis.block:/var/hyperledger/orderer/orderer.genesis.block
      - ./crypto-config/ordererOrganizations/havenhealth.com/orderers/orderer.havenhealth.com/msp:/var/hyperledger/orderer/msp
      - ./crypto-config/ordererOrganizations/havenhealth.com/orderers/orderer.havenhealth.com/tls/:/var/hyperledger/orderer/tls
      - orderer.havenhealth.com:/var/hyperledger/production/orderer
    ports:
      - 7050:7050
    networks:
      - haven-health

  peer0.havenhealth.com:
    container_name: peer0.havenhealth.com
    image: hyperledger/fabric-peer:latest
    environment:
      - CORE_VM_ENDPOINT=unix:///host/var/run/docker.sock
      - CORE_VM_DOCKER_HOSTCONFIG_NETWORKMODE=haven-health-network
      - FABRIC_LOGGING_SPEC=INFO
      - CORE_PEER_TLS_ENABLED=true
      - CORE_PEER_PROFILE_ENABLED=true
      - CORE_PEER_TLS_CERT_FILE=/etc/hyperledger/fabric/tls/server.crt
      - CORE_PEER_TLS_KEY_FILE=/etc/hyperledger/fabric/tls/server.key
      - CORE_PEER_TLS_ROOTCERT_FILE=/etc/hyperledger/fabric/tls/ca.crt
      - CORE_PEER_ID=peer0.havenhealth.com
      - CORE_PEER_ADDRESS=peer0.havenhealth.com:7051
      - CORE_PEER_LISTENADDRESS=0.0.0.0:7051
      - CORE_PEER_CHAINCODEADDRESS=peer0.havenhealth.com:7052
      - CORE_PEER_CHAINCODELISTENADDRESS=0.0.0.0:7052
      - CORE_PEER_GOSSIP_BOOTSTRAP=peer1.havenhealth.com:8051
      - CORE_PEER_GOSSIP_EXTERNALENDPOINT=peer0.havenhealth.com:7051
      - CORE_PEER_LOCALMSPID=HavenHealthMSP
    volumes:
      - /var/run/docker.sock:/host/var/run/docker.sock
      - ./crypto-config/peerOrganizations/havenhealth.com/peers/peer0.havenhealth.com/msp:/etc/hyperledger/fabric/msp
      - ./crypto-config/peerOrganizations/havenhealth.com/peers/peer0.havenhealth.com/tls:/etc/hyperledger/fabric/tls
      - peer0.havenhealth.com:/var/hyperledger/production
    working_dir: /opt/gopath/src/github.com/hyperledger/fabric/peer
    command: peer node start
    ports:
      - 7051:7051
    depends_on:
      - orderer.havenhealth.com
    networks:
      - haven-health
EOF

print_status "Development network configuration created"

# Verify artifacts
print_info "Verifying channel artifacts..."

ARTIFACTS=(
    "channel-artifacts/genesis.block"
    "channel-artifacts/${CHANNEL_NAME}.tx"
    "channel-artifacts/HavenHealthMSPanchors.tx"
)

for artifact in "${ARTIFACTS[@]}"; do
    if [ -f "$artifact" ]; then
        print_status "$artifact created"
        ls -lh "$artifact"
    else
        print_error "$artifact missing"
    fi
done

# Create test script
print_info "Creating network test script..."
cat > test-local-network.sh << 'EOF'
#!/bin/bash
# Test local development network

echo "Starting Haven Health development network..."

# Start network
docker-compose -f docker-compose-dev.yaml up -d

# Wait for network to start
echo "Waiting for network to start..."
sleep 10

# Check container status
docker ps

# Check logs
echo "Checking orderer logs..."
docker logs orderer.havenhealth.com | tail -10

echo "Checking peer0 logs..."
docker logs peer0.havenhealth.com | tail -10

echo ""
echo "To stop the network: docker-compose -f docker-compose-dev.yaml down"
echo "To view logs: docker logs -f <container-name>"
EOF

chmod +x test-local-network.sh
print_status "Test script created"

# Display summary
echo ""
print_status "Channel artifacts configuration complete!"
echo ""
print_info "Generated artifacts:"
echo "  - Configuration file: configtx.yaml"
echo "  - Genesis block: channel-artifacts/genesis.block"
echo "  - Channel transaction: channel-artifacts/${CHANNEL_NAME}.tx"
echo "  - Anchor peer update: channel-artifacts/HavenHealthMSPanchors.tx"
echo "  - Core configuration: core.yaml"
echo "  - Docker compose file: docker-compose-dev.yaml"
echo "  - Test script: test-local-network.sh"
echo ""
echo "Development Environment Setup completed successfully!"
echo ""
echo "Next: Proceed to Smart Contract Development"
