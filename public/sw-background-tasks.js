// Service Worker for Background Tasks
// This file should be placed in the public directory as sw-background-tasks.js

self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing background tasks service worker');
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activating background tasks service worker');
  event.waitUntil(clients.claim());
});

// Handle background sync events
self.addEventListener('sync', async (event) => {
  console.log('[Service Worker] Background sync event:', event.tag);
  
  if (event.tag.startsWith('haven-')) {
    event.waitUntil(handleBackgroundSync(event.tag));
  }
});

// Handle periodic background sync events
self.addEventListener('periodicsync', async (event) => {
  console.log('[Service Worker] Periodic background sync event:', event.tag);
  
  if (event.tag.startsWith('haven-')) {
    event.waitUntil(handlePeriodicBackgroundSync(event.tag));
  }
});

async function handleBackgroundSync(taskId) {
  try {
    // Get task data from IndexedDB
    const taskData = await getTaskData(taskId);
    if (!taskData) {
      console.warn(`[Service Worker] No task data found for ${taskId}`);
      return;
    }

    // Send message to client to execute task
    const client = await getClient();
    if (client) {
      const result = await sendMessageToClient(client, {
        type: 'execute-task',
        taskId: taskId,
      });
      
      console.log(`[Service Worker] Task ${taskId} completed:`, result);
    } else {
      console.warn('[Service Worker] No client available to execute task');
    }
  } catch (error) {
    console.error(`[Service Worker] Error handling sync for ${taskId}:`, error);
  }
}

async function handlePeriodicBackgroundSync(taskId) {
  try {
    // Similar to handleBackgroundSync but for periodic tasks
    await handleBackgroundSync(taskId);
    
    // Update next scheduled execution
    await updateTaskExecutionHistory(taskId);
  } catch (error) {
    console.error(`[Service Worker] Error handling periodic sync for ${taskId}:`, error);
  }
}

async function getClient() {
  const clients = await self.clients.matchAll({
    type: 'window',
    includeUncontrolled: true,
  });
  
  return clients[0] || null;
}

async function sendMessageToClient(client, message) {
  return new Promise((resolve) => {
    const channel = new MessageChannel();
    channel.port1.onmessage = (event) => {
      resolve(event.data);
    };
    
    client.postMessage(message, [channel.port2]);
  });
}

async function getTaskData(taskId) {
  const db = await openTaskDB();
  const tx = db.transaction(['tasks'], 'readonly');
  const store = tx.objectStore('tasks');
  
  return await store.get(taskId);
}

async function updateTaskExecutionHistory(taskId) {
  const db = await openTaskDB();
  const tx = db.transaction(['tasks'], 'readwrite');
  const store = tx.objectStore('tasks');
  
  const existing = await store.get(taskId);
  if (existing) {
    existing.lastExecution = Date.now();
    existing.nextScheduledExecution = existing.options?.interval 
      ? Date.now() + existing.options.interval
      : null;
    
    await store.put(existing);
  }
}

function openTaskDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('HavenBackgroundTasks', 1);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('tasks')) {
        db.createObjectStore('tasks', { keyPath: 'taskId' });
      }
    };
  });
}
