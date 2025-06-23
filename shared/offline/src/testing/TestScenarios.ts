// Common test scenarios for offline functionality
import { TestUtils } from './TestUtilities';
import { MockImplementations } from './MockImplementations';

export const TestScenarios = {
  // Conflict scenarios
  async createBasicConflictScenario() {
    const conflicts = [
      TestUtils.ConflictTestHelper.createValueConflict(
        'diagnosis',
        'Hypertension',
        'High Blood Pressure'
      ),
      TestUtils.ConflictTestHelper.createArrayConflict(
        'medications',
        ['Aspirin', 'Metformin'],
        ['Aspirin', 'Insulin'],
        ['Aspirin']
      ),
      TestUtils.ConflictTestHelper.createObjectConflict(
        'vitals',
        { bp: '120/80', pulse: 72 },
        { bp: '130/85', pulse: 75 },
        { bp: '120/80', pulse: 70 }
      ),
    ];

    return conflicts;
  },

  // Network failure scenarios
  async createNetworkFailureScenario() {
    const network = new TestUtils.NetworkSimulator();
    
    // Offline scenario
    network.setCondition({ isOnline: false });
    
    // High latency scenario
    network.setCondition({ latency: 5000, isOnline: true });
    
    // Packet loss scenario
    network.setCondition({ packetLoss: 0.3, isOnline: true });
    
    // Limited bandwidth scenario
    network.setCondition({ bandwidth: 1024, isOnline: true }); // 1KB/s
    
    return network;
  },

  // Sync queue scenarios
  async createSyncQueueScenario() {
    const operations = TestUtils.SyncTestHelper.generateSyncQueue(10);
    const mockEngine = new MockImplementations.MockSyncEngine();
    
    // Add operations to queue
    for (const op of operations) {
      await mockEngine.queueManager.addOperation(op);
    }
    
    return { operations, mockEngine };
  },
};
  // Storage quota scenarios
  async createStorageQuotaScenario() {
    const storage = new TestUtils.MockStorage();
    
    // Set 1MB quota
    storage.setQuota(1024 * 1024);
    
    // Fill storage to 80%
    const largeData = 'x'.repeat(800 * 1024);
    await storage.setItem('large-data', largeData);
    
    return storage;
  },

  // Performance testing scenarios
  async createPerformanceScenario() {
    const perfHelper = new TestUtils.PerformanceTestHelper();
    const mockEngine = new MockImplementations.MockSyncEngine();
    
    // Test sync performance
    const operations = TestUtils.SyncTestHelper.generateSyncQueue(100);
    
    const endMeasure = perfHelper.startMeasure('sync-100-operations');
    for (const op of operations) {
      await mockEngine.queueManager.addOperation(op);
    }
    await mockEngine.performSync();
    endMeasure();
    
    return perfHelper;
  },

  // Complex merge scenarios
  async createComplexMergeScenario() {
    const healthRecord = TestUtils.TestDataGenerator.generateHealthRecord({
      diagnosis: 'Initial diagnosis',
      medications: ['Med1', 'Med2'],
      vitals: {
        bloodPressure: '120/80',
        pulse: 70,
        temperature: 98.6,
      },
      notes: {
        doctor: 'Initial notes',
        nurse: 'Nurse observations',
      },
    });

    // Create three-way conflict
    const localRecord = {
      ...healthRecord,
      diagnosis: 'Updated diagnosis - local',
      medications: ['Med1', 'Med2', 'Med3'],
      vitals: { ...healthRecord.vitals, pulse: 75 },
      notes: { ...healthRecord.notes, doctor: 'Updated doctor notes' },
    };

    const remoteRecord = {
      ...healthRecord,
      diagnosis: 'Updated diagnosis - remote',
      medications: ['Med1', 'Med4'],
      vitals: { ...healthRecord.vitals, bloodPressure: '130/85' },
      notes: { ...healthRecord.notes, nurse: 'Updated nurse notes' },
    };

    return {
      ancestor: healthRecord,
      local: localRecord,
      remote: remoteRecord,
    };
  },
};