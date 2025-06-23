import { EventEmitter } from 'events';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { ValidationUtils } from './ValidationUtils';

interface DocumentVersion {
  id: string;
  documentId: string;
  version: number;
  checksum: string;
  size: number;
  createdAt: number;
  createdBy: string;
  data: any;
  metadata: {
    changeType: 'minor' | 'major' | 'critical';
    changeDescription?: string;
    tags?: string[];
  };
}

interface RollbackOptions {
  reason: string;
  notifyUsers?: boolean;
  createBackup?: boolean;
}

interface RollbackResult {
  success: boolean;
  previousVersion: number;
  restoredVersion: number;
  backupId?: string;
  timestamp: number;
}

export class DocumentRollbackManager extends EventEmitter {
  private static readonly VERSION_STORAGE_PREFIX = '@doc_versions:';
  private static readonly MAX_VERSIONS_PER_DOCUMENT = 10;
  private static readonly ROLLBACK_HISTORY_KEY = '@rollback_history';
  
  constructor() {
    super();
  }

  /**
   * Save a new version of a document
   */
  async saveVersion(
    documentId: string,
    data: any,
    metadata: DocumentVersion['metadata'],
    userId: string
  ): Promise<DocumentVersion> {
    // Get current versions
    const versions = await this.getVersionHistory(documentId);
    const nextVersion = versions.length > 0 
      ? Math.max(...versions.map(v => v.version)) + 1 
      : 1;
    
    // Create new version
    const version: DocumentVersion = {
      id: `${documentId}_v${nextVersion}`,
      documentId,
      version: nextVersion,
      checksum: ValidationUtils.calculateChecksum(JSON.stringify(data)),
      size: JSON.stringify(data).length,
      createdAt: Date.now(),
      createdBy: userId,
      data,
      metadata,
    };
    
    // Add to versions
    versions.push(version);
    
    // Trim old versions if exceeds limit
    if (versions.length > DocumentRollbackManager.MAX_VERSIONS_PER_DOCUMENT) {
      versions.shift(); // Remove oldest
    }
    
    // Save to storage
    await this.saveVersionHistory(documentId, versions);
    
    this.emit('version-saved', version);
    return version;
  }

  /**
   * Rollback to a specific version
   */
  async rollbackToVersion(
    documentId: string,
    targetVersion: number,
    options: RollbackOptions,
    userId: string
  ): Promise<RollbackResult> {
    const versions = await this.getVersionHistory(documentId);
    const currentVersion = this.getCurrentVersion(versions);
    const targetVersionData = versions.find(v => v.version === targetVersion);
    
    if (!targetVersionData) {
      throw new Error(`Version ${targetVersion} not found for document ${documentId}`);
    }
    
    if (!currentVersion) {
      throw new Error(`No current version found for document ${documentId}`);
    }
    
    // Create backup if requested
    let backupId: string | undefined;
    if (options.createBackup) {
      backupId = await this.createBackup(currentVersion);
    }
    
    // Perform rollback
    const rollbackVersion: DocumentVersion = {
      ...targetVersionData,
      id: `${documentId}_v${currentVersion.version + 1}`,
      version: currentVersion.version + 1,
      createdAt: Date.now(),
      createdBy: userId,
      metadata: {
        ...targetVersionData.metadata,
        changeType: 'critical',
        changeDescription: `Rolled back from v${currentVersion.version} to v${targetVersion}: ${options.reason}`,
      },
    };
    
    // Save the rollback as a new version
    versions.push(rollbackVersion);
    await this.saveVersionHistory(documentId, versions);
    
    // Record rollback in history
    await this.recordRollback(documentId, currentVersion.version, targetVersion, options.reason, userId);
    
    // Emit events
    this.emit('rollback-completed', {
      documentId,
      fromVersion: currentVersion.version,
      toVersion: targetVersion,
      reason: options.reason,
    });
    
    if (options.notifyUsers) {
      this.emit('rollback-notification', {
        documentId,
        message: `Document rolled back from v${currentVersion.version} to v${targetVersion}`,
        reason: options.reason,
      });
    }
    
    return {
      success: true,
      previousVersion: currentVersion.version,
      restoredVersion: targetVersion,
      backupId,
      timestamp: Date.now(),
    };
  }

  /**
   * Get version history for a document
   */
  async getVersionHistory(documentId: string): Promise<DocumentVersion[]> {
    try {
      const key = `${DocumentRollbackManager.VERSION_STORAGE_PREFIX}${documentId}`;
      const stored = await AsyncStorage.getItem(key);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Failed to get version history:', error);
      return [];
    }
  }

  /**
   * Compare two versions
   */
  async compareVersions(
    documentId: string,
    versionA: number,
    versionB: number
  ): Promise<{
    differences: Array<{
      path: string;
      oldValue: any;
      newValue: any;
      changeType: 'added' | 'removed' | 'modified';
    }>;
    summary: {
      added: number;
      removed: number;
      modified: number;
    };
  }> {
    const versions = await this.getVersionHistory(documentId);
    const vA = versions.find(v => v.version === versionA);
    const vB = versions.find(v => v.version === versionB);
    
    if (!vA || !vB) {
      throw new Error('One or both versions not found');
    }
    
    const differences = this.findDifferences(vA.data, vB.data);
    
    return {
      differences,
      summary: {
        added: differences.filter(d => d.changeType === 'added').length,
        removed: differences.filter(d => d.changeType === 'removed').length,
        modified: differences.filter(d => d.changeType === 'modified').length,
      },
    };
  }

  /**
   * Get rollback history
   */
  async getRollbackHistory(documentId?: string): Promise<Array<{
    documentId: string;
    fromVersion: number;
    toVersion: number;
    reason: string;
    userId: string;
    timestamp: number;
  }>> {
    try {
      const stored = await AsyncStorage.getItem(DocumentRollbackManager.ROLLBACK_HISTORY_KEY);
      const history = stored ? JSON.parse(stored) : [];
      
      if (documentId) {
        return history.filter((h: any) => h.documentId === documentId);
      }
      
      return history;
    } catch (error) {
      console.error('Failed to get rollback history:', error);
      return [];
    }
  }

  /**
   * Validate version integrity
   */
  async validateVersion(documentId: string, version: number): Promise<boolean> {
    const versions = await this.getVersionHistory(documentId);
    const versionData = versions.find(v => v.version === version);
    
    if (!versionData) {
      return false;
    }
    
    // Verify checksum
    const calculatedChecksum = ValidationUtils.calculateChecksum(
      JSON.stringify(versionData.data)
    );
    
    return calculatedChecksum === versionData.checksum;
  }

  /**
   * Private helper methods
   */
  
  private async saveVersionHistory(
    documentId: string,
    versions: DocumentVersion[]
  ): Promise<void> {
    const key = `${DocumentRollbackManager.VERSION_STORAGE_PREFIX}${documentId}`;
    await AsyncStorage.setItem(key, JSON.stringify(versions));
  }

  private getCurrentVersion(versions: DocumentVersion[]): DocumentVersion | null {
    if (versions.length === 0) return null;
    return versions.reduce((latest, current) => 
      current.version > latest.version ? current : latest
    );
  }

  private async createBackup(version: DocumentVersion): Promise<string> {
    const backupId = `backup_${version.id}_${Date.now()}`;
    const backupKey = `@backup:${backupId}`;
    
    await AsyncStorage.setItem(backupKey, JSON.stringify(version));
    
    return backupId;
  }

  private async recordRollback(
    documentId: string,
    fromVersion: number,
    toVersion: number,
    reason: string,
    userId: string
  ): Promise<void> {
    const history = await this.getRollbackHistory();
    
    history.push({
      documentId,
      fromVersion,
      toVersion,
      reason,
      userId,
      timestamp: Date.now(),
    });
    
    // Keep only last 100 rollback records
    if (history.length > 100) {
      history.splice(0, history.length - 100);
    }
    
    await AsyncStorage.setItem(
      DocumentRollbackManager.ROLLBACK_HISTORY_KEY,
      JSON.stringify(history)
    );
  }

  private findDifferences(
    objA: any,
    objB: any,
    path: string = ''
  ): Array<{
    path: string;
    oldValue: any;
    newValue: any;
    changeType: 'added' | 'removed' | 'modified';
  }> {
    const differences: Array<{
      path: string;
      oldValue: any;
      newValue: any;
      changeType: 'added' | 'removed' | 'modified';
    }> = [];
    
    // Check all keys in objA
    for (const key in objA) {
      const currentPath = path ? `${path}.${key}` : key;
      
      if (!(key in objB)) {
        differences.push({
          path: currentPath,
          oldValue: objA[key],
          newValue: undefined,
          changeType: 'removed',
        });
      } else if (typeof objA[key] === 'object' && typeof objB[key] === 'object') {
        differences.push(...this.findDifferences(objA[key], objB[key], currentPath));
      } else if (objA[key] !== objB[key]) {
        differences.push({
          path: currentPath,
          oldValue: objA[key],
          newValue: objB[key],
          changeType: 'modified',
        });
      }
    }
    
    // Check for keys in objB not in objA
    for (const key in objB) {
      if (!(key in objA)) {
        const currentPath = path ? `${path}.${key}` : key;
        differences.push({
          path: currentPath,
          oldValue: undefined,
          newValue: objB[key],
          changeType: 'added',
        });
      }
    }
    
    return differences;
  }
}

export default DocumentRollbackManager;