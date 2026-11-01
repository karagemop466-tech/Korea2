"""Shared data loading, modelling and statistics helpers.

Design rules enforced here (see METHODS on the site):
  * Walk-forward only: a prediction for a game may use games that kicked off
    strictly before it. Nothing peeks.
  * Discovery / validation split: DISCOVERY seasons <= 2015, VALIDATION >= 2016.
  * Odds are the American prices recorded in the source extract; every bet is
    settled at the recorded price, never at an assumed -110.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"
DERIVED.mkdir(parents=True, exist_ok=True)

DISCOVERY_END = 2015          # inclusive
FIRST_EVAL_SEASON = 2002      # model burn-in
RATING_HALF_LIFE_YEARS = 1.15

FRANCHISE = {"OAK": "LV", "SD": "LAC", "STL": "LA"}  # continuity across relocations
TEAM_NAMES = {}


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #
def load_games() -> pd.DataFrame:
    df = pd.read_csv(RAW / "games.csv")
    df = df[df["home_score"].notna() & df["away_score"].notna()].copy()
    df["home_team"] = df["home_team"].replace(FRANCHISE)
    df["away_team"] = df["away_team"].replace(FRANCHISE)
    for c in ("home_score", "away_score", "spread_line", "total_line",
              "away_moneyline", "home_moneyline", "away_spread_odds",
              "home_spread_odds", "over_odds", "under_odds", "away_rest",
              "home_rest", "temp", "wind", "div_game"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["gameday"] = pd.to_datetime(df["gameday"])
    df = df.sort_values(["gameday", "game_id"]).reset_index(drop=True)
    df["home_margin"] = df["home_score"] - df["away_score"]
    df["total"] = df["home_score"] + df["away_score"]
    # market convention: home_line < 0 => home is favoured
    df["home_line"] = -df["spread_line"]
    df["ats_home_margin"] = df["home_margin"] + df["home_line"]
    df["over_margin"] = df["total"] - df["total_line"]
    return df


def load_unplayed() -> pd.DataFrame:
    df = pd.read_csv(RAW / "games.csv")
    df = df[df["home_score"].isna()].copy()
    df["home_team"] = df["home_team"].replace(FRANCHISE)
    df["away_team"] = df["away_team"].replace(FRANCHISE)
    for c in ("spread_line", "total_line", "away_moneyline", "home_moneyline",
              "away_spread_odds", "home_spread_odds", "over_odds", "under_odds",
              "away_rest", "home_rest"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["gameday"] = pd.to_datetime(df["gameday"])
    return df.sort_values(["gameday", "game_id"]).reset_index(drop=True)


def load_player_weeks() -> pd.DataFrame:
    frames = []
    for p in sorted((RAW / "player").glob("weekly_stats_*.csv")):
        frames.append(pd.read_csv(p, low_memory=False))
    df = pd.concat(frames, ignore_index=True)
    df["recent_team"] = df["recent_team"].replace(FRANCHISE)
    df["opponent_team"] = df["opponent_team"].replace(FRANCHISE)
    return df


# --------------------------------------------------------------------------- #
# walk-forward rating model
# --------------------------------------------------------------------------- #
def _design(rows: pd.DataFrame, teams: list[str], tix: dict[str, int]):
    """Stacked two-equation design matrix (home equation, away equation).

    NOTE: the row selectors are explicit index ARRAYS, not slices. Indexing with
    `X[0::2, 2+h]` would broadcast into a (n, n) block and silently fill the whole
    matrix - a bug this project found and fixed during verification.
    """
    n = len(rows)
    k = 2 + 2 * len(teams) + 1          # mu, hfa, off*, def*, rest_diff
    base = 2 + len(teams)
    h = rows["home_team"].map(tix).to_numpy(dtype=int)
    a = rows["away_team"].map(tix).to_numpy(dtype=int)
    rd = rows["rest_diff"].to_numpy(dtype=float)
    ev = np.arange(0, 2 * n, 2)
    od = np.arange(1, 2 * n, 2)
    X = np.zeros((2 * n, k))
    X[ev, 0] = 1.0
    X[ev, 1] = 1.0
    X[ev, 2 + h] = 1.0
    X[ev, base + a] = -1.0
    X[ev, -1] = rd
    X[od, 0] = 1.0
    X[od, 2 + a] = 1.0
    X[od, base + h] = -1.0
    X[od, -1] = -rd
    y = np.empty(2 * n)
    y[ev] = rows["home_score"].to_numpy(dtype=float)
    y[od] = rows["away_score"].to_numpy(dtype=float)
    w = np.empty(2 * n)
    w[ev] = rows["w"].to_numpy(dtype=float)
    w[od] = rows["w"].to_numpy(dtype=float)
    return X, y, w, k


def _fit(rows, teams, tix, lam=6.0, prior=None, lam_prior=2.0):
    X, y, w, k = _design(rows, teams, tix)
    XtW = X.T * w
    A = XtW @ X
    b = XtW @ y
    nt = len(teams)
    P = np.zeros(k)
    d = np.zeros(k)
    for j in range(2, 2 + 2 * nt):
        P[j] += lam
        if prior is not None:
            P[j] += lam_prior
            d[j] += lam_prior * prior[j]
    beta = np.linalg.solve(A + np.diag(P), b + d)
    return beta


def walk_forward_predictions(games: pd.DataFrame) -> pd.DataFrame:
    """Return pred_home_score / pred_away_score / pred_margin / pred_total per game.

    For every (season, week) block the ratings are fitted on all games that
    kicked off in an earlier week, with exponential recency weights, then the
    block is predicted. Nothing from the block itself enters its own fit.
    """
    teams = sorted(set(games.home_team) | set(games.away_team))
    tix = {t: i for i, t in enumerate(teams)}
    g = games.copy().reset_index(drop=True)
    g["rest_diff"] = (g["home_rest"].fillna(7) - g["away_rest"].fillna(7)).clip(-14, 14)
    g["w"] = 1.0
    base = 2 + len(teams)
    out = np.full((len(g), 2), np.nan)
    prior = None
    beta = None
    for season, sdf in g.groupby("season", sort=True):
        for wk, wdf in sdf.groupby("week", sort=True):
            train = g[(g.season < season) | ((g.season == season) & (g.week < wk))]
            if len(train) >= 200:
                asof = train["gameday"].max()
                tr = train.copy()
                tr["w"] = np.exp(-math.log(2) *
                                 (asof - tr["gameday"]).dt.days.to_numpy() / 365.25
                                 / RATING_HALF_LIFE_YEARS)
                beta = _fit(tr, teams, tix, prior=prior)
            if beta is None:
                continue
            h = wdf["home_team"].map(tix).to_numpy()
            a = wdf["away_team"].map(tix).to_numpy()
            rd = wdf["rest_diff"].to_numpy(dtype=float)
            ph = beta[0] + beta[1] + beta[2 + h] - beta[base + a] + beta[-1] * rd
            pa = beta[0] + beta[2 + a] - beta[base + h] - beta[-1] * rd
            out[wdf.index.to_numpy(), 0] = ph
            out[wdf.index.to_numpy(), 1] = pa
        if beta is not None:   # carry a shrunk prior into the next season
            nb = len(teams)
            prior = np.zeros(2 + 2 * nb + 1)
            prior[2:2 + nb] = 0.6 * beta[2:2 + nb]
            prior[2 + nb:2 + 2 * nb] = 0.6 * beta[2 + nb:2 + 2 * nb]
            prior[0] = beta[0]
            prior[1] = beta[1]
    res = g[["game_id", "season", "week", "gameday", "home_team", "away_team"]].copy()
    res["pred_home_score"] = out[:, 0]
    res["pred_away_score"] = out[:, 1]
    res["pred_margin"] = res.pred_home_score - res.pred_away_score
    res["pred_total"] = res.pred_home_score + res.pred_away_score
    return res


def current_ratings(games: pd.DataFrame, asof: pd.Timestamp | None = None) -> dict:
    """Fit on every game played so far; return the parameter vector + helper."""
    teams = sorted(set(games.home_team) | set(games.away_team))
    tix = {t: i for i, t in enumerate(teams)}
    g = games.copy()
    g["rest_diff"] = (g["home_rest"].fillna(7) - g["away_rest"].fillna(7)).clip(-14, 14)
    asof = asof or g["gameday"].max()
    age = (asof - g["gameday"]).dt.days / 365.25
    g["w"] = np.exp(-math.log(2) * age / RATING_HALF_LIFE_YEARS)
    beta = _fit(g, teams, tix)
    nb = len(teams)
    return {
        "teams": teams, "tix": tix, "beta": beta,
        "off": {t: beta[2 + tix[t]] for t in teams},
        "def": {t: beta[2 + nb + tix[t]] for t in teams},
        "mu": beta[0], "hfa": beta[1], "rest_coef": beta[-1],
        "asof": asof,
    }


def predict_with(ratings: dict, home: str, away: str, rest_diff: float = 0.0):
    tix, beta, nb = ratings["tix"], ratings["beta"], len(ratings["teams"])
    h, a = tix[home], tix[away]
    ph = beta[0] + beta[1] + beta[2 + h] - beta[2 + nb + a] + beta[-1] * rest_diff
    pa = beta[0] + beta[2 + a] - beta[2 + nb + h] - beta[-1] * rest_diff
    return ph, pa


# --------------------------------------------------------------------------- #
# odds & settlement
# --------------------------------------------------------------------------- #
def american_to_decimal(a: float) -> float:
    a = float(a)
    return 1.0 + (a / 100.0 if a > 0 else 100.0 / abs(a))


def american_to_prob(a: float) -> float:
    """Implied probability ignoring the vig."""
    a = float(a)
    return 100.0 / (a + 100.0) if a > 0 else abs(a) / (abs(a) + 100.0)


def settle(american_odds: float, won: bool) -> float:
    """Profit in units for a 1-unit stake."""
    dec = american_to_decimal(american_odds)
    return (dec - 1.0) if won else -1.0


def moneyline_odds(prob: float, cap: float = 2000) -> int:
    prob = min(max(prob, 1e-4), 1 - 1e-4)
    if prob >= 0.5:
        v = -100.0 * prob / (1 - prob)
    else:
        v = 100.0 * (1 - prob) / prob
    v = int(round(v))
    if v > 0:
        v = min(v, cap)
    else:
        v = max(v, -cap)
    if -100 < v < 0:
        v = -100
    if 0 < v < 100:
        v = 100
    return v


# --------------------------------------------------------------------------- #
# statistics
# --------------------------------------------------------------------------- #
def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - half) / denom, (centre + half) / denom)


def binom_p_greater(k: int, n: int, p0: float = 0.5) -> float:
    """One-sided exact binomial p-value for H1: p > p0."""
    if n == 0:
        return float("nan")
    from scipy.stats import binom
    return float(binom.sf(k - 1, n, p0))


def binom_p_two_sided_normal(k: int, n: int, p0: float = 0.5) -> float:
    if n == 0:
        return float("nan")
    from scipy.stats import norm as _norm
    p = k / n
    se = math.sqrt(p0 * (1 - p0) / n)
    if se == 0:
        return float("nan")
    z = (p - p0) / se
    return float(2 * (1 - _norm.cdf(abs(z))))


def bh_qvalues(pvals):
    """Benjamini-Hochberg FDR adjusted q-values."""
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order]
    q = np.empty(n)
    prev = 1.0
    for i in range(n - 1, -1, -1):
        val = min(prev, ranked[i] * n / (i + 1))
        q[order[i]] = val
        prev = val
    return q


def bootstrap_ci(returns: np.ndarray, n_boot: int = 4000, seed: int = 7):
    rng = np.random.default_rng(seed)
    if len(returns) == 0:
        return (float("nan"), float("nan"))
    means = np.array([rng.choice(returns, size=len(returns), replace=True).mean()
                      for _ in range(n_boot)])
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def t_stat(returns: np.ndarray) -> float:
    if len(returns) < 3:
        return float("nan")
    s = returns.std(ddof=1)
    if s == 0:
        return float("nan")
    return float(returns.mean() / (s / math.sqrt(len(returns))))


def max_drawdown(returns: np.ndarray) -> float:
    if len(returns) == 0:
        return 0.0
    cum = np.cumsum(returns)
    peak = np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:]
    return float(np.max(peak - cum))


# --------------------------------------------------------------------------- #
# team-game long format with causal rolling features
# --------------------------------------------------------------------------- #
def team_games(games: pd.DataFrame) -> pd.DataFrame:
    """One row per team per game with rolling, strictly-prior features."""
    rows = []
    for _, r in games.iterrows():
        rows.append(dict(game_id=r.game_id, season=r.season, week=r.week,
                         gameday=r.gameday, team=r.home_team, opp=r.away_team,
                         is_home=True, pts=r.home_score, opp_pts=r.away_score,
                         margin=r.home_margin,
                         ats_result=(r.ats_home_margin if pd.notna(r.ats_home_margin) else np.nan),
                         total=r.total, total_line=r.total_line,
                         qb=r.home_qb_id, rest=r.home_rest,
                         over_result=(np.sign(r.over_margin) if pd.notna(r.over_margin) else np.nan)))
        rows.append(dict(game_id=r.game_id, season=r.season, week=r.week,
                         gameday=r.gameday, team=r.away_team, opp=r.home_team,
                         is_home=False, pts=r.away_score, opp_pts=r.home_score,
                         margin=-r.home_margin,
                         ats_result=(-r.ats_home_margin if pd.notna(r.ats_home_margin) else np.nan),
                         total=r.total, total_line=r.total_line,
                         qb=r.away_qb_id, rest=r.away_rest,
                         over_result=(np.sign(r.over_margin) if pd.notna(r.over_margin) else np.nan)))
    tg = pd.DataFrame(rows).sort_values(["gameday", "game_id"]).reset_index(drop=True)
    grp = tg.groupby("team", sort=False)
    tg["prev_margin"] = grp["margin"].shift(1)
    tg["prev2_margin"] = grp["margin"].shift(2)
    tg["form3"] = grp["margin"].transform(
        lambda s: s.shift(1).rolling(3, min_periods=2).mean())
    tg["form8"] = grp["margin"].transform(
        lambda s: s.shift(1).rolling(8, min_periods=4).mean())
    tg["ats_form5"] = grp["ats_result"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=3).mean())
    tg["pts_for4"] = grp["pts"].transform(lambda s: s.shift(1).rolling(4, min_periods=2).mean())
    tg["pts_ag4"] = grp["opp_pts"].transform(lambda s: s.shift(1).rolling(4, min_periods=2).mean())
    tg["qb_prev"] = grp["qb"].shift(1)
    tg["qb_changed"] = ((tg["qb"].notna()) & (tg["qb_prev"].notna())
                        & (tg["qb"] != tg["qb_prev"])).astype(int)
    tg["games_played"] = grp.cumcount()
    return tg


def attach_team_features(games: pd.DataFrame, tg: pd.DataFrame) -> pd.DataFrame:
    home = tg[tg.is_home].set_index("game_id")
    away = tg[~tg.is_home].set_index("game_id")
    out = games.copy()
    for col in ("form3", "form8", "ats_form5", "pts_for4", "pts_ag4",
                "qb_changed", "games_played", "pts_for4"):
        out["h_" + col] = out.game_id.map(home[col])
        out["a_" + col] = out.game_id.map(away[col])
    return out
