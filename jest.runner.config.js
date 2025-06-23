/**
 * Jest runner configuration for Haven Health Passport
 * Optimized for performance and reliability
 */

module.exports = {
  // Maximum number of workers for parallel execution
  maxWorkers: process.env.CI ? 2 : '50%',
  
  // Maximum number of concurrent tests per worker
  maxConcurrency: 5,
  
  // Test timeout configuration
  testTimeout: process.env.CI ? 20000 : 10000,
  
  // Slow test threshold (warns about slow tests)
  slowTestThreshold: 5000,
  
  // Retry configuration for flaky tests
  testRetries: process.env.CI ? 2 : 0,
  
  // Bail on first test failure in CI
  bail: process.env.CI ? 1 : 0,
  
  // Error on deprecated APIs
  errorOnDeprecated: true,
  
  // Detect open handles and force exit
  detectOpenHandles: true,
  forceExit: true,
  
  // Runner configuration
  runner: 'jest-runner',
  
  // Test sequencer for optimal execution order
  testSequencer: '<rootDir>/test-setup/testSequencer.js',
  
  // Shard configuration (for distributed testing)
  shard: process.env.JEST_SHARD ? process.env.JEST_SHARD : undefined,
  
  // Performance tracking
  logHeapUsage: process.env.CI ? true : false,
  
  // Notification configuration
  notify: !process.env.CI,
  notifyMode: 'failure-change',
  
  // Update snapshots in CI
  updateSnapshot: process.env.CI ? false : true,
};
