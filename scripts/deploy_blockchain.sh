#!/bin/bash

# Haven Health Passport - Hyperledger Fabric Deployment Script
# This script deploys the blockchain network for health record verification

set -e

echo "================================================"
echo "Haven Health Passport Blockchain Deployment"
echo "================================================"

# Configuration
export FABRIC_VERSION=2.5.0
export CA_VERSION=1.5.5
export CHANNEL_NAME=healthcare-channel
export CHAINCODE_NAME=health-records
export CHAINCODE_VERSION=1.0
export CHAINCODE_PATH=./chaincode/health-records

# Check prerequisites
check_prerequisites() {
    echo "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo "Error: Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo "Error: Docker Compose is not installed"
        exit 1
    fi
    
    # Check Go (for chaincode)
    if ! command -v go &> /dev/null; then
        echo "Warning: Go is not installed. Required for chaincode development"
    fi
    
    echo "Prerequisites check passed!"
}

# Download Fabric binaries
download_fabric_binaries() {
    echo "Downloading Hyperledger Fabric binaries..."
    
    if [ ! -d "fabric-samples" ]; then
        curl -sSL https://bit.ly/2ysbOFE | bash -s -- ${FABRIC_VERSION} ${CA_VERSION} -s
    else
        echo "Fabric binaries already downloaded"
    fi
    
    export PATH=$PWD/fabric-samples/bin:$PATH
    export FABRIC_CFG_PATH=$PWD/fabric-samples/config/
}

# Generate crypto materials
generate_crypto_materials() {
    echo "Generating crypto materials..."
    
    # Create crypto-config.yaml
    cat > crypto-config.yaml <<EOF
OrdererOrgs:
  - Name: Orderer
    Domain: havenhealthpassport.org
    EnableNodeOUs: true
    Specs:
      - Hostname: orderer
        SANS:
          - localhost
          - 127.0.0.1

PeerOrgs:
  - Name: Org1
    Domain: org1.havenhealthpassport.org
    EnableNodeOUs: true
    Template:
      Count: 2
    Users:
      Count: 1
EOF

    # Generate certificates
    cryptogen generate --config=./crypto-config.yaml --output="crypto-config"
    
    echo "Crypto materials generated successfully"
}

# Generate genesis block
generate_genesis_block() {
    echo "Generating genesis block..."
    
    # Create configtx.yaml
    cat > configtx.yaml <<EOF
Organizations:
    - &OrdererOrg
        Name: OrdererOrg
        ID: OrdererMSP
        MSPDir: crypto-config/ordererOrganizations/havenhealthpassport.org/msp
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

    - &Org1
        Name: Org1MSP
        ID: Org1MSP
        MSPDir: crypto-config/peerOrganizations/org1.havenhealthpassport.org/msp
        Policies:
            Readers:
                Type: Signature
                Rule: "OR('Org1MSP.admin', 'Org1MSP.peer', 'Org1MSP.client')"
            Writers:
                Type: Signature
                Rule: "OR('Org1MSP.admin', 'Org1MSP.client')"
            Admins:
                Type: Signature
                Rule: "OR('Org1MSP.admin')"
            Endorsement:
                Type: Signature
                Rule: "OR('Org1MSP.peer')"

Capabilities:
    Channel: &ChannelCapabilities
        V2_0: true
    Orderer: &OrdererCapabilities
        V2_0: true
    Application: &ApplicationCapabilities
        V2_0: true

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

Orderer: &OrdererDefaults
    OrdererType: etcdraft
    Addresses:
        - orderer.havenhealthpassport.org:7050
    EtcdRaft:
        Consenters:
        - Host: orderer.havenhealthpassport.org
          Port: 7050
          ClientTLSCert: crypto-config/ordererOrganizations/havenhealthpassport.org/orderers/orderer.havenhealthpassport.org/tls/server.crt
          ServerTLSCert: crypto-config/ordererOrganizations/havenhealthpassport.org/orderers/orderer.havenhealthpassport.org/tls/server.crt
    BatchTimeout: 2s
    BatchSize:
        MaxMessageCount: 10
        AbsoluteMaxBytes: 99 MB
        PreferredMaxBytes: 512 KB
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

Profiles:
    HealthcareOrdererGenesis:
        <<: *ChannelDefaults
        Orderer:
            <<: *OrdererDefaults
            Organizations:
                - *OrdererOrg
            Capabilities:
                <<: *OrdererCapabilities
        Consortiums:
            HealthcareConsortium:
                Organizations:
                    - *Org1
    HealthcareChannel:
        Consortium: HealthcareConsortium
        <<: *ChannelDefaults
        Application:
            <<: *ApplicationDefaults
            Organizations:
                - *Org1
            Capabilities:
                <<: *ApplicationCapabilities
EOF

    # Generate genesis block
    configtxgen -profile HealthcareOrdererGenesis -channelID system-channel -outputBlock ./channel-artifacts/genesis.block
    
    # Generate channel configuration
    configtxgen -profile HealthcareChannel -outputCreateChannelTx ./channel-artifacts/${CHANNEL_NAME}.tx -channelID ${CHANNEL_NAME}
    
    # Generate anchor peer transactions
    configtxgen -profile HealthcareChannel -outputAnchorPeersUpdate ./channel-artifacts/Org1MSPanchors.tx -channelID ${CHANNEL_NAME} -asOrg Org1MSP
    
    echo "Genesis block and channel configuration generated"
}

# Create docker-compose file
create_docker_compose() {
    echo "Creating docker-compose configuration..."
    
    cat > docker-compose-blockchain.yaml <<EOF
version: '3.7'

networks:
  healthcare:
    name: healthcare-network

services:
  orderer.havenhealthpassport.org:
    container_name: orderer.havenhealthpassport.org
    image: hyperledger/fabric-orderer:${FABRIC_VERSION}
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
        - ./crypto-config/ordererOrganizations/havenhealthpassport.org/orderers/orderer.havenhealthpassport.org/msp:/var/hyperledger/orderer/msp
        - ./crypto-config/ordererOrganizations/havenhealthpassport.org/orderers/orderer.havenhealthpassport.org/tls/:/var/hyperledger/orderer/tls
        - orderer.havenhealthpassport.org:/var/hyperledger/production/orderer
    ports:
      - 7050:7050
    networks:
      - healthcare

  peer0.org1.havenhealthpassport.org:
    container_name: peer0.org1.havenhealthpassport.org
    image: hyperledger/fabric-peer:${FABRIC_VERSION}
    environment:
      - CORE_VM_ENDPOINT=unix:///host/var/run/docker.sock
      - CORE_VM_DOCKER_HOSTCONFIG_NETWORKMODE=healthcare-network
      - FABRIC_LOGGING_SPEC=INFO
      - CORE_PEER_TLS_ENABLED=true
      - CORE_PEER_PROFILE_ENABLED=true
      - CORE_PEER_TLS_CERT_FILE=/etc/hyperledger/fabric/tls/server.crt
      - CORE_PEER_TLS_KEY_FILE=/etc/hyperledger/fabric/tls/server.key
      - CORE_PEER_TLS_ROOTCERT_FILE=/etc/hyperledger/fabric/tls/ca.crt
      - CORE_PEER_ID=peer0.org1.havenhealthpassport.org
      - CORE_PEER_ADDRESS=peer0.org1.havenhealthpassport.org:7051
      - CORE_PEER_LISTENADDRESS=0.0.0.0:7051
      - CORE_PEER_CHAINCODEADDRESS=peer0.org1.havenhealthpassport.org:7052
      - CORE_PEER_CHAINCODELISTENADDRESS=0.0.0.0:7052
      - CORE_PEER_GOSSIP_BOOTSTRAP=peer1.org1.havenhealthpassport.org:8051
      - CORE_PEER_GOSSIP_EXTERNALENDPOINT=peer0.org1.havenhealthpassport.org:7051
      - CORE_PEER_LOCALMSPID=Org1MSP
      - CORE_OPERATIONS_LISTENADDRESS=0.0.0.0:9443
    volumes:
        - /var/run/docker.sock:/host/var/run/docker.sock
        - ./crypto-config/peerOrganizations/org1.havenhealthpassport.org/peers/peer0.org1.havenhealthpassport.org/msp:/etc/hyperledger/fabric/msp
        - ./crypto-config/peerOrganizations/org1.havenhealthpassport.org/peers/peer0.org1.havenhealthpassport.org/tls:/etc/hyperledger/fabric/tls
        - peer0.org1.havenhealthpassport.org:/var/hyperledger/production
    working_dir: /opt/gopath/src/github.com/hyperledger/fabric/peer
    command: peer node start
    ports:
      - 7051:7051
      - 9443:9443
    networks:
      - healthcare
    depends_on:
      - orderer.havenhealthpassport.org

  peer1.org1.havenhealthpassport.org:
    container_name: peer1.org1.havenhealthpassport.org
    image: hyperledger/fabric-peer:${FABRIC_VERSION}
    environment:
      - CORE_VM_ENDPOINT=unix:///host/var/run/docker.sock
      - CORE_VM_DOCKER_HOSTCONFIG_NETWORKMODE=healthcare-network
      - FABRIC_LOGGING_SPEC=INFO
      - CORE_PEER_TLS_ENABLED=true
      - CORE_PEER_PROFILE_ENABLED=true
      - CORE_PEER_TLS_CERT_FILE=/etc/hyperledger/fabric/tls/server.crt
      - CORE_PEER_TLS_KEY_FILE=/etc/hyperledger/fabric/tls/server.key
      - CORE_PEER_TLS_ROOTCERT_FILE=/etc/hyperledger/fabric/tls/ca.crt
      - CORE_PEER_ID=peer1.org1.havenhealthpassport.org
      - CORE_PEER_ADDRESS=peer1.org1.havenhealthpassport.org:8051
      - CORE_PEER_LISTENADDRESS=0.0.0.0:8051
      - CORE_PEER_CHAINCODEADDRESS=peer1.org1.havenhealthpassport.org:8052
      - CORE_PEER_CHAINCODELISTENADDRESS=0.0.0.0:8052
      - CORE_PEER_GOSSIP_BOOTSTRAP=peer0.org1.havenhealthpassport.org:7051
      - CORE_PEER_GOSSIP_EXTERNALENDPOINT=peer1.org1.havenhealthpassport.org:8051
      - CORE_PEER_LOCALMSPID=Org1MSP
      - CORE_OPERATIONS_LISTENADDRESS=0.0.0.0:9444
    volumes:
        - /var/run/docker.sock:/host/var/run/docker.sock
        - ./crypto-config/peerOrganizations/org1.havenhealthpassport.org/peers/peer1.org1.havenhealthpassport.org/msp:/etc/hyperledger/fabric/msp
        - ./crypto-config/peerOrganizations/org1.havenhealthpassport.org/peers/peer1.org1.havenhealthpassport.org/tls:/etc/hyperledger/fabric/tls
        - peer1.org1.havenhealthpassport.org:/var/hyperledger/production
    working_dir: /opt/gopath/src/github.com/hyperledger/fabric/peer
    command: peer node start
    ports:
      - 8051:8051
      - 9444:9444
    networks:
      - healthcare
    depends_on:
      - orderer.havenhealthpassport.org

  ca.org1.havenhealthpassport.org:
    image: hyperledger/fabric-ca:${CA_VERSION}
    container_name: ca.org1.havenhealthpassport.org
    environment:
      - FABRIC_CA_HOME=/etc/hyperledger/fabric-ca-server
      - FABRIC_CA_SERVER_CA_NAME=ca-org1
      - FABRIC_CA_SERVER_TLS_ENABLED=true
      - FABRIC_CA_SERVER_PORT=7054
      - FABRIC_CA_SERVER_OPERATIONS_LISTENADDRESS=0.0.0.0:17054
    ports:
      - "7054:7054"
      - "17054:17054"
    command: sh -c 'fabric-ca-server start -b admin:adminpw -d'
    volumes:
      - ./crypto-config/peerOrganizations/org1.havenhealthpassport.org/ca/:/etc/hyperledger/fabric-ca-server
    networks:
      - healthcare

volumes:
  orderer.havenhealthpassport.org:
  peer0.org1.havenhealthpassport.org:
  peer1.org1.havenhealthpassport.org:
EOF

    echo "Docker compose configuration created"
}

# Start the network
start_network() {
    echo "Starting Hyperledger Fabric network..."
    
    # Create necessary directories
    mkdir -p channel-artifacts
    mkdir -p crypto-config
    mkdir -p config/blockchain/wallet
    
    # Start containers
    docker-compose -f docker-compose-blockchain.yaml up -d
    
    # Wait for network to start
    sleep 10
    
    echo "Blockchain network started successfully"
}

# Create and join channel
create_channel() {
    echo "Creating channel ${CHANNEL_NAME}..."
    
    # Create channel
    docker exec -e CORE_PEER_LOCALMSPID=Org1MSP \
        -e CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.havenhealthpassport.org/users/Admin@org1.havenhealthpassport.org/msp \
        peer0.org1.havenhealthpassport.org peer channel create \
        -o orderer.havenhealthpassport.org:7050 \
        -c ${CHANNEL_NAME} \
        -f /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts/${CHANNEL_NAME}.tx \
        --tls --cafile /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/havenhealthpassport.org/orderers/orderer.havenhealthpassport.org/msp/tlscacerts/tlsca.havenhealthpassport.org-cert.pem
    
    # Join peers to channel
    for PEER in peer0 peer1; do
        docker exec -e CORE_PEER_LOCALMSPID=Org1MSP \
            -e CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.havenhealthpassport.org/users/Admin@org1.havenhealthpassport.org/msp \
            ${PEER}.org1.havenhealthpassport.org peer channel join -b ${CHANNEL_NAME}.block
    done
    
    echo "Channel created and peers joined"
}

# Deploy chaincode
deploy_chaincode() {
    echo "Deploying chaincode..."
    
    # Package chaincode
    cd ${CHAINCODE_PATH}/javascript
    npm install
    cd -
    
    peer lifecycle chaincode package ${CHAINCODE_NAME}.tar.gz \
        --path ${CHAINCODE_PATH}/javascript \
        --lang node \
        --label ${CHAINCODE_NAME}_${CHAINCODE_VERSION}
    
    # Install chaincode on peers
    for PEER in peer0 peer1; do
        docker exec ${PEER}.org1.havenhealthpassport.org peer lifecycle chaincode install ${CHAINCODE_NAME}.tar.gz
    done
    
    # Approve chaincode
    PACKAGE_ID=$(docker exec peer0.org1.havenhealthpassport.org peer lifecycle chaincode queryinstalled | grep ${CHAINCODE_NAME} | awk '{print $3}' | cut -d ',' -f1)
    
    docker exec peer0.org1.havenhealthpassport.org peer lifecycle chaincode approveformyorg \
        -o orderer.havenhealthpassport.org:7050 \
        --channelID ${CHANNEL_NAME} \
        --name ${CHAINCODE_NAME} \
        --version ${CHAINCODE_VERSION} \
        --package-id ${PACKAGE_ID} \
        --sequence 1 \
        --tls --cafile /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/havenhealthpassport.org/orderers/orderer.havenhealthpassport.org/msp/tlscacerts/tlsca.havenhealthpassport.org-cert.pem
    
    # Commit chaincode
    docker exec peer0.org1.havenhealthpassport.org peer lifecycle chaincode commit \
        -o orderer.havenhealthpassport.org:7050 \
        --channelID ${CHANNEL_NAME} \
        --name ${CHAINCODE_NAME} \
        --version ${CHAINCODE_VERSION} \
        --sequence 1 \
        --tls --cafile /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/havenhealthpassport.org/orderers/orderer.havenhealthpassport.org/msp/tlscacerts/tlsca.havenhealthpassport.org-cert.pem \
        --peerAddresses peer0.org1.havenhealthpassport.org:7051 \
        --tlsRootCertFiles /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.havenhealthpassport.org/peers/peer0.org1.havenhealthpassport.org/tls/ca.crt
    
    echo "Chaincode deployed successfully"
}

# Initialize chaincode
initialize_chaincode() {
    echo "Initializing chaincode..."
    
    docker exec peer0.org1.havenhealthpassport.org peer chaincode invoke \
        -o orderer.havenhealthpassport.org:7050 \
        --tls --cafile /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/havenhealthpassport.org/orderers/orderer.havenhealthpassport.org/msp/tlscacerts/tlsca.havenhealthpassport.org-cert.pem \
        -C ${CHANNEL_NAME} \
        -n ${CHAINCODE_NAME} \
        -c '{"function":"initLedger","Args":[]}'
    
    echo "Chaincode initialized"
}

# Main execution
main() {
    echo "Starting Haven Health Passport blockchain deployment..."
    
    check_prerequisites
    download_fabric_binaries
    generate_crypto_materials
    generate_genesis_block
    create_docker_compose
    start_network
    create_channel
    deploy_chaincode
    initialize_chaincode
    
    echo "================================================"
    echo "Blockchain deployment completed successfully!"
    echo "================================================"
    echo ""
    echo "Network endpoints:"
    echo "  - Orderer: localhost:7050"
    echo "  - Peer0: localhost:7051"
    echo "  - Peer1: localhost:8051"
    echo "  - CA: localhost:7054"
    echo ""
    echo "Channel: ${CHANNEL_NAME}"
    echo "Chaincode: ${CHAINCODE_NAME} v${CHAINCODE_VERSION}"
    echo ""
    echo "To stop the network: docker-compose -f docker-compose-blockchain.yaml down"
    echo "To view logs: docker-compose -f docker-compose-blockchain.yaml logs -f"
}

# Run main function
main "$@"