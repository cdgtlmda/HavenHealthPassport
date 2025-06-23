/* eslint-disable no-restricted-globals */

// This service worker can be customized!
// See https://developers.google.com/web/tools/workbox/modules
// for the list of available Workbox modules, or add any other
// code you'd like.

const CACHE_NAME = 'haven-health-passport-v1';
const urlsToCache = [
  '/',
  '/static/css/main.css',
  '/static/js/main.js',
  '/manifest.json',
  '/favicon.ico',
  '/logo192.png',
  '/logo512.png',
];

// Install event - cache essential files
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('Opened cache');
      return cache.addAll(urlsToCache);
    })
  );
  // Force the waiting service worker to become the active service worker
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  const cacheWhitelist = [CACHE_NAME];
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  
  // Take control of all pages immediately
  self.clients.claim();
});
// Fetch event - implement caching strategies
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Handle different types of requests with appropriate strategies
  if (request.method !== 'GET') {
    // Don't cache non-GET requests
    return;
  }

  // API calls - Network First strategy
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      networkFirst(request, {
        cacheName: 'api-cache',
        networkTimeoutSeconds: 5,
      })
    );
    return;
  }

  // Images - Cache First strategy
  if (request.destination === 'image') {
    event.respondWith(
      cacheFirst(request, {
        cacheName: 'image-cache',
        maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days
      })
    );
    return;
  }

  // Static assets - Cache First strategy
  if (
    url.pathname.startsWith('/static/') ||
    url.pathname.endsWith('.js') ||
    url.pathname.endsWith('.css')
  ) {
    event.respondWith(
      cacheFirst(request, {
        cacheName: 'static-cache',
        maxAgeSeconds: 7 * 24 * 60 * 60, // 7 days
      })
    );
    return;
  }

  // HTML pages - Network First strategy
  if (request.mode === 'navigate' || request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      networkFirst(request, {
        cacheName: 'pages-cache',
        networkTimeoutSeconds: 3,
      })
    );
    return;
  }

  // Default - Network First
  event.respondWith(
    networkFirst(request, {
      cacheName: CACHE_NAME,
      networkTimeoutSeconds: 5,
    })
  );
});
// Network First strategy
async function networkFirst(request, options = {}) {
  const { cacheName, networkTimeoutSeconds = 5 } = options;
  
  try {
    const networkResponse = await fetchWithTimeout(request, networkTimeoutSeconds * 1000);
    
    if (networkResponse.ok) {
      // Cache successful responses
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    // Network failed, try cache
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Return offline page for navigation requests
    if (request.mode === 'navigate') {
      return caches.match('/offline.html');
    }
    
    throw error;
  }
}

// Cache First strategy
async function cacheFirst(request, options = {}) {
  const { cacheName, maxAgeSeconds } = options;
  
  const cachedResponse = await caches.match(request);
  
  if (cachedResponse && !isExpired(cachedResponse, maxAgeSeconds)) {
    return cachedResponse;
  }
  
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    if (cachedResponse) {
      // Return stale cache if network fails
      return cachedResponse;
    }
    throw error;
  }
}
// Utility function to fetch with timeout
function fetchWithTimeout(request, timeout) {
  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      reject(new Error('Network request timeout'));
    }, timeout);
    
    fetch(request)
      .then((response) => {
        clearTimeout(timeoutId);
        resolve(response);
      })
      .catch((error) => {
        clearTimeout(timeoutId);
        reject(error);
      });
  });
}

// Check if cached response is expired
function isExpired(response, maxAgeSeconds) {
  if (!maxAgeSeconds) return false;
  
  const dateHeader = response.headers.get('date');
  if (!dateHeader) return false;
  
  const date = new Date(dateHeader);
  const age = (Date.now() - date.getTime()) / 1000;
  
  return age > maxAgeSeconds;
}

// Background sync for offline actions
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-health-records') {
    event.waitUntil(syncHealthRecords());
  }
});

async function syncHealthRecords() {
  try {
    const syncData = await getSyncData();
    
    if (syncData && syncData.length > 0) {
      const response = await fetch('/api/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(syncData),
      });
      
      if (response.ok) {
        await clearSyncData();
        self.registration.showNotification('Data synced successfully', {
          body: 'Your offline changes have been synchronized.',
          icon: '/logo192.png',
          badge: '/logo192.png',
        });
      }
    }
  } catch (error) {
    console.error('Sync failed:', error);
  }
}
// Helper functions for IndexedDB operations
async function getSyncData() {
  // This would interact with IndexedDB to get pending sync data
  return new Promise((resolve) => {
    // Placeholder - implement IndexedDB logic
    resolve([]);
  });
}

async function clearSyncData() {
  // This would clear synced data from IndexedDB
  return new Promise((resolve) => {
    // Placeholder - implement IndexedDB logic
    resolve();
  });
}

// Push notification handling
self.addEventListener('push', (event) => {
  const options = {
    body: event.data ? event.data.text() : 'New update available',
    icon: '/logo192.png',
    badge: '/logo192.png',
    vibrate: [200, 100, 200],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1,
    },
  };
  
  event.waitUntil(
    self.registration.showNotification('Haven Health Passport', options)
  );
});

// Notification click handling
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  
  event.waitUntil(
    clients.openWindow('/')
  );
});