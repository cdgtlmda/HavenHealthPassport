import { EventEmitter } from 'events';

interface BatchRequest {
  id: string;
  url: string;
  method: string;
  headers?: Record<string, string>;
  body?: any;
  priority: number;
  timestamp: number;
  retryCount: number;
  callback?: (response: any, error?: Error) => void;
}

interface BatchConfig {
  maxBatchSize: number;
  batchInterval: number;
  maxRetries: number;
  enableCompression: boolean;
  enableCoalescing: boolean;
  priorityLevels: number;
}

interface BatchResponse {
  batchId: string;
  responses: Array<{
    requestId: string;
    status: number;
    data?: any;
    error?: string;
  }>;
  timestamp: number;
}

export class RequestBatcher extends EventEmitter {
  private config: BatchConfig;
  private requestQueue: Map<number, BatchRequest[]> = new Map();
  private batchTimer?: NodeJS.Timeout;
  private activeBatches: Map<string, BatchRequest[]> = new Map();
  private isProcessing = false;
  
  constructor(config: Partial<BatchConfig> = {}) {
    super();
    this.config = {
      maxBatchSize: 50,
      batchInterval: 100, // ms
      maxRetries: 3,
      enableCompression: true,
      enableCoalescing: true,
      priorityLevels: 3,
      ...config,
    };
    
    // Initialize priority queues
    for (let i = 0; i < this.config.priorityLevels; i++) {
      this.requestQueue.set(i, []);
    }
  }

  /**
   * Add request to batch
   */
  addRequest(
    url: string,
    options: {
      method?: string;
      headers?: Record<string, string>;
      body?: any;
      priority?: number;
    } = {}
  ): Promise<any> {
    return new Promise((resolve, reject) => {
      const request: BatchRequest = {
        id: this.generateRequestId(),
        url,
        method: options.method || 'GET',
        headers: options.headers,
        body: options.body,
        priority: Math.min(options.priority || 1, this.config.priorityLevels - 1),
        timestamp: Date.now(),
        retryCount: 0,
        callback: (response, error) => {
          if (error) {
            reject(error);
          } else {
            resolve(response);
          }
        },
      };
      
      // Add to appropriate priority queue
      const queue = this.requestQueue.get(request.priority) || [];
      
      // Check for request coalescing
      if (this.config.enableCoalescing) {
        const existing = this.findCoalescableRequest(queue, request);
        if (existing) {
          // Attach callback to existing request
          const existingCallback = existing.callback;
          existing.callback = (response, error) => {
            existingCallback?.(response, error);
            request.callback?.(response, error);
          };
          this.emit('request-coalesced', { original: existing.id, new: request.id });
          return;
        }
      }
      
      queue.push(request);
      
      // Start batch timer
      this.scheduleBatch();
      
      this.emit('request-added', request);
    });
  }

  /**
   * Force process current batch
   */
  async flush(): Promise<void> {
    if (this.batchTimer) {
      clearTimeout(this.batchTimer);
      this.batchTimer = undefined;
    }
    
    await this.processBatch();
  }

  /**
   * Get queue statistics
   */
  getStatistics() {
    let totalQueued = 0;
    const queuedByPriority: Record<number, number> = {};
    
    for (const [priority, queue] of this.requestQueue.entries()) {
      queuedByPriority[priority] = queue.length;
      totalQueued += queue.length;
    }
    
    return {
      totalQueued,
      queuedByPriority,
      activeBatches: this.activeBatches.size,
      isProcessing: this.isProcessing,
    };
  }

  /**
   * Private methods
   */
  
  private scheduleBatch(): void {
    if (this.batchTimer) return;
    
    this.batchTimer = setTimeout(() => {
      this.batchTimer = undefined;
      this.processBatch();
    }, this.config.batchInterval);
  }

  private async processBatch(): Promise<void> {
    if (this.isProcessing) return;
    
    const batch = this.collectBatch();
    if (batch.length === 0) return;
    
    this.isProcessing = true;
    const batchId = this.generateBatchId();
    this.activeBatches.set(batchId, batch);
    
    try {
      const response = await this.sendBatch(batchId, batch);
      this.handleBatchResponse(batchId, batch, response);
    } catch (error) {
      this.handleBatchError(batchId, batch, error as Error);
    } finally {
      this.activeBatches.delete(batchId);
      this.isProcessing = false;
      
      // Process next batch if requests pending
      if (this.hasPendingRequests()) {
        this.scheduleBatch();
      }
    }
  }

  private collectBatch(): BatchRequest[] {
    const batch: BatchRequest[] = [];
    
    // Collect requests by priority
    for (let priority = this.config.priorityLevels - 1; priority >= 0; priority--) {
      const queue = this.requestQueue.get(priority) || [];
      
      while (queue.length > 0 && batch.length < this.config.maxBatchSize) {
        batch.push(queue.shift()!);
      }
      
      if (batch.length >= this.config.maxBatchSize) break;
    }
    
    return batch;
  }

  private async sendBatch(batchId: string, requests: BatchRequest[]): Promise<BatchResponse> {
    const batchPayload = {
      batchId,
      requests: requests.map(req => ({
        id: req.id,
        url: req.url,
        method: req.method,
        headers: req.headers,
        body: req.body,
      })),
    };
    
    // Compress if enabled
    let body = JSON.stringify(batchPayload);
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    
    if (this.config.enableCompression) {
      // In real implementation, would use compression library
      headers['Content-Encoding'] = 'gzip';
    }
    
    // Send batch request
    const response = await fetch('/api/batch', {
      method: 'POST',
      headers,
      body,
    });
    
    if (!response.ok) {
      throw new Error(`Batch request failed: ${response.statusText}`);
    }
    
    return response.json();
  }

  private handleBatchResponse(
    batchId: string,
    requests: BatchRequest[],
    response: BatchResponse
  ): void {
    const responseMap = new Map(
      response.responses.map(r => [r.requestId, r])
    );
    
    for (const request of requests) {
      const result = responseMap.get(request.id);
      
      if (result) {
        if (result.error) {
          request.callback?.(null, new Error(result.error));
        } else {
          request.callback?.(result.data);
        }
      } else {
        // No response for this request
        request.callback?.(null, new Error('No response received'));
      }
    }
    
    this.emit('batch-completed', { batchId, requestCount: requests.length });
  }

  private handleBatchError(
    batchId: string,
    requests: BatchRequest[],
    error: Error
  ): void {
    // Retry individual requests
    for (const request of requests) {
      if (request.retryCount < this.config.maxRetries) {
        request.retryCount++;
        
        // Re-queue with same priority
        const queue = this.requestQueue.get(request.priority) || [];
        queue.push(request);
        
        this.emit('request-retry', { requestId: request.id, attempt: request.retryCount });
      } else {
        // Max retries exceeded
        request.callback?.(null, error);
        this.emit('request-failed', { requestId: request.id, error });
      }
    }
    
    this.emit('batch-error', { batchId, error });
    
    // Schedule retry
    if (this.hasPendingRequests()) {
      this.scheduleBatch();
    }
  }

  private findCoalescableRequest(
    queue: BatchRequest[],
    newRequest: BatchRequest
  ): BatchRequest | null {
    if (newRequest.method !== 'GET') return null;
    
    return queue.find(req => 
      req.method === 'GET' &&
      req.url === newRequest.url &&
      JSON.stringify(req.headers) === JSON.stringify(newRequest.headers)
    ) || null;
  }

  private hasPendingRequests(): boolean {
    for (const queue of this.requestQueue.values()) {
      if (queue.length > 0) return true;
    }
    return false;
  }

  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private generateBatchId(): string {
    return `batch_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

export default RequestBatcher;