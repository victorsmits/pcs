{% load static %}
// Service worker PCS Live — installable + cache statique + repli hors-ligne.
const CACHE = 'pcs-live-v{{ CSS_VERSION }}';
const SHELL = [
  '/',
  '{% static "css/app.css" %}',
  '{% static "img/icon-192.png" %}'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  // Données live / API : toujours le réseau (fraîcheur)
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/live/')) return;

  // Statiques : cache d'abord
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return resp;
      }))
    );
    return;
  }

  // Navigation : réseau d'abord, repli cache puis page d'accueil
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req).catch(() => caches.match(req).then((hit) => hit || caches.match('/')))
    );
  }
});

// ─────────────── Notifications push ───────────────
self.addEventListener('push', (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { body: e.data && e.data.text() }; }
  const title = d.title || 'PCS Live';
  e.waitUntil(self.registration.showNotification(title, {
    body: d.body || '',
    icon: '{% static "img/icon-192.png" %}',
    badge: '{% static "img/icon-192.png" %}',
    tag: d.tag || undefined,
    renotify: !!d.tag,
    data: { url: d.url || '/' }
  }));
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || '/';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((cl) => {
      for (const c of cl) {
        if (c.url.indexOf(url) !== -1 && 'focus' in c) return c.focus();
      }
      return clients.openWindow(url);
    })
  );
});
