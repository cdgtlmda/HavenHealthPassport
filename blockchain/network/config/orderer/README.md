# Raft Consensus Configuration for Haven Health Passport

## Overview

This directory contains the configuration files for implementing Raft consensus in the Haven Health Passport blockchain network. Raft is a crash fault-tolerant (CFT) ordering service that provides a more efficient consensus mechanism compared to Solo or Kafka-based ordering.

## Configuration Files

### 1. `configtx.yaml`
The main configuration file that defines:
- **OrdererType**: Set to `etcdraft` for Raft consensus
- **Consenters**: 5 orderer nodes (orderer1-5.havenhealthpassport.org)
- **Raft Options**:
  - TickInterval: 500ms
  - ElectionTick: 10
  - HeartbeatTick: 1
  - MaxInflightBlocks: 5
  - SnapshotIntervalSize: 100 MB
- **Organizations**: OrdererOrg, HealthcareProvider1, HealthcareProvider2, RefugeeOrg, UNHCROrg
- **Channel Configuration**: Healthcare channel for data sharing

### 2. `docker-compose-orderer-raft.yaml`
Docker Compose configuration for running the 5-node Raft cluster:
- Each orderer runs on a different port (7050, 8050, 9050, 10050, 11050)
- TLS enabled for all communications
- Channel participation API enabled
- Prometheus metrics enabled

### 3. `orderer.yaml`
Individual orderer node configuration:
- TLS settings for secure communication
- Cluster configuration for intra-orderer communication
- Consensus WAL and snapshot directories
- Operations and metrics endpoints
- Admin API configuration

### 4. `configure-raft-consensus.sh`
Automated script to:
- Generate genesis block with Raft configuration
- Create channel configuration transaction
- Generate anchor peer transactions
- Verify Raft configuration
- Create startup scripts

## Raft Consensus Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Number of Nodes | 5 | Provides fault tolerance for up to 2 failed nodes |
| Election Timeout | 10 ticks (5 seconds) | Time before a follower becomes a candidate |
| Heartbeat Interval | 1 tick (500ms) | Frequency of heartbeat messages |
| Max Inflight Blocks | 5 | Maximum unacknowledged blocks |
| Snapshot Interval | 100 MB | Size trigger for creating snapshots |

## Usage

1. **Configure the Network**:
   ```bash
   ./configure-raft-consensus.sh
   ```

2. **Start the Raft Orderers**:
   ```bash
   ./start-raft-orderers.sh
   ```

3. **Verify Cluster Status**:
   ```bash
   docker-compose -f docker-compose-orderer-raft.yaml ps
   ```

## Fault Tolerance

With 5 orderer nodes, the network can tolerate up to 2 node failures while maintaining consensus. The Raft algorithm ensures:
- Leader election in case of failures
- Log replication across all nodes
- Consistent ordering of transactions

## Monitoring

Each orderer exposes:
- Operations endpoint (ports 9443-9447) for health checks
- Metrics endpoint for Prometheus monitoring
- Admin API (ports 7053-11053) for channel management

## Security

- All communications use TLS encryption
- Client authentication required for admin operations
- Separate certificates for server and cluster communications
- MSP-based identity management

## Troubleshooting

1. **Check Orderer Logs**:
   ```bash
   docker logs orderer1.havenhealthpassport.org
   ```

2. **Verify Raft Leader**:
   Check logs for "Raft leader changed" messages

3. **Network Connectivity**:
   Ensure all orderer ports are accessible between nodes

## Next Steps

After configuring Raft consensus:
1. Set up orderer nodes (next item in checklist)
2. Define consenter set
3. Configure election parameters
4. Continue with remaining consensus configuration items
