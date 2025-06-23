import NetInfo, { NetInfoState, NetInfoSubscription } from '@react-native-community/netinfo';
import { NetworkMonitor, NetworkStatus, NetworkChangeCallback } from '../types';

export class ReactNativeNetworkMonitor implements NetworkMonitor {
  private subscription: NetInfoSubscription | null = null;
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

  async initialize(): Promise<void> {
    // Configure NetInfo
    NetInfo.configure({
      reachabilityUrl: 'https://clients3.google.com/generate_204',
      reachabilityTest: async (response) => response.status === 204,
      reachabilityLongTimeout: 60 * 1000, // 60s
      reachabilityShortTimeout: 5 * 1000, // 5s
      reachabilityRequestTimeout: 15 * 1000, // 15s
      reachabilityShouldRun: () => true,
      shouldFetchWiFiSSID: true,
    });

    // Get initial status
    const state = await NetInfo.fetch();
    this.updateStatus(state);

    // Subscribe to network changes
    this.subscription = NetInfo.addEventListener(state => {
      this.updateStatus(state);
    });
  }

  async checkConnectivity(): Promise<NetworkStatus> {
    const state = await NetInfo.fetch();
    this.updateStatus(state);
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

  async measureLatency(url: string): Promise<number> {
    try {
      const start = Date.now();
      const response = await fetch(url, {
        method: 'HEAD',
        cache: 'no-cache',
      });
      
      if (!response.ok) {
        throw new Error('Network request failed');
      }
      
      return Date.now() - start;
    } catch (error) {
      console.error('Failed to measure latency:', error);
      return -1;
    }
  }

  async measureBandwidth(): Promise<number> {
    try {
      // Download a known file size to measure bandwidth
      const testUrl = 'https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png';
      const start = Date.now();
      
      const response = await fetch(testUrl);
      const blob = await response.blob();
      
      const duration = (Date.now() - start) / 1000; // seconds
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
      const response = await fetch(url, {
        method: 'HEAD',
        cache: 'no-cache',
        mode: 'no-cors',
      });
      
      return true; // If no error thrown, assume reachable
    } catch (error) {
      return false;
    }
  }

  destroy(): void {
    if (this.subscription) {
      this.subscription();
      this.subscription = null;
    }
    this.listeners.clear();
  }

  // Private methods
  private updateStatus(state: NetInfoState): void {
    const previousStatus = { ...this.currentStatus };
    
    this.currentStatus = {
      isOnline: state.isConnected && state.isInternetReachable !== false,
      type: this.mapConnectionType(state.type),
      effectiveType: this.mapEffectiveType(state),
      downlink: this.estimateDownlink(state),
      rtt: this.estimateRTT(state),
      saveData: false, // React Native doesn't provide this
      details: {
        isConnected: state.isConnected,
        isInternetReachable: state.isInternetReachable,
        type: state.type,
        isWifiEnabled: state.isWifiEnabled,
        details: state.details,
      },
    };

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
  private mapEffectiveType(state: NetInfoState): NetworkStatus['effectiveType'] {
    if (!state.isConnected) return 'offline';
    
    // For cellular connections, try to determine effective type
    if (state.type === 'cellular' && state.details) {
      const cellularGeneration = (state.details as any).cellularGeneration;
      switch (cellularGeneration) {
        case '2g':
          return 'slow-2g';
        case '3g':
          return '3g';
        case '4g':
          return '4g';
        case '5g':
          return '4g'; // Treat 5G as 4G for now
      }
    }

    // For WiFi, assume 4G-like speeds
    if (state.type === 'wifi') {
      return '4g';
    }

    return 'unknown';
  }

  private estimateDownlink(state: NetInfoState): number {
    if (!state.isConnected) return 0;
    
    // Estimate based on connection type
    switch (state.type) {
      case 'wifi':
        return 10; // 10 Mbps typical WiFi
      case 'cellular':
        if (state.details) {
          const cellularGeneration = (state.details as any).cellularGeneration;
          switch (cellularGeneration) {
            case '2g':
              return 0.1; // 100 Kbps
            case '3g':
              return 1; // 1 Mbps
            case '4g':
              return 10; // 10 Mbps
            case '5g':
              return 50; // 50 Mbps
          }
        }
        return 1; // Default cellular
      case 'ethernet':
        return 100; // 100 Mbps typical ethernet
      default:
        return 0;
    }
  }

  private estimateRTT(state: NetInfoState): number {
    if (!state.isConnected) return 0;
    
    // Estimate based on connection type
    switch (state.type) {
      case 'wifi':
        return 50; // 50ms typical WiFi
      case 'cellular':
        if (state.details) {
          const cellularGeneration = (state.details as any).cellularGeneration;
          switch (cellularGeneration) {
            case '2g':
              return 300; // 300ms
            case '3g':
              return 100; // 100ms
            case '4g':
              return 50; // 50ms
            case '5g':
              return 20; // 20ms
          }
        }
        return 100; // Default cellular
      case 'ethernet':
        return 10; // 10ms typical ethernet
      default:
        return 0;
    }
  }

  private hasStatusChanged(prev: NetworkStatus, current: NetworkStatus): boolean {
    return prev.isOnline !== current.isOnline ||
           prev.type !== current.type ||
           prev.effectiveType !== current.effectiveType;
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