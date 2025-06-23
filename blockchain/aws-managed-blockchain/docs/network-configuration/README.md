# AWS Managed Blockchain Network Configuration Documentation
# Haven Health Passport

## Network Overview

The Haven Health Passport blockchain network is built on AWS Managed Blockchain using Hyperledger Fabric framework. This document details the network configuration, architecture decisions, and operational guidelines.

## Network Configuration Details

### Basic Network Settings

| Parameter | Value | Justification |
|-----------|-------|---------------|
| Framework | Hyperledger Fabric | Industry standard for permissioned blockchain, supports private channels |
| Framework Version | 2.2 | Stable version with enhanced performance and security features |
| Network Edition | STANDARD | Production-grade with higher performance and availability |
| Network Name | haven-health-passport-network | Descriptive name for easy identification |

### Voting Policy Configuration

| Parameter | Value | Justification |
|-----------|-------|---------------|
| Approval Threshold | 50% | Balanced between security and operational efficiency |
| Proposal Duration | 24 hours | Sufficient time for review while maintaining agility |
| Threshold Comparator | GREATER_THAN_OR_EQUAL_TO | Standard majority voting |

### Member Configuration

| Parameter | Value | Justification |
|-----------|-------|---------------|
| Initial Member | haven-health-primary-member | Primary organization managing the network |
| Admin Access | Username/Password | Secure credentials stored in AWS Secrets Manager |
| CA Logging | Enabled | Full audit trail for certificate operations |

### Peer Node Configuration

| Parameter | Value | Justification |
|-----------|-------|---------------|
| Node Count | 2 (default) | High availability with cost optimization |
| Instance Type | bc.t3.small | Sufficient for initial deployment, can scale up |
| Availability Zones | Multi-AZ | Fault tolerance and high availability |
| Logging | Enabled | Full audit trail for peer and chaincode operations |

## Architecture Decisions

### 1. Network Topology
- **Decision**: Multi-peer, single-member initial deployment
- **Rationale**: Simplifies initial deployment while allowing future expansion
- **Future**: Can add additional members for healthcare providers, NGOs, etc.

### 2. Security Configuration
- **TLS**: Enabled for all communications
- **Access Control**: IAM-based with principle of least privilege
- **Encryption**: Data at rest and in transit
- **Key Management**: AWS KMS for cryptographic operations

### 3. Logging Strategy
- **CloudWatch Integration**: All logs centralized
- **Retention**: 30 days default, adjustable based on compliance needs
- **Log Types**: CA logs, peer logs, chaincode logs, VPC flow logs

### 4. VPC Configuration
- **Endpoint Type**: Interface endpoint for private connectivity
- **Security Groups**: Restrictive ingress, controlled egress
- **Network ACLs**: Additional layer of network security
- **Flow Logs**: Full traffic monitoring for security analysis

### 5. High Availability
- **Multi-AZ Deployment**: Peer nodes distributed across availability zones
- **Automatic Failover**: Managed by AWS
- **Backup Strategy**: Regular state snapshots
- **Disaster Recovery**: Cross-region replication planned

## Network Endpoints

### Production Environment
- **Network ID**: Stored in SSM Parameter Store at `/{env}/blockchain/network_id`
- **CA Endpoint**: Stored in SSM Parameter Store at `/{env}/blockchain/network_endpoint`
- **Peer Endpoints**: Stored in SSM Parameter Store at `/{env}/blockchain/peer_endpoint_{n}`

### Access Patterns
1. **Internal Applications**: Via VPC endpoint
2. **External Integrations**: Via API Gateway (future)
3. **Admin Access**: Via AWS Console or SDK

## Performance Specifications

| Metric | Target | Current Configuration |
|--------|--------|----------------------|
| Transaction Throughput | 1000 TPS | bc.t3.small supports ~100 TPS |
| Block Size | 2 MB | Default configuration |
| State DB Queries | < 100ms | CouchDB indexed queries |
| Network Latency | < 50ms | Within region deployment |

## Compliance Considerations

### HIPAA Compliance
- Encryption at rest and in transit
- Access logging and monitoring
- Regular security assessments
- BAA with AWS in place

### Data Sovereignty
- Region-specific deployment
- No cross-border data transfer without explicit consent
- Local jurisdiction compliance

### Audit Requirements
- Immutable audit trail on blockchain
- CloudWatch logs for operational audit
- Regular compliance reports

## Monitoring and Alerting

### Key Metrics
1. **Network Health**: Member and peer node status
2. **Transaction Metrics**: Success rate, latency, throughput
3. **Resource Utilization**: CPU, memory, storage
4. **Security Events**: Failed auth attempts, policy violations

### Alert Thresholds
- Peer node unavailability: Immediate
- Transaction failure rate > 5%: High priority
- Resource utilization > 80%: Medium priority
- Certificate expiration < 30 days: Low priority

## Operational Procedures

### Routine Maintenance
1. **Daily**: Check network health dashboard
2. **Weekly**: Review performance metrics
3. **Monthly**: Security audit review
4. **Quarterly**: Capacity planning review

### Emergency Procedures
1. **Network Outage**: Failover to secondary region (future)
2. **Security Breach**: Immediate isolation and investigation
3. **Data Corruption**: Restore from last known good state

## Cost Optimization

### Current Estimates
- Network membership: ~$500/month
- Peer nodes (2x bc.t3.small): ~$150/month each
- Data transfer: Variable based on usage
- CloudWatch logs: ~$50/month

### Optimization Strategies
1. Right-size peer nodes based on actual usage
2. Implement log retention policies
3. Use reserved instances for predictable workloads
4. Monitor and optimize data transfer costs

## Future Enhancements

### Phase 2 (Q2 2024)
- Multi-member network with healthcare providers
- Cross-channel communication
- Advanced privacy features (private data collections)

### Phase 3 (Q3 2024)
- Cross-region deployment
- Integration with external blockchain networks
- Advanced analytics and reporting

### Phase 4 (Q4 2024)
- Full decentralization
- Community governance model
- Token economics implementation

## References

- [AWS Managed Blockchain Documentation](https://docs.aws.amazon.com/managed-blockchain/)
- [Hyperledger Fabric Documentation](https://hyperledger-fabric.readthedocs.io/)
- [HIPAA Compliance Guide](https://aws.amazon.com/compliance/hipaa-compliance/)
- [Network Architecture Diagram](./network-diagram.png)
