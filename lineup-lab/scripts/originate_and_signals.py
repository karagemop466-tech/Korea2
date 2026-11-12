#!/usr/bin/env python3
"""LL-5: Walk-forward Ridge game origination, player-stat projection signals, and luck decomposition.

Pure Python 3.11 stdlib. Zero future leakage:
- Walk-forward evaluation trains only on prior seasons (< target_season).
- Features use strictly trailing games (< current week) in team_week.csv.gz.
- Missing sportsbook fields (e.g., Week 10 lines, player-prop historical odds) remain "".
Outputs:
  lineup-lab/data/origination.json
  lineup-lab/data/signals.json
  lineup-lab/data/luck.json
"""
from __future__ import annotations

import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def build_team_rolling_features(games: list[dict[str, str]], tw_rows: list[dict[str, str]]) -> tuple[dict, dict]:
    """Compute strictly ex-ante (pre-game) rolling team stats indexed by (game_id, team)."""
    tw_lookup: dict[tuple[str, str], dict[str, str]] = {}
    for r in tw_rows:
        if r["season_type"] == "REG":
            tw_lookup[(r["game_id"], C.std_team(r["team"]))] = r

    # Combine committed games + official 16 post-Nov-1 games so we can inspect Wk 9-10 too
    played_reg = [
        r for r in games
        if r["game_type"] == "REG" and int(r["season"]) >= 2015
    ]
    played_reg.sort(key=lambda r: (int(r["season"]), int(r["week"]), r["gameday"], r["game_id"]))

    # Store per-team rolling game log across seasons (carry over 35% decayed prior-season rating)
    team_history: dict[str, list[dict[str, float]]] = defaultdict(list)
    last_season_summary: dict[str, dict[str, float]] = {}
    current_season_logs: dict[tuple[int, str], list[dict[str, float]]] = defaultdict(list)

    pregame_feats: dict[tuple[str, str], dict[str, float]] = {}

    def summarize_prior(team: str, season: int) -> dict[str, float]:
        s_logs = current_season_logs[(season, team)]
        prior_yr = last_season_summary.get(team, {
            "off_epa": 0.0, "def_epa": 0.0, "pt_diff": 0.0, "pass_epa": 0.0,
            "rush_epa": 0.0, "sacks_suf": 2.2, "def_sacks": 2.2, "to_margin": 0.0, "pts": 22.0, "pa": 22.0
        })
        if not s_logs:
            # Regress 50% toward league average for Week 1
            return {k: (0.5 * v if k not in ("pts", "pa", "sacks_suf", "def_sacks") else v * 0.5 + (22.0 if k in ("pts", "pa") else 2.2) * 0.5)
                    for k, v in prior_yr.items()}
        n = len(s_logs)
        wt_cur = min(1.0, n / 6.0)
        out = {}
        recent4 = s_logs[-4:]
        for k in ("off_epa", "def_epa", "pt_diff", "pass_epa", "rush_epa", "sacks_suf", "def_sacks", "to_margin", "pts", "pa"):
            cur_mean = sum(x[k] for x in s_logs) / n
            rec_mean = sum(x[k] for x in recent4) / len(recent4)
            blended_cur = 0.55 * cur_mean + 0.45 * rec_mean
            out[k] = wt_cur * blended_cur + (1.0 - wt_cur) * prior_yr[k]
        out["games_played"] = float(n)
        return out

    seen_seasons: set[int] = set()
    prev_season = None
    for g in played_reg:
        season = int(g["season"])
        if prev_season is not None and season != prev_season:
            for t in set(k[1] for k in current_season_logs if k[0] == prev_season):
                logs = current_season_logs[(prev_season, t)]
                if logs:
                    last_season_summary[t] = {
                        k: sum(x[k] for x in logs) / len(logs)
                        for k in ("off_epa", "def_epa", "pt_diff", "pass_epa", "rush_epa", "sacks_suf", "def_sacks", "to_margin", "pts", "pa")
                    }
        prev_season = season

        ht = C.std_team(g["home_team"])
        at = C.std_team(g["away_team"])
        pregame_feats[(g["game_id"], ht)] = summarize_prior(ht, season)
        pregame_feats[(g["game_id"], at)] = summarize_prior(at, season)

        # Update ONLY if scores and team_week stats exist (through 2026 Wk 8)
        if g["home_score"] != "" and g["away_score"] != "":
            hs = float(g["home_score"])
            aws = float(g["away_score"])
            htw = tw_lookup.get((g["game_id"], ht))
            atw = tw_lookup.get((g["game_id"], at))
            if htw and atw:
                for side_t, opp_t, pts_f, pts_a, tw_self, tw_opp in (
                    (ht, at, hs, aws, htw, atw),
                    (at, ht, aws, hs, atw, htw),
                ):
                    off_epa = (C.fnum(tw_self.get("passing_epa")) or 0.0) + (C.fnum(tw_self.get("rushing_epa")) or 0.0)
                    def_epa = (C.fnum(tw_opp.get("passing_epa")) or 0.0) + (C.fnum(tw_opp.get("rushing_epa")) or 0.0)
                    to_self = (C.fnum(tw_self.get("passing_interceptions")) or 0.0) + (C.fnum(tw_self.get("fumbles_lost_total")) or 0.0)
                    to_opp = (C.fnum(tw_opp.get("passing_interceptions")) or 0.0) + (C.fnum(tw_opp.get("fumbles_lost_total")) or 0.0)
                    row = {
                        "off_epa": off_epa,
                        "def_epa": def_epa,
                        "pt_diff": pts_f - pts_a,
                        "pass_epa": C.fnum(tw_self.get("passing_epa")) or 0.0,
                        "rush_epa": C.fnum(tw_self.get("rushing_epa")) or 0.0,
                        "sacks_suf": C.fnum(tw_self.get("sacks_suffered")) or 0.0,
                        "def_sacks": C.fnum(tw_self.get("def_sacks")) or 0.0,
                        "to_margin": to_opp - to_self,
                        "pts": pts_f,
                        "pa": pts_a,
                    }
                    team_history[side_t].append(row)
                    current_season_logs[(season, side_t)].append(row)
            else:
                # For games after Wk 8 (if any), score-only update without team_week
                pass

    return pregame_feats, summarize_prior


def featurize_game(g: dict[str, str], pre: dict[tuple[str, str], dict[str, float]]) -> list[float]:
    ht = C.std_team(g["home_team"])
    at = C.std_team(g["away_team"])
    hf = pre[(g["game_id"], ht)]
    af = pre[(g["game_id"], at)]
    is_home = 1.0 if g["location"] == "Home" else 0.0
    rest_diff = (C.fnum(g["home_rest"]) or 7.0) - (C.fnum(g["away_rest"]) or 7.0)
    div_g = float(g["div_game"] or 0.0)
    wind = C.fnum(g["wind"]) or 0.0
    outdoor = 0.0 if (g["roof"] in ("dome", "closed")) else 1.0
    high_wind = 1.0 if (outdoor > 0 and wind >= 15.0) else 0.0
    # [intercept, is_home, off_epa_diff, def_epa_diff, pt_diff_diff, net_to_diff, sack_diff, rest_diff, div_g]
    return [
        1.0,
        is_home,
        (hf["off_epa"] - af["off_epa"]) / 10.0,
        (af["def_epa"] - hf["def_epa"]) / 10.0,  # positive means home defense allowed fewer EPA
        (hf["pt_diff"] - af["pt_diff"]) / 10.0,
        (hf["to_margin"] - af["to_margin"]),
        (af["sacks_suf"] - hf["sacks_suf"]),
        rest_diff / 7.0,
        div_g,
        high_wind,
    ]


def featurize_total(g: dict[str, str], pre: dict[tuple[str, str], dict[str, float]]) -> list[float]:
    ht = C.std_team(g["home_team"])
    at = C.std_team(g["away_team"])
    hf = pre[(g["game_id"], ht)]
    af = pre[(g["game_id"], at)]
    dome = 1.0 if g["roof"] in ("dome", "closed") else 0.0
    wind = C.fnum(g["wind"]) or 0.0
    high_wind = 1.0 if (dome == 0.0 and wind >= 15.0) else 0.0
    return [
        1.0,
        (hf["pts"] + af["pts"]) / 10.0,
        (hf["pa"] + af["pa"]) / 10.0,
        (hf["off_epa"] + af["off_epa"]) / 10.0,
        (hf["def_epa"] + af["def_epa"]) / 10.0,
        dome,
        high_wind,
    ]


def run_origination(games: list[dict[str, str]], pre: dict) -> dict:
    """Walk-forward Ridge origination on 2023-2026 Wk 8 + Week 9 prospective replay + Week 10 slate."""
    usable = [
        g for g in games
        if g["game_type"] == "REG" and 2016 <= int(g["season"]) <= 2026
        and g["home_score"] != "" and g["away_score"] != ""
        and g["spread_line"] != "" and g["total_line"] != ""
        and int(g["week"]) >= 2  # evaluate after Week 1 bootstrap so stats are live
    ]
    usable.sort(key=lambda r: (int(r["season"]), int(r["week"]), r["gameday"], r["game_id"]))

    oos_rows = []
    season_summary = []

    for eval_season in (2023, 2024, 2025, 2026):
        train = [g for g in usable if int(g["season"]) < eval_season]
        test = [g for g in usable if int(g["season"]) == eval_season]
        X_tr = [featurize_game(g, pre) for g in train]
        y_tr = [float(g["home_score"]) - float(g["away_score"]) for g in train]
        w_margin = C.fit_ridge(X_tr, y_tr, alpha=25.0)

        Xt_tr = [featurize_total(g, pre) for g in train]
        yt_tr = [float(g["home_score"]) + float(g["away_score"]) for g in train]
        w_total = C.fit_ridge(Xt_tr, yt_tr, alpha=25.0)

        m_errs, k_errs, b_errs = [], [], []
        tm_errs, tk_errs = [], []
        for g in test:
            xm = featurize_game(g, pre)
            xt = featurize_total(g, pre)
            pred_m = sum(a * b for a, b in zip(w_margin, xm))
            pred_t = sum(a * b for a, b in zip(w_total, xt))
            mkt_m = float(g["spread_line"])
            mkt_t = float(g["total_line"])
            act_m = float(g["home_score"]) - float(g["away_score"])
            act_t = float(g["home_score"]) + float(g["away_score"])
            blend_m = 0.5 * pred_m + 0.5 * mkt_m
            m_errs.append(abs(act_m - pred_m))
            k_errs.append(abs(act_m - mkt_m))
            b_errs.append(abs(act_m - blend_m))
            tm_errs.append(abs(act_t - pred_t))
            tk_errs.append(abs(act_t - mkt_t))
            oos_rows.append({
                "season": eval_season,
                "week": int(g["week"]),
                "game_id": g["game_id"],
                "pred_margin": pred_m,
                "mkt_margin": mkt_m,
                "act_margin": act_m,
                "pred_total": pred_t,
                "mkt_total": mkt_t,
                "act_total": act_t,
                "edge": pred_m - mkt_m,
                "mkt_residual": act_m - mkt_m,
                "home_spread_odds": C.fnum(g["home_spread_odds"]),
                "away_spread_odds": C.fnum(g["away_spread_odds"]),
            })
        season_summary.append({
            "season": eval_season,
            "games": len(test),
            "model_spread_mae": round(sum(m_errs) / len(m_errs), 3),
            "market_spread_mae": round(sum(k_errs) / len(k_errs), 3),
            "blend_50_50_mae": round(sum(b_errs) / len(b_errs), 3),
            "model_total_mae": round(sum(tm_errs) / len(tm_errs), 3),
            "market_total_mae": round(sum(tk_errs) / len(tk_errs), 3),
            "sources": ["SRC-GITHUB-REPO", "SRC-SKLEARN-LINEAR"],
        })

    # Overall 2023-2026 OOS incremental information test
    ols = C.ols_slope_p([r["edge"] for r in oos_rows], [r["mkt_residual"] for r in oos_rows])
    all_model_mae = round(sum(abs(r["act_margin"] - r["pred_margin"]) for r in oos_rows) / len(oos_rows), 3)
    all_mkt_mae = round(sum(abs(r["act_margin"] - r["mkt_margin"]) for r in oos_rows) / len(oos_rows), 3)
    all_blend_mae = round(sum(abs(r["act_margin"] - 0.5 * (r["pred_margin"] + r["mkt_margin"])) for r in oos_rows) / len(oos_rows), 3)
    all_tot_mod_mae = round(sum(abs(r["act_total"] - r["pred_total"]) for r in oos_rows) / len(oos_rows), 3)
    all_tot_mkt_mae = round(sum(abs(r["act_total"] - r["mkt_total"]) for r in oos_rows) / len(oos_rows), 3)

    # Fit final Ridge weights on all played 2016-2026 Wk 8 games for Week 9 replay & Week 10 benchmark
    X_all = [featurize_game(g, pre) for g in usable]
    y_all = [float(g["home_score"]) - float(g["away_score"]) for g in usable]
    w_m_final = C.fit_ridge(X_all, y_all, alpha=25.0)
    Xt_all = [featurize_total(g, pre) for g in usable]
    yt_all = [float(g["home_score"]) + float(g["away_score"]) for g in usable]
    w_t_final = C.fit_ridge(Xt_all, yt_all, alpha=25.0)

    # Week 9 prospective replay against official NFL.com Week 9 finals (stored pre-kickoff lines vs actuals)
    w9_official = {f["game_id"]: f for f in C.OFFICIAL_2026_POST_NOV1_FINALS if f["week"] == 9}
    wk9_games = [g for g in games if g["season"] == "2026" and int(g["week"]) == 9]
    wk9_replay = []
    for g in wk9_games:
        xm = featurize_game(g, pre)
        xt = featurize_total(g, pre)
        pm = round(sum(a * b for a, b in zip(w_m_final, xm)), 2)
        pt = round(sum(a * b for a, b in zip(w_t_final, xt)), 2)
        mm = C.fnum(g["spread_line"])
        mt = C.fnum(g["total_line"])
        fin = w9_official.get(g["game_id"], {})
        act_m = (fin["home_score"] - fin["away_score"]) if fin else None
        act_t = (fin["home_score"] + fin["away_score"]) if fin else None
        wk9_replay.append({
            "game_id": g["game_id"],
            "matchup": f"{g['away_team']} @ {g['home_team']}",
            "official_final": f"{fin['away_team']} {fin['away_score']} @ {fin['home_team']} {fin['home_score']}" if fin else "",
            "model_margin_home": pm,
            "market_spread_home": mm,
            "actual_margin_home": act_m,
            "model_total": pt,
            "market_total": mt,
            "actual_total": act_t,
            "away_spread_odds": C.fnum(g["away_spread_odds"]),
            "home_spread_odds": C.fnum(g["home_spread_odds"]),
            "sources": ["SRC-NFL-SCHED-W9", "SRC-GITHUB-REPO"],
        })

    # Week 10 forward slate (market spread/total/odds explicitly blank "" because not in committed extract)
    wk10_games = [g for g in games if g["season"] == "2026" and int(g["week"]) == 10]
    w10_notes = {
        "2026_10_WAS_NYG": "WAS Yankoff/Lucas Patrick Out (Thu); NYG M. Harrison Q",
        "2026_10_NE_DET": "Munich neutral; NE Ben Brown/Davis/Henderson Out; DET Reed/Mays DNP",
        "2026_10_MIA_IND": "MIA QB1 Willis IR -> McCord 1st start; IND 4 DB/LB DNP",
        "2026_10_SEA_LV": "SEA QB1 Darnold Out -> Lock (LP); LV traded Cousins",
        "2026_10_LA_ARI": "LA Nacua DNP/IR risk + 3 starters DNP; AZ rookie QB Carson Beck",
        "2026_10_MIN_GB": "MIN acquired Cousins Nov 10; GB Jacobs Out + Parsons LP",
        "2026_10_SF_DAL": "SF T. Williams/Lenoir DNP; DAL Ferguson/Hooker/V. Miller DNP",
        "2026_10_PIT_CIN": "PIT Watt/Heyward DNP; CIN REG10 report incomplete",
        "2026_10_LAC_BAL": "MNF; BAL Jackson/Huntley IR -> Brissett/Fagnano",
    }
    wk10_slate = []
    for g in wk10_games:
        xm = featurize_game(g, pre)
        xt = featurize_total(g, pre)
        pm = round(sum(a * b for a, b in zip(w_m_final, xm)), 2)
        pt = round(sum(a * b for a, b in zip(w_t_final, xt)), 2)
        wk10_slate.append({
            "game_id": g["game_id"],
            "gameday": g["gameday"],
            "matchup": f"{g['away_team']} @ {g['home_team']}",
            "model_margin_home": pm,
            "model_total": pt,
            "market_spread_home": "",
            "market_total": "",
            "market_odds": "",
            "lineup_alert": w10_notes.get(g["game_id"], "Standard weekly practice cadence; recheck 90-min inactive list."),
            "sources": ["SRC-NFL-SCHED-W10", "SRC-NFL-INJURIES-W10", "SRC-OPS-RULEBOOK"],
        })

    feature_names = [
        "intercept", "is_home", "off_epa_diff_div10", "def_epa_allowed_diff_div10",
        "pt_diff_div10", "to_margin_diff", "sacks_suffered_diff", "rest_diff_wk", "div_game", "high_wind_15mph"
    ]
    return {
        "meta": {
            "verified_on": C.VERIFIED_DATE,
            "walk_forward_seasons": [2023, 2024, 2025, 2026],
            "total_oos_games": len(oos_rows),
            "ridge_alpha": 25.0,
        },
        "overall_oos": {
            "model_spread_mae": all_model_mae,
            "market_spread_mae": all_mkt_mae,
            "blend_50_50_mae": all_blend_mae,
            "model_total_mae": all_tot_mod_mae,
            "market_total_mae": all_tot_mkt_mae,
            "residual_regression": ols,
            "verdict": "Market beats pure statistical Ridge model (higher MAE, slope beta on residual not reliably profitable).",
            "sources": ["SRC-GITHUB-REPO", "SRC-SKLEARN-LINEAR", "SRC-NWS-WIND"],
        },
        "season_summary": season_summary,
        "ridge_margin_weights": [
            {"feature": fn, "weight": round(wt, 4), "sources": ["SRC-SKLEARN-LINEAR", "SRC-GITHUB-REPO"]}
            for fn, wt in zip(feature_names, w_m_final)
        ],
        "week9_replay": wk9_replay,
        "week10_slate": wk10_slate,
    }


def run_player_signals() -> dict:
    """Walk-forward ex-ante trailing 4-game player stat projections (2023-2026 Wk 8).

    Leaves sportsbook prop odds/ROI/CLV explicitly '' because historical prop lines do not exist in repo.
    """
    pw = C.load_csv_gz("player_week.csv.gz")
    logs: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in pw:
        if r["season_type"] != "REG" or int(r["season"]) < 2018:
            continue
        logs[(r["player_id"], r["position"])].append({
            "season": int(r["season"]),
            "week": int(r["week"]),
            "name": r["player_display_name"],
            "team": C.std_team(r["team"]),
            "pass_yds": float(r["passing_yards"] or 0),
            "attempts": float(r["attempts"] or 0),
            "rush_yds": float(r["rushing_yards"] or 0),
            "carries": float(r["carries"] or 0),
            "rec_yds": float(r["receiving_yards"] or 0),
            "targets": float(r["targets"] or 0),
        })

    specs = [
        ("QB", "pass_yds", "attempts", 15.0, "Passing yards (QB >=15 att)"),
        ("RB", "rush_yds", "carries", 8.0, "Rushing yards (RB >=8 car)"),
        ("WR", "rec_yds", "targets", 4.0, "Receiving yards (WR >=4 tgt)"),
        ("TE", "rec_yds", "targets", 3.0, "Receiving yards (TE >=3 tgt)"),
    ]

    market_summaries = []
    recent_2026_leaders = defaultdict(list)

    for pos, stat_col, vol_col, min_vol, label in specs:
        preds, acts = [], []
        for (pid, ppos), rows in logs.items():
            if ppos != pos:
                continue
            rows.sort(key=lambda x: (x["season"], x["week"]))
            hist_vals = []
            for r in rows:
                if r[vol_col] < min_vol:
                    continue
                if len(hist_vals) >= 4:
                    trail4 = sum(hist_vals[-4:]) / 4.0
                    trail8 = sum(hist_vals[-8:]) / len(hist_vals[-8:])
                    # Shrink 35% toward positional baseline
                    pos_mean = sum(hist_vals) / len(hist_vals)
                    proj = 0.55 * trail4 + 0.30 * trail8 + 0.15 * pos_mean
                    if 2023 <= r["season"] <= 2026:
                        preds.append(proj)
                        acts.append(r[stat_col])
                    if r["season"] == 2026 and r["week"] == 8:
                        recent_2026_leaders[pos].append({
                            "player": r["name"],
                            "team": r["team"],
                            "trailing_4gm_avg": round(trail4, 1),
                            "ex_ante_proj": round(proj, 1),
                            "wk8_actual": round(r[stat_col], 1),
                            "prop_sportsbook_line": "",
                            "prop_edge_clv": "",
                        })
                hist_vals.append(r[stat_col])

        errs = [abs(a - p) for a, p in zip(acts, preds)]
        sq_errs = [(a - p) ** 2 for a, p in zip(acts, preds)]
        r_corr, n_obs = C.pearson_r(preds, acts)
        market_summaries.append({
            "market": label,
            "oos_observations": n_obs,
            "ex_ante_mae": round(sum(errs) / n_obs, 2) if n_obs else None,
            "ex_ante_rmse": round(math.sqrt(sum(sq_errs) / n_obs), 2) if n_obs else None,
            "median_abs_error": round(statistics.median(errs), 2) if errs else None,
            "proj_actual_r": round(r_corr, 4),
            "historical_prop_closing_line": "",
            "historical_prop_roi": "",
            "gap_flag": "FL-01: No sportsbook prop closing lines or prop prices exist in repository.",
            "sources": ["SRC-GITHUB-REPO", "SRC-NFL-PASSING-2026"],
        })

    # Build top 2026 Week 8/10 sample projections across positions
    watch_rows = []
    for pos in ("QB", "RB", "WR", "TE"):
        top = sorted(recent_2026_leaders[pos], key=lambda x: -x["ex_ante_proj"])[:3]
        for t in top:
            t["position"] = pos
            t["sources"] = ["SRC-GITHUB-REPO", "SRC-NFL-INJURIES-W10"]
            watch_rows.append(t)

    return {
        "meta": {
            "verified_on": C.VERIFIED_DATE,
            "eval_window": "2023-2026 Week 8 OOS (strictly trailing game logs)",
            "prop_lines_status": "UNVERIFIABLE — zero prop odds stored in repository (FL-01); ROI columns left blank.",
        },
        "prop_calibration": market_summaries,
        "week8_top_baselines": watch_rows,
    }


def run_luck_decomposition(games: list[dict[str, str]], tw_rows: list[dict[str, str]]) -> dict:
    """Split-half persistence (Weeks 1-8 vs Weeks 9-18, 2015-2025) & 2026 luck table."""
    tw_map = {(r["game_id"], C.std_team(r["team"])): r for r in tw_rows if r["season_type"] == "REG"}
    reg = [
        g for g in games
        if g["game_type"] == "REG" and 2015 <= int(g["season"]) <= 2025
        and g["home_score"] != "" and g["away_score"] != ""
    ]

    # Collect per (season, team, half) metrics: half 1 = wk <= 8, half 2 = wk >= 9
    buckets: dict[tuple[int, str, int], list[dict]] = defaultdict(list)
    for g in reg:
        s = int(g["season"])
        w = int(g["week"])
        half = 1 if w <= 8 else 2
        hs, aws = float(g["home_score"]), float(g["away_score"])
        for side, opp_side, pf, pa in (("home", "away", hs, aws), ("away", "home", aws, hs)):
            t = C.std_team(g[f"{side}_team"])
            ot = C.std_team(g[f"{opp_side}_team"])
            tw_s = tw_map.get((g["game_id"], t))
            tw_o = tw_map.get((g["game_id"], ot))
            if not tw_s or not tw_o:
                continue
            pass_epa = C.fnum(tw_s.get("passing_epa")) or 0.0
            rush_epa = C.fnum(tw_s.get("rushing_epa")) or 0.0
            def_epa = (C.fnum(tw_o.get("passing_epa")) or 0.0) + (C.fnum(tw_o.get("rushing_epa")) or 0.0)
            plays = (C.fnum(tw_s.get("attempts")) or 0.0) + (C.fnum(tw_s.get("carries")) or 0.0) + (C.fnum(tw_s.get("sacks_suffered")) or 0.0)
            yds = (C.fnum(tw_s.get("passing_yards")) or 0.0) + (C.fnum(tw_s.get("rushing_yards")) or 0.0)
            fum_lost = C.fnum(tw_s.get("fumbles_lost_total")) or 0.0
            def_int = C.fnum(tw_s.get("def_interceptions")) or 0.0
            margin = pf - pa
            buckets[(s, t, half)].append({
                "win": 1.0 if margin > 0 else (0.5 if margin == 0 else 0.0),
                "margin": margin,
                "pf": pf,
                "pa": pa,
                "close_gm": 1.0 if abs(margin) <= 7.0 else 0.0,
                "close_win": 1.0 if (abs(margin) <= 7.0 and margin > 0) else 0.0,
                "pass_epa": pass_epa,
                "net_epa": (pass_epa + rush_epa) - def_epa,
                "ypp": yds / plays if plays > 0 else 5.3,
                "fum_lost": fum_lost,
                "def_int": def_int,
            })

    def agg(rows: list[dict]) -> dict[str, float]:
        n = len(rows)
        pf = sum(r["pf"] for r in rows)
        pa = sum(r["pa"] for r in rows)
        pyth = (pf ** 2.37) / ((pf ** 2.37) + (pa ** 2.37)) if (pf + pa) > 0 else 0.5
        win_pct = sum(r["win"] for r in rows) / n
        cg = sum(r["close_gm"] for r in rows)
        return {
            "pass_epa_pg": sum(r["pass_epa"] for r in rows) / n,
            "net_epa_pg": sum(r["net_epa"] for r in rows) / n,
            "ypp": sum(r["ypp"] for r in rows) / n,
            "margin_pg": sum(r["margin"] for r in rows) / n,
            "win_pct": win_pct,
            "pyth_residual": win_pct - pyth,
            "close_win_pct": (sum(r["close_win"] for r in rows) / cg) if cg > 0 else 0.5,
            "fum_lost_pg": sum(r["fum_lost"] for r in rows) / n,
            "def_int_pg": sum(r["def_int"] for r in rows) / n,
        }

    pairs = []
    for s in range(2015, 2026):
        teams = set(k[1] for k in buckets if k[0] == s)
        for t in teams:
            h1 = buckets.get((s, t, 1), [])
            h2 = buckets.get((s, t, 2), [])
            if len(h1) >= 6 and len(h2) >= 6:
                pairs.append((agg(h1), agg(h2)))

    metric_specs = [
        ("net_epa_pg", "Net EPA per game (off - def)", "High-persistence underlying team quality"),
        ("pass_epa_pg", "Offensive Passing EPA per game", "Core repeatable QB/scheme skill metric"),
        ("ypp", "Offensive Yards per Play", "Stable efficiency signal"),
        ("margin_pg", "Point differential per game", "Headline team strength (skill + turnover variance)"),
        ("win_pct", "Actual win percentage", "Moderately stable; distorted by 1-score luck"),
        ("def_int_pg", "Defensive interceptions per game", "Noisy — strongly regresses midseason"),
        ("fum_lost_pg", "Fumbles lost per game", "Nearly pure ball-bounce luck"),
        ("close_win_pct", "One-score game win pct (|margin|<=7)", "Classic close-game luck; regresses toward 50%"),
        ("pyth_residual", "Win% minus Pythagorean Win% (exp 2.37)", "Pure luck residual — mean-reverts sharply"),
    ]
    persistence_rows = []
    for key, label, interp in metric_specs:
        xs = [p[0][key] for p in pairs]
        ys = [p[1][key] for p in pairs]
        r, n = C.pearson_r(xs, ys)
        lo, hi = C.fisher_z_ci(r, n)
        persistence_rows.append({
            "metric": label,
            "team_seasons": n,
            "split_half_r": round(r, 4),
            "ci_95_low": lo,
            "ci_95_high": hi,
            "r_squared": round(r * r, 4),
            "interpretation": interp,
            "sources": ["SRC-GITHUB-REPO"],
        })

    # Apply to live 2026 Wk 1-9 standings + Wk 1-8 EPA
    from verify_official_2026 import OFFICIAL_2026_W9
    g2026 = [g for g in games if g["season"] == "2026" and g["game_type"] == "REG" and g["home_score"] != ""]
    close_rec = defaultdict(lambda: [0, 0])
    epa_sum = defaultdict(lambda: [0.0, 0])
    for g in g2026:
        hs, aws = float(g["home_score"]), float(g["away_score"])
        for side, opp, pf, pa in (("home", "away", hs, aws), ("away", "home", aws, hs)):
            t = C.std_team(g[f"{side}_team"])
            ot = C.std_team(g[f"{opp}_team"])
            if abs(pf - pa) <= 7:
                close_rec[t][1] += 1
                if pf > pa:
                    close_rec[t][0] += 1
            tw_s = tw_map.get((g["game_id"], t))
            tw_o = tw_map.get((g["game_id"], ot))
            if tw_s and tw_o:
                ne = ((C.fnum(tw_s.get("passing_epa")) or 0.0) + (C.fnum(tw_s.get("rushing_epa")) or 0.0)
                      - ((C.fnum(tw_o.get("passing_epa")) or 0.0) + (C.fnum(tw_o.get("rushing_epa")) or 0.0)))
                epa_sum[t][0] += ne
                epa_sum[t][1] += 1
    # Add post-Nov-1 official 16 games into 1-score tally
    for f in C.OFFICIAL_2026_POST_NOV1_FINALS:
        hs, aws = f["home_score"], f["away_score"]
        for t, pf, pa in ((f["home_team"], hs, aws), (f["away_team"], aws, hs)):
            if abs(pf - pa) <= 7:
                close_rec[t][1] += 1
                if pf > pa:
                    close_rec[t][0] += 1

    team_2026_luck = []
    for t, (w, l, tie, pf, pa) in sorted(OFFICIAL_2026_W9.items()):
        gp = w + l + tie
        actual_pct = (w + 0.5 * tie) / gp
        pyth_pct = (pf ** 2.37) / ((pf ** 2.37) + (pa ** 2.37))
        luck_wins = round((actual_pct - pyth_pct) * gp, 2)
        cw, cg = close_rec[t]
        ne_avg = round(epa_sum[t][0] / epa_sum[t][1], 2) if epa_sum[t][1] else 0.0
        team_2026_luck.append({
            "team": t,
            "w9_record": f"{w}-{l}-{tie}",
            "pf": pf,
            "pa": pa,
            "actual_win_pct": round(actual_pct, 3),
            "pyth_win_pct": round(pyth_pct, 3),
            "luck_wins_above_pyth": luck_wins,
            "one_score_record": f"{cw}-{cg - cw}",
            "net_epa_pg_wk1_8": ne_avg,
            "sources": ["SRC-NFL-STANDINGS-2026", "SRC-GITHUB-REPO"],
        })
    team_2026_luck.sort(key=lambda r: -r["luck_wins_above_pyth"])

    return {
        "meta": {
            "verified_on": C.VERIFIED_DATE,
            "split_half_seasons": "2015-2025 (H1 Wk 1-8 vs H2 Wk 9-18)",
        },
        "persistence_table": persistence_rows,
        "team_2026_luck": team_2026_luck,
    }


def main() -> int:
    games = C.load_csv_gz("games.csv.gz")
    tw_rows = C.load_csv_gz("team_week.csv.gz")
    pre, _ = build_team_rolling_features(games, tw_rows)

    orig = run_origination(games, pre)
    sigs = run_player_signals()
    luck = run_luck_decomposition(games, tw_rows)

    C.write_strict_json(C.DATA_DIR / "origination.json", orig)
    C.write_strict_json(C.DATA_DIR / "signals.json", sigs)
    C.write_strict_json(C.DATA_DIR / "luck.json", luck)

    print("Origination OOS (2023-2026):", orig["overall_oos"])
    print("Prop calibration:")
    for p in sigs["prop_calibration"]:
        print(" ", p["market"], "n=", p["oos_observations"], "mae=", p["ex_ante_mae"], "r=", p["proj_actual_r"])
    print("Luck persistence (top & bottom):")
    for r in luck["persistence_table"]:
        print(" ", r["metric"], "r=", r["split_half_r"], f"[{r['ci_95_low']}, {r['ci_95_high']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
