import { PerformanceMonitor, PerformanceMetrics, PerformanceEntry, PerformanceOptions } from '../types';
import DeviceInfo from 'react-native-device-info';
import { AppState, AppStateStatus } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

export class ReactNativePerformanceMonitor implements PerformanceMonitor {
  private measurements: Map<string, number[]> = new Map();
  private marks: Map<string, number> = new Map();
  private observers: Set<(metrics: PerformanceMetrics) => void> = new Set();
  private isMonitoring = false;
  private appStateSubscription: any;
  private lastFrameTime = 0;
  private frameCount = 0;
  private fpsHistory: number[] = [];
  private memoryUsageHistory: number[] = [];

  async initialize(options?: PerformanceOptions): Promise<void> {
    this.isMonitoring = true;

    // Monitor app state changes
    this.appStateSubscription = AppState.addEventListener(
      'change',
      this.handleAppStateChange
    );

    // Start monitoring if requested
    if (options?.autoStart) {
      this.startMonitoring();
    }

    // Load historical data
    await this.loadHistoricalData();
  }

  mark(name: string): void {
    this.marks.set(name, performance.now());
  }

  measure(name: string, startMark?: string, endMark?: string): PerformanceEntry | null {
    const endTime = endMark ? this.marks.get(endMark) : performance.now();
    const startTime = startMark ? this.marks.get(startMark) : this.marks.get(name);

    if (!startTime || !endTime) {
      console.warn(`Performance marks not found for measure: ${name}`);
      return null;
    }

    const duration = endTime - startTime;
    
    // Store measurement
    const measurements = this.measurements.get(name) || [];
    measurements.push(duration);
    if (measurements.length > 100) {
      measurements.shift(); // Keep only last 100 measurements
    }
    this.measurements.set(name, measurements);

    const entry: PerformanceEntry = {
      name,
      entryType: 'measure',
      startTime,
      duration,
      timestamp: Date.now(),
    };

    this.notifyObservers();
    return entry;
  }

  async getMetrics(): Promise<PerformanceMetrics> {
    const deviceInfo = await this.getDeviceInfo();
    const memoryInfo = await this.getMemoryInfo();
    const storageInfo = await this.getStorageInfo();
    const networkMetrics = await this.getNetworkMetrics();

    return {
      cpu: {
        usage: 0, // React Native doesn't provide CPU usage
        cores: deviceInfo.cores,
      },
      memory: {
        used: memoryInfo.used,
        total: memoryInfo.total,
        available: memoryInfo.available,
      },
      storage: {
        used: storageInfo.used,
        total: storageInfo.total,
        available: storageInfo.available,
      },
      battery: {
        level: await DeviceInfo.getBatteryLevel(),
        charging: await DeviceInfo.isBatteryCharging(),
      },
      network: networkMetrics,
      fps: this.calculateAverageFPS(),
      jsHeapSize: memoryInfo.jsHeapSize,
      renderTime: this.getAverageRenderTime(),
      customMetrics: this.getCustomMetrics(),
    };
  }
  startMonitoring(): void {
    if (!this.isMonitoring) {
      this.isMonitoring = true;
      this.startFPSMonitoring();
      this.startMemoryMonitoring();
    }
  }

  stopMonitoring(): void {
    this.isMonitoring = false;
    // Clear any monitoring intervals
  }

  clearMetrics(): void {
    this.measurements.clear();
    this.marks.clear();
    this.fpsHistory = [];
    this.memoryUsageHistory = [];
  }

  onMetricsUpdate(callback: (metrics: PerformanceMetrics) => void): () => void {
    this.observers.add(callback);
    return () => {
      this.observers.delete(callback);
    };
  }

  async exportMetrics(): Promise<string> {
    const metrics = await this.getMetrics();
    const data = {
      timestamp: Date.now(),
      deviceInfo: await this.getDeviceInfo(),
      metrics,
      measurements: Object.fromEntries(this.measurements),
      history: {
        fps: this.fpsHistory,
        memory: this.memoryUsageHistory,
      },
    };

    return JSON.stringify(data, null, 2);
  }

  destroy(): void {
    this.stopMonitoring();
    if (this.appStateSubscription) {
      this.appStateSubscription.remove();
    }
    this.observers.clear();
    this.clearMetrics();
  }

  // Private methods
  private handleAppStateChange = (nextAppState: AppStateStatus) => {
    if (nextAppState === 'active') {
      this.startMonitoring();
    } else {
      this.stopMonitoring();
    }
  };

  private startFPSMonitoring(): void {
    let lastFrameTime = performance.now();
    const measureFPS = () => {
      if (!this.isMonitoring) return;

      const currentTime = performance.now();
      const delta = currentTime - lastFrameTime;
      const fps = 1000 / delta;
      
      this.fpsHistory.push(fps);
      if (this.fpsHistory.length > 60) {
        this.fpsHistory.shift();
      }

      lastFrameTime = currentTime;
      requestAnimationFrame(measureFPS);
    };
    
    requestAnimationFrame(measureFPS);
  }

  private startMemoryMonitoring(): void {
    const interval = setInterval(async () => {
      if (!this.isMonitoring) {
        clearInterval(interval);
        return;
      }

      const memoryInfo = await this.getMemoryInfo();
      this.memoryUsageHistory.push(memoryInfo.used);
      if (this.memoryUsageHistory.length > 60) {
        this.memoryUsageHistory.shift();
      }

      this.notifyObservers();
    }, 5000); // Every 5 seconds
  }
  private async getDeviceInfo(): Promise<any> {
    return {
      brand: await DeviceInfo.getBrand(),
      model: await DeviceInfo.getModel(),
      systemName: await DeviceInfo.getSystemName(),
      systemVersion: await DeviceInfo.getSystemVersion(),
      cores: 0, // React Native doesn't expose CPU core count directly
      deviceId: await DeviceInfo.getDeviceId(),
      isEmulator: await DeviceInfo.isEmulator(),
      totalMemory: await DeviceInfo.getTotalMemory(),
      totalDiskCapacity: await DeviceInfo.getTotalDiskCapacity(),
    };
  }

  private async getMemoryInfo(): Promise<any> {
    const totalMemory = await DeviceInfo.getTotalMemory();
    const usedMemory = await DeviceInfo.getUsedMemory();
    
    return {
      total: totalMemory,
      used: usedMemory,
      available: totalMemory - usedMemory,
      jsHeapSize: 0, // Not directly available in React Native
    };
  }

  private async getStorageInfo(): Promise<any> {
    const totalDisk = await DeviceInfo.getTotalDiskCapacity();
    const freeDisk = await DeviceInfo.getFreeDiskStorage();
    
    return {
      total: totalDisk,
      used: totalDisk - freeDisk,
      available: freeDisk,
    };
  }

  private async getNetworkMetrics(): Promise<any> {
    // Network metrics would come from the NetworkMonitor
    return {
      latency: 0,
      bandwidth: 0,
      type: 'unknown',
    };
  }

  private calculateAverageFPS(): number {
    if (this.fpsHistory.length === 0) return 60;
    
    const sum = this.fpsHistory.reduce((acc, fps) => acc + fps, 0);
    return Math.round(sum / this.fpsHistory.length);
  }

  private getAverageRenderTime(): number {
    const renderMeasurements = this.measurements.get('render') || [];
    if (renderMeasurements.length === 0) return 0;
    
    const sum = renderMeasurements.reduce((acc, time) => acc + time, 0);
    return sum / renderMeasurements.length;
  }

  private getCustomMetrics(): Record<string, any> {
    const customMetrics: Record<string, any> = {};
    
    for (const [name, measurements] of this.measurements) {
      if (measurements.length > 0) {
        const sum = measurements.reduce((acc, val) => acc + val, 0);
        customMetrics[name] = {
          average: sum / measurements.length,
          min: Math.min(...measurements),
          max: Math.max(...measurements),
          count: measurements.length,
          last: measurements[measurements.length - 1],
        };
      }
    }
    
    return customMetrics;
  }

  private notifyObservers(): void {
    if (this.observers.size === 0) return;
    
    this.getMetrics().then(metrics => {
      this.observers.forEach(callback => {
        try {
          callback(metrics);
        } catch (error) {
          console.error('Error in performance observer:', error);
        }
      });
    });
  }

  private async loadHistoricalData(): Promise<void> {
    try {
      const data = await AsyncStorage.getItem('performance_history');
      if (data) {
        const history = JSON.parse(data);
        this.fpsHistory = history.fps || [];
        this.memoryUsageHistory = history.memory || [];
      }
    } catch (error) {
      console.error('Failed to load performance history:', error);
    }
  }

  private async saveHistoricalData(): Promise<void> {
    try {
      const data = {
        fps: this.fpsHistory.slice(-60), // Keep last 60 entries
        memory: this.memoryUsageHistory.slice(-60),
        timestamp: Date.now(),
      };
      await AsyncStorage.setItem('performance_history', JSON.stringify(data));
    } catch (error) {
      console.error('Failed to save performance history:', error);
    }
  }
}