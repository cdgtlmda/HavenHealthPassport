// Mock implementations for testing offline functionality
import { BaseSyncEngine, SyncOperation, SyncStatus } from '../BaseSyncEngine';
import { ConflictResolver } from '../ConflictResolver';
import { QueueManager } from '../QueueManager';
import { CompressionUtil } from '../CompressionUtil';
import { ValidationUtil } from '../ValidationUtil';
import { ConflictData } from '../types';

// Mock Sync Engine
export class MockSyncEngine extends BaseSyncEngine {
  private mockResponses = new Map<string, any>();
  private syncDelay = 0;
  public syncCallCount = 0;
  public lastSyncedOperations: SyncOperation[] = [];

  setSyncDelay(ms: number) {
    this.syncDelay = ms;
  }

  setMockResponse(operationId: string, response: any) {
    this.mockResponses.set(operationId, response);
  }

  async performSync(): Promise<void> {
    this.syncCallCount++;
    await new Promise(resolve => setTimeout(resolve, this.syncDelay));
    
    const operations = await this.queueManager.getPendingOperations();
    this.lastSyncedOperations = operations;

    for (const operation of operations) {
      const mockResponse = this.mockResponses.get(operation.id);
      if (mockResponse) {
        if (mockResponse.error) {
          throw new Error(mockResponse.error);
        }
        // Simulate successful sync
        await this.queueManager.markAsCompleted(operation.id);
      }
    }
  }

  async checkConnectivity(): Promise<boolean> {
    return true;
  }

  reset() {
    this.syncCallCount = 0;
    this.lastSyncedOperations = [];
    this.mockResponses.clear();
  }
}

// Mock Conflict Resolver
export class MockConflictResolver extends ConflictResolver {
  public resolveCallCount = 0;
  public lastResolvedConflict: ConflictData | null = null;
  private mockResolutions = new Map<string, any>();

  setMockResolution(conflictId: string, resolution: any) {
    this.mockResolutions.set(conflictId, resolution);
  }

  async resolveConflict(conflict: ConflictData): Promise<any> {
    this.resolveCallCount++;
    this.lastResolvedConflict = conflict;

    const mockResolution = this.mockResolutions.get(conflict.id);
    if (mockResolution) {
      return mockResolution;
    }

    // Default to local value
    return conflict.localValue;
  }

  reset() {
    this.resolveCallCount = 0;
    this.lastResolvedConflict = null;
    this.mockResolutions.clear();
  }
}

// Mock Queue Manager
export class MockQueueManager extends QueueManager {
  private queue: SyncOperation[] = [];
  public addCallCount = 0;
  public processCallCount = 0;

  async addOperation(operation: SyncOperation): Promise<void> {
    this.addCallCount++;
    this.queue.push(operation);
  }

  async getPendingOperations(): Promise<SyncOperation[]> {
    return [...this.queue.filter(op => op.status === 'pending')];
  }

  async markAsCompleted(operationId: string): Promise<void> {
    const operation = this.queue.find(op => op.id === operationId);
    if (operation) {
      operation.status = 'completed';
    }
  }

  async processQueue(): Promise<void> {
    this.processCallCount++;
    // Mock processing
  }

  getQueueSize(): number {
    return this.queue.filter(op => op.status === 'pending').length;
  }

  reset() {
    this.queue = [];
    this.addCallCount = 0;
    this.processCallCount = 0;
  }
}
// Mock Compression Utility
export class MockCompressionUtil extends CompressionUtil {
  public compressCallCount = 0;
  public decompressCallCount = 0;
  private compressionRatio = 0.5;

  setCompressionRatio(ratio: number) {
    this.compressionRatio = ratio;
  }

  async compress(data: string): Promise<string> {
    this.compressCallCount++;
    // Simulate compression by returning a shorter string
    return data.substring(0, Math.floor(data.length * this.compressionRatio));
  }

  async decompress(data: string): Promise<string> {
    this.decompressCallCount++;
    // Simulate decompression by padding the string
    return data + data.substring(0, Math.floor(data.length / this.compressionRatio));
  }

  reset() {
    this.compressCallCount = 0;
    this.decompressCallCount = 0;
  }
}

// Mock Validation Utility
export class MockValidationUtil extends ValidationUtil {
  public validateCallCount = 0;
  private validationErrors = new Map<string, string[]>();

  setValidationError(field: string, errors: string[]) {
    this.validationErrors.set(field, errors);
  }

  validate(data: any, schema: any): { valid: boolean; errors: string[] } {
    this.validateCallCount++;
    
    const errors: string[] = [];
    for (const [field, fieldErrors] of this.validationErrors) {
      if (data.hasOwnProperty(field)) {
        errors.push(...fieldErrors);
      }
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }

  reset() {
    this.validateCallCount = 0;
    this.validationErrors.clear();
  }
}

// Export all mock implementations
export const MockImplementations = {
  MockSyncEngine,
  MockConflictResolver,
  MockQueueManager,
  MockCompressionUtil,
  MockValidationUtil,
};