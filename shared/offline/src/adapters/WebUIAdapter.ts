import { UIAdapter, UINotification, UIDialog, UIProgress } from '../types';

/**
 * Web UI adapter
 * Uses browser APIs and web-specific notification systems
 */
export class WebUIAdapter implements UIAdapter {
  private activeNotifications: Map<string, Notification> = new Map();
  private activeProgress: Map<string, { element: HTMLElement; progressBar: HTMLElement }> = new Map();
  private loadingIndicators: Map<string, HTMLElement> = new Map();

  constructor() {
    // Request notification permission on initialization
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }

  async showNotification(notification: UINotification): Promise<void> {
    const { id, title, message, type, duration, action } = notification;

    // Try to use native notifications first
    if ('Notification' in window && Notification.permission === 'granted') {
      const notif = new Notification(title, {
        body: message,
        icon: this.getIconForType(type),
        badge: '/icons/badge.png',
        tag: id,
        requireInteraction: !duration || duration > 5000,
      });

      if (id) {
        this.activeNotifications.set(id, notif);
      }

      if (action) {
        notif.onclick = () => {
          action.handler();
          notif.close();
        };
      }

      if (duration) {
        setTimeout(() => notif.close(), duration);
      }
    } else {
      // Fallback to in-app notification
      this.showInAppNotification(notification);
    }
  }

  async showDialog(dialog: UIDialog): Promise<any> {
    return new Promise((resolve) => {
      // Create dialog overlay
      const overlay = document.createElement('div');
      overlay.className = 'hhp-dialog-overlay';
      overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
      `;

      // Create dialog container
      const dialogEl = document.createElement('div');
      dialogEl.className = 'hhp-dialog';
      dialogEl.style.cssText = `
        background: white;
        border-radius: 8px;
        padding: 24px;
        max-width: 500px;
        width: 90%;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
      `;

      // Add title
      const titleEl = document.createElement('h2');
      titleEl.textContent = dialog.title;
      titleEl.style.cssText = 'margin: 0 0 16px 0; font-size: 20px;';
      dialogEl.appendChild(titleEl);

      // Add message
      const messageEl = document.createElement('p');
      messageEl.textContent = dialog.message;
      messageEl.style.cssText = 'margin: 0 0 24px 0; color: #666;';
      dialogEl.appendChild(messageEl);

      // Add buttons
      const buttonsContainer = document.createElement('div');
      buttonsContainer.style.cssText = 'display: flex; gap: 8px; justify-content: flex-end;';

      dialog.buttons.forEach(button => {
        const buttonEl = document.createElement('button');
        buttonEl.textContent = button.label;
        buttonEl.style.cssText = `
          padding: 8px 16px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
          ${button.style === 'primary' ? 'background: #1976d2; color: white;' :
            button.style === 'destructive' ? 'background: #d32f2f; color: white;' :
            'background: #e0e0e0; color: #333;'}
        `;

        buttonEl.onclick = () => {
          if (button.handler) {
            button.handler();
          }
          document.body.removeChild(overlay);
          resolve(button.value);
        };

        buttonsContainer.appendChild(buttonEl);
      });

      dialogEl.appendChild(buttonsContainer);
      overlay.appendChild(dialogEl);

      // Handle cancelable
      if (dialog.cancelable) {
        overlay.onclick = (e) => {
          if (e.target === overlay) {
            document.body.removeChild(overlay);
            resolve(undefined);
          }
        };
      }

      document.body.appendChild(overlay);
    });
  }

  async showProgress(progress: UIProgress): Promise<void> {
    const { id, title, value, max, message } = progress;

    // Create progress container
    const container = document.createElement('div');
    container.className = 'hhp-progress-container';
    container.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: white;
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
      min-width: 300px;
      z-index: 9999;
    `;

    // Add title
    const titleEl = document.createElement('div');
    titleEl.textContent = title;
    titleEl.style.cssText = 'font-weight: 500; margin-bottom: 8px;';
    container.appendChild(titleEl);

    // Add message if provided
    if (message) {
      const messageEl = document.createElement('div');
      messageEl.className = 'hhp-progress-message';
      messageEl.textContent = message;
      messageEl.style.cssText = 'font-size: 14px; color: #666; margin-bottom: 8px;';
      container.appendChild(messageEl);
    }

    // Add progress bar
    const progressWrapper = document.createElement('div');
    progressWrapper.style.cssText = `
      width: 100%;
      height: 8px;
      background: #e0e0e0;
      border-radius: 4px;
      overflow: hidden;
    `;

    const progressBar = document.createElement('div');
    progressBar.className = 'hhp-progress-bar';
    progressBar.style.cssText = `
      height: 100%;
      background: #1976d2;
      transition: width 0.3s ease;
      width: ${max ? (value / max * 100) : 0}%;
    `;

    progressWrapper.appendChild(progressBar);
    container.appendChild(progressWrapper);

    // Add percentage
    const percentageEl = document.createElement('div');
    percentageEl.className = 'hhp-progress-percentage';
    percentageEl.textContent = max ? `${Math.round(value / max * 100)}%` : '0%';
    percentageEl.style.cssText = 'font-size: 12px; color: #666; margin-top: 4px; text-align: right;';
    container.appendChild(percentageEl);

    document.body.appendChild(container);

    if (id) {
      this.activeProgress.set(id, { element: container, progressBar });
    }
  }

  async updateProgress(progressId: string, value: number, message?: string): Promise<void> {
    const progress = this.activeProgress.get(progressId);
    if (!progress) return;

    const { element, progressBar } = progress;
    
    // Update progress bar
    const max = parseFloat(progressBar.parentElement?.getAttribute('data-max') || '100');
    progressBar.style.width = `${(value / max) * 100}%`;

    // Update percentage
    const percentageEl = element.querySelector('.hhp-progress-percentage');
    if (percentageEl) {
      percentageEl.textContent = `${Math.round((value / max) * 100)}%`;
    }

    // Update message if provided
    if (message) {
      const messageEl = element.querySelector('.hhp-progress-message');
      if (messageEl) {
        messageEl.textContent = message;
      }
    }
  }

  async hideProgress(progressId: string): Promise<void> {
    const progress = this.activeProgress.get(progressId);
    if (progress) {
      progress.element.remove();
      this.activeProgress.delete(progressId);
    }
  }

  async showLoading(message?: string): Promise<string> {
    const loadingId = `loading_${Date.now()}`;
    
    const loader = document.createElement('div');
    loader.className = 'hhp-loading';
    loader.style.cssText = `
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: white;
      border-radius: 8px;
      padding: 24px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      display: flex;
      flex-direction: column;
      align-items: center;
      z-index: 10001;
    `;

    // Add spinner
    const spinner = document.createElement('div');
    spinner.className = 'hhp-spinner';
    spinner.style.cssText = `
      width: 40px;
      height: 40px;
      border: 3px solid #f3f3f3;
      border-top: 3px solid #1976d2;
      border-radius: 50%;
      animation: hhp-spin 1s linear infinite;
    `;

    // Add message
    if (message) {
      const messageEl = document.createElement('div');
      messageEl.textContent = message;
      messageEl.style.cssText = 'margin-top: 16px; color: #666;';
      loader.appendChild(messageEl);
    }

    loader.appendChild(spinner);
    document.body.appendChild(loader);

    // Add spinner animation
    if (!document.querySelector('#hhp-spinner-style')) {
      const style = document.createElement('style');
      style.id = 'hhp-spinner-style';
      style.textContent = `
        @keyframes hhp-spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `;
      document.head.appendChild(style);
    }

    this.loadingIndicators.set(loadingId, loader);
    return loadingId;
  }

  async hideLoading(loadingId: string): Promise<void> {
    const loader = this.loadingIndicators.get(loadingId);
    if (loader) {
      loader.remove();
      this.loadingIndicators.delete(loadingId);
    }
  }

  // Web-specific methods
  private showInAppNotification(notification: UINotification): void {
    const { id, title, message, type, duration = 5000, action } = notification;

    const notif = document.createElement('div');
    notif.className = `hhp-notification hhp-notification-${type}`;
    notif.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: ${this.getBackgroundForType(type)};
      color: white;
      padding: 16px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      max-width: 400px;
      z-index: 9999;
      animation: hhp-slide-in 0.3s ease;
    `;

    const titleEl = document.createElement('div');
    titleEl.textContent = title;
    titleEl.style.cssText = 'font-weight: 500; margin-bottom: 4px;';
    notif.appendChild(titleEl);

    const messageEl = document.createElement('div');
    messageEl.textContent = message;
    messageEl.style.cssText = 'font-size: 14px; opacity: 0.9;';
    notif.appendChild(messageEl);

    if (action) {
      const actionButton = document.createElement('button');
      actionButton.textContent = action.label;
      actionButton.style.cssText = `
        margin-top: 8px;
        padding: 4px 12px;
        background: rgba(255, 255, 255, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.3);
        color: white;
        border-radius: 4px;
        cursor: pointer;
      `;
      actionButton.onclick = () => {
        action.handler();
        notif.remove();
      };
      notif.appendChild(actionButton);
    }

    // Add close button
    const closeButton = document.createElement('button');
    closeButton.textContent = '×';
    closeButton.style.cssText = `
      position: absolute;
      top: 8px;
      right: 8px;
      background: none;
      border: none;
      color: white;
      font-size: 24px;
      cursor: pointer;
      opacity: 0.8;
    `;
    closeButton.onclick = () => notif.remove();
    notif.appendChild(closeButton);

    document.body.appendChild(notif);

    // Add slide-in animation
    if (!document.querySelector('#hhp-notification-style')) {
      const style = document.createElement('style');
      style.id = 'hhp-notification-style';
      style.textContent = `
        @keyframes hhp-slide-in {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
      `;
      document.head.appendChild(style);
    }

    // Auto-remove after duration
    if (duration) {
      setTimeout(() => notif.remove(), duration);
    }
  }

  private getIconForType(type?: string): string {
    switch (type) {
      case 'success': return '/icons/success.png';
      case 'error': return '/icons/error.png';
      case 'warning': return '/icons/warning.png';
      default: return '/icons/info.png';
    }
  }

  private getBackgroundForType(type?: string): string {
    switch (type) {
      case 'success': return '#4caf50';
      case 'error': return '#f44336';
      case 'warning': return '#ff9800';
      default: return '#2196f3';
    }
  }

  // Additional web-specific methods
  async requestPermission(type: 'notification' | 'storage' | 'camera'): Promise<boolean> {
    switch (type) {
      case 'notification':
        if ('Notification' in window) {
          const permission = await Notification.requestPermission();
          return permission === 'granted';
        }
        return false;

      case 'storage':
        if ('storage' in navigator && 'persist' in navigator.storage) {
          return await navigator.storage.persist();
        }
        return false;

      case 'camera':
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ video: true });
          stream.getTracks().forEach(track => track.stop());
          return true;
        } catch {
          return false;
        }

      default:
        return false;
    }
  }

  vibrate(pattern?: number | number[]): void {
    if ('vibrate' in navigator) {
      navigator.vibrate(pattern || 200);
    }
  }

  playSound(soundUrl: string): void {
    const audio = new Audio(soundUrl);
    audio.play().catch(err => console.error('Failed to play sound:', err));
  }
}