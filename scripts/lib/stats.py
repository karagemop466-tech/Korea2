#!/usr/bin/env python3
"""Small, auditable statistics helpers used by every strategy test.

Nothing here is NFL-specific. Each function is deliberately explicit so a reviewer can check the
arithmetic against a textbook. Methods are cited in docs/METHODOLOGY.md.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps


# ---------------------------------------------------------------- proportions
def wilson_ci(k: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (Wilson 1927)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def binomial_p(k: int, n: int, p0: float = 0.5) -> float:
    """Two-sided exact binomial test p-value against p0."""
    if n == 0:
        return float("nan")
    res = sps.binomtest(int(k), int(n), p0, alternative="two-sided")
    return float(res.pvalue)


def min_sample_size(p1: float, p0: float, alpha: float = 0.05, power: float = 0.80) -> int:
    """Bets needed to detect a true rate p1 against a null rate p0 (two-sided, normal approx)."""
    if p0 <= 0 or p0 >= 1 or p1 <= 0 or p1 >= 1:
        return -1
    z_a = sps.norm.ppf(1 - alpha / 2)
    z_b = sps.norm.ppf(power)
    pbar = (p0 + p1) / 2
    num = (z_a * math.sqrt(2 * pbar * (1 - pbar)) + z_b * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2
    return int(math.ceil(num / (p1 - p0) ** 2))


# ---------------------------------------------------------------- returns
def bootstrap_mean_ci(x: np.ndarray, iters: int = 10000, alpha: float = 0.05, seed: int = 20261101):
    """Percentile bootstrap CI for the mean of x (units of profit per 1 unit staked)."""
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, x.size, size=(iters, x.size))
    means = x[idx].mean(axis=1)
    return (float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2)))


def bootstrap_sharpe_ci(x: np.ndarray, iters: int = 10000, alpha: float = 0.05, seed: int = 20261101):
    x = np.asarray(x, dtype=float)
    if x.size < 3 or x.std(ddof=1) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, x.size, size=(iters, x.size))
    s = x[idx]
    sr = s.mean(axis=1) / s.std(axis=1, ddof=1)
    return (float(np.quantile(sr, alpha / 2)), float(np.quantile(sr, 1 - alpha / 2)))


# ---------------------------------------------------------------- multiple testing
def benjamini_hochberg(pvals: list[float], q: float = 0.10) -> dict:
    """BH step-up FDR control (Benjamini & Hochberg 1995). Returns adjusted p-values + rejects."""
    p = np.asarray([1.0 if v is None or (isinstance(v, float) and math.isnan(v)) else v for v in pvals],
                   dtype=float)
    m = p.size
    order = np.argsort(p)
    ranked = p[order]
    adj = ranked * m / (np.arange(1, m + 1))
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.clip(adj, 0, 1)
    out = np.empty(m)
    out[order] = adj
    return {
        "q_threshold": q,
        "adjusted": [float(v) for v in out],
        "reject": [bool(v <= q) for v in out],
        "n_tests": int(m),
    }


def deflated_sharpe(observed_sr: float, n_obs: int, n_trials: int, sr_var: float | None = None) -> dict:
    """Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014).

    Returns the probability that the observed Sharpe would have been beaten by the best of
    `n_trials` strategies that in truth have zero skill. Low p => unlikely to be a multiple-testing
    artefact.
    """
    if n_obs < 3 or n_trials < 1:
        return {"deflated_p": float("nan")}
    emc = 0.5772156649
    e_max = ((1 - emc) * sps.norm.ppf(1 - 1 / n_trials) + emc * sps.norm.ppf(1 - 1 / (n_trials * math.e)))
    var_sr = sr_var if sr_var is not None else 1.0 / n_obs
    sr0 = math.sqrt(max(var_sr, 1e-12)) * e_max
    se = math.sqrt(max(var_sr, 1e-12))
    z = (observed_sr - sr0) / se
    return {"expected_max_sr_under_null": float(sr0), "z": float(z),
            "deflated_p": float(1 - sps.norm.cdf(z)), "n_trials": int(n_trials)}


# ---------------------------------------------------------------- correlation
def pearson_ci(r: float, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Fisher z CI for a Pearson correlation."""
    if n <= 3 or not np.isfinite(r) or abs(r) >= 1:
        return (float("nan"), float("nan"))
    z = math.atanh(r)
    se = 1 / math.sqrt(n - 3)
    zc = sps.norm.ppf(1 - alpha / 2)
    return (float(math.tanh(z - zc * se)), float(math.tanh(z + zc * se)))


def corr_pair(x: np.ndarray, y: np.ndarray, min_n: int = 30) -> dict:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    n = int(x.size)
    if n < min_n or x.std() == 0 or y.std() == 0:
        return {"n": n, "r": None, "p": None, "ci_low": None, "ci_high": None,
                "status": "insufficient_data"}
    r, p = sps.pearsonr(x, y)
    lo, hi = pearson_ci(float(r), n)
    return {"n": n, "r": float(r), "p": float(p), "ci_low": lo, "ci_high": hi,
            "r2": float(r) ** 2, "status": "measured"}


# ---------------------------------------------------------------- misc
def american_to_decimal(ml: float) -> float:
    ml = float(ml)
    return 1 + (ml / 100 if ml > 0 else 100 / abs(ml))


def decimal_to_american(dec: float) -> float:
    if dec >= 2:
        return round((dec - 1) * 100, 0)
    return round(-100 / (dec - 1), 0)


def implied_prob(dec_odds: float) -> float:
    return 1.0 / dec_odds


def devig_multiplicative(probs: list[float]) -> list[float]:
    """Proportional (normalised) devig - the simplest of the standard methods."""
    s = sum(probs)
    return [p / s for p in probs] if s > 0 else probs


def devig_shin(probs: list[float], iters: int = 200) -> list[float]:
    """Shin (1993) devig: solves for the insider-trading parameter z, then removes the margin."""
    s = sum(probs)
    if s <= 1:
        return devig_multiplicative(probs)

    def implied(z: float) -> list[float]:
        return [(math.sqrt(z * z + 4 * (1 - z) * (p ** 2 / s)) - z) / (2 * (1 - z)) for p in probs]

    lo, hi = 0.0, 0.5
    for _ in range(iters):
        mid = (lo + hi) / 2
        if sum(implied(mid)) > 1:
            lo = mid
        else:
            hi = mid
    return implied((lo + hi) / 2)
