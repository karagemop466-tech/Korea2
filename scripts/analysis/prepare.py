"""Build pruned, analysis-ready datasets and a provenance manifest.

Raw downloads stay out of git (see .gitignore). Only the pruned extracts and
the manifest (URL, byte size, sha256, row count) are committed.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

from common import DERIVED, RAW, SOURCES, jdump, load_games, sha256

DERIVED.mkdir(parents=True, exist_ok=True)

GAMES_COLS = [
    "game_id", "season", "game_type", "week", "gameday", "weekday", "gametime",
    "away_team", "away_score", "home_team", "home_score", "location", "result",
    "total", "overtime", "away_rest", "home_rest", "away_moneyline",
    "home_moneyline", "spread_line", "away_spread_odds", "home_spread_odds",
    "total_line", "under_odds", "over_odds", "div_game", "roof", "surface",
    "temp", "wind", "away_qb_name", "home_qb_name", "stadium", "referee",
]

TEAM_COLS = [
    "season", "week", "team", "season_type", "game_id", "opponent_team",
    "attempts", "passing_yards", "passing_tds", "passing_interceptions",
    "sacks_suffered", "passing_air_yards", "passing_epa", "passing_cpoe",
    "carries", "rushing_yards", "rushing_tds", "rushing_epa",
    "receptions", "targets", "receiving_yards", "receiving_epa",
    "def_sacks", "def_interceptions", "def_tackles_for_loss",
    "fg_made", "fg_att", "punt_returns", "penalties", "penalty_yards",
    "fumbles_lost_total", "timeouts",
]

PLAYER_COLS = [
    "player_id", "player_display_name", "position", "position_group", "season",
    "week", "season_type", "team", "opponent_team",
    "completions", "attempts", "passing_yards", "passing_tds",
    "passing_interceptions", "passing_epa", "passing_cpoe", "sacks_suffered",
    "carries", "rushing_yards", "rushing_tds", "rushing_epa",
    "receptions", "targets", "receiving_yards", "receiving_tds",
    "receiving_air_yards", "receiving_epa", "target_share", "air_yards_share",
    "wopr", "racr",
]


def main():
    manifest = {"generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "files": []}

    g = load_games()
    keep = [c for c in GAMES_COLS if c in g.columns]
    g[keep].to_csv(DERIVED / "games.csv.gz", index=False, compression="gzip")
    manifest["files"].append({
        "name": "games.csv.gz", "source_url": SOURCES["games"],
        "rows": int(len(g)), "season_min": int(g.season.min()), "season_max": int(g.season.max()),
        "raw_sha256": sha256(RAW / "games.csv") if (RAW / "games.csv").exists() else None,
    })

    tw = []
    for y in range(2015, 2027):
        p = RAW / f"stats_team_week_{y}.csv"
        if p.exists():
            df = pd.read_csv(p, low_memory=False)
            tw.append(df[[c for c in TEAM_COLS if c in df.columns]])
    if tw:
        tw = pd.concat(tw, ignore_index=True)
        tw.to_csv(DERIVED / "team_week.csv.gz", index=False, compression="gzip")
        manifest["files"].append({"name": "team_week.csv.gz", "rows": int(len(tw)),
                                  "source_url_pattern": SOURCES["team_week"],
                                  "seasons": sorted(tw.season.unique().tolist())})

    pw, missing = [], []
    for y in range(2015, 2027):
        p = RAW / f"stats_player_week_{y}.csv"
        ok = False
        if p.exists():
            try:
                df = pd.read_csv(p, low_memory=False)
                if len(df):
                    pw.append(df[[c for c in PLAYER_COLS if c in df.columns]])
                    ok = True
            except Exception:
                ok = False
        if not ok:
            missing.append(y)
    if pw:
        pw = pd.concat(pw, ignore_index=True)
        pw.to_csv(DERIVED / "player_week.csv.gz", index=False, compression="gzip")
        manifest["files"].append({"name": "player_week.csv.gz", "rows": int(len(pw)),
                                  "source_url_pattern": SOURCES["player_week"],
                                  "seasons": sorted(pw.season.unique().tolist())})
    manifest["missing_player_seasons"] = missing
    jdump(manifest, DERIVED.parent / "provenance.json")
    print("prepared:", manifest)


if __name__ == "__main__":
    main()
