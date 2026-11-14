#!/usr/bin/env python3
"""Build the price-snapshot store and the verified results feed.

Outputs (price-desk/data/):
  price_snapshots.csv        one row per (game market x originating engine)
  price_snapshots_props.csv  one row per originated player-prop market
  results_feed.csv           one row per game with settlement columns
  store_summary.json         coverage counts rendered on the site

Verification policy (applies to every output row):
  * A value confirmed digit-for-digit from an official NFL source carries
    status "verified-official" and the official URL used.
  * A value taken from a third-party archive (nflverse-derived repo files)
    carries status "archived-unverified" and its provenance ref. It is
    retained so backtests can run, and is never presented as verified.
  * A value with no source at all is BLANK with status "blank-missing".
  * "computed" values (differences, settlements) state their inputs and
    inherit the weakest status among those inputs.

Nothing is inferred or filled in: every non-blank value traces to either a
named repo file (archived), a named official page (verified), or a stated
arithmetic rule over such values (computed).
"""
import csv
import gzip
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "price-desk", "data")

# Convention verified empirically in results/market.json (convention_check):
# in games.csv.gz / predictions.csv, a POSITIVE spread_line means the HOME
# team is favoured by that many points. Home covers when
# (home_margin - spread_line) > 0; equality is a push.
SPREAD_CONVENTION = (
    "positive spread_line = home team favoured by that many points "
    "(verified empirically in results/market.json convention_check)"
)


def fnum(x):
    if x is None:
        return ""
    s = str(x).strip()
    if s in ("", "nan", "None"):
        return ""
    try:
        return float(s)
    except ValueError:
        return ""


def fmt(x, nd=4):
    if x == "" or x is None:
        return ""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return ""
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.{nd}f}".rstrip("0").rstrip(".")


def american_to_prob(a):
    """American price -> implied win probability (unnormalised)."""
    a = float(a)
    if a < 0:
        return -a / (-a + 100.0)
    return 100.0 / (a + 100.0)


def prob_to_american(p):
    p = float(p)
    if p <= 0 or p >= 1:
        return ""
    if p > 0.5:
        return round(-100.0 * p / (1.0 - p))
    return round(100.0 * (1.0 - p) / p)


def load_games():
    games = {}
    with gzip.open(os.path.join(ROOT, "data", "derived", "games.csv.gz"), "rt") as f:
        for r in csv.DictReader(f):
            games[r["game_id"]] = r
    return games


def load_verified():
    with open(os.path.join(OUT, "verified_results_2026.json")) as f:
        v = json.load(f)
    by_id = {r["game_id"]: r for r in v["verified_scores"]}
    hidden = {r["game_id"]: r for r in v["hidden_scores"]}
    return v, by_id, hidden


def load_board_a():
    """Root-pipeline origination board (data/derived/predictions.csv)."""
    rows = []
    with open(os.path.join(ROOT, "data", "derived", "predictions.csv")) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def load_board_b():
    """Origination-lab slate (origination-lab/data/derived/lines.json)."""
    with open(os.path.join(ROOT, "origination-lab", "data", "derived", "lines.json")) as f:
        d = json.load(f)
    return d["slate"]["rows"], d["slate"].get("asof", "")


def load_props():
    rows = []
    with open(os.path.join(ROOT, "origination-lab", "data", "derived", "prop_lines.csv")) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def settle(margin_vs_line):
    if margin_vs_line == "":
        return ""
    if margin_vs_line > 0:
        return "win"
    if margin_vs_line < 0:
        return "loss"
    return "push"


def main():
    os.makedirs(OUT, exist_ok=True)
    games = load_games()
    verified, verified_by_id, hidden_by_id = load_verified()
    board_a = load_board_a()
    board_b, slate_asof = load_board_b()
    props = load_props()

    # ------------------------------------------------------------------
    # Results feed: every REG game 2023+ in the archive, plus official
    # overlay (verified rows replace archive values; hidden rows keep the
    # archive values flagged as unverified).
    # ------------------------------------------------------------------
    feed_rows = []
    archive_agree = 0
    archive_disagree = 0
    archive_filled_by_official = 0
    for gid, g in sorted(games.items()):
        if g["season"] < "2023" or g["game_type"] != "REG":
            continue
        ver = verified_by_id.get(gid)
        hid = hidden_by_id.get(gid)
        a_away, a_home = fnum(g["away_score"]), fnum(g["home_score"])
        if ver:
            o_away, o_home = fnum(ver["away_score"]), fnum(ver["home_score"])
            if a_away == "" and a_home == "":
                score_status = "verified-official (official score added; archive was empty)"
                archive_filled_by_official += 1
            elif a_away == o_away and a_home == o_home:
                score_status = "verified-official (archive agrees)"
                archive_agree += 1
            else:
                score_status = "verified-official (ARCHIVE DISAGREES - official wins)"
                archive_disagree += 1
            away_score, home_score = o_away, o_home
            official_url = ver["source_url"]
            verified_on = verified["meta"]["verified_on"]
        else:
            away_score, home_score = a_away, a_home
            if a_away == "" or a_home == "":
                score_status = "missing (archive empty; not yet verified)"
            else:
                score_status = "archived-unverified"
            official_url = ""
            verified_on = ""
        flags = []
        if hid and not ver:
            flags.append("official page returned Hidden Score on 2026-11-14; score not verified")
        if ver and score_status.startswith("verified-official (ARCHIVE DISAGREES"):
            flags.append("archive disagrees with official source")

        home_margin = ""
        total_points = ""
        if away_score != "" and home_score != "":
            home_margin = home_score - away_score
            total_points = home_score + away_score

        spread_line = fnum(g["spread_line"])
        total_line = fnum(g["total_line"])
        home_ml = fnum(g["home_moneyline"])
        away_ml = fnum(g["away_moneyline"])

        ats_home = total_over = ml_home = ""
        if home_margin != "" and spread_line != "":
            ats_home = settle(home_margin - spread_line)
        if total_points != "" and total_line != "":
            total_over = settle(total_points - total_line)
        if home_margin != "" and home_ml != "" and away_ml != "":
            ml_home = "win" if home_margin > 0 else ("loss" if home_margin < 0 else "push")

        line_status = "archived-unverified" if spread_line != "" else "blank-missing"
        if home_margin != "" and (spread_line == "" or total_line == ""):
            settle_status = "partial (closing line missing for some markets)"
        elif home_margin != "":
            settle_status = "settled"
        else:
            settle_status = "unsettled"

        feed_rows.append({
            "game_id": gid,
            "season": g["season"],
            "week": g["week"],
            "gameday": g["gameday"],
            "away_team": g["away_team"],
            "home_team": g["home_team"],
            "away_score": fmt(away_score, 1),
            "home_score": fmt(home_score, 1),
            "home_margin": fmt(home_margin, 1),
            "total_points": fmt(total_points, 1),
            "score_status": score_status,
            "spread_close_home": fmt(spread_line, 1),
            "total_close": fmt(total_line, 1),
            "home_ml_close": fmt(home_ml, 1),
            "away_ml_close": fmt(away_ml, 1),
            "line_status": line_status,
            "ats_home_result": ats_home,
            "total_over_result": total_over,
            "ml_home_result": ml_home,
            "settle_status": settle_status,
            "official_source_url": official_url,
            "verified_on": verified_on,
            "flags": "; ".join(flags),
        })

    with open(os.path.join(OUT, "results_feed.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(feed_rows[0].keys()))
        w.writeheader()
        w.writerows(feed_rows)

    # ------------------------------------------------------------------
    # Price snapshots: one row per (game, market type, originating engine).
    # Opening numbers: no official or archived opening-line source covers
    # our origination window (the only opening archive in the repo,
    # origination-lab/data/raw/initial_lines.csv, is WSGT 2021 spread/total
    # only). Per policy the open columns are BLANK with status
    # "blank-missing-no-source" and flag PS-F-01.
    # ------------------------------------------------------------------
    open_status = "blank-missing-no-source"
    open_flag = "PS-F-01: no opening-line source covers this market; value left blank"

    snap_rows = []

    def snap(game_id, season, week, gameday, engine, mtype, our_line, our_price,
             close_line, close_price, diff, diff_unit, our_status, close_status):
        snap_rows.append({
            "market_id": f"{game_id}:{mtype}:{engine}",
            "game_id": game_id,
            "season": season,
            "week": week,
            "gameday": gameday,
            "market_type": mtype,
            "origin_engine": engine,
            "our_fair_line": fmt(our_line),
            "our_fair_price_american": fmt(our_price, 1),
            "our_status": our_status,
            "market_open_line": "",
            "market_open_price_american": "",
            "open_status": open_status,
            "market_close_line": fmt(close_line),
            "market_close_price_american": fmt(close_price, 1),
            "close_status": close_status,
            "difference": fmt(diff),
            "difference_unit": diff_unit,
            "difference_status": "computed (our_fair_line - market_close_line)" if diff != "" else "blank (input missing)",
            "official_source_url": "",
            "flags": open_flag,
        })

    for r in board_a:
        gid = r["game_id"]
        g = games.get(gid, {})
        model_margin, model_total = fnum(r["model_margin"]), fnum(r["model_total"])
        mkt_margin, mkt_total = fnum(r["market_margin"]), fnum(r["market_total"])
        close_status = "archived-unverified (nflverse-derived games.csv.gz via data/derived)"
        snap(gid, r["season"], r["week"], g.get("gameday", ""), "root-pipeline",
             "SPREAD", model_margin, "", mkt_margin, "",
             (model_margin - mkt_margin) if (model_margin != "" and mkt_margin != "") else "",
             "points (home margin)", "ours-reproducible (data/derived/predictions.csv)", close_status)
        snap(gid, r["season"], r["week"], g.get("gameday", ""), "root-pipeline",
             "TOTAL", model_total, "", mkt_total, "",
             (model_total - mkt_total) if (model_total != "" and mkt_total != "") else "",
             "points", "ours-reproducible (data/derived/predictions.csv)", close_status)

    for r in board_b:
        gid = r["game_id"]
        g = games.get(gid, {})
        season = g.get("season", gid[:4])
        week = g.get("week", r.get("week", ""))
        # slate 'our_spread' is a DISPLAY home line (negative = home favourite);
        # confirmed against 'our_home_win_prob' (our_spread<0 <-> p_home>0.5) and
        # reproducible as edge_home_pts == our_spread - market_home_line.
        # Convert to home-margin convention (positive = home favoured) by negation.
        our_spread_disp, mkt_spread = fnum(r.get("our_spread")), fnum(r.get("market_spread"))
        our_margin = -our_spread_disp if our_spread_disp != "" else ""
        our_total, mkt_total = fnum(r.get("our_total")), fnum(r.get("market_total"))
        our_prob = fnum(r.get("our_home_win_prob"))
        mkt_home_ml, mkt_away_ml = fnum(r.get("market_home_ml")), fnum(r.get("market_away_ml"))
        our_status = "ours-reproducible (origination-lab lines.json slate; display line negated to home-margin convention)"
        snap(gid, season, week, r.get("gameday", g.get("gameday", "")), "origination-lab",
             "SPREAD", our_margin, "", mkt_spread, "",
             (our_margin - mkt_spread) if (our_margin != "" and mkt_spread != "") else "",
             "points (home margin)", our_status,
             close_status if mkt_spread != "" else "blank (market not yet priced/closed)")
        snap(gid, season, week, r.get("gameday", g.get("gameday", "")), "origination-lab",
             "TOTAL", our_total, "", mkt_total, "",
             (our_total - mkt_total) if (our_total != "" and mkt_total != "") else "",
             "points", our_status,
             close_status if mkt_total != "" else "blank (market not yet priced/closed)")
        if our_prob != "":
            if mkt_home_ml != "":
                p_home_mkt = american_to_prob(mkt_home_ml)
                p_away_mkt = american_to_prob(mkt_away_ml) if mkt_away_ml != "" else 0.0
                norm = p_home_mkt + p_away_mkt
                p_mkt_norm = (p_home_mkt / norm) if norm > 0 else ""
            else:
                p_mkt_norm = ""
            snap(gid, season, week, r.get("gameday", g.get("gameday", "")), "origination-lab",
                 "MONEYLINE", our_prob, prob_to_american(our_prob), p_mkt_norm,
                 mkt_home_ml if mkt_home_ml != "" else "",
                 (our_prob - p_mkt_norm) if p_mkt_norm != "" else "",
                 "home win probability (market prob normalised over both prices)",
                 our_status,
                 close_status if p_mkt_norm != "" else "blank (market not yet priced/closed)")

    with open(os.path.join(OUT, "price_snapshots.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(snap_rows[0].keys()))
        w.writeheader()
        w.writerows(snap_rows)

    # ------------------------------------------------------------------
    # Player-prop snapshots (market price columns blank: no prop-price
    # archive exists in the repo - flag PS-F-02).
    # ------------------------------------------------------------------
    prop_rows = []
    for r in props:
        our_line = fnum(r["our_line"])
        actual = fnum(r["actual"])
        settle_vs_our = settle(actual - our_line) if (actual != "" and our_line != "") else ""
        prop_rows.append({
            "market_id": f"{r['season']}_wk{r['week']}_{r['player_id']}_{r['market']}",
            "season": r["season"],
            "week": r["week"],
            "player_id": r["player_id"],
            "player": r["player_display_name"],
            "team": r["recent_team"],
            "opponent": r["opponent_team"],
            "market": r["market"],
            "our_line": fmt(our_line),
            "our_status": "ours-reproducible (origination-lab/data/derived/prop_lines.csv)",
            "market_open_line": "",
            "market_close_line": "",
            "market_status": "blank-missing-no-source",
            "actual": fmt(actual, 1),
            "actual_status": "archived-unverified (nflverse weekly stats)",
            "settle_vs_our_line": settle_vs_our,
            "official_source_url": "",
            "flags": "PS-F-02: no player-prop market price archive exists; open/close columns left blank",
        })
    with open(os.path.join(OUT, "price_snapshots_props.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(prop_rows[0].keys()))
        w.writeheader()
        w.writerows(prop_rows)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    summary = {
        "generated_from": [
            "data/derived/predictions.csv (root pipeline board A)",
            "origination-lab/data/derived/lines.json slate (board B)",
            "origination-lab/data/derived/prop_lines.csv (props)",
            "data/derived/games.csv.gz (nflverse-derived archive)",
            "price-desk/data/verified_results_2026.json (official overlay)",
        ],
        "slate_asof": slate_asof,
        "spread_convention": SPREAD_CONVENTION,
        "games_in_feed": len(feed_rows),
        "feed_by_score_status": dict(Counter(r["score_status"].split(" (")[0] for r in feed_rows)),
        "archive_crosscheck": {
            "official_rows": sum(1 for r in feed_rows if r["score_status"].startswith("verified-official")),
            "archive_agrees": archive_agree,
            "archive_disagrees": archive_disagree,
            "official_filled_empty_archive": archive_filled_by_official,
        },
        "settled_games": sum(1 for r in feed_rows if r["settle_status"] == "settled"),
        "snapshot_rows": len(snap_rows),
        "snapshot_by_market_type": dict(Counter(r["market_type"] for r in snap_rows)),
        "snapshot_by_engine": dict(Counter(r["origin_engine"] for r in snap_rows)),
        "open_column_status": {
            "status": open_status,
            "note": "The only opening-line archive in the repository covers WSGT 2021 spread/total (origination-lab/data/raw/initial_lines.csv), which is outside our 2023-2026 origination window. No official body publishes historical opening odds. Open columns are therefore blank by policy (flag PS-F-01).",
        },
        "prop_rows": len(prop_rows),
        "prop_by_settle": dict(Counter(r["settle_vs_our_line"] for r in prop_rows)),
        "verification_policy": {
            "verified-official": "digit-for-digit from an official NFL page/gamebook, with URL and date",
            "archived-unverified": "third-party archive value retained for computation, never presented as verified",
            "blank-missing-no-source": "no source exists; value left blank and flagged",
            "ours-reproducible": "our own model output, reproducible from named repo files",
            "computed": "arithmetic over stated inputs; inherits weakest input status",
        },
    }
    with open(os.path.join(OUT, "store_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
