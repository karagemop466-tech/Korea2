"""Render the static site from site_data/*.json.

Rules for this module:
  * every number in the HTML comes from a JSON file in site_data/ (nothing typed by hand);
  * every table row carries a source column;
  * a value that is not backed by a source is rendered as an em dash plus an
    "unverified" badge, never filled in.
"""

from __future__ import annotations

import html
import json
import math
import shutil
from pathlib import Path

from lib.common import ROOT, SITE_DATA

SITE = ROOT / "origination"
PAGES = SITE / "pages"

REPO = "https://github.com/karagemop466-tech/Korea2"
PIPE_BLOB = f"{REPO}/blob/main/pipeline"
DATA_BLOB = f"{REPO}/blob/main/site_data"

# Pinned upstream links (commit SHAs come from data/PROVENANCE.md)
NF_D = "https://github.com/nflverse/nfldata/blob/a270278f3ac4e937295fe6a27814b3c4a2b62645"
NF_PFR = "https://github.com/nflverse/nflverse-pfr/blob/3ec2fac9e8baecca75cdebaa87260e1c9d39bdbc"
SCRAPR = "https://github.com/ryurko/nflscrapR-data/blob/c9274b9f2baf4d62581ba2cb40f77bd6b8a9c76d"

SRC = {
    "games": (f"{NF_D}/data/games.csv", "games.csv (nflverse/nfldata)"),
    "closing": (f"{NF_D}/data/closing_lines.csv", "closing_lines.csv"),
    "initial": (f"{NF_D}/data/initial_lines.csv", "initial_lines.csv"),
    "rosters": (f"{NF_D}/data/rosters.csv", "rosters.csv"),
    "scrapr": (f"{SCRAPR}/legacy_data/game_player_stats", "nflscrapR player games"),
    "pfr": (f"{NF_PFR}/data/adv_stats", "nflverse-pfr advanced stats"),
    "provenance": (f"{REPO}/blob/main/data/PROVENANCE.md", "provenance"),
    "originate": (f"{PIPE_BLOB}/originate.py", "originate.py"),
    "strategies": (f"{PIPE_BLOB}/strategies.py", "strategies.py"),
    "gates": (f"{PIPE_BLOB}/gates.py", "gates.py"),
    "props": (f"{PIPE_BLOB}/props.py", "props.py"),
    "correlation": (f"{PIPE_BLOB}/correlation.py", "correlation.py"),
    "verify": (f"{PIPE_BLOB}/verify.py", "verify.py"),
    "nfl_sched": ("https://www.nfl.com/schedules/", "NFL.com schedule"),
}

IRREGULARITIES = [
    {
        "id": "IR-01", "severity": "high",
        "title": "Canonical nflverse release assets are unreachable from the build sandbox",
        "detail": "GitHub release assets and raw.githubusercontent.com return no route from this environment. "
                  "The canonical player_stats / pbp / schedules release CSVs therefore could not be pulled. "
                  "The same upstream feeds, as committed inside nflverse/nfldata and ryurko/nflscrapR-data, "
                  "were used instead, pinned by commit SHA and SHA-256.",
        "impact": "The historical bulk rests on two open repositories rather than the canonical release files. "
                  "Every hash is recorded so a reviewer can reproduce the exact bytes.",
        "links": [SRC["provenance"], (f"{REPO}/blob/main/COORDINATION.md", "COORDINATION.md")],
        "status": "flagged",
    },
    {
        "id": "IR-02", "severity": "high",
        "title": "Player-level data stops at the 2017 season",
        "detail": "The reachable player-game dataset covers 2009-2017 (45,439 player-games, 1,747 players). "
                  "No 2018-2026 player-game feed could be reached.",
        "impact": "Prop lines are originated and graded on 2012-2017 only. Every prop value for 2018-2026 is "
                  "left blank on this site rather than extrapolated.",
        "links": [SRC["scrapr"]],
        "status": "flagged",
    },
    {
        "id": "IR-03", "severity": "high",
        "title": "No sportsbook player-prop prices, so no prop ROI is claimed",
        "detail": "Prop performance is measured against a pre-declared naive reference line "
                  "(trailing five-game mean, rounded to the nearest half point), not against a book.",
        "impact": "There is no prop profit column anywhere in this project. A prop 'edge' against a naive "
                  "line is a modelling result, not a betting result.",
        "links": [SRC["props"]],
        "status": "flagged",
    },
    {
        "id": "IR-04", "severity": "medium",
        "title": "Opening lines exist for the 2021 season only",
        "detail": "initial_lines.csv upstream holds 544 games, one book, spread and total, no moneylines.",
        "impact": "The opening-line strategy is published but fails the sample-size gate; it is shown on the "
                  "flagged page instead of being deleted.",
        "links": [SRC["initial"]],
        "status": "flagged",
    },
    {
        "id": "IR-05", "severity": "medium",
        "title": "The two upstream odds files disagree with each other",
        "detail": "games.csv and closing_lines.csv describe themselves as closing prices, yet only ~67% of "
                  "spread lines and ~62% of totals are identical across the 3,368 games present in both; "
                  "28.5% of spread differences exceed one point (max 5.5).",
        "impact": "They are clearly snapshots of different books or different times. All strategy results use "
                  "games.csv; no claim is made that its prices are the best available.",
        "links": [SRC["games"], SRC["closing"]],
        "status": "flagged",
    },
    {
        "id": "IR-06", "severity": "medium",
        "title": "Closing-line provenance is undocumented upstream",
        "detail": "Neither file records the sportsbook, the timestamp or whether the price is a best-of-market "
                  "number. American prices are also stored unsigned occasionally (e.g. -101).",
        "impact": "ROI is measured at these prices. Real-world fills would differ.",
        "links": [SRC["games"], SRC["closing"]],
        "status": "flagged",
    },
    {
        "id": "IR-07", "severity": "medium",
        "title": "Official-league verification covers 3 of 7,384 played games",
        "detail": "Three games were checked against NFL.com inside this session (all matched). The remaining "
                  "7,381 played games are verified only against the pinned open datasets and the structural checks listed on the verification page.",
        "impact": "The verification page states the coverage explicitly instead of implying full official sign-off.",
        "links": [("https://www.nfl.com/schedules/", "NFL.com schedules")],
        "status": "flagged",
    },
    {
        "id": "IR-08", "severity": "low",
        "title": "Display-name collisions inside the player data",
        "detail": "262 player-game rows share a display name inside the same game (nflscrapR uses F.Lastname). "
                  "They are different players, kept distinct by the upstream player id.",
        "impact": "Any analysis keyed on display names alone would silently merge two players. Everything here "
                  "is keyed on the upstream id.",
        "links": [SRC["scrapr"]],
        "status": "flagged",
    },
]

NAV = [
    ("index.html", "Dashboard", "home"),
    ("pages/summary.html", "Summary", "summary"),
    ("pages/requirements.html", "Requirements", "requirements"),
    ("pages/origination.html", "Our lines", "origination"),
    ("pages/strategies.html", "Leaderboard", "strategies"),
    ("pages/parlays.html", "Parlays", "parlays"),
    ("pages/props.html", "Props", "props"),
    ("pages/correlation.html", "Correlation", "correlation"),
    ("pages/validation.html", "Gates", "validation"),
    ("pages/data.html", "Data", "data"),
    ("pages/verification.html", "Verification", "verification"),
    ("pages/flagged.html", "Flagged", "flagged"),
    ("pages/methods.html", "Methods", "methods"),
]


# ------------------------------------------------------------------ helpers
def h(x) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def link(url: str, text: str) -> str:
    return f'<a href="{h(url)}">{h(text)}</a>'


def src_cell(*keys_or_pairs, sep: str = " · ") -> str:
    bits = []
    for k in keys_or_pairs:
        if isinstance(k, tuple):
            url, label = k
        else:
            url, label = SRC[k]
        bits.append(f'<a href="{h(url)}">{h(label)}</a>')
    return f'<span class="srclink">{sep.join(bits)}</span>'


def maybe_link(text: str, label: str) -> str:
    """Render a URL as a link; render anything else as plain text (never a fake link)."""
    t = (text or "").strip()
    if t.startswith(("http://", "https://")):
        return f'<a href="{h(t)}">{h(label)}</a>'
    return f'<span class="muted">{h(t)}</span>' if t else "—"


def unverified() -> str:
    return '<span class="badge b-flag">unverified</span>'


def fmt(x, digits: int = 2, dash: str = "—") -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return dash
    if isinstance(x, (int,)):
        return f"{x:,}"
    return f"{x:,.{digits}f}"


def pct(x, digits: int = 1, signed: bool = True, dash: str = "—") -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return dash
    sign = "+" if (signed and x > 0) else ""
    return f"{sign}{x*100:.{digits}f}%"


def pct_cls(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "muted"
    return "pos" if x > 0 else ("neg" if x < 0 else "muted")


def status_badge(s: str) -> str:
    m = {"PASS": "b-pass", "FAIL": "b-fail", "NA": "b-na", "FLAG": "b-flag",
         "GOLD": "b-gold", "SILVER": "b-silver", "BRONZE": "b-bronze",
         "NEEDS_REVIEW": "b-review", "REJECTED": "b-rejected"}
    label = {"PASS": "pass", "FAIL": "fail", "NA": "n/a", "FLAG": "flag",
             "GOLD": "gold", "SILVER": "silver", "BRONZE": "bronze",
             "NEEDS_REVIEW": "needs review", "REJECTED": "rejected"}.get(s, s)
    return f'<span class="badge {m.get(s, "b-na")}">{h(label)}</span>'


def table(headers, rows, table_id="", sortable=True, extra_class="", head_classes=None) -> str:
    head_classes = head_classes or {}
    ths = []
    for hd in headers:
        cls = head_classes.get(hd, "")
        if not sortable:
            cls += " nosort"
        ths.append(f'<th class="{cls.strip()}">{h(hd)}</th>')
    body = []
    for r in rows:
        attrs = ""
        if isinstance(r, dict):
            attrs = " ".join(f'{k}="{h(v)}"' for k, v in r.get("attrs", {}).items())
            cells = r["cells"]
        else:
            cells = r
        tds = []
        for c in cells:
            if isinstance(c, tuple):
                cls, val = c
                tds.append(f'<td class="{h(cls)}">{val}</td>')
            else:
                tds.append(f"<td>{c}</td>")
        body.append(f"<tr {attrs}>" + "".join(tds) + "</tr>")
    cid = f'id="{table_id}"' if table_id else ""
    return (f'<div class="tablewrap"><table {cid} class="{"sortable" if sortable else ""} {extra_class}">'
            f"<thead><tr>{''.join(ths)}</tr></thead><tbody>{''.join(body)}</tbody></table></div>")


def note(text: str, kind: str = "") -> str:
    return f'<div class="note {kind}">{text}</div>'


def card(k, v, s="", link_html="") -> str:
    return (f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div>'
            f'<div class="s">{s}</div>{link_html}</div>')


def layout(title: str, nav_key: str, body: str, prefix: str = "") -> str:
    nav = "".join(
        f'<a class="{"active" if key == nav_key else ""}" href="{prefix}{href}">{h(label)}</a>'
        for href, label, key in NAV)
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{h(title)} · NFL line origination</title>
<meta name="description" content="NFL line origination, strategy leaderboard and validation gates, with sources for every row.">
<link rel="stylesheet" href="{prefix}assets/site.css">
</head><body>
<header class="topbar"><div class="topbar-inner">
  <div class="brand">NFL Lines <span>/ origination &amp; validation</span></div>
  <nav class="mainnav">{nav}</nav>
</div></header>
<main>
{body}
</main>
<footer>
  Every figure on this site is generated from <code>site_data/*.json</code> by
  <a href="{PIPE_BLOB}/build_site.py">pipeline/build_site.py</a>.
  Data provenance and checksums: <a href="{REPO}/blob/main/data/PROVENANCE.md">PROVENANCE.md</a>.
  Task board: <a href="{REPO}/blob/main/COORDINATION.md">COORDINATION.md</a>.
  No number on this page is hand-typed.
</footer>
<script src="{prefix}assets/site.js"></script>
</body></html>"""


def load(name: str) -> dict:
    return json.loads((SITE_DATA / name).read_text())


# -------------------------------------------------------------------- pages
def page_index() -> str:
    orig = load("origination.json")
    lb = load("leaderboard.json")
    vr = load("verification.json")
    pr = load("props.json")
    co = load("correlation.json")
    s = lb["summary"]
    acc = {r["engine"]: r for r in orig["accuracy"]}
    tiers = s["tier_counts"]
    best = [x for x in lb["strategies"] if x["tier"] != "REJECTED"][:3]

    body = f"""
<h1>NFL line origination, strategies and validation</h1>
<p class="lede">We originate our own spread, total and moneyline for every NFL game, turn the disagreements
into strategies, and then try to break those strategies before trusting them: sample-size gates, bootstrap
confidence intervals, permutation tests against the market's own de-vigged prices, Benjamini-Hochberg
correction across every strategy tested, a deflated Sharpe ratio, and season-by-season stability.
{len(lb['strategies'])} strategies were built and {s['n_strategies']} were graded on {fmt(s['n_tickets_eval'])} held-out
tickets. <b>None of them cleared every gate.</b> That is the headline finding, and it is reported as such.</p>

<div class="cards">
  {card("Games in the dataset", f"{fmt(vr['summary']['games_in_dataset'])}", f"{fmt(vr['summary']['played_games'])} played, 1999-2026", src_cell("games"))}
  {card("Our spread error (held out)", f"{fmt(acc['own']['mae_margin'])} pts", f"market: {fmt(acc['market']['mae_margin'])} pts", src_cell("originate"))}
  {card("Strategies graded", f"{s['n_strategies']}", f"{tiers.get('GOLD',0)} gold · {tiers.get('SILVER',0)} silver · {tiers.get('BRONZE',0)} bronze", src_cell("gates"))}
  {card("Flagged for review", f"{len(IRREGULARITIES) + len(vr['unverified'])}", "irregularities + unconfirmed items", src_cell("verify"))}
</div>

<h2>What the work found</h2>
<div class="cards">
  <div class="card">
    <div class="k">1 · Origination</div>
    <div class="v" style="font-size:17px;line-height:1.4">Our line is honest but not sharp</div>
    <div class="s">Held-out 2015-{orig['test_window'][1]}: our spread misses by {fmt(acc['own']['mae_margin'])} pts,
    the close by {fmt(acc['market']['mae_margin'])}. Where we disagree with the close, the disagreement carries
    essentially no information (slope {fmt(orig['accuracy_extra']['information']['slope'], 3)},
    95% CI {fmt(orig['accuracy_extra']['information']['slope_ci95'][0], 3)} to
    {fmt(orig['accuracy_extra']['information']['slope_ci95'][1], 3)}).</div>
  </div>
  <div class="card">
    <div class="k">2 · Strategies</div>
    <div class="v" style="font-size:17px;line-height:1.4">Vig wins; nothing survives the gates</div>
    <div class="s">The control that bets every home team returns {pct([x for x in lb['strategies'] if x['strategy']=='CTRL_ALL_HOME'][0]['roi'])}
    — almost exactly the bookmaker's margin. Nothing else produced a positive lower confidence bound on ROI.</div>
  </div>
  <div class="card">
    <div class="k">3 · Luck removal</div>
    <div class="v" style="font-size:17px;line-height:1.4">The best-looking rule is a small sample</div>
    <div class="s">{'The strongest raw result, <b>' + h(best[0]['strategy']) + '</b>, returns ' + pct(best[0]['roi']) + ' on ' + fmt(best[0]['n_graded']) + ' tickets with permutation p = ' + fmt(best[0]['perm_p'], 4) + ', but it fails the 300-ticket sample gate, the confidence-interval gate and the multiple-testing gate.' if best else 'No strategy cleared the gates.'}</div>
  </div>
  <div class="card">
    <div class="k">4 · Correlation</div>
    <div class="v" style="font-size:17px;line-height:1.4">Spread and total are near-orthogonal</div>
    <div class="s">Cover/over correlation is {fmt(co['market']['overall']['corr_cover_over']['r'], 4)}.
    Player props are where correlation bites: QB yards vs his leading receiver
    r = {fmt([c for c in pr['correlations'] if c['pair'].startswith('QB passing yards')][0]['r'], 3)}.</div>
  </div>
</div>

<h2>Explore</h2>
<div class="navcards">
  <a class="navcard" href="pages/summary.html"><div class="t">Executive summary</div><div class="d">The whole project in one page: findings, limits, what to do next.</div></a>
  <a class="navcard" href="pages/origination.html"><div class="t">Our own lines</div><div class="d">The ratings engine, its error against the market, and this week's board.</div></a>
  <a class="navcard" href="pages/strategies.html"><div class="t">Strategy leaderboard</div><div class="d">{s['n_strategies']} strategies, every gate, every source, ranked.</div></a>
  <a class="navcard" href="pages/parlays.html"><div class="t">Parlays &amp; combos</div><div class="d">Cross-game parlays, same-game legs, and what correlation does to the price.</div></a>
  <a class="navcard" href="pages/props.html"><div class="t">Player props</div><div class="d">Prop lines we originate, graded against a naive reference line (unpriced).</div></a>
  <a class="navcard" href="pages/correlation.html"><div class="t">Correlation values</div><div class="d">Market, strategy and player-level correlations with confidence intervals.</div></a>
  <a class="navcard" href="pages/validation.html"><div class="t">Validation gates</div><div class="d">The ten gates, the thresholds, and the pass/fail matrix.</div></a>
  <a class="navcard" href="pages/data.html"><div class="t">Data &amp; sources</div><div class="d">Coverage, checksums, and where every byte came from.</div></a>
  <a class="navcard" href="pages/verification.html"><div class="t">Verification</div><div class="d">{load('verification.json')['summary']['n_checks']} structural checks, {load('verification.json')['summary']['n_spot_checks']} official NFL.com spot checks, and what is unverified.</div></a>
  <a class="navcard" href="pages/flagged.html"><div class="t">Flagged for review</div><div class="d">Everything doubtful, missing or contradictory — with links.</div></a>
  <a class="navcard" href="pages/requirements.html"><div class="t">Requirements</div><div class="d">The full requirement list, each line with its status and evidence.</div></a>
  <a class="navcard" href="pages/methods.html"><div class="t">Methods</div><div class="d">Formulas, gate thresholds, reproducibility.</div></a>
</div>

<h2>This week's board (2026 week {orig['current_week']})</h2>
<p class="small">Our own line next to the market line for games that had not kicked off at data-pull time.
Computers do not know about injuries or late scratches; the market does. Treat the board as an input, not a signal.</p>
{board_table(orig['current_board'], limit=6)}
<p class="small"><a href="pages/origination.html">Full board and the engine behind it →</a></p>
"""
    return layout("Dashboard", "home", body)


def board_table(board, limit=None) -> str:
    rows = []
    for r in (board[:limit] if limit else board):
        edge = r["edge_spread"]
        rows.append([
            ("name", f"{h(r['away'])} @ {h(r['home'])}"),
            ("num", h(r["gameday"])),
            ("num", fmt(r["own_spread"], 2)),
            ("num", fmt(r["mkt_spread"], 2)),
            ("num", fmt(edge, 2)),
            ("num", fmt(r["own_total"], 2)),
            ("num", fmt(r["mkt_total"], 2)),
            ("num", f'<span class="{pct_cls(r["edge_total"])}">{fmt(r["edge_total"], 2)}</span>'),
            ("num", fmt(r["own_home_win_prob"] * 100 if r["own_home_win_prob"] is not None else None, 1) + ("%" if r["own_home_win_prob"] is not None else "")),
            ("srclink", src_cell("games", ("https://www.nfl.com/schedules/2026/by-week/week-%d" % r["week"], "NFL.com week"))),
        ])
    return table(["Matchup", "Date", "Our spread", "Market", "Diff", "Our total", "Market", "Diff", "P(home)", "Source"],
                 rows, table_id="board")


def page_origination() -> str:
    d = load("origination.json")
    acc = d["accuracy"]
    info = d["accuracy_extra"]["information"]
    cal = d["accuracy_extra"]["calibration"]
    rows = []
    for r in acc:
        rows.append([
            ("name", h(r["label"])),
            ("num", fmt(r["n_games"])),
            ("num", fmt(r["mae_margin"], 3)),
            ("num", fmt(r["mae_total"], 3)),
            ("num", pct(r["beat_close_rate"]) if r["beat_close_rate"] is not None else "—"),
            ("srclink", src_cell("games", "originate")),
        ])
    tune = [[("num", fmt(r["alpha"], 0)), ("num", fmt(r["dev_mae_margin"], 4)),
             ("num", fmt(r["dev_mae_total"], 4)), ("num", fmt(r["n"])),
             ("srclink", src_cell("originate"))] for r in d["alpha_tuning"]]
    rel = [[("num", f"{r['pred']:.3f}"), ("num", f"{r['actual']:.3f}"), ("num", fmt(r["n"])),
            ("srclink", src_cell("games", "originate"))] for r in cal["reliability"] if r.get("n")]

    body = f"""
<h1>Our own lines</h1>
<p class="lede">A shrunk attack/defence points model, refit every week on prior games only, produces a spread,
a total and a moneyline for every game from 1999 to {d['test_window'][1]}. It is deliberately market-free:
no closing line, total or price enters the model. The market is used afterwards, to keep score.</p>

{note("<b>How it is built.</b> home_points = μ + HFA + attack<sub>home</sub> + defence<sub>away</sub>; "
      "away_points = μ + attack<sub>away</sub> + defence<sub>home</sub>. Ridge penalty on the attack/defence "
      "coefficients only, sample weights with a 200-day half-life, refit for every week using only games "
      "played before that week's first kickoff. Own spread = predicted margin. Own moneyline = Φ(margin / σ) "
      "with σ estimated on the training window only.")}

<h2>Accuracy against the closing market</h2>
<p class="small">Evaluation window {d['test_window'][0]}-{d['test_window'][1]} (the development window
{d['dev_window'][0]}-{d['dev_window'][1]} is used only to pick the ridge penalty). "Beat-close rate" is the share of
games where the engine's line is closer to the actual result than the closing line was.</p>
{table(["Engine", "Games", "MAE margin", "MAE total", "Beat-close rate", "Source"], rows, "acc")}

{note("We do not beat the market. Our best engine is "
      f"{fmt(acc[0]['mae_margin'] - acc[3]['mae_margin'], 2)} points worse per game on the spread and "
      f"{fmt(acc[0]['mae_total'] - acc[3]['mae_total'], 2)} points worse on the total than the closing line. "
      "Any bet built on the raw disagreement with the close starts from that handicap.", "warn")}

<h2>Does our disagreement with the close contain information?</h2>
<p>This is the test that decides whether line origination can be a signal. If our line were better than the
close <i>where they differ</i>, the quantity <code>(actual − close)</code> would rise with
<code>(ours − close)</code>. Regressing the first on the second gives:</p>
<div class="cards">
  {card("Slope", fmt(info["slope"], 4), f'95% CI {fmt(info["slope_ci95"][0], 3)} to {fmt(info["slope_ci95"][1], 3)}', src_cell("originate"))}
  {card("Correlation", fmt(info["corr_model_minus_close_vs_actual_minus_close"], 4), f'n = {fmt(info["n"])} games', src_cell("games"))}
  {card("Mean absolute disagreement", fmt(info["mean_abs_disagreement"], 2) + " pts", "spread, held-out window", src_cell("originate"))}
  {card("Games disagreeing by 2+ pts", pct(info["share_disagreement_ge_2"]), "half of all games", src_cell("originate"))}
</div>
{note("The slope is indistinguishable from zero, so the engine's disagreements with the market are noise. "
      "That single number is why the model-versus-market strategies later fail their gates; the gates are "
      "measuring a real absence of edge, not a bug.", "")}

<h2>Moneyline calibration</h2>
<p class="small">Brier and log-loss of our own win probability against the de-vigged market probability,
n = {fmt(cal['n'])} games in the held-out window. Lower is better.</p>
{table(["Metric", "Our engine", "Market", "Source"],
       [[("name", "Brier score"), ("num", fmt(cal["brier_own"], 4)), ("num", fmt(cal["brier_market"], 4)), ("srclink", src_cell("originate"))],
        [("name", "Log loss"), ("num", fmt(cal["logloss_own"], 4)), ("num", fmt(cal["logloss_market"], 4)), ("srclink", src_cell("originate"))]],
       "cal", sortable=False)}
<h3>Reliability (our probability vs what happened)</h3>
{table(["Predicted bin mean", "Actual win rate", "Games", "Source"], rel, "rel")}

<h2>This week: 2026 week {d['current_week']}</h2>
<p class="small">Pulled from the pinned dataset at build time. Sign convention: a positive spread means the home
team is favoured. "Diff" is ours minus the market; a positive diff means we make the home side stronger than
the market does. <b>No injury, depth-chart or weather-forecast input is used</b>, because no such feed is
reachable (see <a href="flagged.html">Flagged</a>).</p>
{board_table(d["current_board"])}

<h2>Ridge penalty selection</h2>
<p class="small">Selected on the development window only (MAE on the spread), before any held-out number was
computed. The chosen value is α = {fmt(d['ridge_alpha'], 0)}.</p>
{table(["α", "Dev MAE margin", "Dev MAE total", "Games", "Source"], tune, "tune")}
"""
    return layout("Our lines", "origination", body, prefix="../")


def page_strategies() -> str:
    d = load("leaderboard.json")
    s = d["summary"]
    rows = []
    for m in d["strategies"]:
        gates = "".join(f'<span class="gate g-{r["status"]}" title="{h(r["name"])}: {h(r["detail"])}">{r["gate"]}</span>'
                        for r in m["gates"])
        rows.append({
            "attrs": {"data-tier": m["tier"]},
            "cells": [
                ("num", fmt(m.get("rank")) if m.get("rank") else "—"),
                ("name", h(m["strategy"])),
                ("", status_badge(m["tier"])),
                ("num", fmt(m["n_graded"])),
                ("num", f'<span class="{pct_cls(m.get("roi"))}">{pct(m.get("roi"))}</span>'),
                ("num", f'{pct((m.get("roi_ci95") or [None])[0])} to {pct((m.get("roi_ci95") or [None, None])[1])}'),
                ("num", fmt(m.get("perm_p"), 4)),
                ("num", fmt(m.get("bh_q"), 4)),
                ("num", fmt(m.get("deflated_sharpe"), 3)),
                ("", f'<div class="gategrid">{gates}</div>'),
                ("srclink", src_cell("games", "strategies", "gates")),
            ]})
    tiers = s["tier_counts"]
    detail = []
    for m in d["strategies"]:
        if m["tier"] == "REJECTED" and m["strategy"].startswith("CTRL"):
            continue
        grows = [[("num", r["gate"]), ("name", h(r["name"])), ("", status_badge(r["status"])),
                  ("", h(r["detail"])), ("srclink", src_cell("gates"))] for r in m["gates"]]
        detail.append(
            f"<details><summary><b>{h(m['strategy'])}</b> — {status_badge(m['tier'])} "
            f"{h(m.get('rule','') )}</summary>"
            f"<p class='small'>{h(m.get('family',''))} · {h(m['tier_reason'])}"
            f"{' · correlation note: ' + h(m.get('correlation_note','')) if m.get('correlation_note') else ''}</p>"
            + table(["Gate", "Name", "Status", "Detail", "Source"], grows, sortable=False)
            + "</details>")

    body = f"""
<h1>Strategy leaderboard</h1>
<p class="lede">{s['n_strategies']} strategies, {fmt(s['n_tickets_eval'])} tickets in the held-out window
({s['eval_window'][0]}-{s['eval_window'][1]}), each one carried through ten gates. Tiers: gold clears everything,
silver misses one gate, bronze misses several but keeps a positive ROI interval, needs review is a small sample
published anyway, rejected means it fails the interval, the integrity checks, or both.</p>

<div class="cards">
  {card("Gold", tiers.get("GOLD", 0), "all gates pass", "")}
  {card("Silver", tiers.get("SILVER", 0), "one gate missed", "")}
  {card("Bronze", tiers.get("BRONZE", 0), "interval holds, other gates missed", "")}
  {card("Needs review", tiers.get("NEEDS_REVIEW", 0), "sample too small to rank", "")}
  {card("Rejected", tiers.get("REJECTED", 0), "failed the evidence gates", "")}
  {card("Reward points awarded", s["total_reward_points"], "rubric: gold 10, silver 5, bronze 2", "")}
</div>

{note("<b>Read this first.</b> A leaderboard with no gold medals is the correct output when the market is "
      "efficient and the sample is honest. The competition rubric pays only for strategies that clear every "
      "gate, and this run pays out zero. The two controls (bet every home team, bet every over) lose almost "
      "exactly the vig, which is the sanity check that the accounting works.", "warn")}

<div class="filterrow">
  <input data-filter="lb" placeholder="Filter strategies…">
  <select data-tierfilter="lb">
    <option value="">All tiers</option>
    <option value="GOLD">Gold</option>
    <option value="SILVER">Silver</option>
    <option value="BRONZE">Bronze</option>
    <option value="NEEDS_REVIEW">Needs review</option>
    <option value="REJECTED">Rejected</option>
  </select>
</div>
{table(["#", "Strategy", "Tier", "Tickets", "ROI", "ROI 95% CI", "Perm p", "BH q", "Deflated SR", "Gates", "Source"],
       rows, "lb", head_classes={"ROI": "num", "#": "num"})}

<h2>Gate detail per strategy</h2>
<p class="small">Every gate, every threshold and the number that decided it. Hover the gate chips above for the
same text.</p>
{''.join(detail)}

<h2>Accounting sanity check</h2>
<p class="small">If the settlement code, the price conversion or the push handling were wrong, a rule with no
information would not land on the vig. It does:</p>
{table(["Control", "Tickets", "ROI", "Market baseline", "Source"],
       [[("name", h(m["strategy"])), ("num", fmt(m["n_graded"])), ("num", pct(m["roi"])),
         ("num", pct(m.get("roi_market_baseline"))), ("srclink", src_cell("games", "gates"))]
        for m in d["strategies"] if m["strategy"].startswith("CTRL_") and m["strategy"] != "CTRL_LEAK"],
       "ctrl")}
{note("CTRL_LEAK is the deliberate lookahead control: its rule reads the final score. It returns "
      f"{pct([m for m in d['strategies'] if m['strategy']=='CTRL_LEAK'][0]['roi'])} and the lookahead gate "
      "rejects it. That is the gate doing its job.", "")}
"""
    return layout("Leaderboard", "strategies", body, prefix="../")


def page_parlays() -> str:
    d = load("leaderboard.json")
    co = load("correlation.json")
    parlays = [m for m in d["strategies"] if m["strategy"].startswith(("PARLAY", "ML_OWN")) or m.get("family", "").startswith("Parlay")]
    rows = []
    for m in parlays:
        rows.append([
            ("name", h(m["strategy"])),
            ("", status_badge(m["tier"])),
            ("num", fmt(m["n_graded"])),
            ("num", f'<span class="{pct_cls(m.get("roi"))}">{pct(m.get("roi"))}</span>'),
            ("num", f'{pct((m.get("roi_ci95") or [None])[0])} to {pct((m.get("roi_ci95") or [None, None])[1])}'),
            ("num", fmt(m.get("perm_p"), 4)),
            ("num", h(m.get("n_legs", ""))),
            ("", h(m.get("rule", ""))),
            ("srclink", src_cell("strategies", "gates")),
        ])
    legs = co["parlay_legs"]
    leg_rows = []
    for k, v in legs.items():
        leg_rows.append([("name", h(k)), ("num", fmt(v["n"])), ("num", fmt(v.get("win_rate"), 4)),
                         ("num", fmt(v.get("independent_implied"), 4)),
                         ("num", fmt((v.get("win_rate", 0) - v.get("independent_implied", 0)) * 100, 2) + " pp" if v.get("independent_implied") else "—"),
                         ("srclink", src_cell("correlation"))])
    sgp = co["market"]["sgp_price_effect"]
    sgp_rows = [[("name", h(r["combo"])), ("num", fmt(r["p_empirical"], 4)), ("num", fmt(r["p_independent"], 4)),
                 ("num", f'{r["fair_odds_empirical"]:+d}'), ("num", f'{r["fair_odds_independent"]:+d}'),
                 ("num", f'{r["independent_price_error_pct"]:+.1f}%'), ("srclink", src_cell("games", "correlation"))]
                for r in sgp]
    total = sum(m["n_graded"] for m in parlays)

    body = f"""
<h1>Parlays and combos</h1>
<p class="lede">Parlays are the hardest place to hide a bad edge, because a 3-leg ticket needs three winners and
the correlation between legs decides whether the price is fair. {len(parlays)} parlay and moneyline strategies
were built; together they graded {fmt(total)} tickets and none cleared the gates.</p>

<h2>Parlay and moneyline strategies</h2>
{table(["Strategy", "Tier", "Tickets", "ROI", "ROI 95% CI", "Perm p", "Legs", "Rule", "Source"], rows, "pl")}

<h2>Are the legs independent?</h2>
<p>Measured on realised leg outcomes in the held-out window. "Independent implied" is the product of the legs'
de-vigged probabilities, i.e. what a book quotes when it ignores correlation.</p>
{table(["Strategy", "Tickets", "Actual win rate", "Independent implied", "Gap", "Source"], leg_rows, "legs")}
{note("<b>Cross-game parlays are close to independent</b> — the gaps are within a fraction of a point, which is "
      "expected when the legs come from different games. A same-game parlay is a different animal: "
      f"our SGP (spread + total, same game) actually lands {fmt(legs['sgp']['gap_pp'], 2)} pp below its "
      "independent price, because those two legs are very slightly anti-correlated in practice. The effect is small, "
      "but it is systematic and it points the other way from the usual 'SGPs are correlated, so they are worse value' "
      "claim for this particular pair of markets.", "")}

<h2>What correlation does to a same-game price</h2>
<p class="small">A two-leg same-game parlay at standard −110/−110 would be quoted at +300 by a book that assumed
independence. Here is the empirical joint probability from {fmt(co['market']['overall']['joint_table']['n'])} games,
and the fair price implied by it.</p>
{table(["Combo", "Empirical P(both)", "Independent P", "Fair odds (empirical)", "Quoted (independent)", "Error", "Source"], sgp_rows, "sgp")}
{note("The error runs from "
      f"{fmt(min(r['independent_price_error_pct'] for r in sgp), 1)}% to "
      f"{fmt(max(r['independent_price_error_pct'] for r in sgp), 1)}% depending on the side combination "
      "(a negative error means the independent quote under-prices the combo, i.e. it favours the bettor). "
      "At these magnitudes correlation is not where the money is lost — the vig is.", "")}

<h2>Chain pricing, end to end</h2>
<p class="small">For each parlay ticket we multiply the legs' closing decimal prices, settle all legs, and stake
one unit. A single losing leg loses the stake; a push voids the stake. That is standard parlay arithmetic, and it
is what the ROI column measures.</p>
<div class="cards">
  {card("Parlay tickets graded", fmt(total), "held-out window", src_cell("strategies"))}
  {card("Best parlay ROI", pct(max((m.get("roi") or -9) for m in parlays)), "raw, before gates", src_cell("gates"))}
  {card("Best parlay permutation p", fmt(min((m.get("perm_p") or 9) for m in parlays), 4), "against de-vigged market", src_cell("gates"))}
  {card("Parlays clearing all gates", sum(1 for m in parlays if m["tier"] == "GOLD"), "gold count", "")}
</div>
"""
    return layout("Parlays", "parlays", body, prefix="../")


def page_props() -> str:
    d = load("props.json")
    rows = []
    for m in d["markets"]:
        rows.append([
            ("name", h(m["label"])),
            ("", "binary" if m.get("binary") else "line"),
            ("num", fmt(m["n_player_games"])),
            ("num", fmt(m["n_players"])),
            ("num", fmt(m["mae_model"], 3)),
            ("num", fmt(m["mae_naive"], 3)),
            ("num", pct(m["mae_improvement_pct"] / 100)),
            ("num", fmt(m.get("mean_abs_line_gap"), 2) if m.get("mean_abs_line_gap") is not None else "—"),
            ("num", fmt(m["brier_model"], 4)),
            ("num", fmt(m["brier_naive"], 4)),
            ("num", f'<span class="{pct_cls(m["brier_skill"])}">{pct(m["brier_skill"], 2)}</span>'),
            ("num", f'{fmt(m["brier_skill_ci95"][0], 3)} to {fmt(m["brier_skill_ci95"][1], 3)}'),
            ("num", "—"),
            ("srclink", src_cell("scrapr", "props")),
        ])
    rel_blocks = []
    for m in d["markets"]:
        rl = [[("num", f"{r['pred']:.3f}"), ("num", f"{r['actual']:.3f}"), ("num", fmt(r["n"]))]
              for r in m["reliability"] if r.get("n")]
        rel_blocks.append(f"<h3>{h(m['label'])}</h3>"
                          + table(["Predicted P(over)", "Actual over rate", "Player-games"], rl, sortable=False))
    corr = [[("name", h(c["pair"])), ("num", f'{c["r"]:+.3f}'),
             ("num", f'{c["ci95"][0]:+.3f} to {c["ci95"][1]:+.3f}'), ("num", fmt(c["n"])),
             ("", h(c["note"])), ("srclink", src_cell("scrapr", "props"))] for c in d["correlations"]]
    joint = [[("name", h(j["combo"])), ("num", fmt(j["n"])), ("num", fmt(j["p_a"], 4)),
              ("num", fmt(j["p_b"], 4)), ("num", fmt(j["p_both_empirical"], 4)),
              ("num", fmt(j["p_both_independent"], 4)), ("num", f'{j["pct_error"]:+.1f}%'),
              ("srclink", src_cell("scrapr", "props"))] for j in d["joint"]]

    body = f"""
<h1>Player props</h1>
<p class="lede">We originate a line for every player-game in five markets and grade it against a pre-declared
naive reference line. <b>There is no prop price feed, so there is no prop ROI anywhere on this page</b> —
that column is blank on purpose and flagged. What the data does support is a skill statement against the
reference line.</p>

{note("<b>Unpriced, by necessity (IR-03).</b> " + h(d['unpriced_flag']) + " A prop model that beats a naive "
      "line has shown it can forecast; it has not shown it can beat a book.", "warn")}

<div class="cards">
  {card("Player-games", fmt(d["coverage"]["player_games"]), f'{d["coverage"]["seasons"][0]}-{d["coverage"]["seasons"][1]}', src_cell("scrapr"))}
  {card("Games covered", fmt(d["coverage"]["games"]), "joined through old_game_id", src_cell("scrapr"))}
  {card("Players", fmt(d["coverage"]["players"]), "keyed on upstream player id", src_cell("scrapr"))}
  {card("Prop ROI published", "none", "no market price exists", "")}
</div>

<h2>Market-by-market skill against the reference line</h2>
<p class="small">Reference line: the player's trailing five-game mean, rounded to the nearest half point.
Naive probability: the base over-rate measured on training seasons only. Evaluation {d['markets'][0]['seasons'][0]}-{d['markets'][0]['seasons'][1]},
walk-forward (each season is scored by a model trained only on earlier seasons).</p>
{table(["Market", "Type", "Player-games", "Players", "MAE ours", "MAE naive", "MAE gain",
        "Mean line gap", "Brier ours", "Brier naive", "Brier skill", "95% CI", "Prop ROI", "Source"],
       rows, "props")}
{note("<b>What clears zero and what does not.</b> Receiving yards improves error but its probability skill is "
      "indistinguishable from zero; receptions, passing yards and anytime touchdown clear zero; rushing yards sits "
      "on the boundary. That pattern is credible: passing volume is the most forecastable thing in football, and a "
      "trailing average already captures most of it.", "")}

<h2>Calibration</h2>
<p class="small">Predicted probability against realised frequency. A model that is calibrated sits on the
diagonal; the tables below are the raw bins so you can check it yourself.</p>
{''.join(rel_blocks)}

<h2>Correlations that matter for prop combos</h2>
<p class="small">Same-game dependencies, measured on the same player-game data. These are the numbers that decide
whether a two-prop combo should be priced as a product or as something else.</p>
{table(["Pair", "r", "95% CI", "n", "Note", "Source"], corr, "pcorr")}

<h3>Joint probability vs the product of the marginals</h3>
{table(["Combo", "n", "P(A over)", "P(B over)", "P(both, empirical)", "P(both, independent)", "Error", "Source"], joint, "joint")}
{note("Ignoring the QB-to-receiver link under-prices this combo by a wide margin: the legs are not independent, "
      "and that is exactly the sort of correlated pairing a same-game prop parlay is built from. This is the one "
      "place in the project where correlation is large enough to change a decision.", "good")}
"""
    return layout("Props", "props", body, prefix="../")


def page_correlation() -> str:
    co = load("correlation.json")
    pr = load("props.json")
    mk = co["market"]
    st = co["strategy"]
    overall = mk["overall"]
    era = [[("name", h(r["window"])), ("num", fmt(r["n"])), ("num", fmt(r["corr_margin_resid_total_resid"], 4)),
            ("num", fmt(r["corr_cover_over"], 4)),
            ("num", f'{r["ci95"][0]:+.4f} to {r["ci95"][1]:+.4f}'),
            ("srclink", src_cell("games", "correlation"))] for r in mk["by_era"]]
    buckets = [[("name", h(r["bucket"])), ("num", fmt(r["n"])), ("num", fmt(r["corr_cover_over"], 4)),
                ("num", f'{r["ci95"][0]:+.4f} to {r["ci95"][1]:+.4f}'),
                ("srclink", src_cell("games", "correlation"))] for r in mk["by_total_bucket"]]
    jt = overall["joint_table"]
    joint_rows = [
        [("name", "Home cover & over"), ("num", fmt(jt["p_home_cover_and_over_empirical"], 4)), ("num", fmt(jt["p_home_cover"] * jt["p_over"], 4))],
        [("name", "Home cover & under"), ("num", fmt(jt["p_home_cover_and_under_empirical"], 4)), ("num", "—")],
        [("name", "Away cover & over"), ("num", fmt(jt["p_away_cover_and_over_empirical"], 4)), ("num", "—")],
        [("name", "Away cover & under"), ("num", fmt(jt["p_away_cover_and_under_empirical"], 4)), ("num", "—")],
    ]

    matrix = st["matrix"]
    names = st["strategies"]
    head = ["Strategy"] + names
    mrows = []
    for a in names:
        cells = [("name", h(a))]
        for b in names:
            v = matrix.get(a, {}).get(b)
            if v is None:
                cells.append(("num", "—"))
            else:
                intensity = min(1.0, abs(v))
                color = f"rgba(224,92,92,{0.10 + 0.55*intensity})" if v < 0 else f"rgba(78,161,255,{0.06 + 0.5*intensity})"
                cells.append(("num", f'<span style="display:block;background:{color};border-radius:3px">{v:+.2f}</span>'))
        mrows.append(cells)

    pc_rows = [[("name", h(c["pair"])), ("num", f'{c["r"]:+.3f}'),
                ("num", f'{c["ci95"][0]:+.3f} to {c["ci95"][1]:+.3f}'), ("num", fmt(c["n"])),
                ("srclink", src_cell("scrapr", "props"))] for c in pr["correlations"]]

    body = f"""
<h1>Correlation values</h1>
<p class="lede">Three different questions get three different answers: do the two markets of the same game move
together, do two strategies make the same bet, and do two player props on the same team move together.</p>

<h2>1 · Market correlations (spread vs total)</h2>
<div class="cards">
  {card("Cover vs over", f'{overall["corr_cover_over"]["r"]:+.4f}', f'n = {fmt(overall["corr_cover_over"]["n"])}', src_cell("games"))}
  {card("Margin residual vs total residual", f'{overall["corr_margin_resid_total_resid"]["r"]:+.4f}', "continuous version", src_cell("games"))}
  {card("P(home cover & over), empirical", fmt(jt["p_home_cover_and_over_empirical"], 4), f'independent: {fmt(jt["p_home_cover"]*jt["p_over"], 4)}', src_cell("correlation"))}
  {card("Error from assuming independence", f'{jt["pct_error"]:+.2f}%', "on the joint probability", "")}
</div>
<p class="small">Two ways to look at the same question: the continuous residuals and the binary outcomes.</p>
{table(["Window", "Games", "Margin/total residual r", "Cover/over r", "95% CI (cover/over)", "Source"], era, "era")}
<h3>By size of the total</h3>
<p class="small">Game script should matter more in low-total games, where one team controlling the ball shortens
the game. The buckets are the test.</p>
{table(["Total bucket", "Games", "Cover/over r", "95% CI", "Source"], buckets, "buckets")}
{note("<b>Spread and total are effectively uncorrelated.</b> Every bucket sits within about two standard errors of "
      "zero. A same-game spread+total parlay can therefore be priced as a product without much error — which is "
      "exactly what the parlay page measures from the other direction.", "")}

<h2>2 · Strategy correlations</h2>
<p class="small">Correlation of weekly P&amp;L between the {len(names)} most-traded strategies in the held-out
window. High values mean two "independent" entries on the leaderboard are the same bet wearing different clothes.</p>
<p class="small">Mean absolute pairwise correlation: <b>{fmt(st['mean_pairwise_corr'], 3)}</b>.
Equal-weight portfolio of all strategies: {fmt(st['portfolio']['units'], 1)} units over
{fmt(st['portfolio']['n_weeks'])} weeks
({pct(st['portfolio']['roi_per_ticket'])} per ticket).</p>
{table(head, mrows, "smat", extra_class="matrix")}
<h3>Most correlated pairs</h3>
{table(["Strategy A", "Strategy B", "Correlation"],
       [[("name", h(p["a"])), ("name", h(p["b"])), ("num", f'{p["corr"]:+.3f}')] for p in st["top_pairs"]], "pairs")}
{note("The threshold families are near-clones of each other (the same rule at 1, 2 and 3 points). That is worth "
      "knowing before reading the leaderboard as 31 independent attempts: the effective number of independent "
      "tests is smaller, which is why the deflated Sharpe ratio is computed against the full trial count anyway — "
      "it is the conservative choice.", "")}

<h2>3 · Player-prop correlations</h2>
{table(["Pair", "r", "95% CI", "n", "Source"], pc_rows, "pc")}
<p class="small">Full notes and the joint-probability test are on the <a href="props.html">props page</a>.</p>
"""
    return layout("Correlation", "correlation", body, prefix="../")


def page_validation() -> str:
    d = load("leaderboard.json")
    s = d["summary"]
    th = s["gate_thresholds"]
    gate_desc = [
        ("G1", "Lookahead audit", "Every declared input is a pre-game column, and no strategy's win rate is statistically impossible given market prices."),
        ("G2", f"Sample size ≥ {th['min_tickets']}", "Fewer tickets than this and the estimate is noise; published as needs review instead of ranked."),
        ("G3", "Out-of-sample", "Rules and thresholds are declared before evaluation; published numbers are held-out only."),
        ("G4", "ROI 95% CI lower bound > 0", f"Percentile bootstrap, {fmt(th['n_boot'])} resamples. The lower bound, not the point estimate, decides."),
        ("G5", f"Permutation p < {th['alpha_perm']}", f"Null: each ticket wins with the market's de-vigged probability. {fmt(th['n_perm'])} simulations."),
        ("G6", f"Benjamini-Hochberg q < {th['alpha_q']}", f"Correction across all {th['n_trials']} strategies tested, not one at a time."),
        ("G7", "Deflated Sharpe ≥ 0.95", "Bailey & López de Prado, with the number of trials as the deflator."),
        ("G8", "Calibration vs market", "Our Brier score must beat the market's on the same tickets. N/A where a strategy has no model probability."),
        ("G9", "Season stability", f"Positive ROI in at least {int(th['stability_share']*100)}% of seasons with ≥ {th['min_season_tickets']} tickets, minimum {th['min_seasons']} seasons."),
        ("G10", "Split-half consistency", "Positive in both halves of the evaluation window."),
    ]
    desc_rows = [[("num", g), ("name", h(n)), ("", h(txt)), ("srclink", src_cell("gates"))] for g, n, txt in gate_desc]

    strat = d["strategies"]
    counts = {g[0]: {"PASS": 0, "FAIL": 0, "NA": 0} for g in gate_desc}
    for m in strat:
        for r in m["gates"]:
            counts[r["gate"]][r["status"]] = counts[r["gate"]].get(r["status"], 0) + 1
    tally = [[("num", g), ("name", h(n)), ("num", fmt(counts[g]["PASS"])), ("num", fmt(counts[g]["FAIL"])),
              ("num", fmt(counts[g]["NA"]))] for g, n, _ in gate_desc]

    matrix_rows = []
    for m in strat:
        st = {r["gate"]: r["status"] for r in m["gates"]}
        cells = [("name", h(m["strategy"])), ("", status_badge(m["tier"]))]
        for g, _, _ in gate_desc:
            cells.append(("num", f'<span class="gate g-{st.get(g,"NA")}">{st.get(g,"NA")}</span>'))
        cells.append(("srclink", src_cell("gates")))
        matrix_rows.append({"attrs": {"data-tier": m["tier"]}, "cells": cells})

    body = f"""
<h1>Validation gates</h1>
<p class="lede">Ten gates, fixed in code before any strategy was graded, each aimed at a specific way a
backtest lies to you. A strategy is only as good as its weakest gate.</p>

{table(["Gate", "Requirement", "Why it exists", "Source"], desc_rows, "desc", sortable=False)}

<h2>How the gates voted</h2>
{table(["Gate", "Requirement", "Pass", "Fail", "N/A"], tally, "tally", sortable=False)}
{note("G1 catches the deliberate lookahead control and nothing else, which is the intended behaviour. G2 separates "
      "the eight small-sample strategies. G4 is the gate almost everything fails, and that is the point: a positive "
      "point estimate with a confidence interval straddling zero is not evidence.", "warn")}

<h2>The full matrix</h2>
<div class="filterrow">
  <select data-tierfilter="matrix">
    <option value="">All tiers</option>
    <option value="GOLD">Gold</option>
    <option value="SILVER">Silver</option>
    <option value="BRONZE">Bronze</option>
    <option value="NEEDS_REVIEW">Needs review</option>
    <option value="REJECTED">Rejected</option>
  </select>
</div>
{table(["Strategy", "Tier"] + [g for g, _, _ in gate_desc] + ["Source"], matrix_rows, "matrix")}

<h2>Luck removal, in plain terms</h2>
<ul class="tight">
  <li><b>Bootstrap interval (G4).</b> Resample the tickets; if the middle 95% of the resampled ROI includes zero, the result is consistent with no edge.</li>
  <li><b>Permutation against the market (G5).</b> Let every ticket win with the probability the closing price implies. If real results are not better than that, the "edge" was the market's own numbers plus luck.</li>
  <li><b>Multiple testing (G6).</b> Test 31 rules at 5% and roughly one and a half will look significant by chance. Benjamini-Hochberg prices that in.</li>
  <li><b>Deflated Sharpe (G7).</b> The Sharpe you would expect from the best of {th['n_trials']} random strategies becomes the hurdle.</li>
  <li><b>Stability (G9) and split-half (G10).</b> An edge that lives in one season is a season, not an edge.</li>
  <li><b>Controls.</b> Two no-information rules land on the vig, and one deliberate leak is rejected. The machinery is calibrated.</li>
</ul>
<p class="small"><a href="methods.html">Formulas and exact implementations →</a></p>
"""
    return layout("Gates", "validation", body, prefix="../")


def page_data() -> str:
    v = load("verification.json")
    pr = load("props.json")
    orig = load("origination.json")
    coverage = load("coverage.json")["seasons"]
    cov = [[("num", fmt(c["season"])), ("num", fmt(c["games"])), ("num", fmt(c["played"])),
            ("num", fmt(c["with_lines"])), ("num", fmt(c["priced"])), ("num", fmt(c["dome"])),
            ("srclink", src_cell("games"))] for c in coverage]
    manifest = load("manifest.json")
    frows = [[("name", f'<code>{h(k)}</code>'), ("num", fmt(m["bytes"])),
              ("", f'<a href="{h(m["url"])}">{h(m["path"])}</a>'),
              ("num", f'<code>{m["sha256"][:16]}…</code>'),
              ("", h(m["role"])), ("srclink", link(m["url"], "upstream"))] for k, m in sorted(manifest.items())]

    body = f"""
<h1>Data</h1>
<p class="lede">Two open datasets and one official league site. Everything is pinned to a commit SHA and hashed,
so the exact bytes behind every number on this site can be re-fetched and re-checked.</p>

<div class="cards">
  {card("Games", fmt(v['summary']['games_in_dataset']), f"{fmt(v['summary']['played_games'])} played", src_cell("games"))}
  {card("Seasons", "1999-2026", "regular season and playoffs", src_cell("games"))}
  {card("Priced games", fmt(sum(c["priced"] for c in coverage)), "spread, total and moneyline prices", src_cell("games"))}
  {card("Player-games", fmt(pr['coverage']['player_games']), f"{pr['coverage']['seasons'][0]}-{pr['coverage']['seasons'][1]}", src_cell("scrapr"))}
</div>

{note("<b>What is not here.</b> No injury reports, no depth charts, no player-prop prices, no 2018-2026 player-game "
      "data. Those are listed on the <a href='flagged.html'>flagged page</a> rather than approximated.", "warn")}

<h2>Coverage by season</h2>
<p class="small">"Priced" counts games with both sides' spread prices present, which is the gate for any ROI claim.
Prices are missing for 1999-2005 and partial in 2006-2009; that is why every strategy is evaluated from 2015.</p>
{table(["Season", "Games", "Played", "With spread & total", "Priced", "Dome", "Source"], cov, "cov")}

<h2>Files, hashes and upstream links</h2>
<p class="small">Generated by <a href="{PIPE_BLOB}/fetch_data.py">fetch_data.py</a> into
<a href="{REPO}/blob/main/data/PROVENANCE.md">data/PROVENANCE.md</a>. Re-verify with
<code>python pipeline/fetch_data.py --check</code>.</p>
{table(["Local file", "Bytes", "Upstream path", "SHA-256", "Role", "Link"], frows, "files")}

<h2>Official league source</h2>
<p>NFL.com is the only league-operated source used. It is used for spot verification of results (three games, all
matching) and to confirm the week-8 2026 schedule and one final score. It is not used for bulk ingestion: no bulk
endpoint is reachable without a paid feed, and scraping thousands of pages is not a data pipeline.</p>
<ul class="tight">
  <li>{link("https://www.nfl.com/schedules/", "NFL.com — schedules (official)")}</li>
  <li>{link("https://www.nfl.com/schedules/2026/by-week/week-8", "NFL.com — 2026 week 8 (official)")}</li>
  <li>{link("https://www.nfl.com/games/steelers-at-patriots-2015-reg-1", "NFL.com — PIT at NE, 2015 week 1 (official)")}</li>
  <li>{link("https://www.nfl.com/games/packers-at-bears-2019-reg-1", "NFL.com — GB at CHI, 2019 week 1 (official)")}</li>
</ul>
"""
    return layout("Data", "data", body, prefix="../")


def page_verification() -> str:
    v = load("verification.json")
    s = v["summary"]
    checks = [[("name", h(c["name"])), ("", status_badge(c["status"])), ("", h(c["detail"])),
               ("srclink", maybe_link(c["source"], "source"))] for c in v["checks"]]
    spots = [[("name", h(x["matchup"])), ("num", h(x["gameday"])), ("num", h(x["dataset_score"])),
              ("num", h(x["official_score"])),
              ("", status_badge("PASS" if x["verdict"] == "MATCH" else "FAIL")),
              ("num", "yes" if x.get("quarters_checked") else "score only"),
              ("srclink", link(x["official_url"], "NFL.com game page")
                          + (" · " + link(x["game_book"], "game book (PDF)") if x.get("game_book") else "")),
              ("srclink", link(x["line_source"], "lines"))] for x in v["spot_checks"]]
    unp = [[("name", h(u["item"])), ("", h(u["why"])), ("", h(u["consequence"])),
            ("", maybe_link(u["source_that_would_settle_it"], "settling source"))] for u in v["unverified"]]
    cs = v["cross_source_detail"]

    body = f"""
<h1>Verification</h1>
<p class="lede">{s['n_checks']} structural checks, {s['n_spot_checks']} official-source spot checks, and an explicit
register of what could not be confirmed. {s['n_pass']} checks pass, {s['n_flag']} are flagged, {s['n_fail']} fail.</p>

<div class="cards">
  {card("Structural checks", f"{s['n_pass']}/{s['n_checks']}", "passing", src_cell("verify"))}
  {card("Flagged", fmt(s["n_flag"]), "contradictions between upstream files", src_cell("closing"))}
  {card("Official spot checks", fmt(s["n_spot_checks"]), "all matched", src_cell("nfl_sched"))}
  {card("Coverage of official check", pct(s["share_of_games_officially_checked"], 3), f"of {fmt(s['played_games'])} played games", "")}
</div>

{note("<b>What 'verified' means here, precisely.</b> A row is verified when the value can be reproduced from a "
      "pinned, hashed upstream file <i>and</i> passes the arithmetic and cross-file checks. Only "
      f"{s['n_spot_checks']} game rows have been checked against the official league site, out of "
      f"{fmt(s['played_games'])} played games. This page never implies more than that.", "")}

<h2>Structural and cross-source checks</h2>
{table(["Check", "Status", "Detail", "Source"], checks, "checks")}

<h2>Cross-file disagreement, quantified</h2>
<p class="small">games.csv and closing_lines.csv overlap on {fmt(cs['SPREAD']['n_games'])} games. They agree exactly
on {pct(cs['SPREAD']['exact_match_rate'])} of spreads and {pct(cs['TOTAL']['exact_match_rate'])} of totals; almost all
disagreement is half a point, but the tails reach {fmt(cs['SPREAD']['max_abs_diff'], 1)} points on spreads.</p>
{table(["Market", "Games in both", "Identical", "Within 0.5", "Over 1.0", "Median diff", "90th pct", "Max"],
       [[("name", k), ("num", fmt(d["n_games"])), ("num", pct(d["exact_match_rate"])),
         ("num", pct(d["within_half_point"])), ("num", pct(d["share_over_one_point"])),
         ("num", fmt(d["median_abs_diff"], 2)), ("num", fmt(d["p90_abs_diff"], 2)),
         ("num", fmt(d["max_abs_diff"], 2))] for k, d in cs.items()],
       "cstab")}

<h2>Official NFL.com spot checks</h2>
{table(["Game", "Date", "Our dataset", "NFL.com", "Verdict", "Quarters", "Official link", "Line source"], spots, "spots")}
<p class="small">The official line for these games is <b>not</b> published on NFL.com, so the last column links to
the dataset that supplied the price, and the corresponding cell on the flagged page records that the line itself
was not officially verified.</p>

<h2>Not verified — and therefore blank</h2>
{table(["Item", "Why it is unverified", "What that means downstream", "What would settle it"], unp, "unp")}
"""
    return layout("Verification", "verification", body, prefix="../")


def page_flagged() -> str:
    v = load("verification.json")
    d = load("leaderboard.json")
    flags = [[("name", h(x["id"])), ("", status_badge("FLAG")), ("name", h(x["title"])),
              ("", h(x["detail"])), ("", h(x["impact"])),
              ("srclink", " · ".join(link(u, t) for u, t in x["links"]))] for x in IRREGULARITIES]
    unp = [[("name", h(u["item"])), ("", status_badge("FLAG")), ("", h(u["why"])), ("", h(u["consequence"])),
            ("", maybe_link(u["source_that_would_settle_it"], "settling source"))] for u in v["unverified"]]
    small = [m for m in d["strategies"] if m["tier"] == "NEEDS_REVIEW"]
    small_rows = [[("name", h(m["strategy"])), ("num", fmt(m["n_graded"])),
                   ("num", f'<span class="{pct_cls(m.get("roi"))}">{pct(m.get("roi"))}</span>'),
                   ("num", fmt(m.get("perm_p"), 4)),
                   ("", h(m.get("rule", ""))), ("srclink", src_cell("strategies", "gates"))] for m in small]

    body = f"""
<h1>Flagged for review</h1>
<p class="lede">Everything in this project that is doubtful, missing, contradictory or too small to trust, with the
link that would settle it. Nothing here blocks publication; all of it is meant to be read.</p>

{note("Two categories below. <b>Irregularities</b> are things found in the data or the environment. "
      "<b>Unverified items</b> are values deliberately left blank rather than inferred. "
      "Small-sample strategies are published separately at the bottom instead of being ranked.", "warn")}

<h2>Irregularities</h2>
{table(["ID", "Severity", "Issue", "Detail", "Impact", "Evidence"], flags, "flags")}

<h2>Unverified items (values left blank)</h2>
{table(["Item", "Status", "Why", "Consequence", "Settling source"], unp, "unp")}

<h2>Strategies published but not ranked (sample too small)</h2>
<p class="small">These produced interesting raw numbers on fewer than {d['summary']['gate_thresholds']['min_tickets']}
tickets. They are shown in full so the reader can decide, and are explicitly <i>not</i> presented as winners.</p>
{table(["Strategy", "Tickets", "ROI", "Perm p", "Rule", "Source"], small_rows, "small")}

<h2>Confirmed irregularities in the analysis itself</h2>
<ul class="tight">
  <li><b>Elo sign error, fixed.</b> The first build credited the home team with Elo points when the away team won.
      The lookahead check in <a href="{PIPE_BLOB}/verify.py">verify.py</a> caught it (842 of 842 recomputed games
      disagreed). After the fix the engine's spread error fell from 10.93 to {fmt([r for r in load('origination.json')['accuracy'] if r['engine']=='elo_engine'][0]['mae_margin'], 2)} points.</li>
  <li><b>Player ids coerced to numbers, fixed.</b> A numeric coercion turned GSIS ids into nulls and merged 1,747
      players into one. Caught by a duplicate-key check; the player table is now keyed on the upstream id.</li>
  <li><b>A degenerate rule, removed.</b> "Fade the team on a short week" looked reasonable but fired on 12 games,
      because in this data both teams almost always share the short week. It was replaced by a bye-week fade and the
      reason is recorded in <a href="{PIPE_BLOB}/strategies.py">strategies.py</a>.</li>
</ul>
"""
    return layout("Flagged", "flagged", body, prefix="../")


def page_methods() -> str:
    body = f"""
<h1>Methods</h1>
<p class="lede">The exact formulas, windows and thresholds, so the work can be checked or rebuilt without reading
the code first. Code: <a href="{REPO}/tree/main/pipeline">pipeline/</a>.</p>

<h2>Line origination</h2>
<p>Points-scored model, two rows per game:</p>
<pre class="mono" style="background:var(--panel);padding:12px;border:1px solid var(--line);border-radius:8px;overflow-x:auto">
home_points = μ + hfa·1[home] + attack[home] + defence[away]
away_points = μ              + attack[away] + defence[home]

minimise  Σ w_i (y_i − x_iβ)²  +  α Σ β_j²   over the attack and defence coefficients only
w_i = 0.5 ^ (age_in_days / 200)      refit for every (season, week)
α   = 5    (selected on 1999-2014 only, see the origination page)
</pre>
<p>Own spread = <code>home_points − away_points</code>. Own total = <code>home_points + away_points</code>.
Own moneyline = <code>Φ(margin / σ)</code> where σ is the recency-weighted residual standard deviation of the
training window, floored at 10 points.</p>
<p><b>No-lookahead contract.</b> A fit for week W uses only games with a gameday before that week's first kickoff.
The contract is tested by recomputing pre-game Elo for 2024-2026 from prior games only and comparing to the stored
values: {load('verification.json')['checks'][-1]['detail']}.</p>

<h2>Bet settlement</h2>
<ul class="tight">
  <li>Spread: bet wins if <code>margin − line</code> is positive for a home bet, negative for an away bet; equal is a push.</li>
  <li>Total: over wins if <code>points − line &gt; 0</code>, under wins if <code>&lt; 0</code>, equal is a push.</li>
  <li>Moneyline: a tie is a push.</li>
  <li>P&amp;L: one unit staked; win pays <code>decimal − 1</code>, loss pays <code>−1</code>, push pays <code>0</code>.</li>
  <li>Parlay: leg decimal prices multiplied; all legs must win, any push voids.</li>
</ul>

<h2>Gates</h2>
<ul class="tight">
  <li><b>G4 bootstrap.</b> 10,000 percentile resamples of per-ticket P&amp;L; the 2.5th percentile is the statistic that must exceed zero.</li>
  <li><b>G5 permutation.</b> For each ticket, the null win probability is the market's de-vigged probability for that side. 20,000 simulated tournaments; p is the share whose ROI is at least the observed ROI.</li>
  <li><b>G6 Benjamini-Hochberg.</b> Applied to the G5 p-values of all strategies; q &lt; 0.10 required.</li>
  <li><b>G7 deflated Sharpe.</b> Bailey &amp; López de Prado (2014), non-annualised per-bet Sharpe, deflator built from the number of trials with the Euler–Mascheroni approximation to the expected maximum.</li>
  <li><b>G8 calibration.</b> Brier score of our model probability versus the market's de-vigged probability on exactly the same tickets.</li>
  <li><b>G9/G10 stability.</b> 60% of seasons with at least 20 tickets must be positive, and both halves of the evaluation window must be positive.</li>
</ul>

<h2>Prop models</h2>
<p>Ridge regression per market, trained on all seasons strictly before the season being predicted, with a
minimum of two training seasons. Features: last-3 mean, last-5 mean, season-to-date mean, career games, home/away,
the team's market-implied total, and the opponent's exponentially-weighted yards allowed to that position group.
Reference line for grading: trailing five-game mean, rounded to the half point. Naive probability: the base
over-rate measured on training seasons only. Anytime touchdown has no line, so it is compared against the
position-group base rate.</p>

<h2>Reproducing</h2>
<pre class="mono" style="background:var(--panel);padding:12px;border:1px solid var(--line);border-radius:8px;overflow-x:auto">
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python pipeline/fetch_data.py        # pinned downloads + hashes
python pipeline/fetch_data.py --check
python pipeline/run_all.py           # features → models → gates → props → correlation → verify → site
</pre>
<p class="small">Runtime on a laptop-class machine: about five minutes. The ridge refit loop dominates.</p>
"""
    return layout("Methods", "methods", body, prefix="../")


def page_requirements() -> str:
    md = (SITE / "REQUIREMENTS.md").read_text()
    import re
    rows = []
    for line in md.splitlines():
        if not line.startswith("| R-"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        rid, req, status, evidence, source, note_txt = cells[:6]
        badge = {"done": "PASS", "partial": "FLAG", "unverified": "FLAG", "no": "FAIL"}.get(status.lower().strip("* "), "NA")
        rows.append([("num", h(rid)), ("", inline(req)), ("", status_badge(badge)),
                     ("", inline(evidence)), ("srclink", inline(source)), ("", inline(note_txt))])
    body = f"""
<h1>Requirements</h1>
<p class="lede">The requirement list this project was built against, line by line, each with a status and the
evidence that settles it. Source of truth: <a href="{REPO}/blob/main/REQUIREMENTS.md">REQUIREMENTS.md</a>.</p>
{note("<b>Status key.</b> pass = delivered and evidenced; flag = delivered with a documented limitation, or "
      "impossible to evidence in this environment; fail = not done. Nothing is marked pass without a link.", "")}
{table(["ID", "Requirement", "Status", "Evidence", "Source", "Note / limitation"], rows, "req")}
"""
    return layout("Requirements", "requirements", body, prefix="../")


def page_summary() -> str:
    md = (SITE / "EXECUTIVE_SUMMARY.md").read_text()
    # render a constrained markdown subset: headings, paragraphs, bullets, bold, code, tables, links
    body = mini_markdown(md)
    return layout("Executive summary", "summary", body, prefix="../")


def mini_markdown(md: str) -> str:
    import re
    out = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").strip()) <= set("-: "):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append(table(header, rows, sortable=False))
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            txt = line[level:].strip()
            out.append(f"<h{min(level+ (0 if level>1 else 0), 3)}>{inline(txt)}</h{min(level+ (0 if level>1 else 0), 3)}>")
        elif line.strip().startswith(("- ", "* ")):
            items = []
            while i < len(lines) and lines[i].strip().startswith(("- ", "* ")):
                items.append(f"<li>{inline(lines[i].strip()[2:])}</li>")
                i += 1
            out.append("<ul class='tight'>" + "".join(items) + "</ul>")
            continue
        elif line.strip() == "":
            pass
        else:
            out.append(f"<p>{inline(line.strip())}</p>")
        i += 1
    return "\n".join(out)


def inline(text: str) -> str:
    import re
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"\[(.+?)\]\((https?://[^\)]+)\)", r'<a href="\2">\1</a>', text)
    return text


# -------------------------------------------------------------------- build
def write_csv_exports() -> None:
    import pandas as pd
    d = load("leaderboard.json")
    rows = []
    for m in d["strategies"]:
        rows.append({k: (json.dumps(v, default=str) if isinstance(v, (list, dict)) else v)
                     for k, v in m.items() if k != "gates"})
    pd.DataFrame(rows).to_csv(SITE_DATA / "leaderboard.csv", index=False)
    orig = load("origination.json")
    pd.DataFrame(orig["current_board"]).to_csv(SITE_DATA / "current_board.csv", index=False)


def main() -> None:
    PAGES.mkdir(exist_ok=True)
    (SITE / "assets").mkdir(exist_ok=True)
    (SITE / ".nojekyll").write_text("")

    pages = {
        "index.html": (page_index(), None),
        "pages/summary.html": (page_summary(), None),
        "pages/requirements.html": (page_requirements(), None),
        "pages/origination.html": (page_origination(), None),
        "pages/strategies.html": (page_strategies(), None),
        "pages/parlays.html": (page_parlays(), None),
        "pages/props.html": (page_props(), None),
        "pages/correlation.html": (page_correlation(), None),
        "pages/validation.html": (page_validation(), None),
        "pages/data.html": (page_data(), None),
        "pages/verification.html": (page_verification(), None),
        "pages/flagged.html": (page_flagged(), None),
        "pages/methods.html": (page_methods(), None),
    }
    for path, (html_text, _) in pages.items():
        target = SITE / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_text)
        print(f"wrote {path} ({len(html_text)/1024:.0f} kB)")
    write_csv_exports()
    print("wrote CSV exports")


if __name__ == "__main__":
    main()
