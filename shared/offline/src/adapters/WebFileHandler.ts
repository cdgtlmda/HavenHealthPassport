import { FileHandler, FileInfo, FileOperationOptions, FileOperationResult } from '../types';

export class WebFileHandler implements FileHandler {
  private fileSystemAPI: any = null;
  private rootDirectory: any = null;

  async initialize(): Promise<void> {
    // Check if File System Access API is available
    if ('showDirectoryPicker' in window) {
      try {
        // Request persistent storage
        if ('storage' in navigator && 'persist' in navigator.storage) {
          await navigator.storage.persist();
        }
      } catch (error) {
        console.warn('Failed to request persistent storage:', error);
      }
    } else {
      console.warn('File System Access API not available, using fallback methods');
    }
  }

  async readFile(path: string, options?: FileOperationOptions): Promise<FileOperationResult> {
    try {
      // If we have a file handle from File System Access API
      if (options?.fileHandle) {
        const file = await options.fileHandle.getFile();
        const content = options?.encoding === 'base64' 
          ? await this.fileToBase64(file)
          : await file.text();

        return {
          success: true,
          data: content,
          metadata: {
            size: file.size,
            modificationTime: file.lastModified,
            name: file.name,
            mimeType: file.type,
          },
        };
      }

      // Fallback: Read from IndexedDB or other storage
      const storedFile = await this.getStoredFile(path);
      if (!storedFile) {
        return {
          success: false,
          error: 'File not found',
        };
      }

      return {
        success: true,
        data: storedFile.content,
        metadata: storedFile.metadata,
      };
    } catch (error) {
      console.error('WebFileHandler: Failed to read file', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  async writeFile(
    path: string,
    content: string | ArrayBuffer,
    options?: FileOperationOptions
  ): Promise<FileOperationResult> {
    try {
      // If we have a file handle from File System Access API
      if (options?.fileHandle && 'createWritable' in options.fileHandle) {
        const writable = await options.fileHandle.createWritable();
        await writable.write(content);
        await writable.close();

        const file = await options.fileHandle.getFile();
        return {
          success: true,
          data: path,
          metadata: {
            size: file.size,
            modificationTime: file.lastModified,
            name: file.name,
            mimeType: file.type,
          },
        };
      }

      // Fallback: Store in IndexedDB
      const metadata: FileInfo = {
        name: path.split('/').pop() || '',
        path: path,
        size: content instanceof ArrayBuffer ? content.byteLength : new Blob([content]).size,
        modificationTime: Date.now(),
        isDirectory: false,
      };

      await this.storeFile(path, content, metadata);

      return {
        success: true,
        data: path,
        metadata,
      };
    } catch (error) {
      console.error('WebFileHandler: Failed to write file', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  async deleteFile(path: string): Promise<FileOperationResult> {
    try {
      // If using File System Access API
      if (this.rootDirectory) {
        const handle = await this.getFileHandle(path);
        if (handle && 'remove' in handle) {
          await handle.remove();
          return {
            success: true,
            data: 'File deleted successfully',
          };
        }
      }

      // Fallback: Delete from IndexedDB
      await this.deleteStoredFile(path);
      return {
        success: true,
        data: 'File deleted successfully',
      };
    } catch (error) {
      console.error('WebFileHandler: Failed to delete file', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }
  async moveFile(sourcePath: string, destPath: string): Promise<FileOperationResult> {
    try {
      // Read the file content first
      const readResult = await this.readFile(sourcePath);
      if (!readResult.success) {
        return readResult;
      }

      // Write to new location
      const writeResult = await this.writeFile(destPath, readResult.data);
      if (!writeResult.success) {
        return writeResult;
      }

      // Delete original file
      await this.deleteFile(sourcePath);

      return {
        success: true,
        data: destPath,
      };
    } catch (error) {
      console.error('WebFileHandler: Failed to move file', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  async copyFile(sourcePath: string, destPath: string): Promise<FileOperationResult> {
    try {
      // Read the file content
      const readResult = await this.readFile(sourcePath);
      if (!readResult.success) {
        return readResult;
      }

      // Write to new location
      const writeResult = await this.writeFile(destPath, readResult.data);
      
      return writeResult;
    } catch (error) {
      console.error('WebFileHandler: Failed to copy file', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  async listFiles(directory: string): Promise<FileOperationResult> {
    try {
      // If using File System Access API
      if (this.rootDirectory) {
        const dirHandle = await this.getDirectoryHandle(directory);
        if (dirHandle) {
          const files: FileInfo[] = [];
          
          for await (const entry of dirHandle.values()) {
            const info: FileInfo = {
              name: entry.name,
              path: `${directory}/${entry.name}`,
              size: 0,
              modificationTime: Date.now(),
              isDirectory: entry.kind === 'directory',
            };

            if (entry.kind === 'file') {
              const file = await entry.getFile();
              info.size = file.size;
              info.modificationTime = file.lastModified;
              info.mimeType = file.type;
            }

            files.push(info);
          }

          return {
            success: true,
            data: files,
          };
        }
      }

      // Fallback: List from IndexedDB
      const files = await this.listStoredFiles(directory);
      return {
        success: true,
        data: files,
      };
    } catch (error) {
      console.error('WebFileHandler: Failed to list files', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }
  async pickFile(options?: FileOperationOptions): Promise<FileOperationResult> {
    try {
      // Modern File System Access API
      if ('showOpenFilePicker' in window) {
        const pickerOptions: any = {
          multiple: options?.multiple || false,
        };

        if (options?.mimeType) {
          pickerOptions.types = [{
            description: 'Files',
            accept: { [options.mimeType]: options.extensions || [] },
          }];
        }

        const handles = await (window as any).showOpenFilePicker(pickerOptions);
        const fileHandle = handles[0];
        const file = await fileHandle.getFile();

        const fileInfo: FileInfo = {
          name: file.name,
          path: file.name,
          size: file.size,
          modificationTime: file.lastModified,
          isDirectory: false,
          mimeType: file.type,
          fileHandle,
        };

        return {
          success: true,
          data: options?.multiple ? handles : fileInfo,
        };
      }

      // Fallback: Traditional file input
      return await this.pickFileWithInput(options);
    } catch (error) {
      console.error('WebFileHandler: Failed to pick file', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  async shareFile(path: string, options?: FileOperationOptions): Promise<FileOperationResult> {
    try {
      // Get file content
      const readResult = await this.readFile(path);
      if (!readResult.success) {
        return readResult;
      }

      // Check if Web Share API is available
      if ('share' in navigator && 'canShare' in navigator) {
        const file = new File(
          [readResult.data],
          path.split('/').pop() || 'file',
          { type: options?.mimeType || 'application/octet-stream' }
        );

        const shareData: ShareData = {
          title: options?.dialogTitle || 'Share File',
          files: [file],
        };

        if (await navigator.canShare(shareData)) {
          await navigator.share(shareData);
          return {
            success: true,
            data: 'File shared successfully',
          };
        }
      }

      // Fallback: Download the file
      const blob = new Blob([readResult.data], { 
        type: options?.mimeType || 'application/octet-stream' 
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = path.split('/').pop() || 'download';
      a.click();
      URL.revokeObjectURL(url);

      return {
        success: true,
        data: 'File downloaded successfully',
      };
    } catch (error) {
      console.error('WebFileHandler: Failed to share file', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }
  async getFileInfo(path: string): Promise<FileOperationResult> {
    try {
      // Try to get from File System Access API
      if (this.rootDirectory) {
        const handle = await this.getFileHandle(path);
        if (handle && handle.kind === 'file') {
          const file = await handle.getFile();
          const fileInfo: FileInfo = {
            name: file.name,
            path: path,
            size: file.size,
            modificationTime: file.lastModified,
            isDirectory: false,
            mimeType: file.type,
          };

          return {
            success: true,
            data: fileInfo,
          };
        }
      }

      // Fallback: Get from IndexedDB
      const storedFile = await this.getStoredFile(path);
      if (!storedFile) {
        return {
          success: false,
          error: 'File not found',
        };
      }

      return {
        success: true,
        data: storedFile.metadata,
      };
    } catch (error) {
      console.error('WebFileHandler: Failed to get file info', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  // Helper methods
  private async pickFileWithInput(options?: FileOperationOptions): Promise<FileOperationResult> {
    return new Promise((resolve) => {
      const input = document.createElement('input');
      input.type = 'file';
      input.multiple = options?.multiple || false;
      
      if (options?.mimeType) {
        input.accept = options.mimeType;
      }

      input.onchange = async (event) => {
        const files = (event.target as HTMLInputElement).files;
        if (!files || files.length === 0) {
          resolve({
            success: false,
            error: 'No files selected',
          });
          return;
        }

        if (options?.multiple) {
          const fileInfos = await Promise.all(
            Array.from(files).map(async (file) => ({
              name: file.name,
              path: file.name,
              size: file.size,
              modificationTime: file.lastModified,
              isDirectory: false,
              mimeType: file.type,
              file,
            }))
          );

          resolve({
            success: true,
            data: fileInfos,
          });
        } else {
          const file = files[0];
          const fileInfo: FileInfo = {
            name: file.name,
            path: file.name,
            size: file.size,
            modificationTime: file.lastModified,
            isDirectory: false,
            mimeType: file.type,
            file,
          };

          resolve({
            success: true,
            data: fileInfo,
          });
        }
      };

      input.click();
    });
  }
  private async fileToBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const result = reader.result as string;
        resolve(result.split(',')[1]); // Remove data:mime;base64, prefix
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  private async getFileHandle(path: string): Promise<any> {
    if (!this.rootDirectory) return null;
    
    const parts = path.split('/').filter(p => p);
    let current = this.rootDirectory;
    
    for (let i = 0; i < parts.length - 1; i++) {
      current = await current.getDirectoryHandle(parts[i], { create: false });
    }
    
    return await current.getFileHandle(parts[parts.length - 1], { create: false });
  }

  private async getDirectoryHandle(path: string): Promise<any> {
    if (!this.rootDirectory) return null;
    
    const parts = path.split('/').filter(p => p);
    let current = this.rootDirectory;
    
    for (const part of parts) {
      current = await current.getDirectoryHandle(part, { create: false });
    }
    
    return current;
  }

  // IndexedDB storage methods (fallback)
  private async storeFile(path: string, content: any, metadata: FileInfo): Promise<void> {
    // Implementation would use IndexedDB to store files
    // This is a placeholder - actual implementation would be more complex
    const db = await this.openFileDB();
    const tx = db.transaction(['files'], 'readwrite');
    const store = tx.objectStore('files');
    
    await store.put({
      path,
      content,
      metadata,
      timestamp: Date.now(),
    });
  }

  private async getStoredFile(path: string): Promise<any> {
    const db = await this.openFileDB();
    const tx = db.transaction(['files'], 'readonly');
    const store = tx.objectStore('files');
    
    return await store.get(path);
  }

  private async deleteStoredFile(path: string): Promise<void> {
    const db = await this.openFileDB();
    const tx = db.transaction(['files'], 'readwrite');
    const store = tx.objectStore('files');
    
    await store.delete(path);
  }

  private async listStoredFiles(directory: string): Promise<FileInfo[]> {
    const db = await this.openFileDB();
    const tx = db.transaction(['files'], 'readonly');
    const store = tx.objectStore('files');
    
    const allFiles = await store.getAll();
    return allFiles
      .filter(file => file.path.startsWith(directory))
      .map(file => file.metadata);
  }

  private async openFileDB(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('HavenFileStorage', 1);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains('files')) {
          db.createObjectStore('files', { keyPath: 'path' });
        }
      };
    });
  }
}