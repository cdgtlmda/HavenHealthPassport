import { EventEmitter } from 'events';
import { 
  SyncableEntity, 
  SyncMetadata, 
  OfflineOperation, 
  ConflictResolution, 
  SyncResult,
  ConflictInfo,
  SyncError,
  StorageAdapter,
  NetworkAdapter 
} from './types';
import { QueueManager } from './QueueManager';
import { ConflictResolver } from './ConflictResolver';
import { CompressionUtils } from './CompressionUtils';
import { ValidationUtils } from './ValidationUtils';

export interface SyncEngineConfig {
  batchSize: number;
  maxRetries: number;
  retryDelay: number;
  conflictResolution: ConflictResolution;
  enableCompression: boolean;
  enableValidation: boolean;
  syncEndpoint: string;
}

export abstract class BaseSyncEngine extends EventEmitter {
  protected config: SyncEngineConfig;
  protected storage: StorageAdapter;
  protected network: NetworkAdapter;
  protected queueManager: QueueManager;
  protected conflictResolver: ConflictResolver;
  protected isSyncing: boolean = false;
  protected syncAbortController?: AbortController;

  constructor(
    storage: StorageAdapter,
    network: NetworkAdapter,
    config: Partial<SyncEngineConfig> = {}
  ) {
    super();
    this.storage = storage;
    this.network = network;
    this.config = {
      batchSize: 50,
      maxRetries: 3,
      retryDelay: 1000,
      conflictResolution: { strategy: 'manual' },
      enableCompression: true,
      enableValidation: true,
      syncEndpoint: '/api/sync',
      ...config,
    };
    
    this.queueManager = new QueueManager(storage, this.config.maxRetries);
    this.conflictResolver = new ConflictResolver(this.config.conflictResolution);
    
    this.setupNetworkListener();
  }
  private setupNetworkListener(): void {
    this.network.addConnectionListener((isConnected) => {
      this.emit('network-status-changed', isConnected);
      if (isConnected && !this.isSyncing) {
        this.sync().catch(console.error);
      }
    });
  }

  /**
   * Start synchronization
   */
  async sync(): Promise<SyncResult> {
    if (this.isSyncing) {
      this.emit('sync-already-in-progress');
      return {
        success: false,
        syncedCount: 0,
        conflictCount: 0,
        errorCount: 0,
      };
    }

    const isConnected = await this.network.isConnected();
    if (!isConnected) {
      this.emit('sync-failed', 'No network connection');
      return {
        success: false,
        syncedCount: 0,
        conflictCount: 0,
        errorCount: 0,
      };
    }

    this.isSyncing = true;
    this.syncAbortController = new AbortController();
    this.emit('sync-started');

    const result: SyncResult = {
      success: true,
      syncedCount: 0,
      conflictCount: 0,
      errorCount: 0,
      conflicts: [],
      errors: [],
    };

    try {
      // Get pending operations
      const pendingOps = await this.queueManager.getPendingOperations();
      
      // Process in batches
      for (let i = 0; i < pendingOps.length; i += this.config.batchSize) {
        if (this.syncAbortController.signal.aborted) {
          break;
        }
        
        const batch = pendingOps.slice(i, i + this.config.batchSize);
        const batchResult = await this.processBatch(batch);
        
        result.syncedCount += batchResult.syncedCount;
        result.conflictCount += batchResult.conflictCount;
        result.errorCount += batchResult.errorCount;
        result.conflicts?.push(...(batchResult.conflicts || []));
        result.errors?.push(...(batchResult.errors || []));
      }
      // Pull remote changes
      await this.pullRemoteChanges();
      
      // Clean up completed operations
      await this.queueManager.cleanupCompleted();
      
      this.emit('sync-completed', result);
    } catch (error) {
      result.success = false;
      this.emit('sync-error', error);
    } finally {
      this.isSyncing = false;
      this.syncAbortController = undefined;
    }

    return result;
  }

  /**
   * Process a batch of operations
   */
  protected abstract processBatch(operations: OfflineOperation[]): Promise<SyncResult>;

  /**
   * Pull remote changes
   */
  protected abstract pullRemoteChanges(): Promise<void>;

  /**
   * Queue an operation for sync
   */
  async queueOperation<T>(
    type: OfflineOperation['type'],
    entity: string,
    entityId: string,
    data: T
  ): Promise<void> {
    const operation: OfflineOperation<T> = {
      id: this.generateOperationId(),
      type,
      entity,
      entityId,
      data,
      timestamp: Date.now(),
      retryCount: 0,
      maxRetries: this.config.maxRetries,
    };

    // Validate if enabled
    if (this.config.enableValidation) {
      const validationResult = ValidationUtils.validateOperation(operation);
      if (!validationResult.valid) {
        throw new Error(`Invalid operation: ${validationResult.errors.join(', ')}`);
      }
    }

    await this.queueManager.addOperation(operation);
    this.emit('operation-queued', operation);

    // Try to sync immediately if online
    const isConnected = await this.network.isConnected();
    if (isConnected && !this.isSyncing) {
      this.sync().catch(console.error);
    }
  }
  /**
   * Handle conflict
   */
  protected async handleConflict(
    local: any,
    remote: any,
    ancestor?: any
  ): Promise<any> {
    const resolution = await this.conflictResolver.resolve(local, remote, ancestor);
    this.emit('conflict-resolved', { local, remote, resolution });
    return resolution;
  }

  /**
   * Abort current sync
   */
  abortSync(): void {
    if (this.syncAbortController) {
      this.syncAbortController.abort();
      this.emit('sync-aborted');
    }
  }

  /**
   * Get sync status
   */
  getSyncStatus(): { isSyncing: boolean; queueSize: number } {
    return {
      isSyncing: this.isSyncing,
      queueSize: this.queueManager.getQueueSize(),
    };
  }

  /**
   * Clear all pending operations
   */
  async clearQueue(): Promise<void> {
    await this.queueManager.clearAll();
    this.emit('queue-cleared');
  }

  /**
   * Generate unique operation ID
   */
  protected generateOperationId(): string {
    return `op_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Update configuration
   */
  updateConfig(config: Partial<SyncEngineConfig>): void {
    this.config = { ...this.config, ...config };
    if (config.conflictResolution) {
      this.conflictResolver.updateStrategy(config.conflictResolution);
    }
    this.emit('config-updated', this.config);
  }
}

export default BaseSyncEngine;