// Platform-agnostic compression utilities
export class CompressionUtils {
  /**
   * Compress string data using LZ-string algorithm
   * This is a simple implementation - in production, use a proper library
   */
  static compress(data: string): string {
    if (!data) return data;
    
    // Simple RLE compression for demonstration
    // In production, use pako or lz-string library
    let compressed = '';
    let count = 1;
    let currentChar = data[0];
    
    for (let i = 1; i < data.length; i++) {
      if (data[i] === currentChar && count < 9) {
        count++;
      } else {
        compressed += count > 1 ? count + currentChar : currentChar;
        currentChar = data[i];
        count = 1;
      }
    }
    
    compressed += count > 1 ? count + currentChar : currentChar;
    
    // Base64 encode for safe transport
    return btoa(compressed);
  }

  /**
   * Decompress string data
   */
  static decompress(data: string): string {
    if (!data) return data;
    
    try {
      // Base64 decode
      const decoded = atob(data);
      
      // Simple RLE decompression
      let decompressed = '';
      let i = 0;
      
      while (i < decoded.length) {
        if (/\d/.test(decoded[i])) {
          const count = parseInt(decoded[i]);
          const char = decoded[i + 1];
          decompressed += char.repeat(count);
          i += 2;
        } else {
          decompressed += decoded[i];
          i++;
        }
      }
      
      return decompressed;
    } catch (error) {
      console.error('Decompression error:', error);
      return data; // Return original if decompression fails
    }
  }
  /**
   * Calculate compression ratio
   */
  static getCompressionRatio(original: string, compressed: string): number {
    if (!original || original.length === 0) return 0;
    return 1 - (compressed.length / original.length);
  }

  /**
   * Check if data should be compressed
   */
  static shouldCompress(data: string, threshold: number = 1024): boolean {
    return data.length > threshold;
  }

  /**
   * Compress JSON object
   */
  static compressJSON(obj: any): string {
    const json = JSON.stringify(obj);
    return this.compress(json);
  }

  /**
   * Decompress to JSON object
   */
  static decompressJSON<T = any>(compressed: string): T {
    const json = this.decompress(compressed);
    return JSON.parse(json);
  }

  /**
   * Compress with metadata
   */
  static compressWithMetadata(data: string): {
    compressed: string;
    originalSize: number;
    compressedSize: number;
    algorithm: string;
    timestamp: number;
  } {
    const compressed = this.compress(data);
    
    return {
      compressed,
      originalSize: data.length,
      compressedSize: compressed.length,
      algorithm: 'simple-rle',
      timestamp: Date.now(),
    };
  }
}

export default CompressionUtils;