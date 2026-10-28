// Service worker de Reformayuda: la app funciona sin conexión y las ayudas se actualizan al volver la red.
const VERSION = "reformayuda-v8";
const SHELL = ["./", "index.html", "data/ayudas.json", "data/preguntas.json", "manifest.webmanifest", "icons/icon.svg", "icons/icon-192.png", "icons/icon-512.png", "fonts/bricolage-grotesque.woff2", "fonts/nunito-sans.woff2"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  // La página y los datos de ayudas: primero la red (para ver siempre lo último) y, sin conexión, la copia guardada.
  if (e.request.mode === "navigate" || url.pathname.includes("/data/") || url.pathname.endsWith("/index.html")) {
    e.respondWith(fetch(e.request).then(r => {
      const copy = r.clone(); caches.open(VERSION).then(c => c.put(e.request, copy)); return r;
    }).catch(() => caches.match(e.request).then(r => r || caches.match("index.html"))));
    return;
  }
  // Resto: primero la copia guardada y se refresca en segundo plano.
  e.respondWith(caches.match(e.request).then(hit => {
    const net = fetch(e.request).then(r => {
      if (r.ok) { const copy = r.clone(); caches.open(VERSION).then(c => c.put(e.request, copy)); }
      return r;
    }).catch(() => hit);
    return hit || net;
  }));
});

// Notificaciones: llegan desde Firebase Cloud Messaging con los datos {title, body, url}.
self.addEventListener("push", e => {
  let p = {};
  try { p = e.data ? e.data.json() : {}; } catch (err) { p = { data: { body: e.data && e.data.text() } }; }
  const d = p.data || {}, n = p.notification || {};
  const title = d.title || n.title || "Reformayuda";
  e.waitUntil(self.registration.showNotification(title, {
    body: d.body || n.body || "Hay novedades en tus ayudas.",
    icon: "icons/icon-192.png",
    badge: "icons/icon-monochrome-512.png",
    tag: d.tag || "reformayuda",
    data: { url: d.url || "./" }
  }));
});

self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = new URL(e.notification.data && e.notification.data.url || "./", self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(ws => {
    for (const w of ws) if (w.url.startsWith(self.registration.scope) && "navigate" in w) return w.navigate(url).then(c => c && c.focus());
    return self.clients.openWindow(url);
  }));
});
