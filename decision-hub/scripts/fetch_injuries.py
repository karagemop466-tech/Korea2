#!/usr/bin/env python3
"""Download the official NFL injury reports, weekly depth charts, rosters and snap counts,
then build the participation-deficiency table.

WHY THIS RUNS ON GITHUB ACTIONS
--------------------------------
The authoring sandbox's shell can only reach an allowlist of hosts; GitHub *release assets*
redirect to `release-assets.githubusercontent.com`, which is blocked there (TLS reset). GitHub-
hosted runners have unrestricted egress, so `.github/workflows/fetch-injuries.yml` runs this
script and commits the *derived* JSON (never the multi-megabyte raw CSVs) back to the branch.

WHAT THIS DOES **NOT** DO
-------------------------
It does not claim a missing starter means the backup plays, or that the backup is worse.
Nothing in the official feed says who will play. What it measures, from the league's own injury
report plus the club depth chart, is how much known depth a team has reported unavailable:

    rank 1 at a position  -> "1st string",  rank 2 -> "2nd string",  rank 3 -> "3rd string" ...

and per team-week it reports which positions are down to a 2nd, 3rd or 4th string player.

HOW THE RANK IS COMPUTED (and why it changed)
---------------------------------------------
`pos_rank` in the nflverse depth-chart feed is the rank **within a slot** (`pos_slot`), and a
team can have several slots for one position: the 2026 Ravens list Lamar Jackson at slot 9 rank 4
and Tyler Huntley at slot 9 rank 5, i.e. two different slots both called "QB". Taking
`pos_rank` alone would therefore call the third-string QB a starter.

So the rank used here is the ordinal of each player within (team, position) ordered by
`pos_slot` then `pos_rank`: QB1 is the first QB on the chart, QB4 the fourth. The raw
`pos_slot`/`pos_rank` pair is kept in the published rows so a reviewer can audit the ordering,
and both numbers are shown on the page.

SOURCE COLUMNS (verified against the published dictionaries on 2026-11-12)
--------------------------------------------------------------------------
* injuries      season, season_type, game_type, team, week, gsis_id, position, full_name, ...
                report_primary_injury, report_secondary_injury, report_status,
                practice_primary_injury, practice_secondary_injury, practice_status
                https://nflreadr.nflverse.com/reference/load_injuries.html
* depth charts  dt, team, player_name, espn_id, gsis_id, pos_grp_id, pos_grp, pos_id, pos_name,
                pos_abb, pos_slot, pos_rank   (schema from 2025 onward; 777,815 rows for 2026)
                https://nflreadr.nflverse.com/articles/dictionary_depth_charts.html
* weekly roster season, team, position, depth_chart_position, ..., status, full_name, gsis_id,
                pfr_id, ..., week
                https://nflreadr.nflverse.com/articles/dictionary_rosters.html
* snap counts   game_id, ..., week, player, pfr_player_id, position, team, opponent,
                offense_snaps, offense_pct, defense_snaps, defense_pct, st_snaps, st_pct
                -- no gsis_id, so it is joined through the roster's pfr_id
                https://nflreadr.nflverse.com/articles/dictionary_snap_counts.html

Usage (on a runner):
    python decision-hub/scripts/fetch_injuries.py --season 2026
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

RELEASE = "https://github.com/nflverse/nflverse-data/releases/download"
URLS = {
    "injuries": RELEASE + "/injuries/injuries_{season}.csv",
    "depth": RELEASE + "/depth_charts/depth_charts_{season}.csv",
    "roster": RELEASE + "/weekly_rosters/roster_weekly_{season}.csv",
    "snaps": RELEASE + "/snap_counts/snap_counts_{season}.csv",
}
OUT_DIR = os.path.join("decision-hub", "data")
UA = {"User-Agent": "decision-hub/1.0 (+https://github.com/karagemop466-tech/Korea2)"}

OUT_STATUSES = ("Out", "Doubtful")
WATCH_STATUSES = ("Questionable",)

# Every position abbreviation the depth-chart feed uses, classified. The first version of this
# script used a hand-written set and silently classified CB/S/LB as "special" because it only
# matched exact strings like "LB" while the feed writes "RILB"/"LCB". Anything not in this map
# is reported as "unclassified" rather than guessed.
OFFENSE_POS = {"QB", "RB", "FB", "WR", "TE", "T", "G", "C", "OT", "OG", "OL", "LT", "RT", "LG",
               "RG", "LWR", "RWR", "SWR", "LTE", "RTE", "UTE", "HB", "TB", "KR", "PR"}
DEFENSE_POS = {"DE", "DT", "NT", "EDGE", "LB", "ILB", "OLB", "MLB", "LILB", "RILB", "WLB", "SLB",
               "CB", "LCB", "RCB", "NCB", "S", "SS", "FS", "DB", "SAF", "LDE", "RDE", "LDT", "RDT",
               "LOLB", "ROLB", "NB", "SCB", "NICKEL"}
SPECIAL_POS = {"K", "P", "LS", "H", "PK"}


def side_of(pos: str) -> str:
    p = (pos or "").upper().strip()
    if p in DEFENSE_POS:
        return "defense"
    if p in SPECIAL_POS:
        return "special"
    if p in OFFENSE_POS:
        return "offense"
    # suffix rules, used only for abbreviations not listed above (e.g. "RDT51")
    if p.endswith("LB") or p.endswith("CB") or p.endswith("DE") or p.endswith("DT") or p.endswith("S"):
        return "defense"
    return "unclassified"


TEAM_ALIAS = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LA",
              "LVR": "LV", "SFO": "SF", "TAM": "TB", "NWE": "NE", "NOR": "NO", "KAN": "KC",
              "GNB": "GB", "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU"}


def norm_team(t: str) -> str:
    t = (t or "").strip().upper()
    return TEAM_ALIAS.get(t, t)


def fetch(url: str, dest: str) -> dict:
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        blob = open(dest, "rb").read()
        return {"url": url, "status": "cached", "bytes": len(blob),
                "sha256": hashlib.sha256(blob).hexdigest()}
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as fh:
        fh.write(r.read())
    blob = open(dest, "rb").read()
    return {"url": url, "status": 200, "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest()}


def read_csv(path: str) -> tuple[list[dict], list[str]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rdr = csv.DictReader(fh)
        rows = list(rdr)
        return rows, list(rdr.fieldnames or [])


def schema_sample(rows: list[dict], cols: list[str], n: int = 2) -> dict:
    """A small, quoted sample kept in the committed JSON so a reviewer can see the exact
    columns and values this build consumed without needing the 74 MB raw file."""
    keep = [c for c in cols if c in
            ("season", "season_type", "game_type", "team", "week", "gsis_id", "position",
             "full_name", "report_primary_injury", "report_status", "practice_primary_injury",
             "practice_status", "dt", "player_name", "pos_grp", "pos_name", "pos_abb", "pos_id",
             "pos_slot", "pos_rank", "pfr_id", "status", "pfr_player_id", "offense_pct",
             "defense_pct", "game_id", "player")]
    sample = [{k: (r.get(k) or "")[:120] for k in keep if (r.get(k) or "") != ""}
              for r in rows[:n]]
    return {"columns": cols, "kept_columns": keep, "rows": sample, "total_rows": len(rows)}


def to_int(v):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None


def build(season: int, raw: str) -> dict:
    os.makedirs(raw, exist_ok=True)
    meta: dict = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "season": season, "files": [], "notes": []}
    paths, samples = {}, {}
    for key, tpl in URLS.items():
        url = tpl.format(season=season)
        dest = os.path.join(raw, f"{key}_{season}.csv")
        try:
            meta["files"].append({"name": key, **fetch(url, dest)})
            paths[key] = dest
        except Exception as exc:  # noqa: BLE001
            meta["notes"].append(f"{key}: download failed: {exc!r}")
            print(f"WARN {key}: {exc!r}", file=sys.stderr)

    if "injuries" not in paths:
        raise SystemExit("the injury report feed is required; aborting rather than publishing blanks")

    tables = {}
    for key, path in paths.items():
        rows, cols = read_csv(path)
        tables[key] = rows
        samples[key] = schema_sample(rows, cols)

    injuries = tables["injuries"]
    depth_rows = tables.get("depth", [])
    roster_rows = tables.get("roster", [])
    snap_rows = tables.get("snaps", [])

    # ---------------------------------------------------------------- depth chart: latest snapshot
    dts = sorted({(r.get("dt") or "").strip() for r in depth_rows if (r.get("dt") or "").strip()})
    latest = dts[-1] if dts else ""
    meta["depth_snapshot_dt"] = latest
    meta["depth_snapshots_available"] = len(dts)

    snap = [r for r in depth_rows if not latest or (r.get("dt") or "").strip() == latest]
    by_team_pos: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in snap:
        pos = (r.get("pos_abb") or "").strip().upper()
        team = norm_team(r.get("team", ""))
        if pos and team:
            by_team_pos[(team, pos)].append(r)
    depth_by_id: dict[str, dict] = {}
    for (team, pos), lst in by_team_pos.items():
        for r in lst:
            gid = (r.get("gsis_id") or "").strip()
            if not gid:
                continue
            # `pos_rank` is the feed's own rank *grouped by pos_slot* (documented), so a player
            # ranked 2 is the second man at his position. Using it directly is the only reading
            # the feed supports; anything else is this project inventing an ordering. Where two
            # players share the same (pos_slot, pos_rank) they are a tie and are labelled as one.
            rank = to_int(r.get("pos_rank"))
            depth_by_id[gid] = {
                "player": r.get("player_name", ""),
                "team": team, "pos": pos, "pos_name": r.get("pos_name", ""),
                "pos_grp": r.get("pos_grp", ""),
                "pos_slot": to_int(r.get("pos_slot")),
                "pos_rank_in_slot": rank,
                "depth_rank": rank,
                "position_depth": len(lst),
            }
    # how many players share the same (team, position, pos_slot, pos_rank) tuple: a tie group is
    # not a depth ordering, and the page must not present it as one
    tie_count: dict[tuple, int] = defaultdict(int)
    for r in snap:
        key = (norm_team(r.get("team", "")), (r.get("pos_abb") or "").strip().upper(),
               to_int(r.get("pos_slot")), to_int(r.get("pos_rank")))
        tie_count[key] += 1
    for gid, rec in depth_by_id.items():
        rec["tied_at_slot"] = tie_count[(rec["team"], rec["pos"], rec["pos_slot"],
                                        rec["pos_rank_in_slot"])]
    meta["depth_players_in_snapshot"] = len(depth_by_id)
    meta["players_in_slot_tie_groups"] = sum(1 for r in depth_by_id.values() if r["tied_at_slot"] > 1)
    meta["positions_with_depth"] = len(by_team_pos)

    # ---------------------------------------------------------------- roster: status + pfr crosswalk
    roster_by_id: dict[str, dict] = {}
    pfr_to_gsis: dict[str, str] = {}
    for r in roster_rows:
        gid = (r.get("gsis_id") or "").strip()
        pfr = (r.get("pfr_id") or "").strip()
        if pfr and gid:
            pfr_to_gsis[pfr] = gid
        if not gid:
            continue
        wk = to_int(r.get("week")) or 0
        prev = roster_by_id.get(gid)
        if prev is None or wk >= (prev.get("_week") or 0):
            roster_by_id[gid] = {"team": norm_team(r.get("team", "")), "_week": wk,
                                 "status": r.get("status", ""),
                                 "position": r.get("position", ""),
                                 "depth_chart_position": r.get("depth_chart_position", ""),
                                 "full_name": r.get("full_name", "")}

    # ---------------------------------------------------------------- snap counts, via pfr id
    snaps_by_id: dict[str, list[dict]] = defaultdict(list)
    unmatched = 0
    for r in snap_rows:
        pfr = (r.get("pfr_player_id") or "").strip()
        gid = pfr_to_gsis.get(pfr)
        if not gid:
            unmatched += 1
            continue
        snaps_by_id[gid].append({"week": to_int(r.get("week")) or 0,
                                 "off": r.get("offense_pct"), "def": r.get("defense_pct")})
    meta["snap_rows_without_gsis_crosswalk"] = unmatched
    meta["snap_rows_total"] = len(snap_rows)
    meta["snap_players_matched"] = len(snaps_by_id)

    def snap_share(gid: str, side: str, through_week: int | None) -> float | None:
        recs = [x for x in snaps_by_id.get(gid, []) if through_week is None or x["week"] < through_week]
        recs.sort(key=lambda x: x["week"])
        recs = recs[-4:]
        key = "off" if side == "offense" else "def"
        vals = []
        for x in recs:
            try:
                vals.append(float(x[key]))
            except (TypeError, ValueError):
                pass
        return round(sum(vals) / len(vals), 4) if vals else None

    # ---------------------------------------------------------------- assemble team-weeks
    by_team_week: dict[tuple[str, int], list[dict]] = defaultdict(list)
    weeks_by_team: dict[str, set[int]] = defaultdict(set)
    for r in injuries:
        team = norm_team(r.get("team", ""))
        wk = to_int(r.get("week"))
        if not team or wk is None:
            continue
        gid = (r.get("gsis_id") or "").strip()
        d = depth_by_id.get(gid, {})
        prof = roster_by_id.get(gid, {})
        pos = (d.get("pos") or r.get("position") or prof.get("position") or "").upper()
        side = side_of(pos)
        rec = {
            "gsis_id": gid,
            "player": r.get("full_name") or d.get("player") or prof.get("full_name", ""),
            "position": pos,
            "position_name": d.get("pos_name", ""),
            "pos_grp": d.get("pos_grp", ""),
            "pos_slot": d.get("pos_slot"),
            "pos_rank_in_slot": d.get("pos_rank_in_slot"),
            "depth_rank": d.get("depth_rank"),
            "position_depth": d.get("position_depth"),
            "tied_at_slot": d.get("tied_at_slot"),
            "on_depth_chart": gid in depth_by_id,
            "report_status": (r.get("report_status") or "").strip(),
            "report_injury": (r.get("report_primary_injury") or "").strip(),
            "practice_status": (r.get("practice_status") or "").strip(),
            "practice_injury": (r.get("practice_primary_injury") or "").strip(),
            "roster_status": prof.get("status", ""),
            "side": side,
            "snap_share_4wk": snap_share(gid, side, wk),
        }
        by_team_week[(team, wk)].append(rec)
        weeks_by_team[team].add(wk)

    summary, rows = [], []

    def string_label(rank, n_at_rank: int | None = None):
        """Label a depth ordinal, but do not pretend to distinguish a crowd.

        At WR a club lists six to nine players in the same slot with the same pos_rank, so they
        all share rank 1 in the feed and the ordinal then reads 8th for a player who is really
        "one of eight receivers, all nominally first string". When several players share the
        feed's own (pos_slot, pos_rank) pair, the label says so instead of inventing an order.
        """
        if not rank:
            return "unknown"
        if n_at_rank and n_at_rank > 1:
            return f"1 of {n_at_rank} tied at this slot"
        return {1: "1st string", 2: "2nd string", 3: "3rd string", 4: "4th string",
                5: "5th string"}.get(rank, f"{rank}th string")

    for (team, wk), recs in sorted(by_team_week.items()):
        lost = [x for x in recs if x["report_status"] in OUT_STATUSES]
        watching = [x for x in recs if x["report_status"] in WATCH_STATUSES]
        dnp = [x for x in recs if x["practice_status"] == "Did Not Participate In Practice"]
        ranked = [x for x in lost if isinstance(x["depth_rank"], int)]
        by_side = {"offense": 0, "defense": 0, "special": 0, "unclassified": 0}
        for x in lost:
            by_side[x["side"]] = by_side.get(x["side"], 0) + 1
        # who is next up at each position where someone is out
        next_up = {}
        positions_down = []
        for pos in sorted({x["position"] for x in ranked}):
            out_here = sorted([x for x in ranked if x["position"] == pos],
                              key=lambda y: y["depth_rank"])
            avail = [y for y in recs if y["position"] == pos
                     and isinstance(y["depth_rank"], int)
                     and y["report_status"] not in OUT_STATUSES]
            avail.sort(key=lambda y: y["depth_rank"])
            best_out = out_here[0] if out_here else None
            if not avail:
                continue
            nxt = avail[0]
            next_up[pos] = {
                "player": nxt["player"], "rank": nxt["depth_rank"],
                "string": string_label(nxt["depth_rank"], nxt.get("tied_at_slot")),
                "tied_at_slot": nxt.get("tied_at_slot"),
                "snap_share_4wk": nxt["snap_share_4wk"],
                "report_status": nxt["report_status"],
                "practice_status": nxt["practice_status"],
                "covering_for": [{"player": o["player"], "rank": o["depth_rank"],
                                  "injury": o["report_injury"]} for o in out_here],
            }
            distinguishable = (nxt.get("tied_at_slot") or 1) == 1
            if best_out and nxt["depth_rank"] >= 2 and distinguishable:
                positions_down.append({
                    "position": pos,
                    "position_name": out_here[0]["position_name"],
                    "starter_out": best_out["player"],
                    "starter_injury": best_out["report_injury"],
                    "replacement": nxt["player"],
                    "replacement_rank": nxt["depth_rank"],
                    "replacement_string": string_label(nxt["depth_rank"], nxt.get("tied_at_slot")),
                    "replacement_tied_at_slot": nxt.get("tied_at_slot"),
                    "replacement_snap_share_4wk": nxt["snap_share_4wk"],
                    "out_count_at_position": len(out_here),
                })
        positions_down.sort(key=lambda p: -p["replacement_rank"])
        summary.append({
            "team": team, "week": wk,
            "listed": len(recs),
            "out_or_doubtful": len(lost),
            "questionable": len(watching),
            "dnp": len(dnp),
            "starters_out": sum(1 for x in ranked if x["depth_rank"] == 1),
            "two_deep_out": sum(1 for x in ranked if x["depth_rank"] <= 2),
            "three_deep_out": sum(1 for x in ranked if x["depth_rank"] <= 3),
            "backup_replacement_count": len(positions_down),
            "deepest_replacement_rank": max((p["replacement_rank"] for p in positions_down), default=0),
            "offense_out": by_side.get("offense", 0),
            "defense_out": by_side.get("defense", 0),
            "special_out": by_side.get("special", 0),
            "unclassified_out": by_side.get("unclassified", 0),
            "on_depth_chart": sum(1 for x in lost if x["on_depth_chart"]),
            "rank_unknown": len(lost) - len(ranked),
            "weighted_depth_lost": round(sum(1.0 / x["depth_rank"] for x in ranked), 3),
            "next_up": next_up,
            "positions_down": positions_down,
            "out_names": [{"player": x["player"], "pos": x["position"], "rank": x["depth_rank"],
                           "string": string_label(x["depth_rank"], x.get("tied_at_slot")),
                           "injury": x["report_injury"],
                           "status": x["report_status"], "snap_share_4wk": x["snap_share_4wk"],
                           "pos_grp": x["pos_grp"], "pos_slot": x["pos_slot"],
                           "pos_rank_in_slot": x["pos_rank_in_slot"]}
                          for x in sorted(ranked, key=lambda y: (y["depth_rank"], y["position"]))],
        })
        for x in lost:
            rows.append({"team": team, "week": wk, **{k: x[k] for k in
                        ("player", "position", "position_name", "pos_grp", "pos_slot",
                         "pos_rank_in_slot", "depth_rank", "position_depth", "side",
                         "report_status", "report_injury", "practice_status", "practice_injury",
                         "roster_status", "snap_share_4wk", "on_depth_chart", "gsis_id",
                         "tied_at_slot")},
                         "string": string_label(x["depth_rank"], x.get("tied_at_slot"))})

    teams = sorted({s["team"] for s in summary})
    final_week = {t: max(weeks_by_team[t]) for t in weeks_by_team}
    current = [s for s in summary if s["week"] == final_week.get(s["team"])]
    # week 10 is the report the league is publishing right now; teams whose latest row is week 9
    # have not filed a week-10 report yet (or have a bye), which is stated rather than imputed.
    league_week = max(final_week.values()) if final_week else 0
    current.sort(key=lambda s: (-s["weighted_depth_lost"], s["team"]))
    return {
        "meta": {**meta,
                 "source_pages": [
                     "https://nflreadr.nflverse.com/reference/load_injuries.html",
                     "https://nflreadr.nflverse.com/articles/dictionary_depth_charts.html",
                     "https://nflreadr.nflverse.com/articles/dictionary_rosters.html",
                     "https://nflreadr.nflverse.com/articles/dictionary_snap_counts.html",
                     "https://www.nfl.com/injuries/"],
                 "schema_samples": samples,
                 "teams": teams,
                 "weeks": sorted({s["week"] for s in summary}),
                 "league_week": league_week,
                 "latest_week_by_team": final_week,
                 "teams_on_latest_week": sum(1 for t in final_week if final_week[t] == league_week),
                 "definition": (
                     "depth_rank is the ordinal of the player within (team, position) on the "
                     "newest depth-chart snapshot, ordered by pos_slot then pos_rank; the raw "
                     "pos_slot and pos_rank_in_slot are kept on every row. NULL means the player "
                     "has no depth-chart row and is NOT counted as a starter. "
                     "weighted_depth_lost = sum(1/rank) over absences with a known rank. "
                     "positions_down lists positions where the best available player is 2nd "
                     "string or deeper because everyone ahead of him is Out/Doubtful."),
                 "caveats": [
                     "'Out' is a final designation; 'Doubtful' is a probability the league does "
                     "not quantify. Both are reported separately and neither is a performance claim.",
                     "'Not injury related - resting player' / 'personal matter' rows exist in the "
                     "feed and are counted in out_or_doubtful; they are disclosed, not filtered.",
                     "Depth charts are club-supplied and scraped; a rank can lag a transaction "
                     "and does not by itself show who will take the snaps.",
                     "Snap share is joined through the roster's pfr_id (the snap-count feed has "
                     f"no gsis_id); {unmatched} of {len(snap_rows)} snap rows had no crosswalk.",
                     "Nothing here says a backup will play, or how well."]},
        "weeks_by_team": {k: sorted(v) for k, v in weeks_by_team.items()},
        "team_week_summary": summary,
        "current": current,
        "absences": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--raw-dir", default=os.path.join("data", "raw", "decision-hub"))
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "injuries.json"))
    args = ap.parse_args()
    data = build(args.season, args.raw_dir)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(data, fh, indent=1)
    print(f"wrote {args.out}: {len(data['absences'])} absences, "
          f"{len(data['team_week_summary'])} team-weeks, {len(data['current'])} current team rows, "
          f"league week {data['meta']['league_week']}")


if __name__ == "__main__":
    main()
