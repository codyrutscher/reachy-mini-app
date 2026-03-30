const CACHE_NAME = 'reachy-care-v2';
const STATIC_ASSETS = [
  '/',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
];

// Pages to cache for offline access
const PAGE_CACHE = 'reachy-pages-v1';
const CACHEABLE_PAGES = [
  '/', '/patients', '/history', '/family', '/live',
  '/medications', '/schedule', '/reports', '/activity',
];

// Install — cache static assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activate — clean old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch — network first, fall back to cache
self.addEventListener('fetch', event => {
  // Skip SSE and API POST requests
  if (event.request.url.includes('/stream') ||
      (event.request.url.includes('/api/') && event.request.method === 'POST')) {
    return;
  }

  // API GET requests — network first, cache fallback for offline
  if (event.request.url.includes('/api/') && event.request.method === 'GET') {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(PAGE_CACHE).then(cache => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => caches.match(event.request).then(r => r || new Response('{"error":"offline"}', {
          headers: {'Content-Type': 'application/json'}
        })))
    );
    return;
  }

  // Pages and static assets — network first, cache fallback
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response.ok && event.request.method === 'GET') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});

// Handle push notification messages from main thread
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'notify') {
    self.registration.showNotification(event.data.title, {
      body: event.data.body,
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      vibrate: [200, 100, 200],
      tag: 'reachy-alert',
      renotify: true,
      actions: [
        { action: 'open', title: 'Open Dashboard' },
        { action: 'dismiss', title: 'Dismiss' },
      ],
    });
  }
});

// Notification click — open dashboard
self.addEventListener('notificationclick', event => {
  event.notification.close();
  if (event.action === 'dismiss') return;
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then(windowClients => {
      for (const client of windowClients) {
        if (client.url.includes('/') && 'focus' in client) {
          return client.focus();
        }
      }
      return clients.openWindow('/');
    })
  );
});
