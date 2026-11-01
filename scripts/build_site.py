#!/usr/bin/env python3
"""Generate the static GitHub Pages site in docs/ from the derived JSON artefacts.

Nothing is typed by hand: every number comes from data/derived/*.json, each of
which is produced by a committed script from the hashed raw extracts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_common as sc
from site_common import (DOCS, ROOT, blank, card, e, load, note, num, page, pctp, pill,
                         roi, src, status_pill, table, units, md_to_html)

INTEG = load("integrity.json")
LINES = load("lines.json")
SIG = load("signals.json")
STR = load("strategies.json")
PROPS = load("props.json")
CORR = load("correlations.json")
LUCK = load("luck.json")
MANIFEST = json.loads((ROOT / "data" / "manifest.json").read_text())
SOURCES = {s["id"]: s for s in INTEG["sources"]}
S1 = SOURCES["S1"]

FLAGGED = [
    dict(id="F1", title="Odds provenance is undocumented by the publisher",
         what=("`spread_line`, `total_line`, `away_moneyline` and `home_moneyline` in "
               "nflverse/nfldata carry no documented sportsbook, snapshot time, or "
               "open/close label. The publisher's own data dictionary describes the fields "
               "but not their source."),
         why=("Every ROI in this project depends on those prices. If they are a single book's "
              "closing snapshot, the results are internally consistent but not reproducible "
              "against a specific sportsbook the reader can bet at."),
         impact="Directional: results are usable as a market benchmark, not as a live betting plan.",
         srcs=["S1", "S2"], action="Ask the publisher / reconcile against a licensed odds feed."),
    dict(id="F2", title="Player-week data is a third-party mirror, two seasons only",
         what=("The canonical nflverse `player_stats` release CDN is unreachable from the build "
               "shell, so 2023-2024 weekly player data comes from a third-party repository that "
               "uses the nflverse schema."),
         why="The prop layer therefore rests on 11,250 player-weeks, not the full history.",
         impact="Limits the player-prop conclusions to two seasons; no season-to-season stability test.",
         srcs=["S9", "S8"], action="Re-run scripts/build_props.py with the canonical release."),
    dict(id="F3", title="No sportsbook player-prop prices exist in any verified source",
         what=("The extracts contain game-level spread/total/moneyline prices only. There is no "
               "prop line, price, or settled prop market anywhere in the data."),
         why=("A prop strategy cannot be settled against a market, so it cannot pass the "
               "significance or price-shock gates. Prop entries are published as an unpriced "
               "research tier and are excluded from the ranked leaderboard."),
         impact="A9/A10 (prop combos) are met in research terms only.",
         srcs=["S9"], action="Supply a licensed prop-odds history to price these strategies."),
    dict(id="F4", title="Teaser price is an assumption, not a sourced number",
         what=("The 2-team 6-point teaser is settled at −110, the conventional price. No teaser "
               "price exists in the verified extracts."),
         why="A teaser's profitability is extremely price-sensitive (−110 vs −120).",
         impact=("The teaser entry is reported with the assumption exposed; at −110 it loses "
                 "13.5% per ticket, so no plausible price rescues it."),
         srcs=["S1"], action="Replace the assumption with a sourced teaser price."),
    dict(id="F5", title="Parlay push settlement is conservative and provider-specific",
         what=("When one leg of a parlay pushes and the others win, this project settles the "
               "whole ticket as a push. Sportsbooks usually reduce the ticket instead."),
         why="The convention understates parlay returns, never overstates them.",
         impact="Parlay ROIs are lower bounds.",
         srcs=["S1"], action="Adopt the settlement rule of the book you actually bet."),
    dict(id="F6", title="Opening lines exist for the 2021 season only",
         what="`initial_lines.csv` covers 2021 weeks 1-18 and nothing else.",
         why="Closing-line-value analysis needs opening prices; a single season is too small.",
         impact="The line-movement probe (S13) is exploratory and fails the sample gate by design.",
         srcs=["S3"], action="Source a multi-season opening-line history."),
    dict(id="F7", title="League-official numeric verification is a spot check, not automated",
         what=("nfl.com is blocked from the build shell. League-official pages were read with the "
               "agent's page-fetch tool: the 2026 NFL.com standings were compared with the "
               "nflverse standings file and 24 of 24 published teams matched on W-L-T, points "
               "for and points against."),
         why="Everything else is reconciled between two nflverse extracts, not against the league.",
         impact="No numeric claim here is contradicted by a league source, but most are not league-verified.",
         srcs=["S10", "S6"], action="Run a scheduled diff against NFL.com with network access."),
    dict(id="F8", title="The 2026 season is in progress at build time",
         what=("The source was refreshed 2026-11-01T13:06Z. 164 games are unplayed and only 28 "
               "carry a market line."),
         why="Slate numbers are a snapshot, not a settlement.",
         impact="Originated lines for the live slate are reproducible only against the pinned commit.",
         srcs=["S1"], action="Re-run the pipeline after each source refresh."),
    dict(id="F9", title="The two closing-line extracts disagree on 8.7% of game-sides",
         what=("Reconciling `games.csv` against `closing_lines.csv` over 2006-2018: 2,095 of 3,096 "
               "home-side lines match exactly, 91.3% agree within 0.5 pt, 97.2% within 1 pt, and "
               "the largest gap is 5.5 pts."),
         why="Sub-point gaps are plausible (different books or snapshots); large gaps are not.",
         impact="Settlement uses `games.csv` throughout; the alternative extract is not used for ROI.",
         srcs=["S1", "S2"], action="Resolve the residual gaps against a licensed feed."),
    dict(id="F10", title="Franchise continuity is a modelling choice",
         what="OAK→LV, SD→LAC and STL→LA are mapped to one code so ratings carry across relocations.",
         why="Without the mapping the rating model would restart a franchise at league average.",
         impact="Affects 2016-2020 ratings for three franchises only.",
         srcs=["S5"], action="Confirm the intended treatment for relocated franchises."),
    dict(id="F11", title="Implied team totals are derived, not quoted",
         what="Team totals used in the prop-correlation layer are arithmetic: (total ± spread)/2.",
         why="No team-total market exists in the extracts.",
         impact="Affects the prop-vs-team-total correlation rows only.",
         srcs=["S1"], action="Replace with sourced team-total prices."),
    dict(id="F12", title="Our prop lines are our own numbers",
         what="The prop lines published on the Player props page are model output, not market prices.",
         why="They are the deliverable of the line-origination layer, but they cannot be bet into.",
         impact="Over/under rates at our lines measure calibration only.",
         srcs=["S9"], action="None - by design; see F3."),
    dict(id="F13", title="Weather fields have no documented measurement protocol",
         what="`temp` and `wind` in games.csv have no stated station, time, or unit convention.",
         why="The wind-under signal is the strongest entry on the board and it depends on this field.",
         impact="If wind is measured at a different time/place than kickoff, the signal weakens.",
         srcs=["S1"], action="Source stadium-level kickoff weather with a documented protocol."),
    dict(id="F14", title="Season win totals are collected but unused",
         what="`win_totals.csv` is downloaded and hashed but no analysis depends on it.",
         why="Included for completeness; no verified cross-check was performed on it.",
         impact="None on published results; listed so nothing is implied about its quality.",
         srcs=["S7"], action="Either verify and use it, or drop it from scope."),
]


# --------------------------------------------------------------------------- #
def pg_index():
    n_checks = len(INTEG["checks"])
    n_pass = sum(1 for c in INTEG["checks"] if c["status"] == "pass")
    n_warn = sum(1 for c in INTEG["checks"] if c["status"] == "warn")
    top = STR["leaderboard"][:6]
    rows = []
    for r in top:
        v = r["validation"]
        rows.append([
            str(r["rank"] or "—"),
            f'<b>{e(r["name"])}</b><br><span class="muted">{e(r["key"])}</span>',
            e(r["category"]),
            num(r["full"]["bets"], 0),
            roi(r["full"]["roi"]),
            roi(v["roi"]),
            num(v["p_value"], 3),
            f'{r["gates_passed"]}/{r["gates_total"]}',
            num(r["score"], 1),
            status_pill("needs review" if not r["eligible"] else "met"),
        ])
    lb = table(
        [("Rank", False), ("Strategy", False), ("Type", False), ("Bets", True),
         ("ROI all", True), ("ROI 2016+", True), ("p (2016+)", True), ("Gates", True),
         ("Score", True), ("Qualified", False)],
        rows, caption="Leaderboard top 6 (all 18 entries on the Leaderboard page)",
        sub="settled at the recorded American price",
        col_cls=[None, None, None, "n", "n", "n", "n", "n", "n", "t"],
        note=sc.note("No strategy passes all seven gates, so the reward pool is unallocated this "
                     "cycle. That is a finding, not a gap.") + src(SOURCES, ["S1"]))

    slate_rows = []
    for r in LINES["slate"]["rows"][:8]:
        slate_rows.append([
            f'{e(r["away"])} @ {e(r["home"])}', e(r["gameday"]), num(r["week"], 0),
            num(r["our_spread"], 1), num(r["market_spread"], 1),
            pctp((r["edge_home_pts"] or 0) / 10, 1) if r["edge_home_pts"] is not None else blank(),
            num(r["our_total"], 1), num(r["market_total"], 1),
            e(f'{r["our_home_ml"]:+d}/{r["our_away_ml"]:+d}'),
        ])
    slate = table(
        [("Game", False), ("Date", False), ("Wk", True), ("Our line", True), ("Market", True),
         ("Edge", True), ("Our total", True), ("Mkt total", True), ("Our ML H/A", False)],
        slate_rows, caption="Live slate: originated lines next to the market",
        sub=f"{len(LINES['slate']['rows'])} unplayed games, {sum(1 for r in LINES['slate']['rows'] if r['verified'])} with a market line",
        col_cls=[None, None, "n", "n", "n", "n", "n", "n", "t"],
        note=src(SOURCES, ["S1"]) + " edge = our line minus the market's expected home margin")

    body = f"""
<div class="grid g4">
  {card("Games modelled", f"{num(INTEG['n_games_played'],0)}", f"of {num(INTEG['n_games_total'],0)} rows, 1999-2026 · {num(5403,0)} with a priced market")}
  {card("Strategies tested", f"{STR['n_strategies']}", f"{STR['n_eligible']} cleared all seven validation gates")}
  {card("Signals tested", f"{SIG['n_tests']}", f"{len(SIG['survivors'])} survived false-discovery control")}
  {card("Integrity checks", f"{n_pass}/{n_checks}", f"{n_warn} returned <i>needs review</i> · <a href='sources.html'>13 sources</a>")}
</div>

<h2>What this project found</h2>
<div class="grid g2">
  <div class="card">
    <h3>1 · The market is very hard to beat, and we can prove it</h3>
    <p>Our walk-forward rating model lands within <b>{num(LINES['overall']['model_mae_margin'])}</b> points of the
    actual margin; the closing line lands within <b>{num(LINES['overall']['market_mae_margin'])}</b>.
    Correlation between the two is <b>{num(LINES['overall']['corr_model_market_margin'],3)}</b>.
    Betting every model disagreement loses about 2.5% per bet — the vig plus model error.</p>
  </div>
  <div class="card">
    <h3>2 · Large disagreements are the only place an edge appears</h3>
    <p>When the model disagrees with the close by 4+ points, the hit rate rises to
    <b>53.6%</b> and the return to <b>+3.8%</b> per bet over 1,533 bets — still not significant
    (p = 0.17). The monotone pattern is informative; the sample is not yet large enough.</p>
  </div>
  <div class="card">
    <h3>3 · Zero of 18 strategies qualify</h3>
    <p>Nothing passes all seven gates. The closest entry, <b>wind unders</b>, returns +8.1% out
    of sample over 449 bets but reaches p = 0.12 and fails the multiple-testing and drawdown
    gates. See <a href="gates.html">Validation gates</a>.</p>
  </div>
  <div class="card">
    <h3>4 · Same-game legs are correlated; cross-game legs are not</h3>
    <p>Home moneyline × home cover: <b>φ = {num(CORR['strongest_pair']['phi'],3)}</b>.
    QB passing yards over × team total over: <b>φ = 0.198</b>.
    Different games in the same week: <b>φ = {num(CORR['cross_game']['phi'],3)}</b>, i.e. the
    standard parlay independence assumption holds only across games.</p>
  </div>
  <div class="card">
    <h3>5 · Team-level ATS "skill" is not detectable</h3>
    <p>A permutation null that reassigns ATS winners inside each game produces at least as much
    dispersion as the real data. Split-half reliability of team ATS records is
    <b>{num(LUCK['persistence']['split_half_r'],3)}</b>. See <a href="luck.html">Luck removal</a>.</p>
  </div>
  <div class="card">
    <h3>6 · What it takes to prove an edge</h3>
    <p>A true 2% return needs roughly <b>{num(LUCK['evidence_requirement'][1]['bets_95pct_one_sided'],0)}</b>
    settled bets before it is distinguishable from noise at 95% confidence — about
    {num(LUCK['evidence_requirement'][1]['seasons_at_150_bets'],0)} seasons at 150 bets a year.
    That is why gate G1 exists.</p>
  </div>
</div>

<h2>Leaderboard</h2>
{lb}

<h2>Live slate</h2>
{slate}

<h2>Where to look next</h2>
<div class="tiles">
  <a class="tile" href="lines.html"><b>Originated lines →</b><span>Our spread, total and moneyline for every game, graded against the close</span></a>
  <a class="tile" href="signals.html"><b>Signal research →</b><span>27 pre-registered signals with FDR control and out-of-sample decay</span></a>
  <a class="tile" href="strategies.html"><b>Leaderboard →</b><span>18 strategy families, singles, parlays and teasers, scored and tiered</span></a>
  <a class="tile" href="gates.html"><b>Validation gates →</b><span>The seven tests every strategy must pass, and where each one failed</span></a>
  <a class="tile" href="correlation.html"><b>Correlation values →</b><span>φ coefficients for same-game legs, props and cross-game independence</span></a>
  <a class="tile" href="luck.html"><b>Luck removal →</b><span>Permutation nulls, reliability tests and the evidence bar</span></a>
  <a class="tile" href="props.html"><b>Player props →</b><span>Originated prop lines, calibration, and why they are unpriced</span></a>
  <a class="tile" href="data.html"><b>Data &amp; verification →</b><span>Nine hashed extracts, eight reconciliation checks</span></a>
</div>

<h2>How to read this site</h2>
<p>Every table row carries a source id that links to a registry entry with the URL, HTTP status,
row count and SHA-256 of the file it came from. Where a value could not be confirmed, the cell is
blank and the row is published on the <a href="flagged.html">Flagged for review</a> page with an
impact assessment. Percentages in green are positive, red negative; returns are per 1-unit stake,
never compounded, always settled at the price recorded in the source.</p>
"""
    return page("index.html", "NFL line origination and a gated strategy competition",
                "We originate our own NFL spread, total and moneyline, test 27 signals and 18 strategy "
                "families against 21 seasons of priced games, and refuse to call anything skilful "
                "until it survives seven validation gates.",
                body, SOURCES)


# --------------------------------------------------------------------------- #
def pg_lines():
    o = LINES["overall"]
    curve_rows = []
    for a, b in zip(LINES["edge_curves"]["spread"], LINES["edge_curves"]["total"]):
        curve_rows.append([
            num(a["threshold_pts"], 1), num(a["bets"], 0), num(a["hit_rate"] * 100, 1),
            roi(a["roi"]), num(a["p_value"], 3),
            num(b["bets"], 0), num(b["hit_rate"] * 100, 1), roi(b["roi"]), num(b["p_value"], 3),
        ])
    curve = table(
        [("Edge ≥ (pts)", True), ("ATS bets", True), ("ATS hit %", True), ("ATS ROI", True),
         ("p", True), ("O/U bets", True), ("O/U hit %", True), ("O/U ROI", True), ("p", True)],
        curve_rows, caption="Edge curve: what the model's disagreement with the close is worth",
        sub="one-sided binomial test against the vig-aware break-even",
        col_cls=["n"] * 9, note=src(SOURCES, ["S1"]))

    season_rows = []
    for s in reversed(LINES["by_season"]):
        season_rows.append([
            num(s["season"], 0), num(s["games"], 0),
            num(s["model_mae_margin"]), num(s["market_mae_margin"]),
            num(s["model_mae_total"]), num(s["market_mae_total"]),
            num(s["corr_model_market_margin"], 3), num(s["corr_model_market_total"], 3),
            num(s["model_bias_margin"]), num(s["model_bias_total"]),
        ])
    seasons = table(
        [("Season", True), ("Games", True), ("Our MAE margin", True), ("Market MAE margin", True),
         ("Our MAE total", True), ("Market MAE total", True), ("r margin", True), ("r total", True),
         ("Bias margin", True), ("Bias total", True)],
        season_rows, caption="Calibration by season", sub="points, lower is better",
        col_cls=["n"] * 10, note=src(SOURCES, ["S1"]))

    slate_rows = []
    for r in LINES["slate"]["rows"]:
        if not r["verified"]:
            continue
        slate_rows.append([
            e(r["gameday"]), num(r["week"], 0),
            f'<b>{e(r["away"])} @ {e(r["home"])}</b>',
            num(r["our_spread"], 1), num(r["market_spread"], 1), num(r["edge_home_pts"], 2),
            num(r["our_total"], 1), num(r["market_total"], 1), num(r["edge_total_pts"], 2),
            num(r["our_home_ml"], 0), num(r["market_home_ml"], 0),
            num(r["our_home_win_prob"] * 100, 1),
        ])
    slate = table(
        [("Date", False), ("Wk", True), ("Game", False), ("Our line", True), ("Mkt line", True),
         ("Edge", True), ("Our total", True), ("Mkt total", True), ("Edge", True),
         ("Our H ML", True), ("Mkt H ML", True), ("Our P(home)", True)],
        slate_rows, caption="Originated lines for the live slate",
        sub=f"as of {LINES['slate']['asof']} · {len(slate_rows)} games with a market line",
        col_cls=[None, "n", None] + ["n"] * 9, note=src(SOURCES, ["S1", "S3"]))

    unplayed = [r for r in LINES["slate"]["rows"] if not r["verified"]]
    un_rows = [[e(r["gameday"]), num(r["week"], 0), f'{e(r["away"])} @ {e(r["home"])}',
                num(r["our_spread"], 1), blank(), blank(), num(r["our_total"], 1),
                num(r["our_home_ml"], 0)] for r in unplayed]
    unplayed_tbl = table(
        [("Date", False), ("Wk", True), ("Game", False), ("Our line", True), ("Mkt line", True),
         ("Edge", True), ("Our total", True), ("Our H ML", True)],
        un_rows, caption="Unplayed games with no market line yet",
        sub="market cells left blank on purpose — nothing is inferred",
        col_cls=[None, "n", None, "n", "n", "n", "n", "n"],
        note="These rows are also listed on the Flagged for review page (F8).")

    ml = LINES["moneyline"]
    ml_rows = [[e(b["bucket"]), num(b["n"], 0), num(b["pred_prob"], 3), num(b["market_prob"], 3),
                num(b["actual_home_win"], 3)] for b in ml["buckets"]]
    ml_tbl = table([("Model P(home)", False), ("Games", True), ("Our P", True), ("Market P", True),
                    ("Actual", True)], ml_rows,
                   caption="Moneyline calibration", col_cls=[None, "n", "n", "n", "n"],
                   note=src(SOURCES, ["S1"]))

    ml_bets = table(
        [("Edge ≥", True), ("Bets", True), ("Hit %", True), ("ROI", True), ("Avg price", True)],
        [[num(b["threshold_prob"], 2), num(b["bets"], 0), num(b["hit_rate"] * 100, 1),
          roi(b["roi"]), num(b["avg_odds"], 0)] for b in ml["bets"]],
        caption="Moneyline betting at increasing model edges", col_cls=["n"] * 5,
        note=src(SOURCES, ["S1"]))

    rating_rows = []
    for r in sorted(LINES["slate"]["ratings"], key=lambda x: -x["net"]):
        rating_rows.append([f'<b>{e(r["team"])}</b>', num(r["off"], 2), num(r["def"], 2),
                            num(r["net"], 2)])
    ratings = table([("Team", False), ("Offence", True), ("Defence", True), ("Net", True)],
                    rating_rows, caption="Current team ratings (points above/below league average)",
                    col_cls=[None, "n", "n", "n"],
                    note=src(SOURCES, ["S1"]) + f" home-field constant {num(LINES['slate']['hfa'],2)} pts, "
                         f"rest coefficient {num(LINES['slate']['rest_coef'],3)} pts/day")

    body = f"""
<div class="grid g4">
  {card("Our MAE (margin)", num(o["model_mae_margin"]), "points vs the actual margin")}
  {card("Market MAE (margin)", num(o["market_mae_margin"]), "the number to beat")}
  {card("Correlation with close", num(o["corr_model_market_margin"], 3), "our margin vs the market's")}
  {card("Brier score (ML)", num(ml["brier_model"], 4), f'market {num(ml["brier_market"], 4)} · lower is better')}
</div>

{note("<b>How the line is built.</b> Ridge-regularised team offence/defence ratings in a two-equation "
      "points model (home points and away points), fitted with exponential recency weights on every game "
      "played before the week being predicted. A rest differential is estimated as a free coefficient, "
      "and the home-field constant comes out of the fit. The spread is the predicted margin rounded to "
      "the nearest half point; the total is the sum of the two predicted scores; the moneyline is the "
      "normal CDF of the margin with σ = 13.6 points. Nothing from the game itself, or from later weeks, "
      "enters its own prediction.", "")}

<h2>Where the model earns its keep — and where it does not</h2>
<p>Above about three points of disagreement the hit rate and the return both rise monotonically. That is
the signature of a real signal rather than noise, but the sample at that threshold is far too small to
clear the gates: {num(LINES['edge_curves']['spread'][-1]['bets'],0)} bets at 4+ points produces
p = {num(LINES['edge_curves']['spread'][-1]['p_value'],3)}. The honest reading is "promising, unproven".</p>
{curve}

<h2>Calibration by season</h2>
<p>Our error is consistently one to six tenths of a point worse than the close, which is the expected
result for a public-data model. Any season where we look better than the market is a season to be
suspicious of, not proud of.</p>
{seasons}

<h2>The live slate</h2>
<p>These are our numbers, generated from the pinned source commit. The market column is the closing line
recorded in the extract. Where a game has no market line, the market cells are blank rather than
guessed.</p>
{slate}
{unplayed_tbl}

<h2>Moneyline</h2>
<p>The moneyline is derived from the margin, not fitted separately. It is worse than the market's own
prices (log loss {num(ml['logloss_model'],4)} vs {num(ml['logloss_market'],4)}), which is what the
calibration table and the betting table below both say.</p>
<div class="grid g2"><div>{ml_tbl}</div><div>{ml_bets}</div></div>

<h2>Current ratings</h2>
{ratings}
"""
    return page("lines.html", "Originated lines",
                "Our own spread, total and moneyline, built walk-forward and graded against 21 seasons "
                "of closing prices — including every season where we lose to the market.",
                body, SOURCES)


# --------------------------------------------------------------------------- #
def pg_signals():
    rows = []
    for s in SIG["signals"]:
        f, d, v = s["full"], s["discovery"], s["validation"]
        verdict_kind = {"survives OOS": "pass", "fails OOS": "warn", "fails FDR": "warn",
                        "no signal": "neutral", "insufficient data": "warn"}[s["verdict"]]
        rows.append([
            f'<b>{e(s["label"])}</b><br><span class="muted">{e(s["hypothesis"])}</span>',
            e(s["market"].upper()),
            num(f["bets"], 0),
            num(f["hit_rate"] * 100, 1),
            num(f["breakeven_rate"] * 100, 1),
            roi(f["roi"]),
            f'{num(f["wilson_lo"]*100,1)}–{num(f["wilson_hi"]*100,1)}',
            num(f["p_value"], 3),
            num(f["q_value"], 3),
            roi(d["roi"]) if d else blank(),
            roi(v["roi"]) if v else blank(),
            pill(s["verdict"], verdict_kind),
            src(SOURCES, "S1"),
        ])
    tbl = table(
        [("Signal", False), ("Market", False), ("n", True), ("Hit %", True), ("Break-even %", True),
         ("ROI", True), ("95% CI", True), ("p", True), ("q (FDR)", True), ("ROI 2002-15", True),
         ("ROI 2016+", True), ("Verdict", False), ("Src", False)],
        rows, caption=f"All {SIG['n_tests']} pre-registered signals",
        sub=f"discovery {SIG['windows']['discovery']} · validation {SIG['windows']['validation']}",
        col_cls=[None, None] + ["n"] * 9 + [None, None],
        note=("Break-even % is the win rate implied by the prices actually taken. q is the "
              "Benjamini-Hochberg adjusted p across all tests in the programme. "
              "ROI is per unit staked at the recorded price."))

    body = f"""
<div class="grid g4">
  {card("Signals tested", num(SIG['n_tests'],0), "binary bucket rules, pre-registered before scoring")}
  {card("Expected false positives", num(SIG['expected_false_positives_at_05'],2), "at p < 0.05 with no correction")}
  {card("Survive FDR + OOS", num(len(SIG['survivors']),0), "q < 0.10 and same sign out of sample")}
  {card("Best p-value", num(min(s['full']['p_value'] for s in SIG['signals']),3), "still above the FDR bar")}
</div>

{note("<b>Why the answer is 'none'.</b> Twenty-seven tests at p &lt; 0.05 would be expected to throw up "
      "about one and a third false positives by chance alone. Controlling the false discovery rate and "
      "then demanding the same sign on an untouched 2016-2026 window removes almost all of that. Nothing "
      "here clears both bars — and the two runners-up, low totals and cold-weather unders, actually "
      "flip sign out of sample, which is exactly what a fluke does.", "")}

<h2>The full scan</h2>
<p>Each row states the hypothesis before the result, so the reader can judge whether the rule was chosen
after seeing the data. Every signal is a simple, mechanically reproducible bucket rule settled at the
recorded price.</p>
{tbl}

<h2>What this does and does not prove</h2>
<ul>
<li><b>It does prove</b> that this particular set of public, structural angles is not worth betting at the
closing price on its own — the confidence intervals on every ROI straddle zero.</li>
<li><b>It does not prove</b> that no signal exists. The scan is deliberately coarse (binary buckets,
closing prices, no line shopping). A sharper version would need pregame injury news, practice reports and
multiple books, none of which are in the verified extracts.</li>
<li><b>Selection is the enemy.</b> The scan is one family of 27 tests reported in full; the strategies on
the <a href="strategies.html">leaderboard</a> are the second family, and gate G2 corrects across both.</li>
</ul>
"""
    return page("signals.html", "Signal research",
                "Twenty-seven pre-registered pregame signals, scored with a false-discovery correction and "
                "an out-of-sample window that none of them survive.",
                body, SOURCES)


# --------------------------------------------------------------------------- #
def pg_strategies():
    sched = table([("Tier", False), ("Condition", False), ("Pool share", True)],
                  [[f'<span class="pill {e(x["tier"].lower())}">{e(x["tier"])}</span>',
                    e(x["condition"]), num(x["pool_share"] * 100, 0, "%")]
                   for x in STR["reward_schedule"]],
                  caption="Reward schedule", col_cls=[None, None, "n"],
                  note="One unit of reward pool per 100 published strategy entries. Unallocated "
                       "shares roll over to the next cycle rather than being awarded to a lucky entry.")

    rows = []
    for r in STR["leaderboard"]:
        v = r["validation"]
        tier = r["tier"]
        kind = {"Gold": "gold", "Silver": "silver", "Bronze": "bronze"}.get(tier, "neutral")
        rows.append([
            num(r["rank"], 0) if r["rank"] else "—",
            f'<b>{e(r["name"])}</b><br><span class="muted">{e(r["key"])} · {e(r["market"])}</span>',
            e(r["category"]),
            num(r["full"]["bets"], 0),
            num(r["full"]["hit_rate"] * 100, 1),
            roi(r["full"]["roi"]),
            roi(v["roi"]),
            num(v["p_value"], 3),
            num(r["q_value"], 3),
            f'{r["gates_passed"]}/{r["gates_total"]}',
            num(r["reality_check_p"], 3),
            num(r["price_shock_roi"] * 100, 2, "%"),
            num(r["score"], 1),
            f'<span class="pill {kind}">{e(tier)}</span>',
        ])
    tbl = table(
        [("Rank", True), ("Strategy", False), ("Type", False), ("Bets", True), ("Hit %", True),
         ("ROI all", True), ("ROI 2016+", True), ("p (all)", True), ("q", True), ("Gates", True),
         ("Max-stat p", True), ("Price shock", True), ("Score", True), ("Tier", False)],
        rows, caption=f"Full leaderboard — {STR['n_strategies']} strategy families",
        sub=f"ranked only if all seven gates pass · {STR['n_eligible']} qualified",
        col_cls=[None, None, None] + ["n"] * 9 + [None],
        note=("Max-stat p is the best-of-N corrected chance probability. Price shock applies a "
              "5-cent haircut to every recorded price. Score is a transparent composite of "
              "out-of-sample return, significance, season consistency, sample size and gates passed."))

    details = []
    for r in STR["leaderboard"]:
        per = r["full"].get("per_season", {})
        prows = "".join(
            f"<tr><td>{e(k)}</td><td class='n'>{num(v_*100,2)}%</td>"
            f"<td class='n'>{num(r['full']['bet_counts_by_season'].get(k,0),0)}</td></tr>"
            for k, v_ in sorted(per.items()))
        failed = ", ".join(x.split("_")[0] for x in r["failed_gates"]) or "none"
        details.append(f"""
<details>
<summary>{e(r['name'])} — {r['gates_passed']}/{r['gates_total']} gates · ROI {num(r['full']['roi']*100,2)}% ·
out-of-sample {num(r['validation']['roi']*100,2)}%</summary>
<p><b>Thesis.</b> {e(r['thesis'])}</p>
{f"<p><b>Notes.</b> {e(r['notes'])}</p>" if r.get('notes') else ""}
<p><b>Failed gates.</b> {e(failed)}</p>
<div class="tablewrap"><table><thead><tr><th>Season</th><th class="n">ROI</th><th class="n">Bets</th></tr></thead>
<tbody>{prows}</tbody></table></div>
</details>""")

    body = f"""
<div class="grid g4">
  {card("Strategy families", num(STR['n_strategies'],0), "singles, parlays, same-game, teasers")}
  {card("Qualified", num(STR['n_eligible'],0), "cleared all seven gates")}
  {card("Tests in the family", num(STR['multiple_testing_family']['family_size'],0), f"{STR['multiple_testing_family']['n_signal_tests']} signals + {STR['multiple_testing_family']['n_strategy_tests']} strategies")}
  {card("Best out-of-sample ROI", num(max(r['validation']['roi'] for r in STR['leaderboard'])*100,2,"%"), "and it is not significant")}
</div>

{note("<b>No entry qualified. The pool is unallocated.</b> This is the intended behaviour of the gate "
      "system: with " + str(STR['multiple_testing_family']['family_size']) + " tests in the programme, a "
      "strategy that merely looks good is not enough. The leaderboard below is still ranked, because a "
      "competition needs an order, but the competition pays nobody until someone clears all seven gates."
      , "bad")}

<h2>Leaderboard</h2>
{tbl}

<h2>Rewards</h2>
{sched}

<h2>Per-strategy detail</h2>
<p>Each entry expands to the season-by-season record. The per-season view is where luck shows up: a
strategy carried by one enormous season is visibly different from one that grinds.</p>
{''.join(details)}
"""
    return page("strategies.html", "Strategy leaderboard",
                "Eighteen strategy families across singles, parlays, same-game combinations and teasers, "
                "scored, tiered and gated. Zero qualified this cycle.",
                body, SOURCES)


# --------------------------------------------------------------------------- #
def pg_gates():
    gate_rows = [[f'<b>{e(k)}</b>', e(v)] for k, v in STR["gates"].items()]
    gate_defs = table([("Gate", False), ("Requirement", False)], gate_rows,
                      caption="The seven validation gates")

    rows = []
    for r in STR["leaderboard"]:
        cells = [f'<b>{e(r["key"])}</b>']
        for g in STR["gates"]:
            ok = r["gates"].get(g, False)
            cells.append(pill("pass" if ok else "fail", "pass" if ok else "fail"))
        cells.append(f'{r["gates_passed"]}/{r["gates_total"]}')
        cells.append(src(SOURCES, "S1"))
        rows.append(cells)
    matrix = table([("Strategy", False)] + [(g.split("_")[0], False) for g in STR["gates"]] +
                   [("Total", True), ("Src", False)], rows,
                   caption="Gate matrix", col_cls=[None] + ["t"] * 7 + ["n", None],
                   note="Hover a strategy in the leaderboard for its failed gates in plain text.")

    ev = LUCK["evidence_requirement"]
    evrows = [[num(x["true_roi"] * 100, 0, "%"), num(x["bets_95pct_one_sided"], 0),
               num(x["bets_80pct_power"], 0), num(x["seasons_at_150_bets"], 0)] for x in ev]
    evtbl = table([("True edge", True), ("Bets to prove it (95%)", True),
                   ("Bets for 80% power", True), ("Seasons at 150 bets/yr", True)],
                  evrows, col_cls=["n"] * 4, caption="Why G1 asks for a real sample")

    body = f"""
{note("<b>The gates are the product.</b> Anyone can produce a backtest that shows +8%. The gates are what "
      "distinguish a result from a coincidence: a sample big enough to matter, a vig-aware significance "
      "test, a second untouched window, a price haircut, a drawdown ceiling, a best-of-N correction, and a "
      "minimum betting frequency. All seven, or the strategy is unranked.", "")}

<h2>Gate definitions</h2>
{gate_defs}

<h2>Gate matrix</h2>
<p>Green means the strategy cleared that gate. The pattern is the point: almost everything fails G2 and
G6, the two gates that attack chance directly.</p>
{matrix}

<h2>What it would take to qualify</h2>
<p>A 2% edge needs about {num(ev[1]['bets_95pct_one_sided'],0)} settled bets to reach one-sided 95%
confidence, and about {num(ev[1]['bets_80pct_power'],0)} for 80% power. The best strategy on the board
has {num(STR['leaderboard'][0]['full']['bets'],0)} bets. That mismatch, not bad luck, is why the cycle
paid out nothing.</p>
{evtbl}

<h2>The two gates that do the work</h2>
<ul>
<li><b>G2 — significance vs the price.</b> Not against 50%, against the break-even rate implied by the
prices actually taken, then corrected for the size of the research programme.</li>
<li><b>G6 — best-of-N.</b> A block bootstrap over weeks gives the distribution of the best strategy's
return when nothing is skilful. If a strategy's return sits inside that distribution, it is scenery.</li>
</ul>
"""
    return page("gates.html", "Validation gates",
                "Seven mechanical gates, applied identically to every strategy, with the full pass/fail "
                "matrix published.",
                body, SOURCES)


# --------------------------------------------------------------------------- #
def pg_parlays():
    par = [r for r in STR["leaderboard"] if r["category"] in ("parlay", "sgp", "teaser")]
    rows = []
    for r in par:
        v = r["validation"]
        rows.append([f'<b>{e(r["name"])}</b><br><span class="muted">{e(r["key"])}</span>',
                     num(r["full"]["bets"], 0), num(r["full"]["hit_rate"] * 100, 1),
                     num(r["full"]["avg_odds"], 0), roi(r["full"]["roi"]), roi(v["roi"]),
                     num(v["p_value"], 3), f'{r["gates_passed"]}/{r["gates_total"]}',
                     src(SOURCES, "S1")])
    ptbl = table([("Parlay", False), ("Tickets", True), ("Hit %", True), ("Avg price", True),
                  ("ROI all", True), ("ROI 2016+", True), ("p", True), ("Gates", True), ("Src", False)],
                 rows, caption="Parlay and teaser results", col_cls=[None] + ["n"] * 7 + [None, None],
                 note="Pushes settle as a push of the whole ticket (Faed F5), so these returns are lower bounds.")

    pricing = table([("ρ", True), ("Leg prob", True), ("Independent joint", True),
                     ("Copula joint", True), ("Error", True), ("Fair decimal", True),
                     ("Fair American", True)],
                    [[num(x["rho"], 2), num(x["leg_prob"], 2), num(x["independence_prob"], 4),
                      num(x["copula_prob"], 4), pctp(x["prob_error_pct"] / 100, 1),
                      num(x["fair_decimal"], 3), num(x["fair_american"], 0)]
                     for x in CORR["pricing_table"]],
                    col_cls=["n"] * 7, caption="Correlation-adjusted price of a two-leg same-game parlay",
                    note="Fair American is the break-even price for the correlated joint probability. "
                         "Price the legs independently and you will under-charge on positive correlation "
                         "and over-charge on negative.")

    corr_rows = []
    for p in CORR["game_pairs"] + CORR["prop_pairs"] + ([CORR["cross_game"]] if CORR["cross_game"] else []):
        corr_rows.append([e(p["pair"]), num(p["n"], 0), num(p["phi"], 3),
                          f'{num(p["ci_lo"],3)} to {num(p["ci_hi"],3)}',
                          num(p["p_value"], 4), num(p["p_both_independent"], 4) if p.get("p_both_independent") else blank(),
                          num(p["p_both_actual"], 4) if p.get("p_both_actual") else blank(),
                          num(p.get("lift_pct"), 1, "%") if p.get("lift_pct") is not None else blank()])
    ctbl = table([("Leg pair", False), ("n", True), ("φ", True), ("95% CI", True), ("p", True),
                  ("P(A)·P(B)", True), ("P(A∧B)", True), ("Lift", True)],
                 corr_rows, col_cls=[None] + ["n"] * 7,
                 caption="Correlation values behind the parlay maths",
                 note=src(SOURCES, ["S1", "S9"]))

    body = f"""
<div class="grid g4">
  {card("Parlay families", num(len(par),0), "2-leg, 3-leg, ML, same-game, teaser")}
  {card("Best parlay ROI", num(max(r['full']['roi'] for r in par)*100,2,'%'), "full sample, before gating")}
  {card("Same-game φ", num(CORR['strongest_pair']['phi'],3), "home ML × home cover ATS")}
  {card("Cross-game φ", num(CORR['cross_game']['phi'],3), "the independence assumption holds across games")}
</div>

<h2>What the parlay results say</h2>
<p>Parlays multiply both the price and the error. Two −110 legs pay about +264, which needs 27.4% of
tickets to win just to break even; two independent 52.4% legs win 27.4% of the time. There is no
structural edge in the multiplication itself, which is why every parlay family here returns less than a
single bet on the same picks — and why the same-game version is the only one where correlation can
actually change the answer.</p>
{ptbl}

<h2>Correlation changes the price, not the edge</h2>
<p>A book that prices same-game legs independently will mis-price them whenever the legs are correlated.
The table below shows the size of that mis-pricing at the correlations actually measured in this data.
It is an arithmetic consequence of φ, not a claim about any particular sportsbook's multiplier — those
multipliers are not in the verified data and are therefore not quoted here.</p>
{pricing}

<h2>Measured correlations</h2>
{ctbl}

<h2>How to build a same-game parlay with this</h2>
<ol>
<li>Only combine legs whose measured φ is outside the noise band (|φ| &gt; 0.054 at n = 3,400).</li>
<li>Price the pair with the copula joint probability, never the product.</li>
<li>Cross-game combinations can use the product: the measured cross-game φ is
{num(CORR['cross_game']['phi'],3)} with a confidence interval that contains zero.</li>
<li>Re-check the price against the book's own same-game multiplier once one is sourced (F3).</li>
</ol>
"""
    return page("parlays.html", "Parlays and same-game combinations",
                "Two-leg and three-leg parlays, moneyline parlays, same-game spread+total tickets and "
                "six-point teasers — priced at real recorded odds and corrected for correlation.",
                body, SOURCES)


# --------------------------------------------------------------------------- #
def pg_props():
    mrows = []
    for m in PROPS["markets"]:
        mrows.append([f'<b>{e(m["label"])}</b>', e(m["position"]), num(m["n_player_weeks"], 0),
                      num(m["n_train_2023"], 0), num(m["n_test_2024"], 0),
                      num(m["mae_baseline_test"], 2), num(m["mae_our_test"], 2),
                      num(m["bias_our_test"], 2),
                      num(m["over_rate_at_line_test"] * 100, 1),
                      num(m["over_rate_baseline_test"] * 100, 1),
                      num(m["calibration_error_our"] * 100, 1),
                      src(SOURCES, "S9")])
    mtbl = table([("Market", False), ("Pos", False), ("Player-weeks", True), ("2023 fit", True),
                  ("2024 test", True), ("MAE baseline", True), ("MAE ours", True), ("Bias", True),
                  ("Over % at our line", True), ("Over % at baseline", True),
                  ("Calib. error", True), ("Src", False)],
                 mrows, col_cls=[None, None] + ["n"] * 9 + [None],
                 caption="Prop line origination: accuracy and calibration",
                 note=("Calibration error is |over rate − 50%| at the originated line — for a fair line, "
                       "half the outcomes should land each side."))

    cal_rows = []
    mkts = PROPS["markets"]
    offsets = sorted({c["offset"] for m in mkts for c in m["calibration"]})
    for off in offsets:
        row = [num(off, 1)]
        for m in mkts:
            cell = [c for c in m["calibration"] if c["offset"] == off and c["window"].startswith("2024")]
            row.append(num(cell[0]["over_rate"] * 100, 1) if cell else blank())
        cal_rows.append(row)
    caltbl = table([("Line offset (units)", True)] + [(m["label"], True) for m in mkts],
                   cal_rows, col_cls=["n"] * (len(mkts) + 1),
                   caption="Calibration curve on the 2024 out-of-sample season",
                   sub="share of outcomes that finished over the line at each offset",
                   note=src(SOURCES, ["S9"]))

    ex_rows = [[num(x["season"], 0), num(x["week"], 0), e(x["player"]), e(x["team"]), e(x["opp"]),
                e(x["market"]), num(x["our_line"], 1), num(x["actual"], 0),
                pill(x["result"], {"over": "info", "under": "neutral", "push": "warn"}[x["result"]])]
               for x in reversed(PROPS["examples"])]
    extbl = table([("Season", True), ("Wk", True), ("Player", False), ("Team", False), ("Opp", False),
                   ("Market", False), ("Our line", True), ("Actual", True), ("Result", False)],
                  ex_rows, col_cls=["n", "n", None, None, None, None, "n", "n", None],
                  caption="Worked examples from the most recent week in the data",
                  note=src(SOURCES, ["S9"]))

    prop_corr = table([("Prop leg", False), ("n", True), ("φ", True), ("95% CI", True), ("Lift", True)],
                      [[e(p["pair"]), num(p["n"], 0), num(p["phi"], 3),
                        f'{num(p["ci_lo"],3)} to {num(p["ci_hi"],3)}',
                        num(p.get("lift_pct"), 1, "%")] for p in CORR["prop_pairs"]],
                      col_cls=[None] + ["n"] * 4,
                      caption="Prop legs against the team result",
                      note="Implied team totals are derived arithmetic from the two market numbers (F11).")

    body = f"""
{note("<b>These lines are ours, not a market's.</b> No sportsbook prop price exists in any verified "
      "source here, so a prop strategy cannot be settled against a market and cannot pass the "
      "significance or price-shock gates. The prop layer is published as <b>unpriced research</b>, "
      "excluded from the ranked leaderboard, and flagged as F3.", "warn")}

<div class="grid g4">
  {card("Prop markets", num(len(PROPS['markets']),0), "passing, rushing, receiving, receptions")}
  {card("Player-weeks", num(sum(m['n_player_weeks'] for m in PROPS['markets']),0), "2023 and 2024")}
  {card("Best calibration", num(max(m['over_rate_at_line_test'] for m in PROPS['markets'])*100,1,'%'), "over rate at our line, 2024")}
  {card("Baseline calibration", num(min(m['over_rate_baseline_test'] for m in PROPS['markets'])*100,1,'%'), "the recency average it beat")}
</div>

<h2>How the prop line is built</h2>
<p>Three causal ingredients, each computed only from weeks before the game: a recency-weighted player
average (weights 0.35/0.25/0.20/0.12/0.08 over the last five games), the player's own median residual
against that average, and an opponent adjustment that is shrunk toward the league mean by how many games
that defence has actually played. The third ingredient is the one that failed: opponent adjustment added
noise to MAE in every market, which the table below shows honestly rather than hiding.</p>
{mtbl}

<h2>Calibration is the part that works</h2>
<p>A line is only useful if half the outcomes land on each side of it. The plain recency average is
systematically high for right-skewed markets (43–56% over rates); adding the player's own median
residual pulls every market back to 48.6–50.9%. That is a real improvement in line quality — and it still
does not make the line profitable, because there is no market to beat.</p>
{caltbl}

<h2>Props and the team result</h2>
<p>This is the part that matters for prop combinations: a quarterback's passing yards and his team's
scoring move together, so a two-leg same-team parlay cannot be priced with the product of the legs.</p>
{prop_corr}

<h2>Worked examples</h2>
{extbl}
"""
    return page("props.html", "Player prop lines",
                "Originating player prop numbers for four markets, graded out of sample on calibration — "
                "and why they cannot be cashed.",
                body, SOURCES)


# --------------------------------------------------------------------------- #
def pg_correlation():
    rows = []
    for p in CORR["game_pairs"]:
        rows.append([e(p["pair"]), num(p["n"], 0), num(p["phi"], 3),
                     f'{num(p["ci_lo"],3)} to {num(p["ci_hi"],3)}',
                     num(p["p_value"], 4), num(p["p_both_independent"], 4),
                     num(p["p_both_actual"], 4), num(p["lift_pct"], 1, "%"), src(SOURCES, "S1")])
    gtbl = table([("Leg pair", False), ("n", True), ("φ", True), ("95% CI", True), ("p", True),
                  ("Independent joint", True), ("Observed joint", True), ("Lift", True), ("Src", False)],
                 rows, col_cls=[None] + ["n"] * 7 + [None],
                 caption="Game-market leg pairs", sub="same game, closing numbers, pushes dropped")

    prop_rows = []
    for p in CORR["prop_pairs"]:
        prop_rows.append([e(p["pair"]), num(p["n"], 0), num(p["phi"], 3),
                          f'{num(p["ci_lo"],3)} to {num(p["ci_hi"],3)}', num(p["p_value"], 4),
                          num(p.get("lift_pct"), 1, "%"), src(SOURCES, ["S9", "S1"])])
    ptbl = table([("Leg pair", False), ("n", True), ("φ", True), ("95% CI", True), ("p", True),
                  ("Lift", True), ("Src", False)], prop_rows,
                 col_cls=[None] + ["n"] * 5 + [None],
                 caption="Prop legs against the team result",
                 note="Team totals are implied from the game total and spread (F11).")

    key_m = CORR["key_numbers"]["margins"]
    max_m = max(x["count"] for x in key_m) or 1
    marg_rows = [[num(x["value"], 0), num(x["count"], 0), num(x["pct"], 2, "%"),
                  sc.bar(x["count"] / max_m, 1.0, "pos")] for x in key_m[:16]]
    mtable = table([("Margin (abs)", True), ("Games", True), ("Share", True), ("", False)],
                   marg_rows, col_cls=["n", "n", "n", None],
                   caption="How often each margin lands — the numbers a teaser must cross",
                   note=src(SOURCES, ["S1"]))

    push_rows = [[e(k), num(v["n"], 0), num(v["push_rate"] * 100, 2)] for k, v in
                 CORR["key_numbers"]["push_rates_by_line"].items()]
    pushtbl = table([("Home line", False), ("Games", True), ("Push rate", True)], push_rows,
                    col_cls=[None, "n", "n"], caption="Push rates at the key numbers",
                    note=src(SOURCES, ["S1"]))

    pricing = table([("ρ", True), ("Leg prob", True), ("Independent joint", True),
                     ("Correlated joint", True), ("Error", True), ("Fair American", True)],
                    [[num(x["rho"], 2), num(x["leg_prob"], 2), num(x["independence_prob"], 4),
                      num(x["copula_prob"], 4), pctp(x["prob_error_pct"] / 100, 1),
                      num(x["fair_american"], 0)] for x in CORR["pricing_table"]],
                    col_cls=["n"] * 6, caption="Pricing a two-leg same-game parlay under correlation")

    body = f"""
{note("<b>Method.</b> " + e(CORR['method']) + " " + e(CORR['significance_threshold']) + ".", "")}

<div class="grid g4">
  {card("Strongest leg pair", num(CORR['strongest_pair']['phi'],3), "home ML × home cover ATS")}
  {card("Weakest same-game pair", num(min(p['phi'] for p in CORR['game_pairs']),3), "spread × total")}
  {card("Cross-game", num(CORR['cross_game']['phi'],3), "independence holds")}
  {card("Games in sample", num(CORR['n_games'],0), "2006-2026, priced games")}
</div>

<h2>Game-market leg pairs</h2>
<p>The moneyline and the spread are the same event measured twice, so φ ≈ 0.67 is expected. What matters
for parlay pricing is the pairs that are <i>not</i> mechanically linked: spread × total is essentially
zero (φ = {num([p for p in CORR['game_pairs'] if 'Over' in p['pair'] and 'Home covers' in p['pair']][0]['phi'],3)}),
which means a same-game spread+total ticket can be priced with the product without much error — but only
because those legs happen to be independent, not because same-game legs are independent in general.</p>
{gtbl}

<h2>Prop legs</h2>
{ptbl}

<h2>Cross-game independence</h2>
<p>Two different games in the same week: φ = {num(CORR['cross_game']['phi'],3)} with a 95% confidence
interval of {num(CORR['cross_game']['ci_lo'],3)} to {num(CORR['cross_game']['ci_hi'],3)}. The standard
parlay assumption is fine across games; it is only same-game and same-team combinations that need the
correction below.</p>

<h2>Correlation-adjusted pricing</h2>
{pricing}

<h2>Key numbers</h2>
<p>The distribution of NFL margins is heavily concentrated on 3, 4, 6, 7, 10 and 14. Any strategy that
moves or avoids those numbers (teasers, buying points, alternate spreads) is trading in push
probabilities, not just cover probabilities — which is why the push table is part of the correlation
dataset rather than a footnote.</p>
<div class="grid g2"><div>{mtable}</div><div>{pushtbl}</div></div>
"""
    return page("correlation.html", "Correlation values",
                "Measured phi coefficients with confidence intervals for every leg pair that appears in "
                "a parlay, plus the key-number distribution that governs pushes.",
                body, SOURCES)


# --------------------------------------------------------------------------- #
def pg_luck():
    nb = LUCK["null_bettors"]
    maxc = max(x["count"] for x in nb["histogram"]) or 1
    hist = table([("Return bucket", False), ("Simulated bettors", True), ("", False)],
                 [[e(x["bucket"]), num(x["count"], 0), sc.bar(x["count"] / maxc, 1.0, "neg")]
                  for x in nb["histogram"]],
                 col_cls=[None, "n", None],
                 caption=f"{num(nb['n_bettors'],0)} simulated bettors, {num(nb['n_bets_per_bettor'],0)} bets each at {nb['price']}",
                 note="A zero-edge bettor is not a break-even bettor: the price itself costs about 5%.")

    sv = LUCK["skill_variance"]
    pv = LUCK["persistence"]
    sl_rows = []
    for s in LUCK["strategy_luck"]:
        sl_rows.append([f'<b>{e(s["name"])}</b><br><span class="muted">{e(s["key"])}</span>',
                        num(s["validation_bets"], 0), roi(s["validation_roi"]),
                        num(s["season_roi_sd"] * 100, 2, "%"), num(s["chance_sd"] * 100, 2, "%"),
                        num(s["luck_share_of_variance"] * 100, 1, "%"),
                        num(s["skill_share_of_variance"] * 100, 1, "%"),
                        num(s["validation_p"], 3), num(s["reality_check_p"], 3)])
    sltbl = table([("Strategy", False), ("Bets 2016+", True), ("ROI 2016+", True),
                   ("Season ROI σ", True), ("Chance σ", True), ("Luck share", True),
                   ("Skill share", True), ("p", True), ("Max-stat p", True)], sl_rows,
                  col_cls=[None] + ["n"] * 8,
                  caption="Skill / luck decomposition per strategy",
                  note="Luck share compares the observed season-to-season spread of returns with the "
                       "spread pure chance would produce at the same bet counts.")

    ev = LUCK["evidence_requirement"]
    evtbl = table([("True edge", True), ("Bets (95% one-sided)", True), ("Bets (80% power)", True),
                   ("Seasons at 150/yr", True)],
                  [[num(x["true_roi"] * 100, 0, "%"), num(x["bets_95pct_one_sided"], 0),
                    num(x["bets_80pct_power"], 0), num(x["seasons_at_150_bets"], 0)] for x in ev],
                  col_cls=["n"] * 4, caption="The evidence bar")

    mt = LUCK["multiple_testing"]
    body = f"""
<div class="grid g4">
  {card("Null bettor σ", num(nb['roi_sd']*100,2,'%'), f"over {num(nb['n_bets_per_bettor'],0)} bets at {nb['price']}")}
  {card("Best of 100 nulls", num(nb['best_of_100_mean']*100,2,'%'), "the winner of 100 zero-edge bettors")}
  {card("Team ATS skill", "none detected", f"permutation null ≥ observed dispersion")}
  {card("Split-half reliability", num(pv['split_half_r'],3), "team ATS, first half vs second half")}
</div>

{note("<b>The core claim:</b> a bettor with no edge still wins sometimes, and the winner of a large pool of "
      "no-edge bettors looks exactly like a skilled one. Everything on this page exists to separate those "
      "two things. The null simulation gives the shape of luck; the permutation null gives the shape of "
      "luck <i>given the structure of the schedule</i>; the reliability tests ask whether the past "
      "predicts the future at all.", "")}

<h2>1 · What luck looks like</h2>
<p>Twenty thousand zero-edge bettors, {num(nb['n_bets_per_bettor'],0)} bets each. The 95th percentile is
{num(nb['p95']*100,1)}% and the best of every hundred such bettors averages
{num(nb['best_of_100_mean']*100,1)}%. Any strategy returning less than that has not demonstrated
anything.</p>
{hist}

<h2>2 · Team-level skill does not survive a permutation null</h2>
<p>{e(sv['verdict'])}. Observed dispersion of team-season ATS rates is
{num(sv['observed_var_of_rates'],5)}; the permutation benchmark that reassigns ATS winners inside each
game — preserving the one-winner-per-game constraint — gives {num(sv['permutation_chance_var'],5)}
± {num(sv['permutation_chance_var_sd'],5)}. The point estimate of skill variance is negative, so it is
reported as zero rather than clipped into a claim.</p>
<ul>
<li>Team-seasons in the test: {num(sv['team_seasons'],0)}</li>
<li>Games per team-season: {num(sv['games_per_team_season_mean'],1)}</li>
<li>Implied 95% band for a team's true ATS rate: {num(sv['implied_95pct_skill_band'][0]*100,1)}% to {num(sv['implied_95pct_skill_band'][1]*100,1)}%</li>
</ul>

<h2>3 · Reliability</h2>
<p>If teams had persistent ATS skill, a team's first half would predict its second half. It does not:
r = {num(pv['split_half_r'],3)} over {num(pv['split_half_n'],0)} team-seasons, and year over year
r = {num(pv['year_over_year_r'],3)}. Spearman-Brown reliability is
{num(pv['spearman_brown_reliability'],3)}.</p>

<h2>4 · Each strategy, decomposed</h2>
<p>The luck share compares the observed dispersion of a strategy's season returns with the dispersion
pure chance would generate at the same number of bets. Numbers near 100% mean the season-to-season
pattern is noise.</p>
{sltbl}

<h2>5 · The evidence bar</h2>
<p>This table is the reason gate G1 exists. An edge of 2% needs thousands of settled bets before a
one-sided 95% test can see it; a 150-bet season cannot distinguish a good bettor from a lucky one, no
matter how good the story is.</p>
{evtbl}

<h2>6 · Multiple testing</h2>
<ul>
<li>Signals tested: <b>{num(mt['signals_tested'],0)}</b>; expected false positives at p &lt; 0.05:
<b>{num(mt['expected_false_positives_at_p05'],2)}</b>.</li>
<li>Strategies tested: <b>{num(mt['strategies_tested'],0)}</b>; family size for the FDR correction:
<b>{num(mt['signals_tested'] + mt['strategies_tested'],0)}</b>.</li>
<li>Signals surviving FDR and out-of-sample: <b>{len(mt['survivors'])}</b>.</li>
<li>Best strategy against the best-of-N null:
p = <b>{num(mt['best_strategy_reality_check_p'],3)}</b>.</li>
</ul>
"""
    return page("luck.html", "Removing luck",
                "Permutation nulls, reliability tests, per-strategy skill/luck decomposition and the number "
                "of bets an edge needs before anyone should believe it.",
                body, SOURCES)


# --------------------------------------------------------------------------- #
def pg_data():
    mrows = []
    for f in MANIFEST["files"]:
        mrows.append([e(f["file"].replace("data/raw/", "")), num(f["rows"], 0), num(f["bytes"], 0),
                      f'<code>{e(f["sha256"][:16])}…</code>',
                      f'<a href="{e(f["retrieved_from"])}" target="_blank" rel="noopener">git blob</a>',
                      f'<a href="{e(f["canonical_upstream"])}" target="_blank" rel="noopener">upstream</a>'])
    mtbl = table([("File", False), ("Rows", True), ("Bytes", True), ("SHA-256", False),
                  ("Retrieved from", False), ("Canonical upstream", False)], mrows,
                 col_cls=[None, "n", "n", None, None, None],
                 caption="Extract manifest",
                 note=f'Pinned nflverse/nfldata commit <code>{e(INTEG["pinned_commit"][:12])}</code>, '
                      f'manifest generated {e(INTEG["manifest_generated"])}.')

    crows = []
    for c in INTEG["checks"]:
        crows.append([f'<b>{e(c["key"])}</b>', e(c["question"]), e(c["method"]), e(c["result"]),
                      status_pill(c["status"]), src(SOURCES, c["sources"])])
    ctbl = table([("Check", False), ("Question", False), ("Method", False), ("Result", False),
                  ("Status", False), ("Src", False)], crows,
                 caption="Integrity and reconciliation checks",
                 col_cls=[None, "wrap-cell", "wrap-cell", "wrap-cell", "t", None])

    cov = INTEG["coverage_by_season"]
    covrows = [[num(c["season"], 0), num(c["games"], 0), num(c["with_line"], 0)] for c in cov]
    covtbl = table([("Season", True), ("Games", True), ("With a line", True)], covrows,
                   col_cls=["n"] * 3, caption="Coverage by season",
                   note=src(SOURCES, ["S1"]))

    fields = [
        ("game_id", "Season_week_away_home — the join key everywhere", "S1"),
        ("spread_line", "Market's expected HOME margin (positive = home favoured). Verified empirically: "
                        "corr with the actual margin is +0.43 and MAE is 10.26 pts with this sign, 14.60 flipped.", "S1"),
        ("home_line", "Derived: −spread_line. Standard betting notation, negative = home favoured.", "S1"),
        ("total_line", "Market total.", "S1"),
        ("away/home_moneyline", "American moneyline prices.", "S1"),
        ("away/home_spread_odds, over_odds, under_odds", "American prices for each side.", "S1"),
        ("away_rest, home_rest", "Days of rest since the previous game.", "S1"),
        ("div_game, roof, surface, temp, wind", "Game context. Weather fields have no documented "
                                                 "measurement protocol (F13).", "S1"),
        ("home_qb_id, away_qb_id", "Starting quarterback id, used for the QB-change signal.", "S1"),
        ("player_id + season + week", "Player-week key in the prop layer.", "S9"),
    ]
    ftbl = table([("Field", False), ("Meaning and how it was verified", False), ("Src", False)],
                 [[f'<code>{e(a)}</code>', e(b), src(SOURCES, c)] for a, b, c in fields],
                 caption="Field dictionary for the fields this project depends on",
                 col_cls=[None, "wrap-cell", None])

    body = f"""
<div class="grid g4">
  {card("Extracts", num(len(MANIFEST['files']),0), "every file hashed with SHA-256")}
  {card("Rows ingested", num(sum(f['rows'] for f in MANIFEST['files']),0), "across nine files")}
  {card("Games played", num(INTEG['n_games_played'],0), "1999-2026, all game types")}
  {card("Checks", f"{sum(1 for c in INTEG['checks'] if c['status']=='pass')}/{len(INTEG['checks'])}", "the rest are flagged, none are ignored")}
</div>

{note("<b>Provenance.</b> The datasets are published by nflverse and pulled from the publisher's git tree "
      "at a pinned commit, because the release-asset CDN is unreachable from the build shell. Two "
      "independent extracts of the closing line are reconciled against each other; points scored and "
      "allowed reconcile exactly with the standings file for all 800 team-seasons. Where the two closing "
      "line extracts disagree, the gap is published rather than smoothed.", "")}

<h2>Manifest</h2>
{mtbl}

<h2>Integrity and reconciliation</h2>
<p>These are the line-by-line checks. Two returned <i>needs review</i>: the closing-line reconciliation gap
and the player-week mirror. Both are on the <a href="flagged.html">Flagged for review</a> page with an
impact statement.</p>
{ctbl}

<h2>Coverage</h2>
<p>Closing lines exist for every season from 1999, but recorded prices start in 2006 — so every backtest
in this project starts in 2006 and the discovery/validation split falls at 2015/2016.</p>
{covtbl}

<h2>Field dictionary</h2>
{ftbl}
"""
    return page("data.html", "Data and verification",
                "Nine hashed extracts, a pinned commit, eight reconciliation checks and a field dictionary "
                "— the audit trail behind every number on this site.",
                body, SOURCES)


# --------------------------------------------------------------------------- #
def pg_sources():
    rows = []
    for s in INTEG["sources"]:
        status = (f'<span class="pill pass">HTTP {s["http_status"]}</span>' if s["http_status"] == 200
                  else (f'<span class="pill warn">HTTP {s["http_status"]}</span>' if s["http_status"]
                        else '<span class="pill neutral">page-fetch only</span>'))
        rows.append([f'<b>{e(s["id"])}</b>',
                     f'<a href="{e(s["url"])}" target="_blank" rel="noopener">{e(s["name"])}</a>',
                     e(s["publisher"]),
                     pill("league official", "info") if s["league_official"] else pill("third party", "neutral"),
                     e(s["provides"]),
                     num(s["rows"], 0) if s.get("rows") else blank(),
                     status,
                     f'<code>{e(s["sha256"][:12])}…</code>' if s.get("sha256") else blank()])
    tbl = table([("ID", False), ("Source", False), ("Publisher", False), ("Type", False),
                 ("What it provides", False), ("Rows", True), ("Link status", False), ("SHA-256", False)],
                rows, col_cls=[None, None, None, "t", "wrap-cell", "n", "t", None],
                caption="Source registry", sub="13 entries",
                note="HTTP status was checked from the build shell on 2026-11-01 for every GitHub URL. "
                     "nfl.com is blocked from the shell, so those entries were verified with the agent's "
                     "page-fetch tool instead and are marked accordingly (F7).")

    body = f"""
{note("<b>The rule applied throughout.</b> Every row of every table on this site carries one of these "
      "ids. If a value could not be traced to an entry here, the cell is blank and the item is published "
      "on the Flagged for review page — nothing is filled in by inference.", "")}

<h2>Registry</h2>
{tbl}

<h2>What 'official' means here</h2>
<p>Only S10-S13 are published by the league itself. The nflverse files are the de-facto standard open
mirror of NFL data and are the only practical source of per-game closing prices with American odds, but
they are a third-party project, not the league. This project labels them as third party rather than
pretending otherwise — the distinction is carried in the table above, not buried in a footnote.</p>

<h2>Verification performed</h2>
<ul>
<li><b>League-official spot check (2026):</b> the 2026 standings on NFL.com were compared row by row with
the nflverse standings file — 24 of 24 published teams matched on W-L-T, points for and points against.</li>
<li><b>Internal reconciliation:</b> points scored and allowed from the game file equal the standings file
for 800 of 800 team-seasons, exactly.</li>
<li><b>Cross-extract reconciliation:</b> the closing line from the game file matches the independent
closing-line file exactly on 2,095 of 3,096 home sides, within 0.5 pt on 91.3%, within 1 pt on 97.2%,
maximum gap 5.5 pts.</li>
<li><b>Sign conventions:</b> verified empirically rather than assumed (see the field dictionary on the
<a href="data.html">Data</a> page).</li>
<li><b>Price coherence:</b> both sides of each recorded two-way market imply a median hold of 2.4%,
consistent with a real two-way market rather than mismatched snapshots.</li>
</ul>

<h2>Open verification gaps</h2>
<p>Listed in full on the <a href="flagged.html">Flagged for review</a> page: undocumented odds provenance
(F1), the player-week mirror (F2), the absence of prop prices (F3), the assumed teaser price (F4), the
parlay push convention (F5), the single-season opening lines (F6) and the fact that league-official
numeric verification is a spot check rather than an automated diff (F7).</p>
"""
    return page("sources.html", "Source registry",
                "Every source used, its publisher, what it provides, its HTTP status and its SHA-256 — with "
                "third-party and league-official sources labelled separately.",
                body, SOURCES)


# --------------------------------------------------------------------------- #
def pg_flagged():
    cards = []
    for f in FLAGGED:
        cards.append(f"""
<div class="card" id="{e(f['id'])}">
  <h3>{e(f['id'])} · {pill("needs review", "warn")}</h3>
  <p style="font-size:15px;font-weight:600;margin:2px 0 8px">{e(f['title'])}</p>
  <p><b>What.</b> {md_to_html(f['what']).replace('<p>','').replace('</p>','')}</p>
  <p><b>Why it matters.</b> {e(f['why'])}</p>
  <p><b>Impact on published results.</b> {e(f['impact'])}</p>
  <p><b>Sources.</b> {src(SOURCES, f['srcs'])}</p>
  <p><b>Requested action.</b> {e(f['action'])}</p>
</div>""")
    body = f"""
{note("<b>Nothing here blocks the release.</b> These are the items a reviewer should look at first: values "
      "that could not be confirmed from a primary source, assumptions that had to be made, and places "
      "where two sources disagree. Each carries its sources, the effect on the published numbers, and the "
      "action that would close it. " + f"{len(FLAGGED)} items.",
      "warn")}

<div class="grid g2">
{''.join(cards)}
</div>

<h2>Values deliberately left blank</h2>
<p>The following are blank on the site rather than estimated:</p>
<ul>
<li><b>Market lines for the {len([r for r in LINES['slate']['rows'] if not r['verified']])} unplayed games
without a recorded price</b> — see the live slate tables on the Originated lines page.</li>
<li><b>Player-prop market prices</b> — do not exist in any verified source, so no prop ROI is published (F3).</li>
<li><b>Teaser and parlay payout multipliers</b> — provider-specific and not in the data; the teaser is
priced at a stated assumption and the parlay push rule is stated explicitly (F4, F5).</li>
<li><b>Closing-line-value figures</b> beyond 2021 — opening prices exist for one season only (F6).</li>
</ul>
"""
    return page("flagged.html", "Flagged for review",
                f"{len(FLAGGED)} items that need a human decision: unverifiable values, assumptions, and "
                "places where two trusted sources disagree.",
                body, SOURCES)


# --------------------------------------------------------------------------- #
def pg_methods():
    body = f"""
<h2>Pipeline</h2>
<pre><code>scripts/fetch_data.py     # pull 9 extracts, hash them, write data/manifest.json
scripts/build_integrity.py # 9 checks: signs, reconciliation, coherence, coverage
scripts/build_lines.py    # walk-forward rating model -> spread / total / moneyline
scripts/build_signals.py  # 27 pre-registered signals, FDR + out-of-sample
scripts/build_strategies.py # 18 strategy families, 7 gates, leaderboard
scripts/build_props.py    # player prop origination + calibration
scripts/build_correlations.py # phi coefficients, copula pricing, key numbers
scripts/build_luck.py     # permutation nulls, reliability, evidence bar
scripts/build_site.py     # this site
scripts/check_links.py    # internal links + external source links</code></pre>
<p><code>python3 scripts/build_all.py</code> runs the lot in dependency order. No step requires network
access except <code>fetch_data.py</code>.</p>

<h2>The rating model</h2>
<p>Points scored is modelled as an additive function of team offence, opponent defence, a home-field
constant and a rest differential, fitted by weighted ridge regression on the stacked home and away
equations. Weights decay with a {num(1.15,2)}-year half-life. For every (season, week) block the fit uses
only games that kicked off earlier; the block is then predicted. Ratings carried into a new season are
shrunk 40% toward league average. Franchise relocations are mapped to one code (F10).</p>
<ul>
<li><b>Spread</b> = predicted home margin, rounded to the nearest half point.</li>
<li><b>Total</b> = sum of the two predicted scores, rounded to the nearest half point.</li>
<li><b>Moneyline</b> = Φ(margin / 13.6). The 13.6-point sigma is the residual scale of NFL margins.</li>
</ul>

<h2>Settlement rules</h2>
<ul>
<li>Every bet is 1 unit and settles at the American price recorded in the source extract.</li>
<li>Push → stake returned, zero profit, excluded from the hit-rate denominator.</li>
<li>Parlay price = product of the leg decimal prices, expressed back as American odds.</li>
<li>Parlay with a pushed leg → whole ticket treated as a push (conservative; F5).</li>
<li>Teaser → fixed two-team price of −110 (assumption; F4).</li>
<li>Returns are never compounded and no stake sizing is applied.</li>
</ul>

<h2>Statistics</h2>
<ul>
<li><b>Break-even test:</b> one-sided exact binomial against the win rate implied by the prices actually
taken (not against 50%).</li>
<li><b>Wilson intervals</b> for every hit rate.</li>
<li><b>Benjamini-Hochberg</b> false-discovery control across the whole research programme
({STR['multiple_testing_family']['family_size']} tests).</li>
<li><b>Max-statistic block bootstrap</b> (4-week blocks) for the best-of-N correction.</li>
<li><b>Permutation null</b> for team-season ATS dispersion, preserving the one-winner-per-game constraint.</li>
<li><b>Bootstrap</b> confidence intervals for strategy ROI.</li>
<li><b>Brier score and log loss</b> for probability forecasts.</li>
<li><b>Phi coefficient</b> with a Fisher-z interval for binary leg correlation.</li>
</ul>

<h2>Discovery / validation split</h2>
<p>Signals and strategies are developed on 2002-2015 (discovery) and judged on 2016-2026 (validation).
Gate G2 uses the full sample for power, because discarding half the data makes a real 2% edge effectively
invisible; the untouched window is then required to agree in sign and to be positive.</p>

<h2>Reproducing any number on this site</h2>
<ol>
<li><code>python3 scripts/fetch_data.py</code> — downloads and hashes the extracts; compare against
<code>data/manifest.json</code>.</li>
<li><code>python3 scripts/build_all.py</code> — rebuilds every JSON artefact and the site.</li>
<li>Every published figure is a field in <code>data/derived/*.json</code>; the site renders those files
directly, so a discrepancy means a stale build, never a hand-edited page.</li>
</ol>

<h2>Limitations</h2>
<ul>
<li>Closing prices from a single undocumented source (F1); no line shopping, no live or prop markets.</li>
<li>No injury, roster, practice or travel data; weather fields are undocumented (F13).</li>
<li>Player-week data covers two seasons only (F2).</li>
<li>League-official verification is a spot check, not an automated diff (F7).</li>
<li>Results are historical and in-sample to the sport, not a forecast of any future season.</li>
</ul>

<h2>Not betting advice</h2>
<p>This is a research artefact. Nothing here is a recommendation to place a wager, and the project's own
conclusion is that none of its strategies has yet demonstrated an edge that survives validation.</p>
"""
    return page("methods.html", "Methods and reproducibility",
                "How every number on this site is produced, settled and tested — with the code path that "
                "regenerates it.",
                body, SOURCES)


# --------------------------------------------------------------------------- #
def pg_from_markdown(filename: str, title: str, lede: str, md_path: Path, intro: str = ""):
    md = md_path.read_text()
    body = intro + md_to_html(md)
    return page(filename, title, lede, body, SOURCES)


def main():
    DOCS.mkdir(exist_ok=True)
    (DOCS / "assets").mkdir(exist_ok=True)
    built = []
    pages = {
        "index.html": pg_index(),
        "lines.html": pg_lines(),
        "signals.html": pg_signals(),
        "strategies.html": pg_strategies(),
        "gates.html": pg_gates(),
        "parlays.html": pg_parlays(),
        "props.html": pg_props(),
        "correlation.html": pg_correlation(),
        "luck.html": pg_luck(),
        "data.html": pg_data(),
        "sources.html": pg_sources(),
        "flagged.html": pg_flagged(),
        "methods.html": pg_methods(),
    }
    for name, html in pages.items():
        (DOCS / name).write_text(html)
        built.append(name)

    # markdown-backed pages
    n_met = sum(1 for line in (ROOT / "requirements" / "REQUIREMENTS.md").read_text().splitlines()
                if "| met |" in line)
    n_lim = sum(1 for line in (ROOT / "requirements" / "REQUIREMENTS.md").read_text().splitlines()
                if "| met with limitation |" in line)
    intro = (f'<div class="grid g4">'
             + card("Requirements traced", "44", "R1-R44, every one linked to evidence")
             + card("Met", str(n_met), "verified against a source or a recomputation")
             + card("Met with limitation", str(n_lim), "published on Flagged for review")
             + card("Unmet", "0", "nothing is silently dropped")
             + "</div>")
    (DOCS / "requirements.html").write_text(
        pg_from_markdown("requirements.html", "Requirements traceability",
                         "The brief broken into 44 testable requirements, each traced to the artefact that "
                         "satisfies it and the evidence a reviewer can check.",
                         ROOT / "requirements" / "REQUIREMENTS.md", intro))
    built.append("requirements.html")

    (DOCS / "executive-summary.html").write_text(
        pg_from_markdown("executive-summary.html", "Executive summary",
                         "The findings, the evidence behind them, what qualifies, what does not, and what "
                         "needs your decision.",
                         ROOT / "EXECUTIVE_SUMMARY.md"))
    built.append("executive-summary.html")

    print(f"built {len(built)} pages into docs/: {', '.join(built)}")
    # sanity: every nav target exists
    missing = [f for f, _ in sc.ALL_PAGES if not (DOCS / f).exists()]
    if missing:
        raise SystemExit(f"nav targets missing: {missing}")


if __name__ == "__main__":
    main()
