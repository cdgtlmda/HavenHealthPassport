import { EventEmitter } from 'events';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { DocumentRollbackManager } from './DocumentRollbackManager';
import { ValidationUtils } from './ValidationUtils';

interface EditOperation {
  id: string;
  documentId: string;
  type: 'insert' | 'delete' | 'format' | 'replace';
  position: number;
  content?: string;
  length?: number;
  format?: Record<string, any>;
  timestamp: number;
  userId: string;
}

interface EditSession {
  sessionId: string;
  documentId: string;
  startTime: number;
  endTime?: number;
  operations: EditOperation[];
  isDirty: boolean;
  autoSaveEnabled: boolean;
}

interface OfflineEditConfig {
  autoSaveInterval: number; // ms
  conflictResolution: 'manual' | 'auto-merge' | 'last-write-wins';
  enableVersioning: boolean;
  maxUndoHistory: number;
}

export class OfflineDocumentEditor extends EventEmitter {
  private editSessions: Map<string, EditSession> = new Map();
  private undoStack: Map<string, EditOperation[]> = new Map();
  private redoStack: Map<string, EditOperation[]> = new Map();
  private autoSaveTimers: Map<string, NodeJS.Timeout> = new Map();
  private config: OfflineEditConfig;
  private rollbackManager: DocumentRollbackManager;
  
  constructor(config: Partial<OfflineEditConfig> = {}) {
    super();
    this.config = {
      autoSaveInterval: 30000, // 30 seconds
      conflictResolution: 'auto-merge',
      enableVersioning: true,
      maxUndoHistory: 100,
      ...config,
    };
    this.rollbackManager = new DocumentRollbackManager();
  }

  /**
   * Start editing session
   */
  async startEditSession(
    documentId: string,
    documentContent: string,
    userId: string
  ): Promise<string> {
    const sessionId = this.generateSessionId();
    
    const session: EditSession = {
      sessionId,
      documentId,
      startTime: Date.now(),
      operations: [],
      isDirty: false,
      autoSaveEnabled: true,
    };
    
    this.editSessions.set(sessionId, session);
    this.undoStack.set(sessionId, []);
    this.redoStack.set(sessionId, []);
    
    // Start auto-save timer
    if (session.autoSaveEnabled) {
      this.startAutoSave(sessionId);
    }
    
    // Save initial version if versioning enabled
    if (this.config.enableVersioning) {
      await this.rollbackManager.saveVersion(
        documentId,
        documentContent,
        { changeType: 'minor', changeDescription: 'Edit session started' },
        userId
      );
    }
    
    this.emit('session-started', { sessionId, documentId });
    return sessionId;
  }

  /**
   * Apply edit operation
   */
  async applyEdit(
    sessionId: string,
    operation: Omit<EditOperation, 'id' | 'timestamp'>
  ): Promise<void> {
    const session = this.editSessions.get(sessionId);
    if (!session) {
      throw new Error('Invalid edit session');
    }
    
    const fullOperation: EditOperation = {
      ...operation,
      id: this.generateOperationId(),
      timestamp: Date.now(),
    };
    
    // Add to session operations
    session.operations.push(fullOperation);
    session.isDirty = true;
    
    // Add to undo stack
    const undoStack = this.undoStack.get(sessionId)!;
    undoStack.push(fullOperation);
    
    // Limit undo history
    if (undoStack.length > this.config.maxUndoHistory) {
      undoStack.shift();
    }
    
    // Clear redo stack on new operation
    this.redoStack.set(sessionId, []);
    
    this.emit('edit-applied', { sessionId, operation: fullOperation });
  }

  /**
   * Undo last operation
   */
  undo(sessionId: string): EditOperation | null {
    const undoStack = this.undoStack.get(sessionId);
    const redoStack = this.redoStack.get(sessionId);
    
    if (!undoStack || !redoStack || undoStack.length === 0) {
      return null;
    }
    
    const operation = undoStack.pop()!;
    redoStack.push(operation);
    
    // Create inverse operation
    const inverseOp = this.createInverseOperation(operation);
    
    this.emit('undo', { sessionId, operation: inverseOp });
    return inverseOp;
  }

  /**
   * Redo last undone operation
   */
  redo(sessionId: string): EditOperation | null {
    const undoStack = this.undoStack.get(sessionId);
    const redoStack = this.redoStack.get(sessionId);
    
    if (!undoStack || !redoStack || redoStack.length === 0) {
      return null;
    }
    
    const operation = redoStack.pop()!;
    undoStack.push(operation);
    
    this.emit('redo', { sessionId, operation });
    return operation;
  }

  /**
   * Save document
   */
  async saveDocument(
    sessionId: string,
    currentContent: string,
    userId: string
  ): Promise<void> {
    const session = this.editSessions.get(sessionId);
    if (!session) {
      throw new Error('Invalid edit session');
    }
    
    if (!session.isDirty) {
      return; // No changes to save
    }
    
    // Save to storage
    const key = `@document:${session.documentId}`;
    await AsyncStorage.setItem(key, JSON.stringify({
      content: currentContent,
      lastModified: Date.now(),
      checksum: ValidationUtils.calculateChecksum(currentContent),
    }));
    
    // Save version if enabled
    if (this.config.enableVersioning) {
      await this.rollbackManager.saveVersion(
        session.documentId,
        currentContent,
        {
          changeType: 'minor',
          changeDescription: `Auto-save with ${session.operations.length} operations`,
        },
        userId
      );
    }
    
    session.isDirty = false;
    this.emit('document-saved', { sessionId, documentId: session.documentId });
  }

  /**
   * End edit session
   */
  async endEditSession(
    sessionId: string,
    finalContent: string,
    userId: string
  ): Promise<void> {
    const session = this.editSessions.get(sessionId);
    if (!session) {
      throw new Error('Invalid edit session');
    }
    
    // Save final content
    if (session.isDirty) {
      await this.saveDocument(sessionId, finalContent, userId);
    }
    
    // Stop auto-save
    const timer = this.autoSaveTimers.get(sessionId);
    if (timer) {
      clearInterval(timer);
      this.autoSaveTimers.delete(sessionId);
    }
    
    // Clean up
    session.endTime = Date.now();
    this.editSessions.delete(sessionId);
    this.undoStack.delete(sessionId);
    this.redoStack.delete(sessionId);
    
    this.emit('session-ended', { sessionId, documentId: session.documentId });
  }

  /**
   * Merge concurrent edits
   */
  async mergeEdits(
    localOperations: EditOperation[],
    remoteOperations: EditOperation[]
  ): Promise<EditOperation[]> {
    if (this.config.conflictResolution === 'last-write-wins') {
      // Simple: remote wins
      return remoteOperations;
    }
    
    // Operational transformation for auto-merge
    const merged: EditOperation[] = [];
    let localIndex = 0;
    let remoteIndex = 0;
    
    while (localIndex < localOperations.length || remoteIndex < remoteOperations.length) {
      const localOp = localOperations[localIndex];
      const remoteOp = remoteOperations[remoteIndex];
      
      if (!remoteOp || (localOp && localOp.timestamp < remoteOp.timestamp)) {
        merged.push(this.transformOperation(localOp, remoteOperations.slice(0, remoteIndex)));
        localIndex++;
      } else {
        merged.push(this.transformOperation(remoteOp, localOperations.slice(0, localIndex)));
        remoteIndex++;
      }
    }
    
    return merged;
  }

  /**
   * Private helper methods
   */
  
  private startAutoSave(sessionId: string): void {
    const timer = setInterval(async () => {
      const session = this.editSessions.get(sessionId);
      if (session && session.isDirty) {
        // Auto-save logic would go here
        this.emit('auto-save', { sessionId });
      }
    }, this.config.autoSaveInterval);
    
    this.autoSaveTimers.set(sessionId, timer);
  }

  private createInverseOperation(operation: EditOperation): EditOperation {
    switch (operation.type) {
      case 'insert':
        return {
          ...operation,
          type: 'delete',
          length: operation.content?.length || 0,
          content: undefined,
        };
      
      case 'delete':
        return {
          ...operation,
          type: 'insert',
          // Content would need to be stored for proper undo
        };
      
      case 'replace':
        return {
          ...operation,
          // Would need original content
        };
      
      default:
        return operation;
    }
  }

  private transformOperation(
    operation: EditOperation,
    againstOperations: EditOperation[]
  ): EditOperation {
    let transformed = { ...operation };
    
    for (const against of againstOperations) {
      if (against.type === 'insert' && against.position <= transformed.position) {
        transformed.position += against.content?.length || 0;
      } else if (against.type === 'delete' && against.position < transformed.position) {
        transformed.position -= against.length || 0;
      }
    }
    
    return transformed;
  }

  private generateSessionId(): string {
    return `edit_session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private generateOperationId(): string {
    return `op_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

export default OfflineDocumentEditor;