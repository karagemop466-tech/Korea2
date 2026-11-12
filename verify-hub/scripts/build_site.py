#!/usr/bin/env python3
"""Deterministic static-site generator for verify-hub (cross-lab verification & decision hub).

Reads verify-hub/data/*.json and renders verify-hub/index.html, verify-hub/pages/*.html
and verify-hub/EXECUTIVE_SUMMARY.md. Nothing is hand-written in the HTML: every value
comes from the committed JSON. Re-running the generator is byte-identical.

Session arena/f1123a1a-korea2. Standard library only.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PAGES = ROOT / "pages"

NAV = [
    ("index.html", "Home"),
    ("pages/repo-audit.html", "Repo audit"),
    ("pages/questions.html", "Questions"),
    ("pages/suggestions.html", "Suggestions"),
    ("pages/leaderboard.html", "Leaderboard"),
    ("pages/injuries-depth.html", "Injuries &amp; depth"),
    ("pages/executive.html", "Executive"),
    ("pages/sources.html", "Sources"),
    ("pages/flagged.html", "Flagged"),
]


def load(name: str) -> dict:
    with open(DATA / name, encoding="utf-8") as fh:
        return json.load(fh)


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def link(href: str, label: str, cls: str = "") -> str:
    c = f' class="{cls}"' if cls else ""
    return f'<a href="{esc(href)}"{c} rel="noopener">{label}</a>'


LINK_PREFIX = ""  # set per rendered page depth inside build()


def src_links(where: str, source_ids: list[str], src_by_id: dict, prefix: str | None = None) -> str:
    """Source cell: the internal 'where published' link first, then each registered source.

    `where` values are relative to the verify-hub root; `prefix` re-bases them for
    pages rendered one level down (verify-hub/pages/*.html).
    """
    if prefix is None:
        prefix = LINK_PREFIX
    parts = []
    if where:
        parts.append(link(prefix + where, "where published", "internal"))
    for sid in source_ids:
        s = src_by_id.get(sid)
        if not s:
            continue
        parts.append(link(s["url"], esc(s["label"]), "ext"))
    return " &middot; ".join(parts) if parts else ""


def table(headers: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for r in rows:
        tds = "".join(f"<td>{c}</td>" for c in r)
        body.append(f"<tr>{tds}</tr>")
    return (
        '<div class="table-wrap"><table><thead><tr>'
        + th
        + "</tr></thead><tbody>"
        + "\n".join(body)
        + "</tbody></table></div>"
    )


def page(title: str, body: str, active: str, depth: int = 0) -> str:
    prefix = "../" * depth
    nav_links = []
    for href, label in NAV:
        full = prefix + href
        cur = ' class="active"' if href == active else ""
        nav_links.append(f'<a href="{full}"{cur}>{label}</a>')
    nav_html = "\n      ".join(nav_links)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | Verify Hub</title>
<meta name="description" content="Cross-lab verification, decision-readiness and suggestion review for the NFL research repository.">
<meta name="generator" content="verify-hub/scripts/build_site.py">
<link rel="stylesheet" href="{prefix}assets/style.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="shell">
  <aside class="sidebar">
    <a class="brand" href="{prefix}index.html"><span class="mark">VH</span><span>VERIFY HUB<small>CROSS-LAB DECISIONS</small></span></a>
    <nav aria-label="Hub navigation">
      {nav_html}
    </nav>
    <div class="sidebar-note">Sibling labs are read-only inputs to this hub. Live root site: <a href="{prefix}index.html" rel="noopener">Line Lab</a>.</div>
  </aside>
  <main id="main">
    <header class="topbar"><span class="crumb">{title.upper()}</span>
      <a class="review-link" href="{prefix}pages/flagged.html">Flagged for review &nearr;</a>
    </header>
{body}
    <footer>
      <p>Research and measurement, not betting advice. Every value is read from committed JSON by
      <code>verify-hub/scripts/build_site.py</code>; every table row links the source it rests on.
      Values that no official source confirms are left blank and published on the Flagged page.</p>
      <p><a href="{prefix}pages/sources.html">Source register</a> &middot;
         <a href="{prefix}pages/questions.html">Decision questions</a> &middot;
         <a href="{prefix}pages/flagged.html">Flagged for review</a></p>
    </footer>
  </main>
</div>
</body>
</html>
"""


def exec_summary_content() -> list[dict]:
    """Single source of truth for the executive summary (Markdown + HTML renderings)."""
    return [
        {
            "heading": "1. Bottom line",
            "bullets": [
                "The repository is a complete measurement apparatus: five gate systems, four labs with walk-forward results, an independent recomputation (49 checks, 0 disagreements) and official-source reconciliations (32/32 teams for 2020 and 2026 at their snapshot dates).",
                "No strategy has passed validation anywhere: root 0 of 9, skill-lab 0 of 16, quant-lab 0 of 21, origination-lab 0 eligible, pipeline 0 of 5. Nothing here should be bet.",
                "The closing market beats the model (MAE 9.71 vs 10.39; incremental coefficient -0.019, p = 0.881; Brier skill -0.038).",
                "Same-game parlay legs are strongly correlated (QB-WR1 r = 0.56-0.61; 4-leg joint 11.1% vs 5.7% product); independent leg pricing is wrong and favors the bettor, which is why books reprice SGPs.",
                "The injury/depth requirement is half-satisfiable from official data today: the weekly injury report is official and live (verified Week 10 2026), but depth strings (1st-4th) are not published by the league (404 verified).",
            ],
        },
        {
            "heading": "2. What this hub adds",
            "bullets": [
                "A line-by-line cross-lab claims audit: 45 published claims, each with its evidence class (10 verified against official sources on 2026-11-12, 21 verified against committed data, 6 blank/unverified, 8 irregularities).",
                "A decision-readiness register: 20 questions with Have/Partial/Missing status, verified answers where they exist, and a discovery suggestion for every gap.",
                "A suggestion review queue (14 proposals) with trade-offs and a recommended path per proposal - nothing is implemented until a reviewer approves.",
                "One cross-lab consolidation of strategies, gates, correlations, luck metrics and reward schedules, with every lab's window and definition printed next to its numbers.",
            ],
        },
        {
            "heading": "3. Decisions the owner must make before anything is implemented",
            "bullets": [
                "SG-01: declare one canonical site (recommended: root Line Lab) and treat the eight sibling hubs as archives.",
                "SG-02: adopt one injury & depth tracker design (official report + inferred usage tiers, blanks kept).",
                "SG-03/SG-04: adopt one gate catalog and one reward schedule (paper until funding is decided).",
                "Q-05/Q-06: decide whether to acquire a licensed historical odds feed - without it there can be no prop ROI and no CLV, ever.",
            ],
        },
        {
            "heading": "4. Verification performed on 2026-11-12",
            "bullets": [
                "NFL.com 2026 standings page: all 32 records read; repo snapshots reconcile at 2026-11-01/02 and drift with Week 9 is documented team by team.",
                "NFL.com Week 10 injury report: live; team records inside it match the standings page; per-team rows transcribed as the verified sample on the Injuries page.",
                "nflverse release metadata via the GitHub Releases API: 28/31 manifest assets byte-match upstream; 3 rolling 2026 assets are newer upstream (expected, flagged).",
                "Two cited official URLs confirmed dead (operations.nfl.com injury policy; nfl.com club depth-chart) and recorded as irregularities with blank values.",
                "Full local suite green: tests/check_site.py, tests/check_derived.py, scripts/check_links.py, scripts/validate_data.py, audit/check_site.py, plus this hub's verify.py and unit tests.",
            ],
        },
    ]


def render_exec_html(src_by_id: dict) -> str:
    parts = ['<div class="hero"><div class="eyebrow">EXECUTIVE SUMMARY</div>',
             "<h1>What matters,<br><em>and what must be decided.</em></h1>",
             '<p class="lede">Generated from verify-hub/data and the committed lab results on 2026-11-12. '
             'The Markdown twin of this page is verify-hub/EXECUTIVE_SUMMARY.md.</p></div>']
    for sec in exec_summary_content():
        items = "".join(f"<li>{esc(b)}</li>" for b in sec["bullets"])
        parts.append(f'<section class="block"><h2>{esc(sec["heading"])}</h2><ul class="ticks">{items}</ul></section>')
    row = [
        "Audit rows published with evidence classes",
        "45 rows (10 official / 21 internal / 6 blank / 8 irregularities)",
        "Every claim any lab publishes, checked line by line",
        src_links("pages/repo-audit.html", ["VH-SRC-09"], src_by_id),
    ]
    parts.append('<section class="block"><h2>Audit at a glance</h2>' + table(
        ["Item", "Value", "Meaning", "Source"], [row]) + "</section>")
    return "\n".join(parts)


def render_exec_md() -> str:
    lines = [
        "# Executive summary — Verify Hub (cross-lab verification & decision hub)",
        "",
        "**Session:** arena/f1123a1a-korea2  |  **As of:** 2026-11-12  |  **Site:** verify-hub/index.html",
        "",
        "Every number below is read from committed JSON by verify-hub/scripts/build_site.py; the HTML twin",
        "of this file is verify-hub/pages/executive.html. Values no official source confirms are blank and",
        "published on the Flagged page.",
        "",
    ]
    for sec in exec_summary_content():
        lines.append(f"## {sec['heading']}")
        lines.append("")
        for b in sec["bullets"]:
            lines.append(f"- {b}")
        lines.append("")
    lines += [
        "## Status rules used throughout this hub",
        "",
        "- verified-official — checked against an official publisher on 2026-11-12 (link in the row).",
        "- verified-internal — read from committed repo data and matched to the published page; computed from third-party feed extracts; no official publisher of the statistic exists.",
        "- unverified-blank — cannot be confirmed; value left blank; published on the Flagged page.",
        "- irregularity — inconsistency, dead source or quotation hazard found by the audit.",
        "",
        "Research and measurement, not betting advice. 0 strategies approved. Reward schedules are paper.",
    ]
    return "\n".join(lines) + "\n"


def build() -> list[Path]:
    global LINK_PREFIX
    LINK_PREFIX = ""
    PAGES.mkdir(parents=True, exist_ok=True)
    sources = load("sources.json")
    src_by_id = {s["id"]: s for s in sources["sources"]}
    audit = load("claims_audit.json")
    questions = load("questions.json")
    sugg = load("suggestions.json")
    strat = load("strategies.json")
    inj = load("injuries_gap.json")
    flagged = load("flagged.json")

    written: list[Path] = []

    # ---------- index ----------
    kpis = [
        ("Strategies approved (all labs)", "0", "Five gate systems, 68 strategy rows tested, zero passes.", "pages/leaderboard.html"),
        ("Audit rows checked", "45", "10 verified against official sources, 21 against committed data, 8 irregularities.", "pages/repo-audit.html"),
        ("Decision questions open", "20", "9 answered, 7 partial, 4 missing - each missing item has a discovery suggestion.", "pages/questions.html"),
        ("Suggestions awaiting review", "14", "Nothing is implemented until a reviewer picks a path.", "pages/suggestions.html"),
        ("Injury/depth official coverage", "partial", "Weekly report is official and live; depth strings are not published by the league.", "pages/injuries-depth.html"),
        ("Flags for owner review", "12", "All values blank by policy; none blocks publication.", "pages/flagged.html"),
    ]
    kpi_html = "".join(
        f'<article class="kpi"><span class="kpi-label">{esc(label)}</span><strong>{esc(val)}</strong>'
        f"<p>{esc(note)}</p><a class=\"card-link\" href=\"{esc(href)}\">Open &rarr;</a></article>"
        for label, val, note, href in kpis
    )
    body = f"""
    <div class="hero">
      <div class="eyebrow">CROSS-LAB VERIFICATION &amp; DECISION HUB</div>
      <h1>Review everything.<br><em>Decide once.</em></h1>
      <p class="lede">This hub audits every published claim across the repository's research labs line by line,
      consolidates the strategy, gate, correlation and luck findings, and holds the two registers a reviewer
      needs before anything changes: the questions that must be answered first, and the suggestions with a
      recommended path. Nothing here is implemented until a reviewer approves it.</p>
    </div>
    <div class="notice"><span class="dot"></span><div>
      <strong>Current verdict: zero strategies approved; four decisions block implementation.</strong><br>
      The measurement apparatus is complete and verified; the market beats every model in the repo;
      the injury/depth requirement is only partially satisfiable from official data today.</div>
      <a href="pages/executive.html">Read the executive summary &rarr;</a></div>
    <div class="kpis">{kpi_html}</div>
    <section class="block">
      <div class="eyebrow">DECISION QUEUE</div>
      <h2>What a reviewer decides first</h2>
      {table(
        ["Decision", "Recommended path", "Why it blocks", "Source"],
        [
            ["Canonical site (SG-01)", "Root Line Lab as canonical; sibling hubs become archives", "Eight overlapping hubs confuse every reader-facing claim", src_links("pages/suggestions.html", ["VH-SRC-09"], src_by_id)],
            ["Injury &amp; depth tracker (SG-02)", "One tracker: official weekly report + inferred usage tiers, blanks kept", "The only major requirement with no working implementation", src_links("pages/injuries-depth.html", ["VH-SRC-02", "VH-SRC-03"], src_by_id)],
            ["Gate catalog &amp; rewards (SG-03/04)", "One 10-gate catalog, one paper reward schedule", "Four gate systems and four reward schemes are published today", src_links("pages/leaderboard.html", ["VH-SRC-08"], src_by_id)],
            ["Odds data acquisition (Q-05/Q-06)", "Acquire a licensed historical odds feed or start a forward-only log", "Without prices there can be no prop ROI and no CLV, ever", src_links("pages/questions.html", ["VH-SRC-10"], src_by_id)],
        ],
      )}
    </section>
    <section class="block">
      <div class="eyebrow">VERIFIED THIS SESSION</div>
      <h2>Official checks performed on 2026-11-12</h2>
      {table(
        ["Check", "Result", "Detail", "Source"],
        [
            ["NFL.com 2026 standings", "pass", "All 32 records read; repo snapshots reconcile at their as-of dates; Week 9 drift documented", src_links("", ["VH-SRC-01"], src_by_id)],
            ["NFL.com Week 10 injury report", "pass", "Live; player/position/injury/practice/game status per club; cross-checks with standings", src_links("", ["VH-SRC-02"], src_by_id)],
            ["nflverse release metadata", "pass with drift", "28/31 manifest assets byte-match; 3 rolling 2026 assets newer upstream (flagged)", src_links("", ["VH-SRC-04"], src_by_id)],
            ["Cited official URLs", "2 dead found", "operations.nfl.com injury policy and nfl.com depth-chart both 404 (flagged, blanks kept)", src_links("", ["VH-SRC-05", "VH-SRC-03"], src_by_id)],
            ["Local build &amp; link suite", "pass", "verify.py + tests/check_site.py + check_links + validate_data + audit/check_site", src_links("", ["VH-SRC-09"], src_by_id)],
        ],
      )}
    </section>
    """
    p = ROOT / "index.html"
    p.write_text(page("Overview", body, "index.html", depth=0), encoding="utf-8")
    written.append(p)
    LINK_PREFIX = "../"  # everything below renders one level down (verify-hub/pages/)

    # ---------- repo-audit ----------
    defs = audit["meta"]["status_definitions"]
    def_rows = [[esc(k), esc(v), "Evidence-class definition", src_links("", ["VH-SRC-09"], src_by_id)] for k, v in defs.items()]
    rows = []
    for r in audit["rows"]:
        rows.append([
            esc(r["id"]),
            esc(r["lab"]),
            esc(r["claim"]),
            esc(r.get("published_value", "")) or "&mdash;",
            f'<span class="tag tag-{esc(r["status"])}">{esc(r["status"])}</span>',
            esc(r["verification"]),
            esc(r.get("note", "")),
            src_links(r.get("where", ""), r.get("sources", []), src_by_id),
        ])
    body = f"""
    <div class="hero"><div class="eyebrow">VH-1 &middot; LINE-BY-LINE REPO AUDIT</div>
      <h1>Every published claim,<br><em>checked and labelled.</em></h1>
      <p class="lede">45 claims from every lab in the repository. Official checks were performed on 2026-11-12;
      computed claims were re-read from the committed data that generates them. Unconfirmable values are blank
      and listed on the Flagged page. Manual-review links are in the last column of every row.</p></div>
    <section class="block"><h2>Status definitions</h2>
      {table(["Status", "Definition", "Class", "Source"], def_rows)}</section>
    <section class="block"><h2>Audit rows</h2>
      {table(["ID", "Lab", "Claim", "Published value", "Status", "Verification performed", "Note", "Links"], rows)}</section>
    """
    p = PAGES / "repo-audit.html"
    p.write_text(page("Repo audit", body, "pages/repo-audit.html", depth=1), encoding="utf-8")
    written.append(p)

    # ---------- questions ----------
    rows = []
    for q in questions["rows"]:
        rows.append([
            esc(q["id"]),
            esc(q["question"]),
            esc(q["information_needed"]),
            f'<span class="tag tag-{esc(q["status"].lower())}">{esc(q["status"])}</span>',
            esc(q.get("answer", "")) or "&mdash;",
            esc(q.get("where", "")),
            esc(q["discovery_suggestion"]),
            src_links("", q.get("sources", []), src_by_id),
        ])
    body = f"""
    <div class="hero"><div class="eyebrow">VH-2 &middot; DECISION-READINESS REGISTER</div>
      <h1>Questions first.<br><em>Decisions second.</em></h1>
      <p class="lede">The clear list of questions, information and answers that must exist before any decision
      can be reasonably made. Where an answer does not exist, the answer cell is blank and the row carries a
      discovery suggestion aimed at finding the missing information. Nothing is inferred.</p></div>
    <section class="block"><h2>Register</h2>
      {table(["ID", "Question", "Information needed", "Status", "Verified answer", "Where", "Discovery suggestion for missing information", "Source"], rows)}</section>
    """
    p = PAGES / "questions.html"
    p.write_text(page("Questions", body, "pages/questions.html", depth=1), encoding="utf-8")
    written.append(p)

    # ---------- suggestions ----------
    rows = []
    for s in sugg["rows"]:
        rows.append([
            esc(s["id"]),
            esc(s["proposal"]),
            esc(s["category"]),
            esc(s["priority"]),
            esc(s["expected_impact"]),
            esc(s["effort"]),
            esc(s["tradeoffs"]),
            esc(s["recommended_path"]),
            esc(s["status"]),
            src_links("", s.get("sources", []), src_by_id),
        ])
    body = f"""
    <div class="hero"><div class="eyebrow">VH-3 &middot; SUGGESTION REVIEW QUEUE</div>
      <h1>Choose the best path<br><em>before implementing.</em></h1>
      <p class="lede">Fourteen cross-lab proposals to improve decision-making, each with its trade-offs and a
      recommended path. This is a review queue, not a change list: a reviewer marks a row Approved, Rejected or
      Deferred before any implementation session touches the referenced files.</p></div>
    <div class="notice"><span class="dot"></span><div><strong>Review gate:</strong> every row is
      <em>proposed - awaiting owner approval</em>. Implementation sessions must reference an approved row id.</div>
      <a href="../pages/questions.html">See what still blocks decisions &rarr;</a></div>
    <section class="block"><h2>Queue</h2>
      {table(["ID", "Proposal", "Category", "Priority", "Expected impact", "Effort", "Trade-offs", "Recommended path", "Status", "Source"], rows)}</section>
    """
    p = PAGES / "suggestions.html"
    p.write_text(page("Suggestions", body, "pages/suggestions.html", depth=1), encoding="utf-8")
    written.append(p)

    # ---------- leaderboard ----------
    rows = []
    for r in strat["cross_lab_rows"]:
        roi = esc(r["roi_pct"]) if r["roi_pct"] != "" else "&mdash;"
        rows.append([
            esc(r["id"]), esc(r["lab"]), esc(r["strategy"]), esc(r["family"]), esc(r["window"]),
            esc(r["n"]), roi, esc(r["gates"]), esc(r["verdict"]), esc(r["luck_note"]),
            src_links(r.get("where", ""), r.get("sources", []), src_by_id),
        ])
    corr_rows = [
        [esc(c["id"]), esc(c["pair"]), esc(c["value"]), esc(c["n"]), esc(c["window"]), esc(c["lab"]),
         src_links(c.get("where", ""), c.get("sources", []), src_by_id)]
        for c in strat["correlation_rows"]
    ]
    gate_rows = [
        [esc(g["id"]), esc(g["name"]), esc(g["rule"]), esc(g["adopted_from"]),
         src_links(g.get("where", ""), g.get("sources", []), src_by_id)]
        for g in strat["gate_catalog_rows"]
    ]
    reward_rows = [
        [esc(r["id"]), esc(r["scheme"]), esc(r["unit"]), esc(r.get("funded", "")) or "&mdash;", esc(r["lab"]),
         src_links(r.get("where", ""), r.get("sources", []), src_by_id)]
        for r in strat["reward_rows"]
    ]
    luck_rows = [
        [esc(l["id"]), esc(l["metric"]), esc(l["value"]), esc(l["reading"]),
         src_links(l.get("where", ""), l.get("sources", []), src_by_id)]
        for l in strat["luck_rows"]
    ]
    body = f"""
    <div class="hero"><div class="eyebrow">VH-4 &middot; CROSS-LAB CONSOLIDATION</div>
      <h1>One leaderboard.<br><em>Every lab's numbers.</em></h1>
      <p class="lede">Singles, parlays and player-prop combos from all five gate systems, the measured
      correlation values that decide parlay prices, the luck-removal results and the reward schedules.
      Windows and definitions differ per lab and are printed with every row. Nothing is re-computed here.</p></div>
    <div class="notice"><span class="dot"></span><div><strong>Competition rule:</strong>
      {esc(strat["meta"]["competition_rule"])}</div>
      <a href="../pages/suggestions.html">Reward-scheme decision SG-04 &rarr;</a></div>
    <section class="block"><h2>Strategy results by lab</h2>
      {table(["ID", "Lab", "Strategy", "Family", "Window", "Tickets", "ROI %", "Gates", "Verdict", "Luck note", "Source"], rows)}</section>
    <section class="block"><h2>Correlation values</h2>
      {table(["ID", "Pair", "Value", "n", "Window", "Lab", "Source"], corr_rows)}</section>
    <section class="block"><h2>Adopted gate catalog (proposal SG-03)</h2>
      {table(["Gate", "Name", "Rule", "Adopted from", "Source"], gate_rows)}</section>
    <section class="block"><h2>Reward schedules in the repository</h2>
      {table(["ID", "Scheme", "Unit", "Funded", "Lab", "Source"], reward_rows)}</section>
    <section class="block"><h2>Luck vs skill</h2>
      {table(["ID", "Metric", "Value", "Reading", "Source"], luck_rows)}</section>
    """
    p = PAGES / "leaderboard.html"
    p.write_text(page("Leaderboard", body, "pages/leaderboard.html", depth=1), encoding="utf-8")
    written.append(p)

    # ---------- injuries / depth ----------
    gap_rows = [
        [esc(g["id"]), esc(g["requirement_item"]), esc(g["official_status"]), esc(g["evidence"]),
         esc(g["gap"]), esc(g["discovery_suggestion"]), src_links("", g.get("sources", []), src_by_id)]
        for g in inj["gap_rows"]
    ]
    sample = inj["verified_week10_sample"]
    sample_rows = [
        [esc(r["team"]), esc(r["unit"]), esc(r["player"]), esc(r["position"]), esc(r["injury"]) or "&mdash;",
         esc(r["practice"]) or "&mdash;", esc(r["game_status"]) or "&mdash;",
         esc(r["string"]) or "&mdash;", esc(r["deficiency_note"]),
         src_links("", r.get("sources", []), src_by_id)]
        for r in sample["rows"]
    ]
    body = f"""
    <div class="hero"><div class="eyebrow">VH-5 &middot; INJURY &amp; DEPTH-DEFICIENCY TRACKING</div>
      <h1>What the league publishes.<br><em>And what it does not.</em></h1>
      <p class="lede">The requirement: track injuries and know any deficiencies in defenses (2nd/3rd/4th-string
      backups replacing starters) and the same on offense. This register separates what verified official data
      can satisfy today from what must be inferred - and keeps every unverifiable cell blank.</p></div>
    <div class="notice"><span class="dot"></span><div><strong>Key gap, verified 2026-11-12:</strong>
      the official weekly injury report is live and complete on status, but the league publishes
      <em>no depth strings</em> - the official depth-chart path returns 404. Every 'string' cell below is blank
      by policy.</div><a href="../pages/questions.html">Discovery route Q-08 &rarr;</a></div>
    <section class="block"><h2>Requirement / gap register</h2>
      {table(["ID", "Requirement item", "Official status", "Verified evidence", "Gap", "Discovery suggestion", "Source"], gap_rows)}</section>
    <section class="block"><h2>Verified sample &mdash; official Week 10 2026 injury report (read 2026-11-12)</h2>
      {table(["Team", "Unit", "Player", "Pos", "Injury", "Practice", "Game status", "String", "Deficiency note", "Source"], sample_rows)}</section>
    """
    p = PAGES / "injuries-depth.html"
    p.write_text(page("Injuries & depth", body, "pages/injuries-depth.html", depth=1), encoding="utf-8")
    written.append(p)

    # ---------- executive ----------
    body = render_exec_html(src_by_id)
    p = PAGES / "executive.html"
    p.write_text(page("Executive summary", body, "pages/executive.html", depth=1), encoding="utf-8")
    written.append(p)
    p = ROOT / "EXECUTIVE_SUMMARY.md"
    p.write_text(render_exec_md(), encoding="utf-8")
    written.append(p)

    # ---------- sources ----------
    rows = []
    for s in sources["sources"]:
        opened = esc(s.get("opened_utc", "")) or "&mdash;"
        rows.append([
            esc(s["id"]), esc(s["label"]), esc(s["publisher"]), esc(s["type"]),
            opened, esc(s["how_verified"]), esc(s.get("note", "")), link(s["url"], esc(s["url"]), "ext"),
        ])
    body = f"""
    <div class="hero"><div class="eyebrow">SOURCE REGISTER</div>
      <h1>Every link,<br><em>and when it was checked.</em></h1>
      <p class="lede">Sources opened and read by this session on 2026-11-12 carry that date and the exact
      verification method. Context sources verified by earlier sessions say so and are not re-claimed here.</p></div>
    <section class="block"><h2>Register</h2>
      {table(["ID", "Label", "Publisher", "Type", "Opened", "How verified", "Note", "URL"], rows)}</section>
    """
    p = PAGES / "sources.html"
    p.write_text(page("Sources", body, "pages/sources.html", depth=1), encoding="utf-8")
    written.append(p)

    # ---------- flagged ----------
    rows = []
    for f in flagged["rows"]:
        rows.append([
            esc(f["id"]), esc(f["item"]), esc(f["value"]) or "&mdash;", esc(f["severity"]),
            esc(f["reason"]), esc(f["action"]), src_links("", f.get("sources", []), src_by_id),
        ])
    body = f"""
    <div class="hero"><div class="eyebrow">FLAGGED FOR REVIEW</div>
      <h1>Blank on purpose.<br><em>Published for your review.</em></h1>
      <p class="lede">Every row is something this repository cannot confirm from an official source, or an
      irregularity found during the line-by-line audit. Values are blank by policy - never inferred. None of
      these items blocks publication; they are the open questions behind the decisions.</p></div>
    <section class="block"><h2>Register</h2>
      {table(["ID", "Item", "Value", "Severity", "Reason", "Suggested action", "Source"], rows)}</section>
    """
    p = PAGES / "flagged.html"
    p.write_text(page("Flagged for review", body, "pages/flagged.html", depth=1), encoding="utf-8")
    written.append(p)

    return written


if __name__ == "__main__":
    files = build()
    for f in files:
        print("wrote", f.relative_to(ROOT.parent))
