import React from 'react';
import { UIAdapter, UINotification, UILoadingOptions, UIDialogOptions, UIToastOptions } from '../types';

export class WebUIAdapter implements UIAdapter {
  private activeNotifications: Set<string> = new Set();
  private loadingElements: Map<string, HTMLElement> = new Map();
  private toastContainer: HTMLElement | null = null;

  constructor() {
    this.ensureToastContainer();
  }

  async showNotification(notification: UINotification): Promise<void> {
    const { type, title, message, duration = 3000, action } = notification;
    
    // Check if Notification API is available and permitted
    if ('Notification' in window && Notification.permission === 'granted') {
      const notif = new Notification(title || 'Haven Health Passport', {
        body: message,
        icon: '/favicon.ico',
        tag: `haven-${Date.now()}`,
        requireInteraction: action !== undefined,
      });

      if (action) {
        notif.onclick = () => {
          action.onPress();
          notif.close();
        };
      }

      if (duration !== 'persistent') {
        setTimeout(() => notif.close(), duration);
      }
    } else {
      // Fallback to toast notification
      await this.showToast({
        message: `${title ? title + ': ' : ''}${message}`,
        duration: duration === 'persistent' ? 'long' : 'short',
        position: 'top',
      });
    }

    // Vibration API for feedback
    if ('vibrate' in navigator) {
      switch (type) {
        case 'success':
          navigator.vibrate(200);
          break;
        case 'error':
          navigator.vibrate([100, 50, 100]);
          break;
        case 'warning':
          navigator.vibrate([50, 50, 50]);
          break;
      }
    }
  }

  async showLoading(options?: UILoadingOptions): Promise<() => void> {
    const { message = 'Loading...', overlay = true, cancellable = false } = options || {};
    const loadingId = `loading-${Date.now()}`;

    // Create loading element
    const loadingEl = document.createElement('div');
    loadingEl.id = loadingId;
    loadingEl.className = 'haven-loading';
    loadingEl.innerHTML = `
      <div class="haven-loading-overlay${overlay ? ' haven-loading-overlay-visible' : ''}">
        <div class="haven-loading-container">
          <div class="haven-loading-spinner"></div>
          <div class="haven-loading-text">${message}</div>
          ${cancellable ? '<button class="haven-loading-cancel">Cancel</button>' : ''}
        </div>
      </div>
    `;

    if (cancellable && options?.onCancel) {
      const cancelBtn = loadingEl.querySelector('.haven-loading-cancel');
      cancelBtn?.addEventListener('click', options.onCancel);
    }

    document.body.appendChild(loadingEl);
    this.loadingElements.set(loadingId, loadingEl);

    // Return hide function
    return () => {
      const el = this.loadingElements.get(loadingId);
      if (el) {
        el.remove();
        this.loadingElements.delete(loadingId);
      }
    };
  }
  async showDialog(options: UIDialogOptions): Promise<boolean> {
    return new Promise((resolve) => {
      // Create custom dialog element
      const dialogEl = document.createElement('div');
      dialogEl.className = 'haven-dialog-overlay';
      dialogEl.innerHTML = `
        <div class="haven-dialog">
          <h3 class="haven-dialog-title">${options.title}</h3>
          <p class="haven-dialog-message">${options.message}</p>
          <div class="haven-dialog-actions">
            ${options.cancelable !== false ? `<button class="haven-dialog-cancel">${options.cancelText || 'Cancel'}</button>` : ''}
            <button class="haven-dialog-confirm${options.destructive ? ' haven-dialog-destructive' : ''}">
              ${options.confirmText || 'OK'}
            </button>
          </div>
        </div>
      `;

      // Add event listeners
      const confirmBtn = dialogEl.querySelector('.haven-dialog-confirm');
      const cancelBtn = dialogEl.querySelector('.haven-dialog-cancel');

      confirmBtn?.addEventListener('click', () => {
        dialogEl.remove();
        resolve(true);
      });

      cancelBtn?.addEventListener('click', () => {
        dialogEl.remove();
        resolve(false);
      });

      if (options.cancelable !== false) {
        dialogEl.addEventListener('click', (e) => {
          if (e.target === dialogEl) {
            dialogEl.remove();
            resolve(false);
          }
        });
      }

      document.body.appendChild(dialogEl);
    });
  }

  async showToast(options: UIToastOptions): Promise<void> {
    const { message, duration = 'short', position = 'bottom' } = options;
    
    const toastEl = document.createElement('div');
    toastEl.className = `haven-toast haven-toast-${position}`;
    toastEl.textContent = message;

    this.toastContainer?.appendChild(toastEl);

    // Trigger animation
    requestAnimationFrame(() => {
      toastEl.classList.add('haven-toast-visible');
    });

    // Auto hide
    const timeout = duration === 'short' ? 2000 : 4000;
    setTimeout(() => {
      toastEl.classList.remove('haven-toast-visible');
      setTimeout(() => toastEl.remove(), 300);
    }, timeout);
  }

  async vibrate(pattern?: number | number[]): Promise<void> {
    if ('vibrate' in navigator) {
      if (pattern === undefined) {
        navigator.vibrate(200);
      } else {
        navigator.vibrate(pattern);
      }
    }
  }

  getOfflineIndicator(): React.ComponentType<any> {
    return ({ isOnline }: { isOnline: boolean }) => (
      <div className={`haven-offline-indicator ${isOnline ? 'haven-online' : 'haven-offline'}`}>
        <span className="haven-offline-icon">
          {isOnline ? '☁️' : '🚫'}
        </span>
        <span className="haven-offline-text">
          {isOnline ? 'Online' : 'Offline'}
        </span>
      </div>
    );
  }
  getSyncStatusIndicator(): React.ComponentType<any> {
    return ({ status, progress }: { status: string; progress?: number }) => {
      const iconMap: Record<string, string> = {
        idle: '🔄',
        syncing: '🔄',
        success: '✅',
        error: '❌',
      };

      return (
        <div className={`haven-sync-indicator haven-sync-${status}`}>
          <span className={`haven-sync-icon ${status === 'syncing' ? 'haven-sync-rotating' : ''}`}>
            {iconMap[status] || '🔄'}
          </span>
          {progress !== undefined && (
            <span className="haven-sync-progress">{Math.round(progress * 100)}%</span>
          )}
        </div>
      );
    };
  }

  getConflictResolutionUI(): React.ComponentType<any> {
    // Return a reference to the platform-specific conflict resolution UI
    // This would typically import from the web app's components
    return ({ conflicts, onResolve, onCancel }: any) => (
      <div className="haven-conflict-container">
        <h2 className="haven-conflict-title">Resolve Conflicts</h2>
        <p className="haven-conflict-subtitle">
          {conflicts.length} conflicts need your attention
        </p>
        {/* Actual implementation would render the full conflict resolution UI */}
      </div>
    );
  }

  // Platform-specific features
  async requestOfflinePermissions(): Promise<boolean> {
    try {
      // Request persistent storage
      if ('storage' in navigator && 'persist' in navigator.storage) {
        const isPersisted = await navigator.storage.persisted();
        if (!isPersisted) {
          const result = await navigator.storage.persist();
          return result;
        }
        return true;
      }
      return false;
    } catch (error) {
      console.error('Failed to request offline permissions:', error);
      return false;
    }
  }

  supportsBackgroundSync(): boolean {
    return 'serviceWorker' in navigator && 'sync' in ServiceWorkerRegistration.prototype;
  }

  supportsPersistentStorage(): boolean {
    return 'storage' in navigator && 'persist' in navigator.storage;
  }

  supportsIndexedDB(): boolean {
    return 'indexedDB' in window;
  }

  // Private methods
  private ensureToastContainer(): void {
    if (!this.toastContainer) {
      this.toastContainer = document.getElementById('haven-toast-container');
      if (!this.toastContainer) {
        this.toastContainer = document.createElement('div');
        this.toastContainer.id = 'haven-toast-container';
        this.toastContainer.className = 'haven-toast-container';
        document.body.appendChild(this.toastContainer);
      }
    }
  }
}

// Add default styles
const styles = `
  .haven-loading-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
  }
  
  .haven-loading-overlay-visible {
    background: rgba(0, 0, 0, 0.5);
  }
  
  .haven-loading-container {
    background: white;
    padding: 24px;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    text-align: center;
  }  
  .haven-loading-spinner {
    width: 40px;
    height: 40px;
    border: 3px solid #f3f3f3;
    border-top: 3px solid #007AFF;
    border-radius: 50%;
    animation: haven-spin 1s linear infinite;
    margin: 0 auto 16px;
  }
  
  @keyframes haven-spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  .haven-loading-text {
    color: #333;
    font-size: 16px;
    margin-bottom: 16px;
  }
  
  .haven-loading-cancel {
    padding: 8px 16px;
    background: #f44336;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  
  .haven-dialog-overlay {
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
  }
  
  .haven-dialog {
    background: white;
    padding: 24px;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    max-width: 400px;
    width: 90%;
  }
  
  .haven-dialog-title {
    margin: 0 0 16px;
    font-size: 20px;
    font-weight: bold;
  }
  
  .haven-dialog-message {
    margin: 0 0 24px;
    color: #666;
  }
  
  .haven-dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }
  
  .haven-dialog-cancel,
  .haven-dialog-confirm {
    padding: 8px 16px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
  }
  
  .haven-dialog-cancel {
    background: #e0e0e0;
    color: #333;
  }
  
  .haven-dialog-confirm {
    background: #007AFF;
    color: white;
  }
  
  .haven-dialog-destructive {
    background: #f44336;
  }
  
  .haven-toast-container {
    position: fixed;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10001;
  }
  
  .haven-toast {
    background: #333;
    color: white;
    padding: 12px 24px;
    border-radius: 4px;
    margin-bottom: 8px;
    opacity: 0;
    transform: translateY(20px);
    transition: all 0.3s ease;
  }
  
  .haven-toast-visible {
    opacity: 1;
    transform: translateY(0);
  }
  
  .haven-toast-top {
    top: 20px;
  }
  
  .haven-toast-center {
    top: 50%;
    transform: translateX(-50%) translateY(-50%);
  }
  
  .haven-toast-bottom {
    bottom: 20px;
  }
  
  .haven-offline-indicator {
    display: inline-flex;
    align-items: center;
    padding: 6px 12px;
    border-radius: 16px;
    font-size: 12px;
    font-weight: 600;
  }
  
  .haven-online {
    background: #34C759;
    color: white;
  }
  
  .haven-offline {
    background: #FF3B30;
    color: white;
  }
  
  .haven-offline-icon {
    margin-right: 6px;
  }
  
  .haven-sync-indicator {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  
  .haven-sync-rotating {
    animation: haven-spin 1s linear infinite;
  }
  
  .haven-sync-progress {
    font-size: 12px;
    color: #007AFF;
  }
  
  .haven-conflict-container {
    padding: 20px;
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }
  
  .haven-conflict-title {
    margin: 0 0 8px;
    font-size: 18px;
    font-weight: bold;
  }
  
  .haven-conflict-subtitle {
    margin: 0;
    color: #666;
    font-size: 14px;
  }
`;

// Inject styles
if (typeof document !== 'undefined') {
  const styleEl = document.createElement('style');
  styleEl.textContent = styles;
  document.head.appendChild(styleEl);
}