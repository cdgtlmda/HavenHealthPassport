# Channel Restrictions Documentation
Haven Health Passport - Multi-Channel Security and Resource Management

## Overview

Channel restrictions provide fine-grained control over blockchain channels, including:
- Which orderers can service which channels
- Resource allocation and QoS per channel
- Access control and security policies
- Compliance requirements per channel type

## Configuration Structure

### 1. Global Settings
- **Max channels per orderer**: 10
- **Max total channels**: 50
- **Channel naming pattern**: `^[a-z][a-z0-9-]{2,63}$`

### 2. Channel Categories

#### System Channels
- **Purpose**: Core blockchain operations
- **Priority**: Critical
- **Restrictions**: Only system admins can create, cannot be deleted
- **Orderers**: Limited to orderer0 and orderer1

#### Healthcare Channels
- **Purpose**: Patient records and medical data
- **Priority**: High
- **Compliance**: HIPAA required, 7-year retention
- **Encryption**: Mandatory
- **Orderers**: All orderers can service

#### Emergency Channels
- **Purpose**: Crisis response and disaster management
- **Priority**: Critical
- **Special**: Reduced restrictions for speed
- **Orderers**: High-availability orderers only

#### Audit Channels
- **Purpose**: Compliance and regulatory data
- **Priority**: Normal
- **Storage**: 2TB quota for audit trails
- **Retention**: 10 years, immutable
- **Orderers**: Specific compliance orderers

#### Research Channels
- **Purpose**: Analytics and studies
- **Priority**: Low
- **Privacy**: Anonymization required
- **Orderers**: All orderers allowed

### 3. Resource Allocation

#### QoS Classes
1. **Critical**: 40% CPU/Memory, 5000 IOPS
2. **High**: 30% CPU/Memory, 3000 IOPS
3. **Normal**: 20% CPU/Memory, 1000 IOPS
4. **Low**: 10% CPU/Memory, 500 IOPS

#### Dynamic Adjustment
- CPU scale-up threshold: 80%
- Memory scale-up threshold: 75%
- Queue depth trigger: 1000 messages

### 4. Security Policies

#### Channel Isolation
- Network isolation: Enabled
- Storage isolation: Enabled
- Process isolation: Disabled (performance)

#### Access Control
- Default policy: Deny
- Explicit allow required
- Regular access review: 30 days

#### Data Protection
- Encryption at rest: Required
- Encryption in transit: Required
- Key rotation: 90 days

## Implementation

### Files Created
1. **Main Configuration**: `channel-restrictions-config.yaml`
2. **Deployment Script**: `deploy-channel-restrictions.sh`
3. **Verification Script**: `verify-channel-restrictions.sh`
4. **Per-Orderer Configs**: `orderer-restrictions-{orderer-name}.yaml`
5. **Channel Policies**: `channel-policy-{category}.json`

### Deployment Process
```bash
cd blockchain/scripts
./deploy-channel-restrictions.sh
```

### Verification
```bash
./verify-channel-restrictions.sh
```

## Orderer Assignments

| Orderer | Required Channels | Max Channels | Specialization |
|---------|------------------|--------------|----------------|
| orderer0 | system-channel, healthcare-primary | 10 | System & Healthcare |
| orderer1 | system-channel, healthcare-primary | 10 | System & Healthcare |
| orderer2 | healthcare-secondary | 15 | Healthcare & Research |
| orderer3 | audit-primary | 20 | Audit & Compliance |
| orderer4 | audit-secondary | 20 | Audit & Research |

## Channel Lifecycle

### Creation Process
1. Validate channel name
2. Verify creation policy
3. Check resource availability
4. Assign orderers
5. Setup monitoring
6. Configure backup
7. Enable audit logging

### Deletion Process
1. Verify no active transactions
2. Confirm data archived
3. Get compliance approval
4. Stop processing
5. Archive data (30-day grace period)
6. Clean up resources
7. Retain data for regulatory period

## Monitoring

### Key Metrics
- Transaction rate per channel
- Storage usage
- Resource utilization
- Organization count
- Block height

### Alerts
- Channel quota exceeded (>90% storage)
- High transaction rate (>80% max TPS)
- Unauthorized access attempts
- Resource exhaustion (>90% utilization)

## Best Practices

1. **Channel Naming**
   - Use descriptive, hierarchical names
   - Follow the regex pattern strictly
   - Avoid reserved prefixes

2. **Resource Planning**
   - Start with normal QoS, upgrade as needed
   - Monitor utilization regularly
   - Plan for burst capacity

3. **Security**
   - Review access logs monthly
   - Rotate keys on schedule
   - Test channel isolation

4. **Compliance**
   - Document all channel creation/deletion
   - Maintain audit trails
   - Regular compliance audits

## Troubleshooting

### Common Issues

1. **Channel Creation Fails**
   - Check naming pattern
   - Verify creator has correct policy
   - Ensure resources available

2. **Performance Issues**
   - Review QoS assignment
   - Check orderer load distribution
   - Consider channel-specific orderers

3. **Access Denied**
   - Verify user policies
   - Check channel access rules
   - Review audit logs

## Integration Points

### AWS Integration
- IAM for access control
- Security groups per channel
- CloudWatch for monitoring

### Kubernetes Integration
- Namespaces for isolation
- Resource quotas
- Network policies
