#!/usr/bin/env python3
"""Build the Week 11 availability hub from committed inputs only.

Inputs (all committed):
  injury-capture/manifests/reg11_2026_*.json   runner manifests (hash, time, per-table counts, no names)
  availability-w11/data/schedule_w11.json      official schedule facts, transcribed with source URLs
  availability-w11/data/flags.json             review flags with sources

Outputs:
  availability-w11/index.html, pages/*.html, assets/style.css
  availability-w11/data/clubs_w11.csv, data/captures_w11.csv

Rules: no player names are read or written; a blank stays blank; nothing is inferred.
The script stops (exit 2) if the two Week 11 reads disagree on hash or per-table counts.
"""
import csv
import glob
import html
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO = os.path.abspath(os.path.join(ROOT, ".."))
REPORT_URL = "https://www.nfl.com/injuries/league/2026/reg11"
SCHEDULE_URL = "https://www.nfl.com/schedules/2026/by-week/week-11"

PRACTICE = {
    "Did Not Participate In Practice": "DNP",
    "Limited Participation in Practice": "LP",
    "Full Participation in Practice": "FP",
}
GAME = {"Out": "Out", "Doubtful": "Doubtful", "Questionable": "Questionable", "": "blank"}

CLUB_NAMES = {
    "IND": "Colts", "HOU": "Texans", "PIT": "Steelers", "PHI": "Eagles", "ARI": "Cardinals", "KC": "Chiefs",
    "BAL": "Ravens", "CAR": "Panthers", "TB": "Buccaneers", "DET": "Lions", "MIA": "Dolphins", "BUF": "Bills",
    "TEN": "Titans", "DAL": "Cowboys", "NO": "Saints", "CHI": "Bears", "NYJ": "Jets", "LAC": "Chargers",
    "JAX": "Jaguars", "NYG": "Giants", "LV": "Raiders", "DEN": "Broncos", "MIN": "Vikings", "SF": "49ers",
    "CIN": "Bengals", "WAS": "Commanders", "ATL": "Falcons", "CLE": "Browns", "GB": "Packers", "LAR": "Rams",
    "NE": "Patriots", "SEA": "Seahawks",
}


def esc(s):
    return html.escape(str(s), quote=True)


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_reads():
    paths = sorted(glob.glob(os.path.join(REPO, "injury-capture", "manifests", "reg11_2026_*.json")))
    reads = [load_json(p) for p in paths]
    reads = [r | {"_file": os.path.relpath(p, REPO)} for r, p in zip(reads, paths)]
    reads.sort(key=lambda r: r["fetched_at_utc"])
    if not reads:
        sys.exit("no Week 11 manifests found")
    for r in reads:
        if r.get("week") != 11 or r.get("status") != "OK" or r.get("problems"):
            sys.exit(f"manifest not clean: {r['_file']}")
    return reads


def per_table_signature(read):
    """Fields both reads carry. The first Week 11 manifest predates the per-label counts, so those are compared only when present in both."""
    return [(t["team_slug"], t["rows"], t["rows_with_game_status"]) for t in read["per_table"]]


def label_counts_present(read):
    return all("practice_status_counts" in t and "game_status_counts" in t for t in read["per_table"])


def club_counts(read, slug_to_abbr):
    """Return {abbr: {...}} from one manifest. Unknown labels stop the build."""
    out = {}
    for t in read["per_table"]:
        abbr = slug_to_abbr[t["team_slug"]]
        prac = {"DNP": 0, "LP": 0, "FP": 0}
        for label, n in t["practice_status_counts"].items():
            if label not in PRACTICE:
                sys.exit(f"unknown practice label {label!r}")
            prac[PRACTICE[label]] += n
        game = {"Out": 0, "Doubtful": 0, "Questionable": 0, "blank": 0}
        for label, n in t["game_status_counts"].items():
            if label not in GAME:
                sys.exit(f"unknown game label {label!r}")
            game[GAME[label]] += n
        out[abbr] = {"rows": t["rows"], **prac, **game,
                     "designated": game["Out"] + game["Doubtful"] + game["Questionable"]}
    return out


def page(title, body, depth):
    prefix = "../" if depth == 1 else ""
    nav = (f'<nav><a href="{prefix}index.html">Home</a>'
           f'<a href="{prefix}pages/clubs.html">Clubs</a>'
           f'<a href="{prefix}pages/schedule.html">Schedule &amp; byes</a>'
           f'<a href="{prefix}pages/captures.html">Captures</a>'
           f'<a href="{prefix}pages/flagged.html">Flagged for Review</a></nav>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} | Week 11 availability</title>
<link rel="stylesheet" href="{prefix}assets/style.css">
</head><body>
<header><h1>Week 11 availability</h1><p class="sub">Official NFL injury report, captured by a scheduled runner. Counts only; every figure links to its official source.</p>{nav}</header>
<main>{body}</main>
<footer>Derived from official NFL.com pages. Not an NFL product. Blank cells are unverified, not healthy. Terms: see Flagged W11-F04.</footer>
</body></html>
"""


def table(headers, rows_html):
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    return f"<div class='tw'><table><thead><tr>{head}</tr></thead><tbody>{''.join(rows_html)}</tbody></table></div>"


def link(url, text=None):
    return f'<a href="{esc(url)}">{esc(text or url)}</a>'


def build():
    reads = load_reads()
    first, last = reads[0], reads[-1]
    if len(reads) >= 2:
        if first["raw_sha256"] != last["raw_sha256"]:
            sys.exit("Week 11 reads have different raw hashes; not published as one read")
        if per_table_signature(first) != per_table_signature(last):
            sys.exit("Week 11 reads have different per-table counts")
    if not label_counts_present(last):
        sys.exit("latest Week 11 manifest lacks per-label counts")
    primary = last
    sched = load_json(os.path.join(ROOT, "data", "schedule_w11.json"))
    flags = load_json(os.path.join(ROOT, "data", "flags.json"))["flags"]

    slug_to_abbr = dict(sched["club_slugs"])
    counts = club_counts(primary, slug_to_abbr)
    fixtures = sched["fixtures"]
    playing = {}
    for f in fixtures:
        playing[f["away"]] = (f, "away")
        playing[f["home"]] = (f, "home")
    byes = [b["abbr"] for b in sched["teams_on_bye"]]
    if len(playing) != 26 or len(byes) != 6 or set(playing) & set(byes):
        sys.exit("schedule must give 26 playing clubs and 6 byes")
    all32 = set(playing) | set(byes)
    if len(all32) != 32:
        sys.exit("expected 32 clubs")
    missing_tables = sorted(a for a in playing if a not in counts)
    if sorted(set(counts) - set(playing)):
        sys.exit("a club with a table is not playing per schedule")

    total_rows = sum(c["rows"] for c in counts.values())
    if total_rows != primary["listed_rows_parsed"]:
        sys.exit("row total differs from manifest")
    tot = {k: sum(c[k] for c in counts.values()) for k in ("DNP", "LP", "FP", "Out", "Doubtful", "Questionable", "blank", "designated")}

    # ---------- clubs.csv (derived) ----------
    club_rows = []
    for abbr in sorted(all32):
        if abbr in byes:
            club_rows.append({"abbr": abbr, "club": CLUB_NAMES[abbr], "week11": "Bye (official schedule)", "listed_rows": "",
                              "DNP": "", "LP": "", "FP": "", "Out": "", "Doubtful": "", "Questionable": "", "no_game_status_printed": "",
                              "designated": "", "in_report": "no (bye)", "source": SCHEDULE_URL})
            continue
        f, side = playing[abbr]
        opp = f["home"] if side == "away" else f["away"]
        at = "at" if side == "away" else "vs"
        game_txt = f"{at} {opp} ({f['day'].split(' (')[0]})"
        if abbr in counts:
            c = counts[abbr]
            club_rows.append({"abbr": abbr, "club": CLUB_NAMES[abbr], "week11": game_txt, "listed_rows": c["rows"],
                              "DNP": c["DNP"], "LP": c["LP"], "FP": c["FP"], "Out": c["Out"], "Doubtful": c["Doubtful"],
                              "Questionable": c["Questionable"], "no_game_status_printed": c["blank"],
                              "designated": c["designated"], "in_report": "yes", "source": REPORT_URL})
        else:
            club_rows.append({"abbr": abbr, "club": CLUB_NAMES[abbr], "week11": game_txt, "listed_rows": "",
                              "DNP": "", "LP": "", "FP": "", "Out": "", "Doubtful": "", "Questionable": "", "no_game_status_printed": "",
                              "designated": "", "in_report": "no table in either read (F01)", "source": REPORT_URL})
    cols = list(club_rows[0].keys())
    with open(os.path.join(ROOT, "data", "clubs_w11.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in club_rows:
            w.writerow(r)

    # ---------- captures.csv ----------
    cap_rows = []
    for i, r in enumerate(reads, 1):
        cap_rows.append({"read": i, "fetched_at_utc": r["fetched_at_utc"], "http_status": r["http_status"],
                         "raw_bytes": r["raw_bytes"], "raw_sha256": r["raw_sha256"], "injury_tables": r["injury_tables"],
                         "listed_rows_parsed": r["listed_rows_parsed"], "pinned_min_rows": r["pinned_min_rows"],
                         "status": r["status"], "manifest": r["_file"], "source": REPORT_URL})
    with open(os.path.join(ROOT, "data", "captures_w11.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cap_rows[0].keys()))
        w.writeheader()
        for r in cap_rows:
            w.writerow(r)

    # ---------- index ----------
    open_flags = [f for f in flags if f["severity"] == "high"]
    idx_body = f"""
<section class="cards">
  <div class="card"><div class="n">{primary['listed_rows_parsed']}</div><div>listed player rows (official report, Week 11)</div></div>
  <div class="card"><div class="n">{len(counts)} of {len(playing)}</div><div>playing clubs with a report table</div></div>
  <div class="card warn"><div class="n">{len(missing_tables)}</div><div>playing clubs with no table ({', '.join(missing_tables)}) — flagged W11-F01</div></div>
  <div class="card"><div class="n">{tot['designated']}</div><div>rows with a printed game status (Out {tot['Out']}, Questionable {tot['Questionable']}, Doubtful {tot['Doubtful']})</div></div>
  <div class="card"><div class="n">{len(byes)}</div><div>clubs on bye (official schedule)</div></div>
</section>
<section>
  <h2>What was captured</h2>
  <p>Two reads of <a href="{REPORT_URL}">{REPORT_URL}</a> on {esc(first['fetched_at_utc'])} and {esc(last['fetched_at_utc'])} (UTC) returned the same raw SHA-256
  <code>{esc(last['raw_sha256'])}</code> ({last['raw_bytes']:,} bytes). Both reads agree on every per-club row count and game-status count. The reads are on the <a href="pages/captures.html">Captures</a> page.</p>
  <p>Practice status across the {primary['listed_rows_parsed']} rows: Did Not Participate {tot['DNP']}, Limited {tot['LP']}, Full {tot['FP']}.</p>
  <p>Printed game status is present only for the Thursday game (IND–HOU); the other 22 tables print a blank Game Status. A blank is not a clean bill of health (<a href="pages/flagged.html">W11-F02</a>).</p>
</section>
<section>
  <h2>What this site does not show yet</h2>
  <ul>
    <li><strong>Starters, depth rank and replacements:</strong> blank. No verified official depth chart or Game Book has been read for Week 11 (<a href="pages/flagged.html">W11-F05</a>).</li>
    <li><strong>Net injury count:</strong> the brief does not define it; counts are shown by label instead (<a href="pages/flagged.html">W11-F06</a>).</li>
    <li><strong>Deltas:</strong> the first Week 11 read in the repository is shown as a level with its timestamp; deltas start at the next read (<a href="pages/flagged.html">W11-F07</a>).</li>
    <li><strong>Stadium venues:</strong> not transcribed from game centre pages (<a href="pages/flagged.html">W11-F03</a>).</li>
    <li><strong>Player names:</strong> withheld from this public site until the NFL terms are resolved (<a href="pages/flagged.html">W11-F04</a>).</li>
  </ul>
</section>
<section>
  <h2>Pages</h2>
  <ul>
    <li><a href="pages/clubs.html">Clubs</a> — all 32 clubs: game, listed rows, practice and game-status counts, source link.</li>
    <li><a href="pages/schedule.html">Schedule &amp; byes</a> — 13 official fixtures, 6 byes, and whether each club has a table.</li>
    <li><a href="pages/captures.html">Captures</a> — both reads with time, byte count, raw hash and manifest.</li>
    <li><a href="pages/flagged.html">Flagged for Review</a> — {len(flags)} flags, {len(open_flags)} rated high, each with its official source.</li>
  </ul>
</section>
"""
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(page("Home", idx_body, 0))

    # ---------- clubs page ----------
    rows_html = []
    for r in club_rows:
        def v(x):
            return "" if x == "" else str(x)
        rows_html.append(
            "<tr>"
            f"<td>{esc(r['club'])} <span class='abbr'>{esc(r['abbr'])}</span></td>"
            f"<td>{esc(r['week11'])}</td>"
            f"<td class='n'>{v(r['listed_rows'])}</td>"
            f"<td class='n'>{v(r['DNP'])}</td><td class='n'>{v(r['LP'])}</td><td class='n'>{v(r['FP'])}</td>"
            f"<td class='n'>{v(r['Out'])}</td><td class='n'>{v(r['Doubtful'])}</td><td class='n'>{v(r['Questionable'])}</td>"
            f"<td class='n'>{v(r['no_game_status_printed'])}</td>"
            f"<td>{esc(r['in_report'])}</td>"
            f"<td>{link(r['source'], 'official source')}</td>"
            "</tr>")
    clubs_body = f"""
<h2>All 32 clubs, Week 11</h2>
<p class="note">Counts come from the runner manifest for {esc(primary['fetched_at_utc'])} (UTC). A blank cell means nothing was printed or no table was captured. It is not zero and not available. "Designated" = Out + Doubtful + Questionable. There is no net injury count: its formula is undefined (W11-F06).</p>
<p class="note">Totals across 24 captured clubs: listed {total_rows}; DNP {tot['DNP']}, LP {tot['LP']}, FP {tot['FP']}; Out {tot['Out']}, Doubtful {tot['Doubtful']}, Questionable {tot['Questionable']}, blank game status {tot['blank']}.</p>
{table(['Club', 'Week 11 game', 'Listed rows', 'DNP', 'LP', 'FP', 'Out', 'Doubtful', 'Questionable', 'No game status printed', 'In report?', 'Source'], rows_html)}
"""
    open(os.path.join(ROOT, "pages", "clubs.html"), "w", encoding="utf-8").write(page("Clubs", clubs_body, 1))

    # ---------- schedule page ----------
    fx_rows = []
    for f in fixtures:
        a_in = f["away"] in counts
        h_in = f["home"] in counts
        if a_in and h_in:
            inrep = "both clubs have a table"
        elif not a_in and not h_in:
            inrep = "neither club has a table (W11-F01)"
        else:
            inrep = "one club has no table"
        venue = f["venue"] or "blank (not transcribed)"
        fx_rows.append(
            "<tr>"
            f"<td>{esc(f['day'])}</td>"
            f"<td>{esc(f['away_name'])} at {esc(f['home_name'])} <span class='abbr'>{esc(f['away'])}@{esc(f['home'])}</span></td>"
            f"<td>{esc(f['kickoff_et'])} ET (as printed)</td><td>{esc(f['network'])}</td>"
            f"<td>{esc(venue)}</td><td>{esc(inrep)}</td>"
            f"<td>{link(f['game_url'], 'official game page')}</td></tr>")
    bye_rows = [f"<tr><td>{esc(b['name'])} <span class='abbr'>{esc(b['abbr'])}</span></td><td>Bye</td><td>{link(sched['bye_source_url'], 'official schedule')}</td></tr>"
                for b in sched["teams_on_bye"]]
    sched_body = f"""
<h2>Week 11 fixtures (official schedule)</h2>
<p class="note">Read {esc(sched['read_date_utc'])} from <a href="{SCHEDULE_URL}">{SCHEDULE_URL}</a>. Kickoff times and networks are as printed on that page. Venues are blank unless the page text itself names one.</p>
{table(['Day', 'Game', 'Kickoff', 'Network', 'Venue', 'Club tables in report', 'Source'], fx_rows)}
<h2>Teams on bye</h2>
<p class="note">Six clubs. Byes are not inferred from absence in the report; this list comes from the official "Teams on Bye" section.</p>
{table(['Club', 'Status', 'Source'], bye_rows)}
"""
    open(os.path.join(ROOT, "pages", "schedule.html"), "w", encoding="utf-8").write(page("Schedule and byes", sched_body, 1))

    # ---------- captures page ----------
    cap_html = []
    for r in cap_rows:
        cap_html.append(
            "<tr>"
            f"<td>{r['read']}</td><td>{esc(r['fetched_at_utc'])}</td><td class='n'>{r['http_status']}</td>"
            f"<td class='n'>{r['raw_bytes']:,}</td><td><code>{esc(r['raw_sha256'])}</code></td>"
            f"<td class='n'>{r['injury_tables']}</td><td class='n'>{r['listed_rows_parsed']}</td>"
            f"<td>{esc(r['status'])}</td>"
            f"<td>{link('../../' + r['manifest'], 'manifest (no names)')}</td>"
            f"<td>{link(REPORT_URL, 'official report')}</td></tr>")
    cap_body = f"""
<h2>Immutable capture record</h2>
<p class="note">Each read is a GitHub Actions run on a hosted runner. The raw HTML is kept as a run artifact (90-day retention) and is not committed. The committed manifest holds the hash, time and counts only.</p>
{table(['Read', 'Fetched (UTC)', 'HTTP', 'Raw bytes', 'Raw SHA-256', 'Injury tables', 'Listed rows', 'Status', 'Manifest', 'Source'], cap_html)}
<h2>How the counts were checked</h2>
<ul>
  <li>Both reads have the same raw SHA-256 and identical per-club row and game-status counts. The first read's manifest (19:51:12Z) predates the per-label counts, so the practice and label breakdowns come from the second read (19:52:41Z) alone.</li>
  <li>Four clubs (Colts, Texans, Steelers, Eagles) were read by hand from the official page text. Their row counts, practice-status counts and game-status counts match the manifest exactly. The other 20 clubs were not re-read by hand (W11-F09).</li>
  <li>Parsing enforces: the week text is present, each table has the required columns, every row has the same cell count as the header, and at least 50 rows are parsed.</li>
</ul>
"""
    open(os.path.join(ROOT, "pages", "captures.html"), "w", encoding="utf-8").write(page("Captures", cap_body, 1))

    # ---------- flags page ----------
    fl_html = []
    for f in flags:
        srcs = " · ".join(link(u, "source") for u in f["sources"])
        fl_html.append(
            "<tr>"
            f"<td>{esc(f['id'])}</td><td>{esc(f['severity'])}</td>"
            f"<td><strong>{esc(f['title'])}</strong><br>{esc(f['detail'])}</td>"
            f"<td>{esc(f['known'])}</td><td>{esc(f['unknown'])}</td><td>{esc(f['discover'])}</td>"
            f"<td>{srcs}</td></tr>")
    flags_body = f"""
<h2>Flagged for Review</h2>
<p class="note">These items do not block publication. Each one states what is known, what is not, and the official source to check. Nothing has been filled in to close a flag.</p>
{table(['ID', 'Severity', 'Issue', 'Known', 'Unknown', 'How to resolve', 'Sources'], fl_html)}
"""
    open(os.path.join(ROOT, "pages", "flagged.html"), "w", encoding="utf-8").write(page("Flagged for Review", flags_body, 1))

    print("built", len(club_rows), "club rows,", len(fixtures), "fixtures,", len(flags), "flags")


STYLE = """
:root{--ink:#1d2430;--mut:#5b6575;--line:#e3e7ee;--bg:#f7f8fb;--acc:#1f5fbf;--warn:#b35c00;--warnbg:#fff4e5}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header{background:#fff;border-bottom:1px solid var(--line);padding:18px 24px}
h1{margin:0 0 4px;font-size:22px}h2{font-size:18px;margin:26px 0 8px}
.sub{margin:0 0 10px;color:var(--mut)}
nav{display:flex;flex-wrap:wrap;gap:6px}nav a{padding:6px 10px;border:1px solid var(--line);border-radius:6px;text-decoration:none;color:var(--acc);background:#fff}
nav a:hover{background:#eef4ff}
main{padding:18px 24px;max-width:1200px}
a{color:var(--acc)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:8px 0 6px}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px}
.card .n{font-size:26px;font-weight:700}.card.warn{background:var(--warnbg);border-color:#f2c48a}
.card.warn .n{color:var(--warn)}
.tw{overflow-x:auto;background:#fff;border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#f0f3f8;position:sticky;top:0;font-weight:600}
td.n{text-align:right;font-variant-numeric:tabular-nums}
.abbr{color:var(--mut);font-size:12px;margin-left:4px}
code{font-size:12px;word-break:break-all}
.note{color:var(--mut);font-size:14px}
footer{padding:14px 24px;color:var(--mut);font-size:13px;border-top:1px solid var(--line);background:#fff}
"""


if __name__ == "__main__":
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "pages"), exist_ok=True)
    with open(os.path.join(ROOT, "assets", "style.css"), "w", encoding="utf-8") as fh:
        fh.write(STYLE.strip() + "\n")
    build()
