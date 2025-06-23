import { EventEmitter } from 'events';

interface LazyLoadOptions {
  threshold?: number; // Distance from viewport to start loading
  rootMargin?: string; // Margin around root
  placeholder?: any; // Placeholder while loading
  errorFallback?: any; // Error state
  retryAttempts?: number;
  retryDelay?: number;
  priority?: 'high' | 'normal' | 'low';
  preload?: boolean; // Preload resource without rendering
}

interface LoadableResource {
  id: string;
  url?: string;
  loader?: () => Promise<any>;
  type: 'image' | 'component' | 'data' | 'module';
  priority: 'high' | 'normal' | 'low';
  size?: number;
  dependencies?: string[];
}

interface LoadState {
  loading: boolean;
  loaded: boolean;
  error: Error | null;
  data: any;
  attempts: number;
}

export class AdvancedLazyLoader extends EventEmitter {
  private loadStates: Map<string, LoadState> = new Map();
  private loadQueue: Map<string, LoadableResource> = new Map();
  private activeLoads: Map<string, Promise<any>> = new Map();
  private intersectionObserver?: IntersectionObserver;
  private performanceObserver?: PerformanceObserver;
  private maxConcurrentLoads = 3;
  private isLoading = false;
  
  constructor() {
    super();
    this.initializeObservers();
    this.startLoadMonitoring();
  }

  /**
   * Register resource for lazy loading
   */
  register(resource: LoadableResource, options: LazyLoadOptions = {}): void {
    const state: LoadState = {
      loading: false,
      loaded: false,
      error: null,
      data: null,
      attempts: 0,
    };
    
    this.loadStates.set(resource.id, state);
    
    if (options.preload) {
      this.preloadResource(resource);
    } else {
      this.loadQueue.set(resource.id, resource);
    }
    
    this.emit('resource-registered', resource);
  }

  /**
   * Observe element for lazy loading
   */
  observe(element: Element, resourceId: string, options: LazyLoadOptions = {}): void {
    if (!this.intersectionObserver) return;
    
    // Store options on element
    (element as any).__lazyLoadOptions = options;
    (element as any).__resourceId = resourceId;
    
    this.intersectionObserver.observe(element);
  }

  /**
   * Unobserve element
   */
  unobserve(element: Element): void {
    if (!this.intersectionObserver) return;
    this.intersectionObserver.unobserve(element);
  }

  /**
   * Load resource immediately
   */
  async loadNow(resourceId: string): Promise<any> {
    const resource = this.loadQueue.get(resourceId);
    if (!resource) {
      throw new Error(`Resource ${resourceId} not found`);
    }
    
    return this.loadResource(resource);
  }

  /**
   * Preload resource without rendering
   */
  private async preloadResource(resource: LoadableResource): Promise<void> {
    try {
      if (resource.type === 'image' && resource.url) {
        await this.preloadImage(resource.url);
      } else if (resource.type === 'module' && resource.loader) {
        // Preload but don't execute
        const module = await resource.loader();
        this.cacheModule(resource.id, module);
      }
      
      this.emit('resource-preloaded', resource);
    } catch (error) {
      this.emit('preload-error', { resource, error });
    }
  }

  /**
   * Load resource with retry logic
   */
  private async loadResource(resource: LoadableResource): Promise<any> {
    const state = this.loadStates.get(resource.id);
    if (!state) return null;
    
    // Check if already loading
    const activeLoad = this.activeLoads.get(resource.id);
    if (activeLoad) return activeLoad;
    
    // Check if already loaded
    if (state.loaded && state.data) {
      return state.data;
    }
    
    state.loading = true;
    this.updateLoadState(resource.id, state);
    
    const loadPromise = this.performLoad(resource, state);
    this.activeLoads.set(resource.id, loadPromise);
    
    try {
      const result = await loadPromise;
      state.loaded = true;
      state.data = result;
      state.loading = false;
      this.updateLoadState(resource.id, state);
      
      this.activeLoads.delete(resource.id);
      this.emit('resource-loaded', { resource, data: result });
      
      return result;
    } catch (error) {
      state.loading = false;
      state.error = error as Error;
      this.updateLoadState(resource.id, state);
      
      this.activeLoads.delete(resource.id);
      this.emit('load-error', { resource, error });
      
      throw error;
    }
  }

  /**
   * Perform actual load operation
   */
  private async performLoad(resource: LoadableResource, state: LoadState): Promise<any> {
    const maxAttempts = 3;
    const baseDelay = 1000;
    
    while (state.attempts < maxAttempts) {
      try {
        state.attempts++;
        
        switch (resource.type) {
          case 'image':
            if (resource.url) {
              return await this.loadImage(resource.url);
            }
            break;
          
          case 'component':
          case 'module':
            if (resource.loader) {
              return await resource.loader();
            }
            break;
          
          case 'data':
            if (resource.url) {
              return await this.loadData(resource.url);
            } else if (resource.loader) {
              return await resource.loader();
            }
            break;
        }
        
        throw new Error('No loader available for resource');
      } catch (error) {
        if (state.attempts >= maxAttempts) {
          throw error;
        }
        
        // Exponential backoff
        const delay = baseDelay * Math.pow(2, state.attempts - 1);
        await this.delay(delay);
      }
    }
    
    throw new Error('Max retry attempts reached');
  }

  /**
   * Load image
   */
  private loadImage(url: string): Promise<HTMLImageElement | string> {
    if (typeof window !== 'undefined') {
      return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = url;
      });
    } else {
      // React Native environment
      return Promise.resolve(url);
    }
  }

  /**
   * Preload image
   */
  private preloadImage(url: string): Promise<void> {
    if (typeof window !== 'undefined') {
      const link = document.createElement('link');
      link.rel = 'preload';
      link.as = 'image';
      link.href = url;
      document.head.appendChild(link);
    }
    return Promise.resolve();
  }

  /**
   * Load data from URL
   */
  private async loadData(url: string): Promise<any> {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to load data: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Cache module
   */
  private cacheModule(id: string, module: any): void {
    const state = this.loadStates.get(id);
    if (state) {
      state.data = module;
      state.loaded = true;
    }
  }

  /**
   * Initialize intersection observer
   */
  private initializeObservers(): void {
    if (typeof window === 'undefined' || !('IntersectionObserver' in window)) {
      return;
    }
    
    this.intersectionObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const element = entry.target as any;
            const resourceId = element.__resourceId;
            
            if (resourceId) {
              this.loadResource(this.loadQueue.get(resourceId)!);
              this.intersectionObserver?.unobserve(element);
            }
          }
        });
      },
      {
        rootMargin: '50px',
        threshold: 0.01,
      }
    );
    
    // Performance observer for monitoring
    if ('PerformanceObserver' in window) {
      this.performanceObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          this.emit('performance-entry', entry);
        }
      });
      
      this.performanceObserver.observe({ entryTypes: ['resource'] });
    }
  }

  /**
   * Start load monitoring
   */
  private startLoadMonitoring(): void {
    setInterval(() => {
      this.processLoadQueue();
    }, 100);
  }

  /**
   * Process load queue based on priority
   */
  private async processLoadQueue(): Promise<void> {
    if (this.isLoading || this.activeLoads.size >= this.maxConcurrentLoads) {
      return;
    }
    
    this.isLoading = true;
    
    // Sort queue by priority
    const sortedQueue = Array.from(this.loadQueue.entries()).sort(([, a], [, b]) => {
      const priorityOrder = { high: 0, normal: 1, low: 2 };
      return priorityOrder[a.priority] - priorityOrder[b.priority];
    });
    
    // Process high priority items first
    for (const [id, resource] of sortedQueue) {
      if (this.activeLoads.size >= this.maxConcurrentLoads) break;
      
      const state = this.loadStates.get(id);
      if (state && !state.loading && !state.loaded) {
        this.loadResource(resource);
      }
    }
    
    this.isLoading = false;
  }

  /**
   * Update load state
   */
  private updateLoadState(id: string, state: LoadState): void {
    this.loadStates.set(id, state);
    this.emit('state-updated', { id, state });
  }

  /**
   * Get load state
   */
  getLoadState(resourceId: string): LoadState | undefined {
    return this.loadStates.get(resourceId);
  }

  /**
   * Clear completed loads from memory
   */
  clearCompleted(): void {
    for (const [id, state] of this.loadStates.entries()) {
      if (state.loaded && !state.loading) {
        this.loadStates.delete(id);
        this.loadQueue.delete(id);
      }
    }
    
    this.emit('cache-cleared');
  }

  /**
   * Set max concurrent loads
   */
  setMaxConcurrentLoads(max: number): void {
    this.maxConcurrentLoads = max;
  }

  /**
   * Helper delay function
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Destroy loader and clean up
   */
  destroy(): void {
    this.intersectionObserver?.disconnect();
    this.performanceObserver?.disconnect();
    this.loadStates.clear();
    this.loadQueue.clear();
    this.activeLoads.clear();
    this.removeAllListeners();
  }
}

export default AdvancedLazyLoader;