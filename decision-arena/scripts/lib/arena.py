#!/usr/bin/env python3
"""Shared primitives for the Decision Arena.

Two rules are enforced here rather than in prose:

  1. `table()` refuses to render a row that does not end in a source cell. Every number that
     is published therefore carries the page it came from, or an explicit "unverified" marker.
  2. `layout()` renders every page through one shell, so the navigation cannot drift between
     pages and a dead link is detectable by a single crawl.

Statistics are pure-stdlib so the hub rebuilds on a runner with no wheels installed.
"""
from __future__ import annotations

import html
import json
import math
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # decision-arena/
DATA = os.path.join(ROOT, "data")

# ------------------------------------------------------------------ navigation
NAV = [
    ("index.html", "Overview"),
    ("pages/executive.html", "Executive summary"),
    ("pages/prices.html", "Price snapshots"),
    ("pages/results.html", "Results feed"),
    ("pages/origination.html", "Origination"),
    ("pages/leaderboard.html", "Leaderboard"),
    ("pages/strategies.html", "Strategy lab"),
    ("pages/gates.html", "Gates &amp; demotion"),
    ("pages/correlation.html", "Correlation"),
    ("pages/depth.html", "Injuries &amp; depth"),
    ("pages/suggestions.html", "Suggestions"),
    ("pages/questions.html", "Decision questions"),
    ("pages/verification.html", "Verification"),
    ("pages/flagged.html", "Flagged for review"),
    ("pages/sources.html", "Source register"),
    ("pages/methods.html", "Methods"),
]


from string import Template as _T


def render(tmpl: str, **kw) -> str:
    """Substitute $name placeholders.

    Pages are built with $name rather than {name} on purpose: HTML and CSS are full of braces,
    and a template language that shares their syntax produces escaping bugs that look like
    content bugs. Anything missing from kw raises, so a typo cannot silently blank a section.
    """
    return _T(tmpl).substitute(**kw)


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def load(path: str, default=None):
    p = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if not os.path.exists(p):
        return {} if default is None else default
    with open(p) as fh:
        return json.load(fh)


def dump(path: str, obj) -> None:
    p = path if os.path.isabs(path) else os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        json.dump(obj, fh, indent=1, sort_keys=False)
        fh.write("\n")


def sources() -> dict:
    return {s["id"]: s for s in load("data/sources.json").get("sources", [])}


def src(sid: str, label: str | None = None, tier_note: bool = False) -> str:
    """A link to a registered source, with an honest tier marker."""
    s = sources().get(sid)
    if not s:
        raise KeyError(f"unregistered source id: {sid}")
    text = label or s.get("title") or sid
    if len(text) > 62:
        text = text[:59].rstrip() + "..."
    tag = ""
    if tier_note and s.get("tier") == "third_party":
        tag = ' <span class="tier" title="Third-party redistributor, not the league">3P</span>'
    return f'<a href="{esc(s["url"])}" rel="noopener">{esc(text)}</a>{tag}'


def blank(reason: str = "no official source") -> str:
    """The only permitted way to publish an empty value."""
    return f'<span class="blank" title="{esc(reason)}">blank &middot; {esc(reason)}</span>'


# ------------------------------------------------------------------ html shell
CSS = """
:root{--bg:#0d1117;--panel:#141a23;--panel2:#1a2230;--line:#243040;--ink:#e6edf3;--mute:#8b9bb0;
--acc:#4cc9f0;--ok:#3fb950;--warn:#d29922;--bad:#f85149;--violet:#a78bfa;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.shell{display:grid;grid-template-columns:250px minmax(0,1fr);min-height:100vh}
aside{background:#0a0f15;border-right:1px solid var(--line);padding:18px 14px;position:sticky;top:0;height:100vh;overflow:auto}
.brand{display:flex;gap:10px;align-items:center;color:var(--ink);font-weight:700;letter-spacing:.06em;font-size:13px;margin-bottom:18px}
.mark{display:grid;place-items:center;width:34px;height:34px;border-radius:9px;background:linear-gradient(135deg,var(--acc),var(--violet));color:#05121a;font-weight:800;font-size:13px}
.brand small{display:block;color:var(--mute);font-weight:500;letter-spacing:.12em;font-size:9px}
.nav-label{color:var(--mute);font-size:10px;letter-spacing:.16em;text-transform:uppercase;margin:16px 0 6px}
nav{display:flex;flex-direction:column;gap:1px}
nav a{color:#b7c3d0;padding:6px 9px;border-radius:7px;font-size:13.5px}
nav a:hover{background:var(--panel2);text-decoration:none;color:#fff}
nav a.active{background:var(--panel2);color:#fff;box-shadow:inset 2px 0 0 var(--acc)}
.side-note{margin-top:18px;padding:10px;border:1px solid var(--line);border-radius:9px;font-size:12px;color:var(--mute);background:#0c1219}
.side-note strong{color:var(--ink)}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--ok);margin-right:6px}
main{padding:0 30px 60px;max-width:1280px}
.topbar{display:flex;justify-content:space-between;align-items:center;padding:14px 0;border-bottom:1px solid var(--line);font-size:12px;color:var(--mute);letter-spacing:.1em}
.crumb{text-transform:uppercase}
.hero{padding:30px 0 12px}
.eyebrow{color:var(--acc);font-size:11px;letter-spacing:.18em;text-transform:uppercase;margin-bottom:8px}
h1{font-size:34px;line-height:1.15;margin:0 0 10px;letter-spacing:-.01em}
h1 em{color:var(--acc);font-style:normal}
.lede{color:#c2ccd8;max-width:840px;margin:0 0 8px}
h2{font-size:20px;margin:0 0 12px}h3{font-size:15px;margin:0 0 8px}
section.block{margin:26px 0}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:18px 0}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:16px 0}
@media(max-width:1000px){.shell{grid-template-columns:1fr}aside{position:static;height:auto}.grid2,.grid3{grid-template-columns:1fr}}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:18px 0}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px}
.kpi-label{color:var(--mute);font-size:11px;letter-spacing:.1em;text-transform:uppercase}
.kpi strong{display:block;font-size:24px;margin:6px 0 4px;font-variant-numeric:tabular-nums}
.kpi p{margin:0;color:#aeb9c6;font-size:12.5px}
.kpi .card-link{display:inline-block;margin-top:8px;font-size:12px}
.notice{display:flex;gap:14px;align-items:flex-start;border:1px solid var(--line);border-left:3px solid var(--acc);background:#0f1620;border-radius:10px;padding:12px 14px;margin:16px 0;font-size:13.5px;color:#c8d2de}
.notice.warn{border-left-color:var(--warn)}.notice.bad{border-left-color:var(--bad)}.notice.ok{border-left-color:var(--ok)}
.notice a{margin-left:auto;white-space:nowrap}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:13px}
caption{caption-side:top;text-align:left;padding:10px 12px;color:var(--mute);font-size:12px;border-bottom:1px solid var(--line)}
th{position:sticky;top:0;background:#101722;text-align:left;padding:9px 10px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#9fb0c3;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:8px 10px;border-bottom:1px solid #1b2330;vertical-align:top}
tbody tr:hover{background:#151d28}
td.num{text-align:right;font-variant-numeric:tabular-nums;font-family:var(--mono);white-space:nowrap}
td.src{font-size:11.5px;color:#93a4b8;max-width:280px}
.blank{color:#7d8ea3;font-style:italic;font-size:11.5px;border-bottom:1px dotted #7d8ea3}
code{font-family:var(--mono);font-size:12px;background:#101722;padding:1px 5px;border-radius:4px;border:1px solid var(--line)}
pre{background:#0b1119;border:1px solid var(--line);border-radius:10px;padding:12px;overflow:auto;font-size:12px}
.badge{display:inline-block;padding:1px 7px;border-radius:999px;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--line)}
.b-ok{background:rgba(63,185,80,.12);color:#56d364;border-color:rgba(63,185,80,.4)}
.b-warn{background:rgba(210,153,34,.12);color:#e3b341;border-color:rgba(210,153,34,.4)}
.b-bad{background:rgba(248,81,73,.12);color:#ff7b72;border-color:rgba(248,81,73,.4)}
.b-info{background:rgba(76,201,240,.12);color:#76d6f5;border-color:rgba(76,201,240,.4)}
.b-mute{background:#141c26;color:#96a6b8}
.tier{font-size:9.5px;color:#e3b341;border:1px solid rgba(210,153,34,.5);border-radius:4px;padding:0 3px;margin-left:3px;vertical-align:1px}
.ticks,.crosses{list-style:none;padding:0;margin:0}
.ticks li,.crosses li{padding:5px 0 5px 22px;position:relative;font-size:13px;border-bottom:1px solid #1b2330}
.ticks li:before{content:"\\2713";position:absolute;left:2px;color:var(--ok)}
.crosses li:before{content:"\\2715";position:absolute;left:2px;color:var(--bad)}
footer{margin-top:34px;padding-top:16px;border-top:1px solid var(--line);color:var(--mute);font-size:12px}
.skip{position:absolute;left:-9999px}
.mono{font-family:var(--mono);font-size:12px}
.small{font-size:12px;color:var(--mute)}
.tag-row{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
"""


def write_css() -> None:
    path = os.path.join(ROOT, "assets", "style.css")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("/* Decision Arena - generated from scripts/lib/arena.py; do not edit by hand */\n" + CSS)


def shell(title: str, crumb: str, body: str, active: str, subtitle: str = "") -> str:
    """Render a page through the one shell.

    `active` is the site-relative path of the page being written (e.g. "pages/prices.html"), so the
    shell can compute how to get back to the root. Nav entries are stored site-relative and are
    rewritten per page, which is what keeps a link valid from both index.html and pages/*.html.
    """
    depth = 0 if "/" not in active else active.count("/")
    up = "../" * depth

    def href(target: str) -> str:
        return up + target if target else up

    active_attr = ' class="active" aria-current="page"'
    nav = "".join(f'<a href="{href(h)}"{active_attr if h == active else ""}>{lab}</a>'
                  for h, lab in NAV)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} | Decision Arena</title>
<meta name="description" content="{esc(subtitle or "Independent NFL line origination, price snapshots, verified results and a gated signal competition.")}">
<link rel="stylesheet" href="{up}assets/style.css">
</head><body>
<a class="skip" href="#main">Skip to content</a>
<div class="shell">
<aside class="sidebar">
  <a class="brand" href="{href("index.html")}"><span class="mark">DA</span><span>DECISION ARENA<small>NFL SIGNAL RESEARCH</small></span></a>
  <div class="nav-label">Workspace</div>
  <nav aria-label="Main navigation">{nav}</nav>
  <div class="side-note"><span class="dot"></span><strong>No strategy is live.</strong>
  <div>Signals and staking are reported separately; every value is blank unless a source states it.</div></div>
</aside>
<main id="main">
<header class="topbar"><span class="crumb">{crumb}</span>
<a class="review-link" href="{href("pages/flagged.html")}">Flagged for review &nearr;</a></header>
{body}
<footer>
  <p>Research and measurement, not betting advice. Values are computed by the code in this repository
  from the sources on the <a href="{href("pages/sources.html")}">source register</a>;
  anything that could not be confirmed from a source is left blank and listed on
  <a href="{href("pages/flagged.html")}">Flagged for review</a>.</p>
</footer>
</main></div></body></html>"""


# ------------------------------------------------------------------ table with source enforcement
def table(headers: list[str], rows: list[list[str]], caption: str = "", cls: str = "", src_header: str = "Source") -> str:
    """Render a table. Each row's LAST cell must be a source cell.

    A source cell is accepted when it contains a link to https:// (a registered source) or an
    explicit `blank <span class=...>` marker produced by `blank()`. Anything else raises, so an
    unsourced number cannot reach a page even by mistake.
    """
    out = []
    for i, r in enumerate(rows):
        if not r:
            raise ValueError(f"row {i} is empty in table {caption!r}")
        cell = r[-1]
        ok = ("https://" in cell and "<a " in cell) or 'class="blank"' in cell
        if not ok:
            raise ValueError(f"row {i} of {caption!r} has no source cell: {cell[:90]!r}")
        out.append(r)
    head = "".join(f"<th>{h}</th>" for h in headers[:-1]) + f"<th>{esc(src_header)}</th>"
    body = "".join(
        "<tr>" + "".join(f'<td class="{"num" if j and _isnum(c) else ""}">{c}</td>' for j, c in enumerate(r[:-1]))
        + f'<td class="src">{r[-1]}</td></tr>'
        for i, r in enumerate(out)
    )
    cap = f'<caption class="caption">{caption}</caption>' if caption else ""
    return f'<div class="table-wrap"><table class="{cls}">{cap}<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _isnum(c: str) -> bool:
    txt = c.replace("<", "").replace(">", "")
    txt = txt.replace("&minus;", "-").replace("&nbsp;", " ").strip()
    for ch in ("%", ",", "\u2212", "+"):
        txt = txt.replace(ch, "")
    try:
        float(txt)
        return True
    except ValueError:
        return False


def kpi(label: str, value: str, note: str, link_href: str = "", link_text: str = "") -> str:
    lk = f'<a class="card-link" href="{esc(link_href)}">{esc(link_text)} &rarr;</a>' if link_href else ""
    return f'<article class="kpi"><span class="kpi-label">{esc(label)}</span><strong>{value}</strong><p>{note}</p>{lk}</article>'


def notice(text: str, kind: str = "", link: str = "", link_text: str = "") -> str:
    lk = f'<a href="{esc(link)}">{esc(link_text)} &rarr;</a>' if link else ""
    return f'<div class="notice {kind}"><span class="dot"></span><div>{text}</div>{lk}</div>'


def badge(text: str, kind: str = "mute") -> str:
    return f'<span class="badge b-{kind}">{esc(text)}</span>'


def fmt(x, nd: int = 2, dash: str = "&mdash;") -> str:
    if x is None or x == "":
        return dash
    try:
        return f"{x:,.{nd}f}"
    except (TypeError, ValueError):
        return esc(x)


def pct(x, nd: int = 1, dash: str = "&mdash;") -> str:
    if x is None or x == "":
        return dash
    return f"{x * 100:,.{nd}f}%"


# ------------------------------------------------------------------ statistics (stdlib only)
def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Inverse standard normal (Acklam's approximation, |rel err| < 1.2e-9)."""
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def two_sided_p(z: float) -> float:
    return 2.0 * (1.0 - norm_cdf(abs(z)))


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def fisher_ci(r: float, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Fisher z confidence interval for a correlation (NIST/SEMATECH method)."""
    if n <= 3 or abs(r) >= 1.0:
        return (math.nan, math.nan)
    zr = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    return (math.tanh(zr - z * se), math.tanh(zr + z * se))


def corr_p(r: float, n: int) -> float:
    """Two-sided p for Pearson r under the null rho=0 (t approximation)."""
    if n <= 2 or abs(r) >= 1.0:
        return 0.0
    t = r * math.sqrt((n - 2) / (1 - r * r))
    # Student-t survival function via the incomplete beta is overkill; use the normal limit for
    # large n and a t-to-normal correction for small n (documented in methods.html).
    if n > 400:
        return two_sided_p(t)
    df = n - 2
    # Cornish-Fisher style expansion of the t quantile back to a z scale
    return two_sided_p(t * (1 - 1 / (4 * df)) / math.sqrt(1 + t * t / (2 * df)))


def pearson(xs: list[float], ys: list[float]) -> tuple[float, int]:
    pairs = [(a, b) for a, b in zip(xs, ys) if a is not None and b is not None
             and not (isinstance(a, float) and math.isnan(a)) and not (isinstance(b, float) and math.isnan(b))]
    n = len(pairs)
    if n < 3:
        return (math.nan, n)
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    syy = sum((p[1] - my) ** 2 for p in pairs)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    if sxx <= 0 or syy <= 0:
        return (math.nan, n)
    return (sxy / math.sqrt(sxx * syy), n)


def bh_qvalues(pvals: list[float]) -> list[float]:
    """Benjamini-Hochberg adjusted q-values (monotone)."""
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    q = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        val = pvals[i] * m / rank
        prev = min(prev, val)
        q[i] = min(1.0, prev)
    return q


def bootstrap_mean_ci(vals: list[float], n_boot: int = 2000, seed: int = 20261114, alpha: float = 0.05):
    if not vals:
        return (math.nan, math.nan)
    rnd = random.Random(seed)
    n = len(vals)
    means = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += vals[rnd.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int((alpha / 2) * n_boot)]
    hi = means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return (lo, hi)


def deflated_sharpe_p(returns: list[float], n_trials: int, seed: int = 20261114) -> float:
    """Best-of-N luck correction (Bailey & Lopez de Prado 2014, approximation).

    A strategy picked because it looked best among N variants must clear a higher bar than one
    specified in advance. The expected maximum Sharpe of N independent zero-skill strategies is
    approximated, then compared with the observed Sharpe on the same per-bet scale.
    """
    n = len(returns)
    if n < 30 or n_trials < 1:
        return math.nan
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    if var <= 0:
        return math.nan
    sd = math.sqrt(var)
    sr = mean / sd                       # per-bet Sharpe
    g = 0.5772156649                     # Euler-Mascheroni
    if n_trials == 1:
        exp_max = 0.0
    else:
        exp_max = (1 - g) * norm_ppf(1 - 1 / n_trials) + g * norm_ppf(1 - 1 / (n_trials * math.e))
    # spread of the maximum under the null, in per-bet Sharpe units
    se = math.sqrt((1 - 0 + 0.5 * sr ** 2) / (n - 1))
    z = (sr - exp_max * se) / se
    return 1.0 - norm_cdf(z)


def power_n(p0: float, p1: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """Bets needed to detect a true rate p1 against a null p0, two-sided, normal approximation."""
    z_a = norm_ppf(1 - alpha / 2)
    z_b = norm_ppf(power)
    num = (z_a * math.sqrt(p0 * (1 - p0)) + z_b * math.sqrt(p1 * (1 - p1))) ** 2
    return int(math.ceil(num / (p1 - p0) ** 2))


def american_to_decimal(ml: float) -> float:
    return 1 + (ml / 100.0 if ml > 0 else 100.0 / abs(ml))


def american_to_prob(ml: float) -> float:
    """Implied probability of an American price, vig included."""
    return 100.0 / (ml + 100.0) if ml > 0 else abs(ml) / (abs(ml) + 100.0)


def prob_to_american(p: float) -> float:
    if p <= 0 or p >= 1:
        return math.nan
    return round((100.0 * (1 - p) / p) if p < 0.5 else -(100.0 * p / (1 - p)), 1)


def prob_to_spread_prob(margin_mean: float, sigma: float, line: float) -> float:
    """P(home margin > line) under a normal margin model (push ignored)."""
    if sigma <= 0:
        return math.nan
    return 1.0 - norm_cdf((line - margin_mean) / sigma)
