// Live counters on the generated pages and the embeddable widget. Nothing here touches the
// main app's saved settings.
//
// <section class="live" data-hourly="25" data-mode="session|clock">
//   session: counts from the moment the page opened, as if you were working at that hourly rate.
//   clock:   also counts from the page open, but the rate is spread over every hour of the year
//            (for people whose earnings don't stop when they sleep); meta shows "earned so far today".
//   data-hourly="auto" (the widget) reads ?hourly= / ?annual= / &mode= / &label= / &theme= from the URL.
(() => {
    'use strict';

    const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
    const fmtWhole = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
    const HOURS_PER_YEAR = 2080;

    function splitAmount(value) {
        const total = Math.floor(value * 10000 + 1e-6);
        return { main: fmt.format(Math.floor(total / 100) / 100), sub: String(total % 100).padStart(2, '0') };
    }

    function parseMoney(text) {
        const n = parseFloat(String(text || '').replace(/,(\d{1,2})$/, '.$1').replace(/[^\d.]/g, ''));
        return Number.isFinite(n) && n > 0 ? n : 0;
    }

    // Widget configuration from the URL (only on /embed/widget/).
    function widgetConfig() {
        const q = new URLSearchParams(location.search);
        let hourly = parseMoney(q.get('hourly'));
        const annual = parseMoney(q.get('annual'));
        const mode = q.get('mode') === 'clock' ? 'clock' : 'session';
        if (!hourly && annual) hourly = mode === 'clock' ? annual / 8760 : annual / HOURS_PER_YEAR;
        if (q.get('theme') === 'light' || q.get('theme') === 'dark') document.documentElement.dataset.theme = q.get('theme');
        const label = (q.get('label') || '').slice(0, 80);
        return { hourly: Math.min(hourly, 1e9), mode, label, annual };
    }

    function startCounter(section) {
        let hourly = parseFloat(section.dataset.hourly);
        let mode = section.dataset.mode || 'session';
        if (section.dataset.hourly === 'auto') {
            const cfg = widgetConfig();
            hourly = cfg.hourly || 25;
            mode = cfg.mode;
            const labelEl = section.querySelector('[data-live="label"]');
            if (labelEl) {
                labelEl.textContent = cfg.label || (cfg.annual
                    ? `Earning ${fmtWhole.format(cfg.annual)}/yr since you opened this page`
                    : `Earning ${fmt.format(hourly)}/hr since you opened this page`);
            }
        }
        if (!(hourly > 0)) return;
        const main = section.querySelector('[data-live="main"]');
        const sub = section.querySelector('[data-live="sub"]');
        const meta = section.querySelector('[data-live="meta"]');
        let opened = Date.now();
        let lastSecond = -1;
        let rafId = 0;

        function tick() {
            const now = Date.now();
            const earned = hourly * ((now - opened) / 3600000);
            const parts = splitAmount(earned);
            main.textContent = parts.main;
            sub.textContent = parts.sub;

            const sec = Math.floor(now / 1000);
            if (sec !== lastSecond && meta) {
                lastSecond = sec;
                if (mode === 'clock') {
                    const midnight = new Date(now); midnight.setHours(0, 0, 0, 0);
                    const today = hourly * ((now - midnight.getTime()) / 3600000);
                    meta.textContent = `${fmtWhole.format(today)} so far today · ${fmt.format(hourly / 3600)} every second`;
                } else {
                    const s = Math.floor((now - opened) / 1000);
                    meta.textContent = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')} on this page · ${fmt.format(hourly / 60)} a minute`;
                }
            }
            rafId = requestAnimationFrame(tick);
        }
        function run() { cancelAnimationFrame(rafId); if (!document.hidden) tick(); }
        run();
        document.addEventListener('visibilitychange', () => { if (document.hidden) cancelAnimationFrame(rafId); else run(); });
        section.dataset.running = 'true';

        // Lets the embed configurator re-point the preview at a new rate.
        section.setRate = (h, newMode) => { hourly = h; if (newMode) mode = newMode; opened = Date.now(); lastSecond = -1; };
    }

    document.querySelectorAll('.live[data-hourly]').forEach(startCounter);

    // "They earn your yearly pay every …" comparison on person pages.
    document.querySelectorAll('[data-compare]').forEach((block) => {
        const annual = parseFloat(block.dataset.annual);
        const input = block.querySelector('[data-compare-input]');
        const out = block.querySelector('[data-compare-out]');
        const perSecond = annual / (365 * 24 * 3600);
        const match = out.textContent.match(/^(.*?) (earns|makes|spends|produces|costs) /);
        const name = match ? match[1] : out.textContent.split(' ')[0];
        const verb = match ? match[2] : 'earns';

        function duration(seconds) {
            if (seconds < 1) return `${seconds.toFixed(2)} seconds`;
            if (seconds < 60) return `${Math.round(seconds)} seconds`;
            if (seconds < 3600) return `${Math.round(seconds / 60)} minutes`;
            if (seconds < 86400) { const h = Math.floor(seconds / 3600); return `${h}h ${String(Math.round((seconds % 3600) / 60)).padStart(2, '0')}m`; }
            if (seconds < 86400 * 60) return `${(seconds / 86400).toFixed(1)} days`;
            return `${(seconds / (86400 * 30.44)).toFixed(1)} months`;
        }
        function update() {
            const yours = parseMoney(input.value);
            if (!yours) { out.textContent = 'Enter your salary to compare.'; return; }
            out.replaceChildren(`${name} ${verb} your yearly pay every `, Object.assign(document.createElement('strong'), { textContent: duration(yours / perSecond) }), '.');
        }
        input.addEventListener('input', update);
    });

    // Embed configurator on /embed/: live preview + copyable snippet.
    const form = document.querySelector('[data-embed-form]');
    if (form) {
        const rate = form.querySelector('[data-embed-rate]');
        const label = form.querySelector('[data-embed-label]');
        const dark = form.querySelector('[data-embed-dark]');
        const code = document.querySelector('[data-embed-code]');
        const preview = document.getElementById('embedPreview');
        function update() {
            const h = parseMoney(rate.value) || 25;
            const params = new URLSearchParams({ hourly: String(Math.round(h * 100) / 100) });
            if (label.value.trim()) params.set('label', label.value.trim());
            if (!dark.checked) params.set('theme', 'light');
            code.textContent = `<iframe src="https://mylivesalary.com/embed/widget/?${params}" width="100%" height="220" style="border:0;border-radius:16px" title="Live Salary counter" loading="lazy"></iframe>`;
            if (preview && preview.setRate) {
                preview.setRate(h);
                preview.querySelector('.eyebrow').textContent = label.value.trim() || `Earning ${fmt.format(h)}/hr since you opened this page`;
            }
        }
        form.addEventListener('input', update);
        form.addEventListener('submit', (e) => e.preventDefault());
        code.addEventListener('click', () => {
            const sel = window.getSelection(), range = document.createRange();
            range.selectNodeContents(code); sel.removeAllRanges(); sel.addRange(range);
            if (navigator.clipboard) navigator.clipboard.writeText(code.textContent).catch(() => {});
        });
        update();
    }
})();
