# Haven Health Passport Blockchain Chaincode

## Overview

This directory contains the smart contracts (chaincode) for the Haven Health Passport blockchain implementation on AWS Managed Blockchain with Hyperledger Fabric. These contracts ensure the integrity, verifiability, and secure sharing of health records for displaced refugees.

## ⚠️ CRITICAL: Production Medical Data

This chaincode handles sensitive medical data for vulnerable populations. All code must be:
- **HIPAA Compliant**: Full audit trails and access controls
- **GDPR Compliant**: Data minimization and right to erasure
- **Secure**: No PHI stored on-chain, only hashes and metadata
- **Reliable**: 99.9%+ availability for life-critical systems

## Chaincode Contracts

### 1. Health Record Contract (`health-record/`)
Manages health record verification and integrity.

**Key Functions:**
- `CreateHealthRecord`: Store health record hash on blockchain
- `QueryHealthRecord`: Retrieve health record by ID
- `RecordVerification`: Record verification attempts
- `GetVerificationHistory`: Get all verifications for a record
- `UpdateHealthRecord`: Update record status or metadata

### 2. Cross-Border Contract (`cross-border/`)
Manages secure health record sharing between countries.

**Key Functions:**
- `CreateCrossBorderVerification`: Enable cross-border sharing
- `GetCrossBorderVerification`: Retrieve verification details
- `LogCrossBorderAccess`: Log access attempts
- `RevokeCrossBorderVerification`: Revoke sharing agreement
- `GetCountryPublicKey`: Get public key for country encryption

### 3. Access Control Contract (`access-control/`)
Manages granular permissions for health records.

**Key Functions:**
- `GrantAccess`: Grant permissions to healthcare provider
- `RevokeAccess`: Revoke existing permissions
- `CheckAccess`: Verify access permissions
- `GetAccessHistory`: Audit trail of all access grants

## Development

### Prerequisites

- Go 1.19 or higher
- AWS CLI configured
- Access to AWS Managed Blockchain network

### Building

```bash
# Build all chaincode
make build

# Run tests
make test

# Lint code
make lint

# Security check
make security-check
```

### Testing Locally

```bash
# Run in development mode (requires local Fabric)
make dev

# Run unit tests
cd chaincode/health-record
go test -v ./...
```

## Deployment

### Package Chaincode

```bash
# Package all chaincode
make package

# Deploy to AWS
make deploy
```

### Manual Deployment Steps

1. **Package chaincode**:
   ```bash
   cd chaincode/health-record
   tar -czf health-record.tar.gz .
   ```

2. **Upload to S3**:
   ```bash
   aws s3 cp health-record.tar.gz s3://haven-health-chaincode-${NETWORK_ID}/
   ```

3. **Install via AWS Console**:
   - Navigate to AWS Managed Blockchain
   - Select your network and member
   - Install chaincode from S3

4. **Instantiate chaincode**:
   - Select installed chaincode
   - Set endorsement policy
   - Initialize with `{"function":"InitLedger","Args":[]}`

## Security Considerations

### Data Privacy
- **No PHI on blockchain**: Only hashes and metadata
- **Encryption**: All data encrypted before hashing
- **Access logs**: Every access attempt logged
- **Audit trail**: Complete history maintained

### Best Practices
1. Never store sensitive data directly
2. Use composite keys for efficient queries
3. Implement proper access controls
4. Log all security-relevant events
5. Regular security audits

## Chaincode Structure

```
chaincode/
├── health-record/
│   ├── health_record.go    # Main contract logic
│   ├── go.mod              # Go module definition
│   └── go.sum              # Dependency checksums
├── cross-border/
│   ├── cross_border.go     # Cross-border sharing
│   └── go.mod
└── access-control/
    ├── access_control.go   # Permission management
    └── go.mod
```

## Error Handling

All chaincode functions follow these error handling principles:

1. **Validate inputs**: Check all required fields
2. **Clear error messages**: Include context in errors
3. **Fail fast**: Return early on validation failures
4. **Log errors**: Audit trail for debugging
5. **No sensitive data**: Never include PHI in error messages

## Performance Optimization

1. **Use composite keys** for efficient queries
2. **Minimize state reads** in transactions
3. **Batch operations** where possible
4. **Index design** for common queries
5. **Pagination** for large result sets

## Monitoring

Key metrics to monitor:

- Transaction success rate
- Endorsement failures
- Query performance
- State database size
- Event emission rate

## Compliance

### HIPAA Requirements
- Audit logs for all access
- Encryption of data at rest
- Access controls enforced
- Minimum necessary access
- Regular compliance audits

### GDPR Requirements
- Data minimization
- Purpose limitation
- Right to erasure (off-chain)
- Cross-border transfer controls
- Consent management

## Troubleshooting

### Common Issues

1. **Transaction fails with "MVCC_READ_CONFLICT"**
   - Cause: Concurrent updates to same key
   - Solution: Implement retry logic

2. **Query timeout**
   - Cause: Large result set
   - Solution: Implement pagination

3. **Endorsement failure**
   - Cause: Policy not met
   - Solution: Check endorsement policy

## Support

For issues or questions:
1. Check AWS Managed Blockchain logs
2. Review chaincode debug output
3. Contact Haven Health support

## License

Copyright © 2024 Haven Health Passport. All rights reserved.

This software handles medical data and is subject to healthcare regulations.
