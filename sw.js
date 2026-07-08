// GymOS Service Worker v1.0
const CACHE_NAME = 'gymos-pwa-v1';
const STATIC_ASSETS = [
  '/',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

// ── Instalación ──────────────────────────────────────────
self.addEventListener('install', function(e) {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(STATIC_ASSETS).catch(function() {});
    })
  );
});

// ── Activación ───────────────────────────────────────────
self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE_NAME; })
            .map(function(k) { return caches.delete(k); })
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

// ── Fetch: network first, cache fallback ─────────────────
self.addEventListener('fetch', function(e) {
  // Solo cachear GETs, no APIs
  if (e.request.method !== 'GET') return;
  if (e.request.url.includes('/api/')) return;

  e.respondWith(
    fetch(e.request)
      .then(function(response) {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(e.request, clone);
          });
        }
        return response;
      })
      .catch(function() {
        return caches.match(e.request);
      })
  );
});

// ── Background Sync (para guardar pasos offline) ─────────
self.addEventListener('sync', function(e) {
  if (e.tag === 'sync-pasos') {
    e.waitUntil(sincronizarPasosPendientes());
  }
});

async function sincronizarPasosPendientes() {
  // Si hay datos pendientes de pasos guardados offline, los envía
  const cache = await caches.open(CACHE_NAME);
  // Implementación futura: enviar pasos guardados en IDB cuando vuelve la conexión
}

// ── Mensajes desde la página ─────────────────────────────
self.addEventListener('message', function(e) {
  if (e.data && e.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
