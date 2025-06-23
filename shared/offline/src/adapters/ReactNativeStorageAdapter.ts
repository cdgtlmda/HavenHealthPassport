import AsyncStorage from '@react-native-async-storage/async-storage';
import { Database } from '@nozbe/watermelondb';
import { StorageAdapter, StorageItem, StorageMetadata, StorageOptions } from '../types';
import { CompressionUtils } from '../CompressionUtils';
import { ValidationUtils } from '../ValidationUtils';

export class ReactNativeStorageAdapter implements StorageAdapter {
  private readonly prefix: string;
  private readonly compressionUtil: CompressionUtils;
  private readonly validationUtil: ValidationUtils;
  private database?: Database;
  private encryptionKey?: string;

  constructor(options: StorageOptions = {}) {
    this.prefix = options.prefix || 'haven_offline_';
    this.compressionUtil = new CompressionUtils();
    this.validationUtil = new ValidationUtils();
    this.encryptionKey = options.encryptionKey;
  }

  async initialize(database?: Database): Promise<void> {
    this.database = database;
    
    // Initialize storage metadata
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
      const prefixedKey = this.getPrefixedKey(key);
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

      await AsyncStorage.setItem(prefixedKey, JSON.stringify(storageItem));
      await this.updateMetadata(key, serializedValue.length);
    } catch (error) {
      console.error('ReactNativeStorageAdapter: Failed to set item', error);
      throw error;
    }
  }

  async getItem(key: string): Promise<any | null> {
    try {
      const prefixedKey = this.getPrefixedKey(key);
      const itemStr = await AsyncStorage.getItem(prefixedKey);
      
      if (!itemStr) {
        return null;
      }

      const storageItem: StorageItem = JSON.parse(itemStr);
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
      console.error('ReactNativeStorageAdapter: Failed to get item', error);
      return null;
    }
  }

  async removeItem(key: string): Promise<void> {
    try {
      const prefixedKey = this.getPrefixedKey(key);
      const item = await this.getItem(key);
      
      if (item) {
        await AsyncStorage.removeItem(prefixedKey);
        await this.updateMetadata(key, 0, true);
      }
    } catch (error) {
      console.error('ReactNativeStorageAdapter: Failed to remove item', error);
      throw error;
    }
  }

  async clear(): Promise<void> {
    try {
      const keys = await this.getAllKeys();
      const prefixedKeys = keys.map(key => this.getPrefixedKey(key));
      await AsyncStorage.multiRemove(prefixedKeys);
      
      // Reset metadata
      await this.setMetadata({
        version: '1.0.0',
        createdAt: Date.now(),
        lastUpdated: Date.now(),
        itemCount: 0,
        totalSize: 0,
      });
    } catch (error) {
      console.error('ReactNativeStorageAdapter: Failed to clear storage', error);
      throw error;
    }
  }

  async getAllKeys(): Promise<string[]> {
    try {
      const allKeys = await AsyncStorage.getAllKeys();
      return allKeys
        .filter(key => key.startsWith(this.prefix))
        .map(key => key.replace(this.prefix, ''));
    } catch (error) {
      console.error('ReactNativeStorageAdapter: Failed to get all keys', error);
      return [];
    }
  }

  async getMultiple(keys: string[]): Promise<Map<string, any>> {
    try {
      const result = new Map<string, any>();
      const prefixedKeys = keys.map(key => this.getPrefixedKey(key));
      const items = await AsyncStorage.multiGet(prefixedKeys);

      for (const [prefixedKey, itemStr] of items) {
        if (itemStr) {
          const key = prefixedKey.replace(this.prefix, '');
          const value = await this.getItem(key);
          if (value !== null) {
            result.set(key, value);
          }
        }
      }

      return result;
    } catch (error) {
      console.error('ReactNativeStorageAdapter: Failed to get multiple items', error);
      return new Map();
    }
  }
  async setMultiple(items: Map<string, any>, options?: StorageOptions): Promise<void> {
    try {
      const pairs: [string, string][] = [];

      for (const [key, value] of items) {
        const prefixedKey = this.getPrefixedKey(key);
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

        pairs.push([prefixedKey, JSON.stringify(storageItem)]);
      }

      await AsyncStorage.multiSet(pairs);
      
      // Update metadata for all items
      for (const [key, value] of items) {
        const serializedValue = JSON.stringify(value);
        await this.updateMetadata(key, serializedValue.length);
      }
    } catch (error) {
      console.error('ReactNativeStorageAdapter: Failed to set multiple items', error);
      throw error;
    }
  }

  async getSize(): Promise<number> {
    try {
      const metadata = await this.getMetadata();
      return metadata?.totalSize || 0;
    } catch (error) {
      console.error('ReactNativeStorageAdapter: Failed to get size', error);
      return 0;
    }
  }

  async getQuota(): Promise<number> {
    // React Native doesn't have a specific quota limit
    // Return a large number to indicate effectively unlimited storage
    return Number.MAX_SAFE_INTEGER;
  }

  async persist(): Promise<boolean> {
    // React Native AsyncStorage is already persistent
    return true;
  }
  // Helper methods
  private getPrefixedKey(key: string): string {
    return `${this.prefix}${key}`;
  }

  private async getMetadata(): Promise<StorageMetadata | null> {
    try {
      const metadataStr = await AsyncStorage.getItem(`${this.prefix}_metadata`);
      return metadataStr ? JSON.parse(metadataStr) : null;
    } catch (error) {
      console.error('ReactNativeStorageAdapter: Failed to get metadata', error);
      return null;
    }
  }

  private async setMetadata(metadata: StorageMetadata): Promise<void> {
    try {
      await AsyncStorage.setItem(`${this.prefix}_metadata`, JSON.stringify(metadata));
    } catch (error) {
      console.error('ReactNativeStorageAdapter: Failed to set metadata', error);
    }
  }

  private async updateMetadata(key: string, size: number, isRemoval = false): Promise<void> {
    try {
      const metadata = await this.getMetadata();
      if (!metadata) return;

      if (isRemoval) {
        metadata.itemCount = Math.max(0, metadata.itemCount - 1);
        metadata.totalSize = Math.max(0, metadata.totalSize - size);
      } else {
        const existingItem = await AsyncStorage.getItem(this.getPrefixedKey(key));
        if (!existingItem) {
          metadata.itemCount++;
        } else {
          const oldSize = JSON.parse(existingItem).value.length;
          metadata.totalSize = Math.max(0, metadata.totalSize - oldSize);
        }
        metadata.totalSize += size;
      }

      metadata.lastUpdated = Date.now();
      await this.setMetadata(metadata);
    } catch (error) {
      console.error('ReactNativeStorageAdapter: Failed to update metadata', error);
    }
  }

  // Encryption methods (basic implementation - should use proper crypto library in production)
  private async encrypt(data: string): Promise<string> {
    // In production, use react-native-crypto or similar
    // This is a placeholder implementation
    if (!this.encryptionKey) return data;
    
    // Simple XOR encryption for demonstration
    const key = this.encryptionKey;
    let encrypted = '';
    for (let i = 0; i < data.length; i++) {
      encrypted += String.fromCharCode(
        data.charCodeAt(i) ^ key.charCodeAt(i % key.length)
      );
    }
    return Buffer.from(encrypted).toString('base64');
  }

  private async decrypt(data: string): Promise<string> {
    if (!this.encryptionKey) return data;
    
    const key = this.encryptionKey;
    const decoded = Buffer.from(data, 'base64').toString();
    let decrypted = '';
    for (let i = 0; i < decoded.length; i++) {
      decrypted += String.fromCharCode(
        decoded.charCodeAt(i) ^ key.charCodeAt(i % key.length)
      );
    }
    return decrypted;
  }

  // WatermelonDB specific methods
  async syncWithDatabase(): Promise<void> {
    if (!this.database) {
      throw new Error('Database not initialized');
    }

    // Sync offline storage with WatermelonDB
    const keys = await this.getAllKeys();
    for (const key of keys) {
      const value = await this.getItem(key);
      if (value && value.tableName && value.recordId) {
        // Sync with appropriate table in WatermelonDB
        // Implementation depends on your database schema
      }
    }
  }

  async getOfflineChanges(): Promise<any[]> {
    const keys = await this.getAllKeys();
    const changes: any[] = [];

    for (const key of keys) {
      if (key.startsWith('offline_change_')) {
        const change = await this.getItem(key);
        if (change) {
          changes.push(change);
        }
      }
    }

    return changes.sort((a, b) => a.timestamp - b.timestamp);
  }
}
  // Helper methods
  private getPrefixedKey(key: string): string {
    return `${this.prefix}${key}`;
  }

  private async getMetadata(): Promise<StorageMetadata | null> {
    try {
      const metadataStr = await AsyncStorage.getItem(`${this.prefix}_metadata`);
      return metadataStr ? JSON.parse(metadataStr) : null;
    } catch (error) {
      console.error('ReactNativeStorageAdapter: Failed to get metadata', error);
      return null;
    }
  }

  private async setMetadata(metadata: StorageMetadata): Promise<void> {
    try {
      await AsyncStorage.setItem(`${this.prefix}_metadata`, JSON.stringify(metadata));
    } catch (error) {
      console.error('ReactNativeStorageAdapter: Failed to set metadata', error);
    }
  }

  private async updateMetadata(key: string, size: number, isRemoval = false): Promise<void> {
    try {
      const metadata = await this.getMetadata();
      if (!metadata) return;

      if (isRemoval) {
        metadata.itemCount = Math.max(0, metadata.itemCount - 1);
        metadata.totalSize = Math.max(0, metadata.totalSize - size);
      } else {
        const existingItem = await AsyncStorage.getItem(this.getPrefixedKey(key));
        if (!existingItem) {
          metadata.itemCount++;
        } else {
          const oldSize = JSON.parse(existingItem).value.length;
          metadata.totalSize = Math.max(0, metadata.totalSize - oldSize);
        }
        metadata.totalSize += size;
      }

      metadata.lastUpdated = Date.now();
      await this.setMetadata(metadata);
    } catch (error) {
      console.error('ReactNativeStorageAdapter: Failed to update metadata', error);
    }
  }

  // Encryption methods (basic implementation - should use proper crypto library in production)
  private async encrypt(data: string): Promise<string> {
    // In production, use react-native-crypto or similar
    // This is a placeholder implementation
    if (!this.encryptionKey) return data;
    
    // Simple XOR encryption for demonstration
    const key = this.encryptionKey;
    let encrypted = '';
    for (let i = 0; i < data.length; i++) {
      encrypted += String.fromCharCode(
        data.charCodeAt(i) ^ key.charCodeAt(i % key.length)
      );
    }
    return Buffer.from(encrypted).toString('base64');
  }

  private async decrypt(data: string): Promise<string> {
    if (!this.encryptionKey) return data;
    
    const key = this.encryptionKey;
    const decoded = Buffer.from(data, 'base64').toString();
    let decrypted = '';
    for (let i = 0; i < decoded.length; i++) {
      decrypted += String.fromCharCode(
        decoded.charCodeAt(i) ^ key.charCodeAt(i % key.length)
      );
    }
    return decrypted;
  }

  // WatermelonDB specific methods
  async syncWithDatabase(): Promise<void> {
    if (!this.database) {
      throw new Error('Database not initialized');
    }

    // Sync offline storage with WatermelonDB
    const keys = await this.getAllKeys();
    for (const key of keys) {
      const value = await this.getItem(key);
      if (value && value.tableName && value.recordId) {
        // Sync with appropriate table in WatermelonDB
        // Implementation depends on your database schema
      }
    }
  }

  async getOfflineChanges(): Promise<any[]> {
    const keys = await this.getAllKeys();
    const changes: any[] = [];

    for (const key of keys) {
      if (key.startsWith('offline_change_')) {
        const change = await this.getItem(key);
        if (change) {
          changes.push(change);
        }
      }
    }

    return changes.sort((a, b) => a.timestamp - b.timestamp);
  }
}