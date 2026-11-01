"""Build the game-level modelling table.

Everything created here is *pre-game* information only:
  * Elo ratings and rolling team form use strictly prior games (shift-by-one),
  * rest, roof, weather and officials come straight from the upstream file,
  * market prices are carried unchanged and are only used as a benchmark / bet price,
    never as a modelling input for the origination model.

Output: data/interim/games.parquet
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from lib.common import INTERIM, read_csv

HFA_ELO = 65.0          # home-field advantage in Elo points (538 convention ~ 65)
K_ELO = 20.0
SEASON_REGRESSION = 1.0 / 3.0
ELO_MEAN = 1505.0


def load_games() -> pd.DataFrame:
    g = read_csv("nfldata_games.csv")
    g["gameday"] = pd.to_datetime(g["gameday"], errors="coerce")
    num = ["away_score", "home_score", "result", "total", "spread_line", "total_line",
           "away_moneyline", "home_moneyline", "away_spread_odds", "home_spread_odds",
           "over_odds", "under_odds", "away_rest", "home_rest", "temp", "wind", "div_game"]
    for c in num:
        g[c] = pd.to_numeric(g[c], errors="coerce")

    g = g.sort_values(["gameday", "gametime"], na_position="last").reset_index(drop=True)
    g["season"] = g["season"].astype(int)
    g["week"] = pd.to_numeric(g["week"], errors="coerce").astype("Int64")
    g["played"] = g["home_score"].notna() & g["away_score"].notna()
    # recompute result/total from scores so the derived fields cannot drift from the raw ones
    g["margin"] = g["home_score"] - g["away_score"]
    g["points_total"] = g["home_score"] + g["away_score"]
    g["home_win"] = (g["margin"] > 0).astype(float)
    g.loc[~g["played"], ["margin", "points_total", "home_win"]] = np.nan
    g["neutral"] = (g["location"] == "Neutral").astype(int)
    return g


def add_elo(g: pd.DataFrame) -> pd.DataFrame:
    """FiveThirtyEight-style Elo, updated only after each game is played."""
    elo: dict[str, float] = {}
    pre_home, pre_away, post_home, post_away = [], [], [], []
    last_season = None
    for row in g.itertuples(index=False):
        if last_season is not None and row.season != last_season:
            for t in list(elo):
                elo[t] = ELO_MEAN + (elo[t] - ELO_MEAN) * (1 - SEASON_REGRESSION)
        last_season = row.season
        eh = elo.get(row.home_team, ELO_MEAN)
        ea = elo.get(row.away_team, ELO_MEAN)
        pre_home.append(eh)
        pre_away.append(ea)
        if not row.played:
            post_home.append(eh)
            post_away.append(ea)
            continue
        hfa = 0.0 if row.neutral else HFA_ELO
        exp_h = 1.0 / (1.0 + 10 ** (-((eh + hfa) - ea) / 400.0))
        mov = abs(row.margin)
        winner_elo = eh + hfa if row.margin > 0 else ea
        loser_elo = ea if row.margin > 0 else eh + hfa
        mult = ((mov + 3.0) ** 0.8) / (7.5 + 0.006 * (winner_elo - loser_elo))
        # margin > 0 -> home won: home gains K*mult*(1-exp_h)
        # margin < 0 -> away won: home loses K*mult*(1-exp_away) = K*mult*exp_h
        if row.margin > 0:
            delta = K_ELO * mult * (1.0 - exp_h)
        elif row.margin < 0:
            delta = -K_ELO * mult * exp_h
        else:
            delta = 0.0
        elo[row.home_team] = eh + delta
        elo[row.away_team] = ea - delta
        post_home.append(elo[row.home_team])
        post_away.append(elo[row.away_team])
    g["elo_home_pre"] = pre_home
    g["elo_away_pre"] = pre_away
    g["elo_home_post"] = post_home
    g["elo_away_post"] = post_away
    g["elo_diff"] = g["elo_home_pre"] - g["elo_away_pre"]
    return g


def add_rolling_form(g: pd.DataFrame) -> pd.DataFrame:
    """Per-team rolling form from prior games only (shift(1) everywhere)."""
    rows = []
    for side in ("home", "away"):
        other = "away" if side == "home" else "home"
        sub = pd.DataFrame({
            "game_id": g["game_id"],
            "gameday": g["gameday"],
            "season": g["season"],
            "team": g[f"{side}_team"],
            "opp": g[f"{other}_team"],
            "pf": g[f"{side}_score"],
            "pa": g[f"{other}_score"],
            "win": (g["margin"] > 0).astype(float) if side == "home" else (g["margin"] < 0).astype(float),
            "is_home": side == "home",
        })
        sub.loc[~g["played"].values, ["win"]] = np.nan
        rows.append(sub)
    long = pd.concat(rows).sort_values(["team", "gameday"]).reset_index(drop=True)

    grp = long.groupby("team", group_keys=False)
    for col, src in (("pf_ewm", "pf"), ("pa_ewm", "pa")):
        long[col] = grp[src].apply(lambda s: s.shift(1).ewm(halflife=6, min_periods=1).mean())
    long["win_pct_l10"] = grp["win"].apply(lambda s: s.shift(1).rolling(10, min_periods=3).mean())
    long["pf_l5"] = grp["pf"].apply(lambda s: s.shift(1).rolling(5, min_periods=2).mean())
    long["pa_l5"] = grp["pa"].apply(lambda s: s.shift(1).rolling(5, min_periods=2).mean())
    long["games_played_before"] = grp.cumcount()
    long["last_gameday"] = grp["gameday"].apply(lambda s: s.shift(1))

    feat_cols = ["pf_ewm", "pa_ewm", "win_pct_l10", "pf_l5", "pa_l5",
                 "games_played_before", "last_gameday"]
    merged = g.merge(
        long[["game_id", "team"] + feat_cols].rename(columns={"team": "home_team"}),
        on=["game_id", "home_team"], how="left")
    merged = merged.merge(
        long[["game_id", "team"] + feat_cols].rename(
            columns={"team": "away_team", **{c: c.replace("_", "_away_") if c.startswith(("pf", "pa", "win", "games")) else c for c in feat_cols}}),
        on=["game_id", "away_team"], how="left")
    return merged


def add_situational(g: pd.DataFrame) -> pd.DataFrame:
    g["rest_diff"] = g["home_rest"] - g["away_rest"]
    g["short_week_home"] = (g["home_rest"] <= 5).astype(int)
    g["short_week_away"] = (g["away_rest"] <= 5).astype(int)
    g["off_bye_home"] = (g["home_rest"] >= 13).astype(int)
    g["off_bye_away"] = (g["away_rest"] >= 13).astype(int)
    g["is_dome"] = g["roof"].isin(["dome", "closed"]).astype(int)
    g["is_thursday"] = (g["weekday"] == "Thursday").astype(int)
    g["wind_bin"] = pd.cut(g["wind"], [-0.01, 9.99, 14.99, 100],
                           labels=["calm", "breezy", "windy"]).astype(str)
    g["temp_bin"] = pd.cut(g["temp"], [-100, 32, 45, 100],
                           labels=["freezing", "cold", "mild"]).astype(str)
    g.loc[g["wind"].isna(), "wind_bin"] = "unknown"
    g.loc[g["temp"].isna(), "temp_bin"] = "unknown"
    return g


def add_market_derived(g: pd.DataFrame) -> pd.DataFrame:
    """Market-implied quantities, used only as benchmarks and bet prices."""
    from lib.common import american_to_decimal, american_to_prob, devig_two_way

    hp = g["home_moneyline"].map(american_to_prob)
    ap = g["away_moneyline"].map(american_to_prob)
    fair_home = []
    for a, b in zip(hp, ap):
        if np.isnan(a) or np.isnan(b):
            fair_home.append(np.nan)
        else:
            fair_home.append(devig_two_way(a, b)[0])
    g["mkt_home_win_prob"] = fair_home
    g["home_ml_dec"] = g["home_moneyline"].map(american_to_decimal)
    g["away_ml_dec"] = g["away_moneyline"].map(american_to_decimal)
    g["home_spread_dec"] = g["home_spread_odds"].map(american_to_decimal)
    g["away_spread_dec"] = g["away_spread_odds"].map(american_to_decimal)
    g["over_dec"] = g["over_odds"].map(american_to_decimal)
    g["under_dec"] = g["under_odds"].map(american_to_decimal)
    # expected total implied by the market is the total line itself; keep a copy
    g["mkt_total"] = g["total_line"]
    g["mkt_spread"] = g["spread_line"]
    return g


def main() -> None:
    g = load_games()
    g = add_elo(g)
    g = add_rolling_form(g)
    g = add_situational(g)
    g = add_market_derived(g)

    cols = [c for c in g.columns if c not in ("gsis", "nfl_detail_id", "pff", "ftn")]
    out = g[cols].copy()
    path = INTERIM / "games.parquet"
    out.to_parquet(path, index=False)
    print(f"wrote {path}  rows={len(out):,}  cols={out.shape[1]}")
    played = out[out["played"]]
    print(f"played games: {len(played):,}  seasons {int(played.season.min())}-{int(played.season.max())}")
    print(f"games with closing spread+total: {played[['spread_line','total_line']].notna().all(axis=1).sum():,}")
    print(f"games with priced spread: {played[['away_spread_odds','home_spread_odds']].notna().all(axis=1).sum():,}")


if __name__ == "__main__":
    main()
