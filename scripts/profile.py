#!/usr/bin/env python3
"""Profile the downloaded data so every downstream number is built on observed, not assumed, columns.

Output: data/derived/profile.json
"""
from __future__ import annotations

import glob
import json
import os

import pandas as pd

RAW = os.path.join("data", "raw")
DERIVED = os.path.join("data", "derived")


def frame_info(df: pd.DataFrame, name: str, season_col: str | None = "season") -> dict:
    info = {
        "file": name,
        "rows": int(len(df)),
        "columns": list(df.columns),
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
    }
    if season_col and season_col in df.columns:
        info["seasons"] = sorted(int(s) for s in df[season_col].dropna().unique())
        info["rows_by_season"] = {
            int(k): int(v) for k, v in df[season_col].value_counts().sort_index().items()
        }
    return info


def main() -> None:
    os.makedirs(DERIVED, exist_ok=True)
    profile: dict = {}

    games = pd.read_parquet(os.path.join(RAW, "games.parquet"))
    profile["games"] = frame_info(games, "games.parquet")
    odds_cols = [c for c in ("spread_line", "total_line", "away_moneyline", "home_moneyline")
                 if c in games.columns]
    profile["games"]["odds_columns"] = odds_cols
    if odds_cols:
        cov = games.groupby("season")[odds_cols].apply(lambda d: d.notna().mean().round(3))
        profile["games"]["odds_coverage_by_season"] = {
            int(s): {c: float(v) for c, v in row.items()} for s, row in cov.iterrows()
        }
    for c in ("result", "total", "home_score", "away_score"):
        if c in games.columns:
            profile["games"][f"nonnull_{c}"] = int(games[c].notna().sum())

    player_files = sorted(glob.glob(os.path.join(RAW, "stats_player_week_*.parquet")))
    player = pd.concat([pd.read_parquet(f) for f in player_files], ignore_index=True) if player_files else pd.DataFrame()
    if len(player):
        profile["player_week"] = frame_info(player, f"{len(player_files)} season files")
        stat_cols = [c for c in (
            "passing_yards", "rushing_yards", "receiving_yards", "receptions", "targets",
            "carries", "passing_tds", "rushing_tds", "receiving_tds", "interceptions",
            "attempts", "completions", "fantasy_points", "fantasy_points_ppr",
        ) if c in player.columns]
        profile["player_week"]["stat_columns_present"] = stat_cols
        if "season_type" in player.columns:
            profile["player_week"]["season_type_counts"] = {
                str(k): int(v) for k, v in player["season_type"].value_counts().items()
            }
        if "week" in player.columns and "season" in player.columns:
            cur = player[player["season"] == player["season"].max()]
            profile["player_week"]["current_season_max_week"] = int(cur["week"].max())
        profile["player_week"]["positions"] = (
            {str(k): int(v) for k, v in player["position"].value_counts().head(15).items()}
            if "position" in player.columns else {}
        )

    team_files = sorted(glob.glob(os.path.join(RAW, "stats_team_week_*.parquet")))
    if team_files:
        team = pd.concat([pd.read_parquet(f) for f in team_files], ignore_index=True)
        profile["team_week"] = frame_info(team, f"{len(team_files)} season files")
        profile["team_week"]["stat_columns_present"] = [
            c for c in team.columns if any(k in c for k in ("points", "yards", "turnover", "epa", "third"))
        ][:60]

    with open(os.path.join(DERIVED, "profile.json"), "w") as fh:
        json.dump(profile, fh, indent=2, default=str)

    print("=== GAMES ===")
    print("rows", profile["games"]["rows"], "seasons", profile["games"]["seasons"][:3], "...",
          profile["games"]["seasons"][-3:])
    print("columns:", profile["games"]["columns"])
    if odds_cols:
        for s in (1999, 2010, 2020, 2025, 2026):
            if s in profile["games"]["odds_coverage_by_season"]:
                print(s, profile["games"]["odds_coverage_by_season"][s])
    print("=== PLAYER ===")
    if "player_week" in profile:
        print("rows", profile["player_week"]["rows"], "cols", len(profile["player_week"]["columns"]))
        print("stat cols:", profile["player_week"]["stat_columns_present"])
        print("max week current season:", profile["player_week"].get("current_season_max_week"))
        print("season_type:", profile["player_week"].get("season_type_counts"))
    print("=== TEAM ===")
    if "team_week" in profile:
        print("rows", profile["team_week"]["rows"])
        print("stat cols:", profile["team_week"]["stat_columns_present"])


if __name__ == "__main__":
    main()
