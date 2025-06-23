# Member Admin Configuration

This module handles the configuration of admin users for AWS Managed Blockchain members in the Haven Health Passport system.

## Overview

The member admin configuration provides:
- Secure admin user creation with strong password policies
- Certificate-based authentication setup
- Granular permission management
- Multi-factor authentication support
- Comprehensive audit logging
- AWS IAM integration

## Configuration File

The admin configuration is defined in `config/member-admin-config.yaml`. Key sections include:

### User Attributes
- Username and organizational attributes
- Certificate configuration with ECDSA-256 keys
- 365-day certificate validity period

### Access Policies
- Channel creation permissions
- Chaincode lifecycle management (install, instantiate, upgrade, invoke, query)
- Peer management capabilities
- Certificate management rights
- Policy administration permissions

### Security Settings
- Password policy: 16+ characters with complexity requirements
- TOTP-based multi-factor authentication
- 30-minute session timeout
- Maximum 2 concurrent sessions

### Notifications
- Email alerts for critical events
- Webhook integration for automated responses
- Configurable alert types

### Audit Settings
- 7-year retention period
- Encrypted audit logs
- Comprehensive action tracking

## Usage

### Install Dependencies
```bash
npm install
```
### Build the Module
```bash
npm run build
```

### Configure Member Admin
```bash
npm run configure-admin -- configure --network-id <NETWORK_ID> [--member-id <MEMBER_ID>]
```

### Validate Configuration
```bash
npm run configure-admin -- validate
```

## Environment Variables

Required environment variables:
- `AWS_ACCOUNT_ID`: AWS account ID
- `AWS_REGION`: AWS region (default: us-east-1)
- `KMS_KEY_ID`: KMS key for encryption
- `WEBHOOK_SECRET`: Secret for webhook authentication

## Security Considerations

1. **Password Storage**: Admin passwords are generated using cryptographically secure random functions and stored in AWS Secrets Manager
2. **Certificate Security**: All certificates use ECDSA-256 for strong cryptographic protection
3. **Access Control**: Implements principle of least privilege with granular permissions
4. **Audit Trail**: All admin actions are logged for compliance and security monitoring

## Integration with AWS Managed Blockchain

The configuration integrates with AWS Managed Blockchain by:
1. Creating member configurations with admin credentials
2. Setting up CloudWatch logging for CA logs
3. Configuring IAM roles with necessary permissions
4. Managing member lifecycle operations

## Next Steps

After configuring the member admin:
1. Deploy smart contracts using the admin credentials
2. Set up peer nodes with proper access controls
3. Configure channels and endorsement policies
4. Implement monitoring and alerting

## Troubleshooting

Common issues:
- **Invalid credentials**: Check AWS credentials and permissions
- **Network not found**: Verify network ID and region
- **Permission denied**: Ensure IAM role has required Managed Blockchain permissions
- **Configuration errors**: Validate YAML syntax and required fields
