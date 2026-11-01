#!/usr/bin/env python3
"""Decide the spread sign convention from the data itself, and publish the evidence.

If `spread_line` were the home team's handicap (home +3), then home covers when
result + spread_line > 0. If it is "home favoured by X" (a predicted home margin), home covers when
result - spread_line > 0. Exactly one of those produces a ~50% cover rate, because book lines are
two-way balanced. The moneyline columns give an independent cross-check.

Outputs data/derived/diag_signs.json and data/derived/sample_games_2026.csv (audit sample).
"""
from __future__ import annotations

import json
import os
import traceback

import numpy as np
import pandas as pd

from lib import data as D

DERIVED = os.path.join("data", "derived")


def main() -> None:
    games, checks = D.load_games()
    played = games.dropna(subset=["home_score", "away_score", "spread_line"]).copy()
    played = played[played["game_type"] == "REG"]

    out: dict = {"n_games_with_line": int(len(played)), "qa_checks": checks}
    out["corr_spread_line_result"] = round(float(np.corrcoef(played["spread_line"], played["result"])[0, 1]), 4)

    conv_a = played["result"] - played["spread_line"]   # spread_line = home favoured by X
    conv_b = played["result"] + played["spread_line"]   # spread_line = home handicap (+X)
    out["home_cover_rate_if_line_means_home_favoured"] = {
        "cover_rate_excl_push": round(float((conv_a[conv_a != 0] > 0).mean()), 4),
        "n": int((conv_a != 0).sum()), "pushes": int((conv_a == 0).sum()),
    }
    out["home_cover_rate_if_line_means_home_handicap"] = {
        "cover_rate_excl_push": round(float((conv_b[conv_b != 0] > 0).mean()), 4),
        "n": int((conv_b != 0).sum()), "pushes": int((conv_b == 0).sum()),
    }

    ml = played.dropna(subset=["home_moneyline"])
    if len(ml):
        fav = ml[ml["home_moneyline"] < 0]
        dog = ml[ml["home_moneyline"] > 0]
        out["moneyline_cross_check"] = {
            "mean_spread_line_when_home_is_ml_favourite": round(float(fav["spread_line"].mean()), 3),
            "n_home_fav": int(len(fav)),
            "mean_spread_line_when_home_is_ml_underdog": round(float(dog["spread_line"].mean()), 3),
            "n_home_dog": int(len(dog)),
            "verdict": ("If home ML favourites show a POSITIVE mean spread_line, then positive means "
                        "the home team is favoured (a predicted home margin), because a home team "
                        "favoured on the moneyline lays points on the spread."),
        }

    recent = played[played["season"] >= 2025]
    out["recent_years_same_tests"] = {
        "seasons": sorted(int(s) for s in recent["season"].unique()),
        "corr_spread_line_result": round(float(np.corrcoef(recent["spread_line"], recent["result"])[0, 1]), 4),
        "home_cover_rate_if_home_favoured": round(float((recent["result"] - recent["spread_line"] > 0).mean()), 4),
        "home_cover_rate_if_home_handicap": round(float((recent["result"] + recent["spread_line"] > 0).mean()), 4),
    }

    # totals cross-check
    tot = games.dropna(subset=["total", "total_line"])
    out["totals_check"] = {
        "n": int(len(tot)),
        "mean_total": round(float(tot["total"].mean()), 2),
        "mean_total_line": round(float(tot["total_line"].mean()), 2),
        "over_rate": round(float((tot["total"] > tot["total_line"]).mean()), 4),
        "corr": round(float(np.corrcoef(tot["total_line"], tot["total"])[0, 1]), 4),
    }

    # 2026 audit sample: every week-9 game with a line, plus the last eight played games
    s = games[(games["season"] == 2026)].copy()
    sample = s[s["game_type"] == "REG"].tail(30)[[
        "game_id", "week", "gameday", "home_team", "away_team", "home_score", "away_score",
        "result", "total", "spread_line", "total_line", "home_moneyline", "away_moneyline",
        "away_spread_odds", "home_spread_odds", "over_odds", "under_odds",
    ]]
    sample.to_csv(os.path.join(DERIVED, "sample_games_2026.csv"), index=False)

    with open(os.path.join(DERIVED, "diag_signs.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(1)
