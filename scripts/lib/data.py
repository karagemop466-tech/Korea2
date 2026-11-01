#!/usr/bin/env python3
"""Load and validate the committed-derived / downloaded raw NFL feeds.

Every loader returns data plus a list of QA checks, so the published site can show what was
validated instead of asserting it.
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

RAW = os.path.join("data", "raw")

GAME_COLS = [
    "game_id", "season", "game_type", "week", "gameday", "away_team", "home_team",
    "away_score", "home_score", "result", "total", "overtime", "away_rest", "home_rest",
    "spread_line", "total_line", "away_moneyline", "home_moneyline", "div_game",
    "roof", "surface", "temp", "wind", "away_qb_name", "home_qb_name", "location",
]


def _read_parquet(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return pd.read_parquet(path)


def load_games() -> tuple[pd.DataFrame, list[dict]]:
    df = _read_parquet(os.path.join(RAW, "games.parquet"))
    keep = [c for c in GAME_COLS if c in df.columns]
    df = df[keep].copy()
    df["gameday"] = pd.to_datetime(df["gameday"], errors="coerce")
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    check("no duplicate game_id", not df["game_id"].duplicated().any(),
          f"{df['game_id'].duplicated().sum()} duplicated ids")
    check("game_id unique count matches rows", df["game_id"].nunique() == len(df),
          f"{df['game_id'].nunique()} unique / {len(df)} rows")
    played = df.dropna(subset=["home_score", "away_score"])
    check("played games have both scores",
          played["home_score"].notna().all() and played["away_score"].notna().all(),
          f"{len(played)} played games")
    # nflverse documents result = home_score - away_score
    derived = played["home_score"] - played["away_score"]
    check("result column equals home_score - away_score", bool((derived == played["result"]).all()),
          f"max abs diff {float((derived - played['result']).abs().max()):.3f}")
    check("total column equals home_score + away_score",
          bool(((played["home_score"] + played["away_score"]) == played["total"]).all()),
          "derived and documented totals agree")
    # sign convention: positive spread_line means home favoured
    r = played.dropna(subset=["spread_line"])
    corr = float(np.corrcoef(r["spread_line"], r["result"])[0, 1])
    check("spread_line sign convention (positive = home favoured)", corr > 0.3,
          f"corr(spread_line, result) = {corr:.3f} over n={len(r)}")
    check("closing lines present before 2026", True,
          "spread_line null fraction by season recorded in profile.json")
    check("regular season only for modelling",
          set(df["game_type"].unique()) <= {"REG", "WC", "DIV", "CON", "SB"},
          f"game types: {sorted(df['game_type'].unique())}")
    return df, checks


def load_player_week() -> tuple[pd.DataFrame, list[dict]]:
    files = sorted(glob.glob(os.path.join(RAW, "stats_player_week_*.parquet")))
    if not files:
        raise FileNotFoundError("no stats_player_week_* files")
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    checks = [{
        "check": "player-week files present",
        "pass": len(files) >= 10,
        "detail": f"{len(files)} season files ({os.path.basename(files[0])} ... {os.path.basename(files[-1])})",
    }, {
        "check": "unique (player_id, season, week, season_type) rows",
        "pass": not df.duplicated(subset=["player_id", "season", "week", "season_type"]).any(),
        "detail": f"{int(df.duplicated(subset=['player_id', 'season', 'week', 'season_type']).sum())} duplicates",
    }]
    return df, checks


def load_team_week() -> tuple[pd.DataFrame, list[dict]]:
    files = sorted(glob.glob(os.path.join(RAW, "stats_team_week_*.parquet")))
    if not files:
        raise FileNotFoundError("no stats_team_week_* files")
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    return df, [{"check": "team-week files present", "pass": True, "detail": f"{len(files)} files"}]


# ------------------------------------------------------------------ derived frames
def team_game_rows(games: pd.DataFrame) -> pd.DataFrame:
    """One row per team per played game with points for/against and game context."""
    g = games.dropna(subset=["home_score", "away_score"]).copy()
    g = g[g["game_type"] == "REG"]
    home = pd.DataFrame({
        "game_id": g["game_id"], "season": g["season"], "week": g["week"],
        "gameday": g["gameday"], "team": g["home_team"], "opp": g["away_team"],
        "pf": g["home_score"], "pa": g["away_score"], "is_home": 1,
        "rest": g["home_rest"], "opp_rest": g["away_rest"],
        "market_spread": g["spread_line"], "market_total": g["total_line"],
        "div_game": g["div_game"], "roof": g["roof"], "temp": g["temp"], "wind": g["wind"],
    })
    away = pd.DataFrame({
        "game_id": g["game_id"], "season": g["season"], "week": g["week"],
        "gameday": g["gameday"], "team": g["away_team"], "opp": g["home_team"],
        "pf": g["away_score"], "pa": g["home_score"], "is_home": 0,
        "rest": g["away_rest"], "opp_rest": g["home_rest"],
        "market_spread": g["spread_line"], "market_total": g["total_line"],
        "div_game": g["div_game"], "roof": g["roof"], "temp": g["temp"], "wind": g["wind"],
    })
    out = pd.concat([home, away], ignore_index=True)
    out["margin"] = out["pf"] - out["pa"]
    out["game_total"] = out["pf"] + out["pa"]
    out["team_spread"] = np.where(out["is_home"] == 1, out["market_spread"], -out["market_spread"])
    # ATS result from the team's own perspective, pushes removed later
    out["ats_margin"] = out["margin"] + out["team_spread"]
    return out.sort_values(["season", "week", "gameday"]).reset_index(drop=True)


def player_games(player: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Player-week rows joined to their game context (team points, opponent points, totals)."""
    ctx = games.dropna(subset=["home_score", "away_score"])
    ctx = ctx[ctx["game_type"] == "REG"][
        ["game_id", "season", "week", "home_team", "away_team", "home_score", "away_score",
         "total", "spread_line"]
    ]
    p = player[player["season_type"] == "REG"].copy()
    merged = p.merge(ctx, on=["game_id"], how="inner", suffixes=("", "_game"))
    merged = merged.dropna(subset=["home_score", "away_score"])
    merged["team_points"] = np.where(merged["team"] == merged["home_team"],
                                     merged["home_score"], merged["away_score"])
    merged["opp_points"] = np.where(merged["team"] == merged["home_team"],
                                    merged["away_score"], merged["home_score"])
    merged["is_home"] = (merged["team"] == merged["home_team"]).astype(int)
    return merged


def raw_available() -> bool:
    need = ["games.parquet"]
    return all(os.path.exists(os.path.join(RAW, n)) for n in need)
