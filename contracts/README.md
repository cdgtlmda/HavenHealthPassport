# Haven Health Passport Smart Contracts

## Overview

This directory contains the Hyperledger Fabric chaincode (smart contracts) for the Haven Health Passport blockchain network.

## Prerequisites

1. **Hyperledger Fabric** (v2.5+)
   ```bash
   curl -sSL https://bit.ly/2ysbOFE | bash -s
   ```

2. **Go** (v1.19+)
   ```bash
   # On macOS
   brew install go
   ```

3. **Docker** and **Docker Compose**

## Chaincode Structure

### health-records/
The main chaincode for managing health records on the blockchain:
- `main.go` - Entry point for the chaincode
- `health_records.go` - Core smart contract logic
- `go.mod` - Go module dependencies

## Setting Up the Blockchain Network

### 1. Start the Fabric Test Network

```bash
# Clone fabric-samples if not already done
cd ~
git clone https://github.com/hyperledger/fabric-samples.git
cd fabric-samples
git checkout v2.5.0

# Start the test network
cd test-network
./network.sh up createChannel -ca
```

### 2. Deploy Haven Health Chaincode

```bash
# From the Haven Health Passport root directory
cd /path/to/HavenHealthPassport

# Package the chaincode
peer lifecycle chaincode package health-records.tar.gz \
  --path ./contracts/health-records \
  --lang golang \
  --label health_records_1.0

# Install on Org1 peer
export CORE_PEER_TLS_ENABLED=true
export CORE_PEER_LOCALMSPID="Org1MSP"
export CORE_PEER_TLS_ROOTCERT_FILE=${PWD}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt
export CORE_PEER_MSPCONFIGPATH=${PWD}/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp
export CORE_PEER_ADDRESS=localhost:7051

peer lifecycle chaincode install health-records.tar.gz

# Install on Org2 peer
export CORE_PEER_LOCALMSPID="Org2MSP"
export CORE_PEER_TLS_ROOTCERT_FILE=${PWD}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt
export CORE_PEER_MSPCONFIGPATH=${PWD}/organizations/peerOrganizations/org2.example.com/users/Admin@org2.example.com/msp
export CORE_PEER_ADDRESS=localhost:9051

peer lifecycle chaincode install health-records.tar.gz
```

### 3. Approve and Commit Chaincode

```bash
# Get the package ID
peer lifecycle chaincode queryinstalled

# Approve for Org1
export CC_PACKAGE_ID=<PACKAGE_ID_FROM_ABOVE>
peer lifecycle chaincode approveformyorg -o localhost:7050 \
  --ordererTLSHostnameOverride orderer.example.com \
  --channelID mychannel \
  --name health_records \
  --version 1.0 \
  --package-id $CC_PACKAGE_ID \
  --sequence 1 \
  --tls \
  --cafile ${PWD}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem

# Check readiness
peer lifecycle chaincode checkcommitreadiness \
  --channelID mychannel \
  --name health_records \
  --version 1.0 \
  --sequence 1 \
  --tls \
  --cafile ${PWD}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem \
  --output json

# Commit the chaincode
peer lifecycle chaincode commit -o localhost:7050 \
  --ordererTLSHostnameOverride orderer.example.com \
  --channelID mychannel \
  --name health_records \
  --version 1.0 \
  --sequence 1 \
  --tls \
  --cafile ${PWD}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem \
  --peerAddresses localhost:7051 \
  --tlsRootCertFiles ${PWD}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt \
  --peerAddresses localhost:9051 \
  --tlsRootCertFiles ${PWD}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt
```

## Testing the Chaincode

### Create a Health Record

```bash
peer chaincode invoke -o localhost:7050 \
  --ordererTLSHostnameOverride orderer.example.com \
  --tls \
  --cafile ${PWD}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem \
  -C mychannel \
  -n health_records \
  --peerAddresses localhost:7051 \
  --tlsRootCertFiles ${PWD}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt \
  --peerAddresses localhost:9051 \
  --tlsRootCertFiles ${PWD}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt \
  -c '{"function":"CreateHealthRecord","Args":["record1","patient123","vaccination","hash123","provider456","Haven Clinic","QmXxx..."]}'
```

### Query a Health Record

```bash
peer chaincode query -C mychannel \
  -n health_records \
  -c '{"function":"ReadHealthRecord","Args":["record1"]}'
```

### Query by Patient ID

```bash
peer chaincode query -C mychannel \
  -n health_records \
  -c '{"function":"GetHealthRecordsByPatient","Args":["patient123"]}'
```

## Production Deployment

For production deployment:

1. Use proper CA certificates (not test certificates)
2. Configure proper MSP for organizations
3. Set up proper ordering service (Raft consensus)
4. Enable mutual TLS
5. Configure proper access control policies
6. Set up monitoring and logging
7. Implement proper key management

## Troubleshooting

### Common Issues

1. **Chaincode installation fails**
   - Ensure Go is installed and GOPATH is set
   - Check Docker daemon is running
   - Verify fabric binaries are in PATH

2. **Network not accessible**
   - Check if all containers are running: `docker ps`
   - Check logs: `docker logs peer0.org1.example.com`
   - Ensure ports are not already in use

3. **Permission errors**
   - Run with proper user permissions
   - Check file ownership in mounted volumes

### Useful Commands

```bash
# View all containers
docker ps -a

# View chaincode logs
docker logs <chaincode-container-name>

# Stop the network
./network.sh down

# Clean everything (including volumes)
./network.sh down && docker volume prune -f
```

## Security Considerations

- All health data is encrypted before storing on blockchain
- Only record hashes and metadata are stored on-chain
- Actual health data is stored in IPFS with encryption
- Access control is enforced at chaincode level
- Patient always maintains access to their own records