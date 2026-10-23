#!/usr/bin/env python3
"""Generates every static page except the home page, plus the sitemaps.

    python3 build/generate.py

Reads build/data/*.json and writes into hourly/, salary/, monthly/, biweekly/, earns/, about/,
methodology/, privacy/, contact/, embed/ and sitemaps/ at the repo root, overwriting what is there.
Only the Python standard library is used. Tax and wage assumptions live at the top of this file.
"""

import json
import math
import os
import shutil
from datetime import date
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "build", "data")
SITE = "https://mylivesalary.com"
TODAY = date.today().isoformat()
CONTACT_EMAIL = None  # e.g. "hello@mylivesalary.com"; shown on the contact page when set
REPO_URL = "https://github.com/caden-m/LiveSalary"

# ---------- Assumptions (kept in one place so the copy and the maths agree) ----------

HOURS_PER_WEEK = 40
WEEKS_PER_YEAR = 52
HOURS_PER_YEAR = HOURS_PER_WEEK * WEEKS_PER_YEAR          # 2,080
FEDERAL_MIN_WAGE = 7.25
US_MEDIAN_WEEKLY = 1251                                   # BLS, full-time median usual weekly earnings, Q2 2026 (series LEU0252881500)
US_MEDIAN_WEEKLY_LABEL = "Q2 2026"
US_MEDIAN_ANNUAL = US_MEDIAN_WEEKLY * WEEKS_PER_YEAR      # 65,052
US_MEDIAN_HOURLY = US_MEDIAN_ANNUAL / HOURS_PER_YEAR      # ~31.27
LIVING_WAGE_SINGLE = 25.0                                 # Rough mid-point of MIT Living Wage Calculator state estimates for one adult, no children (MIT publishes no national figure)
US_MEDIAN_HOUSEHOLD_INCOME = 81604                        # Census ACS 2024 1-year, US (ACSBR-025)
US_MEDIAN_HOUSEHOLD_LABEL = "ACS 2024"

# 2025 federal income tax, single filer. Rough take-home only: no credits, no 401(k), no health premiums.
STANDARD_DEDUCTION = 15750                                # 2025, after the July 2025 law (P.L. 119-21) raised it from $15,000
BRACKETS = [(11925, 0.10), (48475, 0.12), (103350, 0.22), (197300, 0.24), (250525, 0.32), (626350, 0.35), (math.inf, 0.37)]
SS_RATE, SS_CAP = 0.062, 176100
MEDICARE_RATE, MEDICARE_EXTRA_FROM = 0.0145, 200000

# Everyday price points used for "how long does it take to earn…" (rounded national figures, 2025)
PRICES = [("a $5 coffee", 5), ("a $15 lunch", 15), ("a $120 pair of sneakers", 120), ("a $999 phone", 999), ("$1,600 in rent", 1600)]
TYPICAL_RENT = 1600           # national median asking rent, roughly
TYPICAL_GROCERIES = 450       # single adult, monthly, roughly


def bracket_tax(taxable, brackets):
    tax, lower = 0.0, 0
    for upper, rate in brackets:
        upper = math.inf if upper is None else upper
        if taxable <= lower:
            break
        tax += (min(taxable, upper) - lower) * rate
        lower = upper
    return tax


def federal_tax(gross):
    tax = bracket_tax(max(0, gross - STANDARD_DEDUCTION), BRACKETS)
    fica = min(gross, SS_CAP) * SS_RATE + gross * MEDICARE_RATE + max(0, gross - MEDICARE_EXTRA_FROM) * 0.009
    return tax, fica


def take_home(gross, state=None):
    """Returns (net, federal, fica, state_tax)."""
    tax, fica = federal_tax(gross)
    st = state_tax(gross, state) if state else 0.0
    return gross - tax - fica - st, tax, fica, st


def state_tax(gross, state):
    if state["tax_type"] == "none":
        return 0.0
    taxable = max(0, gross - state.get("standard_deduction_single", 0))
    return bracket_tax(taxable, [(b[0], b[1]) for b in state["brackets_single"]])


# ---------- Formatting ----------

def money(v, cents=False):
    if cents:
        return f"${v:,.2f}"
    return f"${round(v):,}"


def rate_text(h):
    return f"${h:,.2f}" if h != int(h) else f"${int(h):,}"


def slug_for_rate(h):
    return str(int(h)) if h == int(h) else f"{h:.2f}".rstrip("0").replace(".", "-")


def pct(x):
    return f"{x * 100:.0f}%"


def duration(seconds):
    seconds = max(0, seconds)
    if seconds < 1:
        return f"{seconds:.2f} seconds"
    if seconds < 60:
        return f"{seconds:.0f} seconds"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.0f} minute{'s' if round(minutes) != 1 else ''}"
    hours = minutes / 60
    if hours < 24:
        h, m = int(hours), round((hours - int(hours)) * 60)
        return f"{h}h {m:02d}m"
    days = hours / 24
    if days < 60:
        return f"{days:.1f} days"
    return f"{days / 30.44:.1f} months"


def short_money(v):
    if v >= 1e9:
        return f"${v / 1e9:.1f}B"
    if v >= 1e6:
        return f"${v / 1e6:.1f}M".replace(".0M", "M")
    if v >= 1e3:
        return f"${v / 1e3:.0f}k"
    return f"${v:,.0f}"


# ---------- Page shell ----------

CSP = ("default-src 'none'; script-src 'self' https://gc.zgo.at; style-src 'self'; font-src 'self'; img-src 'self' "
       "https://cadenlivesalary.goatcounter.com; manifest-src 'self'; worker-src 'self'; connect-src 'self' "
       "https://cadenlivesalary.goatcounter.com; base-uri 'none'; object-src 'none'; form-action 'self'")

GOATCOUNTER = ('<script data-goatcounter="https://cadenlivesalary.goatcounter.com/count" async src="https://gc.zgo.at/count.v5.js" '
               'integrity="sha384-atnOLvQb9t+jTSipvd75X2yginT4PjVbqDdlJAmxMm+wYElFmeR6EmLP5bYeoRVQ" crossorigin="anonymous"></script>')

FOOT_NAV = ('<a href="/hourly/">Hourly wages</a> · <a href="/salary/">Salaries</a> · <a href="/monthly/">Monthly pay</a> · '
            '<a href="/biweekly/">Biweekly pay</a> · <a href="/earns/">Who earns what</a> · <a href="/embed/">Embed</a> · '
            '<a href="/about/">About</a> · <a href="/methodology/">Methodology</a> · <a href="/privacy/">Privacy</a> · <a href="/contact/">Contact</a>')


def shell(*, path, title, description, body, breadcrumbs, json_ld=None, bare=False, extra_head="", og=None):
    url = f"{SITE}{path}"
    og_url = f"{SITE}/assets/og/{og}.png" if og else f"{SITE}/assets/og-image.png"
    ld_blocks = []
    if breadcrumbs:
        ld_blocks.append({
            "@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": f"{SITE}{p}"} for i, (n, p) in enumerate(breadcrumbs)]
        })
    if json_ld:
        ld_blocks.append(json_ld)
    ld_html = "\n    ".join(f'<script type="application/ld+json">{json.dumps(b, ensure_ascii=False)}</script>' for b in ld_blocks)
    crumbs_html = " <span class=\"sep\">/</span> ".join(
        f'<a href="{escape(p)}">{escape(n)}</a>' if i < len(breadcrumbs) - 1 else f"<span>{escape(n)}</span>"
        for i, (n, p) in enumerate(breadcrumbs))
    header = "" if bare else f"""
    <header class="page-top">
        <a class="brand" href="/">Live Salary</a>
        <nav class="crumbs" aria-label="Breadcrumb">{crumbs_html}</nav>
    </header>"""
    footer = "" if bare else f"""
    <footer class="page-foot">
        <nav aria-label="Site">{FOOT_NAV}</nav>
        <p>Figures are estimates for a single filer based on {HOURS_PER_WEEK} hours a week, {WEEKS_PER_YEAR} weeks a year — see the <a href="/methodology/">methodology</a>. Not tax or financial advice. Updated {TODAY}.</p>
    </footer>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta http-equiv="Content-Security-Policy" content="{CSP}">
    <meta name="referrer" content="no-referrer">
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
    <title>{escape(title)}</title>
    <meta name="description" content="{escape(description)}">
    <link rel="canonical" href="{url}">
    <meta name="theme-color" content="#0e0e10" media="(prefers-color-scheme: dark)">
    <meta name="theme-color" content="#f6f5f1" media="(prefers-color-scheme: light)">
    <meta property="og:type" content="website">
    <meta property="og:title" content="{escape(title)}">
    <meta property="og:description" content="{escape(description)}">
    <meta property="og:url" content="{url}">
    <meta property="og:image" content="{og_url}">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:image" content="{og_url}">
    <link rel="icon" href="/assets/icon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
    <link rel="stylesheet" href="/styles.css">
    <link rel="stylesheet" href="/pages.css">
    <script src="/theme.js"></script>
    {ld_html}{extra_head}
</head>
<body class="page{' bare' if bare else ''}">{header}
    <main class="page-main">
{body}
    </main>{footer}
    <script src="/counter.js"></script>
    {GOATCOUNTER}
</body>
</html>
"""


# ---------- Social preview cards ----------
# Each base page gets a 1200×630 card. The generator writes SVGs to build/og/; build/render_og.sh
# turns new or changed ones into assets/og/<slug>.png with macOS QuickLook. State pages reuse
# their parent wage's card.

OG_CARDS = {}


def og_card(slug, kicker, big, small, foot="mylivesalary.com"):
    big_size = max(56, min(190, int(1040 / (0.62 * max(len(big), 1)))))
    small_size = max(24, min(40, int(1080 / (0.52 * max(len(small), 1)))))
    OG_CARDS[slug] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="#0e0e10"/>
  <circle cx="600" cy="340" r="300" fill="#9fe8b8" opacity="0.10"/>
  <circle cx="600" cy="340" r="200" fill="#9fe8b8" opacity="0.08"/>
  <text x="600" y="150" text-anchor="middle" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="24" letter-spacing="7" fill="#9fe8b8">{escape(kicker.upper())}</text>
  <text x="600" y="{340 + big_size * 0.35:.0f}" text-anchor="middle" font-family="Menlo, monospace" font-size="{big_size}" fill="#f2f2ef">{escape(big)}</text>
  <text x="600" y="490" text-anchor="middle" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="{small_size}" fill="#9a9a97">{escape(small)}</text>
  <text x="600" y="572" text-anchor="middle" font-family="Menlo, monospace" font-size="24" fill="#5c5c5a">{escape(foot)}</text>
</svg>
"""
    return slug


def write_og_cards():
    out = os.path.join(ROOT, "build", "og")
    os.makedirs(out, exist_ok=True)
    for slug, svg in OG_CARDS.items():
        p = os.path.join(out, f"{slug}.svg")
        old = open(p).read() if os.path.exists(p) else None
        if old != svg:
            with open(p, "w", encoding="utf-8") as f:
                f.write(svg)
    return len(OG_CARDS)


def write(path, html):
    out = os.path.join(ROOT, path.strip("/"), "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)


# ---------- Shared fragments ----------

def counter_block(hourly, *, label, mode="session"):
    """The live counter, preloaded with a rate. counter.js reads the data attributes."""
    return f"""
        <section class="live" data-hourly="{hourly:.6f}" data-mode="{mode}">
            <p class="eyebrow">{escape(label)}</p>
            <div class="live-amount" aria-live="off"><span class="live-main" data-live="main">$0.00</span><span class="live-sub" data-live="sub">00</span></div>
            <p class="live-meta" data-live="meta"></p>
            <p class="live-cta"><a class="btn primary" href="/">Track your own salary live →</a></p>
        </section>"""


def breakdown_table(hourly, state=None):
    annual = hourly * HOURS_PER_YEAR
    net, tax, fica, st = take_home(annual, state)
    periods = [("Per year", 1), ("Per month", 12), ("Every two weeks", 26), ("Per week", 52), ("Per day (8 hours)", 260), ("Per hour", HOURS_PER_YEAR)]
    rows = "\n".join(
        f"<tr><th scope=\"row\">{p}</th><td>{money(annual / d, cents=annual / d < 100)}</td><td>{money(net / d, cents=net / d < 100)}</td></tr>"
        for p, d in periods)
    where = f" in {state['name']}" if state else ""
    taxes = f"federal income tax ({money(tax)}), Social Security and Medicare ({money(fica)})"
    if state:
        taxes += f" and {state['name']} income tax ({money(st)})" if st > 0 else f"; {state['name']} has no state income tax on wages"
    return f"""
        <table class="grid">
            <thead><tr><th scope="col">Period</th><th scope="col">Before tax</th><th scope="col">After tax*</th></tr></thead>
            <tbody>
{rows}
            </tbody>
        </table>
        <p class="fine">*Estimate for a single filer in 2025 taking the standard deduction{where}: {taxes} — about {money(tax + fica + st)} a year, an effective rate of {pct((tax + fica + st) / annual) if annual else '0%'}. {'Local income taxes, ' if state and state.get('local_income_tax') else ''}Health insurance, retirement contributions and credits would change it. <a href="/methodology/">How this is calculated.</a></p>"""


def hours_table(hourly):
    rows = "\n".join(
        f"<tr><th scope=\"row\">{h} hours a week</th><td>{money(hourly * h * WEEKS_PER_YEAR)}</td><td>{money(hourly * h * WEEKS_PER_YEAR / 12)}</td></tr>"
        for h in (20, 25, 30, 35, 40, 45, 50))
    return f"""
        <table class="grid">
            <thead><tr><th scope="col">Schedule</th><th scope="col">Per year</th><th scope="col">Per month</th></tr></thead>
            <tbody>
{rows}
            </tbody>
        </table>"""


def time_to_earn_list(hourly):
    per_second = hourly / 3600
    items = "\n".join(f"<li><strong>{duration(price / per_second)}</strong> to earn {name}</li>" for name, price in PRICES)
    return f"<ul class=\"ticks\">\n{items}\n</ul>"


def context_paragraph(hourly):
    vs_min = hourly / FEDERAL_MIN_WAGE
    vs_med = hourly / US_MEDIAN_HOURLY
    med = (f"{(vs_med - 1) * 100:.0f}% above" if vs_med >= 1.02 else f"{(1 - vs_med) * 100:.0f}% below" if vs_med <= 0.98 else "right at")
    return (f"<p>{rate_text(hourly)} an hour is <strong>{vs_min:.1f}×</strong> the federal minimum wage of ${FEDERAL_MIN_WAGE} and "
            f"<strong>{med}</strong> the median full-time US wage of about ${US_MEDIAN_HOURLY:.2f} an hour "
            f"({money(US_MEDIAN_ANNUAL)} a year).</p>")


def is_it_good_section(hourly, occupations, *, label=None):
    """Answers the question behind the search: is this pay good, what jobs pay it, what does the budget feel like."""
    label = label or f"{rate_text(hourly)} an hour"
    annual = hourly * HOURS_PER_YEAR
    net, *_ = take_home(annual)
    net_month = net / 12
    ratio = hourly / US_MEDIAN_HOURLY
    if hourly < FEDERAL_MIN_WAGE:
        verdict = "below the federal minimum wage, so it's only legal in limited cases such as tipped work, some students and trainees"
    elif ratio < 0.6:
        verdict = "well below the US median — a typical entry-level or part-time wage"
    elif ratio < 0.9:
        verdict = "below the US median, in the range of many service, retail and early-career jobs"
    elif ratio < 1.1:
        verdict = "right around the US median full-time wage"
    elif ratio < 1.5:
        verdict = "comfortably above the US median — typical of skilled trades and experienced professionals"
    elif ratio < 3:
        verdict = "well above the US median, in the range of senior professionals and many managers"
    else:
        verdict = "far above the US median — top-percentile pay"
    living = ("above" if hourly >= LIVING_WAGE_SINGLE * 1.02 else "below" if hourly <= LIVING_WAGE_SINGLE * 0.98 else "right at")
    rent_share = TYPICAL_RENT / net_month if net_month > 0 else math.inf
    if rent_share > 1:
        rent_line = f"a typical {money(TYPICAL_RENT)} rent is more than the whole month's take-home, so this wage alone can't cover a one-bedroom at national prices."
    elif rent_share > 0.5:
        rent_line = f"a typical {money(TYPICAL_RENT)} rent would take about {pct(rent_share)} of take-home — far above the 30% most budgets aim for, so roommates, a cheaper area or a second income are usually part of the picture."
    elif rent_share > 0.3:
        rent_line = f"a typical {money(TYPICAL_RENT)} rent would take about {pct(rent_share)} of take-home — above the 30% guideline, workable with a careful budget."
    else:
        rent_line = f"a typical {money(TYPICAL_RENT)} rent would take about {pct(rent_share)} of take-home, under the 30% guideline, leaving room to save."
    left = net_month - TYPICAL_RENT - TYPICAL_GROCERIES
    left_line = (f"After rent and about {money(TYPICAL_GROCERIES)} of groceries, roughly <strong>{money(left)}</strong> a month is left for everything else: transport, insurance, phone, debt, savings."
                 if left > 0 else "After rent and groceries there is nothing left at national prices; the numbers only work with lower housing costs or additional income.")

    # Jobs that pay about this much (median), from the occupations data.
    near = sorted(occupations, key=lambda o: abs(o["annual"] / HOURS_PER_YEAR - hourly))
    close = [o for o in near if abs(o["annual"] / HOURS_PER_YEAR - hourly) / hourly <= 0.15][:4] or near[:3]
    jobs = ", ".join(f'<a href="/earns/{o["slug"]}/">{o["plural"]}</a> ({money(o["annual"] / HOURS_PER_YEAR, cents=True)}/hr)' for o in close)
    jobs_intro = "Jobs whose median pay is close to this" if close is not near[:3] or abs(close[0]["annual"] / HOURS_PER_YEAR - hourly) / hourly <= 0.15 else "The nearest everyday jobs by median pay"

    return f"""
        <h2>Is {label} good?</h2>
        <p>{label.capitalize()} is <strong>{verdict}</strong>. It's {living} the roughly ${LIVING_WAGE_SINGLE:.0f} an hour that a single adult with no children typically needs to cover basic costs in the US, going by MIT's Living Wage Calculator state estimates (which run from the low $20s to over $30 in expensive states).</p>
        <p>In practice it means about <strong>{money(net_month)} a month</strong> after federal taxes. At that level {rent_line} {left_line}</p>
        <p>{jobs_intro}: {jobs}.</p>"""


def neighbours(values, current, fmt, hub, count=6):
    idx = values.index(current)
    near = values[max(0, idx - count // 2): idx] + values[idx + 1: idx + 1 + count // 2]
    return "".join(f'<a href="{hub}{fmt(v)[1]}/">{fmt(v)[0]}</a>' for v in near)


def state_links(base_path, states):
    if not states:
        return ""
    chips = "".join(f'<a href="{base_path}{s["slug"]}/">{escape(s["name"])}</a>' for s in states)
    return f"""
        <h2>After taxes in your state</h2>
        <p>State income tax ranges from nothing to over 10%. Pick a state for the full take-home picture:</p>
        <nav class="chips">{chips}</nav>"""


def webpage_ld(title, description, path):
    return {"@context": "https://schema.org", "@type": "WebPage", "name": title, "description": description, "url": SITE + path,
            "isPartOf": {"@type": "WebSite", "name": "Live Salary", "url": SITE + "/"}, "dateModified": TODAY}


# ---------- Hourly pages ----------

def hourly_page(h, all_hourly, annual_values, occupations, states):
    annual = h * HOURS_PER_YEAR
    path = f"/hourly/{slug_for_rate(h)}/"
    title = f"{rate_text(h)} an Hour Is How Much a Year? {money(annual)} | Live Salary"
    net, *_ = take_home(annual)
    description = (f"{rate_text(h)} an hour is {money(annual)} a year before tax (about {money(net)} after federal tax), "
                   f"{money(annual / 12)} a month or {money(h * HOURS_PER_WEEK)} a week. Is it good? What jobs pay it? Plus a live counter.")
    closest_salary = min(annual_values, key=lambda a: abs(a - annual))
    body = f"""
        <h1>{rate_text(h)} an hour is <span class="hl">{money(annual)}</span> a year</h1>
        <p class="lede">Working {HOURS_PER_WEEK} hours a week, {WEEKS_PER_YEAR} weeks a year — that's {money(annual / 12)} a month before tax, or roughly <strong>{money(net)}</strong> a year after federal taxes.</p>
{counter_block(h, label=f"Earning {rate_text(h)}/hr since you opened this page")}
        <h2>{rate_text(h)} an hour, broken down</h2>
{breakdown_table(h)}
{is_it_good_section(h, occupations)}
        <h2>How it compares</h2>
{context_paragraph(h)}
        <h2>Fewer or more hours</h2>
        <p>Not everyone works 40 hours. Here's the same {rate_text(h)} an hour on other schedules:</p>
{hours_table(h)}
        <h2>How long does it take to earn…</h2>
        <p>At {rate_text(h)} an hour you earn about <strong>{money(h / 60, cents=True)} a minute</strong>, so it takes:</p>
{time_to_earn_list(h)}
{state_links(path, states)}
        <h2>Nearby wages</h2>
        <nav class="chips">{neighbours(all_hourly, h, lambda v: (rate_text(v) + "/hr", slug_for_rate(v)), "/hourly/")}</nav>
        <p>Or flip it around: <a href="/salary/{closest_salary}/">{money(closest_salary)} a year is how much an hour?</a></p>
"""
    og = og_card(f"hourly-{slug_for_rate(h)}", "Hourly wage", f"{rate_text(h)}/hr = {money(annual)}/yr",
                 f"{money(annual / 12)} a month · about {money(net)} a year after federal tax")
    write(path, shell(path=path, title=title, description=description, body=body, json_ld=webpage_ld(title, description, path), og=og,
                      breadcrumbs=[("Live Salary", "/"), ("Hourly wages", "/hourly/"), (f"{rate_text(h)} an hour", path)]))
    return path


# ---------- Salary pages ----------

def salary_page(a, all_annual, hourly_values, occupations, states):
    h = a / HOURS_PER_YEAR
    path = f"/salary/{a}/"
    title = f"{money(a)} a Year Is How Much an Hour? {money(h, cents=True)} | Live Salary"
    net, *_ = take_home(a)
    description = (f"{money(a)} a year is {money(h, cents=True)} an hour at {HOURS_PER_WEEK} hours a week — {money(a / 12)} a month, "
                   f"{money(a / 26)} every two weeks, about {money(net)} after federal tax. Is it a good salary? See it add up live.")
    closest_hourly = min(hourly_values, key=lambda v: abs(v - h))
    body = f"""
        <h1>{money(a)} a year is <span class="hl">{money(h, cents=True)}</span> an hour</h1>
        <p class="lede">Based on a {HOURS_PER_WEEK}-hour week for {WEEKS_PER_YEAR} weeks ({HOURS_PER_YEAR:,} working hours). That's {money(a / 12)} a month before tax, or about <strong>{money(net / 12)}</strong> a month after federal taxes.</p>
{counter_block(h, label=f"Earning {money(a)}/yr since you opened this page")}
        <h2>{money(a)} a year, broken down</h2>
{breakdown_table(h)}
{is_it_good_section(h, occupations, label=f"{money(a)} a year")}
        <h2>How it compares</h2>
{context_paragraph(h)}
        <h2>If you work different hours</h2>
        <p>A {money(a)} salary spread over fewer or more hours changes the effective hourly rate:</p>
        <table class="grid">
            <thead><tr><th scope="col">Schedule</th><th scope="col">Effective hourly rate</th></tr></thead>
            <tbody>
{chr(10).join(f'<tr><th scope="row">{hw} hours a week</th><td>{money(a / (hw * WEEKS_PER_YEAR), cents=True)}</td></tr>' for hw in (30, 35, 40, 45, 50, 60))}
            </tbody>
        </table>
        <h2>How long does it take to earn…</h2>
        <p>On {money(a)} a year you earn about <strong>{money(h / 60, cents=True)} a minute</strong> while working, so it takes:</p>
{time_to_earn_list(h)}
{state_links(path, states)}
        <h2>Nearby salaries</h2>
        <nav class="chips">{neighbours(all_annual, a, lambda v: (money(v), str(v)), "/salary/")}</nav>
        <p>Or flip it around: <a href="/hourly/{slug_for_rate(closest_hourly)}/">{rate_text(closest_hourly)} an hour is how much a year?</a></p>
"""
    og = og_card(f"salary-{a}", "Annual salary", f"{money(a)}/yr = {money(h, cents=True)}/hr",
                 f"{money(a / 12)} a month · about {money(net)} a year after federal tax")
    write(path, shell(path=path, title=title, description=description, body=body, json_ld=webpage_ld(title, description, path), og=og,
                      breadcrumbs=[("Live Salary", "/"), ("Salaries", "/salary/"), (f"{money(a)} a year", path)]))
    return path


# ---------- Monthly and biweekly pages ----------

def period_page(amount, kind, all_values, annual_values, occupations):
    per_year = 12 if kind == "monthly" else 26
    annual = amount * per_year
    h = annual / HOURS_PER_YEAR
    noun = "a month" if kind == "monthly" else "every two weeks"
    hub_name = "Monthly pay" if kind == "monthly" else "Biweekly pay"
    path = f"/{kind}/{amount}/"
    title = f"{money(amount)} {'a Month' if kind == 'monthly' else 'Biweekly'} Is How Much a Year? {money(annual)} ({money(h, cents=True)}/hr) | Live Salary"
    net, *_ = take_home(annual)
    description = (f"{money(amount)} {noun} is {money(annual)} a year, or {money(h, cents=True)} an hour at {HOURS_PER_WEEK} hours a week — "
                   f"about {money(net / per_year)} {noun} after federal tax. Is it good pay? See it add up live.")
    closest_salary = min(annual_values, key=lambda a: abs(a - annual))
    other_kind = "biweekly" if kind == "monthly" else "monthly"
    other_amount = annual / (26 if kind == "monthly" else 12)
    body = f"""
        <h1>{money(amount)} {noun} is <span class="hl">{money(annual)}</span> a year</h1>
        <p class="lede">That works out to <strong>{money(h, cents=True)} an hour</strong> on a {HOURS_PER_WEEK}-hour week — {money(other_amount)} {'every two weeks' if kind == 'monthly' else 'a month'}, and about {money(net / per_year)} {noun} after federal taxes.</p>
{counter_block(h, label=f"Earning {money(amount)} {noun} since you opened this page")}
        <h2>{money(amount)} {noun}, broken down</h2>
{breakdown_table(h)}
{is_it_good_section(h, occupations, label=f"{money(amount)} {noun}")}
        <h2>How it compares</h2>
{context_paragraph(h)}
        <h2>Nearby amounts</h2>
        <nav class="chips">{neighbours(all_values, amount, lambda v: (money(v), str(v)), f"/{kind}/")}</nav>
        <p>See the full picture for <a href="/salary/{closest_salary}/">{money(closest_salary)} a year</a>, including take-home by state.</p>
"""
    og = og_card(f"{kind}-{amount}", hub_name, f"{money(amount)} {noun} = {money(annual)}/yr",
                 f"{money(h, cents=True)} an hour · about {money(net / per_year)} {noun} after federal tax")
    write(path, shell(path=path, title=title, description=description, body=body, json_ld=webpage_ld(title, description, path), og=og,
                      breadcrumbs=[("Live Salary", "/"), (hub_name, f"/{kind}/"), (f"{money(amount)} {noun}", path)]))
    return path


# ---------- State pages ----------

def state_tax_table(state):
    note = (" " + escape(state["note"])) if state.get("note") else ""
    ded = state.get("standard_deduction_single") or 0
    ded_text = f" after a {money(ded)} standard deduction" if ded else ""
    if state["tax_type"] == "none":
        return f"<p>{state['name']} does not tax wage income.{note}</p>"
    if state["tax_type"] == "flat":
        rate = state["brackets_single"][0][1]
        return f"<p>{state['name']} has a <strong>flat {rate * 100:.2f}%</strong> income tax{ded_text}.{note}</p>"
    rows, lower = [], 0
    for upper, rate in state["brackets_single"]:
        rng = f"{money(lower)} – {money(upper)}" if upper else f"over {money(lower)}"
        rows.append(f"<tr><th scope=\"row\">{rng}</th><td>{rate * 100:.2f}%</td></tr>")
        lower = upper or lower
    return f"""
        <p>{state['name']} uses progressive brackets on taxable income{ded_text}.{note}</p>
        <table class="grid">
            <thead><tr><th scope="col">Taxable income (single)</th><th scope="col">Rate</th></tr></thead>
            <tbody>
{chr(10).join(rows)}
            </tbody>
        </table>"""


def state_page(kind, value, state, states, occupations):
    """kind is 'hourly' or 'salary'; value is the rate or the annual amount."""
    if kind == "hourly":
        h, annual = value, value * HOURS_PER_YEAR
        amount_text, amount_title = f"{rate_text(h)} an hour", f"{rate_text(h)} an Hour"
        parent_path, parent_name = f"/hourly/{slug_for_rate(h)}/", f"{rate_text(h)} an hour"
    else:
        annual, h = value, value / HOURS_PER_YEAR
        amount_text, amount_title = f"{money(annual)} a year", f"{money(annual)} a Year"
        parent_path, parent_name = f"/salary/{annual}/", f"{money(annual)} a year"
    path = f"{parent_path}{state['slug']}/"
    net, fed, fica, st = take_home(annual, state)
    net_us, *_ = take_home(annual)
    name = state["name"]
    title = f"{amount_title} After Taxes in {name}: {money(net)} Take-Home ({money(net / 12)}/month) | Live Salary"
    description = (f"{amount_text.capitalize()} in {name} is about {money(net)} a year after federal and state taxes — {money(net / 12)} a month, "
                   f"{money(net / 26)} every two weeks. {name} income tax: {money(st)}. Compared with the state minimum wage and median income.")
    vs_min = h / state["min_wage"]
    mhi = state.get("median_household_income")
    mhi_line = (f" The median <em>household</em> income in {name} is about {money(mhi)} (US: {money(US_MEDIAN_HOUSEHOLD_INCOME)}), so {amount_text} from one earner is "
                f"{pct(annual / mhi)} of a typical household's income here." if mhi else "")
    local = f" Many {name} residents also pay a local income tax on top of this, which isn't included." if state.get("local_income_tax") else ""
    body = f"""
        <h1>{amount_text.capitalize()} in {name} is about <span class="hl">{money(net)}</span> after taxes</h1>
        <p class="lede">{money(annual)} a year before tax becomes roughly <strong>{money(net / 12)} a month</strong> in {name} after federal income tax, Social Security, Medicare and {name} state income tax{' (which is zero)' if st == 0 else f' of {money(st)}'}.{local}</p>
{counter_block(h, label=f"Earning {amount_text} since you opened this page")}
        <h2>Take-home pay in {name}</h2>
{breakdown_table(h, state)}
        <h2>{name} income tax on {amount_text}</h2>
{state_tax_table(state)}
        <p>Compared with a state with no income tax, living in {name} {'costs about ' + money(st) + ' a year on this income — ' + money(st / 12) + ' a month' if st > 0 else 'costs nothing extra in state income tax'}. Nationally (federal taxes only), take-home would be {money(net_us)}.</p>
        <h2>How {amount_text} compares in {name}</h2>
        <p>{amount_text.capitalize()} is <strong>{vs_min:.1f}×</strong> the {name} minimum wage of {rate_text(state['min_wage'])}{' (the federal rate)' if state['min_wage'] == FEDERAL_MIN_WAGE else ''} and {('above' if h > US_MEDIAN_HOURLY * 1.02 else 'below' if h < US_MEDIAN_HOURLY * 0.98 else 'right at')} the national median full-time wage of ${US_MEDIAN_HOURLY:.2f} an hour.{mhi_line}</p>
        <h2>Other states</h2>
        <nav class="chips">{''.join(f'<a href="{parent_path}{s["slug"]}/">{escape(s["name"])}</a>' for s in states if s["slug"] != state["slug"])}</nav>
        <p>Back to <a href="{parent_path}">{parent_name} nationally</a>.</p>
"""
    og = f"hourly-{slug_for_rate(h)}" if kind == "hourly" else f"salary-{annual}"
    write(path, shell(path=path, title=title, description=description, body=body, json_ld=webpage_ld(title, description, path), og=og,
                      breadcrumbs=[("Live Salary", "/"), ("Hourly wages" if kind == "hourly" else "Salaries", f"/{kind}/"), (parent_name, parent_path), (name, path)]))
    return path


# ---------- Earner pages (people and occupations) ----------

def earner_page(e, kind, source, all_earners, occupations):
    annual = e["annual"]
    per_second = annual / (365 * 24 * 3600)
    per_hour_working = annual / HOURS_PER_YEAR
    path = f"/earns/{e['slug']}/"
    name = e["name"]
    is_person = kind == "person"
    if is_person:
        title = f"How Much Does {name} Make Per Second, Minute and Hour? | Live Salary"
        description = (f"{name} earns an estimated {short_money(annual)} a year — about {money(per_second, cents=True)} every second, "
                       f"{money(per_second * 60, cents=True)} a minute and {money(per_second * 3600)} an hour, around the clock. Watch it tick up live.")
        h1 = f"{name} earns about <span class=\"hl\">{money(per_second, cents=True)}</span> every second"
        lede = (f"{name} ({e['role']}) made an estimated <strong>{money(annual)}</strong> over a year. Spread evenly across every second of "
                f"the year — sleep included — that's {money(per_second * 60, cents=True)} a minute, {money(per_second * 3600)} an hour and {money(annual / 365)} a day.")
        label = f"{name} has earned this much since you opened this page"
        mode = "clock"
    else:
        title = f"How Much Does a {name} Make Per Hour, Day and Year? | Live Salary"
        description = (f"The median {name.lower()} in the US earns about {money(annual)} a year — roughly {money(per_hour_working, cents=True)} an hour, "
                       f"{money(annual / 12)} a month. Is it good pay? See it add up second by second.")
        h1 = f"A {name.lower()} earns about <span class=\"hl\">{money(per_hour_working, cents=True)}</span> an hour"
        lede = (f"The median annual wage for {e['plural']} in the US is about <strong>{money(annual)}</strong> ({source}). Over a standard "
                f"{HOURS_PER_WEEK}-hour week that works out to {money(per_hour_working, cents=True)} an hour, {money(annual / 12)} a month, or {money(per_hour_working * 8)} a day.")
        label = f"A {name.lower()} earning the median wage, since you opened this page"
        mode = "session"
    rate_for_counter = per_second * 3600 if is_person else per_hour_working
    median_time = duration(US_MEDIAN_ANNUAL / per_second) if is_person else None

    if is_person:
        extras = f"""
{earner_hero(name, per_second, per_second * 3600, US_MEDIAN_HOURLY, "Median US worker")}
        <h2>Compared with a typical salary</h2>
        <p>The median full-time US worker earns about {money(US_MEDIAN_ANNUAL)} a year. {name} earns that much in roughly <strong>{median_time}</strong>.</p>
        <p class="compare" data-compare data-annual="{annual}">
            <label>Your salary: <span class="input-wrap"><span class="prefix">$</span><input type="text" inputmode="numeric" value="{US_MEDIAN_ANNUAL}" data-compare-input aria-label="Your annual salary"></span></label>
            <span data-compare-out>{name} earns your yearly pay every <strong>{median_time}</strong>.</span>
        </p>
        <h2>How long does it take {name} to earn…</h2>
        <ul class="ticks">
{chr(10).join(f'<li><strong>{duration(price / per_second)}</strong> to earn {n}</li>' for n, price in PRICES)}
        </ul>
        <h2>Per period</h2>
        <table class="grid">
            <thead><tr><th scope="col">Period</th><th scope="col">Estimated earnings</th></tr></thead>
            <tbody>
                <tr><th scope="row">Per second</th><td>{money(per_second, cents=True)}</td></tr>
                <tr><th scope="row">Per minute</th><td>{money(per_second * 60, cents=True)}</td></tr>
                <tr><th scope="row">Per hour</th><td>{money(per_second * 3600)}</td></tr>
                <tr><th scope="row">Per day</th><td>{money(annual / 365)}</td></tr>
                <tr><th scope="row">Per week</th><td>{money(annual / 52)}</td></tr>
                <tr><th scope="row">Per month</th><td>{money(annual / 12)}</td></tr>
                <tr><th scope="row">Per year</th><td>{money(annual)}</td></tr>
            </tbody>
        </table>
        <p class="fine">Source: {escape(e.get('source', source))}. Earnings are estimates before tax, agents' fees and expenses; they change every year.</p>"""
    else:
        closest_hourly_slug = slug_for_rate(min(HOURLY_VALUES, key=lambda v: abs(v - per_hour_working)))
        extras = f"""
        <h2>{name} pay, broken down</h2>
{breakdown_table(per_hour_working)}
{is_it_good_section(per_hour_working, [o for o in occupations if o["slug"] != e["slug"]], label=f"{money(annual)} a year")}
        <h2>How it compares</h2>
{context_paragraph(per_hour_working)}
        <h2>How long does a {name.lower()} work to earn…</h2>
{time_to_earn_list(per_hour_working)}
        <p>See <a href="/hourly/{closest_hourly_slug}/">what {rate_text(min(HOURLY_VALUES, key=lambda v: abs(v - per_hour_working)))} an hour earns by state</a>.</p>
        <p class="fine">Source: {escape(source)}. Half of {e['plural']} earn more than the median and half earn less; pay varies a lot by state, employer and experience.</p>"""

    others = "".join(f'<a href="/earns/{o["slug"]}/">{escape(o["name"])}</a>' for o in all_earners if o["slug"] != e["slug"])
    body = f"""
        <h1>{h1}</h1>
        <p class="lede">{lede}</p>
{counter_block(rate_for_counter, label=label, mode=mode)}
{extras}
        <h2>More earners</h2>
        <nav class="chips">{others}</nav>
"""
    if is_person:
        og = og_card(f"earns-{e['slug']}", name, f"{money(per_second, cents=True)} every second", f"{e['role']} · about {short_money(annual)} a year")
    else:
        og = og_card(f"earns-{e['slug']}", name, f"{money(per_hour_working, cents=True)} an hour", f"US median {money(annual)} a year · {money(annual / 12)} a month")
    write(path, shell(path=path, title=title, description=description, body=body, json_ld=webpage_ld(title, description, path), og=og,
                      breadcrumbs=[("Live Salary", "/"), ("Who earns what", "/earns/"), (name, path)]))
    return path


def earner_hero(name, per_second, per_hour, baseline_per_hour, baseline_name):
    """Big per-period tiles plus a to-scale bar against the median worker. Bar widths use .w-N classes
    (inline styles are blocked by the CSP)."""
    ratio = per_hour / baseline_per_hour if baseline_per_hour else 0
    base_w = max(1, min(100, round(100 / ratio))) if ratio >= 1 else 100
    them_w = 100 if ratio >= 1 else max(1, round(100 * ratio))
    tile_money = lambda v: short_money(v) if v >= 100000 else money(v, cents=v < 1000)
    tiles = "".join(
        f'<div class="tile"><span class="tile-k">{k}</span><span class="tile-v">{v}</span></div>'
        for k, v in [("Per second", tile_money(per_second)), ("Per minute", tile_money(per_second * 60)),
                     ("Per hour", tile_money(per_hour)), ("Per day", tile_money(per_second * 86400))])
    return f"""
        <section class="hero-earner" aria-label="Earnings at a glance">
            <div class="tiles">{tiles}</div>
            <div class="vs">
                <div class="vs-row"><span class="vs-name">{escape(name)}</span><div class="vs-bar"><span class="w-{them_w}"></span></div><span class="vs-val">{money(per_hour)}/hr</span></div>
                <div class="vs-row"><span class="vs-name">{escape(baseline_name)}</span><div class="vs-bar"><span class="base w-{base_w}"></span></div><span class="vs-val">{money(baseline_per_hour, cents=True)}/hr</span></div>
            </div>
            <p class="vs-note">Drawn to scale: hour for hour, that's <strong>{ratio:,.0f}×</strong> what the median full-time US worker earns{' — counting every hour of the day and night' if per_hour == per_second * 3600 else ''}.</p>
        </section>"""


# ---------- Organisation pages (companies, governments) ----------

def org_page(o, all_orgs):
    annual = o["annual"]
    per_second = annual / (365 * 24 * 3600)
    path = f"/earns/{o['slug']}/"
    name = o["name"]
    is_gov = o.get("kind") == "government"
    basis = o.get("basis", "net income")
    kind = "interest" if "interest" in basis.lower() else o.get("kind", "company")
    verb, verb_title, counter_label = {
        "company": ("makes", "Make", f"{name}'s profit since you opened this page"),
        "government": ("spends", "Spend", f"{name} has spent this much since you opened this page"),
        "economy": ("produces", "Produce", f"{name} has produced this much since you opened this page"),
        "interest": ("costs", "Cost", "Interest accrued since you opened this page"),
    }.get(kind, ("makes", "Make", f"{name} since you opened this page"))
    what = " in profit" if verb == "makes" else ""
    title_name = "the " + name[4:] if name.startswith("The ") else name
    title = f"How Much Does {title_name} {verb_title} Per Second? {money(per_second)} | Live Salary"
    description = (f"{title_name.capitalize() if title_name.startswith('the ') else title_name} {verb} about {money(per_second)} every second — {money(per_second * 60)} a minute, {money(per_second * 3600)} an hour — "
                   f"based on {short_money(annual)} {basis} in {o.get('fiscal_year', 'the latest fiscal year')}. Watch it tick up live.")
    median_time = duration(US_MEDIAN_ANNUAL / per_second)
    rev = o.get("revenue")
    rev_line = (f" On revenue of {money(rev)} ({money(rev / 31536000)} a second), that's a {pct(annual / rev)} net margin." if rev and verb == "makes" else
                f" Receipts were {money(rev)} ({money(rev / 31536000)} a second), leaving a gap of {money(o.get('spending', annual) - rev)} for the year." if rev and verb == "spends" else "")
    body = f"""
        <h1>{escape(name)} {verb} about <span class="hl">{money(per_second)}</span>{what} every second</h1>
        <p class="lede">{escape(name)} reported <strong>{money(annual)}</strong> of {escape(basis)} for {escape(o.get('fiscal_year', 'its latest fiscal year'))}. Spread across every second of the year, that's {money(per_second * 60)} a minute, {money(per_second * 3600)} an hour and {money(annual / 365)} a day.{rev_line}</p>
{counter_block(per_second * 3600, label=counter_label, mode="clock")}
{earner_hero(name, per_second, per_second * 3600, US_MEDIAN_HOURLY, "Median US worker")}
        <h2>Compared with a person</h2>
        <p>The median full-time US worker earns about {money(US_MEDIAN_ANNUAL)} a year. {escape(name)} {verb} that much every <strong>{median_time}</strong>.</p>
        <p class="compare" data-compare data-annual="{annual}">
            <label>Your salary: <span class="input-wrap"><span class="prefix">$</span><input type="text" inputmode="numeric" value="{US_MEDIAN_ANNUAL}" data-compare-input aria-label="Your annual salary"></span></label>
            <span data-compare-out>{escape(name)} {verb} your yearly pay every <strong>{median_time}</strong>.</span>
        </p>
        <h2>In the time it takes to…</h2>
        <ul class="ticks">
            <li><strong>{money(per_second * 10)}</strong> while you read this sentence (10 seconds)</li>
            <li><strong>{money(per_second * 60 * 4)}</strong> during a 4-minute song</li>
            <li><strong>{money(per_second * 3600 * 2)}</strong> during a 2-hour film</li>
            <li><strong>{money(per_second * 3600 * 8)}</strong> during your 8-hour workday</li>
            <li><strong>{money(per_second * 86400 * 7)}</strong> in a week</li>
        </ul>
        <h2>Per period</h2>
        <table class="grid">
            <thead><tr><th scope="col">Period</th><th scope="col">{escape(basis.capitalize())}</th></tr></thead>
            <tbody>
                <tr><th scope="row">Per second</th><td>{money(per_second)}</td></tr>
                <tr><th scope="row">Per minute</th><td>{money(per_second * 60)}</td></tr>
                <tr><th scope="row">Per hour</th><td>{money(per_second * 3600)}</td></tr>
                <tr><th scope="row">Per day</th><td>{money(annual / 365)}</td></tr>
                <tr><th scope="row">Per week</th><td>{money(annual / 52)}</td></tr>
                <tr><th scope="row">Per month</th><td>{money(annual / 12)}</td></tr>
                <tr><th scope="row">Per year</th><td>{money(annual)}</td></tr>
            </tbody>
        </table>
        <p class="fine">Source: <a href="{escape(o.get('source', '#'))}" rel="noopener">{escape(o.get('fiscal_year', 'latest fiscal year'))} figures</a>. {'Government outlays are spending, not income.' if is_gov else 'Net income is profit after all costs and taxes; revenue is total sales.'} Per-second figures divide the annual total evenly across the year.</p>
        <h2>More organisations</h2>
        <nav class="chips">{''.join(f'<a href="/earns/{x["slug"]}/">{escape(x["name"])}</a>' for x in all_orgs if x["slug"] != o["slug"])}</nav>
        <p>Or compare with <a href="/earns/">people and everyday jobs</a>.</p>
"""
    og = og_card(f"earns-{o['slug']}", name, f"{money(per_second)} every second", f"{short_money(annual)} {basis} · {o.get('fiscal_year', '')}".strip(" ·"))
    write(path, shell(path=path, title=title, description=description, body=body, json_ld=webpage_ld(title, description, path), og=og,
                      breadcrumbs=[("Live Salary", "/"), ("Who earns what", "/earns/"), (name, path)]))
    return path


# ---------- Hubs and static pages ----------

def hub(path, title, description, h1, lede, sections, crumb):
    body = f"<h1>{h1}</h1>\n<p class=\"lede\">{lede}</p>\n" + "\n".join(sections)
    write(path, shell(path=path, title=title, description=description, body=body, json_ld=webpage_ld(title, description, path),
                      breadcrumbs=[("Live Salary", "/"), (crumb, path)]))
    return path


def static_page(path, title, description, body, crumb):
    write(path, shell(path=path, title=title, description=description, body=body, json_ld=webpage_ld(title, description, path),
                      breadcrumbs=[("Live Salary", "/"), (crumb, path)]))
    return path


def trust_pages(people, occupations, states):
    paths = []
    contact_line = (f'<p>Email <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>' if CONTACT_EMAIL else "")
    paths.append(static_page("/about/", "About Live Salary", "Who makes Live Salary, why it exists, and how it is funded.",
        f"""
        <h1>About Live Salary</h1>
        <p class="lede">Live Salary started in 2024 as a one-page toy: type your hourly rate, press Start, and watch the money count up. It turns out watching your pay arrive second by second changes how an hour feels — and makes abstract numbers like "$25 an hour" or "$275 million a year" suddenly concrete.</p>
        <h2>What's here</h2>
        <p>The <a href="/">live counter</a> is the heart of the site. Around it are pages that answer the questions people actually type into a search box: <a href="/hourly/">what an hourly wage adds up to over a year</a>, <a href="/salary/">what a salary works out to per hour</a>, what's left <a href="/hourly/25/">after taxes in each state</a>, and <a href="/earns/">how fast the highest-paid people on earth earn</a> compared with everyday jobs. Every page has the counter preloaded with that rate.</p>
        <h2>Who makes it</h2>
        <p>Live Salary is made and maintained by Caden, an independent developer in the United States, with help from AI tools for code and research. There's no company behind it. The code is open at <a href="{REPO_URL}">GitHub</a>.</p>
        <h2>How it's funded</h2>
        <p>Right now it isn't. The site may carry a small number of ads on the reference pages in future; the counter itself will stay ad-free. There are no sponsored figures, affiliate placements or paid rankings on any page.</p>
        <h2>Accuracy</h2>
        <p>Every number on the site is computed from stated assumptions and public data; the <a href="/methodology/">methodology page</a> lists them with sources and dates. If something looks wrong, <a href="/contact/">say so</a> — corrections ship within days.</p>
        {contact_line}""", "About"))
    paths.append(static_page("/methodology/", "Methodology: How Live Salary Calculates Pay, Taxes and Comparisons",
        "Every assumption behind the numbers on Live Salary: hours per year, 2025 federal and state tax estimates, data sources for wages, celebrities and occupations.",
        f"""
        <h1>Methodology</h1>
        <p class="lede">Every figure on this site is calculated, not copied. This page lists the assumptions and data behind them so you can judge how well they fit your situation.</p>
        <h2>Working time</h2>
        <p>Annual pay from an hourly rate assumes <strong>{HOURS_PER_WEEK} hours a week for {WEEKS_PER_YEAR} weeks = {HOURS_PER_YEAR:,} hours a year</strong>, with no unpaid time off. Monthly figures divide the year by 12; biweekly by 26; weekly by 52; daily by 260 working days. Each page also shows the result for 20–50 hour weeks.</p>
        <h2>Federal taxes (2025, single filer)</h2>
        <p>Take-home estimates subtract three things from gross pay:</p>
        <ul>
            <li><strong>Federal income tax</strong> using the 2025 brackets for a single filer after the {money(STANDARD_DEDUCTION)} standard deduction (the amount set by the July 2025 tax law, up from the $15,000 announced earlier): {', '.join(f'{r * 100:.0f}% to {money(u)}' for u, r in BRACKETS[:-1])}, then 37%.</li>
            <li><strong>Social Security</strong> at {SS_RATE * 100:.1f}% of wages up to {money(SS_CAP)}.</li>
            <li><strong>Medicare</strong> at {MEDICARE_RATE * 100:.2f}%, plus 0.9% on wages over {money(MEDICARE_EXTRA_FROM)}.</li>
        </ul>
        <p>Not included: tax credits, itemized deductions, 401(k) or HSA contributions, health insurance premiums, filing jointly, dependants. Real take-home is usually a little higher for people with pre-tax benefits and credits, and lower for people with local taxes.</p>
        <h2>State taxes</h2>
        <p>State pages add state income tax for tax year {states['_meta']['tax_year'] if states else 2025} using each state's single-filer brackets and standard deduction (or the closest equivalent where a state uses exemptions or credits instead). Local and city income taxes are not included; pages for states where they are common say so. Source: state revenue departments and the Tax Foundation's annual state tax survey{'; compiled ' + states['_meta']['compiled'] if states else ''}. Treat these as estimates good to a few hundred dollars a year, not a filing calculation.</p>
        <h2>Comparisons</h2>
        <ul>
            <li><strong>Federal minimum wage:</strong> ${FEDERAL_MIN_WAGE} an hour (unchanged since 2009). State pages use the state minimum in effect in 2025.</li>
            <li><strong>US median wage:</strong> {money(US_MEDIAN_WEEKLY)} a week for full-time wage and salary workers (BLS, median usual weekly earnings, {US_MEDIAN_WEEKLY_LABEL}, not seasonally adjusted), treated as {money(US_MEDIAN_ANNUAL)} a year or ${US_MEDIAN_HOURLY:.2f} an hour.</li>
            <li><strong>Living wage:</strong> about ${LIVING_WAGE_SINGLE:.0f} an hour for a single adult with no children. MIT's Living Wage Calculator publishes county and state estimates, not a national one; its 2026 state figures for one adult range from roughly the low $20s to over $30 (California $30.48, Washington $26.59), so ${LIVING_WAGE_SINGLE:.0f} is used here as a rough national mid-point.</li>
            <li><strong>Median household income:</strong> {money(US_MEDIAN_HOUSEHOLD_INCOME)} nationally (Census {US_MEDIAN_HOUSEHOLD_LABEL} 1-year estimate); state figures on state pages are from the same release. Household income usually combines more than one earner, so it is not directly comparable with one person's pay.</li>
            <li><strong>Budget illustrations:</strong> {money(TYPICAL_RENT)} rent (roughly the national median asking rent) and {money(TYPICAL_GROCERIES)} a month of groceries for one adult. Your costs will differ; the point is scale, not precision.</li>
        </ul>
        <h2>Occupation pay</h2>
        <p>Median annual wages for occupations are the national medians from the US Bureau of Labor Statistics Occupational Employment and Wage Statistics ({escape(OCC_SOURCE.split(', ', 1)[-1])}), fetched from the BLS public data API. "Median" means half of workers in that job earn more and half earn less; pay varies widely by state, employer and experience. Where the site uses a plain job name for a BLS category (for example "family doctor" for family medicine physicians, or "dentist" for all dentists), the broader figure is used.</p>
        <h2>Celebrity and executive earnings</h2>
        <p>Athletes and musicians use Forbes' estimates of 12-month earnings (salary, prize money, endorsements and other income, before tax and fees) from its 2025 highest-paid lists. Executives use total compensation reported in company proxy statements, which is mostly stock awards whose eventual value differs. These are public estimates, not audited figures, and are refreshed when new lists are published. Per-second figures divide the annual estimate evenly across all 31,536,000 seconds of the year.</p>
        <h2>The live counter</h2>
        <p>The counter multiplies the chosen rate by the exact time elapsed, so it stays correct even if your device slows down or the tab is hidden. It never rounds up: the large digits show whole cents, the small digits show the next two decimal places.</p>
        <h2>Updates and corrections</h2>
        <p>Assumptions are reviewed when new tax brackets, BLS wage data or Forbes lists are published, normally once a year. Pages show their last update date in the footer. Found an error? <a href="/contact/">Let me know</a>.</p>""", "Methodology"))
    paths.append(static_page("/privacy/", "Privacy Policy | Live Salary", "What Live Salary stores (your settings, in your browser only) and what it doesn't (anything about you).",
        f"""
        <h1>Privacy</h1>
        <p class="lede">Live Salary is built so that it has almost nothing to know about you. This page spells out exactly what happens to data when you use the site.</p>
        <h2>Your salary and settings stay on your device</h2>
        <p>The rate you enter, your currency, mode and theme are saved in your browser's local storage so they're there when you come back. They never leave your device: there is no account, no server-side database and no way for us to read them. Clearing your browser data, or using "Clear saved data" in Settings, removes them. Embedded counters on other websites store nothing.</p>
        <h2>No cookies</h2>
        <p>The site sets no cookies and shows no cookie banner because there is nothing to consent to.</p>
        <h2>Visitor counting</h2>
        <p>We count page views with <a href="https://www.goatcounter.com/">GoatCounter</a>, a privacy-focused service that records the page visited, the referring site, browser type, screen size and country. It does not use cookies or store IP addresses, cannot identify individuals and cannot follow you to other sites. Counts are used only to understand which pages are useful. If you use an ad blocker it will probably block this, and that's fine.</p>
        <h2>Hosting</h2>
        <p>The site is served by GitHub Pages, which, like any web host, sees the IP address of visitors in its server logs for operational and security purposes. See <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement">GitHub's privacy statement</a>.</p>
        <h2>Advertising</h2>
        <p>There are currently no ads. If ads are added to the reference pages in future, this page will be updated first with the provider and any choices available to you; the live counter page will remain ad-free.</p>
        <h2>Links to other sites</h2>
        <p>Sources such as Forbes, the BLS and the Tax Foundation are linked for transparency. Their privacy practices are their own.</p>
        <h2>Changes</h2>
        <p>This policy was last updated on {TODAY}. Material changes will be noted here.</p>
        {contact_line}""", "Privacy"))
    paths.append(static_page("/contact/", "Contact | Live Salary", "How to report an error, suggest a page or get in touch about Live Salary.",
        f"""
        <h1>Contact</h1>
        <p class="lede">Spotted a wrong figure, want a wage or a person added, or have an idea? Here's how to reach me.</p>
        {contact_line if contact_line else ''}
        <h2>Report an error or request a page</h2>
        <p>The quickest route is to <a href="{REPO_URL}/issues">open an issue on GitHub</a> — no account? Just mention the page URL and what's off, and it'll get fixed in the next update.</p>
        <h2>Press and embedding</h2>
        <p>You're welcome to quote any figure from this site with a link. To put a live counter in your own article, see the <a href="/embed/">embed page</a>.</p>
        <h2>What this site is not</h2>
        <p>Live Salary provides estimates for general information. It is not tax, legal or financial advice, and can't answer questions about your personal tax situation.</p>""", "Contact"))
    return paths


def embed_pages():
    paths = []
    paths.append(static_page("/embed/", "Embed a Live Salary Counter in Your Site or Article",
        "Add a live earnings counter to any web page with one line of HTML. Free, no tracking, works with any hourly rate or salary.",
        f"""
        <h1>Embed a live counter</h1>
        <p class="lede">Put a ticking "earned since you opened this page" counter in your article, blog post or dashboard. One line of HTML, no sign-up, nothing tracked.</p>
        <section class="live" data-hourly="25" data-mode="session" id="embedPreview">
            <p class="eyebrow">Earning $25/hr since you opened this page</p>
            <div class="live-amount" aria-live="off"><span class="live-main" data-live="main">$0.00</span><span class="live-sub" data-live="sub">00</span></div>
            <p class="live-meta" data-live="meta"></p>
        </section>
        <h2>Configure</h2>
        <form class="embed-form" data-embed-form>
            <div class="field-row">
                <div class="field">
                    <label for="embedRate">Hourly rate (USD)</label>
                    <div class="input-wrap"><span class="prefix">$</span><input id="embedRate" type="text" inputmode="decimal" value="25" data-embed-rate></div>
                </div>
                <div class="field">
                    <label for="embedLabel">Label (optional)</label>
                    <input id="embedLabel" type="text" maxlength="80" placeholder="Earning $25/hr since you opened this page" data-embed-label>
                </div>
            </div>
            <label class="check"><input type="checkbox" data-embed-dark checked> Dark theme</label>
        </form>
        <h2>Copy this HTML</h2>
        <pre class="code" data-embed-code>&lt;iframe src="{SITE}/embed/widget/?hourly=25" width="100%" height="220" style="border:0;border-radius:16px" title="Live Salary counter" loading="lazy"&gt;&lt;/iframe&gt;</pre>
        <p class="fine">The widget is a plain iframe: it can't read anything on your page, sets no cookies and loads about 20 KB. A small "Live Salary" link in the corner is the only thing we ask for.</p>
        <h2>Tips</h2>
        <ul>
            <li>Use an annual salary instead by dividing by {HOURS_PER_YEAR:,} ({HOURS_PER_WEEK} hours × {WEEKS_PER_YEAR} weeks) — or just pass <code>?annual=60000</code>.</li>
            <li>For a 24/7 earner like an athlete or a company, add <code>&amp;mode=clock</code> to spread the yearly figure across every second of the year.</li>
            <li>Add <code>&amp;theme=light</code> for light backgrounds.</li>
        </ul>""", "Embed"))
    # The widget itself: a bare page driven by query parameters (see counter.js).
    body = f"""
        <section class="live widget" data-hourly="auto" data-mode="session">
            <p class="eyebrow" data-live="label">Earning since you opened this page</p>
            <div class="live-amount" aria-live="off"><span class="live-main" data-live="main">$0.00</span><span class="live-sub" data-live="sub">00</span></div>
            <p class="live-meta" data-live="meta"></p>
            <a class="widget-brand" href="{SITE}/" target="_blank" rel="noopener">Live Salary</a>
        </section>"""
    write("/embed/widget/", shell(path="/embed/widget/", title="Live Salary counter", description="An embedded live earnings counter from Live Salary.",
                                  body=body, breadcrumbs=[], bare=True, extra_head='\n    <meta name="robots" content="noindex">'))
    return paths


# ---------- Sitemaps ----------

def write_sitemaps(groups):
    """groups: dict name -> list of paths. Writes sitemaps/<name>.xml and a sitemap.xml index."""
    os.makedirs(os.path.join(ROOT, "sitemaps"), exist_ok=True)
    index = ['<?xml version="1.0" encoding="UTF-8"?>', '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    total = 0
    for name, paths in groups.items():
        if not paths:
            continue
        xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for p in paths:
            xml.append(f"  <url><loc>{SITE}{p}</loc><lastmod>{TODAY}</lastmod></url>")
        xml.append("</urlset>")
        with open(os.path.join(ROOT, "sitemaps", f"{name}.xml"), "w", encoding="utf-8") as f:
            f.write("\n".join(xml) + "\n")
        index.append(f"  <sitemap><loc>{SITE}/sitemaps/{name}.xml</loc><lastmod>{TODAY}</lastmod></sitemap>")
        total += len(paths)
    index.append("</sitemapindex>")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")
    return total


HOURLY_VALUES = []
OCC_SOURCE = "US Bureau of Labor Statistics, OEWS"


def main():
    global HOURLY_VALUES, OCC_SOURCE
    wages = json.load(open(os.path.join(DATA, "wages.json")))
    people = json.load(open(os.path.join(DATA, "people.json")))
    occupations = json.load(open(os.path.join(DATA, "occupations.json")))["occupations"]
    occ_source = OCC_SOURCE = json.load(open(os.path.join(DATA, "occupations.json")))["source"]
    states_file = os.path.join(DATA, "states.json")
    states_data = json.load(open(states_file)) if os.path.exists(states_file) else None
    states = sorted(states_data["states"], key=lambda s: s["name"]) if states_data else []

    HOURLY_VALUES = hourly_values = sorted(wages["hourly"])
    annual_values = sorted(wages["annual"])
    monthly_values = sorted(wages["monthly"])
    biweekly_values = sorted(wages["biweekly"])

    for d in ("hourly", "salary", "monthly", "biweekly", "earns", "about", "methodology", "privacy", "contact", "embed", "sitemaps"):
        shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)

    groups = {"pages": ["/"], "hourly": [], "salary": [], "periods": [], "earners": [], "states-hourly": [], "states-salary": []}

    for h in hourly_values:
        groups["hourly"].append(hourly_page(h, hourly_values, annual_values, occupations, states))
        for s in states:
            groups["states-hourly"].append(state_page("hourly", h, s, states, occupations))
    for a in annual_values:
        groups["salary"].append(salary_page(a, annual_values, hourly_values, occupations, states))
        for s in states:
            groups["states-salary"].append(state_page("salary", a, s, states, occupations))
    for m in monthly_values:
        groups["periods"].append(period_page(m, "monthly", monthly_values, annual_values, occupations))
    for b in biweekly_values:
        groups["periods"].append(period_page(b, "biweekly", biweekly_values, annual_values, occupations))

    all_people = [dict(p, group=g) for g in people["groups"] for p in g["people"]]
    all_earners = all_people + occupations
    for g in people["groups"]:
        for p in g["people"]:
            groups["earners"].append(earner_page(p, "person", g["source"], all_earners, occupations))
    for o in occupations:
        groups["earners"].append(earner_page(o, "occupation", occ_source, all_earners, occupations))
    orgs_file = os.path.join(DATA, "organizations.json")
    orgs = json.load(open(orgs_file))["organizations"] if os.path.exists(orgs_file) else []
    for o in orgs:
        groups["earners"].append(org_page(o, orgs))

    groups["pages"].append(hub("/hourly/", "Hourly Wage to Salary: What Each Hourly Rate Earns Per Year | Live Salary",
        "Pick an hourly wage to see what it earns per year, month and week, what's left after tax in every state, whether it's good pay, and watch it add up live.",
        "What does an hourly wage earn per year?",
        f"Pick a rate. Every page shows yearly, monthly, weekly and daily pay at {HOURS_PER_WEEK} hours a week, take-home after tax in all 50 states, how it compares, and a live counter.",
        ["<nav class=\"chips big\">" + "".join(f'<a href="/hourly/{slug_for_rate(h)}/">{rate_text(h)}</a>' for h in hourly_values) + "</nav>"], "Hourly wages"))
    groups["pages"].append(hub("/salary/", "Salary to Hourly: What Each Annual Salary Pays Per Hour | Live Salary",
        "Pick an annual salary to see the hourly, monthly and biweekly equivalent, take-home after tax by state, whether it's a good salary, and watch it add up live.",
        "What does a salary work out to per hour?",
        f"Pick a salary. Each page converts it to an hourly rate at {HOURS_PER_WEEK} hours a week, breaks it down by period, estimates take-home in every state, and shows it ticking up live.",
        ["<nav class=\"chips big\">" + "".join(f'<a href="/salary/{a}/">{money(a)}</a>' for a in annual_values) + "</nav>"], "Salaries"))
    groups["pages"].append(hub("/monthly/", "Monthly Pay to Yearly Salary and Hourly Rate | Live Salary",
        "Pick a monthly pay amount to see what it is per year and per hour, after tax, and whether it's good pay.",
        "What does a monthly income work out to?",
        "Pick a monthly amount to convert it to a yearly salary and an hourly rate, with take-home estimates.",
        ["<nav class=\"chips big\">" + "".join(f'<a href="/monthly/{m}/">{money(m)}</a>' for m in monthly_values) + "</nav>"], "Monthly pay"))
    groups["pages"].append(hub("/biweekly/", "Biweekly Paycheck to Yearly Salary and Hourly Rate | Live Salary",
        "Pick a biweekly paycheck amount to see what it is per year and per hour, after tax, and whether it's good pay.",
        "What does a biweekly paycheck work out to?",
        "Paid every two weeks? Pick your gross paycheck to see the yearly salary and hourly rate behind it.",
        ["<nav class=\"chips big\">" + "".join(f'<a href="/biweekly/{b}/">{money(b)}</a>' for b in biweekly_values) + "</nav>"], "Biweekly pay"))

    people_sections = []
    for g in people["groups"]:
        cards = "".join(
            f'<a class="card" href="/earns/{p["slug"]}/"><strong>{escape(p["name"])}</strong><span>{escape(p["role"])}</span><em>{short_money(p["annual"])}/yr · {money(p["annual"] / 31557600, cents=True)}/sec</em></a>'
            for p in g["people"])
        people_sections.append(f"<h2>{escape(g['title'])}</h2>\n<div class=\"cards\">{cards}</div>")
    occ_cards = "".join(
        f'<a class="card" href="/earns/{o["slug"]}/"><strong>{escape(o["name"])}</strong><span>US median</span><em>{money(o["annual"])}/yr · {money(o["annual"] / HOURS_PER_YEAR, cents=True)}/hr</em></a>'
        for o in sorted(occupations, key=lambda o: -o["annual"]))
    if orgs:
        org_cards = "".join(
            f'<a class="card" href="/earns/{o["slug"]}/"><strong>{escape(o["name"])}</strong><span>{escape(o.get("basis", ""))}, {escape(o.get("fiscal_year", ""))}</span><em>{short_money(o["annual"])}/yr · {money(o["annual"] / 31536000)}/sec</em></a>'
            for o in sorted(orgs, key=lambda o: -o["annual"]))
        people_sections.append(f"<h2>Companies &amp; governments</h2>\n<div class=\"cards\">{org_cards}</div>")
    people_sections.append(f"<h2>Occupations</h2>\n<div class=\"cards\">{occ_cards}</div>")
    groups["pages"].append(hub("/earns/", "Who Earns What: Athletes, Celebrities, CEOs and Everyday Jobs, Per Second | Live Salary",
        "See how fast the world's highest-paid athletes, musicians and CEOs earn — per second, minute and hour — next to the median pay for everyday jobs.",
        "Who earns what, per second",
        "The highest-paid people on earth, and the median pay for ordinary jobs, each with a live counter.",
        people_sections, "Who earns what"))

    groups["pages"] += trust_pages(people, occupations, states_data)
    groups["pages"] += embed_pages()

    total = write_sitemaps(groups)
    cards = write_og_cards()
    print(f"Generated {sum(len(v) for v in groups.values()) - 1} pages; sitemap index covers {total} URLs"
          f"{' (no states.json: state pages skipped)' if not states else f' across {len(states)} states'}; {cards} social cards in build/og/ "
          f"(run build/render_og.sh to render new ones).")


if __name__ == "__main__":
    main()
