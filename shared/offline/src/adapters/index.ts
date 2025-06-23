// Platform-specific adapters for offline functionality

// Storage adapters
export { ReactNativeStorageAdapter } from './ReactNativeStorageAdapter';
export { WebStorageAdapter } from './WebStorageAdapter';

// File handling adapters
export { ReactNativeFileHandler } from './ReactNativeFileHandler';
export { WebFileHandler } from './WebFileHandler';

// Network monitoring adapters
export { ReactNativeNetworkMonitor } from './ReactNativeNetworkMonitor';
export { WebNetworkMonitor } from './WebNetworkMonitor';

// Background task managers
export { ReactNativeBackgroundTaskManager } from './ReactNativeBackgroundTaskManager';
export { WebBackgroundTaskManager } from './WebBackgroundTaskManager';

// UI adapters
export { ReactNativeUIAdapter } from './ReactNativeUIAdapter';
export { WebUIAdapter } from './WebUIAdapter';

// Performance monitors
export { ReactNativePerformanceMonitor } from './ReactNativePerformanceMonitor';
export { WebPerformanceMonitor } from './WebPerformanceMonitor';

// Security adapters
export { ReactNativeSecurityAdapter } from './ReactNativeSecurityAdapter';
export { WebSecurityAdapter } from './WebSecurityAdapter';

// Platform detector to choose the right adapter
export function getStorageAdapter() {
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    // Web environment
    return new (require('./WebStorageAdapter').WebStorageAdapter)();
  } else {
    // React Native environment
    return new (require('./ReactNativeStorageAdapter').ReactNativeStorageAdapter)();
  }
}

export function getFileHandler() {
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    // Web environment
    return new (require('./WebFileHandler').WebFileHandler)();
  } else {
    // React Native environment
    return new (require('./ReactNativeFileHandler').ReactNativeFileHandler)();
  }
}

export function getNetworkMonitor() {
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    // Web environment
    return new (require('./WebNetworkMonitor').WebNetworkMonitor)();
  } else {
    // React Native environment
    return new (require('./ReactNativeNetworkMonitor').ReactNativeNetworkMonitor)();
  }
}

export function getBackgroundTaskManager() {
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    // Web environment
    return new (require('./WebBackgroundTaskManager').WebBackgroundTaskManager)();
  } else {
    // React Native environment
    return new (require('./ReactNativeBackgroundTaskManager').ReactNativeBackgroundTaskManager)();
  }
}

export function getUIAdapter() {
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    // Web environment
    return new (require('./WebUIAdapter').WebUIAdapter)();
  } else {
    // React Native environment
    return new (require('./ReactNativeUIAdapter').ReactNativeUIAdapter)();
  }
}

export function getPerformanceMonitor() {
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    // Web environment
    return new (require('./WebPerformanceMonitor').WebPerformanceMonitor)();
  } else {
    // React Native environment
    return new (require('./ReactNativePerformanceMonitor').ReactNativePerformanceMonitor)();
  }
}

export function getSecurityAdapter() {
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    // Web environment
    return new (require('./WebSecurityAdapter').WebSecurityAdapter)();
  } else {
    // React Native environment
    return new (require('./ReactNativeSecurityAdapter').ReactNativeSecurityAdapter)();
  }
}
