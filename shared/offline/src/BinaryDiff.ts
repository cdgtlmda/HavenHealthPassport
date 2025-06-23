/**
 * Binary diff algorithm for efficient file synchronization
 * Uses a rolling hash algorithm similar to rsync
 */
export class BinaryDiff {
  private static readonly BLOCK_SIZE = 4096; // 4KB blocks
  private static readonly WEAK_HASH_PRIME = 65521; // Adler-32 prime
  
  /**
   * Create a diff between two binary files
   */
  static async createDiff(
    original: ArrayBuffer,
    modified: ArrayBuffer
  ): Promise<DiffResult> {
    const originalBlocks = this.createBlockMap(original);
    const patches: DiffPatch[] = [];
    
    const modifiedBytes = new Uint8Array(modified);
    let position = 0;
    let unmatchedStart = 0;
    
    while (position < modifiedBytes.length) {
      const remainingBytes = modifiedBytes.length - position;
      const blockSize = Math.min(this.BLOCK_SIZE, remainingBytes);
      const block = modifiedBytes.slice(position, position + blockSize);
      
      const weakHash = this.computeWeakHash(block);
      const matchingBlocks = originalBlocks.weakHashes.get(weakHash);
      
      if (matchingBlocks) {
        // Check strong hash to confirm match
        const strongHash = await this.computeStrongHash(block);
        const matchedBlock = matchingBlocks.find(b => b.strongHash === strongHash);
        
        if (matchedBlock) {
          // Found matching block
          if (unmatchedStart < position) {
            // Add literal patch for unmatched data
            patches.push({
              type: 'literal',
              offset: unmatchedStart,
              data: modifiedBytes.slice(unmatchedStart, position),
            });
          }
          
          // Add copy patch
          patches.push({
            type: 'copy',
            offset: position,
            sourceOffset: matchedBlock.offset,
            length: blockSize,
          });
          
          position += blockSize;
          unmatchedStart = position;
          continue;
        }
      }
      
      // No match found, move forward
      position++;
    }
    
    // Add final literal patch if needed
    if (unmatchedStart < modifiedBytes.length) {
      patches.push({
        type: 'literal',
        offset: unmatchedStart,
        data: modifiedBytes.slice(unmatchedStart),
      });
    }
    
    return {
      originalSize: original.byteLength,
      modifiedSize: modified.byteLength,
      patches,
    };
  }
  /**
   * Apply diff patches to recreate modified file
   */
  static applyDiff(original: ArrayBuffer, diff: DiffResult): ArrayBuffer {
    const originalBytes = new Uint8Array(original);
    const result = new Uint8Array(diff.modifiedSize);
    let resultPosition = 0;
    
    for (const patch of diff.patches) {
      if (patch.type === 'literal') {
        // Copy literal data
        result.set(patch.data!, resultPosition);
        resultPosition += patch.data!.length;
      } else if (patch.type === 'copy') {
        // Copy from original
        const sourceData = originalBytes.slice(
          patch.sourceOffset!,
          patch.sourceOffset! + patch.length!
        );
        result.set(sourceData, resultPosition);
        resultPosition += patch.length!;
      }
    }
    
    return result.buffer;
  }
  
  /**
   * Create block map for original file
   */
  private static createBlockMap(buffer: ArrayBuffer): BlockMap {
    const bytes = new Uint8Array(buffer);
    const blocks: Block[] = [];
    const weakHashes = new Map<number, Block[]>();
    
    for (let offset = 0; offset < bytes.length; offset += this.BLOCK_SIZE) {
      const blockSize = Math.min(this.BLOCK_SIZE, bytes.length - offset);
      const block = bytes.slice(offset, offset + blockSize);
      
      const weakHash = this.computeWeakHash(block);
      const strongHash = this.computeStrongHashSync(block);
      
      const blockInfo: Block = {
        offset,
        weakHash,
        strongHash,
        size: blockSize,
      };
      
      blocks.push(blockInfo);
      
      if (!weakHashes.has(weakHash)) {
        weakHashes.set(weakHash, []);
      }
      weakHashes.get(weakHash)!.push(blockInfo);
    }
    
    return { blocks, weakHashes };
  }
  
  /**
   * Compute weak hash (Adler-32 variant)
   */
  private static computeWeakHash(data: Uint8Array): number {
    let a = 1;
    let b = 0;
    
    for (let i = 0; i < data.length; i++) {
      a = (a + data[i]) % this.WEAK_HASH_PRIME;
      b = (b + a) % this.WEAK_HASH_PRIME;
    }
    
    return (b << 16) | a;
  }
  /**
   * Compute strong hash (SHA-256)
   */
  private static async computeStrongHash(data: Uint8Array): Promise<string> {
    if (typeof crypto !== 'undefined' && crypto.subtle) {
      const hashBuffer = await crypto.subtle.digest('SHA-256', data);
      return this.bufferToHex(hashBuffer);
    }
    // Fallback for environments without Web Crypto API
    return this.computeStrongHashSync(data);
  }
  
  /**
   * Compute strong hash synchronously (simple hash for fallback)
   */
  private static computeStrongHashSync(data: Uint8Array): string {
    let hash = 0;
    for (let i = 0; i < data.length; i++) {
      hash = ((hash << 5) - hash) + data[i];
      hash = hash & hash; // Convert to 32-bit integer
    }
    return hash.toString(16);
  }
  
  /**
   * Convert ArrayBuffer to hex string
   */
  private static bufferToHex(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    return Array.from(bytes)
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
  }
  
  /**
   * Calculate diff compression ratio
   */
  static calculateCompressionRatio(diff: DiffResult): number {
    const diffSize = diff.patches.reduce((total, patch) => {
      if (patch.type === 'literal') {
        return total + (patch.data?.length || 0) + 12; // 12 bytes for metadata
      } else {
        return total + 16; // 16 bytes for copy instruction
      }
    }, 0);
    
    return 1 - (diffSize / diff.modifiedSize);
  }
}

// Interfaces
interface Block {
  offset: number;
  weakHash: number;
  strongHash: string;
  size: number;
}

interface BlockMap {
  blocks: Block[];
  weakHashes: Map<number, Block[]>;
}

interface DiffPatch {
  type: 'literal' | 'copy';
  offset: number;
  data?: Uint8Array;
  sourceOffset?: number;
  length?: number;
}

interface DiffResult {
  originalSize: number;
  modifiedSize: number;
  patches: DiffPatch[];
}

export default BinaryDiff;
export type { DiffResult, DiffPatch };