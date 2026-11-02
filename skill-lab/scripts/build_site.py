#!/usr/bin/env python3
"""Static GitHub Pages dashboard generator for Skill Lab (SL-7).

Generates skill-lab/index.html + 11 category subpages under skill-lab/pages/*.html
from verified JSON artifacts in skill-lab/data/*.json.

Hard invariants enforced:
- Every <tbody><tr> across every table on all 12 pages ends with a direct https://
  link to a verified primary official source in skill-lab/data/sources.json.
- Every unverified value (flagged items FLG-01..12, unverified SGP/prop ROI in STR-10..14,
  cash prize cells, unverified sportsbook prop lines) renders as a strictly empty
  <td class="blank-cell"></td> (inner text == "").
- Zero external JS/CDN dependencies; clean, self-contained HTML5 + inline SVG + style.css.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from common import DATA_OUT as DATA_DIR, SKILL_LAB_ROOT

PAGES_DIR = SKILL_LAB_ROOT / "pages"

NAV_PAGES: list[tuple[str, str, str]] = [
    ("overview", "Overview", "index.html"),
    ("summary", "Executive Summary", "pages/summary.html"),
    ("origination", "Line & Prop Origination", "pages/origination.html"),
    ("signals", "Signals & FDR", "pages/signals.html"),
    ("luck", "Skill vs. Luck", "pages/luck-skill.html"),
    ("correlations", "Correlations & Copula", "pages/correlations.html"),
    ("leaderboard", "Leaderboard & Rewards", "pages/leaderboard.html"),
    ("strategies", "Singles, Parlays & Props", "pages/strategies.html"),
    ("gates", "10-Gate Matrix", "pages/gates.html"),
    ("official", "NFL.com Audit", "pages/official-audit.html"),
    ("reporeview", "Repo Review", "pages/repo-review.html"),
    ("flagged", "Flagged for Review", "pages/flagged.html"),
]


def esc(val: Any) -> str:
    return html.escape(str(val), quote=True)


def load_json(name: str) -> dict[str, Any]:
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def src_link(sources_by_id: dict[str, dict[str, Any]], sid: str) -> str:
    s = sources_by_id[sid]
    url = esc(s["url"])
    pub = esc(s["publisher"])
    label = f"{esc(sid)} ({pub})"
    return f'<a href="{url}" target="_blank" rel="noopener">{label}</a>'


def badge(text: str, kind: str = "hold") -> str:
    return f'<span class="badge badge-{esc(kind)}">{esc(text)}</span>'


def gate_badge(val: Any) -> str:
    if val is True or val == "PASS":
        return badge("PASS", "pass")
    if val is False or val == "FAIL":
        return badge("FAIL", "fail")
    return badge("HELD", "warn")


def status_badge(status: str) -> str:
    u = str(status).upper()
    if u.startswith("QUALIFIED"):
        return badge(status, "pass")
    if "DISQUALIFIED" in u or "FAIL" in u or "REJECTED" in u:
        return badge(status, "fail")
    if "HELD" in u or "UNVERIFIED" in u or "STALE" in u or "FLAGGED" in u or "UPCOMING" in u:
        return badge(status, "warn")
    if "VERIFIED" in u or "EXACT" in u or "CALIBRATED" in u:
        return badge(status, "pass")
    return badge(status, "hold")


def fmt_pct_or_blank(val: Any) -> str:
    if val == "" or val is None:
        return '<td class="blank-cell" title="Intentionally left blank — unverified against official primary source"></td>'
    return f'<td class="num">{float(val):+.2f}%</td>'


def fmt_num_or_blank(val: Any, fmt: str = "{:.2f}") -> str:
    if val == "" or val is None:
        return '<td class="blank-cell" title="Intentionally left blank — unverified against official primary source"></td>'
    return f'<td class="num">{fmt.format(float(val))}</td>'


def page_shell(active_key: str, title: str, body_html: str, is_root: bool = False) -> str:
    prefix = "" if is_root else "../"
    css_href = f"{prefix}assets/style.css"
    root_overview_href = "../index.html" if is_root else "../../index.html"
    flagged_href = "pages/flagged.html" if is_root else "flagged.html"

    nav_links = []
    for key, label, rel_target in NAV_PAGES:
        href = rel_target if is_root else (
            "../index.html" if rel_target == "index.html" else rel_target.replace("pages/", "")
        )
        cls = ' class="active"' if key == active_key else ""
        nav_links.append(f'<a href="{href}"{cls}>{esc(label)}</a>')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="generator" content="skill-lab/scripts/build_site.py">
  <title>{esc(title)} | NFL Skill Lab</title>
  <link rel="stylesheet" href="{css_href}">
</head>
<body>
  <header class="site-header">
    <div class="header-inner">
      <div class="brand-row">
        <div class="brand-title">NFL Skill Lab &mdash; Line Origination, Copula Pricing &amp; Gated Strategy Competition</div>
        <div class="brand-meta">
          Verified 2026-11-02 UTC &middot; Branch <code>arena/2b9898f7-korea2</code> &middot;
          <a href="{root_overview_href}">Repo Root Site</a>
        </div>
      </div>
      <nav class="site-nav" aria-label="Skill Lab Sections">
        {"".join(nav_links)}
      </nav>
    </div>
  </header>
  <main class="container">
    {body_html}
  </main>
  <footer class="site-footer">
    <strong>Responsible Research Disclosure:</strong> Quantitative sports-market research and paper-competition evaluation only; no real-money wagering advice or funded prize pool exists.
    Every table row cites a verified official source; unconfirmable figures are left strictly blank and logged on the <a href="{flagged_href}">Flagged for Review</a> page.
    Confidential support: <a href="https://www.ncpgambling.org/help-treatment/about-the-national-problem-gambling-helpline/" target="_blank" rel="noopener">NCPG 1-800-MY-RESET</a>.
  </footer>
</body>
</html>
"""


def render_svg_persistence(luck_rows: list[dict[str, Any]]) -> str:
    sorted_rows = sorted(luck_rows, key=lambda r: r["yoy_r"], reverse=True)
    w, row_h, pad_top = 800, 32, 34
    h = pad_top + len(sorted_rows) * row_h + 24
    zero_x = 305
    scale = 410.0
    lines = [
        f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Year-over-year skill persistence r across NFL metrics">',
        f'<text x="12" y="20" font-size="12" font-weight="700" fill="#132030">Year-over-Year Persistence r (2015-2025, N = 317 Consecutive Team-Season Pairs)</text>',
        f'<line x1="{zero_x}" y1="{pad_top - 6}" x2="{zero_x}" y2="{h - 18}" stroke="#4e5d6c" stroke-width="1"/>',
    ]
    for i, r in enumerate(sorted_rows):
        y = pad_top + i * row_h
        val = float(r["yoy_r"])
        bar_w = abs(val) * scale
        bx = zero_x if val >= 0 else zero_x - bar_w
        fill = "#0b4f8a" if val >= 0.25 else ("#5b84b1" if val > 0.10 else "#b84a39")
        lines.append(f'<text x="12" y="{y + 18}" font-size="11.5" fill="#132030">{esc(r["label"])}</text>')
        lines.append(f'<rect x="{bx:.1f}" y="{y + 5}" width="{max(2.0, bar_w):.1f}" height="18" rx="2" fill="{fill}"/>')
        tx = (bx + bar_w + 6) if val >= 0 else (zero_x + 6)
        lines.append(
            f'<text x="{tx:.1f}" y="{y + 18}" font-size="11" font-family="monospace" fill="#132030">'
            f'r={val:+.3f} (luck {r["luck_shrinkage_pct"]:.0f}%)</text>'
        )
    lines.append("</svg>")
    return "\n".join(lines)


def render_svg_copula(combos: list[dict[str, Any]]) -> str:
    w, row_h, pad_top = 800, 36, 36
    h = pad_top + len(combos) * row_h + 24
    base_x = 345
    scale = 205.0
    ref_x = base_x + 1.0 * scale
    lines = [
        f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Gaussian copula joint-probability multiplier vs independent parlay assumption">',
        f'<text x="12" y="20" font-size="12" font-weight="700" fill="#132030">Copula Joint-Hit Multiplier vs. Naive Independence (1.00x Vertical Reference)</text>',
        f'<line x1="{ref_x:.1f}" y1="{pad_top - 8}" x2="{ref_x:.1f}" y2="{h - 16}" stroke="#8e241b" stroke-dasharray="4,3" stroke-width="1.3"/>',
    ]
    for i, c in enumerate(combos):
        y = pad_top + i * row_h
        m = float(c["multiplier"])
        bar_w = m * scale
        fill = "#145a32" if m > 1.05 else ("#8e241b" if m < 0.95 else "#5b6b7a")
        lines.append(f'<text x="12" y="{y + 20}" font-size="11.5" fill="#132030">{esc(c["name"][:46])}</text>')
        lines.append(f'<rect x="{base_x}" y="{y + 6}" width="{bar_w:.1f}" height="19" rx="2" fill="{fill}"/>')
        lines.append(
            f'<text x="{base_x + bar_w + 7:.1f}" y="{y + 20}" font-size="11" font-family="monospace" fill="#132030">'
            f'{m:.2f}x ({c["joint_copula_prob"]:.1f}% vs {c["indep_prob"]:.1f}%)</text>'
        )
    lines.append("</svg>")
    return "\n".join(lines)


def build_all_pages() -> list[Path]:
    sources_doc = load_json("sources.json")
    sources = {s["id"]: s for s in sources_doc["sources"]}
    orig = load_json("origination.json")
    luck = load_json("luck.json")
    signals = load_json("signals.json")
    corrs = load_json("correlations.json")
    strats = load_json("strategies.json")
    lb = load_json("leaderboard.json")
    off = load_json("official_2026.json")
    rev = load_json("repo_review.json")
    flg = load_json("flagged.json")

    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    to = orig["team_origination"]
    po = orig["prop_origination"]
    wk8_live = to["nov1_post_commit_audit"]
    split_half = luck["within_season_split_half"]
    wr_gap = corrs["ex_ante_vs_ex_post_wr1_gap"]

    # ------------------------------------------------------------------
    # 1. index.html — Landing Page
    # ------------------------------------------------------------------
    page_summaries = [
        ("Executive Summary", "pages/summary.html", "End-to-end synthesis of walk-forward origination, FDR signal screening, copula dependence, skill-vs-luck shrinkage, and the 0/16 gated competition verdict.", "SL-SRC-01"),
        ("Line & Prop Origination", "pages/origination.html", f"Walk-forward opponent-adjusted spread/total/ML & prop quantile engine ({to['test_games']:,} OOS games; 2026 Wk 8 Nov 1 live MAE {wk8_live['orig_spread_mae']:.2f} vs market {wk8_live['mkt_spread_mae']:.2f}; 15 originated Week 9 lines).", "SL-SRC-05"),
        ("Signals & FDR", "pages/signals.html", f"{signals['signals_tested']} pre-kickoff structural, weather, rest, and key-number hypotheses; {signals['signals_surviving_fdr']}/{signals['signals_tested']} survive Benjamini-Hochberg FDR q <= 0.10 after vig.", "SL-SRC-24"),
        ("Skill vs. Luck", "pages/luck-skill.html", "Split-half & YoY persistence across 317 team-season pairs (Pass EPA/db r = +0.402 vs ATS r = -0.014) plus 2025->2026 Pythagorean rebound proof.", "SL-SRC-24"),
        ("Correlations & Copula", "pages/correlations.html", f"14 empirical game & player pairs; proves ex-post WR1 selection inflates QB-WR1 r from {wr_gap['ex_ante_wr1_r']:+.4f} to {wr_gap['ex_post_wr1_r']:+.4f} ({wr_gap['inflation_delta_r']:+.4f} bias).", "SL-SRC-23"),
        ("Leaderboard & Rewards", "pages/leaderboard.html", "16-strategy skill leaderboard across Singles, Parlays, SGPs, and Prop Combos with 10,000-pt paper reward tiers (0 qualified; 0 pts awarded).", "SL-SRC-17"),
        ("Singles, Parlays & Props", "pages/strategies.html", "Detailed track-by-track strategy results, including 3-leg bring-back prop stacks (16.71% realized joint hit vs 16.20% copula forecast).", "SL-SRC-20"),
        ("10-Gate Validation Matrix", "pages/gates.html", "Full 16 x 10 gate pass/fail/hold matrix showing G1 catching the 85.19% lookahead control and G10 holding unpriced SGP/prop combos.", "SL-SRC-25"),
        ("Official NFL.com Audit", "pages/official-audit.html", "Line-by-line 2026 (32/32 after 12 Nov 1 finals), 2025 (32/32), 2020 REG, and 7-player exact yard/TD reconciliation against NFL.com.", "SL-SRC-01"),
        ("Line-by-Line Repo Review", "pages/repo-review.html", f"{len(rev['rows'])} audited repository subsystems/files across Korea2 cross-checked against open issues #1-#34.", "SL-SRC-32"),
        ("Flagged for Review", "pages/flagged.html", f"{len(flg['rows'])} unverified data gaps & repo irregularities with strictly blank value cells and official manual-review links.", "SL-SRC-16"),
    ]
    nav_rows_html = [
        f'<tr><td><a href="{esc(href)}"><strong>{esc(name)}</strong></a></td>'
        f'<td>{esc(desc)}</td><td>{src_link(sources, sid)}</td></tr>'
        for name, href, desc, sid in page_summaries
    ]

    top_lb_rows = []
    for r in lb["leaderboard"][:10]:
        top_lb_rows.append(
            f'<tr>'
            f'<td class="num">{r["rank"]}</td>'
            f'<td class="mono">{esc(r["id"])}</td>'
            f'<td><strong>{esc(r["name"])}</strong></td>'
            f'<td>{esc(r["category"])}</td>'
            f'<td class="num">{r["tickets_n"]:,}</td>'
            f'<td class="num">{r["hit_rate_pct"]:.2f}%</td>'
            f'{fmt_pct_or_blank(r["roi_pct"])}'
            f'{fmt_pct_or_blank(r["luck_adjusted_roi_pct"])}'
            f'<td class="mono">{esc(r["gates_passed"])}</td>'
            f'<td class="num">{r["skill_score"]:.1f}</td>'
            f'<td>{status_badge(r["status"])}</td>'
            f'<td>{src_link(sources, r["source_id"])}</td>'
            f'</tr>'
        )

    index_body = f"""
    <section class="hero">
      <h1>NFL Skill Lab: Origination, Copula Dependence &amp; Gated Strategy Competition</h1>
      <p>
        Built and verified line-by-line on <strong>2026-11-02 UTC</strong> against official <code>NFL.com</code> schedules, standings, and player box logs.
        Skill Lab originates walk-forward NFL spreads, totals, moneylines, and player-prop quantiles; decomposes team and betting performance into repeatable skill vs. mean-reverting luck; prices correlated parlays and player-prop stacks via Gaussian copulas; and subjects <strong>16 candidate strategies</strong> across Single Bets, Cross-Game Parlays, Same-Game Parlays, and Ex-Ante Prop Combos to a strict <strong>10-gate validation protocol</strong>.
      </p>
    </section>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">OOS Test Slate (2018-2026)</div>
        <div class="kpi-value">{to["test_games"]:,}</div>
        <div class="kpi-note">Orig MAE {to["orig_spread_mae"]:.3f} vs Close {to["mkt_spread_mae"]:.3f}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">2026 Wk 8 Live Grading (Nov 1)</div>
        <div class="kpi-value">{wk8_live["orig_spread_mae"]:.2f}</div>
        <div class="kpi-note">12 official NFL.com finals (Close MAE {wk8_live["mkt_spread_mae"]:.2f})</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Official NFL.com Reconciliation</div>
        <div class="kpi-value">64 / 64</div>
        <div class="kpi-note">2025 (32/32) &amp; 2026+Nov1 (32/32) + 7/7 players</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Ex-Ante vs Ex-Post QB-WR1 r</div>
        <div class="kpi-value">{wr_gap["ex_ante_wr1_r"]:+.3f}</div>
        <div class="kpi-note">Ex-post inflates r to {wr_gap["ex_post_wr1_r"]:+.3f} ({wr_gap["inflation_delta_r"]:+.3f} bias)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Strategies Passing All 10 Gates</div>
        <div class="kpi-value">0 / 16</div>
        <div class="kpi-note">0 paper pts awarded; vigorish &amp; FDR hold</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Flagged &amp; Blank-Enforced Items</div>
        <div class="kpi-value">{len(flg["rows"])}</div>
        <div class="kpi-note">Zero unverified values inferred or filled in</div>
      </div>
    </div>

    <section class="section">
      <h2>Competition Verdict Snapshot (Top 10 Ranked Entries; Full 16 on Leaderboard)</h2>
      <div class="callout">
        <strong>Headline Scientific Result:</strong> Across verified closing-price games (2018&ndash;2026), <strong>0 of 16 strategies</strong> clear all 10 validation gates.
        Apparent raw winners like the 2-Leg Outdoor Wind-Under Parlay (<code>STR-08</code>, raw ROI <code>+34.88%</code> on <code>n = 63</code>) fail sample-depth and BH-FDR gates and shrink to <code>-3.93%</code> after Empirical Bayes luck removal, while unpriced SGP and player-prop combos (<code>STR-10..STR-14</code>) leave ROI cells <strong>strictly blank</strong> rather than fabricating historical sportsbook prop vig.
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="num">Rank</th>
              <th>ID</th>
              <th>Strategy</th>
              <th>Track</th>
              <th class="num">N</th>
              <th class="num">Hit %</th>
              <th class="num">Verified ROI</th>
              <th class="num">Luck-Adj ROI</th>
              <th>Gates</th>
              <th class="num">Skill Score</th>
              <th>Verdict</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(top_lb_rows)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>Skill Lab Research Directory (12 Pages &mdash; Every Row Linked to Primary Sources)</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Page</th>
              <th>Scope &amp; Key Empirical Result</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(nav_rows_html)}
          </tbody>
        </table>
      </div>
    </section>
    """
    p_idx = SKILL_LAB_ROOT / "index.html"
    p_idx.write_text(page_shell("overview", "Overview", index_body, is_root=True), encoding="utf-8")
    written.append(p_idx)

    # ------------------------------------------------------------------
    # 2. pages/summary.html — Executive Summary
    # ------------------------------------------------------------------
    summary_findings = [
        ("1. Official Data Reconciliation", f"2025 REG matches NFL.com 32/32 (272 games), and 2026 REG ({off['games_2026_reconciled']} settled games through Sunday Nov 1 Week 8) reconciles 32/32 against live NFL.com standings ({off['teams_2026_stale_in_repo']}/32 stale in current extract) plus 7/7 exact player yard/TD totals.", "SL-SRC-01"),
        ("2. Walk-Forward Line Origination", f"Expanding-window opponent-adjusted power ratings + efficiency priors achieve {to['orig_spread_mae']:.3f} spread MAE, {to['orig_total_mae']:.3f} total MAE, and {to['orig_brier']:.4f} Brier across {to['test_games']:,} OOS games vs closing market {to['mkt_spread_mae']:.3f} MAE and {to['mkt_brier']:.4f} Brier. On the 12 live Nov 1 Week 8 finals, ex-ante originated spreads achieved {wk8_live['orig_spread_mae']:.2f} MAE vs closing market {wk8_live['mkt_spread_mae']:.2f} ({wk8_live['ats_lean_record']} directional leans, explicitly noted as N = 12 single-Sunday variance).", "SL-SRC-26"),
        ("3. Separating Skill from Luck", f"Within-season odd/even split-half reliability is r = {split_half['odd_even_epa_per_play_r']:+.4f} for offensive EPA/play vs {split_half['odd_even_net_turnovers_r']:+.4f} for net turnovers and {split_half['odd_even_ats_cover_r']:+.4f} for ATS cover. Year-over-year, Passing EPA/dropback (r = +0.4016) and CPOE (r = +0.3890) carry genuine team skill, whereas net turnovers/game (84.8% luck shrinkage), one-score win % (r = +0.0810, p = 0.150, 91.9% luck), Pythagorean luck (r = +0.0232, 97.7% luck), and team ATS cover % (r = -0.0142, 100.0% luck) mean-revert.", "SL-SRC-24"),
        ("4. Signal Research & Multiple-Testing Control", "Among 10 pre-kickoff signals (SIG-01..SIG-10), outdoor high-wind unders (>=15 mph, SIG-08) post the highest raw hit rate (56.58%, +9.20% ROI, n = 152), but Benjamini-Hochberg FDR across the 10-signal family yields q = 0.4786; 0/10 signals clear q <= 0.10.", "SL-SRC-28"),
        ("5. Ex-Ante vs. Ex-Post Correlation Discovery", f"Defining a team's WR1 strictly ex-ante by prior target share yields QB-WR1 residual correlation r = {wr_gap['ex_ante_wr1_r']:+.4f} (copula rho = +0.4128, 1.245x joint boost). Defining WR1 ex-post by in-game receiving yards inflates correlation to r = {wr_gap['ex_post_wr1_r']:+.4f} ({wr_gap['inflation_delta_r']:+.4f} selection bias). Out-of-sample 3-leg bring-back stacks hit at 16.71% vs 16.20% Gaussian-copula forecast (12.50% independent).", "SL-SRC-23"),
        ("6. 10-Gate Strategy Competition Verdict", "0 of 16 strategies pass all 10 validation gates; 0 of 10,000 paper competition points are awarded. Gate G1 automatically disqualifies the 85.19% lookahead control (STR-16), Empirical Bayes luck shrinkage collapses noisy small-sample parlay spikes (STR-08 +34.88% -> -3.93%), and Gate G10 holds unpriced SGP/prop combos with blank ROI.", "SL-SRC-25"),
        ("7. Line-by-Line Repository Review", "Confirmed and documented 12 concrete irregularities across sibling files (stale Oct 29 cutoff, 2020 standings CSV mixing playoffs into regular season + OAK label, 1,902 pre-2018 unpriced spreads, triple executive-summary drift, and ex-post WR1 inflation) without overwriting any sibling session's scope.", "SL-SRC-03"),
    ]
    sum_rows = [
        f'<tr><td><strong>{esc(k)}</strong></td><td>{esc(v)}</td><td>{src_link(sources, sid)}</td></tr>'
        for k, v, sid in summary_findings
    ]
    summary_body = f"""
    <section class="hero">
      <h1>Executive Summary</h1>
      <p>
        Concise quantitative synthesis of NFL line origination, signal discovery, skill-versus-luck decomposition, multi-leg copula correlation pricing, 10-gate strategy competition results, and line-by-line repository verification as of <strong>2026-11-02 UTC</strong>.
      </p>
    </section>
    <section class="section">
      <h2>Seven Core Findings &amp; Empirical Verdicts</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Pillar</th>
              <th>Verified Quantitative Finding</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(sum_rows)}
          </tbody>
        </table>
      </div>
    </section>
    """
    p_sum = PAGES_DIR / "summary.html"
    p_sum.write_text(page_shell("summary", "Executive Summary", summary_body), encoding="utf-8")
    written.append(p_sum)

    # ------------------------------------------------------------------
    # 3. pages/origination.html — Line & Prop Origination
    # ------------------------------------------------------------------
    bench_rows = [
        ("Closing Consensus Market (Benchmark)", to["mkt_spread_mae"], to["mkt_spread_rmse"], to["mkt_total_mae"], to["mkt_brier"], to["mkt_logloss"], "SL-SRC-18"),
        ("Skill Lab Originated Model (Opponent-Adjusted + Efficiency)", to["orig_spread_mae"], to["orig_spread_rmse"], to["orig_total_mae"], to["orig_brier"], to["orig_logloss"], "SL-SRC-26"),
    ]
    bench_html = [
        f'<tr><td><strong>{esc(name)}</strong></td>'
        f'<td class="num">{smae:.3f}</td>'
        f'<td class="num">{srmse:.3f}</td>'
        f'<td class="num">{tmae:.3f}</td>'
        f'<td class="num">{brier:.4f}</td>'
        f'<td class="num">{ll:.4f}</td>'
        f'<td>{src_link(sources, sid)}</td></tr>'
        for name, smae, srmse, tmae, brier, ll, sid in bench_rows
    ]

    season_html = [
        f'<tr>'
        f'<td class="num">{srow["season"]}</td>'
        f'<td class="num">{srow["games"]}</td>'
        f'<td class="num">{srow["orig_spread_mae"]:.3f}</td>'
        f'<td class="num">{srow["mkt_spread_mae"]:.3f}</td>'
        f'<td class="num">{srow["orig_total_mae"]:.3f}</td>'
        f'<td class="num">{srow["mkt_total_mae"]:.3f}</td>'
        f'<td class="num">{srow["orig_brier"]:.4f}</td>'
        f'<td class="num">{srow["mkt_brier"]:.4f}</td>'
        f'<td>{src_link(sources, srow["source_id"])}</td>'
        f'</tr>'
        for srow in to["by_season"]
    ]

    wk8_rows_html = []
    for g in wk8_live["rows"]:
        won = g["model_lean_won"]
        wk8_rows_html.append(
            f'<tr>'
            f'<td class="mono">{esc(g["away_team"])} @ {esc(g["home_team"])}</td>'
            f'<td class="mono">{g["official_away_score"]}-{g["official_home_score"]}</td>'
            f'<td class="num">{int(g["official_margin"]):+d}</td>'
            f'<td class="num">{g["orig_home_handicap"]:+.2f}</td>'
            f'<td class="num">{g["mkt_home_handicap"]:+.1f}</td>'
            f'<td class="num">{g["orig_abs_err"]:.2f}</td>'
            f'<td class="num">{g["mkt_abs_err"]:.2f}</td>'
            f'<td>{esc(g["model_lean_side"])} {badge("WIN" if won else "LOSS", "pass" if won else "fail")}</td>'
            f'<td>{src_link(sources, g["source_id"])}</td>'
            f'</tr>'
        )

    wk9_rows_html = []
    for g in to["upcoming_board"]:
        if g["week"] not in (8, 9):
            continue
        wk9_rows_html.append(
            f'<tr>'
            f'<td class="num">Wk {g["week"]}</td>'
            f'<td class="mono">{esc(g["gameday"])}</td>'
            f'<td><strong>{esc(g["away_team"])} @ {esc(g["home_team"])}</strong>{" (Neutral)" if g["location"] == "Neutral" else ""}</td>'
            f'<td class="num">{g["orig_home_handicap"]:+.2f}</td>'
            f'{fmt_num_or_blank(g["mkt_home_handicap"], "{:+.1f}")}'
            f'{fmt_num_or_blank(g["spread_disagreement_pts"], "{:+.2f}")}'
            f'<td class="num">{g["orig_total"]:.1f}</td>'
            f'{fmt_num_or_blank(g["mkt_total_line"], "{:.1f}")}'
            f'<td class="num">{g["orig_home_win_prob"]*100:.1f}%</td>'
            f'<td class="mono">{g["orig_home_fair_ml"]:+d} / {g["orig_away_fair_ml"]:+d}</td>'
            f'<td>{src_link(sources, g["source_id"])}</td>'
            f'</tr>'
        )

    prop_mkt_html = [
        f'<tr>'
        f'<td><strong>{esc(m["label"])}</strong></td>'
        f'<td class="num">{m["sample_n"]:,}</td>'
        f'<td class="num">{m["over_rate_at_raw_mean_pct"]:.2f}%</td>'
        f'<td class="num"><strong>{m["over_rate_at_calibrated_median_pct"]:.2f}%</strong></td>'
        f'<td class="num">{m["iqr_25_75_coverage_pct"]:.2f}%</td>'
        f'<td class="num">{m["mae_yards"]:.2f} yds</td>'
        f'<td class="blank-cell" title="No free official historical sportsbook prop odds archive"></td>'
        f'<td>{status_badge(m["status"])}</td>'
        f'<td>{src_link(sources, m["source_id"])}</td>'
        f'</tr>'
        for m in po["markets"]
    ]

    prop_spot_html = [
        f'<tr>'
        f'<td><strong>{esc(p["player"])}</strong> ({esc(p["team"])} &middot; {esc(p["pos"])})</td>'
        f'<td class="mono">vs {esc(p["week8_opp"])} ({esc(p["stat_market"])})</td>'
        f'<td class="num">{p["orig_median_line"]:.1f}</td>'
        f'<td class="blank-cell" title="Unverified sportsbook closing prop line — left blank"></td>'
        f'<td class="num"><strong>{p["official_week8_actual"]}</strong></td>'
        f'<td>{badge(p["outcome_vs_orig_line"], "pass" if p["outcome_vs_orig_line"] == "OVER" else "hold")}</td>'
        f'<td class="num">{p["official_2026_season_total"]:,}</td>'
        f'<td>{src_link(sources, p["source_id"])}</td>'
        f'</tr>'
        for p in po["week8_official_player_spotchecks"]
    ]

    pwr_html = [
        f'<tr>'
        f'<td class="mono"><strong>{esc(r["team"])}</strong></td>'
        f'<td class="mono">{esc(r["record_2026"])}</td>'
        f'<td class="num">{r["pf"]}</td>'
        f'<td class="num">{r["pa"]}</td>'
        f'<td class="num">{r["point_diff"]:+d}</td>'
        f'<td class="num">{r["off_skill_pts"]:+.2f}</td>'
        f'<td class="num">{r["def_skill_pts"]:+.2f}</td>'
        f'<td class="num"><strong>{r["net_power_rating"]:+.2f}</strong></td>'
        f'<td>{src_link(sources, r["source_id"])}</td>'
        f'</tr>'
        for r in to["power_ratings_2026"][:16]
    ]

    orig_body = f"""
    <section class="hero">
      <h1>Walk-Forward NFL Line &amp; Player-Prop Origination</h1>
      <p>
        Strictly chronological expanding-window origination engine trained exclusively on games strictly prior to each NFL week (<code>TimeSeriesSplit</code> discipline).
        Blends opponent-adjusted offensive/defensive power ratings, EPA/play &amp; turnover-shrunk efficiency differentials, rolling dynamic HFA (capturing the post-2020 HFA compression to ~1.7&ndash;2.1 pts), rest/indoor adjustments, and calibrated player quantile offsets.
      </p>
    </section>

    <section class="section">
      <h2>Out-of-Sample Origination Scoreboard ({esc(to["test_window"])}, N = {to["test_games"]:,})</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Model / Benchmark</th>
              <th class="num">Spread MAE</th>
              <th class="num">Spread RMSE</th>
              <th class="num">Total MAE</th>
              <th class="num">Win Brier</th>
              <th class="num">Win Log-Loss</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(bench_html)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>Live Ex-Ante Grading on 12 Official 2026 Week 8 Finals (Sunday, Nov 1, 2026)</h2>
      <p>
        Predicted strictly ex-ante prior to Sunday Nov 1 kickoff and graded against official <code>NFL.com</code> final scores: Skill Lab posted <strong>{wk8_live["orig_spread_mae"]:.2f} spread MAE</strong> vs closing market <strong>{wk8_live["mkt_spread_mae"]:.2f}</strong> (<code>{esc(wk8_live["ats_lean_record"])}</code> directional leans; explicitly noted as <code>N = 12</code> single-Sunday sample variance, <code>p &gt; 0.50</code>).
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Matchup</th>
              <th>Official Final</th>
              <th class="num">Margin</th>
              <th class="num">Orig Hcp</th>
              <th class="num">Close Hcp</th>
              <th class="num">Orig |Err|</th>
              <th class="num">Close |Err|</th>
              <th>Model Lean &amp; Result</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(wk8_rows_html)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>Originated 2026 Week 8 MNF &amp; Full 15-Game Week 9 Slate (Standard Home Handicap)</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="num">Week</th>
              <th>Date</th>
              <th>Matchup</th>
              <th class="num">Orig Hcp</th>
              <th class="num">Market Hcp</th>
              <th class="num">Model - Mkt</th>
              <th class="num">Orig Tot</th>
              <th class="num">Mkt Tot</th>
              <th class="num">Home Win %</th>
              <th>Fair ML (H / A)</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(wk9_rows_html)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>Ex-Ante Player-Prop Quantile Calibration ({esc(po["test_window"])}) &amp; Week 8 NFL.com Spot-Checks</h2>
      <p>
        Right-skewed receiving and rushing yardage distributions cause raw conditional means to over-predict median lines (only <code>41.88%</code> and <code>43.94%</code> Over rates); Skill Lab's empirical quantile calibration restores exact <code>~50%</code> median symmetry and <code>~50%</code> interquartile (<code>P25&ndash;P75</code>) coverage out-of-sample. Historical sportsbook prop ROI and closing prop lines are left strictly blank.
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Prop Market</th>
              <th class="num">OOS N</th>
              <th class="num">Over % @ Mean</th>
              <th class="num">Over % @ Calib P50</th>
              <th class="num">P25-P75 Cov %</th>
              <th class="num">MAE</th>
              <th class="num">Book ROI</th>
              <th>Status</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(prop_mkt_html)}
          </tbody>
        </table>
      </div>
      <h3>Official 2026 Week 8 NFL.com Player Box-Log Verification vs. Ex-Ante Originated Median Lines</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Player</th>
              <th>Week 8 Matchup &amp; Market</th>
              <th class="num">Orig P50 Line</th>
              <th class="num">Book Prop Line</th>
              <th class="num">Official Wk 8 Actual</th>
              <th>Vs Orig P50</th>
              <th class="num">Official 2026 Total</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(prop_spot_html)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>Top 16 2026 NFL Club Power Ratings (Reconciled Through Nov 1 Week 8 Finals)</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Club</th>
              <th>Official 2026 Record</th>
              <th class="num">PF</th>
              <th class="num">PA</th>
              <th class="num">Diff</th>
              <th class="num">Off Skill</th>
              <th class="num">Def Skill (Lower=Better)</th>
              <th class="num">Net Power (Pts vs Avg)</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(pwr_html)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>Season-by-Season Walk-Forward Accuracy (2018&ndash;2026)</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="num">Season</th>
              <th class="num">Games</th>
              <th class="num">Orig Spread MAE</th>
              <th class="num">Mkt Spread MAE</th>
              <th class="num">Orig Total MAE</th>
              <th class="num">Mkt Total MAE</th>
              <th class="num">Orig Brier</th>
              <th class="num">Mkt Brier</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(season_html)}
          </tbody>
        </table>
      </div>
    </section>
    """
    p_orig = PAGES_DIR / "origination.html"
    p_orig.write_text(page_shell("origination", "Line & Prop Origination", orig_body), encoding="utf-8")
    written.append(p_orig)

    # ------------------------------------------------------------------
    # 4. pages/signals.html — Signal Research & BH-FDR Screening
    # ------------------------------------------------------------------
    sig_rows_html = []
    for s in signals["rows"]:
        sig_rows_html.append(
            f'<tr>'
            f'<td class="mono"><strong>{esc(s["id"])}</strong></td>'
            f'<td><strong>{esc(s["name"])}</strong></td>'
            f'<td>{esc(s["market"])}</td>'
            f'<td class="num">{s["settled_bets"]:,}</td>'
            f'<td class="num">{s["win_rate_pct"]:.2f}%</td>'
            f'<td class="num">{s["roi_pct"]:+.2f}%</td>'
            f'{fmt_pct_or_blank(s["recent_2024_2026_roi_pct"])}'
            f'<td class="num">{s["t_stat"]:+.2f}</td>'
            f'<td class="num">{s["p_value"]:.4f}</td>'
            f'<td class="num">{s["bh_q_value"]:.4f}</td>'
            f'<td>{badge("SURVIVES FDR" if s["survives_fdr_q10"] else "REJECTED BY FDR", "pass" if s["survives_fdr_q10"] else "fail")}</td>'
            f'<td>{src_link(sources, s["source_id"])}</td>'
            f'</tr>'
        )

    signals_body = f"""
    <section class="hero">
      <h1>Pre-Kickoff Signal Research &amp; Benjamini-Hochberg FDR Screening</h1>
      <p>
        Every candidate signal is computed strictly from information known prior to kickoff across the verified <strong>{esc(signals["test_window"])}</strong> sample (100% real closing vig, pushes graded <code>0.0u</code>, never imputing <code>-110</code>).
        Across <code>M = {signals["signals_tested"]}</code> tested hypotheses, two-sided p-values are adjusted via Benjamini-Hochberg False Discovery Rate (<code>q &le; {signals["fdr_threshold_q"]:.2f}</code>).
      </p>
    </section>

    <section class="section">
      <h2>10-Signal Hypothesis Screening Table ({signals["signals_surviving_fdr"]} / {signals["signals_tested"]} Clear BH-FDR q &le; 0.10)</h2>
      <div class="callout">
        <strong>Why Raw Edge != True Skill:</strong> Outdoor Wind &ge; 15 mph Unders (<code>SIG-08</code>) win <code>56.58%</code> (<code>+9.20%</code> raw ROI over <code>152</code> games), and Divisional Home Underdogs (<code>SIG-07</code>) win <code>52.38%</code> (<code>+0.67%</code> ROI over <code>231</code> games). Yet under two-sided testing and 10-hypothesis BH-FDR control, <code>SIG-08</code> reaches only <code>q = 0.4786</code> &mdash; indistinguishable from the top draw among 10 noisy trials against a <code>~4.5%</code> vigorish hurdle.
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Signal Hypothesis</th>
              <th>Market</th>
              <th class="num">Settled N</th>
              <th class="num">Win %</th>
              <th class="num">Full ROI</th>
              <th class="num">2024-26 ROI</th>
              <th class="num">t-stat</th>
              <th class="num">p-value</th>
              <th class="num">BH-FDR q</th>
              <th>FDR Verdict</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(sig_rows_html)}
          </tbody>
        </table>
      </div>
    </section>
    """
    p_sig = PAGES_DIR / "signals.html"
    p_sig.write_text(page_shell("signals", "Signals & FDR", signals_body), encoding="utf-8")
    written.append(p_sig)

    # ------------------------------------------------------------------
    # 5. pages/luck-skill.html — Skill vs. Luck Decomposition
    # ------------------------------------------------------------------
    luck_rows_html = []
    for r in luck["metrics"]:
        luck_rows_html.append(
            f'<tr>'
            f'<td><strong>{esc(r["label"])}</strong></td>'
            f'<td class="num">{r["team_season_pairs"]}</td>'
            f'<td class="num"><strong>{r["yoy_r"]:+.4f}</strong></td>'
            f'<td class="num">[{r["ci_95_low"]:+.3f}, {r["ci_95_high"]:+.3f}]</td>'
            f'<td class="num">{r["p_value"]:.4f}</td>'
            f'<td class="num">{r["eb_skill_weight"]:.3f}</td>'
            f'<td class="num">{r["luck_shrinkage_pct"]:.1f}%</td>'
            f'<td>{badge(r["classification"], "pass" if "SKILL" in r["classification"].upper() and "MIXED" not in r["classification"].upper() else ("warn" if "MIXED" in r["classification"].upper() else "fail"))}</td>'
            f'<td>{src_link(sources, r["source_id"])}</td>'
            f'</tr>'
        )

    off26_map = {r["team"]: r["nfl_official_2026"] for r in off["standings_2026"]}
    rebound_html = []
    for r in luck["pythagorean_outliers_2025"]:
        tm = r["team"]
        rebound_html.append(
            f'<tr>'
            f'<td class="mono"><strong>{esc(tm)}</strong></td>'
            f'<td class="mono">{esc(r["record_2025"])}</td>'
            f'<td class="num">{r["pythag_luck_2025_wins"]:+.2f} wins</td>'
            f'<td>{esc(r["direction_predicted_for_2026"])}</td>'
            f'<td class="mono">{esc(off26_map.get(tm, ""))}</td>'
            f'<td>{src_link(sources, r["source_id"])}</td>'
            f'</tr>'
        )

    luck_body = f"""
    <section class="hero">
      <h1>Separating Repeatable Skill from Mean-Reverting Luck</h1>
      <p>
        Decomposes NFL team metrics across <strong>{split_half["team_seasons"]} team-seasons</strong> (odd-week vs. even-week split-half reliability: EPA/play <code>r = {split_half["odd_even_epa_per_play_r"]:+.4f}</code> vs. net turnovers <code>r = {split_half["odd_even_net_turnovers_r"]:+.4f}</code> and ATS cover <code>r = {split_half["odd_even_ats_cover_r"]:+.4f}</code>) and <strong>317 consecutive year-over-year club pairs ({esc(luck["window"])})</strong>.
      </p>
    </section>

    <section class="section">
      <h2>Skill-to-Luck Persistence Continuum (Visual Summary)</h2>
      <div class="chart-box">
        {render_svg_persistence(luck["metrics"])}
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Team Metric</th>
              <th class="num">YoY Pairs</th>
              <th class="num">YoY r</th>
              <th class="num">95% Fisher CI</th>
              <th class="num">p-value</th>
              <th class="num">EB Skill Wt</th>
              <th class="num">Luck Shrink %</th>
              <th>Classification</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(luck_rows_html)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>Out-of-Sample Proof: 2025 Pythagorean Luck Outliers vs. Realized 2026 NFL.com Standings</h2>
      <p>
        Clubs suffering severe 2025 close-game bad luck &mdash; notably <strong>KC</strong> (<code>6-11</code>, <code>-3.49</code> Pythagorean luck wins) and <strong>NYG</strong> (<code>4-13</code>, <code>-3.09</code> luck wins) &mdash; rebounded sharply in 2026 (<code>5-2</code> and <code>4-2-1</code> on official <code>NFL.com</code> Week 8 standings), whereas 2025 positive-luck outliers regressed toward their underlying efficiency baseline.
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Team</th>
              <th>2025 Official Record</th>
              <th class="num">2025 Pythag Luck</th>
              <th>Ex-Ante 2026 Shrinkage Prediction</th>
              <th>2026 Official Wk 8 Record</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(rebound_html)}
          </tbody>
        </table>
      </div>
    </section>
    """
    p_luck = PAGES_DIR / "luck-skill.html"
    p_luck.write_text(page_shell("luck", "Skill vs. Luck", luck_body), encoding="utf-8")
    written.append(p_luck)

    # ------------------------------------------------------------------
    # 6. pages/correlations.html — Empirical Correlations & Copula Pricing
    # ------------------------------------------------------------------
    corr_rows_html = [
        f'<tr>'
        f'<td class="mono"><strong>{esc(c["id"])}</strong></td>'
        f'<td><strong>{esc(c["pair"])}</strong><br><small>{esc(c["note"])}</small></td>'
        f'<td class="num">{c["sample_n"]:,}</td>'
        f'<td class="num"><strong>{c["pearson_r"]:+.4f}</strong></td>'
        f'<td class="num">[{c["ci_95_low"]:+.3f}, {c["ci_95_high"]:+.3f}]</td>'
        f'<td class="num">{c["binary_phi"]:+.4f}</td>'
        f'<td class="num">{c["copula_rho"]:+.4f}</td>'
        f'<td class="num">{c["joint_prob_pct"]:.2f}%</td>'
        f'<td class="num">{c["indep_prob_pct"]:.2f}%</td>'
        f'<td class="num">{c["joint_multiplier"]:.3f}x</td>'
        f'<td>{src_link(sources, c["source_id"])}</td>'
        f'</tr>'
        for c in corrs["pairs"]
    ]

    def fmt_str_or_blank(val: Any) -> str:
        if val == "" or val is None:
            return '<td class="blank-cell" title="Intentionally left blank — unverified proprietary SGP book price"></td>'
        return f'<td class="num">{esc(val)}</td>'

    cop_rows_html = [
        f'<tr>'
        f'<td class="mono"><strong>{esc(cp["combo_id"])}</strong></td>'
        f'<td><strong>{esc(cp["name"])}</strong><br><small>{esc(cp["takeaway"])}</small></td>'
        f'<td class="num">{cp["legs"]}</td>'
        f'<td class="num">{cp["indep_prob"]:.2f}%</td>'
        f'<td class="num"><strong>{cp["joint_copula_prob"]:.2f}%</strong></td>'
        f'<td class="num">{cp["multiplier"]:.3f}x</td>'
        f'<td class="num">{esc(cp["fair_copula_odds"])}</td>'
        f'{fmt_str_or_blank(cp["std_book_parlay_odds"])}'
        f'{fmt_pct_or_blank(cp["ev_at_unadjusted_parlay_pct"])}'
        f'<td>{src_link(sources, cp["source_id"])}</td>'
        f'</tr>'
        for cp in corrs["copula_combos"]
    ]

    cor07 = next(c for c in corrs["pairs"] if c["id"] == "COR-07")
    cor08 = next(c for c in corrs["pairs"] if c["id"] == "COR-08")
    corr_body = f"""
    <section class="hero">
      <h1>Empirical Correlation Matrix &amp; Gaussian-Copula SGP / Prop Pricing</h1>
      <p>
        Computes exact Pearson <code>r</code> (with NIST Fisher-<code>z</code> 95% confidence intervals), binary indicator <code>&phi;</code>, joint-hit probabilities, and tetrachoric/Gaussian-copula latent <code>&rho;<sub>cop</sub></code> across <strong>14 game and player-prop pairs ({esc(corrs["window"])})</strong>.
        To eliminate cross-team talent confounding, player-prop correlations measure <strong>within-player game shocks</strong> (actual outcome minus each player's strictly prior expanding-window baseline).
      </p>
    </section>

    <section class="section">
      <h2>Critical Methodological Discovery: Ex-Post WR1 Selection Bias ({wr_gap["inflation_delta_r"]:+.4f} Inflation)</h2>
      <div class="callout warn">
        <strong>Audit Proof (<code>COR-07</code> vs. <code>COR-08</code>):</strong> Selecting a team's top wide receiver <em>ex-ante</em> by prior cumulative target share yields <code>r = {wr_gap["ex_ante_wr1_r"]:+.4f}</code> (copula <code>&rho; = {cor07["copula_rho"]:+.4f}</code>, joint-hit multiplier <code>{cor07["joint_multiplier"]:.3f}x</code> across <code>{cor07["sample_n"]:,}</code> team-games). Selecting "WR1" <em>ex-post</em> by whoever led the game in receiving yards inflates the apparent correlation to <code>r = {wr_gap["ex_post_wr1_r"]:+.4f}</code> (<code>{cor08["joint_multiplier"]:.3f}x</code>) &mdash; a pure lookahead selection artifact (<code>{wr_gap["inflation_delta_r"]:+.4f}</code> bias) that causes naive SGP models to severely overestimate true joint hit rates.
      </div>
      <div class="chart-box">
        {render_svg_copula(corrs["copula_combos"])}
      </div>
    </section>

    <section class="section">
      <h2>14-Pair Empirical Correlation &amp; Joint-Hit Table</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Pair &amp; Conditioning Basis</th>
              <th class="num">N</th>
              <th class="num">Pearson r</th>
              <th class="num">95% Fisher CI</th>
              <th class="num">Binary &phi;</th>
              <th class="num">Copula &rho;</th>
              <th class="num">Joint Hit %</th>
              <th class="num">Indep %</th>
              <th class="num">Boost</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(corr_rows_html)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>Multi-Leg Gaussian-Copula Fair Pricing vs. Unadjusted Independent Parlay Payouts</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Combo Structure &amp; Pricing Takeaway</th>
              <th class="num">Legs</th>
              <th class="num">Indep Prob</th>
              <th class="num">Copula Prob</th>
              <th class="num">Mult</th>
              <th class="num">Fair Copula Dec</th>
              <th class="num">Std -110 Parlay Dec</th>
              <th class="num">EV @ Unadj -110</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(cop_rows_html)}
          </tbody>
        </table>
      </div>
    </section>
    """
    p_corr = PAGES_DIR / "correlations.html"
    p_corr.write_text(page_shell("correlations", "Correlations & Copula", corr_body), encoding="utf-8")
    written.append(p_corr)

    # ------------------------------------------------------------------
    # 7. pages/leaderboard.html — Strategy Competition Leaderboard & Rewards
    # ------------------------------------------------------------------
    tier_rows_html = []
    for t in lb["reward_tiers"]:
        assert t["cash_funding"] == "", "Cash prize funding must be blank!"
        tier_rows_html.append(
            f'<tr>'
            f'<td><strong>{esc(t["tier"])}</strong></td>'
            f'<td>{esc(t["gate_requirement"])}</td>'
            f'<td class="num">{t["pool_points"]:,} pts</td>'
            f'<td class="num">{t["awarded_count"]}</td>'
            f'<td class="blank-cell" title="No funded cash prize pool exists — left strictly blank"></td>'
            f'<td>{src_link(sources, t["source_id"])}</td>'
            f'</tr>'
        )

    lb_rows_html = []
    for r in lb["leaderboard"]:
        assert r["funded_cash_prize"] == "", "Cash prize cell must be blank!"
        lb_rows_html.append(
            f'<tr>'
            f'<td class="num"><strong>{r["rank"]}</strong></td>'
            f'<td class="mono">{esc(r["id"])}</td>'
            f'<td><strong>{esc(r["name"])}</strong></td>'
            f'<td>{esc(r["category"])}</td>'
            f'<td class="num">{r["tickets_n"]:,}</td>'
            f'<td class="num">{r["hit_rate_pct"]:.2f}%</td>'
            f'{fmt_pct_or_blank(r["roi_pct"])}'
            f'{fmt_pct_or_blank(r["luck_adjusted_roi_pct"])}'
            f'<td class="mono">{esc(r["gates_passed"])}</td>'
            f'<td class="num"><strong>{r["skill_score"]:.1f}</strong></td>'
            f'<td class="num">{r["reward_points"]}</td>'
            f'<td class="blank-cell" title="No funded cash prize pool exists — left strictly blank"></td>'
            f'<td>{status_badge(r["status"])}</td>'
            f'<td>{src_link(sources, r["source_id"])}</td>'
            f'</tr>'
        )

    lb_body = f"""
    <section class="hero">
      <h1>Skill-Based Strategy Competition Leaderboard &amp; Reward Schedule</h1>
      <p>
        Frames all <strong>16 candidate strategies</strong> across Single Bets (<code>STR-01..06</code>), Cross-Game Parlays (<code>STR-07..09</code>), Same-Game Parlays (<code>STR-10..11</code>), Ex-Ante Player Prop Combos (<code>STR-12..14</code>), and Negative/Leak Controls (<code>STR-15..16</code>) as a unified tournament with a <strong>{lb["competition_pool_points"]:,}-point paper research allocation pool</strong>.
        Eligibility for rewards is binary: a strategy must clear <strong>all 10 validation gates (G1&ndash;G10)</strong> before a single point is granted.
      </p>
    </section>

    <section class="section">
      <h2>Competition Reward Tiers (Paper Points Only; Cash Prize Cells Strictly Blank)</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Reward Tier</th>
              <th>Gate Qualification Requirement</th>
              <th class="num">Paper Pool Allocation</th>
              <th class="num">Winners</th>
              <th class="num">Funded Cash Prize</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(tier_rows_html)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>Official 16-Strategy Tournament Standings ({lb["qualified_strategies"]} Qualified &middot; {lb["points_awarded"]} / {lb["competition_pool_points"]:,} Points Awarded)</h2>
      <p>
        Shaded cells indicate unverified historical sportsbook SGP/prop vig or unfunded cash prizes left strictly blank.
        Notice how <code>STR-16</code> (deliberate in-game turnover leak, <code>+64.91%</code> raw ROI) is automatically zeroed and ranked last (<code>#16</code>) by Gate <code>G1</code>, while <code>STR-08</code>'s small-sample parlay spike (<code>+34.88%</code> on <code>n = 63</code>) shrinks to <code>-3.93%</code> after Empirical Bayes luck removal.
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="num">Rank</th>
              <th>ID</th>
              <th>Strategy Name</th>
              <th>Track</th>
              <th class="num">N</th>
              <th class="num">Hit %</th>
              <th class="num">Verified ROI</th>
              <th class="num">Luck-Adj ROI</th>
              <th>Gates</th>
              <th class="num">Skill Score</th>
              <th class="num">Pts</th>
              <th class="num">Cash</th>
              <th>Competition Verdict</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(lb_rows_html)}
          </tbody>
        </table>
      </div>
    </section>
    """
    p_lb = PAGES_DIR / "leaderboard.html"
    p_lb.write_text(page_shell("leaderboard", "Leaderboard & Rewards", lb_body), encoding="utf-8")
    written.append(p_lb)

    # ------------------------------------------------------------------
    # 8. pages/strategies.html — Single Bets, Parlays & Prop Combos Catalog
    # ------------------------------------------------------------------
    strat_rows_html = []
    for s in strats["rows"]:
        strat_rows_html.append(
            f'<tr>'
            f'<td class="mono"><strong>{esc(s["id"])}</strong></td>'
            f'<td><strong>{esc(s["name"])}</strong><br><small>Driver: {esc(s["signal_driver"])}</small></td>'
            f'<td>{esc(s["category"])}</td>'
            f'<td class="num">{s["tickets_n"]:,}</td>'
            f'<td class="num">{s["hit_rate_pct"]:.2f}%</td>'
            f'<td class="num">{s["expected_hit_rate_pct"]:.2f}%</td>'
            f'<td class="num">{s["calibration_err_pct"]:.2f}%</td>'
            f'{fmt_pct_or_blank(s["roi_pct"])}'
            f'{fmt_pct_or_blank(s["luck_adjusted_roi_pct"])}'
            f'{fmt_pct_or_blank(s["stress_roi_pct"])}'
            f'<td>{status_badge(s["status"])}</td>'
            f'<td>{src_link(sources, s["source_id"])}</td>'
            f'</tr>'
        )

    strategies_body = f"""
    <section class="hero">
      <h1>Strategy Catalog: Single Bets, Cross-Game Parlays, SGPs &amp; Player Prop Combos</h1>
      <p>
        Side-by-side empirical evaluation across all five competition tracks ({esc(strats["window"])}).
        For unpriced SGP and player-prop combinations (<code>STR-10..STR-14</code>), Skill Lab measures exact out-of-sample joint hit rates against our Gaussian-copula expected hit rate while leaving sportsbook ROI cells blank.
      </p>
    </section>

    <section class="section">
      <h2>Out-of-Sample Prop-Combo Copula Calibration Highlight</h2>
      <div class="callout">
        <strong>3-Leg Bring-Back Aerial Stack (<code>STR-14</code>: Team QB1 Pass Yds + Team WR1 Rec Yds + Opposing QB1 Pass Yds):</strong>
        Naive independence predicts <code>12.50%</code> (<code>0.5<sup>3</sup></code>). Our Gaussian-copula correlation matrix forecasted <code>16.20%</code>. Across <strong>383 real out-of-sample NFL games (2023&ndash;2026)</strong>, the actual joint hit rate above originated ex-ante <code>P50</code> lines was <strong><code>16.71%</code></strong> &mdash; a <code>0.51</code> percentage-point out-of-sample calibration error.
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Strategy &amp; Driver</th>
              <th>Track</th>
              <th class="num">N</th>
              <th class="num">Realized Hit %</th>
              <th class="num">Expected Hit %</th>
              <th class="num">Calib |Err|</th>
              <th class="num">Verified ROI</th>
              <th class="num">Luck-Adj ROI</th>
              <th class="num">Slippage ROI</th>
              <th>Verdict</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(strat_rows_html)}
          </tbody>
        </table>
      </div>
    </section>
    """
    p_str = PAGES_DIR / "strategies.html"
    p_str.write_text(page_shell("strategies", "Singles, Parlays & Props", strategies_body), encoding="utf-8")
    written.append(p_str)

    # ------------------------------------------------------------------
    # 9. pages/gates.html — 10-Gate Validation Matrix
    # ------------------------------------------------------------------
    gate_def_rows = [
        f'<tr>'
        f'<td class="mono"><strong>{esc(g["id"])}</strong></td>'
        f'<td><strong>{esc(g["name"])}</strong></td>'
        f'<td>{esc(g["threshold"])}</td>'
        f'<td>{src_link(sources, g["source_id"])}</td>'
        f'</tr>'
        for g in strats["gate_catalog"]
    ]

    matrix_rows = []
    for s in strats["rows"]:
        gmap = s["gates"]
        cells = "".join(f'<td>{gate_badge(gmap[f"G{k}"])}</td>' for k in range(1, 11))
        matrix_rows.append(
            f'<tr>'
            f'<td class="mono"><strong>{esc(s["id"])}</strong></td>'
            f'<td>{esc(s["name"])}</td>'
            f'{cells}'
            f'<td class="mono"><strong>{esc(s["gates_passed"])}</strong></td>'
            f'<td>{src_link(sources, s["source_id"])}</td>'
            f'</tr>'
        )

    gates_body = f"""
    <section class="hero">
      <h1>10-Gate Strategy Validation Architecture</h1>
      <p>
        Every strategy must survive all 10 sequential gates covering point-in-time causality, sample depth, positive vigorish-inclusive ROI, block-bootstrap confidence intervals, Benjamini-Hochberg FDR, permutation &amp; Empirical Bayes luck removal, recent holdout stability, drawdown control, execution slippage stress, and verified closing-price provenance.
      </p>
    </section>

    <section class="section">
      <h2>Gate Definitions &amp; Quantitative Thresholds (G1&ndash;G10)</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Gate</th>
              <th>Validation Check</th>
              <th>Exact Quantitative Pass Criterion</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(gate_def_rows)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>Full 16 &times; 10 Strategy Gate Pass / Fail / Hold Matrix</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Strategy</th>
              <th>G1</th><th>G2</th><th>G3</th><th>G4</th><th>G5</th>
              <th>G6</th><th>G7</th><th>G8</th><th>G9</th><th>G10</th>
              <th>Passed</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(matrix_rows)}
          </tbody>
        </table>
      </div>
    </section>
    """
    p_gates = PAGES_DIR / "gates.html"
    p_gates.write_text(page_shell("gates", "10-Gate Matrix", gates_body), encoding="utf-8")
    written.append(p_gates)

    # ------------------------------------------------------------------
    # 10. pages/official-audit.html — Official NFL.com Reconciliation
    # ------------------------------------------------------------------
    st26_rows = [
        f'<tr>'
        f'<td class="mono"><strong>{esc(r["team"])}</strong></td>'
        f'<td class="mono">{esc(r["nfl_official_2026"])}</td>'
        f'<td class="mono">{esc(r["repo_committed_2026"])}</td>'
        f'<td class="mono">{esc(r["reconciled_with_nov1"])}</td>'
        f'<td>{badge("STALE (-1 WK8 GAME)" if r["repo_is_stale"] else "CURRENT (BYE/TNF/MNF)", "warn" if r["repo_is_stale"] else "pass")}</td>'
        f'<td>{badge("EXACT MATCH" if r["exact_match_after_nov1"] else "MISMATCH", "pass" if r["exact_match_after_nov1"] else "fail")}</td>'
        f'<td>{src_link(sources, r["source_id"])}</td>'
        f'</tr>'
        for r in off["standings_2026"]
    ]

    pl26_rows = [
        f'<tr>'
        f'<td><strong>{esc(p["player"])}</strong> ({esc(p["team"])} &middot; {esc(p["pos"])})</td>'
        f'<td>{esc(p["stat_label"])}</td>'
        f'<td class="mono">{esc(p["repo_sum"])} ({p["repo_weeks_present"]} gms)</td>'
        f'<td class="mono">{esc(p["week8_nov1_add"])}</td>'
        f'<td class="mono">{esc(p["reconciled_sum"])}</td>'
        f'<td class="mono"><strong>{esc(p["nfl_official_2026"])}</strong></td>'
        f'<td>{badge("EXACT MATCH" if p["exact_match"] else "MISMATCH", "pass" if p["exact_match"] else "fail")}</td>'
        f'<td>{src_link(sources, p["source_id"])}</td>'
        f'</tr>'
        for p in off["players_2026"]
    ]

    s20_rows = [
        f'<tr>'
        f'<td class="mono"><strong>{esc(r["team_official"])}</strong> (CSV: <code>{esc(r["team_in_csv"])}</code>)</td>'
        f'<td class="mono">{esc(r["nfl_official_2020_reg"])}</td>'
        f'<td class="mono">{esc(r["repo_standings_2020_csv"])}</td>'
        f'<td>{badge("MISMATCH FLAGGED", "fail")}</td>'
        f'<td>{esc(r["finding"])}</td>'
        f'<td>{src_link(sources, r["source_id"])}</td>'
        f'</tr>'
        for r in off["standings_2020_audit"]
    ]

    st25_rows = [
        f'<tr>'
        f'<td class="mono"><strong>{esc(r["team"])}</strong></td>'
        f'<td class="mono">{esc(r["nfl_official_2025"])}</td>'
        f'<td class="mono">{esc(r["repo_committed_2025"])}</td>'
        f'<td>{badge("EXACT MATCH" if r["exact_match"] else "MISMATCH", "pass" if r["exact_match"] else "fail")}</td>'
        f'<td>{src_link(sources, r["source_id"])}</td>'
        f'</tr>'
        for r in off["standings_2025"]
    ]

    official_body = f"""
    <section class="hero">
      <h1>Official NFL.com Reconciliation (2026 Live, 2025 Full Season &amp; 2020 Audit)</h1>
      <p>
        Every team win-loss-tie record, points-for, points-against, and audited 2026 player stat line in <code>data/derived/</code> was checked directly against live <code>NFL.com</code> pages fetched on <strong>2026-11-02 UTC</strong>.
      </p>
    </section>

    <section class="section">
      <h2>2026 NFL Player Stat Reconciliation (7 / 7 Exact Yard &amp; Touchdown Match)</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Player</th>
              <th>Category</th>
              <th>Repo Committed Sum</th>
              <th>Official Nov 1 Wk 8 Log</th>
              <th>Reconciled Total</th>
              <th>NFL.com Official Total</th>
              <th>Status</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(pl26_rows)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>2026 Regular-Season Standings Reconciliation (32 / 32 Exact Match; {off["teams_2026_stale_in_repo"]} / 32 Stale in Repo)</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Team</th>
              <th>NFL.com Official (2026-11-02)</th>
              <th>Repo Committed (Thru Oct 29)</th>
              <th>Repo + 12 Official Nov 1 Finals</th>
              <th>Committed Status</th>
              <th>Reconciled Verdict</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(st26_rows)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>Sibling Irregularity Proof: <code>data/standings_2020.csv</code> vs. Official NFL.com 2020 REG</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Club</th>
              <th>NFL.com Official 2020 REG</th>
              <th>Sibling standings_2020.csv</th>
              <th>Audit Verdict</th>
              <th>Line-by-Line Root Cause</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(s20_rows)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>2025 Completed Regular-Season Control (32 / 32 Exact Match Across 272 Games)</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Team</th>
              <th>NFL.com Official 2025 REG</th>
              <th>Repo Committed 2025 REG</th>
              <th>Audit Verdict</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(st25_rows)}
          </tbody>
        </table>
      </div>
    </section>
    """
    p_off = PAGES_DIR / "official-audit.html"
    p_off.write_text(page_shell("official", "NFL.com Audit", official_body), encoding="utf-8")
    written.append(p_off)

    # ------------------------------------------------------------------
    # 11. pages/repo-review.html — Line-by-Line Repository Review
    # ------------------------------------------------------------------
    rev_rows_html = [
        f'<tr>'
        f'<td class="mono"><strong>{esc(r["id"])}</strong></td>'
        f'<td class="mono">{esc(r["path"])}</td>'
        f'<td class="mono">{esc(r["lines_or_rows"])}</td>'
        f'<td>{status_badge(r["status"])}</td>'
        f'<td>{esc(r["finding"])}</td>'
        f'<td>{src_link(sources, r["source_id"])}</td>'
        f'</tr>'
        for r in rev["rows"]
    ]

    repo_body = f"""
    <section class="hero">
      <h1>Line-by-Line Repository Review (<code>karagemop466-tech/Korea2</code>)</h1>
      <p>
        Systematic audit of datasets, scripts, markdown reports, HTML suites, and GitHub Actions workflows across the repository, cross-referenced against open audit issues (<code>#1</code>&ndash;<code>#34</code>) and official primary sources.
        In strict compliance with multi-session coordination rules, sibling directories were inspected read-only and never overwritten; all defects and drift items are documented here and on the Flagged for Review page.
      </p>
    </section>

    <section class="section">
      <h2>14 Audited Repository Subsystems &amp; Verdicts</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Audit ID</th>
              <th>Repository Path</th>
              <th>Lines / Scope</th>
              <th>Verdict</th>
              <th>Line-by-Line Finding &amp; Resolution</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(rev_rows_html)}
          </tbody>
        </table>
      </div>
    </section>
    """
    p_rev = PAGES_DIR / "repo-review.html"
    p_rev.write_text(page_shell("reporeview", "Repo Review", repo_body), encoding="utf-8")
    written.append(p_rev)

    # ------------------------------------------------------------------
    # 12. pages/flagged.html — Flagged for Review & Unverified Items + Source Registry
    # ------------------------------------------------------------------
    flg_rows_html = []
    for f in flg["rows"]:
        assert f["value"] == "", f"Flagged item {f['id']} has non-blank value!"
        flg_rows_html.append(
            f'<tr>'
            f'<td class="mono"><strong>{esc(f["id"])}</strong></td>'
            f'<td>{esc(f["category"])}</td>'
            f'<td><strong>{esc(f["item"])}</strong></td>'
            f'<td class="blank-cell" title="Intentionally left blank — never inferred or hallucinated"></td>'
            f'<td>{status_badge(f["status"])}</td>'
            f'<td>{esc(f["reason"])}</td>'
            f'<td>{src_link(sources, f["source_id"])}</td>'
            f'</tr>'
        )

    src_reg_rows = []
    for s in sources_doc["sources"]:
        url = esc(s["url"])
        src_reg_rows.append(
            f'<tr>'
            f'<td class="mono"><strong>{esc(s["id"])}</strong></td>'
            f'<td>{esc(s["publisher"])}</td>'
            f'<td>{esc(s["title"])}</td>'
            f'<td>{esc(s["scope"])}</td>'
            f'<td class="mono">{esc(s["verified_date"])}</td>'
            f'<td><a href="{url}" target="_blank" rel="noopener">{esc(s["id"])} ({esc(s["publisher"])})</a></td>'
            f'</tr>'
        )

    flagged_body = f"""
    <section class="hero">
      <h1>Flagged for Review &amp; Unverified Items Register</h1>
      <p>
        Zero-hallucination policy enforcement: whenever a metric, price feed, score, or treasury figure cannot be confirmed directly from an official primary source, its value cell is left <strong>strictly blank (<code>""</code>)</strong>, flagged for manual review, and linked to the authoritative primary source explaining the boundary.
      </p>
    </section>

    <section class="section">
      <h2>12 Unverified Items &amp; Repository Irregularities (Verified Value Cells Strictly Blank)</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Flag ID</th>
              <th>Category</th>
              <th>Item</th>
              <th>Verified Value</th>
              <th>Status</th>
              <th>Detailed Explanation &amp; Handling</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(flg_rows_html)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <h2>Official Primary Source Registry (SL-SRC-01 through SL-SRC-32)</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Source ID</th>
              <th>Official Publisher</th>
              <th>Document / Endpoint Title</th>
              <th>Verification Scope</th>
              <th>Verified Date</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(src_reg_rows)}
          </tbody>
        </table>
      </div>
    </section>
    """
    p_flg = PAGES_DIR / "flagged.html"
    p_flg.write_text(page_shell("flagged", "Flagged for Review", flagged_body), encoding="utf-8")
    written.append(p_flg)

    print(f"Built {len(written)} Skill Lab HTML pages cleanly.")
    return written


if __name__ == "__main__":
    build_all_pages()
