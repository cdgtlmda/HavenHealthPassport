import { 
  PlatformMigrationTool, 
  MigrationOptions, 
  MigrationData, 
  MigrationResult, 
  MigrationProgress,
  MigrationReport,
  MigrationError
} from './types';
import { StorageAdapter, CryptoAdapter } from '../types';
import { CompressionUtils } from '../CompressionUtils';

export abstract class BaseMigrationTool implements PlatformMigrationTool {
  protected storageAdapter: StorageAdapter;
  protected cryptoAdapter: CryptoAdapter;
  protected compressionUtils: CompressionUtils;
  protected platform: 'react-native' | 'web';
  
  constructor(
    storageAdapter: StorageAdapter,
    cryptoAdapter: CryptoAdapter,
    platform: 'react-native' | 'web'
  ) {
    this.storageAdapter = storageAdapter;
    this.cryptoAdapter = cryptoAdapter;
    this.compressionUtils = new CompressionUtils();
    this.platform = platform;
  }

  /**
   * Export all offline data for migration
   */
  async exportData(options: MigrationOptions = {}): Promise<MigrationData> {
    const startTime = Date.now();
    const progress = this.createProgressTracker(options.progressCallback);
    
    try {
      // Stage 1: Preparing
      progress.update('preparing', 0, 100, 'Gathering data keys...');
      const allKeys = await this.storageAdapter.getAllKeys();
      const keysToExport = this.filterKeysForExport(allKeys, options);
      
      // Stage 2: Exporting
      progress.update('exporting', 0, keysToExport.length, 'Exporting data...');
      const exportedData: Record<string, any> = {};
      
      for (let i = 0; i < keysToExport.length; i++) {
        const key = keysToExport[i];
        try {
          const value = await this.storageAdapter.get(key);          if (value !== null) {
            exportedData[key] = await this.prepareDataForExport(key, value, options);
          }
          progress.update('exporting', i + 1, keysToExport.length);
        } catch (error) {
          console.warn(`Failed to export key ${key}:`, error);
        }
      }
      
      // Stage 3: Validating
      progress.update('validating', 0, 100, 'Creating migration package...');
      
      const migrationData: MigrationData = {
        version: '1.0.0',
        platform: this.platform,
        timestamp: Date.now(),
        data: exportedData,
        metadata: await this.generateMetadata(options),
        checksum: ''
      };
      
      // Generate checksum
      const dataString = JSON.stringify(migrationData.data);
      migrationData.checksum = await this.cryptoAdapter.hash(dataString);
      
      progress.update('complete', 100, 100, 'Export complete');
      return migrationData;
      
    } catch (error) {
      progress.update('error', 0, 0, error.message);
      throw error;
    }
  }

  /**
   * Import data from another platform
   */
  async importData(
    data: MigrationData, 
    options: MigrationOptions = {}
  ): Promise<MigrationResult> {
    const startTime = Date.now();
    const progress = this.createProgressTracker(options.progressCallback);
    const errors: MigrationError[] = [];
    const warnings: string[] = [];
    
    try {
      // Stage 1: Validating
      progress.update('validating', 0, 100, 'Validating migration data...');
      
      if (options.validateData !== false) {        const isValid = await this.validateMigrationData(data);
        if (!isValid) {
          throw new Error('Invalid migration data: checksum mismatch');
        }
      }
      
      // Check platform compatibility
      if (data.platform === this.platform) {
        warnings.push('Importing data from the same platform type');
      }
      
      // Stage 2: Preparing
      progress.update('preparing', 0, 100, 'Preparing import...');
      const keysToImport = Object.keys(data.data);
      const totalItems = keysToImport.length;
      
      // Stage 3: Importing
      progress.update('importing', 0, totalItems, 'Importing data...');
      let importedCount = 0;
      
      for (let i = 0; i < keysToImport.length; i++) {
        const key = keysToImport[i];
        try {
          const value = await this.prepareDataForImport(
            key, 
            data.data[key], 
            data, 
            options
          );
          
          await this.storageAdapter.set(key, value);
          importedCount++;
          progress.update('importing', i + 1, totalItems);
        } catch (error) {
          errors.push({
            key,
            error: error.message,
            recoverable: true
          });
        }
      }
      
      progress.update('complete', 100, 100, 'Import complete');
      
      return {
        success: errors.length === 0,
        itemsImported: importedCount,
        errors: errors.length > 0 ? errors : undefined,
        warnings: warnings.length > 0 ? warnings : undefined,
        duration: Date.now() - startTime
      };
          } catch (error) {
      progress.update('error', 0, 0, error.message);
      return {
        success: false,
        errors: [{
          key: 'import',
          error: error.message,
          recoverable: false
        }],
        duration: Date.now() - startTime
      };
    }
  }

  /**
   * Validate migration data integrity
   */
  async validateMigrationData(data: MigrationData): Promise<boolean> {
    try {
      // Verify checksum
      const dataString = JSON.stringify(data.data);
      const calculatedChecksum = await this.cryptoAdapter.hash(dataString);
      
      if (calculatedChecksum !== data.checksum) {
        console.error('Checksum mismatch:', {
          expected: data.checksum,
          calculated: calculatedChecksum
        });
        return false;
      }
      
      // Verify required fields
      if (!data.version || !data.platform || !data.timestamp || !data.data) {
        console.error('Missing required fields in migration data');
        return false;
      }
      
      // Platform-specific validation
      return await this.platformSpecificValidation(data);
      
    } catch (error) {
      console.error('Validation error:', error);
      return false;
    }
  }

  /**
   * Generate migration report
   */
  async generateMigrationReport(): Promise<MigrationReport> {
    const reportKey = `${this.platform}_migration_report`;    const savedReport = await this.storageAdapter.get<MigrationReport>(reportKey);
    
    if (savedReport) {
      return savedReport;
    }
    
    // Create default report
    return {
      totalExports: 0,
      totalImports: 0,
      dataSize: 0,
      conflicts: 0,
      recommendations: [
        'Perform regular backups',
        'Validate data after migration',
        'Test migration in staging environment first'
      ]
    };
  }

  // Protected helper methods

  protected filterKeysForExport(
    allKeys: string[], 
    options: MigrationOptions
  ): string[] {
    return allKeys.filter(key => {
      // Skip system keys
      if (key.startsWith('_system_')) return false;
      
      // Skip secure data if not requested
      if (!options.includeSecureData && key.includes('_secure_')) return false;
      
      // Skip temporary data
      if (key.includes('_temp_') || key.includes('_cache_')) return false;
      
      return true;
    });
  }

  protected async prepareDataForExport(
    key: string, 
    value: any, 
    options: MigrationOptions
  ): Promise<any> {
    // Platform-specific preparation
    const prepared = await this.platformSpecificExportPrep(key, value);
    
    // Compress if large
    if (JSON.stringify(prepared).length > 1024) {
      return {
        _compressed: true,        data: this.compressionUtils.compress(JSON.stringify(prepared))
      };
    }
    
    return prepared;
  }

  protected async prepareDataForImport(
    key: string, 
    value: any,
    migrationData: MigrationData,
    options: MigrationOptions
  ): Promise<any> {
    let data = value;
    
    // Decompress if needed
    if (value._compressed) {
      const decompressed = this.compressionUtils.decompress(value.data);
      data = JSON.parse(decompressed);
    }
    
    // Platform-specific preparation
    return await this.platformSpecificImportPrep(key, data, migrationData);
  }

  protected createProgressTracker(
    callback?: (progress: MigrationProgress) => void
  ) {
    return {
      update: (
        stage: MigrationProgress['stage'], 
        current: number, 
        total: number, 
        message?: string
      ) => {
        if (callback) {
          const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
          callback({
            stage,
            current,
            total,
            percentage,
            message
          });
        }
      }
    };
  }

  protected async generateMetadata(options: MigrationOptions): Promise<any> {
    return {
      appVersion: '1.0.0', // Should be injected
      offlineDataVersion: '1.0.0',
      encryptionMethod: options.encryptionKey ? 'AES-256-GCM' : 'none',
      compressionMethod: 'simple-rle'
    };
  }

  // Abstract methods to be implemented by platform-specific classes
  protected abstract platformSpecificValidation(data: MigrationData): Promise<boolean>;
  protected abstract platformSpecificExportPrep(key: string, value: any): Promise<any>;
  protected abstract platformSpecificImportPrep(
    key: string, 
    value: any, 
    migrationData: MigrationData
  ): Promise<any>;
}