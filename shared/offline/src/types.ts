// Shared types for offline functionality
export interface SyncableEntity {
  id: string;
  version: number;
  lastModified: number;
  checksum?: string;
  _deleted?: boolean;
  _localOnly?: boolean;
}

export interface SyncMetadata {
  syncStatus: 'pending' | 'syncing' | 'synced' | 'conflict' | 'error';
  lastSyncAttempt?: number;
  lastSuccessfulSync?: number;
  syncError?: string;
  conflictData?: any;
}

export interface OfflineOperation<T = any> {
  id: string;
  type: 'create' | 'update' | 'delete';
  entity: string;
  entityId: string;
  data: T;
  timestamp: number;
  retryCount: number;
  maxRetries: number;
  metadata?: Record<string, any>;
}

export interface ConflictResolution<T = any> {
  strategy: 'local_wins' | 'remote_wins' | 'merge' | 'manual';
  resolvedData?: T;
  mergeFunction?: (local: T, remote: T, ancestor?: T) => T;
}

export interface SyncResult {
  success: boolean;
  syncedCount: number;
  conflictCount: number;
  errorCount: number;
  conflicts?: ConflictInfo[];
  errors?: SyncError[];
}

export interface ConflictInfo {
  entityId: string;
  entityType: string;
  localVersion: any;
  remoteVersion: any;
  conflictType: 'update_conflict' | 'delete_conflict' | 'not_found';
}

export interface SyncError {
  entityId: string;
  operation: OfflineOperation;
  error: string;
  retryable: boolean;
}

export interface StorageAdapter {
  get<T>(key: string): Promise<T | null>;
  set<T>(key: string, value: T): Promise<void>;
  delete(key: string): Promise<void>;
  getMany<T>(keys: string[]): Promise<(T | null)[]>;
  setMany<T>(items: Array<{ key: string; value: T }>): Promise<void>;
  deleteMany(keys: string[]): Promise<void>;
  clear(): Promise<void>;
  getAllKeys(): Promise<string[]>;
}

export interface NetworkAdapter {
  isConnected(): Promise<boolean>;
  addConnectionListener(callback: (isConnected: boolean) => void): () => void;
}

export interface CompressionAdapter {
  compress(data: string): Promise<string>;
  decompress(data: string): Promise<string>;
}

export interface CryptoAdapter {
  encrypt(data: string, key: string): Promise<string>;
  decrypt(data: string, key: string): Promise<string>;
  hash(data: string): Promise<string>;
}

// UI Adapter types
export interface UINotification {
  type: 'info' | 'success' | 'warning' | 'error';
  title?: string;
  message: string;
  duration?: number | 'short' | 'long' | 'persistent';
  action?: {
    label: string;
    onPress: () => void;
  };
}

export interface UILoadingOptions {
  message?: string;
  overlay?: boolean;
  cancellable?: boolean;
  onCancel?: () => void;
}

export interface UIDialogOptions {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  destructive?: boolean;
  cancelable?: boolean;
}

export interface UIToastOptions {
  message: string;
  duration?: 'short' | 'long';
  position?: 'top' | 'center' | 'bottom';
}

export interface UIAdapter {
  showNotification(notification: UINotification): Promise<void>;
  showLoading(options?: UILoadingOptions): Promise<() => void>;
  showDialog(options: UIDialogOptions): Promise<boolean>;
  showToast(options: UIToastOptions): Promise<void>;
  vibrate(pattern?: number | number[]): Promise<void>;
  getOfflineIndicator(): React.ComponentType<any>;
  getSyncStatusIndicator(): React.ComponentType<any>;
  getConflictResolutionUI(): React.ComponentType<any>;
  requestOfflinePermissions(): Promise<boolean>;
  supportsBackgroundSync(): boolean;
  supportsPersistentStorage(): boolean;
  supportsIndexedDB(): boolean;
}

// Network Monitor types
export interface NetworkStatus {
  isOnline: boolean;
  type: 'wifi' | 'cellular' | 'ethernet' | 'bluetooth' | 'none' | 'unknown';
  effectiveType: 'slow-2g' | '2g' | '3g' | '4g' | 'offline' | 'unknown';
  downlink: number; // Mbps
  rtt: number; // ms
  saveData: boolean;
  details?: any;
}

export type NetworkChangeCallback = (
  currentStatus: NetworkStatus,
  previousStatus: NetworkStatus
) => void;

export interface NetworkMonitor {
  initialize(): Promise<void>;
  checkConnectivity(): Promise<NetworkStatus>;
  getNetworkStatus(): Promise<NetworkStatus>;
  onStatusChange(callback: NetworkChangeCallback): () => void;
  measureLatency(url: string): Promise<number>;
  measureBandwidth(): Promise<number>;
  isReachable(url: string): Promise<boolean>;
  destroy(): void;
}

// Background Task types
export interface BackgroundTask {
  execute(): Promise<BackgroundTaskResult>;
  options?: BackgroundTaskOptions;
}

export interface BackgroundTaskOptions {
  type?: 'periodic' | 'oneshot';
  interval?: number; // ms
  delay?: number; // ms
  timeout?: number; // ms
  requiresNetwork?: boolean;
  requiresBatteryNotLow?: boolean;
  requiresCharging?: boolean;
  requiresStorageNotLow?: boolean;
  requiresDeviceIdle?: boolean;
}

export interface BackgroundTaskResult {
  success: boolean;
  data?: any;
  error?: string;
}

export interface BackgroundTaskManager {
  initialize(): Promise<void>;
  registerTask(
    taskId: string,
    task: BackgroundTask,
    options?: BackgroundTaskOptions
  ): Promise<void>;
  unregisterTask(taskId: string): Promise<void>;
  executeTask(taskId: string): Promise<BackgroundTaskResult>;
  isTaskRegistered(taskId: string): Promise<boolean>;
  getRegisteredTasks(): Promise<string[]>;
  stopAllTasks(): Promise<void>;
  getTaskStatus(taskId: string): Promise<{
    isRegistered: boolean;
    lastExecution?: number;
    nextScheduledExecution?: number;
  }>;
  requestBackgroundPermissions(): Promise<boolean>;
  minimizeBatteryUsage(enabled: boolean): Promise<void>;
}

// File Handler types
export interface FileInfo {
  name: string;
  path: string;
  size: number;
  modificationTime: number;
  isDirectory: boolean;
  uri?: string;
  mimeType?: string;
  file?: File; // Web only
  fileHandle?: any; // Web File System Access API
}

export interface FileOperationOptions {
  encoding?: 'utf8' | 'base64';
  mimeType?: string;
  multiple?: boolean;
  extensions?: string[];
  copyToApp?: boolean;
  dialogTitle?: string;
  uti?: string; // iOS Universal Type Identifier
}

export interface FileOperationResult {
  success: boolean;
  data?: any;
  error?: string;
  metadata?: any;
}

export interface FileHandler {
  initialize(): Promise<void>;
  readFile(path: string, options?: FileOperationOptions): Promise<FileOperationResult>;
  writeFile(
    path: string,
    content: string | ArrayBuffer,
    options?: FileOperationOptions
  ): Promise<FileOperationResult>;
  deleteFile(path: string): Promise<FileOperationResult>;
  moveFile(sourcePath: string, destPath: string): Promise<FileOperationResult>;
  copyFile(sourcePath: string, destPath: string): Promise<FileOperationResult>;
  listFiles(directory: string): Promise<FileOperationResult>;
  pickFile(options?: FileOperationOptions): Promise<FileOperationResult>;
  shareFile(path: string, options?: FileOperationOptions): Promise<FileOperationResult>;
  getFileInfo(path: string): Promise<FileOperationResult>;
}

// Storage types
export interface StorageItem {
  key: string;
  value: any;
  timestamp: number;
  compressed?: boolean;
  encrypted?: boolean;
  metadata?: any;
}

export interface StorageMetadata {
  version: string;
  createdAt: number;
  lastUpdated: number;
  itemCount: number;
  totalSize: number;
}

export interface StorageOptions {
  prefix?: string;
  compress?: boolean;
  encrypt?: boolean;
  encryptionKey?: string;
  metadata?: any;
}

// Additional existing types remain unchanged...
// Performance Monitor types
export interface PerformanceMetrics {
  cpu: {
    usage: number; // percentage
    cores: number;
  };
  memory: {
    used: number; // bytes
    total: number; // bytes
    available: number; // bytes
    jsHeapSize?: number; // bytes
    limit?: number; // bytes
  };
  storage: {
    used: number; // bytes
    total: number; // bytes
    available: number; // bytes
  };
  battery?: {
    level: number; // 0-1
    charging: boolean;
    chargingTime?: number; // seconds
    dischargingTime?: number; // seconds
  };
  network?: {
    latency: number; // ms
    bandwidth: number; // Mbps
    type: string;
    effectiveType?: string;
    downlink?: number;
    rtt?: number;
  };
  fps: number;
  renderTime: number; // ms
  pageLoadTime?: number; // ms (web only)
  resourceTimings?: any; // (web only)
  customMetrics: Record<string, any>;
}

export interface PerformanceEntry {
  name: string;
  entryType: string;
  startTime: number;
  duration: number;
  timestamp: number;
}

export interface PerformanceOptions {
  autoStart?: boolean;
  sampleRate?: number;
  bufferSize?: number;
}

export interface PerformanceMonitor {
  initialize(options?: PerformanceOptions): Promise<void>;
  mark(name: string): void;
  measure(name: string, startMark?: string, endMark?: string): PerformanceEntry | null;
  getMetrics(): Promise<PerformanceMetrics>;
  startMonitoring(): void;
  stopMonitoring(): void;
  clearMetrics(): void;
  onMetricsUpdate(callback: (metrics: PerformanceMetrics) => void): () => void;
  exportMetrics(): Promise<string>;
  destroy(): void;
}
