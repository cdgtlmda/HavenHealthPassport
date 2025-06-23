# API Changes for Offline Support

## Overview

This document details all API changes and additions required to support offline functionality in Haven Health Passport. These changes ensure that the API can handle sync operations, conflict resolution, and provide the necessary endpoints for offline-first architecture.

## Table of Contents

1. [New Endpoints](#new-endpoints)
2. [Modified Endpoints](#modified-endpoints)
3. [Request/Response Changes](#requestresponse-changes)
4. [Authentication Changes](#authentication-changes)
5. [Error Handling](#error-handling)
6. [Versioning Strategy](#versioning-strategy)
7. [Migration Guide](#migration-guide)

## New Endpoints

### 1. Sync Endpoints

#### POST /api/v2/sync/pull
Retrieves changes since last sync.

**Request:**
```json
{
  "lastSyncTimestamp": "2024-01-01T00:00:00Z",
  "deviceId": "device-uuid",
  "collections": ["patients", "records", "documents"],
  "vectorClock": {
    "device1": 10,
    "device2": 15,
    "server": 25
  },
  "options": {
    "includeDeletions": true,
    "deltaSync": true,
    "maxRecords": 1000,
    "compression": "gzip"
  }
}
```

**Response:**
```json
{
  "changes": [
    {
      "collection": "patients",
      "operation": "create|update|delete",
      "id": "patient-uuid",
      "data": {},
      "version": "2",
      "timestamp": "2024-01-01T00:00:00Z",
      "vectorClock": {}
    }
  ],
  "hasMore": false,
  "nextSyncToken": "token",
  "serverVectorClock": {},
  "syncTimestamp": "2024-01-01T00:00:00Z"
}
```

#### POST /api/v2/sync/push
Pushes local changes to server.

**Request:**
```json
{
  "deviceId": "device-uuid",
  "changes": [
    {
      "collection": "patients",
      "operation": "update",
      "id": "patient-uuid",
      "data": {},
      "localVersion": "1",
      "baseVersion": "1",
      "vectorClock": {}
    }
  ],
  "options": {
    "atomicCommit": true,
    "conflictResolution": "server|client|manual"
  }
}
```

**Response:**
```json
{
  "accepted": ["change-id-1", "change-id-2"],
  "rejected": [
    {
      "changeId": "change-id-3",
      "reason": "conflict|validation|permission",
      "conflict": {
        "localVersion": "1",
        "serverVersion": "2",
        "serverData": {}
      }
    }
  ],
  "serverVectorClock": {},
  "syncTimestamp": "2024-01-01T00:00:00Z"
}
```

#### POST /api/v2/sync/resolve
Resolves conflicts manually.

**Request:**
```json
{
  "conflictId": "conflict-uuid",
  "resolution": {
    "strategy": "merge|local|server|custom",
    "data": {},
    "vectorClock": {}
  },
  "deviceId": "device-uuid"
}
```

**Response:**
```json
{
  "success": true,
  "resolvedVersion": "3",
  "vectorClock": {},
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 2. Batch Operations

#### POST /api/v2/batch
Executes multiple operations in a single request.

**Request:**
```json
{
  "operations": [
    {
      "method": "POST",
      "path": "/api/v2/patients",
      "body": {},
      "id": "op-1"
    },
    {
      "method": "PUT",
      "path": "/api/v2/records/123",
      "body": {},
      "id": "op-2",
      "dependsOn": ["op-1"]
    }
  ],
  "options": {
    "atomic": true,
    "continueOnError": false
  }
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "op-1",
      "status": 201,
      "body": {},
      "headers": {}
    },
    {
      "id": "op-2",
      "status": 200,
      "body": {}
    }
  ],
  "success": true
}
```

### 3. Delta Sync Endpoints

#### GET /api/v2/delta/{collection}/{id}
Gets delta changes for a specific record.

**Request Parameters:**
- `baseVersion`: Base version for delta calculation
- `targetVersion`: Target version (optional, defaults to latest)
- `format`: Delta format (json-patch|custom)

**Response:**
```json
{
  "id": "record-id",
  "baseVersion": "1",
  "targetVersion": "3",
  "patches": [
    {
      "op": "replace",
      "path": "/field",
      "value": "new-value"
    }
  ],
  "checksum": "sha256:abc123"
}
```

### 4. File Sync Endpoints

#### POST /api/v2/files/chunks/init
Initiates chunked file upload.

**Request:**
```json
{
  "fileName": "document.pdf",
  "fileSize": 10485760,
  "mimeType": "application/pdf",
  "checksum": "sha256:abc123",
  "chunkSize": 1048576,
  "metadata": {
    "patientId": "patient-uuid",
    "documentType": "lab_result"
  }
}
```

**Response:**
```json
{
  "uploadId": "upload-uuid",
  "uploadUrl": "https://api.../upload/...",
  "chunkUrls": [],
  "expiresAt": "2024-01-01T01:00:00Z"
}
```

#### PUT /api/v2/files/chunks/{uploadId}/{chunkNumber}
Uploads individual file chunk.

**Headers:**
- `Content-Range`: bytes 0-1048575/10485760
- `Content-MD5`: base64-encoded-md5

**Response:**
```json
{
  "chunkNumber": 1,
  "received": true,
  "checksum": "md5:xyz789"
}
```

## Modified Endpoints

### 1. All Resource Endpoints

All CRUD endpoints now include version information:

#### Response Headers
```
X-Resource-Version: 2
X-Vector-Clock: {"device1": 10, "server": 25}
X-Last-Modified: 2024-01-01T00:00:00Z
ETag: "abc123"
```

#### Request Headers
```
If-Match: "abc123"
If-None-Match: "abc123"
If-Modified-Since: 2024-01-01T00:00:00Z
X-Expected-Version: 1
```

### 2. List Endpoints

All list endpoints now support sync-related query parameters:

```
GET /api/v2/patients?modifiedSince=2024-01-01T00:00:00Z&includeDeleted=true&includeVersion=true
```

**New Query Parameters:**
- `modifiedSince`: ISO 8601 timestamp
- `includeDeleted`: Include soft-deleted records
- `includeVersion`: Include version metadata
- `vectorClock`: JSON-encoded vector clock
- `syncToken`: Continuation token from previous sync

### 3. Create/Update Endpoints

All create/update endpoints now accept version information:

**Request:**
```json
{
  "data": {
    "name": "John Doe",
    "dateOfBirth": "1990-01-01"
  },
  "version": {
    "baseVersion": "1",
    "vectorClock": {"device1": 10}
  }
}
```

## Request/Response Changes

### 1. Envelope Format

All responses now use a consistent envelope format:

```json
{
  "data": {},
  "metadata": {
    "version": "2",
    "vectorClock": {},
    "lastModified": "2024-01-01T00:00:00Z",
    "checksum": "sha256:abc123"
  },
  "sync": {
    "serverTime": "2024-01-01T00:00:00Z",
    "syncRequired": false
  }
}
```

### 2. Partial Updates

Support for JSON Patch (RFC 6902) for partial updates:

```
PATCH /api/v2/patients/123
Content-Type: application/json-patch+json

[
  { "op": "replace", "path": "/phone", "value": "+1234567890" },
  { "op": "add", "path": "/emergencyContacts/-", "value": {} }
]
```

### 3. Conditional Requests

All endpoints support conditional requests:

```
GET /api/v2/patients/123
If-None-Match: "abc123"
If-Modified-Since: 2024-01-01T00:00:00Z

Response: 304 Not Modified (if unchanged)
```

## Authentication Changes

### 1. Offline Token Support

#### Long-Lived Refresh Tokens
```json
{
  "access_token": "short-lived-token",
  "refresh_token": "long-lived-token",
  "offline_token": "offline-capable-token",
  "expires_in": 3600,
  "offline_expires_in": 2592000
}
```

### 2. Device Registration

#### POST /api/v2/auth/devices
Register device for offline access.

**Request:**
```json
{
  "deviceId": "device-uuid",
  "deviceName": "John's iPhone",
  "platform": "ios",
  "capabilities": ["offline", "biometric", "push"]
}
```

**Response:**
```json
{
  "deviceToken": "device-specific-token",
  "publicKey": "device-public-key",
  "syncKey": "encryption-key-for-sync"
}
```

### 3. Offline Validation

Tokens now include offline validation claims:

```json
{
  "sub": "user-id",
  "iat": 1234567890,
  "exp": 1234567890,
  "offline": {
    "validUntil": 1234567890,
    "permissions": ["read", "write"],
    "syncScope": ["patients", "records"]
  }
}
```

## Error Handling

### 1. New Error Codes

| Code | Name | Description |
|------|------|-------------|
| 409 | Version Conflict | Resource version mismatch |
| 410 | Gone | Resource permanently deleted |
| 412 | Precondition Failed | Conditional request failed |
| 422 | Unprocessable Entity | Valid request but semantic errors |
| 423 | Locked | Resource locked for sync |
| 425 | Too Early | Retry after specified time |
| 507 | Insufficient Storage | Server storage quota exceeded |

### 2. Enhanced Error Response

```json
{
  "error": {
    "code": "VERSION_CONFLICT",
    "message": "Resource has been modified",
    "details": {
      "currentVersion": "3",
      "requestedVersion": "1",
      "conflictType": "update-update",
      "conflictData": {
        "local": {},
        "server": {}
      }
    },
    "retryable": true,
    "retryAfter": 60
  }
}
```

### 3. Sync-Specific Errors

```json
{
  "error": {
    "code": "SYNC_FAILED",
    "message": "Synchronization failed",
    "syncErrors": [
      {
        "recordId": "123",
        "collection": "patients",
        "error": "VALIDATION_FAILED",
        "details": {}
      }
    ],
    "partialSuccess": true,
    "succeededCount": 45,
    "failedCount": 5
  }
}
```

## Versioning Strategy

### 1. API Version Header

All requests must include API version:

```
X-API-Version: 2.0
Accept: application/vnd.havenhealthpassport.v2+json
```

### 2. Backward Compatibility

Version 1 endpoints remain available with limitations:
- No offline support
- No conflict resolution
- Basic CRUD only
- Deprecated headers returned

### 3. Version Negotiation

```
GET /api/versions

Response:
{
  "current": "2.0",
  "supported": ["1.0", "2.0"],
  "deprecated": ["1.0"],
  "features": {
    "2.0": ["offline", "sync", "conflicts"],
    "1.0": ["basic-crud"]
  }
}
```

## Migration Guide

### 1. Client Migration Steps

#### Step 1: Update Authentication
```typescript
// Old
const token = await auth.login(username, password);

// New
const { access_token, offline_token } = await auth.loginWithOffline(username, password);
await auth.registerDevice(deviceId);
```

#### Step 2: Update API Calls
```typescript
// Old
const patient = await api.get('/patients/123');

// New
const response = await api.get('/patients/123', {
  headers: {
    'X-API-Version': '2.0',
    'If-None-Match': lastETag
  }
});
const { data, metadata } = response;
```

#### Step 3: Implement Sync
```typescript
// New sync implementation
const syncEngine = new SyncEngine({
  baseURL: 'https://api.../v2',
  deviceId: deviceId,
  conflictResolver: new ConflictResolver()
});

await syncEngine.sync();
```

### 2. Server Migration Steps

1. Deploy new endpoints alongside existing
2. Add version headers to all responses
3. Implement backward compatibility layer
4. Monitor usage of v1 endpoints
5. Gradually deprecate v1 endpoints

### 3. Data Migration

```sql
-- Add version columns
ALTER TABLE patients ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE patients ADD COLUMN vector_clock JSONB;
ALTER TABLE patients ADD COLUMN deleted_at TIMESTAMP;

-- Create sync metadata table
CREATE TABLE sync_metadata (
  id UUID PRIMARY KEY,
  table_name VARCHAR(255),
  record_id UUID,
  version INTEGER,
  vector_clock JSONB,
  last_modified TIMESTAMP,
  checksum VARCHAR(255)
);
```

## Best Practices

### 1. Client Implementation

- Always include version headers
- Handle 409 conflicts gracefully
- Implement exponential backoff
- Cache responses with ETags
- Use conditional requests

### 2. Batch Operations

- Group related operations
- Use dependency ordering
- Limit batch size to 100 operations
- Handle partial failures

### 3. File Uploads

- Use chunked uploads for files > 5MB
- Implement resume capability
- Verify checksums
- Clean up failed uploads

### 4. Performance

- Use delta sync when possible
- Compress request/response bodies
- Implement request deduplication
- Cache frequently accessed data
- Use HTTP/2 multiplexing

## Testing

### 1. Testing Scenarios

- Network interruption during sync
- Version conflicts
- Large batch operations
- File upload resume
- Token expiration during sync

### 2. Test Endpoints

```
POST /api/v2/test/simulate-conflict
POST /api/v2/test/corrupt-data
POST /api/v2/test/network-delay
GET /api/v2/test/sync-status
```

### 3. Load Testing

- 1000 concurrent sync operations
- 10MB file uploads
- 10000 record sync
- Conflict resolution under load
- API rate limiting

## Monitoring

### 1. Metrics to Track

- Sync success rate
- Conflict frequency
- Average sync duration
- API version usage
- Error rates by endpoint

### 2. Alerts

- Sync failure rate > 5%
- Conflict rate > 10%
- API response time > 2s
- Version mismatch errors increasing
- Storage quota warnings

## Security Considerations

### 1. Offline Security

- Encrypt sync tokens
- Validate device certificates
- Implement replay protection
- Use secure random for IDs
- Audit offline access

### 2. Data Protection

- End-to-end encryption for sensitive data
- Field-level encryption keys
- Secure key rotation
- Zero-knowledge sync for passwords
- HIPAA compliance maintained

## Conclusion

These API changes enable robust offline functionality while maintaining backward compatibility. The sync protocol ensures data consistency across devices, and the conflict resolution mechanisms handle concurrent modifications gracefully. Follow the migration guide to upgrade existing implementations.