/**
 * Request Throttling
 * Advanced request throttling and queue management
 */

import { Request, Response, NextFunction } from 'express';
import { EventEmitter } from 'events';
import PQueue from 'p-queue';

/**
 * Throttle configuration
 */
export interface ThrottleConfig {
  concurrency: number;        // Max concurrent requests
  interval: number;           // Time interval in ms
  intervalCap: number;        // Max requests per interval
  queueSize?: number;         // Max queue size
  timeout?: number;           // Request timeout
  priority?: (req: Request) => number;  // Priority function
  onQueued?: (req: Request, position: number) => void;
  onDequeued?: (req: Request) => void;
  onDropped?: (req: Request, reason: string) => void;
  onTimeout?: (req: Request) => void;
  adaptiveThrottling?: boolean;  // Enable adaptive throttling
  metrics?: ThrottleMetrics;      // Metrics collector
}

/**
 * Throttle metrics
 */
export class ThrottleMetrics extends EventEmitter {
  private metrics = {
    totalRequests: 0,
    queuedRequests: 0,
    completedRequests: 0,
    droppedRequests: 0,
    timeoutRequests: 0,
    avgQueueTime: 0,
    avgProcessingTime: 0,
    currentQueueSize: 0,
    currentConcurrency: 0
  };

  record(event: string, data?: any): void {
    switch (event) {
      case 'request':
        this.metrics.totalRequests++;
        break;
      case 'queued':
        this.metrics.queuedRequests++;
        this.metrics.currentQueueSize = data.queueSize;
        break;
      case 'dequeued':
        this.metrics.currentQueueSize = data.queueSize;
        break;
      case 'completed':
        this.metrics.completedRequests++;
        this.updateAvgProcessingTime(data.processingTime);
        break;
      case 'dropped':
        this.metrics.droppedRequests++;
        break;
      case 'timeout':
        this.metrics.timeoutRequests++;
        break;
    }

    this.emit('metric', event, this.metrics);
  }

  private updateAvgProcessingTime(time: number): void {
    const total = this.metrics.completedRequests;
    this.metrics.avgProcessingTime =
      (this.metrics.avgProcessingTime * (total - 1) + time) / total;
  }

  getMetrics() {
    return { ...this.metrics };
  }

  reset(): void {
    Object.keys(this.metrics).forEach(key => {
      this.metrics[key as keyof typeof this.metrics] = 0;
    });
  }
}

/**
 * Request throttler
 */
export class RequestThrottler {
  private config: ThrottleConfig;
  private queue: PQueue;
  private requestMap: Map<string, { req: Request; res: Response; timer?: NodeJS.Timeout }> = new Map();
  private metrics: ThrottleMetrics;

  constructor(config: ThrottleConfig) {
    this.config = {
      queueSize: 1000,
      timeout: 30000,  // 30 seconds default
      adaptiveThrottling: false,
      ...config
    };

    this.metrics = this.config.metrics || new ThrottleMetrics();

    this.queue = new PQueue({
      concurrency: this.config.concurrency,
      interval: this.config.interval,
      intervalCap: this.config.intervalCap,
      autoStart: true
    });

    // Monitor queue size
    this.queue.on('add', () => {
      if (this.queue.size > this.config.queueSize!) {
        // Queue is full, need to drop oldest request
        this.dropOldestRequest('Queue full');
      }
    });

    // Setup adaptive throttling if enabled
    if (this.config.adaptiveThrottling) {
      this.setupAdaptiveThrottling();
    }
  }

  /**
   * Express middleware
   */
  middleware() {
    return async (req: Request, res: Response, next: NextFunction) => {
      const requestId = this.generateRequestId(req);
      const priority = this.config.priority ? this.config.priority(req) : 0;

      this.metrics.record('request');

      // Check if queue is full
      if (this.queue.size >= this.config.queueSize!) {
        this.metrics.record('dropped', { reason: 'Queue full' });

        if (this.config.onDropped) {
          this.config.onDropped(req, 'Queue full');
        }

        return res.status(503).json({
          error: 'Service temporarily unavailable',
          reason: 'Server is overloaded, please try again later'
        });
      }

      // Store request info
      this.requestMap.set(requestId, { req, res });

      // Set timeout
      if (this.config.timeout) {
        const timer = setTimeout(() => {
          this.handleTimeout(requestId);
        }, this.config.timeout);

        this.requestMap.get(requestId)!.timer = timer;
      }

      // Add to queue
      try {
        await this.queue.add(
          async () => {
            const entry = this.requestMap.get(requestId);
            if (!entry) return; // Request was dropped or timed out

            const { req, res, timer } = entry;

            // Clear timeout
            if (timer) clearTimeout(timer);

            // Notify dequeued
            if (this.config.onDequeued) {
              this.config.onDequeued(req);
            }

            this.metrics.record('dequeued', { queueSize: this.queue.size });

            // Process request
            const startTime = Date.now();

            // Continue with request processing
            await new Promise<void>((resolve) => {
              const originalEnd = res.end;
              res.end = function(...args: any[]) {
                const processingTime = Date.now() - startTime;
                this.metrics.record('completed', { processingTime });

                // Clean up
                this.requestMap.delete(requestId);

                // Call original end
                const result = originalEnd.apply(this, args);
                resolve();
                return result;
              }.bind(this);

              next();
            });
          },
          { priority }
        );

        // Notify queued
        const position = this.queue.size;
        if (this.config.onQueued) {
          this.config.onQueued(req, position);
        }

        this.metrics.record('queued', { queueSize: this.queue.size });

        // Set queue position header
        res.setHeader('X-Queue-Position', position.toString());
        res.setHeader('X-Queue-Size', this.queue.size.toString());

      } catch (error) {
        // Clean up on error
        const entry = this.requestMap.get(requestId);
        if (entry?.timer) clearTimeout(entry.timer);
        this.requestMap.delete(requestId);

        console.error('Throttling error:', error);
        res.status(500).json({ error: 'Internal server error' });
      }
    };
  }

  /**
   * Generate unique request ID
   */
  private generateRequestId(req: Request): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Handle request timeout
   */
  private handleTimeout(requestId: string): void {
    const entry = this.requestMap.get(requestId);
    if (!entry) return;

    const { req, res } = entry;

    this.metrics.record('timeout');

    if (this.config.onTimeout) {
      this.config.onTimeout(req);
    }

    // Remove from map
    this.requestMap.delete(requestId);

    // Send timeout response if not already sent
    if (!res.headersSent) {
      res.status(408).json({
        error: 'Request timeout',
        message: 'Request took too long to process'
      });
    }
  }

  /**
   * Drop oldest request from queue
   */
  private dropOldestRequest(reason: string): void {
    // Find oldest request
    let oldestId: string | null = null;
    let oldestTime = Infinity;

    for (const [id, entry] of this.requestMap.entries()) {
      const requestTime = parseInt(id.split('-')[0]);
      if (requestTime < oldestTime) {
        oldestTime = requestTime;
        oldestId = id;
      }
    }

    if (oldestId) {
      const entry = this.requestMap.get(oldestId);
      if (entry) {
        const { req, res, timer } = entry;

        // Clear timeout
        if (timer) clearTimeout(timer);

        // Remove from map
        this.requestMap.delete(oldestId);

        // Notify dropped
        this.metrics.record('dropped', { reason });

        if (this.config.onDropped) {
          this.config.onDropped(req, reason);
        }

        // Send response if not already sent
        if (!res.headersSent) {
          res.status(503).json({
            error: 'Service unavailable',
            reason: 'Request was dropped due to overload'
          });
        }
      }
    }
  }

  /**
   * Setup adaptive throttling
   */
  private setupAdaptiveThrottling(): void {
    setInterval(() => {
      const metrics = this.metrics.getMetrics();

      // Adjust concurrency based on metrics
      if (metrics.avgProcessingTime > 5000 && this.queue.concurrency > 1) {
        // Reduce concurrency if processing is slow
        this.queue.concurrency = Math.max(1, this.queue.concurrency - 1);
      } else if (metrics.avgProcessingTime < 1000 &&
                 metrics.droppedRequests === 0 &&
                 this.queue.concurrency < this.config.concurrency) {
        // Increase concurrency if processing is fast
        this.queue.concurrency = Math.min(
          this.config.concurrency,
          this.queue.concurrency + 1
        );
      }

      // Emit metrics
      this.metrics.emit('adaptive', {
        concurrency: this.queue.concurrency,
        metrics
      });
    }, 10000); // Adjust every 10 seconds
  }

  /**
   * Get current queue status
   */
  getStatus() {
    return {
      queueSize: this.queue.size,
      pending: this.queue.pending,
      concurrency: this.queue.concurrency,
      isPaused: this.queue.isPaused,
      metrics: this.metrics.getMetrics()
    };
  }

  /**
   * Pause processing
   */
  pause(): void {
    this.queue.pause();
  }

  /**
   * Resume processing
   */
  resume(): void {
    this.queue.start();
  }

  /**
   * Clear queue
   */
  clear(): void {
    this.queue.clear();

    // Send 503 to all queued requests
    for (const [id, entry] of this.requestMap.entries()) {
      const { res, timer } = entry;

      if (timer) clearTimeout(timer);

      if (!res.headersSent) {
        res.status(503).json({
          error: 'Service unavailable',
          reason: 'Queue was cleared'
        });
      }
    }

    this.requestMap.clear();
  }
}

/**
 * Circuit breaker for request handling
 */
export class CircuitBreaker {
  private state: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';
  private failures: number = 0;
  private successes: number = 0;
  private nextAttempt: number = Date.now();
  private config: {
    threshold: number;
    timeout: number;
    resetTimeout: number;
    monitoringPeriod: number;
    onOpen?: () => void;
    onClose?: () => void;
    onHalfOpen?: () => void;
  };

  constructor(config: Partial<CircuitBreaker['config']> = {}) {
    this.config = {
      threshold: 5,              // 5 failures to open
      timeout: 60000,            // 1 minute timeout
      resetTimeout: 30000,       // 30 seconds before half-open
      monitoringPeriod: 60000,   // 1 minute monitoring period
      ...config
    };
  }

  middleware() {
    return async (req: Request, res: Response, next: NextFunction) => {
      if (!this.canRequest()) {
        return res.status(503).json({
          error: 'Service unavailable',
          reason: 'Circuit breaker is open',
          retryAfter: Math.ceil((this.nextAttempt - Date.now()) / 1000)
        });
      }

      // Monitor the request
      const originalEnd = res.end;
      const startTime = Date.now();

      res.end = function(...args: any[]) {
        const duration = Date.now() - startTime;
        const success = res.statusCode < 500;

        if (success) {
          this.onSuccess();
        } else {
          this.onFailure();
        }

        return originalEnd.apply(this, args);
      }.bind(this);

      next();
    };
  }

  private canRequest(): boolean {
    if (this.state === 'CLOSED') return true;

    if (this.state === 'OPEN') {
      if (Date.now() > this.nextAttempt) {
        this.state = 'HALF_OPEN';
        if (this.config.onHalfOpen) this.config.onHalfOpen();
        return true;
      }
      return false;
    }

    // HALF_OPEN state
    return true;
  }

  private onSuccess(): void {
    this.failures = 0;

    if (this.state === 'HALF_OPEN') {
      this.successes++;
      if (this.successes >= this.config.threshold) {
        this.close();
      }
    }
  }

  private onFailure(): void {
    this.failures++;
    this.successes = 0;

    if (this.failures >= this.config.threshold) {
      this.open();
    }
  }

  private open(): void {
    this.state = 'OPEN';
    this.nextAttempt = Date.now() + this.config.resetTimeout;
    if (this.config.onOpen) this.config.onOpen();
  }

  private close(): void {
    this.state = 'CLOSED';
    this.failures = 0;
    this.successes = 0;
    if (this.config.onClose) this.config.onClose();
  }

  getState() {
    return {
      state: this.state,
      failures: this.failures,
      successes: this.successes,
      nextAttempt: this.state === 'OPEN' ? new Date(this.nextAttempt) : null
    };
  }
}

/**
 * Backpressure handler
 */
export class BackpressureHandler {
  private pressure: number = 0;
  private config: {
    highWaterMark: number;
    lowWaterMark: number;
    checkInterval: number;
    onHighPressure?: () => void;
    onLowPressure?: () => void;
  };

  constructor(config: Partial<BackpressureHandler['config']> = {}) {
    this.config = {
      highWaterMark: 100,
      lowWaterMark: 50,
      checkInterval: 1000,
      ...config
    };

    this.startMonitoring();
  }

  middleware() {
    return (req: Request, res: Response, next: NextFunction) => {
      if (this.pressure > this.config.highWaterMark) {
        return res.status(503).json({
          error: 'Service unavailable',
          reason: 'System under high load',
          backpressure: this.pressure
        });
      }

      this.pressure++;

      const originalEnd = res.end;
      res.end = function(...args: any[]) {
        this.pressure = Math.max(0, this.pressure - 1);
        return originalEnd.apply(this, args);
      }.bind(this);

      next();
    };
  }

  private startMonitoring(): void {
    setInterval(() => {
      if (this.pressure > this.config.highWaterMark && this.config.onHighPressure) {
        this.config.onHighPressure();
      } else if (this.pressure < this.config.lowWaterMark && this.config.onLowPressure) {
        this.config.onLowPressure();
      }
    }, this.config.checkInterval);
  }

  getPressure(): number {
    return this.pressure;
  }
}

/**
 * Throttle strategies
 */
export const ThrottleStrategies = {
  // Fixed window
  fixedWindow: (requests: number, window: number) => ({
    concurrency: Infinity,
    interval: window,
    intervalCap: requests
  }),

  // Sliding window
  slidingWindow: (requests: number, window: number) => ({
    concurrency: Infinity,
    interval: window / requests,
    intervalCap: 1
  }),

  // Token bucket
  tokenBucket: (capacity: number, refillRate: number) => ({
    concurrency: capacity,
    interval: 1000 / refillRate,
    intervalCap: 1
  }),

  // Leaky bucket
  leakyBucket: (capacity: number, leakRate: number) => ({
    concurrency: 1,
    interval: 1000 / leakRate,
    intervalCap: 1,
    queueSize: capacity
  }),

  // Adaptive
  adaptive: (minConcurrency: number, maxConcurrency: number) => ({
    concurrency: maxConcurrency,
    interval: 100,
    intervalCap: 10,
    adaptiveThrottling: true
  })
};

/**
 * Healthcare-specific throttle configurations
 */
export const HealthcareThrottleConfigs = {
  // Patient data access
  patientData: {
    concurrency: 10,
    interval: 1000,
    intervalCap: 20,
    priority: (req: Request) => {
      // Emergency requests get priority
      return req.headers['x-emergency'] === 'true' ? 10 : 0;
    }
  },

  // Lab results processing
  labResults: {
    concurrency: 5,
    interval: 1000,
    intervalCap: 10,
    queueSize: 100,
    timeout: 60000  // 1 minute for large files
  },

  // Prescription validation
  prescriptions: {
    concurrency: 3,
    interval: 1000,
    intervalCap: 5,
    timeout: 30000
  },

  // Bulk operations
  bulkOperations: {
    concurrency: 1,
    interval: 5000,
    intervalCap: 1,
    queueSize: 10,
    timeout: 300000  // 5 minutes
  }
};

// Export convenience functions
export const createThrottler = (config: ThrottleConfig) => new RequestThrottler(config);
export const createCircuitBreaker = (config?: any) => new CircuitBreaker(config);
export const createBackpressureHandler = (config?: any) => new BackpressureHandler(config);
