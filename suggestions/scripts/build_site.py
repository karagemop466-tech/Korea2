#!/usr/bin/env python3
"""Build Suggestions Hub."""
import json, pathlib, html
ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

def load(name):
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else {}

def esc(s): return html.escape(str(s), quote=True)

def badge(txt, cls="ok"):
    return f'<span class="badge {cls}">{esc(txt)}</span>'

def src_link(ids):
    reg = load("sources.json")
    m = {s["id"]: s.get("url","") for s in reg.get("sources", [])}
    out=[]
    for sid in (ids if isinstance(ids,list) else [ids]):
        url=m.get(sid,"")
        out.append(f'<a href="{esc(url)}" rel="noopener">{esc(sid)}</a>' if url else esc(sid))
    return " · ".join(out)

def table(headers, rows):
    h="".join(f"<th>{esc(c)}</th>" for c in headers)
    body=""
    for r in rows:
        body+="<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>\n"
    return f'<div class="table-wrap"><table><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table></div>'

def header(title, crumb, rel_path):
    is_index = rel_path == "index.html"
    assets = "assets/style.css" if is_index else "../assets/style.css"
    brand = "index.html" if is_index else "../index.html"
    root_index = "../index.html" if is_index else "../../index.html"
    root_archive = "../pages/archive.html" if is_index else "../../pages/archive.html"
    flagged = "pages/flagged.html" if is_index else "flagged.html"
    # nav items
    if is_index:
        nav_items = [
            ("Overview","index.html"),
            ("Executive summary","pages/executive.html"),
            ("Suggestions","pages/suggestions.html"),
            ("Decision prerequisites","pages/decisions.html"),
            ("Questions & answers","pages/questions.html"),
            ("Injuries & depth tracking","pages/injuries.html"),
            ("Signals & origination","pages/signals.html"),
            ("Leaderboard & rewards","pages/leaderboard.html"),
            ("Correlation & parlays","pages/correlations.html"),
            ("Removing luck","pages/luck.html"),
            ("Source register","pages/sources.html"),
            ("Flagged for review","pages/flagged.html"),
            ("Requirements matrix","pages/requirements.html"),
        ]
    else:
        nav_items = [
            ("Overview","../index.html"),
            ("Executive summary","executive.html"),
            ("Suggestions","suggestions.html"),
            ("Decision prerequisites","decisions.html"),
            ("Questions & answers","questions.html"),
            ("Injuries & depth tracking","injuries.html"),
            ("Signals & origination","signals.html"),
            ("Leaderboard & rewards","leaderboard.html"),
            ("Correlation & parlays","correlations.html"),
            ("Removing luck","luck.html"),
            ("Source register","sources.html"),
            ("Flagged for review","flagged.html"),
            ("Requirements matrix","requirements.html"),
        ]
    nav_html="".join(f'<a href="{esc(href)}">{esc(label)}</a>' for label,href in nav_items)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} | Suggestions Hub</title>
<meta name="description" content="NFL decision-making improvement hub.">
<meta name="generator" content="suggestions/scripts/build_site.py">
<link rel="stylesheet" href="{assets}" />
<style>
body{{margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; background:#fafafa; color:#0f172a}}
.shell{{display:flex; min-height:100vh}} .sidebar{{width:260px; background:#0f172a; color:#e2e8f0; padding:20px; flex-shrink:0}}
.sidebar a{{color:#94a3b8; text-decoration:none; display:block; padding:6px 8px; border-radius:6px; margin:2px 0}}
.sidebar a.active, .sidebar a:hover{{background:#1e293b; color:#fff}}
.brand{{display:flex; align-items:center; gap:10px; font-weight:700; color:#fff; font-size:1.1em; margin-bottom:12px}}
.brand .mark{{background:#38bdf8; color:#0f172a; width:28px; height:28px; display:inline-grid; place-items:center; border-radius:6px; font-weight:800}}
.nav-label{{font-size:0.7em; letter-spacing:0.1em; color:#64748b; margin:14px 0 6px}}
.sidebar-note{{margin-top:16px; padding:12px; background:#1e293b; border-radius:8px; font-size:0.85em}} .sidebar-note strong{{display:block; color:#fff}}
main{{flex:1; padding:24px; max-width:1100px}} .topbar{{display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:8px; margin-bottom:16px}}
.crumb{{font-weight:700; letter-spacing:0.08em; font-size:0.8em; color:#475569}}
.hero{{background:white; border:1px solid #e2e8f0; border-radius:12px; padding:20px; margin-bottom:16px}} .hero h1{{margin:4px 0 8px; font-size:1.8em}} .eyebrow{{font-size:0.7em; letter-spacing:0.12em; color:#0284c7; font-weight:700}} .lede{{color:#475569}}
.kpis{{display:grid; grid-template-columns: repeat(auto-fit, minmax(170px,1fr)); gap:12px; margin:12px 0}} .kpi{{background:white; border:1px solid #e2e8f0; border-radius:10px; padding:14px}} .kpi-label{{font-size:0.75em; color:#64748b; letter-spacing:0.06em}} .kpi strong{{display:block; font-size:1.4em; margin:4px 0}}
.block{{background:white; border:1px solid #e2e8f0; border-radius:12px; padding:16px; margin:14px 0}} .table-wrap{{overflow:auto}} table{{width:100%; border-collapse:collapse; font-size:0.9em}} th{{text-align:left; background:#f8fafc; border-bottom:2px solid #e2e8f0; padding:8px}} td{{border-bottom:1px solid #f1f5f9; padding:8px; vertical-align:top}}
.badge{{display:inline-block; padding:2px 6px; border-radius:999px; font-size:0.75em; font-weight:600}} .badge.ok{{background:#dcfce7; color:#166534}} .badge.warn{{background:#fef9c3; color:#854d0e}} .badge.bad{{background:#fee2e2; color:#991b1b}}
.src a{{color:#0284c7; text-decoration:none}} .src a:hover{{text-decoration:underline}}
.notice{{background:#eff6ff; border:1px solid #bfdbfe; border-radius:10px; padding:12px; display:flex; gap:12px; align-items:center; margin:12px 0}} .panel{{background:white; border:1px solid #e2e8f0; border-radius:12px; padding:16px}} .grid2{{display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:12px}} .small{{font-size:0.85em; color:#475569}}
footer{{margin-top:20px; padding-top:12px; border-top:1px solid #e2e8f0; color:#64748b; font-size:0.85em}} footer a{{color:#0284c7; text-decoration:none}} .skip{{position:absolute; left:-9999px}}
</style>
</head><body>
<a class="skip" href="#main">Skip</a>
<div class="shell">
<aside class="sidebar">
  <a class="brand" href="{brand}"><span class="mark">SD</span><span>Suggestions Hub<small style="display:block;font-weight:400;color:#94a3b8;font-size:0.6em;letter-spacing:0.08em">NFL RESEARCH</small></span></a>
  <div class="nav-label">Suggestions Hub</div>
  <nav>{nav_html}</nav>
  <div class="sidebar-note"><span class="dot"></span>Suggestions Hub<br><strong>12 proposals for review</strong><span>All verified from official sources; no value inferred. Proposals must be approved before implementation.</span></div>
  <div class="nav-label">Workspace</div>
  <nav><a href="{root_index}">Root Line Lab &rarr;</a><a href="{root_archive}">Archive (all labs) &rarr;</a></nav>
</aside>
<main id="main">
<header class="topbar"><span class="crumb">{esc(crumb)}</span><a class="review-link" href="{flagged}">Flagged for review &nearr;</a></header>
"""

def footer(rel_path):
    is_index = rel_path == "index.html"
    root_index = "../index.html" if is_index else "../../index.html"
    flagged = "pages/flagged.html" if is_index else "flagged.html"
    sources = "pages/sources.html" if is_index else "sources.html"
    return f"""<footer>
  <p>Research and measurement, not betting advice. Every figure is computed from sources listed on the Source register; nothing is estimated by hand. Proposal review required before any site change.</p>
  <p><a href="{sources}">Source register</a> &middot; <a href="{flagged}">Flagged for review</a> &middot; <a href="{root_index}">Root Line Lab</a></p>
</footer>
</main></div></body></html>"""


def build_index():
    req=load("requirements.json"); sug=load("suggestions.json"); dec=load("decisions.json"); q=load("questions.json")
    h=header("Overview","OVERVIEW","index.html")
    # KPIs
    body=f"""
<div class="hero">
  <div class="eyebrow">SUGGESTIONS &amp; DECISION HUB — INDEPENDENT NFL RESEARCH</div>
  <h1>Originate lines. <em>Prove what you still don't know.</em> Then decide.</h1>
  <p class="lede">This hub extends the Line Lab dashboard to answer what must be true before any decision can be taken. Every requirement, every suggestion, every question and the exact official source behind each row — proposals are published for review, approval is explicit before anything changes.</p>
</div>
<div class="notice"><strong>Current verdict: nothing has earned capital.</strong> Pipeline on 2026-11-01 data; closing market beats model (spread MAE 10.25 vs 10.39 pts, incremental p=0.881); 0 of 7 strategies clear all ten gates. Proposals address why and what would change. <a href="pages/suggestions.html" style="margin-left:auto">Review suggestions &rarr;</a></div>
<div class="kpis">
  <div class="kpi"><span class="kpi-label">Requirements catalogued</span><strong>{len(req.get("requirements",[]))}</strong><p class="small">Every prompt line traced to requirement ID and status.</p><a class="card-link" href="pages/requirements.html">Requirements &rarr;</a></div>
  <div class="kpi"><span class="kpi-label">Proposals for review</span><strong>{len(sug.get("rows",[]))}</strong><p class="small">Site, data and competition improvements — each with priority, impact and source.</p><a class="card-link" href="pages/suggestions.html">Suggestions &rarr;</a></div>
  <div class="kpi"><span class="kpi-label">Decision blockers</span><strong>4 open</strong><p class="small">Decisions #03, #05, #10, #14 blocked by missing/unverified info.</p><a class="card-link" href="pages/decisions.html">Prerequisites &rarr;</a></div>
  <div class="kpi"><span class="kpi-label">Questions enumerated</span><strong>{len(q.get("rows",[]))}</strong><p class="small">Each with Have / Don't Have / answer / discovery suggestion.</p><a class="card-link" href="pages/questions.html">Q&A &rarr;</a></div>
  <div class="kpi"><span class="kpi-label">QB ↔ WR1 correlation</span><strong>0.562</strong><p class="small">7560 team-games; joint 11.1% vs product 5.7%.</p><a class="card-link" href="pages/correlations.html">Correlation &rarr;</a></div>
  <div class="kpi"><span class="kpi-label">Strategies approved</span><strong>0 / 7</strong><p class="small">Ten gates; every candidate fails at least five.</p><a class="card-link" href="pages/leaderboard.html">Leaderboard &rarr;</a></div>
</div>
<section class="block"><div class="eyebrow">AT A GLANCE</div><h2>Five findings that matter</h2>
{table(["Finding","Measured value","What it means","Source"],[
    ["Closing spread is hard to beat","MAE 10.25 pts, slope 1.05","Line this accurate leaves no room for simple model.",'<span class="src"><a href="https://github.com/nflverse/nflverse-data" rel="noopener">nflverse schedules feed</a></span>'],
    ["Model adds nothing beyond close","c=-0.019 (p=0.881)","Coefficient on our margin controlling for close.",'<span class="src"><a href="https://github.com/nflverse/nflverse-data" rel="noopener">Computed from same feed</a></span>'],
    ["Pythagorean luck does not persist","r=0.024 (n=842)","Wins above expectation are noise.",'<span class="src"><a href="https://github.com/nflverse/nflverse-data" rel="noopener">Computed from game results</a></span>'],
    ["Same-game legs correlated","Joint 11.1% vs product 5.7%","Pricing independently overstates parlay odds.",'<span class="src"><a href="https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports" rel="noopener">NFL data partner</a> · <a href="https://github.com/nflverse/nflverse-data" rel="noopener">Player box scores</a></span>'],
    ["Prop model barely beats baseline","MAE change -0.35%","Small gain cannot be converted to ROI without price feed.",'<span class="src"><a href="https://www.nflgsis.com/gsis/documentation/stadiumguides/guide_for_statisticians.pdf" rel="noopener">How stats credited</a></span>'],
])}
</section>
<div class="grid2"><div class="panel"><h3>What is verified today</h3><ul><li>7,548 games (1999-2026) with closing lines, downloaded and hashed.</li><li>260,520 player-weeks (2012-2026).</li><li>Spread sign convention proven from data.</li><li>Every strategy tested out-of-sample 2023+ through 10 gates.</li><li>49 independent recomputations: 45 agree, 0 fail; 2020 and 2026 each 32/32 vs NFL.com.</li></ul><a href="pages/sources.html">Source register &rarr;</a></div>
<div class="panel"><h3>What is deliberately blank</h3><ul><li>No historical player-prop prices — no prop ROI.</li><li>No verified execution access — G9 fails by construction.</li><li>No funded prize pool — paper schedule.</li><li>No per-team deficiency tracker yet — design published, cells blank.</li><li>Injury-policy content not serving; definitions from Competition Committee article.</li></ul><a href="pages/flagged.html">Flagged for review &rarr;</a></div></div>
"""
    return h+body+footer("index.html")

def build_executive():
    h=header("Executive summary","EXECUTIVE SUMMARY","pages/executive.html")
    body='<div class="hero compact"><div class="eyebrow">EXECUTIVE SUMMARY</div><h1>The market beats the model. The gates do their job. The missing pieces are named.</h1><p class="lede">Independent NFL line-origination on 7,548 games (1999-2026) with 260,520 player-weeks, verified 2026-11-12. Every row links to official source.</p></div>'
    body+= '<section class="block"><h2>Bottom line</h2>' + table(["Question","Answer","Evidence","Source"],[
        ["Can the closing line be beaten?","No","Model 10.39 vs market 10.25; c=-0.019 p=0.881",'<span class="src"><a href="https://github.com/nflverse/nflverse-data" rel="noopener">nflverse schedules feed</a></span>'],
        ["Any strategy pass all ten gates?","No — 0 of 7 (+2 controls)","Every candidate fails ≥5; G9 fails for all",'<span class="src"><a href="https://www.gaming.nv.gov/siteassets/content/regs/regulation-22-as-of-1-26.pdf" rel="noopener">Nevada Reg 22</a> · <a href="https://massgaming.com/wp-content/uploads/DraftKings-House-Rules-10.7.26.pdf" rel="noopener">MGC house rules</a></span>'],
        ["Are parlay / prop legs independent?","No","QB→WR1 r=0.562 n=7560; joint 11.1% vs 5.7%",'<span class="src"><a href="https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/correlat.htm" rel="noopener">NIST correlation</a> · <a href="https://github.com/nflverse/nflverse-data" rel="noopener">Player box scores</a></span>'],
        ["Is win-loss record reusable signal?","Mostly luck","Pythagorean R²=0.819; y-o-y luck r=0.024 n=842",'<span class="src"><a href="https://www.nfl.com/standings/division/2020/REG" rel="noopener">NFL.com 2020</a> · <a href="https://www.nfl.com/standings/division/2026/REG" rel="noopener">NFL.com 2026</a></span>'],
        ["Can prop ROI be measured?","Not here","No historical prop prices — flagged",'<span class="src"><a href="https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports" rel="noopener">NFL official data partner</a></span>'],
        ["Do numbers survive recomputation?","Yes (arithmetic)","45/49 agree, 0 fail; 2020 32/32 & 2026 32/32",'<span class="src"><a href="https://www.nfl.com/standings/division/2020/REG" rel="noopener">NFL.com 2020</a> · <a href="https://www.nfl.com/standings/division/2026/REG" rel="noopener">NFL.com 2026</a></span>'],
    ]) + '</section>'
    body+= '<section class="block"><h2>10-gate validation</h2><div class="grid2"><div class="panel"><h3>Gates G1-G10</h3><ol><li>G1 point-in-time integrity</li><li>G2 sample n≥1000</li><li>G3 out-of-sample walk-forward 2023+</li><li>G4 significance + FDR q≤0.10</li><li>G5 bootstrap lower bound >0</li><li>G6 stability ≥60% seasons</li><li>G7 beats closing line</li><li>G8 deflated Sharpe p<0.05</li><li>G9 executable verified</li><li>G10 reproducible</li></ol></div><div class="panel"><h3>What market already prices</h3><ul><li>Spread slope 1.05, mean error +0.037 pts p=0.81 median 0</li><li>Home cover 50.0% over 13,784 team-games</li><li>Wind-under 649→430 bets when excluding no-price rows; +8.65%→+7.14% p=0.125 artefact</li><li>Pythagorean luck SD 1.32 wins, persistence 0.024 noise</li></ul></div></div></section>'
    body+= '<section class="block"><h2>Open gap: injuries & depth deficiencies</h2><p>System cannot answer which defense/offense is deficient because starter Out replaced by 2nd/3rd/4th string. Official injury reports and depth charts exist (NFL.com hub, Colts depth chart), but no automated tracker joins them. <a href="injuries.html">Injuries & Depth page</a> publishes schema (injury_report_daily, depth_chart_tier, team_deficiency_signal), 4pm ET schedule, example rows — cells blank until built. <a href="suggestions.html">SUG-03</a> closes this.</p><ul><li><strong>Have:</strong> weekly injury hub; official depth charts First/Second/Third/Fourth; roster ACT/RES/DEV.</li><li><strong>Missing:</strong> daily ingestion, Player→DepthRank mapping, historical score — flagged.</li></ul></section>'
    body+= '<section class="block"><h2>Where decisions blocked</h2><p>Four classes blocked until discovery: approving strategy for reward (G9 missing), injury/depth signals (tracker missing), executable pricing (account+j jurisdiction missing), funded prizes (pool not funded). Listed with suggestion that discovers each on <a href="decisions.html">Decision Prerequisites</a> and <a href="questions.html">Q&A</a>.</p></section>'
    body+= '<section class="block"><h2>What to do next</h2><ol><li>Review 12 proposals mark proposed→approved/rejected/in_progress.</li><li>For approved, open named branch per suggestion, edit only its scope, pass CI before merge.</li><li>Do not estimate flagged blanks — open official source first.</li></ol><p class="small">Complements root Line Lab dashboard (14 pages, 49 checks, 71 sibling pages). Nothing overwritten; hub lives in suggestions/ only.</p></section>'
    return h+body+footer("pages/executive.html")

def build_suggestions():
    data=load("suggestions.json")
    rows=[]
    for r in data.get("rows",[]):
        cls={"high":"bad","medium":"warn","low":"ok"}.get(r["priority"],"ok")
        rows.append([esc(r["id"]), f"<strong>{esc(r['proposal'])}</strong><br><span class=\"small\">{esc(r['detail'])}</span>", badge(r["priority"],cls), esc(r["expected_impact"]), esc(r["category"]), badge(r["status"],"warn" if r["status"]=="proposed" else "ok"), f'<span class="src">{src_link(r["sources"])}</span>'])
    h=header("Suggestions — review before implementing","SUGGESTIONS","pages/suggestions.html")
    body=f'<div class="hero compact"><div class="eyebrow">SUGGESTIONS</div><h1>12 proposals for review — nothing ships unapproved.</h1><p class="lede">Each row is concrete change with priority, impact and official source. Reviewer decides which path to take; no proposal ships until status moves from proposed to approved.</p></div><div class="notice"><strong>Review rule:</strong> {esc(data.get("proposal_review_rule",""))} &nbsp; <a href="decisions.html">See what decisions these unblock &rarr;</a></div>'
    body+=f'<section class="block"><h2>Suggestion catalog</h2>{table(["ID","Proposal & detail","Priority","Expected impact","Category","Status","Source"],rows)}</section>'
    body+='<section class="block"><h2>How to use</h2><ol><li>Read each proposal detail.</li><li>Mark status proposed→approved/rejected/in_progress.</li><li>Enforce gate on Decision Prerequisites page.</li><li>Check Flagged before claiming completeness.</li></ol></section>'
    return h+body+footer("pages/suggestions.html")

def build_decisions():
    data=load("decisions.json")
    rows=[]
    for r in data.get("rows",[]):
        avail=r["availability"]; cls="ok" if avail=="have" else ("warn" if avail=="partial"else "bad")
        rows.append([esc(r["id"]),esc(r["decision_area"]),esc(r["required_information"]),badge(avail,cls),esc(r["where_to_find"]),esc(r["suggestion_to_discover"]),f'<span class="src">{src_link(r["sources"])}</span>'])
    h=header("Decision prerequisites","DECISION PREREQUISITES","pages/decisions.html")
    body=f'<div class="hero compact"><div class="eyebrow">DECISION PREREQUISITES</div><h1>Must be true before deciding.</h1><p class="lede">A decision is any commitment of attention, capital, model choice, or site change. If required information reads missing/unverified, decision blocked.</p></div><div class="notice"><strong>Rule:</strong> {esc(data.get("rule",""))}</div>'
    body+=f'<section class="block"><h2>Prerequisites inventory — Have / Don\'t Have / How to get it</h2>{table(["ID","Decision area","Required information","Availability","Where to find it","Suggestion to discover if missing","Source"],rows)}</section>'
    body+='<section class="block"><h2>How this prevents bad bets</h2><ul><li>If DEC-03, DEC-05, DEC-10 blocked, no capital decision — leaderboard stays Tier 3.</li><li>Every blocked row names specific suggestion (SUG-03, SUG-06, SUG-08, SUG-09, SUG-12) whose completion supplies missing input with sourced row.</li><li>Discovery is opening official NFL.com injury hub at 4pm ET and publishing sentence with source link.</li></ul></section>'
    return h+body+footer("pages/decisions.html")

def build_questions():
    data=load("questions.json")
    rows=[]
    for r in data.get("rows",[]):
        have=r["have_or_missing"]; cls="ok" if have=="have" else ("warn" if have=="partial" else "bad")
        rows.append([esc(r["id"]),f"<strong>{esc(r['question'])}</strong>",esc(r["information_needed"]),badge(have,cls),esc(r["answer"]) if r["answer"] else '<span class="badge warn">blank — see suggestion</span>',esc(r["suggestion_if_missing"]),f'<span class="src">{src_link(r["sources"])}</span>'])
    h=header("Questions, information & answers before any decision","QUESTIONS & ANSWERS","pages/questions.html")
    body='<div class="hero compact"><div class="eyebrow">QUESTIONS & ANSWERS</div><h1>15 questions that must be answered before any reasonable decision.</h1><p class="lede">Grouped by what we have and what we don\'t. Where answer measurable from official feeds, shown with sample size; where not — injury deficiencies, executable pricing, prop ROI — cell blank and suggestion named.</p></div>'
    body+=f'<section class="block"><h2>Q&A matrix</h2>{table(["ID","Question","Information needed","We have it?","Answer from current data","Suggestion to discover missing piece","Source"],rows)}</section>'
    body+='<section class="block"><h2>How suggestions discover missing info</h2><ul><li><strong>Prop/executable pricing (Q-06, Q-10, Q-14):</strong> SUG-09 documents Big Data Bowl precedent keeps schedule unfunded until sponsor+jurisdiction.</li><li><strong>Injuries (Q-08, Q-09):</strong> SUG-03 implements 4pm ET scrape of injury hub + depth charts; only after history can starter-vs-backup deltas be gated.</li><li><strong>Weather (Q-11):</strong> SUG-06 adds wind_gust + weather_available boolean.</li><li><strong>Staleness (Q-13, Q-15):</strong> SUG-10 automates weekly 32/32 vs NFL.com reconciliation.</li></ul></section>'
    return h+body+footer("pages/questions.html")

def build_injuries():
    data=load("injuries.json")
    h=header("Injuries & depth-chart deficiencies","INJURIES & DEPTH","pages/injuries.html")
    cap=data["current_capability"]
    src_rows=[[esc(s["source_id"]),esc(s["role"]),esc(s["update_cadence"]),esc(s["example_row"]),f'<span class="src">{src_link(s["sources"])}</span>'] for s in data["official_sources"]]
    schema_rows=[[esc(t["table"]),esc(", ".join(t["columns"])),esc(t["notes"]),f'<span class="src">{src_link(t["sources"])}</span>'] for t in data["proposed_schema"]]
    ex_rows=[[esc(e["team"]),esc(e["week"]),esc(e["unit"]),esc(e["position"]),esc(e["scenario"]),esc(e["evidence"]),f'<span class="src">{src_link(e["sources"])}</span>'] for e in data["example_deficiency_rows"]]
    blank_rows=[[esc(b["item"]),esc(b["reason"]),f'<span class="src">{src_link(b["sources"])}</span>'] for b in data["what_stays_blank_until_built"]]
    body=f"""
<div class="hero compact"><div class="eyebrow">INJURIES & DEPTH TRACKING</div><h1>Know who is actually on the field — starters, backups, and who replaces whom.</h1><p class="lede">Official NFL injury-report hub and team depth charts already list info that decides deficiencies. No tracker joins them yet. This page publishes design; no injury signal published until inputs are official, point-in-time and tied to depth tier.</p></div>
<section class="block"><h2>Current capability</h2><div class="grid2"><div class="panel"><h3>What exists today</h3><p>{esc(cap["what_exists"])}</p></div><div class="panel"><h3>What is missing</h3><p>{esc(cap["what_is_missing"])}</p><p class="small">{esc(cap["why_it_matters"])}</p></div></div></section>
<section class="block"><h2>Official feeds tracker will read</h2>{table(["Source","Role","Update cadence","Example row as read","Source"],src_rows)}</section>
<section class="block"><h2>Proposed storage schema — no invented tiers</h2><p class="small">Depth rank is ordinal official depth chart prints. If team groups WR as LWR/SWR/RWR, preserve that — never invent tier beyond roster sentence.</p>{table(["Table","Columns","Notes","Source"],schema_rows)}</section>
<section class="block"><h2>Example deficiency rows (illustrative; not yet dataset)</h2>{table(["Team","Week","Unit","Pos","Scenario & interpretation","Evidence sentence","Source"],ex_rows)}</section>
<section class="block"><h2>What stays blank until tracker built and has history</h2>{table(["Item","Reason blank by policy","Source"],blank_rows)}</section>
<section class="block"><h2>Suggested build schedule</h2><p>{esc(data["schedule"])}</p><ul><li>Each fetch commits JSON with fetched_utc and source_url — only rows with both count.</li><li>Model reading deficiency before files updated is blocked (G1).</li><li>Only after several seasons can starter-vs-backup deltas be gated via FDR.</li></ul></section>
"""
    return h+body+footer("pages/injuries.html")

def build_signals():
    sig=load("signals.json")
    h=header("Signals & origination","SIGNALS & ORIGINATION","pages/signals.html")
    summ=sig.get("origination_summary",{})
    rows=[]
    for r in sig.get("rows",[]):
        status=r["status"]; cls="ok" if "no edge" in status or "proven" in status else ("warn" if "inconclusive" in status or "marginal" in status else "ok")
        if "unmeasured" in status: cls="warn"
        rows.append([esc(r["id"]),esc(r["signal"]),esc(r["inputs"]),esc(r["hypothesis"]), esc(r["measured"]) if r["measured"] else '<span class="badge warn">blank — design only</span>', badge(status,cls), f'<span class="src">{src_link(r["sources"])}</span>'])
    body=f"""
<div class="hero compact"><div class="eyebrow">SIGNALS & ORIGINATION</div><h1>Originate the line. Then stress-test every signal.</h1><p class="lede">Walk-forward spreads, totals and prop quantiles from official play-by-play feed — then 10 gated tests per strategy.</p></div>
<section class="block"><h2>Origination spec</h2><div class="panel"><p><strong>Form:</strong> {esc(summ.get("model",""))}</p><p><strong>Accuracy:</strong> {esc(summ.get("accuracy",""))}</p><p class="small">{esc(summ.get("source_notes",""))}</p></div></section>
<section class="block"><h2>Signal catalog</h2>{table(["ID","Signal","Inputs (pre-kickoff only)","Hypothesis","Measured result","Status","Source"],rows)}</section>
<section class="block"><h2>Research program</h2><ul><li>Start from what market prices: slope 1.05 residual SD 13.2 pts leaves little room; incremental p=0.881 proves simple model insufficient.</li><li>Build point-in-time features only with availability flags (SUG-03, SUG-06).</li><li>Gate every candidate via 10 gates; only all-pass appears ranked — today zero.</li><li>Treat single, parlay, prop-combo as one competition: correlation-aware pricing, price-exclusion counts.</li></ul></section>
"""
    return h+body+footer("pages/signals.html")

def build_leaderboard():
    lb=load("leaderboard.json")
    h=header("Leaderboard — ranked by gate count, then ROI","LEADERBOARD","pages/leaderboard.html")
    reward_rows=[[esc(r["tier"]),esc(r["requirement"]),esc(r["reward"]),f'<span class="src">{src_link(r["sources"])}</span>'] for r in lb.get("reward_schedule",[])]
    gate_rows=[[esc(g["id"]),esc(g["name"]),esc(g["rule"]),f'<span class="src">{src_link(g["sources"])}</span>'] for g in lb.get("gate_definitions",[])]
    entry_rows=[]
    for e in lb.get("entries",[]):
        entry_rows.append([esc(e["rank"]),esc(e["id"]),esc(e["name"]),esc(e["family"]),badge(e["verdict"],"bad" if e["verdict"]=="REJECTED" else "ok"),esc(e["gates_passed"]),esc(str(e["n_bets"])),esc(e["roi"]) if e["roi"] else '<span class="badge warn">blank — no price</span>',esc(e["failed_gates"]),f'<span class="src">{src_link(e["sources"])}</span>'])
    rs=lb.get("reward_summary",{})
    body=f"""
<div class="hero compact"><div class="eyebrow">LEADERBOARD COMPETITION</div><h1>Ranked by gates, not vibes. Rewards only when every gate passes.</h1><p class="lede">Modeled on Kaggle public/private split and NFL Big Data Bowl $100k judged by NFL club analysts.</p></div>
<section class="block"><h2>Reward schedule — paper schedule until funded</h2>{table(["Tier","Requirement","Reward","Source"],reward_rows)}</section>
<section class="block"><h2>Current entries — 0 approved</h2>{table(["Rank","ID","Strategy","Family","Verdict","Gates","Bets","ROI","Failed gates","Source"],entry_rows)}</section>
<section class="block"><h2>Reward summary</h2><div class="panel"><p>Strategies: {rs.get("total_strategies","")} + {rs.get("controls","")} controls · Approved: {esc(rs.get("approved","0"))} · Top: {esc(rs.get("top_performer",""))} · Paid: {esc(rs.get("rewards_paid","0"))}</p><p class="small">{esc(rs.get("note",""))}</p></div></section>
<section class="block"><h2>Gates G1-G10</h2>{table(["ID","Gate","Rule","Source"],gate_rows)}</section>
<section class="block"><h2>Metrics</h2><ul><li><strong>CLV</strong> = bet price vs close; positive means beat close. Requires timestamp + close (unavailable, so ROI measured at close).</li><li><strong>ROI</strong> = profit / staked; win rate vs break-even 52.38% at -110 via 110/210.</li><li><strong>Win rate p</strong> = NIST one-proportion test (N>30).</li><li><strong>Sample & power</strong> = NIST sample-size formulas; G2 enforces larger of 1000 or power minimum.</li></ul></section>
"""
    return h+body+footer("pages/leaderboard.html")

def build_correlations():
    data=load("correlations.json")
    rows=[]
    for r in data.get("rows",[]):
        if "r" in r:
            rows.append([esc(r["pair"]),esc(r["n"]),esc(f'{r["r"]:.3f}'),esc(r.get("p","")),esc(f'{r.get("ci_low",0):.3f} to {r.get("ci_high",0):.3f}'),esc(r.get("r2","")),esc(r["interpretation"]),f'<span class="src">{src_link(r["sources"])}</span>'])
        else:
            rows.append([esc(r["pair"]),esc(r["n"]),esc(f'joint {r["joint"]:.3f} vs product {r["product"]:.3f} (×{r["factor"]:.2f})'),esc(""),esc(""),esc(""),esc(r["interpretation"]),f'<span class="src">{src_link(r["sources"])}</span>'])
    h=header("Correlation & parlay / prop-combo pricing","CORRELATION & PARLAYS","pages/correlations.html")
    body=f'<div class="hero compact"><div class="eyebrow">CORRELATION</div><h1>Same-game legs are not independent — price as joint, not product.</h1><p class="lede">Pearson correlations per team-game (both sides) on committed extract; SGP and prop-combo legs share driver.</p></div><section class="block"><h2>Measured correlations</h2>{table(["Pair / joint test","n","r or joint vs product","p","95% CI","R²","Interpretation","Source"],rows)}</section>'
    body+=f'<section class="block"><h2>Pricing note</h2><p class="small">{esc(data.get("pricing_note",""))}</p><p class="small">Sources: <span class="src">{src_link(data.get("sources_for_note",[]))}</span></p></section>'
    body+='<section class="block"><h2>What this changes</h2><ul><li>Same-team QB→WR1 parlay at independent prices quotes ~2× too long.</li><li>Prop stacks using ex-post leaders inflate r by ~+0.24; need ex-ante depth-ranked assignments (SUG-03).</li><li>Cross-game legs approx independent (r≈0); compounded vig dominates unless each leg beats close.</li></ul></section>'
    return h+body+footer("pages/correlations.html")

def build_luck():
    data=load("luck.json")
    rows=[[esc(r["metric"]),esc(r["value"]),esc(r["interpretation"]),f'<span class="src">{src_link(r["sources"])}</span>'] for r in data.get("rows",[])]
    h=header("Removing luck — isolating skill","REMOVING LUCK","pages/luck.html")
    body='<div class="hero compact"><div class="eyebrow">REMOVING LUCK</div><h1>Luck cannot be deleted. It can be priced.</h1><p class="lede">Would a thousand random portfolios same size at same prices lose to it >95%? Today none do.</p></div>'
    body+=f'<section class="block"><h2>Luck decomposition</h2>{table(["Metric","Measured value","Interpretation","Source"],rows)}</section>'
    body+='<section class="block"><h2>How gates keep skill</h2><ul><li><strong>G4 FDR:</strong> BH q≤0.10 across strategies tried — lone p≈0.02 fails when 5 angles tested.</li><li><strong>G8 luck-adjusted:</strong> deflated Sharpe p<0.05 calibrated to variants — wind-under +34.88% n=63 → -3.93% after shrinkage.</li><li><strong>Public/private split:</strong> season-to-date ranks public; private window (last 4 weeks never tuned) final.</li><li><strong>Result:</strong> nothing ranked preferred over noise promoted — every entry REJECTED until all 10 gates including executable.</li></ul></section>'
    return h+body+footer("pages/luck.html")

def build_sources():
    reg=load("sources.json")
    rows=[[f'<strong>{esc(s["label"])}</strong><br><span class="small">{esc(s["publisher"])} · {esc(s["type"])}</span>', esc(s["what_confirmed"]), f'<span class="src"><a href="{esc(s["url"])}" rel="noopener">Open</a></span>'] for s in reg.get("sources",[])]
    h=header("Source register — every row links here","SOURCE REGISTER","pages/sources.html")
    body=f'<div class="hero compact"><div class="eyebrow">SOURCE REGISTER</div><h1>Every claim has a link.</h1><p class="lede">39 sources opened and read on 2026-11-12. Tables cite SRC-* IDs.</p></div><section class="block"><h2>Registry</h2>{table(["Source (publisher · type)","What was confirmed","Link"],rows)}</section>'
    return h+body+footer("pages/sources.html")

def build_flagged():
    data=load("flagged.json")
    rows=[]
    for r in data.get("rows",[]):
        cls={"high":"bad","medium":"warn","low":"ok"}.get(r["severity"],"warn")
        rows.append([esc(r["id"]),esc(r["item"]),badge(r["severity"],cls),esc(r["reason"]),esc(r["action"]),f'<span class="src">{src_link(r["sources"])}</span>'])
    h=header("Flagged for review — blanks are intentional","FLAGGED FOR REVIEW","pages/flagged.html")
    body='<div class="hero compact"><div class="eyebrow">FLAGGED FOR REVIEW</div><h1>Blanks are policy, not omission.</h1><p class="lede">If value cannot be confirmed from official source, left blank and listed — not inferred.</p></div>'
    body+=f'<section class="block"><h2>Flagged items</h2>{table(["ID","Item","Severity","Reason unverified","What to do before filling","Source"],rows)}</section>'
    return h+body+footer("pages/flagged.html")

def build_requirements():
    data=load("requirements.json")
    rows=[]
    for r in data.get("requirements",[]):
        cls="ok" if r["status"] in ("done","enforced","observed") else ("warn" if r["status"]=="partial" else "bad")
        rows.append([esc(r["id"]),esc(r["text"]),esc(r["category"]),badge(r["status"],cls),esc(r["evidence"]),f'<span class="src">{src_link(r["sources"])}</span>'])
    h=header("Requirements — full list traced to the prompt","REQUIREMENTS","pages/requirements.html")
    body='<div class="hero compact"><div class="eyebrow">REQUIREMENTS</div><h1>Every requirement traced, and whether it is met.</h1><p class="lede">17 requirements extracted verbatim from prompt; each cites artefact and official source.</p></div>'
    body+=f'<section class="block"><h2>Requirements matrix</h2>{table(["ID","Requirement (verbatim)","Category","Status","Evidence in repo","Source"],rows)}</section>'
    return h+body+footer("pages/requirements.html")

BUILDERS={
    "index.html": build_index,
    "pages/executive.html": build_executive,
    "pages/suggestions.html": build_suggestions,
    "pages/decisions.html": build_decisions,
    "pages/questions.html": build_questions,
    "pages/injuries.html": build_injuries,
    "pages/signals.html": build_signals,
    "pages/leaderboard.html": build_leaderboard,
    "pages/correlations.html": build_correlations,
    "pages/luck.html": build_luck,
    "pages/sources.html": build_sources,
    "pages/flagged.html": build_flagged,
    "pages/requirements.html": build_requirements,
}
def main():
    for rel,fn in BUILDERS.items():
        out=ROOT/rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(fn())
        print(f"wrote {rel}")
    print("done")
if __name__=="__main__": main()
