#!/usr/bin/env python3
"""Export the pruned, committed extracts from the downloaded raw feeds.

Why this file exists
--------------------
The analysis JSON in `data/derived/` is produced from `data/raw/*.parquet`, which is gitignored.
Until 2026-11-02 the pruned extracts committed next to it (`games.csv.gz`, `player_week.csv.gz`,
`team_week.csv.gz`) were built by a *different* producer over a *different* season range, so after a
data refresh the published numbers no longer followed from the committed files. The verification
session measured that gap (49 checks, 21 disagreements on the refreshed tree) and this script closes
it: run after `scripts/fetch_data.py`, it writes the extracts from exactly the parquet files the
analysis reads, plus `data/provenance.json`, so "every number is reproducible from the committed
data" is a fact rather than a claim.

Column sets are pinned to the existing CSV headers, so the shape of the committed files does not
change when this runs.

    pip install pandas pyarrow
    python scripts/fetch_data.py
    python scripts/export_extracts.py
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

RAW = os.path.join("data", "raw")
DERIVED = os.path.join("data", "derived")

# Pinned to the headers of the committed extracts (verified 2026-11-02).
COLUMNS = {
    "games.csv.gz": [
        "game_id", "season", "game_type", "week", "gameday", "weekday", "gametime",
        "away_team", "away_score", "home_team", "home_score", "location", "result",
        "total", "overtime", "away_rest", "home_rest", "away_moneyline", "home_moneyline",
        "spread_line", "away_spread_odds", "home_spread_odds", "total_line", "under_odds",
        "over_odds", "div_game", "roof", "surface", "temp", "wind", "away_qb_name",
        "home_qb_name", "stadium", "referee",
    ],
    "player_week.csv.gz": [
        "player_id", "player_display_name", "position", "position_group", "season", "week",
        "season_type", "team", "opponent_team", "completions", "attempts", "passing_yards",
        "passing_tds", "passing_interceptions", "passing_epa", "passing_cpoe", "sacks_suffered",
        "carries", "rushing_yards", "rushing_tds", "rushing_epa", "receptions", "targets",
        "receiving_yards", "receiving_tds", "receiving_air_yards", "receiving_epa",
        "target_share", "air_yards_share", "wopr", "racr",
    ],
    "team_week.csv.gz": [
        "season", "week", "team", "season_type", "game_id", "opponent_team", "attempts",
        "passing_yards", "passing_tds", "passing_interceptions", "sacks_suffered",
        "passing_air_yards", "passing_epa", "passing_cpoe", "carries", "rushing_yards",
        "rushing_tds", "rushing_epa", "receptions", "targets", "receiving_yards",
        "receiving_epa", "def_sacks", "def_interceptions", "def_tackles_for_loss", "fg_made",
        "fg_att", "punt_returns", "penalties", "penalty_yards", "fumbles_lost_total", "timeouts",
    ],
}

SEASON_MIN = 2012  # the window the analysis actually reads


def write_csv_gz(df: pd.DataFrame, path: str) -> None:
    """Deterministic gzip: fixed mtime, so an unchanged dataset produces an unchanged file."""
    with open(path, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as gz:
            df.to_csv(gz, index=False)


def sha256(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(name: str) -> pd.DataFrame:
    path = os.path.join(RAW, name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} is missing - run scripts/fetch_data.py first")
    return pd.read_parquet(path)


def main() -> int:
    os.makedirs(DERIVED, exist_ok=True)
    out: dict = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_repository": "https://github.com/nflverse/nflverse-data",
        "note": ("Pruned extracts written by scripts/export_extracts.py from the same parquet files the "
                 "analysis reads, so the committed data and the published numbers cannot drift apart."),
        "columns_pinned": True,
        "files": [],
    }

    # ------------------------------------------------------------------ games
    games = load("games.parquet")
    g = games[[c for c in COLUMNS["games.csv.gz"] if c in games.columns]].copy()
    g["gameday"] = pd.to_datetime(g["gameday"], errors="coerce").dt.strftime("%Y-%m-%d")
    write_csv_gz(g, os.path.join(DERIVED, "games.csv.gz"))
    settled = g.dropna(subset=["home_score", "away_score"])
    out["files"].append({
        "name": "games.csv.gz",
        "source_url": "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.parquet",
        "rows": int(len(g)),
        "season_min": int(g["season"].min()),
        "season_max": int(g["season"].max()),
        "raw_sha256": sha256(os.path.join(RAW, "games.parquet")),
    })
    out["data_as_of_gameday"] = str(pd.to_datetime(settled["gameday"]).max().date()) if len(settled) else None
    out["games_settled"] = int(len(settled))

    # ------------------------------------------------------------------ player week
    frames, seasons, missing = [], [], []
    for y in range(SEASON_MIN, 2027):
        name = f"stats_player_week_{y}.parquet"
        try:
            df = load(name)
        except FileNotFoundError:
            missing.append(y)
            continue
        frames.append(df[[c for c in COLUMNS["player_week.csv.gz"] if c in df.columns]])
        seasons.append(y)
    if frames:
        pw = pd.concat(frames, ignore_index=True)
        write_csv_gz(pw, os.path.join(DERIVED, "player_week.csv.gz"))
        out["files"].append({
            "name": "player_week.csv.gz",
            "source_url_pattern": ("https://github.com/nflverse/nflverse-data/releases/download/"
                                   "stats_player/stats_player_week_{year}.parquet"),
            "rows": int(len(pw)),
            "seasons": seasons,
            "missing_seasons": missing,
        })
        out["missing_player_seasons"] = missing

    # ------------------------------------------------------------------ team week
    frames, seasons = [], []
    for y in range(SEASON_MIN, 2027):
        name = f"stats_team_week_{y}.parquet"
        try:
            df = load(name)
        except FileNotFoundError:
            continue
        frames.append(df[[c for c in COLUMNS["team_week.csv.gz"] if c in df.columns]])
        seasons.append(y)
    if frames:
        tw = pd.concat(frames, ignore_index=True)
        write_csv_gz(tw, os.path.join(DERIVED, "team_week.csv.gz"))
        out["files"].append({
            "name": "team_week.csv.gz",
            "source_url_pattern": ("https://github.com/nflverse/nflverse-data/releases/download/"
                                   "stats_team/stats_team_week_{year}.parquet"),
            "rows": int(len(tw)),
            "seasons": seasons,
        })

    with open(os.path.join("data", "provenance.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    for f in out["files"]:
        print(f"{f['name']}: {f['rows']} rows")
    print(f"data_as_of_gameday={out['data_as_of_gameday']} games_settled={out['games_settled']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
