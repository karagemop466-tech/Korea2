#!/usr/bin/env python3
"""Run every candidate strategy through the same ten validation gates and rank what survives.

All bets are settled at the closing line that the feed reports, so a strategy must beat the
sharpest available price - there is no soft line to hide behind.

Price policy (revised 2026-11-14): a bet with no stored price is EXCLUDED and counted
(`n_excluded_missing_price`, disclosed per strategy and in meta) - it is never settled at an
assumed -110. An unpriced bet has no ROI evidence, and imputing a price would manufacture a
staking result.

Leaderboard policy (revised 2026-11-14): entries are ranked by SIGNAL ONLY (gates passed, then
Benjamini-Hochberg-adjusted p, then sample size). Staking metrics (ROI and its CI) are reported
under `staking` but never affect rank ordering, so a lucky staking run cannot mask a bad signal.

Outputs data/derived/strategies.json and data/derived/leaderboard.json
"""
from __future__ import annotations

import json
import math
import os
import traceback

import numpy as np
import pandas as pd

from lib import backtest as B
from lib import data as D
from lib import stats as S

DERIVED = os.path.join("data", "derived")

# Bets excluded because the feed stores no price for them (per strategy). Disclosed in output;
# never settled at an assumed price.
MISSING_PRICE_EXCLUSIONS: dict[str, int] = {}


def load_inputs() -> tuple[pd.DataFrame, dict]:
    games, checks = D.load_games()
    pred_path = os.path.join(DERIVED, "predictions.csv")
    preds = pd.read_csv(pred_path)
    g = games[(games["game_type"] == "REG")].dropna(subset=["home_score", "away_score"])
    df = g.merge(preds[["game_id", "model_margin", "model_total"]], on="game_id", how="inner")
    return df, {"qa": checks, "n_games": int(len(df))}


def spread_bets(df: pd.DataFrame, pick, strategy: str, note: str) -> list[dict]:
    """`pick` maps a game row -> 'home' | 'away' | None. Settlement is push-aware.

    A bet whose stored price is missing is excluded and counted (MISSING_PRICE_EXCLUSIONS), never
    settled at an assumed price.
    """
    recs = []
    for r in df.itertuples():
        side = pick(r)
        if side is None:
            continue
        # Proven convention: spread_line is the home team's expected margin, so the home team's
        # handicap is -spread_line and the away team's is +spread_line.
        if side == "home":
            odds = getattr(r, "home_spread_odds", np.nan)
            team, margin, handicap = r.home_team, r.result, -r.spread_line
        else:
            odds = getattr(r, "away_spread_odds", np.nan)
            team, margin, handicap = r.away_team, -r.result, r.spread_line
        if pd.isna(odds):
            MISSING_PRICE_EXCLUSIONS[strategy] = MISSING_PRICE_EXCLUSIONS.get(strategy, 0) + 1
            continue
        outcome, profit, staked = B.settle_spread(margin, handicap, float(odds))
        recs.append({"strategy": strategy, "game_id": r.game_id, "season": int(r.season),
                     "week": int(r.week), "team": team, "side": side, "line": r.spread_line,
                     "odds": float(odds), "outcome": outcome, "profit": profit, "staked": staked,
                     "note": note})
    return recs


def total_bets(df: pd.DataFrame, pick, strategy: str, note: str) -> list[dict]:
    """Total bets. Missing-price bets are excluded and counted, never settled at an assumed price."""
    recs = []
    for r in df.itertuples():
        side = pick(r)
        if side is None:
            continue
        odds = getattr(r, "over_odds" if side == "over" else "under_odds", np.nan)
        if pd.isna(odds):
            MISSING_PRICE_EXCLUSIONS[strategy] = MISSING_PRICE_EXCLUSIONS.get(strategy, 0) + 1
            continue
        outcome, profit, staked = B.settle_total(r.total, r.total_line, side, float(odds))
        recs.append({"strategy": strategy, "game_id": r.game_id, "season": int(r.season),
                     "week": int(r.week), "team": f"{r.away_team}@{r.home_team}",
                     "side": side, "line": r.total_line, "odds": float(odds),
                     "outcome": outcome, "profit": profit, "staked": staked, "note": note})
    return recs


def build_strategies(df: pd.DataFrame) -> dict[str, dict]:
    df = df.copy()
    df["edge"] = df["model_margin"] - df["spread_line"]
    df["edge_total"] = df["model_total"] - df["total_line"]
    df["rest_diff"] = df["home_rest"] - df["away_rest"]
    df["is_outdoor"] = ~df["roof"].astype(str).str.lower().isin(["dome", "closed", "open", "retractable"])
    strat: dict[str, dict] = {}

    strat["S1_model_edge_2"] = {
        "name": "Model spread edge >= 2.0 pts",
        "family": "single bet",
        "hypothesis": "When the transparent ratings model disagrees with the closing line by 2+ points, the model side has value.",
        "bets": spread_bets(df, lambda r: "home" if r.edge >= 2 else ("away" if r.edge <= -2 else None),
                            "S1_model_edge_2", "Model vs closing spread"),
    }
    strat["S2_model_edge_3"] = {
        "name": "Model spread edge >= 3.0 pts",
        "family": "single bet",
        "hypothesis": "A larger disagreement is more likely to survive the market's information.",
        "bets": spread_bets(df, lambda r: "home" if r.edge >= 3 else ("away" if r.edge <= -3 else None),
                            "S2_model_edge_3", "Model vs closing spread"),
    }
    strat["S3_model_total_edge"] = {
        "name": "Model total edge >= 3.0 pts",
        "family": "single bet (total)",
        "hypothesis": "The ratings model's pace estimate beats the closing total when they differ by 3+ points.",
        "bets": total_bets(df, lambda r: "over" if r.edge_total >= 3 else ("under" if r.edge_total <= -3 else None),
                           "S3_model_total_edge", "Model vs closing total"),
    }
    strat["S4_rest_advantage"] = {
        "name": "Rest advantage >= 3 days",
        "family": "single bet (situational)",
        "hypothesis": "A team with a 3+ day rest edge over its opponent is underpriced.",
        "bets": spread_bets(df, lambda r: "home" if r.rest_diff >= 3 else ("away" if r.rest_diff <= -3 else None),
                            "S4_rest_advantage", "Schedule-spot signal"),
    }
    # NOTE on a rejected design: "fade the team on short rest" produced 0 qualifying bets in
    # 2023-2026, because Thursday games put BOTH teams on short rest. It is kept here as a record of
    # a hypothesis that could not be expressed as a bet, rather than silently deleted.
    strat["S5_bye_week_team"] = {
        "name": "Team coming off a bye (13+ days rest) vs a normal-rest opponent",
        "family": "single bet (situational)",
        "hypothesis": "Extra preparation time after a bye is worth more than the closing line implies.",
        "bets": spread_bets(
            df,
            lambda r: ("home" if (r.home_rest >= 13 and r.away_rest < 13)
                       else ("away" if (r.away_rest >= 13 and r.home_rest < 13) else None)),
            "S5_bye_week_team", "Bye-week signal"),
        "rejected_variant": ("An earlier 'short-week fade' version (rest <= 5 vs rest >= 7) selected "
                             "zero games because short-rest games involve two short-rest teams."),
    }
    strat["S6_divisional_home_dog"] = {
        "name": "Divisional home underdog",
        "family": "single bet (situational)",
        "hypothesis": "Familiarity compresses divisional margins, so home dogs in-division are undervalued.",
        "bets": spread_bets(df, lambda r: "home" if (r.div_game == 1 and r.spread_line < 0) else None,
                            "S6_divisional_home_dog", "Division + underdog filter"),
    }
    strat["S7_wind_under"] = {
        "name": "Under when wind >= 15 mph outdoors",
        "family": "single bet (total)",
        "hypothesis": "Wind suppresses scoring more than the closing total implies.",
        "bets": total_bets(df, lambda r: "under" if (r.is_outdoor and pd.notna(r.wind) and r.wind >= 15) else None,
                           "S7_wind_under", "Weather filter"),
    }
    strat["C1_all_home_control"] = {
        "name": "Control - back every home team",
        "family": "control",
        "hypothesis": "No skill; measures the cost of the vig at the closing line.",
        "bets": spread_bets(df, lambda r: "home", "C1_all_home_control", "Control"),
    }
    strat["C2_all_under_control"] = {
        "name": "Control - under every game",
        "family": "control",
        "hypothesis": "No skill; measures the cost of the vig on totals.",
        "bets": total_bets(df, lambda r: "under", "C2_all_under_control", "Control"),
    }
    return strat


def main() -> None:
    df, meta = load_inputs()
    strat = build_strategies(df)
    n_strategies = len([k for k in strat if not k.startswith("C")])

    # First pass: summaries, so the multiple-testing correction sees every test at once.
    summaries = {k: B.summarise(v["bets"], n_trials=n_strategies) for k, v in strat.items()}
    pvals = [summaries[k].get("binomial_p_vs_50") for k in strat]
    bh = S.benjamini_hochberg(pvals, q=0.10)

    out = {
        "meta": {**meta, "n_strategies_tested": n_strategies,
                 "test_window": f"{int(df['season'].min())}-{int(df['season'].max())}",
                 "benchmark": "closing line reported in the nflverse schedules feed",
                 "missing_price_policy": ("bets without a stored closing price are EXCLUDED and "
                                          "counted (n_excluded_missing_price per strategy); no "
                                          "-110 imputation since revision 2026-11-14"),
                 "n_excluded_missing_price_total": 0,  # filled after strategies are built
                 "multiple_testing": {"method": "Benjamini-Hochberg", "q": 0.10,
                                      "n_tests": bh["n_tests"]}},
        "gates_definition": B.GATES,
        "demotion_gate": B.DEMOTION_GATE,
        "strategies": {},
    }
    ranked = []
    for i, (k, v) in enumerate(strat.items()):
        ctx = {
            "point_in_time": True,
            "out_of_sample": True,
            "closing_line_benchmark": True,
            "executable_verified": False,   # no verified price/limit access in this project
            "reproducible": True,
            "live": False,                  # no strategy is promoted; D1 is armed but dormant
            "min_n": S.min_sample_size(0.524, 0.5),  # bets needed to detect a 52.4% edge vs 50%
            "bh_adjusted_p": bh["adjusted"][i],
        }
        gates = B.evaluate_gates(summaries[k], ctx)
        out["strategies"][k] = {
            "name": v["name"], "family": v["family"], "hypothesis": v["hypothesis"],
            "summary": summaries[k], "gates": gates,
            "min_n_required": ctx["min_n"], "bh_adjusted_p": round(bh["adjusted"][i], 6),
            "n_excluded_missing_price": MISSING_PRICE_EXCLUSIONS.get(k, 0),
            "demotion_gate": B.evaluate_demotion(v["bets"], ctx["live"]),
        }
        out["meta"]["n_excluded_missing_price_total"] += MISSING_PRICE_EXCLUSIONS.get(k, 0)
        ranked.append((k, gates["n_passed"], bh["adjusted"][i],
                       summaries[k].get("n", 0)))

    # ---- leaderboard: SIGNAL-ONLY ordering; staking reported separately
    # Sort key: gates passed (desc), then Benjamini-Hochberg-adjusted p (asc - lower means stronger
    # skill evidence after multiple-testing control), then sample size (desc). ROI is deliberately
    # absent from the key: a lucky staking run cannot reorder the board.
    ranked.sort(key=lambda t: (-t[1], t[2], -t[3]))
    board = []
    for rank, (k, npass, bp, n) in enumerate(ranked, start=1):
        s = out["strategies"][k]
        approved = s["gates"]["verdict"] == "APPROVED"
        board.append({
            "rank": rank, "id": k, "name": s["name"], "family": s["family"],
            "verdict": s["gates"]["verdict"], "gates_passed": f"{npass}/10",
            # ---- signal group: skill evidence, ordering basis
            "signal": {
                "gates_passed": f"{npass}/10",
                "win_rate": s["summary"].get("win_rate"),
                "win_rate_ci": s["summary"].get("win_rate_ci"),
                "p_value": s["summary"].get("binomial_p_vs_50"),
                "bh_adjusted_p": s["bh_adjusted_p"],
                "deflated_sharpe_p": s["summary"].get("deflated_sharpe_p"),
                "n_bets": s["summary"].get("n"),
                "decided": s["summary"].get("decided"),
                "clv": None,  # no opening prices in the committed feed; see demotion_gate note
            },
            # ---- staking group: money outcome, reported but NEVER ordering
            "staking": {
                "roi": s["summary"].get("roi"),
                "roi_ci": s["summary"].get("roi_ci"),
                "profit_units": s["summary"].get("profit_units"),
                "units_staked": s["summary"].get("units_staked"),
            },
            "demotion_gate": s["demotion_gate"],
            "reward": "eligible" if approved else "none - gate failure",
            "failed_gates": s["gates"]["failed"],
        })
    out["leaderboard"] = {
        "ranking_rule": ("Rank by SIGNAL ONLY: gates passed, then Benjamini-Hochberg-adjusted p "
                         "(lower = stronger skill evidence), then sample size. Staking metrics "
                         "(ROI and its CI) are reported under `staking` but never affect rank "
                         "ordering, so a lucky staking run cannot mask a bad signal. A strategy "
                         "can only earn a reward when all ten gates pass; a positive ROI alone "
                         "earns nothing."),
        "signal_vs_staking": ("signal = gates, adjusted significance, win rate, deflated Sharpe, "
                              "sample size (ordering basis); staking = ROI, ROI CI, units (money "
                              "outcome only). The split implements the requirement that a lucky "
                              "staking run cannot mask a bad signal."),
        "demotion_gate": B.DEMOTION_GATE,
        "reward_schedule": [
            {"tier": "Tier 1 - validated", "requirement": "10/10 gates", "reward": "Full strategy allocation and public listing as a live signal"},
            {"tier": "Tier 2 - provisional", "requirement": "8-9/10 gates with G9 (executable) verified", "reward": "Paper-trade only until the remaining gate closes"},
            {"tier": "Tier 3 - rejected", "requirement": "<= 7 gates", "reward": "No allocation; retained for research record"},
        ],
        "entries": board,
        "approved_count": sum(1 for b in board if b["verdict"] == "APPROVED"),
    }

    # ---- parlay / prop-combo scoring relative to single bets
    out["parlay_scoring"] = {
        "note": ("Parlays are scored on the same gate set with `n` counted as parlays settled. "
                 "Because leg correlations are measured (correlation.json), a parlay leg set can be "
                 "priced by copula rather than by multiplication; a parlay strategy that only wins "
                 "because legs are correlated is a pricing arbitrage, not a forecasting edge, and is "
                 "labelled as such."),
        "structural_ev": parlay_ev_table(),
    }

    with open(os.path.join(DERIVED, "strategies.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    with open(os.path.join(DERIVED, "leaderboard.json"), "w") as fh:
        json.dump(out["leaderboard"] | {"gates_definition": B.GATES}, fh, indent=2, default=str)
    for b in board:
        roi = b["staking"]["roi"]
        print(f"{b['rank']:2d} {b['id']:26s} {b['signal']['gates_passed']:>5s} "
              f"n={b['signal']['n_bets'] or 0:5d} BH-p={b['signal']['bh_adjusted_p']:.4f} "
              f"ROI={roi if roi is None else round(roi*100,1)}% {b['verdict']}")


def parlay_ev_table() -> list[dict]:
    """Expected value of standard fixed-odds parlays at true 50/50 legs, at -110-equivalent prices."""
    payouts = {2: 2.64, 3: 6.0, 4: 12.28, 5: 24.35, 6: 47.37}  # typical US fixed-odds ladders
    rows = []
    for k, dec in payouts.items():
        fair = 2 ** k
        p = 0.5 ** k
        ev = p * (dec - 1) - (1 - p)
        rows.append({"legs": k, "listed_decimal": dec, "fair_decimal_at_50pct_legs": fair,
                     "implied_edge_pct": round(100 * (dec / fair - 1), 1),
                     "ev_per_unit": round(ev, 4),
                     "note": "EV assumes independent 50/50 legs; correlation moves the true joint probability, not this payout."})
    return rows


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        os.makedirs(DERIVED, exist_ok=True)
        with open(os.path.join(DERIVED, "strategies.json"), "w") as fh:
            json.dump({"status": "failed", "error": traceback.format_exc()}, fh, indent=2)
        traceback.print_exc()
        raise SystemExit(1)
