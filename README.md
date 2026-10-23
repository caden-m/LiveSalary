# Live Salary

A minimalist live earnings counter at **[mylivesalary.com](https://mylivesalary.com)**.
Enter an hourly rate or annual salary and watch what you earn tick up, second by second.

No build step, no framework, no backend. Everything is saved only in the visitor's browser.

## Files

| File | What it does |
| --- | --- |
| `index.html` | The page: clock, the big amount, controls, projections and the settings sheet. |
| `script.js` | All behaviour: saving/restoring state, stopwatch and workday modes, currency formatting, milestone pulses. |
| `styles.css` | Design tokens (dark and light), layout, settings sheet, animations. |
| `theme.js` | Tiny blocking script that applies a saved theme before first paint. Separate file so the page can use a strict Content-Security-Policy with no inline scripts. |
| `manifest.json` | Web-app manifest so the site can be installed to a home screen. |
| `sw.js` | Service worker: caches the app shell so it loads instantly and works offline. |
| `assets/` | Icons and the social preview image, plus the SVG sources they were rendered from. |
| `build/generate.py`, `build/data/` | Generator for every page except the home page (see below). The data files are the only thing to edit when adding a rate, a state, a person or a job. |
| `hourly/`, `salary/`, `monthly/`, `biweekly/`, `earns/`, `about/`, `methodology/`, `privacy/`, `contact/`, `embed/`, `sitemaps/` | **Generated** — don't edit by hand; run the generator instead. |
| `pages.css`, `counter.js` | Styles and the preloaded live counter used by the generated pages and the embeddable widget. |
| `robots.txt`, `sitemap.xml` | Tell search engines the site may be indexed and where the page is. Update `lastmod` in the sitemap when the page changes meaningfully. |
| `assets/fonts/` | Self-hosted Inter and JetBrains Mono (latin subset, variable weight, woff2). Loaded by `@font-face` rules at the top of `styles.css`. |
| `CNAME` | Tells GitHub Pages to serve the site at `mylivesalary.com`. Don't delete it. |

## Features

- **Stopwatch mode** — start/stop/reset; keeps counting even if the tab is closed and reopened.
- **Workday mode** — counts automatically between a start and end time each day, with a progress bar. Overnight shifts work.
- **Hourly or annual** rate, with hours-per-week, and day/week/month/year projections.
- **16 currencies**, formatted for the visitor's locale.
- **Privacy mode** blurs every number; the tab title stops showing the amount too.
- **Auto / dark / light** theme.
- **Milestone pulses** — the glow flares each time the amount crosses a whole unit (or a larger step at high rates).
- **Goal, tips and overtime** (Settings → Extras) — a target amount with a progress bar and time-to-go, a flat tips amount added to the day, and time-and-a-half after 8 hours.
- **Share a snapshot** — the share button renders the current counter to an image on the device and opens the system share sheet (or downloads it).
- Keyboard: `Space` start/stop · `R` reset · `P` privacy · `S` settings · `Esc` close.

Settings and timer state live in `localStorage` under the key `mls.v2`.

## Working on it locally

Any static file server works. With the Python that ships on macOS:

```bash
python3 -m http.server 8765
```

Then open <http://localhost:8765>.

Because of the service worker, a hard refresh (⌘⇧R) or "Update on reload" in DevTools → Application → Service Workers is the quickest way to see changes while developing.

## Generated pages

Besides the counter, the site has a few hundred static pages aimed at searches like "$25 an hour is how much a year" and "how much does LeBron James make per second". They're produced by:

```bash
python3 build/generate.py
```

It reads:

- `build/data/wages.json` — which hourly rates, salaries, monthly and biweekly amounts get a page;
- `build/data/states.json` — 2025 single-filer income tax brackets and deductions, minimum wage and median household income for all 50 states and DC (each wage and salary page gets a sub-page per state, e.g. `/hourly/25/california/`);
- `build/data/people.json` — athletes, musicians and executives with estimated annual earnings and sources;
- `build/data/occupations.json` — BLS median wages.

- `build/data/organizations.json` — companies and governments with revenue, profit or outlays and sources.

It writes about 14,000 pages (most of them state pages), the About/Methodology/Privacy/Contact pages, the embed page and widget, and `sitemap.xml` as an index of the files in `sitemaps/`. It also writes a social-preview card (SVG) per base page into `build/og/`; run `./build/render_og.sh` afterwards to render new or changed cards to `assets/og/*.png` with macOS QuickLook (state pages reuse their parent wage's card). Federal tax brackets, the US median wage and other assumptions live at the top of the script and are documented on `/methodology/`; refresh them, the state data and the earnings data once a year. Commit the regenerated output along with the data change. Set `CONTACT_EMAIL` in the script to show an address on the contact page.

## Deploying

The site is hosted on **GitHub Pages** from the `main` branch of this repository. Deploying is just:

```bash
git push origin main
```

GitHub rebuilds the site within a minute or so. Work on a branch, then merge into `main` when it's ready.

**When you change any file, bump `CACHE` in `sw.js`** (for example `live-salary-v2.0.1`). Visitors who already have the old version cached get the new one on their next load.

### Security notes

- The page sets a Content-Security-Policy via a `<meta>` tag (GitHub Pages can't send custom headers). It allows scripts, styles and fonts only from this site, so **don't add inline `<script>` or `style=""`** — put code in files instead.
- Make sure **"Enforce HTTPS"** is ticked in the repository's Settings → Pages, and that `mylivesalary.com` is listed under your account's Settings → Pages → Verified domains. Both are GitHub settings, not files in this repo.
- The site makes no third-party requests at all: the two font families are self-hosted under `assets/fonts/`, so nothing about a visit is shared with Google or anyone else, and the app works fully offline.

### Visitor counting

Page views are counted with [GoatCounter](https://www.goatcounter.com) — dashboard at <https://cadenlivesalary.goatcounter.com>. It is cookie-free and records only the path, referrer, browser, screen size and country, so no consent banner is needed and nothing the visitor types is ever sent. The script tag at the bottom of `index.html` is pinned to `count.v5.js` with an `integrity` hash: if GoatCounter publishes a new version, update the filename and the hash together (`curl -s https://gc.zgo.at/count.v5.js | openssl dgst -sha384 -binary | openssl base64 -A`). Localhost visits are ignored automatically.

## Regenerating icons

The PNGs in `assets/` are rendered from the SVGs beside them using macOS QuickLook:

```bash
cd assets && qlmanage -t -s 512 -o . icon.svg icon-maskable.svg && qlmanage -t -s 1200 -o . og.svg
```

Then rename the output, crop the social image to 1200×630 (`sips -c 630 1200 og-image.png`) and make the smaller sizes (`sips -Z 192 icon-512.png --out icon-192.png`, `sips -Z 180 icon-512.png --out apple-touch-icon.png`).
