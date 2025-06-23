import { EventEmitter } from 'events';

interface WindowConfig {
  windowSize: number;
  slideSize: number;
  maxWindows: number;
  aggregateFunction?: (data: any[]) => any;
  timeBasedWindow?: boolean;
  windowDuration?: number; // milliseconds
}

interface DataWindow<T> {
  id: string;
  startIndex: number;
  endIndex: number;
  startTime?: number;
  endTime?: number;
  data: T[];
  aggregatedValue?: any;
  metadata: Record<string, any>;
}

export class DataWindowManager<T> extends EventEmitter {
  private config: WindowConfig;
  private windows: Map<string, DataWindow<T>> = new Map();
  private dataBuffer: T[] = [];
  private timeBuffer: Array<{ data: T; timestamp: number }> = [];
  private currentWindowId = 0;
  
  constructor(config: Partial<WindowConfig> = {}) {
    super();
    this.config = {
      windowSize: 100,
      slideSize: 50,
      maxWindows: 10,
      timeBasedWindow: false,
      windowDuration: 60000, // 1 minute default
      ...config,
    };
  }

  /**
   * Add data to the window manager
   */
  addData(data: T | T[]): void {
    const items = Array.isArray(data) ? data : [data];
    const timestamp = Date.now();
    
    if (this.config.timeBasedWindow) {
      // Add to time buffer
      items.forEach(item => {
        this.timeBuffer.push({ data: item, timestamp });
      });
      
      // Clean old data
      this.cleanTimeBuffer();
      
      // Create time-based windows
      this.createTimeWindows();
    } else {
      // Add to regular buffer
      this.dataBuffer.push(...items);
      
      // Create index-based windows
      this.createIndexWindows();
    }
    
    // Clean old windows if exceeds max
    this.cleanOldWindows();
    
    this.emit('data-added', { count: items.length });
  }

  /**
   * Get current window
   */
  getCurrentWindow(): DataWindow<T> | null {
    const windowIds = Array.from(this.windows.keys()).sort();
    if (windowIds.length === 0) return null;
    
    const latestId = windowIds[windowIds.length - 1];
    return this.windows.get(latestId) || null;
  }

  /**
   * Get all windows
   */
  getAllWindows(): DataWindow<T>[] {
    return Array.from(this.windows.values());
  }

  /**
   * Get window by ID
   */
  getWindow(windowId: string): DataWindow<T> | null {
    return this.windows.get(windowId) || null;
  }

  /**
   * Get sliding windows over a range
   */
  getSlidingWindows(startIndex: number, endIndex: number): DataWindow<T>[] {
    const windows: DataWindow<T>[] = [];
    
    for (let i = startIndex; i <= endIndex - this.config.windowSize; i += this.config.slideSize) {
      const window = this.createWindow(
        this.dataBuffer.slice(i, i + this.config.windowSize),
        i,
        i + this.config.windowSize - 1
      );
      windows.push(window);
    }
    
    return windows;
  }

  /**
   * Apply function to all windows
   */
  mapWindows<R>(fn: (window: DataWindow<T>) => R): R[] {
    return Array.from(this.windows.values()).map(fn);
  }

  /**
   * Filter windows
   */
  filterWindows(predicate: (window: DataWindow<T>) => boolean): DataWindow<T>[] {
    return Array.from(this.windows.values()).filter(predicate);
  }

  /**
   * Get aggregated values for all windows
   */
  getAggregatedValues(): Array<{ windowId: string; value: any }> {
    return this.mapWindows(window => ({
      windowId: window.id,
      value: window.aggregatedValue,
    }));
  }

  /**
   * Clear all windows
   */
  clear(): void {
    this.windows.clear();
    this.dataBuffer = [];
    this.timeBuffer = [];
    this.currentWindowId = 0;
    this.emit('cleared');
  }

  /**
   * Get statistics
   */
  getStatistics(): {
    totalWindows: number;
    totalDataPoints: number;
    oldestWindow?: DataWindow<T>;
    newestWindow?: DataWindow<T>;
    averageWindowSize: number;
  } {
    const windows = Array.from(this.windows.values());
    const totalDataPoints = windows.reduce((sum, w) => sum + w.data.length, 0);
    
    return {
      totalWindows: windows.length,
      totalDataPoints,
      oldestWindow: windows[0],
      newestWindow: windows[windows.length - 1],
      averageWindowSize: windows.length > 0 ? totalDataPoints / windows.length : 0,
    };
  }

  /**
   * Private methods
   */
  
  private createIndexWindows(): void {
    // Check if we have enough data for a new window
    while (this.dataBuffer.length >= this.config.windowSize) {
      const windowData = this.dataBuffer.slice(0, this.config.windowSize);
      const startIndex = this.currentWindowId * this.config.slideSize;
      const endIndex = startIndex + this.config.windowSize - 1;
      
      const window = this.createWindow(windowData, startIndex, endIndex);
      this.windows.set(window.id, window);
      
      // Slide the buffer
      this.dataBuffer = this.dataBuffer.slice(this.config.slideSize);
      this.currentWindowId++;
      
      this.emit('window-created', window);
    }
  }

  private createTimeWindows(): void {
    const now = Date.now();
    const windowStart = now - this.config.windowDuration!;
    
    // Get data within the time window
    const windowData = this.timeBuffer
      .filter(item => item.timestamp >= windowStart)
      .map(item => item.data);
    
    if (windowData.length > 0) {
      const window = this.createWindow(
        windowData,
        0,
        windowData.length - 1,
        windowStart,
        now
      );
      
      // Only create new window if it's different from the last one
      const lastWindow = this.getCurrentWindow();
      if (!lastWindow || window.data.length !== lastWindow.data.length) {
        this.windows.set(window.id, window);
        this.emit('window-created', window);
      }
    }
  }

  private createWindow(
    data: T[],
    startIndex: number,
    endIndex: number,
    startTime?: number,
    endTime?: number
  ): DataWindow<T> {
    const window: DataWindow<T> = {
      id: `window_${Date.now()}_${this.currentWindowId}`,
      startIndex,
      endIndex,
      startTime,
      endTime,
      data: [...data],
      metadata: {
        created: Date.now(),
        size: data.length,
      },
    };
    
    // Apply aggregation if configured
    if (this.config.aggregateFunction) {
      window.aggregatedValue = this.config.aggregateFunction(data);
    }
    
    return window;
  }

  private cleanTimeBuffer(): void {
    const cutoff = Date.now() - this.config.windowDuration! * 2;
    this.timeBuffer = this.timeBuffer.filter(item => item.timestamp > cutoff);
  }

  private cleanOldWindows(): void {
    if (this.windows.size <= this.config.maxWindows) return;
    
    const windowIds = Array.from(this.windows.keys()).sort();
    const toRemove = windowIds.slice(0, windowIds.length - this.config.maxWindows);
    
    toRemove.forEach(id => {
      this.windows.delete(id);
      this.emit('window-removed', { windowId: id });
    });
  }
}

// Specialized window managers
export class TumblingWindow<T> extends DataWindowManager<T> {
  constructor(windowSize: number, aggregateFunction?: (data: T[]) => any) {
    super({
      windowSize,
      slideSize: windowSize, // No overlap
      aggregateFunction,
    });
  }
}

export class SlidingWindow<T> extends DataWindowManager<T> {
  constructor(
    windowSize: number,
    slideSize: number,
    aggregateFunction?: (data: T[]) => any
  ) {
    super({
      windowSize,
      slideSize,
      aggregateFunction,
    });
  }
}

export class SessionWindow<T> extends DataWindowManager<T> {
  private sessionTimeout: number;
  private lastActivityTime = 0;
  
  constructor(sessionTimeout: number, aggregateFunction?: (data: T[]) => any) {
    super({
      windowSize: Infinity,
      timeBasedWindow: true,
      aggregateFunction,
    });
    this.sessionTimeout = sessionTimeout;
  }
  
  addData(data: T | T[]): void {
    const now = Date.now();
    
    // Check if session expired
    if (now - this.lastActivityTime > this.sessionTimeout) {
      // Start new session
      this.createNewSession();
    }
    
    this.lastActivityTime = now;
    super.addData(data);
  }
  
  private createNewSession(): void {
    // Implementation for session-based windowing
    this.emit('session-ended');
    this.emit('session-started');
  }
}

export default DataWindowManager;