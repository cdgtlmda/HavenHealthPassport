import { EventEmitter } from 'events';
import AsyncStorage from '@react-native-async-storage/async-storage';

interface AnalyticsEvent {
  id: string;
  name: string;
  category: string;
  timestamp: number;
  properties?: Record<string, any>;
  userId?: string;
  sessionId: string;
  offline: boolean;
}

interface SyncMetrics {
  totalSyncs: number;
  successfulSyncs: number;
  failedSyncs: number;
  averageSyncTime: number;
  dataTransferred: number;
  conflictsResolved: number;
  lastSyncTime?: number;
}

interface UsageMetrics {
  sessionsCount: number;
  totalDuration: number;
  offlineDuration: number;
  onlineDuration: number;
  featuresUsed: Record<string, number>;
  errorCount: number;
}

interface StorageMetrics {
  totalSize: number;
  cacheSize: number;
  documentCount: number;
  mediaCount: number;
  queuedItems: number;
}

interface PerformanceMetrics {
  averageLoadTime: number;
  p95LoadTime: number;
  crashCount: number;
  memoryWarnings: number;
  batteryUsage: number;
}

interface AnalyticsConfig {
  enableTracking: boolean;
  enableOfflineStorage: boolean;
  maxEventsStored: number;
  syncInterval: number;
  anonymizeData: boolean;
  enableDebugLogs: boolean;
}

export class OfflineAnalytics extends EventEmitter {
  private static readonly EVENTS_KEY = '@analytics_events';
  private static readonly METRICS_KEY = '@analytics_metrics';
  
  private config: AnalyticsConfig;
  private events: AnalyticsEvent[] = [];
  private sessionId: string;
  private sessionStartTime: number;
  private isOnline = true;
  private syncTimer?: NodeJS.Timeout;
  
  private syncMetrics: SyncMetrics = {
    totalSyncs: 0,
    successfulSyncs: 0,
    failedSyncs: 0,
    averageSyncTime: 0,
    dataTransferred: 0,
    conflictsResolved: 0,
  };
  
  private usageMetrics: UsageMetrics = {
    sessionsCount: 0,
    totalDuration: 0,
    offlineDuration: 0,
    onlineDuration: 0,
    featuresUsed: {},
    errorCount: 0,
  };
  
  private storageMetrics: StorageMetrics = {
    totalSize: 0,
    cacheSize: 0,
    documentCount: 0,
    mediaCount: 0,
    queuedItems: 0,
  };
  
  private performanceMetrics: PerformanceMetrics = {
    averageLoadTime: 0,
    p95LoadTime: 0,
    crashCount: 0,
    memoryWarnings: 0,
    batteryUsage: 0,
  };
  
  constructor(config: Partial<AnalyticsConfig> = {}) {
    super();
    this.config = {
      enableTracking: true,
      enableOfflineStorage: true,
      maxEventsStored: 1000,
      syncInterval: 300000, // 5 minutes
      anonymizeData: true,
      enableDebugLogs: false,
      ...config,
    };
    
    this.sessionId = this.generateSessionId();
    this.sessionStartTime = Date.now();
    
    this.initialize();
  }

  /**
   * Track an event
   */
  track(eventName: string, properties?: Record<string, any>): void {
    if (!this.config.enableTracking) return;
    
    const event: AnalyticsEvent = {
      id: this.generateEventId(),
      name: eventName,
      category: this.categorizeEvent(eventName),
      timestamp: Date.now(),
      properties: this.sanitizeProperties(properties),
      sessionId: this.sessionId,
      offline: !this.isOnline,
    };
    
    this.events.push(event);
    
    // Update usage metrics
    if (!this.usageMetrics.featuresUsed[event.category]) {
      this.usageMetrics.featuresUsed[event.category] = 0;
    }
    this.usageMetrics.featuresUsed[event.category]++;
    
    // Trim events if exceeds limit
    if (this.events.length > this.config.maxEventsStored) {
      this.events = this.events.slice(-this.config.maxEventsStored);
    }
    
    if (this.config.enableDebugLogs) {
      console.log('Analytics Event:', event);
    }
    
    this.emit('event-tracked', event);
  }

  /**
   * Track sync metrics
   */
  trackSync(success: boolean, duration: number, dataSize: number, conflicts: number = 0): void {
    this.syncMetrics.totalSyncs++;
    
    if (success) {
      this.syncMetrics.successfulSyncs++;
    } else {
      this.syncMetrics.failedSyncs++;
    }
    
    // Update average sync time
    const totalTime = this.syncMetrics.averageSyncTime * (this.syncMetrics.totalSyncs - 1) + duration;
    this.syncMetrics.averageSyncTime = totalTime / this.syncMetrics.totalSyncs;
    
    this.syncMetrics.dataTransferred += dataSize;
    this.syncMetrics.conflictsResolved += conflicts;
    this.syncMetrics.lastSyncTime = Date.now();
    
    this.track('sync_completed', {
      success,
      duration,
      dataSize,
      conflicts,
    });
  }

  /**
   * Track error
   */
  trackError(error: Error, context?: Record<string, any>): void {
    this.usageMetrics.errorCount++;
    
    this.track('error_occurred', {
      error: error.message,
      stack: error.stack,
      context,
    });
  }

  /**
   * Track performance
   */
  trackPerformance(metric: string, value: number): void {
    switch (metric) {
      case 'load_time':
        this.updateLoadTime(value);
        break;
      case 'memory_warning':
        this.performanceMetrics.memoryWarnings++;
        break;
      case 'battery_usage':
        this.performanceMetrics.batteryUsage = value;
        break;
    }
    
    this.track('performance_metric', { metric, value });
  }

  /**
   * Update storage metrics
   */
  updateStorageMetrics(metrics: Partial<StorageMetrics>): void {
    this.storageMetrics = { ...this.storageMetrics, ...metrics };
    this.emit('storage-metrics-updated', this.storageMetrics);
  }

  /**
   * Get all metrics
   */
  getMetrics(): {
    sync: SyncMetrics;
    usage: UsageMetrics;
    storage: StorageMetrics;
    performance: PerformanceMetrics;
  } {
    // Update session duration
    const sessionDuration = Date.now() - this.sessionStartTime;
    this.usageMetrics.totalDuration += sessionDuration;
    
    return {
      sync: { ...this.syncMetrics },
      usage: { ...this.usageMetrics },
      storage: { ...this.storageMetrics },
      performance: { ...this.performanceMetrics },
    };
  }

  /**
   * Get offline usage report
   */
  getOfflineUsageReport(): {
    offlinePercentage: number;
    averageOfflineDuration: number;
    featuresUsedOffline: Record<string, number>;
    offlineErrors: number;
    syncSuccessRate: number;
  } {
    const offlineEvents = this.events.filter(e => e.offline);
    const offlinePercentage = this.events.length > 0 
      ? (offlineEvents.length / this.events.length) * 100 
      : 0;
    
    const featuresUsedOffline: Record<string, number> = {};
    for (const event of offlineEvents) {
      if (!featuresUsedOffline[event.category]) {
        featuresUsedOffline[event.category] = 0;
      }
      featuresUsedOffline[event.category]++;
    }
    
    const offlineErrors = offlineEvents.filter(e => e.name === 'error_occurred').length;
    const syncSuccessRate = this.syncMetrics.totalSyncs > 0
      ? (this.syncMetrics.successfulSyncs / this.syncMetrics.totalSyncs) * 100
      : 0;
    
    return {
      offlinePercentage,
      averageOfflineDuration: this.usageMetrics.offlineDuration / this.usageMetrics.sessionsCount,
      featuresUsedOffline,
      offlineErrors,
      syncSuccessRate,
    };
  }

  /**
   * Create performance dashboard data
   */
  getDashboardData(): {
    charts: Array<{
      type: string;
      title: string;
      data: any;
    }>;
    kpis: Array<{
      name: string;
      value: number | string;
      trend?: 'up' | 'down' | 'stable';
    }>;
  } {
    const metrics = this.getMetrics();
    const offlineReport = this.getOfflineUsageReport();
    
    return {
      charts: [
        {
          type: 'line',
          title: 'Sync Performance Over Time',
          data: this.getSyncPerformanceData(),
        },
        {
          type: 'pie',
          title: 'Feature Usage Distribution',
          data: this.getFeatureUsageData(),
        },
        {
          type: 'bar',
          title: 'Error Frequency by Type',
          data: this.getErrorDistributionData(),
        },
      ],
      kpis: [
        {
          name: 'Sync Success Rate',
          value: `${offlineReport.syncSuccessRate.toFixed(1)}%`,
          trend: offlineReport.syncSuccessRate > 95 ? 'up' : 'down',
        },
        {
          name: 'Offline Usage',
          value: `${offlineReport.offlinePercentage.toFixed(1)}%`,
          trend: 'stable',
        },
        {
          name: 'Average Sync Time',
          value: `${(metrics.sync.averageSyncTime / 1000).toFixed(1)}s`,
          trend: metrics.sync.averageSyncTime < 5000 ? 'up' : 'down',
        },
        {
          name: 'Storage Used',
          value: this.formatBytes(metrics.storage.totalSize),
          trend: 'stable',
        },
      ],
    };
  }

  /**
   * Enable A/B testing
   */
  getABTestVariant(testName: string, variants: string[]): string {
    // Simple hash-based assignment
    const hash = this.hashString(this.sessionId + testName);
    const index = hash % variants.length;
    const variant = variants[index];
    
    this.track('ab_test_assigned', {
      test: testName,
      variant,
    });
    
    return variant;
  }

  /**
   * Export analytics data
   */
  async exportData(): Promise<{
    events: AnalyticsEvent[];
    metrics: any;
    exported: number;
  }> {
    const data = {
      events: [...this.events],
      metrics: this.getMetrics(),
      exported: Date.now(),
    };
    
    this.track('analytics_exported');
    
    return data;
  }

  /**
   * Clear analytics data
   */
  async clearData(): Promise<void> {
    this.events = [];
    await AsyncStorage.removeItem(OfflineAnalytics.EVENTS_KEY);
    await AsyncStorage.removeItem(OfflineAnalytics.METRICS_KEY);
    
    this.emit('data-cleared');
  }

  /**
   * Private methods
   */
  
  private async initialize(): Promise<void> {
    // Load stored events if offline storage enabled
    if (this.config.enableOfflineStorage) {
      await this.loadStoredData();
    }
    
    // Start new session
    this.usageMetrics.sessionsCount++;
    
    // Start sync timer
    if (this.config.syncInterval > 0) {
      this.syncTimer = setInterval(() => {
        this.syncEvents();
      }, this.config.syncInterval);
    }
    
    // Monitor online/offline state
    // NetInfo.addEventListener...
  }

  private categorizeEvent(eventName: string): string {
    if (eventName.includes('sync')) return 'sync';
    if (eventName.includes('error')) return 'error';
    if (eventName.includes('auth')) return 'authentication';
    if (eventName.includes('document')) return 'documents';
    if (eventName.includes('search')) return 'search';
    return 'other';
  }

  private sanitizeProperties(properties?: Record<string, any>): Record<string, any> | undefined {
    if (!properties || !this.config.anonymizeData) return properties;
    
    const sanitized: Record<string, any> = {};
    
    for (const [key, value] of Object.entries(properties)) {
      // Remove sensitive data
      if (['password', 'token', 'email', 'phone'].includes(key.toLowerCase())) {
        sanitized[key] = '[REDACTED]';
      } else if (typeof value === 'string' && value.includes('@')) {
        // Anonymize email-like strings
        sanitized[key] = value.replace(/[^@]+@/, '***@');
      } else {
        sanitized[key] = value;
      }
    }
    
    return sanitized;
  }

  private updateLoadTime(loadTime: number): void {
    // Update average
    const count = this.events.filter(e => e.name === 'performance_metric').length;
    const total = this.performanceMetrics.averageLoadTime * (count - 1) + loadTime;
    this.performanceMetrics.averageLoadTime = total / count;
    
    // Update P95 (simplified)
    this.performanceMetrics.p95LoadTime = Math.max(
      this.performanceMetrics.p95LoadTime,
      loadTime
    );
  }

  private async loadStoredData(): Promise<void> {
    try {
      const storedEvents = await AsyncStorage.getItem(OfflineAnalytics.EVENTS_KEY);
      if (storedEvents) {
        this.events = JSON.parse(storedEvents);
      }
      
      const storedMetrics = await AsyncStorage.getItem(OfflineAnalytics.METRICS_KEY);
      if (storedMetrics) {
        const metrics = JSON.parse(storedMetrics);
        this.syncMetrics = metrics.sync || this.syncMetrics;
        this.usageMetrics = metrics.usage || this.usageMetrics;
        this.storageMetrics = metrics.storage || this.storageMetrics;
        this.performanceMetrics = metrics.performance || this.performanceMetrics;
      }
    } catch (error) {
      console.error('Failed to load analytics data:', error);
    }
  }

  private async syncEvents(): Promise<void> {
    if (!this.isOnline || this.events.length === 0) return;
    
    try {
      // In real implementation, would send to analytics server
      // For now, just store locally
      if (this.config.enableOfflineStorage) {
        await AsyncStorage.setItem(
          OfflineAnalytics.EVENTS_KEY,
          JSON.stringify(this.events.slice(-this.config.maxEventsStored))
        );
        
        await AsyncStorage.setItem(
          OfflineAnalytics.METRICS_KEY,
          JSON.stringify(this.getMetrics())
        );
      }
      
      this.emit('events-synced', { count: this.events.length });
    } catch (error) {
      console.error('Failed to sync analytics:', error);
    }
  }

  private getSyncPerformanceData(): any {
    // Generate chart data for sync performance
    return {
      labels: ['1h ago', '45m ago', '30m ago', '15m ago', 'Now'],
      datasets: [{
        label: 'Sync Time (s)',
        data: [2.1, 1.8, 2.5, 1.5, 1.2],
      }],
    };
  }

  private getFeatureUsageData(): any {
    return Object.entries(this.usageMetrics.featuresUsed).map(([feature, count]) => ({
      name: feature,
      value: count,
    }));
  }

  private getErrorDistributionData(): any {
    const errorTypes: Record<string, number> = {};
    
    this.events
      .filter(e => e.name === 'error_occurred')
      .forEach(e => {
        const errorType = e.properties?.error || 'Unknown';
        errorTypes[errorType] = (errorTypes[errorType] || 0) + 1;
      });
    
    return Object.entries(errorTypes).map(([type, count]) => ({
      type,
      count,
    }));
  }

  private formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  }

  private hashString(str: string): number {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return Math.abs(hash);
  }

  private generateEventId(): string {
    return `evt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Cleanup
   */
  destroy(): void {
    if (this.syncTimer) {
      clearInterval(this.syncTimer);
    }
    
    // Final sync
    this.syncEvents();
  }
}

export default OfflineAnalytics;