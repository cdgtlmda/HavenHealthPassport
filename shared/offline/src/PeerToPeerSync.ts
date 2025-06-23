import { EventEmitter } from 'events';
import { Platform } from 'react-native';
import { NetworkInfo } from 'react-native-network-info';
import { ValidationUtils } from './ValidationUtils';
import { BinaryDiff } from './BinaryDiff';

interface PeerDevice {
  id: string;
  name: string;
  address: string;
  port: number;
  publicKey: string;
  lastSeen: number;
  capabilities: string[];
  syncProtocolVersion: string;
}

interface P2PSyncConfig {
  discoveryPort: number;
  syncPort: number;
  enableEncryption: boolean;
  maxPeers: number;
  syncTimeout: number;
  discoveryInterval: number;
}

interface SyncManifest {
  deviceId: string;
  timestamp: number;
  files: Array<{
    id: string;
    version: number;
    checksum: string;
    size: number;
    lastModified: number;
  }>;
}

export class PeerToPeerSync extends EventEmitter {
  private config: P2PSyncConfig;
  private peers: Map<string, PeerDevice> = new Map();
  private localManifest: SyncManifest;
  private webSocket?: WebSocket;
  private discoveryInterval?: NodeJS.Timeout;
  private isDiscovering = false;
  private isSyncing = false;
  
  constructor(config: Partial<P2PSyncConfig> = {}) {
    super();
    this.config = {
      discoveryPort: 8889,
      syncPort: 8890,
      enableEncryption: true,
      maxPeers: 5,
      syncTimeout: 30000,
      discoveryInterval: 10000,
      ...config,
    };
    
    this.localManifest = {
      deviceId: this.generateDeviceId(),
      timestamp: Date.now(),
      files: [],
    };
  }

  /**
   * Start peer discovery
   */
  async startDiscovery(): Promise<void> {
    if (this.isDiscovering) return;
    
    this.isDiscovering = true;
    this.emit('discovery-started');
    
    // Get local network info
    const ipAddress = await NetworkInfo.getIPV4Address();
    if (!ipAddress) {
      throw new Error('Unable to get local IP address');
    }
    
    // Start WebSocket server for incoming connections
    this.startSyncServer();
    
    // Start discovery broadcasts
    this.discoveryInterval = setInterval(() => {
      this.broadcastPresence(ipAddress);
    }, this.config.discoveryInterval);
    
    // Initial broadcast
    this.broadcastPresence(ipAddress);
  }

  /**
   * Stop peer discovery
   */
  stopDiscovery(): void {
    if (this.discoveryInterval) {
      clearInterval(this.discoveryInterval);
      this.discoveryInterval = undefined;
    }
    
    if (this.webSocket) {
      this.webSocket.close();
      this.webSocket = undefined;
    }
    
    this.isDiscovering = false;
    this.emit('discovery-stopped');
  }

  /**
   * Sync with a specific peer
   */
  async syncWithPeer(peerId: string): Promise<void> {
    const peer = this.peers.get(peerId);
    if (!peer) {
      throw new Error(`Peer ${peerId} not found`);
    }
    
    if (this.isSyncing) {
      throw new Error('Sync already in progress');
    }
    
    this.isSyncing = true;
    this.emit('sync-started', { peerId });
    
    try {
      // Connect to peer
      const connection = await this.connectToPeer(peer);
      
      // Exchange manifests
      const peerManifest = await this.exchangeManifests(connection);
      
      // Calculate sync delta
      const syncPlan = this.calculateSyncPlan(this.localManifest, peerManifest);
      
      // Execute sync
      await this.executeSyncPlan(connection, syncPlan);
      
      this.emit('sync-completed', {
        peerId,
        filesReceived: syncPlan.toReceive.length,
        filesSent: syncPlan.toSend.length,
      });
      
    } catch (error) {
      this.emit('sync-error', { peerId, error });
      throw error;
    } finally {
      this.isSyncing = false;
    }
  }

  /**
   * Update local manifest
   */
  updateLocalManifest(files: Array<{
    id: string;
    version: number;
    checksum: string;
    size: number;
    lastModified: number;
  }>): void {
    this.localManifest = {
      deviceId: this.localManifest.deviceId,
      timestamp: Date.now(),
      files,
    };
  }

  /**
   * Get discovered peers
   */
  getDiscoveredPeers(): PeerDevice[] {
    // Remove stale peers (not seen in 30 seconds)
    const staleThreshold = Date.now() - 30000;
    const activePeers: PeerDevice[] = [];
    
    this.peers.forEach((peer, id) => {
      if (peer.lastSeen > staleThreshold) {
        activePeers.push(peer);
      } else {
        this.peers.delete(id);
      }
    });
    
    return activePeers;
  }

  /**
   * Private methods
   */
  
  private startSyncServer(): void {
    // This would use react-native-tcp or similar library
    // For now, using WebSocket as example
    const wsUrl = `ws://localhost:${this.config.syncPort}`;
    
    // In real implementation, this would be a server
    // For peer-to-peer, each device acts as both client and server
    console.log('P2P sync server would start on:', wsUrl);
  }

  private async broadcastPresence(ipAddress: string): Promise<void> {
    const announcement = {
      type: 'peer-announcement',
      device: {
        id: this.localManifest.deviceId,
        name: await this.getDeviceName(),
        address: ipAddress,
        port: this.config.syncPort,
        capabilities: ['sync', 'binary-diff', 'encryption'],
        syncProtocolVersion: '1.0',
      },
      timestamp: Date.now(),
    };
    
    // In real implementation, this would use UDP broadcast
    // or mDNS/Bonjour for discovery
    this.emit('presence-broadcast', announcement);
  }

  private async connectToPeer(peer: PeerDevice): Promise<WebSocket> {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(`ws://${peer.address}:${peer.port}`);
      
      const timeout = setTimeout(() => {
        ws.close();
        reject(new Error('Connection timeout'));
      }, this.config.syncTimeout);
      
      ws.onopen = () => {
        clearTimeout(timeout);
        resolve(ws);
      };
      
      ws.onerror = (error) => {
        clearTimeout(timeout);
        reject(error);
      };
    });
  }

  private async exchangeManifests(connection: WebSocket): Promise<SyncManifest> {
    return new Promise((resolve, reject) => {
      // Send our manifest
      connection.send(JSON.stringify({
        type: 'manifest',
        data: this.localManifest,
      }));
      
      // Wait for peer manifest
      connection.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'manifest') {
            resolve(message.data);
          }
        } catch (error) {
          reject(error);
        }
      };
    });
  }

  private calculateSyncPlan(
    local: SyncManifest,
    remote: SyncManifest
  ): {
    toReceive: Array<{ id: string; version: number }>;
    toSend: Array<{ id: string; version: number }>;
  } {
    const localFiles = new Map(local.files.map(f => [f.id, f]));
    const remoteFiles = new Map(remote.files.map(f => [f.id, f]));
    
    const toReceive: Array<{ id: string; version: number }> = [];
    const toSend: Array<{ id: string; version: number }> = [];
    
    // Files to receive (newer on remote)
    remoteFiles.forEach((remoteFile, id) => {
      const localFile = localFiles.get(id);
      if (!localFile || remoteFile.version > localFile.version) {
        toReceive.push({ id, version: remoteFile.version });
      }
    });
    
    // Files to send (newer locally)
    localFiles.forEach((localFile, id) => {
      const remoteFile = remoteFiles.get(id);
      if (!remoteFile || localFile.version > remoteFile.version) {
        toSend.push({ id, version: localFile.version });
      }
    });
    
    return { toReceive, toSend };
  }

  private async executeSyncPlan(
    connection: WebSocket,
    plan: {
      toReceive: Array<{ id: string; version: number }>;
      toSend: Array<{ id: string; version: number }>;
    }
  ): Promise<void> {
    // Request files we need
    for (const file of plan.toReceive) {
      await this.requestFile(connection, file.id, file.version);
    }
    
    // Send files peer needs
    for (const file of plan.toSend) {
      await this.sendFile(connection, file.id, file.version);
    }
  }

  private async requestFile(
    connection: WebSocket,
    fileId: string,
    version: number
  ): Promise<void> {
    // Implementation would request and receive file
    connection.send(JSON.stringify({
      type: 'file-request',
      fileId,
      version,
    }));
    
    // Wait for file data...
  }

  private async sendFile(
    connection: WebSocket,
    fileId: string,
    version: number
  ): Promise<void> {
    // Implementation would send file data
    connection.send(JSON.stringify({
      type: 'file-data',
      fileId,
      version,
      // data would be included here
    }));
  }

  private generateDeviceId(): string {
    return `device_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private async getDeviceName(): Promise<string> {
    if (Platform.OS === 'ios' || Platform.OS === 'android') {
      return 'Mobile Device'; // Would use DeviceInfo.getDeviceName()
    }
    return 'Web Client';
  }
}

export default PeerToPeerSync;  /**
   * Start WebSocket server for incoming connections
   */
  private startSyncServer(): void {
    // Note: In React Native, we would use a library like react-native-tcp
    // This is a conceptual implementation
    try {
      const WebSocketServer = require('ws').Server;
      const wss = new WebSocketServer({ port: this.config.syncPort });
      
      wss.on('connection', (ws: WebSocket, req: any) => {
        const peerAddress = req.socket.remoteAddress;
        console.log(`New peer connection from ${peerAddress}`);
        
        ws.on('message', async (data: string) => {
          try {
            const message = JSON.parse(data);
            await this.handlePeerMessage(ws, message);
          } catch (error) {
            console.error('Error handling peer message:', error);
          }
        });
        
        ws.on('close', () => {
          console.log(`Peer disconnected: ${peerAddress}`);
        });
      });
      
      this.emit('server-started', { port: this.config.syncPort });
    } catch (error) {
      console.error('Failed to start sync server:', error);
      // Fallback to client-only mode
    }
  }
  
  /**
   * Broadcast presence on local network
   */
  private async broadcastPresence(ipAddress: string): Promise<void> {
    const announcement = {
      type: 'peer-announcement',
      device: {
        id: this.localManifest.deviceId,
        name: await this.getDeviceName(),
        address: ipAddress,
        port: this.config.syncPort,
        capabilities: ['sync', 'encrypted'],
        syncProtocolVersion: '1.0',
      },
      timestamp: Date.now(),
    };
    
    // Broadcast using UDP multicast or similar
    // Implementation depends on platform capabilities
    this.emit('presence-broadcast', announcement);
  }
  /**
   * Handle messages from peers
   */
  private async handlePeerMessage(ws: WebSocket, message: any): Promise<void> {
    switch (message.type) {
      case 'manifest-request':
        ws.send(JSON.stringify({
          type: 'manifest-response',
          manifest: this.localManifest,
        }));
        break;
        
      case 'file-request':
        const fileData = await this.getFileData(message.fileId);
        ws.send(JSON.stringify({
          type: 'file-response',
          fileId: message.fileId,
          data: fileData,
        }));
        break;
        
      case 'sync-complete':
        this.emit('peer-sync-complete', message);
        break;
        
      default:
        console.warn(`Unknown message type: ${message.type}`);
    }
  }
  
  /**
   * Connect to a peer
   */
  private async connectToPeer(peer: PeerDevice): Promise<WebSocket> {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(`ws://${peer.address}:${peer.port}`);
      
      ws.onopen = () => {
        console.log(`Connected to peer ${peer.id}`);
        resolve(ws);
      };
      
      ws.onerror = (error) => {
        console.error(`Failed to connect to peer ${peer.id}:`, error);
        reject(error);
      };
      
      setTimeout(() => {
        if (ws.readyState !== WebSocket.OPEN) {
          ws.close();
          reject(new Error('Connection timeout'));
        }
      }, this.config.syncTimeout);
    });
  }
  /**
   * Exchange manifests with peer
   */
  private async exchangeManifests(connection: WebSocket): Promise<SyncManifest> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Manifest exchange timeout'));
      }, 10000);
      
      const messageHandler = (event: MessageEvent) => {
        const message = JSON.parse(event.data);
        if (message.type === 'manifest-response') {
          clearTimeout(timeout);
          connection.removeEventListener('message', messageHandler);
          resolve(message.manifest);
        }
      };
      
      connection.addEventListener('message', messageHandler);
      
      connection.send(JSON.stringify({
        type: 'manifest-request',
      }));
    });
  }
  
  /**
   * Calculate sync plan
   */
  private calculateSyncPlan(local: SyncManifest, remote: SyncManifest): {
    toSend: string[];
    toReceive: string[];
    conflicts: string[];
  } {
    const localFiles = new Map(local.files.map(f => [f.id, f]));
    const remoteFiles = new Map(remote.files.map(f => [f.id, f]));
    
    const toSend: string[] = [];
    const toReceive: string[] = [];
    const conflicts: string[] = [];
    
    // Files to receive (in remote but not local, or newer in remote)
    for (const [fileId, remoteFile] of remoteFiles) {
      const localFile = localFiles.get(fileId);
      if (!localFile) {
        toReceive.push(fileId);
      } else if (remoteFile.version > localFile.version) {
        toReceive.push(fileId);
      } else if (remoteFile.version === localFile.version && 
                 remoteFile.checksum !== localFile.checksum) {
        conflicts.push(fileId);
      }
    }
    // Files to send (in local but not remote, or newer in local)
    for (const [fileId, localFile] of localFiles) {
      const remoteFile = remoteFiles.get(fileId);
      if (!remoteFile || localFile.version > remoteFile.version) {
        toSend.push(fileId);
      }
    }
    
    return { toSend, toReceive, conflicts };
  }
  
  /**
   * Execute sync plan
   */
  private async executeSyncPlan(
    connection: WebSocket,
    syncPlan: { toSend: string[]; toReceive: string[]; conflicts: string[] }
  ): Promise<void> {
    // Handle conflicts first
    if (syncPlan.conflicts.length > 0) {
      await this.resolveConflicts(syncPlan.conflicts);
    }
    
    // Receive files
    for (const fileId of syncPlan.toReceive) {
      await this.receiveFile(connection, fileId);
      this.emit('file-received', { fileId });
    }
    
    // Send files
    for (const fileId of syncPlan.toSend) {
      await this.sendFile(connection, fileId);
      this.emit('file-sent', { fileId });
    }
  }
  
  /**
   * Receive file from peer
   */
  private async receiveFile(connection: WebSocket, fileId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error(`File receive timeout: ${fileId}`));
      }, 30000);
      const messageHandler = (event: MessageEvent) => {
        const message = JSON.parse(event.data);
        if (message.type === 'file-response' && message.fileId === fileId) {
          clearTimeout(timeout);
          connection.removeEventListener('message', messageHandler);
          
          // Verify and save file
          if (this.verifyFileData(message.data)) {
            this.saveFileData(fileId, message.data);
            resolve();
          } else {
            reject(new Error('File verification failed'));
          }
        }
      };
      
      connection.addEventListener('message', messageHandler);
      
      connection.send(JSON.stringify({
        type: 'file-request',
        fileId,
      }));
    });
  }
  
  /**
   * Send file to peer
   */
  private async sendFile(connection: WebSocket, fileId: string): Promise<void> {
    const fileData = await this.getFileData(fileId);
    
    connection.send(JSON.stringify({
      type: 'file-response',
      fileId,
      data: fileData,
    }));
  }
  
  /**
   * Helper methods
   */
  private generateDeviceId(): string {
    return `device_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  private async getDeviceName(): Promise<string> {
    if (Platform.OS === 'ios') {
      return 'iOS Device';
    } else if (Platform.OS === 'android') {
      return 'Android Device';
    }
    return 'Unknown Device';
  }
  
  private async getFileData(fileId: string): Promise<any> {
    // Implementation would fetch actual file data
    return { fileId, content: 'file content' };
  }
  
  private async saveFileData(fileId: string, data: any): Promise<void> {
    // Implementation would save file data
    console.log(`Saving file ${fileId}`);
  }
  
  private verifyFileData(data: any): boolean {
    // Implementation would verify file integrity
    return true;
  }
  
  private async resolveConflicts(conflictIds: string[]): Promise<void> {
    // Implementation would handle conflict resolution
    console.log(`Resolving ${conflictIds.length} conflicts`);
  }
}

export default PeerToPeerSync;