import { openDB, DBSchema, IDBPDatabase } from 'idb';
import { StorageAdapter, StorageItem, StorageMetadata, StorageOptions } from '../types';
import { CompressionUtils } from '../CompressionUtils';
import { ValidationUtils } from '../ValidationUtils';

interface HavenDBSchema extends DBSchema {
  storage: {
    key: string;
    value: StorageItem;
    indexes: { 'by-timestamp': number };
  };
  metadata: {
    key: string;
    value: StorageMetadata;
  };
}

export class WebStorageAdapter implements StorageAdapter {
  private db?: IDBPDatabase<HavenDBSchema>;
  private readonly dbName: string;
  private readonly storeName = 'storage';
  private readonly metadataStore = 'metadata';
  private readonly compressionUtil: CompressionUtils;
  private readonly validationUtil: ValidationUtils;
  private encryptionKey?: string;
  private useLocalStorage = false;

  constructor(options: StorageOptions = {}) {
    this.dbName = options.prefix || 'haven_offline_db';
    this.compressionUtil = new CompressionUtils();
    this.validationUtil = new ValidationUtils();
    this.encryptionKey = options.encryptionKey;
    
    // Check if IndexedDB is available
    if (typeof indexedDB === 'undefined') {
      console.warn('IndexedDB not available, falling back to localStorage');
      this.useLocalStorage = true;
    }
  }

  async initialize(): Promise<void> {
    if (this.useLocalStorage) {
      // Initialize localStorage metadata
      const metadata = this.getLocalStorageMetadata();
      if (!metadata) {
        this.setLocalStorageMetadata({
          version: '1.0.0',
          createdAt: Date.now(),
          lastUpdated: Date.now(),
          itemCount: 0,
          totalSize: 0,
        });
      }
      return;
    }

    // Initialize IndexedDB
    this.db = await openDB<HavenDBSchema>(this.dbName, 1, {
      upgrade(db) {
        // Create storage object store
        if (!db.objectStoreNames.contains('storage')) {
          const store = db.createObjectStore('storage', { keyPath: 'key' });
          store.createIndex('by-timestamp', 'timestamp');
        }

        // Create metadata object store
        if (!db.objectStoreNames.contains('metadata')) {
          db.createObjectStore('metadata', { keyPath: 'key' });
        }
      },
    });

    // Initialize metadata
    const metadata = await this.getMetadata();
    if (!metadata) {
      await this.setMetadata({
        version: '1.0.0',
        createdAt: Date.now(),
        lastUpdated: Date.now(),
        itemCount: 0,
        totalSize: 0,
      });
    }
  }

  async setItem(key: string, value: any, options?: StorageOptions): Promise<void> {
    try {
      let serializedValue = JSON.stringify(value);

      // Compress if needed
      if (options?.compress || (options?.compress === undefined && serializedValue.length > 1024)) {
        serializedValue = await this.compressionUtil.compress(serializedValue);
      }

      // Encrypt if encryption key is provided
      if (this.encryptionKey) {
        serializedValue = await this.encrypt(serializedValue);
      }

      const storageItem: StorageItem = {
        key,
        value: serializedValue,
        timestamp: Date.now(),
        compressed: options?.compress || false,
        encrypted: !!this.encryptionKey,
        metadata: options?.metadata,
      };

      if (this.useLocalStorage) {
        localStorage.setItem(this.getLocalStorageKey(key), JSON.stringify(storageItem));
        await this.updateLocalStorageMetadata(key, serializedValue.length);
      } else {
        if (!this.db) throw new Error('Database not initialized');
        
        await this.db.put(this.storeName, storageItem);
        await this.updateMetadata(key, serializedValue.length);
      }
    } catch (error) {
      console.error('WebStorageAdapter: Failed to set item', error);
      
      // Handle quota exceeded error
      if (error instanceof DOMException && error.name === 'QuotaExceededError') {
        throw new Error('Storage quota exceeded');
      }
      throw error;
    }
  }

  async getItem(key: string): Promise<any | null> {
    try {
      let storageItem: StorageItem | null = null;

      if (this.useLocalStorage) {
        const itemStr = localStorage.getItem(this.getLocalStorageKey(key));
        if (itemStr) {
          storageItem = JSON.parse(itemStr);
        }
      } else {
        if (!this.db) throw new Error('Database not initialized');
        storageItem = await this.db.get(this.storeName, key) || null;
      }

      if (!storageItem) {
        return null;
      }

      let value = storageItem.value;

      // Decrypt if encrypted
      if (storageItem.encrypted && this.encryptionKey) {
        value = await this.decrypt(value);
      }

      // Decompress if compressed
      if (storageItem.compressed) {
        value = await this.compressionUtil.decompress(value);
      }

      return JSON.parse(value);
    } catch (error) {
      console.error('WebStorageAdapter: Failed to get item', error);
      return null;
    }
  }
  async removeItem(key: string): Promise<void> {
    try {
      if (this.useLocalStorage) {
        const item = localStorage.getItem(this.getLocalStorageKey(key));
        if (item) {
          localStorage.removeItem(this.getLocalStorageKey(key));
          const storageItem: StorageItem = JSON.parse(item);
          await this.updateLocalStorageMetadata(key, storageItem.value.length, true);
        }
      } else {
        if (!this.db) throw new Error('Database not initialized');
        
        const item = await this.db.get(this.storeName, key);
        if (item) {
          await this.db.delete(this.storeName, key);
          await this.updateMetadata(key, item.value.length, true);
        }
      }
    } catch (error) {
      console.error('WebStorageAdapter: Failed to remove item', error);
      throw error;
    }
  }

  async clear(): Promise<void> {
    try {
      if (this.useLocalStorage) {
        const keys = Object.keys(localStorage).filter(key => 
          key.startsWith(this.getLocalStoragePrefix())
        );
        keys.forEach(key => localStorage.removeItem(key));
        
        this.setLocalStorageMetadata({
          version: '1.0.0',
          createdAt: Date.now(),
          lastUpdated: Date.now(),
          itemCount: 0,
          totalSize: 0,
        });
      } else {
        if (!this.db) throw new Error('Database not initialized');
        
        await this.db.clear(this.storeName);
        await this.setMetadata({
          version: '1.0.0',
          createdAt: Date.now(),
          lastUpdated: Date.now(),
          itemCount: 0,
          totalSize: 0,
        });
      }
    } catch (error) {
      console.error('WebStorageAdapter: Failed to clear storage', error);
      throw error;
    }
  }
  async getAllKeys(): Promise<string[]> {
    try {
      if (this.useLocalStorage) {
        return Object.keys(localStorage)
          .filter(key => key.startsWith(this.getLocalStoragePrefix()))
          .map(key => key.replace(this.getLocalStoragePrefix(), ''));
      } else {
        if (!this.db) throw new Error('Database not initialized');
        
        const keys = await this.db.getAllKeys(this.storeName);
        return keys;
      }
    } catch (error) {
      console.error('WebStorageAdapter: Failed to get all keys', error);
      return [];
    }
  }

  async getMultiple(keys: string[]): Promise<Map<string, any>> {
    try {
      const result = new Map<string, any>();

      if (this.useLocalStorage) {
        for (const key of keys) {
          const value = await this.getItem(key);
          if (value !== null) {
            result.set(key, value);
          }
        }
      } else {
        if (!this.db) throw new Error('Database not initialized');
        
        const tx = this.db.transaction(this.storeName, 'readonly');
        const promises = keys.map(async (key) => {
          const value = await this.getItem(key);
          if (value !== null) {
            result.set(key, value);
          }
        });
        
        await Promise.all(promises);
      }

      return result;
    } catch (error) {
      console.error('WebStorageAdapter: Failed to get multiple items', error);
      return new Map();
    }
  }
  async setMultiple(items: Map<string, any>, options?: StorageOptions): Promise<void> {
    try {
      if (this.useLocalStorage) {
        for (const [key, value] of items) {
          await this.setItem(key, value, options);
        }
      } else {
        if (!this.db) throw new Error('Database not initialized');
        
        const tx = this.db.transaction(this.storeName, 'readwrite');
        const store = tx.objectStore(this.storeName);
        
        for (const [key, value] of items) {
          let serializedValue = JSON.stringify(value);

          if (options?.compress || serializedValue.length > 1024) {
            serializedValue = await this.compressionUtil.compress(serializedValue);
          }

          if (this.encryptionKey) {
            serializedValue = await this.encrypt(serializedValue);
          }

          const storageItem: StorageItem = {
            key,
            value: serializedValue,
            timestamp: Date.now(),
            compressed: options?.compress || false,
            encrypted: !!this.encryptionKey,
            metadata: options?.metadata,
          };

          await store.put(storageItem);
        }
        
        await tx.done;
        
        // Update metadata
        for (const [key, value] of items) {
          const serializedValue = JSON.stringify(value);
          await this.updateMetadata(key, serializedValue.length);
        }
      }
    } catch (error) {
      console.error('WebStorageAdapter: Failed to set multiple items', error);
      throw error;
    }
  }
  async getSize(): Promise<number> {
    try {
      if (this.useLocalStorage) {
        const metadata = this.getLocalStorageMetadata();
        return metadata?.totalSize || 0;
      } else {
        const metadata = await this.getMetadata();
        return metadata?.totalSize || 0;
      }
    } catch (error) {
      console.error('WebStorageAdapter: Failed to get size', error);
      return 0;
    }
  }

  async getQuota(): Promise<number> {
    try {
      if ('storage' in navigator && 'estimate' in navigator.storage) {
        const estimate = await navigator.storage.estimate();
        return estimate.quota || Number.MAX_SAFE_INTEGER;
      }
      
      // Fallback for browsers that don't support storage.estimate()
      // localStorage typically has 5-10MB limit
      // IndexedDB can have much more
      return this.useLocalStorage ? 10 * 1024 * 1024 : 1024 * 1024 * 1024; // 10MB : 1GB
    } catch (error) {
      console.error('WebStorageAdapter: Failed to get quota', error);
      return Number.MAX_SAFE_INTEGER;
    }
  }

  async persist(): Promise<boolean> {
    try {
      if ('storage' in navigator && 'persist' in navigator.storage) {
        const isPersisted = await navigator.storage.persisted();
        if (!isPersisted) {
          return await navigator.storage.persist();
        }
        return true;
      }
      
      // Persistence not supported
      return false;
    } catch (error) {
      console.error('WebStorageAdapter: Failed to persist storage', error);
      return false;
    }
  }
  // Helper methods
  private getLocalStoragePrefix(): string {
    return `${this.dbName}_`;
  }

  private getLocalStorageKey(key: string): string {
    return `${this.getLocalStoragePrefix()}${key}`;
  }

  private getLocalStorageMetadata(): StorageMetadata | null {
    try {
      const metadataStr = localStorage.getItem(`${this.getLocalStoragePrefix()}_metadata`);
      return metadataStr ? JSON.parse(metadataStr) : null;
    } catch (error) {
      console.error('WebStorageAdapter: Failed to get localStorage metadata', error);
      return null;
    }
  }

  private setLocalStorageMetadata(metadata: StorageMetadata): void {
    try {
      localStorage.setItem(`${this.getLocalStoragePrefix()}_metadata`, JSON.stringify(metadata));
    } catch (error) {
      console.error('WebStorageAdapter: Failed to set localStorage metadata', error);
    }
  }

  private async updateLocalStorageMetadata(key: string, size: number, isRemoval = false): Promise<void> {
    try {
      const metadata = this.getLocalStorageMetadata();
      if (!metadata) return;

      if (isRemoval) {
        metadata.itemCount = Math.max(0, metadata.itemCount - 1);
        metadata.totalSize = Math.max(0, metadata.totalSize - size);
      } else {
        const existingItem = localStorage.getItem(this.getLocalStorageKey(key));
        if (!existingItem) {
          metadata.itemCount++;
        } else {
          const oldSize = JSON.parse(existingItem).value.length;
          metadata.totalSize = Math.max(0, metadata.totalSize - oldSize);
        }
        metadata.totalSize += size;
      }

      metadata.lastUpdated = Date.now();
      this.setLocalStorageMetadata(metadata);
    } catch (error) {
      console.error('WebStorageAdapter: Failed to update localStorage metadata', error);
    }
  }
  private async getMetadata(): Promise<StorageMetadata | null> {
    if (!this.db) return null;
    try {
      return await this.db.get(this.metadataStore, 'metadata') || null;
    } catch (error) {
      console.error('WebStorageAdapter: Failed to get metadata', error);
      return null;
    }
  }

  private async setMetadata(metadata: StorageMetadata): Promise<void> {
    if (!this.db) return;
    try {
      await this.db.put(this.metadataStore, { key: 'metadata', ...metadata });
    } catch (error) {
      console.error('WebStorageAdapter: Failed to set metadata', error);
    }
  }

  private async updateMetadata(key: string, size: number, isRemoval = false): Promise<void> {
    if (!this.db) return;
    try {
      const metadata = await this.getMetadata();
      if (!metadata) return;

      if (isRemoval) {
        metadata.itemCount = Math.max(0, metadata.itemCount - 1);
        metadata.totalSize = Math.max(0, metadata.totalSize - size);
      } else {
        const existingItem = await this.db.get(this.storeName, key);
        if (!existingItem) {
          metadata.itemCount++;
        } else {
          const oldSize = existingItem.value.length;
          metadata.totalSize = Math.max(0, metadata.totalSize - oldSize);
        }
        metadata.totalSize += size;
      }

      metadata.lastUpdated = Date.now();
      await this.setMetadata(metadata);
    } catch (error) {
      console.error('WebStorageAdapter: Failed to update metadata', error);
    }
  }

  // Encryption methods (using Web Crypto API)
  private async encrypt(data: string): Promise<string> {
    if (!this.encryptionKey || typeof crypto === 'undefined') return data;
    
    try {
      const encoder = new TextEncoder();
      const dataBuffer = encoder.encode(data);
      
      // Generate key from password
      const keyMaterial = await crypto.subtle.importKey(
        'raw',
        encoder.encode(this.encryptionKey),
        'PBKDF2',
        false,
        ['deriveBits', 'deriveKey']
      );
      
      const key = await crypto.subtle.deriveKey(
        {
          name: 'PBKDF2',
          salt: encoder.encode('haven-health-salt'),
          iterations: 100000,
          hash: 'SHA-256',
        },
        keyMaterial,
        { name: 'AES-GCM', length: 256 },
        false,
        ['encrypt', 'decrypt']
      );
      
      const iv = crypto.getRandomValues(new Uint8Array(12));
      const encryptedData = await crypto.subtle.encrypt(
        { name: 'AES-GCM', iv },
        key,
        dataBuffer
      );
      
      // Combine IV and encrypted data
      const combined = new Uint8Array(iv.length + encryptedData.byteLength);
      combined.set(iv);
      combined.set(new Uint8Array(encryptedData), iv.length);
      
      return btoa(String.fromCharCode(...combined));
    } catch (error) {
      console.error('WebStorageAdapter: Encryption failed', error);
      return data;
    }
  }

  private async decrypt(data: string): Promise<string> {
    if (!this.encryptionKey || typeof crypto === 'undefined') return data;
    
    try {
      const encoder = new TextEncoder();
      const decoder = new TextDecoder();
      
      // Decode base64
      const combined = new Uint8Array(
        atob(data).split('').map(char => char.charCodeAt(0))
      );
      
      // Extract IV and encrypted data
      const iv = combined.slice(0, 12);
      const encryptedData = combined.slice(12);
      
      // Generate key from password
      const keyMaterial = await crypto.subtle.importKey(
        'raw',
        encoder.encode(this.encryptionKey),
        'PBKDF2',
        false,
        ['deriveBits', 'deriveKey']
      );
      
      const key = await crypto.subtle.deriveKey(
        {
          name: 'PBKDF2',
          salt: encoder.encode('haven-health-salt'),
          iterations: 100000,
          hash: 'SHA-256',
        },
        keyMaterial,
        { name: 'AES-GCM', length: 256 },
        false,
        ['encrypt', 'decrypt']
      );
      
      const decryptedData = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv },
        key,
        encryptedData
      );
      
      return decoder.decode(decryptedData);
    } catch (error) {
      console.error('WebStorageAdapter: Decryption failed', error);
      return data;
    }
  }
}