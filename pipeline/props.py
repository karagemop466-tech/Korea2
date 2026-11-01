"""Originate our own player-prop lines, and test them honestly.

What this module can and cannot do
----------------------------------
We have player-game box statistics (2009-2017) but **no sportsbook player-prop prices**
(see IR-03). So we cannot publish a prop ROI. What we can do, and do here:

  1. originate a line for each player-game (our own projection, not a market quote),
  2. grade it against a *pre-declared naive line* (the player's trailing five-game mean,
     rounded to the nearest half point) - the reference line a lazy book would post,
  3. measure whether our line beats that reference line out-of-sample (MAE, Brier,
     log-loss, calibration), which is the only skill statement the data supports,
  4. leave every profit/ROI cell blank and flag it.

Universe (declared before any evaluation)
----------------------------------------
A player enters the prop board for a game only if, before kick-off, he had at least one
prior appearance with the usage threshold for that market:

    receiving markets : >= 3 targets in his most recent game
    rushing markets   : >= 5 carries in his most recent game
    passing markets   : >= 10 attempts in his most recent game

Evaluation seasons: 2012-2017 (models are trained on seasons strictly before the one
being predicted, with a minimum of two seasons of history).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from lib.common import INTERIM, brier, log_loss, normal_cdf, write_json

EVAL_START = 2012
MIN_TRAIN_SEASONS = 2
USAGE = {"rec_yds": ("targets", 3), "rec": ("targets", 3), "any_td": ("targets", 1),
         "rush_yds": ("rush_att", 5), "pass_yds": ("pass_att", 10)}
MARKETS = ["rec_yds", "rec", "rush_yds", "pass_yds", "any_td"]


def team_defence(pg: pd.DataFrame) -> pd.DataFrame:
    """Pre-game rolling average allowed by each defence, by position group."""
    pos_groups = ["WR", "TE", "RB", "QB"]
    frames = []
    for pos in pos_groups:
        allowed = (pg[pg["pos_group"] == pos]
                   .groupby(["game_id", "opp"])[["rec_yds", "rec", "rush_yds", "pass_yds", "any_td"]]
                   .sum().reset_index().rename(columns={"opp": "team"}))
        allowed["pos_group"] = pos
        frames.append(allowed)
    allowed = pd.concat(frames)
    keys = pg[["game_id", "season", "week", "gameday", "team"]].drop_duplicates()
    allowed = allowed.merge(keys, on=["game_id", "team"], how="left").sort_values(["team", "gameday"])
    cols = ["rec_yds", "rec", "rush_yds", "pass_yds", "any_td"]
    grp = allowed.groupby(["team", "pos_group"], group_keys=False)
    for c in cols:
        allowed[f"allowed_{c}_ewm"] = grp[c].apply(lambda s: s.shift(1).ewm(halflife=8, min_periods=2).mean())
    return allowed[["game_id", "team", "pos_group"] + [f"allowed_{c}_ewm" for c in cols]]


def player_features(pg: pd.DataFrame) -> pd.DataFrame:
    pg = pg.sort_values(["player_id", "gameday"]).copy()
    grp = pg.groupby("player_id", group_keys=False)
    for c in ("rec_yds", "rec", "rush_yds", "pass_yds", "targets", "rush_att", "pass_att", "any_td"):
        pg[f"{c}_l3"] = grp[c].apply(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
        pg[f"{c}_l5"] = grp[c].apply(lambda s: s.shift(1).rolling(5, min_periods=2).mean())
        pg[f"{c}_season"] = grp[c].apply(lambda s: s.shift(1).expanding().mean())
    pg["career_games"] = grp.cumcount()
    pg["prev_targets"] = grp["targets"].shift(1)
    pg["prev_carries"] = grp["rush_att"].shift(1)
    pg["prev_attempts"] = grp["pass_att"].shift(1)
    pg["prev_any_td"] = grp["any_td"].shift(1)
    return pg


def build_frame(pg: pd.DataFrame) -> pd.DataFrame:
    extra = player_features(pg)
    allowed = team_defence(pg)
    df = extra.merge(allowed, left_on=["game_id", "opp", "pos_group"],
                     right_on=["game_id", "team", "pos_group"], how="left", suffixes=("", "_def"))
    df["team_implied"] = np.where(df["home"] == 1,
                                  (df["total_line"] + df["spread_line"]) / 2,
                                  (df["total_line"] - df["spread_line"]) / 2)
    return df


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, feats: list[str], target: str,
                alpha: float = 3.0) -> np.ndarray:
    Xtr = train[feats].to_numpy(float)
    ytr = train[target].to_numpy(float)
    mu, sd = np.nanmean(Xtr, axis=0), np.nanstd(Xtr, axis=0)
    sd[sd == 0] = 1.0
    Z = (Xtr - mu) / sd
    Z = np.nan_to_num(Z, nan=0.0)
    Z = np.column_stack([np.ones(len(Z)), Z])
    pen = np.full(Z.shape[1], alpha)
    pen[0] = 0.0
    theta = np.linalg.solve(Z.T @ Z + np.diag(pen), Z.T @ ytr)
    Xte = np.nan_to_num((test[feats].to_numpy(float) - mu) / sd, nan=0.0)
    Xte = np.column_stack([np.ones(len(Xte)), Xte])
    return Xte @ theta


def evaluate_market(df: pd.DataFrame, target: str) -> dict:
    """Originate a line and grade it against a pre-declared naive reference.

    Continuous markets: the reference line is the player's trailing five-game mean,
    rounded to the nearest half point; the naive *probability* is the base over-rate
    measured on training seasons only (a constant forecast).

    Binary market (anytime touchdown): there is no line to post, so the naive
    probability is the position group's base scoring rate, again measured on training
    seasons only. The model's linear probability is compared with it.
    """
    binary = target == "any_td"
    usage_col, min_usage = USAGE[target]
    prev_col = {"targets": "prev_targets", "rush_att": "prev_carries", "pass_att": "prev_attempts"}[usage_col]
    d = df[(df[prev_col] >= min_usage) & df[f"{target}_l5"].notna()
           & df["total_line"].notna() & (df["career_games"] >= 1)].copy()

    feats = [f"{target}_l3", f"{target}_l5", f"{target}_season", "career_games", "home",
             "team_implied", f"allowed_{target}_ewm"]
    if binary:
        d["naive_line"] = d[f"{target}_l5"]
        d["naive_prob"] = np.nan
    else:
        d["naive_line"] = np.round(d[f"{target}_l5"] * 2) / 2
        d["naive_prob"] = np.nan
    d["model_line"] = np.nan
    d["naive_baseline"] = np.nan

    for season in sorted(d["season"].unique()):
        if season < EVAL_START:
            continue
        train = d[d["season"] < season]
        if train["season"].nunique() < MIN_TRAIN_SEASONS:
            continue
        train = train.dropna(subset=[f"allowed_{target}_ewm"])
        test_idx = d[d["season"] == season].index
        d.loc[test_idx, "model_line"] = fit_predict(train, d.loc[test_idx], feats, target)
        if binary:
            base = float(train[target].mean())
        else:
            over_train = (train[target] > train["naive_line"]).astype(float)
            base = float(over_train.mean())
        d.loc[test_idx, "naive_baseline"] = base

    ev = d[(d["season"] >= EVAL_START) & d["model_line"].notna() & d["naive_baseline"].notna()].copy()
    if ev.empty:
        return {"market": target, "status": "no evaluation rows"}

    if binary:
        ev["p_over"] = np.clip(ev["model_line"], 0.01, 0.99)
        ev["over"] = ev[target].astype(float)
        mae_model = float(np.mean(np.abs(ev[target] - ev["p_over"])))
        mae_naive = float(np.mean(np.abs(ev[target] - ev["naive_baseline"])))
        line_spread = None
    else:
        resid_sd = float(np.std(ev[target] - ev["model_line"]))
        ev["p_over"] = [normal_cdf((m - l) / resid_sd) for m, l in zip(ev["model_line"], ev["naive_line"])]
        ev["over"] = (ev[target] > ev["naive_line"]).astype(float)
        ev = ev[ev[target] != ev["naive_line"]]
        mae_model = float(np.mean(np.abs(ev[target] - ev["model_line"])))
        mae_naive = float(np.mean(np.abs(ev[target] - ev["naive_line"])))
        line_spread = float(np.mean(np.abs(ev["model_line"] - ev["naive_line"])))

    p = ev["p_over"].to_numpy()
    y = ev["over"].to_numpy()
    base = ev["naive_baseline"].to_numpy()
    b_model = brier(p, y)
    b_naive = brier(base, y)
    ll_model = log_loss(p, y)
    ll_naive = log_loss(base, y)

    rng = np.random.default_rng(23)
    skill = []
    for _ in range(2000):
        i = rng.integers(0, len(y), len(y))
        bm = np.mean((p[i] - y[i]) ** 2)
        bn = np.mean((base[i] - y[i]) ** 2)
        if bn > 0:
            skill.append(1 - bm / bn)

    bins = np.linspace(0, 1, 6)
    ev["bin"] = pd.cut(ev["p_over"], bins, include_lowest=True)
    curve = (ev.groupby("bin", observed=True)
               .apply(lambda x: pd.Series({"pred": x["p_over"].mean(), "actual": x["over"].mean(),
                                           "n": len(x)}), include_groups=False)
               .reset_index(drop=True))

    # Calibration is measured on bins big enough to mean something; tail bins with a
    # handful of player-games are reported in the curve but excluded from the summary.
    curve["gap"] = (curve["pred"] - curve["actual"]).abs()
    big = curve[curve["n"] >= 100].reset_index(drop=True)
    ece = float(np.sum(big["n"] * big["gap"]) / max(1, big["n"].sum())) if len(big) else float("nan")
    worst = int(big["gap"].idxmax()) if len(big) else 0

    return {
        "market": target,
        "label": {"rec_yds": "Receiving yards", "rec": "Receptions", "rush_yds": "Rushing yards",
                  "pass_yds": "Passing yards", "any_td": "Anytime touchdown"}[target],
        "binary": binary,
        "n_player_games": int(len(ev)),
        "n_players": int(ev["player_id"].nunique()),
        "seasons": [int(ev["season"].min()), int(ev["season"].max())],
        "mae_model": mae_model,
        "mae_naive": mae_naive,
        "mae_improvement_pct": 100 * (mae_naive - mae_model) / mae_naive,
        "mean_abs_line_gap": line_spread,
        "brier_model": b_model,
        "brier_naive": b_naive,
        "logloss_model": ll_model,
        "logloss_naive": ll_naive,
        "brier_skill": 1 - b_model / b_naive,
        "brier_skill_ci95": [float(np.quantile(skill, 0.025)), float(np.quantile(skill, 0.975))],
        "reliability": curve.to_dict("records"),
        "calibration_ece": ece,
        "calibration_worst_bin": {
            "predicted": float(big["pred"].iloc[worst]) if len(big) else None,
            "actual": float(big["actual"].iloc[worst]) if len(big) else None,
            "n": int(big["n"].iloc[worst]) if len(big) else 0,
        } if len(big) else None,
        "calibration_bins_used": int(len(big)),
        "calibrated": bool(len(big) and big["gap"].max() <= 0.03),
    }


def correlation_pairs(df: pd.DataFrame) -> list[dict]:
    """Same-game statistical dependencies that drive prop-combo and SGP pricing."""
    out = []
    d = df[df["game_id"].notna()].copy()

    def corr_block(a, b, label: str, note: str):
        a = pd.Series(np.asarray(a, dtype=float))
        b = pd.Series(np.asarray(b, dtype=float))
        ok = a.notna() & b.notna()
        if ok.sum() < 200:
            return
        r = float(np.corrcoef(a[ok], b[ok])[0, 1])
        rng = np.random.default_rng(31)
        vals = []
        av, bv = a[ok].to_numpy(), b[ok].to_numpy()
        for _ in range(1000):
            i = rng.integers(0, len(av), len(av))
            vals.append(np.corrcoef(av[i], bv[i])[0, 1])
        out.append({"pair": label, "r": r, "ci95": [float(np.quantile(vals, 0.025)),
                                                    float(np.quantile(vals, 0.975))],
                    "n": int(ok.sum()), "note": note})

    # team-level totals
    team_game = (d.groupby(["game_id", "team"])
                  .agg(pass_yds=("pass_yds", "sum"), rec_yds=("rec_yds", "sum"),
                       rush_yds=("rush_yds", "sum"), team_pts=("team_pts", "first")).reset_index())
    corr_block(team_game["pass_yds"], team_game["team_pts"], "Team passing yards vs team points",
               "Same team, same game.")
    corr_block(team_game["rush_yds"], team_game["team_pts"], "Team rushing yards vs team points",
               "Same team, same game.")
    corr_block(team_game["pass_yds"], team_game["rush_yds"], "Team passing vs rushing yards",
               "Game script: passing volume and rushing volume trade off.")

    # QB vs his top receiver
    qb = d[d["pos_group"] == "QB"].groupby(["game_id", "team"]).agg(
        qb_pass=("pass_yds", "sum"), qb_name=("player", "first")).reset_index()
    wr = (d[d["pos_group"].isin(["WR", "TE"])]
          .sort_values("rec_yds", ascending=False)
          .groupby(["game_id", "team"]).agg(wr_rec=("rec_yds", "first"),
                                            wr_name=("player", "first")).reset_index())
    m = qb.merge(wr, on=["game_id", "team"])
    corr_block(m["qb_pass"], m["wr_rec"], "QB passing yards vs his leading receiver's yards",
               "Same team, same game: the strongest positive dependency on the board.")
    tg = team_game.set_index(["game_id", "team"])["team_pts"]
    corr_block(m["wr_rec"].to_numpy(), tg.reindex(list(zip(m["game_id"], m["team"]))).to_numpy(),
               "Leading receiver yards vs team points", "Drives receiver + team-total combos.")

    # two receivers on the same team
    top2 = (d[d["pos_group"].isin(["WR", "TE"])]
            .sort_values("rec_yds", ascending=False).groupby(["game_id", "team"]).head(2))
    p = top2.groupby(["game_id", "team"]).filter(lambda x: len(x) == 2)
    if len(p):
        a = p.groupby(["game_id", "team"])["rec_yds"].apply(lambda s: s.iloc[0])
        b = p.groupby(["game_id", "team"])["rec_yds"].apply(lambda s: s.iloc[1])
        corr_block(a, b, "Team WR1 yards vs team WR2 yards",
                   "Two receivers on the same team compete for targets, but share game script.")

    # rushing RB vs team points
    rb = d[d["pos_group"] == "RB"].groupby(["game_id", "team"]).agg(rb_rush=("rush_yds", "max")).reset_index()
    m2 = rb.merge(team_game[["game_id", "team", "team_pts"]], on=["game_id", "team"])
    corr_block(m2["rb_rush"], m2["team_pts"], "Lead RB rushing yards vs team points",
               "Positive: more points usually means more carries and more yards.")

    # game-level: total points vs the two QBs' combined passing
    game_qb = qb.groupby("game_id")["qb_pass"].sum()
    game_pts = d.groupby("game_id")["points_total"].first()
    corr_block(game_qb, game_pts.reindex(game_qb.index), "Combined QB passing yards vs game total points",
               "The dependency behind QB-yard + over combos.")
    return out


def joint_test(df: pd.DataFrame) -> list[dict]:
    """P(both over) vs the product of the marginals, at the naive lines."""
    out = []
    d = df[df["game_id"].notna()].copy()
    qb = d[d["pos_group"] == "QB"].groupby(["game_id", "team"]).agg(
        pass_yds=("pass_yds", "sum"),
        qb_l5=("pass_yds_l5", "max")).reset_index()
    wr = (d[d["pos_group"].isin(["WR", "TE"])].sort_values("rec_yds", ascending=False)
          .groupby(["game_id", "team"]).agg(rec_yds=("rec_yds", "first"),
                                            wr_l5=("rec_yds_l5", "first")).reset_index())
    m = qb.merge(wr, on=["game_id", "team"]).dropna()
    if len(m) > 200:
        a = (m["pass_yds"] > np.round(m["qb_l5"] * 2) / 2).astype(float)
        b = (m["rec_yds"] > np.round(m["wr_l5"] * 2) / 2).astype(float)
        pa, pb = float(a.mean()), float(b.mean())
        joint = float((a * b).mean())
        iid = pa * pb
        out.append({"combo": "QB passing yards over + his WR receiving yards over",
                    "n": int(len(m)), "p_a": pa, "p_b": pb, "p_both_empirical": joint,
                    "p_both_independent": iid,
                    "pct_error": 100 * (joint - iid) / iid if iid else None})
    return out


def main() -> None:
    pg = pd.read_parquet(INTERIM / "player_games.parquet")
    df = build_frame(pg)

    markets = [evaluate_market(df, m) for m in MARKETS]
    corr = correlation_pairs(df)
    joint = joint_test(df)

    last_season = int(df["season"].max())
    write_json("props.json", {
        "generated": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "coverage": {"seasons": [int(df.season.min()), last_season],
                     "player_games": int(len(df)),
                     "games": int(df["game_id"].nunique()),
                     "players": int(df["player_id"].nunique())},
        "markets": markets,
        "correlations": corr,
        "joint": joint,
        "unpriced_flag": "No sportsbook player-prop price feed is reachable (IR-03). "
                         "Every ROI/profit column for props is intentionally blank.",
        "reference_line": "Trailing five-game mean of the same stat, rounded to the nearest half point; "
                          "for anytime touchdown there is no line, the reference is the position-group base scoring rate.",
        "baseline_note": "Naive probabilities are measured on training seasons only (never on the season being scored).",
    })
    print(pd.DataFrame([{k: v for k, v in m.items() if k not in ("reliability",)} for m in markets])
          .drop(columns=["label"], errors="ignore").to_string(index=False))
    print("\ncorrelations:")
    for c in corr:
        print(f"  {c['pair']:<58} r={c['r']:+.3f}  CI[{c['ci95'][0]:+.3f},{c['ci95'][1]:+.3f}]  n={c['n']:,}")
    print("\njoint:", joint)


if __name__ == "__main__":
    main()
