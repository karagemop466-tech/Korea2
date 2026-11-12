#!/usr/bin/env python3
"""Build the NFL Insights static site from committed JSON data.

Every rendered table row carries an official source link (chip). Any value that
cannot be confirmed from an official source is left blank and flagged — never
inferred. Run from the repository root:

    python3 nfl-insights/scripts/build_site.py
"""
import json
import html
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repo root (nfl-insights/ -> repo root)
DATA = ROOT / "nfl-insights" / "data"
OUT  = ROOT / "nfl-insights"
PAGES = OUT / "pages"
ASSETS = OUT / "assets"


def load(name):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


def esc(s):
    return html.escape(str(s) if s is not None else "")


def source_chips(sources, source_map):
    """Render official source link chips. Unknown ids (internal cross-refs) render as plain text."""
    if not sources:
        return '<span class="badge warn">BLANK — no official source</span>'
    official = []
    internal = []
    for sid in sources:
        src = source_map.get(sid)
        if src and src.get("url"):
            official.append(src)
        else:
            internal.append(sid)
    parts = []
    for src in official:
        parts.append(
            '<a class="chip" href="{url}" target="_blank" rel="noopener noreferrer" '
            'title="{org} — {label} (verified {date})">{id} ↗</a>'.format(
                url=esc(src["url"]), org=esc(src["org"]), label=esc(src["label"]),
                date=esc(src.get("verified_on", "")), id=esc(src["id"])))
    for sid in internal:
        parts.append('<span class="internal-ref">{}</span>'.format(esc(sid)))
    if not parts:
        return '<span class="badge warn">BLANK — no official source</span>'
    return '<span class="chips">{}</span>'.format("".join(parts))


def has_official(sources, source_map):
    return bool([s for s in sources if source_map.get(s, {}).get("url")])


def verified_badge(status, has_official_src):
    if status == "project-disclosure":
        return '<span class="badge blue">PROJECT DISCLOSURE</span>'
    if status == "sibling-session published result" and not has_official_src:
        return '<span class="badge blue">SIBLING-SESSION RESULT (internal ref)</span>'
    if has_official_src:
        return '<span class="badge ok">SOURCE-VERIFIED</span>'
    return '<span class="badge warn">NO OFFICIAL SOURCE</span>'


def nav_bar(active=""):
    links = [
        ("index.html", "Dashboard"),
        ("pages/injuries.html", "Injury Tracking"),
        ("pages/suggestions.html", "Suggestions"),
        ("pages/questions.html", "Questions & Answers"),
        ("pages/executive.html", "Executive Summary"),
        ("pages/strategies.html", "Strategies"),
        ("pages/sources.html", "Sources"),
        ("pages/flagged.html", "⚑ Flagged for Review"),
    ]
    here = os.path.basename(Path(active).resolve()) if active else ""
    items = []
    for href, label in links:
        active_class = " active" if (href == here or (href == "index.html" and here == "index.html")) else ""
        items.append('<a class="nav-item{}" href="{}">{}</a>'.format(active_class, href, esc(label)))
    return (
        '<div class="topbar">'
        '<a class="brand" href="index.html">🏈 Korea2 · NFL Insights<small>decision support · verified 2026-11-12</small></a>'
        '<div class="nav">{}</div>'
        '</div>'
    ).format("".join(items))


def footer():
    return (
        '<div class="footer">'
        'Research and measurement only — not betting advice. No strategy is approved for capital; no prize pool is funded; '
        'no sportbook access, price or limit has been verified. Sports wagering is legal only in some jurisdictions and only '
        'for adults — confirm legality before wagering. '
        '<a href="https://github.com/karagemop466-tech/Korea2">Source: github.com/karagemop466-tech/Korea2</a> · '
        '<a href="pages/flagged.html">Flagged for review</a>. '
        'Every data row links to an official source or is blank and flagged; nothing is inferred.'
        "</div>"
    )


def page_shell(title, body, active=""):
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="description" content="NFL Insights — {}">\n'.format(esc(title)) +
        '<title>{} | NFL Insights</title>\n'.format(esc(title)) +
        '<link rel="stylesheet" href="../assets/style.css">\n'
        '</head>\n<body>\n' +
        nav_bar(active) +
        '<div class="wrap">\n' +
        '<div class="page-head"><h1>{}</h1></div>\n'.format(esc(title)) +
        body +
        footer() +
        '</div>\n</body>\n</html>\n'
    )


def chip_block(text, status=None):
    """A value cell: show value, or blank + flagged."""
    if text is None or text == "":
        return '<span class="empty-val">— (blank: unverified, flagged)</span>'
    return esc(text)


# ---------------------------------------------------------------------------
# Landing / dashboard
# ---------------------------------------------------------------------------
def build_index(sources, suggestions, questions, injuries, flagged, executive, strategies):
    source_map = {s["id"]: s for s in sources["sources"]}
    n_sources = len(sources["sources"])
    n_sugg = len(suggestions["suggestions"])
    n_questions = len(questions["questions"])
    n_injury_teams = len([t for t in injuries["teams"] if t["players"]])
    n_flagged = len(flagged["items"])
    n_strategies = len(strategies["strategies"])

    cards = [
        [str(n_sources), "official sources", "pages/sources.html"],
        [str(n_sugg), "improvement suggestions", "pages/suggestions.html"],
        [str(n_questions), "pre-decision questions", "pages/questions.html"],
        [str(n_injury_teams), "teams with injury data", "pages/injuries.html"],
        [str(n_strategies), "strategies reviewed", "pages/strategies.html"],
        [str(n_flagged), "flagged / unverified items", "pages/flagged.html"],
    ]
    cards_html = "".join(
        '<a class="card cardlink" href="{}"><div class="num">{}</div><div class="lbl">{}</div></a>'.format(
            esc(c[2]), esc(c[0]), esc(c[1])) for c in cards)

    facts = []
    for sec in executive["sections"]:
        facts.append(sec)

    body = (
        '<div class="notice blue"><strong>How to read this site:</strong> every table row ends with '
        '<em>official source link(s)</em> (chips). Rows marked <span class="badge warn">BLANK</span> '
        'could not be confirmed from any official source, so the value is deliberately left blank and listed on the '
        '<a href="pages/flagged.html">⚑ Flagged for Review</a> page. Nothing is inferred.</div>\n'
    )
    body += '<div class="cards">{}</div>\n'.format(cards_html)

    body += (
        '<div class="grid2"><section class="panel">'
        '<h2>League snapshot (verified facts)</h2>'
        '<p class="sub">Official NFL sources — dynamic values carry an as-of date.</p>'
    )
    body += '<table class="data"><thead><tr><th>#</th><th>Fact</th><th>Source</th><th>Status</th></tr></thead><tbody>'
    for i, sec in enumerate(facts, 1):
        sec_sources = sec.get("sources", [])
        body += "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            i, esc(sec["body"]),
            source_chips(sec_sources, source_map),
            verified_badge(sec.get("status", ""), has_official(sec_sources, source_map)))
    body += "</tbody></table></section>"

    body += (
        '<section class="panel">'
        '<h2>⚑ Flagged for review (summary)</h2>'
        '<p class="sub">Values that could not be confirmed from an official source are blank, not inferred.</p>'
    )
    body += '<table class="data"><thead><tr><th>ID</th><th>Flagged item</th><th>Reason</th><th>Source</th></tr></thead><tbody>'
    for item in flagged["items"]:
        body += "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            esc(item["id"]), esc(item["item"]), esc(item["reason"]),
            source_chips(item.get("sources", []), source_map))
    body += (
        "</tbody></table>"
        '<p style="margin:10px 0 0"><a href="pages/flagged.html">Open the full Flagged for Review page →</a></p>'
        "</section></div>\n"
    )

    body += (
        '<section class="panel"><h2>Project map</h2>'
        '<p class="sub">Subpages organized by category. All entries are sourced or flagged.</p>'
        '<div class="map-grid">'
        '<div class="map-card"><a href="pages/injuries.html">Injury Tracking</a>'
        '<p>Official NFL injury report snapshot (Week 10, 2026) with practice/game status. Backup depth flagged — not published by NFL.</p></div>'
        '<div class="map-card"><a href="pages/suggestions.html">Suggestions for Improvement</a>'
        '<p>Reviewable change proposals. Someone chooses the best path before anything is implemented.</p></div>'
        '<div class="map-card"><a href="pages/questions.html">Questions &amp; Answers</a>'
        '<p>Pre-decision register: what we know, what is blank, and what must be resolved before any decision.</p></div>'
        '<div class="map-card"><a href="pages/executive.html">Executive Summary</a>'
        '<p>The important decision-relevant details in one page.</p></div>'
        '<div class="map-card"><a href="pages/strategies.html">Strategies</a>'
        '<p>Line-origination strategies (single, parlay, prop combos), gates, correlations, leaderboard design.</p></div>'
        '<div class="map-card"><a href="pages/sources.html">Data &amp; Sources</a>'
        '<p>Full register of official sources used on this site.</p></div>'
        '<div class="map-card"><a href="pages/flagged.html">⚑ Flagged for Review</a>'
        '<p>Unverified items, with reasons and source links.</p></div>'
        '</div></section>\n'
    )
    return page_shell("Dashboard", body, active="index.html")


# ---------------------------------------------------------------------------
# Injuries
# ---------------------------------------------------------------------------
def build_injuries(injuries, sources):
    source_map = {s["id"]: s for s in sources["sources"]}
    rows = []
    for t in injuries["teams"]:
        if not t["players"]:
            rows.append({
                "team": t["team"], "abbr": t["abbr"], "record": t["record"],
                "player": "— (no injuries reported in reviewed portion)",
                "position": "", "injury": "", "practice": "", "game": "",
                "note": "See live official report",
            })
            continue
        for p in t["players"]:
            rows.append({
                "team": t["team"], "abbr": t["abbr"], "record": t["record"],
                "player": p["name"], "position": p["position"], "injury": p["injury"],
                "practice": p["practice_status"], "game": p["game_status"],
                "note": "",
            })

    body = (
        '<div class="notice"><strong>Source:</strong> official NFL Injury Report, Week 10, 2026 '
        '(nfl.com/injuries/league/2026/reg10), read 2026-11-12. '
        '<strong>Practice status:</strong> DNP = Did Not Participate, Limited = Limited Participation, Full = Full Participation. '
        '<strong>Game status:</strong> Questionable = uncertain, Doubtful = unlikely to play, Out = will not play. '
        'Dynamic — values change weekly; this snapshot is as-of stamped, never permanent truth. '
        '<a href="https://www.nfl.com/injuries/">Open live official injury report ↗</a></div>\n'
    )
    body += (
        '<div class="notice blue"><strong>Backup depth (2nd / 3rd / 4th string):</strong> '
        'The NFL does NOT publish depth-chart ordering on its official roster pages, so which backup replaces an injured '
        'starter on defense or offense <em>cannot</em> be confirmed from an official source. Depth cells are blank and '
        'flagged — never inferred. See <a href="pages/flagged.html">FL-01</a>.</div>\n'
    )
    if injuries["teams_not_itemized"]:
        body += (
            '<div class="notice"><strong>Not itemized in this snapshot:</strong> '
            + ", ".join(injuries["teams_not_itemized"]) +
            ' appear in the live official report but were not captured in the reviewed portion. See live link above.</div>\n'
        )

    body += (
        '<table class="data"><caption>Injury report snapshot — Week 10, 2026 (as-of 2026-11-12). '
        'Every row links to the official NFL injury report.</caption>'
        '<thead><tr><th>Team</th><th>Record</th><th>Player</th><th>Pos.</th><th>Injury</th>'
        '<th>Practice status</th><th>Game status</th><th>Official source</th></tr></thead>'
        '<tbody>'
    )
    for r in rows:
        game_class = "status-out" if r["game"] == "Out" else ("status-q" if r["game"] == "Questionable" else "")
        body += "<tr><td><strong>{abbr}</strong><br><span class=\"pos-col\">{team}</span><br><span class=\"pos-col\">({record})</span></td>" \
                "<td>{record}</td>" \
                "<td>{player}</td>" \
                "<td><span class=\"pos-col\">{position}</span></td>" \
                "<td>{injury}</td>" \
                "<td>{practice}</td>" \
                "<td class=\"{cls}\">{game}</td>" \
                "<td><a class=\"chip\" href=\"https://www.nfl.com/injuries/league/2026/reg10\" target=\"_blank\" rel=\"noopener noreferrer\">NI-INJURIES ↗</a></td>" \
                "</tr>".format(
                    abbr=esc(r["abbr"]), team=esc(r["team"]), record=esc(r["record"]),
                    player=esc(r["player"]), position=esc(r["position"]), injury=chip_block(r["injury"]),
                    practice=esc(r["practice"]), game=esc(r["game"]), cls=game_class)
    body += "</tbody></table>\n"
    body += (
        '<p><strong>Source chips:</strong> each row links to the official NFL injury report '
        '(<a href="https://www.nfl.com/injuries/league/2026/reg10">NI-INJURIES ↗</a>) and the '
        'injury-report policy (<a href="https://www.nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3000000688693">NI-INJURY-POLICY ↗</a>). '
        'Roster pages do not publish depth order (<a href="https://www.nfl.com/teams/green-bay-packers/roster">NI-ROSTER ↗</a>).</p>'
    )
    return page_shell("Injury Tracking", body, active="pages/injuries.html")


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------
def build_suggestions(suggestions, sources):
    source_map = {s["id"]: s for s in sources["sources"]}
    body = (
        '<div class="notice"><strong>Purpose:</strong> {}</div>\n'.format(esc(suggestions["meta"]["purpose"])) +
        '<div class="notice blue"><strong>Every entry is a PROPOSAL.</strong> None is implemented until reviewed and approved. '
        'These are internal project proposals — not source-verified NFL data or strategy. Source cells are deliberately blank and flagged.</div>\n'
    )
    body += (
        '<table class="data"><caption>Suggestions for site improvement — review before implementing.</caption>'
        '<thead><tr><th>ID</th><th>Suggestion</th><th>Rationale</th><th>Decision impact</th><th>Status</th><th>Source</th></tr></thead>'
        '<tbody>'
    )
    for s in suggestions["suggestions"]:
        body += "<tr><td>{id}</td><td>{title}</td><td>{desc}</td><td>{impact}</td>" \
                "<td><span class=\"badge blue\">{status}</span></td><td>{src}</td></tr>".format(
                    id=esc(s["id"]), title=esc(s["title"]), desc=esc(s["description"]),
                    impact=esc(s["decision_impact"]), status=esc(s["status"]),
                    src=source_chips([], source_map) if not s.get("source") else chip_block(s.get("source","")))
    body += "</tbody></table>\n"
    body += (
        '<p><strong>Decision path:</strong> a reviewer reads each suggestion, checks whether its required information '
        'exists (see Questions &amp; Answers), and chooses the best path before any change is implemented. '
        'Approved suggestions move to implementation; rejected ones stay here with a reason.</p>'
    )
    return page_shell("Suggestions", body, active="pages/suggestions.html")


# ---------------------------------------------------------------------------
# Questions & Answers
# ---------------------------------------------------------------------------
def build_questions(questions, sources):
    source_map = {s["id"]: s for s in sources["sources"]}
    body = (
        '<div class="notice"><strong>Purpose:</strong> {}</div>\n'.format(esc(questions["meta"]["purpose"])) +
        '<div class="notice blue"><strong>Blank answer = information we do not have.</strong> Flagged, never inferred. '
        'Only answer from an official source we can link.</div>\n'
    )
    body += (
        '<table class="data"><caption>Pre-decision questions, information and answers.</caption>'
        '<thead><tr><th>ID</th><th>Question</th><th>Information needed</th><th>Answer</th>'
        '<th>Source</th><th>Status</th></tr></thead>'
        '<tbody>'
    )
    for q in questions["questions"]:
        body += "<tr><td>{id}</td><td>{q}</td><td>{info}</td><td>{ans}</td><td>{src}</td>" \
                "<td><span class=\"badge {cls}\">{status}</span></td></tr>".format(
                    id=esc(q["id"]), q=esc(q["question"]), info=esc(q["information_needed"]),
                    ans=chip_block(q.get("answer", "")),
                    src=source_chips([q["source"]] if q.get("source") else [], source_map),
                    cls="ok" if q.get("status","").startswith("answered") else "warn",
                    status=esc(q["status"]))
    body += "</tbody></table>\n"
    body += (
        '<p><strong>How to use:</strong> before any decision (site change, strategy deployment, model use), work down '
        'this register. Any row with a blank answer is information we do not have and must be resolved (or explicitly '
        'accepted as a risk) before the decision is reasonable.</p>'
    )
    return page_shell("Questions &amp; Answers", body, active="pages/questions.html")


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------
def build_executive(executive, sources):
    source_map = {s["id"]: s for s in sources["sources"]}
    body = ""
    for sec in executive["sections"]:
        body += (
            '<section class="panel">'
            '<h2>{}</h2>'
            '<p>{}</p>'
            '<div style="margin-top:8px">{}</div>'
            '</section>\n'.format(
                esc(sec["title"]), esc(sec["body"]),
                source_chips(sec.get("sources", []), source_map) + " " +
                verified_badge(sec.get("status", ""), has_official(sec.get("sources", []), source_map)))
    )
    return page_shell("Executive Summary", body, active="pages/executive.html")


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
def build_strategies(strategies, sources):
    source_map = {s["id"]: s for s in sources["sources"]}
    body = (
        '<div class="notice">{}</div>\n'.format(esc(strategies["meta"]["note"])) +
        '<div class="notice blue"><strong>No strategy passed validation gates.</strong> '
        '0 strategies qualified; nothing is approved for capital and no reward is awarded.</div>\n'
    )
    body += (
        '<table class="data"><caption>Line-origination strategy reference (quoted from published sibling sessions).</caption>'
        '<thead><tr><th>ID</th><th>Strategy</th><th>Bet type</th><th>Description</th>'
        '<th>Inputs</th><th>Gates</th><th>Correlation handling</th><th>Performance</th><th>Status</th><th>Source</th></tr></thead>'
        '<tbody>'
    )
    for st in strategies["strategies"]:
        body += "<tr><td>{id}</td><td>{name}</td><td>{type}</td><td>{desc}</td>" \
                "<td><span class=\"chips\">{inputs}</span></td>" \
                "<td><span class=\"chips\">{gates}</span></td>" \
                "<td>{corr}</td><td>{perf}</td>" \
                "<td><span class=\"badge warn\">{status}</span></td>" \
                "<td>{src}</td></tr>".format(
                    id=esc(st["id"]), name=esc(st["name"]), type=esc(st["type"]),
                    desc=esc(st["description"]),
                    inputs="".join('<span class="chip">{}</span>'.format(esc(i)) for i in st.get("inputs", [])),
                    gates="".join('<span class="chip">{}</span>'.format(esc(g)) for g in st.get("gates", [])),
                    corr=chip_block(st.get("correlation_handling", "")),
                    perf=chip_block(st.get("performance", "")),
                    status=esc(st["status"]),
                    src=source_chips([st["source"]] if st.get("source") else [], source_map))
    body += "</tbody></table>\n"

    lb = strategies["leaderboard"]
    body += (
        '<section class="panel"><h2>Leaderboard (design concept)</h2>'
        '<p>{}</p>'
        '<p><strong>Model:</strong> {}</p>'
        '<p><strong>Status:</strong> <span class="badge warn">{}</span></p>'
        '<p>{}</p></section>\n'.format(
            esc(lb["note"]), esc(lb["model"]), esc(lb["status"]),
            source_chips([lb["source"]] if lb.get("source") else [], source_map))
    )
    return page_shell("Strategies", body, active="pages/strategies.html")


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
def build_sources(sources):
    body = (
        '<div class="notice"><strong>Policy:</strong> {}</div>\n'.format(esc(sources["meta"]["policy"]))
    )
    body += (
        '<table class="data"><caption>Official source register used on this site.</caption>'
        '<thead><tr><th>ID</th><th>Source</th><th>Organization</th><th>Type</th>'
        '<th>Official link</th><th>Verified</th><th>What it verifies</th></tr></thead>'
        '<tbody>'
    )
    for s in sources["sources"]:
        body += "<tr><td>{id}</td><td>{label}</td><td>{org}</td><td>{type}</td>" \
                "<td><a class=\"chip\" href=\"{url}\" target=\"_blank\" rel=\"noopener noreferrer\">{url_short} ↗</a></td>" \
                "<td>{date}</td><td>{note}</td></tr>".format(
                    id=esc(s["id"]), label=esc(s["label"]), org=esc(s["org"]),
                    type=esc(s["type"]), url=esc(s["url"]),
                    url_short=esc(s["url"].replace("https://", "").replace("http://", "")),
                    date=esc(s.get("verified_on", "")), note=esc(s["note"]))
    body += "</tbody></table>\n"
    return page_shell("Data &amp; Sources", body, active="pages/sources.html")


# ---------------------------------------------------------------------------
# Flagged
# ---------------------------------------------------------------------------
def build_flagged(flagged, sources):
    source_map = {s["id"]: s for s in sources["sources"]}
    body = (
        '<div class="notice"><strong>Policy:</strong> {}</div>\n'.format(esc(flagged["meta"]["policy"]))
    )
    body += (
        '<table class="data"><caption>Flagged for review — unverified items, blank by policy.</caption>'
        '<thead><tr><th>ID</th><th>Item</th><th>Value</th><th>Value status</th><th>Reason</th>'
        '<th>Source</th><th>Resolution needed</th></tr></thead>'
        '<tbody>'
    )
    for it in flagged["items"]:
        body += "<tr><td>{id}</td><td>{item}</td><td><span class=\"empty-val\">— (blank)</span></td>" \
                "<td><span class=\"badge warn\">{vs}</span></td><td>{reason}</td>" \
                "<td>{src}</td><td>{res}</td></tr>".format(
                    id=esc(it["id"]), item=esc(it["item"]),
                    vs=esc(it["value_status"]), reason=esc(it["reason"]),
                    src=source_chips(it.get("sources", []), source_map),
                    res=esc(it["resolution_needed"]))
    body += "</tbody></table>\n"
    body += (
        '<p><strong>Handling:</strong> flagged items do not block publication. They are published here so a reviewer '
        'can resolve them. No value is inferred to fill a blank.</p>'
    )
    return page_shell("⚑ Flagged for Review", body, active="pages/flagged.html")


def main():
    sources = load("sources.json")
    injuries = load("injuries.json")
    suggestions = load("suggestions.json")
    questions = load("questions.json")
    executive = load("executive.json")
    strategies = load("strategies.json")
    flagged = load("flagged.json")

    PAGES.mkdir(parents=True, exist_ok=True)

    writers = {
        "index.html": build_index(sources, suggestions, questions, injuries, flagged, executive, strategies),
        "pages/injuries.html": build_injuries(injuries, sources),
        "pages/suggestions.html": build_suggestions(suggestions, sources),
        "pages/questions.html": build_questions(questions, sources),
        "pages/executive.html": build_executive(executive, sources),
        "pages/strategies.html": build_strategies(strategies, sources),
        "pages/sources.html": build_sources(sources),
        "pages/flagged.html": build_flagged(flagged, sources),
    }

    for rel, html_text in writers.items():
        target = OUT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_text, encoding="utf-8")
        print("wrote", target)

    # .nojekyll so GitHub Pages serves everything as static
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print("wrote", OUT / ".nojekyll")
    print("Build complete.")


if __name__ == "__main__":
    main()
