import { EventEmitter } from 'events';
import { Image } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

interface LazyLoadConfig {
  preloadCount: number;
  cacheSize: number;
  priorityFetch: boolean;
  placeholder?: any;
  errorFallback?: any;
  retryAttempts: number;
  retryDelay: number;
}

interface LoadableItem {
  id: string;
  priority: number;
  type: 'image' | 'document' | 'data';
  source: string | (() => Promise<any>);
  size?: number;
  metadata?: Record<string, any>;
}

interface LoadState {
  id: string;
  status: 'pending' | 'loading' | 'loaded' | 'error';
  data?: any;
  error?: Error;
  attempts: number;
  lastAttempt?: number;
}

export class LazyLoadManager extends EventEmitter {
  private config: LazyLoadConfig;
  private loadQueue: LoadableItem[] = [];
  private loadStates: Map<string, LoadState> = new Map();
  private cache: Map<string, any> = new Map();
  private activeLoads: Map<string, Promise<any>> = new Map();
  private visibleItems: Set<string> = new Set();
  private loadTimer?: NodeJS.Timeout;
  
  constructor(config: Partial<LazyLoadConfig> = {}) {
    super();
    this.config = {
      preloadCount: 3,
      cacheSize: 50,
      priorityFetch: true,
      retryAttempts: 3,
      retryDelay: 1000,
      ...config,
    };
  }

  /**
   * Register items for lazy loading
   */
  registerItems(items: LoadableItem[]): void {
    items.forEach(item => {
      if (!this.loadStates.has(item.id)) {
        this.loadStates.set(item.id, {
          id: item.id,
          status: 'pending',
          attempts: 0,
        });
        this.loadQueue.push(item);
      }
    });
    
    // Sort by priority if enabled
    if (this.config.priorityFetch) {
      this.loadQueue.sort((a, b) => b.priority - a.priority);
    }
    
    this.processQueue();
  }

  /**
   * Mark items as visible (prioritize loading)
   */
  setVisibleItems(itemIds: string[]): void {
    this.visibleItems.clear();
    itemIds.forEach(id => this.visibleItems.add(id));
    
    // Re-prioritize queue based on visibility
    this.reprioritizeQueue();
    this.processQueue();
  }

  /**
   * Get item data (from cache or load)
   */
  async getItem(itemId: string): Promise<any> {
    // Check cache first
    if (this.cache.has(itemId)) {
      return this.cache.get(itemId);
    }
    
    // Check if already loading
    if (this.activeLoads.has(itemId)) {
      return this.activeLoads.get(itemId);
    }
    
    // Find item in queue
    const item = this.loadQueue.find(i => i.id === itemId);
    if (!item) {
      throw new Error(`Item ${itemId} not registered`);
    }
    
    // Load item
    return this.loadItem(item);
  }

  /**
   * Preload items around a specific index
   */
  preloadAroundIndex(index: number, items: LoadableItem[]): void {
    const startIdx = Math.max(0, index - this.config.preloadCount);
    const endIdx = Math.min(items.length, index + this.config.preloadCount + 1);
    
    const itemsToPreload = items.slice(startIdx, endIdx);
    
    itemsToPreload.forEach(item => {
      if (!this.cache.has(item.id) && !this.activeLoads.has(item.id)) {
        this.loadItem(item).catch(error => {
          console.error(`Preload failed for ${item.id}:`, error);
        });
      }
    });
  }

  /**
   * Clear cache
   */
  clearCache(): void {
    this.cache.clear();
    this.emit('cache-cleared');
  }

  /**
   * Clear specific items from cache
   */
  evictFromCache(itemIds: string[]): void {
    itemIds.forEach(id => {
      this.cache.delete(id);
    });
  }

  /**
   * Get cache statistics
   */
  getCacheStats(): {
    size: number;
    maxSize: number;
    hitRate: number;
    pendingLoads: number;
  } {
    const totalRequests = this.loadStates.size;
    const cachedItems = this.cache.size;
    
    return {
      size: cachedItems,
      maxSize: this.config.cacheSize,
      hitRate: totalRequests > 0 ? cachedItems / totalRequests : 0,
      pendingLoads: this.activeLoads.size,
    };
  }

  /**
   * Private methods
   */
  
  private async loadItem(item: LoadableItem): Promise<any> {
    const loadState = this.loadStates.get(item.id)!;
    loadState.status = 'loading';
    
    const loadPromise = this.performLoad(item);
    this.activeLoads.set(item.id, loadPromise);
    
    try {
      const data = await loadPromise;
      
      // Update state
      loadState.status = 'loaded';
      loadState.data = data;
      
      // Add to cache
      this.addToCache(item.id, data);
      
      // Clean up
      this.activeLoads.delete(item.id);
      
      this.emit('item-loaded', { id: item.id, data });
      return data;
      
    } catch (error) {
      loadState.status = 'error';
      loadState.error = error as Error;
      loadState.attempts++;
      loadState.lastAttempt = Date.now();
      
      this.activeLoads.delete(item.id);
      
      // Retry if attempts remaining
      if (loadState.attempts < this.config.retryAttempts) {
        setTimeout(() => {
          this.loadItem(item);
        }, this.config.retryDelay * loadState.attempts);
      } else {
        this.emit('item-error', { id: item.id, error });
      }
      
      throw error;
    }
  }

  private async performLoad(item: LoadableItem): Promise<any> {
    switch (item.type) {
      case 'image':
        return this.loadImage(item.source as string);
      
      case 'document':
        return this.loadDocument(item.source as string);
      
      case 'data':
        if (typeof item.source === 'function') {
          return item.source();
        } else {
          const response = await fetch(item.source as string);
          return response.json();
        }
      
      default:
        throw new Error(`Unknown item type: ${item.type}`);
    }
  }

  private loadImage(uri: string): Promise<any> {
    return new Promise((resolve, reject) => {
      Image.prefetch(uri)
        .then(() => {
          Image.getSize(
            uri,
            (width, height) => {
              resolve({ uri, width, height });
            },
            reject
          );
        })
        .catch(reject);
    });
  }

  private async loadDocument(uri: string): Promise<any> {
    const response = await fetch(uri);
    const blob = await response.blob();
    return {
      uri,
      size: blob.size,
      type: blob.type,
      blob,
    };
  }

  private addToCache(itemId: string, data: any): void {
    // Implement LRU cache eviction
    if (this.cache.size >= this.config.cacheSize) {
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
      this.emit('cache-eviction', { evictedId: firstKey });
    }
    
    this.cache.set(itemId, data);
  }

  private reprioritizeQueue(): void {
    this.loadQueue.sort((a, b) => {
      const aVisible = this.visibleItems.has(a.id);
      const bVisible = this.visibleItems.has(b.id);
      
      // Visible items have highest priority
      if (aVisible && !bVisible) return -1;
      if (!aVisible && bVisible) return 1;
      
      // Then sort by original priority
      return b.priority - a.priority;
    });
  }

  private processQueue(): void {
    if (this.loadTimer) {
      clearTimeout(this.loadTimer);
    }
    
    this.loadTimer = setTimeout(() => {
      this.processNextBatch();
    }, 100);
  }

  private async processNextBatch(): Promise<void> {
    const maxConcurrent = 3;
    const toLoad: LoadableItem[] = [];
    
    // Find items to load
    for (const item of this.loadQueue) {
      if (this.activeLoads.size >= maxConcurrent) break;
      
      const state = this.loadStates.get(item.id);
      if (state && state.status === 'pending' && !this.cache.has(item.id)) {
        toLoad.push(item);
      }
    }
    
    // Load items
    await Promise.all(
      toLoad.map(item => 
        this.loadItem(item).catch(error => {
          console.error(`Failed to load ${item.id}:`, error);
        })
      )
    );
    
    // Continue processing if more items
    if (this.loadQueue.some(item => {
      const state = this.loadStates.get(item.id);
      return state && state.status === 'pending';
    })) {
      this.processQueue();
    }
  }
}