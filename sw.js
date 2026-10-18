/* Live Salary service worker: makes the app installable and usable offline.
   Bump CACHE whenever the site's files change so old caches are dropped. */

const CACHE = 'live-salary-v2.4.0';

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
    // Only the app itself is cached. The generated reference pages (hourly/, salary/, earns/, …)
    // are plentiful and change with each rebuild, so they go straight to the network.
    const path = url.pathname.replace(/^\//, '') || './';
    if (!APP_SHELL.includes(path) && !url.pathname.startsWith('/assets/')) return;

    const isNavigation = request.mode === 'navigate';

    event.respondWith(
        caches.open(CACHE).then(async (cache) => {
            // Any path with a query string (e.g. ?utm_source=…) still maps to the one cached page.
            const cached = await cache.match(request, { ignoreSearch: isNavigation });

            const refresh = fetch(request).then((response) => {
                // Only store good, non-opaque responses, and never a URL with a query string.
                if (response.ok && response.type !== 'opaque' && !url.search) {
                    event.waitUntil(cache.put(request, response.clone()));
                }
                return response;
            });

            if (cached) {
                event.waitUntil(refresh.catch(() => {}));
                return cached;
            }
            // Offline and nothing cached: a page request falls back to the cached home page.
            return refresh.catch(async () => (isNavigation && await cache.match('./')) || Response.error());
        })
    );
});
