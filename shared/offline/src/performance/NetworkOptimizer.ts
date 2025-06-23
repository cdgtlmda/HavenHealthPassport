import { EventEmitter } from 'events';
import NetInfo from '@react-native-community/netinfo';
import { BatteryOptimizer } from './BatteryOptimizer';
import { BandwidthThrottler } from '../BandwidthThrottler';

interface NetworkConditions {
  type: 'wifi' | 'cellular' | 'none' | 'unknown';
  isConnected: boolean;
  isInternetReachable: boolean;
  details?: {
    isConnectionExpensive?: boolean;
    cellularGeneration?: '2g' | '3g' | '4g' | '5g';
    strength?: number; // 0-4
  };
  bandwidth?: {
    downlink?: number; // Mbps
    uplink?: number; // Mbps
    rtt?: number; // Round trip time in ms
  };
}

interface SyncConfig {
  enablePowerAwareSync: boolean;
  enableAdaptiveSync: boolean;
  enableProgressiveDownload: boolean;
  enablePartialSync: boolean;
  enableWakeLock: boolean;
  baseInterval: number;
  maxInterval: number;
  minInterval: number;
  qualityPresets: Record<string, QualitySettings>;
  backgroundLimits: {
    maxDuration: number;
    maxDataUsage: number;
  };
}

interface QualitySettings {
  name: string;
  imageQuality: number; // 0-100
  videoQuality: 'auto' | '144p' | '240p' | '360p' | '480p' | '720p' | '1080p';
  audioQuality: 'low' | 'medium' | 'high';
  compressionLevel: number; // 0-9
  enableThumbnails: boolean;
  enablePreviews: boolean;
}

interface SyncTask {
  id: string;
  priority: number;
  size: number;
  type: 'upload' | 'download';
  requiresWifi?: boolean;
  allowCellular?: boolean;
  allowBackground?: boolean;
  progressCallback?: (progress: number) => void;
}

export class NetworkOptimizer extends EventEmitter {
  private config: SyncConfig;
  private batteryOptimizer: BatteryOptimizer;
  private bandwidthThrottler: BandwidthThrottler;
  private networkConditions: NetworkConditions | null = null;
  private syncQueue: SyncTask[] = [];
  private activeSyncs: Map<string, any> = new Map();
  private syncInterval?: NodeJS.Timeout;
  private currentQuality: QualitySettings;
  private wakeLock?: any;
  private backgroundTaskId?: string;
  
  constructor(
    batteryOptimizer: BatteryOptimizer,
    config: Partial<SyncConfig> = {}
  ) {
    super();
    this.batteryOptimizer = batteryOptimizer;
    this.config = {
      enablePowerAwareSync: true,
      enableAdaptiveSync: true,
      enableProgressiveDownload: true,
      enablePartialSync: true,
      enableWakeLock: true,
      baseInterval: 15 * 60 * 1000, // 15 minutes
      maxInterval: 60 * 60 * 1000, // 1 hour
      minInterval: 5 * 60 * 1000, // 5 minutes
      qualityPresets: this.getDefaultQualityPresets(),
      backgroundLimits: {
        maxDuration: 30000, // 30 seconds
        maxDataUsage: 10 * 1024 * 1024, // 10MB
      },
      ...config,
    };
    
    this.bandwidthThrottler = BandwidthThrottler.createAdaptiveThrottler();
    this.currentQuality = this.config.qualityPresets.balanced;
    
    this.initialize();
  }

  /**
   * Initialize network monitoring
   */
  private async initialize(): Promise<void> {
    // Monitor network conditions
    NetInfo.addEventListener(state => {
      this.handleNetworkChange(state);
    });
    
    // Get initial network state
    const state = await NetInfo.fetch();
    this.handleNetworkChange(state);
    
    // Start adaptive sync
    if (this.config.enableAdaptiveSync) {
      this.startAdaptiveSync();
    }
  }

  /**
   * Add sync task
   */
  addSyncTask(task: SyncTask): void {
    // Check if task can be added based on current conditions
    if (!this.canAddTask(task)) {
      this.emit('task-deferred', task);
      return;
    }
    
    // Add to queue with priority sorting
    this.syncQueue.push(task);
    this.syncQueue.sort((a, b) => b.priority - a.priority);
    
    // Process queue
    this.processQueue();
  }

  /**
   * Start power-aware sync
   */
  private startAdaptiveSync(): void {
    const interval = this.calculateSyncInterval();
    
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
    }
    
    this.syncInterval = setInterval(() => {
      this.performSync();
    }, interval);
  }

  /**
   * Calculate adaptive sync interval
   */
  private calculateSyncInterval(): number {
    const batteryStats = this.batteryOptimizer.getBatteryStats();
    const powerProfile = this.batteryOptimizer.getCurrentProfile();
    
    let interval = this.config.baseInterval;
    
    // Adjust based on battery level
    if (batteryStats.currentLevel < 20) {
      interval = this.config.maxInterval;
    } else if (batteryStats.currentLevel < 50) {
      interval = Math.min(interval * 2, this.config.maxInterval);
    }
    
    // Adjust based on charging state
    if (batteryStats.isCharging) {
      interval = this.config.minInterval;
    }
    
    // Adjust based on network conditions
    if (this.networkConditions?.type === 'cellular') {
      interval = Math.min(interval * 1.5, this.config.maxInterval);
    }
    
    // Use power profile sync interval if more conservative
    interval = Math.max(interval, powerProfile.syncInterval);
    
    return interval;
  }

  /**
   * Perform sync with power awareness
   */
  private async performSync(): Promise<void> {
    if (!this.config.enablePowerAwareSync) {
      await this.processQueue();
      return;
    }
    
    const batteryStats = this.batteryOptimizer.getBatteryStats();
    const powerProfile = this.batteryOptimizer.getCurrentProfile();
    
    // Check if sync is allowed
    if (!powerProfile.backgroundTasksEnabled && !this.isInForeground()) {
      this.emit('sync-skipped', { reason: 'background-disabled' });
      return;
    }
    
    if (batteryStats.currentLevel < 10 && !batteryStats.isCharging) {
      this.emit('sync-skipped', { reason: 'low-battery' });
      return;
    }
    
    // Acquire wake lock if enabled
    if (this.config.enableWakeLock) {
      await this.acquireWakeLock();
    }
    
    try {
      await this.processQueue();
    } finally {
      if (this.wakeLock) {
        await this.releaseWakeLock();
      }
    }
  }

  /**
   * Process sync queue
   */
  private async processQueue(): Promise<void> {
    const tasksToProcess = this.getTasksToProcess();
    
    for (const task of tasksToProcess) {
      if (!this.canProcessTask(task)) continue;
      
      try {
        if (task.type === 'download') {
          await this.performDownload(task);
        } else {
          await this.performUpload(task);
        }
        
        // Remove from queue
        const index = this.syncQueue.indexOf(task);
        if (index > -1) {
          this.syncQueue.splice(index, 1);
        }
      } catch (error) {
        this.emit('sync-error', { task, error });
      }
    }
  }

  /**
   * Perform progressive download
   */
  private async performDownload(task: SyncTask): Promise<void> {
    if (!this.config.enableProgressiveDownload) {
      // Regular download
      return this.performRegularDownload(task);
    }
    
    // Progressive download with quality adaptation
    const quality = this.selectQualityForConditions();
    
    this.emit('download-started', { taskId: task.id, quality: quality.name });
    
    // Simulate progressive download
    const chunks = Math.ceil(task.size / (256 * 1024)); // 256KB chunks
    let downloaded = 0;
    
    for (let i = 0; i < chunks; i++) {
      // Check if should continue
      if (!this.shouldContinueDownload(task)) {
        this.emit('download-paused', { taskId: task.id, progress: downloaded / task.size });
        break;
      }
      
      // Download chunk
      const chunkSize = Math.min(256 * 1024, task.size - downloaded);
      await this.downloadChunk(task.id, i, chunkSize);
      
      downloaded += chunkSize;
      
      // Report progress
      if (task.progressCallback) {
        task.progressCallback(downloaded / task.size);
      }
    }
    
    this.emit('download-completed', { taskId: task.id });
  }

  /**
   * Perform partial sync
   */
  private async performPartialSync(task: SyncTask): Promise<void> {
    if (!this.config.enablePartialSync) {
      return this.performRegularDownload(task);
    }
    
    // Determine what parts to sync based on priority and conditions
    const syncParts = this.determineSyncParts(task);
    
    for (const part of syncParts) {
      await this.syncPart(task.id, part);
    }
  }

  /**
   * Select quality based on conditions
   */
  private selectQualityForConditions(): QualitySettings {
    const batteryStats = this.batteryOptimizer.getBatteryStats();
    
    // Low battery - use low quality
    if (batteryStats.currentLevel < 20 && !batteryStats.isCharging) {
      return this.config.qualityPresets.low;
    }
    
    // Check network conditions
    if (this.networkConditions?.type === 'cellular') {
      // Check cellular generation
      const generation = this.networkConditions.details?.cellularGeneration;
      if (generation === '2g' || generation === '3g') {
        return this.config.qualityPresets.low;
      }
    }
    
    // Check bandwidth
    const bandwidth = this.networkConditions?.bandwidth?.downlink;
    if (bandwidth) {
      if (bandwidth < 1) return this.config.qualityPresets.low;
      if (bandwidth < 5) return this.config.qualityPresets.medium;
      if (bandwidth > 10) return this.config.qualityPresets.high;
    }
    
    return this.config.qualityPresets.balanced;
  }

  /**
   * Handle network change
   */
  private handleNetworkChange(state: any): void {
    const previousConditions = this.networkConditions;
    
    this.networkConditions = {
      type: state.type,
      isConnected: state.isConnected,
      isInternetReachable: state.isInternetReachable,
      details: state.details,
    };
    
    // Detect bandwidth if possible
    this.detectBandwidth();
    
    // Adjust sync interval
    if (this.config.enableAdaptiveSync) {
      this.startAdaptiveSync();
    }
    
    // Adjust quality
    this.currentQuality = this.selectQualityForConditions();
    
    this.emit('network-changed', this.networkConditions);
    
    // Process deferred tasks if conditions improved
    if (this.hasImprovedConditions(previousConditions, this.networkConditions)) {
      this.processQueue();
    }
  }

  /**
   * Detect network bandwidth
   */
  private async detectBandwidth(): Promise<void> {
    // Simple bandwidth detection by downloading a test file
    try {
      const testUrl = 'https://example.com/speedtest/1mb.bin';
      const startTime = Date.now();
      
      const response = await fetch(testUrl);
      const data = await response.blob();
      
      const duration = (Date.now() - startTime) / 1000; // seconds
      const sizeMB = data.size / (1024 * 1024);
      const bandwidth = sizeMB / duration * 8; // Mbps
      
      if (this.networkConditions) {
        this.networkConditions.bandwidth = {
          downlink: bandwidth,
        };
      }
      
      // Update bandwidth throttler
      this.bandwidthThrottler.updateBandwidthLimit(bandwidth * 1024 * 1024 / 8);
      
    } catch (error) {
      console.error('Bandwidth detection failed:', error);
    }
  }

  /**
   * Helper methods
   */
  
  private canAddTask(task: SyncTask): boolean {
    // Check network requirements
    if (task.requiresWifi && this.networkConditions?.type !== 'wifi') {
      return false;
    }
    
    if (!task.allowCellular && this.networkConditions?.type === 'cellular') {
      return false;
    }
    
    return true;
  }

  private canProcessTask(task: SyncTask): boolean {
    if (!this.canAddTask(task)) return false;
    
    // Check background limits
    if (!this.isInForeground() && !task.allowBackground) {
      return false;
    }
    
    return true;
  }

  private getTasksToProcess(): SyncTask[] {
    const maxConcurrent = this.networkConditions?.type === 'wifi' ? 3 : 1;
    const available = maxConcurrent - this.activeSyncs.size;
    
    return this.syncQueue.slice(0, available);
  }

  private shouldContinueDownload(task: SyncTask): boolean {
    // Check battery
    const batteryStats = this.batteryOptimizer.getBatteryStats();
    if (batteryStats.currentLevel < 5 && !batteryStats.isCharging) {
      return false;
    }
    
    // Check network
    if (!this.networkConditions?.isConnected) {
      return false;
    }
    
    return true;
  }

  private determineSyncParts(task: SyncTask): any[] {
    // Determine critical parts to sync based on priority
    // This is a simplified implementation
    return [
      { id: 'metadata', priority: 1 },
      { id: 'thumbnails', priority: 2 },
      { id: 'content', priority: 3 },
    ];
  }

  private async downloadChunk(taskId: string, chunkIndex: number, size: number): Promise<void> {
    // Simulate chunk download with throttling
    await this.bandwidthThrottler.throttle(size);
  }

  private async syncPart(taskId: string, part: any): Promise<void> {
    // Simulate partial sync
    await new Promise(resolve => setTimeout(resolve, 100));
  }

  private async performRegularDownload(task: SyncTask): Promise<void> {
    // Regular download implementation
    await this.bandwidthThrottler.throttle(task.size);
  }

  private async performUpload(task: SyncTask): Promise<void> {
    // Upload implementation
    await this.bandwidthThrottler.throttle(task.size);
  }

  private async acquireWakeLock(): Promise<void> {
    // Platform-specific wake lock implementation
    // For web:
    if ('wakeLock' in navigator) {
      try {
        this.wakeLock = await (navigator as any).wakeLock.request('screen');
      } catch (error) {
        console.error('Wake lock failed:', error);
      }
    }
  }

  private async releaseWakeLock(): Promise<void> {
    if (this.wakeLock) {
      await this.wakeLock.release();
      this.wakeLock = null;
    }
  }

  private isInForeground(): boolean {
    // Check if app is in foreground
    return true; // Simplified
  }

  private hasImprovedConditions(
    previous: NetworkConditions | null,
    current: NetworkConditions | null
  ): boolean {
    if (!previous || !current) return false;
    
    // WiFi is better than cellular
    if (previous.type === 'cellular' && current.type === 'wifi') return true;
    
    // Connected is better than disconnected
    if (!previous.isConnected && current.isConnected) return true;
    
    return false;
  }

  private getDefaultQualityPresets(): Record<string, QualitySettings> {
    return {
      high: {
        name: 'high',
        imageQuality: 90,
        videoQuality: '1080p',
        audioQuality: 'high',
        compressionLevel: 0,
        enableThumbnails: true,
        enablePreviews: true,
      },
      balanced: {
        name: 'balanced',
        imageQuality: 70,
        videoQuality: '480p',
        audioQuality: 'medium',
        compressionLevel: 5,
        enableThumbnails: true,
        enablePreviews: true,
      },
      low: {
        name: 'low',
        imageQuality: 50,
        videoQuality: '240p',
        audioQuality: 'low',
        compressionLevel: 9,
        enableThumbnails: true,
        enablePreviews: false,
      },
      minimal: {
        name: 'minimal',
        imageQuality: 30,
        videoQuality: '144p',
        audioQuality: 'low',
        compressionLevel: 9,
        enableThumbnails: false,
        enablePreviews: false,
      },
    };
  }

  /**
   * Cleanup
   */
  destroy(): void {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
    }
    
    if (this.wakeLock) {
      this.releaseWakeLock();
    }
  }
}

export default NetworkOptimizer;