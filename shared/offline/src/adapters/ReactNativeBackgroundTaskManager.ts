import BackgroundFetch from 'react-native-background-fetch';
import * as TaskManager from 'expo-task-manager';
import * as BackgroundFetch from 'expo-background-fetch';
import { BackgroundTaskManager, BackgroundTask, BackgroundTaskOptions, BackgroundTaskResult } from '../types';

const BACKGROUND_FETCH_TASK = 'haven-background-fetch';
const BACKGROUND_SYNC_TASK = 'haven-background-sync';

export class ReactNativeBackgroundTaskManager implements BackgroundTaskManager {
  private tasks: Map<string, BackgroundTask> = new Map();
  private isInitialized = false;

  async initialize(): Promise<void> {
    if (this.isInitialized) return;

    // Define background fetch task
    TaskManager.defineTask(BACKGROUND_FETCH_TASK, async () => {
      try {
        const task = this.tasks.get(BACKGROUND_FETCH_TASK);
        if (task) {
          const result = await task.execute();
          return result.success 
            ? BackgroundFetch.Result.NewData
            : BackgroundFetch.Result.Failed;
        }
        return BackgroundFetch.Result.NoData;
      } catch (error) {
        console.error('Background fetch error:', error);
        return BackgroundFetch.Result.Failed;
      }
    });

    // Define background sync task
    TaskManager.defineTask(BACKGROUND_SYNC_TASK, async () => {
      try {
        const task = this.tasks.get(BACKGROUND_SYNC_TASK);
        if (task) {
          const result = await task.execute();
          return result.success 
            ? BackgroundFetch.Result.NewData
            : BackgroundFetch.Result.Failed;
        }
        return BackgroundFetch.Result.NoData;
      } catch (error) {
        console.error('Background sync error:', error);
        return BackgroundFetch.Result.Failed;
      }
    });

    // Configure react-native-background-fetch
    await BackgroundFetch.configure({
      minimumFetchInterval: 15, // 15 minutes
      stopOnTerminate: false,
      startOnBoot: true,
      enableHeadless: true,
      requiresBatteryNotLow: false,
      requiresCharging: false,
      requiresStorageNotLow: false,
      requiresDeviceIdle: false,
      requiredNetworkType: BackgroundFetch.NETWORK_TYPE_ANY,
    }, async (taskId) => {
      console.log('[BackgroundFetch] taskId:', taskId);
      
      const task = this.tasks.get(taskId);
      if (task) {
        try {
          await task.execute();
          BackgroundFetch.finish(taskId);
        } catch (error) {
          console.error('[BackgroundFetch] Error:', error);
          BackgroundFetch.finish(taskId);
        }
      }
    }, (taskId) => {
      console.log('[BackgroundFetch] TIMEOUT taskId:', taskId);
      BackgroundFetch.finish(taskId);
    });

    this.isInitialized = true;
  }

  async registerTask(
    taskId: string,
    task: BackgroundTask,
    options?: BackgroundTaskOptions
  ): Promise<void> {
    this.tasks.set(taskId, task);

    if (options?.type === 'periodic') {
      // Register with expo-background-fetch
      await BackgroundFetch.registerTaskAsync(taskId, {
        minimumInterval: options.interval || 15 * 60, // 15 minutes default
        stopOnTerminate: false,
        startOnBoot: true,
      });
    } else if (options?.type === 'oneshot') {
      // Schedule one-time task
      await BackgroundFetch.scheduleTaskAsync(taskId, {
        minimumInterval: 0,
        stopOnTerminate: false,
        startOnBoot: false,
      });
    }

    // Also register with react-native-background-fetch for redundancy
    await BackgroundFetch.scheduleTask({
      taskId: taskId,
      delay: options?.delay || 0,
      periodic: options?.type === 'periodic',
      timeout: options?.timeout || 30,
      enableHeadless: true,
      forceAlarmManager: false,
      requiredNetworkType: options?.requiresNetwork 
        ? BackgroundFetch.NETWORK_TYPE_ANY 
        : BackgroundFetch.NETWORK_TYPE_NONE,
      requiresBatteryNotLow: options?.requiresBatteryNotLow || false,
      requiresCharging: options?.requiresCharging || false,
      requiresStorageNotLow: options?.requiresStorageNotLow || false,
      requiresDeviceIdle: options?.requiresDeviceIdle || false,
    });
  }

  async unregisterTask(taskId: string): Promise<void> {
    this.tasks.delete(taskId);
    
    try {
      await BackgroundFetch.unregisterTaskAsync(taskId);
    } catch (error) {
      console.warn('Failed to unregister task from expo:', error);
    }

    try {
      await BackgroundFetch.stop(taskId);
    } catch (error) {
      console.warn('Failed to stop task from background-fetch:', error);
    }
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
    const isRegisteredInExpo = await TaskManager.isTaskRegisteredAsync(taskId);
    const isRegisteredInMap = this.tasks.has(taskId);
    
    return isRegisteredInExpo || isRegisteredInMap;
  }

  async getRegisteredTasks(): Promise<string[]> {
    return Array.from(this.tasks.keys());
  }

  async stopAllTasks(): Promise<void> {
    const taskIds = Array.from(this.tasks.keys());
    
    for (const taskId of taskIds) {
      await this.unregisterTask(taskId);
    }
    
    // Stop background fetch completely
    await BackgroundFetch.stop();
  }

  async getTaskStatus(taskId: string): Promise<{
    isRegistered: boolean;
    lastExecution?: number;
    nextScheduledExecution?: number;
  }> {
    const isRegistered = await this.isTaskRegistered(taskId);
    
    // React Native doesn't provide detailed task status
    return {
      isRegistered,
      lastExecution: undefined,
      nextScheduledExecution: undefined,
    };
  }

  // Platform-specific methods
  async requestBackgroundPermissions(): Promise<boolean> {
    try {
      const status = await BackgroundFetch.status();
      
      switch (status) {
        case BackgroundFetch.STATUS_RESTRICTED:
          console.warn('Background fetch is restricted');
          return false;
        case BackgroundFetch.STATUS_DENIED:
          console.warn('Background fetch is denied');
          return false;
        case BackgroundFetch.STATUS_AVAILABLE:
          return true;
        default:
          return false;
      }
    } catch (error) {
      console.error('Failed to check background fetch status:', error);
      return false;
    }
  }

  async minimizeBatteryUsage(enabled: boolean): Promise<void> {
    // Update all registered tasks to require battery not low
    const taskIds = Array.from(this.tasks.keys());
    
    for (const taskId of taskIds) {
      const task = this.tasks.get(taskId);
      if (task) {
        await this.unregisterTask(taskId);
        await this.registerTask(taskId, task, {
          ...task.options,
          requiresBatteryNotLow: enabled,
          requiresDeviceIdle: enabled,
        });
      }
    }
  }
}