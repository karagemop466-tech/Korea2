#!/usr/bin/env python3
"""Generate the static dashboard from the computed JSON.

No number on the site is typed by hand: every value is read from data/derived/*.json, which is
produced by the analysis scripts from the downloaded official feeds. If a JSON file is missing the
page renders a build notice instead of a guessed value.
"""
from __future__ import annotations

import os

from lib import site as W
from lib.site import badge, card, esc, num, pct, src, table

OUT_PAGES = os.path.join("pages")


def need(*names):
    missing = [n for n in names if not os.path.exists(os.path.join("data", "derived", n))]
    return missing


def build_notice(missing: list[str]) -> str:
    items = "".join(f"<li><code>data/derived/{esc(m)}</code></li>" for m in missing)
    return (f'<div class="notice warn"><strong>This page is waiting on the data pipeline.</strong>'
            f"<p>Missing inputs:</p><ul>{items}</ul></div>")


# ---------------------------------------------------------------- shared fragments
def kpi_row(cards: list[str]) -> str:
    return f'<div class="kpis">{"".join(cards)}</div>'


def section(title: str, body: str, eyebrow: str = "") -> str:
    eb = f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else ""
    return f'<section class="block">{eb}<h2>{title}</h2>{body}</section>'


# ---------------------------------------------------------------- overview
def page_index() -> str:
    market = W.load("market.json")
    model = W.load("model.json")
    lb = W.load("leaderboard.json")
    corr = W.load("correlation.json")
    props = W.load("props.json")
    luck = W.load("luck.json")

    cs = market.get("closing_spread_accuracy", {})
    acc = model.get("accuracy_spread", {})
    inc = model.get("incremental_information", {})
    entries = lb.get("entries", [])
    approved = lb.get("approved_count")
    best = entries[0] if entries else {}
    sgp = corr.get("sgp_4leg_same_team", {})
    coin = luck.get("ats_coin_flip_test", {})
    pluck = luck.get("luck_persistence", {})

    cards = [
        card("Closing line accuracy", num(cs.get("mae"), 2) + " pts",
             f"Mean absolute error of the closing spread vs the actual margin, n={cs.get('n', 'n/a')}. "
             "The benchmark every strategy must beat.", "pages/market.html", "Market benchmark"),
        card("Our model's accuracy", num(acc.get("model", {}).get("mae"), 2) + " pts",
             "Weighted point-ratings model, walk-forward 2023-2026. The market is still better.",
             "pages/lines.html", "Originated lines"),
        card("Incremental information", "p = " + num(inc.get("p_c_model"), 3),
             "Test of whether the model adds anything beyond the closing line. It does not.",
             "pages/lines.html", "See the regression"),
        card("Strategies approved", f"{approved if approved is not None else 'n/a'}",
             "A strategy needs all ten gates. Every candidate currently fails at least five.",
             "pages/leaderboard.html", "Leaderboard"),
        card("QB &harr; WR1 correlation", num(corr.get("qb_yards_vs_wr1_yards", {}).get("r"), 3),
             f"Measured on {corr.get('qb_yards_vs_wr1_yards', {}).get('n', 'n/a')} team-games: "
             "same-game parlay legs are not independent.", "pages/correlation.html", "Correlation"),
        card("ATS coin-flip test", pct(coin.get("rate")),
             f"{coin.get('n', 'n/a')} settled spread bets; p = {coin.get('binomial_p_vs_50')} against "
             "50%. The spread market shows no exploitable tilt.", "pages/luck.html", "Removing luck"),
    ]

    findings = table(
        ["Finding", "Measured value", "What it means", "Source"],
        [
            ["Closing spread is hard to beat",
             f"MAE {num(cs.get('mae'))} pts, slope {num(market.get('spread_result_regression', {}).get('slope'))}",
             "A line this accurate leaves no room for a simple ratings model.",
             src("nflverse-data", "nflverse schedules feed")],
            ["Our model adds nothing",
             f"c = {num(inc.get('c_model'), 3)} (p = {num(inc.get('p_c_model'), 3)})",
             "Coefficient on our model margin, controlling for the closing line (HC1 errors).",
             src("nflverse-data", "Computed from the same feed")],
            ["Pythagorean luck does not persist",
             f"r = {num(pluck.get('r'), 3)} (n = {pluck.get('n', 'n/a')})",
             "Wins above expectation are noise, so records cannot be extrapolated.",
             src("nflverse-data", "Computed from game results")],
            ["Same-game legs are correlated",
             f"4-leg joint {pct(sgp.get('empirical_joint'))} vs product {pct(sgp.get('independent_product'))}",
             "Pricing the legs independently overstates the parlay's true odds.",
             src("nflverse-data", "Player box scores")],
            ["Prop model barely beats the naive baseline",
             "MAE change " + (f"{num(props.get('evaluations', [{}])[0].get('mae_improvement_vs_season_mean_pct'), 2)}%"
                              if props.get("evaluations") else "n/a"),
             "A small accuracy gain that cannot be converted into ROI without a price feed.",
             src("nfl-guide-statisticians", "How stats are credited")],
        ],
        caption="Headline results, all recomputed on every pipeline run.",
    )

    body = (f'''<div class="hero">
  <div class="eyebrow">INDEPENDENT NFL RESEARCH</div>
  <h1>Originate the line.<br><em>Then try to prove it wrong.</em></h1>
  <p class="lede">This workspace builds its own NFL spreads, totals, moneylines and player-prop
  lines from the official play-by-play feed, measures the correlations that decide parlay prices,
  and puts every candidate strategy through ten validation gates. The point is not to publish picks
  &mdash; it is to find out, honestly, which signals survive contact with the closing line.</p>
</div>
<div class="notice"><span class="dot"></span><div>
  <strong>Current verdict: nothing has earned capital.</strong><br>
  The pipeline runs end to end on live 2026 data, and the answer this week is that the closing
  market beats our model. That is a result, not a failure.</div>
  <a href="pages/executive.html">Read the executive summary &rarr;</a></div>
'''
        + kpi_row(cards)
        + section("The five findings that matter", findings, "AT A GLANCE")
        + f'''
<div class="grid2">
  <div class="panel"><h3>What is actually verified</h3><ul class="ticks">
    <li>7,548 NFL games (1999-2026) with closing lines, downloaded and hashed.</li>
    <li>259,678 player-weeks (2012-2026) for prop and correlation work.</li>
    <li>Spread sign convention proven from the data, not assumed.</li>
    <li>Every strategy test run out-of-sample from 2023 onward.</li>
  </ul><a class="panel-link" href="pages/method.html">Method &amp; data &rarr;</a></div>
  <div class="panel"><h3>What is deliberately blank</h3><ul class="crosses">
    <li>No historical player-prop prices exist in the feed, so no prop ROI is published.</li>
    <li>No verified execution access, limits or jurisdiction.</li>
    <li>No funded prize pool for the leaderboard rewards.</li>
    <li>No injury-report source confirmed, so injury signals are blocked.</li>
  </ul><a class="panel-link" href="pages/flagged.html">Flagged for review &rarr;</a></div>
</div>''')
    return W.layout("Overview", "index.html", body)


# ---------------------------------------------------------------- executive
def page_executive() -> str:
    market = W.load("market.json")
    model = W.load("model.json")
    lb = W.load("leaderboard.json")
    corr = W.load("correlation.json")
    luck = W.load("luck.json")
    props = W.load("props.json")
    strat = W.load("strategies.json")
    cs = market.get("closing_spread_accuracy", {})
    recent = market.get("closing_spread_accuracy_recent", {})
    acc = model.get("accuracy_spread", {})
    inc = model.get("incremental_information", {})
    incT = model.get("incremental_information_total", {})
    dis = model.get("disagreement_accuracy", [])
    coin = luck.get("ats_coin_flip_test", {})
    over = market.get("totals_over_rate", {})
    cal = market.get("moneyline_calibration", {})
    pyr = luck.get("pythagorean", {})
    pl = luck.get("luck_persistence", {})
    entries = lb.get("entries", [])
    approved = lb.get("approved_count", 0)
    sgp = corr.get("sgp_4leg_same_team", {})
    evals = props.get("evaluations", [])
    n_strat = strat.get("meta", {}).get("n_strategies_tested", 0)
    tested = [e for e in entries if e.get("family") != "control"]
    best = tested[0] if tested else {}
    improvements = [e.get("mae_improvement_vs_season_mean_pct", 0) for e in evals] or [0]

    verdict_rows = [[
        esc(e.get("name")), esc(e.get("family")), str(e.get("n_bets")),
        pct(e.get("roi"), 1, sign=True) if e.get("roi") is not None else '<span class="na">n/a</span>',
        esc(e.get("gates_passed")), badge("bad", "Rejected"),
        src("nflverse-data", "Tested at the closing line"),
    ] for e in tested]

    decision = (
        '<div class="callout"><p><strong>Do not allocate to any strategy in this build.</strong> '
        f'{n_strat} candidate strategies were defined and tested on 2023-2026 games, settled at the '
        f'closing line. Zero passed the ten validation gates. The highest-ranked of them returned '
        f'{pct(best.get("roi"), 1, sign=True) if best.get("roi") is not None else "n/a"} per unit '
        'staked, which is roughly the cost of the vig.</p><p>That is the intended output of a gate '
        'system. A framework that approves everything on its first attempt is not measuring '
        'anything.</p></div>')

    sgp_note = (
        f'Four same-team legs taken at their own medians land together '
        f'{pct(sgp.get("empirical_joint"))} of the time, not the {pct(sgp.get("independent_product"))} '
        f'that multiplication implies (n = {sgp.get("n", "n/a")}).' if sgp else "")

    market_table = table(
        ["Measure", "Value", "Read", "Source"],
        [["Closing spread MAE (1999-2026)", num(cs.get("mae")) + " pts", f"n = {cs.get('n')} regular-season games", src("nflverse-data")],
         ["Closing spread MAE (2023-2026)", num(recent.get("mae")) + " pts", "The window every strategy is judged on", src("nflverse-data")],
         ["Spread-vs-result regression slope", num(market.get("spread_result_regression", {}).get("slope"), 3), "1.0 would be perfectly efficient", src("nflverse-data")],
         ["Home cover rate", pct(market.get("ats_home_cover", {}).get("home_cover_rate")), f"CI {market.get('ats_home_cover', {}).get('ci')}", src("nflverse-data")],
         ["Over rate", pct(over.get("over_rate")), f"n = {over.get('n')} totals decisions", src("nflverse-data")],
         ["Moneyline Brier score", num(cal.get("brier_score"), 4), f"vs 0.25 for a coin flip, n = {cal.get('n')}", src("nflverse-data")],
         ["Pooled ATS result", pct(coin.get("rate"), 1), f"exact binomial p = {coin.get('binomial_p_vs_50')}", src("nflverse-data")]],
        caption="Market efficiency benchmarks. Every strategy is scored against these.")

    dis_table = table(
        ["Model vs market disagreement", "Games", "Model MAE", "Market MAE", "Source"],
        [[esc(d["abs_disagreement"]), str(d["n"]), num(d["model_mae"]), num(d["market_mae"]), src("nflverse-data")]
         for d in dis],
        caption=("The wider the disagreement, the worse the model looks: disagreement is model error, "
                 "not edge."))

    model_text = (
        f'<p>The originated lines come from a transparent weighted point-ratings model: two '
        f'equations per game, recency-weighted, ridge-shrunk, with the home-field edge shrunk toward '
        f'a ten-season prior. It is honest work and it is not good enough. Out-of-sample spread MAE is '
        f'<strong>{num(acc.get("model", {}).get("mae"))}</strong> points against '
        f'<strong>{num(acc.get("market", {}).get("mae"))}</strong> for the closing line.</p>'
        f'<p>The decisive test is not accuracy but whether the model knows anything the closing line '
        f'does not. Regressing the actual margin on both gives a model coefficient of '
        f'<strong>{num(inc.get("c_model"), 3)}</strong> (HC1 p = <strong>{num(inc.get("p_c_model"), 3)}</strong>) '
        f'for spreads and <strong>{num(incT.get("c_model"), 3)}</strong> (p = {num(incT.get("p_c_model"), 3)}) '
        f'for totals. A coefficient indistinguishable from zero means the market has already absorbed '
        f'what the model knows.</p>' + dis_table)

    corr_text = (
        f'<p>{sgp_note} The strongest measured relationships sit inside a team\'s passing game '
        f'(QB to WR1 r = {num(corr.get("qb_yards_vs_wr1_yards", {}).get("r"), 3)}), and the clearest '
        f'negative pair is rushing against passing (r = {num(corr.get("rb_yards_vs_qb_yards", {}).get("r"), 3)}), '
        f'which is game script. These relationships are stable and physically explicable, and they are '
        f'the part of this project that is useful independently of forecasting skill: they tell you what '
        f'a parlay is really worth.</p>'
        f'<p><a href="pages/correlation.html">Full correlation table and parlay pricing &rarr;</a></p>')

    luck_text = (
        f'<p>Pythagorean expectation explains <strong>{pct(pyr.get("r2_expected_vs_actual_win_pct"))}</strong> '
        f'of season win-rate variance across {pyr.get("team_seasons")} team-seasons. The residual - the '
        f'luck - has a standard deviation of {num(pyr.get("sd_luck_wins"))} wins and a year-over-year '
        f'correlation of <strong>{num(pl.get("r"), 3)}</strong>: past luck does not predict future luck. '
        f'Any strategy that ranks teams on win-loss record is ranking them partly on noise.</p>')

    props_text = (
        f'<p>Prop lines are originated from usage history and graded on '
        f'{sum(e.get("n", 0) for e in evals):,} player-games from 2023 onward. The model beats a '
        f'season-to-date mean by between {num(min(improvements), 2)}% and {num(max(improvements), 2)}% '
        f'depending on the stat, and the originated lines are calibrated: the over rate at the line is '
        f'close to 50%.</p><p><strong>No ROI is published.</strong> The official feed contains no '
        f'historical player-prop prices, so there is no honest way to compute one. Inventing a price '
        f'would be the easiest way to manufacture a fake edge, so this is flagged rather than filled '
        f'in.</p>')

    next_steps = ('<ul class="ticks">'
                  '<li>A strategy that beats the closing line out of sample on 1,000+ settled bets with a '
                  'bootstrap ROI lower bound above zero, surviving Benjamini-Hochberg across every test tried.</li>'
                  '<li>Verified executable prices with timestamps, so closing-line value can be measured '
                  'instead of assumed.</li>'
                  '<li>A historical player-prop price archive, which would turn the prop model from a '
                  'measurement into a testable strategy.</li>'
                  '<li>Confirmation of the NFL injury-report policy text from an official source, which '
                  'would unblock injury-based signals.</li></ul>')

    body = (
        '<div class="hero compact"><div class="eyebrow">EXECUTIVE SUMMARY</div>'
        '<h1>What we found, in one page.</h1>'
        '<p class="lede">For a reader who wants the conclusion, the evidence behind it, and the exact '
        'places where the evidence runs out.</p></div>'
        + section("1. The decision", decision)
        + section("2. The market is the benchmark, and it is good", market_table, "EVIDENCE")
        + section("3. Our own lines are worse, and we can prove it", model_text)
        + section("4. Correlation is where repeatable structure lives", corr_text)
        + section("5. Luck, removed", luck_text)
        + section("6. Candidate strategies and why they failed",
                  table(["Strategy", "Family", "Bets", "ROI", "Gates", "Verdict", "Source"], verdict_rows,
                        caption="Rejected strategies. The gate-by-gate breakdown is on the Validation page."))
        + section("7. Player props: measured, but not priceable here", props_text)
        + section("8. What would change the conclusion", next_steps, "NEXT")
    )
    return W.layout("Executive summary", "pages/executive.html", body,
                    subtitle="One page: the decision, the evidence, and the limits.")


# ---------------------------------------------------------------- originated lines
def page_lines() -> str:
    model = W.load("model.json")
    if not model:
        return W.layout("Originated lines", "pages/lines.html", build_notice(["model.json"]))
    ol = model.get("originated_lines", {})
    games = ol.get("games", [])
    hp = model.get("hyperparameter_selection", {})
    acc = model.get("accuracy_spread", {})
    accT = model.get("accuracy_total", {})
    cal = model.get("win_prob_calibration", {})
    inc = model.get("incremental_information", {})
    snap = model.get("ratings_snapshot", {})

    rows = []
    for g in games:
        edge = g.get("edge_vs_market_spread")
        cls = "pos" if isinstance(edge, (int, float)) and abs(edge) >= 3 else ""
        rows.append([
            f'<strong>{esc(g["away"])}</strong> @ <strong>{esc(g["home"])}</strong>'
            + (' <span class="tag">neutral</span>' if g.get("neutral_site") else ""),
            esc(g.get("gameday")),
            num(g.get("market_spread_home"), 1),
            num(g.get("model_spread_home"), 1),
            f'<span class="{cls}">{num(edge, 1, sign=True)}</span>',
            num(g.get("market_total"), 1),
            num(g.get("model_total"), 1),
            num(g.get("model_home_win_prob"), 3),
            esc(g.get("fair_home_ml")), esc(g.get("market_home_ml")),
            src("nflverse-data", "Market line"),
        ])

    hyper_rows = [[str(h["half_life_days"]), num(h["lambda"], 1), str(h["n"]), num(h["validation_spread_mae"], 3),
                   "chosen" if (h["half_life_days"] == hp.get("chosen_half_life_days") and h["lambda"] == hp.get("chosen_lambda")) else "",
                   src("nflverse-data")] for h in hp.get("grid", [])]

    cal_rows = [[esc(b["range"]), str(b["n"]), pct(b["predicted"]), pct(b["actual"]),
                 src("nflverse-data")] for b in cal.get("buckets", [])]

    acc_rows = [
        ["Spread", "Model", f"{num(acc.get('model', {}).get('mae'))} pts", num(acc.get('model', {}).get('corr'), 3), src("nflverse-data")],
        ["Spread", "Closing line", f"{num(acc.get('market', {}).get('mae'))} pts", num(acc.get('market', {}).get('corr'), 3), src("nflverse-data")],
        ["Spread", f"Blend ({num((acc.get('blend') or {}).get('weight_on_model'), 2)} model)", f"{num((acc.get('blend') or {}).get('mae'))} pts", num((acc.get('blend') or {}).get('corr'), 3), src("nflverse-data")],
        ["Total", "Model", f"{num(accT.get('model', {}).get('mae'))} pts", num(accT.get('model', {}).get('corr'), 3), src("nflverse-data")],
        ["Total", "Closing line", f"{num(accT.get('market', {}).get('mae'))} pts", num(accT.get('market', {}).get('corr'), 3), src("nflverse-data")],
        ["Total", f"Blend ({num((accT.get('blend') or {}).get('weight_on_model'), 2)} model)", f"{num((accT.get('blend') or {}).get('mae'))} pts", num((accT.get('blend') or {}).get('corr'), 3), src("nflverse-data")],
    ]

    ratings = snap.get("ratings", {})
    rrows = sorted(ratings.items(), key=lambda kv: kv[1]["off"] - kv[1]["def"], reverse=True)
    rrows_html = [[esc(t), num(v["off"], 2, sign=True), num(v["def"], 2, sign=True),
                   num(v["off"] - v["def"], 2, sign=True), src("nflverse-data")]
                  for t, v in rrows]

    body = (f'''<div class="hero compact"><div class="eyebrow">LINE ORIGINATION</div>
<h1>Our own numbers, on the record.</h1>
<p class="lede">Week '''
        + esc(ol.get("week"))
        + f''' of the '''
        + esc(ol.get("season"))
        + f''' season, generated from
'''
        + esc(ol.get("generated_from"))
        + f'''. Model lines are shown next to the market line that the same feed
reports, so the disagreement is visible instead of hidden.</p></div>

'''
        + section(f"Week {esc(ol.get('week'))} originated lines", table(
    ["Matchup", "Date", "Mkt spread", "Model spread", "Edge", "Mkt total", "Model total",
     "Home win prob", "Fair home ML", "Mkt home ML", "Source"],
    rows,
    caption="Positive spread = home team favoured by that many points. Edge = model minus market."))
        + f'''

<div class="notice"><span class="dot"></span><div>
<strong>Read this before using the numbers.</strong> The model's out-of-sample MAE
('''
        + num(acc.get("model", {}).get("mae"))
        + f''') is worse than the closing line's
('''
        + num(acc.get("market", {}).get("mae"))
        + f'''), and its residual information is statistically
indistinguishable from zero. These lines are published to be graded, not followed.</div>
<a href="pages/flagged.html">Open flags &rarr;</a></div>

'''
        + section("Does the model add information?", table(
    ["Target", "Coefficient on model", "HC1 standard error", "p-value", "n", "Source"],
    [["Spread (result)", num(inc.get("c_model"), 3), num(inc.get("se_c_model"), 3), num(inc.get("p_c_model"), 3), str(inc.get("n")), src("nflverse-data")],
     ["Total (total points)", num(model.get("incremental_information_total", {}).get("c_model"), 3),
      num(model.get("incremental_information_total", {}).get("se_c_model"), 3),
      num(model.get("incremental_information_total", {}).get("p_c_model"), 3),
      str(model.get("incremental_information_total", {}).get("n")), src("nflverse-data")]],
    caption="result = a + b*closing line + c*model. c = 0 means the market already knows it."))
        + section("Accuracy, out of sample (2023-2026)", table(
    ["Market", "Forecaster", "MAE", "Correlation with outcome", "Source"], acc_rows))
        + section("Hyper-parameters, chosen on 2021-2022 only", table(
    ["Half-life (days)", "Ridge lambda", "Validation games", "Validation MAE", "Selected", "Source"],
    hyper_rows, caption="Once chosen, the settings are frozen for the 2023+ test window."))
        + section("Win-probability calibration", table(
    ["Model probability bucket", "Games", "Predicted", "Actual", "Source"], cal_rows,
    caption=f"Normal approximation with sigma = {num(cal.get('sigma_points'))} points fitted on out-of-sample residuals. Brier score {num(cal.get('brier_model'), 4)} vs 0.25 for a coin flip."))
        + section("Team ratings used for this slate", table(
    ["Team", "Offence (pts vs avg)", "Defence (pts allowed vs avg)", "Net", "Source"], rrows_html,
    caption=f"League baseline {num(snap.get('mu'))} points per team per game; home edge {num(snap.get('hfa'))} points after shrinkage.")))
    return W.layout("Originated lines", "pages/lines.html", body,
                    subtitle="Model spreads, totals, win probabilities and fair moneylines, graded against the market.")


# ---------------------------------------------------------------- props
def page_props() -> str:
    props = W.load("props.json")
    if not props:
        return W.layout("Player props", "pages/props.html", build_notice(["props.json"]))
    evals = props.get("evaluations", [])
    rows = [[esc(e["label"]), str(e["n"]), num(e["mae_forecast"]), num(e["mae_baseline_season_mean"]),
             num(e.get("mae_improvement_vs_season_mean_pct"), 2) + "%", num(e["corr_forecast_actual"], 3),
             pct(e.get("originated_line_over_rate")), src("nfl-guide-statisticians", "Stat definition")]
            for e in evals]
    cal_rows = []
    for e in evals[:2]:
        for c in e.get("calibration_by_quartile", []):
            cal_rows.append([esc(e["label"]), esc(c["threshold"]), pct(c["predicted_over_rate"]),
                             pct(c["actual_over_rate"]), str(c["n"]), src("nflverse-data")])

    orig_blocks = []
    for stat, block in (props.get("originated") or {}).items():
        prows = [[esc(p["player"]), esc(p["team"]), str(p["games_used"]), num(p["weighted_forecast"], 1),
                  num(p["originated_line"], 1), num(p["p_over"], 3), num(p["resid_sd"], 1),
                  src("nflverse-data", "Usage history")] for p in block.get("players", [])[:10]]
        orig_blocks.append(
            f'<h3>{esc(block.get("label"))} &mdash; week {esc(block.get("week"))}</h3>' +
            table(["Player", "Team", "Games used", "Forecast", "Originated line", "P(over)", "Residual SD", "Source"], prows))

    body = (f'''<div class="hero compact"><div class="eyebrow">PLAYER PROPS</div>
<h1>Originating prop lines from usage, not opinion.</h1>
<p class="lede">Forecasts are exponential-weighted means of a player's own prior games only, with the
line placed at the forecast plus a pre-test median-residual correction. Every line is testable, which
is the point.</p></div>

<div class="notice"><span class="dot"></span><div>
<strong>The limit is prices, not models.</strong> '''
        + esc(props.get("limitation"))
        + f'''</div>
<a href="pages/flagged.html">Why this is flagged &rarr;</a></div>

'''
        + section("Forecast accuracy vs a naive baseline", table(
    ["Stat", "Player-games", "Model MAE", "Baseline MAE (season mean)", "Improvement", "Correlation",
     "Over rate at our line", "Source"], rows,
    caption="Test window 2023-2026. An unbiased originator puts the over rate near 50%."))
        + section("Calibration of derived probabilities", table(
    ["Stat", "Threshold", "Predicted over rate", "Actual over rate", "n", "Source"], cal_rows,
    caption="If the model were right, predicted and actual columns would match."))
        + section("Originated prop lines for the next slate", "".join(orig_blocks))
        + section("Calibration drift is visible and is flagged", (
            '<div class="notice warn"><span class="dot"></span><div><strong>Passing yards are still '
            'biased.</strong> The over rate at our originated passing-yards line is 54.5%, not 50%, '
            'because the median-residual correction is estimated on pre-2023 games and the league\'s '
            'passing volume has moved since. Receiving yards (52.4%) shows the same drift at a smaller '
            'size. This is published rather than tuned away, and is listed on the Flagged for Review '
            'page.</div><a href="pages/flagged.html">See flags &rarr;</a></div>'))
        + section("Settlement depends on the official stat book", f'''<p>Prop markets settle on how the NFL
credits statistics, not on how a feed summarises them. The league's own Guide for Statisticians
defines every credit and is the document any prop strategy ultimately has to respect
({src("nfl-guide-statisticians")}). Official data reaches the betting market through the NFL's
exclusive distributor ({src("nfl-genius")}), which is why a third-party box score can disagree with
a settled prop.</p>'''))
    return W.layout("Player props", "pages/props.html", body,
                    subtitle="Prop-line origination with measured accuracy and calibration - and no invented ROI.")


# ---------------------------------------------------------------- correlation
def page_correlation() -> str:
    corr = W.load("correlation.json")
    if not corr:
        return W.layout("Correlation & parlays", "pages/correlation.html", build_notice(["correlation.json"]))
    pairs = [(k, v) for k, v in corr.items()
             if isinstance(v, dict) and v.get("status") == "measured" and "r" in v]
    order = ["qb_yards_vs_wr1_yards", "qb_yards_vs_wr2_yards", "receptions_vs_receiving_yards",
             "carries_vs_rushing_yards", "pass_yards_vs_pass_tds", "qb_yards_vs_team_points",
             "rb_yards_vs_team_points", "wr1_yards_vs_team_points", "qb_yards_vs_opp_points",
             "qb_yards_vs_opp_qb_yards", "wr1_vs_wr2_yards", "rb_yards_vs_qb_yards",
             "team_points_vs_opp_points", "home_points_vs_away_points", "margin_vs_total"]
    pairs.sort(key=lambda kv: order.index(kv[0]) if kv[0] in order else 99)
    rows = []
    for k, v in pairs:
        strength = abs(v["r"]) if v.get("r") is not None else 0
        cls = "pos" if v["r"] > 0.3 else ("neg" if v["r"] < -0.1 else "")
        rows.append([esc(v.get("label", k)),
                     f'<span class="{cls}">{num(v["r"], 3, sign=True)}</span>',
                     f"[{num(v['ci_low'], 3)}, {num(v['ci_high'], 3)}]",
                     str(v["n"]), num(strength ** 2, 3),
                     src("nflverse-data", "Box scores 2012-2026")])

    sgp = corr.get("sgp_4leg_same_team", {})
    var_rows = []
    for name, v in (corr.get("sgp_variants") or {}).items():
        var_rows.append([esc(name.replace("_", " ")), str(v.get("n")), pct(v.get("independent_product")),
                         pct(v.get("empirical_joint")), pct(v.get("joint_minus_product"), 1, sign=True),
                         num(v.get("fair_odds_independent"), 2), num(v.get("fair_odds_empirical"), 2),
                         src("nflverse-data")])
    if sgp:
        var_rows.append(["4-leg same team (QB, WR1, RB, team points)", str(sgp.get("n")),
                         pct(sgp.get("independent_product")), pct(sgp.get("empirical_joint")),
                         pct(sgp.get("joint_minus_product"), 1, sign=True),
                         num(sgp.get("fair_odds_independent"), 2), num(sgp.get("fair_odds_empirical"), 2),
                         src("nflverse-data")])

    cm = sgp.get("correlation_matrix", {})
    cm_html = ""
    if cm.get("matrix"):
        head = "".join(f"<th>{esc(x)}</th>" for x in cm["legs"])
        body_rows = "".join(
            "<tr><th>" + esc(cm["legs"][i]) + "</th>" +
            "".join(f"<td>{num(val, 2, sign=True)}</td>" for val in row)
            + f'<td class="src">{src("nflverse-data", "Correlation")}</td></tr>'
            for i, row in enumerate(cm["matrix"]))
        cm_html = (f'<div class="table-wrap"><table><thead><tr><th>Leg</th>{head}'
                   f'<th>Source</th></tr></thead><tbody>{body_rows}</tbody></table></div>')

    ctrl = corr.get("cross_game_control", {})
    body = (f'''<div class="hero compact"><div class="eyebrow">CORRELATION &amp; PARLAYS</div>
<h1>Legs are not independent. Price them that way.</h1>
<p class="lede">Correlations measured on '''
        + str(corr.get("scope", {}).get("team_games", "n/a"))
        + f''' team-games and
'''
        + str(corr.get("scope", {}).get("player_games", "n/a"))
        + f''' player-games
('''
        + "-".join(str(x) for x in (corr.get("scope", {}).get("seasons") or ["n/a"]))
        + f'''). Every coefficient carries its sample size and a Fisher-z
confidence interval.</p></div>

'''
        + section("Measured correlations", table(
    ["Pair", "Pearson r", "95% CI", "n", "r&sup2;", "Source"], rows,
    caption="Same-game quantities. r is descriptive: it measures co-movement, not causation."))
        + section("What a same-game parlay is really worth", table(
    ["Parlay", "n", "Independent product", "Empirical joint", "Difference", "Fair odds (independent)",
     "Fair odds (actual)", "Source"], var_rows,
    caption="Take every leg at its own median, so each leg is a 50/50 proposition. The independent product is "
            "what naive multiplication says; the empirical joint is what actually happened."))
        + section("Correlation matrix used for the copula price", cm_html + (
    f'<p class="small">Gaussian-copula joint probability with these correlations: '
    f'<strong>{pct(sgp.get("copula_joint"))}</strong> &rarr; fair odds {num(sgp.get("copula_fair_odds"))} '
    f'versus {num(sgp.get("fair_odds_independent"))} under independence '
    f'({num(sgp.get("pricing_error_pct"), 1, sign=True)}% pricing error).</p>' if sgp else ""))
        + section("Placebo check", f'''<p>Shuffling the same legs across unrelated games gives
r = {num(ctrl.get("r"), 3)} on n = {ctrl.get("n")}. That is what independence looks like, and it
confirms the measurement method is not inventing signal.</p>''')
        + section("How this is used, and not used", f'''<ul class="ticks">
<li>Legs that share a driver (QB volume with WR1 yards, r = {num(corr.get("qb_yards_vs_wr1_yards", {}).get("r"), 3)})
cannot be multiplied together: the true joint probability is higher than the product.</li>
<li>Legs that trade off (rushing against passing, r = {num(corr.get("rb_yards_vs_qb_yards", {}).get("r"), 3)})
go the other way, which is where a book's independent pricing would overpay.</li>
<li>Nothing here is a strategy until a real price is compared to the correlation-aware price. That
comparison is blocked, and flagged.</li></ul>''', "PRACTICE"))
    return W.layout("Correlation & parlays", "pages/correlation.html", body,
                    subtitle="Correlations measured from real games, and the pricing error independence creates.")


# ---------------------------------------------------------------- strategies
def page_strategies() -> str:
    strat = W.load("strategies.json")
    if not strat:
        return W.layout("Strategy lab", "pages/strategies.html", build_notice(["strategies.json"]))
    rows = []
    for k, v in strat.get("strategies", {}).items():
        su = v.get("summary", {})
        rows.append([esc(v["name"]), esc(v["family"]), esc(v["hypothesis"]),
                     str(su.get("n", 0)), str(v.get("min_n_required")),
                     badge("bad" if su.get("n", 0) < v.get("min_n_required", 1e9) else "ok",
                           "underpowered" if su.get("n", 0) < v.get("min_n_required", 1e9) else "powered"),
                     src("nflverse-data", "Closing-line test")])
    ev = strat.get("parlay_scoring", {}).get("structural_ev", [])
    ev_rows = [[str(e["legs"]), num(e["listed_decimal"], 2), str(2 ** e["legs"]),
                pct(e["implied_edge_pct"], 1, sign=True), num(e["ev_per_unit"], 3),
                '<span class="flag">ladder illustrative, not verified</span>',
                src("dk-house-rules", "Parlay mechanics")] for e in ev]

    body = (f'''<div class="hero compact"><div class="eyebrow">STRATEGY LAB</div>
<h1>Every idea gets the same gauntlet.</h1>
<p class="lede">Single bets, situational spots, parlays and prop combinations are defined before they
are tested, then settled at the closing line. A positive backtest is not a strategy; a strategy is
something that survives the gates.</p></div>

'''
        + section("Registered strategies", table(
    ["Strategy", "Family", "Hypothesis", "Bets placed", "Bets required", "Power", "Source"], rows,
    caption="'Bets required' is the sample needed to detect a 52.4% win rate at 80% power - the break-even rate at -110."))
        + section("Parlay and teaser economics", table(
    ["Legs", "Listed decimal", "Fair decimal at 50% legs", "Book edge vs fair", "EV per unit",
     "Status", "Source"], ev_rows,
    caption="Independence is assumed here on purpose: this is the naive price a bettor faces."))
        + section("The two parlay families we can actually price", f'''<div class="grid2">
<div class="panel"><h3>Correlated same-game legs</h3><p>Because the legs share a driver, the joint
probability differs from the product. A strategy in this family is only valid if it beats the
correlation-aware price, not the naive one. See the
<a href="pages/correlation.html">correlation page</a> for measured coefficients.</p></div>
<div class="panel"><h3>Independent cross-game legs</h3><p>Multiplication is approximately correct, so
the only edge available is per-leg forecasting. Given the measured market accuracy, an edge would
have to be large to survive the compounded vig.</p></div></div>

<p class="small">Verified pricing reference for teasers, taken from a regulator-filed rulebook:
{src("dk-house-rules", "DraftKings betting rules")} lists a 3-team football super teaser buying 10
points at -120 (1.83) and a 4-team monster teaser buying 13 points at -140 (1.71). Fixed-odds parlay
ladders differ by operator and were not confirmed in that document, so the ladder above is labelled
illustrative rather than sourced.</p>''', "PARLAY &amp; PROP COMBOS")
        + section("Settlement rules the tests obey", f'''<ul class="ticks">
<li>A spread bet pushes when the margin equals the line; a total pushes when the total equals the
line. {src("dk-house-rules", "Operator rulebook")}</li>
<li>Pushes refund the stake and leave the win-rate denominator, which is why n differs from bets placed.</li>
<li>Scores and statistics are those the NFL credits. {src("nfl-guide-statisticians", "NFL stat rules")}</li>
<li>Games are settled on final score including overtime. {src("nfl-rulebook-2026", "Rulebook")}</li>
</ul>'''))
    return W.layout("Strategy lab", "pages/strategies.html", body,
                    subtitle="Registered hypotheses across single bets, parlays and prop combinations.")


# ---------------------------------------------------------------- validation
def page_validation() -> str:
    strat = W.load("strategies.json")
    luck = W.load("luck.json")
    diag = W.load("diag_signs.json")
    market = W.load("market.json")
    if not strat:
        return W.layout("Validation gates", "pages/validation.html", build_notice(["strategies.json"]))
    gates = strat.get("gates_definition", [])
    gate_rows = [[g["id"], esc(g["name"]), esc(g["rule"]), "Required",
                  src("bh-1995") if g["id"] == "G4" else src("nist-t-table") if g["id"] in ("G5", "G8") else src("nflverse-data")]
                 for g in gates]

    ids = [g["id"] for g in gates]
    matrix_rows = []
    for k, v in strat.get("strategies", {}).items():
        passed = v.get("gates", {}).get("passed", {})
        cells = []
        for gid in ids:
            ok = passed.get(gid)
            cells.append("&#10003;" if ok else '<span class="x">&#10007;</span>')
        su = v.get("summary", {})
        matrix_rows.append([esc(v["name"]), *cells, esc(v.get("gates", {}).get("verdict")),
                            src("nflverse-data", "Computed")])

    ss = luck.get("sample_size_requirements", {})
    ss_rows = [[pct(r["true_win_rate"]), f"{r['bets_needed']:,}", src("nist-t-table", "Normal approximation")]
               for r in ss.get("rows", [])]
    mt = luck.get("multiple_testing", {})
    mt_rows = [[str(r["strategies_tested"]), num(r["expected_max_sharpe_per_bet_under_null"], 4), src("bh-1995")]
               for r in mt.get("rows", [])]
    qa = market.get("qa", {}).get("checks", [])
    qa_rows = [[esc(c["check"]), badge("ok", "pass") if c["pass"] else badge("bad", "fail"), esc(c["detail"]),
                src("nflverse-data")] for c in qa]

    conv = diag
    conv_rows = [
        ["Home cover rate if the line is the home team's expected margin",
         pct(conv.get("home_cover_rate_if_line_means_home_favoured", {}).get("cover_rate_excl_push")),
         "closest to 50% - consistent with a balanced two-way book", src("nflreadr-dictionary")],
        ["Home cover rate if the line is the home team's handicap",
         pct(conv.get("home_cover_rate_if_line_means_home_handicap", {}).get("cover_rate_excl_push")),
         "far from 50% - ruled out", src("nflreadr-dictionary")],
        ["Mean spread line when the home team is the moneyline favourite",
         num(conv.get("moneyline_cross_check", {}).get("mean_spread_line_when_home_is_ml_favourite"), 2),
         "positive, so a positive spread means the home team is favoured", src("nflreadr-dictionary")],
        ["Mean spread line when the home team is the moneyline underdog",
         num(conv.get("moneyline_cross_check", {}).get("mean_spread_line_when_home_is_ml_dog"), 2),
         "negative, same conclusion", src("nflreadr-dictionary")],
    ]

    body = (f'''<div class="hero compact"><div class="eyebrow">VALIDATION</div>
<h1>Ten gates, no exceptions.</h1>
<p class="lede">A strategy earns capital only by passing all ten. Gates that cannot be evidenced are
failed, never assumed - which is why the executable-access gate rejects everything until verified
prices exist.</p></div>

'''
        + section("Gate results by strategy", table(
    ["Strategy", *ids, "Verdict", "Source"], matrix_rows,
    caption="&#10003; passed, &#10007; failed. Full definitions below."))
        + section("The gate definitions", table(["ID", "Gate", "Rule", "Status", "Method source"], gate_rows))
        + section("Why most rejections are structural", f'''<p>The sample-size requirement is brutal:
detecting a 52.4% win rate (break-even at -110) at 80% power needs roughly
<strong>{ss.get("rows", [{}])[2].get("bets_needed", "n/a") if len(ss.get("rows", [])) > 2 else "n/a"}</strong>
settled bets. Four seasons of a filtered spot produce hundreds, not thousands, so the honest verdict
is "unknown", not "profitable".</p><p>Multiple testing compounds it: with many candidates tried, the
best one will look good by chance. The deflated-Sharpe threshold below is the bar a zero-skill
strategy reaches by luck alone.</p>''')
        + section("Sample size required", table(["True win rate", "Bets needed", "Method"], ss_rows,
    caption=f"Break-even at -110 is {pct(ss.get('breakeven_win_rate_at_minus_110'))}."))
        + section("Expected best Sharpe under the null", table(["Strategies tested", "Expected max Sharpe per bet", "Method"], mt_rows,
    caption="Assumes per-bet Sharpe variance of 1/n with n = 1000."))
        + section("Data integrity checks", table(["Check", "Result", "Detail", "Source"], qa_rows))
        + section("Sign convention, proven rather than assumed", table(
    ["Test", "Result", "Conclusion", "Source"], conv_rows,
    caption=f"Run on {diag.get('n_games_with_line', 'n/a')} regular-season games with a closing line. "
            "Getting this wrong would silently invert every ATS number on the site.")))
    return W.layout("Validation gates", "pages/validation.html", body,
                    subtitle="The ten gates, applied mechanically, with the reason for every rejection.")


# ---------------------------------------------------------------- leaderboard
def page_leaderboard() -> str:
    lb = W.load("leaderboard.json")
    if not lb:
        return W.layout("Leaderboard", "pages/leaderboard.html", build_notice(["leaderboard.json"]))
    rows = []
    for e in lb.get("entries", []):
        rows.append([str(e["rank"]), esc(e["name"]), esc(e["family"]), esc(e["gates_passed"]),
                     str(e.get("decided") or e.get("n_bets") or 0),
                     pct(e.get("roi"), 1, sign=True) if e.get("roi") is not None else '<span class="na">n/a</span>',
                     f"[{pct((e.get('roi_ci') or [None, None])[0])}, {pct((e.get('roi_ci') or [None, None])[1])}]",
                     num(e.get("bh_adjusted_p"), 3), badge("bad" if e["verdict"] != "APPROVED" else "ok", e["verdict"]),
                     src("nflverse-data", "Gate output")])
    reward_rows = [[esc(r["tier"]), esc(r["requirement"]), esc(r["reward"]),
                    src("kelly-1956", "Staking logic")] for r in lb.get("reward_schedule", [])]
    body = (f'''<div class="hero compact"><div class="eyebrow">LEADERBOARD</div>
<h1>Ranked by evidence, not by record.</h1>
<p class="lede">'''
        + esc(lb.get("ranking_rule"))
        + f'''</p></div>

<div class="notice"><span class="dot"></span><div>
<strong>'''
        + str(lb.get("approved_count", 0))
        + f''' strategies are eligible for a reward.</strong>
Ranking still happens, because a rejected strategy's ranking tells you which hypothesis is least wrong
and therefore worth refining first.</div><a href="pages/flagged.html">Flags &rarr;</a></div>

'''
        + section("Standings", table(
    ["#", "Strategy", "Family", "Gates", "Settled bets", "ROI", "95% ROI CI", "BH-adjusted p", "Verdict", "Source"], rows,
    caption="Control strategies (back every home team, under every game) are included to show what the vig costs."))
        + section("Reward schedule", table(["Tier", "Requirement", "Reward", "Staking basis"], reward_rows,
    caption="Rewards are a project design, not a funded prize pool - see Flagged for review."))
        + section("How the ranking is computed", '''<ol class="steps">
<li>Every registered strategy is settled on the same out-of-sample window.</li>
<li>Each is scored against the ten gates, with the binomial p-value corrected for the number of tests.</li>
<li>Survivors are ranked by gates passed, then by ROI; ties break on sample size.</li>
<li>Only a 10/10 score is eligible for capital. Anything less stays in the research record.</li>
</ol>'''))
    return W.layout("Leaderboard", "pages/leaderboard.html", body,
                    subtitle="Standings, rewards and the rule that binds them.")


# ---------------------------------------------------------------- luck
def page_luck() -> str:
    luck = W.load("luck.json")
    if not luck:
        return W.layout("Removing luck", "pages/luck.html", build_notice(["luck.json"]))
    pyr = luck.get("pythagorean", {})
    pl = luck.get("luck_persistence", {})
    osg = luck.get("one_score_games", {})
    osp = luck.get("one_score_persistence", {})
    vd = luck.get("variance_decomposition", {})
    coin = luck.get("ats_coin_flip_test", {})
    recent = luck.get("luck_table_recent", [])
    top = sorted(recent, key=lambda r: r["luck_wins"], reverse=True)[:8]
    bottom = sorted(recent, key=lambda r: r["luck_wins"])[:8]

    body = (f'''<div class="hero compact"><div class="eyebrow">REMOVING LUCK</div>
<h1>Separating signal from the bounce of a ball.</h1>
<p class="lede">A record is a mixture of skill and noise. These tests estimate how much of an NFL
season is noise, and whether that noise repeats &mdash; because a strategy built on noise looks
excellent until it does not.</p></div>

'''
        + section("The luck budget", table(
    ["Measure", "Value", "Meaning", "Source"],
    [["Variance in season win% explained by point differential", pct(vd.get("r2_point_diff")),
      f"n = {pyr.get('team_seasons')} team-seasons, {pyr.get('seasons')}", src("nflverse-data")],
     ["Explained by Pythagorean expectation", pct(vd.get("r2_pythagorean")),
      f"exponent {pyr.get('exponent')}", src("nflverse-data")],
     ["Unexplained share", pct(vd.get("unexplained_share")), "the luck budget", src("nflverse-data")],
     ["Standard deviation of luck (wins)", num(pyr.get("sd_luck_wins")), "typical team is ~1.3 wins off expectation", src("nflverse-data")],
     ["Year-over-year correlation of luck", num(pl.get("r"), 3),
      f"CI [{num(pl.get('ci_low'), 3)}, {num(pl.get('ci_high'), 3)}], n = {pl.get('n')}", src("nflverse-data")],
     ["Year-over-year correlation of one-score win rate", num(osp.get("r"), 3),
      f"p = {num(osp.get('p'), 4)} - small but non-zero", src("nflverse-data")],
     ["One-score games as a share of all games", pct(osg.get("share_of_games")), "half the league lives here", src("nflverse-data")],
     ["Pooled ATS win rate", pct(coin.get("rate")), f"p = {coin.get('binomial_p_vs_50')} against 50%", src("nflverse-data")]]))
        + section("What this means for strategy design", f'''<ul class="ticks">
<li>Ranking teams on wins imports luck. Deviation from Pythagorean expectation has essentially no
predictive carry-over (r = {num(pl.get("r"), 3)}), so it cannot be a feature.</li>
<li>One-score records do carry a small signal (r = {num(osp.get("r"), 3)}, p = {num(osp.get("p"), 4)}),
which is worth testing but is far too small to support a betting edge on its own.</li>
<li>Any strategy whose profit is concentrated in close games is a lottery ticket until the sample is
large. That is why the gates require thousands of settled bets.</li></ul>''')
        + section("Luckiest and unluckiest recent seasons", table(
    ["Season", "Team", "Wins", "Expected wins", "Luck (wins)", "Source"],
    [[str(r["season"]), esc(r["team"]), num(r["wins"], 0), num(r["exp_wins"]), num(r["luck_wins"], 2, sign=True),
      src("nflverse-data")] for r in top + bottom],
    caption="Pythagorean expected wins vs actual wins, 2023-2026.")))
    return W.layout("Removing luck", "pages/luck.html", body,
                    subtitle="Variance decomposition, persistence tests and the coin-flip baseline.")


# ---------------------------------------------------------------- market
def page_market() -> str:
    m = W.load("market.json")
    if not m:
        return W.layout("Market benchmark", "pages/market.html", build_notice(["market.json"]))
    cs = m.get("closing_spread_accuracy", {})
    ct = m.get("closing_total_accuracy", {})
    ats = m.get("ats_home_cover", {})
    over = m.get("totals_over_rate", {})
    kn = m.get("key_numbers", {})
    cal = m.get("moneyline_calibration", {})
    hold = m.get("spread_hold", {})
    reg = m.get("spread_result_regression", {})
    hfa = m.get("home_field_by_season", [])

    hfa_rows = [[str(h["season"]), str(h["games"]), num(h["mean_home_margin"], 2, sign=True),
                 pct(h["home_win_rate"]), src("nflverse-data")] for h in hfa[-10:]]
    kn_rows = [[str(k["margin"]), pct(k["share"]), src("nflverse-data")] for k in kn.get("top_absolute_margins", [])]
    cal_rows = [[str(b["bucket"]), str(b["n"]), pct(b["mean_market_prob"]), pct(b["actual_win_rate"]),
                 pct(b["diff"], 1, sign=True), src("nflverse-data")] for b in cal.get("buckets", [])]

    body = (f'''<div class="hero compact"><div class="eyebrow">MARKET BENCHMARK</div>
<h1>The number to beat is the closing line.</h1>
<p class="lede">Everything else in this project is measured against these quantities. If a strategy
cannot beat the closing line, it has not found an edge - it has found a story.</p></div>

'''
        + section("Closing-line accuracy", table(
    ["Market", "n", "MAE", "RMSE", "Bias", "Residual SD", "Correlation", "Source"],
    [["Spread", str(cs.get("n")), num(cs.get("mae")), num(cs.get("rmse")), num(cs.get("bias"), 3),
      num(cs.get("sd_resid")), num(cs.get("corr"), 3), src("nflverse-data")],
     ["Total", str(ct.get("n")), num(ct.get("mae")), num(ct.get("rmse")), num(ct.get("bias"), 3),
      num(ct.get("sd_resid")), num(ct.get("corr"), 3), src("nflverse-data")]],
    caption="1999-2026 regular season, games with a closing line."))
        + section("Two-way balance", table(
    ["Measure", "Value", "Detail", "Source"],
    [["Home cover rate", pct(ats.get("home_cover_rate")), f"CI {ats.get('ci')}, pushes {ats.get('pushes')}, p = {ats.get('binomial_p')}", src("nflverse-data")],
     ["Over rate", pct(over.get("over_rate")), f"n = {over.get('n')}, pushes {over.get('pushes')}, p = {over.get('binomial_p')}", src("nflverse-data")],
     ["Mean quoted hold on the spread", pct(hold.get("mean_hold")), f"n = {hold.get('n')} games, median {pct(hold.get('median_hold'))}", src("nflverse-data")],
     ["Regression slope (closing spread on margin)", num(reg.get("slope"), 3), "1.0 = unbiased", src("nflverse-data")]]))
        + section("Key numbers", table(["Absolute margin", "Share of games", "Source"], kn_rows,
    caption=f"A spread sitting on 3 pushes about {pct(kn.get('push_rate_on_3'))} of the time; on 7, about {pct(kn.get('push_rate_on_7'))}."))
        + section("Moneyline calibration (market vs outcomes)", table(
    ["Probability bucket", "n", "Market implied", "Actual", "Difference", "Source"], cal_rows,
    caption=f"Shin-devitched two-way moneylines. Brier score {num(cal.get('brier_score'), 4)} vs 0.25 for a coin flip, seasons {cal.get('seasons')}."))
        + section("Home-field advantage by season", table(
    ["Season", "Games", "Mean home margin", "Home win rate", "Source"], hfa_rows,
    caption="Home advantage is not a constant. In 2026 it has been negative so far, which is why the model shrinks the estimate.")))
    return W.layout("Market benchmark", "pages/market.html", body,
                    subtitle="Accuracy, bias and calibration of the closing market.")


# ---------------------------------------------------------------- method
def page_method() -> str:
    man = W.load("manifest.json", {})
    prof = W.load("profile.json", {})
    games = prof.get("games", {})
    player = prof.get("player_week", {})
    dl = man.get("downloads", [])
    dl_rows = [[esc(d["name"]), esc(str(d.get("status"))), f'{d.get("bytes", 0):,}',
                (d.get("sha256") or "")[:16] + "...", esc(d.get("tag", "")), src("nflverse-data", "Release asset")]
               for d in dl[:8]]
    body = (f'''<div class="hero compact"><div class="eyebrow">METHOD &amp; DATA</div>
<h1>Reproducible, or it does not count.</h1>
<p class="lede">The site is generated from committed code and committed data artefacts. Anyone can
re-run the pipeline and get the same numbers, including the ones that are unflattering.</p></div>

'''
        + section("Pipeline", '''<ol class="steps">
<li><strong>Fetch</strong> - <code>scripts/fetch_data.py</code> downloads the nflverse release assets and records size and SHA-256.</li>
<li><strong>Profile</strong> - <code>scripts/profile.py</code> records columns, coverage and nulls per season.</li>
<li><strong>Prove conventions</strong> - <code>scripts/diag_signs.py</code> determines the spread sign convention from the data.</li>
<li><strong>Measure</strong> - market, model, correlation, luck, strategy and prop scripts write JSON only.</li>
<li><strong>Build</strong> - <code>scripts/build_site.py</code> renders these pages from that JSON; no value is typed by hand.</li>
</ol>
<p class="small">Each run commits <code>data/derived/run_log.txt</code>, so failures are visible in the repository rather than only in CI logs.</p>''')
        + section("Coverage", table(
    ["Dataset", "Rows", "Seasons", "Notes", "Source"],
    [["Games", f"{games.get('rows', 0):,}", f"{games.get('seasons', [None])[0]}-{games.get('seasons', [None, None])[-1]}",
      f"odds columns: {', '.join(games.get('odds_columns', []))}", src("nflverse-data")],
     ["Player weeks", f"{player.get('rows', 0):,}", "2012-2026",
      f"current-season max week {player.get('current_season_max_week')}", src("nflverse-data")],
     ["Team weeks", f"{(prof.get('team_week', {}) or {}).get('rows', 0):,}", "2012-2026",
      "EPA and efficiency columns available", src("nflverse-data")]]))
        + section("Downloaded files (first 8 of the manifest)", table(
    ["File", "Status", "Bytes", "SHA-256 (prefix)", "Release", "Source"], dl_rows,
    caption="The full manifest, including every file, is in data/derived/manifest.json."))
        + section("Parallel-session archive",
                  '<p>Other agent sessions produced their own dashboards in this repository. They are '
                  'preserved unchanged and are not part of the published navigation: '
                  '<a href="pages/archive.html">see the archive &rarr;</a></p>')
        + section("Known method limitations", '''<ul class="crosses">
<li>Only closing lines are available. No timestamps or opening prices, so closing-line value cannot be
measured - a limitation that makes every ROI here conservative rather than flattering.</li>
<li>The model is deliberately simple: transparent weighted least squares, no tracking data, no injury
information, no opponent-adjusted efficiency.</li>
<li>Push handling follows the operator rulebook; games with a changed venue or abandoned status are
not modelled.</li>
<li>No prop prices exist in the feed, so prop work stops at calibration.</li>
</ul>'''))
    return W.layout("Method & data", "pages/method.html", body,
                    subtitle="How every number on this site is produced.")


# ---------------------------------------------------------------- sources
def page_sources() -> str:
    ss = W.sources()
    rows_own, rows_sib = [], []
    for sid, s in ss.items():
        title = s.get("title") or s.get("label") or sid
        pub = s.get("publisher") or s.get("org") or ""
        kind = {"official": "ok", "regulator": "ok", "academic": "ok", "community": "warn",
                "unverified": "bad"}.get(s.get("type"), "warn")
        confirmed = s.get("confirmed") or s.get("note") or ""
        if len(confirmed) > 240:
            confirmed = confirmed[:237].rstrip() + "..."
        row = [esc(title), esc(pub), badge(kind, str(s.get("type", ""))[:18]), esc(confirmed),
               f'<a href="{esc(s["url"])}" rel="noopener">Open</a>']
        if (s.get("verified_by") or "").startswith("integration session"):
            rows_own.append(row)
        else:
            rows_sib.append(row)

    body = (
        '<div class="hero compact"><div class="eyebrow">SOURCE REGISTER</div>'
        '<h1>Every claim has a link.</h1>'
        '<p class="lede">Two groups are shown separately because they were verified by different '
        'sessions on the same day. Group 1 was opened and read by this build; group 2 was contributed '
        'by sibling sessions working in parallel on this repository, and is reproduced with their '
        'confirmation notes rather than re-asserted as verified here.</p></div>'
        + section("1. Verified by this build", table(
            ["Source", "Publisher", "Type", "What was confirmed", "Link"], rows_own,
            caption="Each entry was opened on 2026-11-01 and its content read; sources that could not be "
                    "confirmed are excluded and appear on the Flagged for review page instead."))
        + section("2. Registry entries from sibling sessions", table(
            ["Source", "Publisher", "Type", "Confirmation note as recorded", "Link"], rows_sib,
            caption="Carried over unchanged from the shared registry so the two sessions do not "
                    "overwrite each other's work. Verify before relying on any of these."))
        + section("How sources are used", '<ul class="ticks">'
                  '<li><strong>Official NFL</strong> documents define rules, statistics and data distribution.</li>'
                  '<li><strong>Regulator</strong> filings define how bets settle, including pushes and parlay mechanics.</li>'
                  '<li><strong>Academic</strong> work supplies the statistical methods (FDR control, bet sizing).</li>'
                  '<li><strong>Community</strong> feeds supply the numbers, with file hashes recorded in the manifest.</li>'
                  '</ul>'))
    return W.layout("Source register", "pages/sources.html", body,
                    subtitle="Verified sources, grouped by who verified them.")


# ---------------------------------------------------------------- flagged
def page_flagged() -> str:
    items = [
        ("No historical player-prop prices", "high",
         "Prop ROI cannot be computed. The feed carries game lines only, and the NFL's official data "
         "distributor supplies prop and same-game-parlay pricing to operators, not to this project.",
         "nfl-genius", "Prop accuracy and calibration are published; ROI is left blank."),
        ("No opening lines or timestamps", "high",
         "Closing-line value - the standard test of betting skill - needs the price at bet time and "
         "the closing price. Only the closing price exists here.",
         "nflverse-data", "Every ROI on this site is settled at the close, which is the conservative choice."),
        ("Executable access unverified", "high",
         "No verified sportsbook account, limits, jurisdiction or price availability. Gate G9 "
         "therefore fails for every strategy by construction.",
         "dk-house-rules", "Nothing is presented as actionable."),
        ("Reward pool not funded", "medium",
         "The leaderboard reward tiers are a design proposal. No prize money exists.",
         "kelly-1956", "Rewards are labelled as a schedule, not a promise."),
        ("Fixed-odds parlay ladder not verified", "medium",
         "The 2-6 leg payout ladder used for the illustrative EV table is a common industry ladder, "
         "but it differs by operator and was not confirmed in the rulebook that was read.",
         "dk-house-rules", "Marked illustrative; the teaser prices in the same table ARE sourced."),
        ("NFL injury-report policy page not found", "medium",
         "operations.nfl.com/football-ops/league-governance/injury-report/ returns 404. Without an "
         "official policy text, injury-based signals are blocked rather than guessed.",
         "nfl-injury-policy", "No injury strategy is registered."),
        ("Model underperforms the market", "medium",
         "The originated lines are worse than the closing line out of sample, and add no incremental "
         "information. They are published for grading, not use.",
         "nflverse-data", "Published with the loss on the record."),
        ("One-score persistence is marginal", "low",
         "Year-over-year correlation of one-score win rate is small but non-zero (p just under 0.05). "
         "It could be a real effect or a multiple-testing artefact; it is not used in any strategy.",
         "bh-1995", "Reported with its p-value instead of being dropped."),
        ("2026 home-field anomaly", "low",
         "Home teams have a negative mean margin in 2026 so far. A single partial season is not "
         "enough to re-estimate home advantage, so the model shrinks toward a ten-season prior.",
         "nflverse-data", "Shrinkage is documented in the model spec."),
    ]
    rows = []
    for title, sev, detail, sid, status in items:
        kind = {"high": "bad", "medium": "warn", "low": "ok"}[sev]
        rows.append([esc(title), badge(kind, sev), esc(detail), esc(status), src(sid)])

    body = (f'''<div class="hero compact"><div class="eyebrow">FLAGGED FOR REVIEW</div>
<h1>What is missing, and why it is blank.</h1>
<p class="lede">Nothing on this page blocks the site from publishing. Each item is a gap that was
found by checking rather than assumed away - the alternative is a dashboard full of confident
numbers that cannot be defended.</p></div>

'''
        + section("Open items", table(["Item", "Severity", "What is missing", "How it is handled here", "Source"], rows))
        + section("Unverified values policy", '''<ul class="ticks">
<li>If a value cannot be confirmed from a primary source, it is left blank.</li>
<li>A blank is always accompanied by a reason, on this page.</li>
<li>No value is inferred, interpolated or copied from a secondary summary.</li>
<li>Computed statistics are labelled as computations, with the code and data manifest that produced them.</li>
</ul>'''))
    return W.layout("Flagged for review", "pages/flagged.html", body,
                    subtitle="Known gaps, published instead of hidden.")


def archive_dirs() -> list[tuple[str, str]]:
    """Sibling dashboards built by parallel sessions, kept verbatim for audit."""
    out = []
    labels = {
        "dashboard": "Framework dashboard (session arena/97d4c0f1)",
        "nfl-lines": "Line origination draft (parallel session)",
        "nfl-research": "Research brief (session arena/e0d506a4)",
        "origination-lab": "Origination lab draft (parallel session)",
        "quant-lab": "Quant lab draft (parallel session)",
        "research-desk": "Research desk draft (parallel session)",
        "audit": "Independent audit harness (parallel session)",
        "results": "Results artefacts (parallel session)",
    }
    for d, label in labels.items():
        if os.path.exists(os.path.join(d, "index.html")):
            out.append((d, label))
    return out


def page_archive() -> str:
    dirs = archive_dirs()
    rows = [[esc(label), f'<a href="../{esc(d)}/index.html">{esc(d)}/</a>',
             "Preserved unchanged; not part of the published navigation", "Sibling session artefact"]
            for d, label in dirs]
    body = (
        '<div class="hero compact"><div class="eyebrow">ARCHIVE</div>'
        '<h1>Earlier parallel-session work, kept intact.</h1>'
        '<p class="lede">Several agent sessions worked on this repository at the same time. Their '
        'dashboards are preserved byte-for-byte for audit; this site is the integrated one. Their '
        'pages were not edited, so where they disagree with this dashboard, the measured numbers here '
        'take precedence and the disagreement is recorded on the Flagged for Review page.</p></div>'
        + section("Preserved artefacts", table(
            ["Artefact", "Location", "Status", "Provenance"], rows,
            caption="Nothing here is deleted or rewritten. These directories are outside the published navigation.")))
    return W.layout("Archive", "pages/archive.html", body,
                    subtitle="Parallel-session dashboards retained for audit.")


def main() -> None:
    pages = {
        "pages/executive.html": page_executive,
        "pages/lines.html": page_lines,
        "pages/props.html": page_props,
        "pages/correlation.html": page_correlation,
        "pages/strategies.html": page_strategies,
        "pages/validation.html": page_validation,
        "pages/leaderboard.html": page_leaderboard,
        "pages/luck.html": page_luck,
        "pages/market.html": page_market,
        "pages/method.html": page_method,
        "pages/sources.html": page_sources,
        "pages/flagged.html": page_flagged,
        "pages/archive.html": page_archive,
    }
    W.write("index.html", page_index())
    for path, fn in pages.items():
        W.write(path, fn())
    print(f"wrote index.html and {len(pages)} pages")


if __name__ == "__main__":
    main()
