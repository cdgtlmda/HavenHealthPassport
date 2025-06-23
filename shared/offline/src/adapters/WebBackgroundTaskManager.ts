import { BackgroundTaskManager, BackgroundTask, BackgroundTaskOptions, BackgroundTaskResult } from '../types';

export class WebBackgroundTaskManager implements BackgroundTaskManager {
  private tasks: Map<string, BackgroundTask> = new Map();
  private serviceWorkerRegistration: ServiceWorkerRegistration | null = null;
  private periodicTasks: Map<string, number> = new Map(); // taskId -> intervalId

  async initialize(): Promise<void> {
    // Register service worker if not already registered
    if ('serviceWorker' in navigator) {
      try {
        this.serviceWorkerRegistration = await navigator.serviceWorker.register(
          '/sw-background-tasks.js'
        );
        console.log('Service Worker registered for background tasks');

        // Listen for messages from service worker
        navigator.serviceWorker.addEventListener('message', this.handleServiceWorkerMessage);
      } catch (error) {
        console.error('Failed to register service worker:', error);
      }
    }

    // Check for Background Sync API support
    if ('sync' in ServiceWorkerRegistration.prototype) {
      console.log('Background Sync API is supported');
    } else {
      console.warn('Background Sync API is not supported, using fallback');
    }

    // Check for Periodic Background Sync API support
    if ('periodicSync' in ServiceWorkerRegistration.prototype) {
      console.log('Periodic Background Sync API is supported');
    } else {
      console.warn('Periodic Background Sync API is not supported, using fallback');
    }
  }

  async registerTask(
    taskId: string,
    task: BackgroundTask,
    options?: BackgroundTaskOptions
  ): Promise<void> {
    this.tasks.set(taskId, task);

    if (options?.type === 'periodic') {
      await this.registerPeriodicTask(taskId, task, options);
    } else if (options?.type === 'oneshot') {
      await this.registerOneshotTask(taskId, task, options);
    } else {
      // Default to oneshot
      await this.registerOneshotTask(taskId, task, options);
    }
  }

  private async registerPeriodicTask(
    taskId: string,
    task: BackgroundTask,
    options?: BackgroundTaskOptions
  ): Promise<void> {
    // Try to use Periodic Background Sync API
    if (this.serviceWorkerRegistration && 'periodicSync' in this.serviceWorkerRegistration) {
      try {
        await (this.serviceWorkerRegistration as any).periodicSync.register(taskId, {
          minInterval: options?.interval || 12 * 60 * 60 * 1000, // 12 hours default
        });
        console.log(`Registered periodic background sync: ${taskId}`);
        return;
      } catch (error) {
        console.warn('Failed to register periodic background sync:', error);
      }
    }

    // Fallback: Use setInterval
    const intervalId = window.setInterval(async () => {
      try {
        await task.execute();
      } catch (error) {
        console.error(`Error executing periodic task ${taskId}:`, error);
      }
    }, options?.interval || 15 * 60 * 1000); // 15 minutes default

    this.periodicTasks.set(taskId, intervalId);
  }

  private async registerOneshotTask(
    taskId: string,
    task: BackgroundTask,
    options?: BackgroundTaskOptions
  ): Promise<void> {
    // Try to use Background Sync API
    if (this.serviceWorkerRegistration && 'sync' in this.serviceWorkerRegistration) {
      try {
        await this.serviceWorkerRegistration.sync.register(taskId);
        console.log(`Registered background sync: ${taskId}`);
        
        // Store task data in IndexedDB for service worker to access
        await this.storeTaskData(taskId, task, options);
        return;
      } catch (error) {
        console.warn('Failed to register background sync:', error);
      }
    }

    // Fallback: Use setTimeout
    const delay = options?.delay || 0;
    setTimeout(async () => {
      try {
        await task.execute();
      } catch (error) {
        console.error(`Error executing oneshot task ${taskId}:`, error);
      }
    }, delay);
  }

  async unregisterTask(taskId: string): Promise<void> {
    this.tasks.delete(taskId);
    
    // Clear periodic task if exists
    const intervalId = this.periodicTasks.get(taskId);
    if (intervalId !== undefined) {
      clearInterval(intervalId);
      this.periodicTasks.delete(taskId);
    }

    // Try to unregister from Periodic Background Sync
    if (this.serviceWorkerRegistration && 'periodicSync' in this.serviceWorkerRegistration) {
      try {
        await (this.serviceWorkerRegistration as any).periodicSync.unregister(taskId);
      } catch (error) {
        console.warn('Failed to unregister periodic sync:', error);
      }
    }

    // Remove task data from IndexedDB
    await this.removeTaskData(taskId);
  }

  async executeTask(taskId: string): Promise<BackgroundTaskResult> {
    const task = this.tasks.get(taskId);
    
    if (!task) {
      return {
        success: false,
        error: 'Task not found',
      };
    }

    try {
      const result = await task.execute();
      return result;
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  async isTaskRegistered(taskId: string): Promise<boolean> {
    if (!this.tasks.has(taskId)) {
      return false;
    }

    // Check if registered in Periodic Background Sync
    if (this.serviceWorkerRegistration && 'periodicSync' in this.serviceWorkerRegistration) {
      try {
        const tags = await (this.serviceWorkerRegistration as any).periodicSync.getTags();
        if (tags.includes(taskId)) {
          return true;
        }
      } catch (error) {
        console.warn('Failed to get periodic sync tags:', error);
      }
    }

    // Check if in periodic tasks map
    return this.periodicTasks.has(taskId);
  }
  async getRegisteredTasks(): Promise<string[]> {
    const tasks: string[] = Array.from(this.tasks.keys());
    
    // Also check service worker registered tasks
    if (this.serviceWorkerRegistration && 'periodicSync' in this.serviceWorkerRegistration) {
      try {
        const tags = await (this.serviceWorkerRegistration as any).periodicSync.getTags();
        tags.forEach((tag: string) => {
          if (!tasks.includes(tag)) {
            tasks.push(tag);
          }
        });
      } catch (error) {
        console.warn('Failed to get periodic sync tags:', error);
      }
    }
    
    return tasks;
  }

  async stopAllTasks(): Promise<void> {
    const taskIds = Array.from(this.tasks.keys());
    
    for (const taskId of taskIds) {
      await this.unregisterTask(taskId);
    }
  }

  async getTaskStatus(taskId: string): Promise<{
    isRegistered: boolean;
    lastExecution?: number;
    nextScheduledExecution?: number;
  }> {
    const isRegistered = await this.isTaskRegistered(taskId);
    
    // Get task execution history from IndexedDB
    const taskData = await this.getTaskData(taskId);
    
    return {
      isRegistered,
      lastExecution: taskData?.lastExecution,
      nextScheduledExecution: taskData?.nextScheduledExecution,
    };
  }

  // Platform-specific methods
  async requestBackgroundPermissions(): Promise<boolean> {
    // Check if we have permission for notifications (often required for background sync)
    if ('Notification' in window && Notification.permission !== 'granted') {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        console.warn('Notification permission denied, background sync may be limited');
      }
    }
    
    // Check if periodic background sync permission is needed
    if ('permissions' in navigator) {
      try {
        const result = await navigator.permissions.query({ name: 'periodic-background-sync' } as any);
        return result.state === 'granted';
      } catch (error) {
        // Permission API might not support periodic-background-sync
        console.warn('Could not query periodic-background-sync permission:', error);
      }
    }
    
    // Assume we have permission if APIs are available
    return 'serviceWorker' in navigator;
  }

  async minimizeBatteryUsage(enabled: boolean): Promise<void> {
    // Web doesn't have direct battery optimization controls
    // We can adjust task intervals instead
    if (enabled) {
      // Increase intervals for all periodic tasks
      const taskIds = Array.from(this.tasks.keys());
      
      for (const taskId of taskIds) {
        const task = this.tasks.get(taskId);
        if (task && task.options?.type === 'periodic') {
          await this.unregisterTask(taskId);
          await this.registerTask(taskId, task, {
            ...task.options,
            interval: (task.options.interval || 15 * 60 * 1000) * 2, // Double the interval
          });
        }
      }
    }
  }
  // Helper methods
  private handleServiceWorkerMessage = async (event: MessageEvent) => {
    const { type, taskId, data } = event.data;
    
    if (type === 'execute-task') {
      const result = await this.executeTask(taskId);
      
      // Send result back to service worker
      if (event.ports[0]) {
        event.ports[0].postMessage({ type: 'task-result', taskId, result });
      }
    } else if (type === 'task-completed') {
      // Update task execution history
      await this.updateTaskExecutionHistory(taskId, data);
    }
  };

  private async storeTaskData(
    taskId: string,
    task: BackgroundTask,
    options?: BackgroundTaskOptions
  ): Promise<void> {
    const db = await this.openTaskDB();
    const tx = db.transaction(['tasks'], 'readwrite');
    const store = tx.objectStore('tasks');
    
    await store.put({
      taskId,
      options,
      createdAt: Date.now(),
      lastExecution: null,
      nextScheduledExecution: options?.delay 
        ? Date.now() + options.delay 
        : Date.now() + (options?.interval || 0),
    });
  }

  private async getTaskData(taskId: string): Promise<any> {
    const db = await this.openTaskDB();
    const tx = db.transaction(['tasks'], 'readonly');
    const store = tx.objectStore('tasks');
    
    return await store.get(taskId);
  }

  private async removeTaskData(taskId: string): Promise<void> {
    const db = await this.openTaskDB();
    const tx = db.transaction(['tasks'], 'readwrite');
    const store = tx.objectStore('tasks');
    
    await store.delete(taskId);
  }

  private async updateTaskExecutionHistory(taskId: string, data: any): Promise<void> {
    const db = await this.openTaskDB();
    const tx = db.transaction(['tasks'], 'readwrite');
    const store = tx.objectStore('tasks');
    
    const existing = await store.get(taskId);
    if (existing) {
      existing.lastExecution = Date.now();
      existing.nextScheduledExecution = existing.options?.interval 
        ? Date.now() + existing.options.interval
        : null;
      
      await store.put(existing);
    }
  }

  private async openTaskDB(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('HavenBackgroundTasks', 1);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains('tasks')) {
          db.createObjectStore('tasks', { keyPath: 'taskId' });
        }
      };
    });
  }
}