# AWS Managed Blockchain Network Configuration

## Network Configuration Details

This document records all configuration decisions for the Haven Health Passport blockchain network as per the implementation checklist.

### 1. Network Basic Configuration

- **Network Name**: `HavenHealthPassportNetwork`
- **Network Description**: "Blockchain network for Haven Health Passport - Secure healthcare data management"
- **Framework**: Hyperledger Fabric
- **Framework Version**: 2.2
- **Edition**: STANDARD (chosen for production-grade features and higher throughput)

### 2. Voting Policy Configuration

The voting policy governs how network changes are approved:

- **Approval Threshold Percentage**: 50%
- **Proposal Duration**: 24 hours
- **Threshold Comparator**: GREATER_THAN

This means:
- Network changes require more than 50% of members to approve
- Members have 24 hours to vote on proposals
- A proposal passes if votes exceed the threshold

### 3. Administrator Configuration

- **Admin Username**: `HavenAdmin`
- **Admin Password**: Set during deployment (minimum 8 characters)
- **Security Note**: Password is marked as NoEcho in CloudFormation for security

### 4. Member Configuration

- **Initial Member Name**: `HavenHealthFoundation`
- **Member Description**: "Primary member for Haven Health Passport blockchain network"
- **Member Type**: Standard member with full voting rights
### 5. Certificate Authority Configuration

The Hyperledger Fabric CA is automatically configured by AWS Managed Blockchain with:
- TLS enabled by default
- Automatic certificate generation
- Built-in certificate management

### 6. Peer Node Configuration (To be configured post-deployment)

Planned configuration:
- **Instance Type**: To be determined based on workload
- **Availability Zone**: Multi-AZ for high availability
- **Logging**: Enabled with CloudWatch integration

### 7. CloudWatch Logging Configuration

- **Log Group Prefix**: `/aws/managedblockchain/HavenHealthPassport`
- **Log Retention**: 30 days (configurable)
- **Log Types**:
  - CA logs
  - Peer node logs
  - Chaincode logs

### 8. Network Security Configuration

- **VPC Endpoint**: Required for secure communication
- **Security Groups**: Restrictive inbound rules
- **Network ACLs**: Additional layer of network security
- **VPC Flow Logs**: Enabled for network monitoring

### 9. Configuration Rationale

**Why STANDARD Edition?**
- Higher transaction throughput (up to 1000 TPS)
- More peer nodes per member (up to 5)
- Better suited for healthcare data requirements

**Why 50% Voting Threshold?**
- Balances security with operational flexibility
- Prevents single member from blocking changes
- Allows for democratic governance

**Why 24 Hour Proposal Duration?**
- Gives sufficient time for review
- Accommodates different time zones
- Allows for proper evaluation of changes
