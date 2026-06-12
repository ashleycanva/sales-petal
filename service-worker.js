// No caching — browser handles that natively.
// This SW exists only for push notifications + periodic background sync.

const NOTIF_STORE = 'salepetal-notif-v1';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => {
  // Delete ALL old caches from previous versions
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k)))));
  self.clients.claim();
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
    const updatedAt = data.updatedAt || '';

    const store = await caches.open(NOTIF_STORE);
    const prev = await store.match('last-notified');
    const lastNotified = prev ? await prev.text() : '';
    if (updatedAt && updatedAt === lastNotified) return;

    const products = data.products || [];
    const brands = data.brands || [];

    // Products on sale anywhere
    const onSale = products.filter(p => p.on_sale);
    // Products with a brand promo alert
    const withPromo = products.filter(p => p.brand_promo_alert && !p.on_sale);
    // Brands with active deals
    const brandsWithDeals = brands.filter(b => b.has_deals);

    let title, body;
    if (onSale.length > 0) {
      title = 'Your products are on sale!';
      const names = onSale.slice(0, 2).map(p => p.name);
      body = names.join(', ') + (onSale.length > 2 ? ' + ' + (onSale.length - 2) + ' more' : '') + ' — tap to view';
    } else if (withPromo.length > 0) {
      title = 'Brand promo for your products!';
      body = withPromo[0].brand + ': ' + withPromo[0].brand_promo_alert;
    } else if (brandsWithDeals.length > 0) {
      title = 'New brand promotions!';
      body = brandsWithDeals.slice(0, 2).map(b => b.name).join(', ') + ' have active deals — tap to view';
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

// ── Push notifications ─────────────────────────────────────────────────────
self.addEventListener('push', e => {
  const data = e.data ? e.data.json() : {};
  const title = data.title || 'Sale Petal';
  const options = {
    body: data.body || 'New beauty deals found!',
    icon: '/sales-petal/icons/icon-192.png',
    badge: '/sales-petal/icons/icon-192.png',
    vibrate: [200, 100, 200],
    data: { url: data.url || '/sales-petal/' }
  };
  e.waitUntil(self.registration.showNotification(title, options));
});

// ── Notification click: open the app ──────────────────────────────────────
self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      const existing = list.find(c => c.url.includes('sales-petal'));
      if (existing) return existing.focus();
      return clients.openWindow(e.notification.data.url || '/sales-petal/');
    })
  );
});
