import { EventEmitter } from 'events';
import { AppState, AppStateStatus, Platform } from 'react-native';
import DeviceInfo from 'react-native-device-info';

interface BatteryState {
  level: number; // 0-100
  isCharging: boolean;
  temperature?: number;
  voltage?: number;
  technology?: string;
}

interface PowerProfile {
  name: 'high_performance' | 'balanced' | 'power_saver' | 'ultra_power_saver';
  syncInterval: number;
  backgroundTasksEnabled: boolean;
  animationsEnabled: boolean;
  prefetchEnabled: boolean;
  autoUploadEnabled: boolean;
  locationAccuracy: 'high' | 'balanced' | 'low';
  networkUsage: 'unrestricted' | 'optimized' | 'restricted';
}

interface BatteryOptimizationConfig {
  enableAdaptivePower: boolean;
  lowBatteryThreshold: number;
  criticalBatteryThreshold: number;
  checkInterval: number;
  profiles: Record<string, PowerProfile>;
}

export class BatteryOptimizer extends EventEmitter {
  private config: BatteryOptimizationConfig;
  private currentProfile: PowerProfile;
  private batteryState: BatteryState | null = null;
  private checkInterval?: NodeJS.Timeout;
  private appState: AppStateStatus = 'active';
  private taskQueue: Map<string, () => Promise<void>> = new Map();
  private deferredTasks: Set<string> = new Set();
  
  constructor(config: Partial<BatteryOptimizationConfig> = {}) {
    super();
    this.config = {
      enableAdaptivePower: true,
      lowBatteryThreshold: 20,
      criticalBatteryThreshold: 10,
      checkInterval: 60000, // 1 minute
      profiles: this.getDefaultProfiles(),
      ...config,
    };
    
    this.currentProfile = this.config.profiles.balanced;
    this.initialize();
  }

  /**
   * Initialize battery monitoring
   */
  private async initialize(): Promise<void> {
    // Setup app state listener
    AppState.addEventListener('change', this.handleAppStateChange);
    
    // Start battery monitoring
    await this.checkBatteryState();
    this.startMonitoring();
    
    // Initial profile selection
    this.selectOptimalProfile();
  }

  /**
   * Start battery monitoring
   */
  startMonitoring(): void {
    if (this.checkInterval) return;
    
    this.checkInterval = setInterval(() => {
      this.checkBatteryState();
    }, this.config.checkInterval);
    
    this.emit('monitoring-started');
  }

  /**
   * Stop battery monitoring
   */
  stopMonitoring(): void {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = undefined;
    }
    
    this.emit('monitoring-stopped');
  }

  /**
   * Get current power profile
   */
  getCurrentProfile(): PowerProfile {
    return this.currentProfile;
  }

  /**
   * Set power profile manually
   */
  setProfile(profileName: string): void {
    const profile = this.config.profiles[profileName];
    if (!profile) {
      throw new Error(`Profile ${profileName} not found`);
    }
    
    this.currentProfile = profile;
    this.applyProfile(profile);
    this.emit('profile-changed', profile);
  }

  /**
   * Register a task for battery-aware execution
   */
  registerTask(
    taskId: string,
    task: () => Promise<void>,
    options: {
      priority?: 'high' | 'medium' | 'low';
      requiresCharging?: boolean;
      minBatteryLevel?: number;
    } = {}
  ): void {
    this.taskQueue.set(taskId, task);
    
    // Check if task can run now
    if (this.canRunTask(options)) {
      this.executeTask(taskId);
    } else {
      this.deferredTasks.add(taskId);
    }
  }

  /**
   * Execute deferred tasks when conditions improve
   */
  async executeDeferredTasks(): Promise<void> {
    const tasksToRun = Array.from(this.deferredTasks);
    
    for (const taskId of tasksToRun) {
      if (this.canRunTask({})) {
        await this.executeTask(taskId);
        this.deferredTasks.delete(taskId);
      }
    }
  }

  /**
   * Get battery statistics
   */
  getBatteryStats(): {
    currentLevel: number;
    isCharging: boolean;
    profileName: string;
    deferredTaskCount: number;
    estimatedTimeRemaining?: number;
  } {
    return {
      currentLevel: this.batteryState?.level || 0,
      isCharging: this.batteryState?.isCharging || false,
      profileName: this.currentProfile.name,
      deferredTaskCount: this.deferredTasks.size,
      estimatedTimeRemaining: this.estimateTimeRemaining(),
    };
  }

  /**
   * Private methods
   */
  
  private getDefaultProfiles(): Record<string, PowerProfile> {
    return {
      high_performance: {
        name: 'high_performance',
        syncInterval: 5 * 60 * 1000, // 5 minutes
        backgroundTasksEnabled: true,
        animationsEnabled: true,
        prefetchEnabled: true,
        autoUploadEnabled: true,
        locationAccuracy: 'high',
        networkUsage: 'unrestricted',
      },
      balanced: {
        name: 'balanced',
        syncInterval: 15 * 60 * 1000, // 15 minutes
        backgroundTasksEnabled: true,
        animationsEnabled: true,
        prefetchEnabled: true,
        autoUploadEnabled: true,
        locationAccuracy: 'balanced',
        networkUsage: 'optimized',
      },
      power_saver: {
        name: 'power_saver',
        syncInterval: 30 * 60 * 1000, // 30 minutes
        backgroundTasksEnabled: false,
        animationsEnabled: false,
        prefetchEnabled: false,
        autoUploadEnabled: false,
        locationAccuracy: 'low',
        networkUsage: 'restricted',
      },
      ultra_power_saver: {
        name: 'ultra_power_saver',
        syncInterval: 60 * 60 * 1000, // 1 hour
        backgroundTasksEnabled: false,
        animationsEnabled: false,
        prefetchEnabled: false,
        autoUploadEnabled: false,
        locationAccuracy: 'low',
        networkUsage: 'restricted',
      },
    };
  }

  private async checkBatteryState(): Promise<void> {
    try {
      const level = await DeviceInfo.getBatteryLevel();
      const isCharging = await DeviceInfo.getPowerState().then(state => 
        state.batteryState === 'charging' || state.batteryState === 'full'
      );
      
      this.batteryState = {
        level: Math.round(level * 100),
        isCharging,
      };
      
      // Select optimal profile if adaptive power is enabled
      if (this.config.enableAdaptivePower) {
        this.selectOptimalProfile();
      }
      
      // Execute deferred tasks if conditions improved
      if (isCharging || level > 0.5) {
        this.executeDeferredTasks();
      }
      
      this.emit('battery-update', this.batteryState);
    } catch (error) {
      console.error('Failed to check battery state:', error);
    }
  }

  private selectOptimalProfile(): void {
    if (!this.batteryState) return;
    
    const { level, isCharging } = this.batteryState;
    let selectedProfile: PowerProfile;
    
    if (isCharging) {
      selectedProfile = this.config.profiles.high_performance;
    } else if (level <= this.config.criticalBatteryThreshold) {
      selectedProfile = this.config.profiles.ultra_power_saver;
    } else if (level <= this.config.lowBatteryThreshold) {
      selectedProfile = this.config.profiles.power_saver;
    } else if (level > 50) {
      selectedProfile = this.config.profiles.balanced;
    } else {
      selectedProfile = this.config.profiles.power_saver;
    }
    
    if (selectedProfile.name !== this.currentProfile.name) {
      this.currentProfile = selectedProfile;
      this.applyProfile(selectedProfile);
      this.emit('profile-changed', selectedProfile);
    }
  }

  private applyProfile(profile: PowerProfile): void {
    // Apply profile settings
    this.emit('apply-profile', profile);
    
    // Specific optimizations based on profile
    if (profile.name === 'power_saver' || profile.name === 'ultra_power_saver') {
      // Disable non-essential features
      this.emit('disable-features', {
        animations: !profile.animationsEnabled,
        backgroundTasks: !profile.backgroundTasksEnabled,
        prefetch: !profile.prefetchEnabled,
        autoUpload: !profile.autoUploadEnabled,
      });
    }
  }

  private canRunTask(options: {
    requiresCharging?: boolean;
    minBatteryLevel?: number;
  }): boolean {
    if (!this.batteryState) return false;
    
    if (options.requiresCharging && !this.batteryState.isCharging) {
      return false;
    }
    
    if (options.minBatteryLevel && 
        this.batteryState.level < options.minBatteryLevel) {
      return false;
    }
    
    // Check current profile restrictions
    if (!this.currentProfile.backgroundTasksEnabled && 
        this.appState !== 'active') {
      return false;
    }
    
    return true;
  }

  private async executeTask(taskId: string): Promise<void> {
    const task = this.taskQueue.get(taskId);
    if (!task) return;
    
    try {
      await task();
      this.taskQueue.delete(taskId);
      this.emit('task-executed', taskId);
    } catch (error) {
      this.emit('task-error', { taskId, error });
    }
  }

  private handleAppStateChange = (nextAppState: AppStateStatus): void => {
    this.appState = nextAppState;
    
    if (nextAppState === 'background') {
      // Switch to more conservative profile in background
      if (this.currentProfile.name === 'high_performance') {
        this.setProfile('balanced');
      }
    }
  };

  private estimateTimeRemaining(): number | undefined {
    if (!this.batteryState || this.batteryState.isCharging) {
      return undefined;
    }
    
    // Simple estimation based on current battery level and usage profile
    const baseHours = 10; // Base battery life in hours
    const profileMultiplier = {
      high_performance: 0.5,
      balanced: 1.0,
      power_saver: 1.5,
      ultra_power_saver: 2.0,
    };
    
    const multiplier = profileMultiplier[this.currentProfile.name];
    const hoursRemaining = (this.batteryState.level / 100) * baseHours * multiplier;
    
    return Math.round(hoursRemaining * 60); // Return in minutes
  }

  /**
   * Cleanup
   */
  destroy(): void {
    this.stopMonitoring();
    AppState.removeEventListener('change', this.handleAppStateChange);
  }
}

export default BatteryOptimizer;