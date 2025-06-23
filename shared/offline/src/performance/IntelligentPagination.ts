import { EventEmitter } from 'events';

interface PaginationConfig {
  pageSize: number;
  prefetchPages: number;
  cachePages: number;
  enableInfiniteScroll: boolean;
  enableJumpToPage: boolean;
  adaptivePageSize: boolean;
}

interface Page<T> {
  pageNumber: number;
  items: T[];
  totalItems: number;
  totalPages: number;
  hasNext: boolean;
  hasPrevious: boolean;
}

interface PageCache<T> {
  page: Page<T>;
  timestamp: number;
  accessCount: number;
}

export class IntelligentPagination<T> extends EventEmitter {
  private config: PaginationConfig;
  private pageCache: Map<number, PageCache<T>> = new Map();
  private currentPage = 1;
  private totalItems = 0;
  private totalPages = 0;
  private dataFetcher: (page: number, pageSize: number) => Promise<Page<T>>;
  private prefetchQueue: Set<number> = new Set();
  private isLoading = false;
  private performanceMetrics = {
    averageLoadTime: 0,
    loadCount: 0,
    cacheHits: 0,
    cacheMisses: 0,
  };
  
  constructor(
    dataFetcher: (page: number, pageSize: number) => Promise<Page<T>>,
    config: Partial<PaginationConfig> = {}
  ) {
    super();
    this.dataFetcher = dataFetcher;
    this.config = {
      pageSize: 20,
      prefetchPages: 2,
      cachePages: 5,
      enableInfiniteScroll: true,
      enableJumpToPage: true,
      adaptivePageSize: true,
      ...config,
    };
  }

  /**
   * Get page data
   */
  async getPage(pageNumber: number): Promise<Page<T>> {
    // Validate page number
    if (pageNumber < 1) {
      throw new Error('Page number must be greater than 0');
    }
    
    // Check cache first
    const cached = this.getFromCache(pageNumber);
    if (cached) {
      this.performanceMetrics.cacheHits++;
      this.prefetchAdjacentPages(pageNumber);
      return cached;
    }
    
    // Cache miss
    this.performanceMetrics.cacheMisses++;
    
    // Load page
    const page = await this.loadPage(pageNumber);
    
    // Update current page
    this.currentPage = pageNumber;
    
    // Prefetch adjacent pages
    this.prefetchAdjacentPages(pageNumber);
    
    return page;
  }

  /**
   * Get next page
   */
  async nextPage(): Promise<Page<T> | null> {
    if (this.currentPage >= this.totalPages) {
      return null;
    }
    
    return this.getPage(this.currentPage + 1);
  }

  /**
   * Get previous page
   */
  async previousPage(): Promise<Page<T> | null> {
    if (this.currentPage <= 1) {
      return null;
    }
    
    return this.getPage(this.currentPage - 1);
  }

  /**
   * Jump to specific page
   */
  async jumpToPage(pageNumber: number): Promise<Page<T>> {
    if (!this.config.enableJumpToPage) {
      throw new Error('Jump to page is disabled');
    }
    
    // Clear prefetch queue for big jumps
    if (Math.abs(pageNumber - this.currentPage) > 5) {
      this.prefetchQueue.clear();
    }
    
    return this.getPage(pageNumber);
  }

  /**
   * Get multiple pages for infinite scroll
   */
  async getInfiniteScrollData(
    startPage: number,
    endPage: number
  ): Promise<T[]> {
    if (!this.config.enableInfiniteScroll) {
      throw new Error('Infinite scroll is disabled');
    }
    
    const pages = await Promise.all(
      Array.from({ length: endPage - startPage + 1 }, (_, i) => 
        this.getPage(startPage + i)
      )
    );
    
    return pages.flatMap(page => page.items);
  }

  /**
   * Refresh current page
   */
  async refreshCurrentPage(): Promise<Page<T>> {
    this.removeFromCache(this.currentPage);
    return this.getPage(this.currentPage);
  }

  /**
   * Clear cache
   */
  clearCache(): void {
    this.pageCache.clear();
    this.prefetchQueue.clear();
    this.emit('cache-cleared');
  }

  /**
   * Get pagination info
   */
  getPaginationInfo(): {
    currentPage: number;
    totalPages: number;
    totalItems: number;
    pageSize: number;
    hasPrevious: boolean;
    hasNext: boolean;
  } {
    return {
      currentPage: this.currentPage,
      totalPages: this.totalPages,
      totalItems: this.totalItems,
      pageSize: this.getCurrentPageSize(),
      hasPrevious: this.currentPage > 1,
      hasNext: this.currentPage < this.totalPages,
    };
  }

  /**
   * Get performance metrics
   */
  getPerformanceMetrics() {
    return {
      ...this.performanceMetrics,
      cacheHitRate: this.performanceMetrics.cacheHits / 
        (this.performanceMetrics.cacheHits + this.performanceMetrics.cacheMisses),
      averageLoadTimeMs: this.performanceMetrics.averageLoadTime,
    };
  }

  /**
   * Private methods
   */
  
  private async loadPage(pageNumber: number): Promise<Page<T>> {
    if (this.isLoading) {
      // Wait for current load to complete
      await new Promise(resolve => {
        const checkLoading = setInterval(() => {
          if (!this.isLoading) {
            clearInterval(checkLoading);
            resolve(undefined);
          }
        }, 50);
      });
    }
    
    this.isLoading = true;
    const startTime = Date.now();
    
    try {
      const pageSize = this.getCurrentPageSize();
      const page = await this.dataFetcher(pageNumber, pageSize);
      
      // Update metrics
      const loadTime = Date.now() - startTime;
      this.updatePerformanceMetrics(loadTime);
      
      // Update totals
      this.totalItems = page.totalItems;
      this.totalPages = page.totalPages;
      
      // Cache page
      this.addToCache(pageNumber, page);
      
      this.emit('page-loaded', { pageNumber, itemCount: page.items.length });
      
      return page;
    } finally {
      this.isLoading = false;
    }
  }

  private getCurrentPageSize(): number {
    if (!this.config.adaptivePageSize) {
      return this.config.pageSize;
    }
    
    // Adapt page size based on performance
    const avgLoadTime = this.performanceMetrics.averageLoadTime;
    
    if (avgLoadTime > 2000 && this.config.pageSize > 10) {
      // Reduce page size if loading is slow
      return Math.floor(this.config.pageSize * 0.75);
    } else if (avgLoadTime < 500 && this.config.pageSize < 50) {
      // Increase page size if loading is fast
      return Math.floor(this.config.pageSize * 1.25);
    }
    
    return this.config.pageSize;
  }

  private getFromCache(pageNumber: number): Page<T> | null {
    const cached = this.pageCache.get(pageNumber);
    
    if (cached) {
      // Check if cache is still valid (5 minutes)
      const cacheAge = Date.now() - cached.timestamp;
      if (cacheAge < 5 * 60 * 1000) {
        cached.accessCount++;
        return cached.page;
      } else {
        // Remove stale cache
        this.pageCache.delete(pageNumber);
      }
    }
    
    return null;
  }

  private addToCache(pageNumber: number, page: Page<T>): void {
    // Implement LRU cache with access count consideration
    if (this.pageCache.size >= this.config.cachePages) {
      // Find least recently/frequently used page
      let lruPage: number | null = null;
      let minScore = Infinity;
      
      for (const [num, cache] of this.pageCache.entries()) {
        // Skip current page and adjacent pages
        if (Math.abs(num - this.currentPage) <= 1) continue;
        
        // Calculate score (lower is worse)
        const age = Date.now() - cache.timestamp;
        const score = cache.accessCount * 1000 / age;
        
        if (score < minScore) {
          minScore = score;
          lruPage = num;
        }
      }
      
      if (lruPage !== null) {
        this.pageCache.delete(lruPage);
        this.emit('cache-eviction', { pageNumber: lruPage });
      }
    }
    
    this.pageCache.set(pageNumber, {
      page,
      timestamp: Date.now(),
      accessCount: 1,
    });
  }

  private removeFromCache(pageNumber: number): void {
    this.pageCache.delete(pageNumber);
  }

  private prefetchAdjacentPages(currentPage: number): void {
    const pagesToPrefetch: number[] = [];
    
    // Prefetch next pages
    for (let i = 1; i <= this.config.prefetchPages; i++) {
      const nextPage = currentPage + i;
      if (nextPage <= this.totalPages && !this.pageCache.has(nextPage)) {
        pagesToPrefetch.push(nextPage);
      }
    }
    
    // Prefetch previous page (less priority)
    const prevPage = currentPage - 1;
    if (prevPage >= 1 && !this.pageCache.has(prevPage)) {
      pagesToPrefetch.push(prevPage);
    }
    
    // Add to prefetch queue
    pagesToPrefetch.forEach(page => this.prefetchQueue.add(page));
    
    // Process prefetch queue
    this.processPrefetchQueue();
  }

  private async processPrefetchQueue(): Promise<void> {
    if (this.prefetchQueue.size === 0) return;
    
    const pagesToFetch = Array.from(this.prefetchQueue).slice(0, 2);
    this.prefetchQueue.clear();
    
    // Prefetch in background
    Promise.all(
      pagesToFetch.map(page => 
        this.loadPage(page).catch(error => {
          console.error(`Prefetch failed for page ${page}:`, error);
        })
      )
    );
  }

  private updatePerformanceMetrics(loadTime: number): void {
    this.performanceMetrics.loadCount++;
    this.performanceMetrics.averageLoadTime = 
      (this.performanceMetrics.averageLoadTime * (this.performanceMetrics.loadCount - 1) + loadTime) /
      this.performanceMetrics.loadCount;
  }
}

export default IntelligentPagination;