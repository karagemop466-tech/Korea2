# DEPRECATED 2026-11-02 (session arena/652b0095-korea2): this is a SECOND producer of the
# three pruned extracts and it prunes to a different window (2015-2026) than
# scripts/export_extracts.py (2012-2026, the window the analysis reads). Running it replaced
# a 2012-2026 extract with a 2015-2026 one and broke reproducibility (commit f0d4b26).
# Both workflows now call scripts/export_extracts.py; do not call this file from CI.
"""Build pruned, analysis-ready datasets and a provenance manifest.

Raw downloads stay out of git (see .gitignore). Only the pruned extracts and
the manifest (URL, byte size, sha256, row count) are committed.
"""
from __future__ import annotations

import datetime as dt
import gzip
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


def write_csv_gz(df, path):
    """Deterministic gzip: fixed mtime and header, so an unchanged dataset
    produces an unchanged file. Without this every refresh commits a diff."""
    with open(path, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as gz:
            df.to_csv(gz, index=False)


def main():
    # Deterministic provenance: the "as of" marker is derived from the data, not
    # from the clock, so refreshing an unchanged dataset changes nothing.
    manifest = {"files": []}

    g = load_games()
    keep = [c for c in GAMES_COLS if c in g.columns]
    write_csv_gz(g[keep], DERIVED / "games.csv.gz")
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
        write_csv_gz(tw, DERIVED / "team_week.csv.gz")
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
        write_csv_gz(pw, DERIVED / "player_week.csv.gz")
        manifest["files"].append({"name": "player_week.csv.gz", "rows": int(len(pw)),
                                  "source_url_pattern": SOURCES["player_week"],
                                  "seasons": sorted(pw.season.unique().tolist())})
    manifest["missing_player_seasons"] = missing
    # data-defined as-of marker (deterministic)
    gd = g.copy()
    gd["gameday"] = pd.to_datetime(gd.get("gameday"), errors="coerce")
    settled = gd[pd.to_numeric(gd.get("result"), errors="coerce").notna()]
    manifest = {
        "data_as_of_gameday": str(settled.gameday.max().date()) if len(settled) else None,
        "games_settled": int(len(settled)),
        **manifest,
    }
    jdump(manifest, DERIVED.parent / "provenance.json")
    print("prepared:", manifest)


if __name__ == "__main__":
    main()
