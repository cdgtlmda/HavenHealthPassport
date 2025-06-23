# AWS Managed Blockchain Implementation Guide

## Overview

Haven Health Passport uses AWS Managed Blockchain with Hyperledger Fabric to provide immutable, verifiable health records for displaced refugees. This implementation ensures data integrity, cross-border verification, and compliance with healthcare regulations while leveraging AWS's managed infrastructure.

## Architecture

### AWS Managed Blockchain Components

1. **Network**: Hyperledger Fabric 2.2 on AWS Managed Blockchain
2. **Members**: Healthcare organizations, NGOs, and government agencies
3. **Peer Nodes**: Distributed across availability zones
4. **Chaincode**: Smart contracts for health record management
5. **Lambda Functions**: Serverless chaincode invocation

### Key Features

- **Immutable Health Records**: Cryptographic verification of medical data
- **Cross-Border Verification**: Secure sharing between countries
- **Access Control**: Fine-grained permissions on blockchain
- **Audit Trail**: Complete history of all transactions
- **HIPAA Compliance**: Encrypted data with access controls

## Configuration

### Environment Variables

```bash
# Blockchain Provider Selection
BLOCKCHAIN_PROVIDER=aws_managed_blockchain

# AWS Managed Blockchain Settings
MANAGED_BLOCKCHAIN_NETWORK_ID=n-ABCDEF1234567890
MANAGED_BLOCKCHAIN_MEMBER_ID=m-ABCDEF1234567890
AWS_REGION=us-east-1

# Channel and Chaincode
BLOCKCHAIN_CHANNEL=healthcare-channel
BLOCKCHAIN_CHAINCODE=health-records
BLOCKCHAIN_ORG=HavenHealthOrg
```

### Network Deployment

1. **Deploy AWS Managed Blockchain Network**:
```bash
cd scripts/aws
python deploy_managed_blockchain.py
```

2. **Deploy Lambda Functions**:

**Note**: Lambda function deployment configuration is pending. The chaincode invoker currently returns mock responses for development purposes.

3. **Configure Application**:
```bash
# Copy network IDs to .env file
cp blockchain/aws-managed-blockchain/deployed-config/blockchain.env .env
```

## Blockchain Operations

### Health Record Verification

**Important**: The blockchain integration is currently in development mode. While the AWS Managed Blockchain network can be provisioned, the chaincode invocation through Lambda functions returns mock data. Full Hyperledger Fabric SDK integration is planned for production release.

```python
from haven_health.services.blockchain import get_blockchain_service

# Get blockchain service
blockchain = get_blockchain_service()

# Create hash of health record
record_data = {
    "patient_id": "123",
    "record_type": "vaccination",
    "vaccine": "COVID-19",
    "date": "2024-01-15"
}
hash_value = blockchain.create_record_hash(record_data)

# Store on blockchain
tx_id = blockchain.store_verification(
    record_id=record_id,
    verification_hash=hash_value,
    record_data=record_data
)

# Verify record
result = blockchain.verify_record(record_id, record_data)
if result["verified"]:
    print(f"Record verified with tx_id: {result['blockchain_tx_id']}")
```

### Cross-Border Verification

```python
# Create cross-border verification
verification = blockchain.create_cross_border_verification(
    patient_id=patient_id,
    destination_country="CA",
    health_records=[record1_id, record2_id],
    purpose="medical_treatment",
    duration_days=90
)

# Validate access from destination country
is_valid, details = blockchain.validate_cross_border_access(
    verification_id=verification["verification_id"],
    accessing_country="CA"
)
```

## Smart Contracts

### HealthRecordContract

**Functions**:
- `createHealthRecord`: Store new health record hash
- `queryHealthRecord`: Retrieve health record by ID
- `updateHealthRecord`: Update existing record
- `getVerificationHistory`: Get all verifications for a record

### VerificationContract

**Functions**:
- `requestVerification`: Create verification request
- `approveVerification`: Approve with multi-signature
- `rejectVerification`: Reject with reason
- `revokeVerification`: Revoke existing verification

### AccessControlContract

**Functions**:
- `grantAccess`: Grant permissions to healthcare provider
- `revokeAccess`: Remove access permissions
- `checkAccess`: Verify current access rights
- `getAccessHistory`: Audit trail of access

### CrossBorderContract

**Functions**:
- `createCrossBorderVerification`: Enable cross-border sharing
- `validateAccess`: Check if country has access
- `logAccess`: Record access attempts
- `revokeVerification`: Disable cross-border access

## Security Considerations

### Data Privacy

1. **On-Chain Data**: Only hashes and metadata stored
2. **Off-Chain Storage**: Actual health records in encrypted S3
3. **Access Control**: Multi-level permission system
4. **Encryption**: AES-256 for data at rest, TLS 1.3 in transit

### Compliance

- **HIPAA**: Full audit trails and access controls
- **GDPR**: Right to erasure through revocation
- **Cross-Border**: Country-specific public keys

### Network Security

- **VPC Endpoints**: Private connectivity to blockchain
- **IAM Roles**: Least privilege access
- **KMS Integration**: Hardware security module for keys
- **CloudWatch**: Monitoring and alerting

## Performance Optimization

### Caching Strategy

```python
# Local blockchain reference cache
from src.models.blockchain import BlockchainReference

# Store locally for quick lookup
ref = BlockchainReference(
    record_id=record_id,
    transaction_id=tx_id,
    hash_value=hash_value,
    blockchain_network=f"aws-{network_id}"
)
```

### Lambda Optimization

- **Reserved Concurrency**: Prevent cold starts
- **Memory Allocation**: 512MB for chaincode operations
- **Timeout Settings**: 60 seconds for complex queries
- **Batch Operations**: Group multiple transactions

## Monitoring and Alerts

### CloudWatch Metrics

- Transaction success rate
- Chaincode invocation latency
- Network member health
- Peer node availability

### Alarms

```python
# Example CloudWatch alarm for failed transactions
{
    "AlarmName": "BlockchainTransactionFailures",
    "MetricName": "FailedTransactions",
    "Threshold": 5,
    "Period": 300,
    "EvaluationPeriods": 1
}
```

## Troubleshooting

### Common Issues

1. **Network Not Available**
   - Check network status in AWS Console
   - Verify network and member IDs in configuration
   - Ensure peer nodes are running

2. **Transaction Timeouts**
   - Increase Lambda timeout settings
   - Check peer node performance
   - Verify network connectivity

3. **Permission Denied**
   - Verify IAM roles and policies
   - Check member certificate validity
   - Ensure proper channel membership

### Debug Mode

```python
# Enable debug logging
import logging
logging.getLogger('src.services.blockchain_service_aws').setLevel(logging.DEBUG)
```

## Cost Optimization

### Best Practices

1. **Right-Size Peer Nodes**: Use bc.t3.small for development
2. **Batch Transactions**: Reduce individual invocations
3. **Cache Results**: Minimize blockchain queries
4. **Archive Old Data**: Move to S3 Glacier

### Estimated Costs

- Network: ~$0.30/hour
- Peer Nodes: ~$0.25/hour each
- Lambda Invocations: ~$0.20 per million
- Data Transfer: Standard AWS rates

## Migration Guide

### From Standalone Fabric to AWS

1. Export existing blockchain data
2. Deploy AWS Managed Blockchain network
3. Update application configuration
4. Migrate chaincode to AWS
5. Verify historical transactions
6. Update monitoring and alerts

### Rollback Plan

1. Keep standalone Fabric running during migration
2. Dual-write to both networks temporarily
3. Verify data consistency
4. Switch traffic gradually
5. Maintain backups of all transactions

## Future Enhancements

1. **Multi-Region Deployment**: Global blockchain network
2. **Advanced Analytics**: Real-time blockchain analytics
3. **IoT Integration**: Direct device-to-blockchain
4. **AI Verification**: Machine learning for fraud detection
5. **Quantum-Resistant**: Post-quantum cryptography
