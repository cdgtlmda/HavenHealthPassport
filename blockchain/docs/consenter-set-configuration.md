# Consenter Set Configuration Documentation
# Haven Health Passport - Blockchain Infrastructure

## Overview

This document describes the consenter set configuration for the Haven Health Passport blockchain network using Hyperledger Fabric's Raft consensus mechanism.

## Consenter Set Definition

A consenter set defines the orderer nodes that participate in the Raft consensus protocol. For Haven Health Passport, we use a 5-node configuration distributed across multiple availability zones for high availability.

## Configuration Structure

### 1. Node Distribution

The 5 consenter nodes are distributed as follows:
- **us-east-1a**: 2 nodes (orderer0, orderer1)
- **us-east-1b**: 2 nodes (orderer2, orderer3)
- **us-east-1c**: 1 node (orderer4)

This distribution ensures:
- Fault tolerance across availability zones
- Quorum maintenance even if one AZ fails
- Geographic distribution for latency optimization

### 2. Node Roles

Each node has a specific role:
- **Primary**: orderer0 - Main leader candidate
- **Secondary**: orderer1, orderer2, orderer3 - Backup leaders
- **Arbiter**: orderer4 - Tie-breaker node

### 3. Consensus Parameters

Key Raft consensus parameters:
- **Quorum Size**: 3 (majority of 5 nodes)
- **Election Timeout**: 10 ticks (5000ms)
- **Heartbeat Interval**: 1 tick (500ms)
- **Max In-flight Blocks**: 5
- **Snapshot Interval**: 20MB

### 4. TLS Configuration

All consenter nodes require:
- Mutual TLS authentication
- Client certificates for peer authentication
- Server certificates for secure communication
- Certificate rotation every 90 days
## Implementation Guide

### Step 1: AWS Managed Blockchain Setup

Configure consenters in AWS Managed Blockchain:

```bash
# Create orderer nodes via AWS CLI
aws managedblockchain create-node \
  --network-id ${NETWORK_ID} \
  --member-id ${MEMBER_ID} \
  --node-configuration '{
    "InstanceType": "bc.m5.xlarge",
    "AvailabilityZone": "us-east-1a",
    "LogPublishingConfiguration": {
      "Fabric": {
        "CaLogs": {
          "Cloudwatch": {
            "Enabled": true
          }
        },
        "PeerLogs": {
          "Cloudwatch": {
            "Enabled": true
          }
        }
      }
    }
  }'
```

### Step 2: Certificate Generation

Generate TLS certificates for each consenter:

```bash
# Generate certificates using Fabric CA
fabric-ca-client enroll \
  -u https://admin:adminpw@ca.havenhealthpassport.com:7054 \
  --caname ca.havenhealthpassport.com \
  -M ${MSP_PATH}/orderer0.havenhealthpassport.com \
  --csr.hosts orderer0.havenhealthpassport.com \
  --tls.certfiles ${CA_CERT}
```

### Step 3: Channel Configuration Update

Update the system channel configuration with consenter set:

```bash
# Fetch current configuration
peer channel fetch config config_block.pb \
  -o orderer.havenhealthpassport.com:7050 \
  -c haven-system-channel \
  --tls --cafile ${ORDERER_CA}

# Decode and modify configuration
configtxlator proto_decode \
  --input config_block.pb \
  --type common.Block | jq .data.data[0].payload.data.config > config.json

# Add consenter set to config.json
# Update with consenter addresses and certificates

# Encode and submit update
configtxlator proto_encode \
  --input config_modified.json \
  --type common.Config \
  --output config_modified.pb
```
