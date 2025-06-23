// Network optimization exports
export { RequestBatcher } from './RequestBatcher';
export { ConnectionPoolManager } from './ConnectionPoolManager';
export { CircuitBreaker, CircuitState, createCircuitBreaker } from './CircuitBreaker';
export { RetryManager, RetryPolicies } from './RetryManager';

// Type exports
export type { 
  BatchRequest, 
  BatchConfig, 
  BatchResponse 
} from './RequestBatcher';

export type { 
  Connection, 
  PoolConfig, 
  PoolStats 
} from './ConnectionPoolManager';

export type { 
  CircuitBreakerConfig, 
  CircuitStats, 
  RequestResult 
} from './CircuitBreaker';

export type { 
  RetryConfig, 
  RetryPolicy, 
  RetryStats, 
  RetryOperation 
} from './RetryManager';