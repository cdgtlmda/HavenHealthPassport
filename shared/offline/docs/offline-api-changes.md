# Offline API Documentation

## Overview

This document describes the API changes and additions required to support offline functionality in Haven Health Passport.

## Table of Contents

1. [API Design Principles](#api-design-principles)
2. [Sync Endpoints](#sync-endpoints)
3. [Conflict Resolution Endpoints](#conflict-resolution-endpoints)
4. [Version Management](#version-management)
5. [Batch Operations](#batch-operations)
6. [WebSocket APIs](#websocket-apis)
7. [Error Handling](#error-handling)
8. [Authentication](#authentication)

## API Design Principles

### Offline-First Design

1. **Idempotent Operations**: All write operations must be idempotent
2. **Version Tracking**: Every resource includes version information
3. **Batch Support**: APIs support batch operations to reduce round trips
4. **Delta Updates**: Support partial updates to minimize data transfer
5. **Conflict Detection**: APIs return conflict information when applicable

### RESTful Extensions

```http
# Standard headers for offline support
X-Sync-Token: <sync-token>
X-Device-ID: <device-uuid>
X-Request-ID: <unique-request-id>
X-Vector-Clock: <base64-encoded-vector-clock>
```

## Sync Endpoints

### 1. Initialize Sync

```http
POST /api/v1/sync/initialize
Authorization: Bearer <token>
X-Device-ID: <device-uuid>

{
  "deviceInfo": {
    "platform": "ios",
    "version": "1.0.0",
    "capabilities": ["delta_sync", "compression"]
  }
}

Response:
{
  "syncToken": "sync_token_123",
  "deviceId": "device_uuid",
  "serverTime": "2024-01-01T00:00:00Z",
  "syncEndpoints": {
    "push": "/api/v1/sync/push",
    "pull": "/api/v1/sync/pull",
    "status": "/api/v1/sync/status"
  }
}
```

### 2. Push Changes

```http
POST /api/v1/sync/push
Authorization: Bearer <token>
X-Sync-Token: <sync-token>
Content-Type: application/json

{
  "changes": [
    {
      "id": "record_123",
      "collection": "patients",
      "operation": "update",
      "data": { /* record data */ },
      "version": 2,
      "vectorClock": { "device1": 10, "server": 15 }
    }
  ],
  "lastSyncTimestamp": "2024-01-01T00:00:00Z"
}

Response:
{
  "accepted": ["record_123"],
  "rejected": [],
  "conflicts": [
    {
      "id": "record_456",
      "reason": "version_conflict",
      "localVersion": 2,
      "serverVersion": 3,
      "suggestion": "use_server"
    }
  ],
  "syncToken": "new_sync_token"
}
```

### 3. Pull Changes

```http
GET /api/v1/sync/pull?since=2024-01-01T00:00:00Z&limit=100
Authorization: Bearer <token>
X-Sync-Token: <sync-token>

Response:
{
  "changes": [
    {
      "id": "record_789",
      "collection": "prescriptions",
      "operation": "create",
      "data": { /* record data */ },
      "version": 1,
      "timestamp": "2024-01-01T10:00:00Z"
    }
  ],
  "hasMore": false,
  "syncToken": "updated_sync_token",
  "deletions": ["record_999"]
}
```

### 4. Full Sync

```http
POST /api/v1/sync/full
Authorization: Bearer <token>
X-Device-ID: <device-uuid>

{
  "collections": ["patients", "records", "prescriptions"],
  "includeDeleted": false,
  "checksum": true
}

Response:
{
  "data": {
    "patients": [ /* all patient records */ ],
    "records": [ /* all health records */ ],
    "prescriptions": [ /* all prescriptions */ ]
  },
  "checksums": {
    "patients": "sha256_hash",
    "records": "sha256_hash",
    "prescriptions": "sha256_hash"
  },
  "syncToken": "full_sync_token",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Conflict Resolution Endpoints

### 1. Get Conflicts

```http
GET /api/v1/conflicts?status=unresolved
Authorization: Bearer <token>

Response:
{
  "conflicts": [
    {
      "id": "conflict_123",
      "recordId": "patient_456",
      "type": "update_update",
      "createdAt": "2024-01-01T00:00:00Z",
      "localVersion": { /* local data */ },
      "serverVersion": { /* server data */ },
      "suggestedResolution": "use_latest",
      "requiresManualReview": false
    }
  ],
  "total": 1
}
```

### 2. Resolve Conflict

```http
POST /api/v1/conflicts/conflict_123/resolve
Authorization: Bearer <token>
Content-Type: application/json

{
  "resolution": "merge",
  "mergedData": { /* merged record */ },
  "resolvedBy": "user_123",
  "reason": "Manual merge of contact information"
}

Response:
{
  "success": true,
  "recordId": "patient_456",
  "newVersion": 4,
  "vectorClock": { "device1": 11, "server": 17 }
}
```

### 3. Batch Resolve

```http
POST /api/v1/conflicts/batch-resolve
Authorization: Bearer <token>
Content-Type: application/json

{
  "resolutions": [
    {
      "conflictId": "conflict_123",
      "strategy": "use_server"
    },
    {
      "conflictId": "conflict_124",
      "strategy": "use_local"
    }
  ]
}

Response:
{
  "resolved": ["conflict_123", "conflict_124"],
  "failed": [],
  "errors": []
}
```

## Version Management

### 1. Get Version History

```http
GET /api/v1/records/{id}/versions
Authorization: Bearer <token>

Response:
{
  "versions": [
    {
      "version": 3,
      "timestamp": "2024-01-01T12:00:00Z",
      "modifiedBy": "user_123",
      "changeType": "update",
      "fields": ["medications", "allergies"]
    },
    {
      "version": 2,
      "timestamp": "2024-01-01T10:00:00Z",
      "modifiedBy": "user_456",
      "changeType": "update",
      "fields": ["contact_info"]
    }
  ],
  "currentVersion": 3
}
```

### 2. Get Specific Version

```http
GET /api/v1/records/{id}/versions/{version}
Authorization: Bearer <token>

Response:
{
  "id": "record_123",
  "version": 2,
  "data": { /* record data at version 2 */ },
  "timestamp": "2024-01-01T10:00:00Z",
  "vectorClock": { "device1": 8, "server": 12 }
}
```

### 3. Restore Version

```http
POST /api/v1/records/{id}/restore
Authorization: Bearer <token>
Content-Type: application/json

{
  "targetVersion": 2,
  "reason": "Reverting incorrect medication update"
}

Response:
{
  "success": true,
  "newVersion": 4,
  "restoredFrom": 2
}
```

## Batch Operations

### 1. Batch Create/Update

```http
POST /api/v1/batch
Authorization: Bearer <token>
Content-Type: application/json

{
  "operations": [
    {
      "method": "POST",
      "path": "/patients",
      "body": { /* patient data */ },
      "requestId": "req_123"
    },
    {
      "method": "PATCH",
      "path": "/patients/123",
      "body": { /* update data */ },
      "requestId": "req_124"
    }
  ]
}

Response:
{
  "results": [
    {
      "requestId": "req_123",
      "status": 201,
      "body": { "id": "patient_789", /* created patient */ }
    },
    {
      "requestId": "req_124",
      "status": 200,
      "body": { /* updated patient */ }
    }
  ]
}
```

### 2. Batch Delete

```http
DELETE /api/v1/batch
Authorization: Bearer <token>
Content-Type: application/json

{
  "ids": ["record_1", "record_2", "record_3"],
  "collection": "records"
}

Response:
{
  "deleted": ["record_1", "record_3"],
  "failed": [
    {
      "id": "record_2",
      "reason": "not_found"
    }
  ]
}
```

## WebSocket APIs

### 1. Real-time Sync

```javascript
// Connect to sync WebSocket
const ws = new WebSocket('wss://api.haven.health/sync');

// Authentication
ws.send(JSON.stringify({
  type: 'auth',
  token: 'bearer_token',
  deviceId: 'device_uuid'
}));

// Subscribe to changes
ws.send(JSON.stringify({
  type: 'subscribe',
  collections: ['patients', 'records'],
  since: '2024-01-01T00:00:00Z'
}));

// Receive updates
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  switch (message.type) {
    case 'change':
      // Handle real-time change
      handleChange(message.data);
      break;
    case 'conflict':
      // Handle conflict notification
      handleConflict(message.conflict);
      break;
  }
};
```

### 2. Collaborative Editing

```javascript
// Join editing session
ws.send(JSON.stringify({
  type: 'join_session',
  documentId: 'doc_123',
  mode: 'collaborative'
}));

// Send operation
ws.send(JSON.stringify({
  type: 'operation',
  op: {
    action: 'insert',
    position: 42,
    text: 'New text',
    vectorClock: { 'user_123': 5 }
  }
}));

// Receive operations
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.type === 'operation') {
    applyOperation(message.op);
  }
};
```

## Error Handling

### Error Response Format

```json
{
  "error": {
    "code": "SYNC_CONFLICT",
    "message": "Synchronization conflict detected",
    "details": {
      "conflictingRecords": ["record_123", "record_456"],
      "suggestion": "manual_review"
    },
    "timestamp": "2024-01-01T00:00:00Z",
    "requestId": "req_uuid"
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `SYNC_TOKEN_INVALID` | 401 | Sync token expired or invalid |
| `SYNC_CONFLICT` | 409 | Conflict detected during sync |
| `VERSION_MISMATCH` | 409 | Record version mismatch |
| `QUOTA_EXCEEDED` | 429 | Sync quota exceeded |
| `INVALID_VECTOR_CLOCK` | 400 | Vector clock format invalid |
| `DEVICE_NOT_REGISTERED` | 403 | Device not registered for sync |
| `SYNC_IN_PROGRESS` | 423 | Another sync operation in progress |

### Retry Headers

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1704067200
```

## Authentication

### Offline Token Management

```http
POST /api/v1/auth/offline-token
Authorization: Bearer <online-token>

{
  "deviceId": "device_uuid",
  "validityDays": 30
}

Response:
{
  "offlineToken": "offline_token_xyz",
  "expiresAt": "2024-02-01T00:00:00Z",
  "refreshToken": "refresh_token_abc",
  "capabilities": ["read", "write", "sync"]
}
```

### Token Refresh

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refreshToken": "refresh_token_abc",
  "deviceId": "device_uuid"
}

Response:
{
  "accessToken": "new_access_token",
  "expiresIn": 3600,
  "refreshToken": "new_refresh_token"
}
```

## SDK Examples

### JavaScript/TypeScript SDK

```typescript
import { HavenOfflineSDK } from '@haven-health/offline-sdk';

// Initialize
const sdk = new HavenOfflineSDK({
  apiUrl: 'https://api.haven.health',
  deviceId: 'device_uuid',
  authToken: 'bearer_token'
});

// Sync operations
const syncResult = await sdk.sync.push(changes);
const updates = await sdk.sync.pull({ since: lastSync });

// Conflict resolution
const conflicts = await sdk.conflicts.list();
await sdk.conflicts.resolve(conflictId, 'use_server');

// Batch operations
const results = await sdk.batch([
  { method: 'POST', path: '/patients', body: patientData },
  { method: 'PATCH', path: '/records/123', body: updateData }
]);
```

### Swift SDK

```swift
import HavenOfflineSDK

// Initialize
let sdk = HavenOfflineSDK(
    apiUrl: "https://api.haven.health",
    deviceId: deviceId,
    authToken: authToken
)

// Sync operations
sdk.sync.push(changes) { result in
    switch result {
    case .success(let response):
        print("Synced: \(response.accepted.count) records")
    case .failure(let error):
        print("Sync failed: \(error)")
    }
}

// Conflict resolution
sdk.conflicts.resolve(
    conflictId: "conflict_123",
    strategy: .useServer
) { result in
    // Handle result
}
```

## Best Practices

1. **Always include request IDs** for debugging and idempotency
2. **Use compression** for large payloads (gzip/deflate)
3. **Implement exponential backoff** for retries
4. **Monitor sync performance** and adjust batch sizes
5. **Handle partial failures** in batch operations
6. **Version your API changes** to maintain compatibility
7. **Use ETags** for efficient caching
8. **Implement rate limiting** per device
9. **Log all conflict resolutions** for audit
10. **Test with various network conditions**

## Migration Guide

### From Online-Only to Offline API

1. **Add version tracking** to all resources
2. **Implement vector clocks** for distributed consistency
3. **Create sync endpoints** as documented above
4. **Add conflict detection** to write operations
5. **Update authentication** for offline tokens
6. **Test thoroughly** with offline scenarios

### Backward Compatibility

Maintain compatibility by:
- Supporting both old and new endpoints during transition
- Using API versioning (v1, v2)
- Providing migration tools for clients
- Documenting breaking changes clearly

## Conclusion

The offline API extensions provide robust support for offline functionality while maintaining compatibility with existing systems. Always prioritize data integrity and provide clear conflict resolution paths for healthcare data.