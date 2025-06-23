# Ordering Service Configuration

This module handles the configuration of the ordering service (consensus mechanism) for the Haven Health Passport blockchain network.

## Overview

The ordering service is responsible for:
- Establishing transaction order across the network
- Creating blocks of ordered transactions
- Distributing blocks to peers for validation
- Ensuring consistency across all network participants

## Service Type Selection

### Raft (Recommended for Production)
- **Description**: Crash fault-tolerant (CFT) ordering service based on Raft consensus protocol
- **Fault Tolerance**: Can tolerate (n-1)/2 node failures where n = total nodes
- **Performance**: High throughput with low latency
- **Configuration**: 5 nodes across 3 availability zones

### Why Raft?
1. **Production Ready**: Designed for enterprise deployments
2. **Leader-based**: Efficient transaction ordering with automatic leader election
3. **Fault Tolerant**: Continues operating with minority node failures
4. **No External Dependencies**: Unlike Kafka, requires no additional infrastructure

## Configuration Details

### Cluster Configuration
- **Node Count**: 5 (odd number for optimal consensus)
- **Fault Tolerance**: 2 nodes can fail without service disruption
- **AZ Distribution**:
  - us-east-1a: 2 nodes
  - us-east-1b: 2 nodes
  - us-east-1c: 1 node

### Performance Settings
- **Batch Timeout**: 2 seconds
- **Max Message Count**: 500 transactions per block
- **Max Block Size**: 10 MB absolute, 2 MB preferred
- **Election Timeout**: 5 seconds
- **Heartbeat Interval**: 500ms

### Security Configuration
- **TLS**: Enabled with mutual authentication
- **Certificate Rotation**: Every 90 days with 30-day grace period
- **Access Control**:
  - Admins: MAJORITY policy
  - Writers: ANY policy
  - Readers: ANY policy

## Usage

### Configure Ordering Service
```bash
npm run configure-ordering -- configure --network-id <NETWORK_ID>
```

### Validate Configuration
```bash
npm run configure-ordering -- validate
```

## Integration with AWS Managed Blockchain

In AWS Managed Blockchain:
1. Ordering service infrastructure is fully managed by AWS
2. Configuration is used for channel and chaincode operations
3. High availability and fault tolerance are handled automatically
4. Monitoring and logging integrated with CloudWatch

## Monitoring and Alerts

Key metrics monitored:
- **Consensus Latency**: Alert if > 5000ms
- **Leader Changes**: Warning if > 5 per 5 minutes
- **Message Backlog**: Warning if > 1000 messages
- **Block Height**: Track blockchain growth
- **Transaction Throughput**: Monitor network capacity

## Best Practices

1. **Node Distribution**: Spread nodes across multiple AZs
2. **Resource Allocation**: Ensure adequate CPU and memory
3. **Network Security**: Use private subnets with strict security groups
4. **Monitoring**: Set up comprehensive alerting for consensus issues
5. **Backup**: Regular snapshots of ledger data

## Troubleshooting

Common issues:
- **Leader Election Failures**: Check network connectivity between nodes
- **High Latency**: Review batch settings and network performance
- **Node Crashes**: Check CloudWatch logs for error details
- **Certificate Issues**: Verify TLS certificates are valid and properly configured
