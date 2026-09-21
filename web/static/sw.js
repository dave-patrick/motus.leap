// Cache only same-origin static GETs. Private pages and API responses stay network-only.
const CACHE_NAME = 'motus-leap-v4';
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter(name => name.startsWith('motus-leap-') && name !== CACHE_NAME)
      .map(name => caches.delete(name)));
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin ||
      !url.pathname.startsWith('/static/')) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    try {
      const response = await fetch(event.request, {cache: 'no-cache'});
      if (response.ok && !response.redirected) await cache.put(event.request, response.clone());
      return response;
    } catch (_) {
      return await cache.match(event.request) || new Response('Offline', {status: 503});
    }
  })());
});
