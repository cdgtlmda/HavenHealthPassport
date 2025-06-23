import { BackgroundTaskAdapter, BackgroundTask, TaskResult } from '../types';

/**
 * React Native background task adapter
 * Uses react-native-background-fetch and react-native-background-task
 */
export class ReactNativeBackgroundTaskAdapter implements BackgroundTaskAdapter {
  private BackgroundFetch: any;
  private BackgroundTask: any;
  private tasks: Map<string, BackgroundTask> = new Map();

  constructor(BackgroundFetch: any, BackgroundTask?: any) {
    this.BackgroundFetch = BackgroundFetch;
    this.BackgroundTask = BackgroundTask;
  }

  async registerTask(task: BackgroundTask): Promise<boolean> {
    try {
      this.tasks.set(task.id, task);

      if (task.type === 'periodic') {
        // Use BackgroundFetch for periodic tasks
        await this.BackgroundFetch.configure({
          minimumFetchInterval: Math.floor(task.interval! / 60), // Convert to minutes
          stopOnTerminate: false,
          startOnBoot: true,
          enableHeadless: true,
        }, async (taskId: string) => {
          console.log(`[BackgroundFetch] Task ${taskId} started`);
          
          try {
            const result = await this.executeTask(task.id);
            console.log(`[BackgroundFetch] Task ${taskId} completed:`, result);
          } catch (error) {
            console.error(`[BackgroundFetch] Task ${taskId} error:`, error);
          }
          
          this.BackgroundFetch.finish(taskId);
        }, (error: any) => {
          console.error('[BackgroundFetch] Configure error:', error);
        });

        await this.BackgroundFetch.start();
      } else if (task.type === 'immediate' && this.BackgroundTask) {
        // Use BackgroundTask for immediate tasks
        this.BackgroundTask.define(async () => {
          try {
            await this.executeTask(task.id);
          } catch (error) {
            console.error('[BackgroundTask] Error:', error);
          }
        });

        await this.BackgroundTask.schedule({
          period: task.interval ? task.interval / 1000 : 900, // Convert to seconds, default 15 min
        });
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

      if (task.type === 'periodic') {
        await this.BackgroundFetch.stop(taskId);
      } else if (this.BackgroundTask) {
        await this.BackgroundTask.cancel();
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

      if (this.BackgroundTask) {
        await this.BackgroundTask.schedule({
          period: delay / 1000, // Convert to seconds
        });
        return true;
      }

      // Fallback to setTimeout for immediate execution
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

  // React Native specific methods
  async checkStatus(): Promise<{
    available: boolean;
    restricted: boolean;
    denied: boolean;
  }> {
    try {
      const status = await this.BackgroundFetch.status();
      
      return {
        available: status === this.BackgroundFetch.STATUS_AVAILABLE,
        restricted: status === this.BackgroundFetch.STATUS_RESTRICTED,
        denied: status === this.BackgroundFetch.STATUS_DENIED,
      };
    } catch {
      return {
        available: false,
        restricted: false,
        denied: false,
      };
    }
  }

  async enableHeadlessTask(handler: () => Promise<void>): Promise<void> {
    if (this.BackgroundFetch.registerHeadlessTask) {
      this.BackgroundFetch.registerHeadlessTask(handler);
    }
  }
}