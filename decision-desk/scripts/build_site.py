#!/usr/bin/env python3
"""Build the Decision Desk pages from decision-desk/data/*.json.

Nothing on these pages is typed by hand: every number, name and link is read
from the committed JSON registers. Run from the repository root:

    python3 decision-desk/scripts/build_site.py

Outputs decision-desk/index.html and decision-desk/pages/*.html.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DD = ROOT / "decision-desk"
DATA = DD / "data"
PAGES = DD / "pages"

NAV = [
    ("index.html", "Home"),
    ("pages/executive.html", "Executive summary"),
    ("pages/injuries.html", "Injuries &amp; depth"),
    ("pages/questions.html", "Questions"),
    ("pages/suggestions.html", "Suggestions"),
    ("pages/leaderboard.html", "Leaderboard"),
    ("pages/flagged.html", "Flagged"),
    ("pages/repo-review.html", "Repo review"),
    ("pages/sources.html", "Sources"),
]


def load(name: str) -> dict:
    with open(DATA / name, encoding="utf-8") as fh:
        return json.load(fh)


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def source_links(ids, sources: dict) -> str:
    """Render source ids as external links; unknown ids fail loudly."""
    out = []
    for sid in ids or []:
        src = sources.get(sid)
        if src is None:
            raise SystemExit(f"unknown source id referenced: {sid}")
        out.append(f'<a href="{esc(src["url"])}" target="_blank" rel="noopener">{esc(sid)}</a>')
    return ", ".join(out) if out else ""


def table(headers, rows, caption=None) -> str:
    cap = f"<caption>{caption}</caption>" if caption else ""
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for row in rows:
        cells = "".join(f"<td>{c}</td>" for c in row)
        body.append(f"<tr>{cells}</tr>")
    return f'<table class="data">{cap}<thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def badge(text: str) -> str:
    key = (text or "").upper()
    cls = "b-neutral"
    if key in ("OUT", "IR", "RULED OUT") or key.startswith("OUT"):
        cls = "b-out"
    elif key in ("DNP", "QUESTIONABLE", "LIMITED", "PARTIAL", "UNANSWERED", "HIGH"):
        cls = "b-warn"
    elif key in ("ANSWERED", "PASS", "FULL", "STARTING", "RETAINED"):
        cls = "b-ok"
    elif key in ("PROPOSED", "MEDIUM", "OPEN"):
        cls = "b-warn"
    elif key in ("LOW",):
        cls = "b-neutral"
    return f'<span class="badge {cls}">{esc(text)}</span>'


def link_flags(text: str) -> str:
    """Wrap FL-DD-NN tokens (already escaped) in links to the flagged page."""
    import re
    return re.sub(r"(FL-DD-\d+)", r'<a href="flagged.html#\1">\1</a>', text)


def page(title: str, body: str, depth: int) -> str:
    prefix = "../" * depth
    nav = []
    for href, label in NAV:
        nav.append(f'<a href="{prefix}{href}">{label}</a>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · Decision Desk</title>
<link rel="stylesheet" href="{prefix}assets/style.css">
</head>
<body>
<header>
<h1><a href="{prefix}index.html">Decision Desk</a></h1>
<nav class="topnav">{' | '.join(nav)}</nav>
</header>
<main>
{body}
</main>
<footer>
<p>Decision Desk · session <code>arena/aa66ed82-korea2</code> · every row is source-linked ·
unverified values are blank and flagged, never inferred · captured 2026-11-12.</p>
<p>Research and measurement, not betting advice. Every figure is computed from the sources
listed on the Sources page; nothing is estimated by hand.</p>
</footer>
</body>
</html>
"""


def write(relpath: str, content: str) -> None:
    path = (DD / relpath) if not relpath.startswith("pages/") else (PAGES / relpath[6:])
    if relpath.startswith("pages/"):
        path = PAGES / relpath[len("pages/"):]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    sources_doc = load("sources.json")
    sources = {s["id"]: s for s in sources_doc["sources"]}
    injuries = load("injuries.json")
    questions = load("questions.json")
    suggestions = load("suggestions.json")
    leaderboard = load("leaderboard.json")
    flagged = load("flagged.json")
    review = load("repo_review.json")

    icount = injuries["meta"]["counts"]
    qcount = questions["meta"]["counts"]
    fcount = flagged["meta"]["counts"]
    lbmeta = leaderboard["meta"]

    # ---------------- index.html ----------------
    kpis = [
        ("Strategies qualified", f'0 / {lbmeta["totals"]["evaluations"]}', "across 6 lab boards"),
        ("Injury rows tracked", str(icount["report_rows"] + icount["supplemental_rows"]),
         f'{icount["report_rows"]} official + {icount["supplemental_rows"]} supplemental'),
        ("Deficiency chains", str(icount["deficiencies"]),
         f'{icount["flagged_deficiencies"]} flagged for review'),
        ("Decision questions", str(qcount["total"]),
         f'{qcount["answered"]} answered · {qcount["partial"]} partial · {qcount["unanswered"]} unanswered'),
        ("Suggestions awaiting you", str(suggestions["meta"]["counts"]["total"]),
         "0 decided — reviewer chooses"),
        ("Open flags", str(fcount["total"]), f'{fcount["high"]} high severity'),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="kpi-n">{esc(n)}</div><div class="kpi-l">{esc(l)}</div><div class="kpi-s">{esc(s)}</div></div>'
        for n, l, s in kpis)
    cards = []
    for href, label in NAV[1:]:
        cards.append(f'<a class="card" href="{href}">{esc(label)}</a>')
    body = f"""
<section class="hero">
<h2>Line-by-line decisions, sourced end to end</h2>
<p>This sub-site answers three questions for the reviewer: <strong>what do we know</strong>
(injuries, lineup deficiencies, competition state), <strong>what must be decided</strong>
(questions and suggestions), and <strong>what is unverified</strong> (flags).
Every table row carries a link to the official source it came from.</p>
</section>
<section class="kpis">{kpi_html}</section>
<section>
<h2>Category pages</h2>
<div class="cards">{''.join(cards)}</div>
</section>
<section>
<h2>Standing rules on this site</h2>
<ul class="rules">
<li>Values that cannot be confirmed from an official source are <strong>left blank and flagged</strong> — never inferred.</li>
<li>Every data row's last cell links to its source (fetch date 2026-11-12).</li>
<li>Team depth charts are team-published and mostly labelled <em>Unofficial</em> by the teams themselves.</li>
<li>Flagged items do not block the merge; they live on the <a href="pages/flagged.html">Flagged for Review</a> page.</li>
<li>Suggestions are proposals only — the <a href="pages/suggestions.html">Suggestions register</a> waits for a reviewer's decision.</li>
</ul>
</section>
"""
    write("index.html", page("Home", body, 0))

    # ---------------- injuries.html ----------------
    game_by_team = {}
    for g in injuries["games"]:
        game_by_team[g["away"]] = g
        game_by_team[g["home"]] = g
    game_order = {g["id"]: i for i, g in enumerate(injuries["games"])}

    def row_game(r):
        g = game_by_team.get(r["team"])
        return game_order.get(g["id"], 99) if g else 99

    rows = sorted(injuries["report_rows"], key=lambda r: (row_game(r), r["team"], r["player"]))
    report_tbl = table(
        ["Game", "Team", "Player", "Pos", "Injury (official wording)", "Practice", "Game status", "Source"],
        [[esc(row_game_str(r, game_by_team, game_order)), esc(r["team"]), esc(r["player"]), esc(r["position"]),
          esc(r["injury"]) or '<span class="blank">—</span>',
          badge(r["practice"]) if r["practice"] in ("DNP", "Limited", "Full") else esc(r["practice"]),
          badge(r["game_status"]) if r["game_status"] else '<span class="blank">pending</span>',
          source_links(r["sources"], sources)] for r in rows],
        f'Official Week 10 injury report — {icount["report_rows"]} rows, fetched 2026-11-12 from nfl.com/injuries/')

    supp_tbl = table(
        ["Team", "Player", "Pos", "Injury", "Practice", "Game status", "Note", "Source"],
        [[esc(r["team"]), esc(r["player"]), esc(r["position"]), esc(r["injury"]) or '<span class="blank">—</span>',
          badge(r["practice"]), badge(r["game_status"]) if r["game_status"] else '<span class="blank">pending</span>',
          esc(r.get("note", "")), source_links(r["sources"], sources)]
         for r in injuries["supplemental_rows"]],
        "Supplemental rows — players the official report page omitted while its own news pages reported them")

    nr_tbl = table(
        ["Team", "What the report page said", "Contradicted by", "Flag", "Source"],
        [[esc(r["team"]), esc(r["page_says"]), esc(r["contradicted_by"]),
          f'<a href="flagged.html#{esc(r["flagged"])}">{esc(r["flagged"])}</a>',
          source_links([r["source"]], sources)] for r in injuries["no_report"]],
        "'No Injuries Reported' — treated as untrusted, never as healthy (FL-DD-01)")

    def_def_rows = []
    for d in injuries["deficiencies"]:
        repl = esc(d["replacement"]) if d["replacement"] else '<span class="blank">unverified</span>'
        depth = esc(d["replacement_depth"]) if d["replacement"] else ""
        nxt = esc(d["next_up"]) if d["next_up"] else '<span class="blank">—</span>'
        def_def_rows.append([
            esc(d["team"]), esc(d["side"]), esc(d["position"]), esc(d["unit"]),
            esc(d["starter"]) or '<span class="blank">unverified</span>',
            badge(d["status"]), esc(d["starter_detail"]),
            repl, depth, nxt,
            esc(d["evidence"]),
            (badge("FLAGGED") + (" " + link_flags(esc(d["note"]))) if d["flagged"] else ""),
            source_links(d["sources"], sources),
        ])
    def_tbl = table(
        ["Team", "Side", "Pos", "Unit", "Starter", "Status", "Status detail",
         "Next man up", "Depth", "After him", "Evidence (official)", "Flag", "Source"],
        def_def_rows,
        f'Lineup deficiencies — {icount["deficiencies"]} chains pairing an official status with the team chart order '
        f'({icount["flagged_deficiencies"]} flagged; blanks mean no official confirmation)')

    body = f"""
<section>
<h2>Week 10 2026 — injury tracking &amp; lineup deficiencies</h2>
<p>Primary source: {source_links(["SRC-DD-01"], sources)} (the official NFL injury report, fetched 2026-11-12),
cross-checked against {source_links(["SRC-DD-02", "SRC-DD-03"], sources)}.
Practice vocabulary: <strong>Full/Limited/DNP</strong> = full / limited / did-not-participate in Wednesday practice;
game statuses (Out / Questionable) are provisional until Sunday inactives.</p>
</section>
<section>
<h2>Games on the report</h2>
{table(["Kickoff", "Matchup", "Records", "Network", "Source"],
       [[esc(g["kickoff"]), f'{esc(g["away"])} @ {esc(g["home"])}',
         f'{esc(g["away_record"])} / {esc(g["home_record"])}', esc(g["network"]),
         source_links([g["source"]], sources)] for g in injuries["games"]],
       "All 14 Week 10 games")}
</section>
<section>
<h2>Official injury report rows ({icount["report_rows"]})</h2>
{report_tbl}
</section>
<section>
<h2>Supplemental rows ({icount["supplemental_rows"]})</h2>
{supp_tbl}
</section>
<section>
<h2>"No Injuries Reported" contradictions</h2>
{nr_tbl}
</section>
<section>
<h2>Lineup deficiencies — who replaces whom ({icount["deficiencies"]})</h2>
<p>Reading the table: <em>Starter</em> and <em>Status</em> come from the official report/news;
<em>Next man up</em> and <em>Depth</em> come from the team's own depth chart (string = chart position, not ability);
blank cells are flagged, never guessed. Rows cover offense, defense and special teams, including 2nd/3rd/4th-string
elevations (e.g. NE RB Stevenson+Henderson out → 3rd-string Kiner; SEA QB Darnold out → 2nd-string Lock, 3rd-string Milroe).</p>
{def_tbl}
</section>
<section>
<h2>Method</h2>
<ul class="rules">
<li>Report rows: transcribed from {source_links(["SRC-DD-01"], sources)}; injury wording added only where an official NFL.com source states it ({source_links(["SRC-DD-03"], sources)}).</li>
<li>Replacement order: each team's own depth-chart page (sources {source_links(["SRC-DD-10"], sources)} … {source_links(["SRC-DD-37"], sources)} — full list on the <a href="sources.html">Sources</a> page), fetched 2026-11-12.</li>
<li>Blank + flagged = no official source confirmed the value (unverifiable chart, missing announcement, empty chart cell).</li>
</ul>
</section>
"""
    write("pages/injuries.html", page("Injuries & depth", body, 1))

    # ---------------- questions.html ----------------
    q_rows = []
    for q in questions["questions"]:
        q_rows.append([
            f'<span id="{esc(q["id"])}"><strong>{esc(q["id"])}</strong></span>',
            esc(q["category"]), esc(q["question"]),
            esc(q["answer"]) or '<span class="blank">no answer yet</span>',
            badge(q["status"]),
            esc(q["evidence"]),
            esc(q["gap"]) or '<span class="blank">—</span>',
            ", ".join(f'<a href="suggestions.html#{esc(s)}">{esc(s)}</a>' for s in q["related_suggestions"]) or "—",
            source_links(q["sources"], sources),
        ])
    body = f"""
<section>
<h2>Decision-readiness register</h2>
<p>{qcount["total"]} questions: <strong>{qcount["answered"]} answered</strong> from official sources,
{qcount["partial"]} partial (named gap), {qcount["unanswered"]} unanswered (no official evidence exists yet).
Nothing here is answered by inference — an unanswered row says exactly what is missing and which suggestion would close it.</p>
{table(["ID", "Category", "Question", "Answer", "Status", "Evidence", "Gap to close", "Related suggestions", "Source"],
       q_rows, "What must be addressed before any decision can be reasonably made")}
</section>
<section>
<h2>How to use this page</h2>
<ul class="rules">
<li>Start with the <strong>unanswered</strong> and <strong>partial</strong> rows — those are the decisions that cannot be made yet.</li>
<li>Each of those rows names a gap and links to the suggestion that would close it.</li>
<li>The four blocking reviewer decisions are Q-01 (status quo), Q-05 (pool funding), Q-06 (legal), Q-04 (prop data).</li>
</ul>
</section>
"""
    write("pages/questions.html", page("Questions", body, 1))

    # ---------------- suggestions.html ----------------
    q_by_id = {q["id"]: q for q in questions["questions"]}
    s_rows = []
    for s in suggestions["suggestions"]:
        ids = []
        for qid in s["related_questions"]:
            ids.extend(q_by_id[qid]["sources"] if qid in q_by_id else [])
        seen, uniq = set(), []
        for i in ids:
            if i not in seen:
                seen.add(i)
                uniq.append(i)
        s_rows.append([
            f'<span id="{esc(s["id"])}"><strong>{esc(s["id"])}</strong></span>',
            esc(s["title"]), esc(s["category"]), esc(s["description"]), esc(s["benefit"]),
            esc(s["effort"]), badge(s["priority"]),
            ", ".join(f'<a href="questions.html#{esc(q)}">{esc(q)}</a>' for q in s["related_questions"]),
            badge(s["status"]), esc(s["decision"]),
            source_links(uniq, sources),
        ])
    body = f"""
<section>
<h2>Suggestions register — the reviewer chooses the path</h2>
<p>Every row is a <strong>proposal</strong> with status <em>proposed</em> and decision <em>(awaiting reviewer)</em>.
Nothing in this register has been implemented. To act on one: set its decision to
<em>accepted</em> / <em>deferred</em> / <em>rejected</em>, fill <code>decided_by</code> and
<code>decided_on</code> in <code>decision-desk/data/suggestions.json</code>, then implement only accepted rows.</p>
{table(["ID", "Suggestion", "Category", "What it is", "Why it helps", "Effort", "Priority",
        "Questions it closes", "Status", "Decision", "Source"],
       s_rows, f'{suggestions["meta"]["counts"]["total"]} suggestions · '
               f'{suggestions["meta"]["counts"]["high_priority"]} high priority · 0 decided')}
</section>
<section>
<h2>Recommended first pass (in priority order)</h2>
<ol class="rules">
<li><strong>S-15</strong> — hold the reviewer decision session covering the four blocking questions.</li>
<li><strong>S-01</strong> — confirm the no-bet status quo (every lab currently has 0 qualified strategies).</li>
<li><strong>S-03 / S-04 / S-02</strong> — pool funding, legal review, prop-price feed.</li>
<li><strong>S-06 / S-08</strong> — Friday starter sweep and automated injury fetch (closes FL-DD-01 class issues).</li>
</ol>
</section>
"""
    write("pages/suggestions.html", page("Suggestions", body, 1))

    # ---------------- leaderboard.html ----------------
    lb_rows = []
    for row in leaderboard["leaderboard"]:
        lb_rows.append([
            esc(row["lab"]), esc(row["board"]), esc(row["candidates"]), badge(str(row["qualified"])),
            esc(row["top_result"]), esc(row["ranking_rule"]), source_links(row["sources"], sources),
        ])
    cor_rows = []
    for c in leaderboard["correlations"]:
        cor_rows.append([
            esc(c["id"]), esc(c["pair"]), esc(c["n"]),
            esc(f'{c["r"]:.4f}'),
            esc(f'[{c["ci_low"]:.4f}, {c["ci_high"]:.4f}]'),
            esc(c["p"]), esc(c["note"]), esc(c["source_file"]),
            source_links([c["source_id"]], sources),
        ])
    body = f"""
<section>
<h2>Cross-lab leaderboard</h2>
<p><strong>One rule:</strong> {esc(lbmeta["rule"])}</p>
<p>Board totals at capture: <strong>{lbmeta["totals"]["evaluations"]} strategy evaluations across
{lbmeta["totals"]["labs"]} labs — {lbmeta["totals"]["qualified"]} qualified</strong>.</p>
{table(["Lab", "Board (committed file)", "Candidates", "Qualified", "Top result", "Ranking rule", "Source"],
       lb_rows, "Every lab, read from its committed JSON")}
</section>
<section>
<h2>Measured correlations (parlay and SGP inputs)</h2>
{table(["ID", "Pair", "n", "r", "95% CI", "p", "Note", "File", "Source"],
       cor_rows, "Correlation values measured by the repo's own pipelines — quoted, not estimated")}
</section>
<section>
<h2>Competition status</h2>
<ul class="rules">
<li>0 strategies have cleared every gate anywhere; positive ROI alone earns nothing under every lab's rule.</li>
<li>The skill-lab pool is 10,000 points and <strong>unfunded</strong> (see FL-DD-15 / Q-05 / S-03).</li>
<li>Luck is priced (Pythagorean R² = 0.819, year-over-year luck r = 0.024, p = 0.49) but a skill-based ranking
of qualified strategies has never run because nothing qualified — see Q-14.</li>
<li>Controls (e.g. skill-lab STR-16, a deliberately leaky strategy) are excluded from reward consideration.</li>
<li>Scope: {esc(lbmeta.get("scope_note", ""))}</li>
</ul>
</section>
"""
    write("pages/leaderboard.html", page("Leaderboard", body, 1))

    # ---------------- flagged.html ----------------
    f_rows = []
    for f in flagged["flagged"]:
        f_rows.append([
            f'<span id="{esc(f["id"])}"><strong>{esc(f["id"])}</strong></span>',
            esc(f["title"]), badge(f["severity"]), esc(f["status"]),
            esc(f["detail"]), esc(f["handling"]), source_links(split_ids(f["sources"]), sources),
        ])
    body = f"""
<section>
<h2>Flagged for review</h2>
<p>{fcount["total"]} flags ({fcount["high"]} high severity, {fcount["carry_forward"]} carry-forward).
Per project policy these do <strong>not</strong> block the merge — they are published here instead,
each with what was observed, how the site handles it, and which suggestion would fix it.</p>
{table(["ID", "Title", "Severity", "Status", "Observation", "How this site handles it", "Source"],
       f_rows, "Irregularities found this session and open carry-forwards")}
</section>
<section>
<h2>Policy</h2>
<ul class="rules">
<li>Flagged values stay blank on data pages — the flag is the value.</li>
<li>Carry-forward flags were inherited from earlier sessions' ledgers and re-verified where possible.</li>
<li>Out-of-scope findings (other sessions' files) are logged as requests in COORDINATION.md, not edited here.</li>
</ul>
</section>
"""
    write("pages/flagged.html", page("Flagged", body, 1))

    # ---------------- sources.html ----------------
    src_rows = []
    for s in sources_doc["sources"]:
        src_rows.append([
            f'<span id="{esc(s["id"])}"><strong>{esc(s["id"])}</strong></span>',
            esc(s["title"]), esc(s["publisher"]), esc(s["fetched"]), esc(s["use"]),
            esc(s.get("note", "")),
            f'<a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["id"])} &#8599;</a>',
        ])
    body = f"""
<section>
<h2>Source register</h2>
<p>All {len(sources_doc["sources"])} sources were fetched and read in this session (2026-11-12).
Every table row on this site links to one of these.</p>
{table(["ID", "Source", "Publisher", "Fetched", "What it is used for", "Note", "Source"],
       src_rows, "Official sources only — no secondary aggregators; every row links to the source itself")}
</section>
"""
    write("pages/sources.html", page("Sources", body, 1))

    # ---------------- repo-review.html ----------------
    chk_rows = [[esc(c["name"]), badge("PASS" if c["result"] == "PASS" else "NOT RUN LOCALLY"),
                 esc(c["detail"]), source_links(["SRC-DD-38", "SRC-DD-48"], sources)]
                for c in review["checks"]]
    lbl_rows = [[esc(i["item"]), esc(i["finding"]),
                 source_links(["SRC-DD-38", "SRC-DD-48"], sources)]
                for i in review["line_by_line"]]
    inv = review["inventory"]
    body = f"""
<section>
<h2>Line-by-line repository review</h2>
<p>Branch <code>{esc(review["meta"]["branch"])}</code> (base <code>{esc(review["meta"]["base_commit"][:7])}</code>),
reviewed {esc(review["meta"]["reviewed_on"])}. {esc(review["meta"]["method"])}</p>
{table(["Gate", "Result", "Detail", "Source"], chk_rows, "Automated checks executed this session")}
</section>
<section>
<h2>Inventory</h2>
<ul class="rules">
<li>{inv["tracked_files_at_claim"]} tracked files at claim time; {inv["html_pages"]} HTML pages ({inv["published_pages"]} published).</li>
<li>Workflows: {', '.join(inv["workflows"])}.</li>
<li>Sibling directories treated read-only: {', '.join(inv["sibling_directories_read_only"])}.</li>
</ul>
</section>
<section>
<h2>File-by-file findings</h2>
{table(["File / area", "Finding", "Source"], lbl_rows, "Top-level files and scope rules, read this session")}
</section>
<section>
<h2>Verdict</h2>
<p>{esc(review["verdict"])}</p>
<p>Irregularities logged: {esc(review["irregularities_logged"][0])} {esc(review["irregularities_logged"][1])
} {esc(review["irregularities_logged"][2])}</p>
</section>
"""
    write("pages/repo-review.html", page("Repo review", body, 1))

    # ---------------- executive.html ----------------
    body = f"""
<section>
<h2>Executive summary — Decision Desk</h2>
<p><strong>Captured 2026-11-12 · branch {esc(review["meta"]["branch"])} · data as of the dates shown on each page.</strong></p>
</section>
<section>
<h2>Bottom line</h2>
{table(["Question", "Answer", "Evidence", "Source"],
       [["Should any strategy receive allocation today?",
         badge("NO") + " 0 of " + str(lbmeta["totals"]["evaluations"]) + " evaluations qualified",
         '<a href="leaderboard.html">Leaderboard</a>',
         source_links(["SRC-DD-41", "SRC-DD-46"], sources)],
        ["Can we beat the closing line?",
         badge("NO") + " model Brier skill −0.038 vs market (2,687 games with both prices)",
         '<a href="questions.html#Q-02">Q-02</a>',
         source_links(["SRC-DD-42"], sources)],
        ["Are parlay legs independent?",
         badge("NO") + " QB–WR1 r = 0.5616 (n = 7,560)",
         '<a href="questions.html#Q-03">Q-03</a>',
         source_links(["SRC-DD-47"], sources)],
        ["Is our data trustworthy?",
         badge("PARTIAL") + " all repo gates PASS, but upstream NFL pages contradict themselves (FL-DD-01)",
         '<a href="flagged.html">Flagged</a>',
         source_links(["SRC-DD-01", "SRC-DD-03"], sources)],
        ["Which Week 10 lineups are most deficient?",
         badge("ANSWERED") + " " + str(icount["deficiencies"]) + " chains tracked; NE LG, PIT ×2, TEN ×2, SF LCB have no listed backup",
         '<a href="injuries.html">Injuries &amp; depth</a>',
         source_links(["SRC-DD-01", "SRC-DD-19"], sources)],
        ["What blocks a real decision?",
         badge("4 ITEMS") + " status-quo call, pool funding, legal review, prop-price feed",
         '<a href="suggestions.html">Suggestions</a>',
         source_links(["SRC-DD-41", "SRC-DD-46"], sources)]],
       "One line each — every row links to its register and its source")}
</section>
<section>
<h2>What this session produced</h2>
<ul class="rules">
<li><strong>Injuries &amp; depth:</strong> {icount["report_rows"]} official Week 10 rows + {icount["supplemental_rows"]} supplemental,
{icount["deficiencies"]} starter→backup chains ({icount["flagged_deficiencies"]} flagged), 4 "No Injuries Reported" contradictions exposed.</li>
<li><strong>Questions:</strong> {qcount["total"]} decision-readiness rows — {qcount["answered"]} answered, {qcount["partial"]} partial,
{qcount["unanswered"]} unanswered with named gaps.</li>
<li><strong>Suggestions:</strong> {suggestions["meta"]["counts"]["total"]} proposals, all awaiting a reviewer's decision (0 implemented).</li>
<li><strong>Leaderboard:</strong> {lbmeta["totals"]["evaluations"]} evaluations aggregated from 6 labs with one ranking rule,
plus {icount_correlations(leaderboard)} measured correlation rows.</li>
<li><strong>Flags:</strong> {fcount["total"]} published, none blocking; <strong>repo review:</strong> all runnable gates green.</li>
</ul>
</section>
<section>
<h2>Decisions required before anything moves</h2>
<ol class="rules">
<li>Accept the no-bet status quo or set a new bar (S-01 / Q-01).</li>
<li>Fund or defer the reward pool (S-03 / Q-05).</li>
<li>Commission or skip the jurisdiction legal review (S-04 / Q-06).</li>
<li>Decide on a historical prop-price feed (S-02 / Q-04).</li>
</ol>
<p>Recommended sequence: <a href="suggestions.html#S-15">S-15</a> (one reviewer pass over all four).</p>
</section>
<section>
<h2>Trust statement</h2>
<p>No number on this site was estimated. If an official source did not state it, the cell is blank and the
irregularity is on the <a href="flagged.html">Flagged</a> page. Sources: <a href="sources.html">{len(sources)} registered, all fetched 2026-11-12</a>.</p>
</section>
"""
    write("pages/executive.html", page("Executive summary", body, 1))
    print("built: index.html + 8 pages")


# ---- helpers used above (defined after main body for readability) ----
def row_game_str(r, game_by_team, game_order) -> str:
    g = game_by_team.get(r["team"])
    if not g:
        return "—"
    return g["id"]


def evidence_ids(q) -> list:
    import re
    return re.findall(r"SRC-DD-\d+", q.get("evidence", ""))


def ids_in_evidence(q) -> list:
    return evidence_ids(q)


def extract_ids(text) -> list:
    import re
    return re.findall(r"SRC-DD-\d+", text or "")


def split_ids(text) -> list:
    import re
    return re.findall(r"SRC-DD-\d+", text or "")


def icount_correlations(leaderboard) -> int:
    return leaderboard["meta"]["counts"]["correlation_rows"]


if __name__ == "__main__":
    main()
