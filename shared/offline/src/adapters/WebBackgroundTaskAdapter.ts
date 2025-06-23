import { BackgroundTaskAdapter, BackgroundTask, TaskResult } from '../types';

/**
 * Web background task adapter
 * Uses Service Workers and Background Sync API
 */
export class WebBackgroundTaskAdapter implements BackgroundTaskAdapter {
  private tasks: Map<string, BackgroundTask> = new Map();
  private serviceWorkerRegistration?: ServiceWorkerRegistration;
  private intervals: Map<string, number> = new Map();

  async initialize(): Promise<void> {
    if ('serviceWorker' in navigator) {
      this.serviceWorkerRegistration = await navigator.serviceWorker.ready;
    }
  }

  async registerTask(task: BackgroundTask): Promise<boolean> {
    try {
      this.tasks.set(task.id, task);

      if (task.type === 'periodic') {
        // Use setInterval for periodic tasks
        const intervalId = window.setInterval(
          () => this.executeTask(task.id),
          task.interval || 900000 // Default 15 minutes
        );
        this.intervals.set(task.id, intervalId);
      } else if (task.type === 'sync' && this.serviceWorkerRegistration) {
        // Register for background sync
        await this.serviceWorkerRegistration.sync.register(`task-${task.id}`);
      } else if (task.type === 'immediate') {
        // Execute immediately
        setTimeout(() => this.executeTask(task.id), 0);
      }

      return true;
    } catch (error: any) {
      console.error('Failed to register background task:', error);
      return false;
    }
  }

  async unregisterTask(taskId: string): Promise<boolean> {
    try {
      const task = this.tasks.get(taskId);
      if (!task) return false;

      // Clear interval if exists
      const intervalId = this.intervals.get(taskId);
      if (intervalId) {
        clearInterval(intervalId);
        this.intervals.delete(taskId);
      }

      this.tasks.delete(taskId);
      return true;
    } catch (error: any) {
      console.error('Failed to unregister background task:', error);
      return false;
    }
  }

  async executeTask(taskId: string): Promise<TaskResult> {
    const task = this.tasks.get(taskId);
    if (!task) {
      return {
        success: false,
        error: 'Task not found',
      };
    }

    const startTime = Date.now();
    
    try {
      const result = await task.handler();
      
      return {
        success: true,
        duration: Date.now() - startTime,
        data: result,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message,
        duration: Date.now() - startTime,
      };
    }
  }

  async scheduleTask(taskId: string, delay: number): Promise<boolean> {
    try {
      const task = this.tasks.get(taskId);
      if (!task) return false;

      setTimeout(() => this.executeTask(taskId), delay);
      return true;
    } catch (error: any) {
      console.error('Failed to schedule task:', error);
      return false;
    }
  }

  async getAllTasks(): Promise<BackgroundTask[]> {
    return Array.from(this.tasks.values());
  }

  async getTaskStatus(taskId: string): Promise<'idle' | 'running' | 'completed' | 'failed'> {
    const task = this.tasks.get(taskId);
    if (!task) return 'idle';

    // This is simplified - in a real implementation, you'd track actual status
    return 'idle';
  }

  // Web specific methods
  async requestPersistentStorage(): Promise<boolean> {
    if ('storage' in navigator && 'persist' in navigator.storage) {
      return await navigator.storage.persist();
    }
    return false;
  }

  async registerPeriodicSync(
    tag: string,
    minInterval: number
  ): Promise<boolean> {
    if (!this.serviceWorkerRegistration) return false;

    try {
      const registration = this.serviceWorkerRegistration as any;
      if ('periodicSync' in registration) {
        await registration.periodicSync.register(tag, {
          minInterval,
        });
        return true;
      }
    } catch (error) {
      console.error('Periodic sync registration failed:', error);
    }
    return false;
  }

  async checkPermissions(): Promise<{
    notifications: boolean;
    backgroundSync: boolean;
    persistentStorage: boolean;
  }> {
    const permissions: any = {
      notifications: false,
      backgroundSync: false,
      persistentStorage: false,
    };

    try {
      // Check notification permission
      if ('Notification' in window) {
        permissions.notifications = Notification.permission === 'granted';
      }

      // Check background sync support
      if (this.serviceWorkerRegistration && 'sync' in this.serviceWorkerRegistration) {
        permissions.backgroundSync = true;
      }

      // Check persistent storage
      if ('storage' in navigator && 'persisted' in navigator.storage) {
        permissions.persistentStorage = await navigator.storage.persisted();
      }
    } catch (error) {
      console.error('Error checking permissions:', error);
    }

    return permissions;
  }
}