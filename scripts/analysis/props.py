"""Player-prop research.

Scope note, stated up front: no free, official source publishes historical
player-prop prices. We can therefore measure *projection skill* (how much of a
player's week-to-week output is predictable) but not *edge* (whether a price was
wrong). Projection skill is a hard ceiling on any prop strategy, so it is the
honest thing to report.

Two design rules enforced here:
  1. No leakage. Every opponent/league baseline is built from weeks strictly
     earlier than the game being projected.
  2. Line != mean. Player output is right-skewed, so a line set at the expected
     value is beaten well under half the time. The originator therefore needs a
     median calibration, which is fitted walk-forward and reported.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import RESULTS, jdump, load_player_week

MARKETS = {
    "receiving_yards": ("WR", "TE"),
    "rushing_yards": ("RB",),
    "passing_yards": ("QB",),
    "receptions": ("WR", "TE", "RB"),
}
MIN_GAMES = 4
EVAL_SEASONS = list(range(2018, 2027))


def prep() -> pd.DataFrame:
    p = load_player_week()
    p = p[p.season_type == "REG"].copy()
    for c in ["receiving_yards", "rushing_yards", "passing_yards", "receptions",
              "targets", "carries", "attempts"]:
        p[c] = pd.to_numeric(p[c], errors="coerce").fillna(0)
    return p


def defence_form(p: pd.DataFrame, stat: str) -> pd.DataFrame:
    """Average team production a defence has allowed *before* each week."""
    tw = (p.groupby(["season", "week", "team"], as_index=False)[stat].sum()
            .rename(columns={stat: "produced"}))
    sched = p[["season", "week", "team", "opponent_team"]].drop_duplicates()
    played = tw.merge(sched, on=["season", "week", "team"], how="left")
    allowed = (played.groupby(["season", "week", "opponent_team"], as_index=False)["produced"]
                 .mean().rename(columns={"opponent_team": "defence", "produced": "allowed"}))
    allowed = allowed.sort_values(["defence", "season", "week"])
    allowed["def_form"] = (allowed.groupby(["defence", "season"])["allowed"]
                           .apply(lambda s: s.shift(1).expanding(min_periods=2).mean())
                           .reset_index(level=[0, 1], drop=True))
    league = (played.groupby(["season", "week"], as_index=False)["produced"].mean()
                .rename(columns={"produced": "league"}).sort_values(["season", "week"]))
    league["league_form"] = (league.groupby("season")["league"]
                             .apply(lambda s: s.shift(1).expanding(min_periods=2).mean())
                             .reset_index(level=0, drop=True))
    allowed = allowed.merge(league[["season", "week", "league_form"]], on=["season", "week"], how="left")
    return allowed[["season", "week", "defence", "def_form", "league_form"]]


def project(p: pd.DataFrame, stat: str) -> pd.DataFrame:
    df = p.copy().sort_values(["player_id", "season", "week"])
    g = df.groupby("player_id", group_keys=False)
    df["prev_mean"] = g[stat].apply(lambda s: s.shift(1).expanding(min_periods=1).mean())
    df["prev_l5"] = g[stat].apply(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    df["prev_var"] = g[stat].apply(lambda s: s.shift(1).expanding(min_periods=2).var())
    df["games"] = g.cumcount()

    dform = defence_form(df, stat)
    df = df.merge(dform, left_on=["season", "week", "opponent_team"],
                  right_on=["season", "week", "defence"], how="left")
    ratio = (df.def_form / df.league_form.replace(0, np.nan)).clip(0.55, 1.8).fillna(1.0)

    df["blend"] = 0.6 * df.prev_l5 + 0.4 * df.prev_mean
    df["projection"] = df.blend * (0.45 + 0.55 * ratio)
    df["baseline_form"] = df.prev_l5
    df["baseline_season"] = df.prev_mean
    df["sd"] = np.sqrt(df.prev_var.clip(lower=0))
    return df


def median_calibration(df: pd.DataFrame, stat: str) -> pd.DataFrame:
    """Walk-forward multiplier that turns a mean projection into a median line."""
    df = df.copy()
    df["cal_mult"] = np.nan
    for season in sorted(df.season.unique()):
        prior = df[(df.season < season) & (df.games >= MIN_GAMES)].dropna(subset=["projection"])
        if len(prior) < 300:
            continue
        lo, hi = 0.5, 1.3
        for _ in range(40):
            mid = (lo + hi) / 2
            rate = float((prior[stat] > prior.projection * mid).mean())
            if rate > 0.5:
                lo = mid
            else:
                hi = mid
        df.loc[df.season == season, "cal_mult"] = (lo + hi) / 2
    df["line_median"] = df.projection * df.cal_mult
    return df


def evaluate(df: pd.DataFrame, stat: str) -> dict:
    d = df[(df.games >= MIN_GAMES) & df.season.isin(EVAL_SEASONS)].dropna(subset=["projection"])
    if not len(d):
        return {}
    y = d[stat].to_numpy(float)
    out = {"n": int(len(d))}
    for name, col in [("model", "projection"), ("last5", "baseline_form"),
                      ("season_to_date", "baseline_season")]:
        pred = d[col].to_numpy(float)
        ok = np.isfinite(pred)
        out[name] = {
            "mae": float(np.mean(np.abs(y[ok] - pred[ok]))),
            "rmse": float(np.sqrt(np.mean((y[ok] - pred[ok]) ** 2))),
            "bias": float(np.mean(pred[ok] - y[ok])),
            "corr": float(np.corrcoef(pred[ok], y[ok])[0, 1]) if ok.sum() > 10 else None,
        }
    out["skill_vs_last5"] = 1 - out["model"]["mae"] / out["last5"]["mae"]
    out["skill_vs_season"] = 1 - out["model"]["mae"] / out["season_to_date"]["mae"]
    out["over_rate_vs_mean_projection"] = float((y > d.projection.to_numpy(float)).mean())
    med = d.line_median.to_numpy(float)
    ok = np.isfinite(med)
    out["over_rate_vs_calibrated_line"] = float((y[ok] > med[ok]).mean())
    out["calibration_multiplier_mean"] = float(d.cal_mult.mean())
    out["skew_of_stat"] = float(pd.Series(y).skew())
    out["residual_sd"] = float((y - d.projection.to_numpy(float)).std(ddof=1))
    return out


def by_season(df: pd.DataFrame, stat: str) -> dict:
    d = df[(df.games >= MIN_GAMES) & df.season.isin(EVAL_SEASONS)].dropna(subset=["projection"])
    res = {}
    for season, s in d.groupby("season"):
        y = s[stat].to_numpy(float)
        pm = s.projection.to_numpy(float)
        pl = s.baseline_form.to_numpy(float)
        ok = np.isfinite(pm) & np.isfinite(pl)
        if ok.sum() < 50:
            continue
        res[int(season)] = {"n": int(ok.sum()),
                            "mae_model": float(np.mean(np.abs(y[ok] - pm[ok]))),
                            "mae_last5": float(np.mean(np.abs(y[ok] - pl[ok])))}
    return res


def originate(p: pd.DataFrame) -> dict:
    """Projected lines for the next unplayed 2026 week, from prior weeks only."""
    out = {}
    for stat, positions in MARKETS.items():
        d = median_calibration(project(p[p.position.isin(positions)].copy(), stat), stat)
        cur = d[d.season == 2026]
        if not len(cur):
            continue
        latest_played = int(cur[cur[stat] > 0].week.max()) if (cur[stat] > 0).any() else 0
        target = latest_played + 1
        pool = cur[(cur.week == latest_played) & (cur.games >= 6)].dropna(subset=["line_median"])
        rows = []
        for _, r in pool.nlargest(6, "projection").iterrows():
            rows.append({
                "market": stat, "player": r.player_display_name, "team": r.team,
                "originated_line": float(r.line_median),
                "mean_projection": float(r.projection),
                "sd": float(r.sd) if np.isfinite(r.sd) else None,
                "recent_form": float(r.baseline_form) if np.isfinite(r.baseline_form) else None,
                "sample_games": int(r.games),
            })
        out[stat] = {"target_week": target, "as_of_week": latest_played, "rows": rows}
    return out


def main() -> dict:
    p = prep()
    out: dict = {"markets": {}}
    for stat, positions in MARKETS.items():
        d = project(p[p.position.isin(positions)].copy(), stat)
        d = median_calibration(d, stat)
        out["markets"][stat] = {"positions": list(positions),
                                "overall": evaluate(d, stat),
                                "by_season": by_season(d, stat)}
        o = out["markets"][stat]["overall"]
        if o:
            print(f"  {stat:16s} n={o['n']:6d} MAE={o['model']['mae']:6.2f} "
                  f"skill_last5={o['skill_vs_last5']*100:+5.1f}% "
                  f"over(mean)={o['over_rate_vs_mean_projection']:.3f} "
                  f"over(cal)={o['over_rate_vs_calibrated_line']:.3f} "
                  f"mult={o['calibration_multiplier_mean']:.3f}")
    out["originated"] = originate(p)
    out["coverage"] = {
        "seasons": sorted(int(s) for s in p.season.unique()),
        "players": int(p.player_id.nunique()),
        "player_weeks": int(len(p)),
        "note": ("No historical player-prop prices exist in any free source, so no "
                 "prop ROI is reported. Only projection skill is measured."),
    }
    jdump(out, RESULTS / "props.json")
    print("props.json written")
    return out


if __name__ == "__main__":
    main()
