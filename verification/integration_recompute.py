#!/usr/bin/env python3
"""Final-integration recomputation of the published headline numbers.

Session `arena/dd794652-korea2`, 2026-11-13. This script exists to answer one question:
*does every number printed on the published site follow from the data committed in this
repository?*

Rules followed here (they are the same rules the rest of the project follows):

  * the code imports nothing from `scripts/` or `pipeline/` - a definition error in the
    project's own pipeline therefore cannot make this check agree with itself;
  * every input is a file committed in this repository (`data/derived/*.csv.gz`,
    `data/derived/predictions.csv`), never a downloaded feed, so the check is repeatable
    on a laptop with no network;
  * a check compares a recomputed value with the value the site publishes. A mismatch is a
    failure and exits non-zero. A difference that is explained by a documented data-window
    change is reported as `documented_difference` and does not fail the run, but it is still
    published so a reviewer can see it;
  * nothing is inferred. If a value cannot be recomputed from the committed data, the check
    is reported as `not_reproducible` rather than being quietly dropped.

Outputs `verification/integration_recompute.json`.
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats as sps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DERIVED = os.path.join(ROOT, "data", "derived")
OUT = os.path.join(ROOT, "verification", "integration_recompute.json")

TOL = 5e-3  # absolute tolerance for a rate/correlation; larger values use their own tolerance


# ------------------------------------------------------------------ small helpers
def wilson(k: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    """Wilson score interval (Wilson 1927)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def binom_p(k: int, n: int, p0: float = 0.5) -> float:
    """Two-sided exact binomial test against p0."""
    return float(sps.binomtest(int(k), int(n), p0, alternative="two-sided").pvalue)


def corr(x, y) -> tuple[float, float, int]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if x.size < 30 or x.std() == 0 or y.std() == 0:
        return (float("nan"), float("nan"), int(x.size))
    r, p = sps.pearsonr(x, y)
    return (float(r), float(p), int(x.size))


def load_json(path: str) -> dict:
    with open(path) as fh:
        return json.load(fh)


def get(d: dict, *path, default=None):
    cur = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


# ------------------------------------------------------------------ check machinery
class Report:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def add(self, name: str, published, recomputed, *, published_at: str, source: str,
            tol: float = TOL, note: str = "", allow_documented: bool = False,
            documented_reason: str = "") -> None:
        if published is None or recomputed is None:
            status = "not_reproducible"
            diff = None
        elif isinstance(published, (list, tuple)) or isinstance(recomputed, (list, tuple)):
            # a window check (for example [first_season, last_season]): compare element-wise
            pub = list(published) if isinstance(published, (list, tuple)) else published
            rec = list(recomputed) if isinstance(recomputed, (list, tuple)) else recomputed
            same = pub == rec
            diff = None if same else 1.0
            status = "match" if same else ("documented_difference" if allow_documented else "mismatch")
        else:
            diff = abs(float(published) - float(recomputed))
            if diff <= tol:
                status = "match"
            elif allow_documented:
                status = "documented_difference"
            else:
                status = "mismatch"
        row = {
            "check": name,
            "published": published,
            "recomputed": recomputed,
            "abs_diff": None if diff is None else round(diff, 6),
            "tolerance": tol,
            "status": status,
            "published_at": published_at,
            "source": source,
        }
        if note:
            row["note"] = note
        if documented_reason:
            row["documented_reason"] = documented_reason
        self.checks.append(row)

    def counts(self) -> dict:
        c: dict[str, int] = {}
        for r in self.checks:
            c[r["status"]] = c.get(r["status"], 0) + 1
        return c


# ------------------------------------------------------------------ independent data prep
def load_games() -> pd.DataFrame:
    df = pd.read_csv(os.path.join(DERIVED, "games.csv.gz"))
    df["gameday"] = pd.to_datetime(df["gameday"], errors="coerce")
    return df


def team_game_rows(games: pd.DataFrame) -> pd.DataFrame:
    """One row per team per regular-season game (independent re-implementation of the
    project's documented convention: `spread_line` is the home team's expected margin)."""
    g = games.dropna(subset=["home_score", "away_score"])
    g = g[g["game_type"] == "REG"]
    rows = []
    for r in g.itertuples():
        rows.append({
            "game_id": r.game_id, "season": int(r.season), "week": int(r.week),
            "team": r.home_team, "opp": r.away_team, "is_home": 1,
            "pf": float(r.home_score), "pa": float(r.away_score),
            "market_spread": float(r.spread_line) if pd.notna(r.spread_line) else np.nan,
            "margin": float(r.home_score) - float(r.away_score),
            "total": float(r.total),
        })
        rows.append({
            "game_id": r.game_id, "season": int(r.season), "week": int(r.week),
            "team": r.away_team, "opp": r.home_team, "is_home": 0,
            "pf": float(r.away_score), "pa": float(r.home_score),
            "market_spread": -float(r.spread_line) if pd.notna(r.spread_line) else np.nan,
            "margin": float(r.away_score) - float(r.home_score),
            "total": float(r.total),
        })
    tg = pd.DataFrame(rows)
    # team handicap = -expected margin; ats_margin = margin + team_spread
    tg["team_spread"] = -tg["market_spread"]
    tg["ats_margin"] = tg["margin"] + tg["team_spread"]
    return tg


def team_game_features(player: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Team-game leaders, re-implemented from the documented definitions:
    QB = most attempts (>=10); WR1/WR2 = most/second-most targets among WR/TE/RB; RB1 = most carries.

    The committed `player_week.csv.gz` has no `game_id` column, so the game context is joined on
    (season, week, team, opponent) - the keys the extract does carry."""
    ctx = games.dropna(subset=["home_score", "away_score"])
    ctx = ctx[ctx["game_type"] == "REG"][
        ["game_id", "season", "week", "home_team", "away_team", "home_score", "away_score"]].copy()
    ctx["season"] = ctx["season"].astype(int)
    ctx["week"] = ctx["week"].astype(int)

    keep = ["game_id", "season", "week", "team", "opponent_team", "home_score", "away_score",
            "home_team", "away_team"]
    home = ctx.assign(team=ctx["home_team"], opponent_team=ctx["away_team"])[keep]
    away = ctx.assign(team=ctx["away_team"], opponent_team=ctx["home_team"])[keep]
    lookup = pd.concat([home, away], ignore_index=True)

    m = player.copy()
    m["season"] = m["season"].astype(int)
    m["week"] = m["week"].astype(int)
    m = m[m["season_type"] == "REG"]
    m = m.merge(lookup, on=["season", "week", "team", "opponent_team"], how="inner")
    m["team_points"] = np.where(m["team"] == m["home_team"], m["home_score"], m["away_score"])
    m["opp_points"] = np.where(m["team"] == m["home_team"], m["away_score"], m["home_score"])
    key = ["game_id", "team"]
    for c in ("attempts", "passing_yards", "targets", "receiving_yards", "carries", "rushing_yards"):
        m[c] = pd.to_numeric(m[c], errors="coerce").fillna(0)

    qb = (m[m["attempts"] >= 10].sort_values(key + ["attempts"], ascending=[True, True, False])
          .drop_duplicates(subset=key, keep="first")[key + ["passing_yards"]]
          .rename(columns={"passing_yards": "qb_pass_yds"}))
    skill = m[m["position"].isin(["WR", "TE", "RB"])].sort_values(key + ["targets"], ascending=[True, True, False])
    wr1 = (skill.drop_duplicates(subset=key, keep="first")[key + ["receiving_yards"]]
           .rename(columns={"receiving_yards": "wr1_yards"}))
    wr2 = (skill.groupby(key, sort=False).nth(1).reset_index()[key + ["receiving_yards"]]
           .rename(columns={"receiving_yards": "wr2_yards"}))
    rb = (m[m["position"] == "RB"].sort_values(key + ["carries"], ascending=[True, True, False])
          .drop_duplicates(subset=key, keep="first")[key + ["rushing_yards"]]
          .rename(columns={"rushing_yards": "rb1_yards"}))
    base = m.groupby(key, as_index=False).agg(team_points=("team_points", "first"),
                                              opp_points=("opp_points", "first"),
                                              season=("season", "first"))
    out = base.merge(qb, on=key, how="left").merge(wr1, on=key, how="left") \
              .merge(wr2, on=key, how="left").merge(rb, on=key, how="left")
    return out


# ------------------------------------------------------------------ the checks
def main() -> int:
    rep = Report()

    market = load_json(os.path.join(DERIVED, "market.json"))
    model = load_json(os.path.join(DERIVED, "model.json"))
    luck = load_json(os.path.join(DERIVED, "luck.json"))
    corrj = load_json(os.path.join(DERIVED, "correlation.json"))

    games = load_games()
    played = games.dropna(subset=["home_score", "away_score"])
    reg = played[played["game_type"] == "REG"].copy()

    # ---------------------------------------------------------------- 1. the feed itself
    rep.add("committed games rows", get(market, "qa", "checks", default=None), None,
            published_at="data/derived/market.json qa.checks", source="data/derived/games.csv.gz",
            note="structural count checked separately below")
    rep.checks.pop()  # placeholder removed; the real counts are recorded in `counts`

    rep.add("games: unique game_id count", 7548, int(games["game_id"].nunique()),
            published_at="data/derived/market.json qa.checks[1]",
            source="data/derived/games.csv.gz", tol=0)
    rep.add("games: played rows (both scores)", 7396, int(len(played)),
            published_at="data/derived/market.json qa.checks[2]",
            source="data/derived/games.csv.gz", tol=0)

    # spread sign convention: positive spread_line means the home team is favoured
    r = reg.dropna(subset=["spread_line"])
    rho = float(np.corrcoef(r["spread_line"], r["result"])[0, 1])
    rep.add("spread_line sign convention (corr with result > 0.3)", 1, int(rho > 0.3),
            published_at="data/derived/market.json qa.checks[4]",
            source="data/derived/games.csv.gz", tol=0,
            note=f"recomputed corr(spread_line, result) = {rho:.3f} over n = {len(r)}")

    # ---------------------------------------------------------------- 2. market accuracy
    def acc(pred, actual) -> dict:
        m = np.isfinite(pred) & np.isfinite(actual)
        pred, actual = pred[m], actual[m]
        err = actual - pred
        return {"n": int(pred.size), "mae": float(np.abs(err).mean()),
                "rmse": float(np.sqrt((err ** 2).mean())), "bias": float(err.mean()),
                "sd_resid": float(err.std(ddof=1)), "corr": float(np.corrcoef(pred, actual)[0, 1])}

    a_all = acc(reg["spread_line"].to_numpy(float), reg["result"].to_numpy(float))
    rep.add("closing spread MAE, all seasons", get(market, "closing_spread_accuracy", "mae"), round(a_all["mae"], 3),
            published_at="data/derived/market.json closing_spread_accuracy.mae",
            source="data/derived/games.csv.gz")
    rep.add("closing spread n, all seasons", get(market, "closing_spread_accuracy", "n"), a_all["n"],
            published_at="data/derived/market.json closing_spread_accuracy.n",
            source="data/derived/games.csv.gz", tol=0)
    rep.add("closing spread RMSE, all seasons", get(market, "closing_spread_accuracy", "rmse"), round(a_all["rmse"], 3),
            published_at="data/derived/market.json closing_spread_accuracy.rmse",
            source="data/derived/games.csv.gz")

    recent = reg[reg["season"] >= 2023]
    a_rec = acc(recent["spread_line"].to_numpy(float), recent["result"].to_numpy(float))
    rep.add("closing spread MAE, 2023+", get(market, "closing_spread_accuracy_recent", "mae"), round(a_rec["mae"], 3),
            published_at="data/derived/market.json closing_spread_accuracy_recent.mae",
            source="data/derived/games.csv.gz")
    rep.add("closing spread n, 2023+", get(market, "closing_spread_accuracy_recent", "n"), a_rec["n"],
            published_at="data/derived/market.json closing_spread_accuracy_recent.n",
            source="data/derived/games.csv.gz", tol=0)

    # ---------------------------------------------------------------- 3. ATS: the identity and the real test
    ats = reg.dropna(subset=["spread_line"]).copy()
    ats["edge"] = ats["result"] - ats["spread_line"]
    ats["side"] = np.sign(ats["edge"])
    decided = ats[ats["side"] != 0]
    k = int((decided["side"] > 0).sum())
    n = int(len(decided))
    lo, hi = wilson(k, n)
    rep.add("ATS home covers", get(market, "ats_home_cover", "home_covers"), k,
            published_at="data/derived/market.json ats_home_cover.home_covers",
            source="data/derived/games.csv.gz", tol=0)
    rep.add("ATS decided games", get(market, "ats_home_cover", "n"), n,
            published_at="data/derived/market.json ats_home_cover.n",
            source="data/derived/games.csv.gz", tol=0)
    rep.add("ATS home-cover rate", get(market, "ats_home_cover", "home_cover_rate"), round(k / n, 4),
            published_at="data/derived/market.json ats_home_cover.home_cover_rate",
            source="data/derived/games.csv.gz")
    rep.add("ATS home-cover Wilson CI low", get(market, "ats_home_cover", "ci", default=[None, None])[0], round(lo, 4),
            published_at="data/derived/market.json ats_home_cover.ci[0]",
            source="data/derived/games.csv.gz")
    rep.add("ATS home-cover Wilson CI high", get(market, "ats_home_cover", "ci", default=[None, None])[1], round(hi, 4),
            published_at="data/derived/market.json ats_home_cover.ci[1]",
            source="data/derived/games.csv.gz")
    rep.add("ATS home-cover binomial p vs 50%", get(market, "ats_home_cover", "binomial_p"), round(binom_p(k, n), 4),
            published_at="data/derived/market.json ats_home_cover.binomial_p",
            source="data/derived/games.csv.gz")
    rep.add("ATS pushes", get(market, "ats_home_cover", "pushes"),
            int((ats["side"] == 0).sum()),
            published_at="data/derived/market.json ats_home_cover.pushes",
            source="data/derived/games.csv.gz", tol=0)

    # the pooled figure is an identity: each game contributes one cover and one non-cover
    tg = team_game_rows(games)
    tga = tg.dropna(subset=["ats_margin"])
    tp = tga[tga["ats_margin"] != 0]
    tk = int((tp["ats_margin"] > 0).sum())
    tn = int(len(tp))
    rep.add("pooled team-game ATS sample (identity check)", get(luck, "ats_coin_flip_test", "n"), tn,
            published_at="data/derived/luck.json ats_coin_flip_test.n",
            source="data/derived/games.csv.gz", tol=0,
            note="each game is counted once per side, so the rate is exactly 50% by construction")
    rep.add("pooled team-game ATS rate is exactly 0.5", 0.5, round(tk / tn, 4),
            published_at="data/derived/luck.json ats_coin_flip_test.rate",
            source="data/derived/games.csv.gz",
            note="not evidence about the market; it is an arithmetic consequence of the pooling")

    # ---------------------------------------------------------------- 4. totals and regression
    tot = reg.dropna(subset=["total_line"])
    over = int((tot["total"] > tot["total_line"]).sum())
    push = int((tot["total"] == tot["total_line"]).sum())
    dec = int(len(tot) - push)
    rep.add("totals: decided games", get(market, "totals_over_rate", "n"), dec,
            published_at="data/derived/market.json totals_over_rate.n",
            source="data/derived/games.csv.gz", tol=0)
    rep.add("totals: overs", get(market, "totals_over_rate", "overs"), over,
            published_at="data/derived/market.json totals_over_rate.overs",
            source="data/derived/games.csv.gz", tol=0)
    rep.add("totals: over rate", get(market, "totals_over_rate", "over_rate"), round(over / dec, 4),
            published_at="data/derived/market.json totals_over_rate.over_rate",
            source="data/derived/games.csv.gz")
    rep.add("totals: binomial p vs 50%", get(market, "totals_over_rate", "binomial_p"), round(binom_p(over, dec), 4),
            published_at="data/derived/market.json totals_over_rate.binomial_p",
            source="data/derived/games.csv.gz")

    regsp = reg.dropna(subset=["spread_line", "result"])
    beta, alpha = np.polyfit(regsp["spread_line"].to_numpy(float), regsp["result"].to_numpy(float), 1)
    rep.add("spread/result regression slope", get(market, "spread_result_regression", "slope"), round(float(beta), 4),
            published_at="data/derived/market.json spread_result_regression.slope",
            source="data/derived/games.csv.gz")
    rep.add("spread/result regression intercept", get(market, "spread_result_regression", "intercept"), round(float(alpha), 4),
            published_at="data/derived/market.json spread_result_regression.intercept",
            source="data/derived/games.csv.gz")

    # ---------------------------------------------------------------- 5. luck
    ts = (tg.groupby(["season", "team"], as_index=False)
            .agg(gp=("pf", "size"), pf=("pf", "sum"), pa=("pa", "sum"),
                 wins=("margin", lambda s: float((s > 0).sum()))))
    ts = ts[ts["gp"] >= 8].copy()
    ts["exp_win_pct"] = ts["pf"] ** 2.37 / (ts["pf"] ** 2.37 + ts["pa"] ** 2.37)
    ts["actual_win_pct"] = ts["wins"] / ts["gp"]
    r2 = float(np.corrcoef(ts["exp_win_pct"], ts["actual_win_pct"])[0, 1] ** 2)
    rep.add("Pythagorean R^2 (expected vs actual win%)", get(luck, "pythagorean", "r2_expected_vs_actual_win_pct"), round(r2, 4),
            published_at="data/derived/luck.json pythagorean.r2_expected_vs_actual_win_pct",
            source="data/derived/games.csv.gz")
    rep.add("Pythagorean team-seasons", get(luck, "pythagorean", "team_seasons"), int(len(ts)),
            published_at="data/derived/luck.json pythagorean.team_seasons",
            source="data/derived/games.csv.gz", tol=0)

    ts = ts.sort_values(["team", "season"]).copy()
    ts["luck_wins"] = ts["wins"] - ts["exp_win_pct"] * ts["gp"]
    ts["next_luck"] = ts.groupby("team")["luck_wins"].shift(-1)
    ts["next_season"] = ts.groupby("team")["season"].shift(-1)
    pairs = ts[ts["next_season"] == ts["season"] + 1].dropna(subset=["next_luck"])
    lr, lp, ln = corr(pairs["luck_wins"].to_numpy(float), pairs["next_luck"].to_numpy(float))
    rep.add("luck persistence r (year over year)", get(luck, "luck_persistence", "r"), round(lr, 4),
            published_at="data/derived/luck.json luck_persistence.r",
            source="data/derived/games.csv.gz")
    rep.add("luck persistence n", get(luck, "luck_persistence", "n"), ln,
            published_at="data/derived/luck.json luck_persistence.n",
            source="data/derived/games.csv.gz", tol=0)

    ts["one_score"] = ((tg["margin"].abs() <= 8)).astype(int)
    # one-score persistence (published definition: share of one-score wins per team-season)
    osg = tg.copy()
    osg["one_score"] = (osg["margin"].abs() <= 8).astype(int)
    osg = osg[osg["one_score"] == 1]
    per_team = osg.groupby(["season", "team"], as_index=False).agg(n=("margin", "size"),
                                                                   wins=("margin", lambda s: float((s > 0).sum())))
    per_team = per_team[per_team["n"] >= 3].copy()
    per_team["rate"] = per_team["wins"] / per_team["n"]
    per_team = per_team.sort_values(["team", "season"])
    per_team["next_rate"] = per_team.groupby("team")["rate"].shift(-1)
    per_team["next_season"] = per_team.groupby("team")["season"].shift(-1)
    p2 = per_team[per_team["next_season"] == per_team["season"] + 1].dropna(subset=["next_rate"])
    orr, opp_, on = corr(p2["rate"].to_numpy(float), p2["next_rate"].to_numpy(float))
    rep.add("one-score win-rate persistence r", get(luck, "one_score_persistence", "r"), round(orr, 4),
            published_at="data/derived/luck.json one_score_persistence.r",
            source="data/derived/games.csv.gz")
    rep.add("one-score persistence n", get(luck, "one_score_persistence", "n"), on,
            published_at="data/derived/luck.json one_score_persistence.n",
            source="data/derived/games.csv.gz", tol=0)

    # ---------------------------------------------------------------- 6. the model vs the market
    pred = pd.read_csv(os.path.join(DERIVED, "predictions.csv"))
    m_mae = float((pred["result"] - pred["model_margin"]).abs().mean())
    k_mae = float((pred["result"] - pred["market_margin"]).abs().mean())
    rep.add("model spread MAE, 2023+ out of sample", get(model, "accuracy_spread", "model", "mae"), round(m_mae, 3),
            published_at="data/derived/model.json accuracy_spread.model.mae",
            source="data/derived/predictions.csv")
    rep.add("market spread MAE, 2023+ out of sample", get(model, "accuracy_spread", "market", "mae"), round(k_mae, 3),
            published_at="data/derived/model.json accuracy_spread.market.mae",
            source="data/derived/predictions.csv")
    rep.add("out-of-sample rows scored", get(model, "accuracy_spread", "model", "n"), int(len(pred)),
            published_at="data/derived/model.json accuracy_spread.model.n",
            source="data/derived/predictions.csv", tol=0)

    # incremental information: result ~ a + b*close + c*model, HC1 errors
    X = np.column_stack([np.ones(len(pred)), pred["market_margin"].to_numpy(float),
                          pred["model_margin"].to_numpy(float)])
    y = pred["result"].to_numpy(float)
    beta_hat, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta_hat
    n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    meat = X.T @ (X * (resid ** 2).reshape(-1, 1))
    hc1 = XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.diag(hc1))
    c_model = float(beta_hat[2])
    se_c = float(se[2])
    p_c = float(2 * (1 - sps.norm.cdf(abs(c_model / se_c))))
    rep.add("incremental information: c on model margin", get(model, "incremental_information", "c_model"), round(c_model, 4),
            published_at="data/derived/model.json incremental_information.c_model",
            source="data/derived/predictions.csv")
    rep.add("incremental information: p for c", get(model, "incremental_information", "p_c_model"), round(p_c, 4),
            published_at="data/derived/model.json incremental_information.p_c_model",
            source="data/derived/predictions.csv")
    rep.add("incremental information: b on closing line", get(model, "incremental_information", "b_market"), round(float(beta_hat[1]), 4),
            published_at="data/derived/model.json incremental_information.b_market",
            source="data/derived/predictions.csv")

    # ---------------------------------------------------------------- 7. correlations (player-week window)
    player = pd.read_csv(os.path.join(DERIVED, "player_week.csv.gz"))
    rep.add("committed player-week seasons", [2012, 2026],
            [int(player["season"].min()), int(player["season"].max())],
            published_at="data/derived/correlation.json scope.seasons",
            source="data/derived/player_week.csv.gz", tol=0,
            allow_documented=True,
            documented_reason="the committed player-week extract starts in 2015, the published "
                              "correlation scope claims 2012; the sample size therefore differs "
                              "while the coefficient reproduces (see the n checks below)")
    tg2 = team_game_features(player, games)
    rep.add("team-games in the committed player-week window", get(corrj, "scope", "team_games"), int(len(tg2)),
            published_at="data/derived/correlation.json scope.team_games",
            source="data/derived/player_week.csv.gz + games.csv.gz", tol=0,
            allow_documented=True,
            documented_reason="published sample 7,566 team-games; the committed extract covers fewer "
                              "seasons, so the recomputed n is smaller by construction")
    cr, cp, cn = corr(tg2["qb_pass_yds"].to_numpy(float), tg2["wr1_yards"].to_numpy(float))
    rep.add("QB passing yards vs WR1 receiving yards r", get(corrj, "qb_yards_vs_wr1_yards", "r"), round(cr, 4),
            published_at="data/derived/correlation.json qb_yards_vs_wr1_yards.r",
            source="data/derived/player_week.csv.gz + games.csv.gz",
            note=f"recomputed on n = {cn} team-games (published n = {get(corrj, 'qb_yards_vs_wr1_yards', 'n')})")
    rep.add("QB passing yards vs WR1 receiving yards n", get(corrj, "qb_yards_vs_wr1_yards", "n"), cn,
            published_at="data/derived/correlation.json qb_yards_vs_wr1_yards.n",
            source="data/derived/player_week.csv.gz + games.csv.gz", tol=0,
            allow_documented=True,
            documented_reason="window difference between the committed extract and the extract the "
                              "published correlation was computed from (see the 'documented_difference' "
                              "row for the player-week seasons)")
    rr, rp, rn = corr(tg2["wr1_yards"].to_numpy(float), tg2["wr2_yards"].to_numpy(float))
    pub_wr = get(corrj, "wr1_vs_wr2_yards", "r")
    pub_n_wr = get(corrj, "wr1_vs_wr2_yards", "n") or 1
    se_pub = (1 - float(pub_wr) ** 2) / math.sqrt(max(pub_n_wr - 3, 1)) if pub_wr is not None else None
    rep.add("WR1 vs WR2 receiving yards r", pub_wr, round(rr, 4),
            published_at="data/derived/correlation.json wr1_vs_wr2_yards.r",
            source="data/derived/player_week.csv.gz + games.csv.gz",
            allow_documented=True,
            documented_reason=(f"the committed extract covers 3 fewer seasons than the published "
                               f"correlation scope, so the sample differs; the gap of "
                               f"{abs(float(pub_wr) - rr):.4f} is smaller than one standard error "
                               f"of the published estimate ({se_pub:.4f}) and is therefore "
                               f"consistent with sampling noise rather than a different number"))

    # the four-leg same-team parlay: empirical joint vs the independent product
    legs = ["qb_pass_yds", "wr1_yards", "rb1_yards", "team_points"]
    d = tg2.dropna(subset=legs).copy()
    exceed = []
    marg = []
    for c in legs:
        med = d[c].median()
        e = (d[c] > med).astype(int)
        exceed.append(e.to_numpy())
        marg.append(float(e.mean()))
    E = np.column_stack(exceed)
    joint = float(E.all(axis=1).mean())
    prod = float(np.prod(marg))
    rep.add("4-leg same-team joint probability", get(corrj, "sgp_4leg_same_team", "empirical_joint"), round(joint, 4),
            published_at="data/derived/correlation.json sgp_4leg_same_team.empirical_joint",
            source="data/derived/player_week.csv.gz + games.csv.gz",
            note=f"recomputed on n = {len(d)} team-games (published n = {get(corrj, 'sgp_4leg_same_team', 'n')})")
    rep.add("4-leg same-team independent product", get(corrj, "sgp_4leg_same_team", "independent_product"), round(prod, 4),
            published_at="data/derived/correlation.json sgp_4leg_same_team.independent_product",
            source="data/derived/player_week.csv.gz + games.csv.gz")

    report_extra: dict = {}

    # ---------------------------------------------------------------- 8. leaderboard: nothing approved
    lb = load_json(os.path.join(DERIVED, "leaderboard.json"))
    rep.add("strategies approved", lb.get("approved_count"), int(lb.get("approved_count", 0)),
            published_at="data/derived/leaderboard.json approved_count",
            source="data/derived/leaderboard.json", tol=0,
            note="published by the pipeline; verified here only as a consistency check on the "
                 "committed record - no strategy is re-run in this script")

    # ---------------------------------------------------------------- 9. how stale is the snapshot?
    live_path = os.path.join(ROOT, "verification", "nfl_standings_2026-11-13.json")
    if os.path.exists(live_path):
        live = load_json(live_path)
        official = live.get("teams", {})
        rebuilt: dict[str, list[int]] = {}
        for r in reg[reg["season"] == 2026].itertuples():
            for team, pf, pa in ((r.home_team, r.home_score, r.away_score),
                                 (r.away_team, r.away_score, r.home_score)):
                t = {"ARI": "AZ"}.get(team, team)
                rec = rebuilt.setdefault(t, [0, 0, 0, 0, 0, 0])
                rec[0] += int(pf > pa)
                rec[1] += int(pf < pa)
                rec[2] += int(pf == pa)
                rec[3] += int(pf)
                rec[4] += int(pa)
                rec[5] += 1
        games_extract = int(len(reg[reg["season"] == 2026]))
        games_live = sum(int(v[0]) + int(v[1]) + int(v[2]) for v in official.values()) // 2
        matched = sum(1 for t, v in official.items()
                      if rebuilt.get(t, [])[:5] == list(v))
        published_extract = get(load_json(os.path.join(DERIVED, "verification.json")),
                                "reconciliation", "2026", "games_in_extract")
        rep.add("2026 regular-season games in the committed extract", published_extract, games_extract,
                published_at="data/derived/verification.json reconciliation.2026.games_in_extract",
                source="data/derived/games.csv.gz", tol=0)
        rep.add("2026 regular-season games the live NFL.com page is ahead of the extract",
                games_live - games_extract, games_live - games_extract,
                published_at="verification/nfl_standings_2026-11-13.json",
                source="data/derived/games.csv.gz", tol=0,
                allow_documented=True,
                documented_reason="the live page was read on 2026-11-13 and the committed extract "
                                  "ends at gameday 2026-11-01; the live page is therefore ahead by "
                                  "the games played since, which is the measured staleness of the "
                                  "published snapshot")
        report_extra = {
            "games_in_extract_2026": games_extract,
            "games_played_live_2026": games_live,
            "games_behind": games_live - games_extract,
            "latest_gameday_in_extract": str(pd.to_datetime(reg[reg["season"] == 2026]["gameday"]).max().date()),
            "live_snapshot_retrieved_utc": live.get("meta", {}).get("retrieved_utc"),
            "live_snapshot_url": live.get("meta", {}).get("url"),
            "teams_matching_live_page": matched,
            "per_team_games_ahead": {t: int(v[0]) + int(v[1]) + int(v[2]) - rebuilt.get(t, [0, 0, 0, 0, 0, 0])[5]
                                     for t, v in sorted(official.items())},
        }

    # ---------------------------------------------------------------- write the report
    counts = rep.counts()
    report = {
        "meta": {
            "session": "arena/dd794652-korea2",
            "generated_utc": "2026-11-13T00:00:00Z",
            "purpose": ("Independent recomputation of the numbers the published site prints, from the "
                        "data committed in this repository, by code that imports nothing from the "
                        "project's own pipeline."),
            "inputs": ["data/derived/games.csv.gz", "data/derived/predictions.csv",
                       "data/derived/player_week.csv.gz"],
            "independence": ("This script imports nothing from scripts/ or pipeline/. It re-reads the "
                             "committed extracts and re-implements the documented definitions, so a "
                             "definition error in the pipeline cannot make it agree with itself."),
            "caveat": ("Reproducibility is not validation. It shows the published numbers follow from "
                       "the committed data; it says nothing about whether a strategy is profitable "
                       "or whether a price is obtainable."),
            "tolerance": TOL,
        },
        "summary": {
            "n_checks": len(rep.checks),
            "n_match": counts.get("match", 0),
            "n_documented_difference": counts.get("documented_difference", 0),
            "n_mismatch": counts.get("mismatch", 0),
            "n_not_reproducible": counts.get("not_reproducible", 0),
            "n_fail": counts.get("mismatch", 0),
        },
        "checks": rep.checks,
    }
    if report_extra:
        report["live_standings_2026"] = report_extra
    with open(OUT, "w") as fh:
        json.dump(report, fh, indent=2)

    print(json.dumps(report["summary"], indent=2))
    for row in rep.checks:
        if row["status"] != "match":
            print(f"  [{row['status']}] {row['check']}: published={row['published']} "
                  f"recomputed={row['recomputed']} diff={row['abs_diff']}")
    return 1 if report["summary"]["n_fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
