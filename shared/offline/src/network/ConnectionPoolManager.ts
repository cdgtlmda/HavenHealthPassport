import { EventEmitter } from 'events';

interface Connection {
  id: string;
  endpoint: string;
  protocol: 'http' | 'https' | 'ws' | 'wss';
  state: 'idle' | 'active' | 'closing' | 'closed';
  created: number;
  lastUsed: number;
  useCount: number;
  keepAlive: boolean;
  socket?: any;
  metadata?: Record<string, any>;
}

interface PoolConfig {
  maxConnections: number;
  maxConnectionsPerHost: number;
  connectionTimeout: number;
  idleTimeout: number;
  keepAliveTimeout: number;
  enableMultiplexing: boolean;
  enablePipelining: boolean;
  retryDelay: number;
}

interface PoolStats {
  totalConnections: number;
  activeConnections: number;
  idleConnections: number;
  connectionsByHost: Record<string, number>;
  averageLatency: number;
  successRate: number;
}

export class ConnectionPoolManager extends EventEmitter {
  private config: PoolConfig;
  private connections: Map<string, Connection> = new Map();
  private hostConnections: Map<string, Set<string>> = new Map();
  private waitQueue: Array<{
    endpoint: string;
    resolve: (conn: Connection) => void;
    reject: (error: Error) => void;
    timestamp: number;
  }> = new Array();
  
  private stats = {
    totalRequests: 0,
    successfulRequests: 0,
    failedRequests: 0,
    totalLatency: 0,
  };
  
  constructor(config: Partial<PoolConfig> = {}) {
    super();
    this.config = {
      maxConnections: 50,
      maxConnectionsPerHost: 6,
      connectionTimeout: 30000,
      idleTimeout: 60000,
      keepAliveTimeout: 30000,
      enableMultiplexing: true,
      enablePipelining: true,
      retryDelay: 1000,
      ...config,
    };
    
    this.startMaintenanceTimer();
  }

  /**
   * Get or create connection
   */
  async getConnection(endpoint: string): Promise<Connection> {
    const host = this.extractHost(endpoint);
    
    // Try to find idle connection
    const idleConnection = this.findIdleConnection(endpoint);
    if (idleConnection) {
      this.activateConnection(idleConnection);
      return idleConnection;
    }
    
    // Check if can create new connection
    if (this.canCreateConnection(host)) {
      return this.createConnection(endpoint);
    }
    
    // Add to wait queue
    return this.queueRequest(endpoint);
  }

  /**
   * Release connection back to pool
   */
  releaseConnection(connectionId: string): void {
    const connection = this.connections.get(connectionId);
    if (!connection) return;
    
    if (connection.state === 'active') {
      connection.state = 'idle';
      connection.lastUsed = Date.now();
      
      this.emit('connection-released', connection);
      
      // Process wait queue
      this.processWaitQueue();
    }
  }

  /**
   * Close connection
   */
  async closeConnection(connectionId: string): Promise<void> {
    const connection = this.connections.get(connectionId);
    if (!connection) return;
    
    connection.state = 'closing';
    
    try {
      if (connection.socket && connection.socket.close) {
        await connection.socket.close();
      }
      
      // Remove from tracking
      this.connections.delete(connectionId);
      const host = this.extractHost(connection.endpoint);
      const hostConns = this.hostConnections.get(host);
      if (hostConns) {
        hostConns.delete(connectionId);
        if (hostConns.size === 0) {
          this.hostConnections.delete(host);
        }
      }
      
      connection.state = 'closed';
      this.emit('connection-closed', connection);
      
    } catch (error) {
      this.emit('connection-close-error', { connection, error });
    }
  }

  /**
   * Execute request with connection pooling
   */
  async request(
    endpoint: string,
    options: {
      method?: string;
      headers?: Record<string, string>;
      body?: any;
      timeout?: number;
    } = {}
  ): Promise<any> {
    const startTime = Date.now();
    let connection: Connection | null = null;
    
    try {
      connection = await this.getConnection(endpoint);
      
      // Execute request
      const response = await this.executeRequest(connection, options);
      
      // Update stats
      this.stats.totalRequests++;
      this.stats.successfulRequests++;
      this.stats.totalLatency += Date.now() - startTime;
      
      return response;
      
    } catch (error) {
      this.stats.totalRequests++;
      this.stats.failedRequests++;
      
      throw error;
      
    } finally {
      if (connection) {
        this.releaseConnection(connection.id);
      }
    }
  }

  /**
   * Get pool statistics
   */
  getStatistics(): PoolStats {
    let activeCount = 0;
    let idleCount = 0;
    const connectionsByHost: Record<string, number> = {};
    
    for (const connection of this.connections.values()) {
      if (connection.state === 'active') activeCount++;
      else if (connection.state === 'idle') idleCount++;
      
      const host = this.extractHost(connection.endpoint);
      connectionsByHost[host] = (connectionsByHost[host] || 0) + 1;
    }
    
    return {
      totalConnections: this.connections.size,
      activeConnections: activeCount,
      idleConnections: idleCount,
      connectionsByHost,
      averageLatency: this.stats.totalRequests > 0 
        ? this.stats.totalLatency / this.stats.totalRequests 
        : 0,
      successRate: this.stats.totalRequests > 0
        ? this.stats.successfulRequests / this.stats.totalRequests
        : 1,
    };
  }

  /**
   * Clear all connections
   */
  async clear(): Promise<void> {
    const closePromises = Array.from(this.connections.keys()).map(id => 
      this.closeConnection(id)
    );
    
    await Promise.all(closePromises);
    
    // Clear wait queue
    for (const waiter of this.waitQueue) {
      waiter.reject(new Error('Connection pool cleared'));
    }
    this.waitQueue = [];
  }

  /**
   * Enable HTTP/2 multiplexing
   */
  enableMultiplexing(endpoint: string): void {
    const connection = this.findConnectionForEndpoint(endpoint);
    if (connection && this.config.enableMultiplexing) {
      connection.metadata = {
        ...connection.metadata,
        multiplexing: true,
        maxConcurrentStreams: 100,
      };
    }
  }

  /**
   * Private methods
   */
  
  private findIdleConnection(endpoint: string): Connection | null {
    for (const connection of this.connections.values()) {
      if (connection.endpoint === endpoint && 
          connection.state === 'idle' &&
          !this.isConnectionStale(connection)) {
        return connection;
      }
    }
    return null;
  }

  private canCreateConnection(host: string): boolean {
    if (this.connections.size >= this.config.maxConnections) {
      return false;
    }
    
    const hostConns = this.hostConnections.get(host)?.size || 0;
    return hostConns < this.config.maxConnectionsPerHost;
  }

  private async createConnection(endpoint: string): Promise<Connection> {
    const connectionId = this.generateConnectionId();
    const host = this.extractHost(endpoint);
    
    const connection: Connection = {
      id: connectionId,
      endpoint,
      protocol: this.extractProtocol(endpoint),
      state: 'idle',
      created: Date.now(),
      lastUsed: Date.now(),
      useCount: 0,
      keepAlive: true,
    };
    
    try {
      // Create actual socket connection
      connection.socket = await this.establishConnection(endpoint);
      
      // Track connection
      this.connections.set(connectionId, connection);
      
      if (!this.hostConnections.has(host)) {
        this.hostConnections.set(host, new Set());
      }
      this.hostConnections.get(host)!.add(connectionId);
      
      this.emit('connection-created', connection);
      
      // Activate and return
      this.activateConnection(connection);
      return connection;
      
    } catch (error) {
      this.emit('connection-error', { endpoint, error });
      throw error;
    }
  }

  private async establishConnection(endpoint: string): Promise<any> {
    // In real implementation, would create actual socket
    // For now, simulate connection establishment
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          send: async (data: any) => {
            // Simulate sending data
            return { status: 200, data: {} };
          },
          close: async () => {
            // Simulate closing connection
          },
        });
      }, 50);
    });
  }

  private activateConnection(connection: Connection): void {
    connection.state = 'active';
    connection.lastUsed = Date.now();
    connection.useCount++;
  }

  private async queueRequest(endpoint: string): Promise<Connection> {
    return new Promise((resolve, reject) => {
      this.waitQueue.push({
        endpoint,
        resolve,
        reject,
        timestamp: Date.now(),
      });
      
      // Set timeout
      setTimeout(() => {
        const index = this.waitQueue.findIndex(w => w.resolve === resolve);
        if (index !== -1) {
          this.waitQueue.splice(index, 1);
          reject(new Error('Connection wait timeout'));
        }
      }, this.config.connectionTimeout);
    });
  }

  private processWaitQueue(): void {
    if (this.waitQueue.length === 0) return;
    
    const processed: typeof this.waitQueue = [];
    
    for (const waiter of this.waitQueue) {
      const connection = this.findIdleConnection(waiter.endpoint);
      if (connection) {
        this.activateConnection(connection);
        waiter.resolve(connection);
        processed.push(waiter);
      } else if (this.canCreateConnection(this.extractHost(waiter.endpoint))) {
        this.createConnection(waiter.endpoint)
          .then(conn => waiter.resolve(conn))
          .catch(err => waiter.reject(err));
        processed.push(waiter);
      }
    }
    
    // Remove processed items
    this.waitQueue = this.waitQueue.filter(w => !processed.includes(w));
  }

  private async executeRequest(
    connection: Connection,
    options: any
  ): Promise<any> {
    // Simulate request execution
    if (!connection.socket) {
      throw new Error('Connection has no socket');
    }
    
    return connection.socket.send({
      ...options,
      endpoint: connection.endpoint,
    });
  }

  private isConnectionStale(connection: Connection): boolean {
    const now = Date.now();
    
    // Check idle timeout
    if (now - connection.lastUsed > this.config.idleTimeout) {
      return true;
    }
    
    // Check keep-alive timeout
    if (connection.keepAlive && 
        now - connection.created > this.config.keepAliveTimeout) {
      return true;
    }
    
    return false;
  }

  private startMaintenanceTimer(): void {
    setInterval(() => {
      this.performMaintenance();
    }, 30000); // Every 30 seconds
  }

  private async performMaintenance(): Promise<void> {
    const staleConnections: string[] = [];
    
    for (const [id, connection] of this.connections.entries()) {
      if (this.isConnectionStale(connection) && connection.state === 'idle') {
        staleConnections.push(id);
      }
    }
    
    // Close stale connections
    for (const id of staleConnections) {
      await this.closeConnection(id);
    }
    
    if (staleConnections.length > 0) {
      this.emit('maintenance-completed', { 
        closedConnections: staleConnections.length 
      });
    }
  }

  private findConnectionForEndpoint(endpoint: string): Connection | null {
    for (const connection of this.connections.values()) {
      if (connection.endpoint === endpoint) {
        return connection;
      }
    }
    return null;
  }

  private extractHost(endpoint: string): string {
    try {
      const url = new URL(endpoint);
      return url.host;
    } catch {
      return endpoint;
    }
  }

  private extractProtocol(endpoint: string): Connection['protocol'] {
    if (endpoint.startsWith('https://')) return 'https';
    if (endpoint.startsWith('wss://')) return 'wss';
    if (endpoint.startsWith('ws://')) return 'ws';
    return 'http';
  }

  private generateConnectionId(): string {
    return `conn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

export default ConnectionPoolManager;