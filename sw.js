// ── GymOS Service Worker con Push Notifications ──────────────────────────────
const CACHE_NAME = 'gymos-v3';
const ASSETS = ['/socio/', '/static/css/', '/static/icons/'];

// ── Instalación ───────────────────────────────────────────────────────────────
self.addEventListener('install', e => {
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ── Fetch: cache-first para assets estáticos ──────────────────────────────────
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  // No cachear las APIs
  if (url.pathname.startsWith('/api/')) return;
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});

// ── Push: recibir notificación del servidor ───────────────────────────────────
self.addEventListener('push', e => {
  if (!e.data) return;
  let data = {};
  try { data = e.data.json(); } catch { data = { title: 'GymOS', body: e.data.text() }; }

  const title   = data.title || 'GymOS';
  const options = {
    body:    data.body  || '',
    icon:    data.icon  || '/static/icons/icon-192.png',
    badge:   '/static/icons/icon-72.png',
    vibrate: [200, 100, 200],
    data:    { url: data.url || '/' },
    actions: [
      { action: 'abrir', title: 'Ver ahora' },
      { action: 'cerrar', title: 'Cerrar' }
    ]
  };

  e.waitUntil(self.registration.showNotification(title, options));
});

// ── NotificationClick: abrir la app al tocar ─────────────────────────────────
self.addEventListener('notificationclick', e => {
  e.notification.close();
  if (e.action === 'cerrar') return;

  const url = e.notification.data && e.notification.data.url ? e.notification.data.url : '/';

  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
      // Si ya hay una ventana abierta, enfocarla
      for (const client of windowClients) {
        if (client.url.includes(self.location.origin)) {
          client.focus();
          client.navigate(url);
          return;
        }
      }
      // Si no, abrir una nueva
      return clients.openWindow(url);
    })
  );
});

// ── PushSubscriptionChange: renovar suscripción automáticamente ───────────────
self.addEventListener('pushsubscriptionchange', e => {
  e.waitUntil(
    self.registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: e.oldSubscription ? e.oldSubscription.options.applicationServerKey : null
    }).then(sub => {
      return fetch('/api/push/suscribir', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          socio_id: null, // se recupera del contexto
          endpoint: sub.endpoint,
          p256dh: btoa(String.fromCharCode(...new Uint8Array(sub.getKey('p256dh')))),
          auth:   btoa(String.fromCharCode(...new Uint8Array(sub.getKey('auth'))))
        })
      });
    })
  );
});

// ── Mensaje desde el cliente ──────────────────────────────────────────────────
self.addEventListener('message', e => {
  if (e.data && e.data.type === 'SKIP_WAITING') self.skipWaiting();
});
