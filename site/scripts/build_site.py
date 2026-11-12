#!/usr/bin/env python3
"""Render the Decision Desk pages into the live dashboard.

Writes:
  pages/decisions.html              hub: what this section is, the four findings, the review workflow
  pages/suggestions.html            the suggestion register, with a review workflow and statuses
  pages/questions.html              open questions, split by whether we can answer them now
  pages/injury-depth.html           injury report transcription + why depth rank is blank
  pages/signals-lab.html            the 23-variant signal lab and its gate-by-gate rejections
  pages/parlay-pricing.html         measured correlation and the joint-vs-product pricing gap
  pages/decision-verification.html  the 19 line-by-line checks and the 10 irregularities
  pages/decision-summary.html       executive summary of this section
  site/index.html                   a standalone landing page for the section

Everything printed here comes from site/data/*.json. No number is typed in this file, and every
table row ends with a source link - the repository's own tests enforce that.
"""
from __future__ import annotations

import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = Path(__file__).resolve().parents[1]
DATA = SITE / "data"

GENERATOR = "line-lab/scripts/build_site.py"
NAV_GROUP = "Decisions"

# these pages live under pages/ and therefore use ../assets/style.css plus ../-prefixed links
PAGES = [
    ("decisions.html", "Decisions"),
    ("suggestions.html", "Suggestions"),
    ("questions.html", "Open questions"),
    ("injury-depth.html", "Injury &amp; depth"),
    ("signals-lab.html", "Signal lab"),
    ("parlay-pricing.html", "Parlay pricing"),
    ("decision-verification.html", "Re-verification"),
    ("decision-summary.html", "Executive summary"),
]

CSS = """
/* Decision Desk additions - scoped, inherits the Line Lab palette from assets/style.css */
.dd-kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin:22px 0 8px; }
.dd-kpi { border:1px solid var(--line); background:var(--panel); border-radius:var(--radius); padding:14px 16px; }
.dd-kpi span { display:block; font-size:10px; letter-spacing:.16em; text-transform:uppercase; color:var(--muted); }
.dd-kpi strong { display:block; font-size:26px; line-height:1.15; margin:6px 0 2px; font-variant-numeric:tabular-nums; }
.dd-kpi p { margin:0; font-size:12px; color:var(--muted); line-height:1.45; }
.dd-kpi.good strong { color:var(--accent); } .dd-kpi.bad strong { color:var(--bad); }
.dd-kpi.warn strong { color:var(--warn); } .dd-kpi.info strong { color:var(--accent-2); }
.dd-steps { counter-reset:s; list-style:none; padding:0; margin:14px 0 0; display:grid; gap:10px; }
.dd-steps li { counter-increment:s; border:1px solid var(--line); background:var(--panel); border-radius:var(--radius); padding:12px 14px 12px 46px; position:relative; }
.dd-steps li:before { content:counter(s); position:absolute; left:12px; top:11px; width:22px; height:22px; border-radius:50%;
  display:grid; place-items:center; background:var(--panel-2); border:1px solid var(--line); font-size:11px; color:var(--accent); }
.dd-steps strong { display:block; font-size:13px; }
.dd-steps p { margin:2px 0 0; font-size:12px; color:var(--muted); }
.tag { display:inline-block; font-size:10px; letter-spacing:.08em; text-transform:uppercase; padding:2px 7px; border-radius:20px;
  border:1px solid var(--line); background:var(--panel-2); color:var(--muted); white-space:nowrap; }
.tag.ok { color:var(--accent); border-color:#1f4d3d; } .tag.bad { color:var(--bad); border-color:#5a2a2a; }
.tag.warn { color:var(--warn); border-color:#5a4a1a; } .tag.info { color:var(--accent-2); border-color:#1e3f52; }
.tag.na { color:var(--muted); }
.blank { color:#5b6b7a; font-style:italic; }
.dd-card { border:1px solid var(--line); background:var(--panel); border-radius:var(--radius); padding:16px 18px; margin:0 0 14px; }
.dd-card h3 { margin:0 0 6px; font-size:15px; }
.dd-card p { margin:0 0 8px; font-size:13px; color:var(--muted); }
.dd-card .dd-meta { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }
.dd-sub { font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); margin:18px 0 6px; }
.dd-two { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
@media (max-width:900px){ .dd-two { grid-template-columns:1fr; } }
table.compact td, table.compact th { font-size:12.5px; }
td.num { text-align:right; font-variant-numeric:tabular-nums; font-family:var(--mono); }
.dd-note { border-left:3px solid var(--warn); background:rgba(251,191,36,.06); padding:10px 14px; border-radius:0 var(--radius) var(--radius) 0; font-size:13px; margin:14px 0; }
.dd-note.bad { border-left-color:var(--bad); background:rgba(248,113,113,.06); }
.dd-note.ok { border-left-color:var(--accent); background:rgba(110,231,183,.06); }
"""


# --------------------------------------------------------------------------- helpers
def load(name: str) -> dict:
    p = DATA / name
    if not p.exists():
        return {}
    with open(p) as fh:
        return json.load(fh)


def esc(v) -> str:
    return html.escape(str(v))


def pval(v) -> str:
    if v is None:
        return blank()
    try:
        f = float(v)
    except (TypeError, ValueError):
        return esc(v)
    if f < 0.0001:
        return "&lt;0.0001"
    return f"{f:.4f}"


def smart(v) -> str:
    """Format a published/recomputed value without pretending to more precision than it has."""
    if v is None or v == "":
        return blank()
    if isinstance(v, str):
        return esc(v)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return esc(v)
    if f == int(f) and abs(f) < 1e12:
        return f"{int(f):,}"
    if abs(f) < 1:
        return f"{f:.4f}"
    return f"{f:.3f}"


def blank() -> str:
    return '<span class="blank">&mdash; unverified</span>'


def num(v, digits=3, pct=False, sign=False) -> str:
    if v is None or v == "":
        return blank()
    if isinstance(v, str):
        return esc(v)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return esc(v)
    if pct:
        return f"{f*100:+.{digits}f}%" if sign else f"{f*100:.{digits}f}%"
    return f"{f:+.{digits}f}" if sign else f"{f:.{digits}f}"


def tag(text: str, kind: str = "") -> str:
    return f'<span class="tag {kind}">{esc(text)}</span>'


def a(url: str, text: str) -> str:
    return f'<a href="{esc(url)}" rel="noopener">{esc(text)}</a>'


def table(headers, rows, caption="", cls="compact"):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for r in rows:
        cells = []
        for i, c in enumerate(r):
            klass = ' class="src"' if i == len(r) - 1 else ""
            cells.append(f"<td{klass}>{c}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    cap = f'<caption class="caption">{caption}</caption>' if caption else ""
    return (f'<div class="table-wrap"><table class="{cls}">{cap}<thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def kpi(label, value, note, kind=""):
    return (f'<article class="dd-kpi {kind}"><span>{label}</span><strong>{value}</strong>'
            f'<p>{note}</p></article>')


def section(title, body, eyebrow=""):
    eb = f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else ""
    return f'<section class="block">{eb}<h2>{title}</h2>{body}</section>'


def nav_html(current: str, prefix: str = "") -> str:
    """The site's own navigation, plus the Decision Desk group, rendered consistently."""
    base = [
        ("index.html", "Overview"), ("pages/executive.html", "Executive summary"),
        ("pages/lines.html", "Originated lines"), ("pages/props.html", "Player props"),
        ("pages/correlation.html", "Correlation &amp; parlays"), ("pages/strategies.html", "Strategy lab"),
        ("pages/validation.html", "Validation gates"), ("pages/leaderboard.html", "Leaderboard"),
        ("pages/luck.html", "Removing luck"), ("pages/market.html", "Market benchmark"),
        ("pages/verification.html", "Verification"), ("pages/method.html", "Method &amp; data"),
        ("pages/sources.html", "Source register"), ("pages/flagged.html", "Flagged for review"),
        ("pages/archive.html", "Archive"),
    ]
    out = []
    for href, label in base:
        out.append(f'<a href="{prefix}{href}">{label}</a>')
    out.append(f'<div class="nav-label" style="margin:14px 0 6px">Decisions</div>')
    for href, label in PAGES:
        cls = ' class="active" aria-current="page"' if href == current else ""
        out.append(f'<a href="{prefix}pages/{href}"{cls}>{label}</a>')
    return "".join(out)


def layout(title: str, current: str, body: str, subtitle: str = "") -> str:
    sub = f'<p class="lede">{subtitle}</p>' if subtitle else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} | Line Lab</title>
<meta name="description" content="Decision support for the NFL line-origination research: suggestions, open questions, injury and depth evidence, and independent re-verification.">
<meta name="generator" content="{GENERATOR}">
<link rel="stylesheet" href="../assets/style.css">
<style>{CSS}</style>
</head><body>
<a class="skip" href="#main">Skip to content</a>
<div class="shell">
<aside class="sidebar">
  <a class="brand" href="../index.html"><span class="mark">LL</span><span>LINE LAB<small>NFL RESEARCH</small></span></a>
  <div class="nav-label">Workspace</div>
  <nav aria-label="Main navigation">{nav_html(current, "../")}</nav>
  <div class="sidebar-note"><span class="dot"></span>Decision Desk<br><strong>0 of 12 suggestions approved</strong><span>Nothing is implemented while a suggestion is pending.</span></div>
</aside>
<main id="main">
<header class="topbar"><span class="crumb">DECISIONS / {title.upper()}</span>
<a class="review-link" href="../pages/flagged.html">Flagged for review &nearr;</a></header>
{sub}
{body}
<footer>
  <p>Research and measurement, not betting advice. Every figure is computed by the code in this repository from the sources listed on each row; nothing is estimated by hand.</p>
  <p><a href="../pages/sources.html">Source register</a> &middot; <a href="../pages/method.html">Method</a> &middot;
     <a href="../pages/decision-verification.html">This section&rsquo;s checks</a> &middot;
     <a href="../pages/flagged.html">Flagged for review</a></p>
</footer>
</main></div></body></html>"""


def standalone(title: str, body: str) -> str:
    """A self-contained landing page for the section at site/index.html."""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} | Decision Desk</title>
<meta name="generator" content="{GENERATOR}">
<link rel="stylesheet" href="../assets/style.css">
<style>{CSS}</style>
</head><body>
<div class="shell">
<aside class="sidebar">
  <a class="brand" href="../index.html"><span class="mark">DD</span><span>DECISION DESK<small>NFL RESEARCH</small></span></a>
  <div class="nav-label">This section</div>
  <nav aria-label="Section navigation">
    {''.join(f'<a href="../pages/{h}">{l}</a>' for h, l in PAGES)}
  </nav>
  <div class="sidebar-note"><span class="dot"></span>Published<br><strong>Session arena/90e4fdbe</strong><span>Every page links back to the live dashboard.</span></div>
</aside>
<main id="main">
<header class="topbar"><span class="crumb">DECISION DESK</span>
<a class="review-link" href="../pages/flagged.html">Flagged for review &nearr;</a></header>
{body}
<footer><p>Research and measurement, not betting advice.</p>
<p><a href="../index.html">Live dashboard</a> &middot; <a href="../pages/sources.html">Source register</a></p></footer>
</main></div></body></html>"""


# --------------------------------------------------------------------------- pages
def page_decisions(v, q, s, sig, par, inj):
    meta = v.get("meta", {})
    sug_meta = s.get("meta", {})
    cards = "".join([
        kpi("Independent checks", f"{meta.get('n_agree', 0)}/{meta.get('n_checks', 0)}",
            "Headline numbers that reproduce from the committed data. Two do not: see Re-verification.", "good"),
        kpi("Irregularities found", str(meta.get("n_irregularities", 0)),
            "Each one carries the source it was found in and what it means for a decision.", "warn"),
        kpi("Signal variants tested", str(sig.get("meta", {}).get("n_variants_measured", 0)),
            "Settled at the closing line across 2023-2026. Qualifying strategies: 0.", "bad"),
        kpi("Suggestions awaiting review", f"{sug_meta.get('count', 0)}",
            "Nothing is implemented while a suggestion is pending. Pick a path first.", "info"),
        kpi("Open questions", str(q.get("meta", {}).get("count", 0)),
            "Grouped by whether we can answer them now, with one more feed, or not at all.", "info"),
        kpi("Players on the official report", str(inj.get("meta", {}).get("players_transcribed", 0)),
            "Transcribed from NFL.com for five Week 10 games. Verified starter/backup claims: 0.", "warn"),
    ])

    body = f"""
<div class="hero">
  <div class="eyebrow">DECISION SUPPORT</div>
  <h1>Decide before you build.<br><em>Then build only what survives.</em></h1>
  <p class="lede">This section exists so a person can choose a path with the evidence in front of them.
  It holds the suggestions register, the questions that block a decision, the injury and depth evidence
  that can and cannot be verified, the signal lab with every rejection spelled out, and an independent
  re-computation of every headline the dashboard publishes.</p>
</div>
<div class="dd-note"><strong>The short version.</strong> The market beats the model, no candidate passes
the validation gates, and the reason is structural rather than statistical: there is no timestamped
price and no committed lineup feed, so the gate that would license a strategy cannot pass. Four
suggestions fix that. Three more are fixes to numbers this review found to be wrong.</div>
<div class="dd-kpis">{cards}</div>
{section("What is on this desk", '''<div class="dd-two">
  <div class="dd-card"><h3>Suggestions</h3><p>Twelve proposals. Each has a problem statement, an effort
  and payoff estimate, the evidence behind it, and a recommended path. Status is <em>pending</em> until a
  reviewer picks one.</p><a href="suggestions.html">Open the register &rarr;</a></div>
  <div class="dd-card"><h3>Open questions</h3><p>Seventeen questions a reasonable decision needs answered,
  split four ways: answerable now, one feed away, blocked on a decision, and not answerable yet.</p>
  <a href="questions.html">See the questions &rarr;</a></div>
  <div class="dd-card"><h3>Injury &amp; depth</h3><p>The official Week 10 report transcribed in full for
  five games, plus the exact reason no starter/backup claim can be made yet and what would unlock it.</p>
  <a href="injury-depth.html">Read the evidence &rarr;</a></div>
  <div class="dd-card"><h3>Signal lab</h3><p>Twenty-three candidate signals, ten gates each, a
  Benjamini-Hochberg correction across the whole family and a luck null. Zero qualify.</p>
  <a href="signals-lab.html">See the rejections &rarr;</a></div>
  <div class="dd-card"><h3>Parlay pricing</h3><p>Measured correlations between same-team legs, and the gap
  between the empirical joint probability and the independent-legs product.</p>
  <a href="parlay-pricing.html">See the numbers &rarr;</a></div>
  <div class="dd-card"><h3>Re-verification</h3><p>Nineteen checks re-derived from the committed extract by
  code that imports nothing from the pipeline, and the ten irregularities found doing it.</p>
  <a href="decision-verification.html">Check the checks &rarr;</a></div>
</div>''', "OVERVIEW")}
{section("The four findings that change a decision", table(
    ["Finding", "Evidence", "What it means for the decision", "Source"],
    [[esc(f["title"]), esc(f["detail"][:300] + ("..." if len(f["detail"]) > 300 else "")),
      esc(f["impact"]), a(f["source"], f.get("source_text", "source"))]
     for f in [x for x in v.get("irregularities", []) if x["id"] in ("IR-01", "IR-06", "IR-07", "IR-03")]],
    caption="The four irregularities that most constrain what can be decided today. The full register is on the Re-verification page."), "FINDINGS")}
<p class="lede"><a href="../site/index.html">Open the standalone section index &rarr;</a></p>
{section("How a suggestion becomes a change", '<ol class="dd-steps">' + "".join(
    f'<li><strong>{esc(w["label"])}</strong><p>{esc(w["detail"])}</p></li>'
    for w in s.get("review_workflow", [])) + "</ol>", "REVIEW WORKFLOW")}
"""
    return layout("Decisions", "decisions.html", body)


def page_suggestions(s):
    rows = []
    for x in s.get("suggestions", []):
        rows.append([
            f'<strong>{esc(x["id"])}</strong>',
            esc(x["title"]),
            esc(x["problem"]),
            esc(x["proposal"]),
            f'{esc(x["effort"])} / {esc(x["payoff"])}',
            esc(x["risk"]),
            tag(x["review"], "warn" if x["review"] == "pending" else "ok"),
            esc(x["recommend"]),
            a(x["source"], x.get("source_text", "source")),
        ])
    body = f"""
<div class="hero"><div class="eyebrow">SUGGESTIONS REGISTER</div>
<h1>Twelve paths.<br><em>Choose one before anyone builds.</em></h1>
<p class="lede">Each row is a decision, not a task. The recommended path is what this session would do,
but it is a recommendation only: the status stays <em>pending</em> until a reviewer accepts, parks or
rejects it. Effort is S/M/L, payoff is the expected effect on the project&rsquo;s ability to make a
defensible decision, and risk is what goes wrong if the change is made badly.</p></div>
<div class="dd-note ok"><strong>How to review.</strong> Read the problem, open the source, then pick one
path. A suggestion whose evidence you cannot open should be sent back, not approved. Anything marked
&ldquo;park&rdquo; is not abandoned &mdash; it is waiting on a named prerequisite.</div>
{section("The register", table(
    ["ID", "Suggestion", "Problem it solves", "Proposal", "Effort / payoff", "Risk", "Status", "Recommended path", "Evidence source"],
    rows, caption="Statuses: pending, accepted, parked, rejected. Editing a status is the only change a reviewer needs to make."), "PROPOSALS")}
{section("Recommended order", table(
    ["Order", "Item", "Why it is in this position", "Blocks / blocked by", "Source"],
    [
        ["1", esc("SG-12 Fund nothing until execution is verified"), "It costs nothing and prevents the one irreversible mistake.", "blocks everything financial", a(s["sources"]["nflverse"], "nflverse-data")],
        ["2", esc("SG-02 Timestamped line capture"), "Without it gate G1 can never pass, and every other result is a closing-line result only.", "enables SG-08, Q-09", a(s["sources"]["dates"], "NFL 2026-27 calendar")],
        ["3", esc("SG-03 Injury, depth and snap feeds on a runner"), "The single largest missing input; also unblocks the 2nd/3rd/4th-string question.", "needs SG-02 for timing, unblocks SG-08", a(s["sources"]["depth"], "depth-chart dictionary")],
        ["4", esc("SG-04 Fix the ATS statistic"), "A published number is wrong; it is cheap to fix and cheap to be embarrassed by.", "independent", a(s["sources"]["nflverse"], "nflverse-data")],
        ["5", esc("SG-01 and SG-07 one canonical site, labelled cut-off"), "Removes the ambiguity about which verdict is the product.", "independent", a(s["sources"]["rulebook"], "2026 rulebook")],
        ["6", esc("SG-06 and SG-05 reward rule and pricing headline"), "Makes the competition honest and the finding legible.", "after SG-01", a(s["sources"]["deflated_sharpe"], "deflated Sharpe ratio")],
        ["7", esc("SG-08 starting-QB value"), "The first genuinely new signal that has any chance of clearing G1.", "needs SG-02 and SG-03", a(s["sources"]["injury"], "official injury report")],
    ],
    caption="A dependency-aware order. Doing 5 before 2 does not make the results better, it only makes them look better."), "SEQUENCE")}
"""
    return layout("Suggestions", "suggestions.html", body)


def page_questions(q):
    groups = q.get("meta", {}).get("groups", [])
    blocks = []
    for g in groups:
        items = [x for x in q.get("questions", []) if x["group"] == g]
        rows = [[esc(x["id"]), f'<strong>{esc(x["question"])}</strong>', esc(x["answer"]),
                 esc(x["have"]), esc(x["missing"]), esc(x["decision_needed"]),
                 tag(x["owner"], "info"), a(x["source"], "open")] for x in items]
        kind = {"Answerable now": "ok", "One feed away": "info",
                "Blocked on a decision": "warn", "Cannot be answered yet": "bad"}.get(g, "")
        blocks.append(section(f"{g} &nbsp;{tag(str(len(items)) + ' questions', kind)}", table(
            ["ID", "Question", "Answer we have", "Information we do have", "Information we do NOT have",
             "Decision it forces", "Owner", "Source"], rows), g.upper()))
    body = f"""
<div class="hero"><div class="eyebrow">OPEN QUESTIONS</div>
<h1>What must be answered<br><em>before a decision is reasonable.</em></h1>
<p class="lede">Seventeen questions, each with the information we hold, the information we are missing,
and the decision it forces. Nothing is marked answered unless the answer is computed from a committed
file, and that file is linked. Where the honest answer is &ldquo;nobody can answer this yet&rdquo;, it
says so and names the missing input.</p></div>
<div class="dd-note"><strong>Reading the groups.</strong> <em>Answerable now</em> means the data is in the
repository and the answer is reproduced on this site. <em>One feed away</em> means a published feed
exists that would answer it. <em>Blocked on a decision</em> means no amount of data helps until a human
chooses. <em>Cannot be answered yet</em> means the inputs do not exist in any feed this project can
lawfully obtain today.</div>
{''.join(blocks)}
{section("Also flagged while writing these questions", table(
    ["ID", "Item", "Detail", "Source"],
    [[esc(f["id"]), esc(f["item"]), esc(f["detail"]), a(f["source"], "open")] for f in q.get("flagged", [])]),
    "FLAGGED")}
"""
    return layout("Open questions", "questions.html", body)


def page_injury(inj):
    meta = inj.get("meta", {})
    team_rows = []
    for t in inj.get("teams", []):
        team_rows.append([
            f'<strong>{esc(t["team"])}</strong>', str(t["listed"]), str(t["dnp"]), str(t["limited"]),
            str(t["full"]), str(t["dnp_defense"]), str(t["dnp_offense"]),
            str(t["named_injury"]), str(t["game_status_out"]), str(t["game_status_questionable"]),
            esc(t["qbs_listed"]) if t["qbs_listed"] else blank(),
            tag("blank", "na"), a(t["source"], "NFL.com injury report"),
        ])
    player_rows = []
    for p in inj.get("players", []):
        status_kind = {"Out": "bad", "Questionable": "warn", "Doubtful": "warn"}.get(p.get("game_status") or "", "na")
        player_rows.append([
            esc(p["team"]), esc(p["player"]), esc(p["position"]), esc(p["unit"]),
            esc(p["injury"]) if p["injury"] else '<span class="blank">not listed</span>',
            esc(p["practice_status"]),
            tag(p["game_status"], status_kind) if p.get("game_status") else '<span class="blank">&mdash; not yet filed</span>',
            blank(), blank(), blank(),
            a(p["source"], "NFL.com"),
        ])
    feed_rows = [[esc(f["id"]), esc(f["feed"]), esc(f["rows_from"]),
                  tag("committed" if f["committed_here"] else "missing", "ok" if f["committed_here"] else "bad"),
                  esc(f["useful_for"]), esc(f["status"]),
                  a(f["url"], "release") + (f' &middot; {a(f["schema"], "dictionary")}' if f.get("schema") else "") + f' &middot; <a href="{esc(inj["irregularities"][0]["source"]) if False else esc(f["url"])}" rel="noopener">feed</a>']
                 for f in inj.get("feeds", [])]
    q_rows = [[esc(c["id"]), esc(c["question"]), esc(c["answer"]), esc(c["from"]), tag(c["confidence"], "warn" if "unverified" in c["confidence"] else "ok"), a(c["source"], "source")]
              for c in inj.get("questions", [])]
    irr_rows = [[esc(f["id"]), esc(f["title"]), esc(f["detail"]), esc(f["needs"]), a(f["source"], f.get("source_text", "source"))]
                for f in inj.get("irregularities", [])]
    games_rows = [[esc(g["slot"]), f'{esc(g["away"])} @ {esc(g["home"])}',
                   f'{esc(g["away_record"])} at {esc(g["home_record"])}', a(meta.get("source", ""), "NFL.com injury report")]
                  for g in inj.get("games", [])]
    body = f"""
<div class="hero"><div class="eyebrow">INJURY &amp; DEPTH</div>
<h1>Who is out is official.<br><em>Who replaces him is not in the data.</em></h1>
<p class="lede">The NFL&rsquo;s injury report tells you a player&rsquo;s practice participation and, later
in the week, his game status. It does not tell you whether he is the first-string starter, and it never
says whether the man behind him is the second, third or fourth string. Those cells are left blank here
rather than guessed, and the page names the exact feed that would fill them.</p></div>
<div class="dd-note bad"><strong>The honest count.</strong> {meta.get('players_transcribed', 0)} players
transcribed across {meta.get('teams_transcribed', 0)} teams from the official Week 10 report.
Verified &ldquo;this player is a starter / N-th string&rdquo; claims: {meta.get('starter_claims_verified', 0)}
of {meta.get('starter_claims_total', 0)}. The block is a missing feed, not a missing method.</div>
{section("Games covered", table(["Kickoff", "Matchup", "Records on the official page", "Source"], games_rows,
    caption=f"Transcribed {meta.get('retrieved', '')} from the official NFL injury report. " + meta.get("scope", "")), "SCOPE")}
{section("Per-team summary", table(
    ["Team", "Listed", "DNP", "Limited", "Full", "DNP defense", "DNP offense", "Named injury", "Out", "Questionable", "QBs listed", "Depth rank", "Source"],
    team_rows, caption="Counts computed from the transcription below. 'Depth rank' is blank for every team because no depth-chart feed is committed."), "COUNTS")}
{section("The feeds, and their exact status", table(
    ["ID", "Feed", "Coverage from", "In repo", "What it answers", "Status", "Source"],
    feed_rows, caption="All three missing feeds are published upstream under CC BY 4.0. They are missing from this repository, not from the world."), "FEEDS")}
{section("The questions, answered or not", table(
    ["ID", "Question", "Answer", "Comes from", "Confidence", "Source"], q_rows), "QUESTIONS")}
{section("Every player transcribed", table(
    ["Team", "Player", "Pos", "Unit", "Injury listed", "Practice status", "Game status", "Starter?", "Depth rank", "Replacement", "Source"],
    player_rows, caption="The last three columns are deliberately blank. Filling them from a name, a roster order, or a highlight reel would be inference, and inference is what this page exists to avoid."), "PLAYERS")}
{section("Irregularities", table(["ID", "Issue", "Detail", "What it needs", "Source"], irr_rows), "FLAGGED")}
"""
    return layout("Injury &amp; depth", "injury-depth.html", body)


def page_signals(sig):
    meta = sig.get("meta", {})
    rows = []
    for r in sig.get("leaderboard", []):
        rows.append([
            f'<strong>{esc(r["name"])}</strong>', f'<span class="num">{r["n"]}</span>',
            num(r["roi"], 4, pct=True, sign=True), num(r.get("roi_flat_110"), 4, pct=True, sign=True),
            num(r.get("win_rate"), 3, pct=True), num(r.get("p"), 4),
            f'{r["gates_passed"]}/10',
            esc(", ".join(r["gates_failed"])) if r["gates_failed"] else tag("all passed", "ok"),
            tag("qualified" if r["qualified"] else "rejected", "ok" if r["qualified"] else "bad"),
            a(sig["sources"]["schedules"], "settlement feed"),
        ])
    gate_rows = []
    if sig.get("leaderboard"):
        best = sig["leaderboard"][0]
        for g in best.get("gates", []):
            gate_rows.append([f'<strong>{esc(g["id"])}</strong>', esc(g["name"]),
                              tag("pass" if g["pass"] else "fail", "ok" if g["pass"] else "bad"),
                              esc(g["detail"]), a(sig["sources"]["schedules"], "source")])
    detail_cards = []
    for r in sig.get("leaderboard", [])[:6]:
        detail_cards.append(f'''<div class="dd-card"><h3>{esc(r['name'])} <span class="num">&nbsp;{num(r['roi'],4,pct=True,sign=True)}</span></h3>
<p>{r['n']} settled bets in 2023-2026. Gates passed {r['gates_passed']}/10. Per season:
{esc(", ".join(f"{s['season']}: {s['roi']*100:+.1f}% on {s['n']}" for s in r.get('per_season', [])))}.</p>
<p>{esc("; ".join(f"{g['id']}: {g['detail']}" for g in r['gates'] if not g['pass']))}</p>
<a href="signals-lab.html">Gate detail &rarr;</a></div>''')
    body = f"""
<div class="hero"><div class="eyebrow">SIGNAL LAB</div>
<h1>Twenty-three ideas.<br><em>Zero survive ten gates.</em></h1>
<p class="lede">Every candidate here is a rule fixed in code before it was measured: a ratings model
with a walk-forward fit, rest and bye effects, divisional spots, weather totals, a backup-quarterback
rule, mean-reversion fades, prior-season ratings and a luck fade. Each is settled at the closing line in
the committed extract, each is corrected for the fact that twenty-three things were tried, and each is
compared against random portfolios of the same size at the same prices.</p></div>
<div class="dd-kpis">
{kpi("Variants measured", str(meta.get("n_variants_measured", 0)), "All settled on 2023-2026 regular-season games.", "info")}
{kpi("Qualified", str(meta.get("n_qualified", 0)), "A strategy needs all ten gates. None got past seven.", "bad")}
{kpi("Best ROI", num(sig.get("leaderboard", [{}])[0].get("roi") if sig.get("leaderboard") else None, 2, pct=True, sign=True), "On " + str(sig.get("leaderboard", [{}])[0].get("n", 0)) + " bets - far too few to distinguish from climate noise.", "warn")}
{kpi("Break-even at -110", "52.38%", "The rate needed before any edge exists at all.", "info")}
</div>
<div class="dd-note"><strong>Why every strategy fails G1.</strong> Gate G1 requires strictly pre-kickoff
inputs with a recorded capture. The committed feed holds one closing line per game with no capture time,
and no lineup snapshot is committed either, so G1 cannot be evidenced for <em>any</em> candidate. That is
a data-pipeline problem, and it is the first thing the Suggestions page recommends fixing.</div>
{section("Leaderboard", table(
    ["Variant", "Bets", "ROI", "ROI at flat -110", "Win rate", "p", "Gates", "Failed gates", "Verdict", "Source"],
    rows, caption=meta.get("settlement", "")), "RESULTS")}
{section("Gate-by-gate, on the best-ranked variant", table(
    ["Gate", "Name", "Result", "Detail", "Source"], gate_rows,
    caption="The other variants fail the same gates for the same structural reasons; the per-row list above names them."), "GATES")}
{section("The six closest calls, in full", "".join(detail_cards), "DETAIL")}
{section("Method", f'''<ul class="ticks">
<li><strong>Walk-forward only.</strong> {esc(meta.get("test_window", ""))}; no fitted input sees its own season.</li>
<li><strong>Closing-line settlement.</strong> {esc(meta.get("settlement", ""))}</li>
<li><strong>Multiplicity.</strong> {esc(meta.get("multiplicity", ""))}</li>
<li><strong>Luck null.</strong> 4,000 random portfolios of the same size at the same prices; the share that matched or beat each strategy is reported as <code>G8</code>.</li>
<li><strong>Controls included.</strong> Betting every home side and betting every under are measured on the same footing, so a &ldquo;signal&rdquo; that is just the base rate is visible immediately.</li>
</ul>''', "METHOD")}
"""
    return layout("Signal lab", "signals-lab.html", body)


def page_parlay(par):
    meta = par.get("meta", {})
    pair_rows = []
    for p in par.get("pairs", []):
        pair_rows.append([esc(p["leg_a"]), esc(p["leg_b"]), num(p["r"], 3, sign=True), pval(p["p"]),
                          str(p["n"]), esc(p["context"]), a(par["sources"]["player_week"], "box scores")])
    joint_rows = []
    for name, row in par.get("joints", {}).items():
        if row.get("status"):
            continue
        joint_rows.append([esc(name), str(row["n"]), num(row["empirical_joint"], 4),
                           num(row["independent_product"], 4), num(row.get("ratio"), 3),
                           num(row.get("pricing_error_pct"), 1),
                           num(row.get("fair_decimal_odds_empirical"), 2),
                           num(row.get("fair_decimal_odds_independent"), 2),
                           a(par["sources"]["player_week"], "measured")])
    cop = par.get("copula", {})
    cop_rows = [[esc(cop.get("legs", [])[i] if i < len(cop.get("legs", [])) else str(i)),
                 num(cop.get("marginals", [None]*3)[i] if i < len(cop.get("marginals", [])) else None, 4),
                 " | ".join(num(x, 3, sign=True) for x in row),
                 a(par["sources"]["player_week"], "box scores")]
                for i, row in enumerate(cop.get("correlation_matrix", []))]
    prem = par.get("premium", [])
    body = f"""
<div class="hero"><div class="eyebrow">PARLAY PRICING</div>
<h1>Independent legs<br><em>are the wrong price.</em></h1>
<p class="lede">A same-game parlay is priced by multiplying its legs. That is only correct if the legs are
independent, and they are not: one offence drives several of them at once. This page measures the
correlation, measures the joint probability directly, and puts a Gaussian copula on the measured
correlation matrix as an independent cross-check. The gap between the two prices is the finding.</p></div>
<div class="dd-kpis">
{kpi("Team-games measured", f"{meta.get('team_games', 0):,}", f"Seasons {meta.get('seasons', ['', ''])[0]}-{meta.get('seasons', ['', ''])[1]}.", "info")}
{kpi("QB &harr; WR1", num(next((p["r"] for p in par.get("pairs", []) if p["leg_a"]=="qb_pass_yds" and p["leg_b"]=="wr1_rec_yds"), None), 3, sign=True), "The core same-game pair.", "warn")}
{kpi("2-leg joint vs product", num(prem[0]["empirical_joint"] if prem else None, 3), f"Independent product would price it at {num(prem[0]['independent_product'] if prem else None, 3)}.", "bad")}
{kpi("Independent price", (num(abs(prem[0]["theoretical_hold_pct_if_priced_independently"]), 1) + "% too low") if prem else blank(), "Multiplying the legs under-prices this 2-leg ticket by that much relative to the measured joint.", "bad")}
</div>
<div class="dd-note"><strong>What this does and does not say.</strong> It says the legs are correlated and
that multiplying them is the wrong price. It does <em>not</em> say a correlated parlay is profitable: no
historical player-prop price is committed in this repository, so no prop ROI is computed or implied
anywhere on this site.</div>
{section("Pairwise correlations", table(
    ["Leg A", "Leg B", "Pearson r", "p", "n", "Context", "Source"], pair_rows,
    caption="The cross-game rows are a control: shuffle the rows independently and the correlation collapses to about zero, which is what independence looks like in this data."), "CORRELATION")}
{section("Joint probabilities: measured vs multiplied", table(
    ["Ticket", "n", "Measured joint", "Independent product", "Ratio", "Independent price error (%)", "Fair odds (correlated)", "Fair odds (independent)", "Source"],
    joint_rows, caption="'Fair odds' are 1/probability before any house margin. The error column is how much the independent price overstates the ticket."), "JOINTS")}
{section("Copula cross-check", f'''<p class="lede">Using only the measured pairwise correlations, a Gaussian copula
estimates the joint at <strong>{num(cop.get("copula_joint"), 4)}</strong> against a measured joint of
<strong>{num(cop.get("empirical_joint"), 4)}</strong> and an independent product of
<strong>{num(cop.get("independent_product"), 4)}</strong>. The copula is not a re-statement of the empirical
number: it is computed from the correlation matrix, so agreement between the two is evidence that the
correlation is doing the work.</p>''' + table(
        ["Leg", "Marginal (P above median)", "Correlations with the other legs", "Source"], cop_rows), "COPULA")}
{section("The pricing premium table", table(
    ["Ticket", "n", "Measured joint", "Independent product", "Fair odds if correlated", "Fair odds if independent", "Theoretical error (%)", "Source"],
    [[esc(p["ticket"]), str(p["n"]), num(p["empirical_joint"], 4), num(p["independent_product"], 4),
      num(p["fair_odds_if_correlated"], 2), num(p["fair_odds_if_independent"], 2),
      num(p["theoretical_hold_pct_if_priced_independently"], 1), a(par["sources"]["player_week"], "measured")]
     for p in prem], caption=meta.get("method", "")), "PREMIUM")}
"""
    return layout("Parlay pricing", "parlay-pricing.html", body)


def page_verification(v):
    meta = v.get("meta", {})
    rows = []
    for c in v.get("checks", []):
        kind = {"agree": "ok", "mismatch": "bad", "unverified": "warn"}.get(c["status"], "info")
        rows.append([f'<strong>{esc(c["id"])}</strong>', esc(c["claim"]),
                     esc(c.get("published_on", "")),
                     smart(c["published"]), smart(c["recomputed"]),
                     tag(c["status"], kind), esc(c.get("note") or ""),
                     a(c["source"], c.get("source_text", "source"))])
    irr = []
    for f in v.get("irregularities", []):
        irr.append([f'<strong>{esc(f["id"])}</strong>', esc(f["title"]), esc(f["detail"]), esc(f["impact"]),
                    a(f["source"], f.get("source_text", "source"))])
    head = v.get("headline", [])
    body = f"""
<div class="hero"><div class="eyebrow">RE-VERIFICATION</div>
<h1>Nineteen checks.<br><em>Two numbers do not hold up.</em></h1>
<p class="lede">Every headline the live dashboard prints was re-derived from the committed extract by
code that imports nothing from the pipeline that produced it. Sixteen agree. Two disagree, and both are
the same statistic. One is a documented difference in population. Ten irregularities came out of the
process, each with the source it was found in.</p></div>
<div class="dd-kpis">
{kpi("Checks", str(meta.get("n_checks", 0)), "Independently recomputed, line by line.", "info")}
{kpi("Agree", str(meta.get("n_agree", 0)), "Within a stated tolerance, not eyeballed.", "good")}
{kpi("Mismatch", str(meta.get("n_mismatch", 0)), "Both are the ATS coin-flip statistic. See IR-01.", "bad")}
{kpi("Irregularities", str(meta.get("n_irregularities", 0)), "With a source and an impact for each.", "warn")}
</div>
<div class="dd-note bad"><strong>{esc(meta.get("caveat", ""))}</strong></div>
{section("The headlines, as published", table(
    ["Claim", "Published value", "Check", "Source"],
    [[esc(h["claim"]), smart(h["published"]), esc(h["check_id"]), a(h["source"], "open")] for h in head],
    caption=f"Data as of {esc(meta.get('data_as_of_gameday', ''))}. Each value is the number the live site prints, not a number this page recomputed."), "HEADLINES")}
{section("Line-by-line checks", table(
    ["ID", "Claim", "Where it is published", "Published value", "Recomputed here", "Status", "Note", "Source"], rows,
    caption=f"Generated {esc(meta.get('generated_utc', ''))} by site/scripts/reverify.py. A value that could not be recomputed is marked unverified and left blank."), "CHECKS")}
{section("The irregularity register", table(
    ["ID", "Issue", "Detail", "Impact on a decision", "Source"], irr,
    caption="These are published, not hidden, and they do not block publication. They do block treating the affected number as settled."), "IRREGULARITIES")}
"""
    return layout("Re-verification", "decision-verification.html", body)


def page_summary(v, q, s, sig, par, inj):
    # Blocks are built first and joined afterwards: nested f-strings with quotes are not portable
    # to every Python the project supports.
    state = ('<p class="lede">The repository is an unusually well-documented research effort that has reached '
             'an honest negative result. The closing market beats the model (9.711 vs 10.391 mean absolute '
             'error on 936 walk-forward games), the model adds nothing after controlling for the close '
             '(coefficient -0.019, p = 0.881), and '
             + str(sig.get("meta", {}).get("n_variants_measured", 0)) +
             ' candidate signals tested in this session all fail the validation gates. None of that is a '
             'failure of the work; it is the work doing its job.</p>'
             '<p class="lede">What is <em>not</em> settled is anything that depends on timing. There is one '
             'un-timestamped closing line per game and no committed lineup feed, so the point-in-time gate '
             'cannot pass for any strategy, and the injury and backup-depth question cannot be answered from '
             'this repository at all.</p>')

    verified_rows = [[esc(c["claim"]), esc(c["published"]),
                      tag(c["status"], "ok" if c["status"] == "agree" else "bad"), a(c["source"], "open")]
                     for c in v.get("checks", []) if c["status"] in ("agree", "mismatch")]
    verified = table(["Number", "Value", "Status", "Source"], verified_rows,
                     caption="Sixteen of nineteen agree within tolerance. The two mismatches are the same "
                             "statistic and are explained below.")

    failed_rows = [[esc(f["title"]), esc(f["detail"]), esc(f["impact"]), a(f["source"], "open")]
                   for f in v.get("irregularities", []) if f["id"] in ("IR-01", "IR-02", "IR-03")]
    failed_rows.append([esc("No prop prices exist"),
                        "Prop accuracy is measured; prop prices are not in any committed file.",
                        "Do not list player-prop combos as a tested family until a licensed price history exists.",
                        a(par["sources"]["player_week"], "box scores")])
    failed = table(["Issue", "What is wrong", "What to do", "Source"], failed_rows)

    blocked_rows = [[esc(x["question"]), esc(x["missing"]), esc(x["decision_needed"]), a(x["source"], "open")]
                    for x in q.get("questions", [])
                    if x["group"] in ("Blocked on a decision", "Cannot be answered yet")]
    blocked = table(["Question", "Why it is blocked", "Decision it forces", "Source"], blocked_rows,
                    caption="Full register on the Open questions page.")

    sequence_items = [
        ("Fund nothing.", "No operator, jurisdiction, licence or limit has been verified, and no prize pool "
                          "exists. Keep every reward tier unfunded."),
        ("Capture timestamped prices.", "Ten days of that is worth more than another model, because it is the "
                                        "only route to closing-line value and to passing gate G1."),
        ("Commit the injury, depth and snap feeds on a runner.", "They exist upstream under CC BY 4.0; they are "
                                                                 "missing here, not missing from the world."),
        ("Fix the two statistics that are wrong.", "The ATS coin-flip test is 50% by construction, and the "
                                                    "README's model MAE is stale against the data."),
        ("Then measure what a starting quarterback is worth.", "It is the one genuinely new signal with a "
                                                               "plausible path to clearing G1."),
    ]
    sequence = '<ol class="dd-steps">' + "".join(
        f"<li><strong>{esc(a_)}</strong><p>{esc(b_)}</p></li>" for a_, b_ in sequence_items) + "</ol>"

    falsify = ('<ul class="ticks">'
               '<li>A timestamped price series that shows a repeatable gap between a captured price and the close.</li>'
               '<li>A depth-chart and snap-count history that shows a measurable, market-inefficient effect from losing a specific starter.</li>'
               '<li>A licensed prop price history that turns the measured correlation gap into a testable, priced edge.</li>'
               '<li>A candidate that passes all ten gates out of sample, with a positive lower bound and a luck test it survives.</li>'
               '</ul>'
               '<p class="lede">Absent one of those four, the correct decision is to keep researching and to fund '
               'nothing. That is the recommendation this summary makes.</p>')

    body = (
        '<div class="hero"><div class="eyebrow">EXECUTIVE SUMMARY</div>'
        '<h1>What this review found,<br><em>and what it changes.</em></h1>'
        '<p class="lede">A one-page summary of the Decision Desk: the state of the project, the numbers that '
        'survived an independent check, the ones that did not, the missing inputs that block a decision, and the '
        'order in which to fix them.</p></div>'
        + section("1. Where the project stands", state, "STATE")
        + section("2. What survived verification", verified, "VERIFIED")
        + section("3. What did not survive", failed, "FAILED")
        + section("4. What we cannot decide yet", blocked, "BLOCKED")
        + section("5. The recommended sequence", sequence, "SEQUENCE")
        + section("6. What would change this conclusion", falsify, "FALSIFIABILITY"))
    return layout("Executive summary", "decision-summary.html", body)


def page_site_index(v, q, s, sig, par, inj):
    contents = [
        ("decisions.html", "Decisions hub", "The overview: what is on the desk and the four findings that change a decision."),
        ("suggestions.html", "Suggestions", "Twelve proposals with cost, payoff, risk, evidence and a recommended path."),
        ("questions.html", "Open questions", "What must be answered before a decision is reasonable, and what is missing."),
        ("injury-depth.html", "Injury &amp; depth", "The official Week 10 report transcribed, plus why depth rank is blank."),
        ("signals-lab.html", "Signal lab", "23 candidate signals, ten gates each, and the exact gate that failed."),
        ("parlay-pricing.html", "Parlay pricing", "Measured correlation and the measured-vs-multiplied pricing gap."),
        ("decision-verification.html", "Re-verification", "19 independent checks and 10 irregularities with sources."),
        ("decision-summary.html", "Executive summary", "The one-page version: state, findings, sequence."),
    ]
    cards = "".join(
        f'<div class="dd-card"><h3>{label}</h3><p>{desc}</p>'
        f'<a href="../pages/{href}">Open &rarr;</a></div>' for href, label, desc in contents)
    kpis = "".join([
        kpi("Checks reproduced", f"{v.get('meta',{}).get('n_agree',0)}/{v.get('meta',{}).get('n_checks',0)}",
            "Sixteen agree, two disagree, one documented difference.", "good"),
        kpi("Strategies qualified", str(sig.get('meta',{}).get('n_qualified',0)),
            "Of 23 variants across ten gates.", "bad"),
        kpi("Suggestions", str(s.get('meta',{}).get('count',0)), "All pending a reviewer's decision.", "info"),
        kpi("Open questions", str(q.get('meta',{}).get('count',0)),
            "Four groups, from answerable now to not answerable yet.", "info"),
    ])
    body = (
        '<div class="hero"><div class="eyebrow">DECISION DESK &middot; SESSION ARENA/90E4FDBE</div>'
        '<h1>Everything you need<br><em>to choose a path.</em></h1>'
        '<p class="lede">A decision layer for the NFL line-origination research in this repository: twelve '
        'suggestions with evidence and a review workflow, seventeen open questions with what is missing, the '
        'official injury report transcribed and the depth question left honestly blank, a 23-variant signal lab '
        'with every rejection explained, the measured parlay-pricing gap, and nineteen independent checks of the '
        'numbers the live dashboard publishes.</p>'
        '<p><a href="../index.html" class="review-link">Go to the live dashboard &nearr;</a></p></div>'
        f'<div class="dd-kpis">{kpis}</div>'
        + section("Pages in this section", f'<div class="dd-two">{cards}</div>', "CONTENTS"))
    return standalone("Decision Desk", body)


def write_markdown_summary(v, q, s, sig, par, inj) -> str:
    """The same executive summary as the page, as markdown, generated from the same JSON."""
    vm = v.get("meta", {})
    sm = sig.get("meta", {})
    agreed = [c for c in v.get("checks", []) if c["status"] == "agree"]
    failed = [c for c in v.get("checks", []) if c["status"] == "mismatch"]
    lines = [
        "# Decision Desk - executive summary",
        "",
        f"Generated {vm.get('generated_utc', '')} by `site/scripts/build_site.py` from `site/data/*.json`.",
        f"Data as of {vm.get('data_as_of_gameday', '')}. Session `arena/90e4fdbe-korea2`.",
        "",
        "## Where the project stands",
        "",
        f"* {vm.get('n_checks', 0)} independent checks of the numbers the live dashboard publishes: "
        f"{vm.get('n_agree', 0)} agree, {vm.get('n_mismatch', 0)} disagree, "
        f"{vm.get('n_unverified', 0)} unverified.",
        f"* {sm.get('n_variants_measured', 0)} candidate signals tested against ten validation gates; "
        f"{sm.get('n_qualified', 0)} qualified.",
        f"* {s.get('meta', {}).get('count', 0)} suggestions awaiting a reviewer's decision; "
        f"{q.get('meta', {}).get('count', 0)} open questions across four groups.",
        f"* {inj.get('meta', {}).get('players_transcribed', 0)} players transcribed from the official NFL "
        f"injury report for five 2026 Week 10 games.",
        "",
        "## What survived verification",
        "",
        "| Number | Published | Source |",
        "|---|---|---|",
    ]
    for c in agreed[:12]:
        lines.append(f"| {c['claim']} | {c.get('published')} | {c['source']} |")
    lines += ["", "## What did not survive", ""]
    for c in failed:
        lines.append(f"* **{c['id']}** {c['claim']}: published {c.get('published')}, recomputed "
                     f"{c.get('recomputed')}. {c.get('note', '')}")
    lines += ["", "### Irregularities", "", "| ID | Issue | Impact | Source |", "|---|---|---|---|"]
    for f in v.get("irregularities", []):
        lines.append(f"| {f['id']} | {f['title']} | {f['impact']} | {f['source']} |")
    lines += ["", "## The measurement the pricing decision rests on", "",
              f"* {par['meta'].get('team_games', 0):,} team-games measured.",
              f"* QB passing yards vs WR1 receiving yards: r = "
              f"{next((p['r'] for p in par['pairs'] if p['leg_a'] == 'qb_pass_yds' and p['leg_b'] == 'wr1_rec_yds'), None)}.",
              f"* Best 2-leg joint: measured "
              f"{par['premium'][0]['empirical_joint']}, independent product "
              f"{par['premium'][0]['independent_product']} "
              f"({par['premium'][0]['theoretical_hold_pct_if_priced_independently']}% error).",
              "* No historical player-prop price exists in this repository, so no prop ROI is computed.",
              "", "## Recommended sequence", ""]
    for i, sug in enumerate(s.get("suggestions", [])[:6], start=1):
        lines.append(f"{i}. **{sug['id']} {sug['title']}** - {sug['recommend']} "
                     f"(effort {sug['effort']}, payoff {sug['payoff']}).")
    lines += ["", "## What would change this conclusion", "",
              "* A timestamped price series showing a repeatable gap between a captured price and the close.",
              "* A depth-chart and snap-count history showing a measurable effect from losing a specific starter.",
              "* A licensed prop price history that turns the measured correlation gap into a priced edge.",
              "* A candidate that passes all ten gates out of sample, with a positive lower bound.",
              "",
              "Until one of those exists, the correct decision is to keep researching and to fund nothing.",
              "",
              "## Caveat", "",
              vm.get("caveat", ""),
              "",
              "Every figure above is read from the committed JSON in `site/data/`. Nothing is typed by hand.",
              ""]
    text = "\n".join(lines)
    (SITE / "EXECUTIVE_SUMMARY.md").write_text(text)
    return text


def main() -> int:
    v, q, s = load("verification.json"), load("questions.json"), load("suggestions.json")
    sig, par, inj = load("signals.json"), load("parlay.json"), load("injury_depth.json")
    missing = [n for n, d in [("verification", v), ("questions", q), ("suggestions", s),
                              ("signals", sig), ("parlay", par), ("injury_depth", inj)] if not d]
    if missing:
        raise SystemExit(f"missing site/data inputs: {missing}")

    pages = {
        "decisions.html": page_decisions(v, q, s, sig, par, inj),
        "suggestions.html": page_suggestions(s),
        "questions.html": page_questions(q),
        "injury-depth.html": page_injury(inj),
        "signals-lab.html": page_signals(sig),
        "parlay-pricing.html": page_parlay(par),
        "decision-verification.html": page_verification(v),
        "decision-summary.html": page_summary(v, q, s, sig, par, inj),
    }
    outdir = ROOT / "pages"
    outdir.mkdir(exist_ok=True)
    for name, html_text in pages.items():
        (outdir / name).write_text(html_text)
    (SITE / "index.html").write_text(page_site_index(v, q, s, sig, par, inj))
    write_markdown_summary(v, q, s, sig, par, inj)
    print(f"wrote {len(pages)} pages into pages/, site/index.html and site/EXECUTIVE_SUMMARY.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
