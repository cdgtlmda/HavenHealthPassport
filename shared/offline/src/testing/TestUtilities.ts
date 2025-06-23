// Shared Test Utilities for Offline Functionality
// These utilities can be used across React Native and Web platforms

import { ConflictData, MergeOptions } from '../types';
import { SyncOperation, SyncStatus } from '../BaseSyncEngine';

// Mock data generators
export const generateMockConflict = (overrides?: Partial<ConflictData>): ConflictData => {
  const baseConflict: ConflictData = {
    id: `conflict-${Date.now()}-${Math.random()}`,
    type: 'update-update',
    tableName: 'health_records',
    recordId: `record-${Math.random()}`,
    field: 'diagnosis',
    localValue: 'Local value',
    remoteValue: 'Remote value',
    localTimestamp: Date.now() - 3600000,
    remoteTimestamp: Date.now() - 1800000,
    status: 'pending',
    metadata: {
      localVersion: '1.0.0',
      remoteVersion: '1.0.1',
      userId: 'test-user',
      deviceId: 'test-device',
    },
    ...overrides,
  };

  return baseConflict;
};

export const generateMockSyncOperation = (
  overrides?: Partial<SyncOperation>
): SyncOperation => {
  const baseOperation: SyncOperation = {
    id: `op-${Date.now()}-${Math.random()}`,
    type: 'create',
    tableName: 'health_records',
    recordId: `record-${Math.random()}`,
    data: { field: 'value' },
    timestamp: Date.now(),
    status: 'pending',
    retryCount: 0,
    ...overrides,
  };

  return baseOperation;
};

// Network simulation utilities
export interface NetworkCondition {
  latency: number;
  packetLoss: number;
  bandwidth: number;
  isOnline: boolean;
}

export class NetworkSimulator {
  private condition: NetworkCondition = {
    latency: 0,
    packetLoss: 0,
    bandwidth: Infinity,
    isOnline: true,
  };

  private requestInterceptors: Array<(url: string) => Promise<void>> = [];
  private responseInterceptors: Array<(response: any) => any> = [];

  setCondition(condition: Partial<NetworkCondition>) {
    this.condition = { ...this.condition, ...condition };
  }

  async simulateRequest(url: string, options?: RequestInit): Promise<Response> {
    // Check if online
    if (!this.condition.isOnline) {
      throw new Error('Network is offline');
    }

    // Simulate packet loss
    if (Math.random() < this.condition.packetLoss) {
      throw new Error('Packet loss simulated');
    }

    // Simulate latency
    await this.delay(this.condition.latency);

    // Run request interceptors
    for (const interceptor of this.requestInterceptors) {
      await interceptor(url);
    }

    // Make actual request (in tests, this would be mocked)
    const response = await fetch(url, options);

    // Simulate bandwidth throttling
    if (response.body) {
      const contentLength = parseInt(response.headers.get('content-length') || '0');
      const downloadTime = (contentLength / this.condition.bandwidth) * 1000;
      await this.delay(downloadTime);
    }

    // Run response interceptors
    let modifiedResponse = response;
    for (const interceptor of this.responseInterceptors) {
      modifiedResponse = await interceptor(modifiedResponse);
    }

    return modifiedResponse;
  }

  addRequestInterceptor(interceptor: (url: string) => Promise<void>) {
    this.requestInterceptors.push(interceptor);
  }

  addResponseInterceptor(interceptor: (response: any) => any) {
    this.responseInterceptors.push(interceptor);
  }

  reset() {
    this.condition = {
      latency: 0,
      packetLoss: 0,
      bandwidth: Infinity,
      isOnline: true,
    };
    this.requestInterceptors = [];
    this.responseInterceptors = [];
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
// Storage mock utilities
export class MockStorage {
  private storage = new Map<string, string>();
  private quota = Infinity;
  private used = 0;

  async setItem(key: string, value: string): Promise<void> {
    const size = new Blob([value]).size;
    if (this.used + size > this.quota) {
      throw new Error('QuotaExceededError');
    }
    
    const oldValue = this.storage.get(key);
    if (oldValue) {
      this.used -= new Blob([oldValue]).size;
    }
    
    this.storage.set(key, value);
    this.used += size;
  }

  async getItem(key: string): Promise<string | null> {
    return this.storage.get(key) || null;
  }

  async removeItem(key: string): Promise<void> {
    const value = this.storage.get(key);
    if (value) {
      this.used -= new Blob([value]).size;
      this.storage.delete(key);
    }
  }

  async clear(): Promise<void> {
    this.storage.clear();
    this.used = 0;
  }

  async getAllKeys(): Promise<string[]> {
    return Array.from(this.storage.keys());
  }

  setQuota(bytes: number) {
    this.quota = bytes;
  }

  getUsed(): number {
    return this.used;
  }

  getQuota(): number {
    return this.quota;
  }
}

// Platform-agnostic storage interface
export interface TestStorage {
  setItem(key: string, value: string): Promise<void>;
  getItem(key: string): Promise<string | null>;
  removeItem(key: string): Promise<void>;
  clear(): Promise<void>;
  getAllKeys(): Promise<string[]>;
}
// Conflict resolution test helpers
export class ConflictTestHelper {
  static createValueConflict(field: string, localValue: any, remoteValue: any): ConflictData {
    return generateMockConflict({
      type: 'update-update',
      field,
      localValue,
      remoteValue,
      conflictType: 'value',
    });
  }

  static createArrayConflict(
    field: string,
    localArray: any[],
    remoteArray: any[],
    ancestorArray?: any[]
  ): ConflictData {
    return generateMockConflict({
      type: 'update-update',
      field,
      localValue: localArray,
      remoteValue: remoteArray,
      ancestorValue: ancestorArray,
      conflictType: 'array',
    });
  }

  static createObjectConflict(
    field: string,
    localObj: Record<string, any>,
    remoteObj: Record<string, any>,
    ancestorObj?: Record<string, any>
  ): ConflictData {
    return generateMockConflict({
      type: 'update-update',
      field,
      localValue: localObj,
      remoteValue: remoteObj,
      ancestorValue: ancestorObj,
      conflictType: 'object',
    });
  }

  static createDeleteConflict(field: string, deletedLocally: boolean): ConflictData {
    return generateMockConflict({
      type: deletedLocally ? 'update-delete' : 'delete-update',
      field,
      localValue: deletedLocally ? undefined : 'Local value',
      remoteValue: deletedLocally ? 'Remote value' : undefined,
      conflictType: 'delete',
    });
  }
}

// Sync test utilities
export class SyncTestHelper {
  static async simulateSyncCycle(
    operations: SyncOperation[],
    networkCondition?: Partial<NetworkCondition>
  ): Promise<{
    successful: SyncOperation[];
    failed: SyncOperation[];
    conflicts: ConflictData[];
  }> {
    const network = new NetworkSimulator();
    if (networkCondition) {
      network.setCondition(networkCondition);
    }

    const successful: SyncOperation[] = [];
    const failed: SyncOperation[] = [];
    const conflicts: ConflictData[] = [];

    for (const operation of operations) {
      try {
        // Simulate network request
        await network.simulateRequest('/sync', {
          method: 'POST',
          body: JSON.stringify(operation),
        });

        // Randomly generate conflicts for update operations
        if (operation.type === 'update' && Math.random() < 0.3) {
          conflicts.push(
            ConflictTestHelper.createValueConflict(
              'field',
              operation.data,
              { ...operation.data, modified: true }
            )
          );
        } else {
          successful.push(operation);
        }
      } catch (error) {
        failed.push(operation);
      }
    }

    return { successful, failed, conflicts };
  }

  static generateSyncQueue(count: number): SyncOperation[] {
    const operations: SyncOperation[] = [];
    const types: SyncOperation['type'][] = ['create', 'update', 'delete'];

    for (let i = 0; i < count; i++) {
      operations.push(
        generateMockSyncOperation({
          type: types[Math.floor(Math.random() * types.length)],
          timestamp: Date.now() - Math.random() * 86400000, // Random time within last 24h
        })
      );
    }

    return operations.sort((a, b) => a.timestamp - b.timestamp);
  }
}
// Performance test utilities
export class PerformanceTestHelper {
  private measurements = new Map<string, number[]>();

  startMeasure(label: string): () => void {
    const start = performance.now();
    return () => {
      const duration = performance.now() - start;
      const measurements = this.measurements.get(label) || [];
      measurements.push(duration);
      this.measurements.set(label, measurements);
    };
  }

  getMeasurements(label: string): {
    count: number;
    total: number;
    average: number;
    min: number;
    max: number;
    p95: number;
  } | null {
    const measurements = this.measurements.get(label);
    if (!measurements || measurements.length === 0) {
      return null;
    }

    const sorted = [...measurements].sort((a, b) => a - b);
    const total = measurements.reduce((sum, val) => sum + val, 0);

    return {
      count: measurements.length,
      total,
      average: total / measurements.length,
      min: sorted[0],
      max: sorted[sorted.length - 1],
      p95: sorted[Math.floor(sorted.length * 0.95)],
    };
  }

  clear(label?: string) {
    if (label) {
      this.measurements.delete(label);
    } else {
      this.measurements.clear();
    }
  }
}

// Test data generators for different entity types
export class TestDataGenerator {
  static generateHealthRecord(overrides?: Record<string, any>) {
    return {
      id: `record-${Date.now()}-${Math.random()}`,
      patientId: `patient-${Math.random()}`,
      type: 'consultation',
      date: new Date().toISOString(),
      diagnosis: 'Test diagnosis',
      treatment: 'Test treatment',
      notes: 'Test notes',
      attachments: [],
      metadata: {
        createdAt: Date.now(),
        updatedAt: Date.now(),
        version: 1,
      },
      ...overrides,
    };
  }

  static generatePatientProfile(overrides?: Record<string, any>) {
    return {
      id: `patient-${Date.now()}-${Math.random()}`,
      firstName: 'Test',
      lastName: 'Patient',
      dateOfBirth: '1990-01-01',
      gender: 'other',
      bloodType: 'O+',
      allergies: [],
      medications: [],
      conditions: [],
      emergencyContact: {
        name: 'Emergency Contact',
        phone: '+1234567890',
        relationship: 'family',
      },
      metadata: {
        createdAt: Date.now(),
        updatedAt: Date.now(),
        version: 1,
      },
      ...overrides,
    };
  }
}

// Export all test utilities
export const TestUtils = {
  generateMockConflict,
  generateMockSyncOperation,
  NetworkSimulator,
  MockStorage,
  ConflictTestHelper,
  SyncTestHelper,
  PerformanceTestHelper,
  TestDataGenerator,
};