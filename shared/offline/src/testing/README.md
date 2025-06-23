# Shared Offline Testing Utilities

This directory contains cross-platform testing utilities for offline functionality in the Haven Health Passport application. These utilities can be used in both React Native and Web environments.

## Overview

The testing utilities provide:
- Mock implementations of core offline components
- Network simulation capabilities
- Storage mocking
- Conflict generation helpers
- Performance testing utilities
- Common test scenarios

## Usage

### Basic Setup

```typescript
import { setupTestEnvironment } from '@shared/offline/testing';

describe('Offline functionality', () => {
  const testEnv = setupTestEnvironment();

  afterEach(() => {
    testEnv.cleanup();
  });

  it('should handle offline sync', async () => {
    // Your test code here
  });
});
```

### Network Simulation

```typescript
import { TestUtils } from '@shared/offline/testing';

const network = new TestUtils.NetworkSimulator();

// Simulate offline
network.setCondition({ isOnline: false });

// Simulate slow network
network.setCondition({ 
  latency: 3000, // 3 second latency
  bandwidth: 1024 * 10 // 10KB/s
});

// Simulate unreliable network
network.setCondition({ 
  packetLoss: 0.2 // 20% packet loss
});
```

### Conflict Testing

```typescript
import { TestUtils } from '@shared/offline/testing';

// Create different types of conflicts
const valueConflict = TestUtils.ConflictTestHelper.createValueConflict(
  'diagnosis',
  'Local diagnosis',
  'Remote diagnosis'
);

const arrayConflict = TestUtils.ConflictTestHelper.createArrayConflict(
  'medications',
  ['Med1', 'Med2'],
  ['Med1', 'Med3']
);
```

### Mock Implementations

```typescript
import { MockImplementations } from '@shared/offline/testing';

const mockSyncEngine = new MockImplementations.MockSyncEngine();
const mockConflictResolver = new MockImplementations.MockConflictResolver();

// Set up mock behavior
mockSyncEngine.setSyncDelay(1000);
mockConflictResolver.setMockResolution('conflict-1', { 
  resolved: true, 
  value: 'resolved value' 
});
```

### Performance Testing

```typescript
import { TestUtils } from '@shared/offline/testing';

const perfHelper = new TestUtils.PerformanceTestHelper();

// Measure sync performance
const endMeasure = perfHelper.startMeasure('sync-operation');
await performSync();
endMeasure();

// Get performance metrics
const metrics = perfHelper.getMeasurements('sync-operation');
console.log(`Average sync time: ${metrics.average}ms`);
console.log(`P95 sync time: ${metrics.p95}ms`);
```

## Test Scenarios

Pre-built test scenarios are available for common offline testing needs:

```typescript
import { TestScenarios } from '@shared/offline/testing';

// Get sample conflicts
const conflicts = await TestScenarios.createBasicConflictScenario();

// Get network failure scenario
const network = await TestScenarios.createNetworkFailureScenario();

// Get complex merge scenario
const mergeData = await TestScenarios.createComplexMergeScenario();
```

## Platform-Specific Setup

### React Native

```typescript
import { PlatformTestHelpers } from '@shared/offline/testing';

beforeAll(() => {
  PlatformTestHelpers.setupReactNativeTests();
});
```

### Web

```typescript
import { PlatformTestHelpers } from '@shared/offline/testing';

beforeAll(() => {
  PlatformTestHelpers.setupWebTests();
});
```

## API Reference

See the individual source files for detailed API documentation:
- `TestUtilities.ts` - Core testing utilities
- `MockImplementations.ts` - Mock implementations of offline components
- `TestScenarios.ts` - Pre-built test scenarios
