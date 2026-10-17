#!/usr/bin/env python3
"""Generates the static wage, salary and earner pages plus hub pages and the sitemap.

    python3 build/generate.py

Reads build/data/*.json and writes into hourly/, salary/, earns/ at the repo root,
overwriting what is there. Only the Python standard library is used.
"""

import json
import math
import os
import re
import shutil
from datetime import date
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "build", "data")
SITE = "https://mylivesalary.com"
TODAY = date.today().isoformat()

# ---------- Assumptions (kept in one place so the copy and the maths agree) ----------

HOURS_PER_WEEK = 40
WEEKS_PER_YEAR = 52
HOURS_PER_YEAR = HOURS_PER_WEEK * WEEKS_PER_YEAR          # 2,080
FEDERAL_MIN_WAGE = 7.25
US_MEDIAN_WEEKLY = 1196                                   # BLS, full-time median usual weekly earnings, Q2 2025
US_MEDIAN_ANNUAL = US_MEDIAN_WEEKLY * WEEKS_PER_YEAR      # 62,192
US_MEDIAN_HOURLY = US_MEDIAN_ANNUAL / HOURS_PER_YEAR      # ~29.90

# 2025 federal income tax, single filer. Rough take-home only: no state tax, no credits, no 401(k).
STANDARD_DEDUCTION = 15000
BRACKETS = [(11925, 0.10), (48475, 0.12), (103350, 0.22), (197300, 0.24), (250525, 0.32), (626350, 0.35), (math.inf, 0.37)]
SS_RATE, SS_CAP = 0.062, 176100
MEDICARE_RATE, MEDICARE_EXTRA_FROM = 0.0145, 200000

PRICES = [("a $5 coffee", 5), ("a $15 lunch", 15), ("a $120 pair of sneakers", 120), ("a $999 phone", 999), ("$1,600 in rent", 1600)]


def federal_tax(gross):
    taxable = max(0, gross - STANDARD_DEDUCTION)
    tax, lower = 0.0, 0
    for upper, rate in BRACKETS:
        if taxable <= lower:
            break
        tax += (min(taxable, upper) - lower) * rate
        lower = upper
    fica = min(gross, SS_CAP) * SS_RATE + gross * MEDICARE_RATE + max(0, gross - MEDICARE_EXTRA_FROM) * 0.009
    return tax, fica


def take_home(gross):
    tax, fica = federal_tax(gross)
    return gross - tax - fica, tax, fica


# ---------- Formatting ----------

def money(v, cents=False):
    if cents:
        return f"${v:,.2f}"
    return f"${round(v):,}"


def rate_text(h):
    return f"${h:,.2f}" if h != int(h) else f"${int(h):,}"


def slug_for_rate(h):
    return str(int(h)) if h == int(h) else f"{h:.2f}".rstrip("0").replace(".", "-")


def duration(seconds):
    seconds = max(0, seconds)
    if seconds < 1:
        return "under a second"
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


def shell(*, path, title, description, body, breadcrumbs, json_ld=None):
    url = f"{SITE}{path}"
    crumbs_ld = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": f"{SITE}{p}"} for i, (n, p) in enumerate(breadcrumbs)]
    }
    ld_blocks = [crumbs_ld] + ([json_ld] if json_ld else [])
    ld_html = "\n".join(f'<script type="application/ld+json">{json.dumps(b, ensure_ascii=False)}</script>' for b in ld_blocks)
    crumbs_html = " <span class=\"sep\">/</span> ".join(
        f'<a href="{escape(p)}">{escape(n)}</a>' if i < len(breadcrumbs) - 1 else f"<span>{escape(n)}</span>"
        for i, (n, p) in enumerate(breadcrumbs))
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
    <meta property="og:image" content="{SITE}/assets/og-image.png">
    <meta name="twitter:card" content="summary_large_image">
    <link rel="icon" href="/assets/icon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
    <link rel="stylesheet" href="/styles.css">
    <link rel="stylesheet" href="/pages.css">
    <script src="/theme.js"></script>
    {ld_html}
</head>
<body class="page">
    <header class="page-top">
        <a class="brand" href="/">Live Salary</a>
        <nav class="crumbs" aria-label="Breadcrumb">{crumbs_html}</nav>
    </header>
    <main class="page-main">
{body}
    </main>
    <footer class="page-foot">
        <nav aria-label="Explore">
            <a href="/hourly/">Hourly wages</a> · <a href="/salary/">Salaries</a> · <a href="/earns/">Who earns what</a> · <a href="/">Live counter</a>
        </nav>
        <p>Figures are estimates for a single filer with no state income tax, based on {HOURS_PER_WEEK} hours a week, {WEEKS_PER_YEAR} weeks a year. Not financial advice.</p>
    </footer>
    <script src="/counter.js"></script>
    {GOATCOUNTER}
</body>
</html>
"""


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


def breakdown_table(hourly):
    annual = hourly * HOURS_PER_YEAR
    net, tax, fica = take_home(annual)
    rows = [
        ("Per year", annual, net),
        ("Per month", annual / 12, net / 12),
        ("Every two weeks", hourly * HOURS_PER_WEEK * 2, net / 26),
        ("Per week", hourly * HOURS_PER_WEEK, net / 52),
        ("Per day (8 hours)", hourly * 8, net / 260),
        ("Per hour", hourly, net / HOURS_PER_YEAR),
    ]
    body = "\n".join(f"<tr><th scope=\"row\">{p}</th><td>{money(g, cents=g < 100)}</td><td>{money(n, cents=n < 100)}</td></tr>" for p, g, n in rows)
    return f"""
        <table class="grid">
            <thead><tr><th scope="col">Period</th><th scope="col">Before tax</th><th scope="col">After federal tax*</th></tr></thead>
            <tbody>
{body}
            </tbody>
        </table>
        <p class="fine">*Rough estimate for a single filer in 2025: standard deduction, federal income tax and Social Security/Medicare only — about {money(tax + fica)} a year in this case. State and local taxes, health insurance and retirement contributions would lower it further.</p>"""


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


def neighbours(values, current, fmt, hub, count=6):
    idx = values.index(current)
    near = values[max(0, idx - count // 2): idx] + values[idx + 1: idx + 1 + count // 2]
    return "".join(f'<a href="{hub}{fmt(v)[1]}/">{fmt(v)[0]}</a>' for v in near)


# ---------- Hourly pages ----------

def hourly_page(h, all_hourly, annual_values):
    annual = h * HOURS_PER_YEAR
    path = f"/hourly/{slug_for_rate(h)}/"
    title = f"{rate_text(h)} an Hour Is How Much a Year? {money(annual)} | Live Salary"
    net, _, _ = take_home(annual)
    description = (f"{rate_text(h)} an hour is {money(annual)} a year before tax (about {money(net)} after federal tax), "
                   f"{money(annual / 12)} a month or {money(h * HOURS_PER_WEEK)} a week — plus a live counter showing it add up.")
    closest_salary = min(annual_values, key=lambda a: abs(a - annual))
    body = f"""
        <h1>{rate_text(h)} an hour is <span class="hl">{money(annual)}</span> a year</h1>
        <p class="lede">Working {HOURS_PER_WEEK} hours a week, {WEEKS_PER_YEAR} weeks a year — that's {money(annual / 12)} a month before tax, or roughly <strong>{money(net)}</strong> a year after federal taxes.</p>
{counter_block(h, label=f"Earning {rate_text(h)}/hr since you opened this page")}
        <h2>{rate_text(h)} an hour, broken down</h2>
{breakdown_table(h)}
        <h2>How it compares</h2>
{context_paragraph(h)}
        <h2>Fewer or more hours</h2>
        <p>Not everyone works 40 hours. Here's the same {rate_text(h)} an hour on other schedules:</p>
{hours_table(h)}
        <h2>How long does it take to earn…</h2>
        <p>At {rate_text(h)} an hour you earn about <strong>{money(h / 60, cents=True)} a minute</strong>, so it takes:</p>
{time_to_earn_list(h)}
        <h2>Nearby wages</h2>
        <nav class="chips">{neighbours(all_hourly, h, lambda v: (rate_text(v) + "/hr", slug_for_rate(v)), "/hourly/")}</nav>
        <p>Or flip it around: <a href="/salary/{closest_salary}/">{money(closest_salary)} a year is how much an hour?</a></p>
"""
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": title, "description": description, "url": SITE + path}
    write(path, shell(path=path, title=title, description=description, body=body, json_ld=ld,
                      breadcrumbs=[("Live Salary", "/"), ("Hourly wages", "/hourly/"), (f"{rate_text(h)} an hour", path)]))
    return path


# ---------- Salary pages ----------

def salary_page(a, all_annual, hourly_values):
    h = a / HOURS_PER_YEAR
    path = f"/salary/{a}/"
    title = f"{money(a)} a Year Is How Much an Hour? {money(h, cents=True)} | Live Salary"
    net, _, _ = take_home(a)
    description = (f"{money(a)} a year is {money(h, cents=True)} an hour at {HOURS_PER_WEEK} hours a week — {money(a / 12)} a month, "
                   f"{money(a / 26)} every two weeks, about {money(net)} a year after federal tax. See it add up live.")
    closest_hourly = min(hourly_values, key=lambda v: abs(v - h))
    body = f"""
        <h1>{money(a)} a year is <span class="hl">{money(h, cents=True)}</span> an hour</h1>
        <p class="lede">Based on a {HOURS_PER_WEEK}-hour week for {WEEKS_PER_YEAR} weeks ({HOURS_PER_YEAR:,} working hours). That's {money(a / 12)} a month before tax, or about <strong>{money(net / 12)}</strong> a month after federal taxes.</p>
{counter_block(h, label=f"Earning {money(a)}/yr since you opened this page")}
        <h2>{money(a)} a year, broken down</h2>
{breakdown_table(h)}
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
        <h2>Nearby salaries</h2>
        <nav class="chips">{neighbours(all_annual, a, lambda v: (money(v), str(v)), "/salary/")}</nav>
        <p>Or flip it around: <a href="/hourly/{slug_for_rate(closest_hourly)}/">{rate_text(closest_hourly)} an hour is how much a year?</a></p>
"""
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": title, "description": description, "url": SITE + path}
    write(path, shell(path=path, title=title, description=description, body=body, json_ld=ld,
                      breadcrumbs=[("Live Salary", "/"), ("Salaries", "/salary/"), (f"{money(a)} a year", path)]))
    return path


# ---------- Earner pages (people and occupations) ----------

def earner_page(e, kind, source, all_earners):
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
                       f"{money(annual / 12)} a month. See it add up second by second.")
        h1 = f"A {name.lower()} earns about <span class=\"hl\">{money(per_hour_working, cents=True)}</span> an hour"
        lede = (f"The median annual wage for {e['plural']} in the US is about <strong>{money(annual)}</strong> ({source}). Over a standard "
                f"{HOURS_PER_WEEK}-hour week that works out to {money(per_hour_working, cents=True)} an hour, {money(annual / 12)} a month, or {money(per_hour_working * 8)} a day.")
        label = f"A {name.lower()} earning the median wage, since you opened this page"
        mode = "session"
    rate_for_counter = per_second * 3600 if is_person else per_hour_working
    median_time = duration(US_MEDIAN_ANNUAL / per_second) if is_person else None

    extras = ""
    if is_person:
        extras = f"""
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
        extras = f"""
        <h2>{name} pay, broken down</h2>
{breakdown_table(per_hour_working)}
        <h2>How it compares</h2>
{context_paragraph(per_hour_working)}
        <h2>How long does a {name.lower()} work to earn…</h2>
{time_to_earn_list(per_hour_working)}
        <p class="fine">Source: {escape(source)}. Half of {e['plural']} earn more than the median and half earn less; pay varies a lot by state, employer and experience.</p>"""

    others = "".join(f'<a href="/earns/{o["slug"]}/">{escape(o["name"])}</a>' for o in all_earners if o["slug"] != e["slug"])[:12 * 200]
    body = f"""
        <h1>{h1}</h1>
        <p class="lede">{lede}</p>
{counter_block(rate_for_counter, label=label, mode=mode)}
{extras}
        <h2>More earners</h2>
        <nav class="chips">{others}</nav>
"""
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": title, "description": description, "url": SITE + path}
    write(path, shell(path=path, title=title, description=description, body=body, json_ld=ld,
                      breadcrumbs=[("Live Salary", "/"), ("Who earns what", "/earns/"), (name, path)]))
    return path


# ---------- Hubs ----------

def hub(path, title, description, h1, lede, sections, crumb):
    body = f"<h1>{h1}</h1>\n<p class=\"lede\">{lede}</p>\n" + "\n".join(sections)
    write(path, shell(path=path, title=title, description=description, body=body,
                      breadcrumbs=[("Live Salary", "/"), (crumb, path)]))
    return path


def main():
    wages = json.load(open(os.path.join(DATA, "wages.json")))
    people = json.load(open(os.path.join(DATA, "people.json")))
    occupations = json.load(open(os.path.join(DATA, "occupations.json")))
    hourly_values = sorted(wages["hourly"])
    annual_values = sorted(wages["annual"])

    for d in ("hourly", "salary", "earns"):
        shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)

    paths = []
    for h in hourly_values:
        paths.append(hourly_page(h, hourly_values, annual_values))
    for a in annual_values:
        paths.append(salary_page(a, annual_values, hourly_values))

    all_people = [dict(p, group=g) for g in people["groups"] for p in g["people"]]
    all_earners = all_people + occupations["occupations"]
    for g in people["groups"]:
        for p in g["people"]:
            paths.append(earner_page(p, "person", g["source"], all_earners))
    for o in occupations["occupations"]:
        paths.append(earner_page(o, "occupation", occupations["source"], all_earners))

    paths.append(hub("/hourly/", "Hourly Wage to Salary: What Each Hourly Rate Earns Per Year | Live Salary",
                     "Pick an hourly wage to see what it earns per year, month and week, after tax, and watch it add up live.",
                     "What does an hourly wage earn per year?",
                     f"Pick a rate. Every page shows yearly, monthly, weekly and daily pay at {HOURS_PER_WEEK} hours a week, a rough after-tax figure, and a live counter.",
                     ["<nav class=\"chips big\">" + "".join(f'<a href="/hourly/{slug_for_rate(h)}/">{rate_text(h)}</a>' for h in hourly_values) + "</nav>"],
                     "Hourly wages"))
    paths.append(hub("/salary/", "Salary to Hourly: What Each Annual Salary Pays Per Hour | Live Salary",
                     "Pick an annual salary to see the hourly, monthly and biweekly equivalent, after tax, and watch it add up live.",
                     "What does a salary work out to per hour?",
                     f"Pick a salary. Each page converts it to an hourly rate at {HOURS_PER_WEEK} hours a week, breaks it down by period, and shows it ticking up live.",
                     ["<nav class=\"chips big\">" + "".join(f'<a href="/salary/{a}/">{money(a)}</a>' for a in annual_values) + "</nav>"],
                     "Salaries"))
    people_sections = []
    for g in people["groups"]:
        cards = "".join(
            f'<a class="card" href="/earns/{p["slug"]}/"><strong>{escape(p["name"])}</strong><span>{escape(p["role"])}</span><em>{short_money(p["annual"])}/yr · {money(p["annual"] / 31557600, cents=True)}/sec</em></a>'
            for p in g["people"])
        people_sections.append(f"<h2>{escape(g['title'])}</h2>\n<div class=\"cards\">{cards}</div>")
    occ_cards = "".join(
        f'<a class="card" href="/earns/{o["slug"]}/"><strong>{escape(o["name"])}</strong><span>US median</span><em>{money(o["annual"])}/yr · {money(o["annual"] / HOURS_PER_YEAR, cents=True)}/hr</em></a>'
        for o in sorted(occupations["occupations"], key=lambda o: -o["annual"]))
    people_sections.append(f"<h2>Occupations</h2>\n<div class=\"cards\">{occ_cards}</div>")
    paths.append(hub("/earns/", "Who Earns What: Athletes, Celebrities, CEOs and Everyday Jobs, Per Second | Live Salary",
                     "See how fast the world's highest-paid athletes, musicians and CEOs earn — per second, minute and hour — next to the median pay for everyday jobs.",
                     "Who earns what, per second",
                     "The highest-paid people on earth, and the median pay for ordinary jobs, each with a live counter.",
                     people_sections, "Who earns what"))

    # Sitemap: homepage first, then every generated page.
    urls = [("/", TODAY)] + [(p, TODAY) for p in paths]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p, mod in urls:
        xml.append(f"  <url><loc>{SITE}{p}</loc><lastmod>{mod}</lastmod></url>")
    xml.append("</urlset>")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(xml) + "\n")

    print(f"Generated {len(paths)} pages and sitemap.xml with {len(urls)} URLs.")


if __name__ == "__main__":
    main()
