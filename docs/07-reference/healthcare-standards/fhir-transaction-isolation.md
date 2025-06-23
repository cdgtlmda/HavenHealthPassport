# FHIR Server Transaction Isolation Configuration

## Overview

Transaction isolation configuration ensures data consistency and prevents common concurrency issues in the HAPI FHIR server. This configuration implements READ_COMMITTED isolation level with optimistic locking.

## Configuration Files

### 1. application.yaml
- Basic Hibernate transaction settings
- Connection pool transaction configuration
- PostgreSQL-specific optimizations

### 2. transaction-config.yaml
- Detailed transaction management settings
- Batch processing configuration
- Optimistic locking configuration
- Transaction retry policies

## Key Settings

### Transaction Isolation Level
- **Default Level**: READ_COMMITTED (Level 2)
- Prevents dirty reads
- Allows non-repeatable reads (acceptable for FHIR use cases)
- Better performance than REPEATABLE_READ or SERIALIZABLE

### Connection Pool Settings
```yaml
hikari:
  transaction-isolation: TRANSACTION_READ_COMMITTED
  auto-commit: false
  maximum-pool-size: 10
  minimum-idle: 5
```

### Optimistic Locking
- Enabled by default
- Prevents lost updates
- Automatic retry on version conflicts (max 3 attempts)
- Works with FHIR resource versioning

### Batch Processing
- Transaction timeout: 300 seconds for batch jobs
- Chunk size: 100 resources per transaction
- Skip policy for failed items

## Transaction Boundaries

### REST Operations
- Each HTTP request runs in its own transaction
- Transaction timeout: 30 seconds (configurable)
- Automatic rollback on errors

### Bundle Processing
- Entire bundle processed in single transaction
- All-or-nothing semantics
- Reference validation within transaction

## Performance Optimizations

1. **Connection Pooling**
   - Reuses database connections
   - Reduces connection overhead
   - Leak detection enabled

2. **Batch Operations**
   - Batch inserts/updates
   - PostgreSQL reWriteBatchedInserts enabled
   - Ordered inserts for better performance

3. **Lazy Loading**
   - Open-in-view disabled
   - Explicit fetch strategies
   - Prevents N+1 query problems

## Monitoring

### Transaction Logs
Enable detailed transaction logging:
```bash
export TRANSACTION_DEBUG_LEVEL=DEBUG
```

### Key Metrics to Monitor
- Transaction duration
- Rollback frequency
- Connection pool usage
- Lock wait times

## Common Issues and Solutions

### 1. Deadlocks
- **Symptom**: "deadlock detected" errors
- **Solution**: Ensure consistent resource access order

### 2. Version Conflicts
- **Symptom**: OptimisticLockException
- **Solution**: Automatic retry handles most cases

### 3. Connection Pool Exhaustion
- **Symptom**: "Connection pool timeout" errors
- **Solution**: Increase pool size or optimize queries

### 4. Long-Running Transactions
- **Symptom**: Transaction timeout errors
- **Solution**: Break into smaller transactions or increase timeout

## Best Practices

1. **Keep Transactions Short**
   - Release locks quickly
   - Avoid long computations in transactions

2. **Handle Conflicts Gracefully**
   - Implement retry logic in clients
   - Use conditional updates where possible

3. **Monitor Performance**
   - Track transaction metrics
   - Set up alerts for anomalies

4. **Test Under Load**
   - Simulate concurrent access
   - Verify isolation behavior

## Configuration Tuning

### For High Read Workloads
```yaml
read_isolation_level: 1  # READ_UNCOMMITTED
write_isolation_level: 2  # READ_COMMITTED
```

### For High Consistency Requirements
```yaml
read_isolation_level: 4  # REPEATABLE_READ
write_isolation_level: 4  # REPEATABLE_READ
```

### For Maximum Performance
```yaml
hikari:
  maximum-pool-size: 20
  minimum-idle: 10
hibernate:
  jdbc.batch_size: 50
```
