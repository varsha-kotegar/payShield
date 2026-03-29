/**
 * PayShield Service Worker v1
 * Enables: offline app shell, offline QR verification via cached public key,
 * background sync for queued verify requests.
 */
const VERSION   = 'payshield-v1';
const APP_SHELL = ['/', '/vendor', '/manifest.json'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(VERSION)
      .then(c => c.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request).catch(() =>
        new Response(JSON.stringify({ error: 'Offline — API unavailable.' }),
          { status: 503, headers: { 'Content-Type': 'application/json' } })
      )
    );
    return;
  }
  event.respondWith(
    caches.match(event.request).then(cached =>
      cached || fetch(event.request).then(resp => {
        if (event.request.method === 'GET' && resp.status === 200) {
          caches.open(VERSION).then(c => c.put(event.request, resp.clone()));
        }
        return resp;
      }).catch(() => caches.match('/'))
    )
  );
});
