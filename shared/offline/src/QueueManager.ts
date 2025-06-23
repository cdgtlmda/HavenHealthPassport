import { StorageAdapter, OfflineOperation } from './types';

export class QueueManager {
  private static readonly QUEUE_KEY = 'offline_operation_queue';
  private storage: StorageAdapter;
  private maxRetries: number;
  private queue: Map<string, OfflineOperation> = new Map();

  constructor(storage: StorageAdapter, maxRetries: number = 3) {
    this.storage = storage;
    this.maxRetries = maxRetries;
    this.loadQueue();
  }

  /**
   * Load queue from storage
   */
  private async loadQueue(): Promise<void> {
    const stored = await this.storage.get<{ [key: string]: OfflineOperation }>(
      QueueManager.QUEUE_KEY
    );
    
    if (stored) {
      Object.entries(stored).forEach(([id, operation]) => {
        this.queue.set(id, operation);
      });
    }
  }

  /**
   * Save queue to storage
   */
  private async saveQueue(): Promise<void> {
    const queueObj: { [key: string]: OfflineOperation } = {};
    this.queue.forEach((operation, id) => {
      queueObj[id] = operation;
    });
    
    await this.storage.set(QueueManager.QUEUE_KEY, queueObj);
  }

  /**
   * Add operation to queue
   */
  async addOperation(operation: OfflineOperation): Promise<void> {
    this.queue.set(operation.id, operation);
    await this.saveQueue();
  }

  /**
   * Get pending operations
   */
  async getPendingOperations(): Promise<OfflineOperation[]> {
    return Array.from(this.queue.values())
      .filter(op => op.retryCount < this.maxRetries)
      .sort((a, b) => a.timestamp - b.timestamp);
  }
  /**
   * Update operation status
   */
  async updateOperation(
    operationId: string, 
    updates: Partial<OfflineOperation>
  ): Promise<void> {
    const operation = this.queue.get(operationId);
    if (operation) {
      this.queue.set(operationId, { ...operation, ...updates });
      await this.saveQueue();
    }
  }

  /**
   * Remove operation
   */
  async removeOperation(operationId: string): Promise<void> {
    this.queue.delete(operationId);
    await this.saveQueue();
  }

  /**
   * Increment retry count
   */
  async incrementRetryCount(operationId: string): Promise<void> {
    const operation = this.queue.get(operationId);
    if (operation) {
      operation.retryCount++;
      await this.saveQueue();
    }
  }

  /**
   * Get failed operations
   */
  getFailedOperations(): OfflineOperation[] {
    return Array.from(this.queue.values())
      .filter(op => op.retryCount >= this.maxRetries);
  }

  /**
   * Clean up completed operations
   */
  async cleanupCompleted(): Promise<void> {
    const failedOps = this.getFailedOperations();
    
    // Keep only failed operations for debugging
    this.queue.clear();
    failedOps.forEach(op => {
      this.queue.set(op.id, op);
    });
    
    await this.saveQueue();
  }

  /**
   * Clear all operations
   */
  async clearAll(): Promise<void> {
    this.queue.clear();
    await this.storage.delete(QueueManager.QUEUE_KEY);
  }

  /**
   * Get queue size
   */
  getQueueSize(): number {
    return this.queue.size;
  }

  /**
   * Get operations by entity
   */
  getOperationsByEntity(entity: string): OfflineOperation[] {
    return Array.from(this.queue.values())
      .filter(op => op.entity === entity);
  }
}

export default QueueManager;