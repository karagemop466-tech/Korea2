#!/usr/bin/env python3
"""Originate player-prop lines from usage history and measure how accurate they are.

Important scope limit: the official feed carries no historical player-prop prices, so this module
can measure forecast accuracy and calibration, but it CANNOT measure a market ROI. Any prop ROI on
this site would be an invention, so none is published - see the Flagged for Review page.

Outputs data/derived/props.json
"""
from __future__ import annotations

import json
import math
import os
import traceback

import numpy as np
import pandas as pd
from scipy import stats as sps

from lib import data as D

DERIVED = os.path.join("data", "derived")
TEST_START = 2023

SPECS = [
    {"stat": "receiving_yards", "positions": ["WR", "TE"], "usage": "targets", "min_usage": 30, "label": "Receiving yards"},
    {"stat": "receptions", "positions": ["WR", "TE"], "usage": "targets", "min_usage": 30, "label": "Receptions"},
    {"stat": "rushing_yards", "positions": ["RB"], "usage": "carries", "min_usage": 60, "label": "Rushing yards"},
    {"stat": "passing_yards", "positions": ["QB"], "usage": "attempts", "min_usage": 150, "label": "Passing yards"},
]


def predict_frame(pg: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """Prior-games-only forecast: exponentially weighted mean of the player's earlier games."""
    d = pg[pg["position"].isin(spec["positions"])].copy()
    d = d.sort_values(["player_id", "season", "week"])
    key = ["player_id", "season"]
    d["prior_n"] = d.groupby(key, group_keys=False)[spec["stat"]].transform(lambda s: s.shift(1).expanding().count())
    d["forecast"] = d.groupby(key, group_keys=False)[spec["stat"]].transform(
        lambda s: s.shift(1).ewm(halflife=4, min_periods=3).mean())
    d["baseline_season_mean"] = d.groupby(key, group_keys=False)[spec["stat"]].transform(
        lambda s: s.shift(1).expanding(min_periods=3).mean())
    d["baseline_last3"] = d.groupby(key, group_keys=False)[spec["stat"]].transform(
        lambda s: s.shift(1).rolling(3, min_periods=3).mean())
    return d.dropna(subset=["forecast", "baseline_season_mean", "baseline_last3"])


def evaluate(d: pd.DataFrame, spec: dict) -> dict:
    ev = d[d["season"] >= TEST_START].copy()
    if len(ev) < 200:
        return {"status": "insufficient_data", "n": int(len(ev))}
    y = ev[spec["stat"]].to_numpy(float)
    f = ev["forecast"].to_numpy(float)
    b = ev["baseline_season_mean"].to_numpy(float)
    b3 = ev["baseline_last3"].to_numpy(float)
    resid = y - f
    sd = float(np.std(resid, ddof=1))
    line = np.round(f * 2) / 2  # originate the line at the nearest half-unit
    over = (y > line).astype(int)
    push = (y == line).astype(int)
    decided = over[push == 0]
    return {
        "stat": spec["stat"], "label": spec["label"], "n": int(len(ev)),
        "mae_forecast": round(float(np.abs(resid).mean()), 3),
        "mae_baseline_season_mean": round(float(np.abs(y - b).mean()), 3),
        "mae_baseline_last3": round(float(np.abs(y - b3).mean()), 3),
        "mae_improvement_vs_season_mean_pct": round(100 * (1 - np.abs(resid).mean() / np.abs(y - b).mean()), 2),
        "corr_forecast_actual": round(float(np.corrcoef(f, y)[0, 1]), 4),
        "resid_sd": round(sd, 3),
        "originated_line_over_rate": round(float(decided.mean()), 4),
        "n_decided": int(len(decided)),
        "pushes_at_originated_line": int(push.sum()),
        "calibration_note": ("The line is placed at the forecast, so an unbiased model should show an "
                             "over rate of 50%. The published rate is the observed one."),
        "calibration_by_quartile": _calib_quartiles(f, y, sd),
        "test_seasons": [int(ev["season"].min()), int(ev["season"].max())],
        "status": "measured",
    }


def _calib_quartiles(f: np.ndarray, y: np.ndarray, sd: float) -> list[dict]:
    rows = []
    for threshold_pct in (-0.2, 0.0, 0.2):
        thr = f * (1 + threshold_pct) if threshold_pct != 0 else f
        p_model = 1 - sps.norm.cdf(thr, loc=f, scale=sd)
        actual = (y > thr).astype(float)
        rows.append({"threshold": f"forecast{'+' if threshold_pct >= 0 else ''}{int(threshold_pct*100)}%",
                     "predicted_over_rate": round(float(p_model.mean()), 4),
                     "actual_over_rate": round(float(actual.mean()), 4),
                     "n": int(len(y))})
    return rows


def originate(pg: pd.DataFrame, spec: dict) -> list[dict]:
    """Lines for the next unplayed week for the most-used qualified players."""
    latest = int(pg["season"].max())
    d = pg[pg["position"].isin(spec["positions"])].copy()
    season = d[d["season"] == latest].copy()
    usage = season.groupby(["player_id", "player_display_name", "team"], as_index=False).agg(
        usage=("targets" if spec["usage"] == "targets" else spec["usage"], "sum"))
    qualified = usage[usage["usage"] >= spec["min_usage"] / 3]
    rows = []
    last_week = int(season["week"].max())
    for _, player in qualified.iterrows():
        hist = season[(season["player_id"] == player["player_id"])].sort_values("week")
        hist = hist[hist["week"] <= last_week]
        if len(hist) < 3:
            continue
        recent = hist[spec["stat"]].to_numpy(float)
        w = 0.5 ** (np.arange(len(recent))[::-1] / 4.0)
        fc = float(np.average(recent, weights=w))
        resid_hist = hist[spec["stat"]].to_numpy(float) - hist[spec["stat"]].shift(1).fillna(hist[spec["stat"]].mean()).to_numpy(float)
        sd = float(np.std(resid_hist, ddof=1)) if len(resid_hist) > 2 else float(hist[spec["stat"]].std(ddof=1))
        line = round(fc * 2) / 2
        p_over = float(1 - sps.norm.cdf(line, loc=fc, scale=max(sd, 1e-6)))
        rows.append({"player": player["player_display_name"], "team": player["team"],
                     "games_used": int(len(hist)), "weighted_forecast": round(fc, 1),
                     "originated_line": line, "p_over": round(p_over, 3),
                     "resid_sd": round(sd, 2)})
    rows.sort(key=lambda r: -r["weighted_forecast"])
    return rows[:20]


def main() -> None:
    games, _ = D.load_games()
    player, _ = D.load_player_week()
    pg = D.player_games(player, games)
    out: dict = {
        "scope": {"seasons": [int(pg["season"].min()), int(pg["season"].max())],
                  "test_seasons": [TEST_START, int(pg["season"].max())],
                  "player_games": int(len(pg))},
        "limitation": ("No historical player-prop market prices exist in the official feed, so no "
                       "prop ROI or closing-line comparison is published. Accuracy and calibration "
                       "are measured; profitability is unverified and flagged."),
        "evaluations": [], "originated": {},
    }
    for spec in SPECS:
        d = predict_frame(pg, spec)
        ev = evaluate(d, spec)
        out["evaluations"].append(ev)
        out["originated"][spec["stat"]] = {
            "label": spec["label"],
            "week": int(pg["week"].max()) + 1,
            "players": originate(pg, spec),
        }
        print(spec["stat"], ev.get("n"), ev.get("mae_forecast"), ev.get("mae_baseline_season_mean"),
              ev.get("originated_line_over_rate"))

    with open(os.path.join(DERIVED, "props.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=str)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        os.makedirs(DERIVED, exist_ok=True)
        with open(os.path.join(DERIVED, "props.json"), "w") as fh:
            json.dump({"status": "failed", "error": traceback.format_exc()}, fh, indent=2)
        traceback.print_exc()
        raise SystemExit(1)
