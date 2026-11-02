#!/usr/bin/env python3
"""Originate NFL game lines from a transparent points model, then test the model honestly.

Outputs data/derived/model.json
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
from lib import ratings as R
from lib import stats as S

DERIVED = os.path.join("data", "derived")
VAL_SEASONS = (2021, 2022)   # used only to choose hyper-parameters
TEST_START = 2023            # never used for fitting anything


def acc(pred, actual) -> dict:
    pred, actual = np.asarray(pred, float), np.asarray(actual, float)
    m = np.isfinite(pred) & np.isfinite(actual)
    pred, actual = pred[m], actual[m]
    if pred.size == 0:
        return {"n": 0}
    err = actual - pred
    return {"n": int(pred.size), "mae": round(float(np.abs(err).mean()), 3),
            "rmse": round(float(np.sqrt((err ** 2).mean())), 3),
            "bias": round(float(err.mean()), 3),
            "sd_resid": round(float(err.std(ddof=1)), 3),
            "corr": round(float(np.corrcoef(pred, actual)[0, 1]), 4)}


def ols_hc1(y: np.ndarray, X: np.ndarray) -> dict:
    """OLS with heteroskedasticity-consistent (HC1) standard errors."""
    n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    resid = y - X @ beta
    meat = X.T @ (X * (resid ** 2)[:, None])
    cov = XtX_inv @ meat @ XtX_inv * (n / (n - k))
    se = np.sqrt(np.diag(cov))
    t = beta / se
    p = 2 * (1 - sps.norm.cdf(np.abs(t)))
    return {"beta": [float(b) for b in beta], "se": [float(s) for s in se],
            "t": [float(v) for v in t], "p": [float(v) for v in p], "n": int(n)}


def main() -> None:
    out: dict = {}
    games, checks = D.load_games()

    # ------------------------------------------------------- hyper-parameters on validation only
    grid = [(90, 4.0), (90, 10.0), (180, 4.0), (180, 10.0), (120, 8.0)]
    best_hp, best_score, curve = (120, 8.0), 1e9, []
    for hl, lam in grid:
        f = R.fit_history(games, VAL_SEASONS[0], half_life_days=hl, lam=lam)
        f = f[f["season"].isin(VAL_SEASONS)].dropna(subset=["result"])
        if len(f) < 100:
            continue
        mae = float(np.abs(f["model_margin"] - f["result"]).mean())
        curve.append({"half_life_days": hl, "lambda": lam, "n": int(len(f)),
                      "validation_spread_mae": round(mae, 3)})
        if mae < best_score:
            best_hp, best_score = (hl, lam), mae
    out["hyperparameter_selection"] = {
        "grid": curve, "chosen_half_life_days": best_hp[0], "chosen_lambda": best_hp[1],
        "validation_mae": round(best_score, 3),
        "note": ("Chosen on 2021-2022 games only, then frozen for the 2023+ test window. "
                 "A validation-season win rate is NOT evidence of edge."),
    }

    # ------------------------------------------------------- walk-forward predictions
    val = R.fit_history(games, VAL_SEASONS[0], half_life_days=best_hp[0], lam=best_hp[1])
    val = val[val["season"].isin(VAL_SEASONS)]
    test = R.fit_history(games, TEST_START, half_life_days=best_hp[0], lam=best_hp[1])
    out["model_spec"] = {
        "form": "home = mu + off_home - def_away + hfa ; away = mu + off_away - def_home",
        "estimator": ("weighted least squares with ridge shrinkage; the penalty applied is the "
                      "ridge_lambda below, chosen on the 2021-2022 validation window"),
        "recency_half_life_days": best_hp[0],
        "ridge_lambda": best_hp[1],
        "home_field_shrinkage": "hfa shrunk toward the 10-season mean with 60 pseudo-observations",
        "train_window": "all regular-season games strictly before the predicted week's first kickoff",
        "validation_seasons": list(VAL_SEASONS),
        "test_seasons": [int(test["season"].min()), int(test["season"].max())],
    }

    # choose blend weight on validation seasons only
    grid = np.round(np.arange(0, 1.0001, 0.05), 2)
    best = (None, 1e9)
    for w in grid:
        m = val.dropna(subset=["market_margin", "result"])
        pred = w * m["model_margin"] + (1 - w) * m["market_margin"]
        mae = float(np.abs(pred - m["result"]).mean())
        if mae < best[1]:
            best = (float(w), mae)
    out["blend_selection"] = {
        "grid": [float(g) for g in grid],
        "chosen_weight_on_model": best[0],
        "validation_mae": round(best[1], 3),
        "note": "Weight chosen on 2021-2022 only; applied unchanged to 2023+.",
        "validation_curve": [
            {"w_model": float(w),
             "mae": round(float(np.abs(w * val.dropna(subset=["market_margin", "result"])["model_margin"]
                                       + (1 - w) * val.dropna(subset=["market_margin", "result"])["market_margin"]
                                       - val.dropna(subset=["market_margin", "result"])["result"]).mean()), 3)}
            for w in grid
        ],
    }

    t = test.dropna(subset=["result"]).copy()
    out["accuracy_spread"] = {
        "model": acc(t["model_margin"], t["result"]),
        "market": acc(t["market_margin"], t["result"]),
    }
    out["accuracy_total"] = {
        "model": acc(t["model_total"], t["total"]),
        "market": acc(t["market_total"], t["total"]),
    }
    w = best[0] if best[0] is not None else 0.0
    t["blend_margin"] = w * t["model_margin"] + (1 - w) * t["market_margin"]
    t["blend_total"] = w * t["model_total"] + (1 - w) * t["market_total"]
    out["accuracy_spread"]["blend"] = acc(t["blend_margin"], t["result"])
    out["accuracy_total"]["blend"] = acc(t["blend_total"], t["total"])
    out["accuracy_spread"]["blend"]["weight_on_model"] = w

    # does the model add information beyond the closing line?
    tt = t.dropna(subset=["market_margin", "model_margin", "result"])
    X = np.column_stack([np.ones(len(tt)), tt["market_margin"], tt["model_margin"]])
    reg = ols_hc1(tt["result"].to_numpy(float), X)
    out["incremental_information"] = {
        "spec": "result = a + b*closing_spread + c*model_margin + e  (HC1 errors)",
        "intercept": round(reg["beta"][0], 4), "b_market": round(reg["beta"][1], 4),
        "c_model": round(reg["beta"][2], 4), "se_c_model": round(reg["se"][2], 4),
        "p_c_model": round(reg["p"][2], 4), "n": reg["n"],
        "interpretation": ("c > 0 with p < 0.05 would mean the model knows something the closing line "
                           "does not. c <= 0 means the model is noise relative to the market."),
    }
    # totals version
    tt2 = t.dropna(subset=["market_total", "model_total", "total"])
    X2 = np.column_stack([np.ones(len(tt2)), tt2["market_total"], tt2["model_total"]])
    reg2 = ols_hc1(tt2["total"].to_numpy(float), X2)
    out["incremental_information_total"] = {
        "spec": "total = a + b*closing_total + c*model_total + e  (HC1 errors)",
        "b_market": round(reg2["beta"][1], 4), "c_model": round(reg2["beta"][2], 4),
        "se_c_model": round(reg2["se"][2], 4), "p_c_model": round(reg2["p"][2], 4), "n": reg2["n"],
    }

    # calibration of the model's win probabilities
    sigma = float(np.std(tt["result"] - tt["model_margin"], ddof=1))
    out["margin_sigma"] = round(sigma, 3)
    tt = tt.assign(model_win_prob=1 - sps.norm.cdf(0, loc=tt["model_margin"], scale=sigma))
    tt = tt.assign(blend_win_prob=1 - sps.norm.cdf(0, loc=tt["blend_margin"], scale=sigma))
    buckets = []
    for lo, hi in [(0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)]:
        b = tt[(tt["model_win_prob"] >= lo) & (tt["model_win_prob"] < hi)]
        if len(b):
            buckets.append({"range": f"{lo:.0%}-{hi:.0%}", "n": int(len(b)),
                            "predicted": round(float(b["model_win_prob"].mean()), 4),
                            "actual": round(float((b["result"] > 0).mean()), 4)})
    out["win_prob_calibration"] = {
        "sigma_points": round(sigma, 3), "buckets": buckets,
        "note": "Normal approximation P(margin > 0) with sigma fitted on out-of-sample residuals.",
        "brier_model": round(float(((tt["model_win_prob"] - (tt["result"] > 0)) ** 2).mean()), 5),
        "brier_market_50_50": 0.25,
    }

    # error by disagreement bucket: how the model behaves when it is far from the market
    t["disagreement"] = t["model_margin"] - t["market_margin"]
    dis = []
    for lo, hi in [(0, 1), (1, 2), (2, 3), (3, 5), (5, 100)]:
        b = t[(t["disagreement"].abs() >= lo) & (t["disagreement"].abs() < hi)]
        if len(b) < 10:
            continue
        model_err = float(np.abs(b["model_margin"] - b["result"]).mean())
        market_err = float(np.abs(b["market_margin"] - b["result"]).mean())
        dis.append({"abs_disagreement": f"{lo}-{hi} pts", "n": int(len(b)),
                    "model_mae": round(model_err, 3), "market_mae": round(market_err, 3)})
    out["disagreement_accuracy"] = dis

    # ------------------------------------------------------- committed predictions for audit
    t_out = t[["season", "week", "game_id", "home_team", "away_team", "model_margin", "model_total",
               "market_margin", "market_total", "result", "total"]].copy()
    t_out.round(4).to_csv(os.path.join(DERIVED, "predictions.csv"), index=False)

    # ------------------------------------------------------- originate lines for the next slate
    played = games.dropna(subset=["home_score", "away_score"])
    reg = games[games["game_type"] == "REG"]
    latest_season = int(reg["season"].max())
    played_reg = played[played["game_type"] == "REG"]
    last_week = int(played_reg[played_reg["season"] == latest_season]["week"].max())
    upcoming = reg[(reg["season"] == latest_season) & (reg["week"] == last_week + 1)]
    orig = []
    if len(upcoming):
        cutoff = upcoming["gameday"].min()
        r = R.fit(played_reg[played_reg["gameday"] < cutoff], cutoff,
                  half_life_days=best_hp[0], lam=best_hp[1],
                  hfa_prior=R.hfa_prior_from(games, cutoff))
        for g in upcoming.itertuples():
            neutral = str(getattr(g, "location", "")) == "Neutral"
            pm, pt = r.predict(g.home_team, g.away_team)
            if neutral:
                # neutral site: remove the fitted home advantage from the margin
                pm = pm - r.hfa
                pt = pt - (r.hfa / 2)
            p_home = float(1 - sps.norm.cdf(0, loc=pm, scale=sigma))
            home_fair = S.decimal_to_american(1 / p_home) if 0 < p_home < 1 else None
            away_fair = S.decimal_to_american(1 / (1 - p_home)) if 0 < p_home < 1 else None
            orig.append({
                "game_id": g.game_id, "season": latest_season, "week": last_week + 1,
                "gameday": str(g.gameday)[:10], "kickoff": str(getattr(g, "gametime", ""))[:5],
                "home": g.home_team, "away": g.away_team,
                "neutral_site": bool(neutral),
                "model_spread_home": round(float(pm), 1),
                "model_total": round(float(pt), 1),
                "model_home_win_prob": round(p_home, 4),
                "fair_home_ml": home_fair, "fair_away_ml": away_fair,
                "market_spread_home": None if pd.isna(g.spread_line) else float(g.spread_line),
                "market_total": None if pd.isna(g.total_line) else float(g.total_line),
                "market_home_ml": None if pd.isna(getattr(g, "home_moneyline", np.nan)) else float(g.home_moneyline),
                "market_away_ml": None if pd.isna(getattr(g, "away_moneyline", np.nan)) else float(g.away_moneyline),
                "edge_vs_market_spread": None if pd.isna(g.spread_line) else round(float(pm - g.spread_line), 1),
                "edge_vs_market_total": None if pd.isna(g.total_line) else round(float(pt - g.total_line), 1),
            })
        out["ratings_snapshot"] = r.to_dict()
    out["originated_lines"] = {
        "season": latest_season, "week": last_week + 1, "games": orig,
        "generated_from": f"games through week {last_week} of {latest_season}",
        "sigma_used": round(sigma, 3),
        "market_source": "nflverse schedules feed (third-party closing lines, not an official book archive)",
    }

    with open(os.path.join(DERIVED, "model.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(json.dumps({k: out[k] for k in ("accuracy_spread", "incremental_information",
                                          "incremental_information_total", "blend_selection")}, indent=2))
    print("originated games:", len(orig))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        os.makedirs(DERIVED, exist_ok=True)
        with open(os.path.join(DERIVED, "model.json"), "w") as fh:
            json.dump({"status": "failed", "error": traceback.format_exc()}, fh, indent=2)
        traceback.print_exc()
        raise SystemExit(1)
