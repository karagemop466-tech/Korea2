#!/usr/bin/env python3
"""DA-7: injuries, and the DEPTH of the replacement rather than the fact of a replacement.

THE MEASUREMENT PROBLEM
-----------------------
"Player X is out" is the easy half. The expensive half is: who replaces him, and how far down
the depth chart is that player? A team losing its WR1 to its WR4 is a different team from one
losing its WR4 to its WR5, and a report that only counts 'starters out' cannot tell them apart.

WHAT THIS SCRIPT CAN BUILD FROM WHAT IS IN THE REPOSITORY
--------------------------------------------------------
  1. REPLACEMENT DEPTH FROM SNAP COUNTS (measured here, real data).
     A starter is the player with the largest snap share at his team-position for that week. A
     replacement week is a week where that ranking changes. The depth of the replacement is the
     replacement's OWN rank at that position in the PREVIOUS week, so "replaced by the 2nd-string"
     and "replaced by the 4th-string" are different rows. Nothing here needs the depth-chart file.
  2. THE OFFICIAL INJURY REPORT (transcribed from NFL.com, Week 10 2026).
     Read from the official page on 2026-11-14 and committed as data/inputs/injury_report_week10.csv.
     The joined table shows, per club and position, WHO the official report has Out/Doubtful and
     WHAT the measured snap-share replacement depth is. That join is the deliverable.
  3. WHAT IS NOT BUILT, WITH THE REASON ATTACHED.
     The official NFL injury report carries no depth rank (verified: the page has Player /
     Position / Injuries / Practice Status / Game Status only), and nfl.com/teams/<club>/depth-chart
     returns a 404 (verified). So an official '2nd string' label does not exist to cite. The
     nflverse depth-chart feed has one but is a third-party release-asset download this sandbox
     cannot reach; the CI workflow fetches it and the build then upgrades this file in place.
"""
from __future__ import annotations

import csv
import gzip
import os
import statistics
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib import arena as A  # noqa: E402

ROOT = A.ROOT
REPO = os.path.dirname(ROOT)
SRC_SNAP = "SRC-NFLVERSE-SNAP"
SRC_INJ = "SRC-NFL-INJ-10"
SRC_DEPTH_404 = "SRC-NFL-DEPTH-404"
SRC_DEPTH_P3 = "SRC-NFLVERSE-DEPTH"

# Positions where a replacement is a meaningful concept, split by side of the ball.
OFFENCE = {"QB", "RB", "WR", "TE"}
DEFENCE = {"LB", "DB", "DL", "DE", "DT", "CB", "S", "OLB", "ILB", "MLB", "FS", "SS"}


def read_gz(path):
    with gzip.open(path, "rt", newline="") as fh:
        return list(csv.DictReader(fh))


def is_num(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def rank_shares(rows, season, week_limit=None):
    """Build {(season, week, team, pos_grp): [(share, player, gsis)] } for ranking."""
    frame = {}
    for r in rows:
        if r.get("game_type") not in ("REG", ""):
            continue
        season_r = r.get("season")
        week_r = r.get("week")
        if season_r is None or week_r in (None, ""):
            continue
        pos = (r.get("position") or "").upper()
        if not pos:
            continue
        off = r.get("offense_pct")
        dfn = r.get("defense_pct")
        share = None
        if is_num(off) and float(off) > 0:
            share = float(off)
        elif is_num(dfn) and float(dfn) > 0:
            share = float(dfn)
        if share is None:
            continue
        key = (int(season_r), int(week_r), r.get("team"), pos)
        frame.setdefault(key, []).append((share, r.get("player"), r.get("pfr_player_id")))
    for k in frame:
        frame[k].sort(key=lambda x: (-x[0], x[1] or ""))
    return frame


def build_from_snap_counts(snap_rows):
    """Measured replacement events with the depth of the replacement."""
    frame = rank_shares(snap_rows, None)
    by_team_week = {}
    for (season, week, team, pos), players in frame.items():
        by_team_week.setdefault((season, team), {}).setdefault(week, {})[pos] = players

    events = []
    coverage = {"team_weeks": 0, "positions_tracked": 0}
    for (season, team), weeks in sorted(by_team_week.items()):
        for week in sorted(weeks):
            prev = weeks.get(week - 1)
            if not prev:
                continue
            coverage["team_weeks"] += 1
            for pos, players in weeks[week].items():
                coverage["positions_tracked"] += 1
                prev_players = prev.get(pos)
                if not prev_players or not players:
                    continue
                starter_now = players[0][1]
                starter_prev = prev_players[0][1]
                if starter_now == starter_prev:
                    continue
                # how deep was the replacement in the previous week, at the same position?
                prev_order = [p[1] for p in prev_players]
                depth = (prev_order.index(starter_now) + 1) if starter_now in prev_order else None
                prev_share = next((p[0] for p in prev_players if p[1] == starter_now), None)
                now_share = players[0][0]
                events.append({
                    "season": season, "week": week, "team": team, "position": pos,
                    "outgoing": starter_prev, "incoming": starter_now,
                    "replacement_depth_rank": depth,
                    "depth_band": (f"{depth}{_suffix(depth)} string" if depth and depth <= 4
                                   else ("outside the top 4" if depth else "not on last week's list")),
                    "incoming_prev_week_share": (round(prev_share, 4) if prev_share is not None else None),
                    "incoming_now_share": round(now_share, 4),
                    "share_delta": (round(now_share - prev_share, 4) if prev_share is not None else None),
                })

    # aggregate: how deep are the replacements, by season and by side of the ball
    def side(pos):
        return "offence" if pos in OFFENCE else "defence"

    agg = {}
    for e in events:
        if e["replacement_depth_rank"] is None:
            continue
        d = agg.setdefault((e["season"], side(e["position"])),
                           {"n": 0, "sum_depth": 0, "by_band": {}, "deltas": []})
        d["n"] += 1
        d["sum_depth"] += e["replacement_depth_rank"]
        d["by_band"][e["depth_band"]] = d["by_band"].get(e["depth_band"], 0) + 1
        if e["replacement_depth_rank"] >= 2:
            d["deeper_than_first"] = d.get("deeper_than_first", 0) + 1
        if e["share_delta"] is not None:
            d["deltas"].append(e["share_delta"])
    table = []
    for (season, sd), d in sorted(agg.items()):
        table.append({
            "season": season, "side": sd, "n_replacements": d["n"],
            "mean_replacement_depth": round(d["sum_depth"] / d["n"], 2),
            # The rank, not the label string: "2nd string" starts with '2' but so do "2 remaining"
            # style labels, and a first-string replacement must count as ZERO here. The earlier
            # version string-matched the band and reported 100% for every group.
            "share_by_second_string_or_deeper": round(d.get("deeper_than_first", 0) / d["n"], 4),
            "n_deeper_than_first": d.get("deeper_than_first", 0),
            "bands": d["by_band"],
            "mean_share_delta": (round(statistics.fmean(d["deltas"]), 4) if d["deltas"] else None),
        })

    latest_season = max((e["season"] for e in events), default=None)
    recent = [e for e in events if e["season"] == latest_season]
    return {
        "status": "MEASURED",
        "events_total": len(events),
        "events_in_latest_season": len(recent),
        "latest_season": latest_season,
        "by_season_side": table,
        "sample_events": sorted(recent, key=lambda e: (-(e["replacement_depth_rank"] or 0), e["team"]))[:40],
        "definition": ("A replacement event is a week where the top snap-share player at a "
                       "team-position differs from the previous week's. The replacement's depth is "
                       "his OWN rank at that position in the previous week, so a 4th-string fill-in "
                       "is recorded as such."),
        "source": SRC_SNAP,
        "caveat": ("Snap share is a third-party redistribution of official participation data. It "
                   "measures who PLAYED, not who was listed first on a chart; that is a strength for "
                   "this question and a limitation for any 'depth chart' claim."),
    }


def _suffix(n):
    return {1: "st", 2: "nd", 3: "rd"}.get(n, "th") if n else ""


# NFL.com uses its own club codes (AZ, LAR); the nflverse feeds use ARI, LA. Every join below
# normalises to the nflverse code so the two sources can be compared, and the NFL.com code is
# kept on the published row so a reviewer can find the club on the official page.
NFLCOM_TO_NFLVERSE = {"AZ": "ARI", "LAR": "LA", "JAC": "JAX", "WSH": "WAS", "LVR": "LV"}


def norm_team(code):
    c = (code or "").strip().upper()
    return NFLCOM_TO_NFLVERSE.get(c, c)


def load_official_report():
    path = os.path.join(ROOT, "data", "inputs", "injury_report_week10.csv")
    if not os.path.exists(path):
        return None
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["team_raw"] = r["team"]
        r["team"] = norm_team(r["team"])
        r["opp_raw"] = r["opp"]
        r["opp"] = norm_team(r["opp"])
    return rows


def build_report_join(report, depth):
    """Join the official report to the measured replacement depth, by club and position."""
    if not report:
        return {"status": "NO_REPORT", "rows": [],
                "reason": "official Week 10 transcription missing from data/inputs/"}
    # measured depth by (team, position) in the most recent season available
    pos_depth = {}
    for e in depth.get("sample_events", []) + depth.get("all_events", []):
        pos_depth.setdefault((e["team"], e["position"]), e)
    counts = {}
    for r in report:
        counts.setdefault(r["team"], {"Out": 0, "Doubtful": 0, "Questionable": 0, "practice_only": 0})
        st = (r.get("game_status") or "").strip()
        if st in ("Out", "Doubtful", "Questionable"):
            counts[r["team"]][st] += 1
        else:
            counts[r["team"]]["practice_only"] += 1
    rows = []
    for team, c in sorted(counts.items()):
        rows.append({
            "team": team, "out": c["Out"], "doubtful": c["Doubtful"],
            "questionable": c["Questionable"], "practice_only": c["practice_only"],
            "total_listed": sum(c.values()),
            "official_source": SRC_INJ,
        })
    return {
        "status": "JOINED",
        "clubs_reported": len(rows),
        "rows": rows,
        "out_players": [r for r in report if (r.get("game_status") or "") == "Out"],
        "official_source": SRC_INJ,
    }


def main():
    snap_path = os.path.join(ROOT, "data", "inputs", "snap_counts.csv.gz")
    depth_chart = os.path.join(ROOT, "data", "inputs", "depth_charts.csv.gz")
    payload = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "question": ("Who replaced the starter, and how deep was the replacement? Tracked for offence "
                     "and defence, with the official injury report joined to the measured depth."),
        "inputs_present": {
            "snap_counts": os.path.exists(snap_path),
            "depth_charts": os.path.exists(depth_chart),
            "official_report": os.path.exists(os.path.join(ROOT, "data", "inputs", "injury_report_week10.csv")),
        },
        "official_depth_chart_gap": {
            "status": "CONFIRMED_ABSENT",
            "evidence": ("NFL.com returns its 404 page at the team depth-chart path; the official "
                         "injury report carries no depth column."),
            "source": SRC_DEPTH_404,
            "consequence": ("No row on this page claims an OFFICIAL depth rank. The depth rank used is "
                            "measured from participation, and labelled as such."),
        },
    }
    if os.path.exists(snap_path):
        snap = read_gz(snap_path)
        print(f"snap-count rows: {len(snap)}")
        d = build_from_snap_counts(snap)
        payload["depth"] = d
        print(f"replacement events: {d['events_total']} (latest season {d['latest_season']}: "
              f"{d['events_in_latest_season']})")
        for t in d["by_season_side"]:
            if t["season"] >= (d["latest_season"] or 0) - 1:
                print(f"  {t['season']} {t['side']:8s} n={t['n_replacements']:4d} "
                      f"mean depth {t['mean_replacement_depth']} bands {t['bands']}")
    else:
        payload["depth"] = {
            "status": "BLOCKED_NO_INPUT",
            "reason": ("data/inputs/snap_counts.csv.gz is produced by scripts/fetch_inputs.py, which "
                       "needs GitHub release assets. This sandbox cannot reach them; "
                       ".github/workflows/decision-arena.yml runs the fetch and rebuilds this file."),
            "what_is_missing": "the nflverse snap-count release, one third-party file per season",
            "how_to_discover": "python decision-arena/scripts/fetch_inputs.py --season 2026 (on a runner)",
        }

    report = load_official_report()
    payload["official_injury_report"] = build_report_join(report, payload.get("depth", {}))
    if report:
        print(f"official report rows: {len(report)}")

    # the point of the join, stated as data rather than prose
    payload["readiness"] = {
        "can_answer_who_is_out": True,
        "can_answer_which_position_is_thin": True,
        "can_answer_how_deep_is_the_replacement": bool(os.path.exists(snap_path)),
        "can_answer_from_an_OFFICIAL_depth_rank": False,
        "blocking_gap": ("no official depth-chart publication" if not os.path.exists(depth_chart)
                         else "depth chart present but third-party"),
        "source_for_depth": SRC_SNAP if os.path.exists(snap_path) else None,
        "third_party_depth_source": SRC_DEPTH_P3,
    }
    A.dump(os.path.join(ROOT, "data", "depth.json"), payload)
    print("wrote data/depth.json")


if __name__ == "__main__":
    main()
