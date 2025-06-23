# Performance Tuning Guide

## Overview

This guide provides detailed instructions for optimizing the performance of Haven Health Passport's offline functionality.

## Table of Contents

1. [Performance Metrics](#performance-metrics)
2. [Mobile Optimization](#mobile-optimization)
3. [Web Optimization](#web-optimization)
4. [Database Tuning](#database-tuning)
5. [Network Optimization](#network-optimization)
6. [Memory Management](#memory-management)
7. [Battery Optimization](#battery-optimization)
8. [Monitoring Tools](#monitoring-tools)

## Performance Metrics

### Key Performance Indicators

| Metric | Target | Measurement |
|--------|--------|-------------|
| App Launch Time | < 2s | Cold start to interactive |
| Sync Time | < 30s | For 1000 records |
| Query Response | < 100ms | 95th percentile |
| Memory Usage | < 200MB | Average runtime |
| Battery Impact | < 5%/hour | Active usage |
| Storage Efficiency | > 80% | Compression ratio |

### Measurement Tools

```typescript
// Performance monitoring setup
const performanceMonitor = new PerformanceMonitor({
  sampleRate: 0.1, // 10% of users
  metrics: ['launch', 'sync', 'query', 'memory'],
  reportingInterval: 3600000 // 1 hour
});

performanceMonitor.on('threshold-exceeded', (metric) => {
  console.warn(`Performance degradation: ${metric.name}`);
});
```

## Mobile Optimization

### React Native Performance

#### 1. Enable Hermes
```javascript
// android/app/build.gradle
project.ext.react = [
  enableHermes: true
]

// iOS: Podfile
use_hermes!
```

#### 2. Optimize Lists
```typescript
// Use FlatList with optimization props
<FlatList
  data={records}
  renderItem={renderItem}
  keyExtractor={(item) => item.id}
  removeClippedSubviews={true}
  maxToRenderPerBatch={10}
  updateCellsBatchingPeriod={50}
  windowSize={10}
  initialNumToRender={10}
  getItemLayout={(data, index) => ({
    length: ITEM_HEIGHT,
    offset: ITEM_HEIGHT * index,
    index,
  })}
/>
```

#### 3. Image Optimization
```typescript
// Use FastImage for better caching
import FastImage from 'react-native-fast-image';

<FastImage
  style={styles.image}
  source={{
    uri: imageUrl,
    priority: FastImage.priority.normal,
    cache: FastImage.cacheControl.immutable,
  }}
  resizeMode={FastImage.resizeMode.contain}
/>
```

#### 4. Navigation Performance
```typescript
// Lazy load screens
const ProfileScreen = lazy(() => import('./screens/Profile'));

// Use React.memo for screens
export default React.memo(ProfileScreen, (prevProps, nextProps) => {
  return prevProps.userId === nextProps.userId;
});
```

### iOS Specific

```swift
// Enable background fetch
func application(_ application: UIApplication,
                performFetchWithCompletionHandler completionHandler:
                @escaping (UIBackgroundFetchResult) -> Void) {
    // Perform sync
    OfflineSync.shared.backgroundSync { result in
        completionHandler(result)
    }
}
```

### Android Specific

```java
// Use WorkManager for background sync
public class SyncWorker extends Worker {
    @Override
    public Result doWork() {
        // Perform sync
        return OfflineSync.performSync() 
            ? Result.success() 
            : Result.retry();
    }
}
```

## Web Optimization

### Progressive Web App

#### 1. Service Worker Optimization
```javascript
// Efficient caching strategy
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request)
      .then(cachedResponse => {
        if (cachedResponse) {
          // Return cache and update in background
          event.waitUntil(
            fetch(event.request).then(response => {
              return caches.open(CACHE_NAME).then(cache => {
                cache.put(event.request, response.clone());
              });
            })
          );
          return cachedResponse;
        }
        
        return fetch(event.request);
      })
  );
});
```

#### 2. Bundle Optimization
```javascript
// webpack.config.js
module.exports = {
  optimization: {
    usedExports: true,
    sideEffects: false,
    splitChunks: {
      chunks: 'all',
      cacheGroups: {
        vendor: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          priority: 10
        },
        common: {
          minChunks: 2,
          priority: 5,
          reuseExistingChunk: true
        }
      }
    }
  }
};
```

#### 3. Lazy Loading
```typescript
// Route-based code splitting
const HealthRecords = lazy(() => 
  import(/* webpackChunkName: "health-records" */ './pages/HealthRecords')
);

// Component lazy loading
const HeavyComponent = lazy(() =>
  import(/* webpackPrefetch: true */ './components/HeavyComponent')
);
```

## Database Tuning

### WatermelonDB Optimization

```typescript
// 1. Batch operations
await database.batch(
  ...patients.map(patient => 
    patientsCollection.prepareCreate(draft => {
      draft.name = patient.name;
      draft.dateOfBirth = patient.dateOfBirth;
    })
  )
);

// 2. Use raw queries for complex operations
const complexRecords = await database.adapter.unsafeQueryRaw(
  'SELECT * FROM records WHERE patient_id = ? AND created_at > ?',
  [patientId, lastSyncDate]
);

// 3. Index optimization
await database.adapter.unsafeExecute(
  'CREATE INDEX idx_records_patient_date ON records (patient_id, created_at)'
);
```

### IndexedDB Optimization

```typescript
// 1. Use compound indexes
const store = db.createObjectStore('records', { keyPath: 'id' });
store.createIndex('patient_date', ['patientId', 'createdAt']);

// 2. Cursor-based pagination
async function* paginateRecords(pageSize = 100) {
  const tx = db.transaction('records', 'readonly');
  const index = tx.objectStore('records').index('createdAt');
  const cursor = await index.openCursor(null, 'prev');
  
  let count = 0;
  while (cursor) {
    yield cursor.value;
    count++;
    
    if (count >= pageSize) {
      yield null; // Page break
      count = 0;
    }
    
    await cursor.continue();
  }
}
```

## Network Optimization

### Connection Management

```typescript
// 1. Connection pooling
const connectionPool = new ConnectionPoolManager({
  maxConnections: 6,
  maxConnectionsPerHost: 2,
  keepAliveTimeout: 30000,
  enableHttp2: true
});

// 2. Request prioritization
const requestQueue = new PriorityQueue({
  priorities: {
    critical: 1,    // Medical emergencies
    high: 2,        // User-initiated actions
    normal: 3,      // Background sync
    low: 4          // Analytics, logs
  }
});

// 3. Adaptive quality
const adaptiveSync = new AdaptiveSync({
  bandwidthThresholds: {
    high: 10 * 1024 * 1024,    // 10 Mbps
    medium: 1 * 1024 * 1024,    // 1 Mbps
    low: 256 * 1024             // 256 Kbps
  },
  qualitySettings: {
    high: { imageQuality: 0.9, enableVideo: true },
    medium: { imageQuality: 0.7, enableVideo: false },
    low: { imageQuality: 0.5, enableVideo: false }
  }
});
```

### Bandwidth Management

```typescript
// Progressive download
async function progressiveDownload(url: string, onProgress: Function) {
  const response = await fetch(url);
  const reader = response.body.getReader();
  const contentLength = +response.headers.get('Content-Length');
  
  let receivedLength = 0;
  let chunks = [];
  
  while(true) {
    const {done, value} = await reader.read();
    
    if (done) break;
    
    chunks.push(value);
    receivedLength += value.length;
    
    onProgress(receivedLength / contentLength);
    
    // Process partial data if possible
    if (receivedLength > 1024 * 1024) { // 1MB
      await processPartialData(chunks);
      chunks = [];
    }
  }
}
```

## Memory Management

### Memory Optimization Strategies

```typescript
// 1. Implement object pooling
class ObjectPool<T> {
  private pool: T[] = [];
  private factory: () => T;
  private reset: (obj: T) => void;
  
  acquire(): T {
    return this.pool.pop() || this.factory();
  }
  
  release(obj: T): void {
    this.reset(obj);
    this.pool.push(obj);
  }
}

// 2. Use WeakMap for metadata
const metadataCache = new WeakMap();

function attachMetadata(record: Record, metadata: any) {
  metadataCache.set(record, metadata);
}

// 3. Implement aggressive cleanup
class MemoryManager {
  private cleanupThreshold = 0.8; // 80% memory usage
  
  async monitorAndClean() {
    const usage = await this.getMemoryUsage();
    
    if (usage.percentage > this.cleanupThreshold) {
      await this.performCleanup();
    }
  }
  
  private async performCleanup() {
    // Clear caches
    imageCache.clear();
    queryCache.evictLRU(50); // Evict 50% least recently used
    
    // Garbage collection hint
    if (global.gc) global.gc();
  }
}
```

### Cache Management

```typescript
// Intelligent cache with TTL and size limits
class SmartCache<T> {
  private cache = new Map<string, CacheEntry<T>>();
  private maxSize: number;
  private maxAge: number;
  
  async get(key: string, factory: () => Promise<T>): Promise<T> {
    const entry = this.cache.get(key);
    
    if (entry && !this.isExpired(entry)) {
      entry.lastAccess = Date.now();
      return entry.value;
    }
    
    // Check size before adding
    if (this.cache.size >= this.maxSize) {
      this.evictLRU();
    }
    
    const value = await factory();
    this.cache.set(key, {
      value,
      created: Date.now(),
      lastAccess: Date.now()
    });
    
    return value;
  }
}
```

## Battery Optimization

### Power-Aware Sync

```typescript
// 1. Battery-aware scheduling
class BatteryAwareScheduler {
  async scheduleTask(task: Task) {
    const battery = await this.getBatteryStatus();
    
    if (battery.level < 20 && !battery.isCharging) {
      // Defer non-critical tasks
      if (task.priority < Priority.HIGH) {
        return this.deferTask(task);
      }
    }
    
    if (battery.isCharging) {
      // Optimal time for heavy operations
      return this.executeNow(task);
    }
    
    // Normal scheduling
    return this.scheduleNormal(task);
  }
}

// 2. Reduce wake locks
async function efficientSync() {
  const wakeLock = await navigator.wakeLock.request('screen');
  
  try {
    // Batch all operations
    await Promise.all([
      syncRecords(),
      uploadPhotos(),
      downloadUpdates()
    ]);
  } finally {
    // Always release
    wakeLock.release();
  }
}

// 3. Adaptive sync intervals
function calculateSyncInterval(batteryLevel: number): number {
  if (batteryLevel > 80) return 5 * 60 * 1000;      // 5 minutes
  if (batteryLevel > 50) return 15 * 60 * 1000;     // 15 minutes
  if (batteryLevel > 20) return 30 * 60 * 1000;     // 30 minutes
  return 60 * 60 * 1000;                            // 1 hour
}
```

## Monitoring Tools

### Performance Dashboard

```typescript
// Real-time performance monitoring
class PerformanceDashboard {
  private metrics = {
    fps: new MovingAverage(60),
    memory: new MovingAverage(60),
    networkLatency: new MovingAverage(100),
    queryTime: new MovingAverage(100)
  };
  
  startMonitoring() {
    // FPS monitoring
    let lastTime = performance.now();
    const measureFPS = () => {
      const now = performance.now();
      const fps = 1000 / (now - lastTime);
      this.metrics.fps.add(fps);
      lastTime = now;
      requestAnimationFrame(measureFPS);
    };
    requestAnimationFrame(measureFPS);
    
    // Memory monitoring
    setInterval(() => {
      if (performance.memory) {
        const used = performance.memory.usedJSHeapSize;
        const total = performance.memory.totalJSHeapSize;
        this.metrics.memory.add(used / total * 100);
      }
    }, 1000);
  }
  
  getReport() {
    return {
      fps: this.metrics.fps.average(),
      memory: this.metrics.memory.average(),
      networkLatency: this.metrics.networkLatency.average(),
      queryTime: this.metrics.queryTime.average()
    };
  }
}
```

### Debug Tools

```typescript
// Performance profiler
if (__DEV__) {
  require('react-native-performance').setResourceLoggingEnabled(true);
  
  // Trace sync operations
  Performance.mark('sync-start');
  await syncEngine.sync();
  Performance.mark('sync-end');
  Performance.measure('sync-duration', 'sync-start', 'sync-end');
  
  // Log slow operations
  const measure = Performance.getEntriesByName('sync-duration')[0];
  if (measure.duration > 5000) {
    console.warn('Slow sync detected:', measure.duration);
  }
}
```

## Best Practices Summary

1. **Profile First**: Always measure before optimizing
2. **Optimize Critical Path**: Focus on user-facing operations
3. **Lazy Load Everything**: Defer non-critical work
4. **Cache Wisely**: Balance memory vs. performance
5. **Batch Operations**: Reduce overhead
6. **Monitor Production**: Real-world data is key
7. **Test on Low-End Devices**: Ensure broad compatibility
8. **Respect Battery**: Users notice power drain
9. **Progressive Enhancement**: Start fast, enhance later
10. **Continuous Monitoring**: Performance is not a one-time fix

## Benchmarking

```typescript
// Automated performance benchmarks
class PerformanceBenchmark {
  async run() {
    const results = {
      coldStart: await this.measureColdStart(),
      syncTime: await this.measureSync(1000), // 1000 records
      queryPerformance: await this.measureQueries(),
      memoryUsage: await this.measureMemory(),
      batteryImpact: await this.measureBattery()
    };
    
    // Compare with baselines
    this.compareWithBaseline(results);
    
    // Generate report
    return this.generateReport(results);
  }
}
```

Remember: Performance optimization is an ongoing process. Regular monitoring, user feedback, and continuous improvement are key to maintaining a fast, efficient offline experience.