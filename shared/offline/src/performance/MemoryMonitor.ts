import { EventEmitter } from 'events';
import { AppState, AppStateStatus, Platform } from 'react-native';

interface MemoryStats {
  used: number;
  total: number;
  available: number;
  percentUsed: number;
  timestamp: number;
}

interface MemoryThresholds {
  warning: number; // percentage
  critical: number; // percentage
  oom: number; // percentage (out of memory)
}

interface MemoryMonitorConfig {
  sampleInterval: number; // milliseconds
  historySize: number;
  thresholds: MemoryThresholds;
  enableAutoCleanup: boolean;
  enableAlerts: boolean;
}

export class MemoryMonitor extends EventEmitter {
  private config: MemoryMonitorConfig;
  private history: MemoryStats[] = [];
  private monitorInterval?: NodeJS.Timeout;
  private isMonitoring = false;
  private cleanupCallbacks: Array<() => Promise<void>> = [];
  private currentAppState: AppStateStatus = 'active';
  
  constructor(config: Partial<MemoryMonitorConfig> = {}) {
    super();
    this.config = {
      sampleInterval: 5000, // 5 seconds
      historySize: 100,
      thresholds: {
        warning: 70,
        critical: 85,
        oom: 95,
      },
      enableAutoCleanup: true,
      enableAlerts: true,
      ...config,
    };
    
    this.setupAppStateListener();
  }

  /**
   * Start memory monitoring
   */
  start(): void {
    if (this.isMonitoring) return;
    
    this.isMonitoring = true;
    this.monitorInterval = setInterval(() => {
      this.checkMemory();
    }, this.config.sampleInterval);
    
    // Initial check
    this.checkMemory();
    
    this.emit('monitoring-started');
  }

  /**
   * Stop memory monitoring
   */
  stop(): void {
    if (!this.isMonitoring) return;
    
    if (this.monitorInterval) {
      clearInterval(this.monitorInterval);
      this.monitorInterval = undefined;
    }
    
    this.isMonitoring = false;
    this.emit('monitoring-stopped');
  }

  /**
   * Register cleanup callback
   */
  registerCleanupCallback(callback: () => Promise<void>): void {
    this.cleanupCallbacks.push(callback);
  }

  /**
   * Get current memory stats
   */
  getCurrentStats(): MemoryStats | null {
    return this.history.length > 0 ? this.history[this.history.length - 1] : null;
  }

  /**
   * Get memory history
   */
  getHistory(): MemoryStats[] {
    return [...this.history];
  }

  /**
   * Get average memory usage
   */
  getAverageUsage(windowSize?: number): number {
    const stats = windowSize 
      ? this.history.slice(-windowSize)
      : this.history;
    
    if (stats.length === 0) return 0;
    
    const sum = stats.reduce((acc, stat) => acc + stat.percentUsed, 0);
    return sum / stats.length;
  }

  /**
   * Get memory trend
   */
  getMemoryTrend(): 'stable' | 'increasing' | 'decreasing' {
    if (this.history.length < 5) return 'stable';
    
    const recent = this.history.slice(-5);
    const older = this.history.slice(-10, -5);
    
    const recentAvg = recent.reduce((sum, s) => sum + s.percentUsed, 0) / recent.length;
    const olderAvg = older.reduce((sum, s) => sum + s.percentUsed, 0) / older.length;
    
    const difference = recentAvg - olderAvg;
    
    if (Math.abs(difference) < 5) return 'stable';
    return difference > 0 ? 'increasing' : 'decreasing';
  }

  /**
   * Force cleanup
   */
  async forceCleanup(): Promise<void> {
    this.emit('cleanup-started');
    
    const results = await Promise.allSettled(
      this.cleanupCallbacks.map(callback => callback())
    );
    
    const successCount = results.filter(r => r.status === 'fulfilled').length;
    const failureCount = results.filter(r => r.status === 'rejected').length;
    
    this.emit('cleanup-completed', { successCount, failureCount });
    
    // Force garbage collection if available
    if (global.gc) {
      global.gc();
    }
  }

  /**
   * Get memory leak indicators
   */
  detectMemoryLeaks(): {
    hasLeak: boolean;
    confidence: number;
    reason?: string;
  } {
    if (this.history.length < 20) {
      return { hasLeak: false, confidence: 0, reason: 'Insufficient data' };
    }
    
    // Check for continuous increase
    const recent = this.history.slice(-20);
    let increasingCount = 0;
    
    for (let i = 1; i < recent.length; i++) {
      if (recent[i].percentUsed > recent[i - 1].percentUsed) {
        increasingCount++;
      }
    }
    
    const increaseRatio = increasingCount / (recent.length - 1);
    
    if (increaseRatio > 0.8) {
      return {
        hasLeak: true,
        confidence: increaseRatio,
        reason: 'Continuous memory increase detected',
      };
    }
    
    // Check for no memory release after cleanup
    const cleanupEvents = this.findCleanupEvents();
    if (cleanupEvents.length > 0) {
      const lastCleanup = cleanupEvents[cleanupEvents.length - 1];
      const postCleanup = this.history.filter(s => s.timestamp > lastCleanup);
      
      if (postCleanup.length > 5) {
        const beforeCleanupUsage = this.history[lastCleanup].percentUsed;
        const currentUsage = this.getCurrentStats()?.percentUsed || 0;
        
        if (currentUsage >= beforeCleanupUsage) {
          return {
            hasLeak: true,
            confidence: 0.7,
            reason: 'Memory not released after cleanup',
          };
        }
      }
    }
    
    return { hasLeak: false, confidence: 0 };
  }

  /**
   * Private methods
   */
  
  private async checkMemory(): Promise<void> {
    const stats = await this.getMemoryStats();
    
    // Add to history
    this.history.push(stats);
    
    // Trim history if needed
    if (this.history.length > this.config.historySize) {
      this.history = this.history.slice(-this.config.historySize);
    }
    
    // Check thresholds
    this.checkThresholds(stats);
    
    // Emit update
    this.emit('memory-update', stats);
  }

  private async getMemoryStats(): Promise<MemoryStats> {
    // Platform-specific memory info
    // In real implementation, would use native modules
    // For now, simulating with JavaScript memory
    
    let used = 0;
    let total = 0;
    
    if (Platform.OS === 'web' && performance.memory) {
      used = (performance.memory as any).usedJSHeapSize;
      total = (performance.memory as any).totalJSHeapSize;
    } else {
      // Simulate for mobile platforms
      // In production, use react-native-device-info or similar
      used = Math.random() * 500 * 1024 * 1024; // 0-500MB
      total = 1024 * 1024 * 1024; // 1GB
    }
    
    const available = total - used;
    const percentUsed = (used / total) * 100;
    
    return {
      used,
      total,
      available,
      percentUsed,
      timestamp: Date.now(),
    };
  }

  private checkThresholds(stats: MemoryStats): void {
    const { percentUsed } = stats;
    const { thresholds } = this.config;
    
    if (percentUsed >= thresholds.oom) {
      this.handleOOM(stats);
    } else if (percentUsed >= thresholds.critical) {
      this.handleCritical(stats);
    } else if (percentUsed >= thresholds.warning) {
      this.handleWarning(stats);
    }
  }

  private handleWarning(stats: MemoryStats): void {
    if (this.config.enableAlerts) {
      this.emit('memory-warning', stats);
    }
  }

  private handleCritical(stats: MemoryStats): void {
    if (this.config.enableAlerts) {
      this.emit('memory-critical', stats);
    }
    
    if (this.config.enableAutoCleanup) {
      this.forceCleanup();
    }
  }

  private handleOOM(stats: MemoryStats): void {
    if (this.config.enableAlerts) {
      this.emit('memory-oom', stats);
    }
    
    // Aggressive cleanup
    this.forceCleanup();
    
    // Additional emergency measures
    this.emit('emergency-cleanup-required');
  }

  private setupAppStateListener(): void {
    AppState.addEventListener('change', (nextAppState) => {
      this.currentAppState = nextAppState;
      
      if (nextAppState === 'background') {
        // Reduce monitoring frequency in background
        this.stop();
      } else if (nextAppState === 'active' && this.isMonitoring) {
        // Resume monitoring
        this.start();
      }
    });
  }

  private findCleanupEvents(): number[] {
    // Find indices where memory dropped significantly
    const events: number[] = [];
    
    for (let i = 1; i < this.history.length; i++) {
      const drop = this.history[i - 1].percentUsed - this.history[i].percentUsed;
      if (drop > 10) {
        events.push(i);
      }
    }
    
    return events;
  }

  /**
   * Get recommendations based on current memory state
   */
  getRecommendations(): string[] {
    const recommendations: string[] = [];
    const currentStats = this.getCurrentStats();
    
    if (!currentStats) return recommendations;
    
    if (currentStats.percentUsed > this.config.thresholds.warning) {
      recommendations.push('Consider clearing unused caches');
      recommendations.push('Release unnecessary resources');
    }
    
    const trend = this.getMemoryTrend();
    if (trend === 'increasing') {
      recommendations.push('Memory usage is increasing - check for leaks');
    }
    
    const leakDetection = this.detectMemoryLeaks();
    if (leakDetection.hasLeak) {
      recommendations.push(`Potential memory leak detected: ${leakDetection.reason}`);
    }
    
    return recommendations;
  }
}

export default MemoryMonitor;