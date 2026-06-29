const CACHE_NAME = 'sgi-cache-v1';
const OFFLINE_URL = '/offline/';

// URLs to pre-cache during install
const PRECACHE_URLS = [
  '/',
  '/static/manifest.json',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/static/icons/logo-original.png',
  '/offline/',
  // CSS and JS main files
  '/static/css/style.css',
  '/static/css/login.css',
  '/static/js/js.js',
];

self.addEventListener('install', event => {
  // Skip waiting to activate new SW immediately
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(PRECACHE_URLS);
    })
  );
});

self.addEventListener('activate', event => {
  // Remove old caches
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(name => name !== CACHE_NAME).map(name => caches.delete(name))
      );
    })
  );
});

// Network First strategy for navigation (HTML pages)
function networkFirst(request) {
  return fetch(request)
    .then(response => {
      // If we got a valid response, update the cache.
      const copy = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
      return response;
    })
    .catch(() => {
      // Network request failed, try to serve from cache.
      return caches.match(request).then(cached => {
        if (cached) return cached;
        // If offline page is cached, return it; otherwise return a generic fallback.
        return caches.match(OFFLINE_URL);
      });
    });
}

// Cache First strategy for static assets (CSS, JS, images, icons)
function cacheFirst(request) {
  return caches.match(request).then(cached => {
    return cached || fetch(request).then(response => {
      // Put a copy in the cache for next time.
      const copy = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
      return response;
    });
  });
}

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);

  // Ignore non-GET requests
  if (request.method !== 'GET') return;

  // Navigation requests (HTML pages)
  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request));
    return;
  }

  // Static assets
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Fallback to network for everything else
  event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_URL)));
});
