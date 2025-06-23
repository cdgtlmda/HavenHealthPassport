import React from 'react';
import {
  View,
  Text,
  ActivityIndicator,
  Alert,
  ToastAndroid,
  Platform,
  Modal,
  StyleSheet,
  Animated,
  Vibration,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { UIAdapter, UINotification, UILoadingOptions, UIDialogOptions, UIToastOptions } from '../types';

export class ReactNativeUIAdapter implements UIAdapter {
  private loadingModal: React.RefObject<any> | null = null;
  private activeToasts: Set<string> = new Set();

  async showNotification(notification: UINotification): Promise<void> {
    const { type, title, message, duration = 3000, action } = notification;

    if (Platform.OS === 'android') {
      // Use Android Toast for simple notifications
      ToastAndroid.showWithGravity(
        message,
        duration === 'short' ? ToastAndroid.SHORT : ToastAndroid.LONG,
        ToastAndroid.BOTTOM
      );
    } else {
      // Use Alert for iOS
      Alert.alert(
        title || '',
        message,
        action ? [
          { text: 'Cancel', style: 'cancel' },
          { text: action.label, onPress: action.onPress },
        ] : [{ text: 'OK' }]
      );
    }

    // Haptic feedback based on notification type
    switch (type) {
      case 'success':
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        break;
      case 'error':
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
        break;
      case 'warning':
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
        break;
      default:
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    }
  }

  async showLoading(options?: UILoadingOptions): Promise<() => void> {
    const { message = 'Loading...', overlay = true, cancellable = false } = options || {};

    // Create a unique ID for this loading instance
    const loadingId = Date.now().toString();

    // Return a component that can be rendered
    const LoadingComponent = () => (
      <Modal
        visible={true}
        transparent={true}
        animationType="fade"
        onRequestClose={() => {
          if (cancellable && options?.onCancel) {
            options.onCancel();
          }
        }}
      >
        <View style={styles.loadingOverlay}>
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color="#007AFF" />
            <Text style={styles.loadingText}>{message}</Text>
          </View>
        </View>
      </Modal>
    );

    // Store reference to allow hiding
    this.loadingModal = React.createRef();

    // Return hide function
    return () => {
      this.loadingModal = null;
    };
  }
  async showDialog(options: UIDialogOptions): Promise<boolean> {
    return new Promise((resolve) => {
      const buttons = [];

      if (options.cancelable !== false) {
        buttons.push({
          text: options.cancelText || 'Cancel',
          style: 'cancel' as const,
          onPress: () => resolve(false),
        });
      }

      buttons.push({
        text: options.confirmText || 'OK',
        style: options.destructive ? 'destructive' as const : 'default' as const,
        onPress: () => resolve(true),
      });

      Alert.alert(
        options.title,
        options.message,
        buttons,
        { cancelable: options.cancelable !== false }
      );
    });
  }

  async showToast(options: UIToastOptions): Promise<void> {
    const { message, duration = 'short', position = 'bottom' } = options;

    if (Platform.OS === 'android') {
      const gravityMap = {
        top: ToastAndroid.TOP,
        center: ToastAndroid.CENTER,
        bottom: ToastAndroid.BOTTOM,
      };

      ToastAndroid.showWithGravity(
        message,
        duration === 'short' ? ToastAndroid.SHORT : ToastAndroid.LONG,
        gravityMap[position]
      );
    } else {
      // For iOS, we need to implement a custom toast
      // This would typically be done with a custom component
      // For now, we'll use a simple alert
      Alert.alert('', message, [{ text: 'OK' }]);
    }
  }

  async vibrate(pattern?: number | number[]): Promise<void> {
    if (typeof pattern === 'number') {
      Vibration.vibrate(pattern);
    } else if (Array.isArray(pattern)) {
      Vibration.vibrate(pattern);
    } else {
      // Default vibration
      await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    }
  }

  getOfflineIndicator(): React.ComponentType<any> {
    return ({ isOnline }: { isOnline: boolean }) => (
      <View style={[styles.offlineIndicator, isOnline && styles.onlineIndicator]}>
        <Ionicons 
          name={isOnline ? 'cloud-done' : 'cloud-offline'} 
          size={16} 
          color="white" 
        />
        <Text style={styles.offlineText}>
          {isOnline ? 'Online' : 'Offline'}
        </Text>
      </View>
    );
  }

  getSyncStatusIndicator(): React.ComponentType<any> {
    return ({ status, progress }: { status: string; progress?: number }) => {
      const iconMap: Record<string, string> = {
        idle: 'sync',
        syncing: 'sync',
        success: 'checkmark-circle',
        error: 'alert-circle',
      };

      return (
        <View style={styles.syncIndicator}>
          <Animated.View style={status === 'syncing' ? styles.rotating : {}}>
            <Ionicons 
              name={iconMap[status] || 'sync'} 
              size={20} 
              color={status === 'error' ? '#FF3B30' : '#007AFF'} 
            />
          </Animated.View>
          {progress !== undefined && (
            <Text style={styles.syncProgress}>{Math.round(progress * 100)}%</Text>
          )}
        </View>
      );
    };
  }
  getConflictResolutionUI(): React.ComponentType<any> {
    // Return a reference to the platform-specific conflict resolution UI
    // This would typically import from the mobile app's components
    return ({ conflicts, onResolve, onCancel }: any) => (
      <View style={styles.conflictContainer}>
        <Text style={styles.conflictTitle}>Resolve Conflicts</Text>
        <Text style={styles.conflictSubtitle}>
          {conflicts.length} conflicts need your attention
        </Text>
        {/* Actual implementation would render the full conflict resolution UI */}
      </View>
    );
  }

  // Platform-specific features
  async requestOfflinePermissions(): Promise<boolean> {
    // React Native doesn't require specific offline permissions
    // But we might need to request storage permissions
    try {
      // Check if we need any permissions
      return true;
    } catch (error) {
      console.error('Failed to request offline permissions:', error);
      return false;
    }
  }

  supportsBackgroundSync(): boolean {
    // React Native supports background sync through native modules
    return true;
  }

  supportsPersistentStorage(): boolean {
    // React Native AsyncStorage is persistent by default
    return true;
  }

  supportsIndexedDB(): boolean {
    // React Native doesn't support IndexedDB, uses AsyncStorage instead
    return false;
  }
}

const styles = StyleSheet.create({
  loadingOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingContainer: {
    backgroundColor: 'white',
    padding: 20,
    borderRadius: 10,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
    elevation: 5,
  },
  loadingText: {
    marginTop: 10,
    fontSize: 16,
    color: '#333',
  },
  offlineIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FF3B30',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  onlineIndicator: {
    backgroundColor: '#34C759',
  },
  offlineText: {
    color: 'white',
    marginLeft: 6,
    fontSize: 12,
    fontWeight: '600',
  },
  syncIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  rotating: {
    // Animation would be applied here
  },
  syncProgress: {
    marginLeft: 8,
    fontSize: 12,
    color: '#007AFF',
  },
  conflictContainer: {
    padding: 20,
    backgroundColor: 'white',
  },
  conflictTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  conflictSubtitle: {
    fontSize: 14,
    color: '#666',
  },
});