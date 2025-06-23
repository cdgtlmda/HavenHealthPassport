import { Model } from '@nozbe/watermelondb';
import { OfflineAction, HealthRecord, SyncMetadata } from '../../web/src/offline/IndexedDBWrapper';
import { SyncConflict } from '../src/types';

/**
 * Shared test utilities for offline functionality testing
 * Can be used in both React Native and Web environments
 */

export interface MockNetworkConditions {
  isOnline: boolean;
  type: 'wifi' | '4g' | '3g' | '2g' | 'offline';
  effectiveType: 'slow-2g' | '2g' | '3g' | '4g';
  downlink: number;
  rtt: number;
  saveData: boolean;
}

export interface TestDataGenerator {
  generateHealthRecord(overrides?: Partial<HealthRecord>): HealthRecord;
  generateOfflineAction(overrides?: Partial<OfflineAction>): OfflineAction;
  generateSyncConflict(overrides?: Partial<SyncConflict>): SyncConflict;
  generateBulkData(count: number, type: string): any[];
}

export class OfflineTestUtils {
  /**
   * Mock network conditions for testing
   */
  static mockNetworkConditions(conditions: Partial<MockNetworkConditions>): void {
    const defaultConditions: MockNetworkConditions = {
      isOnline: true,
      type: 'wifi',
      effectiveType: '4g',
      downlink: 10,
      rtt: 50,
      saveData: false,
      ...conditions,
    };

    // Mock navigator.onLine
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      configurable: true,
      value: defaultConditions.isOnline,
    });

    // Mock navigator.connection
    Object.defineProperty(navigator, 'connection', {
      writable: true,
      configurable: true,
      value: {
        type: defaultConditions.type,
        effectiveType: defaultConditions.effectiveType,
        downlink: defaultConditions.downlink,
        rtt: defaultConditions.rtt,
        saveData: defaultConditions.saveData,
      },
    });
  }

  /**
   * Simulate going offline
   */
  static goOffline(): void {
    this.mockNetworkConditions({ isOnline: false, type: 'offline' });
    window.dispatchEvent(new Event('offline'));
  }

  /**
   * Simulate going online
   */
  static goOnline(): void {
    this.mockNetworkConditions({ isOnline: true, type: 'wifi' });
    window.dispatchEvent(new Event('online'));
  }

  /**
   * Simulate network latency
   */
  static async simulateNetworkLatency(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Create a test sync conflict
   */
  static createTestConflict(
    localData: any,
    remoteData: any,
    conflictedFields: string[]
  ): SyncConflict {
    return {
      id: `conflict_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      recordId: localData.id || remoteData.id,
      localVersion: localData,
      remoteVersion: remoteData,
      conflictedFields,
      detectedAt: Date.now(),
      resolution: 'pending',
      type: 'update',
    };
  }

  /**
   * Generate test health records
   */
  static generateHealthRecords(count: number): HealthRecord[] {
    const types: HealthRecord['type'][] = [
      'medication',
      'allergy',
      'condition',
      'procedure',
      'lab_result',
      'vaccination',
    ];

    return Array.from({ length: count }, (_, i) => ({
      id: `test_record_${i}`,
      patientId: `patient_${Math.floor(i / 10)}`,
      type: types[i % types.length],
      data: {
        title: `Test ${types[i % types.length]} ${i}`,
        description: `Test description for record ${i}`,
        date: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000),
        priority: Math.floor(Math.random() * 5) + 1,
      },
      metadata: {
        createdAt: Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000,
        updatedAt: Date.now() - Math.random() * 24 * 60 * 60 * 1000,
        syncStatus: 'pending' as const,
        version: 1,
      },
    }));
  }

  /**
   * Generate test offline actions
   */
  static generateOfflineActions(count: number): OfflineAction[] {
    const actions: OfflineAction['action'][] = ['create', 'update', 'delete'];
    const entities = ['healthRecord', 'appointment', 'medication', 'document'];

    return Array.from({ length: count }, (_, i) => ({
      id: `action_${i}`,
      action: actions[i % actions.length],
      entity: entities[i % entities.length],
      entityId: `entity_${i}`,
      data: {
        test: true,
        index: i,
        timestamp: Date.now(),
      },
      timestamp: Date.now() - Math.random() * 60 * 60 * 1000,
      retryCount: Math.floor(Math.random() * 3),
      syncStatus: 'pending' as const,
    }));
  }

  /**
   * Simulate storage quota exceeded
   */
  static async simulateStorageQuotaExceeded(): Promise<void> {
    if ('storage' in navigator && 'estimate' in navigator.storage) {
      // Mock storage.estimate to return quota exceeded
      const originalEstimate = navigator.storage.estimate;
      navigator.storage.estimate = async () => ({
        usage: 100 * 1024 * 1024,
        quota: 100 * 1024 * 1024,
      });

      // Restore after test
      setTimeout(() => {
        navigator.storage.estimate = originalEstimate;
      }, 0);
    }
  }

  /**
   * Create a mock sync queue
   */
  static createMockSyncQueue(size: number): OfflineAction[] {
    return this.generateOfflineActions(size);
  }

  /**
   * Verify sync queue state
   */
  static async verifySyncQueueState(
    expectedCount: number,
    expectedStatus?: OfflineAction['syncStatus']
  ): Promise<boolean> {
    // This would be implemented differently for each platform
    // Placeholder for shared interface
    return true;
  }

  /**
   * Mock sync completion
   */
  static mockSyncCompletion(actionIds: string[]): void {
    // Simulate successful sync of specified actions
    actionIds.forEach(id => {
      window.dispatchEvent(new CustomEvent('syncCompleted', { detail: { actionId: id } }));
    });
  }

  /**
   * Mock sync failure
   */
  static mockSyncFailure(actionIds: string[], error: string): void {
    // Simulate sync failure
    actionIds.forEach(id => {
      window.dispatchEvent(new CustomEvent('syncFailed', { 
        detail: { actionId: id, error } 
      }));
    });
  }

  /**
   * Test data integrity after sync
   */
  static async verifyDataIntegrity(
    originalData: any[],
    syncedData: any[]
  ): Promise<{ isValid: boolean; differences: any[] }> {
    const differences: any[] = [];

    originalData.forEach((original, index) => {
      const synced = syncedData[index];
      if (!synced) {
        differences.push({ type: 'missing', original });
        return;
      }

      const diff = this.deepDiff(original, synced);
      if (Object.keys(diff).length > 0) {
        differences.push({ type: 'modified', original, synced, diff });
      }
    });

    return {
      isValid: differences.length === 0,
      differences,
    };
  }

  /**
   * Deep diff between two objects
   */
  private static deepDiff(obj1: any, obj2: any): any {
    const diff: any = {};

    // Check obj1 keys
    for (const key in obj1) {
      if (!(key in obj2)) {
        diff[key] = { removed: obj1[key] };
      } else if (typeof obj1[key] === 'object' && typeof obj2[key] === 'object') {
        const nestedDiff = this.deepDiff(obj1[key], obj2[key]);
        if (Object.keys(nestedDiff).length > 0) {
          diff[key] = nestedDiff;
        }
      } else if (obj1[key] !== obj2[key]) {
        diff[key] = { from: obj1[key], to: obj2[key] };
      }
    }

    // Check obj2 keys not in obj1
    for (const key in obj2) {
      if (!(key in obj1)) {
        diff[key] = { added: obj2[key] };
      }
    }

    return diff;
  }

  /**
   * Performance testing utilities
   */
  static async measureSyncPerformance(
    operation: () => Promise<void>
  ): Promise<{
    duration: number;
    memoryUsed?: number;
    peakMemory?: number;
  }> {
    const startTime = performance.now();
    const startMemory = performance.memory ? 
      (performance.memory as any).usedJSHeapSize : undefined;

    await operation();

    const endTime = performance.now();
    const endMemory = performance.memory ? 
      (performance.memory as any).usedJSHeapSize : undefined;

    return {
      duration: endTime - startTime,
      memoryUsed: endMemory && startMemory ? endMemory - startMemory : undefined,
      peakMemory: endMemory,
    };
  }

  /**
   * Stress test sync with large datasets
   */
  static async stressTestSync(options: {
    recordCount: number;
    actionCount: number;
    conflictRate: number;
    errorRate: number;
  }): Promise<{
    totalTime: number;
    successRate: number;
    conflictsResolved: number;
    errors: string[];
  }> {
    const startTime = Date.now();
    const errors: string[] = [];
    let successCount = 0;
    let conflictsResolved = 0;

    // Generate test data
    const records = this.generateHealthRecords(options.recordCount);
    const actions = this.generateOfflineActions(options.actionCount);

    // Simulate sync with conflicts and errors
    for (let i = 0; i < actions.length; i++) {
      const shouldConflict = Math.random() < options.conflictRate;
      const shouldError = Math.random() < options.errorRate;

      if (shouldError) {
        errors.push(`Sync error for action ${actions[i].id}`);
      } else if (shouldConflict) {
        // Simulate conflict resolution
        conflictsResolved++;
        successCount++;
      } else {
        successCount++;
      }

      // Add some latency
      await this.simulateNetworkLatency(Math.random() * 100);
    }

    return {
      totalTime: Date.now() - startTime,
      successRate: successCount / actions.length,
      conflictsResolved,
      errors,
    };
  }

  /**
   * Clean up test data
   */
  static async cleanupTestData(): Promise<void> {
    // Clear test data from storage
    const keys = Object.keys(localStorage);
    keys.forEach(key => {
      if (key.includes('test_') || key.includes('mock_')) {
        localStorage.removeItem(key);
      }
    });

    // Clear IndexedDB test data
    if ('indexedDB' in window) {
      const databases = await indexedDB.databases();
      for (const db of databases) {
        if (db.name?.includes('test')) {
          await indexedDB.deleteDatabase(db.name);
        }
      }
    }
  }
}

/**
 * Platform-specific test utilities interface
 */
export interface PlatformTestUtils {
  setupTestEnvironment(): Promise<void>;
  teardownTestEnvironment(): Promise<void>;
  mockPlatformStorage(): void;
  mockPlatformNetwork(): void;
  getPlatformSpecificData(): any;
}

/**
 * Test helpers for conflict resolution
 */
export class ConflictTestUtils {
  static createFieldConflict(
    fieldName: string,
    localValue: any,
    remoteValue: any
  ): SyncConflict {
    return OfflineTestUtils.createTestConflict(
      { [fieldName]: localValue },
      { [fieldName]: remoteValue },
      [fieldName]
    );
  }

  static createMultiFieldConflict(
    conflicts: Record<string, { local: any; remote: any }>
  ): SyncConflict {
    const localData: any = {};
    const remoteData: any = {};
    const conflictedFields: string[] = [];

    Object.entries(conflicts).forEach(([field, values]) => {
      localData[field] = values.local;
      remoteData[field] = values.remote;
      conflictedFields.push(field);
    });

    return OfflineTestUtils.createTestConflict(localData, remoteData, conflictedFields);
  }

  static async simulateAutoResolution(
    conflict: SyncConflict,
    strategy: 'local' | 'remote' | 'merge'
  ): Promise<any> {
    switch (strategy) {
      case 'local':
        return conflict.localVersion;
      case 'remote':
        return conflict.remoteVersion;
      case 'merge':
        return { ...conflict.remoteVersion, ...conflict.localVersion };
    }
  }
}

export default OfflineTestUtils;