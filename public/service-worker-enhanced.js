// Enhanced Service Worker with proper Background Sync API
/* eslint-disable no-restricted-globals */

importScripts('https://storage.googleapis.com/workbox-cdn/releases/6.4.1/workbox-sw.js');

// Workbox Configuration
workbox.core.setCacheNameDetails({
  prefix: 'haven-health',
  suffix: 'v1',
});

// Skip waiting and claim clients
workbox.core.skipWaiting();
workbox.core.clientsClaim();

// Precache manifest
workbox.precaching.precacheAndRoute(self.__WB_MANIFEST || []);

// IndexedDB setup for offline data
const DB_NAME = 'HavenHealthDB';
const DB_VERSION = 1;
const SYNC_STORE = 'pendingSyncs';

// Initialize IndexedDB
async function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      
      if (!db.objectStoreNames.contains(SYNC_STORE)) {
        db.createObjectStore(SYNC_STORE, { keyPath: 'id', autoIncrement: true });
      }
    };
  });
}
// Register Background Sync
self.addEventListener('message', async (event) => {
  if (event.data && event.data.type === 'REGISTER_SYNC') {
    try {
      const registration = await self.registration;
      await registration.sync.register(event.data.tag || 'health-records-sync');
      
      // Store sync data in IndexedDB
      if (event.data.payload) {
        const db = await openDB();
        const tx = db.transaction([SYNC_STORE], 'readwrite');
        const store = tx.objectStore(SYNC_STORE);
        
        await store.add({
          tag: event.data.tag || 'health-records-sync',
          payload: event.data.payload,
          timestamp: Date.now(),
          retries: 0,
        });
      }
      
      event.ports[0].postMessage({ success: true });
    } catch (error) {
      event.ports[0].postMessage({ success: false, error: error.message });
    }
  }
});

// Handle Background Sync events
self.addEventListener('sync', async (event) => {
  console.log('[Service Worker] Background sync event:', event.tag);
  
  if (event.tag === 'health-records-sync') {
    event.waitUntil(performBackgroundSync());
  } else if (event.tag.startsWith('sync-')) {
    event.waitUntil(performTaggedSync(event.tag));
  }
});
// Perform background sync
async function performBackgroundSync() {
  try {
    const db = await openDB();
    const tx = db.transaction([SYNC_STORE], 'readonly');
    const store = tx.objectStore(SYNC_STORE);
    const allSyncs = await store.getAll();
    
    for (const syncData of allSyncs) {
      try {
        const response = await fetch('/api/sync', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(syncData.payload),
        });
        
        if (response.ok) {
          // Remove successful sync from store
          const deleteTx = db.transaction([SYNC_STORE], 'readwrite');
          await deleteTx.objectStore(SYNC_STORE).delete(syncData.id);
        } else {
          // Update retry count
          syncData.retries++;
          if (syncData.retries < 3) {
            const updateTx = db.transaction([SYNC_STORE], 'readwrite');
            await updateTx.objectStore(SYNC_STORE).put(syncData);
          }
        }
      } catch (error) {
        console.error('Sync failed for item:', syncData.id, error);
      }
    }
    
    // Notify clients of sync completion
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
      client.postMessage({
        type: 'SYNC_COMPLETE',
        timestamp: Date.now(),
      });
    });
    
  } catch (error) {
    console.error('Background sync failed:', error);
    throw error;
  }
}
// Handle periodic background sync
self.addEventListener('periodicsync', async (event) => {
  console.log('[Service Worker] Periodic sync event:', event.tag);
  
  if (event.tag === 'health-records-periodic') {
    event.waitUntil(performPeriodicSync());
  }
});

// Perform periodic sync
async function performPeriodicSync() {
  try {
    // Check for updates
    const response = await fetch('/api/sync/check-updates');
    const data = await response.json();
    
    if (data.hasUpdates) {
      // Trigger regular sync
      await self.registration.sync.register('health-records-sync');
    }
  } catch (error) {
    console.error('Periodic sync failed:', error);
  }
}

// Tagged sync handler
async function performTaggedSync(tag) {
  const db = await openDB();
  const tx = db.transaction([SYNC_STORE], 'readonly');
  const store = tx.objectStore(SYNC_STORE);
  
  const request = store.index('tag').getAll(tag);
  const syncs = await new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  
  for (const sync of syncs) {
    await performBackgroundSync();
  }
}
// Push notification handling
self.addEventListener('push', (event) => {
  const options = {
    body: event.data ? event.data.text() : 'New health record update',
    icon: '/icons/icon-192x192.png',
    badge: '/icons/badge-72x72.png',
    vibrate: [200, 100, 200],
    tag: 'health-update',
    renotify: true,
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1,
    },
    actions: [
      {
        action: 'view',
        title: 'View Update',
        icon: '/icons/checkmark.png',
      },
      {
        action: 'close',
        title: 'Close',
        icon: '/icons/xmark.png',
      },
    ],
  };
  
  event.waitUntil(
    self.registration.showNotification('Haven Health Passport', options)
  );
});

// Notification click handling
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  
  if (event.action === 'view') {
    event.waitUntil(
      clients.openWindow('/updates')
    );
  } else {
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});
// Cache strategies using Workbox
// API calls - Network First
workbox.routing.registerRoute(
  /^https:\/\/api\./,
  new workbox.strategies.NetworkFirst({
    cacheName: 'api-cache',
    networkTimeoutSeconds: 5,
    plugins: [
      new workbox.expiration.ExpirationPlugin({
        maxEntries: 50,
        maxAgeSeconds: 5 * 60, // 5 minutes
      }),
      new workbox.backgroundSync.BackgroundSyncPlugin('api-queue', {
        maxRetentionTime: 24 * 60, // Retry for max of 24 Hours
      }),
    ],
  })
);

// Images - Cache First
workbox.routing.registerRoute(
  /\.(?:png|jpg|jpeg|svg|gif|webp)$/,
  new workbox.strategies.CacheFirst({
    cacheName: 'image-cache',
    plugins: [
      new workbox.expiration.ExpirationPlugin({
        maxEntries: 100,
        maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days
      }),
    ],
  })
);

// Documents (PDFs) - Cache First with larger cache
workbox.routing.registerRoute(
  /\.pdf$/,
  new workbox.strategies.CacheFirst({
    cacheName: 'document-cache',
    plugins: [
      new workbox.expiration.ExpirationPlugin({
        maxEntries: 50,
        maxAgeSeconds: 90 * 24 * 60 * 60, // 90 days
      }),
    ],
  })
);

// Offline fallback
const offlinePage = '/offline.html';
self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match(offlinePage);
      })
    );
  }
});