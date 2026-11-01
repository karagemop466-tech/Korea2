"""Shared helpers: paths, odds maths, JSON output, statistics primitives."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
SITE = ROOT / "origination"
SITE_DATA = SITE / "site_data"
for _p in (INTERIM, SITE_DATA):
    _p.mkdir(parents=True, exist_ok=True)

RNG = np.random.default_rng(20261101)


# --------------------------------------------------------------------------- io
def read_csv(name: str, **kw) -> pd.DataFrame:
    path = RAW / name
    if not path.exists():
        raise FileNotFoundError(f"{path} missing - run pipeline/fetch_data.py first")
    return pd.read_csv(path, **kw)


def write_json(name: str, obj) -> Path:
    path = SITE_DATA / name
    path.write_text(json.dumps(obj, indent=1, default=_json_default) + "\n")
    return path


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        v = float(o)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (pd.Timestamp,)):
        return o.strftime("%Y-%m-%d")
    raise TypeError(type(o))


# ------------------------------------------------------------------------ odds
def american_to_decimal(odds: float) -> float:
    """American odds -> decimal payout multiplier (stake included)."""
    if odds is None or (isinstance(odds, float) and math.isnan(odds)) or odds == 0:
        return float("nan")
    return 1.0 + (odds / 100.0 if odds > 0 else 100.0 / abs(odds))


def american_to_prob(odds: float) -> float:
    """Raw (vig-inclusive) implied probability of American odds."""
    if odds is None or (isinstance(odds, float) and math.isnan(odds)) or odds == 0:
        return float("nan")
    return 100.0 / (odds + 100.0) if odds > 0 else abs(odds) / (abs(odds) + 100.0)


def devig_two_way(p_a: float, p_b: float) -> tuple[float, float]:
    """Multiplicative de-vig of a two-way market."""
    s = p_a + p_b
    return p_a / s, p_b / s


def payout_units(odds: float) -> float:
    """Profit in units for a 1-unit win."""
    return american_to_decimal(odds) - 1.0


# ------------------------------------------------------------------ statistics
def bootstrap_mean_ci(x: np.ndarray, n_boot: int = 10000, alpha: float = 0.05,
                      seed: int = 7) -> tuple[float, float, float]:
    """Percentile bootstrap CI of the mean. Returns (mean, lo, hi)."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if x.size == 0:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, x.size, size=(n_boot, x.size))
    means = x[idx].mean(axis=1)
    return float(x.mean()), float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def bootstrap_stat_ci(x: np.ndarray, stat, n_boot: int = 4000, alpha: float = 0.05,
                      seed: int = 11) -> tuple[float, float, float]:
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if x.size < 5:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    vals = np.array([stat(x[rng.integers(0, x.size, x.size)]) for _ in range(n_boot)])
    return float(stat(x)), float(np.quantile(vals, alpha / 2)), float(np.quantile(vals, 1 - alpha / 2))


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    p, y = np.asarray(p, float), np.asarray(y, float)
    return float(np.mean((p - y) ** 2))


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def probit(p: float) -> float:
    """Inverse normal CDF (Acklam-free, bisection is fine at this precision)."""
    lo, hi = -8.0, 8.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if normal_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def deflated_sharpe_ratio(returns: np.ndarray, n_trials: int,
                          sr_variance_across_trials: float | None = None) -> dict:
    """Bailey & Lopez de Prado (2014) deflated Sharpe ratio.

    ``returns`` are per-bet P&L in units. ``n_trials`` is the number of strategy
    configurations that were searched before this one was selected.
    """
    r = np.asarray(returns, float)
    r = r[~np.isnan(r)]
    n = r.size
    if n < 10:
        return {"n": n, "sr": None, "dsr": None}
    mu, sd = r.mean(), r.std(ddof=1)
    if sd == 0:
        return {"n": n, "sr": None, "dsr": None}
    sr = mu / sd  # per-bet Sharpe (not annualised)
    skew = float(pd.Series(r).skew())
    kurt = float(pd.Series(r).kurt()) + 3.0  # pandas gives excess kurtosis
    # variance of the Sharpe estimator across trials (unknown) -> use the null variance
    var_sr = sr_variance_across_trials if sr_variance_across_trials else (1.0 / n)
    e_max = math.sqrt(var_sr) * (
        (1 - np.euler_gamma) * probit(1 - 1.0 / n_trials)
        + np.euler_gamma * probit(1 - 1.0 / (n_trials * math.e))
    )
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4.0 * sr ** 2))
    dsr = normal_cdf((sr - e_max) * math.sqrt(n - 1) / denom)
    return {"n": int(n), "sr": sr, "e_max_sr": e_max, "skew": skew, "kurtosis": kurt,
            "n_trials": int(n_trials), "dsr": dsr}


def bh_qvalues(pvals: list[float]) -> list[float]:
    """Benjamini-Hochberg adjusted p-values (q-values)."""
    p = np.asarray(pvals, float)
    ok = ~np.isnan(p)
    q = np.full_like(p, np.nan)
    if ok.sum() == 0:
        return list(q)
    pv = p[ok]
    order = np.argsort(pv)
    m = pv.size
    ranked = pv[order]
    adj = ranked * m / (np.arange(1, m + 1))
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.clip(adj, 0, 1)
    out = np.empty_like(pv)
    out[order] = adj
    q[ok] = out
    return list(q)
