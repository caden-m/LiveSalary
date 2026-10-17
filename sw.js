/* Live Salary service worker: makes the app installable and usable offline.
   Bump CACHE whenever the site's files change so old caches are dropped. */

const CACHE = 'live-salary-v2.2.0';

const APP_SHELL = [
    './',
    'styles.css',
    'script.js',
    'theme.js',
    'manifest.json',
    'assets/fonts/inter-latin.woff2',
    'assets/fonts/jetbrains-mono-latin.woff2',
    'assets/icon.svg',
    'assets/icon-192.png',
    'assets/icon-512.png',
    'assets/apple-touch-icon.png'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE)
            // cache: 'reload' bypasses the HTTP cache so a new version never installs stale files.
            .then((cache) => cache.addAll(APP_SHELL.map((url) => new Request(url, { cache: 'reload' }))))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

// Stale-while-revalidate: answer from cache immediately, refresh the cache in the background.
// Only our own files are cached; anything from another origin passes straight through.
self.addEventListener('fetch', (event) => {
    const { request } = event;
    if (request.method !== 'GET') return;

    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;

    const isNavigation = request.mode === 'navigate';

    event.respondWith(
        caches.open(CACHE).then(async (cache) => {
            // Any path with a query string (e.g. ?utm_source=…) still maps to the one cached page.
            const cached = isNavigation
                ? (await cache.match(request, { ignoreSearch: true })) || (await cache.match('./'))
                : await cache.match(request);

            const refresh = fetch(request).then((response) => {
                // Only store good, non-opaque responses, and never a URL with a query string.
                if (response.ok && response.type !== 'opaque' && !url.search) {
                    const copy = response.clone();
                    event.waitUntil(cache.put(isNavigation ? './' : request, copy));
                }
                return response;
            });

            if (cached) {
                event.waitUntil(refresh.catch(() => {}));
                return cached;
            }
            return refresh.catch(() => Response.error());
        })
    );
});
