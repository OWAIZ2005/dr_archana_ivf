// App-shell service worker. Caches ONLY same-origin static build assets
// (hashed /_next/static/ chunks, fonts, the generated icons) so the shell
// paints instantly on a repeat visit / flaky clinic wifi. It never caches
// anything else — in particular never a response from the backend API
// (a different origin: :8600 vs this app's :3100/https origin) or any
// same-origin data route. This mirrors the app's own real/fallback rule
// (see CLAUDE.md: "An error should surface, not silently render fake
// data") — a clinical HMIS must not let a service worker hand a nurse
// yesterday's patient list while claiming it's live.

const CACHE_NAME = 'archana-ivf-shell-v1';
const SHELL_CACHEABLE = (url) =>
  url.origin === self.location.origin &&
  (url.pathname.startsWith('/_next/static/') ||
    url.pathname === '/manifest.webmanifest' ||
    url.pathname === '/icon' ||
    url.pathname === '/apple-icon');

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return; // never touch mutations

  const url = new URL(req.url);
  if (!SHELL_CACHEABLE(url)) return; // let the browser handle everything else normally

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(req);
      if (cached) return cached;
      const response = await fetch(req);
      if (response.ok) cache.put(req, response.clone());
      return response;
    })
  );
});
