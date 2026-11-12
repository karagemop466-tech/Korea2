#!/usr/bin/env python3
"""Shared statistical, financial, and strict-JSON utilities for Lineup Lab.

Pure Python 3.11 standard library implementation so every analytical script runs
identically in the offline sandbox and GitHub Actions without third-party wheels.
"""
from __future__ import annotations

import csv
import gzip
import json
import math
from pathlib import Path
from typing import Any, Iterable

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent
DERIVED_DIR = REPO_ROOT / "data" / "derived"
DATA_DIR = LAB_ROOT / "data"
PAGES_DIR = LAB_ROOT / "pages"
VERIFIED_DATE = "2026-11-12"

# Exact team code standardization across 2015-2026 extracts and NFL.com
TEAM_NORMALIZE = {
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LA",
    "LAR": "LA",
    "AZ": "ARI",
    "WSH": "WAS",
}

# Official 16 completed 2026 games after 2026-11-01 (Week 8 MNF + all 15 Week 9 finals)
# Verified directly from https://www.nfl.com/schedules/2026/by-week/week-8 and week-9 on 2026-11-12
OFFICIAL_2026_POST_NOV1_FINALS = [
    {"game_id": "2026_08_CHI_SEA", "week": 8, "gameday": "2026-11-02", "away_team": "CHI", "away_score": 34, "home_team": "SEA", "home_score": 17, "note": "Week 8 MNF"},
    {"game_id": "2026_09_JAX_BAL", "week": 9, "gameday": "2026-11-05", "away_team": "JAX", "away_score": 33, "home_team": "BAL", "home_score": 10, "note": "Week 9 TNF (BAL 3rd-string QB Joe Fagnano started)"},
    {"game_id": "2026_09_CIN_ATL", "week": 9, "gameday": "2026-11-08", "away_team": "CIN", "away_score": 34, "home_team": "ATL", "home_score": 17, "note": "Week 9 Madrid International"},
    {"game_id": "2026_09_DEN_CAR", "week": 9, "gameday": "2026-11-08", "away_team": "DEN", "away_score": 26, "home_team": "CAR", "home_score": 21, "note": "Week 9"},
    {"game_id": "2026_09_DAL_IND", "week": 9, "gameday": "2026-11-08", "away_team": "DAL", "away_score": 27, "home_team": "IND", "home_score": 23, "note": "Week 9"},
    {"game_id": "2026_09_NYJ_KC",  "week": 9, "gameday": "2026-11-08", "away_team": "NYJ", "away_score": 12, "home_team": "KC",  "home_score": 35, "note": "Week 9"},
    {"game_id": "2026_09_DET_MIA", "week": 9, "gameday": "2026-11-08", "away_team": "DET", "away_score": 19, "home_team": "MIA", "home_score": 9,  "note": "Week 9 (MIA QB1 Malik Willis injured)"},
    {"game_id": "2026_09_CLE_NO",  "week": 9, "gameday": "2026-11-08", "away_team": "CLE", "away_score": 22, "home_team": "NO",  "home_score": 23, "note": "Week 9 (CLE QB Shedeur Sanders started)"},
    {"game_id": "2026_09_NYG_PHI", "week": 9, "gameday": "2026-11-08", "away_team": "NYG", "away_score": 19, "home_team": "PHI", "home_score": 11, "note": "Week 9"},
    {"game_id": "2026_09_LA_WAS",  "week": 9, "gameday": "2026-11-08", "away_team": "LA",  "away_score": 20, "home_team": "WAS", "home_score": 13, "note": "Week 9"},
    {"game_id": "2026_09_HOU_LAC", "week": 9, "gameday": "2026-11-08", "away_team": "HOU", "away_score": 44, "home_team": "LAC", "home_score": 22, "note": "Week 9"},
    {"game_id": "2026_09_LV_SF",   "week": 9, "gameday": "2026-11-08", "away_team": "LV",  "away_score": 17, "home_team": "SF",  "home_score": 38, "note": "Week 9"},
    {"game_id": "2026_09_GB_NE",   "week": 9, "gameday": "2026-11-08", "away_team": "GB",  "away_score": 45, "home_team": "NE",  "home_score": 27, "note": "Week 9"},
    {"game_id": "2026_09_ARI_SEA", "week": 9, "gameday": "2026-11-08", "away_team": "ARI", "away_score": 3,  "home_team": "SEA", "home_score": 17, "note": "Week 9"},
    {"game_id": "2026_09_TB_CHI",  "week": 9, "gameday": "2026-11-08", "away_team": "TB",  "away_score": 24, "home_team": "CHI", "home_score": 27, "note": "Week 9 SNF"},
    {"game_id": "2026_09_BUF_MIN", "week": 9, "gameday": "2026-11-09", "away_team": "BUF", "away_score": 23, "home_team": "MIN", "home_score": 6,  "note": "Week 9 MNF"},
]


def std_team(code: str) -> str:
    return TEAM_NORMALIZE.get(code, code)


def sanitize_json(obj: Any) -> Any:
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError(f"Non-finite float encountered: {obj!r}")
        return 0.0 if obj == 0.0 else obj
    if isinstance(obj, dict):
        return {str(k): sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_json(v) for v in obj]
    return obj


def write_strict_json(path: Path, payload: Any) -> None:
    clean = sanitize_json(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(clean, indent=2, allow_nan=False) + "\n"
    path.write_text(text, encoding="utf-8")


def load_strict_json(path: Path) -> Any:
    def reject(tok: str) -> None:
        raise ValueError(f"Non-standard JSON token {tok!r} in {path}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)


def load_csv_gz(filename: str) -> list[dict[str, str]]:
    path = DERIVED_DIR / filename
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def fnum(val: str | None) -> float | None:
    if val is None or val == "" or val.upper() == "NA":
        return None
    x = float(val)
    return x if math.isfinite(x) else None


def american_to_decimal(odds: float) -> float:
    if odds >= 100.0:
        return 1.0 + odds / 100.0
    if odds <= -100.0:
        return 1.0 + 100.0 / abs(odds)
    raise ValueError(f"Invalid American odds: {odds}")


def american_to_implied_prob(odds: float) -> float:
    if odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    return 100.0 / (odds + 100.0)


def decimal_to_american(dec: float) -> int:
    if dec >= 2.0:
        return int(round((dec - 1.0) * 100.0))
    return int(round(-100.0 / (dec - 1.0)))


def prob_to_fair_american(p: float) -> int:
    p_c = max(0.01, min(0.99, p))
    return decimal_to_american(1.0 / p_c)


def profit_per_unit(odds: float) -> float:
    return american_to_decimal(odds) - 1.0


def settle_spread(margin: float, spread_line: float, side: str, odds: float | None) -> tuple[str, float, float] | None:
    """Settle spread bet using proven sign convention: spread_line > 0 means home favored.

    Returns (outcome, profit, staked) or None if stored odds are missing (never imputes -110).
    """
    if odds is None:
        return None
    diff = (margin - spread_line) if side == "home" else (spread_line - margin)
    if abs(diff) < 1e-9:
        return ("push", 0.0, 0.0)
    if diff > 0:
        return ("win", profit_per_unit(odds), 1.0)
    return ("loss", -1.0, 1.0)


def settle_total(total_pts: float, total_line: float, side: str, odds: float | None) -> tuple[str, float, float] | None:
    if odds is None:
        return None
    diff = (total_pts - total_line) if side == "over" else (total_line - total_pts)
    if abs(diff) < 1e-9:
        return ("push", 0.0, 0.0)
    if diff > 0:
        return ("win", profit_per_unit(odds), 1.0)
    return ("loss", -1.0, 1.0)


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def norm_ppf(p: float) -> float:
    """Acklam inverse standard normal CDF."""
    if not (0.0 < p < 1.0):
        raise ValueError(f"Probability out of bounds: {p}")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / (
            (((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1.0)
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / (
            (((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1.0)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q / (
        (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1.0))


# 16-point Gauss-Legendre nodes/weights on [-1, 1] for bivariate normal CDF quadrature
_GL_NODES = [
    -0.9894009349916499, -0.9445750230732326, -0.8656312023878318, -0.7554044083550030,
    -0.6178762444026438, -0.4580167776572274, -0.2816035507792589, -0.0950125098376374,
     0.0950125098376374,  0.2816035507792589,  0.4580167776572274,  0.6178762444026438,
     0.7554044083550030,  0.8656312023878318,  0.9445750230732326,  0.9894009349916499,
]
_GL_WEIGHTS = [
    0.0271524594117541, 0.0622535239386479, 0.0951585116824928, 0.1246289712555339,
    0.1495959888165767, 0.1691565193950025, 0.1826034150449236, 0.1894506104550685,
    0.1894506104550685, 0.1826034150449236, 0.1691565193950025, 0.1495959888165767,
    0.1246289712555339, 0.0951585116824928, 0.0622535239386479, 0.0271524594117541,
]


def bivariate_norm_cdf(z1: float, z2: float, rho: float) -> float:
    """Compute P(Z1 <= z1, Z2 <= z2) via Drezner/Gauss-Legendre integration over [0, rho]."""
    if abs(rho) < 1e-12:
        return norm_cdf(z1) * norm_cdf(z2)
    rho = max(-0.9999, min(0.9999, rho))
    base = norm_cdf(z1) * norm_cdf(z2)
    half = 0.5 * rho
    mid = 0.5 * rho
    total = 0.0
    for node, wt in zip(_GL_NODES, _GL_WEIGHTS):
        r = mid + half * node
        omr2 = 1.0 - r * r
        expo = -(z1 * z1 - 2.0 * r * z1 * z2 + z2 * z2) / (2.0 * omr2)
        integrand = math.exp(expo) / (2.0 * math.pi * math.sqrt(omr2))
        total += wt * integrand
    return max(0.0, min(1.0, base + half * total))


def pearson_r(xs: Iterable[float], ys: Iterable[float]) -> tuple[float, int]:
    x = list(xs)
    y = list(ys)
    n = len(x)
    if n < 3:
        return (0.0, n)
    mx = sum(x) / n
    my = sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    denom = math.sqrt(sxx * syy)
    return ((sxy / denom if denom > 0 else 0.0), n)


def fisher_z_ci(r: float, n: int) -> tuple[float, float]:
    if n <= 3 or abs(r) >= 0.9999:
        return (round(r, 4), round(r, 4))
    z = 0.5 * math.log((1.0 + r) / (1.0 - r))
    se = 1.0 / math.sqrt(n - 3)
    lo = math.tanh(z - 1.959964 * se)
    hi = math.tanh(z + 1.959964 * se)
    return (round(lo, 4), round(hi, 4))


def wilson_ci(wins: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    phat = wins / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    half = (z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n)) / denom
    return (round(max(0.0, center - half), 4), round(min(1.0, center + half), 4))


def nist_prop_ztest(wins: int, n: int, p0: float = 0.5238095) -> dict[str, Any]:
    """NIST/SEMATECH Section 7.2.4 two-sided proportion z-test against break-even p0."""
    if n <= 0:
        return {"z": 0.0, "p_value": 1.0, "nist_valid": False}
    phat = wins / n
    se = math.sqrt(p0 * (1.0 - p0) / n)
    z = (phat - p0) / se if se > 0 else 0.0
    p_val = 2.0 * (1.0 - norm_cdf(abs(z)))
    valid = (n > 30) and (min(n * p0, n * (1.0 - p0)) >= 5.0)
    return {"z": round(z, 4), "p_value": round(p_val, 6), "nist_valid": valid}


def bh_fdr(p_values: list[float]) -> list[float]:
    m = len(p_values)
    if m == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda t: t[1])
    adj = [1.0] * m
    prev = 1.0
    for rank_rev, (idx, p) in enumerate(reversed(indexed)):
        rank = m - rank_rev
        val = min(prev, p * m / rank)
        adj[idx] = round(min(1.0, val), 6)
        prev = val
    return adj


def solve_linear_system(a: list[list[float]], b: list[float]) -> list[float]:
    """Solve Ax = b via Gauss-Jordan elimination with partial pivoting."""
    n = len(b)
    aug = [list(a[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(aug[r][col]))
        aug[col], aug[piv] = aug[piv], aug[col]
        div = aug[col][col]
        if abs(div) < 1e-12:
            raise ValueError("Singular matrix in linear solver")
        for j in range(col, n + 1):
            aug[col][j] /= div
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor != 0.0:
                for j in range(col, n + 1):
                    aug[r][j] -= factor * aug[col][j]
    return [aug[i][n] for i in range(n)]


def fit_ridge(X: list[list[float]], y: list[float], alpha: float) -> list[float]:
    """Fit w = (X^T X + alpha * I_pen)^(-1) X^T y (intercept in col 0 unpenalized)."""
    n = len(X)
    p = len(X[0])
    xtx = [[0.0] * p for _ in range(p)]
    xty = [0.0] * p
    for row, target in zip(X, y):
        for i in range(p):
            xi = row[i]
            xty[i] += xi * target
            for j in range(i, p):
                xtx[i][j] += xi * row[j]
    for i in range(p):
        for j in range(i):
            xtx[i][j] = xtx[j][i]
        if i > 0:
            xtx[i][i] += alpha
    return solve_linear_system(xtx, xty)


def ols_slope_p(x: list[float], y: list[float]) -> dict[str, float]:
    """Simple OLS y = a + b*x with normal-approx p-value for slope b."""
    n = len(x)
    if n < 10:
        return {"slope": 0.0, "intercept": 0.0, "se": 0.0, "t": 0.0, "p_value": 1.0, "r2": 0.0}
    mx = sum(x) / n
    my = sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    syy = sum((b - my) ** 2 for b in y)
    slope = sxy / sxx if sxx > 0 else 0.0
    intercept = my - slope * mx
    sse = sum((b - (intercept + slope * a)) ** 2 for a, b in zip(x, y))
    s2 = sse / max(1, n - 2)
    se = math.sqrt(s2 / sxx) if sxx > 0 else 0.0
    t_stat = slope / se if se > 0 else 0.0
    p_val = 2.0 * (1.0 - norm_cdf(abs(t_stat)))
    r2 = 1.0 - (sse / syy) if syy > 0 else 0.0
    return {
        "slope": round(slope, 4),
        "intercept": round(intercept, 4),
        "se": round(se, 4),
        "t": round(t_stat, 4),
        "p_value": round(p_val, 6),
        "r2": round(r2, 4),
    }


def empirical_bayes_shrink(roi: float, n_bets: int, prior_mean: float = -0.045, tau: float = 0.03) -> float:
    """Normal-normal Empirical Bayes shrinkage of noisy finite-sample ROI toward market vig prior."""
    if n_bets <= 0:
        return round(prior_mean, 4)
    # Approximate bet-level ROI SD ~ 0.98 for ~-110/-105 binary spread bets
    se2 = (0.98 ** 2) / n_bets
    tau2 = tau ** 2
    wt = tau2 / (tau2 + se2)
    post = wt * roi + (1.0 - wt) * prior_mean
    return round(post, 4)
