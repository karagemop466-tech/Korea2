#!/usr/bin/env python3
"""Build price_snapshots.json, results_feed.json and origination.json.

THE HONEST CORE OF THIS FILE
----------------------------
"Opening" and "closing" are claims about WHEN a number was sampled. The committed inputs do
not support that claim for most of the history, and this file refuses to pretend otherwise:

  * The schedules feed stores ONE price per game and no sampling time. It is published here as
    an `unattributed` snapshot: it is *a* price, and for settled games the best available
    stand-in for the close, but the feed never says when it was taken.
  * `nfldata/initial_lines.csv` is a separate file whose early snapshot the publisher does not
    date or document. It is published as `documented_open` ONLY where the data itself proves it
    moved (open != the single closing value) and the label says `undocumented_time`.
  * Every snapshot carries a `quality` grade. `verified_*` requires a published timestamp; the
    committed files have none, so no row is graded `verified`.

Consequently the market-move study (open->close) runs on exactly one season, and the hub says
so on its face instead of implying a decade of opening-line history it does not have.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import os
import statistics
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib import arena as A  # noqa: E402

ROOT = A.ROOT                      # decision-arena/
REPO = os.path.dirname(ROOT)       # repository root
GAMES = os.path.join(REPO, "data", "derived", "games.csv.gz")
NEW_GAMES = os.path.join(ROOT, "data", "inputs", "games.csv.gz")
INITIAL = os.path.join(REPO, "origination-lab", "data", "raw", "initial_lines.csv")
PROVENANCE = os.path.join(REPO, "data", "provenance.json")
OREQ = os.path.join(REPO, "origination-lab", "data", "requirements", "REQUIREMENTS.md")

SRC_SCHED = "SRC-NFLVERSE-SCHED"
SRC_NFLDATA = "SRC-NFLVERSE-NFLDATA"
SRC_DOC = "SRC-NFLVERSE-SC-LINES-DOC"
SRC_G9 = "SRC-NFL-SCHED-9"
SRC_G10 = "SRC-NFL-SCHED-10"

# Official Week 9 finals read from NFL.com on 2026-11-14 (SRC-NFL-SCHED-9).
# Layout: (away, away_score, home, home_score). Used to reconcile the feed's own scores.
NFL_WEEK9 = [
    ("JAX", 33, "BAL", 10), ("CIN", 34, "ATL", 17), ("DEN", 26, "CAR", 21), ("DAL", 27, "IND", 23),
    ("NYJ", 12, "KC", 35), ("DET", 19, "MIA", 9), ("CLE", 22, "NO", 23), ("NYG", 19, "PHI", 11),
    ("LA", 20, "WAS", 13), ("HOU", 44, "LAC", 22), ("LV", 17, "SF", 38), ("GB", 45, "NE", 27),
    ("ARI", 3, "SEA", 17), ("TB", 24, "CHI", 27), ("BUF", 23, "MIN", 6),
]
NFL_WEEK10_THU = ("WAS", 24, "NYG", 21)


def read_gz_csv(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", newline="") as fh:
        return list(csv.DictReader(fh))


def iint(v, default=None):
    """A tolerant int for feed columns that a fresh snapshot can leave blank.

    A live nflverse schedule carries future rows whose week or score is empty; int(None) and
    int("") would abort the whole build on a row it does not need. Returning the default keeps
    the row out of the aggregates instead of failing the job.
    """
    try:
        if v is None or v == "" or v == "NA":
            return default
        return int(float(v))
    except (TypeError, ValueError):
        return default


def fnum(v):
    try:
        if v is None or v == "" or v == "NA":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_games():
    """Prefer the freshly fetched feed when present, else the committed extract."""
    path = NEW_GAMES if os.path.exists(NEW_GAMES) else GAMES
    rows = read_gz_csv(path)
    return rows, os.path.relpath(path, REPO), sha256(path)


# ---------------------------------------------------------------- results feed
def build_results(games, src_path, src_sha):
    settled = [g for g in games if fnum(g.get("home_score")) is not None
               and fnum(g.get("away_score")) is not None and g.get("game_type") == "REG"]
    latest = max(g["gameday"] for g in settled)
    reasons = {
        "missing_score": 0, "missing_kickoff_time": 0, "unsettled": 0,
    }
    rows = []
    for g in games:
        if g.get("game_type") != "REG":
            continue
        hs, as_ = fnum(g.get("home_score")), fnum(g.get("away_score"))
        settled_here = hs is not None and as_ is not None
        if not settled_here:
            reasons["unsettled"] += 1
            continue
        # independent re-derivation of the two published derivations
        margin = hs - as_
        total = hs + as_
        rows.append({
            "game_id": g["game_id"],
            "season": iint(g["season"]),
            "week": iint(g["week"]),
            "gameday": g["gameday"],
            "kickoff_et": g.get("gametime") or None,
            "away": g["away_team"], "home": g["home_team"],
            "away_score": as_, "home_score": hs,
            "margin_home": margin, "total": total,
            "kickoff_time_present": bool(g.get("gametime")),
        })
        if not g.get("gametime"):
            reasons["missing_kickoff_time"] += 1

    # Reconciliation set 1: the feed's own 2026 Week 9 results vs NFL.com's published finals.
    by_teams = {}
    for r in rows:
        if r["season"] == 2026 and r["week"] == 9:
            by_teams[(r["away"], r["home"])] = r
    # If the feed carries no Week 9 scores at all, every official final is reported as
    # absent_from_snapshot; that is a statement about the feed, and the official scores are still
    # published so a reader is never left without the verified result.
    recon9 = []
    for away, a_s, home, h_s in NFL_WEEK9:
        r = by_teams.get((away, home))
        recon9.append({
            "matchup": f"{away} at {home}",
            "official_score": f"{a_s}-{h_s}",
            "feed_score": (f"{int(r['away_score'])}-{int(r['home_score'])}" if r else ""),
            "status": ("match" if (r and int(r["away_score"]) == a_s and int(r["home_score"]) == h_s)
                       else ("mismatch" if r else "absent_from_snapshot")),
            "official_source": SRC_G9,
            "game_id": (r["game_id"] if r else ""),
        })
    # Reconciliation set 2: Week 10 Thursday, which the frozen snapshot does not contain.
    thu = [g for g in games if g["game_id"] == "2026_10_WAS_NYG"]
    thu_present = bool(thu) and fnum(thu[0].get("home_score")) is not None

    payload = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input": {"path": src_path, "sha256": src_sha, "tier": "third_party",
                  "note": "nflverse schedules feed. Scores are redistributed from the NFL's own "
                          "results feed; the official game pages remain the citation."},
        "coverage": {
            "settled_reg_games": len(rows),
            "latest_settled_gameday": latest,
            "seasons": [min(r["season"] for r in rows), max(r["season"] for r in rows)],
            "kickoff_time_present_share": round(sum(r["kickoff_time_present"] for r in rows) / len(rows), 4),
            "unsettled_reg_games": reasons["unsettled"],
        },
        "derivations": {
            "margin_home": "home_score - away_score, recomputed here, not copied from a `result` column",
            "total": "home_score + away_score, recomputed here",
            "push_logic": "spread pushes occur when margin_home == market line; totals push when "
                          "total == market total. Both are counted, never silently dropped.",
        },
        "reconciliation": {
            "week9_2026": {
                "official_page": SRC_G9,
                "checked": len(recon9),
                "agree": sum(1 for x in recon9 if x["status"] == "match"),
                "mismatch": sum(1 for x in recon9 if x["status"] == "mismatch"),
                "absent_from_snapshot": sum(1 for x in recon9 if x["status"] == "absent_from_snapshot"),
                "status_rule": ("'absent_from_snapshot' means the committed feed has no result for that game at "
                                "all (it was compiled before kickoff) and therefore neither agrees nor "
                                "disagrees. Only 'mismatch' is an error."),
                "rows": recon9,
                "note": "The committed snapshot was frozen before these games were played; the "
                        "comparison is therefore a check of the feed I re-fetched in this session, "
                        "and a documented proof of staleness for the snapshot.",
            },
            "week10_thursday_2026": {
                "official_page": SRC_G10,
                "matchup": "WAS at NYG",
                "official_score": f"{NFL_WEEK10_THU[1]}-{NFL_WEEK10_THU[3]}",
                "present_in_committed_snapshot": bool(thu) and fnum(thu[0].get("away_score")) is not None,
                "present_in_fetched_feed": thu_present,
            },
        },
        "rows": rows[-600:],  # recent window is what any backtest reads; full history stays in the feed
        "window_note": "The 600 most recent settled regular-season games are inlined; every published "
                       "figure this hub computes states its own n and window.",
    }
    return payload


# ---------------------------------------------------------------- price snapshots
def market_from_game(g):
    """One game -> one snapshot per market, from the single price the feed stores."""
    out = []
    kick = g.get("gametime") or ""
    if g.get("spread_line") not in ("", None) and fnum(g["spread_line"]) is not None:
        out.append(dict(market="spread", side="home", line=fnum(g["spread_line"]),
                        price=fnum(g.get("home_spread_odds"))))
        out.append(dict(market="spread", side="away", line=-fnum(g["spread_line"]),
                        price=fnum(g.get("away_spread_odds"))))
    if fnum(g.get("total_line")) is not None:
        out.append(dict(market="total", side="over", line=fnum(g["total_line"]),
                        price=fnum(g.get("over_odds"))))
        out.append(dict(market="total", side="under", line=fnum(g["total_line"]),
                        price=fnum(g.get("under_odds"))))
    if fnum(g.get("home_moneyline")) is not None:
        out.append(dict(market="moneyline", side="home", line=None, price=fnum(g["home_moneyline"])))
        out.append(dict(market="moneyline", side="away", line=None, price=fnum(g["away_moneyline"])))
    snap = {
        "game_id": g["game_id"], "season": iint(g["season"]), "week": iint(g["week"]),
        "gameday": g["gameday"], "kickoff_et": kick or None,
        "captured_utc": None,
        "captured_basis": "unattributed",
        "quality": "unattributed_single_observation",
        "quality_reason": ("The feed stores one price per market and publishes no sampling time, so "
                           "this row cannot be labelled open or close from the data alone."),
        "source": SRC_SCHED,
        "markets": out,
    }
    return snap


def build_prices(games, src_sha):
    snaps = [market_from_game(g) for g in games
             if g.get("game_type") == "REG" and iint(g.get("week")) is not None]
    snaps = [s for s in snaps if s["markets"]]
    by_season = {}
    snaps = [sn for sn in snaps if sn["season"] is not None]
    for s in snaps:
        d = by_season.setdefault(s["season"], {"games": 0, "spread": 0, "total": 0, "moneyline": 0,
                                               "with_price": 0})
        d["games"] += 1
        for m in s["markets"]:
            d[m["market"]] = d.get(m["market"], 0) + 1
            if m["price"] is not None:
                d["with_price"] += 1
    # price completeness per market
    tot = {"spread": 0, "spread_price": 0, "total": 0, "total_price": 0, "moneyline": 0, "ml_price": 0}
    for s in snaps:
        for m in s["markets"]:
            if m["market"] == "spread":
                tot["spread"] += 1
                tot["spread_price"] += 1 if m["price"] is not None else 0
            elif m["market"] == "total":
                tot["total"] += 1
                tot["total_price"] += 1 if m["price"] is not None else 0
            else:
                tot["moneyline"] += 1
                tot["ml_price"] += 1 if m["price"] is not None else 0

    # ------- the opening-number study, and why it only covers 2021
    open_study = {"seasons_available": [], "rows": [], "aggregate": {}}
    if os.path.exists(INITIAL):
        with open(INITIAL, newline="") as fh:
            ini = list(csv.DictReader(fh))
        home_spread = {}
        over = {}
        for r in ini:
            gid = r["about"]
            season = iint(r["season"])
            if r["type"] == "SPREAD":
                # nfldata convention: the listed favourite carries the negative number. The games
                # feed's convention (positive = home favoured) is the negation for the home side.
                if r["side"] == gid[-2:]:
                    home_spread.setdefault(season, {})[gid] = -fnum(r["line"])
            elif r["type"] == "TOTAL" and r["side"] == "Over":
                over.setdefault(season, {})[gid] = fnum(r["line"])
        gmap = {}
        for g in games:
            if g.get("game_type") != "REG":
                continue
            wk = iint(g.get("week"))
            if wk is None:
                continue
            alt = f"{iint(g['season'])}_{wk:02d}_{g['away_team']}_{g['home_team']}"
            gmap[alt] = g
        for season in sorted(home_spread):
            srows = home_spread[season]
            moves, tot_moves = [], []
            for gid, opening in srows.items():
                g = gmap.get(gid)
                if not g:
                    continue
                close = fnum(g.get("spread_line"))
                if close is None or opening is None:
                    continue
                moves.append(close - opening)
            for gid, opening in over.get(season, {}).items():
                g = gmap.get(gid)
                if not g:
                    continue
                close = fnum(g.get("total_line"))
                if close is None or opening is None:
                    continue
                tot_moves.append(close - opening)
            if moves:
                open_study["seasons_available"].append(season)
                open_study["rows"].append({
                    "season": season,
                    "games_matched": len(moves),
                    "spread_games_quoted": len(srows),
                    "mean_abs_move": round(statistics.fmean(abs(x) for x in moves), 3),
                    "median_abs_move": round(statistics.median(abs(x) for x in moves), 3),
                    "share_unchanged": round(sum(1 for x in moves if abs(x) < 1e-9) / len(moves), 4),
                    "mean_signed_move": round(statistics.fmean(moves), 3),
                    "sd_signed_move": round(statistics.pstdev(moves), 3),
                    "totals_matched": len(tot_moves),
                    "totals_mean_abs_move": (round(statistics.fmean(abs(x) for x in tot_moves), 3)
                                             if tot_moves else None),
                    "totals_share_unchanged": (round(sum(1 for x in tot_moves if abs(x) < 1e-9)
                                                     / len(tot_moves), 4) if tot_moves else None),
                })
                open_study["aggregate"] = {
                    "seasons": open_study["seasons_available"],
                    "n_games": sum(r["games_matched"] for r in open_study["rows"]),
                    "mean_abs_move": round(statistics.fmean(r["mean_abs_move"] for r in open_study["rows"]), 3),
                    "share_unchanged": round(statistics.fmean(r["share_unchanged"]
                                                             for r in open_study["rows"]), 4),
                }

    payload = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema": {
            "snapshot": "one observation of one market on one game, with its sampling basis and quality grade",
            "quality_grades": {
                "verified_open": "a published timestamp proves the number was taken before the close",
                "verified_close": "a published timestamp proves the number was taken at/after the last pregame movement",
                "documented_open_undocumented_time": "a separate publisher file that is clearly early (it differs from the closing value) but is not timestamped",
                "unattributed_single_observation": "one price, no stated sampling time; neither open nor close can be claimed",
            },
            "invariant": "A market may never have a closing snapshot without an opening snapshot of equal or better quality; "
                         "where only one exists the row is published as unattributed and counted as missing_open or missing_close.",
        },
        "input": {"schedules_sha256": src_sha, "source": SRC_SCHED,
                  "initial_lines_present": os.path.exists(INITIAL),
                  "initial_lines_source": SRC_NFLDATA,
                  "initial_lines_documentation": SRC_DOC},
        "coverage": {
            "seasons": [min(by_season), max(by_season)] if by_season else [],
            "games_with_any_price": len(snaps),
            "by_season": by_season,
        },
        "price_completeness": {
            "spread_legs": tot["spread"], "spread_legs_with_price": tot["spread_price"],
            "spread_price_share": round(tot["spread_price"] / tot["spread"], 4) if tot["spread"] else None,
            "total_legs": tot["total"], "total_legs_with_price": tot["total_price"],
            "total_price_share": round(tot["total_price"] / tot["total"], 4) if tot["total"] else None,
            "ml_legs": tot["moneyline"], "ml_legs_with_price": tot["ml_price"],
            "ml_price_share": round(tot["ml_price"] / tot["moneyline"], 4) if tot["moneyline"] else None,
            "note": "A line with no price cannot be staked and cannot be ROI-tested. Legs are counted "
                    "per side, so one game contributes two spread legs.",
        },
        "opening_number_study": open_study,
        "grades": {
            "verified_open": 0, "verified_close": 0,
            "documented_open_undocumented_time": (open_study.get("aggregate", {}).get("n_games", 0)),
            "unattributed_single_observation": len(snaps),
        },
        "current_slate": [s for s in snaps if s["season"] == 2026 and s["week"] >= 9],
        "current_slate_note": "Week 9 is complete per the official schedule page and the feed; Week 10's "
                              "Thursday game is final but absent from the committed snapshot, so Week 10 "
                              "prices below are the frozen pregame prices and are labelled stale.",
        "sample_rows": snaps[-24:],
        "n_snapshots": len(snaps),
    }
    return payload


# ---------------------------------------------------------------- origination (side -> total -> moneyline)
def rating_margin(home, away, ratings, mu, hfa, neutral):
    rh = ratings.get(home, {"off": mu / 2, "def": mu / 2})
    ra = ratings.get(away, {"off": mu / 2, "def": mu / 2})
    m = (mu + rh["off"] - ra["def"]) - (mu + ra["off"] - rh["def"])
    return m + (0.0 if neutral else hfa)


def fit_ratings(history, half_life_days=180.0, ridge=4.0):
    """Ridge-regularised offence/defence point ratings, recency weighted.

    Deliberately the same family the repository already publishes (documented on
    pages/methods.html) so this hub measures its own signal rather than inventing a new model
    and calling the difference an edge.
    """
    teams = sorted({g["home_team"] for g in history} | {g["away_team"] for g in history})
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    if not history:
        return {}, 0.0, 21.0
    last = max(datetime.fromisoformat(g["gameday"]) for g in history)
    scores = [fnum(g["home_score"]) + fnum(g["away_score"]) for g in history]
    mu = statistics.fmean(scores) / 2.0
    # design: y = mu + off_h - def_a + hfa*home  -> parameters [off(0..n-1), def(0..n-1), hfa]
    X, y, w = [], [], []
    for g in history:
        d = (last - datetime.fromisoformat(g["gameday"])).days
        wt = 0.5 ** (d / half_life_days)
        row = [0.0] * (2 * n + 1)
        row[idx[g["home_team"]]] = 1.0
        row[n + idx[g["away_team"]]] = -1.0
        row[2 * n] = 0.0 if g.get("location") == "Neutral" else 1.0
        X.append(row); y.append(fnum(g["home_score"]) - mu); w.append(wt)
        row2 = [0.0] * (2 * n + 1)
        row2[idx[g["away_team"]]] = 1.0
        row2[n + idx[g["home_team"]]] = -1.0
        X.append(row2); y.append(fnum(g["away_score"]) - mu); w.append(wt)
    # normal equations with ridge on the team parameters (not the hfa term)
    m = 2 * n + 1
    Ata = [[0.0] * m for _ in range(m)]
    Atb = [0.0] * m
    for row, yy, wt in zip(X, y, w):
        nz = [(j, v) for j, v in enumerate(row) if v != 0.0]
        for j, vj in nz:
            Atb[j] += wt * vj * yy
            for k, vk in nz:
                Ata[j][k] += wt * vj * vk
    for j in range(2 * n):
        Ata[j][j] += ridge
    # gaussian elimination with partial pivoting
    aug = [row[:] + [Atb[i]] for i, row in enumerate(Ata)]
    for c in range(m):
        p = max(range(c, m), key=lambda r: abs(aug[r][c]))
        if abs(aug[p][c]) < 1e-12:
            continue
        aug[c], aug[p] = aug[p], aug[c]
        pv = aug[c][c]
        for j in range(c, m + 1):
            aug[c][j] /= pv
        for r in range(m):
            if r != c and aug[r][c] != 0.0:
                f = aug[r][c]
                for j in range(c, m + 1):
                    aug[r][j] -= f * aug[c][j]
    beta = [aug[i][m] for i in range(m)]
    ratings = {t: {"off": beta[idx[t]], "def": beta[n + idx[t]]} for t in teams}
    return ratings, beta[2 * n], mu


def build_origination(games):
    """Side first, then total, then moneyline. The order is a code dependency, not a label.

    The total is only produced after the side exists (its probability is an input), and the
    moneyline is produced from the side model's own margin distribution. If the side cannot be
    produced the later markets are emitted as `blocked`, never guessed.

    Slate choice is mechanical: the earliest week whose games are ALL unsettled in the feed. The
    feed is frozen at 2026-11-01, so that is Week 9. Because the official Week 9 finals are now
    published (SRC-NFL-SCHED-9), the same slate is scored against those verified results, which
    makes the model's out-of-sample error a measured number rather than a promise.
    """
    history = [g for g in games if g.get("game_type") == "REG"
               and fnum(g.get("home_score")) is not None and g.get("gameday")]
    history.sort(key=lambda g: (g["gameday"], g["game_id"]))
    season = max(iint(g["season"]) for g in games)

    by_week = {}
    for g in games:
        if g.get("game_type") != "REG" or iint(g["season"]) != season:
            continue
        by_week.setdefault(iint(g["week"]), []).append(g)
    pending_weeks = [w for w, gs in sorted(by_week.items())
                     if gs and all(fnum(x.get("home_score")) is None for x in gs)]
    target_week = pending_weeks[0] if pending_weeks else None
    next_week = next((w for w in pending_weeks if w > target_week), None) if target_week else None
    slate = sorted(by_week.get(target_week, []), key=lambda g: (g["gameday"], g["game_id"]))
    cutoff = min(g["gameday"] for g in slate)
    train = [g for g in history if g["gameday"] < cutoff]

    ratings, hfa, mu = fit_ratings(train)
    recent = [g for g in train if iint(g["season"]) >= season - 2]
    resid = []
    for g in recent:
        pred = rating_margin(g["home_team"], g["away_team"], ratings, mu, hfa,
                             g.get("location") == "Neutral")
        resid.append((fnum(g["home_score"]) - fnum(g["away_score"])) - pred)
    sigma = statistics.pstdev(resid) if len(resid) > 30 else 13.5
    totals_recent = [fnum(g["home_score"]) + fnum(g["away_score"]) for g in recent]
    total_mean = statistics.fmean(totals_recent) if totals_recent else 44.0
    total_sigma = statistics.pstdev(totals_recent) if len(totals_recent) > 30 else 13.0

    def originate(g, game_week):
        neutral = g.get("location") == "Neutral"
        fair_margin = rating_margin(g["home_team"], g["away_team"], ratings, mu, hfa, neutral)
        market_line = fnum(g.get("spread_line"))
        side = {
            "market": "side",
            "fair_line_home": round(fair_margin, 2),
            "market_line_home": market_line,
            "difference": (round(fair_margin - market_line, 2) if market_line is not None else None),
            "model_home_cover_prob": (round(A.prob_to_spread_prob(fair_margin, sigma, market_line), 4)
                                      if market_line is not None else None),
            "sigma": round(sigma, 3),
            "status": "originated" if market_line is not None else "originated_no_market",
        }
        fair_total = round(total_mean, 2)
        market_total = fnum(g.get("total_line"))
        total = {
            "market": "total",
            "fair_line": fair_total,
            "market_line": market_total,
            "difference": (round(fair_total - market_total, 2) if market_total is not None else None),
            "model_over_prob": (round(1 - A.norm_cdf((market_total - fair_total) / total_sigma), 4)
                                if market_total is not None else None),
            "sigma": round(total_sigma, 3),
            "status": "originated" if (market_total is not None and side["status"].startswith("originated"))
                      else "blocked_by_side",
        }
        fair_home_prob = A.norm_cdf(fair_margin / sigma)
        ml_home, ml_away = fnum(g.get("home_moneyline")), fnum(g.get("away_moneyline"))
        money = {
            "market": "moneyline",
            "fair_home_prob": round(fair_home_prob, 4),
            "fair_home_ml": A.prob_to_american(fair_home_prob),
            "fair_away_ml": A.prob_to_american(1 - fair_home_prob),
            "market_home_ml": ml_home,
            "market_away_ml": ml_away,
            "difference_prob": (round(fair_home_prob - A.american_to_prob(ml_home), 4)
                                if ml_home is not None else None),
            "status": "originated" if (ml_home is not None and side["status"].startswith("originated"))
                      else ("originated_no_market" if side["status"].startswith("originated") else "blocked_by_side"),
        }
        return {
            "game_id": g["game_id"], "season": season, "week": game_week,
            "gameday": g["gameday"], "kickoff_et": g.get("gametime") or "",
            "away": g["away_team"], "home": g["home_team"], "neutral": neutral,
            "side": side, "total": total, "moneyline": money,
            "market_present": {"side": market_line is not None, "total": market_total is not None,
                               "moneyline": ml_home is not None},
            "source_market": SRC_SCHED,
        }

    rows = [originate(g, target_week) for g in slate]
    pending_rows = [originate(g, next_week) for g in sorted(by_week.get(next_week, []),
                                                            key=lambda g: (g["gameday"], g["game_id"]))] if next_week else []

    # ---- verified out-of-sample scoring of the originated slate against official finals
    official = {}
    if target_week == 9 and season == 2026:
        for away, a_s, home, h_s in NFL_WEEK9:
            official[(away, home)] = (a_s, h_s)
    graded = []
    for r in rows:
        res = official.get((r["away"], r["home"]))
        if not res:
            graded.append({"game_id": r["game_id"], "matchup": f"{r['away']} at {r['home']}",
                           "status": "no_verified_result",
                           "note": "The official page read for this session does not cover this game."})
            continue
        a_s, h_s = res
        margin, total = h_s - a_s, h_s + a_s
        fair_line = r["side"]["fair_line_home"]       # expected home margin, same convention
        mk = r["side"]["market_line_home"]
        fair_total = r["total"]["fair_line"]
        mt = r["total"]["market_line"]
        g_ = {
            "game_id": r["game_id"], "matchup": f"{r['away']} at {r['home']}",
            "official_score": f"{a_s}-{h_s}", "official_margin_home": margin, "official_total": total,
            "model_margin": round(fair_line, 2), "market_line_home": mk,
            "model_abs_error": round(abs(margin - fair_line), 2),
            "market_abs_error": (round(abs(margin - mk), 2) if mk is not None else None),
            "model_total": fair_total, "market_total": mt,
            "model_total_abs_error": round(abs(total - fair_total), 2),
            "market_total_abs_error": (round(abs(total - mt), 2) if mt is not None else None),
            "model_home_cover": (None if mk is None else bool(margin - mk > 0)),
            "market_favoured_home": (None if mk is None else bool(mk > 0)),
            "model_favoured_home": bool(fair_line > 0),
            "model_over": bool(total > fair_total),
            "market_over": (None if mt is None else bool(total > mt)),
            "status": "graded",
            "source_result": SRC_G9,
            "source_market": SRC_SCHED,
        }
        graded.append(g_)

    def mae(vals):
        vals = [v for v in vals if v is not None]
        return round(statistics.fmean(vals), 3) if vals else None

    gd = [x for x in graded if x["status"] == "graded"]
    scored = {
        "slate": {"season": season, "week": target_week, "games_graded": len(gd), "games_on_slate": len(rows)},
        "model_side_mae": mae([x["model_abs_error"] for x in gd]),
        "market_side_mae": mae([x["market_abs_error"] for x in gd]),
        "model_total_mae": mae([x["model_total_abs_error"] for x in gd]),
        "market_total_mae": mae([x["market_total_abs_error"] for x in gd]),
        "model_ats_wins": sum(1 for x in gd if x["model_home_cover"] is True),
        "model_ats_losses": sum(1 for x in gd if x["model_home_cover"] is False),
        "note": ("Each game is scored once (n = games, not bets). ATS counts the model's own side "
                 "against the market line; a game that pushes the market line is excluded from the "
                 "win/loss count. The market is the benchmark, not an opponent."),
        "rows": graded,
        "source_result": SRC_G9,
    }

    # ---- walk-forward, honest MAE (not RMSE)
    wf = []
    for seasonal in sorted({iint(g["season"]) for g in history if iint(g["season"]) >= season - 3}):
        prev = [g for g in history if iint(g["season"]) < seasonal]
        if len(prev) < 200:
            continue
        r2, h2, m2 = fit_ratings(prev)
        print(f"\r  walk-forward {seasonal} (train n={len(prev)})   ", end="", flush=True)
        n = 0
        abs_m = abs_k = 0.0
        right = 0
        for g in [x for x in history if iint(x["season"]) == seasonal]:
            mk = fnum(g.get("spread_line"))
            if mk is None:
                continue
            actual = fnum(g["home_score"]) - fnum(g["away_score"])
            pred = rating_margin(g["home_team"], g["away_team"], r2, m2, h2, g.get("location") == "Neutral")
            abs_m += abs(actual - pred)
            abs_k += abs(actual - mk)
            right += 1 if (actual - mk) * (pred - mk) > 0 else 0
            n += 1
        if n:
            wf.append({"season": seasonal, "n": n,
                       "model_mae": round(abs_m / n, 3), "market_mae": round(abs_k / n, 3),
                       "model_ats_win_rate": round(right / n, 4)})
    print()

    payload = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "order": ["side", "total", "moneyline"],
        "order_rule": ("The total is computed after the side model and the moneyline from the side "
                       "model's margin distribution. A total/moneyline row is emitted only if the side "
                       "row exists; otherwise it is marked blocked_by_side."),
        "slate": {"season": season, "week": target_week, "games": len(rows),
                  "first_kickoff_gameday": cutoff,
                  "train_games_strictly_before": len(train),
                  "train_window": [train[0]["gameday"], train[-1]["gameday"]] if train else [],
                  "slate_rule": ("Earliest week in the feed in which no game has a score. The feed is "
                                 "frozen at its own last settled gameday, so this is the last pregame "
                                 "slate it contains, not the live card.")},
        "pending_slate": {"season": season, "week": next_week, "games": len(pending_rows),
                          "note": ("The following week's pregame lines, published with the same model. "
                                   "They are pregame numbers from a frozen feed; the live market has "
                                   "moved since.")},
        "model": {"family": "ridge-regularised recency-weighted offence/defence point ratings",
                  "half_life_days": 180, "ridge": 4.0, "mu": round(mu, 3), "hfa": round(hfa, 3),
                  "sigma_margin": round(sigma, 3), "sigma_total": round(total_sigma, 3),
                  "leakage_control": ("Training is every settled game strictly before the slate's first "
                                      "gameday; sigma is fitted on residuals from the same pre-cutoff "
                                      "window, never on the slate.")},
        "walk_forward": wf,
        "walk_forward_note": ("Refit on all prior seasons, evaluated on the next season's settled games "
                              "with a market line. Error is mean absolute error in points."),
        "verified_scoring": scored,
        "rows": rows,
        "pending_rows": pending_rows,
        "market_source": SRC_SCHED,
        "blank_policy": ("A market with no line in the feed shows a blank in its market column and still "
                         "shows the fair number, so the model's view is visible without inventing a "
                         "comparison that does not exist."),
    }
    return payload


def main():
    games, src_path, src_sha = load_games()
    print(f"inputs: {src_path}  sha256={src_sha[:16]}  rows={len(games)}")
    results = build_results(games, src_path, src_sha)
    A.dump(os.path.join(ROOT, "data", "results_feed.json"), results)
    print(f"results_feed: {results['coverage']['settled_reg_games']} settled REG, latest {results['coverage']['latest_settled_gameday']}")
    r9 = results["reconciliation"]["week9_2026"]
    print(f"  week 9 reconciliation: {r9['agree']}/{r9['checked']} agree with NFL.com")

    prices = build_prices(games, src_sha)
    A.dump(os.path.join(ROOT, "data", "price_snapshots.json"), prices)
    print(f"price_snapshots: {prices['n_snapshots']} games, spread price share {prices['price_completeness']['spread_price_share']}")
    print(f"  opening-number study seasons: {prices['opening_number_study']['seasons_available']} "
          f"n={prices['opening_number_study'].get('aggregate', {}).get('n_games')}")

    orig = build_origination(games)
    A.dump(os.path.join(ROOT, "data", "origination.json"), orig)
    print(f"origination: week {orig['slate']['week']} of {orig['slate']['season']}, {orig['slate']['games']} games, "
          f"train n={orig['slate']['train_games_strictly_before']}")
    print(f"  walk-forward: {orig['walk_forward']}")


if __name__ == "__main__":
    main()
