// Performance optimization exports
export { LazyLoadManager } from './LazyLoadManager';
export { IntelligentPagination } from './IntelligentPagination';
export { VirtualScroll, useVirtualScroll } from './VirtualScroll';
export { 
  DataWindowManager,
  TumblingWindow,
  SlidingWindow,
  SessionWindow
} from './DataWindowManager';
export { MemoryMonitor } from './MemoryMonitor';
export { ResourceManager } from './ResourceManager';
export { BatteryOptimizer } from './BatteryOptimizer';
export { NetworkOptimizer } from './NetworkOptimizer';

// Type exports
export type { LoadableItem, LoadState } from './LazyLoadManager';
export type { Page, PaginationConfig } from './IntelligentPagination';
export type { VirtualScrollConfig, VirtualScrollProps } from './VirtualScroll';
export type { WindowConfig, DataWindow } from './DataWindowManager';
export type { MemoryStats, MemoryThresholds, MemoryMonitorConfig } from './MemoryMonitor';
export type { ResourceType, ResourcePoolConfig, ConnectionConfig } from './ResourceManager';
export type { BatteryState, PowerProfile, BatteryOptimizationConfig } from './BatteryOptimizer';
export type { NetworkConditions, SyncConfig, QualitySettings, SyncTask } from './NetworkOptimizer';