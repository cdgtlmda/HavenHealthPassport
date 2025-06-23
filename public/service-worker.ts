/// <reference lib="webworker" />

// Service Worker for Haven Health Passport PWA
const CACHE_VERSION = 'v1';
const CACHE_NAME = `haven-health-${CACHE_VERSION}`;
const DYNAMIC_CACHE_NAME = `haven-health-dynamic-${CACHE_VERSION}`;

// Resources to cache immediately
const STATIC_CACHE_URLS = [
  '/',
  '/offline.html',
  '/manifest.json',
  '/css/app.css',
  '/js/app.js',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
];

// API endpoints to cache with network-first strategy
const API_CACHE_PATTERNS = [
  /\/api\/health-records/,
  /\/api\/providers/,
  /\/api\/emergency-contacts/,
  /\/api\/user\/profile/,
];

// Resources to never cache
const CACHE_EXCLUSIONS = [
  /\/api\/auth/,
  /\/api\/sync/,
  /\/ws/,
  /hot-update/,
];

// Install event - cache static resources
self.addEventListener('install', (event: ExtendableEvent) => {
  console.log('[ServiceWorker] Installing...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[ServiceWorker] Caching static resources');
        return cache.addAll(STATIC_CACHE_URLS);
      })
      .then(() => {
        console.log('[ServiceWorker] Skip waiting');
        return (self as any).skipWaiting();
      })
      .catch(error => {
        console.error('[ServiceWorker] Installation failed:', error);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event: ExtendableEvent) => {
  console.log('[ServiceWorker] Activating...');
  
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames
            .filter(cacheName => {
              return cacheName.startsWith('haven-health-') && 
                     cacheName !== CACHE_NAME &&
                     cacheName !== DYNAMIC_CACHE_NAME;
            })
            .map(cacheName => {
              console.log('[ServiceWorker] Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            })
        );
      })
      .then(() => {
        console.log('[ServiceWorker] Claiming clients');
        return (self as any).clients.claim();
      })
  );
});

// Fetch event - implement caching strategies
self.addEventListener('fetch', (event: FetchEvent) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Skip requests that should not be cached
  if (CACHE_EXCLUSIONS.some(pattern => pattern.test(url.pathname))) {
    return;
  }

  // Determine caching strategy
  if (API_CACHE_PATTERNS.some(pattern => pattern.test(url.pathname))) {
    // Network first, fallback to cache for API calls
    event.respondWith(networkFirstStrategy(request));
  } else if (request.destination === 'image' || 
             url.pathname.includes('/static/') ||
             url.pathname.includes('/assets/')) {
    // Cache first for static assets
    event.respondWith(cacheFirstStrategy(request));
  } else if (request.mode === 'navigate') {
    // Network first for navigation requests
    event.respondWith(
      fetch(request)
        .catch(() => {
          return caches.match('/offline.html') as Promise<Response>;
        })
    );
  } else {
    // Stale while revalidate for everything else
    event.respondWith(staleWhileRevalidateStrategy(request));
  }
});

// Cache-first strategy
async function cacheFirstStrategy(request: Request): Promise<Response> {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  
  if (cached) {
    return cached;
  }

  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    console.error('[ServiceWorker] Cache-first fetch failed:', error);
    // Return offline page for navigation requests
    if (request.mode === 'navigate') {
      const offlineResponse = await caches.match('/offline.html');
      if (offlineResponse) {
        return offlineResponse;
      }
    }
    throw error;
  }
}

// Network-first strategy
async function networkFirstStrategy(request: Request): Promise<Response> {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(DYNAMIC_CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    console.log('[ServiceWorker] Network-first fetch failed, trying cache:', error);
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }
    throw error;
  }
}

// Stale-while-revalidate strategy
async function staleWhileRevalidateStrategy(request: Request): Promise<Response> {
  const cache = await caches.open(DYNAMIC_CACHE_NAME);
  const cached = await cache.match(request);
  
  const fetchPromise = fetch(request).then(response => {
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  }).catch(error => {
    console.error('[ServiceWorker] Stale-while-revalidate fetch failed:', error);
    throw error;
  });

  return cached || fetchPromise;
}

// Background sync event
self.addEventListener('sync', (event: any) => {
  console.log('[ServiceWorker] Sync event:', event.tag);
  
  if (event.tag === 'sync-health-records') {
    event.waitUntil(syncHealthRecords());
  } else if (event.tag === 'sync-offline-changes') {
    event.waitUntil(syncOfflineChanges());
  }
});

// Push notification event
self.addEventListener('push', (event: PushEvent) => {
  console.log('[ServiceWorker] Push notification received');
  
  const options = {
    body: 'You have new updates in Haven Health Passport',
    icon: '/icons/icon-192x192.png',
    badge: '/icons/badge-72x72.png',
    vibrate: [200, 100, 200],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'view',
        title: 'View Updates',
        icon: '/icons/checkmark.png'
      },
      {
        action: 'close',
        title: 'Close',
        icon: '/icons/close.png'
      }
    ]
  };

  if (event.data) {
    const data = event.data.json();
    Object.assign(options, {
      body: data.body || options.body,
      title: data.title || 'Haven Health Passport',
      data: data
    });
  }

  event.waitUntil(
    (self as any).registration.showNotification('Haven Health Passport', options)
  );
});

// Notification click event
self.addEventListener('notificationclick', (event: NotificationEvent) => {
  console.log('[ServiceWorker] Notification click:', event.action);
  
  event.notification.close();

  if (event.action === 'view') {
    event.waitUntil(
      (self as any).clients.openWindow('/notifications')
    );
  }
});

// Message event for client communication
self.addEventListener('message', (event: ExtendableMessageEvent) => {
  console.log('[ServiceWorker] Message received:', event.data);
  
  if (event.data.type === 'SKIP_WAITING') {
    (self as any).skipWaiting();
  } else if (event.data.type === 'CACHE_URLS') {
    event.waitUntil(
      cacheUrls(event.data.urls).then(() => {
        event.ports[0].postMessage({ cached: true });
      })
    );
  } else if (event.data.type === 'CLEAR_CACHE') {
    event.waitUntil(
      clearAllCaches().then(() => {
        event.ports[0].postMessage({ cleared: true });
      })
    );
  }
});

// Helper function to cache specific URLs
async function cacheUrls(urls: string[]): Promise<void> {
  const cache = await caches.open(DYNAMIC_CACHE_NAME);
  await cache.addAll(urls);
}

// Helper function to clear all caches
async function clearAllCaches(): Promise<boolean[]> {
  const cacheNames = await caches.keys();
  return Promise.all(
    cacheNames.map(cacheName => caches.delete(cacheName))
  );
}

// Sync health records
async function syncHealthRecords(): Promise<void> {
  try {
    const response = await fetch('/api/sync/health-records', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        lastSync: await getLastSyncTime(),
      }),
    });

    if (response.ok) {
      await updateLastSyncTime();
      console.log('[ServiceWorker] Health records synced successfully');
    }
  } catch (error) {
    console.error('[ServiceWorker] Health records sync failed:', error);
    throw error;
  }
}

// Sync offline changes
async function syncOfflineChanges(): Promise<void> {
  try {
    // Get offline changes from IndexedDB
    const changes = await getOfflineChanges();
    
    if (changes.length === 0) {
      console.log('[ServiceWorker] No offline changes to sync');
      return;
    }

    const response = await fetch('/api/sync/offline-changes', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ changes }),
    });

    if (response.ok) {
      await clearOfflineChanges();
      console.log('[ServiceWorker] Offline changes synced successfully');
    }
  } catch (error) {
    console.error('[ServiceWorker] Offline changes sync failed:', error);
    throw error;
  }
}

// Helper functions for sync (these would interact with IndexedDB)
async function getLastSyncTime(): Promise<number> {
  // Implementation would retrieve from IndexedDB
  return Date.now() - 86400000; // 24 hours ago as placeholder
}

async function updateLastSyncTime(): Promise<void> {
  // Implementation would store in IndexedDB
}

async function getOfflineChanges(): Promise<any[]> {
  // Implementation would retrieve from IndexedDB
  return [];
}

async function clearOfflineChanges(): Promise<void> {
  // Implementation would clear from IndexedDB
}

// Export for TypeScript
export {};