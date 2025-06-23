# Orderer Policies Documentation

## Overview

This document describes the orderer policies implemented for the Haven Health Passport blockchain network. These policies govern the operation, management, and security of the ordering service in our Hyperledger Fabric network.

## Policy Categories

### 1. Core Ordering Service Policies

These policies define basic read, write, and administrative access to the ordering service:

- **OrdererReaders**: Allows query access to orderer configuration
- **OrdererWriters**: Permits transaction submission
- **OrdererAdmins**: Controls administrative operations (requires majority approval)
- **OrdererBlockValidation**: Defines block signing requirements

### 2. Consensus-Specific Policies

Policies for managing the Raft consensus mechanism:

- **ConsensusNodeAddition**: Controls adding new orderer nodes
  - Requires: Orderer admin OR agreement from healthcare providers

- **ConsensusNodeRemoval**: Controls removing orderer nodes
  - Requires: Orderer admin AND at least one healthcare/UN organization

- **RaftConfigurationUpdate**: Manages Raft parameter changes
  - Requires: Orderer admin AND majority approval

### 3. Channel Management Policies

Controls channel lifecycle operations:

- **ChannelCreation**: New channel creation
  - Requires: (Orderer + UNHCR) OR (All healthcare + refugee orgs)

- **ChannelModification**: Channel configuration updates
  - Requires: Majority of channel member admins

- **ChannelRemoval**: Channel archival/removal
  - Requires: Orderer + UNHCR + majority approval

### 4. Emergency and Compliance Policies

Critical policies for healthcare emergencies and regulatory compliance:

- **EmergencyOverride**: 24-hour emergency access for critical healthcare situations
  - Requires: (UN/Refugee org) AND (Healthcare provider)
  - Includes automatic audit and notification

- **HIPAAComplianceOperations**: HIPAA-required operations
  - Requires: Orderer admin OR both healthcare providers

- **DataRetentionPolicy**: Data lifecycle management
  - Requires: Orderer + UN/Refugee org + majority approval
### 5. Performance and Maintenance Policies

Policies for system optimization and maintenance:

- **BatchSizeConfiguration**: Controls transaction batching parameters
  - Constraints: 10-1000 messages, 512KB-100MB size limits

- **BatchTimeoutConfiguration**: Manages batch timeout settings
  - Constraints: 200ms-10s timeout range

- **MaintenanceMode**: Scheduled maintenance operations
  - Requires: 2-hour advance notice, 4-hour max duration

### 6. Security and Access Control

Security-critical policies:

- **TLSCertificateUpdate**: TLS certificate rotation
  - Requires: Orderer admin AND majority approval

- **MSPConfigurationUpdate**: Membership service changes
  - Requires: Unanimous approval (highest security)

- **ACLModification**: Access control list changes
  - Requires: Majority approval

### 7. Monitoring and Audit

Observability and compliance policies:

- **AuditLogAccess**: Audit trail access
  - Allows: Orderer, UNHCR, or both healthcare providers

- **MetricsAccess**: Performance metrics viewing
  - Allows: Any reader (broadest access)

- **DiagnosticOperations**: System diagnostics
  - Allows: Orderer admin OR majority

### 8. Cross-Border Data Policies

International data transfer controls:

- **CrossBorderDataTransfer**: International data movement
  - Requires: UNHCR AND majority approval
  - Ensures compliance with GDPR, HIPAA, regional laws

- **InternationalOrgAccess**: International organization access
  - Requires: UNHCR AND (refugee org OR majority)

## Policy Enforcement

### Evaluation Order

Policies are evaluated in this priority order:
1. EmergencyOverride (highest priority)
2. HIPAAComplianceOperations
3. OrdererAdmins
4. MAJORITY Admins
5. ANY Writers
6. ANY Readers (lowest priority)

### Violation Handling

When policy violations occur:
- Transaction is automatically blocked
- ERROR level audit entry generated
- Alerts sent to Orderer and UNHCR admins
- Detailed violation report created

### Policy Updates

Policy modifications require:
- Orderer admin AND majority approval
- 24-hour grace period before activation
- Backward compatibility maintained
- Rollback capability preserved

## Implementation Details

### Integration Steps

1. Policies defined in `orderer-policies.yaml`
2. Run `integrate-orderer-policies.sh` to merge with main config
3. Generate new genesis block with updated policies
4. Deploy to test network for validation
5. Perform policy enforcement testing
6. Deploy to production network

### Testing Requirements

Each policy must be tested for:
- Positive authorization (allowed actions work)
- Negative authorization (denied actions blocked)
- Edge cases and boundary conditions
- Performance impact under load
- Audit trail completeness

### Compliance Verification

Regular audits ensure:
- HIPAA compliance for healthcare data
- GDPR compliance for EU citizen data
- UNHCR standards for refugee data
- Regional data protection law compliance
- Proper audit trail maintenance

## Maintenance Procedures

### Regular Reviews

- Monthly: Review access logs and policy violations
- Quarterly: Assess policy effectiveness
- Annually: Comprehensive policy audit and update

### Emergency Procedures

For emergency policy updates:
1. Invoke EmergencyOverride if needed
2. Document justification
3. Implement temporary policy
4. Follow up with permanent fix within 48 hours

## Contact Information

For policy questions or issues:
- Technical: Orderer administrators
- Compliance: UNHCR compliance team
- Emergency: 24/7 operations center
