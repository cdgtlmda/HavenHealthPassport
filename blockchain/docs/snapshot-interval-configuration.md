# Snapshot Interval Configuration Documentation
Haven Health Passport - Blockchain Consensus Mechanism

## Overview

This document describes the snapshot interval configuration for the Haven Health Passport blockchain's Raft consensus mechanism. Snapshots are critical for maintaining efficient blockchain operations and ensuring quick recovery in case of node failures.

## Configuration Location

- **Main Config**: `/blockchain/config/consensus/ordering-service-config.yaml`
- **Detailed Config**: `/blockchain/config/consensus/snapshot-config.yaml`
- **Deployment Script**: `/blockchain/scripts/deploy-snapshot-config.sh`
- **Verification Script**: `/blockchain/scripts/verify-snapshot-config.sh`

## Snapshot Interval Settings

### 1. Size-Based Intervals
- **Threshold**: 20 MB (20,971,520 bytes)
- **Minimum Size**: 10 MB before considering snapshot
- **Purpose**: Prevents log files from growing too large

### 2. Block-Based Intervals
- **Threshold**: 10,000 blocks
- **Minimum Blocks**: 1,000 blocks
- **Purpose**: Ensures regular snapshots based on blockchain activity

### 3. Time-Based Intervals
- **Interval**: 24 hours (daily snapshots)
- **Minimum Interval**: 1 hour between snapshots
- **Purpose**: Guarantees snapshots even during low activity periods

### 4. Transaction-Based Intervals
- **Threshold**: 100,000 transactions
- **Minimum Transactions**: 10,000
- **Purpose**: Scales with transaction volume

## Storage Configuration

### Primary Storage (AWS EBS)
- **Volume Type**: gp3
- **IOPS**: 3,000
- **Throughput**: 125 MB/s
- **Encryption**: Enabled with KMS

### Backup Storage (AWS S3)
- **Bucket**: haven-health-blockchain-snapshots
- **Storage Class**: STANDARD_IA (Infrequent Access)
- **Lifecycle**:
  - Move to Glacier after 30 days
  - Delete after 365 days

### Retention Policy
- **Local Snapshots**: Keep 10 most recent
- **Backup Snapshots**: Keep 30 most recent
- **Minimum Age**: Always keep snapshots from last 7 days

## Performance Optimizations

### Compression
- **Algorithm**: zstd (Zstandard)
- **Compression Level**: 3 (balanced speed/size)
- **Parallel Workers**: 4
- **Chunk Size**: 4 MB

### Resource Limits
- **Max CPU Usage**: 50% during snapshot creation
- **Max Memory**: 2048 MB
- **I/O Priority**: 7 (lowest priority)

### Transfer Settings
- **Max Concurrent Transfers**: 3
- **Rate Limit**: 50 MB/s per transfer
- **Burst Allowance**: 100 MB/s for 10 seconds

## Monitoring and Alerts

### CloudWatch Metrics
- **Namespace**: HavenHealth/Blockchain/Snapshots
- **Key Metrics**:
  - SnapshotCreationTime
  - SnapshotSize
  - SnapshotCount
  - SnapshotAge
  - RecoveryTime

### Configured Alerts
1. **SnapshotCreationFailed**: Critical alert on any failure
2. **SnapshotBackupFailed**: Warning on backup failures
3. **SnapshotAgeTooOld**: Warning if oldest snapshot > 48 hours
4. **SnapshotStorageFull**: Warning at 90% storage usage

## Recovery Process

### Automatic Recovery
- **Enabled**: Yes
- **Verification**: Pre and post-recovery checks
- **Timeout**: 30 minutes maximum
- **Source Preference**:
  1. Local storage
  2. AWS EBS
  3. AWS S3

### Manual Recovery
If automatic recovery fails:
1. Check CloudWatch logs
2. Verify snapshot integrity
3. Use manual recovery script
4. Restore from S3 backup if needed

## Deployment Instructions

1. **Deploy Configuration**:
   ```bash
   cd /blockchain/scripts
   ./deploy-snapshot-config.sh
   ```

2. **Verify Configuration**:
   ```bash
   ./verify-snapshot-config.sh
   ```

3. **Apply to AWS Managed Blockchain**:
   - Access AWS Console
   - Navigate to Managed Blockchain
   - Update node configurations with generated settings

## Best Practices

1. **Regular Testing**: Test snapshot recovery monthly
2. **Monitor Metrics**: Check CloudWatch dashboards daily
3. **Storage Management**: Review storage usage weekly
4. **Backup Verification**: Verify S3 backups monthly
5. **Alert Response**: Respond to alerts within 15 minutes

## Troubleshooting

### Common Issues

1. **Snapshot Creation Failures**
   - Check disk space
   - Verify permissions
   - Review CloudWatch logs

2. **Slow Snapshot Creation**
   - Check CPU/memory usage
   - Verify compression settings
   - Consider increasing resources

3. **Recovery Failures**
   - Verify snapshot integrity
   - Check network connectivity
   - Review recovery logs

## Compliance Considerations

- **HIPAA**: Snapshots contain encrypted health data
- **Data Retention**: Follow configured retention policies
- **Access Control**: Limit snapshot access to authorized personnel
- **Audit Trail**: All snapshot operations are logged

## Version History

- **v1.0.0** (Current): Initial snapshot interval configuration
  - Implemented multi-trigger snapshot creation
  - Added S3 backup support
  - Configured monitoring and alerts
