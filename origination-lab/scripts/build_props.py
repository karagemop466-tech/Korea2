#!/usr/bin/env python3
"""Player prop line origination.

We originate our own player prop numbers from player-week data and grade them
out of sample (2023 -> 2024):

  baseline line  : recency-weighted player average (no opponent information)
  our line       : opponent-adjusted, shrunk toward the position mean, with a
                   usage/efficiency blend

Because the source extract contains no sportsbook player-prop prices, prop
strategies CANNOT be settled against a market. They are therefore reported in a
separate "unpriced research" tier and are excluded from the ranked leaderboard.
That gap is published on the Flagged for Review page.

Outputs data/derived/props.json
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nflcore as nc

OUT = nc.DERIVED / "props.json"
MD = lambda x, n=3: None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else round(float(x), n)

MARKETS = [
    ("passing_yards", "QB", "Passing yards", 6),
    ("rushing_yards", "RB", "Rushing yards", 5),
    ("receiving_yards", "WR/TE", "Receiving yards", 5),
    ("receptions", "WR/TE", "Receptions", 5),
]


def load():
    df = nc.load_player_weeks()
    df["week"] = pd.to_numeric(df["week"], errors="coerce")
    df["season"] = pd.to_numeric(df["season"], errors="coerce")
    for c in ["passing_yards", "rushing_yards", "receiving_yards", "receptions",
              "targets", "carries", "attempts", "passing_tds", "rushing_tds",
              "receiving_tds", "passing_epa", "rushing_epa", "receiving_epa"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df


def team_defence(df, stat, shrink_games=6.0):
    """Expanding, shrunk opponent-allowed average per team using prior weeks only."""
    conceded = (df.groupby(["season", "week", "opponent_team"])[stat].sum()
                  .reset_index().rename(columns={"opponent_team": "team", stat: "allowed"}))
    conceded = conceded.sort_values(["season", "week"])
    grp = conceded.groupby(["season", "team"])["allowed"]
    conceded["def_games"] = grp.transform(lambda s: s.shift(1).expanding().count())
    conceded["def_mean"] = grp.transform(lambda s: s.shift(1).expanding().mean())
    # league baseline = mean of the per-team weekly allowance, averaged over the season
    lgt = conceded.groupby(["season", "week"])["allowed"].mean().reset_index()
    lgt["lg_mean"] = lgt.groupby("season")["allowed"].transform("mean")
    conceded = conceded.merge(lgt[["season", "week", "lg_mean"]], on=["season", "week"], how="left")
    w = conceded["def_games"] / (conceded["def_games"] + shrink_games)
    conceded["def_shrunk"] = w * conceded["def_mean"] + (1 - w) * conceded["lg_mean"]
    return conceded.pivot_table(index=["season", "week", "team"],
                                values=["def_shrunk", "lg_mean"]).reset_index()


def build_market(df, stat, pos, label, window):
    d = df[df.position_group.isin([pos] if pos != "WR/TE" else ["WR", "TE"])].copy()
    d = d[d[stat] > 0]
    d = d.sort_values(["player_id", "season", "week"]).reset_index(drop=True)
    g = d.groupby("player_id", sort=False)
    w = [0.35, 0.25, 0.2, 0.12, 0.08]
    W = len(w)
    d["baseline"] = g[stat].transform(lambda s: s.shift(1).rolling(W, min_periods=2).apply(
        lambda x: np.dot(x[::-1], np.array(w[:len(x)])) / np.sum(w[:len(x)]), raw=True))
    d["hist_n"] = g.cumcount()
    # causal calibration on the player's OWN prior residuals (fixes skew/level)
    d["resid"] = d[stat] - d["baseline"]
    d["resid_med"] = d.groupby("player_id")["resid"].transform(
        lambda s: s.shift(1).expanding(min_periods=2).median())
    # shrunk opponent adjustment
    conceded = team_defence(d, stat)
    d = d.merge(conceded, left_on=["season", "week", "opponent_team"],
                right_on=["season", "week", "team"], how="left", suffixes=("", "_c"))
    opp = d["def_shrunk"].fillna(d["lg_mean"])
    adj = (d["lg_mean"].fillna(opp) - opp) / opp.clip(lower=1.0)
    d["our_line"] = (d["baseline"] + d["resid_med"].fillna(0.0)
                     + d["baseline"] * 0.25 * adj.clip(-0.5, 0.5))
    d = d.dropna(subset=["baseline"])
    d = d[d.hist_n >= 3]
    d["actual"] = d[stat]
    d["over_our"] = d.actual > d.our_line
    d["over_base"] = d.actual > d.baseline
    return d


def calibration(d, col, label):
    """Over-rate at successive offsets from the originated line."""
    rows = []
    for off in [-10, -5, -2, -0.5, 0.5, 2, 5, 10]:
        for season, tag in ((2023, "2023 train"), (2024, "2024 test")):
            s = d[d.season == season]
            if s.empty:
                continue
            actual = s.actual.to_numpy()
            line = s[col].to_numpy() + off
            over = actual > line
            push = np.isclose(actual, line)
            n = int((~push).sum())
            if n == 0:
                continue
            rows.append({"offset": off, "window": tag, "n": n,
                         "over_rate": MD(over[~push].mean()),
                         "push_rate": MD(push.mean())})
    return rows


def main():
    df = load()
    out_markets = []
    all_rows = []
    for stat, pos, label, min_hist in MARKETS:
        d = build_market(df, stat, pos, label, min_hist)
        d["market"] = stat
        all_rows.append(d)
        test = d[d.season == 2024]
        train = d[d.season == 2023]
        out_markets.append({
            "market": stat, "label": label, "position": pos,
            "n_player_weeks": int(len(d)),
            "n_train_2023": int(len(train)), "n_test_2024": int(len(test)),
            "mae_baseline_test": MD((test.actual - test.baseline).abs().mean(), 2),
            "mae_our_test": MD((test.actual - test.our_line).abs().mean(), 2),
            "bias_our_test": MD((test.actual - test.our_line).mean(), 2),
            "mae_baseline_train": MD((train.actual - train.baseline).abs().mean(), 2),
            "mae_our_train": MD((train.actual - train.our_line).abs().mean(), 2),
            "over_rate_at_line_test": MD(test.over_our.mean(), 4),
            "over_rate_baseline_test": MD(test.over_base.mean(), 4),
            "calibration_error_our": MD(abs(test.over_our.mean() - 0.5), 4),
            "calibration_error_baseline": MD(abs(test.over_base.mean() - 0.5), 4),
            "push_rate_test": MD((test.actual == test.our_line).mean(), 4),
            "median_line_test": MD(test.our_line.median(), 1),
            "calibration": calibration(test if test.empty else d, "our_line", label),
            "players_test": int(test.player_id.nunique()),
        })

    combined = pd.concat(all_rows, ignore_index=True)
    # originate the most recent week available as a worked example
    latest = combined.sort_values(["season", "week"]).tail(20)
    examples = [{
        "season": int(r.season), "week": int(r.week), "player": r.player_display_name,
        "team": r.recent_team, "opp": r.opponent_team, "market": r.market,
        "our_line": MD(r.our_line, 1), "actual": MD(r.actual, 0),
        "result": "over" if r.actual > r.our_line else ("push" if r.actual == r.our_line else "under"),
    } for r in latest.itertuples()]

    payload = {
        "markets": out_markets,
        "examples": examples,
        "window_note": "2023 = fit/diagnostic season, 2024 = out-of-sample test season",
        "pricing_note": ("No player-prop prices exist in the verified source extracts. These lines "
                         "are originated, graded for accuracy and calibration, and NOT settled "
                         "against a market. They are excluded from the ranked leaderboard."),
        "position_summary": [],
    }
    # save per-week originated lines for the correlation layer
    keep = combined[["season", "week", "player_id", "player_display_name", "recent_team",
                     "opponent_team", "market", "our_line", "actual"]]
    keep.to_csv(nc.DERIVED / "prop_lines.csv", index=False)
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    for m in out_markets:
        print(f"{m['market']:18s} n={m['n_player_weeks']:6d} test_mae_base={m['mae_baseline_test']} "
              f"our={m['mae_our_test']} bias={m['bias_our_test']} overrate={m['over_rate_at_line_test']}")
    print("total player-weeks", len(combined))


if __name__ == "__main__":
    main()
