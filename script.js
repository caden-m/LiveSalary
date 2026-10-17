(() => {
    'use strict';

    // ---------- State ----------

    const KEY = 'mls.v2';

    const DEFAULTS = {
        rateMode: 'hourly',     // 'hourly' | 'annual'
        hourly: 0,
        annual: 0,
        hoursPerWeek: 40,
        currency: guessCurrency(),
        mode: 'stopwatch',      // 'stopwatch' | 'workday'
        dayStart: '09:00',
        dayEnd: '17:00',
        theme: 'auto',          // 'auto' | 'dark' | 'light'
        privacy: false,
        accumulatedMs: 0,       // stopwatch time banked while stopped
        runningSince: null      // timestamp while the stopwatch runs, else null
    };

    const ENUMS = {
        rateMode: ['hourly', 'annual'],
        mode: ['stopwatch', 'workday'],
        theme: ['auto', 'dark', 'light']
    };

    const CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'NZD', 'JPY', 'CHF', 'INR', 'MXN', 'BRL', 'SEK', 'NOK', 'DKK', 'SGD', 'ZAR'];
    const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;
    const MAX_HOURS_PER_WEEK = 168;

    function guessCurrency() {
        const region = (Intl.DateTimeFormat().resolvedOptions().locale || 'en-US').split('-').pop();
        return { US: 'USD', GB: 'GBP', CA: 'CAD', AU: 'AUD', NZ: 'NZD', JP: 'JPY', CH: 'CHF', IN: 'INR', MX: 'MXN', BR: 'BRL', SE: 'SEK', NO: 'NOK', DK: 'DKK', SG: 'SGD', ZA: 'ZAR',
                 DE: 'EUR', FR: 'EUR', ES: 'EUR', IT: 'EUR', NL: 'EUR', IE: 'EUR', PT: 'EUR', AT: 'EUR', BE: 'EUR', FI: 'EUR' }[region] || 'USD';
    }

    const isNonNegNumber = (v) => typeof v === 'number' && Number.isFinite(v) && v >= 0;

    // Rebuilds a valid state from whatever is in storage; anything malformed falls back to its default.
    function sanitize(raw) {
        const s = { ...DEFAULTS };
        if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return s;
        for (const key of Object.keys(ENUMS)) if (ENUMS[key].includes(raw[key])) s[key] = raw[key];
        for (const key of ['hourly', 'annual', 'accumulatedMs']) if (isNonNegNumber(raw[key])) s[key] = raw[key];
        if (isNonNegNumber(raw.hoursPerWeek) && raw.hoursPerWeek > 0) s.hoursPerWeek = Math.min(raw.hoursPerWeek, MAX_HOURS_PER_WEEK);
        if (CURRENCIES.includes(raw.currency)) s.currency = raw.currency;
        if (typeof raw.dayStart === 'string' && TIME_RE.test(raw.dayStart)) s.dayStart = raw.dayStart;
        if (typeof raw.dayEnd === 'string' && TIME_RE.test(raw.dayEnd)) s.dayEnd = raw.dayEnd;
        s.privacy = raw.privacy === true;
        if (isNonNegNumber(raw.runningSince)) s.runningSince = raw.runningSince;
        return s;
    }

    function load() {
        try { return sanitize(JSON.parse(localStorage.getItem(KEY) || '{}')); }
        catch { return sanitize(null); }
    }

    function save() {
        try { localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* private mode etc. */ }
    }

    let state = load();

    // ---------- DOM ----------

    const $ = (id) => document.getElementById(id);
    const el = {
        stage: $('stage'), eyebrow: $('eyebrow'), meta: $('meta'),
        amtPre: $('amtPre'), amtMain: $('amtMain'), amtSub: $('amtSub'), amtPost: $('amtPost'),
        progress: $('progress'), progressFill: $('progressFill'),
        controls: $('controls'), startStop: $('startStopBtn'), reset: $('resetBtn'),
        emptyHint: $('emptyHint'), setRate: $('setRateBtn'),
        clock: $('clock'), date: $('date'),
        privacyBtn: $('privacyBtn'), settingsBtn: $('settingsBtn'),
        settings: $('settings'), form: $('settingsForm'),
        derived: $('derived'), currencySelect: $('currencySelect'), clearData: $('clearDataBtn'),
        statDay: $('statDay'), statWeek: $('statWeek'), statMonth: $('statMonth'), statYear: $('statYear'), statsNote: $('statsNote')
    };
    const progressBar = el.progress.querySelector('[role="progressbar"]');
    const sensitiveNodes = document.querySelectorAll('.sensitive');
    const rateInputs = [$('hourlyInput'), $('annualInput')];
    const themeColorMetas = document.querySelectorAll('meta[name="theme-color"]');
    const THEME_BG = { dark: '#0e0e10', light: '#f6f5f1' };

    // ---------- Money formatting ----------

    let fmt, fmtWhole, minorScale, symbol, decimalSymbol;

    function setupCurrency() {
        let currency = state.currency;
        try { fmt = new Intl.NumberFormat(undefined, { style: 'currency', currency }); }
        catch { currency = state.currency = 'USD'; fmt = new Intl.NumberFormat(undefined, { style: 'currency', currency }); }
        try { fmtWhole = new Intl.NumberFormat(undefined, { style: 'currency', currency, minimumFractionDigits: 0, maximumFractionDigits: 0 }); }
        catch { fmtWhole = fmt; }
        minorScale = Math.pow(10, fmt.resolvedOptions().maximumFractionDigits);
        symbol = (fmt.formatToParts(0).find(p => p.type === 'currency') || { value: currency }).value;
        decimalSymbol = (new Intl.NumberFormat(undefined).formatToParts(1.5).find(p => p.type === 'decimal') || { value: '.' }).value;
        document.querySelectorAll('[data-currency-symbol]').forEach(n => { n.textContent = symbol; });
    }

    // Truncates (never rounds up) to the currency's minor unit, so the title and counter agree.
    const truncateMinor = (value) => Math.floor(value * minorScale + 1e-9) / minorScale;

    // Splits a live amount into: prefix (symbol), main (integer + minor units),
    // sub (the next two digits beyond the minor unit, always ticking) and suffix.
    function renderAmount(value) {
        // Work in whole hundredths-of-minor-units to avoid floating-point drift in the sub digits.
        const total = Math.floor(value * minorScale * 100 + 1e-6);
        const wholeMinor = Math.floor(total / 100);
        const sub = total % 100;
        const parts = fmt.formatToParts(wholeMinor / minorScale);

        let pre = '', main = '', post = '', seenNumber = false, afterNumber = false;
        for (const p of parts) {
            const isNumber = p.type === 'integer' || p.type === 'group' || p.type === 'decimal' || p.type === 'fraction';
            if (isNumber) { seenNumber = true; main += p.value; }
            else if (!seenNumber) pre += p.value;
            else { afterNumber = true; post += p.value; }
        }
        el.amtPre.textContent = pre.trim();
        el.amtMain.textContent = main;
        el.amtSub.textContent = (minorScale === 1 ? decimalSymbol : '') + String(sub).padStart(2, '0');
        el.amtPost.textContent = afterNumber ? post.trim() : '';
    }

    // ---------- Derived values ----------

    function hourlyRate() {
        if (state.rateMode === 'annual') {
            const hoursPerYear = state.hoursPerWeek * 52;
            return hoursPerYear > 0 ? state.annual / hoursPerYear : 0;
        }
        return state.hourly;
    }

    function hasRate() { return hourlyRate() > 0; }

    function stopwatchElapsed(now) {
        return state.accumulatedMs + (state.runningSince ? Math.max(0, now - state.runningSince) : 0);
    }

    // Builds the shift that starts on the given calendar day, using local clock times so that
    // daylight-saving changes don't shift the boundaries.
    function shiftOn(dayOffset, now) {
        const [sh, sm] = state.dayStart.split(':').map(Number);
        const [eh, em] = state.dayEnd.split(':').map(Number);
        const start = new Date(now); start.setDate(start.getDate() + dayOffset); start.setHours(sh, sm, 0, 0);
        const end = new Date(start); end.setHours(eh, em, 0, 0);
        const overnight = end <= start;
        if (overnight) end.setDate(end.getDate() + 1);
        return { start: start.getTime(), end: end.getTime(), durationMs: end - start, overnight };
    }

    // Picks which shift the display should follow right now: today's once it has started;
    // otherwise yesterday's while it is still running, or (for overnight shifts) until the
    // next one starts, so "Day complete" is shown instead of resetting to zero at the end.
    function shiftWindow(now) {
        const today = shiftOn(0, now);
        if (now >= today.start) return today;
        const yesterday = shiftOn(-1, now);
        if (now < yesterday.end || yesterday.overnight) return yesterday;
        return today;
    }

    // ---------- Rendering ----------

    const pad = (n) => String(n).padStart(2, '0');

    function fmtDuration(ms, { seconds = true } = {}) {
        const s = Math.floor(ms / 1000);
        const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
        if (seconds) return `${pad(h)}:${pad(m)}:${pad(s % 60)}`;
        return h > 0 ? `${h}h ${pad(m)}m` : `${m}m`;
    }

    let lastClockSecond = -1;
    function renderClock(now) {
        const d = new Date(now);
        if (d.getSeconds() === lastClockSecond) return;
        lastClockSecond = d.getSeconds();
        el.clock.textContent = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        el.clock.setAttribute('datetime', d.toISOString());
        el.date.textContent = d.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' });
    }

    let lastTitleSecond = -1;
    function renderTitle(now, earnings, active) {
        const sec = Math.floor(now / 1000);
        if (sec === lastTitleSecond) return;
        lastTitleSecond = sec;
        document.title = active && !state.privacy ? `${fmt.format(truncateMinor(earnings))} · Live Salary` : 'Live Salary';
    }

    let lastProgressPct = -1;
    function renderProgress(worked, durationMs) {
        const pct = Math.round((worked / durationMs) * 1000) / 10;
        if (pct === lastProgressPct) return;
        lastProgressPct = pct;
        el.progressFill.style.width = pct + '%';
        progressBar.setAttribute('aria-valuenow', String(pct));
        progressBar.setAttribute('aria-valuetext', `${fmtDuration(worked, { seconds: false })} of ${fmtDuration(durationMs, { seconds: false })}`);
    }

    function render(now = Date.now()) {
        renderClock(now);
        const rate = hourlyRate();
        const ready = rate > 0;
        let earnings = 0, active = false;

        el.stage.dataset.mode = state.mode;
        el.emptyHint.hidden = ready;

        if (state.mode === 'stopwatch') {
            const elapsed = stopwatchElapsed(now);
            active = ready && !!state.runningSince;
            earnings = rate * (elapsed / 3600000);
            el.controls.hidden = !ready;
            el.progress.hidden = true;
            el.eyebrow.textContent = active ? 'Earning now' : elapsed > 0 ? 'Paused' : ready ? 'Ready' : 'Live Salary';
            el.meta.textContent = ready ? `${fmtDuration(elapsed)} · ${fmt.format(rate)}/hr` : 'Earnings, second by second';
            el.startStop.textContent = active ? 'Stop' : elapsed > 0 ? 'Resume' : 'Start';
        } else {
            const { start, end, durationMs } = shiftWindow(now);
            const worked = Math.min(Math.max(now - start, 0), durationMs);
            active = ready && now >= start && now < end;
            earnings = rate * (worked / 3600000);
            el.controls.hidden = true;
            el.progress.hidden = !ready;
            renderProgress(worked, durationMs);
            const range = `${state.dayStart}–${state.dayEnd}`;
            if (!ready) { el.eyebrow.textContent = 'Live Salary'; el.meta.textContent = 'Earnings, second by second'; }
            else if (now < start) { el.eyebrow.textContent = 'Workday'; el.meta.textContent = `${range} · starts in ${fmtDuration(start - now, { seconds: false })}`; }
            else if (now >= end) { el.eyebrow.textContent = 'Day complete'; el.meta.textContent = `${range} · ${fmtDuration(durationMs, { seconds: false })} worked`; }
            else { el.eyebrow.textContent = 'Earned today'; el.meta.textContent = `${range} · ${fmtDuration(end - now, { seconds: false })} left`; }
        }

        el.stage.dataset.running = String(active);
        renderAmount(earnings);
        renderTitle(now, earnings, active);
        pulseMilestones(earnings, active, rate);
    }

    // ---------- Milestone pulses ----------

    // Pulses the glow each time the amount crosses a milestone. The step is the power of ten
    // that keeps pulses at least ~20 seconds apart (1 at $50/hr, 10 at ¥3,000/hr, …);
    // crossing 100× that step gives a bigger pulse.
    let lastMilestone = null, pulseTimer = 0;
    function milestoneStep(rate) {
        if (!(rate > 0)) return 1;
        return Math.max(1, Math.pow(10, Math.ceil(Math.log10(rate * 20 / 3600))));
    }
    function pulseMilestones(earnings, active, rate) {
        const step = milestoneStep(rate);
        const milestone = Math.floor(earnings / step);
        if (lastMilestone === null || !active) { lastMilestone = milestone; return; }
        if (milestone > lastMilestone) {
            const big = Math.floor(milestone / 100) > Math.floor(lastMilestone / 100);
            el.stage.classList.remove('pulse', 'pulse-big');
            void el.stage.offsetWidth; // restart the animation if one is mid-flight
            el.stage.classList.add(big ? 'pulse-big' : 'pulse');
            clearTimeout(pulseTimer);
            pulseTimer = setTimeout(() => el.stage.classList.remove('pulse', 'pulse-big'), 1600);
        }
        lastMilestone = milestone;
    }

    function renderStats() {
        const rate = hourlyRate();
        const week = rate * state.hoursPerWeek, year = week * 52;
        const show = rate > 0;
        el.statDay.textContent = show ? fmtWhole.format(week / 5) : '—';
        el.statWeek.textContent = show ? fmtWhole.format(week) : '—';
        el.statMonth.textContent = show ? fmtWhole.format(year / 12) : '—';
        el.statYear.textContent = show ? fmtWhole.format(year) : '—';
        el.statsNote.textContent = show ? `at ${fmt.format(rate)}/hr · ${state.hoursPerWeek}h per week` : 'Projections appear once you set a rate';
    }

    function renderDerived() {
        const rate = hourlyRate();
        if (!(rate > 0)) { el.derived.textContent = ''; return; }
        el.derived.textContent = state.rateMode === 'annual'
            ? `≈ ${fmt.format(rate)} per hour`
            : `≈ ${fmtWhole.format(rate * state.hoursPerWeek * 52)} per year`;
    }

    function applyTheme() {
        const forced = state.theme === 'dark' || state.theme === 'light';
        if (forced) document.documentElement.dataset.theme = state.theme;
        else delete document.documentElement.dataset.theme;
        // Keep the browser chrome colour in step with a manually chosen theme.
        themeColorMetas.forEach(meta => {
            const scheme = (meta.media || '').includes('light') ? 'light' : 'dark';
            meta.content = THEME_BG[forced ? state.theme : scheme];
        });
    }

    // Privacy mode blurs the numbers, hides them from assistive tech and text selection,
    // and masks the rate fields. The values are still in memory and in storage.
    function applyPrivacy() {
        document.body.classList.toggle('privacy', state.privacy);
        el.privacyBtn.setAttribute('aria-pressed', String(state.privacy));
        sensitiveNodes.forEach(n => { if (state.privacy) n.setAttribute('aria-hidden', 'true'); else n.removeAttribute('aria-hidden'); });
        rateInputs.forEach(input => { input.type = state.privacy ? 'password' : 'text'; });
        lastTitleSecond = -1;
    }

    // Shows/hides settings rows tagged data-show="key:value".
    function applyConditionals() {
        document.querySelectorAll('[data-show]').forEach(node => {
            const [key, value] = node.dataset.show.split(':');
            node.hidden = String(state[key]) !== value;
        });
    }

    function refreshAll() {
        setupCurrency();
        applyTheme();
        applyPrivacy();
        applyConditionals();
        renderDerived();
        renderStats();
        lastClockSecond = -1; lastTitleSecond = -1; lastMilestone = null; lastProgressPct = -1;
        render();
    }

    // ---------- Animation loop ----------

    let rafId = 0;
    function loop() {
        render();
        rafId = requestAnimationFrame(loop);
    }
    function startLoop() {
        cancelAnimationFrame(rafId);
        if (!document.hidden) rafId = requestAnimationFrame(loop);
    }
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) cancelAnimationFrame(rafId); else { lastClockSecond = -1; startLoop(); }
    });
    // Background tabs don't get animation frames; keep the clock and title fresh once a second.
    setInterval(() => { if (document.hidden) render(); }, 1000);

    // ---------- Actions ----------

    function bankStopwatch(now = Date.now()) {
        if (!state.runningSince) return;
        state.accumulatedMs += Math.max(0, now - state.runningSince);
        state.runningSince = null;
    }

    function toggleStopwatch() {
        if (!hasRate()) { openSettings(true); return; }
        const now = Date.now();
        if (state.runningSince) bankStopwatch(now); else state.runningSince = now;
        save();
        render(now);
    }

    let resetArmed = 0;
    function resetStopwatch() {
        if (stopwatchElapsed(Date.now()) === 0) return;
        if (!resetArmed) {
            // First press arms; second press within 3s confirms.
            el.reset.textContent = 'Sure?';
            el.reset.classList.add('armed');
            resetArmed = setTimeout(disarmReset, 3000);
            return;
        }
        disarmReset();
        state.accumulatedMs = 0;
        state.runningSince = null;
        save();
        render();
    }
    function disarmReset() {
        clearTimeout(resetArmed);
        resetArmed = 0;
        el.reset.textContent = 'Reset';
        el.reset.classList.remove('armed');
    }

    function togglePrivacy() {
        state.privacy = !state.privacy;
        save();
        applyPrivacy();
        render();
    }

    function openSettings(focusRate = false) {
        if (el.settings.open) return;
        el.settings.showModal();
        if (focusRate) {
            const input = state.rateMode === 'annual' ? $('annualInput') : $('hourlyInput');
            input.focus();
            input.select();
        }
    }

    // ---------- Settings form ----------

    function populateCurrencies() {
        let names = null;
        try { names = new Intl.DisplayNames(undefined, { type: 'currency' }); } catch { /* unsupported */ }
        el.currencySelect.replaceChildren(...CURRENCIES.map(code => {
            const opt = document.createElement('option');
            opt.value = code;
            opt.textContent = names ? `${code} — ${names.of(code)}` : code;
            return opt;
        }));
    }

    // Accepts "12.50", "12,50" (comma as decimal) and "85,000" (comma as thousands separator).
    function parseAmount(text) {
        const normalized = text.replace(/,(\d{1,2})$/, '.$1').replace(/[^\d.]/g, '');
        const n = parseFloat(normalized);
        return Number.isFinite(n) && n >= 0 ? n : 0;
    }

    function formToState() {
        const prevMode = state.mode;
        el.form.querySelectorAll('[data-key]').forEach(input => {
            const key = input.dataset.key;
            if (input.type === 'radio') { if (input.checked) state[key] = input.value; return; }
            if (input.dataset.type === 'number') { state[key] = parseAmount(input.value); return; }
            if (input.type === 'time') { if (TIME_RE.test(input.value)) state[key] = input.value; return; } // keep the last valid value while editing
            state[key] = input.value;
        });
        // An empty or absurd hours field means "default", not zero.
        if (!(state.hoursPerWeek > 0)) state.hoursPerWeek = DEFAULTS.hoursPerWeek;
        state.hoursPerWeek = Math.min(state.hoursPerWeek, MAX_HOURS_PER_WEEK);
        // Leaving stopwatch mode banks any running time so it can't keep counting invisibly.
        if (prevMode === 'stopwatch' && state.mode !== 'stopwatch') bankStopwatch();
    }

    function stateToForm() {
        el.form.querySelectorAll('[data-key]').forEach(input => {
            const key = input.dataset.key;
            if (input.type === 'radio') { input.checked = input.value === String(state[key]); return; }
            if (input.dataset.type === 'number') { input.value = state[key] > 0 ? String(state[key]) : ''; return; }
            input.value = state[key];
        });
    }

    function onFormInput(e) {
        const input = e.target;
        if (input.dataset.type === 'number' && input.type !== 'password') {
            // Digits, one decimal point, and a comma that may act as the decimal separator.
            const cleaned = input.value.replace(/[^\d.,]/g, '').replace(/^(\d*[.,]\d*).*$/, '$1');
            if (cleaned !== input.value) {
                const pos = Math.max(0, (input.selectionStart || 0) - (input.value.length - cleaned.length));
                input.value = cleaned;
                input.setSelectionRange(pos, pos);
            }
        }
        formToState();
        save();
        refreshAll();
    }

    function clearData() {
        if (!confirm('Clear your saved rate, settings and timer?')) return;
        try { localStorage.removeItem(KEY); } catch { /* ignore */ }
        state = sanitize(null);
        stateToForm();
        refreshAll();
    }

    // ---------- Keyboard ----------

    function onKey(e) {
        if (e.metaKey || e.ctrlKey || e.altKey || e.repeat || el.settings.open) return;
        // Let focused controls handle their own keys (Space/Enter on a button, typing in a field).
        if (e.target instanceof Element && e.target.closest('button, a, input, select, textarea, [contenteditable]')) return;
        switch (e.key) {
            case ' ':
                if (state.mode === 'stopwatch') { e.preventDefault(); toggleStopwatch(); }
                break;
            case 'r': case 'R': if (state.mode === 'stopwatch') resetStopwatch(); break;
            case 'p': case 'P': togglePrivacy(); break;
            case 's': case 'S': case ',': openSettings(); break;
        }
    }

    // ---------- Wire up ----------

    el.startStop.addEventListener('click', toggleStopwatch);
    el.reset.addEventListener('click', resetStopwatch);
    el.privacyBtn.addEventListener('click', togglePrivacy);
    el.settingsBtn.addEventListener('click', () => openSettings());
    el.setRate.addEventListener('click', () => openSettings(true));
    el.clearData.addEventListener('click', clearData);
    el.form.addEventListener('input', onFormInput);
    el.form.addEventListener('change', onFormInput);
    el.settings.addEventListener('click', (e) => { if (e.target === el.settings) el.settings.close(); }); // backdrop click
    el.settings.addEventListener('close', () => { formToState(); save(); stateToForm(); refreshAll(); });
    document.addEventListener('keydown', onKey);
    window.addEventListener('storage', (e) => { if (e.key === KEY || e.key === null) { state = load(); stateToForm(); refreshAll(); } });

    populateCurrencies();
    stateToForm();
    refreshAll();
    startLoop();

    // Offline support and "Add to Home Screen" (only available on https or localhost).
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => { navigator.serviceWorker.register('sw.js').catch(() => {}); });
    }
})();
