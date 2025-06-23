# Debugging Guide for Offline Functionality

## Overview

This guide provides comprehensive debugging strategies, tools, and techniques for troubleshooting offline functionality in Haven Health Passport. It covers common issues, debugging tools, and step-by-step procedures.

## Table of Contents

1. [Debug Setup](#debug-setup)
2. [Common Issues](#common-issues)
3. [Debugging Tools](#debugging-tools)
4. [Mobile Debugging](#mobile-debugging)
5. [Web Debugging](#web-debugging)
6. [Sync Debugging](#sync-debugging)
7. [Performance Debugging](#performance-debugging)
8. [Production Debugging](#production-debugging)

## Debug Setup

### Development Environment

#### Enable Debug Mode
```typescript
// config/debug.ts
export const DEBUG_CONFIG = {
  // Enable verbose logging
  verboseLogging: true,
  
  // Log levels
  logLevel: 'debug',
  
  // Debug features
  showSyncStatus: true,
  showNetworkRequests: true,
  showDatabaseQueries: true,
  showConflicts: true,
  
  // Performance monitoring
  enablePerformanceMonitoring: true,
  
  // Debug UI
  showDebugPanel: true,
  showDatabaseInspector: true
};

// Initialize debug mode
if (__DEV__) {
  initializeDebugMode(DEBUG_CONFIG);
}
```

#### Debug Logger Setup
```typescript
import { Logger } from './logger';

class DebugLogger extends Logger {
  private logs: LogEntry[] = [];
  private maxLogs = 1000;
  
  constructor() {
    super();
    this.setupConsoleInterceptor();
    this.setupErrorHandler();
  }
  
  private setupConsoleInterceptor() {
    const originalLog = console.log;
    const originalError = console.error;
    const originalWarn = console.warn;
    
    console.log = (...args) => {
      this.addLog('info', args);
      originalLog.apply(console, args);
    };
    
    console.error = (...args) => {
      this.addLog('error', args);
      originalError.apply(console, args);
    };
    
    console.warn = (...args) => {
      this.addLog('warn', args);
      originalWarn.apply(console, args);
    };
  }
  
  private addLog(level: string, args: any[]) {
    const entry: LogEntry = {
      timestamp: Date.now(),
      level,
      message: args.map(arg => 
        typeof arg === 'object' ? JSON.stringify(arg, null, 2) : arg
      ).join(' '),
      stackTrace: new Error().stack
    };
    
    this.logs.push(entry);
    
    // Limit log size
    if (this.logs.length > this.maxLogs) {
      this.logs.shift();
    }
    
    // Emit to debug panel
    this.emit('log', entry);
  }
  
  exportLogs(): string {
    return this.logs.map(log => 
      `[${new Date(log.timestamp).toISOString()}] [${log.level}] ${log.message}`
    ).join('\n');
  }
}

export const debugLogger = new DebugLogger();
```

### Debug UI Component

```tsx
// components/DebugPanel.tsx
import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, TouchableOpacity } from 'react-native';

export function DebugPanel() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filter, setFilter] = useState<string>('all');
  const [isMinimized, setIsMinimized] = useState(false);
  
  useEffect(() => {
    const unsubscribe = debugLogger.on('log', (entry) => {
      setLogs(prev => [...prev.slice(-99), entry]);
    });
    
    return unsubscribe;
  }, []);
  
  const filteredLogs = logs.filter(log => 
    filter === 'all' || log.level === filter
  );
  
  if (isMinimized) {
    return (
      <TouchableOpacity 
        style={styles.minimized}
        onPress={() => setIsMinimized(false)}
      >
        <Text>Debug</Text>
      </TouchableOpacity>
    );
  }
  
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Debug Panel</Text>
        <TouchableOpacity onPress={() => setIsMinimized(true)}>
          <Text>Minimize</Text>
        </TouchableOpacity>
      </View>
      
      <View style={styles.filters}>
        {['all', 'error', 'warn', 'info', 'debug'].map(level => (
          <TouchableOpacity
            key={level}
            style={[styles.filterButton, filter === level && styles.activeFilter]}
            onPress={() => setFilter(level)}
          >
            <Text>{level}</Text>
          </TouchableOpacity>
        ))}
      </View>
      
      <ScrollView style={styles.logContainer}>
        {filteredLogs.map((log, index) => (
          <View key={index} style={[styles.logEntry, styles[log.level]]}>
            <Text style={styles.timestamp}>
              {new Date(log.timestamp).toLocaleTimeString()}
            </Text>
            <Text style={styles.message}>{log.message}</Text>
          </View>
        ))}
      </ScrollView>
      
      <View style={styles.actions}>
        <TouchableOpacity onPress={() => exportDebugLogs()}>
          <Text>Export Logs</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => setLogs([])}>
          <Text>Clear</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
```

## Common Issues

### 1. Data Not Syncing

#### Symptoms
- Changes made offline don't appear on other devices
- Sync status shows "pending" indefinitely
- No sync errors but data missing

#### Debug Steps

```typescript
// Check sync queue
async function debugSyncQueue() {
  const queue = await syncQueue.getAll();
  console.log('Sync Queue Status:', {
    totalItems: queue.length,
    oldestItem: queue[0]?.timestamp,
    newestItem: queue[queue.length - 1]?.timestamp,
    failedItems: queue.filter(item => item.retryCount > 0).length
  });
  
  // Check for stuck items
  const stuckItems = queue.filter(item => 
    Date.now() - item.timestamp > 3600000 // 1 hour
  );
  
  if (stuckItems.length > 0) {
    console.error('Stuck sync items:', stuckItems);
  }
}

// Check network connectivity
async function debugNetworkStatus() {
  console.log('Network Status:', {
    online: navigator.onLine,
    connectionType: await NetInfo.fetch(),
    lastSyncTime: await getLastSyncTime(),
    syncEnabled: await isSyncEnabled()
  });
}

// Verify sync configuration
async function debugSyncConfig() {
  const config = await getSyncConfig();
  console.log('Sync Configuration:', {
    endpoint: config.endpoint,
    authToken: config.authToken ? 'Present' : 'Missing',
    syncInterval: config.syncInterval,
    batchSize: config.batchSize
  });
}
```

### 2. Conflict Resolution Failures

#### Symptoms
- Duplicate records appearing
- Data inconsistencies between devices
- Conflict resolver crashes

#### Debug Steps

```typescript
// Debug conflict detection
class ConflictDebugger {
  async analyzeConflicts() {
    const conflicts = await conflictStore.getUnresolved();
    
    console.log('Conflict Analysis:', {
      total: conflicts.length,
      byType: this.groupByType(conflicts),
      averageAge: this.calculateAverageAge(conflicts)
    });
    
    // Analyze each conflict
    for (const conflict of conflicts) {
      await this.analyzeConflict(conflict);
    }
  }
  
  private async analyzeConflict(conflict: Conflict) {
    console.log('Conflict Details:', {
      id: conflict.id,
      type: conflict.type,
      created: conflict.createdAt,
      local: {
        version: conflict.local.version,
        lastModified: conflict.local.lastModified,
        checksum: this.calculateChecksum(conflict.local)
      },
      server: {
        version: conflict.server.version,
        lastModified: conflict.server.lastModified,
        checksum: this.calculateChecksum(conflict.server)
      },
      differences: this.findDifferences(conflict.local, conflict.server)
    });
  }
  
  private findDifferences(local: any, server: any): any {
    const diff = {};
    const allKeys = new Set([
      ...Object.keys(local),
      ...Object.keys(server)
    ]);
    
    for (const key of allKeys) {
      if (JSON.stringify(local[key]) !== JSON.stringify(server[key])) {
        diff[key] = {
          local: local[key],
          server: server[key]
        };
      }
    }
    
    return diff;
  }
}
```

### 3. Database Corruption

#### Symptoms
- App crashes on startup
- Data queries failing
- Inconsistent query results

#### Debug Steps

```typescript
// Database integrity check
async function checkDatabaseIntegrity() {
  try {
    // WatermelonDB check
    const database = getDatabase();
    
    // Check each collection
    const collections = ['patients', 'records', 'documents'];
    
    for (const collectionName of collections) {
      const collection = database.collections.get(collectionName);
      
      // Count records
      const count = await collection.query().fetchCount();
      console.log(`${collectionName}: ${count} records`);
      
      // Check for corruption
      try {
        const sample = await collection.query().take(10).fetch();
        console.log(`${collectionName} sample OK`);
      } catch (error) {
        console.error(`${collectionName} corrupted:`, error);
      }
    }
    
    // Check indexes
    await database.adapter.unsafeQueryRaw(
      'PRAGMA integrity_check'
    ).then(result => {
      console.log('Database integrity:', result);
    });
    
  } catch (error) {
    console.error('Database check failed:', error);
  }
}

// Repair database
async function repairDatabase() {
  console.log('Starting database repair...');
  
  try {
    // Export salvageable data
    const data = await exportSalvageableData();
    console.log(`Exported ${data.length} records`);
    
    // Reset database
    await database.unsafeResetDatabase();
    console.log('Database reset complete');
    
    // Reimport data
    await importData(data);
    console.log('Data reimport complete');
    
  } catch (error) {
    console.error('Database repair failed:', error);
    // Last resort: clear everything
    await clearAllData();
  }
}
```

## Debugging Tools

### 1. Network Inspector

```typescript
class NetworkInspector {
  private requests: NetworkRequest[] = [];
  
  constructor() {
    this.interceptRequests();
  }
  
  private interceptRequests() {
    const originalFetch = global.fetch;
    
    global.fetch = async (url, options) => {
      const requestId = generateId();
      const startTime = Date.now();
      
      // Log request
      this.logRequest(requestId, url, options);
      
      try {
        const response = await originalFetch(url, options);
        const duration = Date.now() - startTime;
        
        // Log response
        this.logResponse(requestId, response, duration);
        
        return response;
      } catch (error) {
        // Log error
        this.logError(requestId, error);
        throw error;
      }
    };
  }
  
  private logRequest(id: string, url: string, options: any) {
    const request = {
      id,
      timestamp: Date.now(),
      url,
      method: options?.method || 'GET',
      headers: options?.headers,
      body: options?.body
    };
    
    this.requests.push(request);
    console.log('🔵 Request:', request);
  }
  
  private logResponse(id: string, response: Response, duration: number) {
    console.log('🟢 Response:', {
      id,
      status: response.status,
      duration: `${duration}ms`,
      headers: Object.fromEntries(response.headers.entries())
    });
  }
  
  getRequests(filter?: string): NetworkRequest[] {
    if (!filter) return this.requests;
    
    return this.requests.filter(req => 
      req.url.includes(filter) ||
      req.method === filter ||
      req.status === filter
    );
  }
}
```

### 2. Database Inspector

```typescript
// Database query logger
class DatabaseInspector {
  private queries: QueryLog[] = [];
  
  async enableQueryLogging() {
    if (Platform.OS === 'ios' || Platform.OS === 'android') {
      await database.adapter.underlyingAdapter.enableQueryLogging();
    }
    
    // Intercept queries
    const originalQuery = database.adapter.query;
    database.adapter.query = async (...args) => {
      const startTime = Date.now();
      const query = args[0];
      
      try {
        const result = await originalQuery.apply(database.adapter, args);
        const duration = Date.now() - startTime;
        
        this.logQuery({
          query,
          duration,
          resultCount: Array.isArray(result) ? result.length : 1,
          timestamp: Date.now()
        });
        
        return result;
      } catch (error) {
        this.logQuery({
          query,
          error: error.message,
          timestamp: Date.now()
        });
        throw error;
      }
    };
  }
  
  getSlowQueries(threshold = 100): QueryLog[] {
    return this.queries.filter(q => q.duration > threshold);
  }
  
  exportSchema(): Promise<string> {
    return database.adapter.unsafeQueryRaw(
      "SELECT sql FROM sqlite_master WHERE type='table'"
    );
  }
}
```

### 3. Sync Monitor

```typescript
class SyncMonitor {
  private syncEvents: SyncEvent[] = [];
  
  constructor(private syncEngine: SyncEngine) {
    this.attachListeners();
  }
  
  private attachListeners() {
    this.syncEngine.on('sync:start', (event) => {
      this.addEvent({
        type: 'start',
        timestamp: Date.now(),
        details: event
      });
    });
    
    this.syncEngine.on('sync:progress', (progress) => {
      this.addEvent({
        type: 'progress',
        timestamp: Date.now(),
        details: progress
      });
    });
    
    this.syncEngine.on('sync:complete', (result) => {
      this.addEvent({
        type: 'complete',
        timestamp: Date.now(),
        details: result
      });
    });
    
    this.syncEngine.on('sync:error', (error) => {
      this.addEvent({
        type: 'error',
        timestamp: Date.now(),
        details: error
      });
    });
  }
  
  getSyncHistory(): SyncEvent[] {
    return this.syncEvents;
  }
  
  getLastSync(): SyncEvent | null {
    const completeEvents = this.syncEvents.filter(e => e.type === 'complete');
    return completeEvents[completeEvents.length - 1] || null;
  }
  
  getSyncErrors(): SyncEvent[] {
    return this.syncEvents.filter(e => e.type === 'error');
  }
  
  generateSyncReport(): SyncReport {
    const last24Hours = Date.now() - (24 * 60 * 60 * 1000);
    const recentEvents = this.syncEvents.filter(e => e.timestamp > last24Hours);
    
    return {
      totalSyncs: recentEvents.filter(e => e.type === 'complete').length,
      failedSyncs: recentEvents.filter(e => e.type === 'error').length,
      averageDuration: this.calculateAverageDuration(recentEvents),
      lastSuccessfulSync: this.getLastSync(),
      errors: this.getSyncErrors().slice(-10)
    };
  }
}
```

## Mobile Debugging

### React Native Debugging

#### Flipper Integration
```typescript
// Install Flipper plugins
import { 
  FlipperDatabasesPlugin,
  FlipperNetworkPlugin,
  FlipperReactPlugin 
} from 'react-native-flipper';

// Configure Flipper
if (__DEV__) {
  // Database plugin for WatermelonDB
  addPlugin(new FlipperDatabasesPlugin({
    database: database.adapter.underlyingAdapter._database
  }));
  
  // Network plugin
  addPlugin(new FlipperNetworkPlugin());
  
  // React DevTools
  addPlugin(new FlipperReactPlugin());
}
```

#### React Native Debugger Setup
```typescript
// Enable debugging features
export function setupDebugging() {
  if (__DEV__) {
    // Enable network inspection
    global.XMLHttpRequest = global.originalXMLHttpRequest || global.XMLHttpRequest;
    global.FormData = global.originalFormData || global.FormData;
    
    // Enable console.tron for Reactotron
    if (console.tron) {
      console.tron.clear();
    }
    
    // Log renders
    if (Platform.OS === 'ios' || Platform.OS === 'android') {
      const whyDidYouRender = require('@welldone-software/why-did-you-render');
      whyDidYouRender(React, {
        trackAllPureComponents: true,
        trackHooks: true,
        logOwnerReasons: true
      });
    }
  }
}
```

### Platform-Specific Debugging

#### iOS Debugging
```objective-c
// Enable verbose logging in iOS
#ifdef DEBUG
  // SQLite debugging
  [[WMDatabase sharedInstance] setVerboseLogging:YES];
  
  // Network debugging
  [NSURLSession sharedSession].configuration.protocolClasses = 
    @[[NetworkDebugProtocol class]];
  
  // Memory debugging
  [[FBAllocationTracker sharedInstance] startTrackingAllocations];
  [[FBAllocationTracker sharedInstance] enableGenerations];
#endif
```

#### Android Debugging
```java
// Enable debugging in Android
if (BuildConfig.DEBUG) {
    // Enable StrictMode
    StrictMode.setThreadPolicy(new StrictMode.ThreadPolicy.Builder()
        .detectAll()
        .penaltyLog()
        .build());
    
    // Enable WebView debugging
    WebView.setWebContentsDebuggingEnabled(true);
    
    // Enable SQLite debugging
    SQLiteDatabase.enableWriteAheadLogging();
    
    // Stetho for Chrome DevTools
    Stetho.initializeWithDefaults(this);
}
```

### Memory Debugging

```typescript
class MemoryDebugger {
  private memorySnapshots: MemorySnapshot[] = [];
  
  takeSnapshot(label: string) {
    const snapshot: MemorySnapshot = {
      label,
      timestamp: Date.now(),
      jsHeapSize: performance.memory?.usedJSHeapSize || 0,
      totalHeapSize: performance.memory?.totalJSHeapSize || 0,
      externalSize: performance.memory?.externalSize || 0
    };
    
    this.memorySnapshots.push(snapshot);
    console.log('Memory snapshot:', snapshot);
  }
  
  compareSnapshots(label1: string, label2: string) {
    const snap1 = this.memorySnapshots.find(s => s.label === label1);
    const snap2 = this.memorySnapshots.find(s => s.label === label2);
    
    if (!snap1 || !snap2) {
      console.error('Snapshots not found');
      return;
    }
    
    console.log('Memory diff:', {
      jsHeapDiff: snap2.jsHeapSize - snap1.jsHeapSize,
      totalHeapDiff: snap2.totalHeapSize - snap1.totalHeapSize,
      timeDiff: snap2.timestamp - snap1.timestamp
    });
  }
  
  detectLeaks() {
    const recentSnapshots = this.memorySnapshots.slice(-10);
    const trend = this.calculateTrend(recentSnapshots);
    
    if (trend > 0.1) { // 10% growth
      console.warn('Potential memory leak detected:', {
        trend: `${(trend * 100).toFixed(2)}%`,
        snapshots: recentSnapshots
      });
    }
  }
}
```

## Web Debugging

### Service Worker Debugging

```javascript
// Debug service worker
self.addEventListener('install', event => {
  console.log('[SW] Installing:', new Date().toISOString());
});

self.addEventListener('activate', event => {
  console.log('[SW] Activating:', new Date().toISOString());
});

self.addEventListener('fetch', event => {
  console.log('[SW] Fetch:', event.request.url);
  
  // Log cache hits/misses
  event.respondWith(
    caches.match(event.request).then(response => {
      if (response) {
        console.log('[SW] Cache hit:', event.request.url);
        return response;
      }
      
      console.log('[SW] Cache miss:', event.request.url);
      return fetch(event.request);
    })
  );
});

// Debug sync events
self.addEventListener('sync', event => {
  console.log('[SW] Sync event:', event.tag);
  
  if (event.tag === 'health-records-sync') {
    event.waitUntil(
      performSync().then(() => {
        console.log('[SW] Sync completed');
      }).catch(error => {
        console.error('[SW] Sync failed:', error);
      })
    );
  }
});
```

### IndexedDB Debugging

```typescript
class IndexedDBDebugger {
  async inspectDatabase(dbName: string) {
    const db = await openDB(dbName);
    const report = {
      name: db.name,
      version: db.version,
      stores: {}
    };
    
    // Inspect each object store
    for (const storeName of db.objectStoreNames) {
      const tx = db.transaction(storeName, 'readonly');
      const store = tx.objectStore(storeName);
      
      report.stores[storeName] = {
        keyPath: store.keyPath,
        indexNames: Array.from(store.indexNames),
        count: await store.count(),
        autoIncrement: store.autoIncrement
      };
      
      // Sample data
      const cursor = await store.openCursor();
      const samples = [];
      let count = 0;
      
      while (cursor && count < 5) {
        samples.push(cursor.value);
        await cursor.continue();
        count++;
      }
      
      report.stores[storeName].samples = samples;
    }
    
    console.log('IndexedDB Report:', report);
    return report;
  }
  
  async clearStore(dbName: string, storeName: string) {
    const db = await openDB(dbName);
    const tx = db.transaction(storeName, 'readwrite');
    await tx.objectStore(storeName).clear();
    console.log(`Cleared store: ${storeName}`);
  }
  
  async exportData(dbName: string) {
    const db = await openDB(dbName);
    const data = {};
    
    for (const storeName of db.objectStoreNames) {
      const tx = db.transaction(storeName, 'readonly');
      const store = tx.objectStore(storeName);
      data[storeName] = await store.getAll();
    }
    
    // Download as JSON
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json'
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${dbName}-export.json`;
    a.click();
  }
}
```

### Chrome DevTools

```typescript
// Custom formatters for Chrome DevTools
if (window.chrome && window.chrome.devtools) {
  window.devtoolsFormatters = [{
    header(obj) {
      if (obj instanceof Patient) {
        return ['div', {}, `Patient: ${obj.name}`];
      }
      return null;
    },
    hasBody() {
      return true;
    },
    body(obj) {
      return ['div', {},
        ['div', {}, `ID: ${obj.id}`],
        ['div', {}, `DOB: ${obj.dateOfBirth}`],
        ['div', {}, `Sync Status: ${obj.syncStatus}`]
      ];
    }
  }];
}
```

## Sync Debugging

### Sync State Inspector

```typescript
class SyncStateInspector {
  async inspectSyncState() {
    const state = {
      queue: await this.inspectQueue(),
      conflicts: await this.inspectConflicts(),
      lastSync: await this.inspectLastSync(),
      pendingChanges: await this.inspectPendingChanges()
    };
    
    console.log('Sync State:', state);
    return state;
  }
  
  private async inspectQueue() {
    const queue = await syncQueue.getAll();
    return {
      total: queue.length,
      byOperation: this.groupBy(queue, 'operation'),
      byCollection: this.groupBy(queue, 'collection'),
      oldestItem: queue[0],
      failedItems: queue.filter(item => item.retryCount > 0)
    };
  }
  
  private async inspectConflicts() {
    const conflicts = await conflictStore.getAll();
    return {
      total: conflicts.length,
      unresolved: conflicts.filter(c => !c.resolved).length,
      byType: this.groupBy(conflicts, 'type'),
      averageAge: this.calculateAverageAge(conflicts)
    };
  }
  
  private async inspectLastSync() {
    const lastSync = await getLastSyncTimestamp();
    const timeSinceSync = Date.now() - lastSync;
    
    return {
      timestamp: lastSync,
      timeSinceSync,
      humanReadable: this.formatDuration(timeSinceSync),
      isOverdue: timeSinceSync > SYNC_INTERVAL
    };
  }
  
  private async inspectPendingChanges() {
    const collections = ['patients', 'records', 'documents'];
    const pending = {};
    
    for (const collection of collections) {
      const changes = await database.collections
        .get(collection)
        .query(Q.where('syncStatus', 'pending'))
        .fetchCount();
      
      pending[collection] = changes;
    }
    
    return pending;
  }
}
```

### Sync Flow Visualization

```typescript
class SyncFlowVisualizer {
  private events: SyncFlowEvent[] = [];
  
  recordEvent(type: string, details: any) {
    this.events.push({
      id: generateId(),
      type,
      timestamp: Date.now(),
      details
    });
  }
  
  generateFlowDiagram() {
    const mermaidCode = this.eventsToMermaid(this.events);
    console.log('Sync Flow Diagram:');
    console.log(mermaidCode);
    
    // Also generate visual timeline
    this.generateTimeline();
  }
  
  private eventsToMermaid(events: SyncFlowEvent[]): string {
    let mermaid = 'sequenceDiagram\n';
    
    events.forEach((event, index) => {
      switch (event.type) {
        case 'sync_start':
          mermaid += `  Client->>Server: Start Sync\n`;
          break;
        case 'push_changes':
          mermaid += `  Client->>Server: Push ${event.details.count} changes\n`;
          break;
        case 'pull_changes':
          mermaid += `  Server->>Client: Pull ${event.details.count} changes\n`;
          break;
        case 'conflict_detected':
          mermaid += `  Note over Client,Server: Conflict detected\n`;
          break;
        case 'conflict_resolved':
          mermaid += `  Client->>Client: Resolve conflict\n`;
          break;
        case 'sync_complete':
          mermaid += `  Note over Client: Sync complete\n`;
          break;
      }
    });
    
    return mermaid;
  }
  
  private generateTimeline() {
    const timeline = this.events.map(event => ({
      time: new Date(event.timestamp).toLocaleTimeString(),
      type: event.type,
      duration: event.details.duration || 0
    }));
    
    console.table(timeline);
  }
}
```

## Performance Debugging

### Performance Profiler

```typescript
class PerformanceProfiler {
  private marks: Map<string, number> = new Map();
  private measures: PerformanceMeasure[] = [];
  
  mark(name: string) {
    this.marks.set(name, performance.now());
    performance.mark(name);
  }
  
  measure(name: string, startMark: string, endMark?: string) {
    const measure = performance.measure(
      name,
      startMark,
      endMark || undefined
    );
    
    this.measures.push({
      name,
      duration: measure.duration,
      startTime: measure.startTime
    });
    
    console.log(`⏱️ ${name}: ${measure.duration.toFixed(2)}ms`);
  }
  
  async profileFunction<T>(
    name: string,
    fn: () => Promise<T>
  ): Promise<T> {
    const startMark = `${name}_start`;
    const endMark = `${name}_end`;
    
    this.mark(startMark);
    
    try {
      const result = await fn();
      this.mark(endMark);
      this.measure(name, startMark, endMark);
      return result;
    } catch (error) {
      this.mark(endMark);
      this.measure(`${name}_error`, startMark, endMark);
      throw error;
    }
  }
  
  generateReport() {
    const report = {
      totalMeasures: this.measures.length,
      averageDuration: this.calculateAverage(this.measures),
      slowestOperations: this.getSlowest(10),
      timeline: this.generateTimeline()
    };
    
    console.log('Performance Report:', report);
    return report;
  }
  
  private getSlowest(count: number): PerformanceMeasure[] {
    return [...this.measures]
      .sort((a, b) => b.duration - a.duration)
      .slice(0, count);
  }
}

// Usage
const profiler = new PerformanceProfiler();

await profiler.profileFunction('syncOperation', async () => {
  await syncEngine.sync();
});

profiler.generateReport();
```

### Render Performance Debugging

```typescript
// React Native render performance
import { unstable_trace as trace } from 'react';

function TracedComponent({ data }) {
  return trace('TracedComponent render', performance.now(), () => {
    // Component logic
    return <View>{/* ... */}</View>;
  });
}

// Track unnecessary renders
class RenderTracker {
  private renders = new Map<string, number>();
  
  trackRender(componentName: string) {
    const count = this.renders.get(componentName) || 0;
    this.renders.set(componentName, count + 1);
    
    if (count > 10) {
      console.warn(`⚠️ ${componentName} rendered ${count} times`);
    }
  }
  
  getReport() {
    const report = Array.from(this.renders.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([name, count]) => ({ component: name, renders: count }));
    
    console.table(report);
    return report;
  }
}
```

## Production Debugging

### Remote Logging

```typescript
class RemoteLogger {
  private queue: LogEntry[] = [];
  private batchSize = 50;
  private flushInterval = 30000; // 30 seconds
  
  constructor(private endpoint: string) {
    setInterval(() => this.flush(), this.flushInterval);
  }
  
  log(level: LogLevel, message: string, context?: any) {
    const entry: LogEntry = {
      timestamp: Date.now(),
      level,
      message,
      context,
      deviceId: getDeviceId(),
      sessionId: getSessionId(),
      userId: getUserId(),
      appVersion: getAppVersion(),
      platform: Platform.OS,
      osVersion: Platform.Version
    };
    
    this.queue.push(entry);
    
    if (this.queue.length >= this.batchSize) {
      this.flush();
    }
  }
  
  async flush() {
    if (this.queue.length === 0) return;
    
    const batch = this.queue.splice(0);
    
    try {
      await fetch(this.endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-App-Version': getAppVersion()
        },
        body: JSON.stringify({ logs: batch })
      });
    } catch (error) {
      // Re-queue on failure
      this.queue.unshift(...batch);
      console.error('Failed to send logs:', error);
    }
  }
}
```

### Crash Reporting

```typescript
// Crash reporter setup
import * as Sentry from '@sentry/react-native';

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: __DEV__ ? 'development' : 'production',
  beforeSend(event, hint) {
    // Add offline context
    event.contexts = {
      ...event.contexts,
      offline: {
        isOffline: !navigator.onLine,
        syncQueueSize: getSyncQueueSize(),
        lastSyncTime: getLastSyncTime(),
        conflictCount: getConflictCount()
      }
    };
    
    // Sanitize sensitive data
    if (event.exception) {
      event.exception.values?.forEach(exception => {
        if (exception.stacktrace) {
          exception.stacktrace.frames?.forEach(frame => {
            // Remove sensitive data from stack traces
            frame.vars = sanitizeVars(frame.vars);
          });
        }
      });
    }
    
    return event;
  }
});

// Custom error boundary
class OfflineErrorBoundary extends React.Component {
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log to remote
    remoteLogger.log('error', 'React error boundary triggered', {
      error: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      offline: !navigator.onLine
    });
    
    // Log locally for offline debugging
    offlineErrorStore.add({
      timestamp: Date.now(),
      error: serializeError(error),
      errorInfo,
      context: this.gatherContext()
    });
  }
  
  private gatherContext() {
    return {
      memoryUsage: getMemoryUsage(),
      storageUsage: getStorageUsage(),
      syncStatus: getSyncStatus(),
      networkStatus: getNetworkStatus()
    };
  }
}
```

### Debug Commands

```typescript
// Debug command system for production
class DebugCommands {
  private commands = new Map<string, DebugCommand>();
  
  constructor() {
    this.registerDefaultCommands();
  }
  
  private registerDefaultCommands() {
    this.register('dumpState', async () => {
      const state = {
        sync: await this.dumpSyncState(),
        database: await this.dumpDatabaseState(),
        cache: await this.dumpCacheState(),
        network: await this.dumpNetworkState()
      };
      
      console.log('State dump:', state);
      return state;
    });
    
    this.register('forceSyncNow', async () => {
      console.log('Forcing sync...');
      await syncEngine.sync({ force: true });
      return 'Sync completed';
    });
    
    this.register('clearSyncQueue', async () => {
      const count = await syncQueue.clear();
      return `Cleared ${count} items from sync queue`;
    });
    
    this.register('resetDatabase', async () => {
      if (confirm('Are you sure? This will delete all local data!')) {
        await database.unsafeResetDatabase();
        return 'Database reset complete';
      }
      return 'Cancelled';
    });
  }
  
  register(name: string, handler: () => Promise<any>) {
    this.commands.set(name, { name, handler });
  }
  
  async execute(commandName: string, ...args: any[]) {
    const command = this.commands.get(commandName);
    if (!command) {
      throw new Error(`Unknown command: ${commandName}`);
    }
    
    return command.handler(...args);
  }
  
  list(): string[] {
    return Array.from(this.commands.keys());
  }
}

// Make available in production console
if (typeof window !== 'undefined') {
  window.debugCommands = new DebugCommands();
}
```

## Debug Utilities

### Data Export

```typescript
class DebugDataExporter {
  async exportAllData(): Promise<string> {
    const data = {
      metadata: {
        exportDate: new Date().toISOString(),
        appVersion: getAppVersion(),
        platform: Platform.OS,
        deviceId: getDeviceId()
      },
      database: await this.exportDatabase(),
      syncQueue: await this.exportSyncQueue(),
      conflicts: await this.exportConflicts(),
      logs: await this.exportLogs(),
      performance: await this.exportPerformanceData()
    };
    
    const json = JSON.stringify(data, null, 2);
    
    // Save to file
    if (Platform.OS === 'web') {
      this.downloadFile(json, 'debug-export.json');
    } else {
      const path = await this.saveToFile(json);
      Share.share({ url: path });
    }
    
    return json;
  }
  
  private async exportDatabase() {
    const collections = ['patients', 'records', 'documents'];
    const data = {};
    
    for (const collectionName of collections) {
      const records = await database.collections
        .get(collectionName)
        .query()
        .fetch();
      
      data[collectionName] = records.map(r => r._raw);
    }
    
    return data;
  }
}
```

### Debug Assertions

```typescript
class DebugAssertions {
  static assertSyncQueueValid() {
    if (!__DEV__) return;
    
    const queue = syncQueue.getAll();
    queue.forEach(item => {
      console.assert(item.id, 'Queue item missing ID');
      console.assert(item.operation, 'Queue item missing operation');
      console.assert(item.timestamp, 'Queue item missing timestamp');
      console.assert(
        ['create', 'update', 'delete'].includes(item.operation),
        `Invalid operation: ${item.operation}`
      );
    });
  }
  
  static assertDatabaseConsistency() {
    if (!__DEV__) return;
    
    // Check for orphaned records
    database.collections.forEach(async collection => {
      const orphaned = await collection.query(
        Q.where('patient_id', Q.notEq(null)),
        Q.experimentalJoinTables(['patients']),
        Q.on('patients', 'id', Q.notEq(null))
      ).fetch();
      
      console.assert(
        orphaned.length === 0,
        `Found ${orphaned.length} orphaned records in ${collection.table}`
      );
    });
  }
  
  static assertNetworkSecurity() {
    if (!__DEV__) return;
    
    // Check for insecure requests
    const originalFetch = global.fetch;
    global.fetch = (url, options) => {
      const urlObj = new URL(url);
      
      console.assert(
        urlObj.protocol === 'https:' || urlObj.hostname === 'localhost',
        `Insecure request to ${url}`
      );
      
      console.assert(
        options?.headers?.['Authorization'],
        `Missing auth header for ${url}`
      );
      
      return originalFetch(url, options);
    };
  }
}
```

## Debug Checklist

### Before Debugging
- [ ] Enable debug mode in app settings
- [ ] Clear app cache and storage
- [ ] Update to latest app version
- [ ] Check device has sufficient storage
- [ ] Ensure stable network connection
- [ ] Export current data for backup

### During Debugging
- [ ] Enable verbose logging
- [ ] Start performance monitoring
- [ ] Begin network request logging
- [ ] Monitor memory usage
- [ ] Track sync operations
- [ ] Record user actions

### Common Solutions
- [ ] Force sync to resolve data issues
- [ ] Clear sync queue for stuck items
- [ ] Reset conflict resolution state
- [ ] Rebuild database indexes
- [ ] Clear service worker cache
- [ ] Re-authenticate user session

### After Debugging
- [ ] Export debug logs
- [ ] Document findings
- [ ] Create bug report if needed
- [ ] Disable debug mode
- [ ] Clear sensitive debug data
- [ ] Verify normal operation

## Conclusion

This debugging guide provides comprehensive tools and techniques for troubleshooting offline functionality in Haven Health Passport. Remember to:

1. Always start with the simplest explanation
2. Use appropriate debugging tools for each platform
3. Monitor performance impact of debugging
4. Document findings for future reference
5. Clean up debug artifacts when done

For additional support, refer to the troubleshooting guide or contact the development team with exported debug logs.