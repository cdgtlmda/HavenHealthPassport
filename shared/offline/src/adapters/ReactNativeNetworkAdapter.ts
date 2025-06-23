import { NetworkAdapter } from '../types';

// React Native network adapter using NetInfo
export class ReactNativeNetworkAdapter implements NetworkAdapter {
  private NetInfo: any;

  constructor(NetInfo: any) {
    this.NetInfo = NetInfo;
  }

  async isConnected(): Promise<boolean> {
    try {
      const state = await this.NetInfo.fetch();
      return state.isConnected && state.isInternetReachable;
    } catch (error) {
      console.error('Network check error:', error);
      return false;
    }
  }

  addConnectionListener(callback: (isConnected: boolean) => void): () => void {
    const unsubscribe = this.NetInfo.addEventListener((state: any) => {
      const connected = state.isConnected && state.isInternetReachable;
      callback(connected);
    });

    // Return unsubscribe function
    return () => {
      if (typeof unsubscribe === 'function') {
        unsubscribe();
      } else if (unsubscribe && typeof unsubscribe.remove === 'function') {
        // Older versions of NetInfo
        unsubscribe.remove();
      }
    };
  }
}

export default ReactNativeNetworkAdapter;