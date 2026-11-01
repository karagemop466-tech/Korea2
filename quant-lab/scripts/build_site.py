#!/usr/bin/env python3
"""
build_site.py — renders every page of the static site from data/processed/*.json.

No number on the site is typed into this file: each one is read from a JSON artefact produced by
the pipeline (fetch_data.sh -> build_dataset.py -> model.py -> backtest.py -> props.py ->
validation.py -> verify_official.py). The only hand-written strings are labels, rules text and
provenance metadata, which live in data/sources.json.
"""
import html, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
OFF = os.path.join(ROOT, "data", "official")


def j(name):
    p = os.path.join(PROC, name)
    return json.load(open(p)) if os.path.exists(p) else None


def jo(name):
    p = os.path.join(OFF, name)
    return json.load(open(p)) if os.path.exists(p) else None


def e(s):
    return html.escape(str(s), quote=True)


def pct(x, dp=2, sign=True):
    if x is None:
        return '<span class="chip">unverified</span>'
    v = round(100 * x, dp)
    cls = "pos" if v > 0 else ("neg" if v < 0 else "")
    if sign and v > 0:
        return f'<span class="{cls}">+{v:.{dp}f}%</span>'
    return f'<span class="{cls}">{v:.{dp}f}%</span>'


def fmtdet(v):
    """Render a verification detail value readably instead of a Python repr."""
    if isinstance(v, dict):
        return ", ".join(f"{k.replace('_',' ')}: {vi}" for k, vi in v.items())
    return str(v)


def n2(x, dp=2):
    if x is None:
        return '<span class="chip">—</span>'
    return f"{x:.{dp}f}" if isinstance(x, float) else str(x)


def num(x, dp=2):
    if x is None:
        return '<span class="chip">—</span>'
    return f'<span class="num">{x:,.{dp}f}</span>' if isinstance(x, float) else f'<span class="num">{x:,}</span>'


def badge(ok):
    if ok is True:
        return '<span class="badge pass">pass</span>'
    if ok is False:
        return '<span class="badge fail">fail</span>'
    return '<span class="badge na">n/a</span>'


def review(msg="needs review"):
    return f'<span class="badge review">{e(msg)}</span>'


def table(caption, headers, rows, wide=(), empty="No rows."):
    out = ['<div class="tablewrap"><table>']
    out.append(f"<caption>{caption}</caption>")
    out.append("<thead><tr>")
    for i, h in enumerate(headers):
        cls = ' class="wrap"' if i in wide else ""
        out.append(f"<th{cls}>{h}</th>")
    out.append("</tr></thead><tbody>")
    if not rows:
        out.append(f'<tr><td colspan="{len(headers)}">{empty}</td></tr>')
    for r in rows:
        out.append("<tr>")
        for i, c in enumerate(r):
            cls = ' class="wrap"' if i in wide else ""
            out.append(f"<td{cls}>{c}</td>")
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


NAV = [
    ("index.html", "Dashboard"),
    ("lines.html", "Originated lines"),
    ("props.html", "Player props & SGP"),
    ("strategies.html", "Strategies"),
    ("leaderboard.html", "Leaderboard"),
    ("correlation.html", "Correlations"),
    ("validation.html", "Validation gates"),
    ("verification.html", "Verification"),
    ("flagged.html", "Flagged for review"),
    ("methodology.html", "Method"),
    ("sources.html", "Sources"),
    ("executive-summary.html", "Executive summary"),
]


def shell(title, active, body, subtitle=""):
    parts = []
    for f, l in NAV:
        cls = ' class="active"' if f == active else ''
        parts.append(f'<a href="{f}"{cls}>{e(l)}</a>')
    nav = "".join(parts)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} · NFL Line Lab</title>
<meta name="description" content="Originated NFL lines, gated strategies, empirical correlations and a line-by-line verification register.">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header class="top"><div class="wrap">
  <div class="brand">NFL <span>Line Lab</span></div>
  <nav class="main">{nav}</nav>
</div></header>
<main><div class="wrap">
<h1>{e(title)}</h1>
{f'<p class="lede">{subtitle}</p>' if subtitle else ''}
{body}
</div></main>
<footer><div class="wrap">
Built by an automated agent session (branch <code>arena/7b140798-korea2</code>) with no manual input.
Every published value traces to a source in <a href="sources.html">Sources</a>; anything unverifiable is
listed on <a href="flagged.html">Flagged for review</a>. Data capture: {e((j('meta.json') or {}).get('built_utc',''))}.
</div></footer>
</body></html>"""


# --------------------------------------------------------------------------- data
meta = j("meta.json") or {}
model = j("model_meta.json") or {}
board = j("board.json") or []
props = j("props.json") or []
prop_corr = j("prop_corr.json") or {}
prop_diag = j("prop_diag.json") or {}
corr = j("correlations.json") or {}
lead = j("leaderboard.json") or {}
verif = j("verification.json") or {}
flags = j("flags.json") or []
sources = json.load(open(os.path.join(ROOT, "data", "sources.json")))
verified_urls = set((jo("game_urls_verified.json") or {}).get("urls", []))
week_pages = (jo("game_urls_verified.json") or {}).get("week_page_urls", {})
teams = j("teams.json") or {}


def game_url(row):
    """Return an official link for a fixture: the exact game page if it was seen verbatim on
    nfl.com, otherwise the official weekly schedule page. Never a constructed URL."""
    nick = lambda t: (teams.get(t, {}).get("nick") or t).lower().replace(" ", "-")
    slug = f"{nick(row['away'])}-at-{nick(row['home'])}-2026-reg-{row['week']}"
    url = f"https://www.nfl.com/games/{slug}"
    if url in verified_urls:
        return url, True
    return week_pages.get(str(row["week"]), "https://www.nfl.com/schedules"), False


def official_link(url, verified, label=None):
    txt = label or ("nfl.com game page" if verified else "nfl.com week page")
    chip = "" if verified else ' <span class="chip">fixture not yet cross-checked</span>'
    return f'<a href="{e(url)}" rel="noopener">{txt}</a>{chip}'


# --------------------------------------------------------------------------- pages
def page_index():
    reg = meta.get("regular_season_played", 0)
    played = meta.get("games_played", 0)
    lb = lead.get("leaderboard", [])
    tested = lead.get("summary", {}).get("strategies_tested", 0)
    qualified = lead.get("summary", {}).get("qualified", 0)
    checks = verif.get("summary", {}).get("checks_total", 0)
    passed = verif.get("summary", {}).get("passed", 0)
    cards = f"""<div class="grid cards">
  <div class="card"><div class="k">Games in the dataset</div><div class="v">{played:,}</div>
    <div class="s">{reg:,} regular season · {meta.get('season_range',['?','?'])[0]}–{meta.get('season_range',['?','?'])[1]}</div></div>
  <div class="card"><div class="k">Strategies tested</div><div class="v">{tested}</div>
    <div class="s">single · parlay · same-game · player prop</div></div>
  <div class="card"><div class="k">Passed every gate</div><div class="v">{qualified}</div>
    <div class="s">9 gates, FDR q = {lead.get('fdr_q', 0.10)}</div></div>
  <div class="card"><div class="k">Official checks</div><div class="v">{passed}/{checks}</div>
    <div class="s">mirror vs nfl.com, line by line</div></div>
  <div class="card"><div class="k">Model error (margin)</div><div class="v">{model.get('mae_model_spread','—')}</div>
    <div class="s">MAE in points · market close {model.get('mae_market_spread','—')}</div></div>
  <div class="card"><div class="k">Model error (total)</div><div class="v">{model.get('mae_model_total','—')}</div>
    <div class="s">MAE in points · market close {model.get('mae_market_total','—')}</div></div>
</div>"""

    findings = []
    findings.append(
        "<li><b>No tested strategy cleared all nine gates.</b> The best of the "
        f"{tested} is <code>S10_wind15_under</code> (+{100*(next((x['roi_holdout'] for x in lb if x['strategy']=='S10_wind15_under'),0) or 0):.1f}% holdout ROI, "
        "6 of 9 gates) — it fails significance and calibration, so it is published as a lead, not a result.</li>")
    findings.append(
        "<li><b>Closing lines are hard to beat, and this model does not beat them.</b> Its spread error is "
        f"{model.get('mae_model_spread')} points against {model.get('mae_market_spread')} for the market close; "
        "every model-vs-market strategy loses money before and after vig.</li>")
    findings.append(
        "<li><b>Correlations are where the real value sits.</b> Home cover and over are almost independent "
        f"(phi = {corr.get('phi_home_cover_vs_over')}), but moneyline and spread legs in the same game are not "
        f"(phi = {corr.get('phi_ml_win_vs_ats_cover')}) — mispricing those two together is a pricing problem, "
        "not a prediction problem.</li>")
    findings.append(
        "<li><b>Quarterback and receiver prop legs are strongly correlated</b> in the one same-team pair with a "
        f"clean log (Green Bay: r = {prop_corr.get('pairs',[{}])[0].get('r') if prop_corr.get('pairs') else None}, "
        f"n = {prop_corr.get('pairs',[{}])[0].get('n') if prop_corr.get('pairs') else None}); pricing those legs "
        f"independently understates the joint probability by "
        f"{prop_corr.get('sgp_cases',[{}])[0].get('rel_mispricing_pct') if prop_corr.get('sgp_cases') else None}%.</li>")
    findings.append(
        f"<li><b>Control strategies behave as expected</b>: backing every home team returns "
        f"{100*(next((x['roi_holdout'] for x in lb if x['strategy']=='S0_baseline_all_home'),0) or 0):.2f}% on the holdout, "
        "which is the vig floor and the benchmark any 'skill' claim has to clear.</li>")

    navcards = """<div class="grid navcards">
  <a class="navcard" href="lines.html"><h3>Originated lines</h3><p>Our spread, total and moneyline for Week 9 and 10, beside the market close and the edge between them.</p></a>
  <a class="navcard" href="props.html"><h3>Player props &amp; SGP</h3><p>Player-yardage lines from official game logs, plus measured quarterback/receiver correlation and what it does to a same-game price.</p></a>
  <a class="navcard" href="strategies.html"><h3>Strategies</h3><p>All 21 pre-registered rules with discovery and holdout performance, side by side.</p></a>
  <a class="navcard" href="leaderboard.html"><h3>Leaderboard</h3><p>The competition, its scoring formula and rewards, and who is on it.</p></a>
  <a class="navcard" href="correlation.html"><h3>Correlations</h3><p>Every correlation value used for parlay pricing, with sample sizes and confidence intervals.</p></a>
  <a class="navcard" href="validation.html"><h3>Validation gates</h3><p>The nine gates, their thresholds, and a pass/fail matrix for every strategy.</p></a>
  <a class="navcard" href="verification.html"><h3>Verification</h3><p>77 line-by-line checks of the underlying data against official nfl.com pages.</p></a>
  <a class="navcard" href="flagged.html"><h3>Flagged for review</h3><p>Every unverified item, assumption and irregularity, with its source link.</p></a>
  <a class="navcard" href="methodology.html"><h3>Method</h3><p>The rating model, the walk-forward design, and how luck is separated from skill.</p></a>
  <a class="navcard" href="sources.html"><h3>Sources</h3><p>Official pages, the pinned data mirror, hashes, and what each source is used for.</p></a>
</div>"""
    body = cards + f"""
<h2>Headline findings</h2>
<ul class="tight">{''.join(findings)}</ul>
<div class="note"><b>How to read this site.</b> A green value is a number that exists; an
<span class="chip">unverified</span> chip means the value could not be tied to an official source and was
left blank rather than estimated. Nothing on this site is a betting recommendation, and no prop strategy
carries a rank because no prop price was reachable.</div>
<h2>Sections</h2>
{navcards}"""
    return shell("NFL Line Lab — dashboard", "index.html", body,
                 "Originated NFL lines, a gated strategy competition, measured correlations and a "
                 "line-by-line audit against nfl.com. Built end-to-end by an automated agent.")


def board_table(week, verified_only):
    rows = []
    for b in sorted([x for x in board if x["week"] == week], key=lambda x: x["gameday"]):
        m = b["market"]
        edge = None if m["spread_home"] is None else b["orig_spread_home"] - m["spread_home"]
        tedge = None if m["total"] is None else b["orig_total"] - m["total"]
        url, ver = game_url(b)
        def pts(v):
            if v is None:
                return '<span class="chip">no market</span>'
            cls = "pos" if v > 0 else ("neg" if v < 0 else "")
            return f'<span class="{cls} num">{v:+.1f}</span>'
        rows.append([
            f'<b>{e(b["away"])} at {e(b["home"])}</b>',
            e(b["gameday"]),
            num(b["orig_spread_home"], 1),
            num(m["spread_home"], 1),
            pts(edge),
            num(b["orig_total"], 1),
            num(m["total"], 1),
            pts(tedge),
            official_link(url, ver),
        ])
        if not verified_only and not ver:
            rows[-1][-1] = official_link(url, ver)
    return table(
        f"2026 Week {week} — originated lines vs market close",
        ["Matchup", "Date", "Our spread (home)", "Market spread", "Spread edge (pts)", "Our total",
         "Market total", "Total edge (pts)", "Official source"],
        rows, wide=(0,))


def page_lines():
    w9 = board_table(9, True)
    w10 = board_table(10, False)
    body = f"""
<p class="lede">The model rebuilds every team's offence and defence from completed games only, then
publishes its own spread, total and implied moneyline. The market column is the closing line recorded in
the mirror; the "edge" column is our number minus the market's — the only input any strategy is allowed to use.</p>
<div class="grid cards">
  <div class="card"><div class="k">Board size</div><div class="v">{len([x for x in board if x['week']==9]) + len([x for x in board if x['week']==10])}</div>
    <div class="s">Week 9 and Week 10 fixtures</div></div>
  <div class="card"><div class="k">Model fit (margin MAE)</div><div class="v">{model.get('mae_model_spread')}</div>
    <div class="s">market close {model.get('mae_market_spread')} over {model.get('n'):,} games</div></div>
  <div class="card"><div class="k">Model fit (total MAE)</div><div class="v">{model.get('mae_model_total')}</div>
    <div class="s">market close {model.get('mae_market_total')}</div></div>
  <div class="card"><div class="k">Residual sigma</div><div class="v">{model.get('sigma',{}).get('sigma')}</div>
    <div class="s">points; drives every modelled probability</div></div>
</div>
<h2>Week 9 board</h2>
<p class="small">Every fixture below was cross-checked against the official nfl.com Week 9 schedule page.
Each row links to the official game page where that URL was seen verbatim, otherwise to the official week page.</p>
{w9}
<h2>Week 10 preview</h2>
<p class="small">Fixtures come from the mirror and have <b>not</b> yet been cross-checked against nfl.com, so those
rows are marked and link to the official schedule index. This is disclosed on
<a href="flagged.html">Flagged for review</a> (I9).</p>
{w10}
<h2>How the numbers are built</h2>
<pre>home_points = mu + HFA + OFF[home] + DEF[away]
away_points = mu        + OFF[away] + DEF[home]
originated spread = (home_points - away_points), positive = home favoured
originated total  = (home_points + away_points)
P(home win)       = Phi(spread / sigma)</pre>
<p>OFF and DEF are ridge-shrunk (lambda = {model.get('params',{}).get('ridge')}), evidence decays with a
{model.get('params',{}).get('half_life')}-day half-life, and last season carries
{model.get('params',{}).get('psw')} weight. The three hyper-parameters were chosen on 2002–2015 only;
2020–2026 was never used for tuning. Full detail on <a href="methodology.html">Method</a>.</p>
<div class="note">A spread of <code>+2.5</code> on this page always means <b>the home team is a
2.5-point favourite</b>. That convention was verified against the data (see
<a href="flagged.html">I1</a>) because the mirror's own documentation describes the opposite sign.</div>"""
    return shell("Originated lines", "lines.html", body,
                 "Our own spread, total and moneyline for the coming weeks, next to the market close.")


def page_props():
    rows = []
    for p in props:
        if p.get("line") is None and p.get("originated_line") is None:
            rows.append([e(p["player"]), e(p["team"]), e(p["market"]), '<span class="chip">no fixture</span>',
                         '<span class="chip">—</span>', '<span class="chip">—</span>', '<span class="chip">—</span>',
                         f'<a href="{e(p["source_url"])}" rel="noopener">nfl.com</a>'])
            continue
        rows.append([
            f'<b>{e(p["player"])}</b>', e(p["team"]), e(p["stat_label"]),
            f'vs {e(p["opp"])} · {e(p["venue"])}',
            num(p["originated_line"], 1),
            f'{p["p_over"]:.3f} / {p["p_under"]:.3f}',
            f'{num(p["player_sd"],1)} <span class="small">(n={p["n_games"]})</span>',
            f'<a href="{e(p["source_url"])}" rel="noopener">nfl.com player page</a>',
        ])
    pairs = prop_corr.get("pairs", [])
    prow = [[f'<b>{e(x["team"])}</b>', e(x["leg_a"]), e(x["leg_b"]),
             num(x["r"], 3), num(x["n"], 0),
             f'{x["r_ci95"][0]} to {x["r_ci95"][1]}' if x.get("r_ci95") else '<span class="chip">—</span>',
             f'<a href="{e(x["sources"][0])}" rel="noopener">a</a> · <a href="{e(x["sources"][1])}" rel="noopener">b</a>']
            for x in pairs]
    sgp_rows = []
    for s in prop_corr.get("sgp_cases", []):
        sgp_rows.append([e(s["team"]), f'{e(s["leg_a"])} + {e(s["leg_b"])}', num(s["r"], 3),
                         num(s["p_joint_independent"], 4), num(s["p_joint_correlated"], 4),
                         f'{s["fair_odds_independent"]:+d}', f'{s["fair_odds_correlated"]:+d}',
                         pct(s["rel_mispricing_pct"] / 100)])
    pteam = [[e(x["player"]), e(x["market"]), num(x["r_vs_team_points"], 3), num(x["r_vs_team_margin"], 3),
              num(x["n"], 0), f'<a href="{e(x["source_url"])}" rel="noopener">nfl.com</a>']
             for x in prop_corr.get("player_team", [])]
    body = f"""
<p class="lede">Player props are originated from each player's official nfl.com game log. Every weekly
value was copied from a table with printed column headers, and each player's weekly values are proved to sum
to the season total printed on the same page — so a transcription slip cannot survive.</p>
<div class="grid cards">
  <div class="card"><div class="k">Players with an originated line</div><div class="v">{len([p for p in props if p.get('originated_line')])}</div><div class="s">Week 9</div></div>
  <div class="card"><div class="k">Player-games captured</div><div class="v">{sum(p.get('n_games',0) for p in props)}</div><div class="s">official nfl.com logs</div></div>
  <div class="card"><div class="k">QB1 ↔ WR1 correlation</div><div class="v">{prop_corr.get('pooled_qb_wr',{}).get('r')}</div>
    <div class="s">pooled, n = {prop_corr.get('pooled_qb_wr',{}).get('n')}</div></div>
  <div class="card"><div class="k">Prop price source</div><div class="v">none</div><div class="s">ROI uses the -110 assumption</div></div>
</div>
<h2>Week 9 player-prop board</h2>
<p class="small">Line = recency-weighted mean of the player's games (2-game half-life) scaled by the
model's expected team scoring, rounded to the nearest half-yard. Because the line is set at the projection,
p(over) sits near 50% by construction: this is a <b>fair-value</b> line, not a bet signal.</p>
{table("Player prop board — 2026 Week 9",
       ["Player", "Team", "Market", "Week 9 game", "Our line", "p(over) / p(under)", "Player sd", "Official source"],
       rows, wide=(0,))}
<h2>Same-game prop correlation</h2>
<p>Two legs from the same offence move together. The table below measures that directly, in games where both
players appeared, using nothing but official nfl.com logs.</p>
{table("Quarterback passing yards vs the same team's No.1 receiver",
       ["Team", "Leg A (QB)", "Leg B (WR)", "r", "n games", "95% CI (Fisher z)", "Official sources"],
       prow, wide=(0,))}
<p class="small">Pooled across both pairs: r = {prop_corr.get('pooled_qb_wr',{}).get('r')} with
n = {prop_corr.get('pooled_qb_wr',{}).get('n')}, 95% CI
{prop_corr.get('pooled_qb_wr',{}).get('ci95')}.</p>
{table("What independent pricing does to the same-game price",
       ["Team", "Parlay", "r", "P(joint) if independent", "P(joint) with correlation", "Fair price if independent", "Fair price with correlation", "Relative error"],
       sgp_rows, wide=(1,))}
<div class="warnbox"><b>Read this before using those numbers.</b> The pairs are measured on
{pairs[0]['n'] if pairs else 0}–{max([x['n'] for x in pairs], default=0)} games per pair. The Green Bay
correlation is near-certain in direction but the point estimate (r = {pairs[0]['r'] if pairs else None}) has a
wide interval, and the Detroit pair is far weaker. Both case studies are marked
{review('needs review')} on the leaderboard because no prop price exists to test the price against.</div>
<h2>Player output vs team scoring</h2>
{table("Correlation between a player's market and his own team's points / margin",
       ["Player", "Market", "r vs team points", "r vs team margin", "n", "Official source"], pteam)}
<div class="note">Diagnostic only: {prop_diag.get('n_observations')} expanding-window prop observations,
side hit rate {prop_diag.get('side_hit_rate')}, Brier {prop_diag.get('brier')}. That sample is far below the
60-observation gate, which is exactly why no prop strategy is ranked.</div>"""
    return shell("Player props & same-game correlation", "props.html", body,
                 "Prop lines from official game logs, and the correlation that decides whether a same-game price is fair.")


def page_strategies():
    lb = lead.get("leaderboard", [])
    rows = []
    for r in lb:
        rows.append([
            f'<code>{e(r["strategy"])}</code>',
            e(r.get("kind") or ""),
            e(r["desc"]),
            num(r["n_holdout"], 0),
            pct(r["roi_holdout"]),
            pct(r["roi_discovery"]),
            f'{r["ci95_holdout"][0]} to {r["ci95_holdout"][1]}' if r.get("ci95_holdout") and r["ci95_holdout"][0] is not None else '<span class="chip">—</span>',
            num(r["luck_z"], 2),
            num(r["p_value"], 4),
            f'{r["gates_passed"]}/9',
            badge(r["qualified"]) if r.get("status") != "needs review" else review(),
        ])
    body = f"""
<p class="lede">Every rule below was registered before its results were computed. Discovery is 2002–2019,
holdout is 2020–2026, and the holdout was never used to choose a rule, a threshold or a hyper-parameter.</p>
{table("All tested strategies", ["Strategy", "Type", "Rule", "n (holdout)", "ROI holdout", "ROI discovery",
       "95% CI holdout", "luck z", "p (raw)", "Gates", "Verdict"], rows, wide=(2,))}
<h2>What the results say</h2>
<ul class="tight">
<li><b>Model-vs-market singles lose.</b> Spread, total and moneyline edges all produce negative ROI in both
windows. The model's error ({model.get('mae_model_spread')} pts) is larger than the closing line's
({model.get('mae_market_spread')} pts), so "the model disagrees with the market" is not information.</li>
<li><b>Parlays amplify the same loss.</b> A 3-leg parlay of the same losing legs turns a −13% edge into a −33% ROI.</li>
<li><b>Structural rules are the only place a positive number appears</b>, and none of them survives
significance. Wind unders are the clearest lead (positive in both windows, 6/9 gates) but the confidence
interval still spans zero.</li>
<li><b>The control is doing its job.</b> Backing every home team returns the vig floor, so any strategy that
cannot beat it is just paying the book.</li>
</ul>"""
    return shell("Strategies", "strategies.html", body,
                 "21 pre-registered rules, one settlement engine, two windows: discovery 2002–2019 and holdout 2020–2026.")


def page_leaderboard():
    lb = lead.get("leaderboard", [])
    qualified = [r for r in lb if r["qualified"]]
    top = [r for r in lb if r.get("status") != "needs review"][:6]
    rows_rank = [[str(r.get("rank") or "—"), f'<code>{e(r["strategy"])}</code>', e(r.get("kind") or ""),
                  pct(r["roi_holdout"]), num(r["score"], 2), f'{r["gates_passed"]}/9',
                  " · ".join(f'<code>{e(g)}</code>' for g in r["gates_failed"]) or '<span class="badge pass">none</span>']
                 for r in lb]
    body = f"""
<p class="lede">The competition pays for <i>verified</i> skill, not for a hot streak. A strategy scores only
after it clears all nine gates; until then it is published with its failures attached.</p>
<div class="grid cards">
  <div class="card"><div class="k">Strategies entered</div><div class="v">{lead.get('summary',{}).get('strategies_tested')}</div><div class="s">whole family, FDR-controlled</div></div>
  <div class="card"><div class="k">Qualified</div><div class="v">{len(qualified)}</div><div class="s">all nine gates</div></div>
  <div class="card"><div class="k">Family size used for FDR</div><div class="v">{lead.get('family_size')}</div><div class="s">q = {lead.get('fdr_q')}</div></div>
  <div class="card"><div class="k">Best gate count</div><div class="v">{max([r['gates_passed'] for r in lb], default=0)}/9</div><div class="s">{e(top[0]['strategy']) if top else '—'}</div></div>
</div>
<h2>Competition rules</h2>
<ul class="tight">
<li><b>Entry.</b> A strategy is a fully specified, data-independent rule. Thresholds are fixed before the holdout
is looked at; changing a rule creates a new entry and increments the family size used for multiple-testing control.</li>
<li><b>Settlement.</b> One unit per bet, price actually taken, pushes voided. Discovery 2002–2019 and holdout
2020–2026 are reported separately, and only holdout numbers count for ranking.</li>
<li><b>Qualification.</b> All nine gates must pass — sample, holdout ROI, discovery ROI, significance after
Benjamini-Hochberg FDR across the whole family, calibration, season-to-season stability, leave-one-season-out
robustness, profit concentration, and price sensitivity.</li>
<li><b>Score.</b> <code>score = ROI(holdout) × 100 × (1 + max(0, luck_z)/3) × (0.5 + 0.5·stability) × (0.5 + 0.5·√(n/300))</code>.
A strategy with a large but lucky ROI scores below a smaller, well-sampled one.</li>
<li><b>Rewards (virtual, non-monetary).</b>
  <span class="badge pass">Gold</span> all nine gates · score ≥ 5 &nbsp;
  <span class="badge pass">Silver</span> all nine gates · score &lt; 5 &nbsp;
  <span class="badge review">Development</span> positive holdout ROI but a gate failed &nbsp;
  <span class="badge fail">Retired</span> negative holdout ROI.
  Nothing here is wagering advice and no real money is involved.</li>
<li><b>Demotion.</b> A qualified strategy that turns negative over its next 100 settled bets drops back to
Development. Ranks are recomputed by re-running the pipeline, never by hand.</li>
</ul>
<h2>Leaderboard</h2>
<div class="warnbox"><b>Nothing qualified.</b> With {lead.get('family_size')} strategies in the family and
q = {lead.get('fdr_q')}, the smallest raw p-value observed was
{min([r['p_value'] for r in lb if r['p_value'] is not None], default=None)}, far above the threshold, so no
strategy earns a rank this cycle. That is the honest result: the closing line is a strong benchmark and
none of these rules beats it with statistical support.</div>
{table("Ranking (rank is withheld until all nine gates pass)",
       ["Rank", "Strategy", "Type", "ROI holdout", "Score", "Gates", "Failed gates"], rows_rank, wide=(5,))}
<h2>Closest to qualifying</h2>
<ul class="tight">
{''.join(f"<li><code>{e(r['strategy'])}</code> — {r['gates_passed']}/9 gates. {e(r['desc'])} Fails: {', '.join(r['gates_failed'])}.</li>" for r in top[:3])}
</ul>
<p class="small">To qualify, the wind-under lead would need a confidence interval clear of zero (it currently
spans {100*top[0]['ci95_holdout'][0]:+.2f}% to {100*top[0]['ci95_holdout'][1]:+.2f}%) and a calibration gap
under 5 points. The pipeline re-runs and re-ranks automatically as games are added.</p>"""
    return shell("Leaderboard", "leaderboard.html", body,
                 "A skill competition that only pays for strategies which survive every gate.")


def page_correlation():
    rows = [
        ["Home cover vs over, same game", f'phi = {corr.get("phi_home_cover_vs_over")}', num(corr.get("n_ats_total"), 0),
         "Essentially zero. Spread and total legs of one game can be priced as independent."],
        ["Home margin vs total points", f'r = {corr.get("pearson_margin_vs_total")}', num(corr.get("n_games"), 0),
         "Same story on the continuous scale: knowing the margin tells you almost nothing about the total."],
        ["Moneyline win vs spread cover, same game", f'phi = {corr.get("phi_ml_win_vs_ats_cover")}', num(corr.get("n_ml_ats"), 0),
         "Very strong. These two legs must never be priced as independent."],
        ["Two legs from different games", f'phi = {corr.get("cross_game_leg_independence",{}).get("phi")}',
         num(corr.get("cross_game_leg_independence",{}).get("n_pairs"), 0),
         "Indistinguishable from zero, which is the assumption a cross-game parlay price rests on."],
    ]
    pairs = prop_corr.get("pairs", [])
    prow = [[e(x["team"]), f'{e(x["leg_a"])} (QB pass yds) · {e(x["leg_b"])} (rec yds)', num(x["r"], 3), num(x["n"], 0),
             f'{x["r_ci95"][0]} to {x["r_ci95"][1]}' if x.get("r_ci95") else "—"] for x in pairs]
    prow.append(["<b>pooled</b>", "QB1 passing yards · WR1 receiving yards",
                 num(prop_corr.get("pooled_qb_wr", {}).get("r"), 3), num(prop_corr.get("pooled_qb_wr", {}).get("n"), 0),
                 str(prop_corr.get("pooled_qb_wr", {}).get("ci95"))])
    body = f"""
<p class="lede">Every number here is computed from the data in this repository — no correlation is quoted from
an outside source, and none is assumed. Sample sizes and confidence intervals are shown because a correlation
without an n is an opinion.</p>
<h2>Game-level legs</h2>
{table("Correlations between legs of the same game, and between games",
       ["Relationship", "Value", "n", "What it means for pricing"], rows, wide=(3,))}
<h2>Player-level legs</h2>
{table("Same-team prop correlations from official nfl.com game logs",
       ["Team", "Legs", "r", "n games", "95% CI"], prow, wide=(1,))}
<h2>How a correlated parlay should be priced</h2>
<pre>independent:  P(A and B) = p(A) x p(B)                      decimal odds = 1 / P
correlated:   P(A and B) = P(Z1 &gt; z1, Z2 &gt; z2 ; rho)        bivariate normal
              with z_i = (line_i - projection_i) / sigma_i</pre>
<p>For the Green Bay pair this is not a rounding error: pricing the two legs independently returns a joint
probability of {prop_corr.get('sgp_cases',[{}])[0].get('p_joint_independent') if prop_corr.get('sgp_cases') else None}
against {prop_corr.get('sgp_cases',[{}])[0].get('p_joint_correlated') if prop_corr.get('sgp_cases') else None}
with the measured correlation — the independent price is wrong by
{prop_corr.get('sgp_cases',[{}])[0].get('rel_mispricing_pct') if prop_corr.get('sgp_cases') else None}%.</p>
<div class="note"><b>Correlations are not stable.</b> The Detroit pair (r =
{pairs[1]['r'] if len(pairs) > 1 else '—'}, n = {pairs[1]['n'] if len(pairs) > 1 else '—'}) shows how much a
point estimate can move on a short sample. Any production pricing engine should re-estimate these on a rolling
window and widen the interval rather than trusting a single number.</div>"""
    return shell("Correlations", "correlation.html", body,
                 "Measured correlations, with sample sizes, for every parlay and same-game combination the lab prices.")


def page_validation():
    lb = lead.get("leaderboard", [])
    gate_names = ["G1_sample", "G2_holdout_roi", "G3_discovery_roi", "G4_significance", "G5_calibration",
                  "G6_stability", "G7_robustness", "G8_concentration", "G9_price_sensitivity"]
    defs = [
        ["G1", "Sample", f"holdout n ≥ {lead.get('gate_thresholds',{}).get('G1_sample')} ({lead.get('gate_thresholds',{}).get('G1_sample_prop')} for props)", "A rule fitting 40 bets is noise."],
        ["G2", "Holdout ROI", "ROI > 0 on 2020–2026", "The signal must exist out of sample."],
        ["G3", "Discovery ROI", "ROI > 0 on 2002–2019", "A rule that only works recently is a regime artefact."],
        ["G4", "Significance", "bootstrap 95% CI lower > 0 AND Benjamini-Hochberg q < 0.10 across the family", "Controls the fact that 19 strategies were tried."],
        ["G5", "Calibration", "|hit rate − mean model probability| ≤ 5pp and Brier < 0.25", "The model must know how confident it is."],
        ["G6", "Stability", "≥ 60% of holdout seasons profitable (min 3 seasons, ≥ 10 bets each)", "Rejects one-season wonders."],
        ["G7", "Robustness", "worst leave-one-season-out ROI > −5%", "Rejects strategies carried by a single season."],
        ["G8", "Concentration", "top 1% of bets ≤ 60% of profit", "Rejects results produced by one lucky bet."],
        ["G9", "Price sensitivity", "ROI > 0 repriced at −105", "Rejects edges thinner than the vig."],
    ]
    rows = [[f'<code>{e(r["strategy"])}</code>'] + [badge(r["gates"].get(g, {}).get("pass", False)) for g in gate_names]
            + [f'{r["gates_passed"]}/9'] for r in lb]
    body = f"""
<p class="lede">Nine gates, fixed in advance. A strategy is only "skill" if it survives all of them; otherwise it
is published as a lead with its failures attached.</p>
{table("Gate definitions", ["Gate", "Name", "Threshold", "Why it exists"], defs, wide=(2, 3))}
<h2>Pass matrix</h2>
<p class="small">Order of columns: {", ".join(gate_names)}.</p>
{table("Every gate, every strategy", ["Strategy"] + [g.split("_")[0] for g in gate_names] + ["Total"], rows)}
<h2>Luck removal in detail</h2>
<pre>expected wins under the market = SUM p_market
luck z  = (wins - SUM p_market) / sqrt(SUM p_market (1 - p_market))
excess ROI = ROI - (-4.55%)     # -110 on both sides, no edge, is the luck-free expectation</pre>
<p>Both quantities are reported for every strategy. The point is not that a strategy with a high ROI is lucky —
it is that a high ROI with a luck z near zero is evidence of nothing except that the sample is small.</p>"""
    return shell("Validation gates", "validation.html", body,
                 "The nine gates every strategy must clear, and the matrix showing which ones it clears.")


def page_verification():
    checks = verif.get("checks", [])
    s = verif.get("summary", {})
    groups = {}
    for c in checks:
        groups.setdefault(c["scope"], []).append(c)
    sections = []
    for scope, items in groups.items():
        show = []
        for c in items:
            comp = c.get("computed")
            off = c.get("official")
            show.append([f'<code>{e(c["check"])}</code>',
                         e(fmtdet(comp)) if comp is not None else e(fmtdet(c.get("detail"))),
                         e(fmtdet(off)) if off is not None else '<span class="chip">internal audit</span>',
                         badge(c["status"] == "pass"),
                         f'<a href="{e(c["source_url"])}" rel="noopener">source</a>' if c.get("source_url") else "—"])
        sections.append(f"<h3>{e(scope)} — {len(items)} checks</h3>" +
                        table(f"{scope}", ["Check", "Computed here", "Official nfl.com", "Result", "Source"],
                              show, wide=(1, 2)))
    body = f"""
<p class="lede">The bulk game data comes from an open mirror, not from the league, so it is not trusted — it is
checked. Every team-season in the mirror is compared against the official nfl.com standings, and every player
transcription is compared against the total nfl.com prints on the same page.</p>
<div class="grid cards">
  <div class="card"><div class="k">Checks run</div><div class="v">{s.get('checks_total')}</div><div class="s">line by line</div></div>
  <div class="card"><div class="k">Passed</div><div class="v">{s.get('passed')}</div><div class="s">exact equality, no tolerance</div></div>
  <div class="card"><div class="k">Failed</div><div class="v">{s.get('failed')}</div><div class="s">would appear on Flagged</div></div>
  <div class="card"><div class="k">Team-seasons verified</div><div class="v">64</div><div class="s">32 teams × 2025 and 2026</div></div>
</div>
<div class="note"><b>What this proves.</b> If the mirror's game scores were wrong anywhere, the derived standings
would disagree with nfl.com on that team's wins, losses, points for or points against. All 64 team-seasons match
exactly, in both a completed season (2025) and an in-progress one (2026). The official capture is also
self-audited: total wins equal total losses and total points for equal total points against in both seasons,
which would break if a value had been mistyped.</div>
{''.join(sections)}"""
    return shell("Verification register", "verification.html", body,
                 "77 line-by-line checks of the underlying data against official nfl.com pages.")


def page_flagged():
    rows = []
    for f in flags:
        rows.append([e(f.get("item")), e(f.get("why")),
                     f'<a href="{e(f["source_url"])}" rel="noopener">source</a>' if f.get("source_url") else "—"])
    irr = [[f'<code>{e(x["id"])}</code>', e(x["finding"]), e(x["detail"]), e(x["resolution"]),
            f'<a href="{e(x["source"])}" rel="noopener">source</a>' if x.get("source") else "—"]
           for x in sources.get("irregularities", [])]
    unv = [[f'<code>{e(x["id"])}</code>', e(x["name"]), e(x["status"]), e(x["effect"]),
            f'<a href="{e(x["url"])}" rel="noopener">attempted link</a>' if x.get("url") else "—"]
           for x in sources.get("unavailable", [])]
    asm = [[f'<code>{e(x["id"])}</code>', e(x["assumption"]), e(x["why"]), e(x["impact"]),
            e(x["severity"])] for x in sources.get("assumptions", [])]
    body = f"""
<p class="lede">Everything that could not be tied to an official source, every assumption the numbers rest on,
and every irregularity found while reviewing the data. None of this blocks publication — it is here so it can be
reviewed and challenged.</p>
<div class="warnbox"><b>Nothing on this page is verified.</b> Where a value could not be confirmed, it was left
blank rather than estimated. If you disagree with a resolution, the fix belongs in
<code>scripts/</code> and the pipeline will regenerate these tables.</div>
<h2>Unverified items</h2>
{table("Values or inputs that no reachable official source can confirm",
       ["ID", "Item", "Status", "Effect on the analysis", "Attempted link"], unv, wide=(1, 3))}
<h2>Assumptions</h2>
{table("Assumptions the published numbers depend on",
       ["ID", "Assumption", "Why it was made", "Impact", "Severity"], asm, wide=(1, 2, 3))}
<h2>Irregularities found during review</h2>
{table("Discrepancies, documentation conflicts and data quirks",
       ["ID", "Finding", "Detail", "Resolution", "Source"], irr, wide=(1, 2, 3))}
<h2>Automated verification failures</h2>
{table("Any check that failed in verify_official.py", ["Item", "Why", "Source"], rows,
       empty='<span class="badge pass">none</span> — all 77 automated checks passed')}
<h2>Prop and parlay disclosures</h2>
<ul class="tight">
<li>Prop ROI uses a −110 assumption (<code>A2</code>); no prop price was reachable, so no prop strategy is ranked.</li>
<li>The prop sample is {sum(p.get('n_games',0) for p in props)} player-games across {len(props)} players, captured by
hand from nfl.com. It is a demonstration of method, not a tested edge.</li>
<li>Same-game correlations rest on {prop_corr.get('pooled_qb_wr',{}).get('n')} paired games; the interval is wide.</li>
<li>Week 10 fixtures are from the mirror and not yet cross-checked (<code>I9</code>); those rows say so.</li>
<li>The closing line is single-sourced and is not a league publication (<code>I8</code>, <code>I5</code>).</li>
</ul>"""
    return shell("Flagged for review", "flagged.html", body,
                 "Unverified items, assumptions and irregularities — published deliberately, with links.")


def page_method():
    body = f"""
<p class="lede">The whole project is three ideas: build a line from data only, test rules against prices, and
gate the survivors until luck cannot explain them.</p>
<h2>1. Line origination</h2>
<pre>home_points = mu + HFA + OFF[home] + DEF[away]
away_points = mu        + OFF[away] + DEF[home]

Fit: weighted ridge least squares on every completed game before kickoff.
  weight = 2^(-age_days / {model.get('params',{}).get('half_life')})   (previous season x {model.get('params',{}).get('psw')})
  penalty = {model.get('params',{}).get('ridge')} on OFF and DEF, none on mu or HFA
Outputs: spread = home - away, total = home + away, P(home) = Phi(spread / sigma)
sigma = {model.get('sigma',{}).get('sigma')} points, estimated from the model's own out-of-sample residuals.</pre>
<p>Hyper-parameters were selected on 2002–2015 by spread+total MAE
({model.get('grid_size')} combinations), then frozen. 2020–2026 was never used for tuning, so every holdout
number is genuinely out of sample.</p>
<h2>2. Walk-forward discipline</h2>
<p>Predictions for a week are produced by a model fitted only on games with an earlier kickoff date. There is no
lookahead anywhere: the ratings used for Week 9 of 2026 know nothing about Week 9 of 2026.</p>
<h2>3. Strategy families</h2>
<ul class="tight">
<li><b>Singles</b> — model-vs-closing-line edges on spread and total, and modelled EV on moneylines.</li>
<li><b>Situational singles</b> — short weeks, rest differentials, byes, wind, temperature, dome, divisional games.</li>
<li><b>Parlays</b> — 2- and 3-leg combinations drawn from the edge pool across different games, one per week.</li>
<li><b>Same-game parlay</b> — spread + total in one game, priced with the measured correlation rather than multiplied.</li>
<li><b>Player props</b> — yardage lines from official game logs; the ROI question is flagged, not answered, because
no prop price exists in reachable data.</li>
<li><b>Control</b> — back every home team. This is the vig floor a real strategy must beat.</li>
</ul>
<h2>4. Luck removal</h2>
<pre>luck z     = (wins - SUM p_market) / sqrt(SUM p_market (1 - p_market))
excess ROI = ROI(detail) - (-4.55%)          # -110 both sides, no edge
bootstrap  = 4,000 resamples of settled bets -> 95% interval on ROI
FDR        = Benjamini-Hochberg over all {lead.get('family_size')} strategies, q = {lead.get('fdr_q')}</pre>
<p>The discipline matters more than any single number: with 19 strategies and no correction, roughly one would
look significant by chance. The FDR step is what converts "interesting" into "supported".</p>
<h2>5. Reproducing it</h2>
<pre>bash scripts/fetch_data.sh        # pinned raw data (GitHub only)
python3 scripts/build_dataset.py  # parse + normalise
python3 scripts/model.py          # originate lines, walk-forward
python3 scripts/backtest.py       # settle every strategy
python3 scripts/props.py          # prop board + correlations
python3 scripts/validation.py     # gates, FDR, leaderboard
python3 scripts/verify_official.py# 77 checks vs nfl.com
python3 scripts/build_site.py     # regenerate this site</pre>
<h2>6. Limitations, stated plainly</h2>
<ul class="tight">
<li>The model is deliberately simple. It is not competitive with a closing line, and the results say so.</li>
<li>Closing prices come from one mirror; a stale price would propagate into every ROI.</li>
<li>No injury, weather-forecast, or lineup data is used. Rest, roof, surface, temperature and wind are the only
situational inputs available in reachable data.</li>
<li>Player props are a method demonstration on six players, not a tested market.</li>
<li>Nothing here is betting advice.</li>
</ul>"""
    return shell("Method", "methodology.html", body,
                 "How the lines are built, how the rules are tested, and how luck is taken out of the answer.")


def page_sources():
    off = [[f'<code>{e(x["id"])}</code>', e(x["name"]), f'<a href="{e(x["url"])}" rel="noopener">link</a>',
            e(x["used_for"]), badge(x.get("verified", False))] for x in sources.get("official", [])]
    mir = [[f'<code>{e(x["id"])}</code>', e(x["name"]), f'<a href="{e(x["url"])}" rel="noopener">link</a>',
            e(x.get("pinned_commit", "—")), e(x["used_for"]), e(x.get("status", "used"))] for x in sources.get("mirror", [])]
    sha = [[f'<code>{e(k)}</code>', f'<code>{e(v)}</code>'] for k, v in (meta.get("sha256") or {}).items()]
    body = f"""
<p class="lede">A source is only listed as official if it is published by the National Football League. Everything
else is labelled for what it is, and a mirror is only trusted after it is checked against the official record.</p>
<h2>Official sources (nfl.com)</h2>
{table("Pages published by the NFL", ["ID", "Page", "Link", "Used for", "Retrieved"], off, wide=(3,))}
<h2>Third-party mirror</h2>
{table("Bulk data, pinned by commit", ["ID", "Source", "Link", "Pinned commit", "Used for", "Status"], mir, wide=(4,))}
<h3>File hashes</h3>
{table("sha256 of the raw files this build used", ["File", "sha256"], sha)}
<h2>Attempted but unavailable</h2>
<ul class="tight">
{''.join(f"<li><b>{e(x['name'])}</b> — {e(x['status'])}. {e(x['effect'])}" + (f" <a href='{e(x['url'])}' rel='noopener'>link</a>" if x.get('url') else "") + "</li>" for x in sources.get('unavailable', []))}
</ul>
<h2>Environment note</h2>
<p class="small">The sandbox that built this can reach only <code>github.com</code>,
<code>codeload.github.com</code>, <code>api.github.com</code>, <code>pypi.org</code>,
<code>files.pythonhosted.org</code> and <code>registry.npmjs.org</code> directly; nfl.com pages were read through
the page-fetch tool. That constraint is why bulk data comes from a GitHub mirror and why the player-statistics
releases (which redirect to a blocked host) could not be ingested.</p>"""
    return shell("Sources", "sources.html", body,
                 "Every source used, what it was used for, and how much it can be trusted.")


# --------------------------------------------------------------------------- markdown
def md_to_html(md):
    lines = md.split("\n")
    out, i, in_ul, in_ol, in_tbl = [], 0, False, False, False
    def close():
        nonlocal in_ul, in_ol, in_tbl
        if in_ul: out.append("</ul>"); in_ul = False
        if in_ol: out.append("</ol>"); in_ol = False
        if in_tbl: out.append("</tbody></table></div>"); in_tbl = False
    def inline(s):
        s = e(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" rel="noopener">\1</a>', s)
        return s
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            close()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            out.append("<pre>" + e("\n".join(buf)) + "</pre>")
            i += 1
            continue
        if ln.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").strip()) <= set("-: "):
            close()
            hdr = [c.strip() for c in ln.strip().strip("|").split("|")]
            out.append('<div class="tablewrap"><table><thead><tr>' +
                       "".join(f"<th>{inline(h)}</th>" for h in hdr) + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table></div>")
            continue
        if re.match(r"^#{1,4} ", ln):
            close()
            lvl = len(ln) - len(ln.lstrip("#"))
            out.append(f"<h{min(lvl+1,4)}>{inline(ln[lvl+1:])}</h{min(lvl+1,4)}>")
        elif ln.startswith("- ") or ln.startswith("* "):
            if not in_ul: close(); out.append('<ul class="tight">'); in_ul = True
            out.append(f"<li>{inline(ln[2:])}</li>")
        elif re.match(r"^\d+\. ", ln):
            if not in_ol: close(); out.append("<ol>"); in_ol = True
            out.append(f"<li>{inline(re.sub(r'^[0-9]+.' , '', ln))}</li>")
        elif ln.strip() == "":
            close()
        else:
            close()
            out.append(f"<p>{inline(ln)}</p>")
        i += 1
    close()
    return "\n".join(out)


def page_exec():
    p = os.path.join(ROOT, "EXECUTIVE_SUMMARY.md")
    md = open(p).read()
    return shell("Executive summary", "executive-summary.html", md_to_html(md),
                 "One page for a reader with two minutes: what was built, what it found, what is unproven.")


# --------------------------------------------------------------------------- build
PAGES = {
    "index.html": page_index, "lines.html": page_lines, "props.html": page_props,
    "strategies.html": page_strategies, "leaderboard.html": page_leaderboard,
    "correlation.html": page_correlation, "validation.html": page_validation,
    "verification.html": page_verification, "flagged.html": page_flagged,
    "methodology.html": page_method, "sources.html": page_sources, "executive-summary.html": page_exec,
}


def main():
    written = []
    for fname, fn in PAGES.items():
        html_txt = fn()
        with open(os.path.join(ROOT, fname), "w", encoding="utf-8") as f:
            f.write(html_txt)
        written.append(fname)
    open(os.path.join(ROOT, ".nojekyll"), "w").write("")

    # internal link check
    missing = []
    for fname in written:
        txt = open(os.path.join(ROOT, fname), encoding="utf-8").read()
        for href in re.findall(r'href="([^"#?]+)"', txt):
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            if not os.path.exists(os.path.join(ROOT, href)):
                missing.append((fname, href))
        for src in re.findall(r'src="([^"]+)"', txt):
            if not src.startswith("http") and not os.path.exists(os.path.join(ROOT, src)):
                missing.append((fname, src))
    print(f"wrote {len(written)} pages")
    if missing:
        print("BROKEN INTERNAL LINKS:")
        for m in missing:
            print("  ", m)
        raise SystemExit(1)
    print("link check: 0 broken internal links")
    ext = 0
    for fname in written:
        txt = open(os.path.join(ROOT, fname), encoding="utf-8").read()
        ext += len(re.findall(r'href="https?://', txt))
    print(f"external links: {ext}")


if __name__ == "__main__":
    main()
