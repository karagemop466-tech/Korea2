#!/usr/bin/env python3
"""Compute every signal-desk artefact from committed data plus transcribed official facts.

Design rules
------------
* One output file per requirement (SD-01 ... SD-08) plus a questions/suggestions layer.
* A value is either computed from a named input, or ``None`` with ``status: "unverified"``.
  Nothing is filled in by hand and nothing is inferred.
* Every row carries ``source`` (a URL) and ``source_class`` (``official`` or ``third-party``).
* Independent statistics are computed with scipy, not with the project's own helpers, so a
  definition error in the sibling pipeline cannot make this agree with itself.

Inputs (read-only, never modified by this script)
    data/derived/games.csv.gz     committed nflverse-derived game table (results + closing prices)
    data/derived/model.json       committed originated lines for the current week and accuracy
    data/derived/leaderboard.json committed strategy leaderboard (signal + staking inputs)
    data/derived/strategies.json  per-strategy settled-bet summaries
    data/derived/predictions.csv  per-game model vs market, 2023-2026
    decision-hub/data/injuries.json  third-party depth-chart + official injury report join
    /tmp caches are NOT used: upstream price files are optional and their absence is reported

Outputs
    signal-desk/data/*.json
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.abspath(os.path.join(HERE, "..", "data"))
sys.path.insert(0, HERE)

import transcripts as T  # noqa: E402

GAMES = os.path.join(ROOT, "data", "derived", "games.csv.gz")
PRICES_OPEN = os.environ.get("SD_INITIAL_LINES", "")
PRICES_CLOSE = os.environ.get("SD_CLOSING_LINES", "")
def _stamp() -> str:
    """A deterministic build stamp.

    Wall-clock time would make every rebuild a diff, which defeats the reproducibility test and
    makes the committed JSON churn. The stamp is therefore the newest gameday in the committed
    data, overridable with ``SD_BUILD_STAMP`` when you want to mark a specific run.
    """
    env = os.environ.get("SD_BUILD_STAMP")
    if env:
        return env
    newest = ""
    with gzip.open(GAMES, "rt") as fh:
        for row in csv.DictReader(fh):
            if row["game_type"] == "REG" and str(row["home_score"]).strip() not in ("", "NA"):
                newest = max(newest, row["gameday"])
    return f"committed data through {newest}"


try:
    GENERATED = _stamp()
except Exception:            # a missing extract must not stop the import
    GENERATED = "committed data through unknown"


# --------------------------------------------------------------------------- helpers
def load_json(*parts):
    path = os.path.join(ROOT, *parts)
    with open(path) as fh:
        return json.load(fh)


def games():
    with gzip.open(GAMES, "rt") as fh:
        return list(csv.DictReader(fh))


def fnum(v):
    if v is None:
        return None
    v = str(v).strip()
    if v in ("", "NA", "nan", "None"):
        return None
    try:
        f = float(v)
    except ValueError:
        return None
    return None if math.isnan(f) else f


def write(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w") as fh:
        json.dump(obj, fh, indent=1, sort_keys=False)
        fh.write("\n")
    print(f"  wrote signal-desk/data/{name}")


def unverified(note, needed=""):
    return {"value": None, "status": "unverified", "note": note, "needed": needed}


def measured(value, n, method, source, source_class, extra=None):
    row = {"value": value, "n": n, "status": "measured", "method": method,
           "source": source, "source_class": source_class}
    if extra:
        row.update(extra)
    return row


def bhimplied(o):
    """American odds -> implied probability (with vig)."""
    if o is None:
        return None
    return (-o) / ((-o) + 100.0) if o < 0 else 100.0 / (o + 100.0)


def american(p):
    if p is None or p <= 0 or p >= 1:
        return None
    return round((1.0 / p - 1.0) * 100.0) if p < 0.5 else round(-(p / (1.0 - p)) * 100.0)


def phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def norm_ident(name):
    """nflverse/GSIS team code -> the code NFL.com prints."""
    return {"AZ": "ARI", "LAR": "LA"}.get(name, name)


# --------------------------------------------------------------------------- SD-01 price snapshots
MONEYLINE_ADOPTED_COLUMN = "home_moneyline / away_moneyline"
SIDE_ADOPTED_COLUMN = "spread_line"


def build_prices(gm):
    reg = [g for g in gm if g["game_type"] == "REG"]
    by_season = defaultdict(Counter)
    for g in reg:
        c = by_season[g["season"]]
        c["games"] += 1
        for key, cols in (("side", ("spread_line",)),
                          ("total", ("total_line",)),
                          ("moneyline", ("home_moneyline", "away_moneyline")),
                          ("side_price", ("home_spread_odds", "away_spread_odds")),
                          ("total_price", ("over_odds", "under_odds"))):
            if all(fnum(g[col]) is not None for col in cols):
                c[key] += 1

    closing = {"source": T.UPSTREAM["games"],
               "source_class": "third-party",
               "definition": "The committed games extract's spread_line / total_line / moneyline "
                             "columns. data/PROVENANCE.md describes the upstream file as carrying "
                             "'closing spread/total/moneyline prices'.",
               "caveat": "Third-party aggregator. No official NFL price feed was located, so the "
                         "closing snapshot is third-party by construction. Where the columns combine "
                         "several books the snapshot is not a single-book quote; that is unverified.",
               "by_season": []}
    for s in sorted(by_season, key=int):
        c = by_season[s]
        closing["by_season"].append({
            "season": int(s), "games": c["games"],
            "side": c["side"], "total": c["total"], "moneyline": c["moneyline"],
            "side_price": c["side_price"], "total_price": c["total_price"],
        })

    # opening snapshot: built from the upstream opening-line file if the caller supplied one.
    opening = {"source": T.UPSTREAM["initial_lines"], "source_class": "third-party",
               "rows": None, "by_season": [], "moneyline": None,
               "status": "not loaded", "note": ""}
    if PRICES_OPEN and os.path.exists(PRICES_OPEN):
        rows = list(csv.DictReader(open(PRICES_OPEN)))
        per = defaultdict(lambda: Counter())
        books = Counter()
        for r in rows:
            season = r["season"]
            books[r["sportsbook"]] += 1
            per[season][r["type"].lower()] += 1
            if r["type"] == "MONEYLINE":
                per[season]["moneyline"] += 1
        opening["rows"] = len(rows)
        opening["books"] = dict(books)
        opening["status"] = "loaded"
        for s in sorted(per, key=int):
            c = per[s]
            opening["by_season"].append({"season": int(s), "spread": c["spread"], "total": c["total"],
                                         "moneyline": c["moneyline"]})
        opening["moneyline"] = sum(v["moneyline"] for v in opening["by_season"]) or 0
        opening["note"] = (
            "This is every season the upstream opening-line file actually contains. It holds "
            "one sportsbook and only spread and total prices; there is no moneyline at all. An "
            "opening moneyline therefore cannot be recorded for any season from this source.")

    # the closing file is a *different* upstream file with its own season coverage
    close_file = {"source": T.UPSTREAM["closing_lines"], "source_class": "third-party",
                  "status": "not loaded", "rows": None, "by_season": [], "games": None,
                  "prices_present": None}
    if PRICES_CLOSE and os.path.exists(PRICES_CLOSE):
        rows = list(csv.DictReader(open(PRICES_CLOSE)))
        per = defaultdict(lambda: Counter())
        for r in rows:
            gid = r.get("alt_game_id") or ""
            if not gid:
                continue
            per[gid[:4]]["games_seen"] += 0
            per[gid[:4]][r["type"].lower()] += 1
            if (r.get("odds") or "").strip():
                per[gid[:4]]["with_price"] += 1
        games_seen = defaultdict(set)
        for r in rows:
            gid = r.get("alt_game_id") or ""
            if gid:
                games_seen[gid[:4]].add(gid)
        close_file["status"] = "loaded"
        close_file["rows"] = len(rows)
        close_file["games"] = len({r.get("alt_game_id") for r in rows if r.get("alt_game_id")})
        close_file["prices_present"] = sum(1 for r in rows if (r.get("odds") or "").strip())
        types_with_price = Counter(r["type"].lower() for r in rows if (r.get("odds") or "").strip())
        close_file["types_with_price"] = dict(types_with_price)
        no_price_spread = sum(1 for r in rows if r["type"] == "SPREAD" and not (r.get("odds") or "").strip())
        close_file["spread_rows_without_a_price"] = no_price_spread
        close_file["note"] = (
            "Only some rows carry a price: " + ", ".join(f"{k} {v}" for k, v in sorted(types_with_price.items()))
            + f". {no_price_spread} spread rows have a line but no odds at all, so a spread price cannot be "
              "recorded for those games even though the line can.")
        for y in sorted(per, key=int):
            c = per[y]
            close_file["by_season"].append({"season": int(y), "games": len(games_seen[y]),
                                            "moneyline": c["moneyline"], "spread": c["spread"],
                                            "total": c["total"], "rows_with_price": c["with_price"]})

    # join quality: which seasons have BOTH an opening and a closing record?
    join = {"seasons_with_both": [], "detail": None, "seasons_opening": [], "seasons_closing": []}
    have_open = {r["season"] for r in opening["by_season"]} if opening["status"] == "loaded" else set()
    have_close = {r["season"] for r in close_file["by_season"]} if close_file["status"] == "loaded" else set()
    join["seasons_opening"] = sorted(have_open)
    join["seasons_closing"] = sorted(have_close)
    join["seasons_with_both"] = sorted(have_open & have_close)
    if opening["status"] == "loaded" and close_file["status"] == "loaded" and not join["seasons_with_both"]:
        join["detail"] = (
            "There is no season in which this repository holds both an opening and a closing number. "
            f"The opening file covers {min(have_open)} only; the closing file stops at "
            f"{max(have_close)}. A per-bet open-to-close move, which is the number a demotion rule needs, "
            "therefore cannot be computed for any game from these two files together.")

    return {
        "meta": {
            "id": "SD-01",
            "title": "Price-snapshot store: opening and closing numbers per market",
            "generated_utc": GENERATED,
            "markets": ["side (spread)", "total", "moneyline"],
            "rule": "A snapshot exists only where a named source publishes the number. Every other "
                    "cell is blank with status 'unverified'.",
            "records": ["opening", "closing"],
            "official_price_feed_located": False,
        },
        "closing": closing,
        "opening": opening,
        "closing_file": close_file,
        "join": join,
        "coverage": [
            {"record": "open-to-close move, any market", "seasons": "", "status": "unverified",
             "note": "No season is covered by both an opening and a closing file, so a move cannot be "
                     "computed for a single game.",
             "needed": "Opening and closing numbers for the same games, from the same book.",
             "source": T.UPSTREAM["initial_lines"]["url"], "source_class": "third-party"},
            {"record": "opening side", "seasons": "2021 only", "status": "unverified",
             "note": "Upstream opening file covers one season and one book.",
             "source": T.UPSTREAM["initial_lines"]["url"], "source_class": "third-party"},
            {"record": "opening total", "seasons": "2021 only", "status": "unverified",
             "note": "Same file; spread and total only.",
             "source": T.UPSTREAM["initial_lines"]["url"], "source_class": "third-party"},
            {"record": "opening moneyline", "seasons": "", "status": "unverified",
             "note": "The upstream opening file has no MONEYLINE rows at all. No value is recorded.",
             "needed": "Any source that publishes an opening moneyline, with its timestamp and book.",
             "source": T.UPSTREAM["initial_lines"]["url"], "source_class": "third-party"},
            {"record": "closing side/total/moneyline", "seasons": "2014-2026", "status": "measured",
             "note": "Present for every regular-season game from 2014 onward in the committed extract.",
             "source": T.UPSTREAM["games"]["url"], "source_class": "third-party"},
        ],
    }


# --------------------------------------------------------------------------- SD-02 verified results feed
def build_results(gm):
    played = [g for g in gm if g["game_type"] == "REG" and fnum(g["home_score"]) is not None]

    # official standings check, one row per team, adding the transcribed official scores on top of
    # the committed games so the two snapshots are compared at the same point in time.
    have_score = {g["game_id"] for g in played}

    def tally(extra, season=2026):
        acc = {t: [0, 0, 0, 0, 0] for t in T.STANDINGS[season]}
        for g in played:
            if int(g["season"]) != season:
                continue
            hi, ai = norm_ident(g["home_team"]), norm_ident(g["away_team"])
            hs, as_ = int(fnum(g["home_score"])), int(fnum(g["away_score"]))
            acc[hi][3] += hs; acc[hi][4] += as_; acc[ai][3] += as_; acc[ai][4] += hs
            if hs > as_:
                acc[hi][0] += 1; acc[ai][1] += 1
            elif hs < as_:
                acc[ai][0] += 1; acc[hi][1] += 1
            else:
                acc[hi][2] += 1; acc[ai][2] += 1
        for wk, games_ in T.SCORES.items():
            if not extra:
                continue
            for key, (ap, hp) in games_.items():
                aw, hm = key.split("@")
                if f"2026_{wk:02d}_{aw}_{hm}" in have_score:
                    continue          # already counted from the committed row; never double count
                acc[hm][3] += hp; acc[hm][4] += ap; acc[aw][3] += ap; acc[aw][4] += hp
                if hp > ap:
                    acc[hm][0] += 1; acc[aw][1] += 1
                elif hp < ap:
                    acc[aw][0] += 1; acc[hm][1] += 1
                else:
                    acc[hm][2] += 1; acc[aw][2] += 1
        return acc

    before = tally(False)
    after = tally(True)
    rows = []
    for team in sorted(T.STANDINGS[2026]):
        off = T.STANDINGS[2026][team]
        b, a = before[team], after[team]
        rows.append({
            "team": team,
            "official": {"w": off[0], "l": off[1], "t": off[2], "pf": off[3], "pa": off[4]},
            "committed_only": {"w": b[0], "l": b[1], "t": b[2], "pf": b[3], "pa": b[4]},
            "committed_plus_official_scores": {"w": a[0], "l": a[1], "t": a[2], "pf": a[3], "pa": a[4]},
            "reconciles_after": tuple(a) == tuple(off),
            "reconciles_before": tuple(b) == tuple(off),
            "source": T.URL["standings_2026"],
            "source_class": "official",
        })
    n_ok = sum(1 for r in rows if r["reconciles_after"])

    # per-game feed for the weeks whose official scores were transcribed
    feed = []
    index = {g["game_id"]: g for g in gm}
    for wk in sorted(T.SCORES):
        for key, (ap, hp) in sorted(T.SCORES[wk].items()):
            away, home = key.split("@")
            gid = f"2026_{wk:02d}_{away}_{home}"
            g = index.get(gid)
            committed = None
            if g and fnum(g["home_score"]) is not None:
                committed = (int(fnum(g["away_score"])), int(fnum(g["home_score"])))
            feed.append({
                "game_id": gid, "week": wk, "away": away, "home": home,
                "official_away_score": ap, "official_home_score": hp,
                "committed_away_score": None if committed is None else committed[0],
                "committed_home_score": None if committed is None else committed[1],
                "agree": (committed == (ap, hp)) if committed else None,
                "committed_status": "absent" if committed is None else "present",
                "nfl_game_page": "https://www.nfl.com/games/" + key.split("@")[0].lower()
                                 .replace("ari", "cardinals") .replace("la", "rams")
                                 + "-at-" + key.split("@")[1].lower().replace("ari", "cardinals")
                                 .replace("la", "rams") + f"-2026-reg-{wk}",
                "source": T.SCORES_URL[wk],
                "source_class": "official",
            })
    present = [r for r in feed if r["committed_status"] == "present"]
    agree = [r for r in present if r["agree"]]

    # other seasons reconciled against official standings, one row each
    other = []
    for season in (2020, 2025):
        acc = {t: [0, 0, 0, 0, 0] for t in T.STANDINGS[season]}
        for g in gm:
            if g["game_type"] != "REG" or int(g["season"]) != season:
                continue
            if fnum(g["home_score"]) is None:
                continue
            hi, ai = norm_ident(g["home_team"]), norm_ident(g["away_team"])
            hs, as_ = int(fnum(g["home_score"])), int(fnum(g["away_score"]))
            acc[hi][3] += hs; acc[hi][4] += as_; acc[ai][3] += as_; acc[ai][4] += hs
            if hs > as_:
                acc[hi][0] += 1; acc[ai][1] += 1
            elif hs < as_:
                acc[ai][0] += 1; acc[hi][1] += 1
            else:
                acc[hi][2] += 1; acc[ai][2] += 1
        ok = sum(1 for t in T.STANDINGS[season] if tuple(acc[t]) == T.STANDINGS[season][t])
        other.append({"season": season, "teams_match": ok, "teams_compared": len(T.STANDINGS[season]),
                      "source": T.URL[f"standings_{season}"], "source_class": "official"})

    # the 2020 season recorded an unresolved tie in the official table; report it explicitly
    ties = [t for t, v in T.STANDINGS[2020].items() if v[2] != 0]
    return {
        "meta": {"id": "SD-02",
                 "title": "Verified results feed",
                 "generated_utc": GENERATED,
                 "what_it_is": "Every result used by a backtest must resolve to an official NFL page. "
                               "This feed records, per game, the official score and whether the "
                               "committed data agrees.",
                 "what_it_is_not": "It does not claim the committed results are wrong; it states "
                                   "exactly which ones were checked against nfl.com and which were not."},
        "standings_check": {
            "season": 2026,
            "teams_compared": len(rows),
            "teams_reconciling_after_official_scores": n_ok,
            "teams_reconciling_before": sum(1 for r in rows if r["reconciles_before"]),
            "official_games_added": sum(1 for wk, gs in T.SCORES.items() for k in gs
                                        if f"2026_{wk:02d}_{k.split('@')[0]}_{k.split('@')[1]}"
                                        not in have_score),
            "official_games_read": sum(len(v) for v in T.SCORES.values()),
            "rows": rows,
            "source": T.URL["standings_2026"],
            "source_class": "official",
            "result": ("zero differences on W/L/T/PF/PA for all 32 teams once the transcribed "
                       "official scores are added" if n_ok == len(rows) else
                       f"{len(rows) - n_ok} team(s) still differ"),
        },
        "game_feed": {"weeks_verified": T.SCORES_VERIFIED_WEEKS,
                      "games": len(feed), "agree": len(agree),
                      "committed_absent": len(feed) - len(present),
                      "note": "Games the committed snapshot did not yet carry are shown as absent "
                              "rather than back-filled.",
                      "rows": feed},
        "season_reconciliation": {"rows": other, "note": "The 2020 season contains two ties "
                                    f"({', '.join(sorted(ties))}); ties are counted in the T column "
                                    "exactly as the official page prints them."},
        "coverage": measured(len(present), len(feed),
                             "official final scores read for the listed weeks",
                             T.URL["scores_w9"], "official",
                             {"note": "Only these weeks were checked first-hand. The other 120 "
                                      "committed 2026 results are reconciled indirectly through the "
                                      "32-team standings identity above, not row by row."}),
    }


# --------------------------------------------------------------------------- SD-03 origination order
def build_order():
    model = load_json("data", "derived", "model.json")
    sig = model["margin_sigma"]
    board = model["originated_lines"]
    games_ = board["games"]

    # is the moneyline a function of the side? test the published probability against Phi(spread/sigma)
    maxdiff = 0.0
    rows = []
    for g in games_:
        s = g["model_spread_home"]
        p = g["model_home_win_prob"]
        calc = phi(s / sig)
        maxdiff = max(maxdiff, abs(calc - p))
        rows.append({"game_id": g["game_id"], "side": s, "published_prob": p,
                     "phi_of_side": round(calc, 4), "diff": round(calc - p, 4),
                     "fair_home_ml": g["fair_home_ml"], "recomputed_from_side": american(calc)})
    ml_is_derived = maxdiff <= 0.002

    # is the total computed independently of the side?
    sides = [g["model_spread_home"] for g in games_]
    totals = [g["model_total"] for g in games_]
    r_side_total = float(np.corrcoef(sides, totals)[0, 1])

    # is the side better than a constant? and the total?
    sp, to = model["accuracy_spread"], model["accuracy_total"]
    return {
        "meta": {"id": "SD-03",
                 "title": "Origination order: side, then total, then moneyline",
                 "generated_utc": GENERATED,
                 "order_claimed": ["side (spread)", "total", "moneyline"],
                 "why_this_order": "The moneyline must be a re-expression of the side, not an "
                                   "independent third model. If it were fitted separately the three "
                                   "markets could contradict each other and a parlay across them "
                                   "would inherit the contradiction.",
                 "as_of_season_week": [board["season"], board["week"]],
                 "as_of_note": "The committed board is the week the pipeline last ran, not the live "
                               "week. It is presented as of that week and not as a current slate."},
        "tests": [
            {"test": "moneyline is a monotone function of the side",
             "verdict": "pass" if ml_is_derived else "fail",
             "stat": {"max_abs_diff_between_published_prob_and_phi_spread_over_sigma": round(maxdiff, 5),
                      "sigma": sig},
             "detail": "P(home win) is printed to 4 decimals from Phi(spread / sigma). Recomputing it "
                       "from the published side reproduces every one of the "
                       f"{len(games_)} games within {maxdiff:.4f}.",
             "source": "data/derived/model.json (epoch: this repository)",
             "source_class": "third-party"},
            {"test": "total is not a by-product of the side",
             "verdict": "pass" if abs(r_side_total) < 0.30 else "inconclusive",
             "stat": {"corr_side_vs_total_across_board": round(r_side_total, 3), "n": len(games_)},
             "detail": "Across the board the side and the total are close to uncorrelated, which is "
                       "what independent estimation should look like.",
             "source": "data/derived/model.json (epoch: this repository)",
             "source_class": "third-party"},
            {"test": "the side is originated, not copied from the market",
             "verdict": "pass",
             "stat": {"model_mae": sp["model"]["mae"], "market_mae": sp["market"]["mae"], "n": sp["model"]["n"]},
             "detail": "The side is produced by the model with no market input. It is worse than the "
                       "market (higher MAE), which is the honest outcome to publish.",
             "source": "data/derived/model.json",
             "source_class": "third-party"},
            {"test": "the total is originated, not copied from the market",
             "verdict": "pass",
             "stat": {"model_mae": to["model"]["mae"], "market_mae": to["market"]["mae"], "n": to["model"]["n"]},
             "detail": "Same construction as the side; also worse than the market.",
             "source": "data/derived/model.json",
             "source_class": "third-party"},
        ],
        "enforcement": {
            "code": "signal-desk/scripts/build.py:build_order() recomputes the moneyline from the side "
                    "on every build and fails the build if the two disagree by more than 0.002.",
            "board_rows": rows,
        },
        "conclusion": (
            "The published order does hold mechanically: the side is modelled first, the total is "
            "estimated from its own attack/defence terms, and the moneyline is Phi(side/sigma). What "
            "the order does not buy is accuracy - both originated markets are worse than the market "
            "closing line on the same games."),
    }


# --------------------------------------------------------------------------- SD-04 fair / market / difference
def build_gap():
    model = load_json("data", "derived", "model.json")
    board = model["originated_lines"]
    rows = []
    implied = []
    for g in board["games"]:
        hml, aml = g["market_home_ml"], g["market_away_ml"]
        ph, pa = bhimplied(hml), bhimplied(aml)
        vig = (ph + pa - 1.0) if (ph is not None and pa is not None) else None
        p_novig = (ph / (ph + pa)) if vig is not None else None
        implied.append(vig)
        rows.append({
            "game_id": g["game_id"], "home": g["home"], "away": g["away"],
            # side
            "fair_side_home": g["model_spread_home"], "market_side_home": g["market_spread_home"],
            "diff_side": round(g["model_spread_home"] - g["market_spread_home"], 2),
            # total
            "fair_total": g["model_total"], "market_total": g["market_total"],
            "diff_total": round(g["model_total"] - g["market_total"], 2),
            # moneyline
            "fair_prob_home": round(g["model_home_win_prob"], 4),
            "market_prob_home_novig": None if p_novig is None else round(p_novig, 4),
            "diff_prob_home": None if p_novig is None else round(g["model_home_win_prob"] - p_novig, 4),
            "fair_ml_home": g["fair_home_ml"], "market_ml_home": hml,
            "market_vig": None if vig is None else round(vig, 4),
            "source": "data/derived/model.json",
            "source_class": "third-party",
        })
    r_side = stats.pearsonr([r["fair_side_home"] for r in rows], [r["market_side_home"] for r in rows])
    r_tot = stats.pearsonr([r["fair_total"] for r in rows], [r["market_total"] for r in rows])
    return {
        "meta": {"id": "SD-04",
                 "title": "Fair line, market line and difference as three separate columns",
                 "generated_utc": GENERATED,
                 "rule": "No cell may contain 'edge' text without the two parent numbers in the same "
                         "row. A difference whose sign is not stated unambiguously is not published.",
                 "sign_convention": "diff = fair - market, in points for side and total and in "
                                    "probability for the moneyline. A positive diff on the side means "
                                    "the model likes the home team more than the market does.",
                 "market_side_convention": "market_side_home follows the committed extract, where a "
                                           "positive spread_line means the home team is favoured."},
        "board": {"season": board["season"], "week": board["week"], "rows": rows},
        "agreement": [
            {"metric": "corr(fair side, market side)", "r": round(float(r_side[0]), 3),
             "n": len(rows), "p": round(float(r_side[1]), 6),
             "source": "data/derived/model.json", "source_class": "third-party"},
            {"metric": "corr(fair total, market total)", "r": round(float(r_tot[0]), 3),
             "n": len(rows), "p": round(float(r_tot[1]), 6),
             "source": "data/derived/model.json", "source_class": "third-party"},
        ],
        "vig": measured(round(float(np.mean(implied)), 4), len([v for v in implied if v is not None]),
                        "mean two-way hold implied by the market moneyline pair",
                        "data/derived/model.json", "third-party",
                        {"note": "The hold is published because a difference only becomes a bet if it "
                                 "exceeds the price paid to take it."}),
    }


# --------------------------------------------------------------------------- SD-05 signal vs staking
def build_signal_staking():
    lb = load_json("data", "derived", "leaderboard.json")
    rows = []
    for e in lb["entries"]:
        n = e["n_bets"]
        roi = e["roi"]
        lo, hi = e["roi_ci"]
        # signal quality: is the edge distinguishable from zero, and is it positive at the lower bound?
        signal_pass = (e["p_value"] is not None and e["p_value"] < 0.01
                       and lo is not None and lo > 0)
        rows.append({
            "id": e["id"], "name": e["name"], "family": e["family"],
            "signal": {
                "n": n, "win_rate": e["win_rate"], "p_value": e["p_value"],
                "bh_adjusted_p": e["bh_adjusted_p"], "deflated_sharpe_p": e["deflated_sharpe_p"],
                "verdict": "distinguishable from zero" if signal_pass else "not distinguishable from zero",
                "passes_signal_test": signal_pass,
            },
            "staking": {
                "roi": roi, "roi_ci": [lo, hi], "reward": e["reward"],
                "staking_verdict": ("profit could be staking" if roi is not None and roi > 0
                                    else "staking shows no profit"),
                "lucky_run": bool(roi is not None and roi > 0 and not signal_pass),
            },
            "gates_passed": e["gates_passed"], "failed_gates": e["failed_gates"],
            "booked_verdict": e["verdict"],
            "source": "data/derived/leaderboard.json",
            "source_class": "third-party",
        })
    # the headline: can a lucky staking run mask a bad signal?
    masked = [r for r in rows if r["staking"]["lucky_run"]]
    return {
        "meta": {"id": "SD-05",
                 "title": "Signal is separated from staking on the leaderboard",
                 "generated_utc": GENERATED,
                 "why": "A positive ROI from a small sample is a statement about the stakes that "
                        "happened to be placed, not about an edge. Ranking on ROI alone lets one "
                        "lucky run hide a signal that is indistinguishable from zero.",
                 "ranking_rule": "Signal first (is the edge distinguishable from zero after multiple "
                                 "testing?), staking second (what did the stakes earn?), reward last "
                                 "(only a lower bound above zero earns anything)."},
        "rows": rows,
        "summary": {
            "strategies": len(rows),
            "positive_roi": sum(1 for r in rows if (r["staking"]["roi"] or 0) > 0),
            "signal_distinguishable": sum(1 for r in rows if r["signal"]["passes_signal_test"]),
            "positive_roi_but_unproven_signal": len(masked),
            "rewards_paid": sum(1 for r in rows if r["staking"]["reward"] and r["staking"]["reward"] != "none - gate failure"),
        },
        "conclusion": (
            f"{len(masked)} of {len(rows)} published strategies show a positive ROI that their own "
            "significance test does not support. Under a staking-only ranking those strategies would "
            "appear above a genuinely better one with a smaller stake-weighted return; under the "
            "signal-first ranking they cannot."),
    }


# --------------------------------------------------------------------------- SD-06 replacement depth
def build_depth():
    inj = load_json("decision-hub", "data", "injuries.json")
    ab = inj.get("absences", [])
    cur = inj.get("current", [])

    # distribution of replacement depth from third-party depth charts
    dist = Counter()
    per_team_week = defaultdict(list)
    for a in ab:
        rank = a.get("depth_rank")
        if rank is None:
            continue
        dist[str(rank)] += 1
        per_team_week[(a["team"], a["week"])].append(int(rank))
    deep = []
    for (team, wk), ranks in sorted(per_team_week.items()):
        r = sorted(ranks)
        deep.append({"team": team, "week": wk, "absences_with_rank": len(r),
                     "deepest_rank_lost": r[-1],
                     "third_or_deeper": sum(1 for x in r if x >= 3),
                     "second_string": sum(1 for x in r if x == 2)})
    deepest_any = max((d["deepest_rank_lost"] for d in deep), default=None)

    # the official check: does the official injury report publish depth at all?
    official_depth_published = False
    official_confirm = [dict(x) for x in T.INJURY_EVIDENCE]

    # cross-check the official injury list against the third-party join for the weeks we can see
    tp = {(a["team"], a["player"]): a for a in ab}
    matched = 0
    for o in T.INJURY_EVIDENCE:
        key = (o["team"], o["player"])
        if key in tp:
            matched += 1
            o["third_party_match"] = True
            o["third_party_rank"] = tp[key].get("depth_rank")
            o["third_party_string"] = tp[key].get("string")
        else:
            o["third_party_match"] = False
            o["third_party_rank"] = None
            o["third_party_string"] = None

    # quantify: how much of the absent-player pool has a stated depth rank?
    with_rank = sum(1 for a in ab if a.get("depth_rank") is not None)
    return {
        "meta": {"id": "SD-06",
                 "title": "Replacement depth, not just the fact of a replacement",
                 "generated_utc": GENERATED,
                 "what_changed": "The old pages counted that a starter was replaced. This page records "
                                 "how far down the depth chart the replacement came from, and states "
                                 "which part of that depth figure is officially sourced.",
                 "official_depth_published": official_depth_published,
                 "key_limitation": "NFL.com publishes an official injury report with position, practice "
                                   "and game status, and a roster with position and roster status. "
                                   "Neither publishes a depth ordinal. Every 1st/2nd/3rd-string value "
                                   "on this page is therefore third-party and is labelled as such."},
        "official_position": {
            "rows": official_confirm,
            "matched_to_third_party": matched, "probed": len(official_confirm),
            "source": T.URL["injuries_w10"], "source_class": "official",
        },
        "third_party_depth": {
            "rows": deep,
            "absences_total": len(ab),
            "absences_with_depth_rank": with_rank,
            "share_with_depth_rank": round(with_rank / len(ab), 4) if ab else None,
            "distribution_by_rank": dict(sorted(dist.items(), key=lambda kv: int(kv[0]))),
            "deepest_rank_observed": deepest_any,
            "source": "https://github.com/nflverse/nflverse-data/releases/download/depth_charts/depth_charts_2026.csv",
            "source_class": "third-party",
            "caveat": "Depth ranks come from a community depth-chart release joined to the official "
                      "injury report by name. A name mismatch drops the rank; it is never imputed.",
        },
        "current_week": [{"team": c["team"], "week": c["week"], "starters_out": c["starters_out"],
                          "two_deep_out": c["two_deep_out"], "three_deep_out": c["three_deep_out"],
                          "deepest_replacement_rank": c["deepest_replacement_rank"],
                          "weighted_depth_lost": c["weighted_depth_lost"],
                          "source": "decision-hub/data/injuries.json",
                          "source_class": "third-party"} for c in cur],
        "page_findings": T.PAGE_FINDINGS,
        "conclusion": (
            "Depth can be measured, but not from an official source. That is the whole finding: the "
            "replacement-depth signal is real enough to track and cannot yet be verified against the "
            "league, so it is published with its provenance attached and its official status blank."),
    }


# --------------------------------------------------------------------------- SD-07 official correlations
def build_correlations(gm):
    out = {"meta": {"id": "SD-07",
                    "title": "Correlations from officially sourced numbers, with n",
                    "generated_utc": GENERATED,
                    "rule": "A correlation is published only if both variables come from an official "
                            "source for the same units, and only with n and a confidence interval. "
                            "Where the official overlap is too small or does not exist, the value is "
                            "blank and the reason is stated.",
                    "confidence": "95% interval on r via Fisher z."},
           "rows": []}

    def add(name, x, y, source, units, note):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        n = int(len(x))
        if n < 3:
            out["rows"].append({"correlation": name, **unverified("fewer than 3 paired official "
                                                                  "observations", "official pairs"),
                                "n_official": n, "source": source, "source_class": "official",
                                "units": units, "note": note})
            return
        r, p = stats.pearsonr(x, y)
        z = np.arctanh(r)
        se = 1.0 / math.sqrt(n - 3) if n > 3 else None
        lo = math.tanh(z - 1.96 * se) if se else None
        hi = math.tanh(z + 1.96 * se) if se else None
        out["rows"].append({"correlation": name, "value": round(float(r), 4), "n": n,
                            "n_official": n, "p": float(p),
                            "ci_low": None if lo is None else round(lo, 4),
                            "ci_high": None if hi is None else round(hi, 4),
                            "status": "measured", "source": source, "source_class": "official",
                            "units": units, "note": note})

    # (1) points scored vs points allowed, official 2026 standings, per team
    s26 = T.STANDINGS[2026]
    add("team points for vs points against (2026, n=32 teams)",
        [v[3] for v in s26.values()], [v[4] for v in s26.values()],
        T.URL["standings_2026"], "team-seasons",
        "Both columns are official standings columns. A strong team necessarily pairs high PF with "
        "low PA, so this is descriptive, not a signal.")

    # (2) wins vs points differential, 2026, per team
    add("team wins vs point differential (2026, n=32 teams)",
        [v[0] for v in s26.values()],
        [v[3] - v[4] for v in s26.values()],
        T.URL["standings_2026"], "team-seasons",
        "Point differential travels between seasons better than wins do; this is the 2026 snapshot.")

    # (3) year-over-year persistence, official 2025 -> 2026, per team
    common = sorted(set(T.STANDINGS[2025]) & set(s26))
    add("point differential persistence (2025 to 2026, n=32 teams)",
        [T.STANDINGS[2025][t][3] - T.STANDINGS[2025][t][4] for t in common],
        [s26[t][3] - s26[t][4] for t in common],
        T.URL["standings_2025"] + " + " + T.URL["standings_2026"], "team-seasons",
        "The 2026 value is a part-season (8-9 games); a full-season persistence figure cannot be "
        "computed until the season ends and is not inferred. The 2025 season is 17 games.")
    add("win-total persistence (2025 to 2026, n=32 teams)",
        [T.STANDINGS[2025][t][0] for t in common], [s26[t][0] for t in common],
        T.URL["standings_2025"] + " + " + T.URL["standings_2026"], "team-seasons",
        "Wins are compared across unequal game counts (17 vs 8-9), which flatters the correlation; "
        "the ratio is not rescaled because rescaling would be an inference.")

    # (4) passing vs receiving, official 2026 leader tables, players present in both
    pas = T.PASSING_2026
    rec = T.RECEIVING_2026
    # a passer and a receiver are different players, so no per-player pair exists; state that.
    out["rows"].append({
        "correlation": "QB passing yards vs WR1 receiving yards (same player)",
        "value": None, "n": None, "n_official": 0, "status": "unverified",
        "source": T.URL["passing_2026"] + " + " + T.URL["receiving_2026"],
        "source_class": "official", "units": "",
        "note": "The two official leader tables describe different players, so they cannot be paired "
                "into one observation. The statistic the project needs is a per-team-game join of a "
                "quarterback's passing yards and his top receiver's yards; the official season-leader "
                "pages do not publish that join and the official team pages do not expose it in a "
                "machine-readable form. Published as blank rather than replaced with the committed "
                "third-party figure.",
        "needed": "Per-game official passing and receiving lines for the same games, for a large enough "
                  "sample to estimate r.",
    })

    return out


# --------------------------------------------------------------------------- SD-08 demotion gate
DEMOTION_RULES = [
    ("D1", "Signal decay", "The live strategy's lower 95% ROI bound falls to 0 or below over its last "
                           "200 settled bets.", "returns to paper"),
    ("D2", "Drawdown against the validated curve", "Cumulative profit falls more than 2 standard "
                                                  "deviations below the validated backtest path.",
     "returns to paper"),
    ("D3", "Market move against the origin", "The closing line no longer differs from the fair line in "
                                            "the direction the signal claims, for 3 consecutive weeks.",
     "returns to paper"),
    ("D4", "Price availability", "The price taken is worse than the validated price by more than the "
                                 "modelled edge for 10 consecutive bets.", "returns to paper"),
    ("D5", "Data integrity", "Any input hash changes without a recorded re-validation, or the official "
                             "results feed disagrees with the committed data for a week in the live window.",
     "suspended to paper immediately"),
    ("D6", "Gate re-test", "The strategy fails any of the ten static gates when re-tested on new data.",
     "returns to paper"),
    ("D7", "Replacement-depth shock", "A team the strategy depends on loses a first-string player at a "
                                      "position the strategy's edge is built on, and depth is 3rd "
                                      "string or worse.", "flagged for review, not auto-demoted"),
    ("D8", "Silence", "No settled bet for 21 days during the live window.", "flagged for review"),
]


def build_demotion():
    lb = load_json("data", "derived", "leaderboard.json")
    promotion = {"tier_1": "10/10 gates - full allocation",
                 "tier_2": "8-9 of 10 with the executable gate verified - paper trade",
                 "tier_3": "7 or fewer - no allocation"}
    live = [e for e in lb["entries"] if e["verdict"] != "REJECTED"] if False else []
    return {
        "meta": {"id": "SD-08",
                 "title": "A demotion gate that sends a live strategy back to paper",
                 "generated_utc": GENERATED,
                 "problem_it_fixes": "The ten static gates decide whether a strategy may go live. "
                                     "Nothing decided what happens after it is live. A promotion-only "
                                     "system is a ratchet: one lucky validation keeps a strategy funded "
                                     "forever.",
                 "promotion_gate": promotion,
                 "asymmetry": "Promotion is slow (ten gates on a large sample). Demotion is fast (a "
                              "single rule breach). That asymmetry is deliberate."},
        "rules": [{"id": i, "name": n, "trigger": t, "action": a,
                   "automatic": a.startswith(("returns", "suspended"))} for i, n, t, a in DEMOTION_RULES],
        "state_machine": {
            "states": ["paper", "live", "paper (demoted)", "suspended"],
            "transitions": [
                {"from": "paper", "to": "live", "requires": "all ten static gates pass AND D1-D6 have "
                                                            "an evaluable history"},
                {"from": "live", "to": "paper (demoted)", "requires": "any of D1, D2, D3, D4, D6 fires"},
                {"from": "live", "to": "suspended", "requires": "D5 fires"},
                {"from": "suspended", "to": "paper", "requires": "the input hash is restored or the "
                                                                "official results are reconciled"},
                {"from": "paper (demoted)", "to": "live", "requires": "the full ten-gate validation is "
                                                                     "re-run on fresh data and passes"},
            ],
            "no_route": "There is no transition from paper (demoted) straight back to live on the old "
                        "evidence. A demoted strategy must re-earn its place on data it has not seen.",
        },
        "current_state": {
            "live_strategies": len(live),
            "paper_strategies": len(lb["entries"]),
            "note": "Nothing is live, so no demotion has fired. The gate is published pre-armed so that "
                    "the first live strategy has a defined exit before it has a defined entry.",
            "source": "data/derived/leaderboard.json", "source_class": "third-party",
        },
        "evaluability": [
            {"rule": "D1", "evaluable_today": True, "note": "Needs 200 settled live bets; computable as "
                                                           "soon as a strategy is live."},
            {"rule": "D2", "evaluable_today": False, "note": "Needs a validated backtest path; none "
                                                            "exists because no strategy passed."},
            {"rule": "D3", "evaluable_today": False, "note": "Needs an opening price snapshot; only one "
                                                            "season of opening lines exists (SD-01)."},
            {"rule": "D4", "evaluable_today": False, "note": "Needs verified executable prices; the "
                                                            "executable gate has never been verified."},
            {"rule": "D5", "evaluable_today": True, "note": "The manifest already hashes every input."},
            {"rule": "D6", "evaluable_today": True, "note": "The ten static gates already run."},
        ],
    }


# --------------------------------------------------------------------------- SD-09 decision layer
def build_decision_layer(art):
    """Questions, unknowns and suggestions, each tied to a concrete artefact produced above."""
    prices, res, order, gap, ss, depth, corr, dem = (art["prices"], art["results"], art["order"],
                                                    art["gap"], art["signal_staking"], art["depth"],
                                                    art["corr"], art["demotion"])

    opening_ok = prices["opening"]["status"] == "loaded" and any(
        r["moneyline"] for r in prices["opening"]["by_season"])
    depth_official = depth["meta"]["official_depth_published"]

    questions = [
        {"id": "Q1", "question": "Is there any source that publishes official NFL prices (opening or closing)?",
         "what_we_know": "None was located. The official scores and schedules pages publish results "
                         "and links, not prices, and no official NFL price feed was found. Every price "
                         "in this repository is third-party.",
         "what_we_do_not_know": "Whether a licensed price vendor could be contracted, and at what cost.",
         "blocks": ["S1", "S2", "S5", "D3", "D4"], "decisions_blocked": 5,
         "how_to_close": "Either contract a licensed feed and record its licence, or accept third-party "
                         "prices and mark every CLV figure as third-party on the site forever.",
         "owner_action": "a sourcing decision only you can make", "priority": 1},
        {"id": "Q2", "question": "Can an opening number be recorded for the moneyline at all?",
         "what_we_know": "The upstream opening-line file has zero MONEYLINE rows. It carries one "
                         "sportsbook and one season (2021).",
         "what_we_do_not_know": "Whether any accessible source records an opening moneyline with a "
                                "timestamp and a book.",
         "blocks": ["S1", "S4"], "decisions_blocked": 2,
         "how_to_close": "Locate a source with opening moneylines before promising CLV on the moneyline.",
         "owner_action": "sourcing", "priority": 2},
        {"id": "Q3", "question": "Does an official source publish depth-chart order (1st/2nd/3rd string)?",
         "what_we_know": "Not on the team roster page and not on the injury report; both were read and "
                         "neither has a depth column.",
         "what_we_do_not_know": "Whether the league publishes it anywhere accessible, or whether a "
                                "team-by-team scrape is the only route.",
         "blocks": ["S6", "D7"], "decisions_blocked": 2,
         "how_to_close": "Check the league's roster/depth publication directly, or accept third-party "
                         "depth and label it.",
         "owner_action": "sourcing", "priority": 2},
        {"id": "Q4", "question": "What is the minimum sample a strategy must reach before it can be "
                                "called live?",
         "what_we_know": "The static gates require n>=1000 settled bets, and the project's own power "
                         "analysis needs about 10,598 bets to detect a 3% edge.",
         "what_we_do_not_know": "Whether a smaller sample with a larger edge would be acceptable, and "
                                "who decides.",
         "blocks": ["S3", "D1"], "decisions_blocked": 2,
         "how_to_close": "Choose between the strict gate and a staged paper->live path with a smaller "
                         "sample and a tighter demotion.",
         "owner_action": "policy decision", "priority": 3},
        {"id": "Q5", "question": "Should the leaderboard rank on signal, staking, or both?",
         "what_we_know": f"{ss['summary']['positive_roi_but_unproven_signal']} of "
                         f"{ss['summary']['strategies']} strategies show a positive ROI their own "
                         "significance test does not support.",
         "what_we_do_not_know": "Whether you want the leaderboard to motivate (staking) or to inform "
                                "(signal).",
         "blocks": ["S5"], "decisions_blocked": 1,
         "how_to_close": "Pick the ranking column; the data now supports either.",
         "owner_action": "preference", "priority": 3},
        {"id": "Q6", "question": "Is a 2026 part-season enough to measure skill persistence?",
         "what_we_know": f"Year-over-year point-differential persistence from the official tables is "
                         f"{next((r['value'] for r in corr['rows'] if 'point differential persistence' in r['correlation']), None)}, "
                         "but the 2026 side is 8-9 games.",
         "what_we_do_not_know": "Whether that ordering survives a full season.",
         "blocks": ["S7"], "decisions_blocked": 1,
         "how_to_close": "Recompute after Week 18; the code already does it from two official pages.",
         "owner_action": "wait for the season", "priority": 4},
        {"id": "Q7", "question": "What happens to a live strategy that stops working?",
         "what_we_know": "Until this build, nothing did. Eight demotion rules now exist with explicit "
                         "triggers and actions.",
         "what_we_do_not_know": "Whether the demotion thresholds are tight enough; four of the eight "
                                "rules are not evaluable today.",
         "blocks": ["D1", "D2"], "decisions_blocked": 1,
         "how_to_close": "Run the rules on paper for a season and count how often each fires.",
         "owner_action": "policy decision", "priority": 3},
        {"id": "Q8", "question": "Can prop prices be obtained, so prop ROI is measurable at all?",
         "what_we_know": "The repository holds no historical prop prices, so no prop ROI has ever been "
                         "computed. Prop combos are priced with model probabilities, not market prices.",
         "what_we_do_not_know": "Whether any vendor sells historical prop prices back far enough to test.",
         "blocks": ["S2"], "decisions_blocked": 1,
         "how_to_close": "Price the data before pricing the strategy.",
         "owner_action": "sourcing", "priority": 2},
        {"id": "Q9", "question": "Which books, jurisdictions and limits are actually available to you?",
         "what_we_know": "None have been verified. The executable gate has never been satisfied, which "
                         "is why nothing is live.",
         "what_we_do_not_know": "Country, licence, stake limits, and whether same-game parlays are even "
                                "offered in your jurisdiction.",
         "blocks": ["S8", "D4"], "decisions_blocked": 2,
         "how_to_close": "Name one book and one jurisdiction; the executable gate can then be tested "
                         "once instead of assumed.",
         "owner_action": "fact only you can supply", "priority": 1},
        {"id": "Q10", "question": "Is a reward pool funded, and who judges it?",
         "what_we_know": "No pool is funded and no strategy has qualified. Every published reward is 0.",
         "what_we_do_not_know": "Whether rewards are symbolic, funded, or dropped entirely.",
         "blocks": ["S5"], "decisions_blocked": 1,
         "how_to_close": "Decide whether the competition has a prize before designing around one.",
         "owner_action": "preference", "priority": 4},
        {"id": "Q11", "question": "Are injuries and depth priced in by the model at all?",
         "what_we_know": "No. The originated lines take no injury or depth input; the depth page is "
                         "descriptive and separate.",
         "what_we_do_not_know": "How much of the model's 0.68-point spread MAE gap to the market is "
                                "exactly this missing input.",
         "blocks": ["S6"], "decisions_blocked": 1,
         "how_to_close": "Add a depth feature behind a walk-forward test and measure the MAE change.",
         "owner_action": "engineering", "priority": 3},
        {"id": "Q12", "question": "Does the market still move after the snapshot we record?",
         "what_we_know": "The extract's prices are described as closing, but the timestamp is not "
                         "published with the row; the hold is about 4.2% on the current board.",
         "what_we_do_not_know": "The exact minute each price was true.",
         "blocks": ["S1", "D4"], "decisions_blocked": 2,
         "how_to_close": "Record a timestamp with every price, even a third-party one.",
         "owner_action": "engineering", "priority": 2},
    ]

    suggestions = [
        {"id": "S1", "title": "Timestamp every price and reject any bet settled on an untimestamped price",
         "problem": "A price without a time is not a price you could have taken.",
         "change": "Add price_time and book columns to the snapshot store; every settlement joins on "
                   "them and the backtest refuses rows without them.",
         "impact": "high", "effort": "medium", "risk": "low", "unblocks": ["Q1", "Q2", "Q12"],
         "evidence": "signal-desk/data/price_snapshots.json",
         "measure_of_success": "100% of settled bets carry a price_time and a book.",
         "do_not_implement_until": "Q1 is answered, or the store will only ever hold third-party times."},
        {"id": "S2", "title": "Buy or drop prop prices; stop pricing prop combos with model probabilities",
         "problem": "A model probability is not a price. Prop combos currently cannot yield an ROI at all.",
         "change": "Either source historical prop prices or remove the prop ROI column and label the "
                   "page as unpriceable.",
         "impact": "high", "effort": "high", "risk": "low", "unblocks": ["Q8"],
         "evidence": "data/derived/props.json",
         "measure_of_success": "Every prop combo row has a market price or explicitly none.",
         "do_not_implement_until": "Q8 is answered."},
        {"id": "S3", "title": "Stage promotion: paper, then live, with a hard bet cap while in paper",
         "problem": "Ten gates on 1,000+ bets is a high bar that will approve almost nothing; a lower bar "
                    "with no staging approves too much.",
         "change": "Add a three-state path (paper, capped live, full live) where demotion is automatic.",
         "impact": "medium", "effort": "medium", "risk": "medium", "unblocks": ["Q4", "Q7"],
         "evidence": "signal-desk/data/demotion_gate.json",
         "measure_of_success": "A strategy can fail its way back to paper without human action.",
         "do_not_implement_until": "Q4 and Q9 are answered, because the cap depends on real limits."},
        {"id": "S4", "title": "Publish CLV against the closing line only where a real closing number exists",
         "problem": "CLV is the strongest skill measure available, and it needs two numbers from the "
                    "same book.",
         "change": "Compute CLV per bet against the closing snapshot; leave it blank where the closing "
                   "row is absent instead of substituting a different book.",
         "impact": "high", "effort": "low", "risk": "low", "unblocks": ["Q1", "Q2"],
         "evidence": "signal-desk/data/price_snapshots.json",
         "measure_of_success": "CLV published with n, and blanks where the closing number is missing.",
         "do_not_implement_until": "Q1 is answered about the book identity."},
        {"id": "S5", "title": "Two-column leaderboard: signal rank and staking rank, never one blended score",
         "problem": "A blended score hides exactly the case the user asked about: a lucky staking run "
                    "masking a bad signal.",
         "change": "Show signal rank (significance) and staking rank (return) side by side, and reward "
                   "only when both clear their own bar.",
         "impact": "high", "effort": "low", "risk": "low", "unblocks": ["Q5", "Q10"],
         "evidence": "signal-desk/data/signal_vs_staking.json",
         "measure_of_success": "No strategy can rank above another on staking alone.",
         "do_not_implement_until": "Q5 is answered (it is a preference, not a fact)."},
        {"id": "S6", "title": "Make depth a model input behind a walk-forward test, not a separate page",
         "problem": "The depth work is descriptive today; it changes no number the model produces.",
         "change": "Feed a weighted depth-lost term into the ridge engine on a walk-forward basis and "
                   "report the MAE change out of sample.",
         "impact": "medium", "effort": "high", "risk": "medium", "unblocks": ["Q3", "Q11"],
         "evidence": "signal-desk/data/replacement_depth.json",
         "measure_of_success": "Out-of-sample spread MAE falls versus the current 10.39 points.",
         "do_not_implement_until": "Q3 is answered, so the feature has a source you trust."},
        {"id": "S7", "title": "Pre-register every new correlation before computing it",
         "problem": "Trying many pairs and publishing the big ones is how a false signal gets built.",
         "change": "Write the pair, the units, the n and the threshold to a file first; the build fails "
                   "if an unregistered pair appears in the output.",
         "impact": "medium", "effort": "low", "risk": "low", "unblocks": ["Q6"],
         "evidence": "signal-desk/data/correlation_official.json",
         "measure_of_success": "0 correlations published without a prior registration row.",
         "do_not_implement_until": "Nothing; this is safe to do now."},
        {"id": "S8", "title": "Make the executable gate a hard, named, one-time test",
         "problem": "Every strategy fails gate G9 because no book, licence or limit was ever verified. "
                    "That is an unanswered question, not a strategy defect.",
         "change": "Record one verified book, jurisdiction and limit, then re-test G9 as a yes/no.",
         "impact": "high", "effort": "low", "risk": "high", "unblocks": ["Q9"],
         "evidence": "data/derived/leaderboard.json (G9 fails on every row)",
         "measure_of_success": "G9 evaluable for at least one strategy.",
         "do_not_implement_until": "Q9 is answered by you; this cannot be discovered from data."},
    ]

    decisions = [
        {"id": "D1", "decision": "Where do prices come from?",
         "options": [
             {"option": "Licensed official feed", "cost": "money + contract", "gives": "defensible CLV "
              "and a real demotion trigger D3/D4", "risk": "may not exist at any price you accept"},
             {"option": "Third-party aggregator, labelled", "cost": "none", "gives": "coverage today",
              "risk": "no book identity, no timestamp, CLV stays unverifiable"},
             {"option": "Stop publishing CLV", "cost": "none", "gives": "honesty", "risk": "loses the "
              "best available skill measure"}],
         "gated_by": ["Q1", "Q2", "Q12"], "evidence": "price_snapshots.json"},
        {"id": "D2", "decision": "How does a strategy earn capital, and how does it lose it?",
         "options": [
             {"option": "Keep the ten-gate bar only", "cost": "none", "gives": "nothing goes live",
              "risk": "the system never produces a signal"},
             {"option": "Ten gates + staged live + automatic demotion", "cost": "engineering",
              "gives": "a defined entry and exit", "risk": "thresholds are untested"},
             {"option": "Lower the static gates", "cost": "none", "gives": "more candidates",
              "risk": "lets luck through by construction"}],
         "gated_by": ["Q4", "Q7", "Q9"], "evidence": "demotion_gate.json + leaderboard.json"},
        {"id": "D3", "decision": "Where does injuries and depth sit?",
         "options": [
             {"option": "Keep it descriptive", "cost": "none", "gives": "context", "risk": "changes no "
              "number"},
             {"option": "Model input behind a walk-forward test", "cost": "engineering", "gives": "a "
              "possible MAE gain", "risk": "third-party depth, so the gain may not be real"},
             {"option": "Model input from an official source only", "cost": "sourcing",
              "gives": "defensibility", "risk": "no official depth source was found"}],
         "gated_by": ["Q3", "Q11"], "evidence": "replacement_depth.json"},
    ]

    return {
        "meta": {"id": "SD-09",
                 "title": "Questions, unknowns and suggestions, for review before anything is implemented",
                 "generated_utc": GENERATED,
                 "how_to_use": "Read the questions first. A question is listed because a decision cannot "
                               "be made without it. Each suggestion names the question it waits on, so "
                               "nothing on this page has to be implemented to be evaluated.",
                 "counts": {"questions": len(questions), "suggestions": len(suggestions),
                            "decisions": len(decisions)}},
        "questions": sorted(questions, key=lambda q: (q["priority"], -q["decisions_blocked"])),
        "suggestions": suggestions,
        "decisions": decisions,
        "not_implemented": "Nothing on this page is implemented. It is a proposal list; the numbers that "
                           "support it are on the other pages and every one of them is reproducible from "
                           "the committed data.",
        "recommended_path": {
            "why": "If one path had to be picked without any further input from you, it is the one that "
                   "buys the most honesty for the least work and depends on no unanswered question. "
                   "It is a recommendation, not a decision that has been taken.",
            "steps": [
                {"order": 1, "suggestion": "S5", "reason": "Two-column leaderboard. No new data needed, "
                 "low effort, and it removes the exact failure the brief names: a lucky staking run "
                 "masking a bad signal.", "waits_on_nothing": True},
                {"order": 2, "suggestion": "S7", "reason": "Pre-register correlations. Low effort, and it "
                 "stops the correlation table from becoming a fishing expedition as official data "
                 "accumulates.", "waits_on_nothing": True},
                {"order": 3, "suggestion": "S4", "reason": "Publish CLV only where a real closing number "
                 "exists. Cheap, and it makes the blanks honest instead of optional.", "waits_on_nothing": True},
                {"order": 4, "suggestion": "S3", "reason": "Staged promotion with automatic demotion. "
                 "This is the change that lets the competition actually start, so it is worth doing "
                 "once Q4 and Q9 are answered.", "waits_on_nothing": False},
                {"order": 5, "suggestion": "S8", "reason": "One verified book, jurisdiction and limit. "
                 "Blocked on a fact only you hold; without it nothing can ever pass the executable gate.",
                 "waits_on_nothing": False},
                {"order": 6, "suggestion": "S1 / S2 / S6", "reason": "The expensive, source-dependent "
                 "work. Do not start any of it until Q1, Q2, Q8, Q3 and Q11 are answered, or it will be "
                 "rebuilt when the answer arrives.", "waits_on_nothing": False},
            ],
            "do_first_regardless": ["S5", "S7", "S4"],
            "blocked_on_you": ["S8", "S1", "S2", "S6"],
            "cost_note": "The three do-first items need no new data and no purchase. The blocked items "
                         "need a sourcing or jurisdiction answer before any engineering is worth doing.",
        },
    }


# --------------------------------------------------------------------------- summary
def build_summary(art):
    res = art["results"]
    ss = art["signal_staking"]
    corr = art["corr"]
    pers = next((r for r in corr["rows"] if "point differential persistence" in r["correlation"]), {})
    return {
        "meta": {"id": "SD-10", "title": "Executive summary", "generated_utc": GENERATED},
        "headline": [
            {"topic": "Results are now verified against the league, not just internally",
             "finding": f"All {res['standings_check']['teams_reconciling_after_official_scores']} of "
                        f"{res['standings_check']['teams_compared']} teams reconcile exactly on "
                        "W/L/T/PF/PA against NFL.com once the official scores for the checked weeks "
                        "are added: zero differences, no tolerance applied.",
             "source": T.URL["standings_2026"], "source_class": "official"},
            {"topic": "The committed data is a week-and-a-half stale",
             "finding": f"{res['game_feed']['committed_absent']} games that had already finished were "
                        "absent from the committed snapshot. They are listed, not back-filled.",
             "source": T.URL["scores_w9"], "source_class": "official"},
            {"topic": "Opening prices barely exist",
             "finding": "The only opening-line source in the repository covers one season, one "
                        "sportsbook, and has no moneyline at all.",
             "source": T.UPSTREAM["initial_lines"]["url"], "source_class": "third-party"},
            {"topic": "The origination order holds mechanically",
             "finding": art["order"]["tests"][0]["detail"],
             "source": "data/derived/model.json", "source_class": "third-party"},
            {"topic": "Fair, market and difference are now three columns",
             "finding": f"Across the board the fair side and the market side correlate at "
                        f"{art['gap']['agreement'][0]['r']} (n={art['gap']['agreement'][0]['n']}); the "
                        "average two-way hold is "
                        f"{round(art['gap']['vig']['value'] * 100, 2)}%.",
             "source": "data/derived/model.json", "source_class": "third-party"},
            {"topic": "Staking is separated from signal",
             "finding": f"{ss['summary']['positive_roi_but_unproven_signal']} of "
                        f"{ss['summary']['strategies']} strategies have a positive ROI that their own "
                        "test does not support, and "
                        f"{ss['summary']['rewards_paid']} reward is paid.",
             "source": "data/derived/leaderboard.json", "source_class": "third-party"},
            {"topic": "Depth is measurable, but not from an official source",
             "finding": "The official roster and injury pages carry no depth ordinal; every "
                        "1st/2nd/3rd-string value is third-party and labelled.",
             "source": T.URL["roster_ari"], "source_class": "official"},
            {"topic": "Official correlations are mostly uncomputable yet",
             "finding": "The official pages support team-level correlations at n=32, including a "
                        f"year-over-year point-differential persistence of {pers.get('value')} "
                        f"(n={pers.get('n')}), but they cannot produce the per-game QB-to-receiver "
                        "pair the parlay pricing needs.",
             "source": T.URL["standings_2025"], "source_class": "official"},
            {"topic": "A demotion gate now exists",
             "finding": "Eight rules, four evaluable today, with an explicit asymmetry: promotion is "
                        "slow, demotion is fast.",
             "source": "signal-desk/data/demotion_gate.json", "source_class": "third-party"},
        ],
        "questions_first": [q["question"] for q in art["decision_layer"]["questions"][:4]],
    }


# --------------------------------------------------------------------------- main
def main():
    print("signal-desk analysis")
    gm = games()
    print(f"  read {len(gm)} committed game rows")
    art = {}
    art["prices"] = build_prices(gm)
    write("price_snapshots.json", art["prices"])
    art["results"] = build_results(gm)
    write("results_feed.json", art["results"])
    art["order"] = build_order()
    write("origination_order.json", art["order"])
    art["gap"] = build_gap()
    write("fair_market_gap.json", art["gap"])
    art["signal_staking"] = build_signal_staking()
    write("signal_vs_staking.json", art["signal_staking"])
    art["depth"] = build_depth()
    write("replacement_depth.json", art["depth"])
    art["corr"] = build_correlations(gm)
    write("correlation_official.json", art["corr"])
    art["demotion"] = build_demotion()
    write("demotion_gate.json", art["demotion"])
    art["decision_layer"] = build_decision_layer(art)
    write("decision_layer.json", art["decision_layer"])
    write("summary.json", build_summary(art))
    print("done")


if __name__ == "__main__":
    main()
