#!/usr/bin/env python3
"""Correlation and parlay pricing: measure how far the independent-legs shortcut is from reality.

The question a same-game parlay asks is "what is the chance every leg wins together?". Pricing houses
that multiply the leg probabilities, which is only right when the legs are independent. They are not:
the same offence drives several legs at once. This module measures, on the committed player-week
extract:

  * pairwise Pearson correlations between four same-team legs (QB passing yards, WR1 receiving yards,
    RB1 rushing yards, team points);
  * the empirical joint probability of clearing the same percentile on 2 and 3 legs, against the
    product of the marginals;
  * a Gaussian-copula estimate of the same joint, which is what a pricer would use if it knew the
    correlation;
  * a cross-game control: the same calculation for legs drawn from two different games, which should
    collapse to the independent answer.

Correlations are measured, not assumed. Where a leg cannot be built from the committed columns it is
omitted rather than proxied.
"""
from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "data" / "derived"
SITE = Path(__file__).resolve().parents[1]
OUT = SITE / "data" / "parlay.json"
SRC_PLAYER = "https://github.com/nflverse/nflverse-data/releases/tag/stats_player"
SRC_SCHEDULES = "https://github.com/nflverse/nflverse-data/releases/tag/schedules"


def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(float(x)) else round(float(x), 6)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def pearson(a: np.ndarray, b: np.ndarray) -> tuple[float, float, int]:
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    n = len(a)
    if n < 30 or a.std() == 0 or b.std() == 0:
        return (math.nan, math.nan, n)
    r = float(np.corrcoef(a, b)[0, 1])
    t = r * math.sqrt((n - 2) / max(1e-12, 1 - r * r))
    try:
        from scipy import stats as sps
        p = float(2 * sps.t.sf(abs(t), df=n - 2))
    except Exception:
        p = math.erfc(abs(t) / math.sqrt(2))
    return (r, p, n)


def copula_joint(rho: np.ndarray, probs: list[float]) -> float:
    """P(all legs win) for a Gaussian copula with correlation matrix rho."""
    from scipy import stats as sps
    z = np.array([sps.norm.ppf(p) for p in probs])
    mvn = sps.multivariate_normal(mean=np.zeros(len(probs)), cov=rho, allow_singular=True)
    return float(mvn.cdf(-z))


def build_legs() -> pd.DataFrame:
    """One row per team-game with the four legs that the committed columns support."""
    pw = pd.read_csv(DERIVED / "player_week.csv.gz", low_memory=False)
    pw = pw[pw["season_type"] == "REG"].copy()
    g = pd.read_csv(DERIVED / "games.csv.gz", low_memory=False)
    g = g.dropna(subset=["home_score", "away_score"])
    g = g[g["game_type"] == "REG"]
    key = ["season", "week", "team"]

    qb = (pw[pw["attempts"].fillna(0) >= 10]
          .sort_values(key + ["attempts"], ascending=[True, True, True, False])
          .drop_duplicates(subset=key, keep="first")[key + ["passing_yards"]]
          .rename(columns={"passing_yards": "qb_pass_yds"}))
    skill = pw[pw["position"].isin(["WR", "TE", "RB"])].copy()
    skill["targets"] = skill["targets"].fillna(0)
    wr1 = (skill.sort_values(key + ["targets"], ascending=[True, True, True, False])
           .drop_duplicates(subset=key, keep="first")[key + ["receiving_yards"]]
           .rename(columns={"receiving_yards": "wr1_rec_yds"}))
    rb = pw[pw["position"] == "RB"].copy()
    rb["carries"] = rb["carries"].fillna(0)
    rb1 = (rb.sort_values(key + ["carries"], ascending=[True, True, True, False])
           .drop_duplicates(subset=key, keep="first")[key + ["rushing_yards"]]
           .rename(columns={"rushing_yards": "rb1_rush_yds"}))

    sc = pd.concat([
        pd.DataFrame({"game_id": g["game_id"], "team": g["home_team"], "team_points": g["home_score"]}),
        pd.DataFrame({"game_id": g["game_id"], "team": g["away_team"], "team_points": g["away_score"]}),
    ])
    # game_id is not in the pruned player extract; map team-weeks to games through the schedules file
    gid = pd.concat([
        g[["game_id", "season", "week", "home_team"]].rename(columns={"home_team": "team"}),
        g[["game_id", "season", "week", "away_team"]].rename(columns={"away_team": "team"}),
    ])
    ctx = gid.drop_duplicates(subset=key)
    ctx = ctx.merge(sc, on=["game_id", "team"], how="left")

    legs = ctx.merge(qb, on=key, how="left").merge(wr1, on=key, how="left").merge(rb1, on=key, how="left")
    return legs.dropna(subset=["qb_pass_yds", "wr1_rec_yds", "rb1_rush_yds", "team_points"])


def joint_table(df: pd.DataFrame, cols: list[str]) -> dict:
    """Empirical P(all above their own medians) vs the product of the marginals."""
    d = df.dropna(subset=cols)
    if len(d) < 200:
        return {"n": int(len(d)), "status": "insufficient"}
    exceed = np.column_stack([(d[c] > d[c].median()).astype(int) for c in cols])
    marg = [float(exceed[:, i].mean()) for i in range(len(cols))]
    joint = float(exceed.all(axis=1).mean())
    prod = float(np.prod(marg))
    se = math.sqrt(max(joint * (1 - joint), 1e-12) / len(d))
    return {
        "n": int(len(d)), "legs": cols,
        "marginal_rates": [round(m, 4) for m in marg],
        "empirical_joint": round(joint, 4),
        "independent_product": round(prod, 4),
        "ratio": round(joint / prod, 3) if prod else None,
        "joint_ci": [round(max(0, joint - 1.96 * se), 4), round(min(1, joint + 1.96 * se), 4)],
        "fair_decimal_odds_empirical": round(1 / joint, 3) if joint else None,
        "fair_decimal_odds_independent": round(1 / prod, 3) if prod else None,
        "pricing_error_pct": round((prod / joint - 1) * 100, 1) if joint else None,
    }


def stamp() -> str:
    """Deterministic build stamp.

    Wall-clock generation times made every CI rebuild differ from the committed file, which broke the
    reproducibility check for a reason that had nothing to do with the numbers. The stamp is therefore
    the date the committed data ends, read from data/provenance.json.
    """
    p = ROOT / "data" / "provenance.json"
    try:
        with open(p) as fh:
            day = json.load(fh).get("data_as_of_gameday")
    except (OSError, ValueError):
        day = None
    return f"{day}T00:00:00Z" if day else "unknown"


def main() -> int:
    legs = build_legs()
    cols = ["qb_pass_yds", "wr1_rec_yds", "rb1_rush_yds", "team_points"]

    # ---- pairwise correlations, same team-game ------------------------------------------------
    pairs = []
    for a, b in itertools.combinations(cols, 2):
        r, p, n = pearson(legs[a].to_numpy(float), legs[b].to_numpy(float))
        pairs.append({"leg_a": a, "leg_b": b, "r": r, "p": p, "n": n, "context": "same team-game"})

    # ---- the same pairs from *different* games: the independence control ---------------------
    rng = np.random.default_rng(23)
    ctrl = legs.sample(frac=1.0, random_state=5).reset_index(drop=True)
    for a, b in itertools.combinations(cols, 2):
        r, p, n = pearson(legs[a].to_numpy(float), ctrl[b].to_numpy(float))
        pairs.append({"leg_a": a, "leg_b": b, "r": r, "p": p, "n": n,
                      "context": "cross-game control (rows shuffled independently)"})

    # ---- 2-leg and 3-leg joints ---------------------------------------------------------------
    combos = {}
    for k in (2, 3):
        for combo in itertools.combinations(cols, k):
            combos["+".join(combo)] = joint_table(legs, list(combo))

    # ---- Gaussian copula on the 3-leg set, using the measured correlations --------------------
    three = ["qb_pass_yds", "wr1_rec_yds", "team_points"]
    d3 = legs[three].dropna()
    rho = np.corrcoef(d3.to_numpy(float), rowvar=False)
    probs = [float((d3[c] > d3[c].median()).mean()) for c in three]
    cop = copula_joint(rho, probs) if len(d3) > 200 else math.nan
    emp = combos["+".join(three)]["empirical_joint"] if "+".join(three) in combos else None
    copula_row = {
        "legs": three, "n": int(len(d3)),
        "marginals": [round(p, 4) for p in probs],
        "correlation_matrix": [[round(float(v), 3) for v in row] for row in rho],
        "empirical_joint": emp,
        "independent_product": round(float(np.prod(probs)), 4),
        "copula_joint": round(cop, 4) if np.isfinite(cop) else None,
        "copula_vs_independent_pct": (round((cop / float(np.prod(probs)) - 1) * 100, 1)
                                      if np.isfinite(cop) else None),
        "note": ("The copula uses only the measured pairwise correlations, so it is an independent check "
                 "on the empirical joint rather than a re-statement of it."),
    }

    # ---- what a correlated parlay is worth vs how it is usually priced -----------------------
    premium = []
    for name, row in combos.items():
        if row.get("status"):
            continue
        if row.get("fair_decimal_odds_empirical") and row.get("fair_decimal_odds_independent"):
            premium.append({
                "ticket": name, "n": row["n"],
                "empirical_joint": row["empirical_joint"],
                "independent_product": row["independent_product"],
                "fair_odds_if_correlated": row["fair_decimal_odds_empirical"],
                "fair_odds_if_independent": row["fair_decimal_odds_independent"],
                "theoretical_hold_pct_if_priced_independently": row["pricing_error_pct"],
            })

    # ---- how often a 2-leg ticket needs both legs to be right -------------------------------
    payload = {
        "meta": {
            "session": "arena/90e4fdbe-korea2",
            "generated_utc": stamp(),
            "team_games": int(len(legs)),
            "seasons": [int(legs["season"].min()), int(legs["season"].max())],
            "legs": {
                "qb_pass_yds": "passing yards of the team's most-used QB that week (min 10 attempts)",
                "wr1_rec_yds": "receiving yards of the team's most-targeted WR/TE/RB",
                "rb1_rush_yds": "rushing yards of the team's most-used RB",
                "team_points": "points scored by that team in that game",
            },
            "method": ("Pearson correlation and empirical joint exceedance rates; a Gaussian copula with "
                       "the measured correlation matrix as an independent cross-check; a shuffled-row "
                       "cross-game control to show what independence looks like in this data."),
            "caveat": ("Correlation is measured on outcomes, not on prices. No historical player-prop price "
                       "is committed in this repository, so no prop-parlay ROI is computed or implied."),
        },
        "pairs": pairs,
        "joints": combos,
        "copula": copula_row,
        "premium": premium,
        "sources": {"player_week": SRC_PLAYER, "schedules": SRC_SCHEDULES},
    }
    OUT.write_text(json.dumps(clean(payload), indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(legs)} team-games, {len(pairs)} pairs, {len(combos)} joints")
    for p in pairs[:4]:
        print(f"  {p['leg_a']:<14} x {p['leg_b']:<14} r={p['r']:+.3f} n={p['n']} ({p['context']})")
    for k in list(combos)[:3]:
        v = combos[k]
        print(f"  {k:<40} joint={v.get('empirical_joint')} product={v.get('independent_product')} "
              f"ratio={v.get('ratio')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
