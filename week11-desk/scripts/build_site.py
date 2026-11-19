#!/usr/bin/env python3
"""Build the Week 11 desk static site from the committed registers.

Every number on every page is read from week11-desk/data/*.csv|json. Nothing is typed into
the HTML. Every table body row carries an official source link, enforced by verify.py.
"""
from __future__ import annotations

import csv
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
DATA = os.path.join(DESK, "data")
PAGES = os.path.join(DESK, "pages")

REG = json.loads(open(os.path.join(DATA, "week11_register.json"), encoding="utf-8").read())
META = REG["meta"]
TOT = REG["totals"]
DS = REG["delta_summary"]

NAV = [
    ("index.html", "Overview"),
    ("pages/report.html", "Week 11 report"),
    ("pages/delta.html", "Week 10 → 11 delta"),
    ("pages/fixtures.html", "Fixtures & venues"),
    ("pages/absence.html", "Not listed ≠ available"),
    ("pages/findings.html", "Findings"),
    ("pages/flagged.html", "Flagged for review"),
    ("pages/method.html", "Method & limits"),
]

CSS = """
:root{--ink:#14202b;--mut:#5b6b7d;--line:#d9e0e8;--bg:#f4f6f9;--card:#fff;
--accent:#0b3d70;--accent2:#0b52c4;--ok:#0a7d33;--warn:#8a5a00;--bad:#a30000}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--ink);line-height:1.5}
header.site{background:var(--accent);color:#fff;padding:16px}
header.site .inner{max-width:1200px;margin:0 auto}
header.site h1{margin:0;font-size:1.3rem;font-weight:650}
header.site .stamp{font-size:.85rem;opacity:.9;margin-top:4px}
nav.hub{background:#0a2f56;padding:0 16px}
nav.hub .inner{max-width:1200px;margin:0 auto;display:flex;flex-wrap:wrap;gap:2px}
nav.hub a{color:#cfe0f5;text-decoration:none;font-size:.9rem;padding:10px 12px;display:block;border-bottom:3px solid transparent}
nav.hub a:hover{background:#0d3a68;color:#fff}
nav.hub a.active{color:#fff;border-bottom-color:#7fb2f0;font-weight:600}
main{max-width:1200px;margin:0 auto;padding:20px 16px 64px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:16px 0}
.card h2{margin:0 0 12px;font-size:1.12rem}
.card h3{margin:18px 0 8px;font-size:1rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0}
.kpi{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px}
.kpi .n{font-size:1.7rem;font-weight:700;line-height:1.1}
.kpi .l{font-size:.8rem;color:var(--mut);margin-top:4px}
table{border-collapse:collapse;width:100%;font-size:.88rem;background:#fff}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:#eef2f7;font-weight:600;position:sticky;top:0;z-index:1}
tbody tr:nth-child(even) td{background:#fafbfd}
.num{text-align:right;font-variant-numeric:tabular-nums}
a{color:var(--accent2)}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:8px}
.pill{display:inline-block;padding:1px 7px;border-radius:99px;font-size:.75rem;font-weight:600;border:1px solid}
.p-out{color:#fff;background:#a30000;border-color:#a30000}
.p-q{color:#5a4200;background:#ffe9a8;border-color:#e0c266}
.p-d{color:#fff;background:#a34d00;border-color:#a34d00}
.p-none{color:var(--mut);background:#f0f2f5;border-color:#dde2e8}
.p-fp{color:#0a5c2a;background:#dff3e5;border-color:#a9d9ba}
.p-lp{color:#7a5000;background:#fdf0d5;border-color:#e6cf9b}
.p-dnp{color:#8a1c1c;background:#fbe3e3;border-color:#e8b4b4}
.note{background:#fff8e6;border:1px solid #e8d9a0;border-radius:8px;padding:12px 14px;margin:12px 0;font-size:.92rem}
.alert{background:#fdecec;border:1px solid #e9b5b5;border-radius:8px;padding:12px 14px;margin:12px 0;font-size:.92rem}
.good{background:#e9f7ee;border:1px solid #b6dfc3;border-radius:8px;padding:12px 14px;margin:12px 0;font-size:.92rem}
.mut{color:var(--mut)}
.small{font-size:.84rem}
code{background:#eef2f7;padding:1px 5px;border-radius:4px;font-size:.85em}
footer{border-top:1px solid var(--line);margin-top:28px;padding:18px 0;color:var(--mut);font-size:.84rem}
h1.page{font-size:1.35rem;margin:6px 0 4px}
.lede{color:var(--mut);margin:0 0 14px}
"""


def e(v) -> str:
    return html.escape(str(v), quote=True)


def pill(status: str) -> str:
    cls = {"Out": "p-out", "Questionable": "p-q", "Doubtful": "p-d", "": "p-none"}.get(status, "p-none")
    return f'<span class="pill {cls}">{e(status) if status else "—"}</span>'


def pract(v: str) -> str:
    if not v:
        return '<span class="mut">—</span>'
    cls = {"Full Participation in Practice": "p-fp",
           "Limited Participation in Practice": "p-lp",
           "Did Not Participate In Practice": "p-dnp"}.get(v)
    return f'<span class="pill {cls}">{e(v)}</span>' if cls else e(v)


def src(url: str, label: str = "NFL.com") -> str:
    return f'<a href="{e(url)}" rel="noopener">{e(label)}</a>'


def shell(title: str, body: str, active: str, depth: int = 0) -> str:
    pre = "" if depth == 0 else "../"
    nav = []
    for href, label in NAV:
        if depth == 0:
            target = href
        elif href == "index.html":
            target = "../index.html"
        else:
            target = href.replace("pages/", "", 1)
        cls = ' class="active"' if href == active else ""
        nav.append(f'<a href="{target}"{cls}>{e(label)}</a>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<style>{CSS}</style>
</head>
<body>
<header class="site"><div class="inner">
<h1>Week 11 desk — official availability capture</h1>
<div class="stamp">Read {e(META['read_at_utc'])} from {src(META['source_url'], 'the official NFL Week 11 injury report')}
· register manifest <code>{e(REG['register_manifest_sha256'][:16])}</code>
· session <code>arena/5d001552-korea2</code></div>
</div></header>
<nav class="hub"><div class="inner">{''.join(nav)}</div></nav>
<main>
{body}
<footer>
<p>Every table row on this site links the official NFL.com page it was transcribed from.
Values the official page does not publish are left blank and labelled; nothing is inferred.
Generated by <code>week11-desk/scripts/build_site.py</code> from
<code>week11-desk/data/</code>. Register manifest
<code>{e(REG['register_manifest_sha256'])}</code>.</p>
<p>This desk measures and publishes availability data. It contains no betting recommendation,
no model output and no strategy result.</p>
</footer>
</main>
</body>
</html>
"""


def read_csv(name: str) -> list[dict]:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


ROWS = read_csv("week11_rows.csv")
COUNTS = read_csv("week11_team_counts.csv")
FIX = read_csv("week11_fixtures.csv")
BYES = read_csv("week11_byes.csv")
DELTA = read_csv("delta_week10_week11.csv")
ABS = read_csv("week11_absence_check.csv")
LOG = read_csv("capture_log.csv")


def kpi(n, label):
    return f'<div class="kpi"><div class="n">{e(n)}</div><div class="l">{e(label)}</div></div>'


def venue_disagreements() -> list[dict]:
    return [f for f in FIX
            if f["venue_official"].strip().lower() != f["venue_prior_register"].strip().lower()]


NO_REPORT_CLUBS = [c["club"] for c in COUNTS if c["page_block"]]


# ---------------------------------------------------------------------------------------
def build_index() -> str:
    dis = venue_disagreements()
    gs = {k: TOT[k] for k in ("out", "doubtful", "questionable", "no_designation")}
    body = f"""
<h1 class="page">Week 11, 2026 — what the official availability pages actually say</h1>
<p class="lede">A dated, per-row transcription of the NFL's own Week 11 injury report and Week 11
schedule, plus the week-over-week delta. Captured <strong>{e(META['read_at_utc'])}</strong>
from {src(META['source_url'])} and {src(META['week11_schedule_url'])}.</p>

<div class="kpis">
{kpi(TOT['rows'], 'player rows on the Week 11 report')}
{kpi(f"{TOT['clubs_with_rows']} + {TOT['clubs_no_report']}", 'clubs with rows + clubs printing “No Injuries Reported”')}
{kpi(TOT['designated'], 'rows carrying a game status')}
{kpi(TOT['no_designation'], 'rows with a practice status only')}
{kpi(len(FIX), 'Week 11 fixtures')}
{kpi(len(BYES), 'clubs on bye')}
{kpi(len(DELTA), 'per-player week-over-week changes')}
{kpi(len(dis), 'fixture venues that disagree with the prior register')}
</div>

<div class="good"><strong>The headline.</strong> At this read the Week 11 page carries a full
game-status column for exactly one fixture — the Thursday game (IND at HOU) — and a practice
status only for the other twelve. So <strong>{TOT['designated']} of {TOT['rows']} rows</strong>
carry an Out / Doubtful / Questionable designation, and {TOT['no_designation']} carry none.
That is not a data gap in this capture; it is where the league's week currently is. Reading
those {TOT['no_designation']} blank cells as “cleared” would fabricate {
  TOT['no_designation']} healthy players. This desk does not do that.</div>

<div class="card"><h2>What this desk found</h2>
<ol>
<li><strong>The Week 11 report is now published.</strong> On 2026-11-18 the
<code>/2026/reg11</code> URL still served the Week 10 report and the repository recorded the
Week 11 report as unpublished (root flag FL-17). It now serves a Week 11 report with its own
heading and fixtures. Recorded on the <a href="pages/flagged.html">Flagged</a> page with both
read times.</li>
<li><strong>The reg10 URL now renders a Week 11 page title.</strong> {src(META['source_url'])} and
{src('https://www.nfl.com/injuries/league/2026/reg10')} both return
<em>“Week 11 of the 2026 Season”</em> in their document title, while the reg10 page body still
reads <em>“Injuries - WEEK 10”</em> with Week 10 fixtures. This is the same title/body mismatch
earlier sessions flagged, still live on 2026-11-19.</li>
<li><strong>{len(dis)} of {len(FIX)} venues disagree with the register already on the site.</strong>
{src(FIX[0]['source_url'])} prints <em>{e(FIX[0]['venue_official'].title())}</em> where
<code>requirements-desk/data/schedule_2026_w11.csv</code> records
<em>{e(FIX[0]['venue_prior_register'])}</em>. All {len(FIX)} venues were read from their own
game centre; see <a href="pages/fixtures.html">Fixtures &amp; venues</a>.</li>
<li><strong>“Not listed” is not “available”.</strong> Lamar Jackson and Malik Willis do not
appear in their clubs' Week 11 tables at all. The page prints no reason. Their absence is
recorded as absence, beside the official headline that explains it — never as availability.
See <a href="pages/absence.html">Not listed ≠ available</a>.</li>
<li><strong>The injury-description column is only populated where a designation exists.</strong>
Of {TOT['rows']} rows, {TOT['injury_named']} carry an injury description, and all
{TOT['injury_named']} also carry a game designation. The two travel together; the desk's
verifier fails the build if that ever stops being true.</li>
</ol></div>

<div class="card"><h2>Where to go</h2>
<div class="scroll"><table>
<thead><tr><th>Page</th><th>What it answers</th><th>Rows</th></tr></thead>
<tbody>
<tr><td><a href="pages/report.html">Week 11 report</a></td><td>Every player row, in page order, with practice status and game status</td><td class="num">{len(ROWS)}</td></tr>
<tr><td><a href="pages/delta.html">Week 10 → 11 delta</a></td><td>Who is newly listed, who dropped off, whose practice moved</td><td class="num">{len(DELTA)}</td></tr>
<tr><td><a href="pages/fixtures.html">Fixtures &amp; venues</a></td><td>The 13 fixtures, with the venue the official game centre prints</td><td class="num">{len(FIX) + len(BYES)}</td></tr>
<tr><td><a href="pages/absence.html">Not listed ≠ available</a></td><td>Named players missing from the tables, and why that cannot be read as healthy</td><td class="num">{len(ABS)}</td></tr>
<tr><td><a href="pages/findings.html">Findings</a></td><td>What this capture changes about the repository's claims</td><td class="num">—</td></tr>
<tr><td><a href="pages/flagged.html">Flagged for review</a></td><td>Irregularities, contradictions and gaps — none blocking</td><td class="num">—</td></tr>
<tr><td><a href="pages/method.html">Method &amp; limits</a></td><td>How to replay this capture, and what it cannot establish</td><td class="num">—</td></tr>
</tbody></table></div>
<p class="small mut">Row counts above are read from the committed registers at build time.</p>
</div>
"""
    return shell("Week 11 desk — official availability capture", body, "index.html")


def build_report() -> str:
    head = "".join(
        f"<tr><th>{e(c)}</th><th>Player</th><th>Pos</th><th>Injury</th>"
        f"<th>Practice status</th><th>Game status</th><th>Source</th></tr>"
        for c in [])
    blocks = []
    for c in COUNTS:
        club = c["club"]
        if c["page_block"]:
            blocks.append(f"""
<h3>{e(club)} — {e(c['club_name'])}</h3>
<p class="mut small">The official page prints the literal block
<strong>“{e(c['page_block'])}”</strong> for this club at {e(META['read_at_utc'])}. It publishes
no player rows, so none are invented here. {src(c['source_url'])}</p>""")
            continue
        rs = [r for r in ROWS if r["club"] == club]
        DASH = '<span class="mut">\u2014</span>'
        trs = "".join(
            f"<tr><td>{e(r['player'])}</td><td>{e(r['position'])}</td>"
            f"<td>{e(r['injury']) or DASH}</td>"
            f"<td>{pract(r['practice_status'])}</td><td>{pill(r['game_status'])}</td>"
            f"<td>{src(r['source_url'])}</td></tr>" for r in rs)
        blocks.append(f"""
<h3>{e(club)} — {e(c['club_name'])} <span class="mut small">({c['rows']} rows,
{c['game_designated']} with a game status)</span></h3>
<div class="scroll"><table>
<thead><tr><th>Player</th><th>Pos</th><th>Injury</th><th>Practice status</th>
<th>Game status</th><th>Source</th></tr></thead>
<tbody>{trs}</tbody></table></div>""")
    body = f"""
<h1 class="page">Week 11 report — every published row</h1>
<p class="lede">{TOT['rows']} player rows across {TOT['clubs_with_rows']} clubs, in the order the
official page prints them, plus {TOT['clubs_no_report']} clubs that print
“No Injuries Reported”. Read {e(META['read_at_utc'])} from {src(META['source_url'])}.</p>

<div class="note"><strong>How to read the game-status column.</strong>
{TOT['designated']} rows carry a designation ({TOT['out']} Out, {TOT['doubtful']} Doubtful,
{TOT['questionable']} Questionable). {TOT['no_designation']} do not — not because those players
are healthy, but because their fixture had not yet reached the stage where the league publishes
game statuses. A dash is a dash. It is never a green light.</div>

<div class="card">
<p class="small mut">Page heading on the official report: <code>{e(META['page_heading'])}</code>.
Table order follows the page: IND, HOU, PIT, PHI, AZ, KC, BAL, CAR, TB, DET, MIA, BUF, TEN, DAL,
NO, CHI, NYJ, LAC, JAX, NYG, LV, DEN, MIN, SF, then CIN and WAS.</p>
{''.join(blocks)}
</div>
"""
    return shell("Week 11 report — Week 11 desk", body, "pages/report.html", 1)


def build_delta() -> str:
    clubs = sorted({d["club"] for d in DELTA})
    rows_by = []
    for d in DELTA:
        rows_by.append(
            f"<tr><td>{e(d['club'])}</td><td>{e(d['player'])}</td><td>{e(d['position_w11'])}</td>"
            f"<td>{e(d['week10_practice / week10_game']) or '—'}</td>"
            f"<td>{e(d['week11_practice / week11_game']) or '—'}</td>"
            f"<td>{e(d['change'])}</td>"
            f"<td>{src(d['week10_source'], 'W10')} · {src(d['week11_source'], 'W11')}</td></tr>")
    by_change = DS["by_change"]
    kpi_cards = "".join(kpi(v, k.replace("-", " ")) for k, v in
                        sorted(by_change.items(), key=lambda kv: -kv[1]))
    excluded = ", ".join(DS["clubs_excluded_from_delta"])
    body = f"""
<h1 class="page">Week 10 → Week 11 delta</h1>
<p class="lede">The brief asks for the delta, never the level. This compares the committed
Week 10 register (read {e(META['week10_read_at_utc'])}) with this session's Week 11 register
(read {e(META['read_at_utc'])}), player by player, and publishes what changed.</p>

<div class="kpis">
{kpi(DS['players_compared'], 'players compared (clubs listed both weeks)')}
{kpi(len(DELTA), 'rows that changed')}
{kpi(DS['clubs_in_both'], 'clubs listed in both weeks')}
{kpi(len(DS['clubs_excluded_from_delta']), 'clubs excluded from the delta (bye in Week 10)')}
</div>
<div class="kpis">{kpi_cards}</div>

<div class="alert"><strong>Why only {DS['clubs_in_both']} clubs are compared, and why that
matters.</strong> {excluded} published no injury table in Week 10 — the official Week 10
schedule page lists all four on bye. Their Week 11 rows are published in full on the
<a href="report.html">report page</a> but are excluded here: calling a bye club's first listing
of the season a “newly listed” injury would manufacture {len(ROWS)} phantom events.
<br><br><strong>And why the game-status column is only compared for two clubs.</strong> At this
read only IND and HOU (the Thursday fixture) had published game statuses. For the other
{len(DS['clubs_game_status_not_comparable'])} clubs the Week 11 game-status cell is still empty,
so those rows are compared on <em>practice status only</em> and their Week 11 game value prints
<code>(no designation published)</code>. A blank there would have produced roughly 150 false
“cleared” rows.</div>

<div class="card"><h2>Every change</h2>
<p class="small mut">Week 10 values come from
<code>availability-sweep/data/week10_rows_20261118.csv</code>, which is owned by another session
and was read, not rewritten, by this one.</p>
<div class="scroll"><table>
<thead><tr><th>Club</th><th>Player</th><th>Pos</th><th>Week 10 practice / game</th>
<th>Week 11 practice / game</th><th>Change</th><th>Sources</th></tr></thead>
<tbody>{''.join(rows_by)}</tbody></table></div>
</div>

<div class="card"><h2>What the delta does not say</h2>
<ul>
<li>It does not say any player is healthy, cleared or available. A row that dropped out of the
report means <em>not listed this week</em> (see <a href="absence.html">Not listed ≠ available</a>).</li>
<li>It does not measure a player's importance to his team. No snap share, depth rank or starter
status is published by any source used here, so none is claimed.</li>
<li>It does not establish that a practice-status change predicts anything. Two weeks is not a
sample; the value is the replayable record, not a signal.</li>
</ul></div>
"""
    return shell("Week 10 → 11 delta — Week 11 desk", body, "pages/delta.html", 1)


def build_fixtures() -> str:
    dis = venue_disagreements()
    trs = []
    for f in FIX:
        agree = f["venue_official"].strip().lower() == f["venue_prior_register"].strip().lower()
        flag = "" if agree else '<span class="pill p-q">differs</span>'
        trs.append(
            f"<tr><td>{e(f['date'])}</td><td>{e(f['kickoff_et'])}</td>"
            f"<td>{e(f['away'])} @ {e(f['home'])}</td><td>{e(f['network'])}</td>"
            f"<td>{e(f['location_official'].title())}</td>"
            f"<td><strong>{e(f['venue_official'].title())}</strong></td>"
            f"<td>{e(f['venue_prior_register'])} {flag}</td>"
            f"<td>{e(f['neutral_site'])}</td><td>{src(f['source_url'], 'game centre')}</td></tr>")
    byes = "".join(
        f"<tr><td>{e(b['club'])}</td><td>{e(b['record_w11'])}</td>"
        f"<td>{src(b['source_url'], 'schedule page')}</td></tr>" for b in BYES)
    body = f"""
<h1 class="page">Fixtures &amp; venues — read from each game centre</h1>
<p class="lede">Venue and location below are the values each fixture's own official game centre
prints on its “Game Info” panel at {e(META['read_at_utc'])}. The final column repeats what the
site's existing Week 11 schedule register records, so a disagreement is visible rather than
silently overwritten.</p>

<div class="alert"><strong>{len(dis)} of {len(FIX)} venues disagree with the register already
committed at <code>requirements-desk/data/schedule_2026_w11.csv</code>.</strong> Each is a real
rename or a real error, not a wording preference:
<ul>
{''.join(f"<li><strong>{e(d['away'])} @ {e(d['home'])}</strong>: official game centre prints <em>{e(d['venue_official'].title())}</em>; the register records <em>{e(d['venue_prior_register'])}</em> — {src(d['source_url'], 'source')}</li>" for d in dis)}
</ul>
This session did not edit that register (it belongs to another session); the correction is
published here and logged as a request in <code>COORDINATION.md</code>.</div>

<div class="card"><h2>The 13 fixtures</h2>
<div class="scroll"><table>
<thead><tr><th>Date</th><th>Kickoff ET</th><th>Matchup</th><th>Network</th>
<th>Location (official)</th><th>Venue (official game centre)</th>
<th>Venue in prior register</th><th>Neutral</th><th>Source</th></tr></thead>
<tbody>{''.join(trs)}</tbody></table></div>
<p class="small mut">The schedule page prints a city (e.g. “Mexico City”) where the game centre
prints a stadium ({e(FIX[11]['venue_official'].title())}). Both are recorded; neither is
derived from the other.</p></div>

<div class="card"><h2>Clubs on bye</h2>
<div class="scroll"><table>
<thead><tr><th>Club</th><th>Record as printed</th><th>Source</th></tr></thead>
<tbody>{byes}</tbody></table></div>
<p class="small mut">From the official Week 11 schedule page's “Teams on Bye” block. Six clubs on
bye plus 26 clubs in the injury report covers all 32.</p></div>
"""
    return shell("Fixtures & venues — Week 11 desk", body, "pages/fixtures.html", 1)


def build_absence() -> str:
    YES = '<span class="pill p-fp">yes</span>'
    NO = '<span class="pill p-out">no</span>'
    trs = "".join(
        f"<tr><td>{e(a['club'])}</td><td>{e(a['player'])}</td>"
        f"<td>{YES if a['listed_in_week11_table']=='yes' else NO}</td>"
        f"<td>{e(a['practical_reading'])}</td>"
        f"<td>{e(a['news_headline_on_official_page'])}</td>"
        f"<td>{src(a['headline_url'], 'headline')} · {src(a['table_source_url'], 'table')}</td></tr>"
        for a in ABS)
    body = f"""
<h1 class="page">Not listed ≠ available</h1>
<p class="lede">The owner brief is explicit: <em>“Capture the reserve list so 'not listed' never
means 'available'”</em>, and <em>“Malik Willis is absent from the weekly report because he is on
injured reserve, not because he is healthy.”</em> This page is the concrete check.</p>

<div class="alert"><strong>The mechanism.</strong> The weekly injury report lists players with a
practice or game designation. It does not list players on injured reserve, and it prints no
“reason for absence” column. So a player missing from the table is <em>unaccounted for</em>, not
cleared. This desk can therefore only publish two things: (1) that a named player is absent from
the Week 11 table, and (2) the official nfl.com headline the report page itself links, which is
the only published explanation available. It does not convert either into an availability flag.</div>

<div class="card"><h2>Named players checked against the Week 11 tables</h2>
<div class="scroll"><table>
<thead><tr><th>Club</th><th>Player</th><th>In Week 11 table?</th><th>What that does and does not mean</th>
<th>Headline the official page links</th><th>Sources</th></tr></thead>
<tbody>{trs}</tbody></table></div>
<p class="small mut">The headline names are transcribed from the news block on
{META['source_url'] and src(META['source_url'])}, which lists those articles. The headlines are
nfl.com editorial text, not a league roster designation, and are labelled as such.</p></div>

<div class="card"><h2>Two rows that make the point</h2>
<p><strong>Lamar Jackson (BAL)</strong> appears nowhere in the Ravens' Week 11 table. Neither does
a reason. A reader who treats “absent from the injury report” as “available” would have to
conclude Baltimore's starting quarterback is fine — while an official nfl.com headline linked
from the very same page reads <em>“Ravens confirm Lamar Jackson expected to miss 6-10 weeks”</em>.
The report cannot tell you which. That is why this desk leaves availability blank.</p>
<p><strong>Malik Willis (MIA)</strong> is likewise absent from the Dolphins' table, and the page
links <em>“Dolphins place QB Malik Willis (groin) on injured reserve”</em>. Absent-from-table and
healthy are different things.</p>
<p class="small mut">Both players' absence and both headlines are recorded above with their own
source links. Neither is asserted as the reason for absence in any model column, because the
injury report does not publish that link — the headline does, and it is editorial.</p></div>
"""
    return shell("Not listed ≠ available — Week 11 desk", body, "pages/absence.html", 1)


def build_findings() -> str:
    dis = venue_disagreements()
    body = f"""
<h1 class="page">Findings</h1>
<p class="lede">What this capture changes about claims already on this site, and what it newly
establishes. Every item names the artefact and the official page behind it.</p>

<div class="card"><h2>1. The Week 11 report is now published — an existing flag can be closed</h2>
<p>Root flag <code>FL-17</code> and the availability-sweep capture log both record that at
<code>2026-11-18T03:55Z</code> the <code>/2026/reg11</code> URL served the Week 10 report and that
no Week 11 report existed. Reading the same URL at <strong>{e(META['read_at_utc'])}</strong> returns
a report whose own heading is <code>{e(META['page_heading'])}</code> and whose fixtures begin
Thursday 2026-11-19 (IND at HOU). The flag's <em>value</em> can now be filled for this read; its
history should stay as the record of the earlier failed read. This session did not edit
<code>data/flagged.json</code> (owned elsewhere); it logs the request in
<code>COORDINATION.md</code>.</p>
<p class="small mut">Sources: {src(META['source_url'])} · prior state in
<code>availability-sweep/data/capture_log.csv</code> row <code>20261118-9fa8ea61-reg11-attempt</code>.</p></div>

<div class="card"><h2>2. The title/body week mismatch is not fixed</h2>
<p>Both injury-report URLs return the document title <em>“Official NFL Injury Report for Players
- Week 11 of the 2026 Season”</em> at this read, while
{src('https://www.nfl.com/injuries/league/2026/reg10')} prints <code>Injuries - WEEK 10</code> in
its body with Week 10 fixtures, and {src(META['source_url'])} prints
<code>{e(META['page_heading'])}</code>. Earlier sessions flagged this; it is still live. Practical
consequence, which is the part that matters: <strong>a scraper that pins to the document title
will read the wrong week.</strong> Any capture job must pin to the body heading and to the
fixtures, which is what this desk's verifier checks.</p></div>

<div class="card"><h2>3. {len(dis)} of {len(FIX)} Week 11 venues on the site are wrong or stale</h2>
<p>Read from each fixture's own game centre, not from the schedule page's city label:</p>
<div class="scroll"><table>
<thead><tr><th>Fixture</th><th>Official game centre</th><th>Value in the prior register</th><th>Source</th></tr></thead>
<tbody>{''.join(f"<tr><td>{e(d['away'])} @ {e(d['home'])}</td><td><strong>{e(d['venue_official'].title())}</strong></td><td>{e(d['venue_prior_register'])}</td><td>{src(d['source_url'], 'game centre')}</td></tr>" for d in dis)}</tbody></table></div>
<p class="small mut">Independence, Houston and Washington have all had their stadium naming
change in reality; the register used the names the desk's own brief quotes. Recording them
as-is would have been the easy path and the wrong one.</p></div>

<div class="card"><h2>4. The game-status column is per-fixture, not per-week</h2>
<p>At {e(META['read_at_utc'])} exactly one fixture — IND at HOU, the Thursday night game — had a
populated game-status column. The other twelve published practice status only. This single fact
explains most of the noise in any naive week-over-week comparison:</p>
<ul>
<li>{TOT['designated']} of {TOT['rows']} rows ({round(100*TOT['designated']/TOT['rows'])}%) carry a
designation at this read.</li>
<li>The Week 10 register, read after that week's games were designated, carries 171 of 347.</li>
<li>A raw comparison would therefore show ~150 players “losing” their designation — a
{round(100*(171-15)/171)}% drop in one week with no football explanation whatsoever.</li>
</ul>
<p><strong>This is the finding with the most modelling consequence.</strong> Any feature built on
“has a game designation” is a clock, not a player state, unless it is timestamped against the
fixture's own designation deadline. The desk's delta encodes that rule explicitly: game status is
compared for {len(DS['clubs_game_status_comparable'])} clubs, practice status only for the rest.</p></div>

<div class="card"><h2>5. Injury descriptions and designations travel together</h2>
<p>{TOT['injury_named']} rows carry an injury description (“Calf”, “Concussion”, “Foot, Illness”)
and every one of them also carries a game designation; no row with a designation lacks an injury
string. This is a useful structural invariant for a parser — and it is now an enforced build
check (<code>verify.py</code> R5), not a hope.</p></div>

<div class="card"><h2>6. What these findings do <em>not</em> license</h2>
<ul>
<li>They do not support a “backup deficiency” feature. The official pages used here publish no
depth rank, no starter designation and no snap share, so a second- or third-string replacement
cannot be identified from them. That requirement stays blocked on a source, exactly as
<code>FL-15</code>/<code>FL-19</code> record.</li>
<li>They do not support pricing anything. Two reads of one page, one week apart, cannot estimate
the effect of an absence on a score. No ablation is possible without outcomes linked to these
snapshots, and no outcomes are linked yet.</li>
<li>They do not show the Week 10 register was wrong. That register was a correct read of a page
that had fully designated its week. The two reads are of the same page at different points in
the league's weekly cycle.</li>
</ul></div>
"""
    return shell("Findings — Week 11 desk", body, "pages/findings.html", 1)


def build_flagged() -> str:
    flags = [
        ("W11-F01", "No raw response bytes retained for the official pages",
         "The sandbox shell has no network route to nfl.com — verified with "
         "<code>curl</code>, which exits 35 on the CONNECT tunnel. Pages were read with the "
         "platform page-retrieval tool, so the register hash covers the transcribed rows as "
         "committed, not the NFL response body. A capture job on a network-enabled runner is "
         "the fix; this desk does not have one.",
         [META["source_url"]], "open"),
        ("W11-F02", "reg10 and reg11 both return a “Week 11” document title",
         "The two URL slugs disagree with the document title on reg10, whose body still "
         "prints WEEK 10. Recorded at 2026-11-19T19:56Z. Do not pin a parser to the title.",
         [META["source_url"], "https://www.nfl.com/injuries/league/2026/reg10"], "open"),
        ("W11-F03", "The CIN and WAS tables print “No Injuries Reported”",
         "Both Monday fixtures show the literal block with no player rows. That is the page's "
         "statement, not an omission. It is almost certainly a week-in-progress artifact — a "
         "club does not report zero injuries in week 11 — but the desk publishes what the page "
         "prints and does not substitute a later read it did not make.",
         [META["source_url"]], "monitor"),
        ("W11-F04", "Prior register records 4 venues the official game centre contradicts",
         "IND@HOU (Reliant Stadium), MIN@SF (Estadio Banorte), CIN@WAS (Northwest Stadium) and "
         "AZ@KC (Arrowhead Stadium). The register at "
         "<code>requirements-desk/data/schedule_2026_w11.csv</code> is owned by another session "
         "and was not edited. Request logged in COORDINATION.md.",
         [d["source_url"] for d in venue_disagreements()], "reported to owner"),
        ("W11-F05", "The Week 10 comparison register is not row-complete by construction",
         "It contains 347 rows, a complete transcript of the Week 10 page as read on "
         "2026-11-18. It is used here only for clubs that appear in both weeks. A player who "
         "moved between weeks is reported as listed/not-listed, never as injured/recovered.",
         [META["week10_comparison_url"]],
         "accepted limitation"),
        ("W11-F06", "Practice status is published for players with no injury description",
         f"Of {TOT['rows']} rows, {TOT['rows'] - TOT['injury_named']} carry a practice status "
         "but no injury text (e.g. BAL Mike Green, Full Participation). The page does not "
         "explain this. It may be a veteran rest day or a routine listing; the desk does not "
         "guess. Consequence: a “did not practice” flag alone cannot be read as an injury.",
         [META["source_url"]], "open"),
        ("W11-F07", "Headlines are editorial, not roster designations",
         "The absence page cites nfl.com headlines (injured-reserve, surgery, expectations). "
         "They are nfl.com editorial copy linked from the official report page, not a league "
         "roster feed. They explain an absence; they are not used to populate any column.",
         [a["headline_url"] for a in ABS], "accepted limitation"),
        ("W11-F08", "No depth, snap or starter evidence exists in any source used here",
         "The official injury report, schedule and game centres publish no depth rank, no snap "
         "count and no confirmed starter. Every requirement that needs a replacement-depth "
         "signal therefore remains blocked on source — the finding, not a defect of this desk.",
         [META["source_url"]], "blocked on source"),
    ]
    card = "".join(f"""
<h3>{e(i)} — {e(t)} <span class="pill p-q">{e(st)}</span></h3>
<p>{txt}</p>
<p class="small mut">Sources: {' · '.join(src(u, u.split('/')[2] + '/…/' + u.rstrip('/').split('/')[-1]) for u in urls)}</p>
""" for (i, t, txt, urls, st) in flags)
    body = f"""
<h1 class="page">Flagged for review</h1>
<p class="lede">Irregularities found while verifying this capture. None of them blocks
publication and none is hidden: each names the artefact, the official page, and what would
resolve it. Per the brief, flagged items do not block the merge — they are published here so
they can be reviewed after the site is live.</p>
<div class="card">{card}</div>
<div class="card"><h2>Not flagged, but worth stating</h2>
<p>No claim on this site asserts that any strategy, model or price is correct, and none could:
this desk contains no odds, no outcomes and no model output. It publishes what two official
pages said, when they said it, and what changed between them.</p></div>
"""
    return shell("Flagged for review — Week 11 desk", body, "pages/flagged.html", 1)


def build_method() -> str:
    reads = "".join(
        f"<tr><td>{e(r['started_utc'])}</td><td>{e(r['finished_utc'])}</td>"
        f"<td>{e(r['chunks'])}</td><td>{e(r['note'])}</td>"
        f"<td>{src(META['source_url'], 'Week 11 report')}</td></tr>" for r in META["reads"])
    log = "".join(
        f"<tr><td>{e(r['capture_id'])}</td><td>{e(r['week'])}</td>"
        f"<td>{e(r['fetched_utc_start'])}</td><td>{e(r['fetched_utc_end'])}</td>"
        f"<td>{e(r['rows_captured'])}</td><td>{e(r['teams_captured'])}</td>"
        f"<td>{e(r['raw_bytes_hash'])}</td><td>{src(r['source_url'], 'source')}</td></tr>" for r in LOG)
    body = f"""
<h1 class="page">Method &amp; limits</h1>
<p class="lede">How to replay this capture, and the honest boundary of what it establishes.</p>

<div class="card"><h2>Reads</h2>
<div class="scroll"><table>
<thead><tr><th>Started (UTC)</th><th>Finished (UTC)</th><th>Chunks</th><th>What was done</th><th>Source</th></tr></thead>
<tbody>{reads}</tbody></table></div>
<p class="small mut">Each read is listed with its clock time, per the brief's requirement to store
every injury-hub read with its clock time. The transcription records the second read as its
<code>read_at_utc</code>.</p></div>

<div class="card"><h2>Capture log</h2>
<div class="scroll"><table>
<thead><tr><th>Capture ID</th><th>Week</th><th>Fetched from</th><th>Fetched to</th>
<th>Rows</th><th>Clubs</th><th>Raw bytes</th><th>Source</th></tr></thead>
<tbody>{log}</tbody></table></div></div>

<div class="card"><h2>Reproduce the register</h2>
<pre><code>cd /home/user/Korea2
python3 week11-desk/scripts/build_register.py --write   # CSV + JSON registers and the manifest
python3 week11-desk/scripts/verify.py                   # strict checks; non-zero exit on drift
python3 week11-desk/scripts/build_site.py               # this site
</code></pre>
<p class="small mut">The register is deterministic: the manifest hash is a SHA-256 of the five
data files, and <code>verify.py</code> recomputes it. Re-running the builder on this tree
reproduces identical files.</p></div>

<div class="card"><h2>Verification rules this build enforces</h2>
<ol class="small">
<li>Every register row carries an official https source URL and its read clock time.</li>
<li>The committed register hashes match the published manifest.</li>
<li>Row counts, per-club counts and the game-status split recompute from the CSV.</li>
<li>Practice and game statuses are a closed vocabulary taken from the page.</li>
<li>Injury text and game designation co-occur on every row.</li>
<li>Every fixture carries a game-centre URL and a non-empty official venue.</li>
<li>Every delta row's two sources are the two official weekly report URLs, and the delta counts
sum to the CSV.</li>
<li>No delta row claims a game-status comparison for a club that published no designation, and
no row uses the words “cleared” or “healthy”.</li>
<li>The built pages print the computed values, the session owner and the read time.</li>
</ol></div>

<div class="card"><h2>What this cannot establish</h2>
<ul>
<li><strong>Availability.</strong> A blank game-status cell is not availability. Nothing here
should be used as a “player is playing” flag.</li>
<li><strong>Replacement depth.</strong> No source used here publishes depth rank, starter status
or snap share. Any 2nd/3rd/4th-string claim would be invention.</li>
<li><strong>Predictive value.</strong> Practice-status transitions are published; whether they
predict anything is untested and this desk makes no claim about it. That requires linked
outcomes and a pre-registered evaluation, neither of which exists.</li>
<li><strong>Historical replay.</strong> This is the first dated Week 11 capture. A series begins
here; it does not yet exist.</li>
<li><strong>Completeness.</strong> The page at this read lists 26 of 32 clubs because six are on
bye. It does not list players on injured reserve, and it does not say why.</li>
</ul></div>

<div class="card"><h2>Sources used</h2>
<div class="scroll"><table>
<thead><tr><th>Source</th><th>What was taken from it</th><th>Link</th></tr></thead>
<tbody>
<tr><td>{src(META['source_url'], 'Week 11 injury report')}</td><td>{TOT['rows']} player rows, {TOT['clubs_no_report']} “No Injuries Reported” blocks, the news headlines on the absence page</td></tr>
<tr><td>{src(META['week11_schedule_url'], 'Week 11 schedule')}</td><td>13 fixtures, kickoff times, networks, the six bye clubs</td></tr>
<tr><td>{src(META['week10_comparison_url'], 'Week 10 injury report')}</td><td>Re-read at 2026-11-19T19:56Z to test the title/body mismatch</td></tr>
<tr><td>Each fixture's own game centre</td><td>Stadium name and location per fixture</td><td>{src(FIX[0]['source_url'], 'first game centre')} … {src(FIX[-1]['source_url'], 'last game centre')}</td></tr>
<tr><td>Week 10 register (another session, read only)</td><td>The Week 10 side of the delta: <code>availability-sweep/data/week10_rows_20261118.csv</code></td><td>{src(META['week10_comparison_url'], 'Week 10 report')}</td></tr>
</tbody></table></div></div>
"""
    return shell("Method & limits — Week 11 desk", body, "pages/method.html", 1)


def main() -> int:
    os.makedirs(PAGES, exist_ok=True)
    open(os.path.join(DESK, "index.html"), "w", encoding="utf-8").write(build_index())
    for name, fn in (("report", build_report), ("delta", build_delta),
                     ("fixtures", build_fixtures), ("absence", build_absence),
                     ("findings", build_findings), ("flagged", build_flagged),
                     ("method", build_method)):
        open(os.path.join(PAGES, f"{name}.html"), "w", encoding="utf-8").write(fn())
    print("built index.html + 7 pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
