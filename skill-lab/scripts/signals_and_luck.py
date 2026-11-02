#!/usr/bin/env python3
"""Signal research & luck-removal / skill decomposition engine (SL-4).

1. Quantifies split-half (odd vs even week) and year-over-year (season t -> t+1)
   persistence across 9 team/market metrics (2015-2025 full seasons) to separate
   repeatable skill from mean-reverting luck, deriving Empirical Bayes shrinkage weights.
2. Evaluates 10 strictly pre-kickoff candidate signals walk-forward on 2018-2026
   priced games (zero imputed odds) with Benjamini-Hochberg FDR control (q <= 0.10).
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from common import (
    american_to_decimal,
    bh_fdr,
    corr_pvalue,
    fisher_ci,
    load_games,
    load_team_weeks,
    pearson_r,
    two_sided_t_pvalue,
    write_json,
)


def compute_luck_decomposition(
    games: list[dict[str, Any]],
    team_weeks: dict[tuple[int, int, str], dict[str, float]],
) -> dict[str, Any]:
    """Measure split-half & YoY persistence across 2015-2025 full regular seasons."""
    full_seasons = list(range(2015, 2026))
    # Per (season, team) accumulators
    agg: dict[tuple[int, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    odd_epa: dict[tuple[int, str], list[float]] = defaultdict(list)
    even_epa: dict[tuple[int, str], list[float]] = defaultdict(list)
    odd_to: dict[tuple[int, str], list[float]] = defaultdict(list)
    even_to: dict[tuple[int, str], list[float]] = defaultdict(list)
    odd_ats: dict[tuple[int, str], list[float]] = defaultdict(list)
    even_ats: dict[tuple[int, str], list[float]] = defaultdict(list)

    for g in games:
        s = g["season"]
        if g["game_type"] != "REG" or s not in full_seasons or g["result"] is None:
            continue
        w = g["week"]
        ht, at = g["home_team"], g["away_team"]
        hs, as_ = g["home_score"], g["away_score"]
        sp = g["spread_line"]

        for team, opp, pts_f, pts_a, is_home in ((ht, at, hs, as_, True), (at, ht, as_, hs, False)):
            rec = agg[(s, team)]
            rec["games"] += 1.0
            rec["pf"] += pts_f
            rec["pa"] += pts_a
            margin = pts_f - pts_a
            if margin > 0:
                rec["wins"] += 1.0
            elif margin == 0:
                rec["wins"] += 0.5
            if abs(margin) <= 8.0 and margin != 0.0:
                rec["os_games"] += 1.0
                if margin > 0:
                    rec["os_wins"] += 1.0
            if sp is not None:
                # Home covers if (hs - as_) > sp; Away covers if (hs - as_) < sp
                h_diff = (hs - as_) - sp
                if h_diff != 0.0:
                    covered = 1.0 if ((h_diff > 0.0 and is_home) or (h_diff < 0.0 and not is_home)) else 0.0
                    rec["ats_n"] += 1.0
                    rec["ats_w"] += covered
                    (odd_ats if w % 2 == 1 else even_ats)[(s, team)].append(covered)

            tw = team_weeks.get((s, w, team))
            tw_opp = team_weeks.get((s, w, opp))
            if tw:
                plays = max(1.0, tw["attempts"] + tw["carries"] + tw["sacks_suffered"])
                dropbacks = max(1.0, tw["attempts"] + tw["sacks_suffered"])
                tot_epa = tw["passing_epa"] + tw["rushing_epa"]
                rec["epa_sum"] += tot_epa
                rec["plays"] += plays
                rec["pass_epa_sum"] += tw["passing_epa"]
                rec["dropbacks"] += dropbacks
                rec["cpoe_weighted"] += tw["passing_cpoe"] * tw["attempts"]
                rec["att_sum"] += tw["attempts"]
                # Net turnover margin: takeaways (def_interceptions + opp fumbles_lost) - giveaways
                opp_fum = tw_opp["fumbles_lost"] if tw_opp else 0.0
                takeaways = tw["def_interceptions"] + opp_fum
                net_to = takeaways - tw["turnovers_lost"]
                rec["net_to"] += net_to
                rec["fumbles_lost"] += tw["fumbles_lost"]
                (odd_epa if w % 2 == 1 else even_epa)[(s, team)].append(tot_epa / plays)
                (odd_to if w % 2 == 1 else even_to)[(s, team)].append(net_to)

    def metric_val(s: int, t: str, key: str) -> float | None:
        r = agg.get((s, t))
        if not r or r["games"] < 16:
            return None
        g_cnt = r["games"]
        if key == "pass_epa_db":
            return r["pass_epa_sum"] / max(1.0, r["dropbacks"])
        if key == "off_epa_play":
            return r["epa_sum"] / max(1.0, r["plays"])
        if key == "cpoe":
            return r["cpoe_weighted"] / max(1.0, r["att_sum"])
        if key == "pt_diff_pg":
            return (r["pf"] - r["pa"]) / g_cnt
        if key == "win_pct":
            return r["wins"] / g_cnt
        if key == "pythag_luck":
            pf_e = max(1.0, r["pf"]) ** 2.37
            pa_e = max(1.0, r["pa"]) ** 2.37
            pyth_w = g_cnt * (pf_e / (pf_e + pa_e))
            return r["wins"] - pyth_w
        if key == "onescore_win_pct":
            return (r["os_wins"] / r["os_games"]) if r["os_games"] >= 4 else None
        if key == "net_to_pg":
            return r["net_to"] / g_cnt
        if key == "ats_cover_pct":
            return (r["ats_w"] / r["ats_n"]) if r["ats_n"] >= 12 else None
        return None

    teams = sorted({t for (_, t) in agg.keys()})
    specs = [
        ("pass_epa_db", "Offensive Passing EPA / Dropback", "True Offensive Skill", "SL-SRC-15"),
        ("off_epa_play", "Total Offensive EPA / Play (Pass + Rush)", "True Offensive Skill", "SL-SRC-15"),
        ("cpoe", "Completion % Over Expected (CPOE)", "Quarterback Accuracy Skill", "SL-SRC-14"),
        ("pt_diff_pg", "Net Point Differential / Game", "Blended Skill + Turnover Noise", "SL-SRC-02"),
        ("win_pct", "Season Win-Loss Percentage", "Blended Skill + Close-Game Luck", "SL-SRC-02"),
        ("net_to_pg", "Net Turnover Margin / Game", "Mostly Ephemeral Bounce Luck", "SL-SRC-15"),
        ("pythag_luck", "Pythagorean Wins Residual (Actual - Expected Wins)", "Pure Mean-Reverting Luck", "SL-SRC-24"),
        ("onescore_win_pct", "One-Score Game Win % (Margin <= 8 pts)", "Pure Close-Game Coin-Flip Luck", "SL-SRC-24"),
        ("ats_cover_pct", "Team Season ATS Cover Rate vs Closing Spread", "Market-Priced Zero-Persistence Residual", "SL-SRC-18"),
    ]

    rows = []
    for key, label, classification, src_id in specs:
        xs, ys = [], []
        for s in range(2015, 2025):
            for t in teams:
                v1 = metric_val(s, t, key)
                v2 = metric_val(s + 1, t, key)
                if v1 is not None and v2 is not None:
                    xs.append(v1)
                    ys.append(v2)
        r_yoy = pearson_r(xs, ys)
        lo, hi = fisher_ci(r_yoy, len(xs))
        pval = corr_pvalue(r_yoy, len(xs))
        # Empirical Bayes optimal linear shrinkage weight toward league mean for next-season projection
        eb_weight = max(0.0, round(r_yoy, 3))
        rows.append({
            "metric_id": key,
            "label": label,
            "team_season_pairs": len(xs),
            "yoy_r": round(r_yoy, 4),
            "ci_95_low": round(lo, 4),
            "ci_95_high": round(hi, 4),
            "p_value": round(pval, 5),
            "eb_skill_weight": eb_weight,
            "luck_shrinkage_pct": round(100.0 * (1.0 - eb_weight), 1),
            "classification": classification,
            "source_id": src_id,
        })

    # Within-season split-half reliability (odd weeks vs even weeks, N = 352 team-seasons)
    sh_epa_x, sh_epa_y = [], []
    sh_to_x, sh_to_y = [], []
    sh_ats_x, sh_ats_y = [], []
    for k in sorted(odd_epa.keys()):
        if even_epa[k]:
            sh_epa_x.append(sum(odd_epa[k]) / len(odd_epa[k]))
            sh_epa_y.append(sum(even_epa[k]) / len(even_epa[k]))
        if odd_to[k] and even_to[k]:
            sh_to_x.append(sum(odd_to[k]) / len(odd_to[k]))
            sh_to_y.append(sum(even_to[k]) / len(even_to[k]))
        if odd_ats[k] and even_ats[k]:
            sh_ats_x.append(sum(odd_ats[k]) / len(odd_ats[k]))
            sh_ats_y.append(sum(even_ats[k]) / len(even_ats[k]))

    split_half = {
        "team_seasons": len(sh_epa_x),
        "odd_even_epa_per_play_r": round(pearson_r(sh_epa_x, sh_epa_y), 4),
        "odd_even_net_turnovers_r": round(pearson_r(sh_to_x, sh_to_y), 4),
        "odd_even_ats_cover_r": round(pearson_r(sh_ats_x, sh_ats_y), 4),
    }

    # 2025 -> 2026 concrete regression-to-the-mean showcase (e.g. one-score & Pythagorean regression)
    pyth_2025_to_2026 = []
    for t in teams:
        luck25 = metric_val(2025, t, "pythag_luck")
        if luck25 is not None and abs(luck25) >= 1.6:
            r25 = agg[(2025, t)]
            w25 = int(r25["wins"])
            l25 = int(r25["games"] - r25["wins"])
            pyth_2025_to_2026.append({
                "team": t,
                "record_2025": f"{w25}-{l25}",
                "pythag_luck_2025_wins": round(luck25, 2),
                "direction_predicted_for_2026": "Negative Regression" if luck25 > 0 else "Positive Rebound",
                "source_id": "SL-SRC-02",
            })
    pyth_2025_to_2026.sort(key=lambda x: abs(x["pythag_luck_2025_wins"]), reverse=True)

    return {
        "window": "2015-2025 full NFL regular seasons (320 consecutive team-season transitions)",
        "metrics": rows,
        "within_season_split_half": split_half,
        "pythagorean_outliers_2025": pyth_2025_to_2026[:8],
    }


def evaluate_signals(
    predictions: list[dict[str, Any]],
    team_weeks: dict[tuple[int, int, str], dict[str, float]],
) -> dict[str, Any]:
    """Screen 10 strictly pre-kickoff signals on 2018-2026 priced games with BH-FDR."""
    preds_sorted = sorted(predictions, key=lambda p: (p["season"], p["week"], p["gameday"], p["game_id"]))

    # Rolling strictly-prior team logs for pre-kickoff feature computation
    prior_epa_vs_margin: dict[tuple[int, str], list[float]] = defaultdict(list)
    prior_onescore_net: dict[tuple[int, str], float] = defaultdict(float)
    last_game_to_lost: dict[tuple[int, str], float] = defaultdict(float)
    prior_epa_pg: dict[tuple[int, str], list[float]] = defaultdict(list)

    enriched: list[dict[str, Any]] = []
    for p in preds_sorted:
        s, w = p["season"], p["week"]
        ht, at = p["home_team"], p["away_team"]

        # Read strictly pre-kickoff state before recording current game!
        h_evm = sum(prior_epa_vs_margin[(s, ht)][-6:]) / len(prior_epa_vs_margin[(s, ht)][-6:]) if len(prior_epa_vs_margin[(s, ht)]) >= 3 else 0.0
        a_evm = sum(prior_epa_vs_margin[(s, at)][-6:]) / len(prior_epa_vs_margin[(s, at)][-6:]) if len(prior_epa_vs_margin[(s, at)]) >= 3 else 0.0
        h_os = prior_onescore_net[(s, ht)]
        a_os = prior_onescore_net[(s, at)]
        h_last_to = last_game_to_lost[(s, ht)]
        a_last_to = last_game_to_lost[(s, at)]
        h_epa_avg = sum(prior_epa_pg[(s, ht)][-6:]) / len(prior_epa_pg[(s, ht)][-6:]) if len(prior_epa_pg[(s, ht)]) >= 3 else -99.0
        a_epa_avg = sum(prior_epa_pg[(s, at)][-6:]) / len(prior_epa_pg[(s, at)][-6:]) if len(prior_epa_pg[(s, at)]) >= 3 else -99.0

        row = dict(p)
        row.update({
            "h_epa_minus_margin": h_evm,
            "a_epa_minus_margin": a_evm,
            "h_onescore_net": h_os,
            "a_onescore_net": a_os,
            "h_last_to": h_last_to,
            "a_last_to": a_last_to,
            "h_epa_avg": h_epa_avg,
            "a_epa_avg": a_epa_avg,
        })
        enriched.append(row)

        # Now update rolling histories from settled outcome of this game
        if p["actual_margin"] is not None:
            m_h = p["actual_margin"]
            if 0.0 < abs(m_h) <= 8.0:
                prior_onescore_net[(s, ht)] += (1.0 if m_h > 0 else -1.0)
                prior_onescore_net[(s, at)] += (1.0 if m_h < 0 else -1.0)
            tw_h = team_weeks.get((s, w, ht))
            tw_a = team_weeks.get((s, w, at))
            if tw_h and tw_a:
                epa_diff_h = (tw_h["passing_epa"] + tw_h["rushing_epa"]) - (tw_a["passing_epa"] + tw_a["rushing_epa"])
                prior_epa_vs_margin[(s, ht)].append(epa_diff_h - m_h)
                prior_epa_vs_margin[(s, at)].append((-epa_diff_h) - (-m_h))
                prior_epa_pg[(s, ht)].append(tw_h["passing_epa"] + tw_h["rushing_epa"])
                prior_epa_pg[(s, at)].append(tw_a["passing_epa"] + tw_a["rushing_epa"])
                last_game_to_lost[(s, ht)] = tw_h["turnovers_lost"]
                last_game_to_lost[(s, at)] = tw_a["turnovers_lost"]

    test_pool = [r for r in enriched if r["season"] >= 2018 and r["actual_margin"] is not None]

    def settle_spread(r: dict[str, Any], side: str) -> float | None:
        sp = r["mkt_spread_line"]
        if sp is None:
            return None
        odds = r["home_spread_odds"] if side == "HOME" else r["away_spread_odds"]
        if odds is None:
            return None
        diff = r["actual_margin"] - sp
        if diff == 0.0:
            return None  # Push refunded per DraftKings KB0010595
        won = (diff > 0.0) if side == "HOME" else (diff < 0.0)
        return (american_to_decimal(odds) - 1.0) if won else -1.0

    def settle_total(r: dict[str, Any], side: str) -> float | None:
        tl = r["mkt_total_line"]
        if tl is None or r["actual_total"] is None:
            return None
        odds = r["over_odds"] if side == "OVER" else r["under_odds"]
        if odds is None:
            return None
        diff = r["actual_total"] - tl
        if diff == 0.0:
            return None
        won = (diff > 0.0) if side == "OVER" else (diff < 0.0)
        return (american_to_decimal(odds) - 1.0) if won else -1.0

    def crosses_key(orig_hcap: float, mkt_hcap: float) -> bool:
        lo, hi = min(orig_hcap, mkt_hcap), max(orig_hcap, mkt_hcap)
        for k in (-7.0, -3.0, 3.0, 7.0):
            if lo < k < hi and (hi - lo) >= 1.5:
                return True
        return False

    signal_defs = [
        (
            "SIG-01",
            "EPA Skill vs Scoreboard Luck Divergence (>= 3.5 pts/g)",
            "Spread",
            "SL-SRC-15",
            lambda r: "HOME" if (r["h_epa_minus_margin"] - r["a_epa_minus_margin"]) >= 3.5 else (
                "AWAY" if (r["a_epa_minus_margin"] - r["h_epa_minus_margin"]) >= 3.5 else None
            ),
            "spread",
        ),
        (
            "SIG-02",
            "One-Score Luck Regression Fade (Net Close-Game Diff >= 3)",
            "Spread",
            "SL-SRC-24",
            lambda r: "HOME" if (r["a_onescore_net"] - r["h_onescore_net"]) >= 3.0 else (
                "AWAY" if (r["h_onescore_net"] - r["a_onescore_net"]) >= 3.0 else None
            ),
            "spread",
        ),
        (
            "SIG-03",
            "Turnover-Spike Mean Reversion (>= 3 Giveaways, Positive EPA)",
            "Spread",
            "SL-SRC-15",
            lambda r: "HOME" if (r["h_last_to"] >= 3.0 and r["h_epa_avg"] > 0.0 and r["a_last_to"] < 3.0) else (
                "AWAY" if (r["a_last_to"] >= 3.0 and r["a_epa_avg"] > 0.0 and r["h_last_to"] < 3.0) else None
            ),
            "spread",
        ),
        (
            "SIG-04",
            "Originated Spread Disagreement (>= 2.5 pts vs Closing Line)",
            "Spread",
            "SL-SRC-18",
            lambda r: (
                "HOME" if (r["mkt_spread_line"] is not None and (r["orig_home_margin"] - r["mkt_spread_line"]) >= 2.5)
                else ("AWAY" if (r["mkt_spread_line"] is not None and (r["mkt_spread_line"] - r["orig_home_margin"]) >= 2.5) else None)
            ),
            "spread",
        ),
        (
            "SIG-05",
            "Key-Number Crossing Edge (Crosses +/-3 or +/-7 by >= 1.5 pts)",
            "Spread",
            "SL-SRC-18",
            lambda r: (
                ("HOME" if r["orig_home_margin"] > r["mkt_spread_line"] else "AWAY")
                if (r["mkt_home_handicap"] is not None and crosses_key(r["orig_home_handicap"], r["mkt_home_handicap"]))
                else None
            ),
            "spread",
        ),
        (
            "SIG-06",
            "Post-Bye / Long-Rest Advantage (>= +6 Days Rest + Top-Half Defense)",
            "Spread",
            "SL-SRC-26",
            lambda r: (
                "HOME" if (r["rest_diff"] >= 6.0 and r["home_def_skill"] <= 0.0)
                else ("AWAY" if (r["rest_diff"] <= -6.0 and r["away_def_skill"] <= 0.0) else None)
            ),
            "spread",
        ),
        (
            "SIG-07",
            "Divisional Home Underdog Compression (Divisional Dog >= +3.0)",
            "Spread",
            "SL-SRC-18",
            lambda r: "HOME" if (r["div_game"] == 1 and r["mkt_home_handicap"] is not None and r["mkt_home_handicap"] >= 3.0) else None,
            "spread",
        ),
        (
            "SIG-08",
            "Outdoor High-Wind Total Under (Outdoor Wind >= 15 mph)",
            "Total",
            "SL-SRC-28",
            lambda r: "UNDER" if (r["roof"] in ("outdoors", "open", "") and r["wind"] is not None and r["wind"] >= 15.0) else None,
            "total",
        ),
        (
            "SIG-09",
            "Outdoor Freezing-Weather Total Under (Outdoor Temp <= 32 F)",
            "Total",
            "SL-SRC-28",
            lambda r: "UNDER" if (r["roof"] in ("outdoors", "open", "") and r["temp"] is not None and r["temp"] <= 32.0) else None,
            "total",
        ),
        (
            "SIG-10",
            "Originated Total Disagreement (>= 3.0 pts vs Closing Total)",
            "Total",
            "SL-SRC-27",
            lambda r: (
                "OVER" if (r["mkt_total_line"] is not None and (r["orig_total"] - r["mkt_total_line"]) >= 3.0)
                else ("UNDER" if (r["mkt_total_line"] is not None and (r["mkt_total_line"] - r["orig_total"]) >= 3.0) else None)
            ),
            "total",
        ),
    ]

    raw_results = []
    pvals = []
    for sig_id, name, mkt_type, src_id, rule_fn, settle_kind in signal_defs:
        pnls: list[float] = []
        wins = 0
        holdout_pnls: list[float] = []  # 2024-2026 recent stability check
        for r in test_pool:
            pick = rule_fn(r)
            if pick is None:
                continue
            pnl = settle_spread(r, pick) if settle_kind == "spread" else settle_total(r, pick)
            if pnl is None:
                continue
            pnls.append(pnl)
            if pnl > 0.0:
                wins += 1
            if r["season"] >= 2024:
                holdout_pnls.append(pnl)

        n = len(pnls)
        roi = (sum(pnls) / n) if n else 0.0
        win_rate = (wins / n) if n else 0.0
        hold_roi = (sum(holdout_pnls) / len(holdout_pnls)) if holdout_pnls else 0.0
        t_stat, p_val = two_sided_t_pvalue(pnls, 0.0)
        pvals.append(p_val)
        raw_results.append({
            "id": sig_id,
            "name": name,
            "market": mkt_type,
            "settled_bets": n,
            "win_rate_pct": round(100.0 * win_rate, 2),
            "roi_pct": round(100.0 * roi, 2),
            "recent_2024_2026_roi_pct": round(100.0 * hold_roi, 2),
            "t_stat": round(t_stat, 3),
            "p_value": round(p_val, 4),
            "source_id": src_id,
        })

    qvals, passed = bh_fdr(pvals, q=0.10)
    for row, qv, ok in zip(raw_results, qvals, passed):
        row["bh_q_value"] = round(qv, 4)
        row["survives_fdr_q10"] = ok
        if ok and row["roi_pct"] > 0.0:
            row["verdict"] = "SURVIVES BH-FDR (q <= 0.10)"
        elif row["p_value"] < 0.05 and row["roi_pct"] > 0.0:
            row["verdict"] = "NOMINAL p < 0.05 (FAILS FDR)"
        else:
            row["verdict"] = "REJECTED (NOISE AFTER VIG)"

    surviving_count = sum(1 for r in raw_results if r["survives_fdr_q10"] and r["roi_pct"] > 0)
    return {
        "test_window": "2018-2026 regular season (strictly pre-kickoff signals, actual closing prices only)",
        "signals_tested": len(raw_results),
        "fdr_threshold_q": 0.10,
        "signals_surviving_fdr": surviving_count,
        "rows": raw_results,
    }


def main() -> None:
    import json
    from common import DATA_OUT

    games = load_games()
    team_weeks = load_team_weeks()
    predictions = json.loads((DATA_OUT / "_predictions_cache.json").read_text(encoding="utf-8"))

    luck_data = compute_luck_decomposition(games, team_weeks)
    sig_data = evaluate_signals(predictions, team_weeks)

    write_json("luck.json", luck_data)
    write_json("signals.json", sig_data)
    print(
        f"Luck & Signals complete: {len(luck_data['metrics'])} persistence series | "
        f"{sig_data['signals_tested']} signals screened, {sig_data['signals_surviving_fdr']} survive BH-FDR q<=0.10"
    )
    for r in sig_data["rows"]:
        print(f"  {r['id']} n={r['settled_bets']:4d} win={r['win_rate_pct']:5.2f}% ROI={r['roi_pct']:+6.2f}% p={r['p_value']:.4f} q={r['bh_q_value']:.4f} -> {r['verdict']}")


if __name__ == "__main__":
    main()
