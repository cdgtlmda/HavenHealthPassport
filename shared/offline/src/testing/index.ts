// Testing utilities for offline functionality
// These utilities provide cross-platform testing support for both React Native and Web

export * from './TestUtilities';
export * from './MockImplementations';
export * from './TestScenarios';
export * from './OfflineTestSuite';

// Re-export commonly used items for convenience
export { TestUtils } from './TestUtilities';
export { MockImplementations } from './MockImplementations';
export { TestScenarios } from './TestScenarios';
export { OfflineTestSuite } from './OfflineTestSuite';

// Helper function to setup a complete test environment
export function setupTestEnvironment() {
  const mockSyncEngine = new MockImplementations.MockSyncEngine();
  const mockConflictResolver = new MockImplementations.MockConflictResolver();
  const mockQueueManager = new MockImplementations.MockQueueManager();
  const mockStorage = new TestUtils.MockStorage();
  const networkSimulator = new TestUtils.NetworkSimulator();
  const performanceHelper = new TestUtils.PerformanceTestHelper();

  return {
    mockSyncEngine,
    mockConflictResolver,
    mockQueueManager,
    mockStorage,
    networkSimulator,
    performanceHelper,
    
    // Cleanup function
    cleanup: () => {
      mockSyncEngine.reset();
      mockConflictResolver.reset();
      mockQueueManager.reset();
      mockStorage.clear();
      networkSimulator.reset();
      performanceHelper.clear();
    },
  };
}

// Platform-specific test setup helpers
export const PlatformTestHelpers = {
  // React Native specific setup
  setupReactNativeTests: () => {
    // Mock React Native specific APIs
    global.fetch = jest.fn();
    jest.mock('@react-native-async-storage/async-storage', () => new TestUtils.MockStorage());
  },

  // Web specific setup
  setupWebTests: () => {
    // Mock Web specific APIs
    global.localStorage = new TestUtils.MockStorage() as any;
    global.indexedDB = {} as any; // Mock IndexedDB if needed
  },
};
