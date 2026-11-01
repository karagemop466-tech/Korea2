"""Shared helpers for the static site generator (no external dependencies)."""
from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DERIVED = ROOT / "data" / "derived"

RESEARCH = [
    ("index.html", "Dashboard"),
    ("lines.html", "Originated lines"),
    ("signals.html", "Signals"),
    ("strategies.html", "Leaderboard"),
    ("gates.html", "Validation gates"),
    ("parlays.html", "Parlays"),
    ("props.html", "Player props"),
    ("correlation.html", "Correlation"),
    ("luck.html", "Luck removal"),
]
META = [
    ("executive-summary.html", "Executive summary"),
    ("requirements.html", "Requirements"),
    ("data.html", "Data"),
    ("sources.html", "Sources"),
    ("methods.html", "Methods"),
    ("flagged.html", "Flagged for review"),
]
ALL_PAGES = RESEARCH + META


def load(name: str):
    return json.loads((DERIVED / name).read_text())


def e(x) -> str:
    return html.escape(str(x), quote=True)


def blank() -> str:
    return '<span class="blank" title="not confirmable from a verified source">—</span>'


def num(x, dp=2, suffix="") -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return blank()
    if isinstance(x, str):
        return e(x + suffix)
    if isinstance(x, int) or (isinstance(x, float) and float(x).is_integer() and dp == 0):
        return f"{int(x):,}{suffix}"
    return f"{x:,.{dp}f}{suffix}"


def pctp(x, dp=1, signed=True) -> str:
    """Percentage points from a fraction, coloured."""
    if x is None:
        return blank()
    v = x * 100
    cls = "pos" if v > 0 else ("neg" if v < 0 else "muted")
    sign = "+" if (signed and v > 0) else ""
    return f'<span class="{cls}">{sign}{v:.{dp}f}%</span>'


def roi(x) -> str:
    return pctp(x, 2)


def units(x) -> str:
    if x is None:
        return blank()
    cls = "pos" if x > 0 else ("neg" if x < 0 else "muted")
    return f'<span class="{cls}">{x:+.2f}u</span>'


def pill(text, kind="neutral") -> str:
    return f'<span class="pill {kind}">{e(text)}</span>'


def status_pill(status: str) -> str:
    kind = {"pass": "pass", "met": "pass", "done": "pass",
            "warn": "warn", "met with limitation": "warn", "needs review": "warn",
            "fail": "fail", "not met": "fail"}.get(status.lower(), "neutral")
    return pill(status, kind)


def src(sources: dict, ids, note: str | None = None) -> str:
    """Per-row / per-table source link strip."""
    if isinstance(ids, str):
        ids = [ids]
    parts = []
    for i in ids:
        s = sources.get(i)
        if not s:
            parts.append(e(i))
            continue
        short = i
        parts.append(f'<a href="{e(s["url"])}" title="{e(s["name"])}" '
                     f'target="_blank" rel="noopener">{e(short)}</a>')
    out = '<span class="src">' + " · ".join(parts)
    if note:
        out += f" {e(note)}"
    return out + "</span>"


def table(headers, rows, caption=None, sub=None, note=None, cls="", col_cls=None,
          source_strip=None) -> str:
    """headers: list of (label, is_numeric). rows: list of list of cell HTML."""
    head = "".join(
        f'<th class="{"n" if is_num else ""}">{e(h)}</th>' for h, is_num in headers
    )
    body = []
    for r in rows:
        cells = []
        for i, c in enumerate(r):
            cc = ""
            if col_cls and i < len(col_cls) and col_cls[i]:
                cc = col_cls[i]
            cells.append(f'<td class="{cc}">{c}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    cap = ""
    if caption:
        cap = f"<caption>{e(caption)}" + (f' <span>{sub}</span>' if sub else "") + "</caption>"
    tnote = f'<div class="tnote">{note}</div>' if note else ""
    if source_strip:
        tnote = (tnote or '<div class="tnote">') + f"{source_strip}"
        if not tnote.endswith("</div>"):
            tnote += "</div>"
    return (f'<div class="tablewrap"><table class="{cls}">{cap}<thead><tr>{head}</tr></thead>'
            f"<tbody>{''.join(body)}</tbody></table>{tnote}</div>")


def card(title, value, sub="", more=None, href=None) -> str:
    link = f'<a class="more" href="{href}">Details →</a>' if href else ""
    return (f'<div class="card"><h3>{e(title)}</h3><div class="kpi">{value}</div>'
            f'<p>{sub}</p>{link}</div>')


def note(text, kind="") -> str:
    return f'<div class="note {kind}">{text}</div>'


def bar(value, scale, kind=None) -> str:
    if value is None or scale == 0:
        return blank()
    w = max(min(abs(value) / scale * 100, 100), 0)
    cls = kind or ("pos" if value > 0 else "neg")
    return (f'<div class="bar"><div class="track"><div class="fill {cls}" '
            f'style="width:{w:.1f}%"></div></div>'
            f'<span class="lbl">{value * 100:+.1f}%</span></div>')


# --------------------------------------------------------------------------- #
# minimal markdown -> html (headings, lists, tables, bold, code, links)
# --------------------------------------------------------------------------- #
def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def md_to_html(md: str) -> str:
    out, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        if line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i])
                i += 1
            rows = [[c.strip() for c in row.strip().strip("|").split("|")] for row in block]
            rows = [r for r in rows if not all(set(c) <= set("-: ") and c for c in r)]
            if not rows:
                continue
            head, *body = rows
            th = "".join(f"<th>{_inline(c)}</th>" for c in head)
            tb = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>"
                         for r in body)
            out.append(f'<div class="tablewrap"><table><thead><tr>{th}</tr></thead>'
                       f"<tbody>{tb}</tbody></table></div>")
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{level}>{_inline(line[level:].strip())}</h{level}>")
            i += 1
            continue
        if line.startswith(("- ", "* ")):
            items = []
            while i < len(lines) and lines[i].startswith(("- ", "* ")):
                items.append(f"<li>{_inline(lines[i][2:].strip())}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        if re.match(r"^\d+\. ", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
                text = re.sub(r"^\d+\. ", "", lines[i]).strip()
                items.append("<li>" + _inline(text) + "</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue
        if line.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip("> ").strip())
                i += 1
            out.append(note(" ".join(_inline(b) for b in buf)))
            continue
        if set(line.strip()) == {"-"}:
            out.append("<hr>")
            i += 1
            continue
        buf = []
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", "- ", "* ", ">")):
            buf.append(lines[i].strip())
            i += 1
        out.append(f"<p>{_inline(' '.join(buf))}</p>")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# page shell
# --------------------------------------------------------------------------- #
def page(filename: str, title: str, lede: str, body: str, sources: dict,
         extra_head: str = "") -> str:
    def links(items):
        out = []
        for f, t in items:
            cur = ' aria-current="page"' if f == filename else ""
            out.append('<a href="' + f + '"' + cur + ">" + e(t) + "</a>")
        return "".join(out)

    main_links = links(RESEARCH)
    sub_links = links(META)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} · NFL Line Lab</title>
<meta name="description" content="{e(lede[:180])}">
<link rel="stylesheet" href="assets/style.css">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%2316233c'/%3E%3Ctext x='16' y='22' font-family='sans-serif' font-size='14' font-weight='700' fill='%23c8102e' text-anchor='middle'%3ENFL%3C/text%3E%3C/svg%3E">
{extra_head}</head>
<body>
<header class="topbar"><div class="wrap">
  <a class="brand" href="index.html"><span class="mark">NFL</span> Line Lab</a>
  <nav class="main">{main_links}</nav>
</div></header>
<div class="subnav"><div class="wrap">{sub_links}</div></div>
<main class="wrap">
<div class="page-head"><h1>{e(title)}</h1><p class="lede">{lede}</p></div>
{body}
</main>
<footer><div class="wrap">
  <div><b>NFL Line Lab</b> — line origination, signal research and a gated strategy competition.<br>
  Built from hashed open datasets; every table row carries its source id. Not betting advice.</div>
  <div><a href="sources.html">Source registry</a> · <a href="flagged.html">Flagged for review</a> ·
  <a href="methods.html">Methods</a> · <a href="requirements.html">Requirements</a></div>
</div></footer>
</body></html>
"""
