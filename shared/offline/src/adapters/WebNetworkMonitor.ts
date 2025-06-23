import { NetworkMonitor, NetworkStatus, NetworkChangeCallback } from '../types';

export class WebNetworkMonitor implements NetworkMonitor {
  private listeners: Set<NetworkChangeCallback> = new Set();
  private currentStatus: NetworkStatus = {
    isOnline: false,
    type: 'unknown',
    effectiveType: 'unknown',
    downlink: 0,
    rtt: 0,
    saveData: false,
    details: {},
  };
  private pollingInterval: NodeJS.Timeout | null = null;
  private connection: any = null;

  async initialize(): Promise<void> {
    // Get Network Information API if available
    this.connection = (navigator as any).connection || 
                     (navigator as any).mozConnection || 
                     (navigator as any).webkitConnection;

    // Get initial status
    await this.updateStatus();

    // Listen to online/offline events
    window.addEventListener('online', this.handleOnline);
    window.addEventListener('offline', this.handleOffline);

    // Listen to connection changes if available
    if (this.connection) {
      this.connection.addEventListener('change', this.handleConnectionChange);
    }

    // Start polling for connection quality
    this.startPolling();
  }

  async checkConnectivity(): Promise<NetworkStatus> {
    await this.updateStatus();
    return this.currentStatus;
  }

  async getNetworkStatus(): Promise<NetworkStatus> {
    return this.currentStatus;
  }

  onStatusChange(callback: NetworkChangeCallback): () => void {
    this.listeners.add(callback);
    
    // Return unsubscribe function
    return () => {
      this.listeners.delete(callback);
    };
  }

  async measureLatency(url: string = 'https://www.google.com/generate_204'): Promise<number> {
    try {
      const start = performance.now();
      const response = await fetch(url, {
        method: 'HEAD',
        cache: 'no-cache',
        mode: 'no-cors',
      });
      
      return performance.now() - start;
    } catch (error) {
      console.error('Failed to measure latency:', error);
      return -1;
    }
  }

  async measureBandwidth(): Promise<number> {
    try {
      // Use a larger file for more accurate measurement
      const testUrl = 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png';
      const start = performance.now();
      
      const response = await fetch(testUrl, { cache: 'no-cache' });
      const blob = await response.blob();
      
      const duration = (performance.now() - start) / 1000; // seconds
      const size = blob.size; // bytes
      const bandwidth = (size * 8) / duration; // bits per second
      
      return bandwidth / 1000000; // Mbps
    } catch (error) {
      console.error('Failed to measure bandwidth:', error);
      return 0;
    }
  }

  async isReachable(url: string): Promise<boolean> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(url, {
        method: 'HEAD',
        cache: 'no-cache',
        mode: 'no-cors',
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      return true;
    } catch (error) {
      return false;
    }
  }

  destroy(): void {
    // Remove event listeners
    window.removeEventListener('online', this.handleOnline);
    window.removeEventListener('offline', this.handleOffline);
    
    if (this.connection) {
      this.connection.removeEventListener('change', this.handleConnectionChange);
    }
    
    // Stop polling
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
    
    this.listeners.clear();
  }

  // Private methods
  private handleOnline = async () => {
    await this.updateStatus();
  };

  private handleOffline = async () => {
    await this.updateStatus();
  };

  private handleConnectionChange = async () => {
    await this.updateStatus();
  };

  private startPolling(): void {
    // Poll every 30 seconds to check connection quality
    this.pollingInterval = setInterval(async () => {
      const latency = await this.measureLatency();
      if (latency > 0 && this.currentStatus.isOnline) {
        const previousRtt = this.currentStatus.rtt;
        this.currentStatus.rtt = latency;
        
        // If latency changed significantly, notify listeners
        if (Math.abs(previousRtt - latency) > 100) {
          this.notifyListeners({ ...this.currentStatus, rtt: previousRtt }, this.currentStatus);
        }
      }
    }, 30000);
  }
  private async updateStatus(): Promise<void> {
    const previousStatus = { ...this.currentStatus };
    
    // Basic online/offline status
    this.currentStatus.isOnline = navigator.onLine;
    
    // Network Information API data if available
    if (this.connection) {
      this.currentStatus.type = this.mapConnectionType(this.connection.type);
      this.currentStatus.effectiveType = this.mapEffectiveType(this.connection.effectiveType);
      this.currentStatus.downlink = this.connection.downlink || 0;
      this.currentStatus.rtt = this.connection.rtt || 0;
      this.currentStatus.saveData = this.connection.saveData || false;
      
      this.currentStatus.details = {
        type: this.connection.type,
        effectiveType: this.connection.effectiveType,
        downlinkMax: this.connection.downlinkMax,
      };
    } else {
      // Fallback: estimate based on online status
      if (this.currentStatus.isOnline) {
        this.currentStatus.type = 'unknown';
        this.currentStatus.effectiveType = '4g'; // Assume good connection
        this.currentStatus.downlink = 10; // Assume 10 Mbps
        this.currentStatus.rtt = 50; // Assume 50ms
      } else {
        this.currentStatus.type = 'none';
        this.currentStatus.effectiveType = 'offline';
        this.currentStatus.downlink = 0;
        this.currentStatus.rtt = 0;
      }
    }
    
    // Additional connectivity check
    if (this.currentStatus.isOnline) {
      const isActuallyOnline = await this.performConnectivityCheck();
      this.currentStatus.isOnline = isActuallyOnline;
    }
    
    // Notify listeners if status changed
    if (this.hasStatusChanged(previousStatus, this.currentStatus)) {
      this.notifyListeners(previousStatus, this.currentStatus);
    }
  }

  private mapConnectionType(type: string): NetworkStatus['type'] {
    switch (type) {
      case 'wifi':
        return 'wifi';
      case 'cellular':
        return 'cellular';
      case 'ethernet':
        return 'ethernet';
      case 'bluetooth':
        return 'bluetooth';
      case 'none':
        return 'none';
      default:
        return 'unknown';
    }
  }

  private mapEffectiveType(type: string): NetworkStatus['effectiveType'] {
    switch (type) {
      case 'slow-2g':
        return 'slow-2g';
      case '2g':
        return '2g';
      case '3g':
        return '3g';
      case '4g':
        return '4g';
      case 'offline':
        return 'offline';
      default:
        return 'unknown';
    }
  }

  private async performConnectivityCheck(): Promise<boolean> {
    try {
      // Try multiple endpoints to ensure connectivity
      const endpoints = [
        'https://www.google.com/generate_204',
        'https://connectivitycheck.gstatic.com/generate_204',
        'https://www.cloudflare.com/cdn-cgi/trace',
      ];
      
      const promises = endpoints.map(url => 
        fetch(url, {
          method: 'HEAD',
          cache: 'no-cache',
          mode: 'no-cors',
        }).then(() => true).catch(() => false)
      );
      
      const results = await Promise.race([
        Promise.any(promises),
        new Promise<boolean>(resolve => setTimeout(() => resolve(false), 5000))
      ]);
      
      return results;
    } catch (error) {
      return false;
    }
  }

  private hasStatusChanged(prev: NetworkStatus, current: NetworkStatus): boolean {
    return prev.isOnline !== current.isOnline ||
           prev.type !== current.type ||
           prev.effectiveType !== current.effectiveType ||
           Math.abs(prev.downlink - current.downlink) > 1 ||
           Math.abs(prev.rtt - current.rtt) > 50;
  }

  private notifyListeners(previousStatus: NetworkStatus, currentStatus: NetworkStatus): void {
    this.listeners.forEach(callback => {
      try {
        callback(currentStatus, previousStatus);
      } catch (error) {
        console.error('Error in network status listener:', error);
      }
    });
  }
}