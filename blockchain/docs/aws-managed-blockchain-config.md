# AWS Managed Blockchain Configuration Notes

## Overview

AWS Managed Blockchain automatically handles many aspects that would require manual configuration in standalone Hyperledger Fabric deployments. This document clarifies what is managed by AWS vs. what requires configuration.

## Automatically Managed by AWS

### 1. Consensus Mechanism
- **Raft Consensus**: AWS Managed Blockchain uses Raft consensus by default
- **Orderer Configuration**: Managed automatically by AWS
- **Leader Election**: Handled transparently by the service
- **Fault Tolerance**: Built-in with multi-AZ deployment

### 2. Identity Management
- **Certificate Authority (CA)**: AWS provides a managed CA for each member
- **User Enrollment**: Done through AWS APIs and console
- **MSP Configuration**: Automatically set up for each member
- **TLS Certificates**: Managed and rotated by AWS

### 3. Network Security
- **VPC Integration**: Network isolation through AWS VPC
- **Security Groups**: Standard AWS security groups apply
- **Encryption**: TLS enabled by default, data encrypted at rest
- **Access Control**: IAM-based permissions

### 4. Performance Optimization
- **Peer Node Scaling**: Configured through instance types
- **State Database**: LevelDB (CouchDB not available)
- **Block Configuration**: Set during network creation
- **Query Optimization**: Use composite keys in chaincode

## What You Configure

### 1. Chaincode
- Smart contract business logic
- Endorsement policies
- Private data collections (if needed)
- Access control within chaincode

### 2. Channels
- Channel creation and configuration
- Member organizations per channel
- Anchor peer settings

### 3. Application Integration
- Connection profiles
- SDK configuration
- Lambda functions for chaincode invocation

## Production Configuration for Medical Data

### Network Configuration
```yaml
Framework: HYPERLEDGER_FABRIC
FrameworkVersion: 2.2
Edition: STANDARD  # Required for production medical data
VotingPolicy:
  ApprovalThresholdPolicy:
    ThresholdPercentage: 50
    ProposalDurationInHours: 24
    ThresholdComparator: GREATER_THAN
```

### Peer Node Configuration
```yaml
InstanceType: bc.m5.large  # Minimum for production
AvailabilityZone: Multi-AZ deployment
LoggingConfiguration:
  Enabled: true
  CloudWatchLogs:
    Enabled: true
    RetentionInDays: 7  # HIPAA requires 7 years for medical records
```

### Security Best Practices

1. **IAM Policies**
   - Principle of least privilege
   - Separate roles for admin vs. application access
   - Enable MFA for administrative access

2. **VPC Configuration**
   - Private subnets for peer nodes
   - VPC endpoints for AWS services
   - Network ACLs for additional security

3. **Monitoring**
   - CloudWatch alarms for failed transactions
   - CloudTrail for audit logging
   - AWS Config for compliance monitoring

4. **Backup and Recovery**
   - Regular snapshots of ledger data
   - Cross-region replication for disaster recovery
   - Tested recovery procedures

## Compliance Considerations

### HIPAA Compliance
- Enable CloudTrail logging
- Encrypt all data at rest and in transit
- Implement access controls in chaincode
- Regular security assessments

### GDPR Compliance
- Private data collections for PII
- Right to erasure through off-chain storage
- Data minimization in on-chain data
- Cross-border transfer controls

## Migration from Standalone Fabric

The following components from standalone Fabric are replaced by AWS services:

| Standalone Fabric | AWS Managed Blockchain |
|------------------|------------------------|
| Orderer nodes | Managed ordering service |
| CA server | Managed CA per member |
| CouchDB | LevelDB only |
| Docker containers | Managed infrastructure |
| Crypto material | AWS KMS integration |
| Network config | AWS console/API |

## Monitoring and Metrics

Key metrics to monitor for medical data:

1. **Transaction Metrics**
   - Transaction success rate (target: >99.9%)
   - Transaction latency (target: <2s)
   - Block creation time

2. **Security Metrics**
   - Failed authentication attempts
   - Unauthorized access attempts
   - Certificate expiration warnings

3. **Compliance Metrics**
   - Audit log completeness
   - Encryption status
   - Access control violations

## Cost Optimization

1. **Right-size peer nodes** based on transaction volume
2. **Use reserved instances** for predictable workloads
3. **Implement efficient chaincode** to reduce compute costs
4. **Archive old blocks** to S3 Glacier

## Support and Resources

- AWS Managed Blockchain documentation
- AWS Support (Business or Enterprise for medical applications)
- AWS Professional Services for healthcare implementations
- AWS Compliance Center for healthcare regulations
