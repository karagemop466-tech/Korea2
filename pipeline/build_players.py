"""Build a compact player-game table from the nflscrapR games files.

Source: ryurko/nflscrapR-data ``legacy_data/game_player_stats`` (2009-2019), which is
derived from NFL play-by-play. Each upstream file is one row per player-game for one
stat family; here they are merged into a single wide player-game table and joined to
the game table (season/week/opponent/home-away) through ``old_game_id``.

Positions come from the nfldata roster file, matched on (season, team, name) - the
rosters use the same ``F.Lastname`` convention as the play-by-play name fields.

Output: data/interim/player_games.parquet
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from lib.common import INTERIM, read_csv

STAT_COLS = {
    "passing": {"Passer_ID": "player_id", "Attempts": "pass_att", "Completions": "pass_cmp",
                "Total_Yards": "pass_yds", "Interceptions": "pass_int", "TDs": "pass_td"},
    "rushing": {"Rusher_ID": "player_id", "Carries": "rush_att", "Total_Yards": "rush_yds",
                "TDs": "rush_td", "Fumbles": "rush_fum"},
    "receiving": {"Receiver_ID": "player_id", "Targets": "targets", "Receptions": "rec",
                  "Total_Yards": "rec_yds", "TDs": "rec_td", "Fumbles": "rec_fum"},
}


def load_family(family: str) -> pd.DataFrame:
    df = read_csv(f"scrapr_game_{family}.csv")
    keep = {"GameID": "old_game_id", "Player_Name": "player", "Team": "team",
            "Opponent": "opp", **STAT_COLS[family]}
    df = df[list(keep)].rename(columns=keep)
    df["player"] = df["player"].astype(str)
    return df


def main() -> None:
    games = pd.read_parquet(INTERIM / "games.parquet")
    games["old_game_id"] = games["old_game_id"].astype(str)
    gmap = games.set_index("old_game_id")[["game_id", "season", "week", "gameday", "home_team",
                                           "away_team", "spread_line", "total_line",
                                           "points_total", "margin"]]

    # Key on the upstream player id, never on the display name: nflscrapR's "F.Lastname"
    # strings collide (e.g. two different players shown as "C.Benson" in the same game).
    frames = {family: load_family(family) for family in ("passing", "rushing", "receiving")}
    for df in frames.values():
        df["old_game_id"] = df["old_game_id"].astype(str)

    names = (pd.concat([df[["player_id", "player"]] for df in frames.values()])
               .dropna(subset=["player_id"]).drop_duplicates("player_id"))

    merged = frames["passing"].drop(columns=["player"])
    for family in ("rushing", "receiving"):
        merged = merged.merge(frames[family].drop(columns=["player"]),
                              on=["old_game_id", "player_id", "team", "opp"], how="outer")

    merged = merged.merge(gmap, left_on="old_game_id", right_index=True, how="left")
    # a player can appear in several families (a QB who also rushed, a back who also caught)
    merged = merged.merge(names, on="player_id", how="left")
    merged = merged[merged["season"].notna()].copy()
    merged["season"] = merged["season"].astype(int)

    stat_cols = [c for c in merged.columns if c in
                 {v for d in STAT_COLS.values() for v in d.values()}]
    for c in stat_cols:
        if c == "player_id":
            continue          # identifiers are strings; coercing them would null them out
        merged[c] = pd.to_numeric(merged[c], errors="coerce").fillna(0.0)

    # touchdowns: any-time TD = any scoring touch (rush + rec). Passing TDs belong to the QB.
    merged["any_td"] = ((merged.get("rush_td", 0) + merged.get("rec_td", 0)) > 0).astype(int)

    # positions
    rosters = read_csv("nfldata_rosters.csv", usecols=["season", "team", "name", "category", "position", "playerid"])
    rosters = rosters.dropna(subset=["name"])
    rosters = rosters.sort_values("season").drop_duplicates(["season", "team", "name"], keep="last")
    merged = merged.merge(rosters.rename(columns={"name": "player", "category": "pos_group",
                                                  "position": "pos_detail", "playerid": "pfr_id"}),
                          on=["season", "team", "player"], how="left")

    merged["home"] = (merged["team"] == merged["home_team"]).astype(int)
    merged["team_pts"] = np.where(merged["home"] == 1, (merged["points_total"] + merged["margin"]) / 2,
                                  (merged["points_total"] - merged["margin"]) / 2)
    merged["opp_pts"] = merged["points_total"] - merged["team_pts"]

    out = merged[["game_id", "old_game_id", "season", "week", "gameday", "player", "team", "opp",
                  "pos_group", "pos_detail", "pfr_id", "home", "team_pts", "opp_pts", "points_total",
                  "spread_line", "total_line"] + stat_cols + ["any_td"]].copy()
    path = INTERIM / "player_games.parquet"
    out.to_parquet(path, index=False)

    print(f"wrote {path} rows={len(out):,}")
    print(f"seasons {int(out.season.min())}-{int(out.season.max())}, games {out.game_id.nunique():,}, players {out.player.nunique():,}")
    print("position coverage:", out["pos_group"].notna().mean().round(3))
    print("unique players by id:", out["player_id"].nunique(),
          "| duplicate (game, player_id):", int(out.duplicated(["game_id", "player_id"]).sum()))
    print(out.groupby("pos_group")["player"].nunique().sort_values(ascending=False).head(8).to_dict())


if __name__ == "__main__":
    main()
