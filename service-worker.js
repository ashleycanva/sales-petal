const CACHE = 'salepetal-v5';
const NOTIF_STORE = 'salepetal-notif-v1';
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

// ── Periodic Background Sync: check deals.json for new matches ────────────
self.addEventListener('periodicsync', e => {
  if (e.tag === 'check-deals') e.waitUntil(checkForNewDeals());
});

async function checkForNewDeals() {
  try {
    const r = await fetch('/sales-petal/deals.json?t=' + Date.now());
    if (!r.ok) return;
    const data = await r.json();
    const deals = data.deals || [];
    const updatedAt = data.updatedAt || '';

    const store = await caches.open(NOTIF_STORE);
    const prev = await store.match('last-notified');
    const lastNotified = prev ? await prev.text() : '';
    if (updatedAt && updatedAt === lastNotified) return;

    const productMatches = deals.filter(d => d.matched_products && d.matched_products.length > 0);
    let title, body;
    if (productMatches.length > 0) {
      const names = [...new Set(productMatches.flatMap(d => d.matched_products))];
      title = 'Your products are on sale!';
      body = names.slice(0, 2).join(', ') + (names.length > 2 ? ' + ' + (names.length - 2) + ' more' : '') + ' — tap to view';
    } else if (deals.length > 0) {
      title = 'Sale Petal';
      body = deals.length + ' beauty deals found — tap to view';
    } else {
      return;
    }

    await self.registration.showNotification(title, {
      body,
      icon: '/sales-petal/icons/icon-192.png',
      badge: '/sales-petal/icons/icon-192.png',
      vibrate: [200, 100, 200],
      tag: 'deal-update',
      renotify: true,
      data: { url: '/sales-petal/' }
    });

    await store.put('last-notified', new Response(updatedAt));
  } catch (e) {
    console.warn('Periodic sync check failed:', e);
  }
}

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
