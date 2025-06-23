import { BaseMigrationTool } from './BaseMigrationTool';
import { MigrationData } from './types';
import { Platform } from 'react-native';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import * as DocumentPicker from 'expo-document-picker';
import { StorageAdapter, CryptoAdapter } from '../types';

export class ReactNativeMigrationTool extends BaseMigrationTool {
  constructor(
    storageAdapter: StorageAdapter,
    cryptoAdapter: CryptoAdapter
  ) {
    super(storageAdapter, cryptoAdapter, 'react-native');
  }

  /**
   * Export data to a file that can be shared
   */
  async exportToFile(options = {}): Promise<string> {
    try {
      // Export data
      const migrationData = await this.exportData(options);
      
      // Convert to JSON string
      const jsonString = JSON.stringify(migrationData, null, 2);
      
      // Create file path
      const fileName = `haven_migration_${Date.now()}.json`;
      const filePath = `${FileSystem.documentDirectory}${fileName}`;
      
      // Write to file
      await FileSystem.writeAsStringAsync(filePath, jsonString, {
        encoding: FileSystem.EncodingType.UTF8
      });
      
      // Share the file
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(filePath, {
          mimeType: 'application/json',
          dialogTitle: 'Export Haven Health Data'
        });
      }
      
      return filePath;
    } catch (error) {
      console.error('Export to file failed:', error);
      throw error;
    }
  }

  /**
   * Import data from a file picker
   */
  async importFromFile(options = {}): Promise<any> {
    try {
      // Pick document
      const result = await DocumentPicker.getDocumentAsync({
        type: 'application/json',
        copyToCacheDirectory: true
      });
      
      if (result.type === 'cancel') {
        return { success: false, cancelled: true };
      }
      
      // Read file content
      const content = await FileSystem.readAsStringAsync(result.uri, {
        encoding: FileSystem.EncodingType.UTF8
      });
      
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
   * Platform-specific validation for React Native
   */
  protected async platformSpecificValidation(data: MigrationData): Promise<boolean> {
    // Check if data contains React Native specific keys
    const hasReactNativeKeys = Object.keys(data.data).some(key => 
      key.includes('AsyncStorage') || key.includes('watermelondb')
    );
    
    if (data.platform === 'react-native' && !hasReactNativeKeys) {
      console.warn('Data claims to be from React Native but lacks platform-specific keys');
    }
    
    return true;
  }

  /**
   * Prepare data for export - React Native specific
   */
  protected async platformSpecificExportPrep(key: string, value: any): Promise<any> {
    // Handle WatermelonDB records
    if (value && value._raw && value._changed) {
      return {
        _watermelondb: true,
        _raw: value._raw,
        _status: value._status,
        collection: value.collection?.modelClass?.name
      };
    }
    
    // Handle React Native specific date formats
    if (value instanceof Date) {
      return {
        _type: 'date',
        value: value.toISOString()
      };
    }
    
    return value;
  }

  /**
   * Prepare data for import - React Native specific
   */
  protected async platformSpecificImportPrep(
    key: string, 
    value: any,
    migrationData: MigrationData
  ): Promise<any> {
    // Handle WatermelonDB records
    if (value._watermelondb) {
      // For now, just store the raw data
      // Actual WatermelonDB import would need database instance
      return value._raw;
    }
    
    // Handle date conversion
    if (value._type === 'date') {
      return new Date(value.value);
    }
    
    // Handle web-specific data structures
    if (migrationData.platform === 'web') {
      // Convert IndexedDB structures to AsyncStorage format
      if (value._indexed) {
        return value.data || value;
      }
    }
    
    return value;
  }

  /**
   * Get device-specific metadata
   */
  protected async generateMetadata(options: any): Promise<any> {
    const baseMetadata = await super.generateMetadata(options);
    
    return {
      ...baseMetadata,
      deviceInfo: {
        platform: Platform.OS,
        version: Platform.Version,
        isTablet: Platform.isPad || false,
        constants: Platform.constants
      }
    };
  }

  /**
   * Create QR code for small data transfers
   */
  async exportToQRCode(filter?: (key: string) => boolean): Promise<string> {
    try {
      const allKeys = await this.storageAdapter.getAllKeys();
      const keysToExport = filter ? allKeys.filter(filter) : allKeys.slice(0, 5); // Limit for QR
      
      const data: Record<string, any> = {};
      for (const key of keysToExport) {
        const value = await this.storageAdapter.get(key);
        if (value !== null) {
          data[key] = value;
        }
      }
      
      const compressed = this.compressionUtils.compress(JSON.stringify(data));
      return compressed;
    } catch (error) {
      console.error('QR export failed:', error);
      throw error;
    }
  }
}

export default ReactNativeMigrationTool;