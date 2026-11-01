"""Line origination.

Build our own spread and total for games that have not kicked off, then put them
beside the market's number. This is the deliverable the project asked for and it
is also where the honesty has to be loudest: on the 2016-2026 walk-forward
backtest the same rating model is measurably worse than the closing line, so a
difference between our number and the market's is a modelling disagreement, not
an edge.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import RESULTS, jdump, load_games
from strategies import build_games, massey, massey_margin

LOOKBACK_SEASONS = 5


def team_points_form(g: pd.DataFrame) -> pd.DataFrame:
    """Season-to-date points scored / allowed per team, from settled games only."""
    h = g[["season", "week", "home_team", "away_team", "home_score", "away_score"]].copy()
    long = pd.concat([
        h.rename(columns={"home_team": "team", "away_team": "opp", "home_score": "pf",
                          "away_score": "pa"}),
        h.rename(columns={"away_team": "team", "home_team": "opp", "away_score": "pf",
                          "home_score": "pa"}),
    ]).sort_values(["team", "season", "week"])
    long["cum_pf"] = long.groupby(["team", "season"])["pf"].cumsum().shift(1)
    long["cum_pa"] = long.groupby(["team", "season"])["pa"].cumsum().shift(1)
    long["n"] = long.groupby(["team", "season"]).cumcount()
    long["avg_pf"] = long.cum_pf / long.n.replace(0, np.nan)
    long["avg_pa"] = long.cum_pa / long.n.replace(0, np.nan)
    return long[["season", "week", "team", "avg_pf", "avg_pa", "n"]]


def main() -> dict:
    g = build_games()
    hist_all = g[(g.season >= 2015)]

    form = team_points_form(hist_all)
    hf = form.rename(columns={"team": "home_team", "avg_pf": "h_pf", "avg_pa": "h_pa", "n": "h_n"})
    af = form.rename(columns={"team": "away_team", "avg_pf": "a_pf", "avg_pa": "a_pa", "n": "a_n"})
    h = hist_all.merge(hf, on=["season", "week", "home_team"], how="left") \
                .merge(af, on=["season", "week", "away_team"], how="left")
    h = h.dropna(subset=["h_pf", "a_pf", "h_pa", "a_pa"])
    h["raw_total"] = (h.h_pf + h.a_pa + h.a_pf + h.h_pa) / 2.0
    # calibrate the naive total formula on settled history
    fit = h[h.season <= 2025].dropna(subset=["total"])
    slope, intercept = np.polyfit(fit.raw_total, fit.total, 1) if len(fit) > 100 else (1.0, 0.0)
    resid = fit.total - (intercept + slope * fit.raw_total)
    total_sigma = float(resid.std(ddof=2))

    # ---- the live slate ----------------------------------------------------
    raw = load_games()
    for c in ["result", "total", "spread_line", "total_line", "home_rest", "away_rest"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    live = raw[(raw.game_type == "REG") & (raw.season == 2026) & raw.result.isna()].copy()
    live = live[live.week <= live.week.min() + 1]
    as_of_week = int(live.week.min())

    hist = g[(g.season >= 2026 - LOOKBACK_SEASONS) & (g.week < as_of_week)]
    ratings = massey(hist, half_life_weeks=8.0, as_of=(2026, as_of_week))

    lf = form[form.season == 2026].sort_values(["team", "week"]).groupby("team").tail(1)
    live = live.merge(lf.rename(columns={"team": "home_team", "avg_pf": "h_pf",
                                         "avg_pa": "h_pa", "n": "h_n"})[
                          ["home_team", "h_pf", "h_pa", "h_n"]], on="home_team", how="left")
    live = live.merge(lf.rename(columns={"team": "away_team", "avg_pf": "a_pf",
                                         "avg_pa": "a_pa", "n": "a_n"})[
                          ["away_team", "a_pf", "a_pa", "a_n"]], on="away_team", how="left")

    live["rest_diff"] = (live.home_rest - live.away_rest).fillna(0)
    live["our_spread"] = [massey_margin(ratings, hm, aw, rd)
                          for hm, aw, rd in zip(live.home_team, live.away_team, live.rest_diff)]
    live["raw_total"] = (live.h_pf + live.a_pa + live.a_pf + live.h_pa) / 2.0
    live["our_total"] = intercept + slope * live.raw_total
    live["spread_gap"] = live.our_spread - live.spread_line
    live["total_gap"] = live.our_total - live.total_line

    rows = []
    for _, r in live.sort_values(["week", "gameday"]).iterrows():
        rows.append({
            "week": int(r.week), "gameday": str(r.gameday),
            "away": r.away_team, "home": r.home_team,
            "our_home_line": None if pd.isna(r.our_spread) else round(float(r.our_spread), 1),
            "market_home_line": None if pd.isna(r.spread_line) else float(r.spread_line),
            "line_gap": None if pd.isna(r.spread_gap) else round(float(r.spread_gap), 1),
            "our_total": None if pd.isna(r.our_total) else round(float(r.our_total), 1),
            "market_total": None if pd.isna(r.total_line) else float(r.total_line),
            "total_gap": None if pd.isna(r.total_gap) else round(float(r.total_gap), 1),
            "home_form_pf": None if pd.isna(r.h_pf) else round(float(r.h_pf), 1),
            "away_form_pf": None if pd.isna(r.a_pf) else round(float(r.a_pf), 1),
            "games_of_form": int(max(r.h_n or 0, r.a_n or 0)) if pd.notna(r.h_n) else None,
        })

    gaps = live.spread_gap.dropna()
    tgaps = live.total_gap.dropna()
    all_ratings = sorted(ratings["rating"].items(), key=lambda kv: -kv[1])
    out = {
        "as_of": {"season": 2026, "week": as_of_week,
                  "last_scored_week": int(g[(g.season == 2026) & g.result.notna()].week.max()),
                  "games_used_for_ratings": int(ratings["n"])},
        "ratings_model": {
            "type": "opponent-adjusted scoring-margin least squares (Massey)",
            "half_life_weeks": 8.0, "hfa": float(ratings["hfa"]),
            "sigma": float(ratings["sigma"]), "n_games": int(ratings["n"]),
            "top": [{"team": t, "rating": round(v, 2)} for t, v in all_ratings[:6]],
            "bottom": [{"team": t, "rating": round(v, 2)} for t, v in all_ratings[-6:]],
        },
        "total_model": {"slope": float(slope), "intercept": float(intercept),
                        "sigma": total_sigma, "n_fit": int(len(fit)),
                        "form": "season-to-date points scored/allowed, opponent-agnostic"},
        "games": rows,
        "summary": {
            "n_games": len(rows),
            "n_with_market_line": int(len(gaps)),
            "mean_abs_line_gap": float(gaps.abs().mean()) if len(gaps) else None,
            "median_abs_line_gap": float(gaps.abs().median()) if len(gaps) else None,
            "max_abs_line_gap": float(gaps.abs().max()) if len(gaps) else None,
            "mean_abs_total_gap": float(tgaps.abs().mean()) if len(tgaps) else None,
            "corr_our_line_market_line": float(np.corrcoef(
                live.spread_line.dropna()[
                    live.spread_line.notna()].to_numpy(float),
                live.our_spread[live.spread_line.notna()].to_numpy(float))[0, 1]) if len(gaps) > 5 else None,
            "note": ("A gap is not an edge. The same model loses to the closing line "
                     "across 2016-2026, so these numbers are a benchmark of model "
                     "disagreement, not a bet list."),
        },
        "convention": ("Lines use the source-data convention: the number is the home "
                       "team's line and a positive value means the home team is "
                       "favoured by that many points."),
    }
    jdump(out, RESULTS / "originate.json")
    print("originate.json:", {k: out["summary"][k] for k in
                              ["n_games", "mean_abs_line_gap", "corr_our_line_market_line"]})
    for r in rows[:5]:
        print("  ", r["week"], r["away"], "@", r["home"], "ours", r["our_home_line"],
              "mkt", r["market_home_line"], "| tot", r["our_total"], r["market_total"])
    return out


if __name__ == "__main__":
    main()
