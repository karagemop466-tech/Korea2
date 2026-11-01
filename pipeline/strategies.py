"""Generate betting strategies and their tickets.

A *strategy* is a pure function of pre-game information that returns at most one side
per game for a given market. Every strategy is turned into tickets with:

  * the closing price from the upstream file (the evaluation price),
  * a unit stake,
  * a settlement computed from the final score,
  * a flag telling whether the ticket is in the development window (used only for
    threshold selection) or the held-out evaluation window (used for every published
    number).

Development window : 2010-2014 (first seasons with priced spreads/totals/moneylines)
Evaluation window  : 2015-2026

``CTRL_LEAK`` is an intentional control that uses post-game information. It exists to
prove the lookahead gate actually fires.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from lib.common import INTERIM, american_to_decimal, american_to_prob, devig_two_way, write_json

DEV_START, DEV_END = 2010, 2014
EVAL_START = 2015


# ------------------------------------------------------------------ plumbing
def _settle_spread(margin: float, line: float, side: str) -> str:
    """side in {'home','away'} ; line is the home spread (positive = home favoured)."""
    if np.isnan(margin) or np.isnan(line):
        return "void"
    x = margin - line
    if abs(x) < 1e-9:
        return "push"
    if side == "home":
        return "win" if x > 0 else "loss"
    return "win" if x < 0 else "loss"


def _settle_total(total: float, line: float, side: str) -> str:
    if np.isnan(total) or np.isnan(line):
        return "void"
    x = total - line
    if abs(x) < 1e-9:
        return "push"
    if side == "over":
        return "win" if x > 0 else "loss"
    return "win" if x < 0 else "loss"


def _settle_ml(margin: float, side: str) -> str:
    if np.isnan(margin):
        return "void"
    if margin == 0:
        return "push"
    if side == "home":
        return "win" if margin > 0 else "loss"
    return "win" if margin < 0 else "loss"


def pnl(result: str, odds_american: float) -> float:
    if result == "win":
        return american_to_decimal(odds_american) - 1.0
    if result == "loss":
        return -1.0
    return 0.0


def make_spread_bets(g: pd.DataFrame, side_series: pd.Series, strategy: str,
                     reason: pd.Series | None = None) -> pd.DataFrame:
    """side_series: 'home'/'away'/NaN per game."""
    d = g.loc[side_series.notna(), ["game_id", "season", "week", "gameday", "home_team", "away_team",
                                    "spread_line", "home_spread_odds", "away_spread_odds",
                                    "margin", "played"]].copy()
    d["side"] = side_series.dropna()
    d["market"] = "SPREAD"
    d["line"] = d["spread_line"]
    d["odds"] = np.where(d["side"] == "home", d["home_spread_odds"], d["away_spread_odds"])
    d["result"] = [_settle_spread(m, l, s) for m, l, s in zip(d["margin"], d["line"], d["side"])]
    d["team"] = np.where(d["side"] == "home", d["home_team"], d["away_team"])
    d["opp"] = np.where(d["side"] == "home", d["away_team"], d["home_team"])
    d["strategy"] = strategy
    return d


def make_total_bets(g: pd.DataFrame, side_series: pd.Series, strategy: str) -> pd.DataFrame:
    d = g.loc[side_series.notna(), ["game_id", "season", "week", "gameday", "home_team", "away_team",
                                    "total_line", "over_odds", "under_odds", "points_total",
                                    "margin", "played"]].copy()
    d["side"] = side_series.dropna()
    d["market"] = "TOTAL"
    d["line"] = d["total_line"]
    d["odds"] = np.where(d["side"] == "over", d["over_odds"], d["under_odds"])
    d["result"] = [_settle_total(t, l, s) for t, l, s in zip(d["points_total"], d["line"], d["side"])]
    d["team"] = "OVER_UNDER"
    d["opp"] = "OVER_UNDER"
    d["strategy"] = strategy
    return d


def make_ml_bets(g: pd.DataFrame, side_series: pd.Series, strategy: str) -> pd.DataFrame:
    d = g.loc[side_series.notna(), ["game_id", "season", "week", "gameday", "home_team", "away_team",
                                    "home_moneyline", "away_moneyline", "margin", "played"]].copy()
    d["side"] = side_series.dropna()
    d["market"] = "MONEYLINE"
    d["line"] = np.nan
    d["odds"] = np.where(d["side"] == "home", d["home_moneyline"], d["away_moneyline"])
    d["result"] = [_settle_ml(m, s) for m, s in zip(d["margin"], d["side"])]
    d["team"] = np.where(d["side"] == "home", d["home_team"], d["away_team"])
    d["opp"] = np.where(d["side"] == "home", d["away_team"], d["home_team"])
    d["strategy"] = strategy
    return d


def finalize(bets: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    """Attach prices, fair probabilities, P&L and the dev/eval flag."""
    bets = bets[bets["played"]].copy()
    bets = bets[bets["odds"].notna() & (bets["odds"] != 0)]
    bets = bets[bets["result"].isin(["win", "loss", "push"])]
    bets["pnl"] = [pnl(r, o) for r, o in zip(bets["result"], bets["odds"])]
    bets["dec_odds"] = bets["odds"].map(american_to_decimal)
    # de-vigged fair probability of the side we took
    fair = []
    for r, s in zip(bets.itertuples(index=False), bets["side"]):
        pass
    fair = []
    for row in bets.itertuples(index=False):
        if row.market == "SPREAD":
            a = american_to_prob(row.home_spread_odds)
            b = american_to_prob(row.away_spread_odds)
            if np.isnan(a) or np.isnan(b):
                fair.append(np.nan)
            else:
                ph, _ = devig_two_way(a, b)
                fair.append(ph if row.side == "home" else 1 - ph)
        elif row.market == "TOTAL":
            a = american_to_prob(row.over_odds)
            b = american_to_prob(row.under_odds)
            if np.isnan(a) or np.isnan(b):
                fair.append(np.nan)
            else:
                po, _ = devig_two_way(a, b)
                fair.append(po if row.side == "over" else 1 - po)
        else:
            a = american_to_prob(row.home_moneyline)
            b = american_to_prob(row.away_moneyline)
            if np.isnan(a) or np.isnan(b):
                fair.append(np.nan)
            else:
                ph, _ = devig_two_way(a, b)
                fair.append(ph if row.side == "home" else 1 - ph)
    bets["fair_prob"] = fair
    bets["window"] = np.where(bets["season"] <= DEV_END, "dev", "eval")
    # market-implied expected value with no edge: fair_prob*dec - 1 (should be negative: the vig)
    bets["ev_fair"] = bets["fair_prob"] * bets["dec_odds"] - 1
    return bets.reset_index(drop=True)


# ---------------------------------------------------------------- strategies
def build_strategies(g: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    meta: list[dict] = []
    frames: list[pd.DataFrame] = []
    empty = pd.Series(np.nan, index=g.index)

    # ---------------- engine driven (model vs market)
    for eng, label in (("own", "Ridge attack/defence engine"),
                       ("elo_engine", "Elo engine")):
        mcol = f"{eng}_margin"
        for thr in (1.0, 2.0, 3.0):
            diff = g[mcol] - g["spread_line"]
            side = pd.Series(np.nan, index=g.index, dtype=object)
            side[diff >= thr] = "home"
            side[diff <= -thr] = "away"
            name = f"ATS_{eng.upper()}_{int(thr)}"
            frames.append(make_spread_bets(g, side, name))
            meta.append({"strategy": name, "family": "Model vs market (spread)",
                         "engine": eng, "threshold_pts": thr,
                         "rule": f"Back the side the {label} likes by >= {thr:g} pts versus the close."})
        tdiff = g[f"{eng}_total"] - g["total_line"]
        for thr in (2.0, 3.0):
            side = pd.Series(np.nan, index=g.index, dtype=object)
            side[tdiff >= thr] = "over"
            side[tdiff <= -thr] = "under"
            name = f"TOT_{eng.upper()}_{int(thr)}"
            frames.append(make_total_bets(g, side, name))
            meta.append({"strategy": name, "family": "Model vs market (total)",
                         "engine": eng, "threshold_pts": thr,
                         "rule": f"Over/under the {label} total when it differs from the close by >= {thr:g} pts."})

    # moneyline from model probability vs de-vigged market probability
    gap = g["own_home_wp"] - g["mkt_home_win_prob"]
    for thr in (0.03, 0.05):
        side = pd.Series(np.nan, index=g.index, dtype=object)
        side[gap >= thr] = "home"
        side[gap <= -thr] = "away"
        name = f"ML_OWN_{int(thr*100)}"
        frames.append(make_ml_bets(g, side, name))
        meta.append({"strategy": name, "family": "Model vs market (moneyline)",
                     "engine": "own", "threshold_prob": thr,
                     "rule": f"Moneyline where our win probability exceeds the de-vigged market by >= {thr:.0%}."})

    # ML underdog / favourite value from the same gap but restricted
    dog_home = g["spread_line"] < 0
    dog_side = pd.Series(np.nan, index=g.index, dtype=object)
    dog_side[(gap >= 0.03) & dog_home] = "home"
    dog_side[(gap <= -0.03) & (~dog_home)] = "away"
    frames.append(make_ml_bets(g, dog_side, "ML_OWN_DOG"))
    meta.append({"strategy": "ML_OWN_DOG", "family": "Model vs market (moneyline)",
                 "rule": "Underdog moneylines where our probability beats the de-vigged market by >= 3 pts."})

    # ---------------- situational
    home_dog = g["spread_line"] < 0
    s = pd.Series(np.nan, index=g.index, dtype=object)
    s[home_dog] = "home"
    frames.append(make_spread_bets(g, s, "SIT_HOME_DOG"))
    meta.append({"strategy": "SIT_HOME_DOG", "family": "Situational (spread)",
                 "rule": "Back every home underdog against the spread."})

    s = pd.Series(np.nan, index=g.index, dtype=object)
    s[(g["div_game"] == 1) & (g["spread_line"] < 0)] = "home"
    s[(g["div_game"] == 1) & (g["spread_line"] > 0)] = "away"
    frames.append(make_spread_bets(g, s, "SIT_DIV_DOG"))
    meta.append({"strategy": "SIT_DIV_DOG", "family": "Situational (spread)",
                 "rule": "Back the underdog in divisional games against the spread."})

    s = pd.Series(np.nan, index=g.index, dtype=object)
    s[g["rest_diff"] >= 3] = "home"
    s[g["rest_diff"] <= -3] = "away"
    frames.append(make_spread_bets(g, s, "SIT_REST_EDGE"))
    meta.append({"strategy": "SIT_REST_EDGE", "family": "Situational (spread)",
                 "rule": "Back the team with >= 3 more days of rest against the spread."})

    # NOTE: a "fade the short-week team" rule was tested first and dropped, because in this
    # data the two teams almost always share the same short week (318 of 324 cases), which
    # leaves 12 games - a degenerate rule, not a strategy. Replaced by the bye-week fade below.
    s = pd.Series(np.nan, index=g.index, dtype=object)
    s[(g["off_bye_home"] == 1) & (g["spread_line"] > 0)] = "away"
    s[(g["off_bye_away"] == 1) & (g["spread_line"] < 0)] = "home"
    frames.append(make_spread_bets(g, s, "SIT_BYE_FAV_FADE"))
    meta.append({"strategy": "SIT_BYE_FAV_FADE", "family": "Situational (spread)",
                 "rule": "Fade a team that is favoured in its first game back from a bye."})

    s = pd.Series(np.nan, index=g.index, dtype=object)
    s[g["div_game"] == 1] = "under"
    frames.append(make_total_bets(g, s, "SIT_DIV_UNDER"))
    meta.append({"strategy": "SIT_DIV_UNDER", "family": "Situational (total)",
                 "rule": "Under in divisional games."})

    s = pd.Series(np.nan, index=g.index, dtype=object)
    s[g["off_bye_home"] == 1] = "home"
    s[g["off_bye_away"] == 1] = "away"
    byes = s.copy()
    byes[(g["off_bye_home"] == 1) & (g["off_bye_away"] == 1)] = np.nan
    frames.append(make_spread_bets(g, byes, "SIT_OFF_BYE"))
    meta.append({"strategy": "SIT_OFF_BYE", "family": "Situational (spread)",
                 "rule": "Back a team playing its first game after a bye against the spread."})

    s = pd.Series(np.nan, index=g.index, dtype=object)
    s[g["wind"] >= 15] = "under"
    frames.append(make_total_bets(g, s, "SIT_WINDY_UNDER"))
    meta.append({"strategy": "SIT_WINDY_UNDER", "family": "Situational (total)",
                 "rule": "Under when the reported wind is >= 15 mph."})

    s = pd.Series(np.nan, index=g.index, dtype=object)
    s[g["temp"] <= 32] = "under"
    frames.append(make_total_bets(g, s, "SIT_FREEZE_UNDER"))
    meta.append({"strategy": "SIT_FREEZE_UNDER", "family": "Situational (total)",
                 "rule": "Under when the reported temperature is <= 32 F."})

    s = pd.Series(np.nan, index=g.index, dtype=object)
    s[g["is_dome"] == 1] = "over"
    frames.append(make_total_bets(g, s, "SIT_DOME_OVER"))
    meta.append({"strategy": "SIT_DOME_OVER", "family": "Situational (total)",
                 "rule": "Over in domes and closed roofs."})

    s = pd.Series(np.nan, index=g.index, dtype=object)
    s[g["is_thursday"] == 1] = "under"
    frames.append(make_total_bets(g, s, "SIT_TNF_UNDER"))
    meta.append({"strategy": "SIT_TNF_UNDER", "family": "Situational (total)",
                 "rule": "Under in Thursday games."})

    # ---------------- opening-line value (single season, deliberately kept and flagged)
    try:
        from lib.common import read_csv
        il = read_csv("nfldata_initial_lines.csv")
    except FileNotFoundError:
        il = None
    if il is not None and len(il):
        il = il[il["type"] == "SPREAD"].copy()
        home_of = g.set_index("game_id")[["home_team", "away_team", "spread_line"]]
        il = il.join(home_of, on="about")
        il = il.dropna(subset=["home_team"])
        # upstream lists the handicap of the named side: negative = that side is favoured.
        # convert to the home-perspective spread used by nfldata (positive = home favoured)
        il["home_open"] = np.where(il["side"] == il["home_team"], -il["line"], il["line"])
        open_spread = il.groupby("about")["home_open"].first()
        idx = g.set_index("game_id")
        op = idx.index.map(open_spread)
        edge_open = idx["own_margin"].to_numpy() - np.asarray(op, dtype=float)
        side = pd.Series(np.nan, index=g.index, dtype=object)
        side[edge_open >= 2] = "home"
        side[edge_open <= -2] = "away"
        frames.append(make_spread_bets(g, side, "OPEN_EDGE_2"))
        meta.append({"strategy": "OPEN_EDGE_2", "family": "Opening-line value (sample limited)",
                     "rule": "Back the side where our own line beats the *opening* line by >= 2 pts (opening lines exist for 2021 only).",
                     "sample_limited": True})

    # ---------------- benchmarks (must be rejected by the gates)
    s = pd.Series("home", index=g.index, dtype=object)
    frames.append(make_spread_bets(g, s, "CTRL_ALL_HOME"))
    meta.append({"strategy": "CTRL_ALL_HOME", "family": "Control",
                 "rule": "Back the home team against the spread in every game (vig benchmark)."})

    s = pd.Series("over", index=g.index, dtype=object)
    frames.append(make_total_bets(g, s, "CTRL_ALL_OVER"))
    meta.append({"strategy": "CTRL_ALL_OVER", "family": "Control",
                 "rule": "Bet the over in every game (vig benchmark)."})

    # intentional lookahead control: uses the final score
    s = pd.Series(np.nan, index=g.index, dtype=object)
    s[g["margin"] > g["spread_line"]] = "home"
    s[g["margin"] < g["spread_line"]] = "away"
    frames.append(make_spread_bets(g, s, "CTRL_LEAK"))
    meta.append({"strategy": "CTRL_LEAK", "family": "Control",
                 "rule": "Back the side that covered, chosen after the game (deliberate lookahead; must be rejected)."})

    bets = pd.concat([f for f in frames if len(f)], ignore_index=True)
    bets = finalize(bets, g)
    return bets, meta


# ------------------------------------------------------------------ parlays
def build_parlays(bets: pd.DataFrame, g: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Parlays built from single-bet tickets, priced multiplicatively."""
    meta: list[dict] = []
    out = []

    def combine(legs: pd.DataFrame, name: str, n_legs: int, family: str, rule: str,
                corr_note: str):
        if legs.empty:
            return
        legs = legs.sort_values(["season", "week", "edge"], ascending=[True, True, False])
        picked = legs.groupby(["season", "week"], group_keys=False).head(n_legs)
        counts = picked.groupby(["season", "week"]).size()
        keep = set(counts[counts == n_legs].index)
        picked = picked[[(s, w) in keep for s, w in zip(picked["season"], picked["week"])]]
        for (season, week), grp in picked.groupby(["season", "week"]):
            won = bool((grp["result"] == "win").all())
            push = bool((grp["result"] == "push").any())
            dec = float(np.prod(grp["dec_odds"].to_numpy()))
            out.append({
                "strategy": name, "season": season, "week": week, "market": "PARLAY",
                "game_id": "+".join(grp["game_id"]), "team": " / ".join(grp["team"]),
                "side": ";".join(grp["side"]), "line": np.nan,
                "odds": None, "dec_odds": dec,
                "result": "push" if push else ("win" if won else "loss"),
                "pnl": 0.0 if push else (dec - 1.0 if won else -1.0),
                "n_legs": n_legs,
                "fair_prob": float(np.prod(grp["fair_prob"].to_numpy())),
                "window": "dev" if season <= DEV_END else "eval",
            })
        meta.append({"strategy": name, "family": family, "rule": rule, "n_legs": n_legs,
                     "correlation_note": corr_note})

    # model edge straight from the games table (|own line - close|)
    eng = g[["game_id", "own_margin", "spread_line"]].copy()
    eng["edge"] = (eng["own_margin"] - eng["spread_line"]).abs()
    sp = bets[bets["strategy"] == "ATS_OWN_1"].merge(eng[["game_id", "edge"]], on="game_id", how="left")
    combine(sp, "PARLAY2_ATS", 2, "Parlay",
            "Each week, the two largest model-vs-close ATS disagreements, combined in a 2-leg parlay at closing prices.",
            "Cross-game legs; independence is a close approximation (see correlation page).")
    combine(sp, "PARLAY3_ATS", 3, "Parlay",
            "Each week, the three largest model-vs-close ATS disagreements, combined in a 3-leg parlay.",
            "Cross-game legs; independence is a close approximation.")

    ml = bets[bets["strategy"] == "ML_OWN_DOG"].merge(eng[["game_id", "edge"]], on="game_id", how="left")
    combine(ml, "PARLAY2_ML_DOG", 2, "Parlay",
            "Each week, the two largest model-vs-market underdog moneyline edges, combined in a 2-leg parlay.",
            "Cross-game legs.")

    # same-game parlay: spread + total from the same game
    s_leg = bets[(bets["strategy"] == "ATS_OWN_1") & (bets["market"] == "SPREAD")]
    t_leg = bets[(bets["strategy"] == "TOT_OWN_2") & (bets["market"] == "TOTAL")]
    sgp = s_leg.merge(t_leg, on="game_id", suffixes=("_s", "_t"))
    rows = []
    for row in sgp.itertuples(index=False):
        won = row.result_s == "win" and row.result_t == "win"
        push = "push" in (row.result_s, row.result_t)
        dec = row.dec_odds_s * row.dec_odds_t
        rows.append({"strategy": "PARLAY_SGP_ATS_TOT", "season": row.season_s, "week": row.week_s,
                     "market": "SGP", "game_id": row.game_id, "team": f"{row.team_s} + {row.team_t}",
                     "side": f"{row.side_s};{row.side_t}", "line": np.nan, "odds": None,
                     "dec_odds": dec, "result": "push" if push else ("win" if won else "loss"),
                     "pnl": 0.0 if push else (dec - 1.0 if won else -1.0), "n_legs": 2,
                     "fair_prob": row.fair_prob_s * row.fair_prob_t,
                     "window": "dev" if row.season_s <= DEV_END else "eval"})
    if rows:
        out.extend(rows)
    meta.append({"strategy": "PARLAY_SGP_ATS_TOT", "family": "Parlay (same game)",
                 "rule": "Same-game parlay: the model's ATS side and the model's total side of the same game.",
                 "n_legs": 2,
                 "correlation_note": "Legs are correlated (see correlation page); priced here at the product of the legs, which is what an independent-pricing book would quote."})

    p = pd.DataFrame(out)
    if p.empty:
        return p, meta
    p = p[p["result"].isin(["win", "loss", "push"])]
    return p.reset_index(drop=True), meta


def main() -> None:
    g = pd.read_parquet(INTERIM / "lines.parquet")
    bets, meta = build_strategies(g)
    parlays, pmeta = build_parlays(bets, g)
    allbets = pd.concat([bets, parlays], ignore_index=True) if len(parlays) else bets
    allbets.to_parquet(INTERIM / "bets.parquet", index=False)
    write_json("strategy_registry.json", {"single": meta, "parlay": pmeta,
                                          "dev_window": [DEV_START, DEV_END],
                                          "eval_window": [EVAL_START, int(g.season.max())]})
    print(f"strategies: {allbets['strategy'].nunique()}   tickets: {len(allbets):,}")
    summ = (allbets[allbets["window"] == "eval"].groupby("strategy")
            .agg(n=("pnl", "size"), roi=("pnl", lambda s: s.sum() / max(1, (s != 0).sum()))))
    print(summ.sort_values("n", ascending=False).to_string())


if __name__ == "__main__":
    main()
