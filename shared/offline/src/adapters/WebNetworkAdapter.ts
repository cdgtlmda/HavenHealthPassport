import { NetworkAdapter } from '../types';

export class WebNetworkAdapter implements NetworkAdapter {
  async isConnected(): Promise<boolean> {
    // Check navigator.onLine first
    if (!navigator.onLine) {
      return false;
    }

    // Try to ping a reliable endpoint to verify actual connectivity
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      const response = await fetch('/api/health', {
        method: 'HEAD',
        signal: controller.signal,
        cache: 'no-cache',
      });

      clearTimeout(timeoutId);
      return response.ok;
    } catch (error) {
      // If health check fails, try a simpler check
      try {
        await fetch('https://www.google.com/favicon.ico', {
          mode: 'no-cors',
          cache: 'no-cache',
        });
        return true;
      } catch {
        return false;
      }
    }
  }

  addConnectionListener(callback: (isConnected: boolean) => void): () => void {
    const handleOnline = () => {
      // Verify actual connectivity
      this.isConnected().then(callback);
    };

    const handleOffline = () => {
      callback(false);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Return unsubscribe function
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }
}

export default WebNetworkAdapter;