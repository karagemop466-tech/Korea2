"""Correlation study.

Why it matters: a parlay is priced by multiplying legs. That is only correct if
the legs are independent. Same-game prop legs emphatically are not; cross-game
legs are measured here with a lag-1 autocorrelation check, which is consistent
with, but does not by itself establish, independence (issue #19).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from common import RESULTS, jdump, load_games, load_player_week, load_team_week


def fisher_ci(r: float, n: int, alpha: float = 0.05):
    """95% CI for a Pearson correlation via Fisher z."""
    if n < 4 or not np.isfinite(r) or abs(r) >= 1:
        return (float("nan"), float("nan"))
    z = math.atanh(r)
    se = 1 / math.sqrt(n - 3)
    lo, hi = math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)
    return (lo, hi)


def corr_row(name: str, x, y, note: str, official: str | None = None) -> dict:
    d = pd.DataFrame({"x": x, "y": y}).dropna()
    n = len(d)
    if n < 30 or d.x.std() == 0 or d.y.std() == 0:
        return {"name": name, "n": int(n), "r": None, "note": note}
    r = float(d.x.corr(d.y))
    lo, hi = fisher_ci(r, n)
    t = r * math.sqrt((n - 2) / max(1e-12, 1 - r * r))
    from math import erfc
    p = float(erfc(abs(t) / math.sqrt(2)))
    return {"name": name, "n": int(n), "r": r, "ci_lo": lo, "ci_hi": hi,
            "p": p, "r2": r * r, "note": note}


def team_game_table(pw: pd.DataFrame) -> pd.DataFrame:
    """One row per (season, week, team): the QB, top two receivers, lead back.

    Issue #19 labelling fix: "WR1"/"WR2" here are the receivers with the most
    REALISED yards in that game — an ex-post game leader, not a player
    identifiable before kickoff. Every published row name says so.
    """
    pw = pw[pw.season_type == "REG"].copy()
    for c in ["passing_yards", "attempts", "receiving_yards", "receptions",
              "rushing_yards", "carries", "targets", "passing_tds", "rushing_tds",
              "receiving_tds"]:
        pw[c] = pd.to_numeric(pw[c], errors="coerce").fillna(0)

    key = ["season", "week", "team"]

    qb = (pw[pw.position == "QB"]
          .sort_values(["season", "week", "team", "attempts"], ascending=[True, True, True, False])
          .groupby(key, as_index=False).first()[key + ["passing_yards", "attempts", "passing_tds"]]
          .rename(columns={"passing_yards": "qb_pass_yards", "passing_tds": "qb_pass_tds",
                           "attempts": "qb_attempts"}))

    wr = pw[pw.position == "WR"].copy()
    wr = wr.sort_values(["season", "week", "team", "receiving_yards"],
                        ascending=[True, True, True, False])
    wr["rank"] = wr.groupby(key).cumcount() + 1
    top2 = wr[wr["rank"] <= 2].pivot_table(
        index=key, columns="rank", values="receiving_yards", aggfunc="first")
    top2.columns = [f"wr{i}_yards" for i in top2.columns]
    top2 = top2.reset_index()

    rb = (pw[pw.position == "RB"]
          .sort_values(["season", "week", "team", "rushing_yards"], ascending=[True, True, True, False])
          .groupby(key, as_index=False).first()[key + ["rushing_yards"]]
          .rename(columns={"rushing_yards": "rb_rush_yards"}))

    tg = (pw.groupby(key, as_index=False)
          .agg(team_receiving_yards=("receiving_yards", "sum"),
               team_targets=("targets", "sum"),
               team_receptions=("receptions", "sum")))
    out = tg.merge(qb, on=key, how="left").merge(top2, on=key, how="left").merge(rb, on=key, how="left")
    return out


def main() -> dict:
    pw = load_player_week()
    if pw is None or not len(pw):
        print("no player data")
        return {}
    tg = team_game_table(pw)
    seasons = sorted(tg.season.unique())

    rows = []
    rows.append(corr_row(
        "QB passing yards vs that team's top receiver (same game, ex-post leader)",
        tg.qb_pass_yards, tg.wr1_yards,
        "Same plays, so the two legs of a same-game parlay are near-duplicates. The receiver is the ex-post yards leader of that game, not a pregame choice; the QB is the passer with the most attempts in it."))
    rows.append(corr_row(
        "Team passing yards vs top receiver's yards (same game, ex-post leader)",
        tg.team_receiving_yards, tg.wr1_yards,
        "Receiving volume concentrates in the top receiver."))
    rows.append(corr_row(
        "Top-two receivers' yards (same team, same game, ranked ex-post)",
        tg.wr1_yards, tg.wr2_yards,
        "Levels move together because the whole passing game expands; the split of "
        "targets is a different, zero-sum question (next row)."))
    share = tg.dropna(subset=["wr1_yards", "wr2_yards", "team_receiving_yards"]).copy()
    share = share[share.team_receiving_yards > 0]
    if len(share) > 100:
        # partial correlation: strip out the shared passing volume first
        def resid(col):
            a = np.polyfit(share.team_receiving_yards, share[col], 1)
            return share[col] - np.polyval(a, share.team_receiving_yards)
        rows.append(corr_row(
            "Top-two receivers' yards, holding team passing volume constant (ex-post ranks)",
            resid("wr1_yards"), resid("wr2_yards"),
            "Partial correlation. This is the part of a same-game pair the market "
            "calls 'positive correlation' when you pair two receivers."))

    rows.append(corr_row(
        "Lead RB rushing yards vs team passing yards (same game)",
        tg.rb_rush_yards, tg.team_receiving_yards,
        "Game script: trailing teams abandon the run."))
    rows.append(corr_row(
        "Lead RB rushing yards vs top receiver's yards (same team, same game, ex-post leaders)",
        tg.rb_rush_yards, tg.wr1_yards,
        "The classic 'one man eats' problem inside a same-game parlay."))

    # player level
    p = pw[pw.season_type == "REG"].copy()
    for c in ["receptions", "receiving_yards", "targets"]:
        p[c] = pd.to_numeric(p[c], errors="coerce")
    rows.append(corr_row(
        "A player's own receptions vs own receiving yards (same game)",
        p[p.position.isin(["WR", "TE"])].receptions, p[p.position.isin(["WR", "TE"])].receiving_yards,
        "Same player, two props. Effectively one leg priced twice."))

    # opposing quarterbacks -- joined through the actual schedule, never by week alone
    sched = load_games()[["season", "week", "home_team", "away_team", "game_type"]]
    sched = sched[sched.game_type == "REG"][["season", "week", "home_team", "away_team"]]
    home = tg.rename(columns={"team": "home_team", "qb_pass_yards": "home_qb_yards",
                              "team_receiving_yards": "home_rec_yards"})[
        ["season", "week", "home_team", "home_qb_yards", "home_rec_yards"]]
    away = tg.rename(columns={"team": "away_team", "qb_pass_yards": "away_qb_yards",
                              "team_receiving_yards": "away_rec_yards"})[
        ["season", "week", "away_team", "away_qb_yards", "away_rec_yards"]]
    both = sched.merge(home, on=["season", "week", "home_team"], how="inner")
    both = both.merge(away, on=["season", "week", "away_team"], how="inner")
    both = both.drop_duplicates(subset=["season", "week", "home_team", "away_team"])
    rows.append(corr_row(
        "Home QB passing yards vs away QB passing yards (same game)",
        both.home_qb_yards, both.away_qb_yards,
        "Pace and shootout games lift both sides: this is the one useful positive cross-team correlation."))
    rows.append(corr_row(
        "Total receiving yards, home vs away (same game)",
        both.home_rec_yards, both.away_rec_yards,
        "Game environment, measured without using the result."))

    # game level, from the schedule file
    g = load_games()
    for c in ["result", "total", "total_line", "spread_line"]:
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g = g[(g.game_type == "REG") & g.result.notna()].copy()
    rows.append(corr_row(
        "Home margin vs game total (completed games)",
        g.result, g.total,
        "Margin and total are close to orthogonal, which is why spread+total combos add little risk."))
    rows.append(corr_row(
        "Closing spread vs closing total",
        g.spread_line, g.total_line,
        "The two prices are quoted almost independently."))
    rows.append(corr_row(
        "Home ATS result vs game total, same game",
        g.result - g.spread_line, g.total - g.total_line,
        "Settlement-level independence for a cross-market same-game parlay."))

    # ---- same-game parlay pricing demo -------------------------------------
    sgp = {}
    d = tg.dropna(subset=["qb_pass_yards", "wr1_yards"]).copy()
    if len(d) > 500:
        q1, q2 = d.qb_pass_yards.median(), d.wr1_yards.median()
        leg1 = d.qb_pass_yards > q1
        leg2 = d.wr1_yards > q2
        p1, p2 = float(leg1.mean()), float(leg2.mean())
        joint = float((leg1 & leg2).mean())
        sgp["qb_plus_wr1"] = {
            "n": int(len(d)),
            "threshold_qb_yards": float(q1), "threshold_wr1_yards": float(q2),
            "p_leg1": p1, "p_leg2": p2,
            "naive_independent_p": p1 * p2, "actual_joint_p": joint,
            "correlation_multiple": joint / (p1 * p2) if p1 * p2 else None,
            "naive_fair_odds": 1 / (p1 * p2) if p1 * p2 else None,
            "true_fair_odds": 1 / joint if joint else None,
            "selection": ("Descriptive full-sample example. Thresholds are whole-sample "
                          "medians and the receiver is the ex-post yards leader, so this "
                          "is NOT a pregame strategy and NOT a priced sportsbook offer "
                          "(issue #19). No prop price is attached to it anywhere."),
            "note": ("Legs are close to the same event, so a book that priced them "
                     "independently would lose; real books shorten same-game prices."),
        }
        d2 = tg.dropna(subset=["wr1_yards", "wr2_yards"]).copy()
        if len(d2) > 500:
            t1, t2 = d2.wr1_yards.median(), d2.wr2_yards.median()
            l1, l2 = d2.wr1_yards > t1, d2.wr2_yards > t2
            p1b, p2b = float(l1.mean()), float(l2.mean())
            jointb = float((l1 & l2).mean())
            sgp["wr1_plus_wr2"] = {
                "n": int(len(d2)),
                "p_leg1": p1b, "p_leg2": p2b,
                "naive_independent_p": p1b * p2b, "actual_joint_p": jointb,
                "correlation_multiple": jointb / (p1b * p2b) if p1b * p2b else None,
                "naive_fair_odds": 1 / (p1b * p2b) if p1b * p2b else None,
                "true_fair_odds": 1 / jointb if jointb else None,
                "note": "Two receivers on one team compete for the same targets.",
            }

    # ---- cross-game autocorrelation check (issue #19: this measures lag-1
    # autocorrelation of weekly aggregates; it does NOT establish independence
    # of same-week cross-game outcomes, and the old home_cover_rate was the
    # mean margin, not a cover rate at all) -----------------------------------
    gc = g.dropna(subset=["spread_line"]).copy()
    cover_margin = gc.result - gc.spread_line
    gc["home_covered"] = np.where(cover_margin == 0, np.nan,
                                  (cover_margin > 0).astype(float))
    wk = gc.groupby(["season", "week"]).agg(
        games=("result", "size"),
        home_cover_rate=("home_covered", "mean"),
        mean_margin=("result", "mean")).reset_index()
    cross = {
        "n_game_weeks": int(len(wk)),
        "corr_consecutive_week_mean_margin": float(wk.mean_margin.autocorr(1)),
        "corr_consecutive_week_home_cover_rate": float(wk.home_cover_rate.autocorr(1)),
        "note": ("Lag-1 autocorrelation of the weekly mean margin and of the weekly "
                 "home cover rate (pushes excluded from the rate). Near-zero values "
                 "are consistent with week-to-week outcomes not carrying over, but "
                 "this does not establish contemporaneous cross-game independence: "
                 "pairwise independence does not imply joint independence of a "
                 "multi-leg ticket."),
    }

    # ---- data coverage ------------------------------------------------------
    coverage = {
        "seasons": [int(s) for s in seasons],
        "team_games": int(len(tg)),
        "note": ("Built from nflverse player-week extracts, which are aggregations of "
                 "the NFL's official play-by-play."),
    }

    out = {"correlations": rows, "sgp": sgp, "cross_game": cross, "coverage": coverage}
    jdump(out, RESULTS / "correlations.json")
    print("correlations.json written")
    for r in rows:
        if r.get("r") is not None:
            print(f"  {r['r']:+.3f}  n={r['n']:6d}  {r['name'][:70]}")
    for k, v in sgp.items():
        print(f"  SGP {k}: naive {v['naive_independent_p']:.3f} vs actual {v['actual_joint_p']:.3f} "
              f"x{v['correlation_multiple']:.2f}")
    return out


if __name__ == "__main__":
    main()
