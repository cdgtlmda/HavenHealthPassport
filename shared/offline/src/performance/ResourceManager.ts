import { EventEmitter } from 'events';
import { MemoryMonitor } from './MemoryMonitor';

interface ResourceType {
  id: string;
  type: 'connection' | 'buffer' | 'cache' | 'computation' | 'storage';
  size: number;
  lastUsed: number;
  priority: number;
  isActive: boolean;
  cleanup?: () => Promise<void>;
}

interface ResourcePoolConfig {
  maxPoolSize: number;
  maxIdleTime: number;
  cleanupInterval: number;
  enableAutoGC: boolean;
  gcThreshold: number; // percentage of pool used
}

interface ConnectionConfig {
  maxConnections: number;
  connectionTimeout: number;
  idleTimeout: number;
  keepAlive: boolean;
}

export class ResourceManager extends EventEmitter {
  private resources: Map<string, ResourceType> = new Map();
  private resourcePools: Map<string, any[]> = new Map();
  private connectionPool: Map<string, any> = new Map();
  private memoryMonitor: MemoryMonitor;
  private cleanupTimer?: NodeJS.Timeout;
  private gcTimer?: NodeJS.Timeout;
  private resourcePriorities: Map<string, number> = new Map();
  
  private poolConfig: ResourcePoolConfig = {
    maxPoolSize: 100,
    maxIdleTime: 300000, // 5 minutes
    cleanupInterval: 60000, // 1 minute
    enableAutoGC: true,
    gcThreshold: 80,
  };
  
  private connectionConfig: ConnectionConfig = {
    maxConnections: 10,
    connectionTimeout: 30000,
    idleTimeout: 120000,
    keepAlive: true,
  };
  
  constructor() {
    super();
    this.memoryMonitor = new MemoryMonitor();
    this.initializeCleanupRoutines();
    this.initializeGarbageCollection();
  }

  /**
   * Register a resource
   */
  registerResource(resource: ResourceType): void {
    this.resources.set(resource.id, resource);
    this.resourcePriorities.set(resource.id, resource.priority);
    
    this.emit('resource-registered', resource);
  }

  /**
   * Unregister and cleanup resource
   */
  async unregisterResource(resourceId: string): Promise<void> {
    const resource = this.resources.get(resourceId);
    if (!resource) return;
    
    if (resource.cleanup) {
      await resource.cleanup();
    }
    
    this.resources.delete(resourceId);
    this.resourcePriorities.delete(resourceId);
    
    this.emit('resource-unregistered', resourceId);
  }

  /**
   * Get resource pool
   */
  getPool<T>(poolName: string): T[] {
    if (!this.resourcePools.has(poolName)) {
      this.resourcePools.set(poolName, []);
    }
    return this.resourcePools.get(poolName) as T[];
  }

  /**
   * Add to resource pool
   */
  addToPool<T>(poolName: string, resource: T): void {
    const pool = this.getPool<T>(poolName);
    
    if (pool.length >= this.poolConfig.maxPoolSize) {
      // Remove oldest resource
      pool.shift();
    }
    
    pool.push(resource);
    this.emit('pool-updated', { poolName, size: pool.length });
  }

  /**
   * Get from pool
   */
  getFromPool<T>(poolName: string): T | null {
    const pool = this.getPool<T>(poolName);
    return pool.pop() || null;
  }

  /**
   * Connection management
   */
  async getConnection(endpoint: string): Promise<any> {
    // Check existing connection
    const existing = this.connectionPool.get(endpoint);
    if (existing && existing.isAlive) {
      existing.lastUsed = Date.now();
      return existing.connection;
    }
    
    // Create new connection
    if (this.connectionPool.size >= this.connectionConfig.maxConnections) {
      // Evict least recently used
      await this.evictLRUConnection();
    }
    
    const connection = await this.createConnection(endpoint);
    this.connectionPool.set(endpoint, {
      connection,
      endpoint,
      created: Date.now(),
      lastUsed: Date.now(),
      isAlive: true,
    });
    
    return connection;
  }

  /**
   * Trigger garbage collection
   */
  async triggerGC(force = false): Promise<void> {
    const stats = this.memoryMonitor.getCurrentStats();
    
    if (!force && stats && stats.percentUsed < this.poolConfig.gcThreshold) {
      return;
    }
    
    this.emit('gc-started');
    
    // Sort resources by priority (lower priority = first to clean)
    const sortedResources = Array.from(this.resources.values())
      .sort((a, b) => a.priority - b.priority);
    
    let cleaned = 0;
    for (const resource of sortedResources) {
      if (!resource.isActive && resource.cleanup) {
        await resource.cleanup();
        this.resources.delete(resource.id);
        cleaned++;
        
        // Check if enough memory freed
        const newStats = this.memoryMonitor.getCurrentStats();
        if (newStats && newStats.percentUsed < 60) {
          break;
        }
      }
    }
    
    // Clear pools
    for (const [poolName, pool] of this.resourcePools.entries()) {
      const sizeBefore = pool.length;
      pool.splice(0, Math.floor(pool.length / 2)); // Remove half
      
      this.emit('pool-cleared', {
        poolName,
        removed: sizeBefore - pool.length,
      });
    }
    
    // Force native GC if available
    if (global.gc) {
      global.gc();
    }
    
    this.emit('gc-completed', { resourcesCleaned: cleaned });
  }

  /**
   * Set resource priority
   */
  setResourcePriority(resourceId: string, priority: number): void {
    const resource = this.resources.get(resourceId);
    if (resource) {
      resource.priority = priority;
      this.resourcePriorities.set(resourceId, priority);
    }
  }

  /**
   * Get resource statistics
   */
  getStatistics() {
    const activeResources = Array.from(this.resources.values())
      .filter(r => r.isActive).length;
    
    const poolStats = Array.from(this.resourcePools.entries())
      .map(([name, pool]) => ({ name, size: pool.length }));
    
    return {
      totalResources: this.resources.size,
      activeResources,
      inactiveResources: this.resources.size - activeResources,
      pools: poolStats,
      connections: this.connectionPool.size,
      memoryUsage: this.calculateMemoryUsage(),
    };
  }

  /**
   * Private methods
   */
  
  private initializeCleanupRoutines(): void {
    this.cleanupTimer = setInterval(() => {
      this.performCleanup();
    }, this.poolConfig.cleanupInterval);
  }

  private initializeGarbageCollection(): void {
    if (!this.poolConfig.enableAutoGC) return;
    
    // Monitor memory and trigger GC when needed
    this.memoryMonitor.on('memory-warning', () => {
      this.triggerGC();
    });
    
    this.memoryMonitor.on('memory-critical', () => {
      this.triggerGC(true);
    });
    
    this.memoryMonitor.start();
  }

  private async performCleanup(): Promise<void> {
    const now = Date.now();
    const toClean: string[] = [];
    
    // Find idle resources
    for (const [id, resource] of this.resources.entries()) {
      if (!resource.isActive && 
          now - resource.lastUsed > this.poolConfig.maxIdleTime) {
        toClean.push(id);
      }
    }
    
    // Clean idle resources
    for (const id of toClean) {
      await this.unregisterResource(id);
    }
    
    // Clean idle connections
    for (const [endpoint, conn] of this.connectionPool.entries()) {
      if (now - conn.lastUsed > this.connectionConfig.idleTimeout) {
        await this.closeConnection(endpoint);
      }
    }
    
    this.emit('cleanup-completed', { cleaned: toClean.length });
  }

  private async createConnection(endpoint: string): Promise<any> {
    // Simulated connection creation
    // In real implementation, would create actual network connection
    return {
      endpoint,
      send: async (data: any) => {
        // Send data
      },
      close: async () => {
        // Close connection
      },
    };
  }

  private async evictLRUConnection(): Promise<void> {
    let lruEndpoint = '';
    let lruTime = Infinity;
    
    for (const [endpoint, conn] of this.connectionPool.entries()) {
      if (conn.lastUsed < lruTime) {
        lruTime = conn.lastUsed;
        lruEndpoint = endpoint;
      }
    }
    
    if (lruEndpoint) {
      await this.closeConnection(lruEndpoint);
    }
  }

  private async closeConnection(endpoint: string): Promise<void> {
    const conn = this.connectionPool.get(endpoint);
    if (conn && conn.connection.close) {
      await conn.connection.close();
    }
    
    this.connectionPool.delete(endpoint);
    this.emit('connection-closed', endpoint);
  }

  private calculateMemoryUsage(): number {
    let totalSize = 0;
    
    for (const resource of this.resources.values()) {
      totalSize += resource.size;
    }
    
    return totalSize;
  }

  /**
   * Cleanup on destroy
   */
  destroy(): void {
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
    }
    
    if (this.gcTimer) {
      clearInterval(this.gcTimer);
    }
    
    this.memoryMonitor.stop();
    
    // Clean all resources
    this.resources.forEach(async (resource) => {
      if (resource.cleanup) {
        await resource.cleanup();
      }
    });
    
    this.resources.clear();
    this.resourcePools.clear();
    this.connectionPool.clear();
  }
}

export default ResourceManager;