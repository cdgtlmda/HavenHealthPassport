import { ConflictResolution } from './types';
import { isEqual, merge, cloneDeep } from 'lodash';

export class ConflictResolver {
  private strategy: ConflictResolution;

  constructor(strategy: ConflictResolution) {
    this.strategy = strategy;
  }

  /**
   * Update resolution strategy
   */
  updateStrategy(strategy: ConflictResolution): void {
    this.strategy = strategy;
  }

  /**
   * Resolve conflict based on strategy
   */
  async resolve<T>(local: T, remote: T, ancestor?: T): Promise<T> {
    switch (this.strategy.strategy) {
      case 'local_wins':
        return cloneDeep(local);
        
      case 'remote_wins':
        return cloneDeep(remote);
        
      case 'merge':
        return this.performMerge(local, remote, ancestor);
        
      case 'manual':
        if (this.strategy.resolvedData) {
          return this.strategy.resolvedData;
        }
        throw new Error('Manual resolution required but no resolved data provided');
        
      default:
        throw new Error(`Unknown resolution strategy: ${this.strategy.strategy}`);
    }
  }

  /**
   * Perform automatic merge
   */
  private performMerge<T>(local: T, remote: T, ancestor?: T): T {
    // If custom merge function provided, use it
    if (this.strategy.mergeFunction) {
      return this.strategy.mergeFunction(local, remote, ancestor);
    }

    // Default merge logic
    if (typeof local !== 'object' || typeof remote !== 'object') {
      // For primitive values, prefer local if different
      return isEqual(local, remote) ? local : local;
    }

    // For objects, deep merge
    const merged = cloneDeep(remote) as any;
    const localObj = local as any;
    // If we have ancestor, perform three-way merge
    if (ancestor) {
      const ancestorObj = ancestor as any;
      
      Object.keys(localObj).forEach(key => {
        if (key.startsWith('_')) return; // Skip metadata fields
        
        const localValue = localObj[key];
        const remoteValue = merged[key];
        const ancestorValue = ancestorObj[key];
        
        // If local changed from ancestor but remote didn't, use local
        if (!isEqual(localValue, ancestorValue) && isEqual(remoteValue, ancestorValue)) {
          merged[key] = localValue;
        }
        // If both changed differently, need to merge or conflict
        else if (!isEqual(localValue, ancestorValue) && 
                 !isEqual(remoteValue, ancestorValue) && 
                 !isEqual(localValue, remoteValue)) {
          // For arrays, try to merge
          if (Array.isArray(localValue) && Array.isArray(remoteValue)) {
            merged[key] = this.mergeArrays(localValue, remoteValue, ancestorValue);
          }
          // For objects, recursively merge
          else if (typeof localValue === 'object' && typeof remoteValue === 'object') {
            merged[key] = this.performMerge(localValue, remoteValue, ancestorValue);
          }
          // For primitives, prefer local
          else {
            merged[key] = localValue;
          }
        }
      });
      
      // Add any new fields from local
      Object.keys(localObj).forEach(key => {
        if (!(key in merged) && !key.startsWith('_')) {
          merged[key] = localObj[key];
        }
      });
    } else {
      // Without ancestor, simple merge preferring local for conflicts
      Object.keys(localObj).forEach(key => {
        if (!key.startsWith('_')) {
          merged[key] = localObj[key];
        }
      });
    }

    return merged as T;
  }
  /**
   * Merge arrays intelligently
   */
  private mergeArrays<T>(local: T[], remote: T[], ancestor?: T[]): T[] {
    // For objects with IDs, merge by ID
    if (local.length > 0 && typeof local[0] === 'object' && 'id' in local[0]) {
      return this.mergeArraysByIds(local, remote, ancestor);
    }
    
    // For primitive arrays, union
    const merged = [...new Set([...local, ...remote])];
    
    // If we have ancestor, remove items that were deleted
    if (ancestor) {
      const deletedInLocal = ancestor.filter(item => !local.includes(item));
      const deletedInRemote = ancestor.filter(item => !remote.includes(item));
      const deleted = [...new Set([...deletedInLocal, ...deletedInRemote])];
      
      return merged.filter(item => !deleted.includes(item));
    }
    
    return merged as T[];
  }

  /**
   * Merge arrays of objects by ID
   */
  private mergeArraysByIds<T extends { id: any }>(
    local: T[], 
    remote: T[], 
    ancestor?: T[]
  ): T[] {
    const merged = new Map<any, T>();
    const ancestorMap = new Map(ancestor?.map(item => [item.id, item]) || []);
    
    // Add all remote items
    remote.forEach(item => merged.set(item.id, item));
    
    // Process local items
    local.forEach(localItem => {
      const remoteItem = merged.get(localItem.id);
      const ancestorItem = ancestorMap.get(localItem.id);
      
      if (!remoteItem) {
        // Item only in local
        merged.set(localItem.id, localItem);
      } else if (ancestorItem) {
        // Item in both, merge if needed
        const mergedItem = this.performMerge(localItem, remoteItem, ancestorItem);
        merged.set(localItem.id, mergedItem);
      } else {
        // New item in both, prefer local
        merged.set(localItem.id, localItem);
      }
    });
    
    return Array.from(merged.values());
  }
}

export default ConflictResolver;