# Offline Troubleshooting Guide

## Overview

This guide helps diagnose and resolve common issues with offline functionality in Haven Health Passport. It covers debugging techniques, common problems, and their solutions.

## Quick Diagnostics

### Offline Status Check

```typescript
// Check current offline status
const status = await OfflineDiagnostics.getStatus();
console.log('Offline Status:', {
  isOnline: status.isOnline,
  syncState: status.syncState,
  queueSize: status.queueSize,
  lastSync: status.lastSync,
  errors: status.errors
});
```

### Common Issues Checklist

- [ ] Network connectivity working?
- [ ] Local storage not full?
- [ ] Sync queue not blocked?
- [ ] No authentication issues?
- [ ] Database not corrupted?
- [ ] App permissions granted?

## Common Problems and Solutions

### 1. Data Not Syncing

#### Symptoms
- Changes not appearing on other devices
- Sync indicator stuck
- Queue size growing

#### Diagnosis
```typescript
// Check sync queue
const queue = await syncEngine.getQueue();
console.log('Queue size:', queue.length);
console.log('Oldest item:', queue[0]?.timestamp);

// Check for errors
const errors = await syncEngine.getErrors();
console.log('Sync errors:', errors);
```

#### Solutions

**1. Clear sync queue blockage**
```typescript
// Identify blocked items
const blocked = await syncEngine.getBlockedItems();
for (const item of blocked) {
  if (item.retryCount > 5) {
    // Remove permanently failed items
    await syncEngine.removeFromQueue(item.id);
  }
}
```

**2. Force sync retry**
```typescript
await syncEngine.forceSync();
```

**3. Reset sync state**
```typescript
await syncEngine.resetSyncState();
await syncEngine.fullSync();
```

### 2. Storage Quota Exceeded

#### Symptoms
- "Storage full" errors
- Cannot save new data
- App crashes on data operations

#### Diagnosis
```typescript
const storage = await StorageDiagnostics.analyze();
console.log('Storage usage:', {
  used: storage.used,
  available: storage.available,
  percentage: storage.percentage,
  largestTables: storage.largestTables
});
```

#### Solutions

**1. Clean up old data**
```typescript
// Remove old cached files
await CacheManager.cleanOldFiles({
  olderThan: 30 * 24 * 60 * 60 * 1000 // 30 days
});

// Compact database
await database.compact();
```

**2. Implement data retention policy**
```typescript
const retentionPolicy = new RetentionPolicy({
  maxAge: 180, // days
  maxRecords: 10000,
  preserveCritical: true
});

await retentionPolicy.apply();
```

### 3. Conflict Resolution Failures

#### Symptoms
- Duplicate records
- Data inconsistencies
- Manual review queue growing

#### Diagnosis
```typescript
const conflicts = await ConflictDiagnostics.analyze();
console.log('Conflict statistics:', {
  total: conflicts.total,
  unresolved: conflicts.unresolved,
  types: conflicts.byType,
  age: conflicts.oldestUnresolved
});
```

#### Solutions

**1. Review conflict patterns**
```typescript
const patterns = await ConflictAnalyzer.findPatterns();
if (patterns.includes('timestamp_skew')) {
  await TimeSync.calibrate();
}
```

**2. Batch resolve similar conflicts**
```typescript
const similar = await ConflictResolver.groupSimilar();
for (const group of similar) {
  if (group.canAutoResolve) {
    await ConflictResolver.batchResolve(group.conflicts);
  }
}
```

### 4. Performance Degradation

#### Symptoms
- Slow app response
- High memory usage
- Battery drain

#### Diagnosis
```typescript
const perf = await PerformanceDiagnostics.profile();
console.log('Performance metrics:', {
  queryTime: perf.averageQueryTime,
  memoryUsage: perf.memoryUsage,
  activeConnections: perf.activeConnections,
  cacheHitRate: perf.cacheHitRate
});
```

#### Solutions

**1. Optimize database queries**
```typescript
// Add missing indexes
await database.createIndex('patients', ['lastUpdated']);
await database.createIndex('records', ['patientId', 'type']);

// Enable query optimization
database.enableQueryOptimizer();
```

**2. Implement lazy loading**
```typescript
const lazyLoader = new LazyLoadManager({
  pageSize: 20,
  preloadAhead: 2,
  cacheSize: 100
});
```

### 5. Authentication Issues

#### Symptoms
- 401/403 errors during sync
- Token expiration during offline period
- Cannot authenticate after coming online

#### Solutions

**1. Implement token refresh**
```typescript
const tokenManager = new TokenManager({
  refreshBefore: 5 * 60 * 1000, // 5 minutes
  maxRetries: 3,
  offlineGracePeriod: 7 * 24 * 60 * 60 * 1000 // 7 days
});

tokenManager.on('token-refreshed', (token) => {
  syncEngine.updateAuthToken(token);
});
```

**2. Handle offline authentication**
```typescript
// Cache credentials securely
await SecureStorage.store('offline_auth', {
  token: encryptedToken,
  expiry: tokenExpiry,
  refreshToken: encryptedRefreshToken
});
```

## Debugging Tools

### 1. Offline Debugger

```typescript
class OfflineDebugger {
  static async generateReport(): Promise<DebugReport> {
    return {
      timestamp: new Date().toISOString(),
      deviceInfo: await this.getDeviceInfo(),
      storageInfo: await this.getStorageInfo(),
      syncInfo: await this.getSyncInfo(),
      errorLog: await this.getErrorLog(),
      performanceMetrics: await this.getPerformanceMetrics()
    };
  }
  
  static async exportLogs(): Promise<string> {
    const logs = await this.collectLogs();
    return this.formatForExport(logs);
  }
}
```

### 2. Network Simulator

```typescript
// Simulate various network conditions
const simulator = new NetworkSimulator();

// Test offline mode
await simulator.goOffline();
// Make changes
await simulator.goOnline();
// Verify sync

// Test poor connectivity
await simulator.simulateCondition({
  latency: 2000,
  packetLoss: 0.1,
  bandwidth: 56 // kbps
});
```

### 3. Sync Monitor

```typescript
const monitor = new SyncMonitor();

monitor.on('sync-start', (e) => {
  console.log('Sync started:', e.timestamp);
});

monitor.on('sync-progress', (e) => {
  console.log(`Sync progress: ${e.progress}%`);
});

monitor.on('sync-error', (e) => {
  console.error('Sync error:', e.error);
});

monitor.enable();
```

## Platform-Specific Issues

### iOS Issues

#### Problem: Background sync not working
```swift
// Ensure background modes are enabled
// In Info.plist:
<key>UIBackgroundModes</key>
<array>
    <string>fetch</string>
    <string>remote-notification</string>
</array>
```

#### Problem: Keychain access in background
```typescript
// Use accessible option
await Keychain.setInternetCredentials(
  server,
  username,
  password,
  { accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY }
);
```

### Android Issues

#### Problem: Doze mode killing sync
```typescript
// Request battery optimization exemption
if (Platform.OS === 'android') {
  await PowerManager.requestIgnoreBatteryOptimizations();
}
```

#### Problem: Storage permissions
```typescript
// Check and request permissions
const granted = await PermissionsAndroid.request(
  PermissionsAndroid.PERMISSIONS.WRITE_EXTERNAL_STORAGE
);
```

### Web Issues

#### Problem: IndexedDB quota exceeded
```typescript
// Request persistent storage
if (navigator.storage && navigator.storage.persist) {
  const persistent = await navigator.storage.persist();
  console.log('Persistent storage:', persistent);
}
```

#### Problem: Service Worker not updating
```javascript
// Force update service worker
navigator.serviceWorker.getRegistration().then(reg => {
  reg.update();
});
```

## Error Recovery Procedures

### 1. Database Corruption Recovery

```typescript
async function recoverDatabase() {
  try {
    // 1. Backup current state
    await DatabaseBackup.create('pre_recovery');
    
    // 2. Run integrity check
    const issues = await database.checkIntegrity();
    
    // 3. Attempt repair
    for (const issue of issues) {
      await database.repair(issue);
    }
    
    // 4. Verify repair
    const postCheck = await database.checkIntegrity();
    if (postCheck.length > 0) {
      // Restore from backup
      await DatabaseBackup.restore('last_known_good');
    }
  } catch (error) {
    console.error('Database recovery failed:', error);
    // Nuclear option: reset database
    await database.reset();
    await syncEngine.fullSync();
  }
}
```

### 2. Sync State Recovery

```typescript
async function recoverSyncState() {
  // 1. Clear corrupted sync metadata
  await syncEngine.clearMetadata();
  
  // 2. Rebuild sync state from local data
  const localData = await database.getAllRecords();
  await syncEngine.rebuildSyncState(localData);
  
  // 3. Request full sync
  await syncEngine.fullSync({
    compareChecksums: true,
    resolveConflicts: true
  });
}
```

### 3. Queue Recovery

```typescript
async function recoverQueue() {
  const queue = await QueueManager.getAll();
  const recovered = [];
  
  for (const item of queue) {
    try {
      // Validate queue item
      await QueueValidator.validate(item);
      recovered.push(item);
    } catch (error) {
      console.error(`Invalid queue item ${item.id}:`, error);
      // Log for manual review
      await ErrorLog.log('queue_corruption', { item, error });
    }
  }
  
  // Rebuild queue with valid items
  await QueueManager.rebuild(recovered);
}
```

## Performance Profiling

### Memory Profiling

```typescript
const memoryProfile = await MemoryProfiler.capture();
console.log('Memory usage by component:', {
  database: memoryProfile.database,
  cache: memoryProfile.cache,
  syncQueue: memoryProfile.syncQueue,
  documents: memoryProfile.documents
});

// Find memory leaks
const leaks = await MemoryProfiler.findLeaks();
if (leaks.length > 0) {
  console.warn('Potential memory leaks:', leaks);
}
```

### Query Performance

```typescript
// Enable query profiling
database.enableProfiling();

// Run operations
await performDatabaseOperations();

// Get profile results
const profile = database.getProfile();
console.log('Slow queries:', profile.slowQueries);
console.log('Missing indexes:', profile.suggestedIndexes);
```

## Monitoring and Alerts

### Setup Monitoring

```typescript
const monitoring = new OfflineMonitoring({
  metricsInterval: 60000, // 1 minute
  alertThresholds: {
    queueSize: 1000,
    syncFailures: 5,
    storageUsage: 0.9, // 90%
    conflictRate: 0.1 // 10%
  }
});

monitoring.on('alert', (alert) => {
  console.error('Offline alert:', alert);
  // Send to monitoring service
  Analytics.track('offline_alert', alert);
});

monitoring.start();
```

### Health Checks

```typescript
class OfflineHealthCheck {
  static async run(): Promise<HealthStatus> {
    const checks = await Promise.all([
      this.checkStorage(),
      this.checkDatabase(),
      this.checkSyncQueue(),
      this.checkConflicts(),
      this.checkPerformance()
    ]);
    
    return {
      healthy: checks.every(c => c.healthy),
      checks: checks,
      timestamp: new Date().toISOString()
    };
  }
  
  static async autoFix(): Promise<void> {
    const health = await this.run();
    
    for (const check of health.checks) {
      if (!check.healthy && check.autoFixAvailable) {
        await check.autoFix();
      }
    }
  }
}
```

## Best Practices for Debugging

1. **Enable verbose logging in development**
```typescript
if (__DEV__) {
  OfflineLogger.setLevel('verbose');
  OfflineLogger.enableFileLogging();
}
```

2. **Add breadcrumbs for error tracking**
```typescript
ErrorTracking.addBreadcrumb({
  message: 'Starting offline sync',
  category: 'offline',
  data: { queueSize: queue.length }
});
```

3. **Use debug panels in development**
```typescript
if (__DEV__) {
  return (
    <>
      <App />
      <OfflineDebugPanel />
    </>
  );
}
```

4. **Export diagnostic data**
```typescript
async function exportDiagnostics() {
  const data = await OfflineDebugger.generateReport();
  const json = JSON.stringify(data, null, 2);
  await FileSystem.writeAsStringAsync(
    `${FileSystem.documentDirectory}diagnostics.json`,
    json
  );
}
```

## Emergency Procedures

### Complete Offline Reset

```typescript
async function emergencyReset() {
  console.warn('Starting emergency offline reset');
  
  try {
    // 1. Stop all offline operations
    await syncEngine.stop();
    await QueueManager.pause();
    
    // 2. Backup critical data
    const backup = await createEmergencyBackup();
    
    // 3. Clear all offline data
    await database.clear();
    await cache.clear();
    await QueueManager.clear();
    
    // 4. Re-initialize
    await OfflineManager.initialize();
    
    // 5. Restore critical data
    await restoreFromBackup(backup);
    
    // 6. Force full sync
    await syncEngine.fullSync();
    
    console.log('Emergency reset completed');
  } catch (error) {
    console.error('Emergency reset failed:', error);
    // Last resort: reinstall app
    Alert.alert(
      'Critical Error',
      'Please reinstall the app to recover offline functionality'
    );
  }
}
```

## Contact Support

If issues persist after trying these solutions:

1. Export diagnostic logs
2. Note reproduction steps
3. Include device information
4. Contact: support@havenhealthpassport.org

Remember: Patient data integrity is paramount. When in doubt, preserve data and seek assistance rather than attempting risky fixes.