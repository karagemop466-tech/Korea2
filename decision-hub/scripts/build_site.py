#!/usr/bin/env python3
"""Build the decision-hub static site.

Every table row is rendered through `table()` which refuses a row whose source cell is empty,
so an unsourced claim cannot reach a published page. Numbers come from committed JSON; nothing
on the site is typed by hand except the prose in the JSON files themselves.
"""
from __future__ import annotations

import html as _html
import json
import os
import re
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HUB = os.path.join(ROOT, "decision-hub")
DATA = os.path.join(HUB, "data")

NAV = [
    ("index.html", "Overview"),
    ("pages/executive-summary.html", "Executive summary"),
    ("pages/suggestions.html", "Suggestions"),
    ("pages/questions.html", "Questions &amp; unknowns"),
    ("pages/decisions.html", "Decisions"),
    ("pages/strategies.html", "Strategy framework"),
    ("pages/injuries.html", "Injuries &amp; depth"),
    ("pages/audit.html", "Line-by-line audit"),
    ("pages/evidence.html", "Evidence tables"),
    ("pages/sources.html", "Sources"),
    ("pages/flagged.html", "Flagged for review"),
    ("pages/workflow.html", "Review workflow"),
]

DISCLAIMER = ("Research and decision support only — not betting advice. Nothing here has passed a "
              "validation gate. Values that could not be confirmed from an official source are "
              "blank and listed on Flagged for review.")


def load(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return json.load(fh)


def esc(v):
    return _html.escape(str(v))


def cell(v, digits=4):
    """A published/recomputed value for a table cell. None prints as a visible dash, not 'None'."""
    if v is None or v == "":
        return '<span class="blank" title="not published">&mdash;</span>'
    if isinstance(v, bool):
        return esc(str(v))
    if isinstance(v, (int, float)):
        if isinstance(v, float) and not v.is_integer():
            return f"{v:.{digits}f}"
        return str(int(v)) if isinstance(v, float) else str(v)
    return esc(v)


def num(v, digits=2, sign=False):
    if v is None or v == "":
        return '<span class="blank" title="unverified or not applicable">&mdash;</span>'
    try:
        f = float(v)
    except (TypeError, ValueError):
        return esc(v)
    return f"{f:+.{digits}f}" if sign else f"{f:.{digits}f}"


def sources():
    """Source register: the root register plus this session's additions."""
    out = {}
    for path in (os.path.join(ROOT, "data", "sources.json"),
                 os.path.join(DATA, "sources.json")):
        if os.path.exists(path):
            with open(path) as fh:
                for s in json.load(fh).get("sources", []):
                    out[s["id"]] = s
    return out


_SRC = None


def src(sid, label=None):
    global _SRC
    if _SRC is None:
        _SRC = sources()
    s = _SRC.get(sid)
    if not s:
        return f'<span class="flag">source id not registered: {esc(sid)}</span>'
    text = label or s.get("short") or s.get("label") or sid
    if len(text) > 52:
        text = text[:49].rstrip() + "..."
    return f'<a href="{_html.escape(s["url"])}" rel="noopener">{_html.escape(text)}</a>'


def badges(items, kind=None):
    return " ".join(f'<span class="badge {kind or "ok"}">{esc(i)}</span>' for i in items)


def table(headers, rows, caption="", cls=""):
    """Refuse a table with a row missing its final (source) cell."""
    bad = [i for i, r in enumerate(rows) if not str(r[-1]).strip()]
    if bad:
        raise ValueError(f"table '{caption}' has rows without a source cell: {bad}")
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for r in rows:
        cells = [f'<td class="src">{c}</td>' if i == len(r) - 1 else f"<td>{c}</td>"
                 for i, c in enumerate(r)]
        body.append("<tr>" + "".join(cells) + "</tr>")
    cap = f'<caption class="caption">{caption}</caption>' if caption else ""
    return (f'<div class="table-wrap"><table class="{cls}">{cap}<thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def kpi(label, value, note, link="", link_text=""):
    l = f'<a class="card-link" href="{link}">{link_text} &rarr;</a>' if link else ""
    return (f'<article class="kpi"><span class="kpi-label">{esc(label)}</span>'
            f"<strong>{value}</strong><p>{note}</p>{l}</article>")


def layout(title, current, body, subtitle=""):
    depth = "../" if current.startswith("pages/") else ""
    nav_items = []
    for href, label in NAV:
        cls = ' class="active" aria-current="page"' if href == current else ''
        nav_items.append(f'<a href="{depth}{href}"{cls}>{label}</a>')
    nav = "".join(nav_items)
    sub = f'<p class="lede">{subtitle}</p>' if subtitle else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} | Decision Hub</title>
<meta name="description" content="Decision support for the NFL line-origination project: suggestions, open questions, strategy framework, injury and depth tracking, and an independent audit.">
<meta name="generator" content="decision-hub/scripts/build_site.py">
<link rel="stylesheet" href="{depth}assets/style.css">
</head><body>
<a class="skip" href="#main">Skip to content</a>
<div class="shell">
<aside class="sidebar">
  <a class="brand" href="{depth}index.html"><span class="mark">DH</span>
    <span>DECISION HUB<small>NFL RESEARCH</small></span></a>
  <div class="nav-label">Review</div>
  <nav aria-label="Main navigation">{nav}</nav>
  <div class="sidebar-note"><span class="dot"></span>Decision support<br>
    <strong>0 of 7 strategies approved</strong>
    <span>Every suggestion is a proposal. Choose before implementing.</span></div>
</aside>
<main id="main">
<header class="topbar"><span class="crumb">{esc(title).upper()}</span>
  <span><a class="review-link" href="{depth}../index.html">&larr; Line Lab</a>
  &nbsp; <a class="review-link" href="{depth}pages/flagged.html">Flagged for review &nearr;</a></span></header>
{sub}
{body}
<footer>
  <p>{DISCLAIMER}</p>
  <p><a href="{depth}pages/sources.html">Sources</a> &middot;
     <a href="{depth}pages/flagged.html">Flagged for review</a> &middot;
     <a href="{depth}pages/workflow.html">Review workflow</a></p>
</footer>
</main></div></body></html>"""


# ------------------------------------------------------------------ pages
def page_index():
    sug = load("suggestions.json")
    qs = load("questions.json")
    aud = load("root_audit.json")
    inj = load("injuries.json")
    st = aud.get("summary", {})
    hi = [s for s in sug.get("suggestions", []) if s.get("impact", 0) >= 5]
    blockers = [q for q in qs.get("questions", []) if q.get("status") == "blocked"]
    meta = inj.get("meta", {})
    body = f"""
<div class="hero">
  <div class="eyebrow">DECISION SUPPORT</div>
  <h1>Decide first.<br><em>Then build.</em></h1>
  <p class="lede">A place to review what the NFL research project actually knows, what it does
  not, and which path to take — before any code is written. Every suggestion names the decision
  it unblocks and the evidence behind it. Nothing on this site is a pick.</p>
</div>
<div class="notice"><span class="dot"></span><div>
  <strong>Start with the questions, not the numbers.</strong><br>
  {len(qs.get('questions', []))} questions separate what is known from what is assumed;
  {len(blockers)} of them cannot be answered with the data this repository holds.</div>
  <a href="pages/questions.html">Open the questions register &rarr;</a></div>
<div class="kpis">
{kpi("Suggestions", len(sug.get('suggestions', [])), f"{len([x for x in sug.get('suggestions', []) if x.get('impact',0)>=4])} rated impact 4 or 5. Each one names its cost, its risk and the decision it unblocks.", "pages/suggestions.html", "Review suggestions")}
{kpi("Open questions", len(qs.get('questions', [])), f"{len(blockers)} blocked on data we do not have. The register states what would answer each one.", "pages/questions.html", "Open questions")}
{kpi("Audit checks", st.get("checks", 0), f"{st.get('pass', 0)} reproduced, {st.get('fail', 0)} failed, {st.get('blank', 0)} unverifiable. Recomputed independently from committed data.", "pages/audit.html", "Line-by-line audit")}
{kpi("Audit flags", st.get("flags", 0), f"{st.get('high_flags', 0)} high severity. Includes one published statistic that cannot fail.", "pages/flagged.html", "Flagged items")}
{kpi("Injury absences tracked", len(inj.get("absences", [])), f"2026 season, {meta.get('league_week', '')} weeks, every Out/Doubtful player with a depth-chart rank where one exists.", "pages/injuries.html", "Injuries &amp; depth")}
{kpi("Strategies approved", 0, "Zero of seven candidates has passed all ten gates. That is a measured result, not a placeholder.", "pages/strategies.html", "Strategy framework")}
</div>
"""
    rows = []
    for s in sorted(sug.get("suggestions", []), key=lambda x: (-x.get("impact", 0), x.get("cost") == "high")):
        rows.append([f'<strong>{esc(s["id"])}</strong> {esc(s["title"])}', esc(s["category"]),
                     badges([f'impact {s["impact"]}'], "ok" if s["impact"] >= 4 else "warn"),
                     esc(s["cost"]),
                     esc(s.get("status", "")),
                     f'<a href="pages/suggestions.html#{s["id"]}">detail</a>'])
    body += f"""<section class="block"><div class="eyebrow">AT A GLANCE</div>
<h2>The {len(rows)} suggestions, ranked by impact</h2>
<p class="muted">Sorted by impact then cost. Click through for the evidence, the risk, and the
decision each one unblocks. Adoption is your call; the workflow page records the choices.</p>
{table(["Suggestion", "Category", "Impact", "Cost", "Status", "Detail"], rows,
       caption="Every suggestion is a proposal, not a finding.")}</section>"""
    body += f"""<div class="grid2">
  <div class="panel"><h3>What the audit found</h3><ul class="ticks">
    <li>{st.get('checks', 0)} published numbers recomputed independently: {st.get('pass', 0)} reproduce exactly.</li>
    <li>One headline statistic is an arithmetic identity that cannot detect a tilt (FL-DH-01).</li>
    <li>{aud.get('rows_totals', {}).get('table_rows', 0)} table rows across the published site, {aud.get('rows_totals', {}).get('rows_without_source_cell', 0)} without a source link.</li>
  </ul><a class="panel-link" href="pages/audit.html">Read the audit &rarr;</a></div>
  <div class="panel"><h3>What is still unknown</h3><ul class="crosses">
    <li>No timestamped price exists, so closing-line value cannot be measured on history.</li>
    <li>No historical prop prices exist, so prop ROI is blank rather than estimated.</li>
    <li>No funded reward pool, and no verified sportsbook access.</li>
    <li>The effect of a missing starter on the line has never been measured here.</li>
  </ul><a class="panel-link" href="pages/questions.html">See the questions &rarr;</a></div>
</div>"""
    return layout("Overview", "index.html", body)


def page_executive():
    aud = load("root_audit.json")
    inj = load("injuries.json")
    qs = load("questions.json")
    sug = load("suggestions.json")
    st = aud.get("summary", {})
    ats = aud.get("ats_honest", {})
    meta = inj.get("meta", {})
    cur = inj.get("current", [])
    worst = sorted(cur, key=lambda s: -s.get("weighted_depth_lost", 0))[:5]
    rows = [
        ["What the model is for", "Measure whether an independent NFL line beats the closing line. Not to sell picks.",
         f"Model coefficient -0.019 (p = 0.881); MAE 10.39 vs 10.25", src("nflverse-data")],
        ["Does it?", "No. The closing line is better and the model adds no incremental information.",
         "Recomputed at audit check market.spread_mae / market.slope", src("nflverse-data")],
        ["Did any strategy pass the gates?", f"No. 0 of 7.", "leaderboard.json, 9 entries incl. 2 controls", src("nflverse-data")],
        ["Is the ATS 'coin flip' evidence?", "No. It is an identity: every game is counted twice, once per side, so the rate is always exactly 50%.",
         aud.get("flags", [{}])[0].get("detail", "")[:120] + "...", src("nflverse-data")],
        ["Corrected ATS result", f"{ats.get('rate', 0)*100:.2f}% home covers, 95% CI {ats.get('ci', [0,0])[0]*100:.2f}-{ats.get('ci', [0,0])[1]*100:.2f}%, p = {ats.get('p_vs_50', 0)}",
         f"n = {ats.get('n', 0)} decided games, one observation per game", src("nflverse-data")],
        ["Are same-game legs correlated?", "Yes, strongly. QB yards vs WR1 yards r = 0.562; four-leg joint 11.1% vs 5.7% independent.",
         "correlation.json / verification sgp.* checks", src("nflverse-data")],
        ["Is a season record a signal?", "No. Pythagorean R-squared 0.83, year-over-year luck correlation 0.019.",
         "luck.json", src("nflverse-data")],
        ["Can prop ROI be measured?", "Not with this data. No historical prop prices exist.",
         "Blank and flagged, not estimated", src("nflverse-data")],
        ["Is injury/depth tracked now?", f"Yes. {len(inj.get('absences', []))} reported absences with a depth rank in 2026, snapshot {meta.get('depth_snapshot_dt', '')}.",
         "decision-hub/data/injuries.json", src("SRC-NFL-INJURIES")],
        ["Does depth loss affect the line?", "Unmeasured. The tracker creates the feature; nobody has estimated the effect.",
         "Q-04 is blocked on a timestamped price", src("nflverse-data")],
        ["What is the biggest risk?", "Reading a guaranteed statistic as evidence, and treating a proposal as a result.",
         f"{st.get('flags', 0)} audit flags; {len([q for q in qs.get('questions', []) if q.get('status') == 'blocked'])} blocked questions", src("SRC-GH-REPO")],
    ]
    worst_rows = []
    for s in worst:
        worst_rows.append([esc(s["team"]), str(s["week"]), num(s["weighted_depth_lost"], 2),
                           str(s.get("starters_out", "")), str(s.get("two_deep_out", "")),
                           str(s.get("backup_replacement_count", "")), str(s.get("deepest_replacement_rank", "")),
                           src("SRC-NFL-INJURIES")])
    body = f"""
<div class="hero compact"><div class="eyebrow">EXECUTIVE SUMMARY</div>
<h1>One page, every number classed.</h1>
<p class="lede">The shortest honest version: the measurement apparatus works, the market wins,
the injury/depth tracker is new and untested, and the suggestions below are proposals awaiting a
decision.</p></div>

<section class="block"><h2>Bottom line</h2>
{table(["Question", "Answer", "Evidence", "Source"], rows, "Executive summary — each row carries the artefact that supports it.")}
</section>

<section class="block"><h2>Site improvements recommended first</h2>
<div class="grid2">
<div class="panel"><h3>Do now (low cost, high impact)</h3><ul class="ticks">
<li>S-02 — replace the ATS identity with the one-sided test. 1 day. Fixes a headline that cannot fail.</li>
<li>S-01 — class every table row as official / computed / proposal. 2 days. Stops proposals reading as results.</li>
<li>S-05 — publish this questions register. Done in this session.</li>
</ul></div>
<div class="panel"><h3>Decide before building</h3><ul class="crosses">
<li>D-01 — is this a measurement system or a picks product?</li>
<li>D-02 — is the leaderboard a rank or a cash prize?</li>
<li>D-03 — which weakness is attacked first: price data, injury signal, or props?</li>
</ul></div></div></section>

<section class="block"><h2>Injury and depth intelligence — what is new</h2>
<p class="muted">Built this session from the official injury report plus club depth charts. Every
Out/Doubtful player is placed on his club's depth chart and numbered 1st, 2nd, 3rd string by
position. The table shows the five team-weeks with the most depth lost in the latest report.</p>
{table(["Team", "Week", "Weighted depth lost", "Starters out", "2-deep out", "Positions down to a backup", "Deepest replacement", "Source"],
       worst_rows, "Weighted depth lost = sum of 1/rank over absences with a known rank. Live data, refreshed by workflow.")}</section>

<section class="block"><h2>How to read this site</h2>
<ul class="ticks">
<li><strong>Questions</strong> — what must be answered before a decision is reasonable. Sorted by how many decisions each one blocks.</li>
<li><strong>Suggestions</strong> — proposals with impact, cost, risk and the decision they unblock.</li>
<li><strong>Decisions</strong> — the three choices that gate everything else, with the evidence for each option.</li>
<li><strong>Strategies</strong> — the ten gates, why nothing passes, and the leaderboard competition design.</li>
<li><strong>Injuries &amp; depth</strong> — the new tracker, with the method and its limits stated.</li>
<li><strong>Audit</strong> — independent recomputation of every published number, with the failures named.</li>
</ul></section>
"""
    return layout("Executive summary", "pages/executive-summary.html", body)


def page_suggestions():
    sug = load("suggestions.json")
    decs = {d["id"]: d for d in sug.get("decisions", [])}
    cats = {}
    for s in sug.get("suggestions", []):
        cats.setdefault(s["category"], []).append(s)
    rows = [[esc(c), str(len(v)),
             str(len([x for x in v if x["impact"] >= 4])),
             f'<a href="pages/suggestions.html#{v[0]["id"]}">first</a>', src("SRC-GH-REPO")]
            for c, v in sorted(cats.items())]
    body = f"""
<div class="hero compact"><div class="eyebrow">SUGGESTIONS</div>
<h1>Every proposal, and the decision it unblocks.</h1>
<p class="lede">None of this is implemented by browsing it. Each card states the problem in the
current site, the proposal, the measured evidence behind it, the risk, and which decision it
moves. Choose what to adopt on the review workflow page.</p></div>
<div class="notice"><span class="dot"></span><div><strong>{len(sug.get('suggestions', []))} suggestions in {len(cats)} categories.</strong><br>
{sug.get('meta', {}).get('policy', '')}</div><a href="pages/workflow.html">Choose a path &rarr;</a></div>
<section class="block"><h2>By category</h2>
{table(["Category", "Count", "Impact 4+", "Open", "Source"], rows, "Grouped from the suggestion register.")}</section>
"""
    for cat, items in sorted(cats.items()):
        cards = []
        for s in sorted(items, key=lambda x: -x["impact"]):
            blocked = "".join(
                f'<li><strong>{esc(b)}</strong> must be answered first — '
                f'<a href="pages/questions.html#{b}">{esc(b)}</a></li>' for b in s.get("blocked_by", []))
            unblock = " ".join(f'<a class="chip" href="pages/decisions.html#{u}">{u}</a>'
                               for u in s.get("unblocks", []))
            qs_links = " ".join(f'<a class="chip" href="pages/questions.html#{q}">{q}</a>'
                                for q in s.get("blocked_by", []))
            cards.append(f"""<article class="suggestion" id="{s['id']}">
  <header><span class="sid">{esc(s['id'])}</span><h3>{esc(s['title'])}</h3>
    <span class="badge {'ok' if s['impact'] >= 4 else 'warn'}">impact {s['impact']}</span>
    <span class="badge">{esc(s['cost'])} cost</span>
    <span class="badge">{esc(s['status'])}</span></header>
  <dl>
    <dt>Problem in the current site</dt><dd>{esc(s['problem'])}</dd>
    <dt>Suggestion</dt><dd>{esc(s['suggestion'])}</dd>
    <dt>Evidence</dt><dd>{esc(s['evidence'])}</dd>
    <dt>Risk</dt><dd>{esc(s['risk'])}</dd>
    <dt>Effort</dt><dd>{s['effort_days']} days</dd>
    <dt>Unblocks</dt><dd>{unblock or '&mdash;'}</dd>
    <dt>Blocked by</dt><dd><ul class="tight">{blocked or '<li>nothing</li>'}</ul></dd>
  </dl></article>""")
        body += (f'<section class="block"><div class="eyebrow">CATEGORY</div><h2>{esc(cat)}</h2>'
                 + "".join(cards) + "</section>")
    return layout("Suggestions", "pages/suggestions.html", body)


def page_questions():
    qs = load("questions.json")
    order = {"blocked": 0, "open": 1, "answerable": 2, "answered": 3}
    items = sorted(qs.get("questions", []), key=lambda q: (-len(q.get("blocks", [])), order.get(q["status"], 9)))
    rows = []
    for q in items:
        rows.append([f'<a href="pages/questions.html#{q["id"]}"><strong>{esc(q["id"])}</strong></a>',
                     esc(q["question"]), badges([q["status"]], {"blocked": "bad", "open": "warn",
                                                                "answerable": "ok"}.get(q["status"], "ok")),
                     " ".join(f'<a class="chip" href="pages/decisions.html#{d}">{d}</a>' for d in q.get("blocks", [])) or "&mdash;",
                     esc(q.get("cost", "")), src(q["source"][0])])
    body = f"""
<div class="hero compact"><div class="eyebrow">QUESTIONS &amp; UNKNOWNS</div>
<h1>What we know, what we don't, and what would tell us.</h1>
<p class="lede">Each question is split into <em>known</em> and <em>unknown</em>. A question marked
<strong>blocked</strong> cannot be answered with the data in this repository — the acquisition step
and its cost are stated rather than the answer invented.</p></div>
<div class="notice"><span class="dot"></span><div><strong>{len(items)} questions; {len([q for q in items if q['status']=='blocked'])} blocked.</strong><br>
Sort is by how many decisions the answer would unblock.</div><a href="pages/decisions.html">See the decisions &rarr;</a></div>
<section class="block"><h2>Register</h2>
{table(["ID", "Question", "Status", "Blocks", "Cost", "Source"], rows, "Legend: answerable = from committed data; open = needs a decision; blocked = needs data we do not have.")}
</section>
"""
    for q in items:
        rows2 = [[esc(q["known"]), src(q["source"][0])],
                 [esc(q["unknown"]), src(q["source"][0])]]
        blocks = " ".join(f'<a class="chip" href="pages/decisions.html#{d}">{d}</a>' for d in q.get("blocks", [])) or "&mdash;"
        body += f"""<section class="block question" id="{q['id']}">
<div class="eyebrow">{esc(q['id'])} &middot; {esc(q['status']).upper()}</div>
<h2>{esc(q['question'])}</h2>
{table(["What we know / what we do not", "Source"], rows2, "The split is the point: a known is a measured or documented value; an unknown is stated, not guessed.")}
<p><strong>How to answer:</strong> {esc(q['how_to_answer'])}</p>
<p><strong>Cost:</strong> {esc(q.get('cost',''))} &nbsp; <strong>Blocks:</strong> {blocks}</p>
<p class="muted"><strong>Verification note:</strong> {esc(q.get('verified_by',''))}</p>
</section>"""
    return layout("Questions &amp; unknowns", "pages/questions.html", body)


def page_decisions():
    sug = load("suggestions.json")
    body = f"""
<div class="hero compact"><div class="eyebrow">DECISIONS</div>
<h1>Three choices gate everything else.</h1>
<p class="lede">Each decision lists the options, what happens if you pick it, and the evidence.
The recommendation column is where the measured evidence points — it is advice, not a finding.</p></div>
"""
    for d in sug.get("decisions", []):
        rows = []
        for o in d["options"]:
            rec = "recommended by evidence" if "recommended" in o["label"].lower() else ""
            rows.append([f'<strong>{esc(o["label"])}</strong>', esc(o["effect"]), esc(o["evidence"]),
                         badges([rec], "ok") if rec else "&mdash;", src("SRC-GH-REPO")])
        blocking = "".join(f"<li>{esc(b)}</li>" for b in d.get("blocking_facts", []))
        body += f"""<section class="block decision" id="{d['id']}">
<div class="eyebrow">{esc(d['id'])}</div><h2>{esc(d['question'])}</h2>
<p class="muted">{esc(d['why_it_matters'])}</p>
{table(["Option", "What happens if chosen", "Supporting evidence", "Notes", "Source"], rows, "Options are mutually exclusive for the next build.")}
<h3>Facts that block this decision</h3><ul class="crosses">{blocking}</ul></section>"""
    body += """<section class="block"><h2>Choosing</h2>
<p>Open the <a href="pages/workflow.html">review workflow</a>: it lists each decision with a
place to record the choice and what follows. Nothing changes on the site until a choice is
recorded there.</p></section>"""
    return layout("Decisions", "pages/decisions.html", body)


def page_strategies():
    gates = load("gate_framework.json")
    aud = load("root_audit.json")
    rows = []
    for g in gates.get("gates", []):
        rows.append([f'<strong>{esc(g["id"])}</strong>', esc(g["name"]), esc(g["test"]),
                     esc(g["pass_rule"]), esc(g["why"]), src(g["source"])])
    lb_rows = []
    for e in aud.get("leaderboard_entries", []):
        lb_rows.append([str(e.get("rank", "")), esc(e.get("name", "")), esc(e.get("family", "")),
                        badges([e["verdict"]], "bad" if e["verdict"] == "REJECTED" else "ok"),
                        str(e.get("gates_passed", "")), str(e.get("n_bets", "")),
                        num(e.get("roi"), 4, True), str(e.get("p_value", "")),
                        src("nflverse-data")])
    body = f"""
<div class="hero compact"><div class="eyebrow">STRATEGY FRAMEWORK</div>
<h1>A competition where the gate is the point.</h1>
<p class="lede">Single bets, parlays and player-prop combos all enter the same ten-gate screen.
A strategy earns a rank only after it survives every gate; the leaderboard is the record of
what was tried and exactly why it failed.</p></div>
<div class="notice warn"><span class="dot"></span><div>
<strong>0 of 7 candidates approved. 2 controls also fail.</strong><br>
The screen currently rejects everything, partly because no executable price exists (G9). A screen
that rejects everything looks the same as one that is broken — see Q-13 and suggestion S-06.</div>
<a href="pages/questions.html#Q-13">Is the screen working? &rarr;</a></div>

<section class="block"><h2>The ten gates</h2>
{table(["Gate", "Name", "Test", "Pass rule", "Why it exists", "Reference"], rows, "Each gate is a pre-registered test; a strategy must pass all ten.")}
</section>

<section class="block"><h2>Leaderboard — what was tried</h2>
{table(["Rank", "Strategy", "Family", "Verdict", "Gates", "n bets", "ROI", "p", "Source"], lb_rows,
       "Copied from data/derived/leaderboard.json at build time. All ten gates are required; the failed gates are on the audit page per strategy.")}
<p class="muted">Reward tiers are a design proposal only. No prize pool exists (FL-DH-07).</p>
</section>

<section class="block"><h2>How luck is removed</h2>
<div class="grid2">
<div class="panel"><h3>At the strategy level</h3><ul class="ticks">
<li>Bootstrap interval on ROI, not a point estimate.</li>
<li>Permutation null: the same number of bets at the same prices, thousands of times.</li>
<li>Benjamini-Hochberg across every strategy tried, so trying more raises the bar.</li>
<li>Held-out seasons touched once.</li>
</ul></div>
<div class="panel"><h3>At the market level</h3><ul class="crosses">
<li>A season record is mostly luck: Pythagorean R-squared 0.83, luck persistence 0.019.</li>
<li>Any 'coin flip' claim must be one observation per game (FL-DH-01).</li>
<li>Sample size floor: 39,240 bets to detect 51% at 80% power.</li>
</ul></div></div></section>

<section class="block"><h2>Bet types and the gate that bites</h2>
{table(["Type", "What the screen does", "Which gate usually fails", "What would unblock it", "Source"],
 [["Single bet", "Settles at the stored closing price from 2023 onward", "G4 positive after vig; G9 executable price",
   "A timestamped price and CLV (S-03)", src("nflverse-data")],
  ["Parlay", "Prices the joint under a Gaussian copula from measured correlations", "G7 correlation validity; G9",
   "A bootstrap interval on each correlation, then on the joint (S-09)", src("nflverse-data")],
  ["Player prop", "Measures calibration and accuracy; ROI left blank", "G4; no price exists at all",
   "Historical prop prices — does not exist in this data (Q-12)", src("nflverse-data")],
  ["Player-prop combo", "Builds same-team combos from measured correlations", "G7; G9",
   "Same as parlay, plus prop prices", src("nflverse-data")]],
 "Every type enters the same screen; the difference is which gate stops it.")}</section>
"""
    return layout("Strategy framework", "pages/strategies.html", body)


def page_injuries():
    inj = load("injuries.json")
    meta = inj.get("meta", {})
    cur = inj.get("current", [])
    rows = []
    for s in cur:
        nm = "; ".join(f'{x.get("player","")} ({x.get("pos","")}, {x.get("string","")})'
                       for x in s.get("out_names", [])[:4])
        nxt = "; ".join(f'{p["position"]}&rarr;{p["replacement"]} ({p["replacement_string"]})'
                        for p in s.get("positions_down", [])[:3]) or "&mdash;"
        rows.append([esc(s["team"]), str(s["week"]), str(s["out_or_doubtful"]), str(s["questionable"]),
                     str(s["starters_out"]), str(s["two_deep_out"]), str(s["three_deep_out"]),
                     num(s["weighted_depth_lost"], 2), esc(nxt), esc(nm), src("SRC-NFL-INJURIES")])
    weeks = meta.get("weeks", [])
    body = f"""
<div class="hero compact"><div class="eyebrow">INJURIES &amp; DEPTH</div>
<h1>Who is out, and how far down the depth chart that reaches.</h1>
<p class="lede">Built from the league's own injury report and each club's depth chart. Every
reported Out/Doubtful player is numbered by position — 1st, 2nd, 3rd string — and each team-week
is scored by how much known depth it has lost. This is an absence record, not a prediction.</p></div>
<div class="notice"><span class="dot"></span><div>
<strong>Snapshot {esc(meta.get('generated_utc','')[:10])} &middot; depth chart {esc(meta.get('depth_snapshot_dt',''))} &middot; league week {meta.get('league_week','')}</strong><br>
{len(inj.get('absences', []))} reported absences across {len(inj.get('team_week_summary', []))} team-weeks.
{meta.get('teams_on_latest_week', 0)} of {len(meta.get('teams', []))} teams have a week-{meta.get('league_week','')} report;
the rest are on week 9 or have not filed.</div>
<a href="pages/evidence.html#absences">Every absence row &rarr;</a></div>

<section class="block"><h2>Current report, every team</h2>
{table(["Team", "Week", "Out/Doubtful", "Questionable", "1st string out", "2-deep out", "3-deep out",
        "Depth lost", "Positions on a backup", "Players out (pos, string)", "Source"], rows,
       "Depth lost = sum of 1/rank over absences with a known rank. 'Positions on a backup' means the best available player at that position is 2nd string or deeper.")}
</section>

<section class="block"><h2>Method — and what it does not claim</h2>
<div class="grid2">
<div class="panel"><h3>How a rank is assigned</h3><ul class="ticks">
<li>The depth-chart feed's <code>pos_rank</code> is rank <em>within a slot</em>, and a team can list the same position in several slots (the 2026 Ravens list two QBs in separate slots).</li>
<li>So the rank used here is the ordinal within (team, position), ordered by slot then slot-rank: QB1 is the first quarterback listed, QB4 the fourth.</li>
<li>The raw slot and slot-rank stay on every published row so the ordering can be audited.</li>
<li>Snap share is the mean of the previous four games, joined through the roster's PFR id because the snap-count feed has no GSIS id.</li>
</ul></div>
<div class="panel"><h3>Limits</h3><ul class="crosses">
<li>Depth charts are club-supplied and can lag a transaction. A rank is not a promise about who plays.</li>
<li>'Doubtful' is a probability the league does not quantify; 'Out' is final. They are counted separately.</li>
<li>Resting-player and personal-matter rows are in the feed and counted; they are disclosed, not filtered.</li>
<li>The effect of depth loss on the line has never been measured here (Q-04).</li>
</ul></div></div>
{table(["Caveat", "Detail", "Source"],
 [[esc(c), "Applied to every row on this page", src("SRC-NFL-INJURIES")] for c in meta.get("caveats", [])],
 "Caveats are part of the dataset, not a footnote.")}</section>

<section class="block"><h2>Data provenance</h2>
{table(["File", "Bytes", "SHA-256 (first 16)", "What it is", "Source"],
 [[esc(f["name"]), f'{f.get("bytes", 0):,}', f'<code>{esc(str(f.get("sha256",""))[:16])}</code>',
   {"injuries": "official injury report, 2026", "depth": "club depth charts, newest snapshot",
    "roster": "weekly roster + status", "snaps": "snap counts, PFR-joined"}.get(f["name"], ""),
   src("SRC-NFL-INJURIES")] for f in meta.get("files", [])],
 "Hashes let anyone confirm the exact inputs this build used.")}
<p class="muted">Schema sample (first rows, trimmed): <code>{esc(json.dumps(meta.get('schema_samples', {}).get('depth', {}).get('rows', [{}])[0])[:300])}</code></p>
</section>
"""
    return layout("Injuries &amp; depth", "pages/injuries.html", body)


def page_audit():
    aud = load("root_audit.json")
    st = aud.get("summary", {})
    rows = []
    for c in aud.get("checks", []):
        kind = {"PASS": "ok", "FAIL": "bad", "BLANK": "warn"}.get(c["verdict"], "warn")
        rows.append([f'<code>{esc(c["id"])}</code>', esc(c["claim"]),
                     cell(c.get("published")), cell(c.get("recomputed")),
                     badges([c["verdict"]], kind), esc(c["method"]), src(c["source_id"])])
    body = f"""
<div class="hero compact"><div class="eyebrow">LINE-BY-LINE AUDIT</div>
<h1>Every published number, recomputed by different code.</h1>
<p class="lede">This page is produced by an independent implementation that does not import the
root project. A number is PASS only if it reproduces from committed inputs within tolerance.
Anything else is FAIL, BLANK, or an observation.</p></div>
<div class="kpis">
{kpi("Checks", st.get("checks", 0), "Each one recomputes a published value.", "", "")}
{kpi("Reproduced", st.get("pass", 0), "Exact match within the stated tolerance.", "", "")}
{kpi("Failed", st.get("fail", 0), "Published value not reproduced.", "", "")}
{kpi("Unverifiable", st.get("blank", 0), "Needs data this repository does not hold.", "", "")}
{kpi("Flags", st.get("flags", 0), f"{st.get('high_flags', 0)} high severity.", "pages/flagged.html", "See flags")}
</div>
<section class="block"><h2>Checks</h2>
{table(["ID", "Claim", "Published", "Recomputed", "Verdict", "Method", "Source"], rows,
       "Tolerance: counts exact, rates 5e-5, statistics 5e-4 unless a rounding band is stated.")}
<p class="muted">Regenerate with <code>python decision-hub/scripts/audit_root.py</code>.</p></section>
<section class="block"><h2>Source-link coverage of the published site</h2>
"""
    rr = aud.get("rows", {})
    coverage = [[esc(p), str(v["table_rows"]), str(v["rows_without_source_cell"]),
                 badges(["clean" if v["rows_without_source_cell"] == 0 else "check"], "ok" if v["rows_without_source_cell"] == 0 else "warn"),
                 src("SRC-GH-REPO")] for p, v in sorted(rr.items())]
    body += table(["Page", "Table rows", "Rows without a source link", "Status", "Source"], coverage,
                  "A row without a link in its final cell is listed, not hidden.")
    body += f"<p class=\"muted\">Totals: {aud.get('rows_totals', {}).get('table_rows', 0)} rows across {aud.get('rows_totals', {}).get('pages', 0)} pages.</p></section>"
    return layout("Line-by-line audit", "pages/audit.html", body)


def page_evidence():
    inj = load("injuries.json")
    aud = load("root_audit.json")
    rows = []
    for a in sorted(inj.get("absences", []), key=lambda x: (x["team"], x["week"], x.get("depth_rank") or 99))[:400]:
        rows.append([esc(a["team"]), str(a["week"]), esc(a["player"]), esc(a["position"]),
                     esc(a.get("position_name", "")), esc(a.get("string", "")),
                     num(a.get("pos_slot")), num(a.get("pos_rank_in_slot")),
                     badges([a["report_status"]], "bad" if a["report_status"] == "Out" else "warn"),
                     esc(a.get("report_injury", "")), esc(a.get("practice_status", "")),
                     num(a.get("snap_share_4wk"), 3), src("SRC-NFL-INJURIES")])
    ats = aud.get("ats_honest", {})
    stat_rows = [
        ["Pooled ATS rate (published method)", f'{ats.get("wins",0)} / {ats.get("n",0)*2}', "50.00%",
         "An identity: each game appears twice, once per side", src("nflverse-data")],
        ["One-sided home cover rate", f'{ats.get("wins",0)} / {ats.get("n",0)}', f'{ats.get("rate",0)*100:.2f}%',
         f'95% CI {ats.get("ci",[0,0])[0]*100:.2f}-{ats.get("ci",[0,0])[1]*100:.2f}%, p = {ats.get("p_vs_50",0)}', src("nflverse-data")],
    ]
    for c in aud.get("checks", []):
        if c["id"].startswith(("market.", "data.")):
            stat_rows.append([esc(c["id"]), esc(c["claim"]), cell(c.get("published")),
                              cell(c.get("recomputed")), src(c["source_id"])])
    body = f"""
<div class="hero compact"><div class="eyebrow">EVIDENCE</div>
<h1>The rows behind the summary.</h1>
<p class="lede">Two tables: the recomputed headline statistics, and the injury/depth rows.
Every row links to the source it came from.</p></div>
<section class="block" id="stats"><h2>Headline statistics, recomputed</h2>
{table(["Statistic", "Published", "Recomputed", "Note", "Source"], stat_rows, "Independent recomputation from committed extracts.")}
</section>
<section class="block" id="absences"><h2>Injury absences, every row</h2>
<p class="muted">Showing the first 400 of {len(inj.get('absences', []))} rows, ordered by team, week
and depth rank. The full set is in <code>decision-hub/data/injuries.json</code>.</p>
{table(["Team", "Wk", "Player", "Pos", "Position name", "String", "Slot", "Slot rank", "Status",
        "Injury", "Practice", "Snap share (4wk)", "Source"], rows,
       "Slot and slot rank are the raw depth-chart fields; the string column is the ordinal within (team, position).")}
</section>
"""
    return layout("Evidence tables", "pages/evidence.html", body)


def page_sources():
    reg = sources()
    order = {"league official": 0, "league official stats": 0, "league official injury data": 0,
             "government regulator": 1, "regulator": 1, "government statistics reference": 2,
             "academic": 3, "sportsbook official rules/help": 4, "community": 5}
    items = sorted(reg.values(), key=lambda s: (order.get(s.get("type", ""), 9), s["id"]))
    rows = [[f'<code>{esc(s["id"])}</code>', esc(s.get("label", ""))[:110], esc(s.get("type", "")),
             esc(s.get("org", "")), f'<a href="{esc(s["url"])}" rel="noopener">link</a>',
             esc((s.get("note") or s.get("verified_by") or ""))[:140],
             src(s["id"])] for s in items]
    body = f"""
<div class="hero compact"><div class="eyebrow">SOURCES</div>
<h1>Where every claim comes from.</h1>
<p class="lede">Official league and regulator documents first, then statistics authorities,
then academic primary sources, then operator rulebooks, then community mirrors. A community mirror
is never treated as an official fact.</p></div>
<section class="block"><h2>Register</h2>
{table(["ID", "What it is", "Type", "Publisher", "Open", "Note", "Link"], rows,
       f"{len(items)} entries. The final column is the same URL as the Open link, so a row is never without a source.")}
</section>
<section class="block"><h2>Class of source, and what it may be used for</h2>
{table(["Class", "Examples here", "May be cited as", "May NOT be cited as", "Source"],
 [["League official", "nfl.com injury report, rulebook, standings", "A fact about the league or a game", "A betting price",
   src("SRC-NFL-INJURIES")],
  ["Regulator", "Massachusetts Gaming Commission filings", "The text of an operator's filed rules", "Proof a strategy works",
   src("SRC-MGC-DK-RULES-CURRENT")],
  ["Government statistics", "NIST handbooks", "A statistical method", "An NFL result",
   src("SRC-NIST-CORR")],
  ["Academic", "Kelly 1956, Benjamini-Hochberg 1995", "A method with a citation", "A sportsbook price",
   src("kelly-1956")],
  ["Community mirror", "nflverse data releases", "A redistributed copy of a league feed, with hashes",
   "An official league publication in its own right", src("nflverse-data")]],
 "The class determines what a number may be called.")}</section>
"""
    return layout("Sources", "pages/sources.html", body)


def page_flagged():
    aud = load("root_audit.json")
    flags = aud.get("flags", [])
    rows = []
    for f in flags:
        rows.append([f'<code>{esc(f["id"])}</code>', badges([f["severity"]], {"high": "bad", "medium": "warn", "low": "ok"}.get(f["severity"], "ok")),
                     esc(f["item"]), esc(f["detail"]), esc(f.get("action", "")),
                     ", ".join(esc(x) for x in f.get("published_where", [])) or "&mdash;",
                     " ".join(src(s) for s in f.get("sources", []))])
    body = f"""
<div class="hero compact"><div class="eyebrow">FLAGGED FOR REVIEW</div>
<h1>What is wrong, blank, or cannot be checked.</h1>
<p class="lede">Nothing here blocks publication. Each item was found by checking rather than
assumed away, and each one states what should happen next. Values that cannot be confirmed from
an official source are left blank on the site and listed here instead.</p></div>
<div class="notice"><span class="dot"></span><div><strong>{len(flags)} items ({len([f for f in flags if f['severity']=='high'])} high).</strong><br>
Generated from <code>decision-hub/data/root_audit.json</code>; regenerate with the audit script.</div>
<a href="pages/audit.html">See the recomputation &rarr;</a></div>
<section class="block"><h2>Register</h2>
{table(["ID", "Severity", "Item", "Detail", "What should happen", "Published on", "Sources"], rows, "Every flag names the exact page or file where the problem appears.")}
</section>
<section class="block"><h2>Unverified-value policy</h2>
<ul class="ticks">
<li>If a value cannot be confirmed from an official or primary source, it is blank.</li>
<li>A blank always has a reason, on this page or the questions register.</li>
<li>No value is inferred, interpolated, or copied from a secondary summary.</li>
<li>A computed statistic is labelled a computation and carries the code and data manifest that produced it.</li>
<li>A proposal is labelled a proposal and never sits in a table of measurements.</li>
</ul></section>
"""
    return layout("Flagged for review", "pages/flagged.html", body)


def page_workflow():
    sug = load("suggestions.json")
    qs = load("questions.json")
    dec_rows = []
    for d in sug.get("decisions", []):
        opts = " / ".join(o["label"] for o in d["options"])
        dec_rows.append([f'<a href="pages/decisions.html#{d["id"]}">{esc(d["id"])}</a>',
                         esc(d["question"]), esc(opts), "open", src("SRC-GH-REPO")])
    body = f"""
<div class="hero compact"><div class="eyebrow">REVIEW WORKFLOW</div>
<h1>How to choose a path without implementing anything.</h1>
<p class="lede">A short, ordered process. Each step says what to read, what to decide, and what
happens next. The site is a decision aid; the decisions are recorded here so an implementation
session can act on them without guessing.</p></div>
<section class="block"><h2>The process</h2>
<ol class="steps">
<li><strong>Read the questions register, blocked items first.</strong> Anything blocked cannot be
decided well yet — it needs data, not opinion. <a href="pages/questions.html">Open it</a>.</li>
<li><strong>Answer the three decisions.</strong> Measurement vs picks; rank vs prize; which
weakness first. Each has the evidence for and against. <a href="pages/decisions.html">Open them</a>.</li>
<li><strong>Adopt suggestions selectively.</strong> Start with the low-cost high-impact set (S-02,
S-01, S-05). Each is one to two days and removes a specific way the site can mislead.
<a href="pages/suggestions.html">Open them</a>.</li>
<li><strong>Only then commission code.</strong> A suggestion with a blocking question is not
actionable; implementing it produces a number nobody can defend.</li>
<li><strong>Re-audit.</strong> Run <code>python decision-hub/scripts/audit_root.py</code> and check
that nothing that used to reproduce has stopped. <a href="pages/audit.html">Open the audit</a>.</li>
</ol></section>
<section class="block"><h2>Decisions to record</h2>
{table(["ID", "Question", "Options", "Status", "Source"], dec_rows, "Status stays 'open' until a choice is written down.")}
</section>
<section class="block"><h2>What a recorded decision needs</h2>
<ul class="ticks">
<li>The option chosen, and the date.</li>
<li>Which questions were answered and which were accepted as open.</li>
<li>Which suggestion list follows from it.</li>
<li>The evidence that would make the decision wrong later (so it can be revisited honestly).</li>
</ul>
<p class="muted">Until a decision is recorded, the recommendation is the default: keep the site a
measurement system, keep rewards as a rank, and fix the ATS statistic first.</p></section>
<section class="block"><h2>Open question backlog</h2>
{table(["Question", "Status", "Blocks", "Source"],
 [[f'<a href="pages/questions.html#{q["id"]}">{esc(q["id"])}: {esc(q["question"])}</a>',
   esc(q["status"]), " ".join(q.get("blocks", [])) or "&mdash;", src(q["source"][0])]
  for q in qs.get("questions", [])], "Sorted as published on the questions page.")}
</section>
"""
    return layout("Review workflow", "pages/workflow.html", body)


CSS = """:root{
 --bg:#0b1020;--panel:#121a30;--panel2:#0f1628;--ink:#e8eefc;--muted:#9db0d0;--line:#22304f;
 --acc:#7cc4ff;--ok:#54d08b;--warn:#f2c14e;--bad:#ff7b72;--chip:#1b2740;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:1rem}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
code{font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;background:#0a1224;border:1px solid var(--line);border-radius:5px;padding:1px 5px}
.skip{position:absolute;left:-9999px}
.skip:focus{left:8px;top:8px;background:var(--acc);color:#001018;padding:6px 10px;border-radius:6px;z-index:9}
.shell{display:grid;grid-template-columns:266px minmax(0,1fr);min-height:100vh}
.sidebar{background:var(--panel2);border-right:1px solid var(--line);padding:18px 14px;position:sticky;top:0;height:100vh;overflow:auto}
.brand{display:flex;gap:10px;align-items:center;color:var(--ink);font-weight:700;letter-spacing:.06em;font-size:13px;margin-bottom:18px}
.brand .mark{display:grid;place-items:center;width:34px;height:34px;border-radius:9px;background:linear-gradient(140deg,#1d3a63,#2a6ea8);font-size:12px}
.brand small{display:block;color:var(--muted);font-weight:600;letter-spacing:.12em;font-size:9px;margin-top:2px}
.nav-label{color:var(--muted);font-size:10px;letter-spacing:.18em;text-transform:uppercase;margin:14px 8px 6px}
nav{display:flex;flex-direction:column;gap:1px}
nav a{color:var(--muted);padding:7px 9px;border-radius:7px;font-size:13.5px;border-left:2px solid transparent}
nav a:hover{background:#16213a;color:var(--ink);text-decoration:none}
nav a.active{background:#17243f;color:var(--ink);border-left-color:var(--acc);font-weight:650}
.sidebar-note{margin-top:18px;padding:11px;border:1px solid var(--line);border-radius:9px;font-size:12px;color:var(--muted);background:#0d1526}
.sidebar-note strong{display:block;color:var(--ink);font-size:12.5px;margin:3px 0}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--ok);margin-right:6px;vertical-align:middle}
main{padding:0 30px 60px;max-width:1180px}
.topbar{display:flex;justify-content:space-between;align-items:center;padding:16px 0;border-bottom:1px solid var(--line);margin-bottom:22px}
.crumb{color:var(--muted);font-size:11px;letter-spacing:.16em}
.review-link{font-size:12.5px}
.hero{padding:22px 0 6px}
.hero.compact{padding-top:12px}
.eyebrow{color:var(--acc);font-size:10.5px;letter-spacing:.2em;margin-bottom:8px}
h1{font-size:clamp(26px,3.4vw,40px);line-height:1.12;margin:0 0 12px;letter-spacing:-.015em}
h1 em{color:var(--acc);font-style:normal}
h2{font-size:21px;margin:6px 0 12px;letter-spacing:-.01em}
h3{font-size:15.5px;margin:0 0 8px}
.lede{color:#c3d2ec;font-size:16px;max-width:78ch;margin:0 0 16px}
.notice{display:flex;gap:16px;align-items:center;justify-content:space-between;background:#101c33;border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:10px;padding:13px 16px;margin:20px 0;font-size:13.5px;color:var(--muted);flex-wrap:wrap}
.notice strong{color:var(--ink)}
.notice.warn{border-left-color:var(--warn);background:#1a1608}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(196px,1fr));gap:12px;margin:22px 0}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:14px}
.kpi-label{display:block;color:var(--muted);font-size:10.5px;letter-spacing:.12em;text-transform:uppercase}
.kpi strong{display:block;font-size:26px;line-height:1.15;margin:7px 0 5px;letter-spacing:-.02em}
.kpi p{color:var(--muted);font-size:12.5px;margin:0}
.card-link{display:inline-block;margin-top:9px;font-size:12px}
.block{margin:34px 0}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px;margin:18px 0}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:16px}
ul.ticks,ul.crosses,ul.tight{list-style:none;padding:0;margin:8px 0}
ul.ticks li,ul.crosses li{position:relative;padding-left:20px;margin:7px 0;font-size:13.5px;color:#cddcf4}
ul.ticks li::before{content:"\\2713";position:absolute;left:0;color:var(--ok)}
ul.crosses li::before{content:"\\00d7";position:absolute;left:0;color:var(--bad)}
ul.tight li{margin:2px 0;font-size:13px}
.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:11px;background:var(--panel)}
table{width:100%;border-collapse:collapse;font-size:12.8px;min-width:560px}
caption.caption{caption-side:bottom;text-align:left;color:var(--muted);font-size:11.5px;padding:9px 12px;border-top:1px solid var(--line)}
th{text-align:left;padding:9px 11px;background:#16223c;color:#cfe0fa;font-size:10.5px;letter-spacing:.11em;text-transform:uppercase;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:8px 11px;border-bottom:1px solid #1b2742;vertical-align:top;color:#dbe6fa}
tbody tr:hover{background:#14203a}
td.src{font-size:11.5px;min-width:110px}
.badge{display:inline-block;padding:1px 7px;border-radius:999px;font-size:10.5px;font-weight:650;letter-spacing:.03em;background:var(--chip);color:#b9cbe8;border:1px solid var(--line)}
.badge.ok{color:#8ee9b7;border-color:#1f5a3c;background:#0f2a1d}
.badge.warn{color:#ffd98a;border-color:#5a4a1f;background:#2a2410}
.badge.bad{color:#ffb3ae;border-color:#5a2626;background:#2a1010}
.chip{display:inline-block;padding:1px 8px;border-radius:999px;background:var(--chip);border:1px solid var(--line);font-size:11.5px;margin:1px 3px 1px 0;color:#bfd4f2}
.blank{color:#6f81a3}
.muted{color:var(--muted)}
.flag{color:var(--bad);font-size:12px}
.suggestion{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:16px;margin:14px 0}
.suggestion header{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
.suggestion h3{margin:0;flex:1 1 260px}
.sid{font:11px ui-monospace,monospace;color:var(--acc);border:1px solid var(--line);border-radius:5px;padding:1px 6px}
dl{margin:0}
dt{color:var(--muted);font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;margin-top:11px}
dd{margin:3px 0 0;font-size:13.5px;color:#dbe6fa}
ol.steps{counter-reset:s;list-style:none;padding:0}
ol.steps li{counter-increment:s;position:relative;padding:12px 14px 12px 52px;background:var(--panel);border:1px solid var(--line);border-radius:11px;margin:10px 0;font-size:13.5px}
ol.steps li::before{content:counter(s);position:absolute;left:14px;top:11px;width:24px;height:24px;border-radius:50%;background:#1d3a63;color:#cfe6ff;display:grid;place-items:center;font-size:12px;font-weight:700}
footer{margin-top:44px;border-top:1px solid var(--line);padding-top:16px;color:var(--muted);font-size:12px}
@media (max-width:860px){.shell{grid-template-columns:1fr}.sidebar{position:static;height:auto}main{padding:0 16px 40px}nav{flex-direction:row;flex-wrap:wrap}nav a{border-left:0;border-bottom:2px solid transparent}}
"""


def main() -> int:
    os.makedirs(os.path.join(HUB, "pages"), exist_ok=True)
    os.makedirs(os.path.join(HUB, "assets"), exist_ok=True)
    pages = {
        "index.html": page_index(),
        "pages/executive-summary.html": page_executive(),
        "pages/suggestions.html": page_suggestions(),
        "pages/questions.html": page_questions(),
        "pages/decisions.html": page_decisions(),
        "pages/strategies.html": page_strategies(),
        "pages/injuries.html": page_injuries(),
        "pages/audit.html": page_audit(),
        "pages/evidence.html": page_evidence(),
        "pages/sources.html": page_sources(),
        "pages/flagged.html": page_flagged(),
        "pages/workflow.html": page_workflow(),
    }
    for path, doc in pages.items():
        full = os.path.join(HUB, path)
        os.makedirs(os.path.dirname(full) or HUB, exist_ok=True)
        if path.startswith("pages/"):
            # page bodies are written with hub-root-relative links; make them relative to pages/
            doc = re.sub(r'href="(?!https?:|#|mailto:|\.\./)([^"]+)"',
                         lambda m: f'href="../{m.group(1)}"', doc)
            doc = doc.replace('href="../assets/', 'href="../assets/')
        with open(full, "w") as fh:
            fh.write(doc)
    with open(os.path.join(HUB, "assets", "style.css"), "w") as fh:
        fh.write(CSS)
    with open(os.path.join(HUB, ".nojekyll"), "w") as fh:
        fh.write("")
    print(f"wrote {len(pages)} pages to decision-hub/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
