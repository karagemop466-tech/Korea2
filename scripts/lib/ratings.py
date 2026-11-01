#!/usr/bin/env python3
"""Recency-weighted ridge team ratings in points, used to originate spreads and totals.

Model (two equations per game, fitted jointly):

    home_score = mu + off_home - def_away + hfa
    away_score = mu + off_away - def_home

`off` and `def` are in points per game relative to the league average team; `hfa` is the extra
points the home team scores. Observations are weighted 0.5 ** (age_days / half_life_days) so recent
games dominate, and ratings are shrunk toward the league average with a ridge penalty. Fitting is a
plain weighted least-squares solve of the normal equations - no black box.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class Ratings:
    def __init__(self, teams: list[str], beta: np.ndarray):
        n = len(teams)
        self.teams = teams
        self.off = dict(zip(teams, beta[:n]))
        self.deff = dict(zip(teams, beta[n:2 * n]))
        self.mu = float(beta[-2])
        self.hfa = float(beta[-1])

    def predict(self, home: str, away: str) -> tuple[float, float]:
        o_h, d_h = self.off.get(home, 0.0), self.deff.get(home, 0.0)
        o_a, d_a = self.off.get(away, 0.0), self.deff.get(away, 0.0)
        home_pts = self.mu + o_h - d_a + self.hfa
        away_pts = self.mu + o_a - d_h
        return home_pts - away_pts, home_pts + away_pts

    def to_dict(self) -> dict:
        return {
            "mu": round(self.mu, 3), "hfa": round(self.hfa, 3),
            "ratings": {t: {"off": round(self.off[t], 2), "def": round(self.deff[t], 2)}
                        for t in self.teams},
        }


def fit(train: pd.DataFrame, ref_date: pd.Timestamp, half_life_days: float = 120.0,
        lam: float = 8.0) -> Ratings:
    train = train.dropna(subset=["home_score", "away_score", "gameday"])
    teams = sorted(set(train["home_team"]) | set(train["away_team"]))
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    p = 2 * n + 2
    m = 2 * len(train)
    X = np.zeros((m, p))
    y = np.zeros(m)
    w = np.zeros(m)
    age = (ref_date - train["gameday"]).dt.days.to_numpy(float)
    ww = 0.5 ** (np.clip(age, 0, None) / half_life_days)
    hi = train["home_team"].map(idx).to_numpy()
    ai = train["away_team"].map(idx).to_numpy()
    X[:len(train), :] = 0.0
    # home equations
    X[np.arange(len(train)), hi] = 1.0
    X[np.arange(len(train)), n + ai] = -1.0
    X[:len(train), 2 * n] = 1.0
    X[:len(train), 2 * n + 1] = 1.0
    y[:len(train)] = train["home_score"].to_numpy(float)
    # away equations
    X[len(train):, ai] = 1.0
    X[len(train):, n + hi] = -1.0
    X[len(train):, 2 * n] = 1.0
    y[len(train):] = train["away_score"].to_numpy(float)
    w[:len(train)] = ww
    w[len(train):] = ww

    XtW = X.T * w
    A = XtW @ X
    pen = np.zeros(p)
    pen[:2 * n] = lam            # shrink team ratings only
    A = A + np.diag(pen)
    b = XtW @ y
    beta = np.linalg.solve(A, b)
    return Ratings(teams, beta)


def fit_history(games: pd.DataFrame, test_start: int, half_life_days: float = 120.0,
                lam: float = 8.0) -> pd.DataFrame:
    """Walk-forward predictions for every regular-season game from `test_start` onward.

    For each (season, week) the model is fitted only on games played strictly before that week's
    first kickoff, so no result can leak into its own prediction.
    """
    reg = games[(games["game_type"] == "REG")].copy()
    rows = []
    for (season, week), grp in reg[reg["season"] >= test_start].groupby(["season", "week"]):
        cutoff = grp["gameday"].min()
        if pd.isna(cutoff):
            continue
        train = reg[(reg["gameday"] < cutoff)]
        if len(train) < 400:
            continue
        r = fit(train, cutoff, half_life_days, lam)
        for g in grp.itertuples():
            pm, pt = r.predict(g.home_team, g.away_team)
            rows.append({
                "season": int(season), "week": int(week), "game_id": g.game_id,
                "home_team": g.home_team, "away_team": g.away_team,
                "model_margin": pm, "model_total": pt,
                "market_margin": g.spread_line, "market_total": g.total_line,
                "result": g.result, "total": g.total,
                "hfa": r.hfa, "mu": r.mu,
            })
    return pd.DataFrame(rows)
