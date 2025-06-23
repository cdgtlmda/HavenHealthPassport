// Platform detection and feature capabilities
export class PlatformDetector {
  private static _instance: PlatformDetector;
  private _platform: 'web' | 'ios' | 'android' | 'unknown' = 'unknown';
  private _features: Map<string, boolean> = new Map();

  private constructor() {
    this.detectPlatform();
    this.detectFeatures();
  }

  static getInstance(): PlatformDetector {
    if (!PlatformDetector._instance) {
      PlatformDetector._instance = new PlatformDetector();
    }
    return PlatformDetector._instance;
  }

  private detectPlatform(): void {
    // Check if running in React Native
    if (typeof global !== 'undefined' && global.__DEV__ !== undefined) {
      // React Native environment
      const userAgent = (global as any).navigator?.userAgent || '';
      
      if (userAgent.includes('iPhone') || userAgent.includes('iPad')) {
        this._platform = 'ios';
      } else if (userAgent.includes('Android')) {
        this._platform = 'android';
      }
    } else if (typeof window !== 'undefined') {
      // Web environment
      this._platform = 'web';
    }
  }

  private detectFeatures(): void {
    // Storage features
    this._features.set('localStorage', this.hasLocalStorage());
    this._features.set('sessionStorage', this.hasSessionStorage());
    this._features.set('indexedDB', this.hasIndexedDB());
    this._features.set('webSQL', this.hasWebSQL());
    
    // Network features
    this._features.set('serviceWorker', this.hasServiceWorker());
    this._features.set('backgroundSync', this.hasBackgroundSync());
    this._features.set('pushNotifications', this.hasPushNotifications());
    
    // File features
    this._features.set('fileAPI', this.hasFileAPI());
    this._features.set('fileSystem', this.hasFileSystem());
    
    // Other features
    this._features.set('webWorker', this.hasWebWorker());
    this._features.set('crypto', this.hasCrypto());
    this._features.set('geolocation', this.hasGeolocation());
    this._features.set('camera', this.hasCamera());
  }
  // Feature detection methods
  private hasLocalStorage(): boolean {
    try {
      return typeof window !== 'undefined' && 
             'localStorage' in window && 
             window.localStorage !== null;
    } catch {
      return false;
    }
  }

  private hasSessionStorage(): boolean {
    try {
      return typeof window !== 'undefined' && 
             'sessionStorage' in window && 
             window.sessionStorage !== null;
    } catch {
      return false;
    }
  }

  private hasIndexedDB(): boolean {
    try {
      return typeof window !== 'undefined' && 
             ('indexedDB' in window || 
              'webkitIndexedDB' in window || 
              'mozIndexedDB' in window);
    } catch {
      return false;
    }
  }

  private hasWebSQL(): boolean {
    try {
      return typeof window !== 'undefined' && 
             'openDatabase' in window;
    } catch {
      return false;
    }
  }

  private hasServiceWorker(): boolean {
    return typeof window !== 'undefined' && 
           'serviceWorker' in navigator;
  }

  private hasBackgroundSync(): boolean {
    return typeof window !== 'undefined' && 
           'serviceWorker' in navigator && 
           'SyncManager' in window;
  }

  private hasPushNotifications(): boolean {
    return typeof window !== 'undefined' && 
           'Notification' in window && 
           'serviceWorker' in navigator && 
           'PushManager' in window;
  }
  private hasFileAPI(): boolean {
    return typeof window !== 'undefined' && 
           'File' in window && 
           'FileReader' in window && 
           'FileList' in window && 
           'Blob' in window;
  }

  private hasFileSystem(): boolean {
    return typeof window !== 'undefined' && 
           ('requestFileSystem' in window || 
            'webkitRequestFileSystem' in window);
  }

  private hasWebWorker(): boolean {
    return typeof window !== 'undefined' && 
           'Worker' in window;
  }

  private hasCrypto(): boolean {
    return typeof window !== 'undefined' && 
           'crypto' in window && 
           'subtle' in window.crypto;
  }

  private hasGeolocation(): boolean {
    return typeof navigator !== 'undefined' && 
           'geolocation' in navigator;
  }

  private hasCamera(): boolean {
    return typeof navigator !== 'undefined' && 
           'mediaDevices' in navigator && 
           'getUserMedia' in navigator.mediaDevices;
  }

  // Public API
  get platform(): 'web' | 'ios' | 'android' | 'unknown' {
    return this._platform;
  }

  hasFeature(feature: string): boolean {
    return this._features.get(feature) || false;
  }

  getAllFeatures(): { [feature: string]: boolean } {
    const features: { [feature: string]: boolean } = {};
    this._features.forEach((value, key) => {
      features[key] = value;
    });
    return features;
  }

  isWeb(): boolean {
    return this._platform === 'web';
  }

  isMobile(): boolean {
    return this._platform === 'ios' || this._platform === 'android';
  }

  isIOS(): boolean {
    return this._platform === 'ios';
  }

  isAndroid(): boolean {
    return this._platform === 'android';
  }

  getStorageCapabilities(): {
    hasLocalStorage: boolean;
    hasSessionStorage: boolean;
    hasIndexedDB: boolean;
    hasWebSQL: boolean;
  } {
    return {
      hasLocalStorage: this._features.get('localStorage') || false,
      hasSessionStorage: this._features.get('sessionStorage') || false,
      hasIndexedDB: this._features.get('indexedDB') || false,
      hasWebSQL: this._features.get('webSQL') || false,
    };
  }

  getOfflineCapabilities(): {
    hasServiceWorker: boolean;
    hasBackgroundSync: boolean;
    hasPushNotifications: boolean;
  } {
    return {
      hasServiceWorker: this._features.get('serviceWorker') || false,
      hasBackgroundSync: this._features.get('backgroundSync') || false,
      hasPushNotifications: this._features.get('pushNotifications') || false,
    };
  }
}

export default PlatformDetector;