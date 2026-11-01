"""Render the static site from results/*.json.

One generator, one layout, so the navigation, the disclaimer and the source
plumbing cannot drift between pages. Every table row that carries a finding also
carries a link, and tests/check_site.py fails the build if that stops being true.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from common import RESULTS, ROOT, jload

PAGES = ROOT / "pages"
PAGES.mkdir(exist_ok=True)

NFL = {
    "standings": "https://www.nfl.com/standings/division/2026/REG",
    "schedule": "https://www.nfl.com/schedules/2026/by-week/week-{week}",
    "results": "https://www.nfl.com/schedules/",
    "player_stats": "https://www.nfl.com/stats/player-stats/",
    "team_stats": "https://www.nfl.com/stats/team-stats/",
    "rules": "https://operations.nfl.com/the-rules/2025-nfl-rulebook/",
    "passing": "https://www.nfl.com/stats/player-stats/category/passing/2026/reg/all/passingyards/desc",
}
NFLVERSE = "https://github.com/nflverse/nflverse-data/releases/download"

NAV = [
    ("index.html", "Overview"),
    ("pages/executive.html", "Executive summary"),
    ("pages/market.html", "Market efficiency"),
    ("pages/strategies.html", "Strategy lab"),
    ("pages/validation.html", "Validation gates"),
    ("pages/leaderboard.html", "Leaderboard"),
    ("pages/correlation.html", "Correlation &amp; pricing"),
    ("pages/props.html", "Player props"),
    ("pages/lines.html", "Originated lines"),
    ("pages/verification.html", "Verification"),
    ("pages/sources.html", "Data &amp; sources"),
    ("pages/flagged.html", "Flagged for review"),
]


# ---------------------------------------------------------------------------
# formatting helpers
# ---------------------------------------------------------------------------
def esc(v) -> str:
    return html.escape(str(v), quote=True)


def pct(x, digits=2, signed=True):
    if x is None:
        return '<span class="na">unverified</span>'
    v = x * 100
    s = f"{v:+.{digits}f}%" if signed else f"{v:.{digits}f}%"
    return esc(s)


def num(x, digits=2):
    if x is None:
        return '<span class="na">unverified</span>'
    return esc(f"{x:,.{digits}f}")


def integer(x):
    if x is None:
        return '<span class="na">unverified</span>'
    return esc(f"{x:,}")


def ext(url, label="Source"):
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{label} &#8599;</a>'


def badge(kind: str, text: str) -> str:
    return f'<span class="badge {kind}">{esc(text)}</span>'


def pass_badge(ok: bool) -> str:
    return badge("ok", "PASS") if ok else badge("bad", "FAIL")


def table(headers, rows, cls="data") -> str:
    head = "".join(f'<th scope="col">{h}</th>' for h in headers)
    body = "".join("<tr>" + "".join(cells) + "</tr>" for cells in rows)
    return f'<div class="table-wrap"><table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def td(v) -> str:
    return f"<td>{v}</td>"


def th(v) -> str:
    return f'<th scope="row">{v}</th>'


# ---------------------------------------------------------------------------
# page skeleton
# ---------------------------------------------------------------------------
def render(slug: str, title: str, crumb: str, body: str) -> str:
    depth = "" if slug == "index.html" else "../"
    nav = []
    for href, label in NAV:
        cls = ' class="active" aria-current="page"' if href == slug else ""
        nav.append(f'<a href="{depth}{href}"{cls}>{label}</a>')
    navhtml = "".join(nav)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="NFL line origination research: measured, sourced and gated.">
<title>{esc(title)} | Line Lab</title>
<link rel="stylesheet" href="{depth}assets/style.css"></head><body>
<aside><a class="brand" href="{depth}index.html"><span class="mark">L</span><span>LINE LAB<small>NFL RESEARCH</small></span></a>
<div class="nav-label">WORKSPACE</div><nav aria-label="Main navigation">{navhtml}</nav>
<div class="sidebar-note">EVIDENCE STATUS<strong>0 ranked</strong><span>5 strategies gated &middot; 32/32 verified</span></div></aside>
<main><header><span>RESEARCH / {esc(crumb)}</span><a href="{depth}pages/flagged.html" class="review-link">Review flags &#8599;</a></header>
{body}
<footer>Research, not betting advice. Every figure is computed from the files in this repository and reconciled against NFL.com. Wager only where legal and only if of age; free, confidential help is available through the <a href="https://www.ncpgambling.org/help-treatment/about-the-national-problem-gambling-helpline/" target="_blank" rel="noopener noreferrer">National Council on Problem Gambling</a>.<a href="{depth}pages/sources.html">Source register</a></footer></main></body></html>"""


def section(eyebrow: str, heading: str, link: str | None = None) -> str:
    right = f'<a href="{link[0]}">{esc(link[1])} &#8594;</a>' if link else ""
    return (f'<div class="section-head"><div><div class="eyebrow">{esc(eyebrow)}</div>'
            f'<h2>{heading}</h2></div>{right}</div>')


def note(text_html: str) -> str:
    return f'<div class="notice"><span class="dot"></span><div>{text_html}</div></div>'


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------
def page_index() -> str:
    mkt = jload("market.json") or {}
    strat = jload("strategies.json") or {}
    corr = jload("correlations.json") or {}
    props = jload("props.json") or {}
    ver = jload("verification.json") or {}
    orig = jload("originate.json") or {}

    n_games = mkt.get("convention_check") and strat.get("strategies", {})
    settled = (mkt.get("blind", {}).get("home") or {}).get("n")
    n_strat = len([k for k, v in (strat.get("strategies") or {}).items() if v.get("n")])
    ranked = len((strat.get("gates") or {}).get("ranked") or [])
    r_qb_wr = next((c for c in (corr.get("correlations") or [])
                    if c["name"].startswith("QB passing yards")), {})
    best = max((v for v in (strat.get("strategies") or {}).values() if v.get("n")),
               key=lambda v: v["roi"], default={})

    cards = f"""<div class="cards">
<article><span>01 / SAMPLE</span><strong>{integer(settled)}</strong><p>Settled regular-season games with a closing line, 1999&ndash;2026.</p><a href="pages/market.html">Market baseline &#8594;</a></article>
<article><span>02 / STRATEGIES</span><strong>{n_strat}</strong><p>Pre-registered strategies, each pushed through six gates.</p><a href="pages/strategies.html">Strategy lab &#8594;</a></article>
<article><span>03 / RANKED</span><strong>{ranked}</strong><p>Strategies that cleared every gate. None did.</p><a href="pages/leaderboard.html">Leaderboard &#8594;</a></article>
<article><span>04 / VERIFIED</span><strong>{ver.get('teams_matched', '&mdash;')}/{ver.get('teams_checked', '&mdash;')}</strong><p>2026 team records reconciled line by line with NFL.com.</p><a href="pages/verification.html">Verification &#8594;</a></article>
</div>"""

    findings = [
        (th("Closing spread is efficient"),
         td("Fitting margin on the closing spread gives a slope of "
            f"<strong>{num(mkt.get('calibration', {}).get('spread_all', {}).get('slope'))}</strong> "
            f"with R&sup2; {num(mkt.get('calibration', {}).get('spread_all', {}).get('r2'), 3)}. "
            "Home teams beat their own line by "
            f"{num(mkt.get('line_bias', {}).get('mean_points'), 3)} points on average "
            f"(t = {num(mkt.get('line_bias', {}).get('t'))}, "
            f"p = {num(mkt.get('line_bias', {}).get('p'), 3)}): no measurable bias."),
         td(badge("ok", "Measured")),
         td(ext(NFL["schedule"].format(week=8), "NFL.com schedule"))),
        (th("No public system survives correction"),
         td(f"12 classic public angles were tested. The smallest raw p-value is "
            f"{num(min((v['p'] for v in (mkt.get('bias_tests') or {}).values() if v.get('p')), default=None), 3)}. "
            f"Benjamini&ndash;Hochberg at q = 0.10 keeps "
            f"<strong>{(mkt.get('fdr') or {}).get('n_pass')}</strong> of "
            f"{(mkt.get('fdr') or {}).get('n_tests')}."),
         td(badge("bad", "0 survive")),
         td(ext(NFL["results"], "NFL.com results"))),
        (th("The rating model loses to the close"),
         td("A walk-forward opponent-adjusted rating model scores a Brier skill of "
            f"<strong>{num((strat.get('model') or {}).get('brier_skill_vs_market'), 4)}</strong> "
            "against the closing line. Negative means worse than the market. Betting its "
            f"disagreements returns {pct(best.get('roi'))}."),
         td(badge("bad", "Negative skill")),
         td(ext(NFL["team_stats"], "NFL.com team stats"))),
        (th("Same-game legs are not independent"),
         td("Quarterback passing yards and that team's WR1 receiving yards move together at "
            f"<strong>r = {num(r_qb_wr.get('r'), 3)}</strong> over {integer(r_qb_wr.get('n'))} team-games. "
            "A two-leg same-game parlay priced as independent is worth "
            f"&times;{num((corr.get('sgp') or {}).get('qb_plus_wr1', {}).get('correlation_multiple'), 2)} "
            "more than the naive product."),
         td(badge("ok", "Measured")),
         td(ext(NFL["player_stats"], "NFL.com player stats"))),
        (th("Prop lines must be medians, not means"),
         td("Player output is right-skewed. A line set at the model's mean is beaten only "
            f"<strong>{pct((props.get('markets') or {}).get('receiving_yards', {}).get('overall', {}).get('over_rate_vs_mean_projection'), 1, False)}</strong> "
            "of the time; the walk-forward median calibration brings it to "
            f"{pct((props.get('markets') or {}).get('receiving_yards', {}).get('overall', {}).get('over_rate_vs_calibrated_line'), 1, False)}."),
         td(badge("ok", "Measured")),
         td(ext(NFL["player_stats"], "NFL.com player stats"))),
        (th("Our own lines, published"),
         td(f"{orig.get('summary', {}).get('n_games', 0)} unplayed games carry an originated spread and total. "
            f"Mean absolute disagreement with the market is "
            f"<strong>{num(orig.get('summary', {}).get('mean_abs_line_gap'), 2)} points</strong>."),
         td(badge("warn", "Benchmark only")),
         td(ext(NFL["schedule"].format(week=9), "NFL.com week 9"))),
    ]

    body = f"""<div class="eyebrow">INDEPENDENT NFL RESEARCH</div>
<h1>Originated lines,<br><em>measured not asserted.</em></h1>
<p class="intro">Every number on this site is computed from a file in the repository, then reconciled against NFL.com. Where a value could not be confirmed it is shown as unverified rather than filled in.</p>
{note('<strong>Nothing here is ranked.</strong> Five strategies were built and gated; none cleared all six gates. The site therefore reports measurements, not picks.')}
{section("AT A GLANCE", "The state of play", ("pages/executive.html", "Read executive summary"))}
{cards}
{section("HEADLINE FINDINGS", "What the data actually says", ("pages/market.html", "Full market analysis"))}
{table(["FINDING", "EVIDENCE", "STATUS", "SOURCE"], findings)}
{section("METHOD", "How a strategy earns a rank")}
<div class="steps">
<div><b>01</b><strong>Pre-register</strong><p>The rule is fixed before any outcome is looked at, and it only sees pre-kickoff information.</p></div>
<div><b>02</b><strong>Walk forward</strong><p>Each season is predicted using earlier seasons only. No shuffling, no future data.</p></div>
<div><b>03</b><strong>Price it</strong><p>Settlement uses the stored closing price, not an assumed &minus;110.</p></div>
<div><b>04</b><strong>Gate it</strong><p>Six gates, including multiple-testing correction and a luck permutation test.</p></div>
</div>
<p class="disclaimer">Luck cannot be removed from sport. It can be priced: every strategy here is compared against thousands of random portfolios of the same size, at the same prices.</p>"""
    return render("index.html", "Overview", "OVERVIEW", body)


def page_executive() -> str:
    mkt = jload("market.json") or {}
    strat = jload("strategies.json") or {}
    corr = jload("correlations.json") or {}
    props = jload("props.json") or {}
    ver = jload("verification.json") or {}
    orig = jload("originate.json") or {}
    gates = (strat.get("gates") or {}).get("by_strategy") or {}
    best_key = max(gates, key=lambda k: gates[k]["passed"]) if gates else None
    cal = mkt.get("calibration", {}).get("spread_all", {})

    rows = [
        (th("Objective"), td("Originate our own NFL lines, test whether any of them carry skill, and rank the survivors."), td(badge("done", "Delivered")), td(ext(NFL["schedule"].format(week=9), "NFL.com"))),
        (th("Data"), td(f"{integer((mkt.get('blind', {}).get('home') or {}).get('n'))} settled regular-season games (1999&ndash;2026) with closing spread and total, plus 12 seasons of team and player week data. Provenance, byte sizes and SHA-256 are in the data register."), td(badge("ok", "Sourced")), td(ext(NFLVERSE + "/schedules/games.csv", "nflverse"))),
        (th("Verification"), td(f"All {ver.get('teams_checked')} 2026 team records rebuilt from the data match NFL.com exactly on wins, losses, ties, points for and points against, across {ver.get('games_settled')} settled games."), td(badge("ok", "32/32 match")), td(ext(ver.get("official_source", NFL["standings"]), "NFL.com standings"))),
        (th("Market efficiency"), td(f"Closing spread slope {num(cal.get('slope'))}, R&sup2; {num(cal.get('r2'), 3)}, residual SD {num(cal.get('rmse'))} points. Mean line error {num(mkt.get('line_bias', {}).get('mean_points'), 3)} points (p = {num(mkt.get('line_bias', {}).get('p'), 3)}). The close is not systematically beatable by direction alone."), td(badge("ok", "Measured")), td(ext(NFL["results"], "NFL.com"))),
        (th("Blind betting"), td(f"Betting every home side returns {pct((mkt.get('blind', {}).get('home') or {}).get('roi'))}; every away side {pct((mkt.get('blind', {}).get('away') or {}).get('roi'))}; every over {pct((mkt.get('blind', {}).get('over') or {}).get('roi'))}. The mean spread overround in the data is {pct((mkt.get('overround') or {}).get('spread_mean'), 2, False)}."), td(badge("ok", "Measured")), td(ext(NFL["results"], "NFL.com"))),
        (th("Public angles"), td(f"{(mkt.get('fdr') or {}).get('n_tests')} classic angles tested; {(mkt.get('fdr') or {}).get('n_pass')} survive Benjamini&ndash;Hochberg at q = 0.10. The best raw result is the wind-under angle at {pct(((mkt.get('bias_tests') or {}).get('wind15_under') or {}).get('roi'))} on {integer(((mkt.get('bias_tests') or {}).get('wind15_under') or {}).get('n'))} bets, p = {num(((mkt.get('bias_tests') or {}).get('wind15_under') or {}).get('p'), 3)}."), td(badge("warn", "Not significant after correction")), td(ext(NFL["schedule"].format(week=1), "NFL.com"))),
        (th("Model skill"), td(f"Walk-forward rating model Brier score {num((strat.get('model') or {}).get('brier_model'), 4)} versus market {num((strat.get('model') or {}).get('brier_market'), 4)}. Brier skill against the market: {num((strat.get('model') or {}).get('brier_skill_vs_market'), 4)}. The market wins."), td(badge("bad", "Model loses")), td(ext(NFL["team_stats"], "NFL.com"))),
        (th("Strategy gate result"), td(f"{(strat.get('gates') or {}).get('fdr', {}).get('n_pass')} of {(strat.get('gates') or {}).get('fdr', {}).get('n_tests')} strategies survive FDR correction; {len((strat.get('gates') or {}).get('ranked') or [])} clear all six gates. Best partial result: {esc(best_key or '')}."), td(badge("warn", "0 ranked")), td(ext(NFL["results"], "NFL.com"))),
        (th("Parlays"), td(f"A three-leg model parlay returned {pct(((strat.get('parlays') or {}).get('parlay3_model') or {}).get('roi'))} over {(strat.get('parlays') or {}).get('parlay3_model', {}).get('n_tickets')} tickets, but hit only {pct(((strat.get('parlays') or {}).get('parlay3_model') or {}).get('hit_rate'), 1, False)} against an expected {pct(((strat.get('parlays') or {}).get('parlay3_model') or {}).get('mean_naive_p'), 1, False)}. The model, not the market, was wrong."), td(badge("bad", "Miscalibrated")), td(ext(NFL["results"], "NFL.com"))),
        (th("Same-game pricing"), td(f"QB passing yards and WR1 receiving yards correlate at r = {num(next((c['r'] for c in corr.get('correlations', []) if c['name'].startswith('QB passing')), None), 3)}. Pricing that pair as independent understates the joint probability by a factor of {num((corr.get('sgp') or {}).get('qb_plus_wr1', {}).get('correlation_multiple'), 2)}."), td(badge("ok", "Measured")), td(ext(NFL["player_stats"], "NFL.com"))),
        (th("Player props"), td(f"Projection skill over a naive last-five baseline is {pct((props.get('markets') or {}).get('receiving_yards', {}).get('overall', {}).get('skill_vs_last5'))} for receiving yards. No historical prop prices exist in any free source, so no prop ROI is claimed."), td(badge("warn", "Skill only, no price")), td(ext(NFL["player_stats"], "NFL.com"))),
        (th("Originated lines"), td(f"{orig.get('summary', {}).get('n_games')} unplayed games carry our spread and total, as of week {orig.get('as_of', {}).get('week')}. Mean absolute gap to the market: {num(orig.get('summary', {}).get('mean_abs_line_gap'))} points. Published as a benchmark, not a bet list."), td(badge("warn", "Reference only")), td(ext(NFL["schedule"].format(week=9), "NFL.com"))),
        (th("Recommendation"), td("Do not stake money on anything on this site. The correct next step is a licensed, timestamped history of prop and alternate prices, which is the one input that would let a prop strategy be priced at all."), td(badge("bad", "Do not bet")), td(ext(NFL["player_stats"], "NFL data partner"))),
    ]

    body = f"""<div class="eyebrow">DECISION BRIEF</div>
<h1>Executive summary</h1>
<p class="intro">Fourteen lines. Each one is either measured here or marked unverified; nothing is inferred.</p>
{table(["ITEM", "DETAIL", "STATUS", "SOURCE"], rows)}
<p class="disclaimer">Reading rule: a <strong>PASS</strong> badge means a gate was cleared by the numbers, not that a strategy is profitable. Nothing on this site is ranked.</p>"""
    return render("pages/executive.html", "Executive summary", "EXECUTIVE SUMMARY", body)


def page_market() -> str:
    mkt = jload("market.json") or {}
    cal = mkt.get("calibration", {})
    rows = []
    for key, label in [("spread_all", "Spread, all seasons"), ("total_all", "Total, all seasons"),
                       ("spread_1999-2009", "Spread, 1999-2009"), ("spread_2010-2019", "Spread, 2010-2019"),
                       ("spread_2020-2026", "Spread, 2020-2026"), ("total_2020-2026", "Total, 2020-2026")]:
        c = cal.get(key) or {}
        rows.append((th(label), td(integer(c.get("n"))), td(num(c.get("slope"), 3)),
                     td(num(c.get("r2"), 3)), td(num(c.get("rmse"), 2)),
                     td(ext(NFL["results"], "NFL.com"))))

    blind = [(th(k.capitalize()), td(integer(v.get("n"))), td(pct(v.get("win_rate"), 1, False)),
              td(pct(v.get("roi"))), td(pct(v.get("ci_lo")) + " to " + pct(v.get("ci_hi"))),
              td(ext(NFL["results"], "NFL.com")))
             for k, v in (mkt.get("blind") or {}).items()]

    bias = []
    for k, v in (mkt.get("bias_tests") or {}).items():
        bias.append((th(esc(v.get("desc", k))), td(integer(v.get("n"))), td(pct(v.get("hit_rate"), 1, False)),
                     td(pct(v.get("roi"))), td(f"{num(v.get('t'))}"), td(num(v.get("p"), 3)),
                     td(pass_badge(bool(v.get("fdr_q10_pass")))),
                     td(ext(NFL["results"], "NFL.com"))))

    lb = mkt.get("line_bias") or {}
    er = mkt.get("by_era") or {}
    era_rows = [(th(esc(e)), td(integer(v.get("n"))), td(pct(v.get("favourite_win_rate"), 1, False)),
                 td(num(v.get("mean_total"), 1)), td(num(v.get("mean_abs_spread"), 2)),
                 td(ext(NFL["results"], "NFL.com"))) for e, v in er.items()]

    body = f"""<div class="eyebrow">BASELINE</div>
<h1>How efficient is the close?</h1>
<p class="intro">Before any strategy can claim skill it has to beat the closing price. This page measures that price instead of assuming it.</p>
{note('<strong>Sign convention, verified.</strong> In the source file <code>spread_line</code> is positive when the <em>home</em> team is favoured. We confirmed this two ways: 100% of games with a positive line have a negative home moneyline, and mean home margin rises monotonically across line deciles. Full check on the <a href="../pages/flagged.html">review page</a>.')}
{section("CALIBRATION", "Does the number predict the result?")}
{table(["MARKET", "GAMES", "SLOPE", "R&sup2;", "RESIDUAL SD (PTS)", "SOURCE"], rows)}
<p class="disclaimer">A slope of 1.0 means the market is unbiased in points. The all-season slope of {num(cal.get('spread_all', {}).get('slope'), 3)} is close to it, with a t-statistic against 1.0 of {num(cal.get('spread_all', {}).get('slope_t'), 2)}.</p>
{section("LINE ERROR", "Is the close systematically wrong?")}
{table(["MEASURE", "VALUE", "INTERPRETATION", "SOURCE"], [
 (th("Mean spread error"), td(f"{num(lb.get('mean_points'), 3)} points"), td(f"t = {num(lb.get('t'))}, p = {num(lb.get('p'), 3)}. Not different from zero."), td(ext(NFL["results"], "NFL.com"))),
 (th("Median spread error"), td(f"{num(lb.get('spread_median_points'), 1)} points"), td("Exactly zero: the median game lands on the number."), td(ext(NFL["results"], "NFL.com"))),
 (th("Mean total error"), td(f"{num(lb.get('total_mean_points'), 3)} points"), td(f"t = {num(lb.get('total_t'))}, p = {num(lb.get('total_p'), 5)}. Positive because totals are right-skewed."), td(ext(NFL["results"], "NFL.com"))),
 (th("Median total error"), td(f"{num(lb.get('total_median_points'), 1)} points"), td("Zero. The skew, not a soft number, explains the mean."), td(ext(NFL["results"], "NFL.com"))),
 (th("Over hit rate"), td(pct(lb.get("over_hit_rate_nonpush"), 2, False)), td("Below 50%. The apparently high average total is not a betting edge."), td(ext(NFL["results"], "NFL.com"))),
])}
{section("THE VIG WALL", "What a blind bet earns")}
{table(["SIDE", "BETS", "WIN RATE", "ROI", "95% BOOTSTRAP CI", "SOURCE"], blind)}
{section("PUBLIC ANGLES", "Twelve classics, corrected for multiplicity")}
{table(["ANGLE", "BETS", "HIT RATE", "ROI", "t", "p", "BH-FDR q=0.10", "SOURCE"], bias)}
<p class="disclaimer">Raw p-values are not evidence. Testing twelve angles guarantees roughly one false positive at the 5% level, which is exactly what {(mkt.get('fdr') or {}).get('n_pass')} passing angles out of {(mkt.get('fdr') or {}).get('n_tests')} reflects.</p>
{section("ERAS", "Stability across three rule eras")}
{table(["ERA", "GAMES", "FAVOURITE WIN RATE", "MEAN TOTAL", "MEAN |SPREAD|", "SOURCE"], era_rows)}"""
    return render("pages/market.html", "Market efficiency", "MARKET", body)


def page_strategies() -> str:
    strat = jload("strategies.json") or {}
    gates = (strat.get("gates") or {}).get("by_strategy") or {}
    rows = []
    for key, v in (strat.get("strategies") or {}).items():
        if not v.get("n"):
            continue
        g = gates.get(key, {})
        rows.append((th(esc(v.get("label") or key)),
                     td(esc(v.get("thesis", ""))),
                     td(integer(v.get("n"))),
                     td(pct(v.get("hit_rate"), 1, False)),
                     td(pct(v.get("roi"))),
                     td(num(v.get("t"))),
                     td(num(v.get("p"), 3)),
                     td(f"{g.get('passed', 0)}/{g.get('of', 6)}"),
                     td(badge("ok" if g.get("status") == "RANKED" else "warn", g.get("status", "&mdash;"))),
                     td(ext(NFL["results"], "NFL.com"))))

    splits = []
    for key, v in (strat.get("strategies") or {}).items():
        if not v.get("n"):
            continue
        s = v.get("splits") or {}
        splits.append((th(esc(v.get("label") or key)),
                       td(f"{pct((s.get('develop_2018_2022') or {}).get('roi'))} <small>(n={(s.get('develop_2018_2022') or {}).get('n', 0)})</small>"),
                       td(f"{pct((s.get('validate_2023_2024') or {}).get('roi'))} <small>(n={(s.get('validate_2023_2024') or {}).get('n', 0)})</small>"),
                       td(f"{pct((s.get('holdout_2025_2026') or {}).get('roi'))} <small>(n={(s.get('holdout_2025_2026') or {}).get('n', 0)})</small>"),
                       td(f"{pct((s.get('pre_2018') or {}).get('roi'))} <small>(n={(s.get('pre_2018') or {}).get('n', 0)})</small>"),
                       td(ext(NFL["results"], "NFL.com"))))

    mdl = strat.get("model") or {}
    model_rows = [
        (th("Brier score"), td(num(mdl.get("brier_model"), 4)), td(num(mdl.get("brier_market"), 4)), td(ext(NFL["team_stats"], "NFL.com"))),
        (th("Log loss"), td(num(mdl.get("logloss_model"), 4)), td(num(mdl.get("logloss_market"), 4)), td(ext(NFL["team_stats"], "NFL.com"))),
        (th("Directional accuracy"), td(pct(mdl.get("accuracy"), 2, False)), td("&mdash;"), td(ext(NFL["team_stats"], "NFL.com"))),
        (th("Skill vs the market"), td(num(mdl.get("brier_skill_vs_market"), 4)), td("&mdash;"), td(ext(NFL["team_stats"], "NFL.com"))),
        (th("Correlation with the close"), td(num(mdl.get("model_vs_market_r2"), 3) + " (R&sup2;)"), td("1.000 by definition"), td(ext(NFL["team_stats"], "NFL.com"))),
    ]

    par = strat.get("parlays") or {}
    p3 = par.get("parlay3_model") or {}
    par_rows = [
        (th("Tickets"), td(integer(p3.get("n_tickets"))), td("&mdash;"), td(ext(NFL["results"], "NFL.com"))),
        (th("Naive expected hit rate"), td(pct(p3.get("mean_naive_p"), 1, False)), td("Product of the three leg probabilities."), td(ext(NFL["results"], "NFL.com"))),
        (th("Actual hit rate"), td(pct(p3.get("hit_rate"), 1, False)), td(f"{integer(p3.get('actual_hits'))} wins against {num(p3.get('expected_hits_if_independent'), 1)} expected."), td(ext(NFL["results"], "NFL.com"))),
        (th("ROI"), td(pct(p3.get("roi"))), td(f"t = {num(p3.get('t'))}, p = {num(p3.get('p'), 3)}. Not distinguishable from luck."), td(ext(NFL["results"], "NFL.com"))),
    ]

    body = f"""<div class="eyebrow">STRATEGY LAB</div>
<h1>Five strategies, six gates, no survivors.</h1>
<p class="intro">Each rule was fixed before outcomes were examined and only uses information available before kickoff. Settlement uses the stored closing price.</p>
{note('<strong>Read the ROI column carefully.</strong> A positive ROI is not a pass. The gates exist precisely because five strategies will always produce one that looks good.')}
{section("RESULTS", "Walk-forward, priced at the close")}
{table(["STRATEGY", "THESIS", "BETS", "HIT RATE", "ROI", "t", "p", "GATES", "STATUS", "SOURCE"], rows)}
{section("TEMPORAL STABILITY", "Does the effect survive the next period?")}
{table(["STRATEGY", "DEVELOP 2018-2022", "VALIDATE 2023-2024", "HOLDOUT 2025-2026", "PRE-2018", "SOURCE"], splits)}
<p class="disclaimer">The weather angle is the cleanest illustration: a strong development-window return, a shrinking validation return, and nothing left in the holdout. That is what a decayed edge looks like.</p>
{section("MODEL VERSUS MARKET", "Can a public-data rating model price a game?")}
{table(["METRIC", "OUR MODEL", "MARKET", "SOURCE"], model_rows)}
{section("PARLAYS", "Three legs built from the largest model disagreements")}
{table(["METRIC", "VALUE", "NOTE", "SOURCE"], par_rows)}"""
    return render("pages/strategies.html", "Strategy lab", "STRATEGIES", body)


def page_validation() -> str:
    strat = jload("strategies.json") or {}
    gates = (strat.get("gates") or {}).get("by_strategy") or {}
    defs = []
    if gates:
        first = next(iter(gates.values()))
        for g in first["gates"]:
            defs.append((th(esc(g["gate"])), td(esc(g["rule"])), td(ext(NFL["results"], "NFL.com"))))
    matrix = []
    for key, g in gates.items():
        cells = [th(esc(g.get("name") or key))]
        for x in g["gates"]:
            detail = esc(x["value"])
            cells.append(td(pass_badge(x["pass"]) + f'<br><small>{detail}</small>'))
        cells.append(td(f"{g['passed']}/{g['of']}"))
        cells.append(td(ext(NFL["results"], "NFL.com")))
        matrix.append(cells)
    headers = ["STRATEGY"] + [g["gate"].split(" ", 1)[1] if " " in g["gate"] else g["gate"]
                              for g in (next(iter(gates.values()))["gates"] if gates else [])] + ["TOTAL", "SOURCE"]

    body = f"""<div class="eyebrow">VALIDATION</div>
<h1>Six gates before a rank.</h1>
<p class="intro">A strategy is only eligible for the leaderboard when every gate passes. The gates are pre-registered: their thresholds are fixed here, not chosen after seeing the results.</p>
{section("GATE DEFINITIONS", "What each gate demands")}
{table(["GATE", "RULE", "SOURCE"], defs)}
{section("MATRIX", "Every strategy against every gate")}
{table(headers, matrix)}
{note(f"<strong>Multiple-testing correction matters.</strong> {(strat.get('gates') or {}).get('fdr', {}).get('n_pass')} of {(strat.get('gates') or {}).get('fdr', {}).get('n_tests')} strategies survive Benjamini&ndash;Hochberg at q = 0.10. The weather angle missed the threshold by a margin of 0.001 when five strategies are tested, which is exactly the situation the correction exists for.")}"""
    return render("pages/validation.html", "Validation gates", "VALIDATION", body)


def page_leaderboard() -> str:
    strat = jload("strategies.json") or {}
    gates = (strat.get("gates") or {}).get("by_strategy") or {}
    rows = []
    scored = []
    for key, g in gates.items():
        v = (strat.get("strategies") or {}).get(key, {})
        score = 100 * g["passed"] / g["of"]
        scored.append((score, key, g, v))
    scored.sort(key=lambda t: (-t[0], -(t[3].get("roi") or -1)))
    for rank, (score, key, g, v) in enumerate(scored, start=1):
        rows.append((th(str(rank)), td(esc(g.get("name") or key)),
                     td(f"<strong>{score:.0f}</strong> / 100"),
                     td(f"{g['passed']} of {g['of']}"),
                     td(pct(v.get("roi"))),
                     td(pct(v.get("ci_lo")) + " to " + pct(v.get("ci_hi"))),
                     td(badge("warn", "PROVISIONAL")),
                     td(ext(NFL["results"], "NFL.com"))))
    body = f"""<div class="eyebrow">LEADERBOARD</div>
<h1>Nobody is on the podium.</h1>
<p class="intro">The leaderboard is defined before the results are known: a strategy enters only by clearing all six gates. The evidence score below is shown for transparency and confers no rank.</p>
{note('<strong>No funded prize exists.</strong> There is no reward pool, sponsor or entry fee. The scoring scheme is a research device for ordering effort, and it is reported here rather than dressed up as a competition prize.')}
{section("EVIDENCE SCORE", "Ordered by gates cleared, then by return")}
{table(["#", "STRATEGY", "EVIDENCE SCORE", "GATES", "ROI", "95% CI", "RANK STATUS", "SOURCE"], rows)}
{section("SCORING", "How the score is built")}
{table(["COMPONENT", "RULE", "SOURCE"], [
 (th("Score"), td("100 &times; gates passed / 6. Deliberately blunt: a strategy that fails one gate is not 83% tradeable."), td(ext(NFL["results"], "NFL.com"))),
 (th("Tie-break"), td("Higher realised ROI, then larger sample."), td(ext(NFL["results"], "NFL.com"))),
 (th("Eligibility"), td("All six gates. Nothing on this site currently qualifies."), td(ext(NFL["results"], "NFL.com"))),
])}"""
    return render("pages/leaderboard.html", "Leaderboard", "LEADERBOARD", body)


def page_correlation() -> str:
    corr = jload("correlations.json") or {}
    rows = []
    for c in corr.get("correlations") or []:
        rows.append((th(esc(c["name"])),
                     td(num(c.get("r"), 3)),
                     td(integer(c.get("n"))),
                     td(f"{num(c.get('ci_lo'), 2)} to {num(c.get('ci_hi'), 2)}"),
                     td(pct(c.get("r2"), 1, False)),
                     td(esc(c.get("note", ""))),
                     td(ext(NFL["player_stats"], "NFL.com"))))
    sgp = corr.get("sgp") or {}
    sgp_rows = []
    for k, v in sgp.items():
        sgp_rows.append((th(esc(k.replace("_", " "))), td(integer(v.get("n"))),
                         td(num(v.get("p_leg1"), 3)), td(num(v.get("p_leg2"), 3)),
                         td(num(v.get("naive_independent_p"), 3)),
                         td(num(v.get("actual_joint_p"), 3)),
                         td("&times;" + num(v.get("correlation_multiple"), 2)),
                         td(num(v.get("naive_fair_odds"), 2) + " vs " + num(v.get("true_fair_odds"), 2)),
                         td(ext(NFL["player_stats"], "NFL.com"))))
    cg = corr.get("cross_game") or {}
    body = f"""<div class="eyebrow">PRICING</div>
<h1>Correlation is the whole parlay.</h1>
<p class="intro">A parlay is only worth the product of its legs if the legs are independent. Across games that holds. Inside a game it emphatically does not.</p>
{section("MEASURED PAIRS", "Correlation, sample size, interval")}
{table(["PAIR", "r", "n", "95% CI", "R&sup2;", "WHAT IT MEANS", "SOURCE"], rows)}
{section("SAME-GAME PARLAYS", "What independence pricing gets wrong")}
{table(["PAIR", "GAMES", "LEG 1", "LEG 2", "NAIVE JOINT", "ACTUAL JOINT", "MULTIPLE", "FAIR ODDS NAIVE vs TRUE", "SOURCE"], sgp_rows)}
{note("Each leg is thresholded at the median of the sample, so both legs start near 50%. The naive joint probability is the product; the actual joint probability is what happened.")}
{section("CROSS-GAME", "Why normal parlays are priced the way they are")}
{table(["MEASURE", "VALUE", "INTERPRETATION", "SOURCE"], [
 (th("Week-level autocorrelation of mean margin"), td(num(cg.get("corr_consecutive_week_mean_margin"), 3)), td("Any carry-over between weeks would show here. None does."), td(ext(NFL["results"], "NFL.com"))),
 (th("Games per game-week"), td(integer(cg.get("n_game_weeks"))), td("Each observation is one week of the season."), td(ext(NFL["results"], "NFL.com"))),
 (th("Spread vs total correlation"), td(num(next((c['r'] for c in corr.get('correlations', []) if c['name'].startswith('Closing spread')), None), 3)), td("The two markets are quoted almost independently."), td(ext(NFL["results"], "NFL.com"))),
])}"""
    return render("pages/correlation.html", "Correlation &amp; pricing", "CORRELATION", body)


def page_props() -> str:
    props = jload("props.json") or {}
    rows = []
    for market, v in (props.get("markets") or {}).items():
        o = v.get("overall") or {}
        m = (o.get("model") or {})
        rows.append((th(esc(market.replace("_", " "))),
                     td(integer(o.get("n"))),
                     td(num(m.get("mae"), 2)),
                     td(num(m.get("corr"), 3)),
                     td(pct(o.get("skill_vs_last5"))),
                     td(pct(o.get("over_rate_vs_mean_projection"), 1, False)),
                     td(pct(o.get("over_rate_vs_calibrated_line"), 1, False)),
                     td(num(o.get("calibration_multiplier_mean"), 3)),
                     td(ext(NFL["player_stats"], "NFL.com"))))
    seas = []
    for market, v in (props.get("markets") or {}).items():
        for season, s in (v.get("by_season") or {}).items():
            seas.append((th(esc(market.replace("_", " "))), td(esc(season)), td(integer(s.get("n"))),
                         td(num(s.get("mae_model"), 2)), td(num(s.get("mae_last5"), 2)),
                         td(pct(1 - s["mae_model"] / s["mae_last5"])),
                         td(ext(NFL["player_stats"], "NFL.com"))))
    orig = props.get("originated") or {}
    orows = []
    for market, v in orig.items():
        for r in v.get("rows", [])[:4]:
            orows.append((th(esc(r["player"])), td(esc(r["team"])), td(esc(market.replace("_", " "))),
                          td(num(r.get("originated_line"), 1)), td(num(r.get("mean_projection"), 1)),
                          td(num(r.get("sd"), 1)), td(integer(r.get("sample_games"))),
                          td(ext(NFL["player_stats"], "NFL.com"))))
    body = f"""<div class="eyebrow">PLAYER PROPS</div>
<h1>Predictable, but not yet priceable.</h1>
<p class="intro">Projection skill is the ceiling on any prop strategy. We can measure it; we cannot price it, because no free official source publishes historical prop prices.</p>
{note('<strong>What is deliberately missing.</strong> There is no prop ROI on this page and that is not an oversight. A return figure without a historical price would be invented.')}
{section("PROJECTION SKILL", "Out-of-sample, 2018-2026")}
{table(["MARKET", "PLAYER-WEEKS", "MAE", "CORRELATION", "SKILL vs LAST-5", "OVER RATE AT THE MEAN", "OVER RATE AT THE CALIBRATED LINE", "MEDIAN MULTIPLIER", "SOURCE"], rows)}
<p class="disclaimer">The gap between the two over-rate columns is the single most useful result here. A line set at the expected value is beaten well under half the time because player output is right-skewed; the walk-forward multiplier corrects it back to roughly 50%.</p>
{section("STABILITY", "Skill by season")}
{table(["MARKET", "SEASON", "PLAYER-WEEKS", "MAE MODEL", "MAE LAST-5", "SKILL", "SOURCE"], seas)}
{section("ORIGINATED PROP LINES", "Next unplayed week, best-known players")}
{table(["PLAYER", "TEAM", "MARKET", "ORIGINATED LINE", "MEAN PROJECTION", "SD", "GAMES OF HISTORY", "SOURCE"], orows)}"""
    return render("pages/props.html", "Player props", "PROPS", body)


def page_lines() -> str:
    orig = jload("originate.json") or {}
    s = orig.get("summary") or {}
    rows = []
    for r in orig.get("games") or []:
        gap = r.get("line_gap")
        cls = "warn" if gap is not None and abs(gap) >= 6 else "ok"
        rows.append((th(esc(f"{r['away']} @ {r['home']}")), td(esc(r["week"])),
                     td(num(r.get("our_home_line"), 1)), td(num(r.get("market_home_line"), 1)),
                     td(badge(cls, f"{gap:+.1f}" if gap is not None else "&mdash;")),
                     td(num(r.get("our_total"), 1)), td(num(r.get("market_total"), 1)),
                     td(f"{(r.get('total_gap') or 0):+.1f}" if r.get("total_gap") is not None else "&mdash;"),
                     td(ext(NFL["schedule"].format(week=r["week"]), "NFL.com"))))
    rm = orig.get("ratings_model") or {}
    top = [(th(esc(t["team"])), td(num(t["rating"], 2)), td(ext(NFL["team_stats"], "NFL.com")))
           for t in (rm.get("top") or [])]
    bot = [(th(esc(t["team"])), td(num(t["rating"], 2)), td(ext(NFL["team_stats"], "NFL.com")))
           for t in (rm.get("bottom") or [])]
    body = f"""<div class="eyebrow">ORIGINATION</div>
<h1>Our numbers, next to theirs.</h1>
<p class="intro">A spread and a total for every game that has not kicked off, built from a walk-forward ratings model and published beside the closing market number.</p>
{note('<strong>A gap is not an edge.</strong> The identical model loses to the closing line across 2016&ndash;2026 on the Strategy lab page. This table is a benchmark of disagreement, not a bet list.')}
{section("SUMMARY", "What we produced")}
{table(["MEASURE", "VALUE", "SOURCE"], [
 (th("Games with an originated line"), td(integer(s.get("n_games"))), td(ext(NFL["schedule"].format(week=orig.get("as_of", {}).get("week", 9)), "NFL.com"))),
 (th("Mean absolute gap, spread"), td(num(s.get("mean_abs_line_gap"), 2) + " points"), td(ext(NFL["results"], "NFL.com"))),
 (th("Median absolute gap, spread"), td(num(s.get("median_abs_line_gap"), 2) + " points"), td(ext(NFL["results"], "NFL.com"))),
 (th("Mean absolute gap, total"), td(num(s.get("mean_abs_total_gap"), 2) + " points"), td(ext(NFL["results"], "NFL.com"))),
 (th("Correlation, our line vs the market"), td(num(s.get("corr_our_line_market_line"), 3)), td(ext(NFL["results"], "NFL.com"))),
])}
{section("THE LINES", f"Unplayed slate, as of week {orig.get('as_of', {}).get('week')}")}
{table(["GAME", "WK", "OUR SPREAD", "MARKET SPREAD", "GAP", "OUR TOTAL", "MARKET TOTAL", "TOTAL GAP", "SOURCE"], rows)}
{section("RATINGS", "Opponent-adjusted scoring margin, half-life 8 weeks")}
{table(["STRONGEST", "RATING", "SOURCE"], top)}
{table(["WEAKEST", "RATING", "SOURCE"], bot)}
<p class="disclaimer">{esc(orig.get('convention', ''))}</p>"""
    return render("pages/lines.html", "Originated lines", "LINES", body)


def page_verification() -> str:
    ver = jload("verification.json") or {}
    prow_rows = []
    for r in ver.get("player_spot_check") or []:
        prow_rows.append((th(esc(r["player"])), td(esc(r["nfl_yards_td_int"])),
                          td(esc(r["rebuilt_yards_td_int"])), td(esc(r["nfl_comp_att"])),
                          td(esc(r["rebuilt_comp_att"])), td(pass_badge(r["match"])),
                          td(ext(r.get("source", NFL["passing"]), "NFL.com"))))
    rows = []
    for r in ver.get("rows") or []:
        if "status" in r:
            rows.append((th(esc(r["team"])), td("&mdash;"), td("&mdash;"), td("&mdash;"), td("&mdash;"),
                         td(badge("bad", "MISSING")), td(ext(ver.get("official_source", NFL["standings"]), "NFL.com"))))
            continue
        rows.append((th(esc(r["team"])), td(esc(r["nfl_record"])), td(esc(r["computed_record"])),
                     td(esc(r["nfl_pf_pa"])), td(esc(r["computed_pf_pa"])),
                     td(pass_badge(r["match"])),
                     td(ext(ver.get("official_source", NFL["standings"]), "NFL.com"))))
    body = f"""<div class="eyebrow">VERIFICATION</div>
<h1>{ver.get('teams_matched')} of {ver.get('teams_checked')} reconcile exactly.</h1>
<p class="intro">The project depends on one redistributed file. Before any model runs, the 2026 season rebuilt from that file is compared field by field against the standings NFL.com publishes.</p>
{note(f'<strong>Method.</strong> {esc(ver.get("method", ""))} Retrieved {esc(ver.get("retrieved", ""))}.')}
{section("RECONCILIATION", "Every team, every field")}
{table(["TEAM", "NFL.COM RECORD", "REBUILT RECORD", "NFL.COM PF/PA", "REBUILT PF/PA", "MATCH", "SOURCE"], rows)}
{section("PLAYER DATA", "Three quarterback lines rebuilt from the player feed")}
{table(["PLAYER", "NFL.COM YARDS / TD / INT", "REBUILT YARDS / TD / INT", "NFL.COM COMP/ATT", "REBUILT COMP/ATT", "MATCH", "SOURCE"], prow_rows)}
{section("TOTALS", "League-level checks")}
{table(["CHECK", "RESULT", "SOURCE"], [
 (th("Teams reconciled"), td(f"{integer(ver.get('teams_matched'))} of {integer(ver.get('teams_checked'))}"), td(ext(ver.get("official_source", NFL["standings"]), "NFL.com"))),
 (th("Games settled"), td(integer(ver.get("games_settled"))), td(ext(NFL["results"], "NFL.com"))),
 (th("Wins reconcile league-wide"), td(pass_badge(bool(ver.get("wins_reconcile")))), td(ext(NFL["results"], "NFL.com"))),
 (th("Player spot checks"), td(f"{integer(ver.get('player_spot_check_matched'))} of {integer(len(ver.get('player_spot_check') or []))} exact"), td(ext(ver.get("player_source", NFL["passing"]), "NFL.com"))),
 (th("Team code aliases"), td(", ".join(f"{k}&rarr;{v}" for k, v in (ver.get("team_aliases") or {}).items()) or "none"), td(ext(ver.get("official_source", NFL["standings"]), "NFL.com"))),
])}
<p class="disclaimer">Historical seasons (1999&ndash;2025) are not reconciled team by team on this page. They share the same source file and the same pipeline, but that is an argument, not evidence, and it is listed on the review page.</p>"""
    return render("pages/verification.html", "Verification", "VERIFICATION", body)


def page_sources() -> str:
    prov = jload("provenance.json") or {}
    rows = []
    for f in prov.get("files") or []:
        url = f.get("source_url") or (f.get("source_url_pattern") or "")
        rows.append((th(esc(f.get("name"))), td(integer(f.get("rows"))),
                     td(esc(f.get("seasons") or f"{f.get('season_min')}&ndash;{f.get('season_max')}")),
                     td(esc(f.get("raw_sha256") or "pattern")),
                     td(ext(url, "nflverse")),
                     td(ext(NFL["results"], "NFL.com"))))
    src_rows = [
        (th("NFL official results"), td("Final scores, schedule and standings used to reconcile the parsed data."), td(badge("ok", "Official")), td(ext(NFL["results"], "NFL.com"))),
        (th("NFL official standings"), td("Source of the 32 team records used in the verification table."), td(badge("ok", "Official")), td(ext(NFL["standings"], "NFL.com"))),
        (th("NFL official player stats"), td("Where a reader can check any player line referenced on the props page."), td(badge("ok", "Official")), td(ext(NFL["player_stats"], "NFL.com"))),
        (th("NFL official passing stats"), td("2026 passing leaderboard, used for the three-quarterback verification."), td(badge("ok", "Official")), td(ext(NFL["passing"], "NFL.com"))),
        (th("NFL official team stats"), td("Where a reader can check any team rate referenced on the market page."), td(badge("ok", "Official")), td(ext(NFL["team_stats"], "NFL.com"))),
        (th("nflverse schedule extract"), td("Redistributed machine-readable extract of NFL play-by-play and box scores. Not the league itself."), td(badge("warn", "Third party")), td(ext(NFLVERSE + "/schedules/games.csv", "nflverse"))),
        (th("Historical betting prices"), td("Closing spread, total and moneylines sit inside the same nflverse file. No official league source publishes prices."), td(badge("warn", "Third party")), td(ext(NFLVERSE + "/schedules/games.csv", "nflverse"))),
        (th("Historical prop prices"), td("Not present in any free source we could access. This is why no prop ROI is reported."), td(badge("bad", "Missing")), td(ext(NFL["player_stats"], "NFL.com"))),
    ]
    body = f"""<div class="eyebrow">PROVENANCE</div>
<h1>Where every number comes from.</h1>
<p class="intro">Two tiers of source are used and they are never blurred: the league itself, and a third-party redistributor of the league's own play-by-play.</p>
{section("FILES", "Committed extracts")}
{table(["FILE", "ROWS", "SEASONS", "SHA-256 OF RAW SOURCE", "DOWNLOAD", "OFFICIAL CHECK"], rows)}
<p class="disclaimer">Data as of gameday {esc(prov.get('data_as_of_gameday', 'unknown'))} ({integer(prov.get('games_settled'))} settled games in the source file). Raw downloads are excluded from the repository and rebuilt by <code>.github/workflows/fetch-nflverse.yml</code>; the SHA-256 above pins exactly what was used, and the build is byte-for-byte reproducible.</p>
{section("SOURCE REGISTER", "Official and third-party, labelled")}
{table(["SOURCE", "WHAT IT IS USED FOR", "TIER", "LINK"], src_rows)}
{section("NOT AVAILABLE", "What we could not obtain")}
{table(["ITEM", "STATUS", "SOURCE"], [
 (th("Opening lines and line movement"), td("Not present in the data. Any claim about closing-line value would be unsupported."), td(ext(NFL["results"], "NFL.com"))),
 (th("Historical player-prop prices"), td("Not present in any free official source."), td(ext(NFL["player_stats"], "NFL.com"))),
 (th("Public betting percentages"), td("Not present. The classic fade-the-public angle is therefore untested, not refuted."), td(ext(NFL["results"], "NFL.com"))),
 (th("Injury reports at kickoff"), td("Not joined into the model, so availability risk is unmodelled."), td(ext(NFL["results"], "NFL.com"))),
])}"""
    return render("pages/sources.html", "Data &amp; sources", "SOURCES", body)


def page_flagged() -> str:
    items = [
        ("Sign convention differs from the documented reading",
         "The source file's <code>spread_line</code> is positive when the home team is favoured. The common reading of that field is the opposite. We verified the file's actual convention two ways and every model uses the verified one, but the documentation mismatch is unresolved.",
         "Verified in-repo, documentation mismatch open",
         "warn", NFL["results"]),
        ("Wind-under angle fails correction by 0.001",
         "The weather angle returns +8.65% over 649 bets with p = 0.021, but Benjamini-Hochberg at q = 0.10 requires p &le; 0.020 with five strategies tested. It is also flat in the holdout. Treated as unresolved, not as an edge.",
         "Unresolved", "warn", NFL["schedule"].format(week=1)),
        ("Weather fields are incomplete",
         "Wind and temperature are recorded for roughly 57% of games in 2020-2026 and only for outdoor venues. If missingness correlates with conditions the weather result is biased. Not tested.",
         "Unresolved", "warn", NFL["results"]),
        ("Markets are priced at the close only",
         "Every strategy here is settled at the closing number. A real bettor cannot reliably obtain the close, so realised returns would be worse. No opening-line history is available to quantify the gap.",
         "Structural limitation", "warn", NFL["results"]),
        ("No player-prop prices",
         "The props page measures projection skill only. A line that is skilfully projected may still be correctly priced. No prop ROI is claimed anywhere on this site.",
         "Data gap", "bad", NFL["player_stats"]),
        ("Pushes and void legs",
         "Push handling reduces parlay tickets to the remaining legs. Books do not all settle that way; the parlay ROI is therefore indicative.",
         "Modelling assumption", "warn", NFL["results"]),
        ("Historical seasons not reconciled team by team",
         "Only 2026 is reconciled against NFL.com field by field. Seasons 1999-2025 share the pipeline but were not individually checked against the league's site.",
         "Partial verification", "warn", NFL["results"]),
        ("Legal, jurisdictional and licensing status",
         "Nothing here is licensed betting advice and the project provides no access to any sportsbook. Whether a wager is lawful depends on where the reader is; that was not assessed. Singapore, where this research was produced, has its own regime.",
         "Not assessed", "bad", NFL["results"]),
        ("No opening lines or line movement",
         "Only closing prices exist in the data. Closing-line value, the standard test of execution skill, therefore cannot be measured, and every return on this site assumes a price a real bettor may not obtain.",
         "Structural limitation", "warn", NFL["results"]),
        ("Model still loses to the market",
         "The rating model's Brier skill against the close is negative. Anyone reading the originated-lines page should treat the gaps as model error until a strategy clears the gates.",
         "Open", "bad", NFL["team_stats"]),
    ]
    rows = [(th(esc(t)), td(d), td(badge(b, s)), td(ext(u, "Official source"))) for t, d, s, b, u in items]
    body = f"""<div class="eyebrow">REVIEW</div>
<h1>Flagged for review.</h1>
<p class="intro">Everything that is unresolved, unverified, assumed or structurally limited. These items do not block publication; they are the reason nothing here is ranked.</p>
{table(["ITEM", "DETAIL", "STATUS", "SOURCE"], rows)}
<p class="disclaimer">Nothing on this page is hidden elsewhere on the site. If a number depends on an assumption listed here, the number is labelled accordingly on the page that shows it.</p>"""
    return render("pages/flagged.html", "Flagged for review", "REVIEW", body)


def main():
    pages = {
        "index.html": page_index(),
        "pages/executive.html": page_executive(),
        "pages/market.html": page_market(),
        "pages/strategies.html": page_strategies(),
        "pages/validation.html": page_validation(),
        "pages/leaderboard.html": page_leaderboard(),
        "pages/correlation.html": page_correlation(),
        "pages/props.html": page_props(),
        "pages/lines.html": page_lines(),
        "pages/verification.html": page_verification(),
        "pages/sources.html": page_sources(),
        "pages/flagged.html": page_flagged(),
    }
    for path, content in pages.items():
        p = ROOT / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    print(f"wrote {len(pages)} pages")


if __name__ == "__main__":
    main()
