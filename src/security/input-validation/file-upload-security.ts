/**
 * File Upload Security
 * Comprehensive security for file uploads
 */

import * as crypto from 'crypto';
import * as path from 'path';
import * as fs from 'fs/promises';
import { Magic, MAGIC_MIME_TYPE } from 'file-type';
import sharp from 'sharp';
import { ClamAV } from 'clamav.js';

/**
 * File upload configuration
 */
export interface FileUploadConfig {
  maxFileSize: number;
  maxFiles: number;
  allowedMimeTypes: string[];
  allowedExtensions: string[];
  scanForVirus: boolean;
  validateMagicNumber: boolean;
  sanitizeFilename: boolean;
  generateHash: boolean;
  resizeImages: boolean;
  stripMetadata: boolean;
  quarantineLocation: string;
  uploadLocation: string;
  tempLocation: string;
}

/**
 * File validation result
 */
export interface FileValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  fileInfo?: {
    originalName: string;
    sanitizedName: string;
    size: number;
    mimeType: string;
    extension: string;
    hash?: string;
    dimensions?: { width: number; height: number };
  };
}

/**
 * Default configurations
 */
export const DefaultFileUploadConfigs = {
  documents: {
    maxFileSize: 10 * 1024 * 1024, // 10MB
    maxFiles: 10,
    allowedMimeTypes: [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'text/plain',
      'application/rtf'
    ],
    allowedExtensions: ['.pdf', '.doc', '.docx', '.txt', '.rtf'],
    scanForVirus: true,
    validateMagicNumber: true,
    sanitizeFilename: true,
    generateHash: true,
    resizeImages: false,
    stripMetadata: false,
    quarantineLocation: '/tmp/quarantine',
    uploadLocation: '/uploads/documents',
    tempLocation: '/tmp/uploads'
  },

  images: {
    maxFileSize: 5 * 1024 * 1024, // 5MB
    maxFiles: 20,
    allowedMimeTypes: [
      'image/jpeg',
      'image/png',
      'image/gif',
      'image/webp',
      'image/svg+xml'
    ],
    allowedExtensions: ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'],
    scanForVirus: true,
    validateMagicNumber: true,
    sanitizeFilename: true,
    generateHash: true,
    resizeImages: true,
    stripMetadata: true,
    quarantineLocation: '/tmp/quarantine',
    uploadLocation: '/uploads/images',
    tempLocation: '/tmp/uploads'
  },

  medicalImages: {
    maxFileSize: 100 * 1024 * 1024, // 100MB
    maxFiles: 50,
    allowedMimeTypes: [
      'application/dicom',
      'image/jpeg',
      'image/png',
      'application/octet-stream' // For DICOM files
    ],
    allowedExtensions: ['.dcm', '.dicom', '.jpg', '.jpeg', '.png'],
    scanForVirus: true,
    validateMagicNumber: true,
    sanitizeFilename: true,
    generateHash: true,
    resizeImages: false,
    stripMetadata: false, // Keep metadata for medical images
    quarantineLocation: '/tmp/quarantine',
    uploadLocation: '/uploads/medical',
    tempLocation: '/tmp/uploads'
  }
};

/**
 * File upload security manager
 */
export class FileUploadSecurity {
  private config: FileUploadConfig;
  private clamav: ClamAV | null = null;

  constructor(config: FileUploadConfig) {
    this.config = config;
    if (config.scanForVirus) {
      this.initializeAntivirus();
    }
  }

  /**
   * Initialize antivirus scanner
   */
  private async initializeAntivirus(): Promise<void> {
    try {
      this.clamav = new ClamAV();
      await this.clamav.init();
    } catch (error) {
      console.error('Failed to initialize antivirus:', error);
      this.clamav = null;
    }
  }

  /**
   * Validate uploaded file
   */
  async validateFile(
    filePath: string,
    originalName: string,
    size: number
  ): Promise<FileValidationResult> {
    const errors: string[] = [];
    const warnings: string[] = [];

    try {
      // Basic validations
      if (size > this.config.maxFileSize) {
        errors.push(`File size exceeds maximum allowed size of ${this.config.maxFileSize} bytes`);
      }

      // Validate extension
      const ext = path.extname(originalName).toLowerCase();
      if (!this.config.allowedExtensions.includes(ext)) {
        errors.push(`File extension '${ext}' is not allowed`);
      }

      // Validate MIME type by magic number
      let detectedMimeType: string | undefined;
      if (this.config.validateMagicNumber) {
        detectedMimeType = await this.detectMimeType(filePath);
        if (!detectedMimeType || !this.config.allowedMimeTypes.includes(detectedMimeType)) {
          errors.push(`Detected MIME type '${detectedMimeType}' is not allowed`);
        }
      }

      // Scan for viruses
      if (this.config.scanForVirus && this.clamav) {
        const scanResult = await this.scanForVirus(filePath);
        if (!scanResult.clean) {
          errors.push(`Virus detected: ${scanResult.virus}`);
          // Move to quarantine
          await this.quarantineFile(filePath, originalName, scanResult.virus || 'Unknown');
        }
      }

      // Check for embedded content
      const hasEmbedded = await this.checkForEmbeddedContent(filePath, detectedMimeType || '');
      if (hasEmbedded) {
        warnings.push('File contains embedded content');
      }

      // Generate file hash
      let hash: string | undefined;
      if (this.config.generateHash) {
        hash = await this.generateFileHash(filePath);
      }

      // Get image dimensions if applicable
      let dimensions: { width: number; height: number } | undefined;
      if (detectedMimeType?.startsWith('image/')) {
        dimensions = await this.getImageDimensions(filePath);
      }

      // Sanitize filename
      const sanitizedName = this.config.sanitizeFilename
        ? this.sanitizeFilename(originalName)
        : originalName;

      return {
        valid: errors.length === 0,
        errors,
        warnings,
        fileInfo: {
          originalName,
          sanitizedName,
          size,
          mimeType: detectedMimeType || '',
          extension: ext,
          hash,
          dimensions
        }
      };
    } catch (error) {
      errors.push(`Validation error: ${error.message}`);
      return { valid: false, errors, warnings };
    }
  }

  /**
   * Detect MIME type using magic numbers
   */
  private async detectMimeType(filePath: string): Promise<string | undefined> {
    try {
      const buffer = await fs.readFile(filePath);
      const fileTypeResult = await fileType.fromBuffer(buffer);
      return fileTypeResult?.mime;
    } catch {
      return undefined;
    }
  }

  /**
   * Scan file for viruses
   */
  private async scanForVirus(filePath: string): Promise<{ clean: boolean; virus?: string }> {
    if (!this.clamav) {
      return { clean: true };
    }

    try {
      const result = await this.clamav.scanFile(filePath);
      return {
        clean: result.isInfected === false,
        virus: result.viruses?.[0]
      };
    } catch (error) {
      console.error('Virus scan error:', error);
      // Fail closed - assume infected if scan fails
      return { clean: false, virus: 'Scan failed' };
    }
  }

  /**
   * Check for embedded content in files
   */
  private async checkForEmbeddedContent(filePath: string, mimeType: string): Promise<boolean> {
    // Check PDFs for embedded JavaScript or files
    if (mimeType === 'application/pdf') {
      return this.checkPDFForEmbedded(filePath);
    }

    // Check Office documents for macros
    if (mimeType.includes('officedocument') || mimeType.includes('msword')) {
      return this.checkOfficeForMacros(filePath);
    }

    // Check images for embedded data
    if (mimeType.startsWith('image/')) {
      return this.checkImageForEmbedded(filePath);
    }

    return false;
  }

  /**
   * Check PDF for embedded content
   */
  private async checkPDFForEmbedded(filePath: string): Promise<boolean> {
    try {
      const content = await fs.readFile(filePath, 'utf8');

      // Check for JavaScript
      if (content.includes('/JavaScript') || content.includes('/JS')) {
        return true;
      }

      // Check for embedded files
      if (content.includes('/EmbeddedFile') || content.includes('/Filespec')) {
        return true;
      }

      // Check for forms
      if (content.includes('/AcroForm')) {
        return true;
      }

      return false;
    } catch {
      return false;
    }
  }

  /**
   * Check Office documents for macros
   */
  private async checkOfficeForMacros(filePath: string): Promise<boolean> {
    // This would require specialized libraries like python-oletools
    // For now, return false but log warning
    console.warn('Office macro detection not fully implemented');
    return false;
  }

  /**
   * Check images for embedded data
   */
  private async checkImageForEmbedded(filePath: string): Promise<boolean> {
    try {
      const metadata = await sharp(filePath).metadata();

      // Check for EXIF data that might contain embedded content
      if (metadata.exif && Buffer.byteLength(metadata.exif) > 10000) {
        return true;
      }

      // Check for suspicious ICC profiles
      if (metadata.icc && Buffer.byteLength(metadata.icc) > 50000) {
        return true;
      }

      return false;
    } catch {
      return false;
    }
  }

  /**
   * Generate file hash
   */
  private async generateFileHash(filePath: string): Promise<string> {
    const hash = crypto.createHash('sha256');
    const stream = fs.createReadStream(filePath);

    return new Promise((resolve, reject) => {
      stream.on('data', data => hash.update(data));
      stream.on('end', () => resolve(hash.digest('hex')));
      stream.on('error', reject);
    });
  }

  /**
   * Get image dimensions
   */
  private async getImageDimensions(filePath: string): Promise<{ width: number; height: number } | undefined> {
    try {
      const metadata = await sharp(filePath).metadata();
      return metadata.width && metadata.height
        ? { width: metadata.width, height: metadata.height }
        : undefined;
    } catch {
      return undefined;
    }
  }

  /**
   * Sanitize filename
   */
  sanitizeFilename(filename: string): string {
    // Remove path components
    let sanitized = path.basename(filename);

    // Remove dangerous characters
    sanitized = sanitized.replace(/[^a-zA-Z0-9._-]/g, '_');

    // Remove multiple dots (prevent double extensions)
    sanitized = sanitized.replace(/\.{2,}/g, '.');

    // Ensure doesn't start with dot
    if (sanitized.startsWith('.')) {
      sanitized = sanitized.substring(1);
    }

    // Limit length
    const maxLength = 255;
    if (sanitized.length > maxLength) {
      const ext = path.extname(sanitized);
      const name = sanitized.substring(0, sanitized.lastIndexOf('.'));
      sanitized = name.substring(0, maxLength - ext.length) + ext;
    }

    // Add timestamp to ensure uniqueness
    const timestamp = Date.now();
    const ext = path.extname(sanitized);
    const name = sanitized.substring(0, sanitized.lastIndexOf('.'));

    return `${name}_${timestamp}${ext}`;
  }

  /**
   * Process uploaded file
   */
  async processFile(
    filePath: string,
    originalName: string
  ): Promise<{ success: boolean; processedPath?: string; error?: string }> {
    try {
      // Strip metadata if configured
      if (this.config.stripMetadata && originalName.match(/\.(jpg|jpeg|png|gif|webp)$/i)) {
        await this.stripImageMetadata(filePath);
      }

      // Resize images if configured
      if (this.config.resizeImages && originalName.match(/\.(jpg|jpeg|png|gif|webp)$/i)) {
        await this.resizeImage(filePath);
      }

      // Move to final location
      const sanitizedName = this.sanitizeFilename(originalName);
      const finalPath = path.join(this.config.uploadLocation, sanitizedName);

      // Ensure upload directory exists
      await fs.mkdir(path.dirname(finalPath), { recursive: true });

      // Move file
      await fs.rename(filePath, finalPath);

      return { success: true, processedPath: finalPath };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Strip image metadata
   */
  private async stripImageMetadata(filePath: string): Promise<void> {
    const tempPath = `${filePath}.tmp`;

    await sharp(filePath)
      .withMetadata({
        exif: {},
        icc: undefined,
        iptc: {},
        xmp: {}
      })
      .toFile(tempPath);

    await fs.rename(tempPath, filePath);
  }

  /**
   * Resize image
   */
  private async resizeImage(filePath: string): Promise<void> {
    const maxWidth = 2048;
    const maxHeight = 2048;

    const metadata = await sharp(filePath).metadata();

    if (metadata.width && metadata.height &&
        (metadata.width > maxWidth || metadata.height > maxHeight)) {
      const tempPath = `${filePath}.tmp`;

      await sharp(filePath)
        .resize(maxWidth, maxHeight, {
          fit: 'inside',
          withoutEnlargement: true
        })
        .toFile(tempPath);

      await fs.rename(tempPath, filePath);
    }
  }

  /**
   * Quarantine infected file
   */
  private async quarantineFile(filePath: string, originalName: string, virus: string): Promise<void> {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const quarantineName = `${timestamp}_${virus}_${path.basename(originalName)}`;
    const quarantinePath = path.join(this.config.quarantineLocation, quarantineName);

    // Ensure quarantine directory exists
    await fs.mkdir(path.dirname(quarantinePath), { recursive: true });

    // Move file to quarantine
    await fs.rename(filePath, quarantinePath);

    // Create metadata file
    const metadataPath = `${quarantinePath}.json`;
    await fs.writeFile(metadataPath, JSON.stringify({
      originalName,
      detectedVirus: virus,
      quarantinedAt: new Date().toISOString(),
      originalPath: filePath
    }, null, 2));
  }

  /**
   * Validate multiple files
   */
  async validateMultipleFiles(
    files: Array<{ path: string; originalName: string; size: number }>
  ): Promise<{
    valid: boolean;
    results: FileValidationResult[];
    totalSize: number;
    errors: string[];
  }> {
    const results: FileValidationResult[] = [];
    const errors: string[] = [];
    let totalSize = 0;

    // Check file count
    if (files.length > this.config.maxFiles) {
      errors.push(`Number of files (${files.length}) exceeds maximum allowed (${this.config.maxFiles})`);
    }

    // Validate each file
    for (const file of files) {
      const result = await this.validateFile(file.path, file.originalName, file.size);
      results.push(result);
      totalSize += file.size;
    }

    // Check for duplicate files by hash
    const hashes = results
      .filter(r => r.fileInfo?.hash)
      .map(r => r.fileInfo!.hash);

    const uniqueHashes = new Set(hashes);
    if (uniqueHashes.size < hashes.length) {
      errors.push('Duplicate files detected');
    }

    return {
      valid: errors.length === 0 && results.every(r => r.valid),
      results,
      totalSize,
      errors
    };
  }

  /**
   * Clean up temporary files
   */
  async cleanupTempFiles(age: number = 3600000): Promise<void> {
    try {
      const files = await fs.readdir(this.config.tempLocation);
      const now = Date.now();

      for (const file of files) {
        const filePath = path.join(this.config.tempLocation, file);
        const stats = await fs.stat(filePath);

        if (now - stats.mtimeMs > age) {
          await fs.unlink(filePath);
        }
      }
    } catch (error) {
      console.error('Cleanup error:', error);
    }
  }
}

/**
 * MIME type validator
 */
export class MimeTypeValidator {
  private static readonly mimeDatabase: Record<string, string[]> = {
    'application/pdf': ['pdf'],
    'image/jpeg': ['jpg', 'jpeg'],
    'image/png': ['png'],
    'image/gif': ['gif'],
    'image/webp': ['webp'],
    'image/svg+xml': ['svg'],
    'text/plain': ['txt'],
    'text/html': ['html', 'htm'],
    'text/css': ['css'],
    'text/javascript': ['js'],
    'application/json': ['json'],
    'application/xml': ['xml'],
    'application/zip': ['zip'],
    'application/x-rar-compressed': ['rar'],
    'application/x-7z-compressed': ['7z'],
    'application/vnd.ms-excel': ['xls'],
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['xlsx'],
    'application/msword': ['doc'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['docx'],
    'application/vnd.ms-powerpoint': ['ppt'],
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['pptx']
  };

  /**
   * Validate MIME type against extension
   */
  static validateMimeExtension(mimeType: string, extension: string): boolean {
    const expectedExtensions = this.mimeDatabase[mimeType];
    if (!expectedExtensions) {
      return false;
    }

    const ext = extension.toLowerCase().replace('.', '');
    return expectedExtensions.includes(ext);
  }

  /**
   * Get expected extensions for MIME type
   */
  static getExpectedExtensions(mimeType: string): string[] {
    return this.mimeDatabase[mimeType] || [];
  }

  /**
   * Get expected MIME types for extension
   */
  static getExpectedMimeTypes(extension: string): string[] {
    const ext = extension.toLowerCase().replace('.', '');
    const mimeTypes: string[] = [];

    for (const [mime, extensions] of Object.entries(this.mimeDatabase)) {
      if (extensions.includes(ext)) {
        mimeTypes.push(mime);
      }
    }

    return mimeTypes;
  }
}

// Export convenience functions
export const createFileUploadSecurity = (config: FileUploadConfig) => new FileUploadSecurity(config);
export const validateMimeExtension = MimeTypeValidator.validateMimeExtension.bind(MimeTypeValidator);
export const getExpectedExtensions = MimeTypeValidator.getExpectedExtensions.bind(MimeTypeValidator);
export const getExpectedMimeTypes = MimeTypeValidator.getExpectedMimeTypes.bind(MimeTypeValidator);
