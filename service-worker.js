const CACHE = 'salepetal-v4';
const ASSETS = [
  '/sales-petal/',
  '/sales-petal/index.html',
  '/sales-petal/manifest.json'
];

// ── Install: cache core files ──────────────────────────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(cache => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

// ── Activate: clear old caches ─────────────────────────────────────────────
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── Fetch: serve from cache, fall back to network ─────────────────────────
self.addEventListener('fetch', e => {
  // Don't intercept API calls — always go live for those
  if (e.request.url.includes('anthropic.com') || e.request.url.includes('fonts.g')) {
    return;
  }
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});

// ── Push notifications ─────────────────────────────────────────────────────
self.addEventListener('push', e => {
  const data = e.data ? e.data.json() : {};
  const title = data.title || 'Sale Petal';
  const options = {
    body: data.body || 'New beauty deals found!',
    icon: '/sales-petal/icons/icon-192.png',
    badge: '/sales-petal/icons/icon-192.png',
    vibrate: [200, 100, 200],
    data: { url: data.url || '/sales-petal/' },
    actions: [
      { action: 'view', title: 'View Deals' },
      { action: 'dismiss', title: 'Dismiss' }
    ]
  };
  e.waitUntil(self.registration.showNotification(title, options));
});

// ── Notification click: open the app ──────────────────────────────────────
self.addEventListener('notificationclick', e => {
  e.notification.close();
  if (e.action === 'dismiss') return;
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      const existing = list.find(c => c.url.includes('sales-petal'));
      if (existing) return existing.focus();
      return clients.openWindow(e.notification.data.url || '/sales-petal/');
    })
  );
});
