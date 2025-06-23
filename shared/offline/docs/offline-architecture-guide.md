# Offline Architecture Guide

## Table of Contents

1. [Overview](#overview)
2. [Core Concepts](#core-concepts)
3. [Architecture Components](#architecture-components)
4. [Data Flow](#data-flow)
5. [Implementation Details](#implementation-details)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

## Overview

The Haven Health Passport offline architecture is designed to provide full functionality without internet connectivity, ensuring healthcare access in remote or connectivity-challenged areas. This guide covers the technical implementation of our offline-first approach.

### Key Features

- **Complete Offline Functionality**: All core features work without internet
- **Intelligent Sync**: Automatic synchronization when connectivity is restored
- **Conflict Resolution**: Advanced CRDT-based conflict resolution
- **Progressive Enhancement**: Features adapt based on connectivity quality
- **Cross-Platform**: Unified offline architecture for mobile and web

## Core Concepts

### Offline-First Design

Our offline-first approach means:
- Data is stored locally first, then synced to the cloud
- User actions are immediately reflected in the UI (optimistic updates)
- Background sync handles data propagation
- Conflicts are resolved automatically using CRDTs

### Data Storage Hierarchy

```
┌─────────────────────────────────────┐
│         User Interface              │
├─────────────────────────────────────┤
│      Offline State Manager          │
├─────────────────────────────────────┤
│   Cache Layer (In-Memory)           │
├─────────────────────────────────────┤
│ Persistent Storage (WatermelonDB)   │
├─────────────────────────────────────┤
│    File System (Documents)          │
└─────────────────────────────────────┘
```

### Sync Strategy

1. **Queue-Based Sync**: All changes are queued locally
2. **Priority Sync**: Critical data (medical records) synced first
3. **Delta Sync**: Only changes are transmitted
4. **Batch Processing**: Multiple changes bundled for efficiency

## Architecture Components

### 1. Storage Layer

#### WatermelonDB (Mobile)
- SQLite-based reactive database
- Lazy loading for performance
- Built-in sync primitives
- Observable queries for real-time updates

#### IndexedDB (Web)
- Browser-based storage
- Structured data storage
- Transaction support
- Large storage quotas

### 2. Sync Engine

#### BaseSyncEngine
Core synchronization logic handling:
- Change detection
- Queue management
- Conflict resolution
- Network state monitoring

```typescript
class BaseSyncEngine {
  // Sync lifecycle
  async startSync(): Promise<void>
  async stopSync(): Promise<void>
  
  // Data operations
  async push(changes: Change[]): Promise<void>
  async pull(lastSync: Date): Promise<Change[]>
  
  // Conflict resolution
  async resolveConflicts(conflicts: Conflict[]): Promise<Resolution[]>
}
```

#### QueueManager
Manages offline operation queue:
- Operation ordering
- Retry logic
- Priority handling
- Failure recovery

### 3. Conflict Resolution

#### CRDT Implementation
- **VersionVector**: Tracks document versions across devices
- **OperationBasedCRDT**: Commutative operations for automatic merging
- **DeltaSync**: Efficient synchronization of changes
- **GarbageCollector**: Cleans up old CRDT metadata

#### Conflict Types
1. **Update-Update**: Same field modified on different devices
2. **Delete-Update**: Document deleted on one device, updated on another
3. **Schema Conflicts**: Data structure changes between versions

### 4. Document Management

#### ChunkBasedFileSync
- Large file handling with chunked uploads/downloads
- Resume capability for interrupted transfers
- Checksum verification
- Bandwidth optimization

#### BinaryDiff
- Efficient binary diff algorithm
- Reduces upload size for document updates
- Supports incremental updates

### 5. Network Optimization

#### RequestBatcher
- Combines multiple API calls
- Reduces network overhead
- Priority-based processing
- Automatic retry handling

#### ConnectionPoolManager
- Reuses connections
- Multiplexing support
- Automatic failover
- Connection health monitoring

#### CircuitBreaker
- Prevents cascade failures
- Automatic service recovery
- Configurable thresholds
- State-based request handling

## Data Flow

### 1. Write Path
```
User Action
    ↓
Local Storage (Immediate)
    ↓
Queue Manager (Background)
    ↓
Sync Engine (When Online)
    ↓
Server
```

### 2. Read Path
```
Data Request
    ↓
Memory Cache (Fast)
    ↓ (miss)
Local Database (Offline)
    ↓ (miss)
Server Fetch (Online Only)
    ↓
Update Local Storage
```

### 3. Sync Flow
```
Network Available
    ↓
Check Queue
    ↓
Batch Operations
    ↓
Send to Server
    ↓
Handle Conflicts
    ↓
Update Local State
    ↓
Notify UI
```

## Implementation Details

### Mobile Implementation

#### React Native Setup
```typescript
import { Database } from '@nozbe/watermelondb';
import SQLiteAdapter from '@nozbe/watermelondb/adapters/sqlite';
import { schema } from './schema';
import { migrations } from './migrations';

const adapter = new SQLiteAdapter({
  schema,
  migrations,
  jsi: true, // Enable JSI for better performance
  onSetUpError: error => {
    // Handle setup errors
  }
});

const database = new Database({
  adapter,
  modelClasses: [Patient, HealthRecord, Document],
});
```

#### Sync Configuration
```typescript
const syncConfig = {
  baseURL: 'https://api.havenhealthpassport.org',
  headers: {
    'Authorization': `Bearer ${token}`,
  },
  conflictResolver: new CRDTConflictResolver(),
  batchSize: 100,
  syncInterval: 5 * 60 * 1000, // 5 minutes
  enableDeltaSync: true,
};
```

### Web Implementation

#### Progressive Web App Setup
```javascript
// Service Worker Registration
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js')
    .then(registration => {
      console.log('ServiceWorker registered');
    });
}

// IndexedDB Setup
const db = await openDB('HavenHealthPassport', 1, {
  upgrade(db) {
    db.createObjectStore('patients', { keyPath: 'id' });
    db.createObjectStore('records', { keyPath: 'id' });
    db.createObjectStore('syncQueue', { keyPath: 'id' });
  },
});
```

#### Background Sync
```javascript
// Service Worker
self.addEventListener('sync', event => {
  if (event.tag === 'health-records-sync') {
    event.waitUntil(syncHealthRecords());
  }
});

async function syncHealthRecords() {
  const queue = await getQueuedOperations();
  const batcher = new RequestBatcher();
  
  for (const operation of queue) {
    await batcher.addRequest(operation.url, {
      method: operation.method,
      body: operation.data,
    });
  }
  
  await batcher.flush();
}
```

### Performance Optimization

#### Lazy Loading
```typescript
// Only load data as needed
const LazyLoadManager = new LazyLoadManager({
  preloadCount: 3,
  cacheSize: 50,
  priorityFetch: true,
});

// Register items for lazy loading
LazyLoadManager.registerItems(documents);

// Load when visible
LazyLoadManager.setVisibleItems(visibleIds);
```

#### Memory Management
```typescript
const memoryMonitor = new MemoryMonitor({
  sampleInterval: 5000,
  thresholds: {
    warning: 70,
    critical: 85,
    oom: 95,
  },
});

memoryMonitor.registerCleanupCallback(async () => {
  await clearImageCache();
  await compactDatabase();
});
```

## Best Practices

### 1. Data Modeling
- Design for eventual consistency
- Use unique IDs (UUIDs) for all entities
- Include version/timestamp in all records
- Avoid complex relationships that can't be resolved offline

### 2. Sync Strategy
- Sync critical data first (medical records, prescriptions)
- Use exponential backoff for retries
- Implement data priority levels
- Batch similar operations

### 3. Error Handling
- Always provide offline fallbacks
- Show clear sync status to users
- Log sync errors for debugging
- Implement retry mechanisms

### 4. Security
- Encrypt sensitive data at rest
- Use secure communication channels
- Implement device-level authentication
- Regular security audits

### 5. Testing
- Test with various network conditions
- Simulate conflicts and resolutions
- Test with large datasets
- Verify data integrity after sync

## Troubleshooting

### Common Issues

#### 1. Sync Conflicts
**Problem**: Data conflicts after offline period
**Solution**: 
- Review conflict resolution logs
- Check CRDT implementation
- Verify timestamp accuracy
- Ensure unique IDs

#### 2. Storage Quota Exceeded
**Problem**: Running out of local storage
**Solution**:
- Implement data retention policies
- Clean up old cache entries
- Compress large files
- Use selective sync

#### 3. Performance Degradation
**Problem**: App becomes slow with large datasets
**Solution**:
- Implement pagination
- Use virtual scrolling
- Optimize database queries
- Enable lazy loading

#### 4. Sync Failures
**Problem**: Data not syncing to server
**Solution**:
- Check network connectivity
- Verify authentication tokens
- Review server logs
- Check for data validation errors

### Debug Tools

#### Logging
```typescript
import { OfflineLogger } from './logging';

const logger = new OfflineLogger({
  logLevel: 'debug',
  persistLogs: true,
  maxLogSize: 10 * 1024 * 1024, // 10MB
});

// Use throughout the app
logger.debug('Sync started', { timestamp: Date.now() });
logger.error('Sync failed', { error, context });
```

#### Sync Inspector
```typescript
const syncInspector = new SyncInspector();

// Get sync status
const status = syncInspector.getStatus();
console.log('Pending operations:', status.pendingCount);
console.log('Last sync:', status.lastSyncTime);
console.log('Sync errors:', status.errors);

// Export sync data for debugging
const debugData = await syncInspector.exportDebugData();
```

### Performance Monitoring

#### Metrics to Track
- Sync duration
- Queue size
- Conflict frequency
- Storage usage
- Battery impact
- Network usage

#### Implementation
```typescript
const performanceMonitor = new PerformanceMonitor();

performanceMonitor.startMeasure('sync');
await syncEngine.sync();
const duration = performanceMonitor.endMeasure('sync');

performanceMonitor.recordMetric('sync_duration', duration);
performanceMonitor.recordMetric('queue_size', queue.length);
```

## Advanced Topics

### Custom Conflict Resolution
```typescript
class MedicalRecordConflictResolver extends ConflictResolver {
  async resolve(local: any, remote: any): Promise<any> {
    // Medical records require special handling
    if (local.type === 'prescription') {
      // Never auto-resolve prescription conflicts
      return { requiresManualReview: true, local, remote };
    }
    
    // For other records, use timestamp
    return local.updatedAt > remote.updatedAt ? local : remote;
  }
}
```

### Selective Sync
```typescript
const selectiveSync = new SelectiveSync({
  // Only sync records from last 6 months
  recordFilter: (record) => {
    const sixMonthsAgo = Date.now() - (6 * 30 * 24 * 60 * 60 * 1000);
    return record.createdAt > sixMonthsAgo;
  },
  
  // Priority for different record types
  priorities: {
    'prescription': 1,
    'lab_result': 2,
    'appointment': 3,
    'note': 4,
  },
});
```

### Offline Analytics
```typescript
const offlineAnalytics = new OfflineAnalytics();

// Track user actions offline
offlineAnalytics.track('document_viewed', {
  documentId: 'abc123',
  timestamp: Date.now(),
  offline: true,
});

// Sync analytics when online
networkMonitor.on('online', async () => {
  await offlineAnalytics.flush();
});
```

## Migration Guide

### From Online-Only to Offline-First

1. **Database Migration**
   - Export existing data
   - Set up local database schema
   - Import data with proper IDs
   - Verify data integrity

2. **API Updates**
   - Implement sync endpoints
   - Add conflict resolution
   - Support delta updates
   - Version API responses

3. **Client Updates**
   - Add offline storage
   - Implement sync engine
   - Update UI for offline states
   - Add conflict resolution UI

4. **Testing**
   - Test migration process
   - Verify data consistency
   - Test offline scenarios
   - Monitor performance

## Conclusion

The offline architecture provides robust healthcare data access regardless of connectivity. By following this guide and best practices, you can ensure reliable offline functionality for critical healthcare applications.

For specific implementation questions or issues, refer to the troubleshooting section or contact the development team.