import { EventEmitter } from 'events';

interface RetryConfig {
  maxRetries: number;
  initialDelay: number;
  maxDelay: number;
  backoffMultiplier: number;
  jitterFactor: number;
  retryBudget: number; // Max retries per time window
  budgetWindowMs: number;
  retryableErrors?: string[];
  nonRetryableErrors?: string[];
}

interface RetryPolicy {
  shouldRetry: (error: Error, attempt: number) => boolean;
  getDelay: (attempt: number) => number;
  onRetry?: (error: Error, attempt: number) => void;
}

interface RetryStats {
  totalAttempts: number;
  successfulAttempts: number;
  failedAttempts: number;
  retriesUsed: number;
  budgetRemaining: number;
  successRate: number;
}

interface RetryOperation {
  id: string;
  fn: () => Promise<any>;
  attempt: number;
  startTime: number;
  lastError?: Error;
  delays: number[];
}

export class RetryManager extends EventEmitter {
  private config: RetryConfig;
  private retryBudgetUsed = 0;
  private budgetWindowStart = Date.now();
  private stats = {
    totalAttempts: 0,
    successfulAttempts: 0,
    failedAttempts: 0,
    totalRetries: 0,
  };
  private activeOperations: Map<string, RetryOperation> = new Map();
  
  constructor(config: Partial<RetryConfig> = {}) {
    super();
    this.config = {
      maxRetries: 3,
      initialDelay: 1000,
      maxDelay: 30000,
      backoffMultiplier: 2,
      jitterFactor: 0.1,
      retryBudget: 100,
      budgetWindowMs: 60000, // 1 minute
      retryableErrors: [],
      nonRetryableErrors: [],
      ...config,
    };
    
    // Start budget reset timer
    this.startBudgetResetTimer();
  }

  /**
   * Execute function with retry logic
   */
  async execute<T>(
    fn: () => Promise<T>,
    policy?: Partial<RetryPolicy>
  ): Promise<T> {
    const operation: RetryOperation = {
      id: this.generateOperationId(),
      fn,
      attempt: 0,
      startTime: Date.now(),
      delays: [],
    };
    
    this.activeOperations.set(operation.id, operation);
    
    try {
      return await this.executeWithRetry(operation, policy);
    } finally {
      this.activeOperations.delete(operation.id);
    }
  }

  /**
   * Execute with exponential backoff
   */
  async executeWithExponentialBackoff<T>(
    fn: () => Promise<T>,
    options?: {
      maxRetries?: number;
      initialDelay?: number;
      maxDelay?: number;
      multiplier?: number;
    }
  ): Promise<T> {
    const policy: RetryPolicy = {
      shouldRetry: (error, attempt) => 
        attempt < (options?.maxRetries || this.config.maxRetries),
      getDelay: (attempt) => {
        const initialDelay = options?.initialDelay || this.config.initialDelay;
        const multiplier = options?.multiplier || this.config.backoffMultiplier;
        const maxDelay = options?.maxDelay || this.config.maxDelay;
        
        const delay = Math.min(
          initialDelay * Math.pow(multiplier, attempt - 1),
          maxDelay
        );
        
        return this.addJitter(delay);
      },
    };
    
    return this.execute(fn, policy);
  }

  /**
   * Execute with linear backoff
   */
  async executeWithLinearBackoff<T>(
    fn: () => Promise<T>,
    options?: {
      maxRetries?: number;
      delay?: number;
      increment?: number;
    }
  ): Promise<T> {
    const policy: RetryPolicy = {
      shouldRetry: (error, attempt) => 
        attempt < (options?.maxRetries || this.config.maxRetries),
      getDelay: (attempt) => {
        const delay = options?.delay || this.config.initialDelay;
        const increment = options?.increment || 1000;
        
        return this.addJitter(delay + (attempt - 1) * increment);
      },
    };
    
    return this.execute(fn, policy);
  }

  /**
   * Execute with custom retry policy
   */
  async executeWithPolicy<T>(
    fn: () => Promise<T>,
    policy: RetryPolicy
  ): Promise<T> {
    return this.execute(fn, policy);
  }

  /**
   * Get retry statistics
   */
  getStatistics(): RetryStats {
    this.checkBudgetWindow();
    
    return {
      totalAttempts: this.stats.totalAttempts,
      successfulAttempts: this.stats.successfulAttempts,
      failedAttempts: this.stats.failedAttempts,
      retriesUsed: this.stats.totalRetries,
      budgetRemaining: this.config.retryBudget - this.retryBudgetUsed,
      successRate: this.stats.totalAttempts > 0
        ? this.stats.successfulAttempts / this.stats.totalAttempts
        : 0,
    };
  }

  /**
   * Reset retry budget
   */
  resetBudget(): void {
    this.retryBudgetUsed = 0;
    this.budgetWindowStart = Date.now();
    this.emit('budget-reset');
  }

  /**
   * Get active operations
   */
  getActiveOperations(): Array<{
    id: string;
    attempt: number;
    duration: number;
  }> {
    return Array.from(this.activeOperations.entries()).map(([id, op]) => ({
      id,
      attempt: op.attempt,
      duration: Date.now() - op.startTime,
    }));
  }

  /**
   * Private methods
   */
  
  private async executeWithRetry<T>(
    operation: RetryOperation,
    customPolicy?: Partial<RetryPolicy>
  ): Promise<T> {
    const policy = this.createPolicy(customPolicy);
    
    while (true) {
      operation.attempt++;
      this.stats.totalAttempts++;
      
      try {
        const result = await operation.fn();
        
        this.stats.successfulAttempts++;
        this.emit('retry-success', {
          operationId: operation.id,
          attempts: operation.attempt,
          totalDelay: operation.delays.reduce((a, b) => a + b, 0),
        });
        
        return result;
      } catch (error) {
        operation.lastError = error as Error;
        
        // Check if should retry
        if (!this.shouldRetry(error as Error, operation.attempt, policy)) {
          this.stats.failedAttempts++;
          this.emit('retry-failure', {
            operationId: operation.id,
            attempts: operation.attempt,
            error,
          });
          throw error;
        }
        
        // Check retry budget
        if (!this.hasRetryBudget()) {
          this.emit('retry-budget-exceeded', {
            operationId: operation.id,
            budgetUsed: this.retryBudgetUsed,
          });
          throw new Error('Retry budget exceeded');
        }
        
        // Calculate delay
        const delay = policy.getDelay(operation.attempt);
        operation.delays.push(delay);
        
        // Emit retry event
        this.emit('retry-attempt', {
          operationId: operation.id,
          attempt: operation.attempt,
          delay,
          error,
        });
        
        // Call custom retry handler
        policy.onRetry?.(error as Error, operation.attempt);
        
        // Wait before retry
        await this.delay(delay);
        
        // Update stats
        this.stats.totalRetries++;
        this.retryBudgetUsed++;
      }
    }
  }

  private shouldRetry(
    error: Error,
    attempt: number,
    policy: RetryPolicy
  ): boolean {
    // Check custom policy
    if (!policy.shouldRetry(error, attempt)) {
      return false;
    }
    
    // Check non-retryable errors
    if (this.config.nonRetryableErrors?.length) {
      const errorName = error.name || error.constructor.name;
      if (this.config.nonRetryableErrors.includes(errorName)) {
        return false;
      }
    }
    
    // Check retryable errors if specified
    if (this.config.retryableErrors?.length) {
      const errorName = error.name || error.constructor.name;
      return this.config.retryableErrors.includes(errorName);
    }
    
    return true;
  }

  private createPolicy(customPolicy?: Partial<RetryPolicy>): RetryPolicy {
    return {
      shouldRetry: customPolicy?.shouldRetry || 
        ((error, attempt) => attempt <= this.config.maxRetries),
      getDelay: customPolicy?.getDelay || 
        ((attempt) => this.calculateExponentialDelay(attempt)),
      onRetry: customPolicy?.onRetry,
    };
  }

  private calculateExponentialDelay(attempt: number): number {
    const delay = Math.min(
      this.config.initialDelay * Math.pow(this.config.backoffMultiplier, attempt - 1),
      this.config.maxDelay
    );
    
    return this.addJitter(delay);
  }

  private addJitter(delay: number): number {
    const jitter = delay * this.config.jitterFactor;
    return delay + (Math.random() * 2 - 1) * jitter;
  }

  private hasRetryBudget(): boolean {
    this.checkBudgetWindow();
    return this.retryBudgetUsed < this.config.retryBudget;
  }

  private checkBudgetWindow(): void {
    const now = Date.now();
    if (now - this.budgetWindowStart >= this.config.budgetWindowMs) {
      this.resetBudget();
    }
  }

  private startBudgetResetTimer(): void {
    setInterval(() => {
      this.checkBudgetWindow();
    }, this.config.budgetWindowMs);
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private generateOperationId(): string {
    return `retry_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

// Predefined retry policies
export const RetryPolicies = {
  noRetry: (): RetryPolicy => ({
    shouldRetry: () => false,
    getDelay: () => 0,
  }),
  
  fixedDelay: (delay: number, maxRetries: number): RetryPolicy => ({
    shouldRetry: (error, attempt) => attempt <= maxRetries,
    getDelay: () => delay,
  }),
  
  exponentialBackoff: (config?: {
    initialDelay?: number;
    maxDelay?: number;
    multiplier?: number;
    maxRetries?: number;
  }): RetryPolicy => ({
    shouldRetry: (error, attempt) => attempt <= (config?.maxRetries || 3),
    getDelay: (attempt) => {
      const initialDelay = config?.initialDelay || 1000;
      const multiplier = config?.multiplier || 2;
      const maxDelay = config?.maxDelay || 30000;
      
      return Math.min(
        initialDelay * Math.pow(multiplier, attempt - 1),
        maxDelay
      );
    },
  }),
  
  linearBackoff: (config?: {
    initialDelay?: number;
    increment?: number;
    maxRetries?: number;
  }): RetryPolicy => ({
    shouldRetry: (error, attempt) => attempt <= (config?.maxRetries || 3),
    getDelay: (attempt) => {
      const initialDelay = config?.initialDelay || 1000;
      const increment = config?.increment || 1000;
      
      return initialDelay + (attempt - 1) * increment;
    },
  }),
};

export default RetryManager;