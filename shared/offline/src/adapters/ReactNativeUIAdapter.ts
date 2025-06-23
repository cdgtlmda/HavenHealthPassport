import { UIAdapter, UINotification, UIDialog, UIProgress } from '../types';

/**
 * React Native UI adapter
 * Uses react-native components and libraries
 */
export class ReactNativeUIAdapter implements UIAdapter {
  private Alert: any;
  private ToastAndroid?: any;
  private ProgressBar?: any;
  private notificationHandlers: Map<string, () => void> = new Map();

  constructor(Alert: any, ToastAndroid?: any, ProgressBar?: any) {
    this.Alert = Alert;
    this.ToastAndroid = ToastAndroid;
    this.ProgressBar = ProgressBar;
  }

  async showNotification(notification: UINotification): Promise<void> {
    const { title, message, type, duration, action } = notification;

    // On Android, use ToastAndroid for simple notifications
    if (this.ToastAndroid && duration && duration < 5000) {
      const toastDuration = duration < 3000 
        ? this.ToastAndroid.SHORT 
        : this.ToastAndroid.LONG;
      
      this.ToastAndroid.show(message, toastDuration);
      
      if (action) {
        this.notificationHandlers.set(notification.id || 'default', action.handler);
      }
    } else {
      // Use Alert for more complex notifications
      const buttons: any[] = [];
      
      if (action) {
        buttons.push({
          text: action.label,
          onPress: action.handler,
          style: action.style,
        });
      }
      
      buttons.push({
        text: 'OK',
        style: 'default',
      });
      
      this.Alert.alert(title, message, buttons);
    }
  }

  async showDialog(dialog: UIDialog): Promise<any> {
    return new Promise((resolve) => {
      const buttons = dialog.buttons.map(button => ({
        text: button.label,
        onPress: () => {
          if (button.handler) {
            button.handler();
          }
          resolve(button.value);
        },
        style: button.style === 'destructive' ? 'destructive' : 
               button.style === 'cancel' ? 'cancel' : 'default',
      }));

      this.Alert.alert(
        dialog.title,
        dialog.message,
        buttons,
        { cancelable: dialog.cancelable ?? true }
      );
    });
  }

  async showProgress(progress: UIProgress): void {
    // Progress display would typically be handled by a component
    // This is a simplified implementation
    console.log(`Progress: ${progress.title} - ${progress.value}/${progress.max}`);
  }

  async updateProgress(progressId: string, value: number, message?: string): void {
    // Update progress in the UI
    console.log(`Progress Update: ${progressId} - ${value}${message ? ` - ${message}` : ''}`);
  }

  async hideProgress(progressId: string): void {
    // Hide progress indicator
    console.log(`Progress Hidden: ${progressId}`);
  }

  async showLoading(message?: string): Promise<string> {
    const loadingId = `loading_${Date.now()}`;
    // In a real implementation, this would show a loading indicator
    console.log(`Loading: ${message || 'Please wait...'}`);
    return loadingId;
  }

  async hideLoading(loadingId: string): Promise<void> {
    // Hide loading indicator
    console.log(`Loading Hidden: ${loadingId}`);
  }

  // React Native specific methods
  async showActionSheet(options: {
    title?: string;
    message?: string;
    options: string[];
    destructiveButtonIndex?: number;
    cancelButtonIndex?: number;
  }): Promise<number> {
    return new Promise((resolve) => {
      // This would use react-native-action-sheet or similar
      // For now, use Alert as fallback
      const buttons = options.options.map((option, index) => ({
        text: option,
        onPress: () => resolve(index),
        style: index === options.destructiveButtonIndex ? 'destructive' :
               index === options.cancelButtonIndex ? 'cancel' : 'default',
      }));

      this.Alert.alert(
        options.title || '',
        options.message,
        buttons,
        { cancelable: true }
      );
    });
  }

  vibrate(pattern?: number | number[]): void {
    // This would use react-native Vibration API
    console.log('Vibrate:', pattern);
  }

  playSound(soundName: string): void {
    // This would use react-native-sound or similar
    console.log('Play sound:', soundName);
  }
}