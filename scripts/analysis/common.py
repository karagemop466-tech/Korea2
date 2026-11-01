"""Shared helpers: paths, loaders, and the statistics used across the project.

Everything here is deterministic and reads only from files in this repository,
so every published number can be re-derived with `python -m scripts.analysis.build`.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"
RESULTS = ROOT / "results"

# ---------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------
NFLVERSE = "https://github.com/nflverse/nflverse-data/releases/download"

SOURCES = {
    "games": f"{NFLVERSE}/schedules/games.csv",
    "team_week": NFLVERSE + "/stats_team/stats_team_week_{year}.csv",
    "player_week": NFLVERSE + "/stats_player/stats_player_week_{year}.csv",
}

# Official NFL destinations used as the "check it yourself" link for each
# computed figure. These are official league properties.
NFL_SCHEDULE = "https://www.nfl.com/schedules/{season}/by-week/week-{week}"
NFL_GAME = "https://www.nfl.com/games/{away}-at-{home}-{season}-reg-{week}"

SEASONS_TEAM = list(range(2015, 2027))
SEASONS_PLAYER = list(range(2015, 2027))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# loaders
# ---------------------------------------------------------------------------
def load_games() -> pd.DataFrame:
    path = DERIVED / "games.csv.gz"
    if not path.exists():
        path = RAW / "games.csv"
    return pd.read_csv(path, low_memory=False)


def load_team_week() -> pd.DataFrame:
    path = DERIVED / "team_week.csv.gz"
    if path.exists():
        return pd.read_csv(path, low_memory=False)
    frames = [pd.read_csv(p, low_memory=False) for p in sorted(RAW.glob("stats_team_week_*.csv"))]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_player_week(seasons: list[int] | None = None) -> pd.DataFrame:
    path = DERIVED / "player_week.csv.gz"
    if path.exists():
        df = pd.read_csv(path, low_memory=False)
        if seasons:
            df = df[df.season.isin(seasons)]
        return df
    frames = []
    for p in sorted(RAW.glob("stats_player_week_*.csv")):
        try:
            df = pd.read_csv(p, low_memory=False)
        except Exception:
            continue
        if len(df):
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---------------------------------------------------------------------------
# odds / payouts
# ---------------------------------------------------------------------------
def american_to_decimal(odds):
    """Convert American odds to decimal odds. -110 -> 1.909..., +150 -> 2.5"""
    odds = np.asarray(odds, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(odds < 0, 1.0 + 100.0 / np.abs(odds), 1.0 + odds / 100.0)
    return out


def implied_prob(odds):
    """Vig-inclusive implied probability from American odds."""
    odds = np.asarray(odds, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(odds < 0, np.abs(odds) / (np.abs(odds) + 100.0), 100.0 / (odds + 100.0))


def bet_return(win: np.ndarray, push: np.ndarray, odds: np.ndarray) -> np.ndarray:
    """Profit per 1 unit staked. win/push are boolean arrays."""
    dec = american_to_decimal(odds)
    return np.where(push, 0.0, np.where(win, dec - 1.0, -1.0))


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------
def t_stat(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    if len(x) < 2 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x))))


def p_from_t(t: float, n: int) -> float:
    """Two-sided p-value from a t statistic without SciPy (Student t)."""
    if not np.isfinite(t) or n < 3:
        return float("nan")
    try:
        from scipy import stats  # optional

        return float(2 * stats.t.sf(abs(t), df=n - 1))
    except Exception:  # normal approximation fallback
        from math import erfc

        return float(erfc(abs(t) / math.sqrt(2)))


def bootstrap_ci(x: np.ndarray, n_boot: int = 10000, alpha: float = 0.05, seed: int = 7):
    x = np.asarray(x, dtype=float)
    if len(x) < 5:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    means = x[idx].mean(axis=1)
    return (float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2)))


def required_n(mean: float, sd: float, alpha: float = 0.05) -> float:
    """Minimum sample size for the observed effect to reach two-sided significance.

    n* = (z_{1-alpha/2} * sd / mean)^2  (NIST/SEMATECH e-Handbook 7.2.4.2 style
    sample-size calculation for a one-sample test on the mean).
    """
    if not np.isfinite(mean) or mean == 0 or sd == 0:
        return float("inf")
    z = 1.959963984540054 if alpha == 0.05 else _z(1 - alpha / 2)
    return float((z * sd / mean) ** 2)


def _z(p: float) -> float:
    """Inverse standard normal (Acklam's algorithm, adequate for p in (0,1))."""
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def permutation_p(bet_returns: np.ndarray, all_returns: np.ndarray, n_perm: int = 20000,
                  seed: int = 11) -> float:
    """Luck test.

    Null: choosing *which* games to bet carried no information, so the strategy's
    realised ROI is a draw from repeatedly taking `k` random games at the same
    prices (k = number of bets the strategy placed). Returns the share of random
    portfolios that matched or beat the strategy.
    """
    rng = np.random.default_rng(seed)
    k = len(bet_returns)
    if k == 0 or len(all_returns) <= k:
        return float("nan")
    obs = bet_returns.mean()
    draws = rng.choice(all_returns, size=(n_perm, k), replace=True).mean(axis=1)
    return float((draws >= obs).mean())


def bh_fdr(pvals: list[float], q: float = 0.10) -> list[bool]:
    """Benjamini-Hochberg step-up. Returns a keep/reject mask."""
    m = len(pvals)
    order = np.argsort(pvals)
    keep = np.zeros(m, dtype=bool)
    thresh = -1
    for rank, idx in enumerate(order, start=1):
        p = pvals[idx]
        if np.isfinite(p) and p <= q * rank / m:
            thresh = rank
    for rank, idx in enumerate(order, start=1):
        if rank <= thresh:
            keep[idx] = True
    return keep.tolist()


def bootstrap_max_drawdown(returns: np.ndarray, seed: int = 3) -> float:
    if len(returns) == 0:
        return float("nan")
    eq = np.cumsum(np.asarray(returns, dtype=float))
    return float(np.max(np.maximum.accumulate(eq) - eq))


def summarise_returns(returns: np.ndarray, label: str = "") -> dict:
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    n = int(len(r))
    if n == 0:
        return {"label": label, "n": 0}
    mean = float(r.mean())
    sd = float(r.std(ddof=1)) if n > 1 else float("nan")
    t = t_stat(r)
    lo, hi = bootstrap_ci(r)
    return {
        "label": label,
        "n": n,
        "roi": mean,
        "sd": sd,
        "t": t,
        "p": p_from_t(t, n),
        "ci_lo": lo,
        "ci_hi": hi,
        "max_dd": bootstrap_max_drawdown(r),
        "req_n": required_n(mean, sd) if n > 1 else float("inf"),
        "units": float(r.sum()),
    }


def jdump(obj, path: Path, indent: int = 1):
    path.parent.mkdir(parents=True, exist_ok=True)

    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return None if not np.isfinite(float(o)) else round(float(o), 6)
        if isinstance(o, float):
            return None if not math.isfinite(o) else round(o, 6)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if o is pd.NA:
            return None
        return o

    path.write_text(json.dumps(clean(obj), indent=indent) + "\n")


def jload(name: str):
    p = RESULTS / name
    if not p.exists():
        return None
    return json.loads(p.read_text())
