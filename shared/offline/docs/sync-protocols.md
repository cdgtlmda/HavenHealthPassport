# Sync Protocols Documentation

## Overview

This document describes the synchronization protocols used in Haven Health Passport for offline data synchronization. Our sync protocols ensure data consistency, handle conflicts, and optimize for low-bandwidth environments.

## Table of Contents

1. [Protocol Overview](#protocol-overview)
2. [Sync States](#sync-states)
3. [Message Format](#message-format)
4. [Sync Operations](#sync-operations)
5. [Conflict Resolution](#conflict-resolution)
6. [Security](#security)
7. [Error Handling](#error-handling)
8. [Performance Optimization](#performance-optimization)

## Protocol Overview

### Design Principles

1. **Eventual Consistency**: Data will eventually be consistent across all devices
2. **Offline-First**: All operations work offline and sync when possible
3. **Conflict-Free**: Use CRDTs to automatically resolve conflicts
4. **Bandwidth-Efficient**: Minimize data transfer with delta sync
5. **Secure**: End-to-end encryption for sensitive data

### Protocol Stack

```
┌─────────────────────────┐
│   Application Layer     │
├─────────────────────────┤
│   Sync Protocol Layer   │
├─────────────────────────┤
│   Security Layer        │
├─────────────────────────┤
│   Transport Layer       │
└─────────────────────────┘
```

## Sync States

### State Machine

```
┌──────────┐      ┌──────────┐      ┌──────────┐
│  IDLE    │ ───> │ SYNCING  │ ───> │ COMPLETE │
└──────────┘      └──────────┘      └──────────┘
     ↑                  │                  │
     │                  ↓                  │
     │            ┌──────────┐            │
     └──────────  │  ERROR   │ ←──────────┘
                  └──────────┘
```

### State Definitions

- **IDLE**: No sync in progress, waiting for trigger
- **SYNCING**: Active synchronization in progress
- **COMPLETE**: Sync completed successfully
- **ERROR**: Sync failed, will retry based on policy

## Message Format

### Base Message Structure

```json
{
  "version": "1.0",
  "messageId": "uuid",
  "timestamp": "2024-01-01T00:00:00Z",
  "deviceId": "device-uuid",
  "sessionId": "session-uuid",
  "type": "sync_request|sync_response|ack|error",
  "payload": {}
}
```

### Sync Request

```json
{
  "type": "sync_request",
  "payload": {
    "lastSyncTimestamp": "2024-01-01T00:00:00Z",
    "deviceInfo": {
      "platform": "ios|android|web",
      "version": "1.0.0",
      "capabilities": ["delta_sync", "compression", "encryption"]
    },
    "syncScope": {
      "collections": ["patients", "records", "documents"],
      "dateRange": {
        "from": "2023-01-01T00:00:00Z",
        "to": "2024-01-01T00:00:00Z"
      },
      "includeDeleted": false
    },
    "vectorClock": {
      "device1": 100,
      "device2": 95,
      "server": 150
    }
  }
}
```

### Sync Response

```json
{
  "type": "sync_response",
  "payload": {
    "changes": [
      {
        "id": "record-uuid",
        "collection": "patients",
        "operation": "create|update|delete",
        "data": {},
        "version": 2,
        "timestamp": "2024-01-01T00:00:00Z",
        "vectorClock": {
          "device1": 101,
          "server": 151
        }
      }
    ],
    "conflicts": [
      {
        "id": "record-uuid",
        "localVersion": {},
        "remoteVersion": {},
        "suggestedResolution": {}
      }
    ],
    "syncToken": "token-for-next-sync",
    "hasMore": false
  }
}
```

## Sync Operations

### 1. Initial Sync

```typescript
interface InitialSyncProtocol {
  // Client initiates
  async requestInitialSync(): Promise<InitialSyncRequest>;
  
  // Server responds with data
  async handleInitialSync(request: InitialSyncRequest): Promise<InitialSyncResponse>;
  
  // Client processes response
  async processInitialSync(response: InitialSyncResponse): Promise<void>;
}
```

**Flow:**
1. Client sends empty sync request
2. Server responds with all data for the user
3. Client stores data locally
4. Client acknowledges completion

### 2. Delta Sync

```typescript
interface DeltaSyncProtocol {
  // Client sends changes since last sync
  async requestDeltaSync(lastSync: Date): Promise<DeltaSyncRequest>;
  
  // Server merges changes and responds
  async handleDeltaSync(request: DeltaSyncRequest): Promise<DeltaSyncResponse>;
  
  // Client applies remote changes
  async processDeltaSync(response: DeltaSyncResponse): Promise<void>;
}
```

**Flow:**
1. Client collects local changes
2. Client sends changes with vector clock
3. Server detects conflicts
4. Server sends back changes and conflicts
5. Client resolves conflicts
6. Client updates vector clock

### 3. Push-Only Sync

```typescript
interface PushSyncProtocol {
  // Client pushes changes without pulling
  async pushChanges(changes: Change[]): Promise<PushResponse>;
  
  // Server acknowledges receipt
  async acknowledgePush(response: PushResponse): Promise<void>;
}
```

**Use Cases:**
- Low bandwidth scenarios
- Battery conservation
- Time-critical updates

### 4. Pull-Only Sync

```typescript
interface PullSyncProtocol {
  // Client requests updates only
  async pullChanges(since: Date): Promise<PullResponse>;
  
  // Client applies pulled changes
  async applyPulledChanges(changes: Change[]): Promise<void>;
}
```

**Use Cases:**
- Read-only devices
- Bandwidth optimization
- Scheduled updates

## Conflict Resolution

### CRDT-Based Resolution

```typescript
interface CRDTResolver {
  // Merge concurrent updates
  merge(local: CRDTDocument, remote: CRDTDocument): CRDTDocument;
  
  // Compare versions
  compare(v1: VersionVector, v2: VersionVector): Ordering;
  
  // Generate operations
  generateOp(change: Change): Operation;
}
```

### Resolution Strategies

#### 1. Last-Write-Wins (LWW)
```json
{
  "strategy": "lww",
  "resolution": {
    "field": "updatedAt",
    "direction": "max"
  }
}
```

#### 2. Multi-Value Register
```json
{
  "strategy": "mvr",
  "resolution": {
    "preserveAll": true,
    "userSelection": true
  }
}
```

#### 3. Operational Transform
```json
{
  "strategy": "ot",
  "resolution": {
    "transformFunction": "medical_record_transform",
    "preserveIntentions": true
  }
}
```

### Conflict Types

1. **Update-Update Conflicts**
   - Same field modified on different devices
   - Resolution: Use CRDT merge or timestamp

2. **Delete-Update Conflicts**
   - Record deleted on one device, updated on another
   - Resolution: Resurrect with marker or confirm deletion

3. **Schema Conflicts**
   - Different schema versions
   - Resolution: Migration or compatibility layer

## Security

### Encryption

```typescript
interface EncryptionProtocol {
  // End-to-end encryption
  async encryptPayload(data: any, recipientKey: string): Promise<EncryptedData>;
  
  // Decryption
  async decryptPayload(encrypted: EncryptedData, privateKey: string): Promise<any>;
  
  // Key exchange
  async exchangeKeys(deviceId: string): Promise<KeyPair>;
}
```

### Authentication

```typescript
interface AuthProtocol {
  // Device authentication
  async authenticateDevice(deviceId: string, token: string): Promise<boolean>;
  
  // Session management
  async createSyncSession(deviceId: string): Promise<Session>;
  
  // Token refresh
  async refreshToken(session: Session): Promise<string>;
}
```

### Data Integrity

```typescript
interface IntegrityProtocol {
  // Checksum verification
  async verifyChecksum(data: any, checksum: string): Promise<boolean>;
  
  // Digital signatures
  async signData(data: any, privateKey: string): Promise<Signature>;
  
  // Audit trail
  async logSyncEvent(event: SyncEvent): Promise<void>;
}
```

## Error Handling

### Error Types

```typescript
enum SyncError {
  NETWORK_ERROR = 'NETWORK_ERROR',
  AUTH_ERROR = 'AUTH_ERROR',
  CONFLICT_ERROR = 'CONFLICT_ERROR',
  QUOTA_EXCEEDED = 'QUOTA_EXCEEDED',
  VERSION_MISMATCH = 'VERSION_MISMATCH',
  CORRUPTION_ERROR = 'CORRUPTION_ERROR',
  TIMEOUT_ERROR = 'TIMEOUT_ERROR',
}
```

### Error Recovery

```typescript
interface ErrorRecovery {
  // Retry with exponential backoff
  async retryWithBackoff(operation: () => Promise<any>): Promise<any>;
  
  // Fallback strategies
  async fallback(error: SyncError): Promise<void>;
  
  // Error reporting
  async reportError(error: SyncError, context: any): Promise<void>;
}
```

### Recovery Strategies

1. **Network Errors**
   - Retry with exponential backoff
   - Queue for later retry
   - Switch to offline mode

2. **Conflict Errors**
   - Apply automatic resolution
   - Queue for manual review
   - Notify user

3. **Quota Errors**
   - Clean up old data
   - Request quota increase
   - Selective sync

## Performance Optimization

### Compression

```typescript
interface CompressionProtocol {
  // Compress before sending
  async compress(data: any): Promise<CompressedData>;
  
  // Decompress on receipt
  async decompress(compressed: CompressedData): Promise<any>;
  
  // Adaptive compression
  selectCompressionLevel(dataSize: number, bandwidth: number): number;
}
```

### Batching

```typescript
interface BatchingProtocol {
  // Batch multiple operations
  async batchOperations(ops: Operation[]): Promise<BatchedOperation>;
  
  // Optimal batch size
  calculateBatchSize(bandwidth: number, latency: number): number;
  
  // Priority batching
  prioritizeBatch(ops: Operation[]): Operation[];
}
```

### Bandwidth Management

```typescript
interface BandwidthProtocol {
  // Adaptive sync frequency
  calculateSyncInterval(bandwidth: number, dataSize: number): number;
  
  // Progressive sync
  async progressiveSync(data: any[], bandwidth: number): AsyncIterator<any>;
  
  // Bandwidth estimation
  async estimateBandwidth(): Promise<number>;
}
```

## Implementation Examples

### Client Implementation

```typescript
class SyncClient {
  private syncEngine: SyncEngine;
  private conflictResolver: ConflictResolver;
  private encryptionManager: EncryptionManager;
  
  async sync(): Promise<SyncResult> {
    try {
      // 1. Prepare local changes
      const localChanges = await this.collectLocalChanges();
      
      // 2. Encrypt sensitive data
      const encrypted = await this.encryptionManager.encryptChanges(localChanges);
      
      // 3. Send sync request
      const response = await this.syncEngine.sync({
        changes: encrypted,
        lastSync: this.lastSyncTimestamp,
        vectorClock: this.vectorClock,
      });
      
      // 4. Handle conflicts
      const resolved = await this.conflictResolver.resolve(response.conflicts);
      
      // 5. Apply changes
      await this.applyChanges(response.changes);
      await this.applyChanges(resolved);
      
      // 6. Update sync state
      this.updateSyncState(response.syncToken);
      
      return { success: true, synced: response.changes.length };
      
    } catch (error) {
      return this.handleSyncError(error);
    }
  }
}
```

### Server Implementation

```typescript
class SyncServer {
  private database: Database;
  private conflictDetector: ConflictDetector;
  private deltaCalculator: DeltaCalculator;
  
  async handleSync(request: SyncRequest): Promise<SyncResponse> {
    // 1. Authenticate device
    await this.authenticateDevice(request.deviceId);
    
    // 2. Apply client changes
    const conflicts = await this.applyClientChanges(request.changes);
    
    // 3. Calculate server changes
    const serverChanges = await this.deltaCalculator.calculate(
      request.lastSync,
      request.deviceId
    );
    
    // 4. Detect conflicts
    const detectedConflicts = await this.conflictDetector.detect(
      request.changes,
      serverChanges
    );
    
    // 5. Prepare response
    return {
      changes: serverChanges,
      conflicts: [...conflicts, ...detectedConflicts],
      syncToken: this.generateSyncToken(),
      vectorClock: this.updateVectorClock(request.vectorClock),
    };
  }
}
```

## Testing Sync Protocols

### Test Scenarios

1. **Normal Sync**
   - Both devices online
   - No conflicts
   - Verify data consistency

2. **Conflict Scenarios**
   - Concurrent updates
   - Delete conflicts
   - Schema migrations

3. **Network Issues**
   - Intermittent connectivity
   - Timeout handling
   - Resume capability

4. **Edge Cases**
   - Large datasets
   - Many devices
   - Rapid changes

### Test Implementation

```typescript
describe('Sync Protocol Tests', () => {
  it('should handle normal sync', async () => {
    const client = new SyncClient();
    const result = await client.sync();
    
    expect(result.success).toBe(true);
    expect(result.conflicts).toHaveLength(0);
  });
  
  it('should resolve conflicts', async () => {
    // Create conflicting changes
    const localChange = createChange('doc1', { name: 'Local' });
    const remoteChange = createChange('doc1', { name: 'Remote' });
    
    // Sync and verify resolution
    const result = await syncWithConflicts(localChange, remoteChange);
    
    expect(result.resolved).toBeDefined();
    expect(result.resolved.name).toBe('Local'); // LWW resolution
  });
});
```

## Monitoring and Debugging

### Metrics to Track

```typescript
interface SyncMetrics {
  // Performance metrics
  syncDuration: number;
  dataTransferred: number;
  conflictsResolved: number;
  
  // Reliability metrics
  syncSuccessRate: number;
  averageRetries: number;
  errorRate: number;
  
  // Usage metrics
  syncFrequency: number;
  averageChangeSetSize: number;
  activeDevices: number;
}
```

### Debug Tools

```typescript
class SyncDebugger {
  // Log all sync operations
  enableVerboseLogging(): void;
  
  // Capture sync traces
  startTrace(sessionId: string): void;
  
  // Export sync state
  exportSyncState(): SyncState;
  
  // Simulate sync scenarios
  simulateConflict(type: ConflictType): void;
  simulateNetworkError(errorType: NetworkError): void;
}
```

## Best Practices

1. **Always use vector clocks** for distributed consistency
2. **Implement idempotent operations** to handle retries
3. **Use compression** for large payloads
4. **Batch small changes** to reduce overhead
5. **Monitor sync performance** and adjust parameters
6. **Test with realistic data** volumes and network conditions
7. **Document conflict resolution** strategies clearly
8. **Implement proper error handling** and recovery
9. **Use encryption** for sensitive healthcare data
10. **Version your sync protocol** for compatibility

## Protocol Evolution

### Versioning Strategy

```typescript
interface ProtocolVersion {
  major: number;  // Breaking changes
  minor: number;  // New features
  patch: number;  // Bug fixes
}

// Version negotiation
async function negotiateVersion(
  clientVersion: ProtocolVersion,
  serverVersion: ProtocolVersion
): Promise<ProtocolVersion> {
  // Find compatible version
  if (clientVersion.major !== serverVersion.major) {
    throw new Error('Incompatible protocol versions');
  }
  
  // Use lower minor version for compatibility
  return {
    major: clientVersion.major,
    minor: Math.min(clientVersion.minor, serverVersion.minor),
    patch: 0,
  };
}
```

### Migration Path

1. **Announce deprecation** in advance
2. **Support multiple versions** during transition
3. **Provide migration tools** for clients
4. **Monitor adoption** of new versions
5. **Sunset old versions** gradually

## Conclusion

The sync protocols provide reliable, secure, and efficient data synchronization for offline-capable healthcare applications. Following these protocols ensures data consistency and optimal performance across all devices and network conditions.