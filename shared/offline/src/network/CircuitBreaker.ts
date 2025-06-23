import { EventEmitter } from 'events';

export enum CircuitState {
  CLOSED = 'CLOSED',
  OPEN = 'OPEN',
  HALF_OPEN = 'HALF_OPEN',
}

interface CircuitBreakerConfig {
  failureThreshold: number;
  resetTimeout: number;
  successThreshold: number;
  timeout: number;
  volumeThreshold: number;
  errorThresholdPercentage: number;
  rollingWindowSize: number;
}

interface CircuitStats {
  state: CircuitState;
  failures: number;
  successes: number;
  totalRequests: number;
  lastFailureTime?: number;
  lastSuccessTime?: number;
  consecutiveFailures: number;
  consecutiveSuccesses: number;
  errorRate: number;
}

interface RequestResult {
  success: boolean;
  duration: number;
  error?: Error;
  timestamp: number;
}

export class CircuitBreaker extends EventEmitter {
  private config: CircuitBreakerConfig;
  private state: CircuitState = CircuitState.CLOSED;
  private failures = 0;
  private successes = 0;
  private consecutiveFailures = 0;
  private consecutiveSuccesses = 0;
  private lastFailureTime?: number;
  private lastSuccessTime?: number;
  private nextAttempt = 0;
  private requestHistory: RequestResult[] = [];
  private halfOpenTestInProgress = false;
  
  constructor(config: Partial<CircuitBreakerConfig> = {}) {
    super();
    this.config = {
      failureThreshold: 5,
      resetTimeout: 60000, // 1 minute
      successThreshold: 3,
      timeout: 10000, // 10 seconds
      volumeThreshold: 10,
      errorThresholdPercentage: 50,
      rollingWindowSize: 60000, // 1 minute window
      ...config,
    };
  }

  /**
   * Execute function with circuit breaker protection
   */
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (!this.canExecute()) {
      throw new Error(`Circuit breaker is OPEN. Next attempt at ${new Date(this.nextAttempt).toISOString()}`);
    }
    
    const startTime = Date.now();
    
    try {
      // Set timeout
      const result = await this.executeWithTimeout(fn, this.config.timeout);
      
      // Record success
      this.recordSuccess(Date.now() - startTime);
      
      return result;
    } catch (error) {
      // Record failure
      this.recordFailure(Date.now() - startTime, error as Error);
      
      throw error;
    }
  }

  /**
   * Get current circuit state
   */
  getState(): CircuitState {
    return this.state;
  }

  /**
   * Get circuit statistics
   */
  getStatistics(): CircuitStats {
    this.updateRequestHistory();
    const errorRate = this.calculateErrorRate();
    
    return {
      state: this.state,
      failures: this.failures,
      successes: this.successes,
      totalRequests: this.failures + this.successes,
      lastFailureTime: this.lastFailureTime,
      lastSuccessTime: this.lastSuccessTime,
      consecutiveFailures: this.consecutiveFailures,
      consecutiveSuccesses: this.consecutiveSuccesses,
      errorRate,
    };
  }

  /**
   * Force open the circuit
   */
  open(): void {
    this.transition(CircuitState.OPEN);
  }

  /**
   * Force close the circuit
   */
  close(): void {
    this.transition(CircuitState.CLOSED);
  }

  /**
   * Reset the circuit breaker
   */
  reset(): void {
    this.failures = 0;
    this.successes = 0;
    this.consecutiveFailures = 0;
    this.consecutiveSuccesses = 0;
    this.lastFailureTime = undefined;
    this.lastSuccessTime = undefined;
    this.requestHistory = [];
    this.nextAttempt = 0;
    this.transition(CircuitState.CLOSED);
  }

  /**
   * Private methods
   */
  
  private canExecute(): boolean {
    if (this.state === CircuitState.CLOSED) {
      return true;
    }
    
    if (this.state === CircuitState.OPEN) {
      // Check if enough time has passed to try again
      if (Date.now() >= this.nextAttempt) {
        this.transition(CircuitState.HALF_OPEN);
        return true;
      }
      return false;
    }
    
    // HALF_OPEN state
    // Allow one request at a time in half-open state
    if (this.halfOpenTestInProgress) {
      return false;
    }
    
    this.halfOpenTestInProgress = true;
    return true;
  }

  private recordSuccess(duration: number): void {
    const result: RequestResult = {
      success: true,
      duration,
      timestamp: Date.now(),
    };
    
    this.requestHistory.push(result);
    this.successes++;
    this.consecutiveSuccesses++;
    this.consecutiveFailures = 0;
    this.lastSuccessTime = Date.now();
    
    if (this.state === CircuitState.HALF_OPEN) {
      this.halfOpenTestInProgress = false;
      
      if (this.consecutiveSuccesses >= this.config.successThreshold) {
        // Circuit has recovered
        this.transition(CircuitState.CLOSED);
      }
    }
    
    this.emit('request-success', result);
  }

  private recordFailure(duration: number, error: Error): void {
    const result: RequestResult = {
      success: false,
      duration,
      error,
      timestamp: Date.now(),
    };
    
    this.requestHistory.push(result);
    this.failures++;
    this.consecutiveFailures++;
    this.consecutiveSuccesses = 0;
    this.lastFailureTime = Date.now();
    
    if (this.state === CircuitState.HALF_OPEN) {
      this.halfOpenTestInProgress = false;
      // Failed in half-open, go back to open
      this.transition(CircuitState.OPEN);
    } else if (this.state === CircuitState.CLOSED) {
      // Check if we should open the circuit
      if (this.shouldOpen()) {
        this.transition(CircuitState.OPEN);
      }
    }
    
    this.emit('request-failure', result);
  }

  private shouldOpen(): boolean {
    // Check volume threshold
    this.updateRequestHistory();
    const recentRequests = this.requestHistory.length;
    
    if (recentRequests < this.config.volumeThreshold) {
      return false;
    }
    
    // Check failure threshold
    if (this.consecutiveFailures >= this.config.failureThreshold) {
      return true;
    }
    
    // Check error rate
    const errorRate = this.calculateErrorRate();
    return errorRate >= this.config.errorThresholdPercentage;
  }

  private transition(newState: CircuitState): void {
    const oldState = this.state;
    this.state = newState;
    
    if (newState === CircuitState.OPEN) {
      this.nextAttempt = Date.now() + this.config.resetTimeout;
    }
    
    if (newState === CircuitState.CLOSED) {
      this.consecutiveFailures = 0;
      this.consecutiveSuccesses = 0;
    }
    
    this.emit('state-change', { from: oldState, to: newState });
  }

  private updateRequestHistory(): void {
    const cutoff = Date.now() - this.config.rollingWindowSize;
    this.requestHistory = this.requestHistory.filter(r => r.timestamp > cutoff);
  }

  private calculateErrorRate(): number {
    if (this.requestHistory.length === 0) return 0;
    
    const failures = this.requestHistory.filter(r => !r.success).length;
    return (failures / this.requestHistory.length) * 100;
  }

  private async executeWithTimeout<T>(
    fn: () => Promise<T>,
    timeout: number
  ): Promise<T> {
    return Promise.race([
      fn(),
      new Promise<T>((_, reject) => 
        setTimeout(() => reject(new Error('Request timeout')), timeout)
      ),
    ]);
  }
}

// Factory function for common circuit breaker patterns
export function createCircuitBreaker(
  name: string,
  options?: Partial<CircuitBreakerConfig>
): CircuitBreaker {
  const defaultConfigs: Record<string, Partial<CircuitBreakerConfig>> = {
    aggressive: {
      failureThreshold: 3,
      resetTimeout: 30000,
      errorThresholdPercentage: 30,
    },
    standard: {
      failureThreshold: 5,
      resetTimeout: 60000,
      errorThresholdPercentage: 50,
    },
    lenient: {
      failureThreshold: 10,
      resetTimeout: 120000,
      errorThresholdPercentage: 70,
    },
  };
  
  const config = {
    ...(defaultConfigs[name] || defaultConfigs.standard),
    ...options,
  };
  
  return new CircuitBreaker(config);
}

export default CircuitBreaker;