# Migration Guides

## Overview

This document provides comprehensive migration guides for transitioning Haven Health Passport to offline-first architecture. It covers migrations for different components and scenarios.

## Table of Contents

1. [Database Migration](#database-migration)
2. [API Migration](#api-migration)
3. [Mobile App Migration](#mobile-app-migration)
4. [Web Portal Migration](#web-portal-migration)
5. [Data Migration](#data-migration)
6. [Testing Migration](#testing-migration)
7. [Rollback Procedures](#rollback-procedures)

## Database Migration

### From Online-Only to Offline-First

#### 1. Schema Changes

**Add Version Tracking:**
```sql
-- Add version columns to all tables
ALTER TABLE patients ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE patients ADD COLUMN vector_clock JSONB DEFAULT '{}';
ALTER TABLE patients ADD COLUMN last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE patients ADD COLUMN device_id VARCHAR(255);
ALTER TABLE patients ADD COLUMN sync_status VARCHAR(50) DEFAULT 'synced';

-- Add soft delete support
ALTER TABLE patients ADD COLUMN deleted_at TIMESTAMP;
ALTER TABLE patients ADD COLUMN deleted_by VARCHAR(255);

-- Create indexes for sync queries
CREATE INDEX idx_patients_last_modified ON patients(last_modified);
CREATE INDEX idx_patients_sync_status ON patients(sync_status);
CREATE INDEX idx_patients_device_id ON patients(device_id);
```

**Create Sync Metadata Tables:**
```sql
-- Sync metadata table
CREATE TABLE sync_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(255) NOT NULL,
    record_id UUID NOT NULL,
    operation VARCHAR(50) NOT NULL,
    version INTEGER NOT NULL,
    vector_clock JSONB NOT NULL,
    device_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP,
    UNIQUE(table_name, record_id, version)
);

-- Conflict tracking table
CREATE TABLE sync_conflicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(255) NOT NULL,
    record_id UUID NOT NULL,
    local_version INTEGER,
    server_version INTEGER,
    local_data JSONB,
    server_data JSONB,
    conflict_type VARCHAR(50),
    resolved BOOLEAN DEFAULT FALSE,
    resolution_strategy VARCHAR(50),
    resolved_at TIMESTAMP,
    resolved_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 2. WatermelonDB Setup (Mobile)

**Migration Script:**
```typescript
import { schemaMigrations } from '@nozbe/watermelondb/Schema/migrations';

export default schemaMigrations({
  migrations: [
    {
      toVersion: 2,
      steps: [
        addColumns({
          table: 'patients',
          columns: [
            { name: 'version', type: 'number', isOptional: false, default: 1 },
            { name: 'vector_clock', type: 'string', isOptional: false, default: '{}' },
            { name: 'sync_status', type: 'string', isOptional: false, default: 'synced' },
            { name: 'deleted_at', type: 'number', isOptional: true }
          ]
        }),
        createTable({
          name: 'sync_queue',
          columns: [
            { name: 'table_name', type: 'string', isIndexed: true },
            { name: 'record_id', type: 'string', isIndexed: true },
            { name: 'operation', type: 'string' },
            { name: 'data', type: 'string' },
            { name: 'created_at', type: 'number' },
            { name: 'retry_count', type: 'number' }
          ]
        })
      ]
    }
  ]
});
```

#### 3. IndexedDB Setup (Web)

**Migration Script:**
```typescript
export async function migrateToOfflineDB() {
  const db = await openDB('HavenHealthPassport', 2, {
    upgrade(db, oldVersion, newVersion, transaction) {
      if (oldVersion < 2) {
        // Add sync metadata to existing stores
        const stores = ['patients', 'records', 'documents'];
        
        stores.forEach(storeName => {
          const store = transaction.objectStore(storeName);
          
          // Add indexes for sync
          if (!store.indexNames.contains('lastModified')) {
            store.createIndex('lastModified', 'lastModified');
          }
          if (!store.indexNames.contains('syncStatus')) {
            store.createIndex('syncStatus', 'syncStatus');
          }
          if (!store.indexNames.contains('version')) {
            store.createIndex('version', 'version');
          }
        });
        
        // Create sync queue store
        if (!db.objectStoreNames.contains('syncQueue')) {
          const syncQueue = db.createObjectStore('syncQueue', { 
            keyPath: 'id', 
            autoIncrement: true 
          });
          syncQueue.createIndex('status', 'status');
          syncQueue.createIndex('createdAt', 'createdAt');
        }
      }
    }
  });
  
  return db;
}
```

## API Migration

### 1. Backend API Changes

**Update Controllers:**
```typescript
// Before
export class PatientController {
  async update(id: string, data: PatientDTO) {
    const patient = await this.patientService.update(id, data);
    return patient;
  }
}

// After
export class PatientController {
  async update(
    id: string, 
    data: PatientDTO,
    headers: SyncHeaders
  ) {
    const version = headers['x-expected-version'];
    const vectorClock = JSON.parse(headers['x-vector-clock'] || '{}');
    
    const result = await this.patientService.updateWithVersion(
      id, 
      data, 
      version,
      vectorClock
    );
    
    if (result.conflict) {
      throw new ConflictError(result.conflict);
    }
    
    return {
      data: result.data,
      metadata: {
        version: result.version,
        vectorClock: result.vectorClock
      }
    };
  }
}
```

**Add Sync Service:**
```typescript
@Injectable()
export class SyncService {
  async pull(request: SyncPullRequest): Promise<SyncPullResponse> {
    const changes = await this.getChangesSince(
      request.lastSyncTimestamp,
      request.collections,
      request.deviceId
    );
    
    return {
      changes: changes.map(this.formatChange),
      hasMore: changes.length >= request.maxRecords,
      serverVectorClock: await this.getServerVectorClock(),
      syncTimestamp: new Date()
    };
  }
  
  async push(request: SyncPushRequest): Promise<SyncPushResponse> {
    const results = await Promise.allSettled(
      request.changes.map(change => this.applyChange(change))
    );
    
    const accepted = [];
    const rejected = [];
    
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        accepted.push(request.changes[index].id);
      } else {
        rejected.push({
          changeId: request.changes[index].id,
          reason: result.reason
        });
      }
    });
    
    return { accepted, rejected };
  }
}
```

### 2. Authentication Migration

**Update Token Generation:**
```typescript
// Add offline claims to JWT
function generateToken(user: User, device?: Device) {
  const claims = {
    sub: user.id,
    email: user.email,
    roles: user.roles,
    iat: Date.now(),
    exp: Date.now() + (60 * 60 * 1000) // 1 hour
  };
  
  if (device) {
    claims.offline = {
      deviceId: device.id,
      validUntil: Date.now() + (30 * 24 * 60 * 60 * 1000), // 30 days
      syncPermissions: device.syncPermissions
    };
  }
  
  return jwt.sign(claims, process.env.JWT_SECRET);
}
```

## Mobile App Migration

### 1. State Management Migration

**Before (Redux):**
```typescript
// Traditional Redux store
const store = createStore(
  rootReducer,
  applyMiddleware(thunk)
);
```

**After (With Offline Support):**
```typescript
// Redux with offline support
import { offline } from '@redux-offline/redux-offline';
import offlineConfig from '@redux-offline/redux-offline/lib/defaults';

const customConfig = {
  ...offlineConfig,
  persistOptions: {
    blacklist: ['ui', 'temp']
  },
  effect: (effect, action) => syncEngine.processAction(effect, action),
  discard: (error, action, retries) => {
    return error.permanent || retries > 3;
  }
};

const store = createStore(
  rootReducer,
  compose(
    applyMiddleware(thunk),
    offline(customConfig)
  )
);
```

### 2. Component Migration

**Before:**
```tsx
function PatientList() {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    api.getPatients()
      .then(setPatients)
      .finally(() => setLoading(false));
  }, []);
  
  if (loading) return <Spinner />;
  return <FlatList data={patients} />;
}
```

**After:**
```tsx
function PatientList() {
  const { database } = useDatabase();
  const patients = useQuery(
    database.collections.get('patients').query()
  );
  const syncStatus = useSyncStatus();
  
  return (
    <>
      {syncStatus.syncing && <SyncIndicator />}
      <FlatList 
        data={patients}
        renderItem={({ item }) => (
          <PatientItem 
            patient={item}
            syncStatus={item.syncStatus}
          />
        )}
      />
    </>
  );
}
```

### 3. Network Layer Migration

**Before:**
```typescript
class ApiService {
  async request(url: string, options: RequestOptions) {
    const response = await fetch(url, options);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  }
}
```

**After:**
```typescript
class OfflineApiService {
  async request(url: string, options: RequestOptions) {
    // Check if online
    if (!navigator.onLine) {
      return this.queueRequest(url, options);
    }
    
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          'X-Device-ID': this.deviceId,
          'X-Sync-Token': await this.getSyncToken()
        }
      });
      
      if (response.status === 409) {
        return this.handleConflict(response);
      }
      
      return response.json();
    } catch (error) {
      if (this.isNetworkError(error)) {
        return this.queueRequest(url, options);
      }
      throw error;
    }
  }
  
  private async queueRequest(url: string, options: RequestOptions) {
    const operation = {
      url,
      method: options.method,
      body: options.body,
      timestamp: Date.now()
    };
    
    await this.syncQueue.add(operation);
    
    // Return optimistic response
    return this.generateOptimisticResponse(operation);
  }
}
```

## Web Portal Migration

### 1. Progressive Web App Setup

**Install Service Worker:**
```typescript
// main.ts
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then(registration => {
        console.log('SW registered:', registration);
        
        // Check for updates
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              // New version available
              showUpdateNotification();
            }
          });
        });
      })
      .catch(err => console.error('SW registration failed:', err));
  });
}
```

**Create Service Worker:**
```javascript
// sw.js
const CACHE_NAME = 'haven-health-v1';
const urlsToCache = [
  '/',
  '/static/css/main.css',
  '/static/js/bundle.js',
  '/offline.html'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response;
        }
        return fetch(event.request);
      })
      .catch(() => {
        if (event.request.destination === 'document') {
          return caches.match('/offline.html');
        }
      })
  );
});
```

### 2. State Management Migration

**Add Offline Store:**
```typescript
// Before
import { createStore } from 'redux';

const store = createStore(rootReducer);

// After
import { configureStore } from '@reduxjs/toolkit';
import { persistStore, persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';
import { offlineMiddleware } from './middleware/offline';

const persistConfig = {
  key: 'root',
  storage,
  whitelist: ['patients', 'records', 'user']
};

const persistedReducer = persistReducer(persistConfig, rootReducer);

export const store = configureStore({
  reducer: persistedReducer,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: ['persist/PERSIST']
      }
    }).concat(offlineMiddleware)
});

export const persistor = persistStore(store);
```

### 3. API Client Migration

**Update API Client:**
```typescript
// Before
class ApiClient {
  async get(url: string) {
    const response = await fetch(url);
    return response.json();
  }
}

// After
class OfflineApiClient {
  private db: IDBDatabase;
  private syncQueue: SyncQueue;
  
  async get(url: string, options?: RequestOptions) {
    // Try online first
    if (navigator.onLine) {
      try {
        const response = await fetch(url, {
          ...options,
          headers: {
            ...options?.headers,
            'X-API-Version': '2.0'
          }
        });
        
        const data = await response.json();
        
        // Cache successful responses
        await this.cacheResponse(url, data);
        
        return data;
      } catch (error) {
        // Fall back to cache
        return this.getCachedResponse(url);
      }
    }
    
    // Offline - return from cache
    return this.getCachedResponse(url);
  }
  
  async post(url: string, data: any) {
    if (!navigator.onLine) {
      // Queue for later
      await this.syncQueue.add({
        method: 'POST',
        url,
        data,
        timestamp: Date.now()
      });
      
      // Return optimistic response
      return {
        id: generateLocalId(),
        ...data,
        _syncStatus: 'pending'
      };
    }
    
    // Online - send immediately
    const response = await fetch(url, {
      method: 'POST',
      body: JSON.stringify(data),
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    return response.json();
  }
}
```

## Data Migration

### 1. Export Existing Data

**PostgreSQL Export Script:**
```sql
-- Export patients with metadata
COPY (
  SELECT 
    id,
    name,
    date_of_birth,
    created_at,
    updated_at,
    1 as version,
    '{}' as vector_clock,
    'server' as device_id,
    'synced' as sync_status
  FROM patients
  WHERE active = true
) TO '/tmp/patients_export.csv' WITH CSV HEADER;

-- Export relationships
COPY (
  SELECT * FROM patient_documents
) TO '/tmp/patient_documents_export.csv' WITH CSV HEADER;
```

### 2. Transform Data

**Data Transformation Script:**
```typescript
async function transformDataForOffline(exportPath: string) {
  const data = await readCSV(exportPath);
  
  return data.map(record => ({
    ...record,
    id: record.id || generateUUID(),
    _id: record.id, // WatermelonDB compatibility
    version: parseInt(record.version) || 1,
    vectorClock: parseVectorClock(record.vector_clock),
    lastModified: record.updated_at || record.created_at,
    syncStatus: 'synced',
    _raw: {
      id: record.id,
      _status: 'synced',
      _changed: ''
    }
  }));
}
```

### 3. Import to Offline Storage

**WatermelonDB Import:**
```typescript
async function importToWatermelonDB(database: Database, data: any[]) {
  await database.action(async () => {
    await database.batch(
      ...data.map(record => 
        database.collections
          .get('patients')
          .prepareCreate(patient => {
            patient._raw = record._raw;
            Object.assign(patient, record);
          })
      )
    );
  });
}
```

**IndexedDB Import:**
```typescript
async function importToIndexedDB(db: IDBDatabase, data: any[]) {
  const tx = db.transaction(['patients'], 'readwrite');
  const store = tx.objectStore('patients');
  
  for (const record of data) {
    await store.put({
      ...record,
      lastModified: new Date(record.lastModified),
      syncStatus: 'synced'
    });
  }
  
  await tx.complete;
}
```

## Testing Migration

### 1. Update Test Environment

**Jest Configuration:**
```javascript
// jest.config.js
module.exports = {
  preset: 'react-native',
  setupFilesAfterEnv: [
    '<rootDir>/test/setup.js',
    '<rootDir>/test/offline-mocks.js'
  ],
  moduleNameMapper: {
    '@nozbe/watermelondb': '<rootDir>/test/mocks/watermelondb.js',
    'react-native-sqlite-2': '<rootDir>/test/mocks/sqlite.js'
  }
};
```

**Offline Test Utilities:**
```typescript
// test/offline-mocks.js
global.navigator = {
  onLine: true,
  connection: {
    effectiveType: '4g'
  }
};

global.indexedDB = require('fake-indexeddb');
global.IDBKeyRange = require('fake-indexeddb/lib/FDBKeyRange');

// Mock sync engine
jest.mock('../src/sync/SyncEngine', () => ({
  SyncEngine: jest.fn().mockImplementation(() => ({
    sync: jest.fn().mockResolvedValue({ success: true }),
    push: jest.fn().mockResolvedValue({ accepted: ['1', '2'] }),
    pull: jest.fn().mockResolvedValue({ changes: [] })
  }))
}));
```

### 2. Testing Strategies

**Offline Behavior Tests:**
```typescript
describe('Offline Patient Management', () => {
  beforeEach(() => {
    // Set offline
    global.navigator.onLine = false;
  });
  
  afterEach(() => {
    // Reset
    global.navigator.onLine = true;
  });
  
  it('should queue patient creation when offline', async () => {
    const patient = {
      name: 'John Doe',
      dateOfBirth: '1990-01-01'
    };
    
    const result = await patientService.create(patient);
    
    expect(result.id).toBeDefined();
    expect(result._syncStatus).toBe('pending');
    
    const queuedOps = await syncQueue.getAll();
    expect(queuedOps).toHaveLength(1);
    expect(queuedOps[0].operation).toBe('create');
  });
  
  it('should sync queued operations when online', async () => {
    // Queue some operations
    await syncQueue.add({ operation: 'create', data: {} });
    await syncQueue.add({ operation: 'update', data: {} });
    
    // Go online
    global.navigator.onLine = true;
    
    // Trigger sync
    await syncEngine.sync();
    
    // Verify queue is empty
    const remaining = await syncQueue.getAll();
    expect(remaining).toHaveLength(0);
  });
});
```

**Conflict Resolution Tests:**
```typescript
describe('Conflict Resolution', () => {
  it('should detect update-update conflicts', async () => {
    const record = { id: '123', name: 'Original', version: 1 };
    
    // Simulate local update
    const localUpdate = { ...record, name: 'Local Update', version: 2 };
    await database.update(localUpdate);
    
    // Simulate server update
    const serverUpdate = { ...record, name: 'Server Update', version: 2 };
    
    const conflict = await conflictResolver.detect(localUpdate, serverUpdate);
    expect(conflict.type).toBe('update-update');
  });
  
  it('should resolve conflicts using CRDT', async () => {
    const conflict = {
      local: { name: 'Local', vectorClock: { device1: 10 } },
      server: { name: 'Server', vectorClock: { server: 15 } }
    };
    
    const resolved = await conflictResolver.resolve(conflict);
    expect(resolved.vectorClock).toEqual({
      device1: 10,
      server: 15
    });
  });
});
```

## Rollback Procedures

### 1. Database Rollback

**PostgreSQL Rollback Script:**
```sql
-- Remove offline columns
ALTER TABLE patients DROP COLUMN IF EXISTS version;
ALTER TABLE patients DROP COLUMN IF EXISTS vector_clock;
ALTER TABLE patients DROP COLUMN IF EXISTS last_modified;
ALTER TABLE patients DROP COLUMN IF EXISTS device_id;
ALTER TABLE patients DROP COLUMN IF EXISTS sync_status;
ALTER TABLE patients DROP COLUMN IF EXISTS deleted_at;

-- Drop sync tables
DROP TABLE IF EXISTS sync_metadata;
DROP TABLE IF EXISTS sync_conflicts;

-- Remove indexes
DROP INDEX IF EXISTS idx_patients_last_modified;
DROP INDEX IF EXISTS idx_patients_sync_status;
DROP INDEX IF EXISTS idx_patients_device_id;
```

### 2. Application Rollback

**Mobile App Rollback:**
```typescript
// Revert to previous database version
const rollbackDatabase = async () => {
  // Export critical data
  const criticalData = await exportCriticalData();
  
  // Delete current database
  await database.unsafeResetDatabase();
  
  // Recreate with old schema
  const oldDatabase = new Database({
    adapter: new SQLiteAdapter({
      schema: oldSchema,
      migrations: []
    }),
    modelClasses: oldModelClasses
  });
  
  // Restore critical data
  await restoreCriticalData(oldDatabase, criticalData);
};
```

**Web Portal Rollback:**
```typescript
// Clear offline storage and service workers
const rollbackWebOffline = async () => {
  // Unregister service workers
  const registrations = await navigator.serviceWorker.getRegistrations();
  for (const registration of registrations) {
    await registration.unregister();
  }
  
  // Clear all caches
  const cacheNames = await caches.keys();
  await Promise.all(
    cacheNames.map(name => caches.delete(name))
  );
  
  // Clear IndexedDB
  await deleteDB('HavenHealthPassport');
  
  // Clear local storage
  localStorage.clear();
  sessionStorage.clear();
};
```

### 3. API Rollback

**Revert API Changes:**
```typescript
// Switch back to v1 endpoints
const API_VERSION = '1.0';

// Remove version headers
delete axios.defaults.headers.common['X-API-Version'];
delete axios.defaults.headers.common['X-Device-ID'];

// Restore simple error handling
axios.interceptors.response.use(
  response => response,
  error => {
    // Simple error handling without conflict detection
    return Promise.reject(error);
  }
);
```

## Migration Checklist

### Pre-Migration
- [ ] Full database backup completed
- [ ] API endpoints tested in staging
- [ ] Rollback procedures tested
- [ ] User communication sent
- [ ] Monitoring alerts configured

### During Migration
- [ ] Database schema updated
- [ ] Data transformation completed
- [ ] API v2 deployed
- [ ] Mobile app update released
- [ ] Web portal PWA enabled

### Post-Migration
- [ ] Data integrity verified
- [ ] Sync functionality tested
- [ ] Performance metrics normal
- [ ] User feedback collected
- [ ] Documentation updated

## Common Issues and Solutions

### Issue 1: Slow Initial Sync
**Solution:** Implement progressive sync with date ranges:
```typescript
async function progressiveSync(startDate: Date) {
  const chunks = generateDateChunks(startDate, new Date(), 30); // 30-day chunks
  
  for (const chunk of chunks) {
    await syncEngine.syncDateRange(chunk.start, chunk.end);
    await updateProgress(chunk.progress);
  }
}
```

### Issue 2: Storage Quota Exceeded
**Solution:** Implement data pruning:
```typescript
async function pruneOldData() {
  const threshold = Date.now() - (90 * 24 * 60 * 60 * 1000); // 90 days
  
  await database.action(async () => {
    const oldRecords = await database.collections
      .get('records')
      .query(Q.where('lastAccessed', Q.lt(threshold)))
      .fetch();
    
    await database.batch(
      ...oldRecords.map(record => record.prepareMarkAsDeleted())
    );
  });
}
```

### Issue 3: Conflict Resolution Loops
**Solution:** Add conflict detection limits:
```typescript
const MAX_CONFLICT_RETRIES = 3;

async function resolveWithLimit(conflict: Conflict) {
  if (conflict.retryCount >= MAX_CONFLICT_RETRIES) {
    // Mark for manual resolution
    await markForManualResolution(conflict);
    return;
  }
  
  const resolved = await conflictResolver.resolve(conflict);
  if (hasNewConflict(resolved)) {
    conflict.retryCount++;
    return resolveWithLimit(conflict);
  }
  
  return resolved;
}
```

## Monitoring Migration Success

### Key Metrics
1. **Sync Success Rate**: Target > 95%
2. **Conflict Rate**: Target < 5%
3. **Offline Usage**: Track adoption
4. **Performance Impact**: Monitor app responsiveness
5. **Storage Growth**: Track local storage usage

### Dashboard Queries
```sql
-- Sync success rate
SELECT 
  DATE(created_at) as date,
  COUNT(*) as total_syncs,
  SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
  ROUND(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as success_rate
FROM sync_logs
WHERE created_at > CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Conflict frequency
SELECT 
  table_name,
  conflict_type,
  COUNT(*) as count,
  ROUND(AVG(EXTRACT(EPOCH FROM (resolved_at - created_at))), 2) as avg_resolution_time_seconds
FROM sync_conflicts
WHERE created_at > CURRENT_DATE - INTERVAL '30 days'
GROUP BY table_name, conflict_type
ORDER BY count DESC;
```

## Conclusion

This migration guide provides a comprehensive path from online-only to offline-first architecture. Follow each section carefully, test thoroughly, and maintain rollback capability throughout the process. The offline-first approach will significantly improve user experience in low-connectivity environments while maintaining data consistency and security.