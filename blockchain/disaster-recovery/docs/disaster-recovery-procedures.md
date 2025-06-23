# Blockchain Disaster Recovery Procedures

## Document Purpose

This document provides step-by-step procedures for recovering the Haven Health Passport blockchain infrastructure from various disaster scenarios. These procedures have been validated through comprehensive testing.

## Emergency Contact Information

- **Blockchain Team Lead**: [Contact Information]
- **AWS Support**: [Premium Support Contact]
- **Security Team**: [Contact Information]
- **Compliance Officer**: [Contact Information]

## Pre-Disaster Preparation

### Daily Tasks
1. Verify automated backups completed successfully
2. Check blockchain network health metrics
3. Review security alerts and logs
4. Validate data replication status

### Weekly Tasks
1. Test backup restoration in sandbox environment
2. Review and update access control lists
3. Validate certificate expiration dates
4. Conduct security vulnerability scans

### Monthly Tasks
1. Execute disaster recovery drills
2. Update recovery procedures based on lessons learned
3. Review and update emergency contact information
4. Validate compliance with regulatory requirements

## Disaster Recovery Procedures by Scenario

### 1. Single Peer Node Failure (DR-NODE-001)

**Detection Indicators:**
- CloudWatch alert for peer node down
- Transaction processing delays
- Reduced network capacity warnings

**Recovery Steps:**
1. **Immediate Response (0-5 minutes)**
   ```bash
   # Verify node failure
   aws managedblockchain list-nodes \
     --network-id $AMB_NETWORK_ID \
     --member-id $AMB_MEMBER_ID \
     --status FAILED
   ```

2. **Assessment (5-10 minutes)**
   - Check CloudWatch logs for failure cause
   - Verify other nodes are operational
   - Assess transaction backlog

3. **Recovery Action (10-15 minutes)**
   ```bash
   # Create replacement node
   aws managedblockchain create-node \
     --network-id $AMB_NETWORK_ID \
     --member-id $AMB_MEMBER_ID \
     --node-configuration file://node-config.json
   ```

4. **Validation (15-20 minutes)**
   - Monitor new node synchronization
   - Verify transaction processing resumed
   - Check data integrity

### 2. Complete Network Partition (DR-NET-001)

**Detection Indicators:**
- Split-brain alerts from monitoring
- Consensus failures across multiple nodes
- Geographic region isolation

**Recovery Steps:**

1. **Immediate Response (0-10 minutes)**
   - Identify partition boundaries
   - Determine which partition has quorum
   - Notify stakeholders of service degradation

2. **Stabilization (10-30 minutes)**
   ```bash
   # Stop non-quorum nodes
   ./scripts/stop-minority-partition.sh

   # Prevent further writes to minority partition
   ./scripts/enforce-read-only-mode.sh
   ```
3. **Network Restoration (30-45 minutes)**
   - Resolve network connectivity issues
   - Restart stopped nodes in sequence
   - Monitor consensus re-establishment

4. **Data Reconciliation (45-60 minutes)**
   - Identify transactions in minority partition
   - Replay valid transactions to main chain
   - Generate reconciliation report

### 3. Certificate Authority Failure (DR-NODE-004)

**Detection Indicators:**
- New identity enrollment failures
- Certificate validation errors
- TLS handshake failures

**Recovery Steps:**

1. **Immediate Response (0-10 minutes)**
   - Switch to backup CA if available
   - Halt new member onboarding
   - Document failure timestamp

2. **CA Recovery (10-30 minutes)**
   ```bash
   # Restore CA from backup
   ./scripts/restore-ca-backup.sh

   # Verify CA database integrity
   ./scripts/verify-ca-database.sh
   ```

3. **Certificate Reissuance (30-45 minutes)**
   - Generate new CA certificate if compromised
   - Update all peer nodes with new CA cert
   - Revoke compromised certificates

### 4. Data Corruption Recovery (DR-DATA-001)

**Detection Indicators:**
- Block validation failures
- State database inconsistencies
- Merkle tree verification errors
**Recovery Steps:**

1. **Immediate Response (0-15 minutes)**
   - Stop affected peer nodes
   - Identify corruption extent
   - Isolate corrupted data

2. **Ledger Restoration (15-45 minutes)**
   ```bash
   # Restore from latest snapshot
   ./scripts/restore-ledger-snapshot.sh \
     --peer-id $PEER_ID \
     --snapshot-id $LATEST_SNAPSHOT

   # Rebuild state database
   ./scripts/rebuild-state-db.sh --peer-id $PEER_ID
   ```

3. **Validation (45-60 minutes)**
   - Verify block integrity
   - Validate state database
   - Run comprehensive health checks

## Critical Decision Points

### When to Declare Disaster
- Multiple node failures (>50% of network)
- Complete region unavailability
- Data corruption affecting >1% of blocks
- Security breach detected

### When to Failover
- Primary region RTO exceeded
- Quorum cannot be maintained
- Compliance requirements at risk

### When to Restore vs Rebuild
- **Restore**: Clean backups available, <4 hours old
- **Rebuild**: Backups corrupted or >4 hours old

## Post-Recovery Actions

1. **Validation Checklist**
   - [ ] All nodes operational
   - [ ] Consensus mechanism functioning
   - [ ] Transaction processing normal
   - [ ] Data integrity verified
   - [ ] Access controls enforced
   - [ ] Monitoring alerts cleared
2. **Documentation Requirements**
   - Incident report with timeline
   - Root cause analysis
   - Actions taken log
   - Lessons learned document
   - Updated procedures (if needed)

3. **Stakeholder Communication**
   - Initial incident notification
   - Progress updates every 30 minutes
   - Resolution confirmation
   - Post-incident review scheduling

## Compliance Considerations

### HIPAA Requirements
- Maintain audit trail during recovery
- Ensure PHI encryption remains intact
- Document access during emergency
- File breach notification if required

### GDPR Requirements
- Preserve data subject rights
- Maintain data portability
- Document any data exposure
- Update privacy impact assessment

## Testing and Maintenance

- Execute full DR test quarterly
- Update procedures after each test
- Review with new team members
- Validate backup integrity weekly
- Update contact information monthly

## Appendices

### A. Emergency Command Reference
```bash
# Network status check
aws managedblockchain get-network --network-id $AMB_NETWORK_ID

# Node health check
aws managedblockchain list-nodes --network-id $AMB_NETWORK_ID

# Create backup
./scripts/create-emergency-backup.sh

# Restore from backup
./scripts/restore-from-backup.sh --backup-id $BACKUP_ID
```

### B. Tool Locations
- Recovery scripts: `/blockchain/disaster-recovery/scripts/`
- Backup storage: `s3://haven-health-dr-backups/`
- Monitoring dashboard: `https://console.aws.amazon.com/cloudwatch/`
- Runbooks: `/blockchain/disaster-recovery/docs/`
