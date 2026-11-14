#!/usr/bin/env python3
"""line-desk site builder: renders line-desk/index.html and line-desk/pages/*.html
deterministically from the committed JSON registers.

Every table row ends in a source-link cell (enforced by table() and by verify.py).
Blank cells render as an em dash with an 'unverified' tooltip: no value is ever
inferred or filled from an unofficial source.

Usage:
  python3 line-desk/scripts/build_site.py            # write pages
  python3 line-desk/scripts/build_site.py --check    # fail if disk differs from a fresh render
"""
from __future__ import annotations

import html
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LD = os.path.join(ROOT, "line-desk")
GENERATOR = "line-desk/scripts/build_site.py"
AS_OF = "2026-11-14"

NAV = [
    ("index.html", "Overview"),
    ("pages/requirements.html", "Requirements"),
    ("pages/results-feed.html", "Results feed"),
    ("pages/price-snapshots.html", "Price snapshots"),
    ("pages/origination.html", "Origination (side-T-ML)"),
    ("pages/leaderboard.html", "Signal vs staking"),
    ("pages/gates.html", "Gates &amp; demotion"),
    ("pages/correlations.html", "Official correlations"),
    ("pages/depth.html", "Replacement depth"),
    ("pages/suggestions.html", "Suggestions"),
    ("pages/questions.html", "Questions &amp; answers"),
    ("pages/executive.html", "Executive summary"),
    ("pages/flagged.html", "Flagged for review"),
    ("pages/repo-review.html", "Repo review"),
    ("pages/sources.html", "Sources"),
]

DISCLAIMER = ("Line Desk &mdash; research and measurement, not betting advice. "
              "Values that cannot be confirmed from an official source are left blank and flagged.")


def load(name: str):
    with open(os.path.join(LD, "data", name), encoding="utf-8") as fh:
        return json.load(fh)


def esc(v) -> str:
    if v is None:
        return ""
    return html.escape(str(v))


def blank(reason: str = "unverified &mdash; no official source") -> str:
    return f'<td class="blank" title="{reason}">&mdash;</td>'


def a(href: str, text: str) -> str:
    return f'<a href="{esc(href)}" rel="noopener">{esc(text)}</a>'


def table(headers: list[str], rows: list[list[str]], caption: str = "") -> str:
    """rows: each row's LAST cell must already be an anchor (source link)."""
    for i, row in enumerate(rows):
        if not row or "<a " not in row[-1]:
            raise SystemExit(f"table row {i} has no source link in its last cell: {row[:2]}")
    cap = f"<caption>{caption}</caption>" if caption else ""
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(row) + "</tr>")
    return (f'<div class="table-wrap"><table>{cap}<thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def kpi(value: str, label: str, note: str = "") -> str:
    n = f'<small>{note}</small>' if note else ""
    return f'<div class="kpi"><strong>{value}</strong><span>{label}</span>{n}</div>'


def page(current: str, title: str, body: str) -> str:
    depth = 0 if current == "index.html" else 1
    prefix = "" if depth == 0 else "../"
    navlinks = []
    for href, label in NAV:
        cls = ' class="active" aria-current="page"' if href == current else ""
        navlinks.append(f'<a href="{prefix}{href}"{cls}>{label}</a>')
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="generator" content="{GENERATOR}">
<meta name="description" content="Line Desk: price snapshots, verified results, origination order, signal vs staking leaderboard, official-only correlations, replacement depth, demotion gate.">
<title>{title} | Line Desk</title>
<link rel="stylesheet" href="{prefix}assets/style.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="app">
<aside class="sidebar">
<a class="brand" href="{prefix}index.html">LINE<b>DESK</b><small>NFL origination requirements</small></a>
<nav aria-label="Main navigation">{"".join(navlinks)}</nav>
<div class="sidebar-note">As of {AS_OF}<br>Research mode &mdash; no live recommendations</div>
</aside>
<main id="main">
<header class="topbar"><h1>{title}</h1><span class="date">AS OF {AS_OF}</span></header>
{body}
<footer>{DISCLAIMER}</footer>
</main>
</div>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# builders
# --------------------------------------------------------------------------- #
def build_index() -> str:
    feed = load("results_feed.json")
    corr = load("correlations.json")
    snap = load("price_snapshots.json")
    lb = load("leaderboard.json")
    depth = load("depth.json")
    gates = load("gates.json")
    req = load("requirements.json")
    flagged = load("flagged.json")

    statuses = [r["status"].split(" - ")[0] for r in req["rows"]]
    built = sum(1 for s in statuses if s == "built")
    partial = sum(1 for s in statuses if s == "partial")
    other = len(statuses) - built - partial

    links = [
        ("pages/requirements.html", "Requirements", "Every brief requirement traced to status and evidence."),
        ("pages/results-feed.html", "Verified results feed", f"{feed['verified_rows']} official finals with per-row source links."),
        ("pages/price-snapshots.html", "Price snapshots", "Open/close store coverage for every originated market."),
        ("pages/origination.html", "Origination order", "Side first, then total, then moneyline &mdash; fair / market / difference columns."),
        ("pages/leaderboard.html", "Signal vs staking", "Two ranks: signal governs, staking is reported only."),
        ("pages/gates.html", "Gates &amp; demotion", "Promotion checks and the live&rarr;paper demotion gate, dry-run on real results."),
        ("pages/correlations.html", "Official correlations", f"{len(corr['correlations'])} coefficients from NFL.com numbers only, each with n."),
        ("pages/depth.html", "Replacement depth", "Depth-of-replacement store; string tiers blank until an official source exists."),
        ("pages/suggestions.html", "Suggestions", "12 proposals for review &mdash; nothing implemented without a decision."),
        ("pages/questions.html", "Questions &amp; answers", "What we have, what is missing, how to discover it."),
        ("pages/executive.html", "Executive summary", "The one-page version of everything below."),
        ("pages/flagged.html", "Flagged for review", f"{len(flagged['rows'])} irregularities, each with a source."),
        ("pages/repo-review.html", "Repo review", "Line-by-line review of the repository and its checks."),
        ("pages/sources.html", "Sources", "Every source opened first-hand on 2026-11-14."),
    ]
    grid = "".join(
        f'<a class="card" href="{h}"><h3>{t}</h3><p>{d}</p></a>' for h, t, d in links)

    kpis = (
        kpi(str(feed["verified_rows"]), "verified results", "NFL.com finals, weeks 7-10 Thu")
        + kpi(str(len(corr["correlations"])), "official correlations", "n = 32 / 32 / 64, CI each")
        + kpi(f"{snap['coverage']['market_open_captured']}/{snap['coverage']['market_records']}", "market prices captured", "no official price source")
        + kpi(f"{lb['n_qualified']}/{lb['n_candidates']}", "strategies qualified", "10/10 gates required")
        + kpi(f"{depth['coverage']['rows_with_string_tier']}/{depth['coverage']['rows']}", "depth tiers sourced", "official depth chart 404s")
        + kpi(f"{built}/{len(req['rows'])}", "requirements built", f"{partial} partial, {other} other")
    )

    body = f"""
<section class="kpis">{kpis}</section>
<section class="block">
<h2>What this desk adds</h2>
<div class="cards">{grid}</div>
</section>
<section class="block note">
<h3>Honest state of play</h3>
<p>The verified results feed and the official-only correlation set are <b>live and sourced</b>.
The price-snapshot store exists as a contract with <b>0 market captures</b> because no official
price source exists (the NFL's official betting feed goes to operators via an exclusive
distributor). Because prices are absent, closing-line value cannot be measured, no strategy can
be promoted to live, and the demotion gate has no subject &mdash; it is defined, dry-run and
waiting. {gates['dry_run']['n_stay_paper']} of {gates['dry_run']['n_evaluated']} candidates stay PAPER.
Every blocked value is blank and listed on <a href="pages/flagged.html">Flagged for review</a>.</p>
</section>
"""
    return page("index.html", "Overview", body)


def build_requirements() -> str:
    req = load("requirements.json")
    rows = []
    for r in req["rows"]:
        rows.append([
            f"<td><b>{esc(r['id'])}</b></td>",
            f"<td>{esc(r['requirement'])}</td>",
            f"<td><span class=\"badge {'ok' if r['status'].startswith(('built','done')) else 'warn'}\">{esc(r['status'])}</span></td>",
            f"<td>{esc(r['what_exists'])}</td>",
            f"<td>{esc(r['gap']) or '&mdash;'}</td>",
            f"<td><code>{esc(r['evidence_path'])}</code></td>",
            a(r["source_url"], r["source_label"]),
        ])
    body = f"""
<section class="block"><p class="lead">{esc(req['description'])}</p>
{table(["ID","Requirement","Status","What exists","Gap / blocker","Evidence","Source"], rows)}
</section>
"""
    return page("pages/requirements.html", "Requirements", body)


def build_results_feed() -> str:
    feed = load("results_feed.json")
    rows = []
    for r in feed["rows"]:
        x = r["cross_check"]
        if x["present"] and x["match"] is True:
            cross = f"match ({x['committed_away_score']}-{x['committed_home_score']} in snapshot)"
        elif x["present"]:
            cross = "snapshot blank/stale"
        else:
            cross = "not in snapshot"
        rows.append([
            f"<td>{esc(r['date'])}</td>",
            f"<td>W{r['week']}</td>",
            f"<td><b>{esc(r['away'])}</b> {r['away_score']} at <b>{esc(r['home'])}</b> {r['home_score']}</td>",
            f"<td><span class=\"badge ok\">{esc(r['status'])} &middot; verified</span></td>",
            f"<td>{esc(cross)}</td>",
            a(r["game_url"], "official game page"),
        ])
    pend_rows = []
    for p in feed["coverage"]["pending_weeks"]:
        pend_rows.append([
            f"<td>W{p['week']}</td>",
            f"<td class=\"blank\" title=\"unverified &mdash; not transcribed\">&mdash;</td>",
            f"<td class=\"blank\" title=\"unverified &mdash; not transcribed\">&mdash;</td>",
            f"<td>{esc(p['status'])} ({p['games_played_per_committed_snapshot']} games per committed third-party snapshot)</td>",
            a(p["source_url"], "official week page (capture point)"),
        ])
    cc = feed["cross_check_summary"]
    body = f"""
<section class="kpis">
{kpi(str(feed['verified_rows']), 'verified finals', 'weeks 7, 8, 9 + week-10 Thursday')}
{kpi(f"{cc['match']}/{cc['compared']}", 'snapshot cross-check', '0 mismatches vs committed extract')}
{kpi(str(sum(p['games_played_per_committed_snapshot'] for p in feed['coverage']['pending_weeks'])), 'games pending', 'weeks 1-6, scores blank')}
</section>
<section class="block">
<p class="lead">{esc(feed['policy'])}</p>
<h2>Verified rows</h2>
{table(["Date","Week","Matchup (official final)","Status","Cross-check vs committed snapshot","Source"], rows,
       'Every score transcribed first-hand from the linked NFL.com page on 2026-11-14.')}
</section>
<section class="block">
<h2>Pending capture (scores left blank)</h2>
{table(["Week","Away score","Home score","Status","Official capture point"], pend_rows,
       'Blank by policy: these scores were not transcribed from the official page, so they are not published.')}
<p class="note">{esc(feed['coverage']['week10_note'])} {esc(feed['coverage']['denominator_source'])}</p>
</section>
"""
    return page("pages/results-feed.html", "Verified results feed", body)


def build_price_snapshots() -> str:
    snap = load("price_snapshots.json")
    cov = snap["coverage"]
    rows = []
    for r in snap["rows"]:
        ours_away = ""
        if "ours_open_away" in r:
            ours_away = f" (away {r['ours_open_away']})"
        rows.append([
            f"<td>{esc(r['matchup'])}</td>",
            f"<td>{r['origination_order']}. {esc(r['market'])}</td>",
            f"<td>{esc(r['ours_open'])}{ours_away}</td>",
            blank("no second capture of our line yet (SG-03)"),
            blank("no official price source (FL-LD-01)"),
            blank("no official price source (FL-LD-01)"),
            f"<td><span class=\"badge warn\">{esc(r['status'])}</span></td>",
            a(r["source_url"], "our line: model output (repo)"),
        ])
    body = f"""
<section class="kpis">
{kpi(str(cov['market_records']), 'market records', '15 games x side, total, moneyline')}
{kpi(str(cov['our_open_line_captured']), 'our open lines', 'captured at origination')}
{kpi(str(cov['our_close_captured']), 'our close lines', 'second capture not scheduled')}
{kpi(str(cov['market_open_captured'] + cov['market_close_captured']), 'market prices', 'no official source')}
</section>
<section class="block">
<p class="lead">{esc(snap['policy'])}</p>
<p class="note">Store contract: {esc(snap['store_reference'])} Slate: {esc(snap['as_of_slate']['generated_from'])}.</p>
{table(["Matchup","Market (origination order)","Our open line","Our close","Market open","Market close","Status","Source"], rows,
       'Market price cells are blank by policy: no official public price source exists (FL-LD-01).')}
</section>
"""
    return page("pages/price-snapshots.html", "Price snapshots", body)


def build_origination() -> str:
    o = load("origination.json")
    order = " &rarr; ".join(f"<b>{s['step']}. {esc(s['market'])}</b>" for s in o["order"])

    def side_rows():
        rows = []
        for g in o["games"]:
            s = g["step1_side"]
            res = s["official_result"]
            cov = s.get("home_side_of_our_line_covered")
            cov_txt = {True: "home side covered", False: "away side covered", "push": "push"}.get(cov, "&mdash;")
            rows.append([
                f"<td>{esc(g['matchup'] if 'matchup' in g else g['away'] + ' at ' + g['home'])} (W{g['week']})</td>",
                f"<td>{s['fair_line']}</td>",
                blank("no official price source (FL-LD-01)"),
                blank("needs market line (FL-LD-01)"),
                f"<td>away {res['away_score']} - home {res['home_score']} final (home margin {res['home_margin']:+d})</td>" if res else blank("official result not captured"),
                f"<td>{cov_txt}</td>",
                a(g["source_url"], "fair line: model output"),
            ])
        return rows

    def total_rows():
        rows = []
        for g in o["games"]:
            t = g["step2_total"]
            res = t["official_result"]
            over = t.get("over_at_our_line")
            over_txt = {True: "over at our line", False: "under at our line"}.get(over, "&mdash;")
            rows.append([
                f"<td>{esc(g['away'])} at {esc(g['home'])} (W{g['week']})</td>",
                f"<td>{t['fair_line']}</td>",
                blank("no official price source (FL-LD-01)"),
                blank("needs market line (FL-LD-01)"),
                f"<td>{res['total']} combined</td>" if res else blank("official result not captured"),
                f"<td>{over_txt}</td>",
                a(g["source_url"], "fair line: model output"),
            ])
        return rows

    def ml_rows():
        rows = []
        for g in o["games"]:
            m = g["step3_moneyline"]
            res = m["official_result"]
            rows.append([
                f"<td>{esc(g['away'])} at {esc(g['home'])} (W{g['week']})</td>",
                f"<td>home {m['fair_home_ml']} / away {m['fair_away_ml']}</td>",
                blank("no official price source (FL-LD-01)"),
                blank("needs market line (FL-LD-01)"),
                ("home won" if m["home_won"] else "away won") if res else blank("official result not captured"),
                a(g["source_url"], "fair ML: model output"),
            ])
        return rows

    disc_rows = []
    for d in o["discrepancy_vs_retired_pipeline"]["rows"]:
        disc_rows.append([
            f"<td>{esc(d['game_id'])}</td>",
            f"<td>{d['model_json_line']}</td>",
            f"<td>{d['results_originate_line']}</td>",
            f"<td>{d['gap_points']:+}</td>",
            a("https://github.com/karagemop466-tech/Korea2/blob/main/line-desk/data/origination.json", "discrepancy table"),
        ])

    body = f"""
<section class="block">
<p class="lead">{esc(o['policy'])}</p>
<p class="steps"><span>Order enforced:</span> {order} &mdash; the moneyline is never originated before the side and total.</p>
<p class="note">Slate: {esc(o['as_of_slate']['generated_from'])}. Sign convention: {esc(o['sign_convention'])}
All {o['n_with_official_result']} of {o['n_games']} games now have an official result (captured on the results-feed page), so every fair line here is settled against official numbers. Market columns: {o['market_columns_published']} published (blank by policy).</p>
</section>
<section class="block"><h2>Step 1 &mdash; side (spread)</h2>
{table(["Matchup","Fair line (ours)","Market line","Difference","Official result","Settlement vs our line","Source"], side_rows())}
</section>
<section class="block"><h2>Step 2 &mdash; total</h2>
{table(["Matchup","Fair total (ours)","Market total","Difference","Official total","At our line","Source"], total_rows())}
</section>
<section class="block"><h2>Step 3 &mdash; moneyline</h2>
{table(["Matchup","Fair ML (ours)","Market ML","Difference","Official winner","Source"], ml_rows())}
</section>
<section class="block"><h2>Dual-originator discrepancy (FL-LD-07)</h2>
<p class="note">{esc(o['discrepancy_vs_retired_pipeline']['note'])}</p>
{table(["Game","model.json line","results/originate.json line","Gap (pts)","Source"], disc_rows)}
</section>
"""
    return page("pages/origination.html", "Origination (side &rarr; total &rarr; moneyline)", body)


def build_leaderboard() -> str:
    lb = load("leaderboard.json")
    sig_rows = []
    stk_rows = []
    for r in lb["rows"]:
        s = r["signal"]
        sig_rows.append([
            f"<td><b>#{r['signal_rank']}</b></td>",
            f"<td>{esc(r['name'])}<br><small>{esc(r['id'])}</small></td>",
            f"<td>{esc(s['gates_passed'])} <small>(failed: {esc(', '.join(s['failed_gates']))})</small></td>",
            f"<td>{s['bh_adjusted_p']:.3f}</td>",
            f"<td>{s['p_value']:.3f}</td>",
            f"<td>{s['win_rate']:.1%} (n={s['decided']})</td>",
            f"<td><span class=\"badge bad\">{esc(s['verdict'])}</span></td>",
            a(r["source_url"], "gate output (repo)"),
        ])
        st = r["staking"]
        gap = r["rank_gap"]
        gap_txt = f"{gap:+d}" if gap else "0"
        stk_rows.append([
            f"<td><b>#{r['staking_rank']}</b></td>",
            f"<td>{esc(r['name'])}</td>",
            f"<td>{st['roi']:+.2%}</td>",
            f"<td>[{st['roi_ci95'][0]:+.1%}, {st['roi_ci95'][1]:+.1%}]</td>",
            f"<td>{st['n_bets']}</td>",
            f"<td>#{r['signal_rank']}</td>",
            f"<td>{gap_txt}</td>",
            a(r["source_url"], "ROI from committed backtest"),
        ])
    ctrl_rows = []
    for c in lb["controls"]:
        ctrl_rows.append([
            f"<td>{esc(c['name'])}</td>",
            f"<td>{c['roi']:+.2%}</td>",
            f"<td>[{c['roi_ci95'][0]:+.1%}, {c['roi_ci95'][1]:+.1%}]</td>",
            f"<td>{c['decided']}</td>",
            f"<td>{esc(c['note'])}</td>",
            a(c["source_url"], "control (repo)"),
        ])
    d = lb["demonstration"]
    body = f"""
<section class="block note">
<h3>{esc(lb['policy'])}</h3>
<p>Signal rank rule: {esc(lb['ranking_rule_signal'])}. Staking rank rule: {esc(lb['ranking_rule_staking'])}.
{esc(lb['upstream_rule_note'])}</p>
</section>
<section class="kpis">
{kpi(str(lb['n_candidates']), 'candidates', 'controls ranked separately')}
{kpi(str(lb['n_qualified']), 'qualified', '10/10 gates required')}
{kpi(f"#{d['best_staking']['signal_rank']}", 'best-staking strategy signal rank', d['best_staking']['id'] + ' holds staking #' + str(d['best_staking']['staking_rank']))}
{kpi('0', 'rewards payable', lb['reward_schedule_note'])}
</section>
<section class="block"><h2>Signal board (governs promotion and rewards)</h2>
{table(["Signal rank","Strategy","Gates (failed)","BH-adjusted p","Raw p","Win rate","Verdict","Source"], sig_rows)}
</section>
<section class="block"><h2>Staking block (reported only &mdash; never ranked into signal)</h2>
{table(["Staking rank","Strategy","ROI","95% ROI CI","Bets","Signal rank","Rank gap","Source"], stk_rows,
       'Staking order is shown for transparency only. It never affects promotion, rewards or the signal rank.')}
</section>
<section class="block"><h2>Controls (vig baselines)</h2>
{table(["Control","ROI","95% ROI CI","Decided","Note","Source"], ctrl_rows)}
</section>
<section class="block note"><h3>Demonstration</h3>
<p>{esc(d['reading'])} Best staking: <b>{esc(d['best_staking']['id'])}</b> (ROI {d['best_staking']['roi']:+.2%}, staking #{d['best_staking']['staking_rank']}, signal #{d['best_staking']['signal_rank']}).
Best signal: <b>{esc(d['best_signal']['id'])}</b> ({d['best_signal']['gates']} gates, signal #{d['best_signal']['signal_rank']}, staking #{d['best_signal']['staking_rank']}).</p></section>
"""
    return page("pages/leaderboard.html", "Signal vs staking", body)


def build_gates() -> str:
    g = load("gates.json")
    prom_rows = [[f"<td>{esc(p['id'])}</td>", f"<td>{esc(p['rule'])}</td>",
                  f"<td><span class=\"badge {'ok' if 'pass' in p['current_result'] and '0 of' not in p['current_result'] and 'not' not in p['current_result'] and '0 ' not in p['current_result'] else 'warn'}\">{esc(p['current_result'])}</span></td>",
                  a("https://github.com/karagemop466-tech/Korea2/tree/main/price-store", "gate design (repo)")]
                 for p in g["promotion"]]
    dem_rows = [[f"<td><b>{esc(d['id'])}</b></td>", f"<td>{esc(d['rule'])}</td>",
                 f"<td>{esc(d['input'])}</td>", f"<td>{esc(d['owner'])}</td>",
                 f"<td>{esc(d['current_result'])}</td>",
                 a("https://github.com/karagemop466-tech/Korea2/blob/main/line-desk/data/gates.json", "spec (repo)")]
                for d in g["demotion"]]
    dry_rows = []
    for d in g["dry_run"]["rows"]:
        dry_rows.append([
            f"<td>{esc(d['id'])}</td>",
            f"<td><span class=\"badge warn\">{esc(d['current_state'])}</span></td>",
            f"<td>{esc('; '.join(d['promotion_blockers']))}</td>",
            f"<td>{esc(d['d1_clv'])}</td>",
            f"<td>{esc(d['d2_outcome_harm'])} (n={d['n_decided']}, upper {d['roi_ci95_upper']:+.1%})</td>",
            a("https://github.com/karagemop466-tech/Korea2/blob/main/line-desk/data/gates.json", "dry-run inputs"),
        ])
    body = f"""
<section class="block note"><h3>{esc(g['status'])}</h3><p>{esc(g['policy'])}</p>
<p>States: {" &rarr; ".join(esc(s) for s in g['states'])} &mdash; promotion only through P1-P3; demotion only through D1/D2/D3.</p></section>
<section class="block"><h2>Promotion (PAPER &rarr; LIVE)</h2>
{table(["ID","Rule","Current result","Source"], prom_rows)}
</section>
<section class="block"><h2>Demotion (LIVE &rarr; PAPER)</h2>
{table(["ID","Rule","Input","Owner","Current result","Source"], dem_rows,
       'A lucky staking run cannot keep a bad signal live: D1 and D2 judge signal quality, not profit alone, and D3 never demotes on missing data.')}
</section>
<section class="block"><h2>Dry run on committed results</h2>
<p class="note">Input: {esc(g['dry_run']['input'])}. Result: {g['dry_run']['n_promoted']} promoted, {g['dry_run']['n_demoted']} demoted, {g['dry_run']['n_stay_paper']} stay PAPER (of {g['dry_run']['n_evaluated']} evaluated).</p>
{table(["Strategy","State","Promotion blockers","D1 (CLV)","D2 (outcome harm)","Source"], dry_rows)}
</section>
"""
    return page("pages/gates.html", "Gates &amp; demotion", body)


def build_correlations() -> str:
    c = load("correlations.json")
    rows = []
    for r in c["correlations"]:
        rows.append([
            f"<td><b>{esc(r['id'])}</b></td>",
            f"<td>{esc(r['pair'])}</td>",
            f"<td>{esc(r['season'])}</td>",
            f"<td><b>{r['r']:+.4f}</b></td>",
            f"<td><b>{r['n']}</b></td>",
            f"<td>[{r['ci95'][0]:+.4f}, {r['ci95'][1]:+.4f}]</td>",
            f"<td><small>{esc(r['inputs'])}</small></td>",
            a(r["data_source_url"], "NFL.com standings"),
        ])
    body = f"""
<section class="block note"><h3>Official-only policy</h3><p>{esc(c['policy'])}</p>
<p>Method: Pearson r; 95% confidence interval by Fisher's normal approximation per
{a('https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm', 'NIST Dataplot - correlation confidence limits')}.
Inputs transcribed from {a('https://www.nfl.com/standings/division/2026/REG', 'NFL.com 2026 standings')} and
{a('https://www.nfl.com/standings/division/2025/REG', 'NFL.com 2025 standings')} on {esc(c['retrieved_on'])}
({c['n_official_rows']} club-season rows). No third-party number enters any coefficient.</p></section>
<section class="block"><h2>Coefficients</h2>
{table(["ID","Pair","Season","r","n","95% CI","Inputs","Data source"], rows)}
</section>
"""
    return page("pages/correlations.html", "Official correlations", body)


def build_depth() -> str:
    d = load("depth.json")
    rows = []
    for r in d["rows"]:
        rows.append([
            f"<td>{esc(r['club'])}</td>",
            f"<td>{esc(r['player'])}</td>",
            f"<td>{esc(r['position'])}</td>",
            f"<td>{esc(r['injury']) or '&mdash;'}</td>",
            f"<td><span class=\"badge {'bad' if r['game_status']=='Out' else 'warn'}\">{esc(r['game_status'])}</span></td>",
            blank("no official source names the replacement (FL-LD-05)"),
            blank("no official depth chart - league path 404s (FL-LD-05)"),
            a(r["source_url"], "official injury report"),
        ])
    schema_rows = [[f"<td><code>{esc(k)}</code></td>", f"<td>{esc(v)}</td>",
                    a("https://www.nfl.com/injuries/league/2026/reg10", "official report columns")]
                   for k, v in d["schema"].items()]
    cov = d["coverage"]
    body = f"""
<section class="kpis">
{kpi(str(cov['rows']), 'injury rows (first-hand)', ', '.join(cov['clubs_sampled_first_hand']))}
{kpi(str(cov['rows_with_replacement']), 'replacements named', 'blank - no official source')}
{kpi(str(cov['rows_with_string_tier']), 'string tiers sourced', 'blank - depth chart 404s')}
</section>
<section class="block note"><h3>Policy</h3><p>{esc(d['policy'])}</p>
<p>{esc(d['signal_use'])}</p>
<p>Blocked: {esc(d['blocked']['reason'])} Checked: {a(d['blocked']['depth_chart_check_url'], 'depth-chart path returned HTTP 404')} on 2026-11-14.</p></section>
<section class="block"><h2>Store schema</h2>
{table(["Field","Meaning","Source"], schema_rows)}
</section>
<section class="block"><h2>Rows (depth fields blank by policy)</h2>
{table(["Club","Player","Pos","Injury","Game status","Replacement player","Replacement string (1st-4th)","Source"], rows,
       esc(cov['note']))}
</section>
"""
    return page("pages/depth.html", "Replacement depth", body)


def build_suggestions() -> str:
    s = load("suggestions.json")
    rows = []
    for r in s["rows"]:
        rows.append([
            f"<td><b>{esc(r['id'])}</b></td>",
            f"<td>{esc(r['title'])}<br><small>{esc(r['category'])}</small></td>",
            f"<td>{esc(r['improves'])}</td>",
            f"<td>{esc(r['effort'])}</td>",
            f"<td>{esc(r['impact'])}</td>",
            f"<td>{esc(r['risk'])}</td>",
            f"<td>{esc(r['discovery'])}</td>",
            f"<td><span class=\"badge warn\">{esc(r['status'])}</span></td>",
            a(r["source_url"], r["source_label"]),
        ])
    body = f"""
<section class="block note"><h3>Review workflow</h3><p>{esc(s['workflow'])}</p>
<p>{esc(s['description'])}</p></section>
<section class="block"><h2>Suggestions</h2>
{table(["ID","Suggestion","What it unblocks / improves","Effort","Impact","Risk","Discovery action","Status","Source"], rows)}
</section>
"""
    return page("pages/suggestions.html", "Suggestions", body)


def build_questions() -> str:
    q = load("questions.json")
    rows = []
    for r in q["rows"]:
        missing = blank("not available - see discovery action") if r["missing_blank"] else f"<td>{esc(r['missing'])}</td>"
        rows.append([
            f"<td><b>{esc(r['id'])}</b></td>",
            f"<td>{esc(r['question'])}</td>",
            f"<td>{esc(r['have'])}</td>",
            f"<td>{a(r['have_source'], 'source')}</td>",
            missing,
            f"<td>{esc(r['discovery'])}</td>",
            f"<td><small>{esc(r['blocks'])}</small></td>",
        ])
    # make sure every row ends with a source link: append have_source as last cell
    for i, r in enumerate(q["rows"]):
        rows[i].append(a(r["have_source"], "evidence"))
    body = f"""
<section class="block note"><h3>Decision readiness</h3><p>{esc(q['description'])}</p></section>
<section class="block"><h2>Questions, information and answers</h2>
{table(["ID","Question","What we have","Have source","What is missing (blank = not inferable)","Discovery action","Blocks","Source"], rows)}
</section>
"""
    return page("pages/questions.html", "Questions &amp; answers", body)


def build_executive() -> str:
    feed = load("results_feed.json")
    corr = load("correlations.json")
    snap = load("price_snapshots.json")
    lb = load("leaderboard.json")
    gates = load("gates.json")
    req = load("requirements.json")
    orig = load("origination.json")

    statuses = [r["status"].split(" - ")[0] for r in req["rows"]]
    built = sum(1 for s in statuses if s == "built")

    head_rows = [
        ["Verified results feed", f"{feed['verified_rows']} official finals (weeks 7-10 Thu), cross-check {feed['cross_check_summary']['match']}/{feed['cross_check_summary']['compared']} vs committed snapshot",
         a("https://www.nfl.com/schedules/2026/by-week/week-9", "NFL.com week pages")],
        ["Official-only correlations", f"{len(corr['correlations'])} coefficients from NFL.com standings only; best-known: net points vs wins r = +0.848 (n = 32, 2026); pooled r = +0.800 (n = 64)",
         a("https://www.nfl.com/standings/division/2026/REG", "NFL.com standings")],
        ["Price snapshots", f"{snap['coverage']['market_records']} market records; our open line on {snap['coverage']['our_open_line_captured']}; market prices 0/45 (no official source)",
         a("https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports", "NFL - official feed distribution")],
        ["Origination order", f"Side &rarr; total &rarr; moneyline enforced; {orig['n_with_official_result']}/{orig['n_games']} fair lines settled against official results; market/difference columns blank",
         a("https://github.com/karagemop466-tech/Korea2/blob/main/line-desk/data/origination.json", "origination register")],
        ["Signal vs staking", "Signal rank governs; staking reported separately. Demonstration: best staking strategy is signal #5; best signal strategy is staking #3",
         a("https://github.com/karagemop466-tech/Korea2/blob/main/line-desk/data/leaderboard.json", "split leaderboard")],
        ["Competition state", f"0 of {lb['n_candidates']} candidates qualified (max 5/10 gates); rewards payable 0; all stay PAPER",
         a("https://github.com/karagemop466-tech/Korea2/blob/main/data/derived/leaderboard.json", "committed gates")],
        ["Demotion gate", f"Defined (D1 CLV + D2 outcome + D3 integrity) and dry-run: {gates['dry_run']['n_promoted']} promoted, {gates['dry_run']['n_demoted']} demoted, {gates['dry_run']['n_stay_paper']} stay PAPER; no live subject",
         a("https://github.com/karagemop466-tech/Korea2/blob/main/line-desk/data/gates.json", "gate spec")],
        ["Replacement depth", "Store built; 0/11 replacements named, 0/11 string tiers - official depth chart 404s, report has no depth column",
         a("https://www.nfl.com/teams/new-england-patriots/depth-chart", "404 evidence")],
        ["Requirements", f"{built} of {len(req['rows'])} requirements built here; {len(req['rows']) - built} partial/existing/blocked - each traced with evidence",
         a("https://github.com/karagemop466-tech/Korea2/blob/main/line-desk/data/requirements.json", "requirements trace")],
    ]
    body = f"""
<section class="block"><h2>Headline</h2>
<p class="lead">Line Desk delivers the brief's infrastructure requirements as a sourced, deterministic
site: a price-snapshot store (contract live, prices blank because none exist officially), a verified
results feed ({feed['verified_rows']} official finals), fixed origination order with fair/market/difference
columns, a signal-only leaderboard, official-only correlations with n, a replacement-depth store with
honest blanks, and a demotion gate dry-run on real results. {built}/{len(req['rows'])} requirements are built;
the rest are partial or blocked with a named discovery path.</p>
{table(["Topic","State (2026-11-14)","Source"], head_rows)}
</section>
<section class="block note"><h3>What would change the picture</h3>
<p>Three things, in order: (1) an official timestamped price feed (unblocks market columns, CLV, official ROI &mdash; SG-01/Q-01);
(2) automated official results capture for weeks 1-6 (completes the feed &mdash; SG-02/Q-04);
(3) a club-official depth source (unblocks string tiers and the deficiency signal &mdash; SG-04/Q-05).
Until then every dependent cell stays blank and flagged - nothing is inferred.</p></section>
"""
    return page("pages/executive.html", "Executive summary", body)


def build_flagged() -> str:
    f = load("flagged.json")
    rows = []
    for r in f["rows"]:
        rows.append([
            f"<td><b>{esc(r['id'])}</b></td>",
            f"<td><span class=\"badge {'bad' if r['severity']=='high' else 'warn' if r['severity']=='medium' else ''}\">{esc(r['severity'])}</span></td>",
            f"<td>{esc(r['issue'])}</td>",
            f"<td>{esc(r['handling'])}</td>",
            a(r["source_url"], r["source_label"]),
        ])
    body = f"""
<section class="block note"><h3>Policy</h3><p>{esc(f['description'])}</p></section>
<section class="block"><h2>Flagged for review</h2>
{table(["ID","Severity","Issue","Handling","Source"], rows)}
</section>
"""
    return page("pages/flagged.html", "Flagged for review", body)


def build_sources() -> str:
    s = load("sources.json")
    rows = []
    for r in s["sources"]:
        rows.append([
            f"<td><b>{esc(r['id'])}</b></td>",
            f"<td>{esc(r['title'])}</td>",
            f"<td><span class=\"badge {'ok' if r['tier']=='official' else 'warn' if r['tier']=='third-party' else ''}\">{esc(r['tier'])}</span></td>",
            f"<td>{esc(r['publisher'])}</td>",
            f"<td>{esc(r['used_for'])}</td>",
            f"<td>{esc(r['opened'])}</td>",
            a(r["url"], "open"),
        ])
    body = f"""
<section class="block note"><h3>Register</h3><p>{esc(s['description'])}</p></section>
<section class="block"><h2>Sources</h2>
{table(["ID","Title","Tier","Publisher","Used for","Opened","Link"], rows)}
</section>
"""
    return page("pages/sources.html", "Sources", body)


def build_repo_review() -> str:
    rv = load("repo_review.json")
    inv_rows = [[f"<td>{esc(k)}</td>", f"<td>{esc(str(v))}</td>",
                 a("https://github.com/karagemop466-tech/Korea2", "repository")]
                for k, v in rv["inventory"].items()]
    chk_rows = [[f"<td>{esc(c['check'])}</td>",
                 f"<td><span class=\"badge {'ok' if c['result'].startswith(('PASS','all')) else 'warn'}\">{esc(c['result'])}</span></td>",
                 f"<td>{esc(c['note'])}</td>",
                 a(c["source_url"], c["source_label"])] for c in rv["checks"]]
    ir_rows = [[f"<td><b>{esc(i['id'])}</b></td>", f"<td>{esc(i['finding'])}</td>",
                f"<td>{esc(i['handling'])}</td>",
                a(i["source_url"], i["source_label"])] for i in rv["irregularities"]]
    body = f"""
<section class="block"><h2>Inventory (2026-11-14)</h2>
{table(["Item","Value","Source"], inv_rows)}
</section>
<section class="block"><h2>Checks run this session</h2>
{table(["Check","Result","Note","Source"], chk_rows)}
</section>
<section class="block"><h2>Irregularities found</h2>
{table(["ID","Finding","Handling","Source"], ir_rows)}
</section>
"""
    return page("pages/repo-review.html", "Repo review", body)


PAGES = {
    "index.html": build_index,
    "pages/requirements.html": build_requirements,
    "pages/results-feed.html": build_results_feed,
    "pages/price-snapshots.html": build_price_snapshots,
    "pages/origination.html": build_origination,
    "pages/leaderboard.html": build_leaderboard,
    "pages/gates.html": build_gates,
    "pages/correlations.html": build_correlations,
    "pages/depth.html": build_depth,
    "pages/suggestions.html": build_suggestions,
    "pages/questions.html": build_questions,
    "pages/executive.html": build_executive,
    "pages/flagged.html": build_flagged,
    "pages/repo-review.html": build_repo_review,
    "pages/sources.html": build_sources,
}


def render_all() -> dict[str, str]:
    out = {}
    for path, fn in PAGES.items():
        out[path] = fn()
    return out


def main() -> int:
    check = "--check" in sys.argv
    rendered = render_all()
    if check:
        bad = []
        for path, content in rendered.items():
            full = os.path.join(LD, path)
            if not os.path.exists(full):
                bad.append(f"missing {path}")
                continue
            with open(full, encoding="utf-8") as fh:
                if fh.read() != content:
                    bad.append(f"stale {path}")
        if bad:
            print("CHECK FAILED:", "; ".join(bad))
            return 1
        print(f"check ok: {len(rendered)} pages byte-identical to a fresh render")
        return 0
    os.makedirs(os.path.join(LD, "pages"), exist_ok=True)
    os.makedirs(os.path.join(LD, "assets"), exist_ok=True)
    for path, content in rendered.items():
        with open(os.path.join(LD, path), "w", encoding="utf-8") as fh:
            fh.write(content)
    print(f"built {len(rendered)} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
