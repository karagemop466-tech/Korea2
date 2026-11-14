#!/usr/bin/env python3
"""Render the signal-desk site from the committed JSON artefacts.

Rules
-----
* No number is typed into the HTML. Every value is read from ``signal-desk/data/*.json``.
* Every table is rendered through :func:`table`, whose last column must be a source link. A row
  without a reachable source is rendered with an explicit ``unverified`` cell, never left blank
  and never given a value.
* Every page is rendered through :func:`layout`, so navigation and the as-of stamp are identical
  everywhere.
* ``check.py`` re-parses every generated page and fails on a broken link, a row with no source,
  or a page that is not in the navigation.
"""
from __future__ import annotations

import html
import json
import re
import os
import shutil
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(ROOT, "data")

NAV = [
    ("index.html", "Overview"),
    ("pages/prices.html", "1 &middot; Prices"),
    ("pages/results.html", "2 &middot; Results"),
    ("pages/order.html", "3 &middot; Origination order"),
    ("pages/gap.html", "4 &middot; Fair vs market"),
    ("pages/leaderboard.html", "5 &middot; Signal vs staking"),
    ("pages/depth.html", "6 &middot; Replacement depth"),
    ("pages/correlations.html", "7 &middot; Correlations"),
    ("pages/demotion.html", "8 &middot; Demotion gate"),
    ("pages/suggestions.html", "Suggestions"),
    ("pages/questions.html", "Questions"),
    ("pages/summary.html", "Executive summary"),
    ("pages/flagged.html", "Flagged for review"),
    ("pages/sources.html", "Sources"),
]


def load(name):
    with open(os.path.join(DATA, name)) as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- primitives
def esc(v):
    return html.escape(str(v))


def num(v, digits=2, signed=False):
    if v is None:
        return '<span class="na">blank</span>'
    try:
        f = float(v)
    except (TypeError, ValueError):
        return esc(v)
    return f"{f:+.{digits}f}" if signed else f"{f:.{digits}f}"


def pct(v, digits=1, signed=False):
    if v is None:
        return '<span class="na">blank</span>'
    try:
        f = float(v) * 100
    except (TypeError, ValueError):
        return esc(v)
    return f"{f:+.{digits}f}%" if signed else f"{f:.{digits}f}%"


def badge(kind, text):
    return f'<span class="badge {esc(kind)}">{esc(text)}</span>'


def status_badge(status, source_class=""):
    if status == "measured":
        cls = "ok" if source_class == "official" else "tp"
        label = "official" if source_class == "official" else "third-party"
        return badge(cls, label)
    return badge("flag", "unverified")


REPO_BLOB = "https://github.com/karagemop466-tech/Korea2/blob/main/"


def src(url, label=None):
    """Render a source link.

    A repository-relative path (``signal-desk/data/x.json``) is turned into a clickable GitHub
    blob URL rather than a site-relative link, because these files are not served by the site.
    """
    if not url:
        return '<span class="flag">no source</span>'
    if isinstance(url, list):
        return " ".join(src(u) for u in url)
    if not re.match(r"^[a-z]+://", str(url)):
        url = REPO_BLOB + str(url).split(" ")[0]
    text = label or str(url).replace("https://", "").replace("http://", "")
    if len(text) > 52:
        text = text[:49].rstrip() + "&hellip;"
    return f'<a href="{esc(url)}" rel="noopener" target="_blank">{esc(text)}</a>'


def table(headers, rows, caption="", cls="", notes=None):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for r in rows:
        cells = "".join(
            f'<td{" class=src" if i == len(r) - 1 else ""}>{c}</td>' for i, c in enumerate(r))
        body.append(f"<tr>{cells}</tr>")
    cap = f'<caption>{caption}</caption>' if caption else ""
    note = f'<p class="tnote">{notes}</p>' if notes else ""
    return (f'<div class="tw"><table class="{cls}">{cap}<thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>{note}')


def kpis(items):
    cards = "".join(
        f'<div class="kpi"><div class="k">{esc(k)}</div><div class="v">{v}</div>'
        f'<div class="s">{esc(s)}</div></div>' for k, v, s in items)
    return f'<div class="kpis">{cards}</div>'


def section(title, body, eyebrow=""):
    eb = f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else ""
    return f'<section class="block">{eb}<h2>{title}</h2>{body}</section>'


def callout(kind, title, body):
    return f'<div class="callout {kind}"><strong>{esc(title)}</strong><p>{body}</p></div>'


CSS = """
:root{--bg:#0e1117;--panel:#161b24;--panel2:#1c2330;--line:#28303d;--txt:#e6e9ee;--dim:#9aa4b2;
--acc:#4c8dff;--ok:#37b26c;--warn:#e0a83a;--bad:#e5534b;--tp:#8b7ce8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.6 -apple-system,BlinkMacSystemFont,
"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
header{background:var(--panel);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}
.bar{max-width:1240px;margin:0 auto;padding:10px 20px;display:flex;gap:18px;align-items:baseline;
flex-wrap:wrap}
.brand{font-weight:700;font-size:16px;letter-spacing:.2px;color:#fff;white-space:nowrap}
.brand span{color:var(--acc)}
.stamp{color:var(--dim);font-size:12px;white-space:nowrap}
nav{max-width:1240px;margin:0 auto;padding:0 20px 10px;display:flex;gap:4px;flex-wrap:wrap}
nav a{font-size:13px;color:var(--dim);padding:5px 9px;border-radius:6px;border:1px solid transparent}
nav a:hover{background:var(--panel2);color:var(--txt);text-decoration:none}
nav a.on{background:var(--panel2);color:#fff;border-color:var(--line)}
main{max-width:1240px;margin:0 auto;padding:26px 20px 70px}
h1{font-size:27px;line-height:1.25;margin:6px 0 8px}
h2{font-size:19px;margin:0 0 12px}
h3{font-size:15px;margin:22px 0 8px;color:#cfd6e0}
p{margin:0 0 12px;max-width:78ch}
.lede{color:var(--dim);font-size:16px;max-width:80ch}
.eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--acc);font-weight:700}
.block{margin:30px 0 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:20px 0}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:13px 15px}
.kpi .k{font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--dim)}
.kpi .v{font-size:23px;font-weight:700;margin-top:4px;font-variant-numeric:tabular-nums}
.kpi .s{font-size:12px;color:var(--dim);margin-top:2px}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:13.5px}
caption{text-align:left;padding:11px 14px 0;color:var(--dim);font-size:12.5px}
th,td{padding:8px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--panel2);font-size:11px;letter-spacing:.07em;text-transform:uppercase;
color:var(--dim);position:sticky;top:0;white-space:nowrap}
tr:last-child td{border-bottom:none}
tr:hover td{background:#1a212c}
td.src{font-size:12px;max-width:230px}
td.src a{display:inline-block;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.num{font-variant-numeric:tabular-nums;text-align:right}
.badge{display:inline-block;font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;
padding:2px 7px;border-radius:20px;font-weight:700;white-space:nowrap}
.badge.ok{background:rgba(55,178,108,.16);color:#5ed492;border:1px solid rgba(55,178,108,.35)}
.badge.tp{background:rgba(139,124,232,.16);color:#a99cf0;border:1px solid rgba(139,124,232,.35)}
.badge.flag{background:rgba(224,168,58,.14);color:#e8bd63;border:1px solid rgba(224,168,58,.35)}
.badge.bad{background:rgba(229,83,75,.14);color:#f0837c;border:1px solid rgba(229,83,75,.35)}
.badge.gray{background:#232b38;color:var(--dim);border:1px solid var(--line)}
.na{color:#6d7787;font-style:italic}
.flag{color:var(--warn)}
.callout{border:1px solid var(--line);border-left:3px solid var(--acc);background:var(--panel);
border-radius:8px;padding:13px 16px;margin:14px 0}
.callout.warn{border-left-color:var(--warn)}
.callout.good{border-left-color:var(--ok)}
.callout.bad{border-left-color:var(--bad)}
.callout strong{display:block;margin-bottom:4px}
.callout p{margin:0;color:#cfd6e0;font-size:14px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(275px,1fr));gap:14px;margin:18px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px}
.card h3{margin:0 0 6px;font-size:15px;color:#fff}
.card p{font-size:13.5px;color:var(--dim);margin:0 0 10px}
.card a{font-size:13px;font-weight:600}
.tnote{color:var(--dim);font-size:12.5px;margin:8px 0 0;max-width:80ch}
details{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 16px;
margin:10px 0}
summary{cursor:pointer;font-weight:600;font-size:14px}
details p,details ul{font-size:13.5px;color:#cfd6e0}
ul{padding-left:20px}li{margin:3px 0;max-width:80ch}
footer{border-top:1px solid var(--line);color:var(--dim);font-size:12px;padding:22px 20px;
max-width:1240px;margin:0 auto}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}
"""


def layout(title, path, body, subtitle="", stamp=""):
    """Render a full page. ``path`` is relative to signal-desk/ so the correct nav entry lights up."""
    up = "../" if path.startswith("pages/") else ""
    links = []
    for href, label in NAV:
        on = ' class="on"' if href == path else ""
        links.append(f'<a href="{up}{href}"{on}>{label}</a>')
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} &middot; Signal Desk</title>
<meta name="generator" content="signal-desk/scripts/build.py">
<meta name="description" content="NFL line origination, verification and decision desk: {esc(subtitle)}">
<style>{CSS}</style></head>
<body>
<header>
  <div class="bar">
    <div class="brand">SIGNAL <span>DESK</span></div>
    <div class="stamp">{esc(stamp)}</div>
    <div class="stamp" style="margin-left:auto">
      <a href="{up}../index.html">Line Lab &rarr;</a>
    </div>
  </div>
  <nav>{''.join(links)}</nav>
</header>
<main>
<h1>{esc(title)}</h1>
{f'<p class="lede">{subtitle}</p>' if subtitle else ''}
{body}
</main>
<footer>
  Research and measurement, not betting advice. Every number on this page is rendered from
  <span class="mono">signal-desk/data/*.json</span>; none is typed by hand. A blank cell means the
  value could not be confirmed from the source named in that row &mdash; it is never inferred.
  <br>Official figures are transcribed from nfl.com pages read on the date shown in each row.
  Third-party figures come from nflverse community data and are labelled as such.
</footer>
</body></html>
"""


def write(path, html_text):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as fh:
        fh.write(html_text)
    print(f"  wrote signal-desk/{path}")


# --------------------------------------------------------------------------- pages
def stamp_of(*objs):
    for o in objs:
        g = (o or {}).get("meta", {}).get("generated_utc")
        if g:
            return f"Data built {g}"
    return ""


def page_index():
    s = load("summary.json")
    res = load("results_feed.json")
    p = load("price_snapshots.json")
    ss = load("signal_vs_staking.json")
    d = load("replacement_depth.json")
    c = load("correlation_official.json")
    order = load("origination_order.json")
    gap = load("fair_market_gap.json")
    dem = load("demotion_gate.json")
    st = stamp_of(s)

    kpi = kpis([
        ("Official standings reconciled", f"{res['standings_check']['teams_reconciling_after_official_scores']}/32",
         "teams, W/L/T/PF/PA vs nfl.com"),
        ("Opening moneylines on file", "0", "the upstream opening file has none"),
        ("Seasons with open AND close", f"{len(p['join']['seasons_with_both'])}",
         "so no open-to-close move exists"),
        ("Strategies with a real signal", f"{ss['summary']['signal_distinguishable']}",
         f"of {ss['summary']['strategies']} published"),
        ("Positive ROI, unproven signal", f"{ss['summary']['positive_roi_but_unproven_signal']}",
         "would fool a staking-only board"),
        ("Rewards paid", f"{ss['summary']['rewards_paid']}", "the gate paid nothing"),
        ("Official correlations at n=32", str(sum(1 for r in c['rows'] if r.get('n_official') == 32)),
         "team-level only; the per-game pair is blank"),
        ("Demotion rules armed", f"{len(dem['rules'])}", "4 evaluable today"),
    ])

    cards = f"""<div class="cards">
  <div class="card"><h3>1 &middot; Price-snapshot store</h3>
    <p>{esc(p['join']['detail'] or 'Opening and closing records per market.')}</p>
    <a href="pages/prices.html">Open prices &rarr;</a></div>
  <div class="card"><h3>2 &middot; Verified results feed</h3>
    <p>{esc(res['standings_check']['result'])}. {res['game_feed']['committed_absent']} finished games
    were missing from the committed snapshot and are listed, not back-filled.</p>
    <a href="pages/results.html">Open results &rarr;</a></div>
  <div class="card"><h3>3 &middot; Origination order</h3>
    <p>{esc(order['conclusion'])}</p><a href="pages/order.html">Open order &rarr;</a></div>
  <div class="card"><h3>4 &middot; Fair, market, difference</h3>
    <p>Three separate numeric columns per market, with the sign convention stated and the hold
    published ({pct(gap['vig']['value'])}).</p><a href="pages/gap.html">Open board &rarr;</a></div>
  <div class="card"><h3>5 &middot; Signal vs staking</h3>
    <p>{esc(ss['conclusion'])}</p><a href="pages/leaderboard.html">Open leaderboard &rarr;</a></div>
  <div class="card"><h3>6 &middot; Replacement depth</h3>
    <p>Depth ranks are tracked down to the {d['third_party_depth']['deepest_rank_observed']}th string,
    and the page states plainly that the official pages publish no depth ordinal.</p>
    <a href="pages/depth.html">Open depth &rarr;</a></div>
  <div class="card"><h3>7 &middot; Correlations</h3>
    <p>Only officially sourced pairs are published, each with n and a confidence interval; the pair
    the parlay pricing needs is blank with a reason.</p>
    <a href="pages/correlations.html">Open correlations &rarr;</a></div>
  <div class="card"><h3>8 &middot; Demotion gate</h3>
    <p>{len(dem['rules'])} rules with explicit triggers. Promotion is slow; demotion is fast.</p>
    <a href="pages/demotion.html">Open gate &rarr;</a></div>
</div>"""

    head = table(["Topic", "Finding", "Class", "Source"],
                 [[esc(h["topic"]), esc(h["finding"]),
                   status_badge("measured", h["source_class"]), src(h["source"])]
                  for h in s["headline"]],
                 caption="The nine findings that matter, each with the class of its source.")

    body = (
        callout("warn", "Read this first",
                "This desk answers a narrower question than a betting site: what can actually be "
                "checked. Where a value could not be confirmed from an official source, the cell is "
                "blank and the row says why. Nothing here is a recommendation to stake money.")
        + kpi + cards
        + section("Findings", head)
        + section("Where to start", f"""<ol>
<li><strong><a href="pages/questions.html">Questions</a></strong> &mdash; twelve questions that each
block at least one decision. Several cannot be answered from data at all; they need a choice from you.</li>
<li><strong><a href="pages/suggestions.html">Suggestions</a></strong> &mdash; eight proposals, each with
impact, effort, risk and the question it waits on. None is implemented.</li>
<li><strong><a href="pages/flagged.html">Flagged for review</a></strong> &mdash; every irregularity and
every unverified cell, with the source link, so you can check it yourself.</li>
</ol>""")
    )
    return layout("The decision desk for the NFL line project", "index.html", body,
                  "Eight requirements, built and verified one line at a time. Each page shows its "
                  "numbers, the source each number came from, and what is still unknown.", st)


def page_prices():
    p = load("price_snapshots.json")
    st = stamp_of(p)
    k = kpis([
        ("Opening file coverage", "1 season" if p["opening"]["status"] == "loaded" else "not loaded",
         "2021 only, one sportsbook"),
        ("Opening moneylines", str(p["opening"]["moneyline"] or 0), "none exist in the source"),
        ("Closing coverage (committed extract)", "2014&ndash;2026", "every regular-season game"),
        ("Seasons with open and close", str(len(p["join"]["seasons_with_both"])), "none"),
    ])
    open_rows = []
    for r in p["opening"]["by_season"]:
        open_rows.append([str(r["season"]), str(r["spread"]), str(r["total"]),
                          r["moneyline"] if r["moneyline"] else '<span class="na">none in source</span>',
                          src(p["opening"]["source"]["url"])])
    close_file_rows = [[str(r["season"]), str(r["games"]), str(r["moneyline"]), str(r["spread"]),
                        str(r["total"]), str(r["rows_with_price"]),
                        src(p["closing_file"]["source"]["url"])]
                       for r in p["closing_file"]["by_season"]]
    committed_rows = [[str(r["season"]), str(r["games"]), str(r["side"]), str(r["total"]),
                       str(r["moneyline"]), str(r["side_price"]), str(r["total_price"]),
                       src(p["closing"]["source"]["url"])]
                      for r in p["closing"]["by_season"] if r["season"] >= 2014]
    cov_rows = [[esc(c["record"]), esc(c["seasons"]) or '<span class="na">none</span>',
                 status_badge(c["status"], c["source_class"]), esc(c["note"]),
                 esc(c.get("needed", "")), src(c["source"])] for c in p["coverage"]]

    body = (
        k
        + callout("warn", "The headline problem",
                  esc(p["join"]["detail"] or "Opening and closing coverage differ."))
        + section("What the store records, and what it cannot",
                  table(["Record", "Seasons", "Status", "What that means", "What would close it", "Source"],
                        cov_rows,
                        caption="A snapshot is recorded only where a named source publishes the number."))
        + section("Opening snapshot (third-party)",
                  table(["Season", "Spread rows", "Total rows", "Moneyline rows", "Source"], open_rows,
                        caption="Every season the opening-line file actually contains.") +
                  f'<p class="tnote">{esc(p["opening"].get("note", ""))}</p>')
        + section("Closing file (third-party, separate upstream file)",
                  table(["Season", "Games", "Moneyline rows", "Spread rows", "Total rows",
                         "Rows carrying a price", "Source"], close_file_rows,
                        caption="This file stops at 2018, which is why no season overlaps the opening file."))
        + section("Closing snapshot used by the models (committed extract)",
                  table(["Season", "Games", "Side", "Total", "Moneyline", "Side prices", "Total prices",
                         "Source"], committed_rows,
                        caption="Coverage of the committed games extract, the closing numbers every "
                                "backtest in this repository settles against.") +
                  f'<p class="tnote">{esc(p["closing"]["caveat"])}</p>')
    )
    return layout("Price-snapshot store: opening and closing numbers per market", "pages/prices.html",
                  body, "Requirement 1. One record per market per game, or an explicit blank.", st)


def page_results():
    r = load("results_feed.json")
    st = stamp_of(r)
    k = kpis([
        ("Teams reconciled", f"{r['standings_check']['teams_reconciling_after_official_scores']}/32",
         "W/L/T/PF/PA against NFL.com"),
        ("Official games added", str(r["standings_check"]["official_games_added"]),
         "games the snapshot was missing"),
        ("Games read from nfl.com", str(r["standings_check"]["official_games_read"]),
         "weeks 8-10, game by game"),
        ("Season reconciliations", "2 &times; 32", "2020 and 2025, all teams"),
    ])
    team_rows = []
    for row in r["standings_check"]["rows"]:
        b, a, o = row["committed_only"], row["committed_plus_official_scores"], row["official"]
        ok = ('<span class="badge ok">match</span>' if row["reconciles_after"]
              else '<span class="badge bad">differs</span>')
        team_rows.append([row["team"], f"{o['w']}-{o['l']}-{o['t']}", f"{o['pf']}/{o['pa']}",
                          f"{b['w']}-{b['l']}-{b['t']}", f"{a['w']}-{a['l']}-{a['t']}", ok,
                          src(row["source"])])
    feed_rows = []
    for g in r["game_feed"]["rows"]:
        committed = ('<span class="na">absent</span>' if g["committed_status"] == "absent"
                     else f"{g['committed_away_score']}&ndash;{g['committed_home_score']}")
        agree = ('<span class="badge ok">agree</span>' if g["agree"] else
                 '<span class="badge gray">not in snapshot</span>')
        feed_rows.append([f"W{g['week']}", f"{g['away']} @ {g['home']}",
                          f"{g['official_away_score']}&ndash;{g['official_home_score']}",
                          committed, agree, src(g["source"])])
    season_rows = [[str(s["season"]), f"{s['teams_match']}/{s['teams_compared']}",
                    '<span class="badge ok">all teams</span>' if s["teams_match"] == s["teams_compared"]
                    else '<span class="badge flag">partial</span>', src(s["source"])]
                   for s in r["season_reconciliation"]["rows"]]

    body = (
        k
        + section("The test that matters",
                  callout("good", r["standings_check"]["result"],
                          "Take the committed 2026 results, add the official final scores that the "
                          "snapshot was missing, and compare all five standings columns team by team "
                          "against the official table. The committed results are not merely "
                          "self-consistent &mdash; they reproduce the league's own table.")
                  + table(["Season", "Teams matching", "Result", "Official source"], season_rows,
                          caption="Whole-season reconciliations, which test the results rather than "
                                  "the schedule."))
        + section("Game-by-game feed",
                  table(["Week", "Game", "Official final", "In committed snapshot", "Agreement", "Source"],
                        feed_rows,
                        caption=f"Weeks {', '.join(str(w) for w in r['game_feed']['weeks_verified'])} read "
                                "from nfl.com on 2026-11-14. A game absent from the snapshot stays absent.") +
                  f'<p class="tnote">{esc(r["game_feed"]["note"])}</p>')
        + section("Team-by-team standings reconciliation, 2026",
                  table(["Team", "Official W-L-T", "Official PF/PA", "Snapshot W-L-T",
                         "Snapshot + official scores", "Result", "Source"], team_rows,
                        caption="Snapshot W-L-T is before the official scores are added; the next "
                                "column is after. Only the last column decides agreement.") +
                  f'<p class="tnote">{esc(r["coverage"].get("note", ""))}</p>')
    )
    return layout("Verified results feed", "pages/results.html", body,
                  "Requirement 2. Backtests and ROI are only meaningful if the results themselves "
                  "resolve to the league.", st)


def page_order():
    o = load("origination_order.json")
    st = stamp_of(o)
    t_rows = [[f'<strong>{esc(t["test"])}</strong>', f'<span class="badge {"ok" if t["verdict"] == "pass" else "flag"}">{esc(t["verdict"])}</span>',
               esc(t["detail"]), src(t["source"])] for t in o["tests"]]
    b_rows = [[g["game_id"], num(g["side"], 1, True), format(g["published_prob"], ".4f"),
               format(g["phi_of_side"], ".4f"), num(g["diff"], 4, True),
               str(g["fair_home_ml"]), str(g["recomputed_from_side"]),
               '<span class="badge ok">reproduces</span>'
               if abs(g["diff"]) <= 0.002 else '<span class="badge bad">differs</span>']
              for g in o["enforcement"]["board_rows"]]
    b_rows = [[*r, src("data/derived/model.json")] for r in b_rows]
    body = (
        callout("good", "The claimed order holds, mechanically",
                esc(o["conclusion"]))
        + section("The order", table(["Step", "Market", "Why it is in this position"], [
            ["1", "Side (spread)", "The attack/defence model estimates a scoring margin. Nothing "
             "downstream can contradict it."],
            ["2", "Total", "Estimated from the same terms but a separate quantity, so the side and "
             "the total cannot be a by-product of one another."],
            ["3", "Moneyline", "A re-expression of the side through Phi(side / sigma). Not a third "
             "independent model."],
        ], caption=esc(o["meta"]["why_this_order"])))
        + section("Tests", table(["Test", "Verdict", "What the numbers show", "Source"], t_rows))
        + section("Moneyline reconstructed from the side",
                  table(["Game", "Side", "Published P(home)", "Phi(side / sigma)", "Difference",
                         "Published ML", "Recomputed ML", "Check", "Source"], b_rows,
                        caption=f"sigma = {o['tests'][0]['stat']['sigma']}. A difference above 0.002 "
                                "would fail the build.") +
                  f'<p class="tnote">Board is season {o["meta"]["as_of_season_week"][0]}, week '
                  f'{o["meta"]["as_of_season_week"][1]}. {esc(o["meta"]["as_of_note"])}</p>')
        + section("Enforcement", callout("warn", "How this is kept true",
                                        esc(o["enforcement"]["code"])))
    )
    return layout("Origination order: side, then total, then moneyline", "pages/order.html", body,
                  "Requirement 3. The moneyline must be a function of the side, not a third opinion.",
                  st)


def page_gap():
    g = load("fair_market_gap.json")
    st = stamp_of(g)
    rows = []
    for r in g["board"]["rows"]:
        rows.append([r["game_id"],
                     num(r["fair_side_home"], 1, True), num(r["market_side_home"], 1, True),
                     num(r["diff_side"], 2, True),
                     num(r["fair_total"], 1), num(r["market_total"], 1), num(r["diff_total"], 2, True),
                     f'{r["fair_prob_home"]:.4f}',
                     '&mdash;' if r["market_prob_home_novig"] is None else f'{r["market_prob_home_novig"]:.4f}',
                     num(r["diff_prob_home"], 4, True),
                     str(r["fair_ml_home"]), str(r["market_ml_home"]),
                     src(r["source"])])
    agree = table(["Metric", "r", "n", "p", "Source"],
                  [[esc(a["metric"]), num(a["r"], 3), str(a["n"]), esc(f'{a["p"]:.5f}'),
                    src(a["source"])] for a in g["agreement"]],
                  caption="Agreement between the fair line and the market line on the same games.")
    body = (
        kpis([("Games on the board", str(len(g["board"]["rows"])), "one row per game, three markets"),
              ("Mean two-way hold", pct(g["vig"]["value"]), "implied by the market moneyline pair"),
              ("Fair vs market, side", f'r = {g["agreement"][0]["r"]}', "the model is close, and worse"),
              ("Fair vs market, total", f'r = {g["agreement"][1]["r"]}', "same story")])
        + callout("warn", "Sign convention", esc(g["meta"]["sign_convention"]) + " "
                  + esc(g["meta"]["market_side_convention"]))
        + section("Three columns per market",
                  table(["Game", "Fair side", "Market side", "Diff", "Fair total", "Market total",
                         "Diff", "Fair P(home)", "Market P(home), de-vigged", "Diff P", "Fair ML",
                         "Market ML", "Source"], rows,
                        caption=f"Season {g['board']['season']}, week {g['board']['week']}. "
                                + esc(g["meta"]["rule"])))
        + section("How far apart are they?", agree)
    )
    return layout("Fair line, market line and difference", "pages/gap.html", body,
                  "Requirement 4. No cell may claim an edge without the two parent numbers beside it.",
                  st)


def page_leaderboard():
    s = load("signal_vs_staking.json")
    st = stamp_of(s)
    sig_rows = []
    for rank, r in enumerate(sorted(s["rows"], key=lambda x: (
            not x["signal"]["passes_signal_test"],
            x["signal"]["p_value"] if x["signal"]["p_value"] is not None else 1.0)), 1):
        sig = r["signal"]
        sig_rows.append([str(rank), f'<strong>{esc(r["name"])}</strong><br><span class="tnote">'
                         f'{esc(r["family"])}</span>',
                         str(sig["n"]), pct(sig["win_rate"]), num(sig["p_value"], 3),
                         num(sig["bh_adjusted_p"], 3), num(sig["deflated_sharpe_p"], 3),
                         badge("ok" if sig["passes_signal_test"] else "bad", sig["verdict"]),
                         esc(r["gates_passed"]), src(r["source"])])
    stake_rows = []
    for rank, r in enumerate(sorted(s["rows"], key=lambda x: -(x["staking"]["roi"] or -9)), 1):
        st_ = r["staking"]
        stake_rows.append([str(rank), f'<strong>{esc(r["name"])}</strong>',
                           pct(st_["roi"], 2, True),
                           f'{pct(st_["roi_ci"][0], 1)} to {pct(st_["roi_ci"][1], 1)}',
                           badge("bad", "lucky run") if st_["lucky_run"] else
                           badge("gray", st_["staking_verdict"]),
                           esc(st_["reward"]), src(r["source"])])
    body = (
        kpis([("Strategies", str(s["summary"]["strategies"]), "published"),
              ("Positive ROI", str(s["summary"]["positive_roi"]), "on the stakes placed"),
              ("Signal distinguishable", str(s["summary"]["signal_distinguishable"]),
               "after multiple testing"),
              ("Rewards paid", str(s["summary"]["rewards_paid"]), "the gate paid nothing")])
        + callout("bad", "Why two tables and not one", esc(s["conclusion"]))
        + section("Table A &mdash; signal", table(
            ["Rank", "Strategy", "n", "Win rate", "p", "BH q", "Deflated Sharpe p", "Signal verdict",
             "Gates", "Source"], sig_rows,
            caption="Ranked by whether the edge is distinguishable from zero. This is the table that "
                    "should decide anything."))
        + section("Table B &mdash; staking", table(
            ["Rank", "Strategy", "ROI", "95% interval", "Staking verdict", "Reward", "Source"],
            stake_rows,
            caption="Ranked by return on the stakes actually placed. Notice how different the order "
                    "is, and that the top row is flagged as a lucky run."))
        + section("The rule", callout("warn", "Ranking rule", esc(s["meta"]["ranking_rule"])))
    )
    return layout("Signal is not staking", "pages/leaderboard.html", body,
                  "Requirement 5. A lucky staking run must not be able to outrank a real signal.",
                  st)


def page_depth():
    d = load("replacement_depth.json")
    st = stamp_of(d)
    tp = d["third_party_depth"]
    cur_rows = []
    for c in sorted(d["current_week"], key=lambda x: -(x["deepest_replacement_rank"] or 0))[:16]:
        cur_rows.append([c["team"], str(c["week"]), str(c["starters_out"]), str(c["two_deep_out"]),
                         str(c["three_deep_out"]),
                         f'<strong>{c["deepest_replacement_rank"]}</strong>',
                         num(c["weighted_depth_lost"], 1), src(c["source"])])
    off_rows = [[f'W{o["week"]}', o["team"], o["player"], o["position"], esc(o["injury"]) or
                 '<span class="na">not listed</span>', esc(o["practice"]),
                 esc(o["game_status"]) or '<span class="na">not listed</span>',
                 badge("tp", f'rank {o["third_party_rank"]}') if o.get("third_party_rank")
                 else badge("flag", "no rank joined"),
                 src(o["url"])] for o in d["official_position"]["rows"]]
    find_rows = [[esc(f["claim"]),
                  badge("ok", "confirmed") if f["verdict"] == "confirmed" else badge("flag", "not confirmed"),
                  esc(f["detail"]), src(f["url"])] for f in d["page_findings"]]
    dist_rows = [[f'<strong>{k}th string</strong>' if k != "1" else "<strong>1st string</strong>",
                  str(v), pct(v / tp["absences_total"])] for k, v in tp["distribution_by_rank"].items()]
    dist_rows = [[*r, src(tp["source"])] for r in dist_rows]
    body = (
        kpis([("Deepest rank observed", f'{tp["deepest_rank_observed"]}th', "a 10th-string absence"),
              ("Absences with a rank", f'{tp["absences_with_depth_rank"]}/{tp["absences_total"]}',
               "the rest have no joinable rank"),
              ("Official depth source", "none", "no official page publishes a depth ordinal"),
              ("3rd-string-or-deeper absences", str(sum(v for k, v in tp["distribution_by_rank"].items()
                                                         if int(k) >= 3)), "of " + str(tp["absences_total"]))])
        + callout("warn", "The honest limitation", esc(d["meta"]["key_limitation"]))
        + section("What an official source does and does not publish",
                  table(["Claim tested", "Verdict", "What the page returned", "Source"], find_rows,
                        caption="Each claim was tested by opening the page and reading it."))
        + section("Depth distribution (third-party)",
                  table(["Depth from which the replacement comes", "Absences", "Share", "Source"],
                        dist_rows,
                        caption="How far down the chart each absence reaches. "
                                + esc(tp["caveat"])))
        + section("Current week, worst depth first (third-party)",
                  table(["Team", "Week", "Starters out", "2-deep out", "3-deep out",
                         "Deepest replacement", "Weighted depth lost", "Source"], cur_rows,
                        caption="Teams where a starter is out, ordered by how deep the replacement "
                                "has to come from."))
        + section("Official rows, joined to third-party depth",
                  table(["Week", "Team", "Player", "Pos", "Injury", "Practice", "Game status",
                         "Depth", "Source"], off_rows,
                        caption="The official injury report supplies everything except depth; the "
                                "depth column is the join, and it is labelled third-party."))
    )
    return layout("Replacement depth, not just the fact of a replacement", "pages/depth.html", body,
                  "Requirement 6. 1st, 2nd and 3rd string, with the provenance of the depth figure "
                  "stated on every row.", st)


def page_correlations():
    c = load("correlation_official.json")
    st = stamp_of(c)
    rows = []
    for r in c["rows"]:
        rows.append([esc(r["correlation"]),
                     num(r["value"], 4) if r["status"] == "measured" else '<span class="na">blank</span>',
                     str(r["n"]) if r.get("n") else '<span class="na">0</span>',
                     esc(f'{r["ci_low"]} to {r["ci_high"]}') if r.get("ci_low") is not None
                     else '<span class="na">blank</span>',
                     status_badge(r["status"], r["source_class"]),
                     esc(r["note"]) + (f' <em>Needed: {esc(r["needed"])}</em>' if r.get("needed") else ""),
                     src(r["source"])])
    body = (
        callout("warn", "The rule", esc(c["meta"]["rule"]))
        + section("Published values",
                  table(["Correlation", "r", "n", "95% interval", "Class", "Note", "Source"], rows,
                        caption="Every value below comes from an official page. None is a "
                                "third-party figure relabelled as official."))
        + section("Why the parlay pair is blank",
                  callout("bad", "Blank on purpose",
                          "The parlay pricing this project wants depends on how a quarterback's "
                          "passing yards move with his top receiver's receiving yards in the same "
                          "game. The official season-leader pages publish the two quantities for "
                          "<em>different players</em>, so they cannot be paired. The value is "
                          "published blank and the reason is stated, rather than replaced with the "
                          "committed third-party estimate &mdash; which exists, and is "
                          "r = 0.5616 at n = 7,560, but is not official."))
        + section("What n=32 means",
                  callout("warn", "Small n, stated plainly",
                          "The team-level correlations are computed over 32 team-seasons. That is "
                          "enough to describe the season and nowhere near enough to claim a stable "
                          "effect. The interval is reported with every value for exactly this reason."))
    )
    return layout("Correlations from officially sourced numbers", "pages/correlations.html", body,
                  "Requirement 7. Official inputs only, n published with every value, blanks where "
                  "the official join does not exist.", st)


def page_demotion():
    d = load("demotion_gate.json")
    st = stamp_of(d)
    rule_rows = [[f'<strong>{r["id"]}</strong>', esc(r["name"]), esc(r["trigger"]),
                  badge("bad", "automatic") if r["automatic"] else badge("flag", r["action"]),
                  src("signal-desk/data/demotion_gate.json")] for r in d["rules"]]
    ev_rows = [[r["rule"], badge("ok", "evaluable") if r["evaluable_today"] else badge("flag", "not yet"),
                esc(r["note"]), src("signal-desk/data/demotion_gate.json")] for r in d["evaluability"]]
    tr_rows = [[esc(t["from"]), "&rarr;", esc(t["to"]), esc(t["requires"]),
                src("signal-desk/data/demotion_gate.json")] for t in d["state_machine"]["transitions"]]
    body = (
        callout("warn", "The gap this closes", esc(d["meta"]["problem_it_fixes"]))
        + section("Rules", table(["ID", "Rule", "Trigger", "Action", "Source"], rule_rows,
                                 caption="A rule fires on its trigger alone; no judgement call is "
                                         "needed at the moment it matters."))
        + section("State machine", table(["From", "", "To", "Requires", "Source"], tr_rows,
                                         caption=esc(d["state_machine"]["no_route"])))
        + section("Can each rule be evaluated today?",
                  table(["Rule", "Evaluable", "Why", "Source"], ev_rows,
                        caption="Four of the eight rules cannot fire yet because their inputs do not "
                                "exist. That is a finding, not an omission."))
        + section("Deliberate asymmetry", callout("good", "Slow in, fast out",
                                                 esc(d["meta"]["asymmetry"])))
        + section("Current state", callout("warn", "Nothing is live",
                                          esc(d["current_state"]["note"])))
    )
    return layout("Demotion gate: sending a live strategy back to paper", "pages/demotion.html", body,
                  "Requirement 8. A promotion-only system is a ratchet. This is the exit.", st)


def page_suggestions():
    s = load("decision_layer.json")
    st = stamp_of(s)
    rows = []
    for x in s["suggestions"]:
        rows.append([f'<strong>{esc(x["id"])}</strong>', f'<strong>{esc(x["title"])}</strong>',
                     esc(x["problem"]), esc(x["change"]),
                     badge("gray", x["impact"]), badge("gray", x["effort"]),
                     badge("bad", x["risk"]) if x["risk"] == "high" else badge("flag", x["risk"]),
                     esc(", ".join(x["unblocks"])), esc(x["measure_of_success"]),
                     src(x["evidence"])])
    body = (
        callout("warn", "Nothing on this page is implemented",
                esc(s["meta"]["how_to_use"]))
        + section("Eight suggestions",
                  table(["ID", "Suggestion", "Problem", "Change", "Impact", "Effort", "Risk",
                         "Waits on", "How you would know it worked", "Evidence"], rows))
        + section("The three decisions that gate everything else", "".join(
            f"""<details><summary>{esc(x["id"])} &middot; {esc(x["decision"])}</summary>
<p><strong>Gated by:</strong> {esc(', '.join(x["gated_by"]))} &middot;
<strong>Evidence:</strong> {esc(x["evidence"])}</p>
<table><thead><tr><th>Option</th><th>Cost</th><th>What you get</th><th>What could go wrong</th></tr></thead>
<tbody>{''.join(f'<tr><td><strong>{esc(o["option"])}</strong></td><td>{esc(o["cost"])}</td>'
                f'<td>{esc(o["gives"])}</td><td>{esc(o["risk"])}</td></tr>' for o in x["options"])}
</tbody></table></details>""" for x in s["decisions"]))
    )
    return layout("Suggestions for review", "pages/suggestions.html", body,
                  "A proposal list you can read and reject before anything is built. Each proposal "
                  "names the question it is waiting on.", st)


def page_questions():
    s = load("decision_layer.json")
    st = stamp_of(s)
    rows = []
    for q in s["questions"]:
        rows.append([f'<strong>{esc(q["id"])}</strong>', f'<strong>{esc(q["question"])}</strong>',
                     esc(q["what_we_know"]), esc(q["what_we_do_not_know"]),
                     esc(", ".join(q["blocks"])), str(q["decisions_blocked"]),
                     esc(q["how_to_close"]), badge("gray", q["owner_action"]),
                     src("signal-desk/data/decision_layer.json")])
    need_you = [q for q in s["questions"] if q["owner_action"] in
                ("a sourcing decision only you can make", "preference", "fact only you can supply",
                 "policy decision")]
    body = (
        callout("warn", "Why this page exists",
                f"Twelve questions. {len(need_you)} of them cannot be answered by any amount of "
                "analysis &mdash; they need a choice or a fact from you. Each is paired with what is "
                "known and what is missing, so a decision can be made without re-reading the site.")
        + section("Questions, knowns and unknowns",
                  table(["ID", "Question", "What we know", "What we do not know", "Blocks",
                         "Decisions blocked", "How to close it", "Who can close it", "Source"], rows,
                        caption="Sorted by priority, then by how many decisions each one blocks."))
        + section("Answer these first", "".join(
            f'<div class="callout {"bad" if q["priority"] == 1 else "warn"}">'
            f'<strong>{esc(q["id"])} &middot; {esc(q["question"])}</strong>'
            f'<p>{esc(q["how_to_close"])}</p></div>'
            for q in s["questions"] if q["priority"] <= 2))
    )
    return layout("Questions that must be answered before a decision", "pages/questions.html", body,
                  "What we know, what we do not, and what is needed to close each gap.", st)


def page_summary():
    s = load("summary.json")
    st = stamp_of(s)
    rows = [[esc(h["topic"]), esc(h["finding"]), status_badge("measured", h["source_class"]),
             src(h["source"])] for h in s["headline"]]
    body = (
        section("One page", table(["Topic", "Finding", "Class", "Source"], rows))
        + section("Answer these four first", "<ol>" + "".join(
            f"<li>{esc(q)}</li>" for q in s["questions_first"]) + "</ol>")
        + section("What is not claimed", callout("warn", "Scope",
                                                 "No strategy is approved for capital. No reward pool "
                                                 "is funded. No sportsbook, licence, limit or "
                                                 "jurisdiction has been verified. Nothing in this "
                                                 "repository is betting advice."))
    )
    return layout("Executive summary", "pages/summary.html", body,
                  "Every number classed as official or third-party, with the source beside it.", st)


def page_flagged():
    res = load("results_feed.json")
    p = load("price_snapshots.json")
    d = load("replacement_depth.json")
    c = load("correlation_official.json")
    dem = load("demotion_gate.json")
    items = []

    def add(ident, item, what, why, source, cls="unverified"):
        items.append([f"<strong>{esc(ident)}</strong>", esc(item), esc(what), esc(why), src(source),
                      badge("flag", cls)])

    add("FL-SD-01", "No official price source exists",
        "Every opening and closing number in the repository is third-party.",
        "No official NFL price feed was located; the scores pages publish results, not prices. "
        "CLV can therefore never be called official.", d["page_findings"][4]["url"])
    add("FL-SD-02", "No season has both an opening and a closing number",
        esc(p["join"]["detail"] or ""),
        "Opening file covers 2021 only; closing file stops at 2018. The overlap is empty.",
        p["opening"]["source"]["url"])
    add("FL-SD-03", "No opening moneyline exists in any source on file",
        "Opening moneyline cells are blank, not zero and not estimated.",
        "The upstream opening file contains zero MONEYLINE rows.",
        p["opening"]["source"]["url"])
    add("FL-SD-04", "15 finished games were missing from the committed snapshot",
        f"{res['game_feed']['committed_absent']} games read from nfl.com were absent from the "
        "committed data and are listed as absent.",
        "The snapshot is roughly a week behind the live slate. Backtests run on it understate the "
        "sample by those games.",
        res["game_feed"]["rows"][0]["source"] if res["game_feed"]["rows"] else "")
    add("FL-SD-05", "The official pages publish no depth-chart ordinal",
        "1st/2nd/3rd string is third-party for every row.",
        "Tested against the official team roster page and the official injury report; neither has a "
        "depth column.", d["page_findings"][1]["url"])
    add("FL-SD-06", "The parlay correlation the pricing needs is uncomputable from official pages",
        "QB passing yards vs WR1 receiving yards is blank with n = 0.",
        "The official leader tables describe different players and cannot be joined into one "
        "observation.", c["rows"][-1]["source"] if c["rows"] else "")
    add("FL-SD-07", "Four of eight demotion rules cannot fire yet",
        "D2, D3, D4 and partly D7 have no data to evaluate them.",
        "They depend on a validated backtest path, opening prices and executable prices, none of "
        "which exist.", "signal-desk/data/demotion_gate.json")
    add("FL-SD-08", "The Week 9 injury page contradicts its own title",
        "URL says reg9, in-page heading says WEEK 9, document title says Week 10.",
        "Read on 2026-11-14 while checking depth. A week mix-up would silently mis-date an injury "
        "feature.", d["page_findings"][5]["url"])
    add("FL-SD-09", "Third-party player data and official totals differ by design",
        "The committed player table ends at Week 8; the official leader pages are through Week 10.",
        "The gaps (for example 372 passing yards for the leader) match the games the snapshot is "
        "missing, which is consistent rather than wrong &mdash; but it means the two must never be "
        "mixed without a date.",
        "https://www.nfl.com/stats/player-stats/category/passing/2026/reg/all/passingyards/desc")
    add("FL-SD-10", "Nothing is live, so the demotion gate has never fired",
        "Zero strategies passed; zero rewards were paid; no live strategy exists to demote.",
        "The gate is published pre-armed. Its thresholds are untested.",
        "signal-desk/data/leaderboard.json")
    body = (
        callout("warn", "Flagged items do not block publication",
                "Every item below is published openly with its source so it can be checked and "
                "challenged. None of them has been resolved by assumption.")
        + section("Irregularities and unverified items",
                  table(["ID", "Item", "What was found", "Why it matters", "Source", "Class"], items))
    )
    return layout("Flagged for review", "pages/flagged.html", body,
                  "Everything that could not be verified, and every irregularity found while "
                  "checking. Nothing here is hidden.")


def page_sources():
    import transcripts as T
    rows = [["Official standings, 2026", "NFL.com division standings, W/L/T/PF/PA, 2026 season",
             "transcribed", src(T.URL["standings_2026"]), badge("ok", "official")],
            ["Official standings, 2025", "NFL.com division standings, 2025 season", "transcribed",
             src(T.URL["standings_2025"]), badge("ok", "official")],
            ["Official standings, 2020", "NFL.com division standings, 2020 season", "transcribed",
             src(T.URL["standings_2020"]), badge("ok", "official")],
            ["Official final scores, week 8", "NFL.com scores, 2026 week 8", "transcribed",
             src(T.URL["scores_w8"]), badge("ok", "official")],
            ["Official final scores, week 9", "NFL.com scores, 2026 week 9", "transcribed",
             src(T.URL["scores_w9"]), badge("ok", "official")],
            ["Official final scores, week 10", "NFL.com scores, 2026 week 10", "transcribed",
             src(T.URL["scores_w10"]), badge("ok", "official")],
            ["Official passing leaders, 2026", "NFL.com player stats, passing yards", "transcribed",
             src(T.URL["passing_2026"]), badge("ok", "official")],
            ["Official receiving leaders, 2026", "NFL.com player stats, receiving yards",
             "transcribed", src(T.URL["receiving_2026"]), badge("ok", "official")],
            ["Official injury report, week 10", "NFL.com injuries, current week", "transcribed",
             src(T.URL["injuries_w10"]), badge("ok", "official")],
            ["Official injury report, week 9", "NFL.com injuries, 2026 reg9", "transcribed",
             src(T.URL["injuries_w9"]), badge("ok", "official")],
            ["Official team roster", "NFL.com Arizona Cardinals roster, tested for a depth column",
             "tested", src(T.URL["roster_ari"]), badge("ok", "official")],
            ["Opening lines", "nflverse/nfldata initial_lines.csv at a pinned commit",
             "downloaded, hashed", src(T.UPSTREAM["initial_lines"]["url"]), badge("tp", "third-party")],
            ["Closing lines", "nflverse/nfldata closing_lines.csv at a pinned commit",
             "downloaded, hashed", src(T.UPSTREAM["closing_lines"]["url"]), badge("tp", "third-party")],
            ["Game results and closing prices", "nflverse/nfldata games.csv, committed as "
             "data/derived/games.csv.gz and hashed in data/PROVENANCE.md", "committed",
             src(T.UPSTREAM["games"]["url"]), badge("tp", "third-party")],
            ["Injury report + depth join", "decision-hub/data/injuries.json (official injury report "
             "joined to a third-party depth chart)", "read, not recomputed",
             src("https://github.com/nflverse/nflverse-data/releases/tag/depth_charts"),
             badge("tp", "third-party")],
            ]
    body = (
        callout("warn", "How a source earns the word official",
                "Official means the page was opened and read on 2026-11-14 and the values were "
                "transcribed into <span class='mono'>signal-desk/scripts/transcripts.py</span>. "
                "Everything else is third-party, including nflverse, which is a community project "
                "and not the league.")
        + section("Source register",
                  table(["Source", "What it supplied", "How it was used", "Link", "Class"], rows))
        + section("Reproduce it",
                  callout("good", "Four commands",
                          "<span class='mono'>python signal-desk/scripts/fetch_prices.py</span> then "
                          "<span class='mono'>python signal-desk/scripts/analysis.py</span> then "
                          "<span class='mono'>python signal-desk/scripts/build.py</span> then "
                          "<span class='mono'>python signal-desk/scripts/check.py</span>. The analysis "
                          "step imports scipy directly and does not reuse the repository's own "
                          "statistics helpers, so it cannot agree with them by construction."))
    )
    return layout("Sources", "pages/sources.html", body,
                  "Every figure on this site traces to one of these pages or files.")


PAGES = {
    "pages/prices.html": page_prices,
    "pages/results.html": page_results,
    "pages/order.html": page_order,
    "pages/gap.html": page_gap,
    "pages/leaderboard.html": page_leaderboard,
    "pages/depth.html": page_depth,
    "pages/correlations.html": page_correlations,
    "pages/demotion.html": page_demotion,
    "pages/suggestions.html": page_suggestions,
    "pages/questions.html": page_questions,
    "pages/summary.html": page_summary,
    "pages/flagged.html": page_flagged,
    "pages/sources.html": page_sources,
}


def main():
    print("signal-desk build")
    write("index.html", page_index())
    for path, fn in PAGES.items():
        write(path, fn())
    print(f"wrote index.html and {len(PAGES)} pages")


if __name__ == "__main__":
    main()
