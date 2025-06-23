import { EventEmitter } from 'events';
import { OfflineDocumentEditor } from './OfflineDocumentEditor';
import { ValidationUtils } from './ValidationUtils';
import * as Y from 'yjs';

interface Collaborator {
  id: string;
  name: string;
  color: string;
  cursor?: { position: number; selection?: { start: number; end: number } };
  lastSeen: number;
  isOnline: boolean;
}

interface CollaborativeSession {
  sessionId: string;
  documentId: string;
  hostId: string;
  collaborators: Map<string, Collaborator>;
  yDoc: Y.Doc;
  awareness: any; // Y.js awareness
  syncState: 'synced' | 'syncing' | 'offline';
}

interface CollaborativeEdit {
  id: string;
  sessionId: string;
  authorId: string;
  timestamp: number;
  changes: Uint8Array; // Y.js update
}

export class OfflineCollaborationManager extends EventEmitter {
  private sessions: Map<string, CollaborativeSession> = new Map();
  private pendingEdits: Map<string, CollaborativeEdit[]> = new Map();
  private editor: OfflineDocumentEditor;
  private userId: string;
  private userName: string;
  
  constructor(userId: string, userName: string) {
    super();
    this.userId = userId;
    this.userName = userName;
    this.editor = new OfflineDocumentEditor();
  }

  /**
   * Create collaborative session
   */
  async createSession(documentId: string, initialContent: string): Promise<string> {
    const sessionId = this.generateSessionId();
    const yDoc = new Y.Doc();
    
    // Initialize Y.js document
    const yText = yDoc.getText('content');
    yText.insert(0, initialContent);
    
    // Create awareness for cursor positions
    const awareness = {
      getLocalState: () => ({
        user: {
          id: this.userId,
          name: this.userName,
          color: this.generateUserColor(),
        },
        cursor: null,
      }),
      setLocalStateField: (field: string, value: any) => {
        // Implementation for setting local state
      },
      on: (event: string, callback: Function) => {
        // Event handling
      },
    };
    
    const session: CollaborativeSession = {
      sessionId,
      documentId,
      hostId: this.userId,
      collaborators: new Map(),
      yDoc,
      awareness,
      syncState: 'offline',
    };
    
    // Add self as collaborator
    session.collaborators.set(this.userId, {
      id: this.userId,
      name: this.userName,
      color: this.generateUserColor(),
      lastSeen: Date.now(),
      isOnline: true,
    });
    
    this.sessions.set(sessionId, session);
    this.pendingEdits.set(sessionId, []);
    
    // Listen for document changes
    yDoc.on('update', (update: Uint8Array, origin: any) => {
      this.handleDocumentUpdate(sessionId, update, origin);
    });
    
    this.emit('session-created', { sessionId, documentId });
    return sessionId;
  }

  /**
   * Join existing session
   */
  async joinSession(sessionId: string, documentSnapshot?: Uint8Array): Promise<void> {
    const session = this.sessions.get(sessionId);
    if (!session) {
      throw new Error('Session not found');
    }
    
    // Add as collaborator
    session.collaborators.set(this.userId, {
      id: this.userId,
      name: this.userName,
      color: this.generateUserColor(),
      lastSeen: Date.now(),
      isOnline: true,
    });
    
    // Apply document snapshot if provided
    if (documentSnapshot) {
      Y.applyUpdate(session.yDoc, documentSnapshot);
    }
    
    this.emit('session-joined', { sessionId, userId: this.userId });
  }

  /**
   * Apply local edit
   */
  applyEdit(sessionId: string, operation: {
    type: 'insert' | 'delete' | 'format';
    position: number;
    content?: string;
    length?: number;
    attributes?: Record<string, any>;
  }): void {
    const session = this.sessions.get(sessionId);
    if (!session) {
      throw new Error('Session not found');
    }
    
    const yText = session.yDoc.getText('content');
    
    switch (operation.type) {
      case 'insert':
        if (operation.content) {
          yText.insert(operation.position, operation.content, operation.attributes);
        }
        break;
      
      case 'delete':
        if (operation.length) {
          yText.delete(operation.position, operation.length);
        }
        break;
      
      case 'format':
        if (operation.length && operation.attributes) {
          yText.format(operation.position, operation.length, operation.attributes);
        }
        break;
    }
  }

  /**
   * Update cursor position
   */
  updateCursor(sessionId: string, position: number, selection?: { start: number; end: number }): void {
    const session = this.sessions.get(sessionId);
    if (!session) return;
    
    const collaborator = session.collaborators.get(this.userId);
    if (collaborator) {
      collaborator.cursor = { position, selection };
      collaborator.lastSeen = Date.now();
      
      // Broadcast cursor update
      this.emit('cursor-updated', {
        sessionId,
        userId: this.userId,
        cursor: collaborator.cursor,
      });
    }
  }

  /**
   * Sync edits when online
   */
  async syncEdits(sessionId: string): Promise<void> {
    const session = this.sessions.get(sessionId);
    const pendingEdits = this.pendingEdits.get(sessionId);
    
    if (!session || !pendingEdits || pendingEdits.length === 0) {
      return;
    }
    
    session.syncState = 'syncing';
    
    try {
      // In real implementation, this would sync with server
      // For now, we'll simulate merging edits
      for (const edit of pendingEdits) {
        // Apply remote edits
        Y.applyUpdate(session.yDoc, edit.changes);
      }
      
      // Clear pending edits
      this.pendingEdits.set(sessionId, []);
      session.syncState = 'synced';
      
      this.emit('sync-completed', { sessionId, editCount: pendingEdits.length });
    } catch (error) {
      session.syncState = 'offline';
      this.emit('sync-error', { sessionId, error });
      throw error;
    }
  }

  /**
   * Get document content
   */
  getContent(sessionId: string): string {
    const session = this.sessions.get(sessionId);
    if (!session) {
      throw new Error('Session not found');
    }
    
    return session.yDoc.getText('content').toString();
  }

  /**
   * Get collaborators
   */
  getCollaborators(sessionId: string): Collaborator[] {
    const session = this.sessions.get(sessionId);
    if (!session) {
      return [];
    }
    
    return Array.from(session.collaborators.values());
  }

  /**
   * Leave session
   */
  leaveSession(sessionId: string): void {
    const session = this.sessions.get(sessionId);
    if (!session) return;
    
    session.collaborators.delete(this.userId);
    
    if (session.collaborators.size === 0) {
      // Clean up empty session
      this.sessions.delete(sessionId);
      this.pendingEdits.delete(sessionId);
    }
    
    this.emit('session-left', { sessionId, userId: this.userId });
  }

  /**
   * Create snapshot for offline storage
   */
  createSnapshot(sessionId: string): Uint8Array {
    const session = this.sessions.get(sessionId);
    if (!session) {
      throw new Error('Session not found');
    }
    
    return Y.encodeStateAsUpdate(session.yDoc);
  }

  /**
   * Private helper methods
   */
  
  private handleDocumentUpdate(sessionId: string, update: Uint8Array, origin: any): void {
    // Skip if update is from remote (to avoid loops)
    if (origin === 'remote') return;
    
    const session = this.sessions.get(sessionId);
    if (!session) return;
    
    const edit: CollaborativeEdit = {
      id: this.generateEditId(),
      sessionId,
      authorId: this.userId,
      timestamp: Date.now(),
      changes: update,
    };
    
    if (session.syncState === 'offline') {
      // Store for later sync
      const pending = this.pendingEdits.get(sessionId) || [];
      pending.push(edit);
      this.pendingEdits.set(sessionId, pending);
    }
    
    this.emit('document-updated', {
      sessionId,
      authorId: this.userId,
      timestamp: edit.timestamp,
    });
  }

  private generateSessionId(): string {
    return `collab_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private generateEditId(): string {
    return `edit_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private generateUserColor(): string {
    const colors = [
      '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A',
      '#98D8C8', '#6C5CE7', '#A29BFE', '#FD79A8',
    ];
    return colors[Math.floor(Math.random() * colors.length)];
  }

  /**
   * Get active sessions
   */
  getActiveSessions(): Array<{
    sessionId: string;
    documentId: string;
    collaboratorCount: number;
    syncState: string;
  }> {
    return Array.from(this.sessions.entries()).map(([sessionId, session]) => ({
      sessionId,
      documentId: session.documentId,
      collaboratorCount: session.collaborators.size,
      syncState: session.syncState,
    }));
  }
}

export default OfflineCollaborationManager;