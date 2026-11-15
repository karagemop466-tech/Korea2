#!/usr/bin/env python3
"""Build injury-report-w10/index.html from the CSV registers. Fails loudly on any check.

Reads only the CSVs in data/. Writes only index.html. No network access.
"""
import csv, html, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
errors = []

def read(name):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

rows = read("week10_rows_read.csv")
counts = read("week10_team_counts_manual.csv")
news = read("week10_reserve_and_news.csv")

# ---- checks -------------------------------------------------------------
for r in rows + counts + news:
    url = r.get("source_url") or r.get("source_url")
    if not url or not url.startswith("https://www.nfl.com/"):
        errors.append(f"row without official nfl.com source: {r}")
for r in rows:
    if not r["fetched_utc"].endswith("Z"):
        errors.append(f"bad timestamp: {r['player']}")
    if r["game_status"] == "" and r["injury"] and r["practice_status"].startswith("Did Not"):
        errors.append(f"DNP with injury but blank game status (unexpected pattern): {r['player']}")

# The three Lions rows the brief named must read Out on the live page
lions_out = {r["player"]: r["game_status"] for r in rows if r["team"] == "DET"
             and r["player"] in ("Kerby Joseph", "Cade Mays", "D.J. Reed")}
if lions_out != {"Kerby Joseph": "Out", "Cade Mays": "Out", "D.J. Reed": "Out"}:
    errors.append(f"Lions designations mismatch: {lions_out}")

def team_rows(team):
    return [r for r in rows if r["team"] == team]

# Where a team was transcribed in full, its row count must equal the team count
for team in sorted({r["team"] for r in rows}):
    c = next((int(x["listed_players_manual_count"]) for x in counts if x["team"] == team), None)
    if c is None:
        errors.append(f"transcribed team {team} missing from counts")
    elif len(team_rows(team)) != c:
        errors.append(f"{team}: transcribed {len(team_rows(team))} rows vs counted {c}")

if len(counts) != 28:
    errors.append(f"expected 28 teams on the Week 10 report, found {len(counts)}")
if len({x['team'] for x in counts}) != 28:
    errors.append("duplicate team in counts")

if errors:
    print("BUILD FAILED:")
    for e in errors:
        print(" -", e)
    sys.exit(1)

# ---- render -------------------------------------------------------------
E = html.escape
def link(url, label="NFL.com"):
    return f'<a href="{E(url)}" rel="noopener">{E(label)}</a>'

def table(headers, body):
    th = "".join(f"<th>{E(h)}</th>" for h in headers)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in body)
    return f"<div class='tw'><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>"

rows_html = table(
    ["Team", "Player", "Pos", "Injury", "Practice status", "Game status", "Source", "Fetched (UTC)"],
    [[E(r["team"]), E(r["player"]), E(r["position"]), E(r["injury"]) or "<em>blank on report</em>",
      E(r["practice_status"]), E(r["game_status"]) or "<em>blank on report</em>",
      link(r["source_url"]), E(r["fetched_utc"])] for r in rows])

count_html = table(
    ["Team", "Opponent", "Listed players (manual count)", "Source", "Fetched (UTC)"],
    [[E(r["team"]), E(r["opponent"]), E(r["listed_players_manual_count"]),
      link(r["source_url"]), E(r["fetched_utc"])] for r in counts])

news_html = table(
    ["Category", "Player", "Team", "What NFL.com reports", "On the Week 10 report?", "Note", "Source"],
    [[E(r["category"]), E(r["player"]), E(r["team"]), E(r["claim_from_nfl_com"]),
      E(r["on_week10_report"]), E(r["note"]), link(r["source_url"], "NFL.com article")] for r in news])

flagged = [
 ("F-W10-1", "Cincinnati is listed with 9 players, not 4. Four of them carry a game status: Kyle Dugger (Out); Jalen Davis, Andrei Iosivas and Brian Parker II (Doubtful). The earlier count of 4 appears to mean players with a game status.", "https://www.nfl.com/injuries/league/2026/REG10"),
 ("F-W10-2", "The brief's totals (279 rows, 2 no-injury sections) could not be reproduced. A manual count of the live page gives 347 listed players across 28 teams. The manual count was not checked by a script, and the counting definition behind 279 is unknown. Neither figure is published as verified.", "https://www.nfl.com/injuries/league/2026/REG10"),
 ("F-W10-3", "TreVeyon Henderson: NFL.com reports a reserve move (illness) on Sat Nov 14, but the Week 10 report still lists him Out, Did Not Participate.", "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-saturday-nov-14"),
 ("F-W10-4", "Puka Nacua: listed Did Not Participate with a blank game status, while NFL.com says he is likely to go on injured reserve. IR is not confirmed in that article.", "https://www.nfl.com/news/rams-wr-puka-nacua-likely-to-be-placed-on-injured-reserve-with-turf-toe-sprained-mcl-and-pcl"),
 ("F-W10-5", "Only 3 of 28 team tables (DET, SEA, CIN) were transcribed row by row. The other 25 teams have counts only. Per-team counts are a manual count from page text and need a script re-check.", "https://www.nfl.com/injuries/league/2026/REG10"),
 ("F-W10-6", "CHI, DEN, PHI and TB do not appear on the report. This page does not verify whether they had a bye in Week 10. Not inferred here.", "https://www.nfl.com/schedules/2026/by-week/week-10"),
 ("F-W10-7", "Capture method: the sandbox shell cannot reach nfl.com. The page was read through the fetch tool, so no raw response hash exists for this capture. The fetch time is recorded; the bytes are not.", "https://www.nfl.com/injuries/league/2026/REG10"),
]
flag_html = "".join(f"<li><strong>{E(i)}</strong> {E(t)} <br>{link(u, 'Source')}</li>" for i, t, u in flagged)

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Week 10 official injury report: re-verification</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#1d2330;background:#f6f7f9;line-height:1.45}}
header{{background:#1d2330;color:#fff;padding:20px 28px}} header a{{color:#9cd1ff}}
main{{max-width:1200px;margin:0 auto;padding:20px 28px}}
h1{{margin:0 0 6px;font-size:1.6rem}} h2{{margin:28px 0 8px;font-size:1.2rem}}
.card{{background:#fff;border:1px solid #dde1e8;border-radius:8px;padding:14px 18px;margin:12px 0}}
.tw{{overflow-x:auto;background:#fff;border:1px solid #dde1e8;border-radius:8px}}
table{{border-collapse:collapse;width:100%;font-size:.9rem}}
th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid #eef0f3;vertical-align:top}}
th{{background:#f0f3f7;position:sticky;top:0}}
em{{color:#8a4b00}} a{{color:#0b5cad}} .warn{{border-left:4px solid #c77700}}
</style></head><body>
<header><h1>Week 10 official injury report: re-verification</h1>
<div>Source: <a href="https://www.nfl.com/injuries/league/2026/REG10">NFL.com Week 10 2026 injury report</a> · Read 2026-11-15 18:08 UTC via the fetch tool · Branch <code>arena/a24825d2-korea2</code></div>
</header><main>
<div class="card warn"><strong>What this page is.</strong> A row-level re-read of the official Week 10 page, with the reserve and news checks the brief asked for. Every row links its source. Blank cells are shown as blank, not filled. Full team tables are published for 3 of 28 teams; the rest show counts only.
<br><strong>What it is not.</strong> It is not a point-in-time archive. The sandbox cannot capture raw bytes from nfl.com, so no hash of the official response is recorded (see F-W10-7).</div>

<h2>1. Rows read verbatim (Lions, Seahawks, Bengals)</h2>
{rows_html}

<h2>2. Per-team listed-player counts (28 teams)</h2>
<div class="card">Counts are manual, from the page text, and are not script-verified. Sum of counts: {sum(int(c['listed_players_manual_count']) for c in counts)}.</div>
{count_html}

<h2>3. Reserve list, news and post-report events</h2>
<div class="card">The weekly report does not list players on injured reserve. A missing row means reserve or other removal, not health. Each row below is taken from an NFL.com article.</div>
{news_html}

<h2>4. Flagged for review</h2>
<div class="card"><ul>{flag_html}</ul></div>
<p><a href="../COORDINATION.md">Coordination board</a> · <a href="../index.html">Repository home</a></p>
</main></body></html>"""

(ROOT / "index.html").write_text(page, encoding="utf-8")
print(f"built index.html: {len(rows)} verbatim rows, {len(counts)} team counts, {len(news)} news rows, {len(flagged)} flags; all checks passed")
