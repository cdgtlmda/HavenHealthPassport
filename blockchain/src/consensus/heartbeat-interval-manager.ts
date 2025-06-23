/**
 * Heartbeat Interval Configuration Manager
 * Haven Health Passport - Raft Consensus
 *
 * Manages heartbeat interval settings for leader-follower communication
 */

export interface HeartbeatConfig {
  interval: number;
  jitterEnabled: boolean;
  jitterRange: number;
  adaptiveEnabled: boolean;
  minInterval: number;
  maxInterval: number;
}

export interface FollowerTimeoutConfig {
  baseMultiplier: number;
  minTimeout: number;
  maxTimeout: number;
  gracePeriod: number;
}

export interface HeartbeatMetrics {
  intervalCurrent: number;
  successRate: number;
  lastHeartbeatTime: Map<string, number>;
  failureCount: number;
}

export class HeartbeatIntervalManager {
  private config: HeartbeatConfig;
  private followerTimeout: FollowerTimeoutConfig;
  private metrics: HeartbeatMetrics;

  constructor() {
    this.config = this.initializeDefaultConfig();
    this.followerTimeout = this.initializeTimeoutConfig();
    this.metrics = this.initializeMetrics();
  }

  /**
   * Initialize default heartbeat configuration
   */
  private initializeDefaultConfig(): HeartbeatConfig {
    return {
      interval: 500,          // 500ms base interval
      jitterEnabled: true,
      jitterRange: 50,        // +/- 50ms jitter
      adaptiveEnabled: true,      minInterval: 100,       // 100ms minimum
      maxInterval: 5000       // 5 seconds maximum
    };
  }

  /**
   * Initialize follower timeout configuration
   */
  private initializeTimeoutConfig(): FollowerTimeoutConfig {
    return {
      baseMultiplier: 10,     // Timeout = 10 * heartbeat interval
      minTimeout: 2000,       // 2 seconds minimum
      maxTimeout: 10000,      // 10 seconds maximum
      gracePeriod: 500        // 500ms grace period
    };
  }

  /**
   * Initialize metrics
   */
  private initializeMetrics(): HeartbeatMetrics {
    return {
      intervalCurrent: this.config.interval,
      successRate: 1.0,
      lastHeartbeatTime: new Map(),
      failureCount: 0
    };
  }

  /**
   * Calculate actual heartbeat interval with jitter
   */
  public getNextHeartbeatInterval(): number {
    let interval = this.config.interval;

    if (this.config.jitterEnabled) {
      const jitter = (Math.random() - 0.5) * 2 * this.config.jitterRange;
      interval += jitter;
    }

    return Math.max(this.config.minInterval,
                   Math.min(this.config.maxInterval, interval));
  }

  /**
   * Calculate follower timeout based on current interval
   */
  public getFollowerTimeout(): number {
    const baseTimeout = this.metrics.intervalCurrent * this.followerTimeout.baseMultiplier;    const timeout = baseTimeout + this.followerTimeout.gracePeriod;

    return Math.max(this.followerTimeout.minTimeout,
                   Math.min(this.followerTimeout.maxTimeout, timeout));
  }

  /**
   * Adapt heartbeat interval based on network conditions
   */
  public adaptInterval(latencyMs: number, successRate: number): void {
    if (!this.config.adaptiveEnabled) return;

    // Adjust based on latency
    if (latencyMs > 100) {
      // Increase interval if network is slow
      this.config.interval = Math.min(
        this.config.interval * 1.1,
        this.config.maxInterval
      );
    } else if (successRate > 0.98 && latencyMs < 50) {
      // Decrease interval if network is fast and stable
      this.config.interval = Math.max(
        this.config.interval * 0.9,
        this.config.minInterval
      );
    }

    this.metrics.intervalCurrent = this.config.interval;
  }

  /**
   * Record heartbeat success
   */
  public recordHeartbeatSuccess(followerId: string): void {
    this.metrics.lastHeartbeatTime.set(followerId, Date.now());
    this.updateSuccessRate(true);
  }

  /**
   * Record heartbeat failure
   */
  public recordHeartbeatFailure(followerId: string): void {
    this.metrics.failureCount++;
    this.updateSuccessRate(false);
  }

  /**
   * Update success rate with exponential moving average
   */
  private updateSuccessRate(success: boolean): void {    const alpha = 0.1; // Smoothing factor
    const value = success ? 1.0 : 0.0;
    this.metrics.successRate = alpha * value + (1 - alpha) * this.metrics.successRate;
  }

  /**
   * Get current configuration
   */
  public getConfig(): HeartbeatConfig {
    return { ...this.config };
  }

  /**
   * Get current metrics
   */
  public getMetrics(): HeartbeatMetrics {
    return {
      ...this.metrics,
      lastHeartbeatTime: new Map(this.metrics.lastHeartbeatTime)
    };
  }

  /**
   * Validate heartbeat configuration
   */
  public validateConfig(): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (this.config.interval < this.config.minInterval) {
      errors.push(`Interval ${this.config.interval}ms is below minimum ${this.config.minInterval}ms`);
    }

    if (this.config.interval > this.config.maxInterval) {
      errors.push(`Interval ${this.config.interval}ms exceeds maximum ${this.config.maxInterval}ms`);
    }

    if (this.config.jitterRange > this.config.interval / 2) {
      errors.push('Jitter range should not exceed half of interval');
    }

    const timeout = this.getFollowerTimeout();
    if (timeout < this.config.interval * 3) {
      errors.push('Follower timeout should be at least 3x heartbeat interval');
    }

    return { valid: errors.length === 0, errors };
  }
}

// Export singleton instance
export const heartbeatManager = new HeartbeatIntervalManager();
