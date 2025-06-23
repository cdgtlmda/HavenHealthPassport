import { EventEmitter } from 'events';

interface ThrottleConfig {
  maxBandwidth: number; // bytes per second
  burstSize?: number; // allow burst up to this size
  measurementInterval?: number; // ms between measurements
}

interface ThrottleStats {
  bytesTransferred: number;
  startTime: number;
  currentBandwidth: number;
  averageBandwidth: number;
  throttleEvents: number;
}

export class BandwidthThrottler extends EventEmitter {
  private config: ThrottleConfig;
  private stats: ThrottleStats;
  private tokens: number;
  private lastTokenRefill: number;
  private measurementWindow: number[] = [];
  private measurementTimestamps: number[] = [];
  
  constructor(config: ThrottleConfig) {
    super();
    this.config = {
      burstSize: config.maxBandwidth * 2, // Allow 2 second burst by default
      measurementInterval: 1000, // 1 second default
      ...config,
    };
    
    this.tokens = this.config.burstSize!;
    this.lastTokenRefill = Date.now();
    
    this.stats = {
      bytesTransferred: 0,
      startTime: Date.now(),
      currentBandwidth: 0,
      averageBandwidth: 0,
      throttleEvents: 0,
    };
    
    // Start bandwidth measurement
    this.startMeasurement();
  }

  /**
   * Throttle data transfer
   */
  async throttle(bytes: number): Promise<void> {
    // Refill tokens based on time elapsed
    this.refillTokens();
    
    // Check if we have enough tokens
    if (this.tokens >= bytes) {
      // Immediate transfer allowed
      this.tokens -= bytes;
      this.recordTransfer(bytes);
      return;
    }
    
    // Need to throttle
    this.stats.throttleEvents++;
    this.emit('throttle', { bytes, tokensAvailable: this.tokens });
    
    // Calculate wait time
    const tokensNeeded = bytes - this.tokens;
    const waitTime = (tokensNeeded / this.config.maxBandwidth) * 1000;
    
    // Wait for tokens to be available
    await this.delay(waitTime);
    
    // Refill and consume tokens
    this.refillTokens();
    this.tokens -= bytes;
    this.recordTransfer(bytes);
  }

  /**
   * Create a throttled stream wrapper
   */
  createThrottledStream(stream: ReadableStream): ReadableStream {
    const throttler = this;
    
    return new ReadableStream({
      async start(controller) {
        const reader = stream.getReader();
        
        try {
          while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
              controller.close();
              break;
            }
            
            // Throttle the chunk
            await throttler.throttle(value.byteLength);
            controller.enqueue(value);
          }
        } catch (error) {
          controller.error(error);
        } finally {
          reader.releaseLock();
        }
      },
    });
  }

  /**
   * Create throttled fetch function
   */
  createThrottledFetch(): typeof fetch {
    const throttler = this;
    
    return async function throttledFetch(
      input: RequestInfo | URL,
      init?: RequestInit
    ): Promise<Response> {
      const response = await fetch(input, init);
      
      // Throttle response body
      if (response.body) {
        const throttledBody = throttler.createThrottledStream(response.body);
        
        return new Response(throttledBody, {
          status: response.status,
          statusText: response.statusText,
          headers: response.headers,
        });
      }
      
      return response;
    };
  }

  /**
   * Refill tokens based on elapsed time
   */
  private refillTokens(): void {
    const now = Date.now();
    const elapsed = (now - this.lastTokenRefill) / 1000; // seconds
    const tokensToAdd = elapsed * this.config.maxBandwidth;
    
    this.tokens = Math.min(
      this.tokens + tokensToAdd,
      this.config.burstSize!
    );
    
    this.lastTokenRefill = now;
  }

  /**
   * Record bytes transferred
   */
  private recordTransfer(bytes: number): void {
    const now = Date.now();
    
    this.stats.bytesTransferred += bytes;
    
    // Update measurement window
    this.measurementWindow.push(bytes);
    this.measurementTimestamps.push(now);
    
    // Clean old measurements
    const cutoff = now - this.config.measurementInterval!;
    while (
      this.measurementTimestamps.length > 0 &&
      this.measurementTimestamps[0] < cutoff
    ) {
      this.measurementWindow.shift();
      this.measurementTimestamps.shift();
    }
    
    // Calculate current bandwidth
    if (this.measurementWindow.length > 0) {
      const windowBytes = this.measurementWindow.reduce((a, b) => a + b, 0);
      const windowDuration = 
        (now - this.measurementTimestamps[0]) / 1000;
      this.stats.currentBandwidth = windowBytes / windowDuration;
    }
    
    // Calculate average bandwidth
    const totalDuration = (now - this.stats.startTime) / 1000;
    this.stats.averageBandwidth = 
      this.stats.bytesTransferred / totalDuration;
  }

  /**
   * Start bandwidth measurement interval
   */
  private startMeasurement(): void {
    setInterval(() => {
      this.emit('bandwidth-update', {
        current: this.stats.currentBandwidth,
        average: this.stats.averageBandwidth,
        throttleEvents: this.stats.throttleEvents,
      });
    }, this.config.measurementInterval!);
  }

  /**
   * Delay helper
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Get current stats
   */
  getStats(): ThrottleStats {
    return { ...this.stats };
  }

  /**
   * Reset stats
   */
  resetStats(): void {
    this.stats = {
      bytesTransferred: 0,
      startTime: Date.now(),
      currentBandwidth: 0,
      averageBandwidth: 0,
      throttleEvents: 0,
    };
    
    this.measurementWindow = [];
    this.measurementTimestamps = [];
  }

  /**
   * Update bandwidth limit
   */
  updateBandwidthLimit(newLimit: number): void {
    this.config.maxBandwidth = newLimit;
    this.config.burstSize = newLimit * 2;
    this.emit('bandwidth-limit-changed', newLimit);
  }

  /**
   * Create adaptive throttler that adjusts based on network conditions
   */
  static createAdaptiveThrottler(
    initialBandwidth: number = 1024 * 1024 // 1 MB/s default
  ): BandwidthThrottler {
    const throttler = new BandwidthThrottler({
      maxBandwidth: initialBandwidth,
    });
    
    // Monitor network conditions and adjust
    let slowTransfers = 0;
    let fastTransfers = 0;
    
    throttler.on('bandwidth-update', (stats) => {
      const targetUtilization = 0.8; // Use 80% of available bandwidth
      
      if (stats.throttleEvents > 5) {
        // Too many throttle events, reduce bandwidth
        slowTransfers++;
        if (slowTransfers > 3) {
          const newLimit = throttler.config.maxBandwidth * 0.9;
          throttler.updateBandwidthLimit(newLimit);
          slowTransfers = 0;
        }
      } else if (stats.current < throttler.config.maxBandwidth * 0.5) {
        // Under-utilizing bandwidth, increase limit
        fastTransfers++;
        if (fastTransfers > 3) {
          const newLimit = throttler.config.maxBandwidth * 1.1;
          throttler.updateBandwidthLimit(newLimit);
          fastTransfers = 0;
        }
      }
    });
    
    return throttler;
  }
}

export default BandwidthThrottler;