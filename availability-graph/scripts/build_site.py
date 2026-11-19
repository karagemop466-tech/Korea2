#!/usr/bin/env python3
"""Deterministic site builder for the availability-graph hub.

Reads the committed registers under availability-graph/data/ and renders the hub pages.
Every rendered table row carries a Source cell linking the official page the row was read from.
Run with --check to verify that the committed HTML matches a fresh build.
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

STYLE = """  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f5f7fa;color:#15202b}
  main{max-width:1240px;margin:0 auto;padding:24px 16px 60px}
  header.site{background:#0b2340;color:#fff;padding:18px 16px}
  header.site .inner{max-width:1240px;margin:0 auto}
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
  .kpis{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}
  .kpi{background:#fff;border:1px solid #dbe2ea;border-radius:10px;padding:12px 16px;min-width:150px}
  .kpi .v{font-size:1.5rem;font-weight:700;color:#0b2340}
  .kpi .l{font-size:.82rem;color:#5a6b7f;text-transform:uppercase;letter-spacing:.03em}
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
  .changed{background:#fff3f3 !important}
"""

PAGES_TITLES = [
    ("gamebooks.html", "Game Books"),
    ("lineups.html", "Official starters"),
    ("inactives.html", "Inactive lists"),
    ("availability-graph.html", "Availability graph"),
    ("teams.html", "Per-club view"),
    ("roster-status.html", "Roster status"),
    ("depth-sources.html", "Depth-order source audit"),
    ("method.html", "Method"),
    ("sources.html", "Sources"),
    ("flags.html", "Flagged for review"),
]


def read_csv(name: str) -> list[dict[str, str]]:
    path = DATA / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_json(name: str, default=None):
    path = DATA / name
    if not path.exists():
        return default if default is not None else {}
    return json.loads(path.read_text(encoding="utf-8"))


def esc(v) -> str:
    if v is None:
        v = ""
    return escape(str(v), quote=True)


def blank(v: str, why: str = "not published by an official source") -> str:
    """A value that could not be confirmed from an official source stays blank and says why."""
    if v:
        return esc(v)
    return f'<span class="mut" title="{esc(why)}">blank</span>'


def link(url: str, label: str = "official") -> str:
    if not url:
        return '<span class="mut" title="no official URL recorded">blank</span>'
    return f'<a href="{esc(url)}" rel="noopener">{esc(label)}</a>'


def status_cls(v: str) -> str:
    v = (v or "").lower()
    if v == "out":
        return "out"
    if v == "questionable":
        return "quest"
    if v == "doubtful":
        return "doubt"
    return ""


def table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for row in rows:
        cells = "".join(f"<td>{c}</td>" for c in row)
        body.append(f"<tr>{cells}</tr>")
    return (f"<table><thead><tr>{head}</tr></thead><tbody>" + "".join(body) + "</tbody></table>")


def page(title: str, body: str, active: str = "") -> str:
    nav = []
    for href, label in PAGES_TITLES:
        cls = ' class="active"' if href == active else ""
        nav.append(f'<a href="{href}"{cls}>{esc(label)}</a>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — Availability Graph</title>
<style>{STYLE}</style>
</head>
<body>
<header class="site"><div class="inner">
<h1>{esc(title)}</h1>
<div class="stamp">Official availability evidence — every row links the official page it was read from</div>
<nav class="hub"><a href="../index.html">Home</a>{''.join(nav)}</nav>
</div></header>
<main>
{body}
</main>
</body>
</html>
"""


def kpi(value: str, label: str) -> str:
    return f'<div class="kpi"><div class="v">{esc(value)}</div><div class="l">{esc(label)}</div></div>'


def build() -> dict[str, str]:
    gamebooks = read_csv("gamebooks.csv")
    lineups = read_csv("lineups.csv")
    inactives = read_csv("inactives.csv")
    subs = read_csv("substitutions.csv")
    roster = read_csv("roster_status.csv")
    depth = read_csv("depth_sources.csv")
    graph = read_csv("availability_graph.csv")
    teams = read_csv("team_view.csv")
    summary = read_json("summary.json")
    flags = read_json("flags.json", {"flags": []})
    sources = read_json("sources.json", {"sources": []})

    out: dict[str, str] = {}
    stamp = max([g["captured_utc"] for g in gamebooks] or ["not captured"])

    # ---------------------------------------------------------------- index
    kpis = "".join([
        kpi(str(summary.get("gamebooks", len(gamebooks))), "Game Books captured"),
        kpi(str(summary.get("lineup_rows", len(lineups))), "Official starter rows"),
        kpi(str(summary.get("not_active_rows", 0)), "Official Not-Active rows"),
        kpi(str(summary.get("roster_rows", len(roster))), "Official roster-status rows"),
        kpi(str(summary.get("clubs_with_roster_status", 0)), "Clubs with roster status"),
        kpi(str(summary.get("slots_compared", len(graph))), "Slots compared"),
        kpi(str(summary.get("slots_changed", 0)), "Slots whose starter changed"),
    ])
    body = f"""
<div class="card flaginfo">
<h2>What this hub is</h2>
<p>The official availability evidence the rest of this project was missing. Every row below was read
from an official NFL source and links to the page it was read from: the official
<strong>Game Book</strong> of each game (starting lineups, substitutions, Did Not Play, Not Active,
venue, roof and surface, game-day weather), the official <strong>NFL.com team roster page</strong> of
each club (the official roster status of every player) and the official
<strong>weekly injury report</strong> (designations).</p>
<p><strong>Nothing here is inferred.</strong> A depth tier, a snap count, a replacement tier or a
game status that no official source publishes is left blank and flagged, never filled in from a
roster listing, a jersey number, an experience count or a salary.</p>
</div>
<div class="kpis">{kpis}</div>
<div class="card">
<h2>Pages</h2>
<ul>
<li><a href="pages/gamebooks.html">Game Books</a> — one row per captured game: official venue, roof
and surface, game-day weather and the Game Book link.</li>
<li><a href="pages/lineups.html">Official starters</a> — the official starting lineup of every
captured game, both clubs, offense and defense.</li>
<li><a href="pages/inactives.html">Inactive lists</a> — the official Not Active and Did Not Play
lists, and the players who came off the bench.</li>
<li><a href="pages/availability-graph.html">Availability graph</a> — who was expected to start and
who actually started, slot by slot, with the official designation of each player.</li>
<li><a href="pages/teams.html">Per-club view</a> — starters out, replacements named, net injury
count.</li>
<li><a href="pages/roster-status.html">Roster status</a> — the official roster status of every
player of all 32 clubs, so that "not listed in the weekly report" can never be read as "available".</li>
<li><a href="pages/depth-sources.html">Depth-order source audit</a> — what each club actually
publishes as a depth chart, verified club by club.</li>
<li><a href="pages/flags.html">Flagged for review</a> — every irregularity found, with its source.</li>
<li><a href="pages/sources.html">Sources</a> — the source register.</li>
</ul>
</div>
<div class="card">
<h2>Capture</h2>
<p>Captured by <code>availability-graph/scripts/capture_availability.py</code> on a GitHub runner
(the authoring sandbox cannot reach nfl.com). Raw bytes are kept as a workflow artifact outside
this site; the parsed registers and the hash manifests are committed. Last capture stamp:
{esc(stamp)}.</p>
</div>
"""
    out["index.html"] = page("Availability Graph", body)

    # ---------------------------------------------------------------- game books
    rows = []
    for g in sorted(gamebooks, key=lambda r: (int(r["week"]), r["game_date"], r["slug"])):
        rows.append([
            esc(g["week"]), esc(g["gamebook_date"]), esc(g["away_team"]), esc(g["home_team"]),
            blank(g["away_score"]), blank(g["home_score"]),
            blank(g["venue_text"]), blank(g["roof"]), blank(g["surface"]),
            blank(g["weather"]), blank(g["temp"]), blank(g["humidity"]), blank(g["wind"]),
            link(g["gamebook_url"], "Game Book PDF"),
            link(g["game_url"], "game centre"),
        ])
    body = f"""
<div class="card">
<h2>Official Game Books</h2>
<p>One row per captured game. The venue, the roof/surface designation and the game-day weather are
printed in the official game book; the scores are the official final scores published on the
official week schedule page.</p>
</div>
{table(["Week", "Date", "Away", "Home", "Away score", "Home score", "Venue (official game book)",
        "Roof status", "Surface", "Weather", "Temp", "Humidity", "Wind", "Game Book", "Game centre"],
       rows)}
"""
    out["pages/gamebooks.html"] = page("Game Books", body, "gamebooks.html")

    # ---------------------------------------------------------------- lineups
    rows = []
    for r in sorted(lineups, key=lambda x: (int(x["week"]), x["slug"], x["team"], x["unit"],
                                            int(x["jersey"] or 0))):
        rows.append([
            esc(r["week"]), esc(r["team"]), esc(r["unit"]), esc(r["slot"]),
            blank(r["jersey"]), esc(r["player"]),
            link(r["source_url"], "Game Book"),
            link(r["game_url"], "game centre"),
        ])
    body = f"""
<div class="card">
<h2>Official starting lineups</h2>
<p>Exactly what the official game book prints: the eleven offensive and the eleven defensive
starters of each club, with the slot label the game book uses. No starter is inferred from a roster
listing, a depth chart or a projected lineup.</p>
<p class="mut">{len(lineups)} official starter rows captured.</p>
</div>
{table(["Week", "Club", "Unit", "Slot", "Jersey", "Player (as printed in the Game Book)",
        "Source", "Game centre"], rows)}
"""
    out["pages/lineups.html"] = page("Official starters", body, "lineups.html")

    # ---------------------------------------------------------------- inactives
    rows = []
    for r in sorted(inactives, key=lambda x: (int(x["week"]), x["team"], x["category"], x["player"])):
        rows.append([
            esc(r["week"]), esc(r["team"]), esc(r["category"].replace("_", " ")),
            esc(r["position"]), blank(r["jersey"]), esc(r["player"]),
            link(r["source_url"], "Game Book"), link(r["game_url"], "game centre"),
        ])
    sub_rows = []
    for r in sorted(subs, key=lambda x: (int(x["week"]), x["team"], x["player"])):
        sub_rows.append([
            esc(r["week"]), esc(r["team"]), esc(r["position"]), blank(r["jersey"]), esc(r["player"]),
            link(r["source_url"], "Game Book"), link(r["game_url"], "game centre"),
        ])
    body = f"""
<div class="card">
<h2>Official Not Active and Did Not Play lists</h2>
<p>These are the lists the NFL publishes in every game book. They are the evidence that a player was
in the building but not in the game, which is what makes a replacement confirmable rather than
suspected.</p>
<p class="mut">{len(inactives)} rows across the Not Active and Did Not Play lists.</p>
</div>
{table(["Week", "Club", "List", "Position", "Jersey", "Player", "Source", "Game centre"], rows)}
<div class="card">
<h2>Players who came off the bench (official substitution lists)</h2>
<p class="mut">{len(subs)} rows.</p>
</div>
{table(["Week", "Club", "Position", "Jersey", "Player", "Source", "Game centre"], sub_rows)}
"""
    out["pages/inactives.html"] = page("Inactive lists", body, "inactives.html")

    # ---------------------------------------------------------------- availability graph
    early = summary.get("comparison_weeks", [None, None])[0]
    later = summary.get("comparison_weeks", [None, None])[1]
    rows = []
    for r in graph:
        e_key = f"expected_player_wk{early}"
        a_key = f"actual_player_wk{later}"
        changed = r.get("changed") == "yes"
        rows.append([
            esc(r["team"]), esc(r["unit"]), esc(r["slot"]), esc(r.get("slot_ordinal", "")),
            blank(r.get(e_key, "")), blank(r.get(f"expected_designation", "")),
            blank(r.get("expected_roster_status", "")),
            ('<strong>' + esc(r.get(a_key, "")) + '</strong>') if changed else blank(r.get(a_key, "")),
            blank(r.get("actual_designation", "")),
            blank(r.get("actual_roster_status", "")),
            ('<span class="out">changed</span>' if changed else '<span class="ok">unchanged</span>'),
            blank(r.get("depth_tier", ""), "no official depth order verified for this club"),
            link(r.get("gamebook_url", ""), "Game Book"),
            link(r.get("injury_report_url", ""), "injury report"),
        ])
    body = f"""
<div class="card">
<h2>Availability graph — expected starter vs actual starter</h2>
<p>For every position slot of every club, the official starting lineup of week {esc(early)} (the
player who was expected to start) is set against the official starting lineup of week
{esc(later)} (the player who actually started). The designation of each player is the official
weekly injury report; the roster status is the official club roster page.</p>
<p><strong>The depth tier column is blank on purpose.</strong> A tier (1st string, 2nd string, ...)
may only be published where an official depth order has been verified for that club &mdash; see
<a href="depth-sources.html">the depth-order source audit</a>. No tier is inferred from a jersey
number, an experience count, a salary or a roster listing.</p>
<p class="mut">{len(graph)} slots compared; {summary.get('slots_changed', 0)} slots changed.</p>
</div>
{table(["Club", "Unit", "Slot", "#", f"Expected starter (wk {esc(early)})", "Designation",
        "Roster status", f"Actual starter (wk {esc(later)})", "Designation", "Roster status",
        "Change", "Depth tier", "Source", "Injury report"], rows)}
"""
    out["pages/availability-graph.html"] = page("Availability graph", body, "availability-graph.html")

    # ---------------------------------------------------------------- per-club view
    rows = []
    for r in teams:
        rows.append([
            esc(r["team"]), esc(r["slots_compared"]), esc(r["slots_changed"]),
            esc(r["out_designated"]), esc(r["questionable"]), esc(r["doubtful"]),
            esc(r["not_active"]), esc(r["did_not_play"]), esc(r["net_injury_count"]),
            blank(r["starters_out"]), blank(r["replacements_named"]),
            link(r["injury_report_url"], "injury report"),
            link(r["gamebook_url"], "Game Book"),
        ])
    body = f"""
<div class="card">
<h2>Per-club decision view</h2>
<p>Starters out (official designation), replacements named (official starting lineups of two
captured weeks) and the net injury count (official designations on the official weekly report).
A player who is not listed in the weekly report is <em>not</em> assumed to be available &mdash; the
official roster status is published on the <a href="roster-status.html">roster status page</a>.</p>
</div>
{table(["Club", "Slots compared", "Slots changed", "Out", "Questionable", "Doubtful",
        "Not Active (official)", "Did Not Play (official)", "Net injury count", "Starters out",
        "Replacements named", "Source", "Game Book"], rows)}
"""
    out["pages/teams.html"] = page("Per-club view", body, "teams.html")

    # ---------------------------------------------------------------- roster status
    rows = []
    for r in sorted(roster, key=lambda x: (x["club"], x["status"], x["position"], x["player"])):
        rows.append([
            esc(r["club"]), esc(r["player"]), blank(r["jersey"]), esc(r["position"]),
            esc(r["status"]), esc(r.get("height", "")), esc(r.get("weight", "")),
            link(r["source_url"], "official roster page"),
        ])
    counts: dict[str, int] = {}
    for r in roster:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    status_rows = [[esc(k), esc(v)] for k, v in sorted(counts.items())]
    body = f"""
<div class="card">
<h2>Official roster status, all 32 clubs</h2>
<p>The NFL.com team roster page prints a status code for every player on a club's roster. The codes
are published exactly as printed and are never translated. This is the register that makes
"not listed in the weekly report" safe: a player on injured reserve or on the reserve list is
visible here even when the weekly injury report does not mention them.</p>
<p class="mut">{len(roster)} player rows across
{len({r['club'] for r in roster})} clubs.</p>
</div>
{table(["Status code (as printed)", "Players"], status_rows)}
{table(["Club", "Player", "Jersey", "Position", "Status", "Height (in)", "Weight (lb)",
        "Source"], rows)}
"""
    out["pages/roster-status.html"] = page("Roster status", body, "roster-status.html")

    # ---------------------------------------------------------------- depth sources
    rows = []
    for r in sorted(depth, key=lambda x: x["club"]):
        rows.append([
            esc(r["club"]), link(r["roster_url"], "NFL.com roster page"),
            link(r["depth_url"], "club depth chart"),
            blank(r.get("depth_http_status", "")),
            blank(r.get("depth_has_table", "")),
            blank(r.get("depth_image_count", "")),
            ('<span class="quest">yes</span>' if r.get("depth_mentions_unofficial") == "yes"
             else blank(r.get("depth_mentions_unofficial", ""))),
            blank(r.get("note", "")),
            esc(r.get("depth_sha256", "")[:16] or ""),
            esc(r.get("captured_utc", "")),
        ])
    weeks_captured = ", ".join(str(w) for w in summary.get("weeks_captured", []))
    depth_table = table(["Club", "NFL.com roster page", "Official depth-chart URL", "HTTP status",
                         "Machine-readable table?", "Images on page",
                         "Club calls it unofficial?", "Note", "Page SHA-256 (first 16)",
                         "Captured (UTC)"], rows)
    body = f"""
<div class="card">
<h2>Depth-order source audit — every club, verified club by club</h2>
<p>The brief asks for the depth order to be resolved before any backup-deficiency feature is built,
and forbids deriving it from a jersey number, experience or salary. This is the resolution record:
for each of the 32 clubs it shows the official depth-chart URL the NFL.com roster page links to,
whether the page answered, whether the depth information is published as a machine-readable table
or as an image, and whether the club labels the chart <em>unofficial</em>.</p>
<p><strong>Gate:</strong> a depth tier may be published only where an official depth order has been
verified for that club. Until then the tier column of the availability graph stays blank.</p>
</div>
{depth_table}
"""
    out["pages/depth-sources.html"] = page("Depth-order source audit", body, "depth-sources.html")

    # ---------------------------------------------------------------- flags
    flag_rows = []
    for f in flags.get("flags", []):
        flag_rows.append([
            esc(f.get("id", "")), esc(f.get("area", "")), esc(f.get("finding", "")),
            esc(f.get("handling", "")),
            " ".join(link(u, "official") for u in f.get("sources", [])),
        ])
    body = f"""
<div class="card">
<h2>Flagged for review</h2>
<p>Every irregularity found while capturing this evidence, with the official source that shows it.
None of these blocks publication; each one is a limit on what the evidence can support.</p>
</div>
{table(["ID", "Area", "Finding", "Handling", "Source"], flag_rows)}
"""
    out["pages/flags.html"] = page("Flagged for review", body, "flags.html")

    # ---------------------------------------------------------------- sources
    src_rows = []
    for s in sources.get("sources", []):
        src_rows.append([
            esc(s.get("id", "")), esc(s.get("title", "")), link(s.get("url", ""), "open"),
            esc(s.get("read_at", "")), esc(s.get("note", "")),
        ])
    body = f"""
<div class="card">
<h2>Source register</h2>
<p>Every official source read for this hub, with the date it was read.</p>
</div>
{table(["ID", "Source", "URL", "Read (UTC)", "Note"], src_rows)}
"""
    out["pages/sources.html"] = page("Sources", body, "sources.html")

    # ---------------------------------------------------------------- method
    body = f"""
<div class="card">
<h2>How this evidence is produced</h2>
<ol>
<li><strong>Capture.</strong> <code>availability-graph/scripts/capture_availability.py</code> runs on
a GitHub runner. It reads the official week schedule page, the official game centre page of every
game, the official Game Book PDF it links to, the official NFL.com team roster page of all 32
clubs and the club depth-chart page each of those roster pages links to. Every response is hashed
(SHA-256) and timestamped; the raw bytes are uploaded as a workflow artifact and are kept outside
this site.</li>
<li><strong>Parse.</strong> The game-book reader is pinned by unit tests to the official rows of the
New England Patriots at Detroit Lions game book (2026 REG 10), which was read first-hand:
<code>availability-graph/tests/test_capture_parse.py</code>. A section that cannot be parsed is a
failed capture, not a blank cell.</li>
<li><strong>Join.</strong> <code>availability-graph/scripts/analyze.py</code> joins the official
starting lineups of two captured weeks, the official weekly injury report and the official roster
status into the availability graph.</li>
<li><strong>Publish.</strong> <code>availability-graph/scripts/build_site.py</code> renders these
pages from the committed registers, and <code>availability-graph/scripts/verify.py</code> fails the
build if any table row loses its source link or if a register drifts from the published counts.</li>
</ol>
</div>
<div class="card">
<h2>What this evidence cannot support yet</h2>
<ul>
<li><strong>No depth tier.</strong> The depth-order source audit records what each club publishes;
a tier is published only for a club whose official depth order is verified. Nothing is inferred from
a jersey number, experience, salary or a roster listing.</li>
<li><strong>No snap counts.</strong> A game book prints participation, not snaps. Snap counts are a
separate official source (Next Gen Stats) and are not captured here.</li>
<li><strong>One capture series.</strong> The registers hold the weeks that have been captured. The
graph compares the earliest and the latest captured week, so the comparison window is a capture
window, not a season.</li>
<li><strong>Game Book reuse terms.</strong> The official Game Book carries a written notice that the
summary and play-by-play are for assisting media coverage and that any other use needs the written
permission of the NFL. The links are published; the reuse position is a decision for the owner and
is flagged on the Flagged for review page.</li>
</ul>
</div>
<div class="card">
<h2>Comparison window</h2>
<p class="mut">Weeks captured: {esc(weeks_captured)}.
Compared: week {esc(early)} (expected) against week {esc(later)} (actual). Slot key: club, unit,
slot label and the ordinal of that slot inside the unit's lineup, as printed by the game book.</p>
</div>
"""
    out["pages/method.html"] = page("Method", body, "method.html")
    return out


def main() -> int:
    pages = build()
    check = "--check" in sys.argv
    failures = []
    for path, html in pages.items():
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if check:
            if not target.exists():
                failures.append(f"missing {path}")
            elif target.read_text(encoding="utf-8") != html:
                failures.append(f"{path} differs from a fresh build")
        else:
            target.write_text(html, encoding="utf-8")
            print(f"wrote {path}")
    if failures:
        for f in failures:
            print("FAIL:", f, file=sys.stderr)
        return 1
    print("site build OK" if check else "site built")
    return 0


if __name__ == "__main__":
    sys.exit(main())
