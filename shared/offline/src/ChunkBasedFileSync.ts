import { EventEmitter } from 'events';
import { CompressionUtils } from './CompressionUtils';
import { ValidationUtils } from './ValidationUtils';

interface FileChunk {
  id: string;
  fileId: string;
  index: number;
  data: string;
  checksum: string;
  size: number;
  compressed: boolean;
}

interface ChunkedFile {
  id: string;
  name: string;
  size: number;
  mimeType: string;
  totalChunks: number;
  chunkSize: number;
  checksum: string;
  createdAt: number;
  chunks: FileChunk[];
}

interface UploadProgress {
  fileId: string;
  totalChunks: number;
  uploadedChunks: number;
  percentage: number;
  bytesUploaded: number;
  totalBytes: number;
}

export class ChunkBasedFileSync extends EventEmitter {
  private static readonly DEFAULT_CHUNK_SIZE = 1024 * 256; // 256KB chunks
  private static readonly MAX_PARALLEL_UPLOADS = 3;
  private static readonly MAX_RETRIES = 3;
  
  private chunkSize: number;
  private uploadQueue: Map<string, ChunkedFile> = new Map();
  private activeUploads: Map<string, AbortController> = new Map();
  private uploadProgress: Map<string, UploadProgress> = new Map();
  
  constructor(chunkSize: number = ChunkBasedFileSync.DEFAULT_CHUNK_SIZE) {
    super();
    this.chunkSize = chunkSize;
  }

  /**
   * Chunk a file for upload
   */
  async chunkFile(file: File | Blob, fileId?: string): Promise<ChunkedFile> {
    const id = fileId || this.generateFileId();
    const chunks: FileChunk[] = [];
    const totalChunks = Math.ceil(file.size / this.chunkSize);
    
    for (let i = 0; i < totalChunks; i++) {
      const start = i * this.chunkSize;
      const end = Math.min(start + this.chunkSize, file.size);
      const chunk = file.slice(start, end);
      
      const chunkData = await this.readChunk(chunk);
      const compressed = CompressionUtils.shouldCompress(chunkData);
      const processedData = compressed ? 
        CompressionUtils.compress(chunkData) : chunkData;
      
      chunks.push({
        id: `${id}_chunk_${i}`,
        fileId: id,
        index: i,
        data: processedData,
        checksum: ValidationUtils.calculateChecksum(processedData),
        size: chunk.size,
        compressed,
      });
    }
    const fileChecksum = await this.calculateFileChecksum(chunks);
    
    const chunkedFile: ChunkedFile = {
      id,
      name: (file as File).name || 'unnamed',
      size: file.size,
      mimeType: file.type,
      totalChunks,
      chunkSize: this.chunkSize,
      checksum: fileChecksum,
      createdAt: Date.now(),
      chunks,
    };
    
    this.uploadQueue.set(id, chunkedFile);
    this.emit('file-chunked', chunkedFile);
    
    return chunkedFile;
  }

  /**
   * Upload chunked file with resume capability
   */
  async uploadFile(
    fileId: string,
    uploadEndpoint: string,
    options?: {
      headers?: Record<string, string>;
      onProgress?: (progress: UploadProgress) => void;
      startFromChunk?: number;
    }
  ): Promise<void> {
    const file = this.uploadQueue.get(fileId);
    if (!file) {
      throw new Error(`File ${fileId} not found in upload queue`);
    }
    
    const abortController = new AbortController();
    this.activeUploads.set(fileId, abortController);
    
    const progress: UploadProgress = {
      fileId,
      totalChunks: file.totalChunks,
      uploadedChunks: options?.startFromChunk || 0,
      percentage: 0,
      bytesUploaded: 0,
      totalBytes: file.size,
    };
    
    this.uploadProgress.set(fileId, progress);
    
    try {
      const startIndex = options?.startFromChunk || 0;
      const uploadPromises: Promise<void>[] = [];
      
      for (let i = startIndex; i < file.chunks.length; i += ChunkBasedFileSync.MAX_PARALLEL_UPLOADS) {
        if (abortController.signal.aborted) break;
        
        const batch = file.chunks.slice(i, i + ChunkBasedFileSync.MAX_PARALLEL_UPLOADS);
        
        const batchPromises = batch.map(chunk => 
          this.uploadChunk(chunk, uploadEndpoint, {
            ...options,
            signal: abortController.signal,
            onChunkComplete: () => {
              progress.uploadedChunks++;
              progress.bytesUploaded += chunk.size;
              progress.percentage = (progress.uploadedChunks / progress.totalChunks) * 100;
              
              this.emit('upload-progress', progress);
              options?.onProgress?.(progress);
            },
          })
        );
        
        await Promise.all(batchPromises);
      }
      // Verify upload completion
      await this.verifyUpload(fileId, uploadEndpoint, options?.headers);
      
      this.emit('upload-complete', fileId);
      this.uploadQueue.delete(fileId);
      this.uploadProgress.delete(fileId);
      
    } catch (error) {
      this.emit('upload-error', { fileId, error });
      throw error;
    } finally {
      this.activeUploads.delete(fileId);
    }
  }

  /**
   * Upload individual chunk with retry
   */
  private async uploadChunk(
    chunk: FileChunk,
    endpoint: string,
    options?: {
      headers?: Record<string, string>;
      signal?: AbortSignal;
      onChunkComplete?: () => void;
    }
  ): Promise<void> {
    let retries = 0;
    
    while (retries < ChunkBasedFileSync.MAX_RETRIES) {
      try {
        const response = await fetch(`${endpoint}/chunks`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-File-Id': chunk.fileId,
            'X-Chunk-Index': chunk.index.toString(),
            'X-Chunk-Checksum': chunk.checksum,
            'X-Chunk-Compressed': chunk.compressed.toString(),
            ...options?.headers,
          },
          body: JSON.stringify({
            data: chunk.data,
            metadata: {
              fileId: chunk.fileId,
              index: chunk.index,
              size: chunk.size,
              checksum: chunk.checksum,
              compressed: chunk.compressed,
            },
          }),
          signal: options?.signal,
        });
        
        if (!response.ok) {
          throw new Error(`Chunk upload failed: ${response.statusText}`);
        }
        
        options?.onChunkComplete?.();
        return;
        
      } catch (error) {
        retries++;
        if (retries >= ChunkBasedFileSync.MAX_RETRIES) {
          throw error;
        }
        
        // Exponential backoff
        await this.delay(Math.pow(2, retries) * 1000);
      }
    }
  }
  /**
   * Verify upload completion
   */
  private async verifyUpload(
    fileId: string,
    endpoint: string,
    headers?: Record<string, string>
  ): Promise<void> {
    const response = await fetch(`${endpoint}/verify/${fileId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
    });
    
    if (!response.ok) {
      throw new Error('Upload verification failed');
    }
    
    const result = await response.json();
    if (!result.verified) {
      throw new Error('File integrity check failed');
    }
  }

  /**
   * Resume interrupted upload
   */
  async resumeUpload(
    fileId: string,
    uploadEndpoint: string,
    options?: {
      headers?: Record<string, string>;
      onProgress?: (progress: UploadProgress) => void;
    }
  ): Promise<void> {
    // Check which chunks have been uploaded
    const uploadedChunks = await this.getUploadedChunks(fileId, uploadEndpoint, options?.headers);
    const startFromChunk = uploadedChunks.length;
    
    return this.uploadFile(fileId, uploadEndpoint, {
      ...options,
      startFromChunk,
    });
  }

  /**
   * Get list of already uploaded chunks
   */
  private async getUploadedChunks(
    fileId: string,
    endpoint: string,
    headers?: Record<string, string>
  ): Promise<number[]> {
    const response = await fetch(`${endpoint}/status/${fileId}`, {
      headers: {
        ...headers,
      },
    });
    
    if (!response.ok) {
      return [];
    }
    
    const status = await response.json();
    return status.uploadedChunks || [];
  }
  /**
   * Abort upload
   */
  abortUpload(fileId: string): void {
    const controller = this.activeUploads.get(fileId);
    if (controller) {
      controller.abort();
      this.activeUploads.delete(fileId);
      this.emit('upload-aborted', fileId);
    }
  }

  /**
   * Get upload progress
   */
  getUploadProgress(fileId: string): UploadProgress | undefined {
    return this.uploadProgress.get(fileId);
  }

  /**
   * Helper methods
   */
  private async readChunk(chunk: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(chunk);
    });
  }

  private async calculateFileChecksum(chunks: FileChunk[]): Promise<string> {
    const concatenated = chunks
      .sort((a, b) => a.index - b.index)
      .map(c => c.checksum)
      .join('');
    return ValidationUtils.calculateChecksum(concatenated);
  }

  private generateFileId(): string {
    return `file_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Download file in chunks
   */
  async downloadFile(
    fileId: string,
    downloadEndpoint: string,
    options?: {
      headers?: Record<string, string>;
      onProgress?: (progress: UploadProgress) => void;
    }
  ): Promise<Blob> {
    // Get file metadata
    const metadata = await this.getFileMetadata(fileId, downloadEndpoint, options?.headers);
    const chunks: Blob[] = [];
    
    for (let i = 0; i < metadata.totalChunks; i++) {
      const chunk = await this.downloadChunk(fileId, i, downloadEndpoint, options?.headers);
      chunks.push(chunk);
      
      if (options?.onProgress) {
        options.onProgress({
          fileId,
          totalChunks: metadata.totalChunks,
          uploadedChunks: i + 1,
          percentage: ((i + 1) / metadata.totalChunks) * 100,
          bytesUploaded: 0,
          totalBytes: metadata.size,
        });
      }
    }
    
    return new Blob(chunks, { type: metadata.mimeType });
  }
  private async getFileMetadata(
    fileId: string,
    endpoint: string,
    headers?: Record<string, string>
  ): Promise<any> {
    const response = await fetch(`${endpoint}/metadata/${fileId}`, {
      headers: {
        ...headers,
      },
    });
    
    if (!response.ok) {
      throw new Error('Failed to get file metadata');
    }
    
    return response.json();
  }

  private async downloadChunk(
    fileId: string,
    chunkIndex: number,
    endpoint: string,
    headers?: Record<string, string>
  ): Promise<Blob> {
    const response = await fetch(`${endpoint}/chunks/${fileId}/${chunkIndex}`, {
      headers: {
        ...headers,
      },
    });
    
    if (!response.ok) {
      throw new Error(`Failed to download chunk ${chunkIndex}`);
    }
    
    const data = await response.json();
    const chunkData = data.compressed ? 
      CompressionUtils.decompress(data.data) : data.data;
    
    // Convert base64 to blob
    const byteCharacters = atob(chunkData.split(',')[1]);
    const byteNumbers = new Array(byteCharacters.length);
    
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    
    const byteArray = new Uint8Array(byteNumbers);
    return new Blob([byteArray]);
  }
}

export default ChunkBasedFileSync;