// Platform migration types
export interface MigrationOptions {
  encryptionKey?: string;
  progressCallback?: (progress: MigrationProgress) => void;
  includeMetadata?: boolean;
  includeSecureData?: boolean;
  chunkSize?: number;
  validateData?: boolean;
}

export interface MigrationProgress {
  stage: 'preparing' | 'exporting' | 'importing' | 'validating' | 'complete' | 'error';
  current: number;
  total: number;
  percentage: number;
  message?: string;
  error?: string;
}

export interface MigrationData {
  version: string;
  platform: 'react-native' | 'web';
  timestamp: number;
  data: Record<string, any>;
  metadata?: MigrationMetadata;
  checksum: string;
}

export interface MigrationMetadata {
  deviceInfo?: any;
  appVersion: string;
  offlineDataVersion: string;
  encryptionMethod?: string;
  compressionMethod?: string;
}

export interface MigrationResult {
  success: boolean;
  itemsExported?: number;
  itemsImported?: number;
  errors?: MigrationError[];
  warnings?: string[];
  duration: number;
}

export interface MigrationError {
  key: string;
  error: string;
  recoverable: boolean;
}

export interface PlatformMigrationTool {
  exportData(options?: MigrationOptions): Promise<MigrationData>;
  importData(data: MigrationData, options?: MigrationOptions): Promise<MigrationResult>;
  validateMigrationData(data: MigrationData): Promise<boolean>;
  generateMigrationReport(): Promise<MigrationReport>;
}

export interface MigrationReport {
  lastExport?: Date;
  lastImport?: Date;
  totalExports: number;
  totalImports: number;
  dataSize: number;
  conflicts: number;
  recommendations: string[];
}