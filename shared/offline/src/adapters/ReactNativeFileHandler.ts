import { Platform } from 'react-native';
import * as FileSystem from 'expo-file-system';
import * as DocumentPicker from 'expo-document-picker';
import * as MediaLibrary from 'expo-media-library';
import * as Sharing from 'expo-sharing';
import { FileHandler, FileInfo, FileOperationOptions, FileOperationResult } from '../types';

export class ReactNativeFileHandler implements FileHandler {
  private readonly baseDirectory: string;
  private readonly cacheDirectory: string;

  constructor() {
    this.baseDirectory = FileSystem.documentDirectory || '';
    this.cacheDirectory = FileSystem.cacheDirectory || '';
  }

  async initialize(): Promise<void> {
    // Request permissions
    const { status } = await MediaLibrary.requestPermissionsAsync();
    if (status !== 'granted') {
      console.warn('Media library permissions not granted');
    }

    // Create app directories if they don't exist
    await this.ensureDirectoryExists('documents');
    await this.ensureDirectoryExists('images');
    await this.ensureDirectoryExists('temp');
  }

  async readFile(path: string, options?: FileOperationOptions): Promise<FileOperationResult> {
    try {
      const fullPath = this.getFullPath(path);
      const fileInfo = await FileSystem.getInfoAsync(fullPath);

      if (!fileInfo.exists) {
        return {
          success: false,
          error: 'File not found',
        };
      }

      let content: any;
      if (options?.encoding === 'base64' || this.isImageFile(path)) {
        content = await FileSystem.readAsStringAsync(fullPath, {
          encoding: FileSystem.EncodingType.Base64,
        });
      } else {
        content = await FileSystem.readAsStringAsync(fullPath, {
          encoding: FileSystem.EncodingType.UTF8,
        });
      }

      return {
        success: true,
        data: content,
        metadata: {
          size: fileInfo.size || 0,
          modificationTime: fileInfo.modificationTime || Date.now(),
          uri: fileInfo.uri,
        },
      };
    } catch (error) {
      console.error('ReactNativeFileHandler: Failed to read file', error);
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
      const fullPath = this.getFullPath(path);
      await this.ensureDirectoryExists(this.getDirectoryFromPath(path));

      if (options?.encoding === 'base64' || content instanceof ArrayBuffer) {
        const base64Content = content instanceof ArrayBuffer
          ? this.arrayBufferToBase64(content)
          : content;
        
        await FileSystem.writeAsStringAsync(fullPath, base64Content, {
          encoding: FileSystem.EncodingType.Base64,
        });
      } else {
        await FileSystem.writeAsStringAsync(fullPath, content as string, {
          encoding: FileSystem.EncodingType.UTF8,
        });
      }

      const fileInfo = await FileSystem.getInfoAsync(fullPath);
      return {
        success: true,
        data: fullPath,
        metadata: {
          size: fileInfo.size || 0,
          modificationTime: fileInfo.modificationTime || Date.now(),
          uri: fileInfo.uri,
        },
      };
    } catch (error) {
      console.error('ReactNativeFileHandler: Failed to write file', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  async deleteFile(path: string): Promise<FileOperationResult> {
    try {
      const fullPath = this.getFullPath(path);
      const fileInfo = await FileSystem.getInfoAsync(fullPath);

      if (!fileInfo.exists) {
        return {
          success: false,
          error: 'File not found',
        };
      }

      await FileSystem.deleteAsync(fullPath);
      return {
        success: true,
        data: 'File deleted successfully',
      };
    } catch (error) {
      console.error('ReactNativeFileHandler: Failed to delete file', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }
  async moveFile(sourcePath: string, destPath: string): Promise<FileOperationResult> {
    try {
      const fullSourcePath = this.getFullPath(sourcePath);
      const fullDestPath = this.getFullPath(destPath);
      
      await this.ensureDirectoryExists(this.getDirectoryFromPath(destPath));
      await FileSystem.moveAsync({
        from: fullSourcePath,
        to: fullDestPath,
      });

      return {
        success: true,
        data: fullDestPath,
      };
    } catch (error) {
      console.error('ReactNativeFileHandler: Failed to move file', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  async copyFile(sourcePath: string, destPath: string): Promise<FileOperationResult> {
    try {
      const fullSourcePath = this.getFullPath(sourcePath);
      const fullDestPath = this.getFullPath(destPath);
      
      await this.ensureDirectoryExists(this.getDirectoryFromPath(destPath));
      await FileSystem.copyAsync({
        from: fullSourcePath,
        to: fullDestPath,
      });

      return {
        success: true,
        data: fullDestPath,
      };
    } catch (error) {
      console.error('ReactNativeFileHandler: Failed to copy file', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  async listFiles(directory: string): Promise<FileOperationResult> {
    try {
      const fullPath = this.getFullPath(directory);
      const files = await FileSystem.readDirectoryAsync(fullPath);
      
      const fileInfos: FileInfo[] = await Promise.all(
        files.map(async (filename) => {
          const filePath = `${fullPath}/${filename}`;
          const info = await FileSystem.getInfoAsync(filePath);
          
          return {
            name: filename,
            path: `${directory}/${filename}`,
            size: info.size || 0,
            modificationTime: info.modificationTime || Date.now(),
            isDirectory: info.isDirectory || false,
            uri: info.uri,
          };
        })
      );

      return {
        success: true,
        data: fileInfos,
      };
    } catch (error) {
      console.error('ReactNativeFileHandler: Failed to list files', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }
  async pickFile(options?: FileOperationOptions): Promise<FileOperationResult> {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: options?.mimeType || '*/*',
        copyToCacheDirectory: true,
        multiple: options?.multiple || false,
      });

      if (result.type === 'cancel') {
        return {
          success: false,
          error: 'User cancelled',
        };
      }

      if ('uri' in result) {
        const fileInfo: FileInfo = {
          name: result.name,
          path: result.uri,
          size: result.size || 0,
          modificationTime: Date.now(),
          isDirectory: false,
          uri: result.uri,
          mimeType: result.mimeType,
        };

        // Copy to app's document directory if requested
        if (options?.copyToApp) {
          const destPath = `documents/${result.name}`;
          const copyResult = await this.copyFile(result.uri, destPath);
          if (copyResult.success) {
            fileInfo.path = destPath;
          }
        }

        return {
          success: true,
          data: fileInfo,
        };
      }

      return {
        success: false,
        error: 'Invalid result from document picker',
      };
    } catch (error) {
      console.error('ReactNativeFileHandler: Failed to pick file', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  async shareFile(path: string, options?: FileOperationOptions): Promise<FileOperationResult> {
    try {
      const fullPath = this.getFullPath(path);
      const canShare = await Sharing.isAvailableAsync();

      if (!canShare) {
        return {
          success: false,
          error: 'Sharing is not available on this device',
        };
      }

      await Sharing.shareAsync(fullPath, {
        mimeType: options?.mimeType,
        dialogTitle: options?.dialogTitle || 'Share File',
        UTI: options?.uti,
      });

      return {
        success: true,
        data: 'File shared successfully',
      };
    } catch (error) {
      console.error('ReactNativeFileHandler: Failed to share file', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }
  async getFileInfo(path: string): Promise<FileOperationResult> {
    try {
      const fullPath = this.getFullPath(path);
      const info = await FileSystem.getInfoAsync(fullPath);

      if (!info.exists) {
        return {
          success: false,
          error: 'File not found',
        };
      }

      const fileInfo: FileInfo = {
        name: path.split('/').pop() || '',
        path: path,
        size: info.size || 0,
        modificationTime: info.modificationTime || Date.now(),
        isDirectory: info.isDirectory || false,
        uri: info.uri,
      };

      return {
        success: true,
        data: fileInfo,
      };
    } catch (error) {
      console.error('ReactNativeFileHandler: Failed to get file info', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  // Helper methods
  private getFullPath(path: string): string {
    if (path.startsWith('file://') || path.startsWith('/')) {
      return path;
    }
    return `${this.baseDirectory}${path}`;
  }

  private getDirectoryFromPath(path: string): string {
    const parts = path.split('/');
    parts.pop();
    return parts.join('/');
  }

  private async ensureDirectoryExists(directory: string): Promise<void> {
    if (!directory) return;
    
    const fullPath = this.getFullPath(directory);
    const info = await FileSystem.getInfoAsync(fullPath);
    
    if (!info.exists) {
      await FileSystem.makeDirectoryAsync(fullPath, { intermediates: true });
    }
  }

  private isImageFile(path: string): boolean {
    const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'];
    const extension = path.toLowerCase().split('.').pop();
    return imageExtensions.includes(`.${extension}`);
  }

  private arrayBufferToBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }
}