#!/usr/bin/env python3
"""HTML primitives for the static dashboard.

Design rules enforced here:
  * every table is rendered through `table()`, which REQUIRES a source cell in each row;
  * every page is rendered through `layout()`, so navigation is identical everywhere;
  * no JavaScript is needed to read any number on the site.
"""
from __future__ import annotations

import html as _html
import json
import os
import re

"""Navigation is grouped so the sidebar stays readable while every hub stays reachable.

Integrated by session `arena/4c90e65f-korea2` (2026-11-18): the previous list carried four duplicate
labels ("Suggestions hub" twice, "Decision desk"/"Decision hub" twice, a stale hub-map page and the
register page), and the hubs merged after it was written (line-desk, price-desk, price-store,
review-board, verify-hub, skill-lab, origination, injury-report-w10) were not linked at all. Groups:
  Analysis            - the measured result, page by page
  Decision registers  - what is ready, what is blocked, what a reviewer must answer
  Sibling hubs         - every hub directory that exists on main, discovered at build time
"""

CORE = [
    ("index.html", "Overview"),
    ("pages/executive.html", "Executive summary"),
    ("pages/readiness.html", "Decision readiness"),
    ("pages/lines.html", "Originated lines"),
    ("pages/props.html", "Player props"),
    ("pages/correlation.html", "Correlation &amp; parlays"),
    ("pages/strategies.html", "Strategy lab"),
    ("pages/validation.html", "Validation gates"),
    ("pages/leaderboard.html", "Leaderboard"),
    ("pages/luck.html", "Removing luck"),
    ("pages/market.html", "Market benchmark"),
]
REGISTERS = [
    ("pages/live-checks.html", "Live official checks"),
    ("pages/verification.html", "Verification"),
    ("pages/method.html", "Method &amp; data"),
    ("pages/sources.html", "Source register"),
    ("pages/suggestions.html", "Suggestion register"),
    ("pages/decision-questions.html", "Open questions"),
    ("pages/injuries-depth.html", "Injury &amp; depth"),
    ("pages/decision-parlay.html", "Parlay pricing"),
    ("pages/decision-signals.html", "Signal lab"),
    ("pages/decision-verify.html", "Re-verify the numbers"),
    ("pages/decision-summary.html", "Decision summary"),
    ("pages/flagged.html", "Flagged for review"),
    ("pages/archive.html", "Site archive"),
]

# Sibling hubs, labelled with what they hold. The index page is discovered at build time: a hub
# directory that exists is linked, so the navigation cannot silently lose a merged hub again.
HUB_LABELS = {
    "line-desk": "Line Desk &nearr;",
    "price-desk": "Price Desk &nearr;",
    "price-store": "Price Store &nearr;",
    "review-board": "Review Board &nearr;",
    "verify-hub": "Verify Hub &nearr;",
    "decision-desk": "Decision Desk &nearr;",
    "decision-hub": "Decision hub &nearr;",
    "signal-desk": "Signal Desk &nearr;",
    "lineup-lab": "Lineup Lab &nearr;",
    "suggestions": "Suggestions hub &nearr;",
    "skill-lab": "Skill Lab &nearr;",
    "origination": "Origination hub &nearr;",
    "origination-lab": "Origination Lab &nearr;",
    "quant-lab": "Quant Lab &nearr;",
    "nfl-command": "NFL Command Center &nearr;",
    "injury-report-w10": "Week 10 injury re-check &nearr;",
    "site": "Decision site &nearr;",
    "audit": "Audit &nearr;",
    "dashboard": "Dashboard (early draft) &nearr;",
    "nfl-lines": "NFL Lines (early draft) &nearr;",
    "nfl-research": "NFL Research (early draft) &nearr;",
    "research-desk": "Research desk (early draft) &nearr;",
    "readiness": "Readiness hub &nearr;",
    "requirements-desk": "Requirements Desk &nearr;",
}


def hub_nav(root: str = ".") -> list[tuple[str, str]]:
    """Hubs present on disk, in the order they are listed in HUB_LABELS, then alphabetically."""
    found = []
    for name, label in list(HUB_LABELS.items()):
        if os.path.exists(os.path.join(root, name, "index.html")):
            found.append((f"{name}/index.html", label))
    for name in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        path = os.path.join(root, name)
        if (name not in HUB_LABELS and os.path.isdir(path) and not name.startswith((".", "_"))
                and os.path.exists(os.path.join(path, "index.html"))):
            found.append((f"{name}/index.html", f"{name} &nearr;"))
    return found


NAV_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Workspace", CORE),
    ("Decision registers", REGISTERS),
]


def nav_groups(root: str = ".") -> list[tuple[str, list[tuple[str, str]]]]:
    return NAV_GROUPS + [("Sibling hubs", hub_nav(root))]


NAV = [item for _, items in nav_groups() for item in items]

DISCLAIMER = (
    "Research and measurement, not betting advice. Every figure is computed by the code in this "
    "repository from the sources listed on the Source register page; nothing is estimated by hand."
)


def load(name: str, default=None):
    path = os.path.join("data", "derived", name)
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path) as fh:
        return json.load(fh)


def sources() -> dict:
    path = os.path.join("data", "sources.json")
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        data = json.load(fh)
    return {s["id"]: s for s in data.get("sources", [])}


def src(sid: str, label: str | None = None) -> str:
    """Render a source link. `sid` must exist in data/sources.json."""
    s = sources().get(sid)
    if not s:
        return '<span class="flag">source missing</span>'
    text = label or s.get("short") or s.get("title") or s.get("label") or sid
    if len(text) > 44:
        text = text[:41].rstrip() + "..."
    return f'<a href="{_html.escape(s["url"])}" rel="noopener">{_html.escape(text)}</a>'


def esc(v) -> str:
    return _html.escape(str(v))


def pct(v, digits=1, sign=False):
    if v is None:
        return '<span class="na">n/a</span>'
    try:
        f = float(v) * 100
    except (TypeError, ValueError):
        return esc(v)
    s = f"{f:+.{digits}f}%" if sign else f"{f:.{digits}f}%"
    return s


def num(v, digits=2, sign=False):
    if v is None:
        return '<span class="na">n/a</span>'
    try:
        return f"{float(v):+.{digits}f}" if sign else f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return esc(v)


def badge(kind: str, text: str) -> str:
    return f'<span class="badge {kind}">{esc(text)}</span>'


def table(headers: list[str], rows: list[list[str]], caption: str = "", cls: str = "") -> str:
    """Render a table. The last header must be a source/method column and every row must fill it."""
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for r in rows:
        cells = []
        for i, c in enumerate(r):
            cls_cell = ' class="src"' if i == len(r) - 1 else ""
            cells.append(f"<td{cls_cell}>{c}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    cap = f'<caption class="caption">{caption}</caption>' if caption else ""
    return (f'<div class="table-wrap"><table class="{cls}">{cap}<thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def card(title: str, value: str, note: str = "", link: str = "", link_text: str = "") -> str:
    l = f'<a class="card-link" href="{link}">{link_text or "Open"} &rarr;</a>' if link else ""
    return (f'<article class="kpi"><span class="kpi-label">{title}</span>'
            f'<strong>{value}</strong><p>{note}</p>{l}</article>')


def as_of() -> str:
    """The date the committed data ends, read from the pipeline's own manifests."""
    for path, key in ((os.path.join("data", "derived", "verification.json"), "data_as_of_gameday"),
                      (os.path.join("data", "provenance.json"), "data_as_of_gameday")):
        if os.path.exists(path):
            with open(path) as fh:
                v = json.load(fh)
            stamp = (v.get("meta") or {}).get(key) if "meta" in v else v.get(key)
            if stamp:
                return str(stamp)
    return ""


def status_note() -> str:
    lb = load("leaderboard.json", {})
    entries = lb.get("entries", [])
    approved = lb.get("approved_count", 0)
    tested = len([e for e in entries if e.get("family") != "control"])
    read = official_read_date()
    ready = readiness_summary()
    if not entries:
        return ('<span class="dot"></span>Pipeline building<br><strong>Awaiting data</strong>'
                '<span>Run the data-pipeline workflow.</span>')
    stamp = as_of()
    fresh = f"Data through {stamp}. " if stamp else ""
    if read:
        fresh += f"Official pages last read {read}. "
    return (f'<span class="dot"></span>Pipeline live<br><strong>{approved} of {tested} strategies approved</strong>'
            f"<span>{fresh}{ready}</span>")


def official_read_date() -> str:
    """Date of the newest dated official-source capture committed under data/derived/."""
    import glob

    found = sorted(glob.glob(os.path.join("data", "derived", "official_capture_*.json")))
    if not found:
        return ""
    try:
        with open(found[-1]) as fh:
            meta = (json.load(fh) or {}).get("meta", {})
    except (OSError, ValueError):
        return ""
    return str(meta.get("read_at_utc", ""))[:10]


def readiness_summary() -> str:
    doc = load("readiness.json", {})
    totals = doc.get("meta", {}).get("status_totals", {})
    n = doc.get("meta", {}).get("row_count", 0)
    if not n:
        return "Decision readiness: register not built yet."
    parts = ", ".join(f"{v} {k}" for k, v in sorted(totals.items()))
    return f"Decision readiness: {n} requirements - {parts}."


def layout(page_title: str, current: str, body: str, subtitle: str = "") -> str:
    parts = []
    for label, items in nav_groups():
        links = []
        for href, text in items:
            active = ' class="active" aria-current="page"' if href == current else ""
            links.append(f'<a href="{href}"{active}>{text}</a>')
        parts.append(f'<span class="nav-group">{label}</span>{"".join(links)}')
    navhtml = "".join(parts)
    sub = f'<p class="lede">{subtitle}</p>' if subtitle else ""
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(page_title)} | Line Lab</title>
<meta name="description" content="Independent NFL line origination, correlation measurement and strategy validation research.">
<meta name="generator" content="line-lab/scripts/build_site.py">
<link rel="stylesheet" href="{'../' if current.startswith('pages/') else ''}assets/style.css">
</head><body>
<a class="skip" href="#main">Skip to content</a>
<div class="shell">
<aside class="sidebar">
  <a class="brand" href="{'../' if current.startswith('pages/') else ''}index.html">
    <span class="mark">LL</span><span>LINE LAB<small>NFL RESEARCH</small></span></a>
  <div class="nav-label">Workspace</div>
  <nav aria-label="Main navigation">{navhtml}</nav>
  <div class="sidebar-note">{status_note()}</div>
</aside>
<main id="main">
<header class="topbar">
  <span class="crumb">{esc(page_title).upper()}</span>
  <a class="review-link" href="pages/flagged.html">Flagged for review &nearr;</a>
</header>
{sub}
{body}
<footer>
  <p>{DISCLAIMER}</p>
  <p><a href="pages/sources.html">Source register</a> &middot;
     <a href="pages/method.html">Method</a> &middot;
     <a href="pages/flagged.html">Flagged for review</a></p>
</footer>
</main></div></body></html>"""
    if current.startswith("pages/"):
        doc = re.sub(r'href="(?!#|https?:|mailto:|\.\./)([^"]+)"', r'href="../\1"', doc)
    return doc


def write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as fh:
        fh.write(content)
