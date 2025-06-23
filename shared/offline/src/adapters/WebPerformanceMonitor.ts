import { PerformanceMonitor, PerformanceMetrics, PerformanceEntry, PerformanceOptions } from '../types';

export class WebPerformanceMonitor implements PerformanceMonitor {
  private observers: Set<(metrics: PerformanceMetrics) => void> = new Set();
  private isMonitoring = false;
  private performanceObserver?: PerformanceObserver;
  private metricsInterval?: number;
  private resourceTimings: PerformanceResourceTiming[] = [];
  private navigationTimings: PerformanceNavigationTiming[] = [];
  private customMeasurements: Map<string, number[]> = new Map();
  private fpsHistory: number[] = [];
  private lastFrameTime = 0;
  private rafId?: number;

  async initialize(options?: PerformanceOptions): Promise<void> {
    // Set up Performance Observer
    if ('PerformanceObserver' in window) {
      this.performanceObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.entryType === 'resource') {
            this.resourceTimings.push(entry as PerformanceResourceTiming);
            // Keep only last 100 resource timings
            if (this.resourceTimings.length > 100) {
              this.resourceTimings.shift();
            }
          } else if (entry.entryType === 'navigation') {
            this.navigationTimings.push(entry as PerformanceNavigationTiming);
          }
        }
      });

      // Observe resource and navigation timings
      this.performanceObserver.observe({ 
        entryTypes: ['resource', 'navigation', 'measure'] 
      });
    }

    if (options?.autoStart) {
      this.startMonitoring();
    }
  }

  mark(name: string): void {
    if ('performance' in window && 'mark' in performance) {
      performance.mark(name);
    }
  }

  measure(name: string, startMark?: string, endMark?: string): PerformanceEntry | null {
    if (!('performance' in window && 'measure' in performance)) {
      return null;
    }

    try {
      // Use Performance API to create measure
      let measureEntry: PerformanceMeasure;
      
      if (startMark && endMark) {
        measureEntry = performance.measure(name, startMark, endMark);
      } else if (startMark) {
        measureEntry = performance.measure(name, startMark);
      } else {
        measureEntry = performance.measure(name);
      }

      // Store in custom measurements
      const measurements = this.customMeasurements.get(name) || [];
      measurements.push(measureEntry.duration);
      if (measurements.length > 100) {
        measurements.shift();
      }
      this.customMeasurements.set(name, measurements);

      const entry: PerformanceEntry = {
        name,
        entryType: 'measure',
        startTime: measureEntry.startTime,
        duration: measureEntry.duration,
        timestamp: Date.now(),
      };

      this.notifyObservers();
      return entry;
    } catch (error) {
      console.error('Failed to create performance measure:', error);
      return null;
    }
  }
  async getMetrics(): Promise<PerformanceMetrics> {
    const memoryInfo = this.getMemoryInfo();
    const connectionInfo = this.getConnectionInfo();
    const deviceInfo = this.getDeviceInfo();

    return {
      cpu: {
        usage: await this.estimateCPUUsage(),
        cores: navigator.hardwareConcurrency || 1,
      },
      memory: memoryInfo,
      storage: await this.getStorageInfo(),
      battery: await this.getBatteryInfo(),
      network: {
        latency: this.calculateAverageLatency(),
        bandwidth: this.calculateBandwidth(),
        type: connectionInfo.type,
        effectiveType: connectionInfo.effectiveType,
        downlink: connectionInfo.downlink,
        rtt: connectionInfo.rtt,
      },
      fps: this.calculateAverageFPS(),
      jsHeapSize: memoryInfo.jsHeapSize || 0,
      renderTime: this.getAverageRenderTime(),
      customMetrics: this.getCustomMetrics(),
      pageLoadTime: this.getPageLoadTime(),
      resourceTimings: this.getResourceTimingSummary(),
    };
  }

  startMonitoring(): void {
    if (this.isMonitoring) return;
    
    this.isMonitoring = true;
    
    // Start FPS monitoring
    this.startFPSMonitoring();
    
    // Start periodic metrics collection
    this.metricsInterval = window.setInterval(() => {
      this.notifyObservers();
    }, 5000); // Every 5 seconds
  }

  stopMonitoring(): void {
    this.isMonitoring = false;
    
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
      this.rafId = undefined;
    }
    
    if (this.metricsInterval) {
      clearInterval(this.metricsInterval);
      this.metricsInterval = undefined;
    }
  }

  clearMetrics(): void {
    this.resourceTimings = [];
    this.navigationTimings = [];
    this.customMeasurements.clear();
    this.fpsHistory = [];
    
    // Clear Performance API entries
    if ('performance' in window && 'clearMarks' in performance) {
      performance.clearMarks();
      performance.clearMeasures();
    }
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
      userAgent: navigator.userAgent,
      url: window.location.href,
      metrics,
      customMeasurements: Object.fromEntries(this.customMeasurements),
      resourceTimings: this.resourceTimings.map(timing => ({
        name: timing.name,
        duration: timing.duration,
        transferSize: timing.transferSize,
        encodedBodySize: timing.encodedBodySize,
        decodedBodySize: timing.decodedBodySize,
        initiatorType: timing.initiatorType,
      })),
      navigationTiming: this.navigationTimings[0] ? {
        domContentLoadedEventEnd: this.navigationTimings[0].domContentLoadedEventEnd,
        loadEventEnd: this.navigationTimings[0].loadEventEnd,
        responseEnd: this.navigationTimings[0].responseEnd,
      } : null,
    };

    return JSON.stringify(data, null, 2);
  }

  destroy(): void {
    this.stopMonitoring();
    
    if (this.performanceObserver) {
      this.performanceObserver.disconnect();
    }
    
    this.observers.clear();
    this.clearMetrics();
  }
  // Private methods
  private startFPSMonitoring(): void {
    const measureFPS = (timestamp: number) => {
      if (!this.isMonitoring) return;

      if (this.lastFrameTime) {
        const delta = timestamp - this.lastFrameTime;
        const fps = 1000 / delta;
        
        this.fpsHistory.push(fps);
        if (this.fpsHistory.length > 60) {
          this.fpsHistory.shift();
        }
      }

      this.lastFrameTime = timestamp;
      this.rafId = requestAnimationFrame(measureFPS);
    };
    
    this.rafId = requestAnimationFrame(measureFPS);
  }

  private getMemoryInfo(): any {
    const memory = (performance as any).memory;
    
    if (memory) {
      return {
        used: memory.usedJSHeapSize,
        total: memory.totalJSHeapSize,
        available: memory.totalJSHeapSize - memory.usedJSHeapSize,
        jsHeapSize: memory.usedJSHeapSize,
        limit: memory.jsHeapSizeLimit,
      };
    }
    
    // Fallback if memory API not available
    return {
      used: 0,
      total: 0,
      available: 0,
      jsHeapSize: 0,
      limit: 0,
    };
  }

  private async getStorageInfo(): Promise<any> {
    if ('storage' in navigator && 'estimate' in navigator.storage) {
      try {
        const estimate = await navigator.storage.estimate();
        return {
          used: estimate.usage || 0,
          total: estimate.quota || 0,
          available: (estimate.quota || 0) - (estimate.usage || 0),
        };
      } catch (error) {
        console.error('Failed to get storage estimate:', error);
      }
    }
    
    return {
      used: 0,
      total: 0,
      available: 0,
    };
  }

  private async getBatteryInfo(): Promise<any> {
    if ('getBattery' in navigator) {
      try {
        const battery = await (navigator as any).getBattery();
        return {
          level: battery.level,
          charging: battery.charging,
          chargingTime: battery.chargingTime,
          dischargingTime: battery.dischargingTime,
        };
      } catch (error) {
        console.error('Failed to get battery info:', error);
      }
    }
    
    return {
      level: 1,
      charging: false,
    };
  }

  private getConnectionInfo(): any {
    const connection = (navigator as any).connection || 
                      (navigator as any).mozConnection || 
                      (navigator as any).webkitConnection;
    
    if (connection) {
      return {
        type: connection.type || 'unknown',
        effectiveType: connection.effectiveType || 'unknown',
        downlink: connection.downlink || 0,
        rtt: connection.rtt || 0,
        saveData: connection.saveData || false,
      };
    }
    
    return {
      type: 'unknown',
      effectiveType: 'unknown',
      downlink: 0,
      rtt: 0,
      saveData: false,
    };
  }
  private getDeviceInfo(): any {
    return {
      userAgent: navigator.userAgent,
      platform: navigator.platform,
      language: navigator.language,
      languages: navigator.languages,
      hardwareConcurrency: navigator.hardwareConcurrency,
      deviceMemory: (navigator as any).deviceMemory,
      screenResolution: {
        width: window.screen.width,
        height: window.screen.height,
        pixelRatio: window.devicePixelRatio,
      },
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
      },
    };
  }

  private async estimateCPUUsage(): Promise<number> {
    // Rough estimation based on main thread blocking
    return new Promise((resolve) => {
      const start = performance.now();
      const iterations = 1000000;
      
      // Perform CPU-intensive task
      let sum = 0;
      for (let i = 0; i < iterations; i++) {
        sum += Math.sqrt(i);
      }
      
      const duration = performance.now() - start;
      // Estimate CPU usage based on time taken (rough approximation)
      const usage = Math.min(100, (duration / 10) * 100);
      resolve(usage);
    });
  }

  private calculateAverageFPS(): number {
    if (this.fpsHistory.length === 0) return 60;
    
    const sum = this.fpsHistory.reduce((acc, fps) => acc + fps, 0);
    return Math.round(sum / this.fpsHistory.length);
  }

  private calculateAverageLatency(): number {
    const resourceTimings = this.resourceTimings.slice(-20); // Last 20 resources
    if (resourceTimings.length === 0) return 0;
    
    const latencies = resourceTimings
      .filter(timing => timing.responseStart > 0)
      .map(timing => timing.responseStart - timing.fetchStart);
    
    if (latencies.length === 0) return 0;
    
    const sum = latencies.reduce((acc, latency) => acc + latency, 0);
    return Math.round(sum / latencies.length);
  }

  private calculateBandwidth(): number {
    const resourceTimings = this.resourceTimings.slice(-10); // Last 10 resources
    const downloads = resourceTimings.filter(timing => 
      timing.transferSize > 0 && timing.duration > 0
    );
    
    if (downloads.length === 0) return 0;
    
    const bandwidths = downloads.map(timing => 
      (timing.transferSize * 8) / (timing.duration / 1000) / 1000000 // Mbps
    );
    
    const sum = bandwidths.reduce((acc, bw) => acc + bw, 0);
    return Math.round((sum / bandwidths.length) * 100) / 100;
  }

  private getAverageRenderTime(): number {
    const renderMeasurements = this.customMeasurements.get('render') || [];
    if (renderMeasurements.length === 0) return 0;
    
    const sum = renderMeasurements.reduce((acc, time) => acc + time, 0);
    return Math.round(sum / renderMeasurements.length);
  }

  private getPageLoadTime(): number {
    if (this.navigationTimings.length === 0) return 0;
    
    const navTiming = this.navigationTimings[0];
    return Math.round(navTiming.loadEventEnd - navTiming.fetchStart);
  }

  private getResourceTimingSummary(): any {
    const summary = {
      count: this.resourceTimings.length,
      totalSize: 0,
      totalDuration: 0,
      byType: {} as Record<string, number>,
    };
    
    this.resourceTimings.forEach(timing => {
      summary.totalSize += timing.transferSize || 0;
      summary.totalDuration += timing.duration || 0;
      
      const type = timing.initiatorType || 'other';
      summary.byType[type] = (summary.byType[type] || 0) + 1;
    });
    
    return summary;
  }

  private getCustomMetrics(): Record<string, any> {
    const customMetrics: Record<string, any> = {};
    
    for (const [name, measurements] of this.customMeasurements) {
      if (measurements.length > 0) {
        const sum = measurements.reduce((acc, val) => acc + val, 0);
        const sorted = [...measurements].sort((a, b) => a - b);
        
        customMetrics[name] = {
          average: sum / measurements.length,
          min: sorted[0],
          max: sorted[sorted.length - 1],
          median: sorted[Math.floor(sorted.length / 2)],
          p95: sorted[Math.floor(sorted.length * 0.95)],
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
}