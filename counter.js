// Live counters on the wage, salary and earner pages. Nothing here touches the main app's saved settings.
//
// <section class="live" data-hourly="25" data-mode="session|clock">
//   session: counts from the moment the page opened, as if you were working at that hourly rate.
//   clock:   also counts from the page open, but the rate is spread over every hour of the year
//            (for people whose earnings don't stop when they sleep); meta shows "earned so far today".
(() => {
    'use strict';

    const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
    const fmtWhole = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });

    function splitAmount(value) {
        const total = Math.floor(value * 10000 + 1e-6);
        return { main: fmt.format(Math.floor(total / 100) / 100), sub: String(total % 100).padStart(2, '0') };
    }

    document.querySelectorAll('.live[data-hourly]').forEach((section) => {
        const hourly = parseFloat(section.dataset.hourly);
        if (!(hourly > 0)) return;
        const mode = section.dataset.mode || 'session';
        const main = section.querySelector('[data-live="main"]');
        const sub = section.querySelector('[data-live="sub"]');
        const meta = section.querySelector('[data-live="meta"]');
        const opened = Date.now();
        let lastSecond = -1;

        function tick() {
            const now = Date.now();
            const earned = hourly * ((now - opened) / 3600000);
            const parts = splitAmount(earned);
            main.textContent = parts.main;
            sub.textContent = parts.sub;

            const sec = Math.floor(now / 1000);
            if (sec !== lastSecond) {
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
            if (!document.hidden) requestAnimationFrame(tick);
        }
        tick();
        document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });
        section.dataset.running = 'true';
    });

    // "They earn your yearly pay every …" comparison on person pages.
    document.querySelectorAll('[data-compare]').forEach((block) => {
        const annual = parseFloat(block.dataset.annual);
        const input = block.querySelector('[data-compare-input]');
        const out = block.querySelector('[data-compare-out]');
        const perSecond = annual / (365 * 24 * 3600);
        const name = out.textContent.split(' earns ')[0];

        function duration(seconds) {
            if (seconds < 60) return `${Math.round(seconds)} seconds`;
            if (seconds < 3600) return `${Math.round(seconds / 60)} minutes`;
            if (seconds < 86400) { const h = Math.floor(seconds / 3600); return `${h}h ${String(Math.round((seconds % 3600) / 60)).padStart(2, '0')}m`; }
            if (seconds < 86400 * 60) return `${(seconds / 86400).toFixed(1)} days`;
            return `${(seconds / (86400 * 30.44)).toFixed(1)} months`;
        }
        function update() {
            const yours = parseFloat(input.value.replace(/[^\d.]/g, ''));
            if (!(yours > 0)) { out.textContent = 'Enter your salary to compare.'; return; }
            out.innerHTML = '';
            out.append(`${name} earns your yearly pay every `);
            const strong = document.createElement('strong');
            strong.textContent = duration(yours / perSecond);
            out.append(strong, '.');
        }
        input.addEventListener('input', update);
    });
})();
