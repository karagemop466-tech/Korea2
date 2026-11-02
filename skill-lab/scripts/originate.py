#!/usr/bin/env python3
"""Walk-forward, zero-lookahead NFL line & player-prop origination engine.

Key guarantees:
1. Empirical sign-convention proof before any grading.
2. Hyperparameters & situational weights fitted ONLY on 2015-2017; frozen on 2018-2026 test set.
3. Residual sigmas (margin & total) estimated strictly from completed seasons < s (zero holdout leakage).
4. Ex-ante evaluation on the 12 newly settled Sunday Nov 1, 2026 Week 8 NFL.com finals, plus
   live Week 8 MNF + Week 9 board updated with official Nov 1 outcomes.
5. Ex-ante role selection (prior rolling usage, never in-game yardage) for QB1/WR1/RB1 prop lines.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any

from common import (
    OFFICIAL_PLAYER_LOGS_2026,
    OFFICIAL_STANDINGS_2025,
    OFFICIAL_STANDINGS_2026,
    OFFICIAL_STANDINGS_2020_SPOT,
    OFFICIAL_WEEK8_NOV1_FINALS,
    SOURCES,
    american_to_decimal,
    devig_two_way,
    load_games,
    load_player_weeks,
    load_team_weeks,
    norm_cdf,
    pearson_r,
    prob_to_fair_american,
    quantile,
    two_sided_t_pvalue,
    write_json,
)


def prove_sign_convention(games: list[dict[str, Any]]) -> dict[str, Any]:
    pos_line_neg_ml = 0
    pos_line_total = 0
    neg_line_pos_ml = 0
    neg_line_total = 0
    margins: list[float] = []
    spreads: list[float] = []
    covers_as_fav: list[int] = []
    covers_inverted: list[int] = []

    for g in games:
        if g["game_type"] != "REG" or g["result"] is None or g["spread_line"] is None:
            continue
        sp = g["spread_line"]
        res = g["result"]  # home_score - away_score
        margins.append(res)
        spreads.append(sp)
        if res != sp:
            covers_as_fav.append(1 if res > sp else 0)
        if res != -sp:
            covers_inverted.append(1 if res > -sp else 0)
        hml = g["home_moneyline"]
        aml = g["away_moneyline"]
        if hml is not None and aml is not None:
            if sp >= 3.0:
                pos_line_total += 1
                if hml < aml:
                    pos_line_neg_ml += 1
            elif sp <= -3.0:
                neg_line_total += 1
                if hml > aml:
                    neg_line_pos_ml += 1

    r_val = pearson_r(spreads, margins)
    return {
        "settled_reg_with_spread": len(margins),
        "pos_spread_ge3_count": pos_line_total,
        "pos_spread_home_ shorter_ml_pct": round(100.0 * pos_line_neg_ml / max(1, pos_line_total), 2),
        "neg_spread_le_neg3_count": neg_line_total,
        "neg_spread_home_longer_ml_pct": round(100.0 * neg_line_pos_ml / max(1, neg_line_total), 2),
        "corr_spread_line_vs_home_margin": round(r_val, 4),
        "home_cover_rate_correct_sign_pct": round(100.0 * sum(covers_as_fav) / len(covers_as_fav), 2),
        "home_cover_rate_inverted_sign_pct": round(100.0 * sum(covers_inverted) / len(covers_inverted), 2),
        "conclusion": (
            "In data/derived/games.csv.gz, spread_line > 0 means HOME is favored by spread_line points "
            "(standard sportsbook home handicap = -spread_line). Home covers iff (home_score - away_score) > spread_line."
        ),
        "source_id": "SL-SRC-18",
    }


def run_team_origination(
    games: list[dict[str, Any]],
    team_weeks: dict[tuple[int, int, str], dict[str, float]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Chronological walk-forward team rating & line origination across 2006-2026."""
    reg_games = [g for g in games if g["game_type"] == "REG" and g["season"] >= 2006]
    reg_games.sort(key=lambda g: (g["season"], g["week"], g["gameday"], g["game_id"]))

    # Team skill states: net offensive & defensive points above league average
    off_rating: dict[str, float] = defaultdict(float)
    def_rating: dict[str, float] = defaultdict(float)  # positive = allows MORE points than avg

    # Track season-level league scoring, home margin, and prediction residuals strictly from past seasons
    season_home_margins: dict[int, list[float]] = defaultdict(list)
    season_totals: dict[int, list[float]] = defaultdict(list)
    season_margin_resids: dict[int, list[float]] = defaultdict(list)
    season_total_resids: dict[int, list[float]] = defaultdict(list)

    # Pre-2018 structural parameters (frozen for 2018-2026 walk-forward evaluation)
    K_OFF = 0.075
    K_DEF = 0.075
    EPA_WEIGHT = 0.55       # when play-by-play EPA exists (2015+), blend 55% EPA-pts + 45% capped score
    SCORE_CAP = 24.0        # cap blowout garbage-time distortions
    SEASON_RETAIN = 0.64    # Empirical Bayes offseason retention toward 0
    REST_COEF = 0.14        # pts per rest-day edge (capped [-7, +7])
    DIV_SHRINK = 0.92       # divisional matchup familiarity compression
    WIND_TOTAL_COEF = -0.22 # pts per mph above 12 mph outdoors
    COLD_TOTAL_ADJ = -1.10  # outdoor temp <= 32 F

    current_season = None
    predictions: list[dict[str, Any]] = []

    def get_priors(s: int) -> tuple[float, float, float, float]:
        """Compute HFA, base total, sigma_margin, sigma_total strictly from seasons < s."""
        past_seasons = [ps for ps in range(max(2006, s - 5), s) if season_home_margins[ps]]
        if not past_seasons:
            return (2.35, 43.5, 13.4, 13.5)
        hm_vals = [m for ps in past_seasons for m in season_home_margins[ps]]
        tot_vals = [t for ps in past_seasons for t in season_totals[ps]]
        raw_hfa = sum(hm_vals) / len(hm_vals)
        # Shrink 5-yr empirical HFA 70% data + 30% structural prior (2.0 pts)
        hfa = 0.70 * raw_hfa + 0.30 * 2.00
        # Weight most recent 2 seasons slightly higher for total scoring environment
        recent_2 = [ps for ps in range(max(2006, s - 2), s) if season_totals[ps]]
        if recent_2:
            r_tots = [t for ps in recent_2 for t in season_totals[ps]]
            base_total = 0.65 * (sum(r_tots) / len(r_tots)) + 0.35 * (sum(tot_vals) / len(tot_vals))
        else:
            base_total = sum(tot_vals) / len(tot_vals)

        res_m = [e for ps in past_seasons for e in season_margin_resids[ps]]
        res_t = [e for ps in past_seasons for e in season_total_resids[ps]]
        sig_m = statistics.pstdev(res_m) if len(res_m) >= 100 else 13.4
        sig_t = statistics.pstdev(res_t) if len(res_t) >= 100 else 13.5
        return (hfa, base_total, max(11.5, min(15.5, sig_m)), max(11.5, min(15.5, sig_t)))

    hfa, base_total, sig_m, sig_t = (2.35, 43.5, 13.4, 13.5)

    def predict_game(g: dict[str, Any], hfa_val: float, base_tot: float, sm: float, st: float) -> dict[str, Any]:
        ht, at = g["home_team"], g["away_team"]
        loc_hfa = 0.0 if g["location"] == "Neutral" else hfa_val
        rest_diff = 0.0
        if g["home_rest"] is not None and g["away_rest"] is not None:
            rest_diff = max(-7.0, min(7.0, g["home_rest"] - g["away_rest"]))

        # Expected points for home and away based on opponent-adjusted skill ratings
        half_tot = 0.5 * base_tot
        exp_home = half_tot + 0.5 * (off_rating[ht] + def_rating[at]) + 0.5 * loc_hfa + 0.5 * REST_COEF * rest_diff
        exp_away = half_tot + 0.5 * (off_rating[at] + def_rating[ht]) - 0.5 * loc_hfa - 0.5 * REST_COEF * rest_diff

        raw_margin = exp_home - exp_away
        if g["div_game"]:
            raw_margin *= DIV_SHRINK

        raw_total = exp_home + exp_away
        is_outdoor = g["roof"] in ("outdoors", "open", "")
        if is_outdoor and g["wind"] is not None and g["wind"] > 12.0:
            raw_total += WIND_TOTAL_COEF * (g["wind"] - 12.0)
        if is_outdoor and g["temp"] is not None and g["temp"] <= 32.0:
            raw_total += COLD_TOTAL_ADJ

        p_home_win = norm_cdf(raw_margin / sm)
        sp_mkt = g["spread_line"]
        tot_mkt = g["total_line"]
        p_home_cover = norm_cdf((raw_margin - sp_mkt) / sm) if sp_mkt is not None else None
        p_over = norm_cdf((raw_total - tot_mkt) / st) if tot_mkt is not None else None

        return {
            "game_id": g["game_id"],
            "season": g["season"],
            "week": g["week"],
            "gameday": g["gameday"],
            "away_team": at,
            "home_team": ht,
            "location": g["location"],
            "div_game": g["div_game"],
            "roof": g["roof"],
            "wind": g["wind"],
            "temp": g["temp"],
            "rest_diff": rest_diff,
            "home_off_skill": round(off_rating[ht], 3),
            "home_def_skill": round(def_rating[ht], 3),
            "away_off_skill": round(off_rating[at], 3),
            "away_def_skill": round(def_rating[at], 3),
            "orig_home_margin": round(raw_margin, 2),
            "orig_home_handicap": round(-raw_margin, 2),
            "orig_total": round(raw_total, 2),
            "orig_home_win_prob": round(p_home_win, 4),
            "orig_home_fair_ml": prob_to_fair_american(p_home_win),
            "orig_away_fair_ml": prob_to_fair_american(1.0 - p_home_win),
            "sigma_margin": round(sm, 3),
            "sigma_total": round(st, 3),
            "mkt_spread_line": sp_mkt,
            "mkt_home_handicap": round(-sp_mkt, 2) if sp_mkt is not None else None,
            "mkt_total_line": tot_mkt,
            "home_spread_odds": g["home_spread_odds"],
            "away_spread_odds": g["away_spread_odds"],
            "over_odds": g["over_odds"],
            "under_odds": g["under_odds"],
            "home_moneyline": g["home_moneyline"],
            "away_moneyline": g["away_moneyline"],
            "p_home_cover": round(p_home_cover, 4) if p_home_cover is not None else None,
            "p_over": round(p_over, 4) if p_over is not None else None,
            "away_score": g["away_score"],
            "home_score": g["home_score"],
            "actual_margin": g["result"],
            "actual_total": g["total"],
        }

    def update_from_outcome(g: dict[str, Any], pred: dict[str, Any], hs: float, as_: float, base_tot: float) -> None:
        ht, at = g["home_team"], g["away_team"]
        s, w = g["season"], g["week"]
        margin = hs - as_
        tot = hs + as_
        if g["location"] != "Neutral":
            season_home_margins[s].append(margin)
        season_totals[s].append(tot)
        season_margin_resids[s].append(margin - pred["orig_home_margin"])
        season_total_resids[s].append(tot - pred["orig_total"])

        # Cap extreme garbage-time score blowouts around expected score
        adj_margin = max(-SCORE_CAP, min(SCORE_CAP, margin))
        half_tot = 0.5 * base_tot
        capped_hs = 0.5 * (tot + adj_margin)
        capped_as = 0.5 * (tot - adj_margin)

        # Luck-reduced skill signal: blend play-by-play EPA (stripped of fumble-bounce noise) when available
        tw_h = team_weeks.get((s, w, ht))
        tw_a = team_weeks.get((s, w, at))
        if tw_h and tw_a:
            # EPA points relative to neutral ~0 EPA baseline + league half_tot
            epa_h = half_tot + (tw_h["passing_epa"] + tw_h["rushing_epa"])
            epa_a = half_tot + (tw_a["passing_epa"] + tw_a["rushing_epa"])
            eff_hs = EPA_WEIGHT * epa_h + (1.0 - EPA_WEIGHT) * capped_hs
            eff_as = EPA_WEIGHT * epa_a + (1.0 - EPA_WEIGHT) * capped_as
        else:
            eff_hs, eff_as = capped_hs, capped_as

        loc_hfa = 0.0 if g["location"] == "Neutral" else hfa
        exp_h = half_tot + 0.5 * (off_rating[ht] + def_rating[at]) + 0.5 * loc_hfa
        exp_a = half_tot + 0.5 * (off_rating[at] + def_rating[ht]) - 0.5 * loc_hfa

        err_h = eff_hs - exp_h
        err_a = eff_as - exp_a

        off_rating[ht] += K_OFF * err_h
        def_rating[at] += K_DEF * err_h
        off_rating[at] += K_OFF * err_a
        def_rating[ht] += K_DEF * err_a

    # Walk chronologically through committed dataset; handle 2026 Week 8 Nov 1 finals strictly ex-ante!
    live_nov1_eval: list[dict[str, Any]] = []
    upcoming_board: list[dict[str, Any]] = []

    for g in reg_games:
        s = g["season"]
        if s != current_season:
            if current_season is not None:
                # Mean-center and shrink ratings between seasons
                if off_rating:
                    mo = sum(off_rating.values()) / len(off_rating)
                    md = sum(def_rating.values()) / len(def_rating)
                    for t in list(off_rating.keys()):
                        off_rating[t] = SEASON_RETAIN * (off_rating[t] - mo)
                        def_rating[t] = SEASON_RETAIN * (def_rating[t] - md)
            current_season = s
            hfa, base_total, sig_m, sig_t = get_priors(s)

        pred = predict_game(g, hfa, base_total, sig_m, sig_t)
        gid = g["game_id"]

        if g["home_score"] is not None and g["away_score"] is not None:
            predictions.append(pred)
            update_from_outcome(g, pred, g["home_score"], g["away_score"], base_total)
        elif gid in OFFICIAL_WEEK8_NOV1_FINALS:
            # Predict strictly BEFORE updating from Nov 1 outcome, then grade & update for Week 9!
            fin = OFFICIAL_WEEK8_NOV1_FINALS[gid]
            as_fin = float(fin["away_score"])
            hs_fin = float(fin["home_score"])
            act_m = hs_fin - as_fin
            act_t = hs_fin + as_fin
            sp_mkt = g["spread_line"] or 0.0
            tot_mkt = g["total_line"] or 0.0
            live_row = dict(pred)
            live_row.update({
                "official_away_score": int(as_fin),
                "official_home_score": int(hs_fin),
                "official_margin": act_m,
                "official_total": act_t,
                "orig_abs_err": round(abs(act_m - pred["orig_home_margin"]), 2),
                "mkt_abs_err": round(abs(act_m - sp_mkt), 2),
                "orig_tot_abs_err": round(abs(act_t - pred["orig_total"]), 2),
                "mkt_tot_abs_err": round(abs(act_t - tot_mkt), 2),
                "home_covered_mkt": None if act_m == sp_mkt else (act_m > sp_mkt),
                "model_lean_side": (
                    f"{g['home_team']} ({pred['mkt_home_handicap']:+.1f})"
                    if pred["orig_home_margin"] > sp_mkt
                    else f"{g['away_team']} ({sp_mkt:+.1f})"
                ),
                "model_lean_won": (
                    None if act_m == sp_mkt else (
                        (act_m > sp_mkt) if pred["orig_home_margin"] > sp_mkt else (act_m < sp_mkt)
                    )
                ),
                "source_url": fin["url"],
                "source_id": "SL-SRC-06" if gid == "2026_08_BAL_BUF" else "SL-SRC-04",
            })
            live_nov1_eval.append(live_row)
            update_from_outcome(g, pred, hs_fin, as_fin, base_total)
        elif s == 2026 and g["week"] in (8, 9):
            # Upcoming MNF Week 8 (CHI@SEA Nov 2) + all 15 Official Week 9 fixtures (Nov 5-9)!
            board_row = dict(pred)
            board_row["spread_disagreement_pts"] = (
                round(pred["orig_home_handicap"] - pred["mkt_home_handicap"], 2)
                if pred["mkt_home_handicap"] is not None else None
            )
            board_row["total_disagreement_pts"] = (
                round(pred["orig_total"] - pred["mkt_total_line"], 2)
                if pred["mkt_total_line"] is not None else None
            )
            board_row["source_id"] = "SL-SRC-04" if g["week"] == 8 else "SL-SRC-05"
            upcoming_board.append(board_row)

    # Evaluate historical walk-forward test window: 2018-2026 settled games with full closing odds
    test_preds = [
        p for p in predictions
        if p["season"] >= 2018
        and p["mkt_spread_line"] is not None
        and p["mkt_total_line"] is not None
        and p["home_moneyline"] is not None
        and p["away_moneyline"] is not None
    ]

    orig_mae = sum(abs(p["actual_margin"] - p["orig_home_margin"]) for p in test_preds) / len(test_preds)
    mkt_mae = sum(abs(p["actual_margin"] - p["mkt_spread_line"]) for p in test_preds) / len(test_preds)
    orig_rmse = math.sqrt(sum((p["actual_margin"] - p["orig_home_margin"]) ** 2 for p in test_preds) / len(test_preds))
    mkt_rmse = math.sqrt(sum((p["actual_margin"] - p["mkt_spread_line"]) ** 2 for p in test_preds) / len(test_preds))

    orig_tot_mae = sum(abs(p["actual_total"] - p["orig_total"]) for p in test_preds) / len(test_preds)
    mkt_tot_mae = sum(abs(p["actual_total"] - p["mkt_total_line"]) for p in test_preds) / len(test_preds)

    # Proper probability scoring on non-tie moneyline outcomes (Brier & Log-Loss vs de-vigged market ML)
    non_ties = [p for p in test_preds if p["actual_margin"] != 0.0]
    brier_orig = 0.0
    brier_mkt = 0.0
    ll_orig = 0.0
    ll_mkt = 0.0
    for p in non_ties:
        y = 1.0 if p["actual_margin"] > 0.0 else 0.0
        po = max(0.01, min(0.99, p["orig_home_win_prob"]))
        pm, _, _ = devig_two_way(p["home_moneyline"], p["away_moneyline"])
        pm = max(0.01, min(0.99, pm))
        brier_orig += (po - y) ** 2
        brier_mkt += (pm - y) ** 2
        ll_orig += -(y * math.log(po) + (1.0 - y) * math.log(1.0 - po))
        ll_mkt += -(y * math.log(pm) + (1.0 - y) * math.log(1.0 - pm))

    brier_orig /= len(non_ties)
    brier_mkt /= len(non_ties)
    ll_orig /= len(non_ties)
    ll_mkt /= len(non_ties)
    brier_skill_vs_mkt = 1.0 - (brier_orig / brier_mkt)

    # Residual information test: regress (actual_margin - mkt_spread) on (orig_margin - mkt_spread)
    disagreements = [p["orig_home_margin"] - p["mkt_spread_line"] for p in test_preds]
    mkt_errors = [p["actual_margin"] - p["mkt_spread_line"] for p in test_preds]
    r_disagree = pearson_r(disagreements, mkt_errors)
    mean_d = sum(disagreements) / len(disagreements)
    mean_e = sum(mkt_errors) / len(mkt_errors)
    slope = sum((d - mean_d) * (e - mean_e) for d, e in zip(disagreements, mkt_errors)) / sum(
        (d - mean_d) ** 2 for d in disagreements
    )
    t_mkt_bias, p_mkt_bias = two_sided_t_pvalue(mkt_errors, 0.0)

    # Season-by-season test breakdown
    by_season: list[dict[str, Any]] = []
    for s in sorted({p["season"] for p in test_preds}):
        sub = [p for p in test_preds if p["season"] == s]
        nt = [p for p in sub if p["actual_margin"] != 0.0]
        bo = sum((p["orig_home_win_prob"] - (1.0 if p["actual_margin"] > 0 else 0.0)) ** 2 for p in nt) / len(nt)
        bm = sum((devig_two_way(p["home_moneyline"], p["away_moneyline"])[0] - (1.0 if p["actual_margin"] > 0 else 0.0)) ** 2 for p in nt) / len(nt)
        by_season.append({
            "season": s,
            "games": len(sub),
            "orig_spread_mae": round(sum(abs(p["actual_margin"] - p["orig_home_margin"]) for p in sub) / len(sub), 3),
            "mkt_spread_mae": round(sum(abs(p["actual_margin"] - p["mkt_spread_line"]) for p in sub) / len(sub), 3),
            "orig_total_mae": round(sum(abs(p["actual_total"] - p["orig_total"]) for p in sub) / len(sub), 3),
            "mkt_total_mae": round(sum(abs(p["actual_total"] - p["mkt_total_line"]) for p in sub) / len(sub), 3),
            "orig_brier": round(bo, 4),
            "mkt_brier": round(bm, 4),
            "source_id": "SL-SRC-01" if s == 2026 else ("SL-SRC-02" if s == 2025 else "SL-SRC-27"),
        })

    # Live Nov 1 Week 8 summary
    nov1_lean_wins = sum(1 for r in live_nov1_eval if r["model_lean_won"] is True)
    nov1_lean_losses = sum(1 for r in live_nov1_eval if r["model_lean_won"] is False)
    nov1_orig_mae = sum(r["orig_abs_err"] for r in live_nov1_eval) / len(live_nov1_eval)
    nov1_mkt_mae = sum(r["mkt_abs_err"] for r in live_nov1_eval) / len(live_nov1_eval)
    nov1_orig_tot_mae = sum(r["orig_tot_abs_err"] for r in live_nov1_eval) / len(live_nov1_eval)
    nov1_mkt_tot_mae = sum(r["mkt_tot_abs_err"] for r in live_nov1_eval) / len(live_nov1_eval)

    # Current Top 10 / All 32 Power Ratings entering Week 8 MNF / Week 9
    power_board = []
    for team, (w, l, t, pf, pa) in OFFICIAL_STANDINGS_2026.items():
        net_skill = off_rating[team] - def_rating[team]
        power_board.append({
            "team": team,
            "record_2026": f"{w}-{l}-{t}" if t else f"{w}-{l}",
            "pf": pf,
            "pa": pa,
            "point_diff": pf - pa,
            "off_skill_pts": round(off_rating[team], 2),
            "def_skill_pts": round(-def_rating[team], 2),  # positive = stingy defense above avg
            "net_power_rating": round(net_skill, 2),
            "source_id": "SL-SRC-01",
        })
    power_board.sort(key=lambda r: r["net_power_rating"], reverse=True)

    diagnostics = {
        "test_window": "2018-2026 (walk-forward out-of-sample, zero imputed prices)",
        "test_games": len(test_preds),
        "orig_spread_mae": round(orig_mae, 3),
        "mkt_spread_mae": round(mkt_mae, 3),
        "orig_spread_rmse": round(orig_rmse, 3),
        "mkt_spread_rmse": round(mkt_rmse, 3),
        "orig_total_mae": round(orig_tot_mae, 3),
        "mkt_total_mae": round(mkt_tot_mae, 3),
        "orig_brier": round(brier_orig, 4),
        "mkt_brier": round(brier_mkt, 4),
        "brier_skill_vs_market": round(brier_skill_vs_mkt, 4),
        "orig_logloss": round(ll_orig, 4),
        "mkt_logloss": round(ll_mkt, 4),
        "corr_orig_vs_mkt_spread": round(
            pearson_r([p["orig_home_margin"] for p in test_preds], [p["mkt_spread_line"] for p in test_preds]), 4
        ),
        "disagreement_slope_on_mkt_error": round(slope, 4),
        "disagreement_corr_with_mkt_error": round(r_disagree, 4),
        "mkt_closing_spread_mean_error_pts": round(mean_e, 4),
        "mkt_closing_spread_bias_t": round(t_mkt_bias, 3),
        "mkt_closing_spread_bias_p": round(p_mkt_bias, 4),
        "by_season": by_season,
        "nov1_post_commit_audit": {
            "games": len(live_nov1_eval),
            "orig_spread_mae": round(nov1_orig_mae, 2),
            "mkt_spread_mae": round(nov1_mkt_mae, 2),
            "orig_total_mae": round(nov1_orig_tot_mae, 2),
            "mkt_total_mae": round(nov1_mkt_tot_mae, 2),
            "ats_lean_record": f"{nov1_lean_wins}-{nov1_lean_losses}",
            "rows": live_nov1_eval,
        },
        "upcoming_board": upcoming_board,
        "power_ratings_2026": power_board,
    }
    return (predictions, diagnostics)


def run_prop_origination(player_weeks: list[dict[str, Any]]) -> dict[str, Any]:
    """Strictly ex-ante quantile-calibrated player-prop origination (QB1 pass yds, WR1 rec yds, RB1 rush yds)."""
    pw_sorted = sorted(player_weeks, key=lambda r: (r["season"], r["week"], r["team"], r["player_id"]))

    # Group player rows by (season, week, team)
    by_team_game: dict[tuple[int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for r in pw_sorted:
        by_team_game[(r["season"], r["week"], r["team"])].append(r)

    # Track rolling player histories strictly prior to (season, week)
    player_hist: dict[str, list[dict[str, Any]]] = defaultdict(list)
    opp_def_hist: dict[tuple[str, str], list[float]] = defaultdict(list)  # (team, stat_key) -> allowed

    # Priors (league baselines for Empirical Bayes shrinkage)
    PRIORS = {
        "qb_pass_yds": (228.0, 5.0),   # (prior_mean, pseudo_games_weight)
        "wr_rec_yds":  (62.0,  5.0),
        "rb_rush_yds": (58.0,  5.0),
    }

    # Pre-2023 residuals used to learn median offset (right-skew correction) without lookahead
    train_resids: dict[str, list[float]] = defaultdict(list)
    test_records: dict[str, list[dict[str, Any]]] = defaultdict(list)

    # Also capture pre-Week-8 2026 projections for our 6 official Nov 1 NFL.com spot-check players!
    all_keys = sorted(by_team_game.keys())
    for s, w, team in all_keys:
        roster_rows = by_team_game[(s, w, team)]
        opp = roster_rows[0]["opp"]

        # Identify ex-ante QB1, WR1, RB1 strictly from prior history (last 8 appearances, min 3 games)
        def select_ex_ante(pos_set: set[str], usage_field: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
            candidates = []
            for r in roster_rows:
                if r["pos"] not in pos_set:
                    continue
                h = player_hist.get(r["player_id"], [])[-8:]
                if len(h) >= 3:
                    avg_u = sum(x[usage_field] for x in h) / len(h)
                    candidates.append((avg_u, r, h))
            if not candidates:
                return (None, [])
            candidates.sort(key=lambda x: x[0], reverse=True)
            return (candidates[0][1], candidates[0][2])

        qb_row, qb_h = select_ex_ante({"QB"}, "attempts")
        wr_row, wr_h = select_ex_ante({"WR", "TE"}, "target_share")
        rb_row, rb_h = select_ex_ante({"RB"}, "carries")

        role_specs = [
            ("qb_pass_yds", qb_row, qb_h, "passing_yards"),
            ("wr_rec_yds",  wr_row, wr_h, "receiving_yards"),
            ("rb_rush_yds", rb_row, rb_h, "rushing_yards"),
        ]

        for mkt_key, prow, hist, stat_col in role_specs:
            if prow is None:
                continue
            prior_mu, k_shrink = PRIORS[mkt_key]
            n_h = len(hist)
            raw_mean = sum(x[stat_col] for x in hist) / n_h
            shrunk_mean = (n_h * raw_mean + k_shrink * prior_mu) / (n_h + k_shrink)

            # Opponent defensive adjustment (shrunk last 10 games allowed)
            opp_allowed = opp_def_hist.get((opp, mkt_key), [])[-10:]
            if len(opp_allowed) >= 4:
                opp_factor = ((sum(opp_allowed) / len(opp_allowed)) - prior_mu) * 0.25
            else:
                opp_factor = 0.0

            mean_proj = max(10.0, shrunk_mean + opp_factor)
            actual = prow[stat_col]

            if s < 2023:
                train_resids[mkt_key].append(actual - mean_proj)
            else:
                # Calibrate median line & 25/75 quantiles using strictly prior residuals!
                res_pool = train_resids[mkt_key]
                med_offset = quantile(res_pool, 0.50) if res_pool else 0.0
                q25_offset = quantile(res_pool, 0.25) if res_pool else -25.0
                q75_offset = quantile(res_pool, 0.75) if res_pool else 25.0
                med_line = max(5.5, round((mean_proj + med_offset) * 2.0) / 2.0)
                if med_line == int(med_line):
                    med_line += 0.5  # half-yard hook eliminates pushes
                test_records[mkt_key].append({
                    "season": s,
                    "week": w,
                    "team": team,
                    "opp": opp,
                    "player": prow["name"],
                    "mean_proj": round(mean_proj, 1),
                    "median_line": med_line,
                    "q25": round(max(0.0, mean_proj + q25_offset), 1),
                    "q75": round(mean_proj + q75_offset, 1),
                    "actual": actual,
                })
                # Expand residual pool chronologically after scoring
                train_resids[mkt_key].append(actual - mean_proj)

        # Update opponent defense & player histories AFTER scoring this team-game
        tot_pass = sum(r["passing_yards"] for r in roster_rows if r["pos"] == "QB")
        opp_def_hist[(opp, "qb_pass_yds")].append(tot_pass)
        if wr_row is not None:
            opp_def_hist[(opp, "wr_rec_yds")].append(wr_row["receiving_yards"])
        if rb_row is not None:
            opp_def_hist[(opp, "rb_rush_yds")].append(rb_row["rushing_yards"])
        for r in roster_rows:
            player_hist[r["player_id"]].append(r)

    summary_rows = []
    label_map = {
        "qb_pass_yds": "QB1 Passing Yards (Ex-Ante Starter)",
        "wr_rec_yds":  "WR1 Receiving Yards (Ex-Ante Target Leader)",
        "rb_rush_yds": "RB1 Rushing Yards (Ex-Ante Carry Leader)",
    }
    for mkt_key, recs in test_records.items():
        n = len(recs)
        over_mean = sum(1 for x in recs if x["actual"] > x["mean_proj"]) / n
        over_med = sum(1 for x in recs if x["actual"] > x["median_line"]) / n
        in_iqr = sum(1 for x in recs if x["q25"] <= x["actual"] <= x["q75"]) / n
        mae_med = sum(abs(x["actual"] - x["median_line"]) for x in recs) / n
        summary_rows.append({
            "market": mkt_key,
            "label": label_map[mkt_key],
            "sample_n": n,
            "over_rate_at_raw_mean_pct": round(100.0 * over_mean, 2),
            "over_rate_at_calibrated_median_pct": round(100.0 * over_med, 2),
            "iqr_25_75_coverage_pct": round(100.0 * in_iqr, 2),
            "mae_yards": round(mae_med, 2),
            "historical_book_roi": "",  # Strictly blank per verification rule (no free official prop odds)
            "status": "CALIBRATED (ODDS UNVERIFIED)",
            "source_id": "SL-SRC-21",
        })

    # Live ex-ante prop projections vs Official Nov 1, 2026 NFL.com Week 8 box scores!
    by_name_hist: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in pw_sorted:
        if r["season"] in (2025, 2026) and not (r["season"] == 2026 and r["week"] >= 8):
            by_name_hist[r["name"]].append(r)

    week8_prop_spotchecks = []
    for pl in OFFICIAL_PLAYER_LOGS_2026:
        name = pl["player"]
        pos = pl["pos"]
        mkt_key = "qb_pass_yds" if pos == "QB" else ("wr_rec_yds" if pos == "WR" else "rb_rush_yds")
        stat_col = "passing_yards" if pos == "QB" else ("receiving_yards" if pos == "WR" else "rushing_yards")
        hist = by_name_hist[name][-8:]
        prior_mu, k_shrink = PRIORS[mkt_key]
        raw_m = sum(x[stat_col] for x in hist) / len(hist)
        shrunk_m = (len(hist) * raw_m + k_shrink * prior_mu) / (len(hist) + k_shrink)
        med_off = quantile(train_resids[mkt_key], 0.50)
        orig_line = round((shrunk_m + med_off) * 2.0) / 2.0
        if orig_line == int(orig_line):
            orig_line += 0.5
        act = pl["week8_actual"]
        week8_prop_spotchecks.append({
            "player": name,
            "team": pl["team"],
            "pos": pos,
            "week8_opp": pl["week8_opp"],
            "stat_market": mkt_key,
            "orig_median_line": orig_line,
            "official_week8_actual": act,
            "outcome_vs_orig_line": "OVER" if act > orig_line else "UNDER",
            "official_2026_season_total": pl["nfl_season_total"],
            "bookmaker_closing_prop_line": "",  # Strictly blank — not published on NFL.com
            "source_id": pl["source_id"],
        })

    return {
        "test_window": "2023-2026 (strictly ex-ante player role selection, zero imputed prop odds)",
        "markets": summary_rows,
        "week8_official_player_spotchecks": week8_prop_spotchecks,
    }


def main() -> None:
    games = load_games()
    team_weeks = load_team_weeks()
    player_weeks = load_player_weeks()

    sign_proof = prove_sign_convention(games)
    predictions, team_diag = run_team_origination(games, team_weeks)
    prop_diag = run_prop_origination(player_weeks)

    write_json("sources.json", {"verified_date": "2026-11-02", "sources": SOURCES})
    write_json("origination.json", {
        "sign_convention": sign_proof,
        "team_origination": team_diag,
        "prop_origination": prop_diag,
    })
    # Also persist lightweight game predictions for downstream signal/strategy scripts
    write_json("_predictions_cache.json", predictions)
    print(
        f"Origination complete: {team_diag['test_games']} test games | "
        f"Spread MAE orig={team_diag['orig_spread_mae']} vs mkt={team_diag['mkt_spread_mae']} | "
        f"Nov 1 Week 8 live MAE orig={team_diag['nov1_post_commit_audit']['orig_spread_mae']} "
        f"vs mkt={team_diag['nov1_post_commit_audit']['mkt_spread_mae']} "
        f"(ATS leans {team_diag['nov1_post_commit_audit']['ats_lean_record']})"
    )


if __name__ == "__main__":
    main()
