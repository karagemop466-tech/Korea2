"""Originate our own NFL lines: spread, total and moneyline, for every game.

Engine
------
A shrunk attack/defence points model, refit *every week* on games played before that
week only:

    home_points = mu + hfa + att[home] + def[away]
    away_points = mu          + att[away] + def[home]

Ridge penalty on ``att`` / ``def`` (not on ``mu`` / ``hfa``), sample weights decaying
with age (half-life in days). Own spread = predicted margin, own total = predicted
points, own moneyline = normal-CDF win probability with the residual sigma estimated
on the *training* window only (never on the game being predicted).

Two further reference engines are produced for comparison, and are labelled as such
in every table that uses them:

  * ``ELO``    : pure Elo -> points conversion, slope fitted on the development window only.
  * ``BLEND``  : 50/50 average of the ridge engine and the closing market line.
                 This one *uses the market*, so it is a benchmark, not an origination.

No-lookahead contract
---------------------
Every fit for week W only sees games with a gameday strictly before Monday of that week
(i.e. previous weeks of the same season and previous seasons). ``tests/test_lookahead.py``
re-computes a season with all future data removed and asserts identical output.

Output
------
data/interim/lines.parquet      one row per game with all engines' lines
site_data/origination.json      accuracy metrics + current-week board
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from lib.common import (INTERIM, american_to_decimal, bootstrap_mean_ci, brier, log_loss,
                        normal_cdf, write_json)

DEV_END = 2014          # seasons <= DEV_END are development (threshold/alpha tuning only)
TEST_START = 2015      # evaluation window for every published number
LOOKBACK_SEASONS = 2   # seasons of history used in each weekly refit
HALFLIFE_DAYS = 200.0


# --------------------------------------------------------------------- design
def design_matrix(df: pd.DataFrame, teams: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Two rows per game (home points, away points)."""
    idx = {t: i for i, t in enumerate(teams)}
    n = len(df)
    k = 2 + 2 * len(teams)          # intercept, hfa, att, def
    X = np.zeros((2 * n, k))
    y = np.zeros(2 * n)
    for i, (row, home_pts, away_pts) in enumerate(
            zip(df.itertuples(index=False), df["home_score"].to_numpy(), df["away_score"].to_numpy())):
        # home row
        X[2 * i, 0] = 1.0
        X[2 * i, 1] = 0.0 if row.neutral else 1.0
        X[2 * i, 2 + idx[row.home_team]] += 1.0
        X[2 * i, 2 + len(teams) + idx[row.away_team]] += 1.0
        y[2 * i] = home_pts
        # away row
        X[2 * i + 1, 0] = 1.0
        X[2 * i + 1, 2 + idx[row.away_team]] += 1.0
        X[2 * i + 1, 2 + len(teams) + idx[row.home_team]] += 1.0
        y[2 * i + 1] = away_pts
    return X, y


def ridge_fit(X: np.ndarray, y: np.ndarray, w: np.ndarray, alpha: float,
              n_teams: int) -> np.ndarray:
    pen = np.zeros(X.shape[1])
    pen[2:] = alpha                      # penalise att/def only
    Xw = X * w[:, None]
    A = X.T @ Xw + np.diag(pen)
    b = X.T @ (y * w)
    return np.linalg.solve(A, b)


def predict(theta: np.ndarray, df: pd.DataFrame, teams: list[str]) -> tuple[np.ndarray, np.ndarray]:
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    home = []
    away = []
    for row in df.itertuples(index=False):
        hfa = 0.0 if row.neutral else 1.0
        home.append(theta[0] + theta[1] * hfa + theta[2 + idx[row.home_team]] + theta[2 + n + idx[row.away_team]])
        away.append(theta[0] + theta[2 + idx[row.away_team]] + theta[2 + n + idx[row.home_team]])
    return np.array(home), np.array(away)


# ------------------------------------------------------------------ walk-fwd
def walk_forward(g: pd.DataFrame, alpha: float) -> pd.DataFrame:
    teams = sorted(set(g["home_team"]).union(g["away_team"]))
    played = g[g["played"]].copy()
    out = np.full((len(g), 4), np.nan)   # own_home, own_away, sigma, n_train
    g = g.reset_index(drop=True)
    keys = g[["season", "week"]].astype({"week": "float"}).fillna(0)
    week_starts = (g.assign(wk=g["week"].astype(float).fillna(0))
                     .groupby(["season", "wk"])["gameday"].min())

    for (season, wk), rows in g.groupby([g["season"], g["week"].astype(float).fillna(0)]):
        cutoff = week_starts.loc[(season, wk)]
        hist = played[(played["gameday"] < cutoff) & (played["season"] >= season - LOOKBACK_SEASONS)]
        if len(hist) < 150:
            continue
        age_days = (cutoff - hist["gameday"]).dt.days.to_numpy(dtype=float)
        w = 0.5 ** (age_days / HALFLIFE_DAYS)
        X, y = design_matrix(hist, teams)
        ww = np.repeat(w, 2)
        theta = ridge_fit(X, y, ww, alpha, len(teams))
        ph, pa = predict(theta, rows, teams)
        res = (y[0::2] - np.repeat(ph := predict(theta, hist, teams)[0], 1)) if False else None
        hp, ap = predict(theta, hist, teams)
        resid_margin = (hist["home_score"].to_numpy() - hp) - (hist["away_score"].to_numpy() - ap)
        # weight-classic: recency-weighted residual sigma, floored for stability
        sigma = float(np.sqrt(np.average(resid_margin ** 2, weights=w))) if len(hist) else 13.5
        sigma = max(sigma, 10.0)
        pos = rows.index.to_numpy()
        out[pos, 0] = ph
        out[pos, 1] = pa
        out[pos, 2] = sigma
        out[pos, 3] = len(hist)

    g["own_home_pts"] = out[:, 0]
    g["own_away_pts"] = out[:, 1]
    g["own_sigma"] = out[:, 2]
    g["own_n_train"] = out[:, 3]
    g["own_margin"] = g["own_home_pts"] - g["own_away_pts"]
    g["own_total"] = g["own_home_pts"] + g["own_away_pts"]
    return g


def tune_alpha(g: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    """Pick the ridge penalty on the development window only."""
    rows = []
    for alpha in (2.0, 5.0, 10.0, 20.0, 40.0, 80.0):
        out = walk_forward(g, alpha)
        dev = out[(out["played"]) & (out["season"] <= DEV_END) & out["own_margin"].notna()]
        mae = float(np.mean(np.abs(dev["own_margin"] - dev["margin"])))
        mae_tot = float(np.mean(np.abs(dev["own_total"] - dev["points_total"])))
        rows.append({"alpha": alpha, "dev_mae_margin": mae, "dev_mae_total": mae_tot,
                     "n": int(len(dev))})
        print(f"  alpha={alpha:<5} dev MAE margin={mae:.3f} total={mae_tot:.3f} n={len(dev):,}")
    tab = pd.DataFrame(rows)
    best = float(tab.sort_values("dev_mae_margin").iloc[0]["alpha"])
    return best, tab


def add_engines(g: pd.DataFrame) -> pd.DataFrame:
    # Elo engine: slope fitted on the development window only
    dev = g[(g["played"]) & (g["season"] <= DEV_END) & g["elo_diff"].notna()].copy()
    X = np.column_stack([np.ones(len(dev)), dev["elo_diff"]])
    coef, *_ = np.linalg.lstsq(X, dev["margin"], rcond=None)
    g["elo_engine_margin"] = coef[0] + coef[1] * g["elo_diff"]
    # total from a dev-fitted expansion of each team's rolling points form
    dev["form_sum"] = dev["pf_ewm"] + dev["pa_ewm"]           # home for + away against
    dev2 = g[(g["played"]) & (g["season"] <= DEV_END)].copy()
    dev2["form_sum"] = dev2["pf_ewm"] + dev2["pa_ewm"]
    ok = dev2["form_sum"].notna()
    Xt = np.column_stack([np.ones(ok.sum()), dev2.loc[ok, "form_sum"]])
    ct, *_ = np.linalg.lstsq(Xt, dev2.loc[ok, "points_total"], rcond=None)
    g["elo_engine_total"] = ct[0] + ct[1] * (g["pf_ewm"] + g["pa_ewm"])

    g["blend_margin"] = 0.5 * g["own_margin"] + 0.5 * g["spread_line"]
    g["blend_total"] = 0.5 * g["own_total"] + 0.5 * g["total_line"]

    for eng in ("own", "elo_engine", "blend"):
        s = g["own_sigma"].fillna(13.5) if eng != "blend" else g["own_sigma"].fillna(13.5) * 0.75
        g[f"{eng}_home_wp"] = [normal_cdf(m / s) if (not math.isnan(m) and not math.isnan(s)) else np.nan
                               for m, s in zip(g[f"{eng}_margin"], s)]
        g[f"{eng}_away_wp"] = 1 - g[f"{eng}_home_wp"]
    return g


# --------------------------------------------------------------- evaluation
def accuracy_table(g: pd.DataFrame) -> tuple[list[dict], dict]:
    ev = g[(g["played"]) & (g["season"] >= TEST_START) & g["own_margin"].notna()
           & g["spread_line"].notna() & g["total_line"].notna()].copy()
    rows = []
    for eng, mcol, tcol, plab in (("own", "own_margin", "own_total", "Ridge attack/defence"),
                                  ("elo_engine", "elo_engine_margin", "elo_engine_total", "Elo + form"),
                                  ("blend", "blend_margin", "blend_total", "Model/market blend (benchmark)")):
        d = ev[ev[mcol].notna()]
        mae_m = float(np.mean(np.abs(d[mcol] - d["margin"])))
        mae_t = float(np.mean(np.abs(d[tcol] - d["points_total"])))
        closer = float(np.mean(np.abs(d[mcol] - d["margin"]) < np.abs(d["spread_line"] - d["margin"])))
        rows.append({"engine": eng, "label": plab, "n_games": int(len(d)),
                     "mae_margin": mae_m, "mae_total": mae_t,
                     "beat_close_rate": closer})
    # reference rows that are not engines
    rows.append({"engine": "market", "label": "Closing market line (benchmark)", "n_games": int(len(ev)),
                 "mae_margin": float(np.mean(np.abs(ev["spread_line"] - ev["margin"]))),
                 "mae_total": float(np.mean(np.abs(ev["total_line"] - ev["points_total"]))),
                 "beat_close_rate": None})
    rows.append({"engine": "naive_home", "label": "Naive home-field line (-2.5 home)",
                 "n_games": int(len(ev)),
                 "mae_margin": float(np.mean(np.abs(-2.5 - ev["margin"]))),
                 "mae_total": float(np.mean(np.abs(ev["points_total"] - ev["points_total"].mean()))),
                 "beat_close_rate": float(np.mean(np.abs(-2.5 - ev["margin"]) < np.abs(ev["spread_line"] - ev["margin"])))})

    # does our disagreement with the close contain information?
    d = ev[ev["own_margin"].notna()]
    diff = (d["own_margin"] - d["spread_line"]).to_numpy()
    resid = (d["margin"] - d["spread_line"]).to_numpy()
    slope = float(np.polyfit(diff, resid, 1)[0])
    rng = np.random.default_rng(5)
    slopes = []
    for _ in range(2000):
        i = rng.integers(0, len(diff), len(diff))
        slopes.append(np.polyfit(diff[i], resid[i], 1)[0])
    info = {
        "n": int(len(diff)),
        "corr_model_minus_close_vs_actual_minus_close": float(np.corrcoef(diff, resid)[0, 1]),
        "slope": slope,
        "slope_ci95": [float(np.quantile(slopes, 0.025)), float(np.quantile(slopes, 0.975))],
        "mean_abs_disagreement": float(np.mean(np.abs(diff))),
        "share_disagreement_ge_2": float(np.mean(np.abs(diff) >= 2)),
    }

    # probability calibration
    cal = {}
    dd = ev[ev["own_home_wp"].notna() & ev["mkt_home_win_prob"].notna()]
    y = (dd["margin"] > 0).astype(float).to_numpy()
    cal["n"] = int(len(dd))
    cal["brier_own"] = brier(dd["own_home_wp"].to_numpy(), y)
    cal["brier_market"] = brier(dd["mkt_home_win_prob"].to_numpy(), y)
    cal["logloss_own"] = log_loss(dd["own_home_wp"].to_numpy(), y)
    cal["logloss_market"] = log_loss(dd["mkt_home_win_prob"].to_numpy(), y)
    bins = np.linspace(0.05, 0.95, 10)
    dd = dd.assign(bin=pd.cut(dd["own_home_wp"], bins))
    curve = (dd.groupby("bin", observed=True)
               .apply(lambda x: pd.Series({"pred": x["own_home_wp"].mean(), "actual": (x["margin"] > 0).mean(),
                                           "n": len(x)}), include_groups=False)
               .reset_index(drop=True))
    cal["reliability"] = curve.to_dict("records")
    return rows, {"information": info, "calibration": cal}


def current_board(g: pd.DataFrame, season: int) -> list[dict]:
    """Next unplayed week: our own line next to the market line."""
    up = g[(g["season"] == season) & (~g["played"])].copy()
    if up.empty:
        return []
    up = up[up["spread_line"].notna()]
    if up.empty:
        return []
    week = up["week"].min()
    up = up[up["week"] == week].sort_values(["gameday", "gametime"])
    out = []
    for r in up.itertuples(index=False):
        out.append({
            "game_id": r.game_id, "gameday": r.gameday, "week": int(week),
            "away": r.away_team, "home": r.home_team,
            "own_spread": None if pd.isna(r.own_margin) else round(-float(r.own_margin), 2),
            "own_total": None if pd.isna(r.own_total) else round(float(r.own_total), 2),
            "own_home_win_prob": None if pd.isna(r.own_home_wp) else round(float(r.own_home_wp), 4),
            "mkt_spread": None if pd.isna(r.spread_line) else float(r.spread_line),
            "mkt_total": None if pd.isna(r.total_line) else float(r.total_line),
            "mkt_home_ml": None if pd.isna(r.home_moneyline) else float(r.home_moneyline),
            "mkt_away_ml": None if pd.isna(r.away_moneyline) else float(r.away_moneyline),
            "edge_spread": None if pd.isna(r.own_margin) or pd.isna(r.spread_line) else round(float(r.own_margin - r.spread_line), 2),
            "edge_total": None if pd.isna(r.own_total) or pd.isna(r.total_line) else round(float(r.own_total - r.total_line), 2),
            "roof": r.roof, "wind": None if pd.isna(r.wind) else float(r.wind),
            "temp": None if pd.isna(r.temp) else float(r.temp),
        })
    return out


def main() -> None:
    g = pd.read_parquet(INTERIM / "games.parquet")
    print("tuning ridge penalty on the development window (1999-2014)...")
    alpha, tab = tune_alpha(g)
    print(f"selected alpha={alpha}")
    g = walk_forward(g, alpha)
    g = add_engines(g)

    # fair moneyline (American) from our own win probabilities
    def fair_ml(p):
        if p is None or (isinstance(p, float) and math.isnan(p)) or p <= 0.005 or p >= 0.995:
            return np.nan
        dec = 1.0 / p
        return round(-(100.0 / (dec - 1.0)), 0) if dec < 2.0 else round((dec - 1.0) * 100.0, 0)

    g["own_home_ml"] = g["own_home_wp"].map(fair_ml)
    g["own_away_ml"] = g["own_away_wp"].map(fair_ml)

    rows, extra = accuracy_table(g)
    season = int(g["season"].max())
    board = current_board(g, season)

    write_json("origination.json", {
        "generated": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "test_window": [TEST_START, int(g["season"].max())],
        "dev_window": [int(g["season"].min()), DEV_END],
        "ridge_alpha": alpha,
        "alpha_tuning": tab.to_dict("records"),
        "accuracy": rows,
        "accuracy_extra": extra,
        "current_board": board,
        "current_week": int(board[0]["week"]) if board else None,
        "current_season": season,
    })
    g.to_parquet(INTERIM / "lines.parquet", index=False)
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"\ninfo on own-vs-close disagreement: {extra['information']}")
    print(f"calibration: brier own={extra['calibration']['brier_own']:.4f} "
          f"market={extra['calibration']['brier_market']:.4f}")
    print(f"current board rows: {len(board)}")


if __name__ == "__main__":
    main()
