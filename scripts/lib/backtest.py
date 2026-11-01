#!/usr/bin/env python3
"""Settlement and scoring for spread/total bets at the closing line.

Settlement convention (documented in docs/METHODOLOGY.md):
  * A spread bet wins if (team margin + team spread) > 0, loses if < 0, pushes if == 0.
  * A total bet wins if (game total - line) > 0 for over, < 0 for under, pushes if == 0.
  * Pushes refund the stake and are excluded from the win-rate denominator.
  * Profit is expressed per 1.00 unit staked at the price actually quoted for that game in the
    source feed (American odds -> decimal), with -110 used only when the feed has no price.
"""
from __future__ import annotations

import math

import numpy as np

from . import stats as S

DEFAULT_AMERICAN = -110


def american_to_profit(american: float, won: bool) -> float:
    if won:
        return american / 100 if american > 0 else 100 / abs(american)
    return -1.0


def settle_spread(team_margin: float, team_spread: float, odds: float) -> tuple[str, float, float]:
    """Returns (outcome, profit, units_staked). team_spread is that team's handicap (e.g. +3)."""
    edge = team_margin + team_spread
    if not math.isfinite(edge):
        return ("void", 0.0, 0.0)
    if abs(edge) < 1e-9:
        return ("push", 0.0, 0.0)
    return ("win" if edge > 0 else "loss", american_to_profit(odds, edge > 0), 1.0)


def settle_total(game_total: float, line: float, side: str, odds: float) -> tuple[str, float, float]:
    if not (math.isfinite(game_total) and math.isfinite(line)):
        return ("void", 0.0, 0.0)
    edge = (game_total - line) * (1 if side == "over" else -1)
    if abs(edge) < 1e-9:
        return ("push", 0.0, 0.0)
    return ("win" if edge > 0 else "loss", american_to_profit(odds, edge > 0), 1.0)


def summarise(records: list[dict], n_trials: int = 1, seed: int = 20261101) -> dict:
    """Full statistical summary for a list of bet records: outcome, profit, season, week."""
    if not records:
        return {"n": 0, "status": "no_bets"}
    won = sum(1 for r in records if r["outcome"] == "win")
    lost = sum(1 for r in records if r["outcome"] == "loss")
    push = sum(1 for r in records if r["outcome"] == "push")
    decided = won + lost
    staked = sum(r["staked"] for r in records)
    profit = sum(r["profit"] for r in records)
    profits = np.array([r["profit"] for r in records], dtype=float)

    roi = profit / staked if staked > 0 else float("nan")
    win_rate = won / decided if decided else float("nan")
    wlo, whi = S.wilson_ci(won, decided) if decided else (float("nan"), float("nan"))
    p = S.binomial_p(won, decided) if decided else float("nan")
    rlo, rhi = S.bootstrap_mean_ci(profits, seed=seed)
    sd = float(profits.std(ddof=1)) if profits.size > 1 else float("nan")
    sharpe = float(profits.mean() / sd) if sd and sd > 0 else float("nan")
    by_season: dict[str, dict] = {}
    for r in records:
        k = str(r.get("season", "?"))
        d = by_season.setdefault(k, {"n": 0, "profit": 0.0, "won": 0, "lost": 0})
        d["n"] += 1
        d["profit"] += r["profit"]
        d["won"] += r["outcome"] == "win"
        d["lost"] += r["outcome"] == "loss"
    for d in by_season.values():
        d["roi"] = round(d["profit"] / d["n"], 4) if d["n"] else None
        d["profit"] = round(d["profit"], 2)

    ds = S.deflated_sharpe(sharpe, profits.size, max(n_trials, 1)) if profits.size > 2 and math.isfinite(sharpe) else {
        "deflated_p": float("nan")}
    return {
        "n": len(records), "decided": decided, "won": won, "lost": lost, "pushes": push,
        "win_rate": None if not decided else round(win_rate, 4),
        "win_rate_ci": [None if not decided else round(wlo, 4), None if not decided else round(whi, 4)],
        "binomial_p_vs_50": None if not decided else round(p, 6),
        "units_staked": round(staked, 2), "profit_units": round(profit, 3),
        "roi": None if not math.isfinite(roi) else round(roi, 4),
        "roi_ci": [None if not math.isfinite(rlo) else round(rlo, 4),
                   None if not math.isfinite(rhi) else round(rhi, 4)],
        "profit_sd_per_bet": None if not math.isfinite(sd) else round(sd, 4),
        "sharpe_per_bet": None if not math.isfinite(sharpe) else round(sharpe, 4),
        "deflated_sharpe_p": None if not math.isfinite(ds.get("deflated_p", float("nan")))
        else round(ds["deflated_p"], 6),
        "by_season": by_season,
    }


# ------------------------------------------------------------------ validation gates
GATES = [
    {"id": "G1", "name": "Point-in-time integrity",
     "rule": "Inputs are strictly pre-kickoff; no result-derived feature; source hashes recorded."},
    {"id": "G2", "name": "Sample size",
     "rule": "n >= 1000 settled bets (or the power-analysis minimum, whichever is larger)."},
    {"id": "G3", "name": "Out-of-sample",
     "rule": "Evaluated on walk-forward seasons never used to fit the model."},
    {"id": "G4", "name": "Significance after multiple testing",
     "rule": "Two-sided p < 0.01 AND Benjamini-Hochberg q-value <= 0.10 across all tested strategies."},
    {"id": "G5", "name": "Positive lower bound",
     "rule": "Lower 95% bootstrap bound on ROI is above 0."},
    {"id": "G6", "name": "Stability",
     "rule": "Profitable in >= 60% of evaluated seasons and no single season > 50% of total profit."},
    {"id": "G7", "name": "Beats the closing line",
     "rule": "ROI is measured against the closing line, i.e. it must beat the sharpest public price."},
    {"id": "G8", "name": "Survives luck adjustment",
     "rule": "Deflated-Sharpe p < 0.05 given the number of variants tried."},
    {"id": "G9", "name": "Executable",
     "rule": "Price, limit and jurisdiction verified for the exact bet and time window."},
    {"id": "G10", "name": "Reproducible",
     "rule": "Committed code + data manifest + fixed seed reproduce the published numbers."},
]


def evaluate_gates(summary: dict, ctx: dict) -> dict:
    """Apply the ten gates. Any gate that cannot be evidenced is failed, never assumed."""
    s = summary
    n = s.get("n", 0)
    rlo = (s.get("roi_ci") or [None, None])[0]
    p = s.get("binomial_p_vs_50")
    bp = ctx.get("bh_adjusted_p")
    seasons = s.get("by_season", {})
    profits = [v["profit"] for v in seasons.values()]
    pos = sum(1 for v in profits if v > 0)
    total_profit = sum(profits)
    largest = max(profits) if profits else 0

    res = {}
    res["G1"] = bool(ctx.get("point_in_time", False))
    res["G2"] = n >= max(1000, ctx.get("min_n", 0))
    res["G3"] = bool(ctx.get("out_of_sample", False))
    res["G4"] = bool(p is not None and p < 0.01 and bp is not None and bp <= 0.10)
    res["G5"] = bool(rlo is not None and rlo > 0)
    res["G6"] = bool(len(profits) >= 3 and pos / len(profits) >= 0.6
                     and (total_profit <= 0 or largest / total_profit <= 0.5))
    res["G7"] = bool(ctx.get("closing_line_benchmark", False))
    res["G8"] = bool(s.get("deflated_sharpe_p") is not None and s["deflated_sharpe_p"] < 0.05)
    res["G9"] = bool(ctx.get("executable_verified", False))
    res["G10"] = bool(ctx.get("reproducible", False))
    passed = sum(res.values())
    return {
        "passed": res,
        "n_passed": passed,
        "n_gates": len(res),
        "verdict": "APPROVED" if passed == len(res) else "REJECTED",
        "failed": [g for g, ok in res.items() if not ok],
    }
