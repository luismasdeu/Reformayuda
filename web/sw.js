// Service worker de Reformayuda: la app funciona sin conexión y las ayudas se actualizan al volver la red.
const VERSION = "reformayuda-v3";
const SHELL = ["./", "index.html", "data/ayudas.json", "manifest.webmanifest", "icons/icon.svg", "icons/icon-192.png", "icons/icon-512.png", "fonts/bricolage-grotesque.woff2", "fonts/nunito-sans.woff2"];

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
  if (e.request.mode === "navigate" || url.pathname.endsWith("/data/ayudas.json") || url.pathname.endsWith("/index.html")) {
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
