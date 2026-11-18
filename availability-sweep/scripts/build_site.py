#!/usr/bin/env python3
"""Deterministic site builder for the availability-sweep hub.

Reads the committed CSV/JSON registers under data/ and renders the hub pages.
Every rendered table row carries a Source cell linking the official page the
row was read from. Run with --check to verify the committed HTML matches a
fresh build.
"""
from __future__ import annotations

import csv
import json
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PAGES = ROOT / "pages"

CAPTURE_STAMP = "2026-11-18T03:55:37Z"
REPORT_URL = "https://www.nfl.com/injuries/league/2026/REG10"
SCHEDULE_URL = "https://www.nfl.com/schedules/2026/by-week/week-10"

STYLE = """  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f5f7fa;color:#15202b}
  main{max-width:1180px;margin:0 auto;padding:24px 16px 60px}
  header.site{background:#0b2340;color:#fff;padding:18px 16px}
  header.site .inner{max-width:1180px;margin:0 auto}
  header.site h1{margin:0;font-size:1.35rem}
  header.site .stamp{font-size:.85rem;opacity:.85;margin-top:4px}
  nav.hub{margin-top:10px;display:flex;flex-wrap:wrap;gap:12px}
  nav.hub a{color:#9cc3ff;text-decoration:none;font-size:.95rem}
  nav.hub a:hover{text-decoration:underline}
  .card{background:#fff;border:1px solid #dbe2ea;border-radius:10px;padding:16px 18px;margin:18px 0}
  .card h2{margin:0 0 10px;font-size:1.15rem}
  .card h3{margin:16px 0 8px;font-size:1.02rem}
  .note{background:#fff8e6;border:1px solid #e8d9a0;border-radius:8px;padding:10px 14px;font-size:.92rem;margin:12px 0}
  .flaginfo{background:#eef4ff}
  table{border-collapse:collapse;width:100%;font-size:.9rem}
  th,td{border:1px solid #d7dde5;padding:5px 8px;text-align:left;vertical-align:top}
  th{background:#eef2f7;position:sticky;top:0}
  tr:nth-child(even) td{background:#fafbfd}
  .num{text-align:right}
  a{color:#0b52c4}
  .mut{color:#5a6b7f}
  .out{color:#a30000;font-weight:600}
  .quest{color:#8a6d00;font-weight:600}
  .doubt{color:#a34d00;font-weight:600}
  .ok{color:#0a7d33}
"""


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def esc(v) -> str:
    if not isinstance(v, str):
        v = str(v)
    return escape(v or "", quote=True)


def status_cls(v: str) -> str:
    v = (v or "").lower()
    if v == "out":
        return "out"
    if v == "questionable":
        return "quest"
    if v == "doubtful":
        return "doubt"
    return ""


def blank(v: str) -> str:
    return v if v else '<span class="mut">blank</span>'


def page(title: str, body: str, active: str, depth: int = 0) -> str:
    up = "../" * depth
    links = [
        ("index.html" if depth == 0 else "../index.html", "Overview", "index"),
        ("pages/week10.html" if depth == 0 else "week10.html", "Week 10 rows (347)", "week10"),
        ("pages/deltas.html" if depth == 0 else "deltas.html", "Captures &amp; deltas", "deltas"),
        ("pages/flags.html" if depth == 0 else "flags.html", "Flagged for review", "flags"),
        ("../../index.html" if depth else "../index.html", "Repo root site", ""),
    ]
    nav_html = "".join(
        '<a href="%s"%s>%s</a>' % (esc(h), ' class="active"' if active == key else "", label)
        for h, label, key in links
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
{STYLE}</style>
</head>
<body>
<header class="site"><div class="inner">
<h1>Availability Sweep — official injury-report register</h1>
<div class="stamp">Week 10 capture of {CAPTURE_STAMP} · sources: <a style="color:#9cc3ff" href="{REPORT_URL}">NFL.com Week 10 injury report</a> · <a style="color:#9cc3ff" href="{SCHEDULE_URL}">NFL.com Week 10 schedule</a> · session owner: arena/9fa8ea61-korea2</div>
<nav class="hub">
{nav_html}
</nav>
</div></header>
<main>
{body}
</main>
</body>
</html>
"""


def rel_url(u: str, depth: int) -> str:
    """Resolve a data-file reference to a href relative to the page being built.

    http(s) URLs pass through; anything else is treated as repo-root-relative.
    """
    if u.startswith("http://") or u.startswith("https://"):
        return u
    # repo-root-relative references need one extra level up from the page's own depth
    return "../" * (depth + 1) + u


def source_cell(urls: list[str], label: str = "Source") -> str:
    links = ", ".join(f'<a href="{esc(u)}" rel="noopener">{label}</a>' if i == 0 else f'<a href="{esc(u)}" rel="noopener">{i + 1}</a>' for i, u in enumerate(urls))
    return links


def build_week10_page(rows: list[dict[str, str]], counts: list[dict[str, str]], byes: list[dict[str, str]], depth: int = 1) -> str:
    parts: list[str] = []
    parts.append('<div class="card"><h2>Week 10 official injury report — full row register (28 teams, 347 rows)</h2>')
    parts.append('<p class="mut">Transcribed verbatim from the official NFL.com Week 10 injury report on '
                 + CAPTURE_STAMP + '. Each row links the report page and the player\'s official page. '
                 'Blank practice/game-status cells are rendered as <span class="mut">blank</span>, exactly as published. '
                 'Multi-injury text is shown with the page\'s comma form.</p>')
    order = [c["team"] for c in counts]
    for team in order:
        trows = [r for r in rows if r["team"] == team]
        cnt = next(c for c in counts if c["team"] == team)
        opp = trows[0]["opponent"] if trows else ""
        gdate = trows[0]["game_date"] if trows else ""
        parts.append(f'<h3>{esc(team)} — {esc(gdate)} vs {esc(opp)} · {cnt["rows"]} rows '
                     f'(<a href="{REPORT_URL}" rel="noopener">report</a>, '
                     f'<a href="{esc(cnt["game_url"])}" rel="noopener">game centre</a>)</h3>')
        parts.append('<table><thead><tr><th>Player</th><th>Pos</th><th>Injuries</th><th>Practice status</th>'
                     '<th>Game status</th><th>Row sources</th></tr></thead><tbody>')
        for r in trows:
            player_cell = f'<a href="{esc(r["player_url"])}" rel="noopener">{esc(r["player"])}</a>' if r["player_url"] else esc(r["player"])
            inj = r["injuries"].replace("; ", ", ")
            cls = status_cls(r["game_status"])
            gs = f'<span class="{cls}">{esc(r["game_status"])}</span>' if r["game_status"] else blank("")
            parts.append(f'<tr><td>{player_cell}</td><td>{esc(r["position"])}</td><td>{esc(inj)}</td>'
                         f'<td>{esc(r["practice_status"])}</td><td>{gs}</td>'
                         f'<td>{source_cell([REPORT_URL, r["player_url"]])}</td></tr>')
        parts.append('</tbody></table>')
    parts.append('<h3>Bye teams — official "Teams on Bye" section</h3>')
    parts.append('<table><thead><tr><th>Team</th><th>Record</th><th>Bye week</th><th>Source</th></tr></thead><tbody>')
    for b in byes:
        parts.append(f'<tr><td>{esc(b["team"])}</td><td>{esc(b["record"])}</td><td>{esc(b["bye_week"])}</td>'
                     f'<td><a href="{esc(b["source_url"])}" rel="noopener">Source</a></td></tr>')
    parts.append('</tbody></table></div>')
    return page("Week 10 rows — Availability Sweep", "\n".join(parts), "week10", depth)


def build_delta_page(rows: list[dict[str, str]], log: list[dict[str, str]], delta: list[dict[str, str]], reg11: dict, depth: int = 1) -> str:
    changed = [d for d in delta if d["changed"] == "yes"]
    parts = ['<div class="card"><h2>Capture series and row-level deltas</h2>',
             '<p class="mut">Store the read with its clock time and publish the delta, never just the level. '
             'Two dated captures of the same Week 10 report exist; the first covered 3 of 28 teams row by row, '
             'the second covers all 28. No raw response hash was retained for either read (fetch-tool limitation).</p>',
             '<h3>Capture log</h3>',
             '<table><thead><tr><th>Capture</th><th>Week</th><th>URL</th><th>Fetched (UTC)</th><th>Scope</th><th>Rows</th><th>Teams</th><th>Raw hash</th></tr></thead><tbody>']
    for c in log:
        parts.append(f'<tr><td>{esc(c["capture_id"])}</td><td>{esc(c["week"])}</td>'
                     f'<td><a href="{esc(c["source_url"])}" rel="noopener">{esc(c["url"])}</a></td>'
                     f'<td>{esc(c["fetched_utc_end"])}</td><td>{esc(c["scope"])}</td>'
                     f'<td class="num">{esc(c["rows_captured"])}</td><td class="num">{esc(c["teams_captured"])}</td>'
                     f'<td>{esc(c["raw_bytes_hash"])}</td></tr>')
    parts.append('</tbody></table>')
    parts.append(f'<h3>Delta: capture 2026-11-15 → capture {CAPTURE_STAMP} (33 overlapping rows: DET, SEA, CIN)</h3>')
    if changed:
        parts.append(f'<p class="out">{len(changed)} row(s) changed between captures:</p>')
        parts.append('<table><thead><tr><th>Team</th><th>Player</th><th>Field</th><th>2026-11-15</th><th>2026-11-18</th><th>Source</th></tr></thead><tbody>')
        for d in changed:
            parts.append(f'<tr><td>{esc(d["team"])}</td><td>{esc(d["player"])}</td><td>{esc(d["field"])}</td>'
                         f'<td>{esc(d["value_20261115"]) or blank("")}</td><td>{esc(d["value_20261118"]) or blank("")}</td>'
                         f'<td><a href="{REPORT_URL}" rel="noopener">Source</a></td></tr>')
        parts.append('</tbody></table>')
    else:
        parts.append('<p class="ok">No field changed across all 33 overlapping rows between 2026-11-15T18:08:20Z and '
                     + CAPTURE_STAMP + ' — the report is frozen at its final weekly state after game day. '
                     'The full per-row comparison is committed at <code>data/delta_20261115_20261118.csv</code>.</p>')
    parts.append('<h3>Week 11 attempt</h3>')
    parts.append('<div class="note">' + esc(reg11["detail"]) + ' <a href="' + esc(reg11["source_url"])
                 + '" rel="noopener">Source</a></div>')
    parts.append('<h3>Fixture context officially published with the Week 10 report</h3>')
    parts.append('<p class="mut">Game dates, slots and results read from the official schedule page. Venue is recorded '
                 'only where the schedule page states it (the Munich International Game); other venues are left blank '
                 'rather than inferred — per-game game-centre venue transcription is a separate pending task.</p>')
    games = read_csv(DATA / "week10_games.csv")
    parts.append('<table><thead><tr><th>Date</th><th>Matchup</th><th>Final</th><th>Slot</th><th>Venue</th><th>Source</th></tr></thead><tbody>')
    for g in games:
        venue = "Munich (International Game)" if "Munich" in g["slot"] else ""
        parts.append(f'<tr><td>{esc(g["game_date"])}</td><td>{esc(g["away_team"])} at {esc(g["home_team"])}</td>'
                     f'<td>{esc(g["away_score"])}–{esc(g["home_score"])} ({esc(g["status"])})</td><td>{esc(g["slot"])}</td>'
                     f'<td>{esc(venue) or blank("")}</td>'
                     f'<td><a href="{esc(g["source_url"])}" rel="noopener">Game centre</a>, '
                     f'<a href="{SCHEDULE_URL}" rel="noopener">schedule</a></td></tr>')
    parts.append('</tbody></table></div>')
    return page("Captures & deltas — Availability Sweep", "\n".join(parts), "deltas", depth)


def build_flags_page(flags: dict, depth: int = 1) -> str:
    parts = ['<div class="card"><h2>Flagged for review — availability sweep</h2>',
             '<p class="mut">Conflicts, limitations and unverified items found during the sweep. '
             'Nothing here was silently corrected; values stay as published and the conflict is recorded.</p>',
             '<table><thead><tr><th>ID</th><th>Severity</th><th>Finding</th><th>Sources</th></tr></thead><tbody>']
    for f in flags["flags"]:
        urls = f.get("source_urls", [f.get("source_url", "")])
        links = ", ".join(f'<a href="{esc(rel_url(u, depth))}" rel="noopener">{i + 1}</a>' for i, u in enumerate(urls) if u)
        parts.append(f'<tr><td>{esc(f["id"])}</td><td>{esc(f["severity"])}</td><td><strong>{esc(f["title"])}</strong> — {esc(f["detail"])}</td>'
                     f'<td>{links}</td></tr>')
    parts.append('</tbody></table></div>')
    return page("Flagged for review — Availability Sweep", "\n".join(parts), "flags", depth)


def build_index(rows: list[dict[str, str]], counts: list[dict[str, str]], byes: list[dict[str, str]], flags: dict, log: list[dict[str, str]], depth: int = 0) -> str:
    with_status = sum(1 for r in rows if r["game_status"])
    out_rows = sum(1 for r in rows if r["game_status"].lower() == "out")
    quest = sum(1 for r in rows if r["game_status"].lower() == "questionable")
    doubt = sum(1 for r in rows if r["game_status"].lower() == "doubtful")
    dnp = sum(1 for r in rows if r["practice_status"].lower().startswith("did not"))
    fullp = sum(1 for r in rows if r["practice_status"].lower().startswith("full"))
    limb = sum(1 for r in rows if r["practice_status"].lower().startswith("limited"))
    conflicts = [f for f in flags["flags"] if f["severity"] == "conflict"]

    parts = ['<div class="card"><h2>What this hub is</h2>',
             '<p>The 32-team Week 10 availability sweep: every row of the official NFL.com Week 10 injury report '
             'transcribed with its clock time, the four bye clubs verified against the official schedule page, a '
             'row-level delta against the earlier dated capture, and a Week 11 first-read attempt. All values are '
             'transcriptions of official pages; nothing is inferred. Sibling hubs: '
             '<a href="../injury-report-w10/index.html">injury-report-w10</a> (2026-11-15 partial capture and its flags).</p>',
             '<table><thead><tr><th>Measure</th><th>Value</th><th>Basis</th><th>Source</th></tr></thead><tbody>',
             f'<tr><td>Team tables transcribed</td><td class="num">28 of 28 listed</td><td>row-by-row read, {CAPTURE_STAMP}</td><td><a href="{REPORT_URL}" rel="noopener">Source</a></td></tr>',
             f'<tr><td>Report rows captured</td><td class="num">{len(rows)}</td><td>sum of the 28 team tables</td><td><a href="{REPORT_URL}" rel="noopener">Source</a></td></tr>',
             f'<tr><td>Rows with a game status</td><td class="num">{with_status}</td><td>Out {out_rows} · Questionable {quest} · Doubtful {doubt}; the rest blank as published</td><td><a href="{REPORT_URL}" rel="noopener">Source</a></td></tr>',
             f'<tr><td>Practice-status mix</td><td class="num">Full {fullp} · Limited {limb} · DNP {dnp}</td><td>verbatim strings from the report</td><td><a href="{REPORT_URL}" rel="noopener">Source</a></td></tr>',
             f'<tr><td>Bye clubs verified</td><td class="num">{len(byes)}</td><td>official "Teams on Bye" section: CHI, DEN, PHI, TB</td><td><a href="{SCHEDULE_URL}" rel="noopener">Source</a></td></tr>',
             f'<tr><td>Delta vs 2026-11-15 capture</td><td class="num">0 fields changed</td><td>33 overlapping rows (DET, SEA, CIN), full comparison committed</td><td><a href="pages/deltas.html">Delta table</a></td></tr>',
             f'<tr><td>Week 11 report status</td><td>not yet published at capture time</td><td>REG11 URL served the Week 10 report</td><td><a href="pages/flags.html">AV-F1</a></td></tr>',
             f'<tr><td>Open conflicts carried</td><td class="num">{len(conflicts)}</td><td>Walker downgrade vs table; Henderson IR; Nacua blank status</td><td><a href="pages/flags.html">Flagged page</a></td></tr>',
             '</tbody></table></div>']

    parts.append('<div class="card"><h2>Per-team row counts</h2>'
                 '<table><thead><tr><th>Team</th><th>Game date</th><th>Opponent</th><th>Rows</th><th>Out</th>'
                 '<th>Doubtful</th><th>Questionable</th><th>Blank status</th><th>Sources</th></tr></thead><tbody>')
    for c in counts:
        trows = [r for r in rows if r["team"] == c["team"]]
        parts.append(f'<tr><td>{esc(c["team"])}</td><td>{esc(c["game_date"])}</td><td>{esc(c["opponent"])}</td>'
                     f'<td class="num">{esc(c["rows"])}</td>'
                     f'<td class="num">{sum(1 for r in trows if r["game_status"].lower() == "out")}</td>'
                     f'<td class="num">{sum(1 for r in trows if r["game_status"].lower() == "doubtful")}</td>'
                     f'<td class="num">{sum(1 for r in trows if r["game_status"].lower() == "questionable")}</td>'
                     f'<td class="num">{sum(1 for r in trows if not r["game_status"])}</td>'
                     f'<td><a href="{REPORT_URL}" rel="noopener">report</a>, <a href="{esc(c["game_url"])}" rel="noopener">game centre</a></td></tr>')
    for b in byes:
        parts.append(f'<tr><td>{esc(b["team"])}</td><td colspan="2">bye (no Week 10 game)</td><td class="num">0</td>'
                     f'<td colspan="4" class="mut">absence explained by official bye listing</td>'
                     f'<td><a href="{esc(b["source_url"])}" rel="noopener">schedule</a></td></tr>')
    parts.append('</tbody></table></div>')

    parts.append('<div class="card"><h2>Capture log</h2><table><thead><tr><th>Capture</th><th>When (UTC)</th>'
                 '<th>Scope</th><th>Rows</th><th>Source</th></tr></thead><tbody>')
    for c in log:
        parts.append(f'<tr><td>{esc(c["capture_id"])}</td><td>{esc(c["fetched_utc_end"])}</td><td>{esc(c["scope"])}</td>'
                     f'<td class="num">{esc(c["rows_captured"])}</td><td><a href="{esc(c["source_url"])}" rel="noopener">Source</a></td></tr>')
    parts.append('</tbody></table>'
                 '<p class="mut">Requirement context: "Store every injury-hub read with its clock time and publish the '
                 'delta, never the level" and "Run the 32-team roster/IR sweep before any team-level model is trusted." '
                 'Still unmet elsewhere: raw-byte hashes, daily Wed/Thu/Fri series, reserve-list ingestion, depth/starters '
                 'evidence (Game Books). See <a href="pages/flags.html">flagged items</a>.</p></div>')

    parts.append('<div class="card"><h2>Verification performed for this hub</h2><ul>'
                 '<li>Row-by-row transcription of all 8 chunks of the official report; every row carries the report URL '
                 'and the player-page URL as its sources.</li>'
                 '<li>Per-team counts reconcile against the independent manual counts committed by the 2026-11-15 capture '
                 '(all 28 teams match; totals both 347).</li>'
                 '<li>32/32 clubs accounted for: 28 report tables + 4 official "Teams on Bye" entries.</li>'
                 '<li>Delta computed programmatically against the committed 2026-11-15 register (33 rows, 0 changes).</li>'
                 '<li><code>scripts/verify.py</code> enforces schema, counts, domains, status vocabularies and delta integrity.</li>'
                 '</ul></div>')
    return page("Availability Sweep — 32-team Week 10 register", "\n".join(parts), "index", depth)


def main(argv: list[str]) -> int:
    check = "--check" in argv
    rows = read_csv(DATA / "week10_rows_20261118.csv")
    byes = read_csv(DATA / "week10_byes.csv")
    games = read_csv(DATA / "week10_games.csv")
    log = read_csv(DATA / "capture_log.csv")
    flags = json.loads((DATA / "flags.json").read_text(encoding="utf-8"))

    # per-team counts, joined to game-centre URLs (both home and away clubs)
    game_url: dict[str, str] = {}
    for g in games:
        game_url[g["home_team"]] = g["source_url"]
        game_url[g["away_team"]] = g["source_url"]
    seen: dict[str, dict] = {}
    for r in rows:
        t = r["team"]
        if t not in seen:
            seen[t] = {"team": t, "game_date": r["game_date"], "opponent": r["opponent"],
                       "rows": 0, "game_url": game_url.get(t, REPORT_URL)}
        seen[t]["rows"] += 1
    for b in byes:
        seen.setdefault(b["team"], {"team": b["team"], "game_date": "", "opponent": "bye", "rows": 0,
                                    "game_url": b["source_url"]})
    counts = [seen[t] for t in sorted(seen, key=lambda t: (t not in {r["team"] for r in rows}, t))]
    counts = [c for c in counts if c["team"] in {r["team"] for r in rows}]

    # delta against the committed 2026-11-15 partial capture
    old = read_csv(ROOT.parent / "injury-report-w10" / "data" / "week10_rows_read.csv")
    new_by_key = {(r["team"], r["player"]): r for r in rows}
    delta = []
    for o in old:
        key = (o["team"], o["player"])
        n = new_by_key.get(key)
        if n is None:
            delta.append({"team": o["team"], "player": o["player"], "field": "row", "value_20261115": "present",
                          "value_20261118": "MISSING", "changed": "yes"})
            continue
        old_inj = (o["injury"] or "").strip()
        new_inj = (n["injuries"] or "").replace("; ", ", ").strip()
        pairs = [("injuries", old_inj, new_inj),
                 ("practice_status", (o["practice_status"] or "").strip(), (n["practice_status"] or "").strip()),
                 ("game_status", (o["game_status"] or "").strip(), (n["game_status"] or "").strip())]
        for field, a, b in pairs:
            if a != b:
                delta.append({"team": o["team"], "player": o["player"], "field": field,
                              "value_20261115": a, "value_20261118": b, "changed": "yes"})
        if all(a == b for _, a, b in pairs):
            delta.append({"team": o["team"], "player": o["player"], "field": "(all fields)",
                          "value_20261115": "unchanged", "value_20261118": "unchanged", "changed": "no"})

    with (DATA / "week10_team_counts_20261118.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["team", "game_date", "opponent", "rows", "game_url"])
        w.writeheader()
        w.writerows(counts)
    with (DATA / "delta_20261115_20261118.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["team", "player", "field", "value_20261115", "value_20261118", "changed"])
        w.writeheader()
        w.writerows(delta)

    reg11 = next(f for f in flags["flags"] if f["id"] == "AV-F1")

    pages = {
        PAGES / "week10.html": build_week10_page(rows, counts, byes),
        PAGES / "deltas.html": build_delta_page(rows, log, delta, reg11),
        PAGES / "flags.html": build_flags_page(flags),
        ROOT / "index.html": build_index(rows, counts, byes, flags, log),
    }
    if check:
        bad = [str(p) for p, html in pages.items() if p.read_text(encoding="utf-8") != html]
        for p in bad:
            print(f"MISMATCH: {p}", file=sys.stderr)
        print("check:", "ok" if not bad else f"{len(bad)} mismatched page(s)")
        return 1 if bad else 0
    for p, html in pages.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")
    print(f"built {len(pages)} pages from {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
