#!/usr/bin/env python3
"""How efficient is the NFL closing market? Everything a strategy claims must be judged against this.

Outputs data/derived/market.json
"""
from __future__ import annotations

import json
import math
import os
import traceback

import numpy as np
import pandas as pd

from lib import data as D
from lib import stats as S

DERIVED = os.path.join("data", "derived")
TEST_START = 2023  # held-out window used consistently across the whole project


def accuracy(pred: np.ndarray, actual: np.ndarray) -> dict:
    m = np.isfinite(pred) & np.isfinite(actual)
    pred, actual = pred[m], actual[m]
    if pred.size == 0:
        return {"n": 0}
    err = actual - pred
    return {
        "n": int(pred.size),
        "mae": round(float(np.abs(err).mean()), 3),
        "rmse": round(float(np.sqrt((err ** 2).mean())), 3),
        "bias": round(float(err.mean()), 3),
        "sd_resid": round(float(err.std(ddof=1)), 3),
        "corr": round(float(np.corrcoef(pred, actual)[0, 1]), 4),
    }


def main() -> None:
    out: dict = {}
    games, checks = D.load_games()
    played = games.dropna(subset=["home_score", "away_score"]).copy()
    played = played[played["game_type"] == "REG"]

    # ------------------------------------------------ data QA
    out["qa"] = {"checks": checks}

    # ------------------------------------------------ closing-line accuracy (all seasons)
    out["closing_spread_accuracy"] = accuracy(played["spread_line"].to_numpy(),
                                             played["result"].to_numpy())
    out["closing_total_accuracy"] = accuracy(played["total_line"].to_numpy(),
                                            played["total"].to_numpy())
    out["closing_spread_accuracy_recent"] = accuracy(
        played.loc[played.season >= TEST_START, "spread_line"].to_numpy(),
        played.loc[played.season >= TEST_START, "result"].to_numpy())

    # ------------------------------------------------ home field advantage by season
    hfa = played.groupby("season").agg(
        games=("result", "size"), mean_margin=("result", "mean"), home_win=("result", lambda s: (s > 0).mean())
    ).reset_index()
    out["home_field_by_season"] = [
        {"season": int(r.season), "games": int(r.games),
         "mean_home_margin": round(float(r.mean_margin), 2),
         "home_win_rate": round(float(r.home_win), 4)} for r in hfa.itertuples()
    ]

    # ------------------------------------------------ ATS efficiency
    ats = played.copy()
    ats["ats_edge"] = ats["result"] + ats["spread_line"]  # >0 means home cover
    ats["ats"] = np.sign(ats["ats_edge"]).where(ats["ats_edge"].abs() > 1e-9, 0)
    decided = ats[ats["ats"] != 0]
    k = int((decided["ats"] > 0).sum())
    n = int(len(decided))
    lo, hi = S.wilson_ci(k, n)
    out["ats_home_cover"] = {
        "n": n, "home_covers": k, "home_cover_rate": round(k / n, 4),
        "ci": [round(lo, 4), round(hi, 4)], "binomial_p": round(S.binomial_p(k, n), 4),
        "pushes": int(len(ats) - n - int(ats["ats_edge"].isna().sum())),
        "note": "Home-team covers across all regular-season games with a closing spread.",
    }
    # over/under base rate
    tot = played.dropna(subset=["total_line"])
    over = (tot["total"] > tot["total_line"]).sum()
    push = (tot["total"] == tot["total_line"]).sum()
    dec = int(len(tot) - push)
    lo2, hi2 = S.wilson_ci(int(over), dec)
    out["totals_over_rate"] = {
        "n": dec, "overs": int(over), "pushes": int(push), "over_rate": round(float(over) / dec, 4),
        "ci": [round(lo2, 4), round(hi2, 4)], "binomial_p": round(S.binomial_p(int(over), dec), 4),
    }
    # by season, to show the absence of a stable bias
    by_season = []
    for season, grp in decided.groupby("season"):
        kk, nn = int((grp["ats"] > 0).sum()), int(len(grp))
        by_season.append({"season": int(season), "n": nn, "home_cover_rate": round(kk / nn, 4)})
    out["ats_by_season"] = by_season

    # ------------------------------------------------ key numbers
    margins = played["result"].abs().astype(int)
    counts = margins.value_counts().normalize().sort_index()
    out["key_numbers"] = {
        "top_absolute_margins": [
            {"margin": int(m), "share": round(float(s), 4)}
            for m, s in counts.sort_values(ascending=False).head(8).items()
        ],
        "share_exactly_3": round(float(counts.get(3, 0.0)), 4),
        "share_exactly_7": round(float(counts.get(7, 0.0)), 4),
        "push_rate_on_3": round(float(counts.get(3, 0.0)), 4),
        "push_rate_on_7": round(float(counts.get(7, 0.0)), 4),
        "n_games": int(len(played)),
        "note": ("Share of games with that absolute margin. A spread sitting on 3 or 7 pushes at "
                 "roughly these rates, which is why those numbers are priced differently."),
    }
    landing_totals = played["total"].dropna().round().astype(int).value_counts().sort_index()
    out["total_landing_spots"] = [
        {"total": int(t), "games": int(c)} for t, c in landing_totals.tail(12).items()
    ]

    # ------------------------------------------------ market calibration from moneylines
    ml = played.dropna(subset=["home_moneyline", "away_moneyline"])
    if len(ml) > 100:
        rows = []
        for r in ml.itertuples():
            dq = [S.american_to_decimal(r.home_moneyline), S.american_to_decimal(r.away_moneyline)]
            raw = [S.implied_prob(d) for d in dq]
            fair = S.devig_shin(raw)
            rows.append({"season": int(r.season), "p_home": fair[0], "home_won": int(r.result > 0),
                         "push": int(r.result == 0)})
        cal = pd.DataFrame(rows)
        cal = cal[cal["push"] == 0].copy()
        cal["bin"] = pd.qcut(cal["p_home"], 10, duplicates="drop", labels=False)
        table = []
        for b, grp in cal.groupby("bin"):
            table.append({
                "bucket": int(b), "n": int(len(grp)),
                "mean_market_prob": round(float(grp["p_home"].mean()), 4),
                "actual_win_rate": round(float(grp["home_won"].mean()), 4),
                "diff": round(float(grp["home_won"].mean() - grp["p_home"].mean()), 4),
            })
        brier = float(((cal["p_home"] - cal["home_won"]) ** 2).mean())
        out["moneyline_calibration"] = {
            "n": int(len(cal)),
            "devig_method": "Shin (1993) two-way",
            "brier_score": round(brier, 5),
            "brier_random_50": 0.25,
            "buckets": table,
            "seasons": [int(ml["season"].min()), int(ml["season"].max())],
        }

    # ------------------------------------------------ market spread vs result regression
    reg = played.dropna(subset=["spread_line", "result"])
    x = reg["spread_line"].to_numpy(float)
    y = reg["result"].to_numpy(float)
    beta, alpha = np.polyfit(x, y, 1)
    out["spread_result_regression"] = {
        "n": int(len(reg)), "slope": round(float(beta), 4), "intercept": round(float(alpha), 4),
        "note": "A perfectly efficient, unbiased closing line implies slope 1.0 and intercept ~ home field advantage / 2.",
    }

    # ------------------------------------------------ vig / hold
    odds_pairs = played.dropna(subset=["away_spread_odds", "home_spread_odds"])
    if len(odds_pairs):
        holds = []
        for r in odds_pairs.itertuples():
            a = S.american_to_decimal(r.away_spread_odds)
            h = S.american_to_decimal(r.home_spread_odds)
            holds.append(S.implied_prob(a) + S.implied_prob(h) - 1)
        out["spread_hold"] = {
            "n": int(len(holds)), "mean_hold": round(float(np.mean(holds)), 4),
            "median_hold": round(float(np.median(holds)), 4),
            "note": "Sum of implied probabilities minus 1 at the quoted two-way spread price.",
        }

    with open(os.path.join(DERIVED, "market.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(json.dumps({k: v for k, v in out.items() if k in
                      ("closing_spread_accuracy", "ats_home_cover", "totals_over_rate")}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        os.makedirs(DERIVED, exist_ok=True)
        with open(os.path.join(DERIVED, "market.json"), "w") as fh:
            json.dump({"status": "failed", "error": traceback.format_exc()}, fh, indent=2)
        raise SystemExit(1)
