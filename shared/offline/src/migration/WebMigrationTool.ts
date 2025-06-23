import { BaseMigrationTool } from './BaseMigrationTool';
import { MigrationData } from './types';
import { StorageAdapter, CryptoAdapter } from '../types';

export class WebMigrationTool extends BaseMigrationTool {
  constructor(
    storageAdapter: StorageAdapter,
    cryptoAdapter: CryptoAdapter
  ) {
    super(storageAdapter, cryptoAdapter, 'web');
  }

  /**
   * Export data as downloadable file
   */
  async exportToFile(options = {}): Promise<void> {
    try {
      // Export data
      const migrationData = await this.exportData(options);
      
      // Convert to JSON string
      const jsonString = JSON.stringify(migrationData, null, 2);
      
      // Create blob
      const blob = new Blob([jsonString], { type: 'application/json' });
      
      // Create download link
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `haven_migration_${Date.now()}.json`;
      
      // Trigger download
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      // Clean up
      setTimeout(() => URL.revokeObjectURL(url), 100);
    } catch (error) {
      console.error('Export to file failed:', error);
      throw error;
    }
  }

  /**
   * Import data from file input
   */
  async importFromFile(file?: File, options = {}): Promise<any> {
    try {      let fileToRead = file;
      
      // If no file provided, show file picker
      if (!fileToRead) {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'application/json';
        
        fileToRead = await new Promise<File>((resolve, reject) => {
          input.onchange = (e) => {
            const target = e.target as HTMLInputElement;
            const file = target.files?.[0];
            if (file) {
              resolve(file);
            } else {
              reject(new Error('No file selected'));
            }
          };
          input.click();
        });
      }
      
      // Read file content
      const content = await fileToRead.text();
      
      // Parse migration data
      const migrationData: MigrationData = JSON.parse(content);
      
      // Import the data
      return await this.importData(migrationData, options);
    } catch (error) {
      console.error('Import from file failed:', error);
      throw error;
    }
  }

  /**
   * Export using File System Access API (if available)
   */
  async exportWithFileSystemAccess(options = {}): Promise<void> {
    try {
      // Check if File System Access API is available
      if (!('showSaveFilePicker' in window)) {
        // Fallback to regular download
        return this.exportToFile(options);
      }
      
      // Export data
      const migrationData = await this.exportData(options);
      const jsonString = JSON.stringify(migrationData, null, 2);      
      // Show save file picker
      const handle = await (window as any).showSaveFilePicker({
        suggestedName: `haven_migration_${Date.now()}.json`,
        types: [{
          description: 'JSON files',
          accept: { 'application/json': ['.json'] }
        }]
      });
      
      // Write file
      const writable = await handle.createWritable();
      await writable.write(jsonString);
      await writable.close();
    } catch (error) {
      console.error('Export with File System Access failed:', error);
      // Fallback to regular download
      return this.exportToFile(options);
    }
  }

  /**
   * Platform-specific validation for Web
   */
  protected async platformSpecificValidation(data: MigrationData): Promise<boolean> {
    // Check if data contains web-specific keys
    const hasWebKeys = Object.keys(data.data).some(key => 
      key.includes('indexeddb') || key.includes('localstorage')
    );
    
    if (data.platform === 'web' && !hasWebKeys) {
      console.warn('Data claims to be from web but lacks platform-specific keys');
    }
    
    return true;
  }

  /**
   * Prepare data for export - Web specific
   */
  protected async platformSpecificExportPrep(key: string, value: any): Promise<any> {
    // Handle IndexedDB object stores
    if (value && value.objectStore) {
      return {
        _indexed: true,
        storeName: value.objectStore,
        data: value.data || value
      };
    }
    
    // Handle File objects
    if (value instanceof File || value instanceof Blob) {      const buffer = await value.arrayBuffer();
      return {
        _type: 'blob',
        data: Array.from(new Uint8Array(buffer)),
        mimeType: value.type,
        name: (value as File).name || 'blob'
      };
    }
    
    return value;
  }

  /**
   * Prepare data for import - Web specific
   */
  protected async platformSpecificImportPrep(
    key: string, 
    value: any,
    migrationData: MigrationData
  ): Promise<any> {
    // Handle blob reconstruction
    if (value._type === 'blob') {
      const uint8Array = new Uint8Array(value.data);
      return new Blob([uint8Array], { type: value.mimeType });
    }
    
    // Handle React Native specific data
    if (migrationData.platform === 'react-native') {
      // Convert AsyncStorage format to IndexedDB format
      if (value._watermelondb) {
        return value._raw || value;
      }
    }
    
    return value;
  }

  /**
   * Get browser-specific metadata
   */
  protected async generateMetadata(options: any): Promise<any> {
    const baseMetadata = await super.generateMetadata(options);
    
    return {
      ...baseMetadata,
      deviceInfo: {
        userAgent: navigator.userAgent,
        language: navigator.language,
        platform: navigator.platform,
        cookieEnabled: navigator.cookieEnabled,
        onLine: navigator.onLine,
        storage: await this.getStorageInfo()
      }
    };
  }

  /**
   * Get storage quota information
   */
  private async getStorageInfo(): Promise<any> {
    try {
      if ('storage' in navigator && 'estimate' in navigator.storage) {
        const estimate = await navigator.storage.estimate();
        return {
          usage: estimate.usage,
          quota: estimate.quota,
          persistent: await navigator.storage.persisted()
        };
      }
    } catch (error) {
      console.warn('Could not get storage info:', error);
    }
    return null;
  }

  /**
   * Export to clipboard for small data
   */
  async exportToClipboard(filter?: (key: string) => boolean): Promise<void> {
    try {
      const allKeys = await this.storageAdapter.getAllKeys();
      const keysToExport = filter ? allKeys.filter(filter) : allKeys.slice(0, 10);
      
      const data: Record<string, any> = {};
      for (const key of keysToExport) {
        const value = await this.storageAdapter.get(key);
        if (value !== null) {
          data[key] = value;
        }
      }
      
      const jsonString = JSON.stringify(data, null, 2);
      await navigator.clipboard.writeText(jsonString);
      
      console.log('Data copied to clipboard');
    } catch (error) {
      console.error('Clipboard export failed:', error);
      throw error;
    }
  }
}

export default WebMigrationTool;