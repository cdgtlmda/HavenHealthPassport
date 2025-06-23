import { 
  StorageAdapter, 
  NetworkAdapter, 
  CompressionAdapter, 
  CryptoAdapter 
} from './types';
import { PlatformDetector } from './PlatformDetector';

// Platform-specific implementations interface
export interface PlatformImplementations {
  storage: StorageAdapter;
  network: NetworkAdapter;
  compression?: CompressionAdapter;
  crypto?: CryptoAdapter;
}

// Platform bridge for unified API
export class PlatformBridge {
  private static instance: PlatformBridge;
  private implementations: PlatformImplementations;
  private detector: PlatformDetector;

  private constructor(implementations: PlatformImplementations) {
    this.implementations = implementations;
    this.detector = PlatformDetector.getInstance();
  }

  static initialize(implementations: PlatformImplementations): void {
    if (!PlatformBridge.instance) {
      PlatformBridge.instance = new PlatformBridge(implementations);
    }
  }

  static getInstance(): PlatformBridge {
    if (!PlatformBridge.instance) {
      throw new Error('PlatformBridge not initialized. Call initialize() first.');
    }
    return PlatformBridge.instance;
  }

  // Storage operations
  get storage(): StorageAdapter {
    return this.implementations.storage;
  }

  // Network operations
  get network(): NetworkAdapter {
    return this.implementations.network;
  }

  // Compression operations
  get compression(): CompressionAdapter | undefined {
    return this.implementations.compression;
  }

  // Crypto operations
  get crypto(): CryptoAdapter | undefined {
    return this.implementations.crypto;
  }

  // Platform info
  get platform(): ReturnType<PlatformDetector['platform']> {
    return this.detector.platform;
  }
  get capabilities(): ReturnType<PlatformDetector['getAllFeatures']> {
    return this.detector.getAllFeatures();
  }

  // Platform-specific file operations
  async saveFile(filename: string, data: Blob): Promise<string> {
    if (this.detector.isWeb()) {
      // Web: Use File API
      const url = URL.createObjectURL(data);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      return filename;
    } else {
      // Mobile: Store in app storage
      const base64 = await this.blobToBase64(data);
      await this.storage.set(`file_${filename}`, {
        filename,
        data: base64,
        size: data.size,
        type: data.type,
        savedAt: Date.now(),
      });
      return `file_${filename}`;
    }
  }

  async loadFile(identifier: string): Promise<Blob | null> {
    if (this.detector.isWeb()) {
      // Web: File picker would be needed
      throw new Error('File loading not implemented for web');
    } else {
      // Mobile: Load from storage
      const fileData = await this.storage.get<any>(identifier);
      if (!fileData) return null;
      
      return this.base64ToBlob(fileData.data, fileData.type);
    }
  }

  // Helper methods
  private async blobToBase64(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  private base64ToBlob(base64: string, type: string): Blob {
    const byteCharacters = atob(base64.split(',')[1]);
    const byteNumbers = new Array(byteCharacters.length);
    
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    
    const byteArray = new Uint8Array(byteNumbers);
    return new Blob([byteArray], { type });
  }

  // Platform-specific notification handling
  async requestNotificationPermission(): Promise<boolean> {
    if (this.detector.isWeb() && 'Notification' in window) {
      const permission = await Notification.requestPermission();
      return permission === 'granted';
    }
    // Mobile platforms handle this differently
    return true;
  }

  async showNotification(title: string, options?: NotificationOptions): Promise<void> {
    if (this.detector.isWeb() && 'Notification' in window) {
      if (Notification.permission === 'granted') {
        new Notification(title, options);
      }
    }
    // Mobile platforms would use their native notification APIs
  }
}

export default PlatformBridge;