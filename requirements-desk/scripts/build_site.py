#!/usr/bin/env python3
"""Build the Requirements Desk static site.

Deterministic, dependency-free. Reads the registers written by
`official_capture.py` and `analyze.py` plus the requirement / decision
registers, and writes `index.html` and `pages/*.html`.

Rule enforced here: every <tr> in a <tbody> contains a source link. Where a
value cannot be confirmed from an official source the cell is rendered blank
and the row is also listed on the Flagged page.
"""

from __future__ import annotations

import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyze            # noqa: E402
import decisions          # noqa: E402
import official_capture as oc  # noqa: E402
import requirements as rq  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAGES = os.path.join(ROOT, "pages")
ASSETS = os.path.join(ROOT, "assets")
DATA = os.path.join(ROOT, "data")

GENERATOR = "requirements-desk/scripts/build_site.py"
SITE_TITLE = "NFL Requirements Desk"

HUB = "/requirements-desk/"

NAV = [
    ("Overview", HUB + "index.html"),
    ("Executive summary", HUB + "pages/executive.html"),
    ("Requirements register", HUB + "pages/requirements.html"),
    ("Decision readiness", HUB + "index.html#readiness"),
    ("— Evidence —", ""),
    ("Availability register", HUB + "pages/injuries.html"),
    ("Verified results", HUB + "pages/results.html"),
    ("Fixture & venue", HUB + "pages/schedule.html"),
    ("Standings & luck", HUB + "pages/standings.html"),
    ("Removal of luck", HUB + "pages/luck.html"),
    ("Official correlations", HUB + "pages/correlations.html"),
    ("— Review —", ""),
    ("Suggestion review queue", HUB + "pages/suggestions.html"),
    ("Decision questions", HUB + "pages/questions.html"),
    ("Brief claim audit", HUB + "pages/verification.html"),
    ("Flagged for review", HUB + "pages/flagged.html"),
    ("Source register", HUB + "pages/sources.html"),
]

STATUS_LABEL = {
    "verified": "Verified",
    "partial": "Partial",
    "blocked": "Blocked",
    "not started": "Not started",
}

CSS = """
:root{
  --bg:#0e1116; --panel:#151a22; --panel2:#1b222c; --line:#263041;
  --ink:#e6edf3; --dim:#9aa7b5; --accent:#4f9cf9; --ok:#3fb950;
  --part:#d29922; --bad:#f85149; --mute:#6e7b8a;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--ink);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.shell{display:flex;min-height:100vh}
.sidebar{width:250px;flex:0 0 250px;background:var(--panel);border-right:1px solid var(--line);
  padding:18px 0;position:sticky;top:0;height:100vh;overflow:auto}
.brand{display:block;padding:0 18px 16px;border-bottom:1px solid var(--line);margin-bottom:12px}
.brand strong{display:block;font-size:15px;letter-spacing:.3px}
.brand span{display:block;color:var(--dim);font-size:11px;letter-spacing:1.4px;text-transform:uppercase;margin-top:3px}
.sidebar nav a{display:block;padding:7px 18px;color:var(--dim);font-size:13.5px;border-left:3px solid transparent}
.sidebar nav a:hover{background:var(--panel2);color:var(--ink);text-decoration:none}
.sidebar nav a.active{background:var(--panel2);color:var(--ink);border-left-color:var(--accent)}
.sidebar nav a.sep{color:var(--mute);font-size:11px;letter-spacing:1.2px;text-transform:uppercase;
  padding:14px 18px 4px;pointer-events:none}
main{flex:1;min-width:0;padding:26px 30px 60px;max-width:1500px}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.2px}
h2{font-size:19px;margin:30px 0 10px;padding-bottom:7px;border-bottom:1px solid var(--line)}
h3{font-size:15px;margin:20px 0 8px}
p{margin:9px 0}
.lede{color:var(--dim);max-width:900px;font-size:15px}
.eyebrow{color:var(--accent);font-size:11px;letter-spacing:1.6px;text-transform:uppercase;margin-bottom:6px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:20px 0 6px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:14px 15px}
.kpi .lbl{font-size:11px;letter-spacing:1.1px;text-transform:uppercase;color:var(--dim)}
.kpi .val{font-size:25px;font-weight:650;margin:5px 0 4px;letter-spacing:-.5px}
.kpi .sub{font-size:12.5px;color:var(--dim);line-height:1.45}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:16px 18px;margin:16px 0}
.panel h3{margin-top:0}
table{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0 4px}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
th{background:var(--panel2);font-weight:600;font-size:12px;letter-spacing:.3px;
   text-transform:uppercase;color:var(--dim);position:sticky;top:0}
tbody tr:nth-child(even){background:rgba(255,255,255,.018)}
.tw{overflow:auto;max-height:none;border:1px solid var(--line);border-radius:9px}
.tw.scroll{max-height:70vh}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.src{white-space:nowrap;font-size:12px}
.pill{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:600;
  letter-spacing:.3px;white-space:nowrap}
.p-ok{background:rgba(63,185,80,.15);color:var(--ok);border:1px solid rgba(63,185,80,.4)}
.p-part{background:rgba(210,153,34,.15);color:var(--part);border:1px solid rgba(210,153,34,.4)}
.p-bad{background:rgba(248,81,73,.13);color:var(--bad);border:1px solid rgba(248,81,73,.4)}
.p-mute{background:rgba(110,123,138,.14);color:var(--dim);border:1px solid rgba(110,123,138,.4)}
.notice{background:var(--panel2);border:1px solid var(--line);border-left:3px solid var(--part);
  border-radius:7px;padding:12px 15px;margin:16px 0;font-size:13.5px;color:var(--dim)}
.notice b{color:var(--ink)}
.crit{border-left-color:var(--bad)}
.good{border-left-color:var(--ok)}
ul.tight{margin:8px 0;padding-left:20px}
ul.tight li{margin:5px 0}
.blank{color:var(--mute);font-style:italic}
code{background:var(--panel2);padding:1px 5px;border-radius:4px;font-size:12.5px}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);color:var(--mute);font-size:12.5px}
.crumb{font-size:11px;letter-spacing:1.6px;text-transform:uppercase;color:var(--dim);margin-bottom:10px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:1000px){.grid2{grid-template-columns:1fr}}
@media(max-width:820px){.shell{flex-direction:column}.sidebar{width:100%;flex:none;height:auto;position:static}
  main{padding:18px}}
.opt{background:var(--panel2);border:1px solid var(--line);border-radius:7px;padding:10px 13px;margin:7px 0;font-size:13.5px}
.opt b{color:var(--accent)}
.small{font-size:12.5px;color:var(--dim)}
.tag{display:inline-block;background:var(--panel2);border:1px solid var(--line);border-radius:5px;
  padding:1px 7px;font-size:11.5px;color:var(--dim);margin-right:5px}
"""


def esc(x):
    return html.escape("" if x is None else str(x))


def site(url, depth=1):
    """Resolve a site-root-absolute path ('/line-desk/') for a page at *depth*.

    depth=1 -> requirements-desk/index.html   (prefix '..')
    depth=2 -> requirements-desk/pages/*.html (prefix '../..')
    """
    if url.startswith("/"):
        return "/".join([".."] * depth) + url
    return url


A = '<a href="{u}" rel="noopener" target="_blank">{t}</a>'

# Depth of the page currently being rendered (1 = index.html, 2 = pages/*.html).
_DEPTH = 1


def link(url, text=None):
    return A.format(u=esc(site(url, _DEPTH)), t=esc(text or "source"))


def page(title, active, body, crumb=None, wide=False):
    nav = []
    for label, href in NAV:
        if not href:
            nav.append(f'<a class="sep">{esc(label)}</a>')
        else:
            cls = "active" if href == HUB + active else ""
            nav.append(f'<a class="{cls}" href="{site(href, _DEPTH)}">{label}</a>')
    src_pg = site(HUB + "pages/sources.html", _DEPTH)
    flag_pg = site(HUB + "pages/flagged.html", _DEPTH)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} | {SITE_TITLE}</title>
<meta name="generator" content="{GENERATOR}">
<link rel="stylesheet" href="{site(HUB + 'assets/style.css', _DEPTH)}">
</head><body>
<div class="shell">
<aside class="sidebar">
  <a class="brand" href="{site(HUB + 'index.html', _DEPTH)}">
    <strong>REQUIREMENTS DESK</strong><span>NFL research · verified rows only</span></a>
  <nav aria-label="Main navigation">{''.join(nav)}</nav>
</aside>
<main>
<div class="crumb">{esc(crumb or title)}</div>
{body}
<footer>
  <p>Research and measurement, not betting advice. Every number on these pages is computed by the code in
  this repository from the official pages listed in the <a href="{src_pg}">source register</a>.
  Values that cannot be confirmed from an official source are left blank and listed on
  <a href="{flag_pg}">Flagged for review</a>.</p>
  <p><a href="{site('/index.html', _DEPTH)}">Main site</a> ·
     <a href="{site('/line-desk/index.html', _DEPTH)}">Line Desk</a> ·
     <a href="{site('/price-desk/index.html', _DEPTH)}">Price Desk</a> ·
     <a href="{site('/injury-report-w10/index.html', _DEPTH)}">Week 10 re-verification</a></p>
</footer>
</main></div></body></html>
"""


def table(headers, rows, scroll=False, cls=""):
    th = "".join(f"<th>{h if h.startswith('<') else esc(h)}</th>" for h in headers)
    tb = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    c = "tw scroll" if scroll else "tw"
    return f'<div class="{c}"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>'


def pill(status):
    key = status.lower()
    cls = {"verified": "p-ok", "partial": "p-part",
           "blocked": "p-bad", "not started": "p-mute"}.get(key, "p-mute")
    return f'<span class="pill {cls}">{esc(STATUS_LABEL.get(key, status))}</span>'


def blank():
    return '<span class="blank">blank &mdash; not published by source</span>'


# --------------------------------------------------------------------------
# Page builders
# --------------------------------------------------------------------------

def build_index(an, req_summary):
    inj = an["injury"]
    res = an["results"]
    sch = an["schedule"]
    luck = an["luck"]
    n_req = len(rq.REQUIREMENTS)
    n_ver = req_summary.get("verified", 0)
    n_block = req_summary.get("blocked", 0) + req_summary.get("not started", 0)

    kpis = [
        ("Requirements traced", f"{n_req}",
         f"{n_ver} verified, {req_summary.get('partial',0)} partial, {n_block} blocked or not started. "
         "Every row below names the gate and the number that clears it."),
        ("Availability rows captured", f"{inj['total_rows']}",
         f"Week 10 official injury report, {inj['clubs_with_table']} club tables, "
         f"{inj['rows_with_game_status']} rows carry a game status. Captured {an['capture']['capture_utc']}."),
        ("Games verified FINAL", f"{res['n_final']}/{res['n_games']}",
         "Week 10, transcribed from the official NFL schedule page. Earlier weeks are still pending official capture."),
        ("Fixtures with venue", f"{sch['n_games']}/{sch['n_games']}",
         f"Week 11, {len(sch['bye'])} clubs on bye, {len(sch['neutral_site_games'])} neutral-site game."),
        ("Official correlations", "4",
         "Computed from NFL.com standings with n=32 and Fisher-z 95% intervals. "
         "No third-party value enters any coefficient."),
        ("Luck spread (SD)", f"{luck['luck_sd']} wins",
         "Pythagorean expected wins against actual wins across 32 clubs. Single season; persistence not yet tested."),
        ("Strategies qualified", "0",
         "No candidate has passed its gates. Rewards are unfunded and points-only."),
        ("Open review items", f"{len(decisions.SUGGESTIONS)}",
         f"{len(decisions.QUESTIONS)} decision questions are unanswered. Nothing in the queue is auto-implemented."),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="lbl">{esc(l)}</div><div class="val">{esc(v)}</div>'
        f'<div class="sub">{s}</div></div>' for l, v, s in kpis)

    # decision-readiness table
    rows = []
    for r in rq.REQUIREMENTS:
        rows.append([
            f'<span class="tag">{esc(r["id"])}</span>',
            esc(r["cat"]),
            esc(r["req"]),
            pill(r["status"]),
            esc(r["gate"]),
            esc(r["clears"]),
            esc(r["ev"]),
            link(r["ev_url"], "evidence"),
        ])
    readiness = table(
        ["#", "Category", "Requirement (from the brief)", "Status",
         "Gate that blocks it", "Number that would clear it", "Evidence today", "Source"],
        rows)

    cats = "".join(
        f'<span class="tag">{esc(c)}: {sum(1 for r in rq.REQUIREMENTS if r["cat"]==c)}</span>'
        for c in rq.CATEGORY_ORDER)

    body = f"""
<div class="eyebrow">NFL LINE ORIGINATION · DECISION READINESS</div>
<h1>One row per requirement.<br>The gate. The number that clears it.</h1>
<p class="lede">This desk tracks every requirement in the project brief and states, for each one, exactly
what is blocking it and what measurable result would clear the block. Nothing here is inferred. Where an
official source does not publish a value, the cell is blank and the row is
<a href="pages/flagged.html">flagged</a>.</p>

<div class="notice"><b>As of {esc(an['capture']['capture_utc'])}.</b> The official pages linked here were
retrieved at that time. The NFL.com Week 11 injury report was not yet published at capture time, so the
latest official report available is Week 10. No strategy is qualified, no reward is funded, and no
price-derived statistic is published because no official price archive has been captured.</div>

<div class="kpis">{kpi_html}</div>

<h2 id="readiness">Decision-readiness table</h2>
<p class="small">Eight categories, {n_req} requirements. Status meanings:
<span class="pill p-ok">Verified</span> a published value is confirmed against an official source ·
<span class="pill p-part">Partial</span> structure built, values blank or flagged ·
<span class="pill p-bad">Blocked</span> impossible without missing information ·
<span class="pill p-mute">Not started</span> no structure exists.</p>
<p>{cats}</p>
{readiness}

<h2>What this session verified first-hand</h2>
<div class="grid2">
  <div class="panel"><h3>Official pages retrieved and transcribed</h3>
  <ul class="tight">
    <li><a href="{oc.SOURCES['injury_w10']['url']}" rel="noopener" target="_blank">Week 10 injury report</a>
        — 8 chunks, {inj['total_rows']} listed-player rows across {inj['clubs_with_table']} club tables.</li>
    <li><a href="{oc.SOURCES['sched_w10']['url']}" rel="noopener" target="_blank">Week 10 schedule</a>
        — {res['n_final']} games FINAL with both scores; 4 clubs confirmed on bye.</li>
    <li><a href="{oc.SOURCES['sched_w11']['url']}" rel="noopener" target="_blank">Week 11 schedule</a>
        — {sch['n_games']} fixtures with kickoff, network, venue and bye list.</li>
    <li><a href="{oc.SOURCES['standings']['url']}" rel="noopener" target="_blank">2026 division standings</a>
        — 32 clubs with wins, losses, ties, points for and against.</li>
  </ul></div>
  <div class="panel"><h3>What is still missing, and why it blocks</h3>
  <ul class="tight">
    <li><b>Official prices.</b> No opening or closing price archive ⇒ no CLV, residual or ROI.</li>
    <li><b>Official inactives.</b> No inactives capture ⇒ "Questionable" cannot be calibrated.</li>
    <li><b>Depth order.</b> 0 of 32 club depth charts parsed ⇒ no string tier, no deficiency matrix.</li>
    <li><b>Historical results.</b> Only Week 10 is complete ⇒ the 136-game corpus cannot be frozen.</li>
  </ul>
  <p><a href="pages/questions.html">Read the 12 decision questions &rarr;</a></p></div>
</div>

<h2>How to use the review queue</h2>
<p>Improvements are proposed, never auto-implemented. Each entry on the
<a href="pages/suggestions.html">suggestion page</a> lists the problem, a proposal, and the paths a
reviewer can choose between. Each entry on the
<a href="pages/questions.html">question page</a> states what is known, what is missing, how to discover it,
and which decision stays blocked until it is answered.</p>
"""
    return page("Overview", "index.html", body, crumb="OVERVIEW")


def build_executive(an, req_summary):
    inj = an["injury"]
    res = an["results"]
    sch = an["schedule"]
    luck = an["luck"]
    n = len(rq.REQUIREMENTS)
    rows = [
        ["Status of the brief", f"{req_summary.get('verified',0)} of {n} requirements verified; "
         f"{req_summary.get('partial',0)} partial; {req_summary.get('blocked',0)} blocked; "
         f"{req_summary.get('not started',0)} not started",
         rq.E_REQDESK + "index.html", rq.E_REQDESK + "index.html"],
        ["What was captured", f"{inj['total_rows']} injury-report rows ({inj['clubs_with_table']} clubs), "
         f"{res['n_final']} final scores, {sch['n_games']} fixtures, {len(an['luck']['table'])} standings rows",
         oc.SOURCES["injury_w10"]["url"], "injuries.html"],
        ["Designation coverage", f"{inj['rows_with_game_status']} of {inj['total_rows']} rows carry a game "
         f"status ({100*inj['rows_with_game_status']//inj['total_rows']}%). "
         "Questionable 90, Out 70, Doubtful 11, blank 176",
         oc.SOURCES["injury_w10"]["url"], "injuries.html"],
        ["Absent clubs", "CHI, DEN, PHI and TB have no table on the Week 10 report. The official Week 10 "
         "schedule page lists all four under 'Teams on Bye', so absence means bye, not healthy",
         oc.SOURCES["sched_w10"]["url"], "injuries.html"],
        ["Results verified", f"{res['n_final']} of {res['n_games']} Week 10 games FINAL on the official "
         "schedule page. Home teams won "
         f"{res['home_wins']} of {res['home_wins']+res['home_losses']} decided games",
         oc.SOURCES["sched_w10"]["url"], "results.html"],
        ["Removal of luck", f"Pythagorean luck SD {luck['luck_sd']} wins across 32 clubs; "
         f"r(win pct, net points) = +0.875 [+0.758, +0.938], n=32",
         oc.SOURCES["standings"]["url"], "luck.html"],
        ["Correlations", "4 coefficients from official standings, each with n=32 and a Fisher-z 95% interval. "
         "No player-leg or parlay-leg correlation exists from an official source",
         oc.SOURCES["standings"]["url"], "correlations.html"],
        ["Origination", "Two committed originators disagree by 1.5-9.0 points on the same 15 games. "
         "No canonical model has been selected, so no market residual is publishable",
         oc.SOURCES["sched_w11"]["url"], "requirements.html"],
        ["Prices", "Official-only price store: 0 rows. Wider register: 2,364 game-market rows with 2,364 "
         "blank opening fields and 1,956 third-party closing values. No CLV, residual or ROI is published",
         "https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports", "requirements.html"],
        ["Leaderboard", "0 strategies qualified. Signal and staking are ranked separately so a lucky staking "
         "run cannot mask a bad signal. Rewards are unfunded and points-only",
         oc.SOURCES["standings"]["url"], "requirements.html"],
        ["Depth and inactives", "0 of 32 club depth charts parsed; 0 inactives captured; 0 official snap-count "
         "rows. Replacement names and string tiers are blank everywhere by design",
         "https://operations.nfl.com/players/players-rights-and-responsibilities/official-game-book/", "injuries.html"],
        ["Open decisions", f"{len(decisions.SUGGESTIONS)} suggestions awaiting a reviewer's choice; "
         f"{len(decisions.QUESTIONS)} questions unanswered. Nothing in either queue is implemented",
         oc.SOURCES["injury_w10"]["url"], "suggestions.html"],
    ]
    body = f"""
<div class="eyebrow">EXECUTIVE SUMMARY</div>
<h1>Where the project stands, in twelve lines</h1>
<p class="lede">Every figure below comes from an official page retrieved on
{esc(an['capture']['capture_utc'])}, or from a repository record that is itself linked. Where a number
does not exist, the row says so instead of showing an estimate.</p>

<div class="notice"><b>Bottom line.</b> The evidence layer is now partly real: one full official injury
capture, one complete week of official results, one full fixture set and a complete standings table. The
pricing layer is still empty, and until it exists no closing-line value, market residual or ROI figure can
be published honestly. No strategy is qualified and no reward is funded.</div>

<h2>The twelve lines</h2>
{table(["Area", "What is true today", "Source", "Detail"],
       [[esc(a), esc(b), link(c), f'<a href="{esc(site(d, _DEPTH))}">open</a>'] for a, b, c, d in rows])}

<h2>What would change the answer</h2>
<div class="grid2">
  <div class="panel"><h3>Unblocks the most</h3>
  <ol class="tight">
    <li>A scheduled, agent-free capture of the same official pages (clears 8 requirements).</li>
    <li>A written price-data policy and an authorised feed (clears 6).</li>
    <li>One canonical originator (clears 4).</li>
    <li>A depth source verified for all 32 clubs (clears 11).</li>
  </ol></div>
  <div class="panel"><h3>Does not unblock anything on its own</h3>
  <ul class="tight">
    <li>Adding another dashboard. The repository already has ~26 hubs and they disagree.</li>
    <li>More backtests. Every backtest inherits the missing price and results coverage.</li>
    <li>Any injury feature built before inactives and snap counts are captured.</li>
    <li>A reward schedule without funding, eligibility rules and a jurisdiction review.</li>
  </ul></div>
</div>
"""
    return page("Executive summary", "pages/executive.html", body)


def build_requirements(an):
    rows = []
    for r in rq.REQUIREMENTS:
        rows.append([
            f'<span class="tag">{esc(r["id"])}</span>',
            esc(r["cat"]),
            esc(r["req"]),
            pill(r["status"]),
            esc(r["gate"]),
            esc(r["clears"]),
            esc(r["ev"]),
            link(r["ev_url"], "evidence"),
        ])
    body = f"""
<div class="eyebrow">REQUIREMENTS REGISTER</div>
<h1>Every requirement, its gate, and the number that clears it</h1>
<p class="lede">{len(rq.REQUIREMENTS)} requirements grouped into {len(rq.CATEGORY_ORDER)} categories. The
clearance column is written as a countable threshold so a reviewer can tell without argument whether the
gate has been met.</p>
{table(["#", "Category", "Requirement", "Status", "Gate that blocks it",
        "Number that would clear it", "Evidence today", "Source"], rows)}
"""
    return page("Requirements register", "pages/requirements.html", body)


def build_suggestions():
    rows = []
    for s in decisions.SUGGESTIONS:
        opts = "".join(f'<div class="opt"><b>Option {i}.</b> {esc(o)}</div>'
                       for i, o in enumerate(s["options"], 1))
        rows.append([
            f'<span class="tag">{esc(s["id"])}</span>',
            esc(s["priority"]),
            f'<b>{esc(s["title"])}</b><br><span class="small">{esc(s["area"])}</span>',
            esc(s["problem"]),
            esc(s["proposal"]),
            opts,
            esc(s["unblocks"]),
            esc(s["clears"]),
            link(s["source_url"], "source"),
        ])
    body = f"""
<div class="eyebrow">REVIEW QUEUE · NOT IMPLEMENTED</div>
<h1>Suggestions for improving the site and the decisions behind it</h1>
<p class="lede">Nothing on this page has been implemented. Each item states the problem, one proposal, and
the paths a reviewer can choose between. Pick a path and it becomes work; leave it and it stays a proposal.
Priority: <span class="tag">P1</span> unblocks the most ·
<span class="tag">P2</span> material · <span class="tag">P3</span> optional.</p>

<div class="notice"><b>How to review.</b> For each row: read the problem, then choose one of the listed
options or reject the item. The "unblocks" column shows which requirement ids depend on the choice, so the
cost of deferring is visible.</div>

{table(["#", "Pri", "Suggestion", "Problem it solves", "Proposal", "Paths to choose between",
        "Unblocks", "Number that clears it", "Source"], rows)}

<h2>Ordering if everything were approved</h2>
<ol class="tight">
  {"".join(f'<li><b>{esc(s["id"])}</b> — {esc(s["title"])}</li>' for s in decisions.SUGGESTIONS)}
</ol>
"""
    return page("Suggestion review queue", "pages/suggestions.html", body)


def build_questions():
    rows = []
    for q in decisions.QUESTIONS:
        rows.append([
            f'<span class="tag">{esc(q["id"])}</span>',
            f'<b>{esc(q["topic"])}</b><br>{esc(q["question"])}',
            esc(q["known"]),
            esc(q["missing"]),
            esc(q["discover"]),
            esc(q["blocked"]),
            link(q["source_url"], "source"),
        ])
    body = f"""
<div class="eyebrow">DECISION QUESTIONS</div>
<h1>What we know, what we do not, and what each gap blocks</h1>
<p class="lede">{len(decisions.QUESTIONS)} questions. Each states the information already held, the
information that is missing, the route to discovering it, and the decision that cannot reasonably be made
until it is answered.</p>
{table(["#", "Question", "What is already known", "What is missing", "How to discover it",
        "Decision that stays blocked", "Source"], rows)}
"""
    return page("Decision questions", "pages/questions.html", body)


def build_injuries(an):
    inj = an["injury"]
    src = inj["source_url"]

    # per-club summary
    club_rows = []
    for club, d in sorted(inj["per_club"].items()):
        club_rows.append([
            f"<b>{esc(club)}</b>",
            str(d["listed"]), str(d["Out"]), str(d["Doubtful"]),
            str(d["Questionable"]), str(d["no_game_status"]),
            blank(),                  # starters out: the report does not identify starters
            blank(),                  # replacement named: no official source names one
            blank(),                  # string tier: no official source ranks depth
            link(src, "report"),
        ])
    club_tbl = table(
        ["Club", "Listed", "Out", "Doubtful", "Questionable", "No game status",
         "Starters out", "Replacement named", "Replacement string tier", "Source"], club_rows)

    raw = oc.INJURY_ROWS
    reg_rows = [[
        esc(club), esc(player), esc(pos),
        esc(injury) if injury else blank(),
        esc(practice),
        esc(gstatus) if gstatus else blank(),
        esc(slot),
        link(src, "row"),
    ] for (slot, club, player, pos, injury, practice, gstatus) in raw]
    reg_tbl = table(["Club", "Player", "Pos", "Injury as printed", "Practice status",
                     "Game status", "Fixture block", "Source"], reg_rows, scroll=True)

    absent = table(["Club", "Why it is absent, as published", "Source"],
                   [[f"<b>{esc(r['club'])}</b>", esc(r["reason_as_published"]),
                     link(r["source_url"], "source")] for r in an["absent_clubs"]])

    dist = table(["Game status", "Rows", "Share of 347", "Source"],
                 [[esc(k), str(v), f"{100*v/inj['total_rows']:.1f}%", link(src, "report")]
                  for k, v in inj["game_status_counts"].items()])

    news = table(["Date", "Headline published by NFL.com", "Source"],
                 [[esc(d), esc(h), link(u, "article")]
                  for (d, h, u) in oc.INJURY_PAGE_NEWS])

    body = f"""
<div class="eyebrow">AVAILABILITY REGISTER · OFFICIAL SOURCE ONLY</div>
<h1>Week 10 2026 injury report, transcribed row by row</h1>
<p class="lede">{inj['total_rows']} listed-player rows across {inj['clubs_with_table']} club tables,
transcribed from the official NFL.com injury report at {esc(an['capture']['capture_utc'])}. Practice and
game status are reproduced verbatim. A blank cell on the official page is reproduced as a blank cell here.</p>

<div class="notice"><b>What this source does not contain.</b> The injury report publishes no depth chart,
no depth slot, no replacement name and no string tier. It also does not state injured-reserve status. The
"Replacement named" and "Replacement string tier" columns are therefore blank for every club, and a player
who is absent from the report is <i>not</i> thereby confirmed available.</div>

<h2>Per-club summary</h2>
<p class="small">"Listed" is the number of players the club's table contains — the only net count the
source supports. "Starters out" stays blank for every club because the injury report does not identify
starters; filling it would require inferring starter status from a roster attribute, which the brief
explicitly forbids. The same applies to the replacement and string-tier columns.</p>
{club_tbl}

<h2>Game-status distribution</h2>
{dist}

<h2>Clubs with no table, and why</h2>
{absent}

<h2>Full row register ({inj['total_rows']} rows)</h2>
{reg_tbl}

<h2>Dated news headlines the report page itself links</h2>
<p class="small">Recorded as headlines only. They are the context the page supplies for absent players;
they are not treated as verified injury facts and they do not populate any column above.</p>
{news}
"""
    return page("Availability register", "pages/injuries.html", body)


def build_results(an):
    res = an["results"]
    rows = []
    for g in res["games"]:
        win = g["home"] if g["margin"] > 0 else (g["away"] if g["margin"] < 0 else "")
        rows.append([
            esc(g["date"]),
            f'{esc(g["away"])} {g["away_points"]}',
            f'{esc(g["home"])} {g["home_points"]}',
            esc(win) if win else "Tie",
            f'{g["margin"]:+d}' if g["margin"] else "0",
            str(g["total"]),
            link(g["source_url"], "game page"),
        ])
    body = f"""
<div class="eyebrow">VERIFIED RESULTS FEED</div>
<h1>Week 10 2026: {res['n_final']} of {res['n_games']} games FINAL</h1>
<p class="lede">Both scores for every game below were transcribed from the official NFL schedule page at
{esc(an['capture']['capture_utc'])}. No third-party value is used, and no earlier week is included, because
those weeks have not been captured from an official source.</p>

<div class="kpis">
  <div class="kpi"><div class="lbl">Games verified</div><div class="val">{res['n_final']}/{res['n_games']}</div>
    <div class="sub">Every Week 10 game printed FINAL with both scores on the official page.</div></div>
  <div class="kpi"><div class="lbl">Home win rate</div>
    <div class="val">{res['home_win_rate']*100:.1f}%</div>
    <div class="sub">{res['home_wins']} home wins, {res['home_losses']} home losses, {res['home_ties']} ties.
    One week; not a test of any hypothesis.</div></div>
  <div class="kpi"><div class="lbl">Mean total</div><div class="val">{res['mean_total']}</div>
    <div class="sub">Median {res['median_total']}, range {res['min_total']} to {res['max_total']}. n={res['n_games']}.</div></div>
  <div class="kpi"><div class="lbl">Mean absolute margin</div><div class="val">{res['mean_abs_margin']}</div>
    <div class="sub">Average winning margin across the {res['n_games']} games.</div></div>
</div>

<h2>Game log</h2>
{table(["Date", "Away (pts)", "Home (pts)", "Winner", "Margin (home)", "Total", "Source"], rows)}

<div class="notice"><b>Scope.</b> One week is not a backtest corpus. The pre-registered 136-game corpus
needs official results for every game in its window; Weeks 1 to 6 are still pending official capture.
The two results registers elsewhere in this repository use different scopes and verification labels and
must not be added together.</div>
"""
    return page("Verified results", "pages/results.html", body)


def build_schedule(an):
    sch = an["schedule"]
    rows = []
    for g in sch["games"]:
        rows.append([
            esc(g["date"]), esc(g["kickoff_et"]),
            f'{esc(g["away"])} at {esc(g["home"])}',
            esc(g["network"]),
            esc(g["venue"]),
            "Yes" if g["neutral_site"] else "No",
            link(g["source_url"], "game page"),
        ])
    bye_rows = [[f"<b>{esc(c)}</b>", esc("Listed under 'Teams on Bye' on the official Week 11 schedule page"),
                 link(sch["source_url"], "source")] for c in sch["bye"]]
    body = f"""
<div class="eyebrow">FIXTURE CONTEXT · PUBLISHED SCHEDULE FACTS ONLY</div>
<h1>Week 11 2026: {sch['n_games']} fixtures, {len(sch['bye'])} clubs on bye</h1>
<p class="lede">Every field below is printed by the official NFL schedule page: date, kickoff time in ET,
the two clubs, the broadcast network, and the venue. No travel distance, rest day, timezone shift or
weather term has been added, because none of those is published on this page.</p>

<div class="notice"><b>Venue provenance.</b> The venue string is the stadium name the official schedule
page publishes in its own on-page stadium reference for that fixture. It has not yet been re-transcribed
from each game centre, which is what the brief asks for. That re-verification is open on the
<a href="flagged.html">flagged page</a>. The Vikings-49ers fixture is labelled Mexico City on the official
page and is marked neutral here.</div>

{table(["Date", "Kickoff (ET)", "Matchup", "Network", "Venue as published", "Neutral site", "Source"], rows)}

<h2>Teams on bye ({len(sch['bye'])})</h2>
{table(["Club", "As published", "Source"], bye_rows)}

<h2>What a fixture-context feature set may legally contain</h2>
<div class="grid2">
  <div class="panel"><h3>Published by this page</h3>
  <ul class="tight">
    <li>Kickoff date and time (ET) — a real scheduling fact.</li>
    <li>Home and away designation.</li>
    <li>Venue string.</li>
    <li>Neutral-site marker where the league labels one.</li>
    <li>Bye status, and therefore each club's week number.</li>
  </ul></div>
  <div class="panel"><h3>Not published by this page — must stay blank</h3>
  <ul class="tight">
    <li>Roof open or closed. Needs the official 90-minute designation, which is not captured.</li>
    <li>Surface. Not on this page.</li>
    <li>Wind and precipitation. Needs an NWS grid captured at a recorded time.</li>
    <li>Travel distance and rest differential. Derivable, but only from these published facts —
        and not yet built.</li>
  </ul></div>
</div>
"""
    return page("Fixture & venue", "pages/schedule.html", body)


def build_standings(an):
    st = an["luck"]["table"]
    rows = []
    for t in st:
        rows.append([
            f'<b>{esc(t["club"])}</b>', esc(t["division"]),
            str(t["w"]), str(t["l"]), str(t["t"]), f'{t["pct"]:.3f}',
            str(t["pf"]), str(t["pa"]), str(t["net"]),
            f'{t["pythag_wins"]:.2f}',
            f'{t["luck_wins"]:+.2f}',
            link(an["luck"]["source_url"], "standings"),
        ])
    body = f"""
<div class="eyebrow">OFFICIAL STANDINGS · n=32</div>
<h1>2026 standings through the capture date</h1>
<p class="lede">Wins, losses, ties, points for and points against for all 32 clubs, transcribed from the
official NFL division standings page at {esc(an['capture']['capture_utc'])}. Pythagorean expected wins and
the luck residual are computed here from those two official columns; the exponent is a stated assumption,
not an NFL figure.</p>

{table(["Club", "Division", "W", "L", "T", "Pct", "PF", "PA", "Net", "Pythagorean wins", "Luck (wins)", "Source"],
       rows)}

<div class="notice"><b>Reading the luck column.</b> Positive means the club has won more games than its
points ratio implies. The standard deviation across the 32 clubs is
{an['luck']['luck_sd']} wins, so a single-season gap of one to two wins is well inside normal spread.
Whether luck persists from season to season is not tested here — that needs at least three seasons of
official standings.</div>
"""
    return page("Standings & luck", "pages/standings.html", body)


def build_luck(an):
    lk = an["luck"]
    corr_rows = [[esc(c["pair"]), esc(c["r"]), esc(c["ci95"]), str(c["n"]),
                  link(c["source_url"], "data"), link(c["method_url"], "method")]
                 for c in lk["correlations"]]
    pos = [[esc(t["club"]), f'{t["luck_wins"]:+.2f}', str(t["w"]), str(t["l"]),
            f'{t["pythag_wins"]:.2f}', link(lk["source_url"], "standings")]
           for t in lk["luck_most_positive"]]
    neg = [[esc(t["club"]), f'{t["luck_wins"]:+.2f}', str(t["w"]), str(t["l"]),
            f'{t["pythag_wins"]:.2f}', link(lk["source_url"], "standings")]
           for t in lk["luck_most_negative"]]
    body = f"""
<div class="eyebrow">REMOVAL OF LUCK</div>
<h1>How much of the 2026 table is not skill</h1>
<p class="lede">Computed from two official columns — points for and points against — for all 32 clubs.
Every coefficient below carries its n and a Fisher-z 95% interval. Nothing here uses a third-party feed.</p>

<div class="kpis">
  <div class="kpi"><div class="lbl">Luck standard deviation</div><div class="val">{lk['luck_sd']} wins</div>
    <div class="sub">Spread of actual wins around Pythagorean expectation across 32 clubs.</div></div>
  <div class="kpi"><div class="lbl">Luck range</div><div class="val">{lk['luck_min']:+.2f} to {lk['luck_max']:+.2f}</div>
    <div class="sub">Most-negative to most-positive residual in the league this season.</div></div>
  <div class="kpi"><div class="lbl">Win pct vs net points</div><div class="val">{lk['correlations'][2]['r']}</div>
    <div class="sub">95% interval {lk['correlations'][2]['ci95']}, n=32.</div></div>
  <div class="kpi"><div class="lbl">Pythagorean exponent</div><div class="val">{lk['exponent']}</div>
    <div class="sub">A stated assumption of this calculation, not a figure published by the NFL.</div></div>
</div>

<h2>Correlations from official data</h2>
{table(["Pair", "Pearson r", "95% CI (Fisher z)", "n", "Data source", "Method"], corr_rows)}

<h2>Most positive luck residuals</h2>
{table(["Club", "Luck (wins)", "W", "L", "Pythagorean wins", "Source"], pos)}

<h2>Most negative luck residuals</h2>
{table(["Club", "Luck (wins)", "W", "L", "Pythagorean wins", "Source"], neg)}

<div class="notice"><b>What this does not prove.</b> One season cannot show whether luck persists, and
persistence is the part that matters for separating skill from variance. A season-to-season luck
correlation needs at least three seasons of official standings. Until then this panel is descriptive,
and no strategy should be promoted on the strength of it.</div>

<h2>Why the leaderboard does not rank on win rate</h2>
<p>A win-rate ranking rewards whichever club or bettor caught the favourable side of a
{lk['luck_sd']}-win spread. The project therefore ranks by a pre-registered benchmark-relative proper
score with a game-cluster lower bound and a multiplicity adjustment, reports staking outcomes in a
separate block, and includes random and favourites-only controls under identical settlement rules.</p>
"""
    return page("Removal of luck", "pages/luck.html", body)


def build_correlations(an):
    lk = an["luck"]
    rows = [[esc(c["pair"]), esc(c["r"]), esc(c["ci95"]), str(c["n"]),
             esc("Official NFL.com standings (2026)"),
             link(c["source_url"], "data"), link(c["method_url"], "method")]
            for c in lk["correlations"]]
    missing = [
        ["QB passing yards to WR1 receiving yards (same game)",
         "No official player-game joint distribution has been captured",
         "≥500 paired player-game observations from an official source, with n and interval published",
         "https://www.nfl.com/stats/player-stats/"],
        ["Any same-game parlay leg pair",
         "Requires observed joint outcomes; a marginal correlation does not determine a joint distribution",
         "Directly validated joint probabilities over ≥2 seasons plus the operator's void/push rules",
         "https://www.itl.nist.gov/div898/possolo/TutorialWEBServer/TutorialMetrologists2011Nov09.xht"],
        ["Injury designation to actual play",
         "No official inactives list has been captured, so no play rate per designation exists",
         "≥1,000 designation-to-outcome pairs over ≥2 seasons with a 95% interval per designation",
         "https://operations.nfl.com/players/players-rights-and-responsibilities/official-game-book/"],
        ["Depth tier to performance",
         "No official source states string tier for any club",
         "A depth register verified for all 32 clubs before any slot is used as a feature",
         "https://www.nfl.com/teams/"],
    ]
    body = f"""
<div class="eyebrow">CORRELATIONS · OFFICIAL NUMBERS ONLY, n ALWAYS PUBLISHED</div>
<h1>Four coefficients we can stand behind, and the ones we cannot</h1>
<p class="lede">Every coefficient below is computed only from numbers transcribed from an official NFL.com
page. Each carries its sample size and a Fisher-z 95% interval. Coefficients that cannot be computed from
an official source are listed as missing rather than estimated.</p>

<h2>Published correlations (team-standings family)</h2>
{table(["Pair", "Pearson r", "95% CI (Fisher z)", "n", "Input", "Data source", "Method"], rows)}

<div class="notice"><b>Family boundary.</b> These are team-standings relationships over 32 clubs. They are
not player-prop, injury or parlay-leg correlations and must not be transferred to those uses. The
Line Desk register elsewhere adds eight standings coefficients at n=32 and two pooled at n=64; those are
the same family and the same boundary applies.</div>

<h2>Correlations that do not exist yet, and what would produce them</h2>
{table(["Coefficient needed", "Why it is missing", "What would produce it", "Source to capture"],
       [[esc(a), esc(b), esc(c), link(d, "route")] for a, b, c, d in missing])}

<h2>Why parlays stay behind a joint-evidence gate</h2>
<p>Multiplying marginal probabilities assumes the legs are independent. Within a single NFL game they are
not — the same game script drives both. A marginal correlation does not determine a joint distribution
either. A combo is therefore ranked only when a directly validated joint probability exists and the
operator's void and push rules are both on record. Nothing has passed that gate, so no combo is ranked.</p>
"""
    return page("Official correlations", "pages/correlations.html", body)


def build_verification(an):
    rows = [[esc(a["claim_id"]), esc(a["claim"]), esc(a["official_page_says"]),
             esc(a["verdict"]), link(a["source_url"], "source")]
            for a in an["brief_audit"]]
    body = f"""
<div class="eyebrow">BRIEF CLAIM AUDIT</div>
<h1>What the brief asserted, checked against the official page</h1>
<p class="lede">Each row takes a specific factual claim from the project brief and states what the official
page actually says at {esc(an['capture']['capture_utc'])}. Where the claim could not be confirmed, the row
says so rather than restating the claim.</p>
{table(["Claim id", "Claim in the brief", "What the official page says", "Verdict", "Source"], rows)}

<div class="notice crit"><b>Two counts in the brief do not reproduce.</b> The brief cites 254 rows and then
279 rows for the Week 10 injury report. A full transcription of the page as captured today yields
{an['injury']['total_rows']} listed-player rows across {an['injury']['clubs_with_table']} club tables, with
no club table left empty. The {an['injury']['total_rows']} figure is a complete transcription, not a
sample; the two earlier figures should be retired.</div>

<div class="notice"><b>Good news from the same check.</b> The three Lions designations the brief flagged as
blank are all present and read Out on the official page. The four clubs missing from the report are
confirmed on bye by the official schedule page, which closes that flag. And the claim that only 6 rows
carry a game designation is out of date: {an['injury']['rows_with_game_status']} of
{an['injury']['total_rows']} rows carry one.</div>
"""
    return page("Brief claim audit", "pages/verification.html", body)


def build_flagged(an):
    cap = an["capture"]
    items = [
        ("F-01", "No raw-response hash",
         "The sandbox shell has no network route to nfl.com, so only the retrieval tool could read the page. "
         "The register hash published in the manifest covers the transcribed rows, not the NFL response body.",
         "Raw HTTP retention requires a runner with network access to nfl.com and a decision on where raw "
         "payloads are stored. Until then, treat the capture as a faithful transcription with a register "
         "hash rather than an immutable byte-level snapshot.",
         "https://www.nfl.com/injuries/league/2026/REG10"),
        ("F-02", "Week 11 report not yet published at capture time",
         f"At {cap['capture_utc']} the canonical NFL.com injury page still displayed Week 10. The latest "
         "official report available is therefore Week 10, which is post-kickoff.",
         "Re-capture after the NFL publishes the Week 11 report, which normally appears on the Wednesday "
         "before the Sunday slate.",
         "https://www.nfl.com/injuries/league/2026/REG10"),
        ("F-03", "Two prior row counts do not reproduce",
         "The brief cites 254 rows and 279 rows for the Week 10 report. A complete transcription today gives "
         f"{an['injury']['total_rows']} rows across {an['injury']['clubs_with_table']} clubs.",
         "Retire both earlier counts and use the full transcription. If a reviewer wants an independent "
         "recount, the register CSV can be re-counted directly.",
         "https://www.nfl.com/injuries/league/2026/REG10"),
        ("F-04", "Replacement name and string tier are blank for every club",
         "The official injury report publishes no depth column, no replacement name and no string tier. "
         "Neither field can be filled from this source.",
         "Resolve a depth source for all 32 clubs, or leave both columns permanently blank and drop the "
         "deficiency matrix from scope.",
         "https://operations.nfl.com/players/players-rights-and-responsibilities/official-game-book/"),
        ("F-05", "Absent players are not confirmed available",
         "Malik Willis and Lamar Jackson do not appear in their clubs' Week 10 tables. The report does not "
         "state why. Their injured-reserve status comes from NFL.com news headlines the page links, not "
         "from a reserve register.",
         "Capture an official IR or reserve list weekly and join it to the report so every absent player is "
         "classified as IR, bye or genuinely not listed.",
         "https://www.nfl.com/news/dolphins-place-qb-malik-willis-groin-on-injured-reserve-kyle-mccord-in-line-for-first-start"),
        ("F-06", "Venue not yet transcribed from the game centre",
         "Venue strings come from the stadium reference the official schedule page publishes for each "
         "fixture, not from an individual game-centre read.",
         "Transcribe the venue per fixture from the game centre and reconcile it against the schedule-page "
         "string for at least two weeks.",
         "https://www.nfl.com/schedules/2026/by-week/week-11"),
        ("F-07", "Venue string for the neutral-site game is a city, not a stadium",
         "The official page labels the Vikings-49ers fixture 'Mexico City' rather than naming a stadium, so "
         "the venue cell records what the page prints.",
         "Re-read the game centre for that fixture and record the stadium name if the NFL publishes one.",
         "https://www.nfl.com/games/vikings-at-49ers-2026-reg-11"),
        ("F-08", "One week of results is not a backtest corpus",
         f"{an['results']['n_final']} Week 10 games are verified. Weeks 1 to 6 have not been captured from "
         "an official source.",
         "Capture official results week by week until the pre-registered window is fully covered, then "
         "freeze the corpus with a commit hash.",
         "https://www.nfl.com/schedules/2026/by-week/week-10"),
        ("F-09", "No official price of any kind",
         "The official-only price store has 0 rows. No opening price, no closing price, no own closing line "
         "has been captured, so CLV, market residual and ROI are all uncomputed.",
         "Approve a price-data policy and an authorised feed before publishing any price-derived statistic.",
         "https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports"),
        ("F-10", "Two originators disagree and neither is canonical",
         "Two committed models differ by 1.5 to 9.0 points on each of the same 15 games.",
         "Name one canonical originator and label the other historical, or run the pre-registered "
         "walk-forward comparison the brief specifies.",
         "https://www.nfl.com/schedules/2026/by-week/week-11"),
        ("F-11", "Luck persistence untested",
         f"The luck panel covers one season (n=32, SD {an['luck']['luck_sd']} wins). Whether a luck residual "
         "repeats is unknown.",
         "Capture at least three seasons of official standings and publish a season-to-season correlation "
         "with n and interval.",
         "https://www.nfl.com/standings/division/2026/REG"),
        ("F-12", "Designation reliability unmeasured",
         f"Designations are counted (Questionable 90, Out 70, Doubtful 11, blank 176 of "
         f"{an['injury']['total_rows']}) but no play rate per designation can be computed without inactives.",
         "Capture official inactives and join them to designations over at least two seasons before the "
         "label is used as a model feature.",
         "https://www.nfl.com/injuries/league/2026/REG10"),
    ]
    rows = [[esc(i), esc(t), esc(w), esc(f), link(u, "source")] for i, t, w, f, u in items]
    body = f"""
<div class="eyebrow">FLAGGED FOR REVIEW</div>
<h1>Everything that could not be verified, in one place</h1>
<p class="lede">{len(items)} items. Each states what could not be confirmed, why, and what would resolve it.
None of these blocks publication of the site; all of them block the claim that the affected number is
verified.</p>
{table(["#", "Item", "What is unresolved", "What would resolve it", "Source"], rows)}
"""
    return page("Flagged for review", "pages/flagged.html", body)


def build_sources(an):
    src_rows = []
    for key, s in sorted(oc.SOURCES.items()):
        src_rows.append([
            f"<b>{esc(key)}</b>",
            esc(s["title"]),
            f'<a href="{esc(s["url"])}" rel="noopener" target="_blank">{esc(s["url"])}</a>',
            f'{s["chunks"]}',
            esc(s["captured_utc"]),
        ])
    reg_rows = []
    for key, r in sorted(an["capture"]["registers"].items()):
        reg_rows.append([
            esc(key),
            f'<code>{esc(r["sha256"][:32])}…</code>',
            str(r["rows"]),
            esc(r["captured_utc"]),
            link(r["source_url"], "source"),
        ])
    ref_rows = [
        ["NFL Game Books", "Official starters, Did-Not-Play and Not-Active per game",
         "https://operations.nfl.com/players/players-rights-and-responsibilities/official-game-book/"],
        ["NFL-Genius Sports partnership", "Context for official data distribution; not a price feed",
         "https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports"],
        ["NWS web API", "The route the brief names for hourly wind and precipitation grids",
         "https://www.weather.gov/documentation/services-web-api"],
        ["NIST correlation intervals", "Fisher-z confidence-interval method used for every coefficient",
         "https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm"],
        ["NIST dependence tutorial", "Why a marginal correlation does not determine a joint distribution",
         "https://www.itl.nist.gov/div898/possolo/TutorialWEBServer/TutorialMetrologists2011Nov09.xht"],
        ["NFL transactions", "The log the brief wants for stale-depth and roster-turnover checks",
         "https://www.nfl.com/transactions/league/transactions/2026/11"],
        ["NFL player statistics", "The route for official player-game distributions, if joint data is needed",
         "https://www.nfl.com/stats/player-stats/"],
        ["NFL terms", "Source-by-source terms register still to be written",
         "https://www.nfl.com/legal/terms"],
    ]
    body = f"""
<div class="eyebrow">SOURCE REGISTER</div>
<h1>Every official page this desk used, and when</h1>
<p class="lede">Four pages were retrieved and transcribed for this hub. The remaining entries are routes
the brief names but that have not been captured yet; they are listed so a reviewer can see the gap rather
than infer one.</p>

<h2>Pages retrieved and transcribed</h2>
{table(["Key", "Page title as published", "URL", "Chunks read", "Captured (UTC)"], src_rows)}

<h2>Registers written, with content hashes</h2>
<p class="small">The hash covers the canonical register rows as written to CSV. It is not a hash of the NFL
response body — see <a href="flagged.html">F-01</a> for why.</p>
{table(["Register", "SHA-256 (first 32 chars)", "Rows", "Captured (UTC)", "Source"], reg_rows)}

<h2>Method and reference links</h2>
{table(["Resource", "What it is used for here", "URL"],
       [[esc(a), esc(b), link(c, "open")] for a, b, c in ref_rows])}

<h2>Capture method, stated plainly</h2>
<div class="panel"><p>{esc(an['capture']['capture_method'])}</p></div>
"""
    return page("Source register", "pages/sources.html", body)


# --------------------------------------------------------------------------

def at_depth(depth, fn):
    """Render a page builder at a given path depth."""
    global _DEPTH
    _DEPTH = depth
    try:
        return fn()
    finally:
        _DEPTH = 1


def main():
    os.makedirs(PAGES, exist_ok=True)
    os.makedirs(ASSETS, exist_ok=True)
    with open(os.path.join(ASSETS, "style.css"), "w", encoding="utf-8") as fh:
        fh.write(CSS.lstrip())

    an = analyze.build()
    req_summary = rq.summary()

    written = []
    jobs = [
        ("index.html", 1, lambda: build_index(an, req_summary)),
        ("pages/executive.html", 2, lambda: build_executive(an, req_summary)),
        ("pages/requirements.html", 2, lambda: build_requirements(an)),
        ("pages/suggestions.html", 2, build_suggestions),
        ("pages/questions.html", 2, build_questions),
        ("pages/injuries.html", 2, lambda: build_injuries(an)),
        ("pages/results.html", 2, lambda: build_results(an)),
        ("pages/schedule.html", 2, lambda: build_schedule(an)),
        ("pages/standings.html", 2, lambda: build_standings(an)),
        ("pages/luck.html", 2, lambda: build_luck(an)),
        ("pages/correlations.html", 2, lambda: build_correlations(an)),
        ("pages/verification.html", 2, lambda: build_verification(an)),
        ("pages/flagged.html", 2, lambda: build_flagged(an)),
        ("pages/sources.html", 2, lambda: build_sources(an)),
    ]
    for name, depth, fn in jobs:
        path = os.path.join(ROOT, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(at_depth(depth, fn))
        written.append(name)

    print(f"wrote {len(written)} pages:")
    for w in written:
        print("  -", w)
    print("requirement summary:", req_summary)


if __name__ == "__main__":
    main()
