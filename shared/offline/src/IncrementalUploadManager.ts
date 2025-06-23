import { EventEmitter } from 'events';
import { BinaryDiff, DiffResult } from './BinaryDiff';
import { ChunkBasedFileSync } from './ChunkBasedFileSync';
import { ValidationUtils } from './ValidationUtils';
import { CompressionUtils } from './CompressionUtils';

interface FileVersion {
  id: string;
  fileId: string;
  version: number;
  checksum: string;
  size: number;
  createdAt: number;
  data?: ArrayBuffer;
}

interface IncrementalUploadOptions {
  endpoint: string;
  headers?: Record<string, string>;
  onProgress?: (progress: IncrementalUploadProgress) => void;
  compressionThreshold?: number;
  useBinaryDiff?: boolean;
}

interface IncrementalUploadProgress {
  fileId: string;
  version: number;
  bytesUploaded: number;
  totalBytes: number;
  percentage: number;
  compressionRatio?: number;
  uploadType: 'full' | 'incremental';
}

export class IncrementalUploadManager extends EventEmitter {
  private fileVersions: Map<string, FileVersion[]> = new Map();
  private chunkUploader: ChunkBasedFileSync;
  private compressionThreshold: number = 0.7; // 70% size reduction threshold
  
  constructor() {
    super();
    this.chunkUploader = new ChunkBasedFileSync();
  }

  /**
   * Upload file incrementally based on previous version
   */
  async uploadIncremental(
    fileId: string,
    newData: ArrayBuffer,
    options: IncrementalUploadOptions
  ): Promise<void> {
    try {
      // Get latest version of the file
      const latestVersion = await this.getLatestVersion(fileId, options.endpoint, options.headers);
      
      if (!latestVersion || !options.useBinaryDiff) {
        // No previous version or binary diff disabled, do full upload
        return this.uploadFull(fileId, newData, options);
      }
      
      // Create diff between versions
      const diff = await BinaryDiff.createDiff(latestVersion.data!, newData);
      const compressionRatio = BinaryDiff.calculateCompressionRatio(diff);
      
      // Check if incremental upload is worth it
      if (compressionRatio < this.compressionThreshold) {
        // Not enough compression, do full upload
        return this.uploadFull(fileId, newData, options);
      }
      
      // Upload the diff
      await this.uploadDiff(fileId, diff, latestVersion.version, options);
      
      // Store new version locally
      this.storeVersion(fileId, {
        id: `${fileId}_v${latestVersion.version + 1}`,
        fileId,
        version: latestVersion.version + 1,
        checksum: ValidationUtils.calculateChecksum(new Uint8Array(newData)),
        size: newData.byteLength,
        createdAt: Date.now(),
        data: newData,
      });
      
      this.emit('incremental-upload-complete', {
        fileId,
        version: latestVersion.version + 1,
        compressionRatio,
      });
      
    } catch (error) {
      this.emit('upload-error', { fileId, error });
      throw error;
    }
  }

  /**
   * Upload full file when incremental is not beneficial
   */
  private async uploadFull(
    fileId: string,
    data: ArrayBuffer,
    options: IncrementalUploadOptions
  ): Promise<void> {
    const blob = new Blob([data]);
    const chunkedFile = await this.chunkUploader.chunkFile(blob, fileId);
    
    await this.chunkUploader.uploadFile(fileId, options.endpoint, {
      headers: options.headers,
      onProgress: (progress) => {
        options.onProgress?.({
          fileId,
          version: 1,
          bytesUploaded: progress.bytesUploaded,
          totalBytes: progress.totalBytes,
          percentage: progress.percentage,
          uploadType: 'full',
        });
      },
    });
  }

  /**
   * Upload diff to server
   */
  private async uploadDiff(
    fileId: string,
    diff: DiffResult,
    baseVersion: number,
    options: IncrementalUploadOptions
  ): Promise<void> {
    const diffData = JSON.stringify(diff);
    const compressed = CompressionUtils.compress(diffData);
    
    const response = await fetch(`${options.endpoint}/incremental/${fileId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Base-Version': baseVersion.toString(),
        'X-Diff-Compressed': 'true',
        ...options.headers,
      },
      body: compressed,
    });
    
    if (!response.ok) {
      throw new Error(`Incremental upload failed: ${response.statusText}`);
    }
    
    options.onProgress?.({
      fileId,
      version: baseVersion + 1,
      bytesUploaded: compressed.length,
      totalBytes: diff.modifiedSize,
      percentage: 100,
      compressionRatio: BinaryDiff.calculateCompressionRatio(diff),
      uploadType: 'incremental',
    });
  }

  /**
   * Get latest version from server
   */
  private async getLatestVersion(
    fileId: string,
    endpoint: string,
    headers?: Record<string, string>
  ): Promise<FileVersion | null> {
    // Check local cache first
    const localVersions = this.fileVersions.get(fileId);
    if (localVersions && localVersions.length > 0) {
      return localVersions[localVersions.length - 1];
    }
    
    // Fetch from server
    try {
      const response = await fetch(`${endpoint}/versions/${fileId}/latest`, {
        headers,
      });
      
      if (!response.ok) {
        return null;
      }
      
      const versionInfo = await response.json();
      
      // Download the actual file data for diff
      const dataResponse = await fetch(`${endpoint}/download/${fileId}?version=${versionInfo.version}`, {
        headers,
      });
      
      if (!dataResponse.ok) {
        return null;
      }
      
      const data = await dataResponse.arrayBuffer();
      
      const version: FileVersion = {
        id: versionInfo.id,
        fileId,
        version: versionInfo.version,
        checksum: versionInfo.checksum,
        size: versionInfo.size,
        createdAt: versionInfo.createdAt,
        data,
      };
      
      this.storeVersion(fileId, version);
      return version;
      
    } catch (error) {
      console.error('Failed to get latest version:', error);
      return null;
    }
  }

  /**
   * Store version locally
   */
  private storeVersion(fileId: string, version: FileVersion): void {
    if (!this.fileVersions.has(fileId)) {
      this.fileVersions.set(fileId, []);
    }
    
    const versions = this.fileVersions.get(fileId)!;
    versions.push(version);
    
    // Keep only last 3 versions to save memory
    if (versions.length > 3) {
      versions.shift();
    }
  }

  /**
   * Clear version cache for a file
   */
  clearVersionCache(fileId: string): void {
    this.fileVersions.delete(fileId);
  }

  /**
   * Clear all version caches
   */
  clearAllCaches(): void {
    this.fileVersions.clear();
  }
}

export default IncrementalUploadManager;