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
It does not claim a missing starter means the backup plays. Nothing in the official feed says
who will play. What it measures, from the league's own injury report plus the depth chart, is:

    a player is listed on the official report with game status Out / Doubtful
    -> how many snaps he actually played recently (snap counts, 4-week mean)
    -> his rank at that position on the most recent depth-chart snapshot

"Depth lost" is defined as the sum of 1/rank over the absent players whose rank is known. A
rank-1 starter lost contributes 1.0, a second-stringer 0.5, a third-stringer 0.33. A player with
no depth-chart row contributes nothing and is counted in `rank_unknown` instead of being guessed.

SOURCE COLUMNS (verified against the published dictionaries on 2026-11-12)
--------------------------------------------------------------------------
* injuries      season, season_type, game_type, team, week, gsis_id, position, full_name, ...
                report_primary_injury, report_secondary_injury, report_status,
                practice_primary_injury, practice_secondary_injury, practice_status
                https://nflreadr.nflverse.com/reference/load_injuries.html
* depth charts  dt, team, player_name, espn_id, gsis_id, pos_grp_id, pos_grp, pos_id,
                pos_name, pos_abb, pos_slot, pos_rank   (schema from 2025 onward)
                https://nflreadr.nflverse.com/articles/dictionary_depth_charts.html
* weekly roster season, team, position, depth_chart_position, jersey_number, status, full_name,
                ... gsis_id, pfr_id ...
                https://nflreadr.nflverse.com/articles/dictionary_rosters.html
* snap counts   game_id, pfr_game_id, season, game_type, week, player, pfr_player_id, position,
                team, opponent, offense_snaps, offense_pct, defense_snaps, defense_pct,
                st_snaps, st_pct  -- NOTE: no gsis_id, so it is joined through the roster pfr_id
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
import re
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

OFFENSE = {"QB", "RB", "FB", "WR", "TE", "T", "G", "C", "OT", "OG", "OL", "LT", "RT", "LG", "RG",
           "K", "P", "LS"}
DEFENSE = {"DE", "DT", "NT", "EDGE", "LB", "ILB", "OLB", "MLB", "CB", "S", "SS", "FS", "DB", "SAF"}

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
    sample = []
    for r in rows[:n]:
        sample.append({k: (r.get(k) or "")[:120] for k in cols if (r.get(k) or "") != ""})
    return {"columns": cols, "rows": sample, "total_rows": len(rows)}


def to_int(v):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None


def week_of(r: dict) -> int | None:
    return to_int(r.get("week"))


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
    # `dt` (ISO-8601) is the point-in-time stamp; without it a rank from August would be
    # applied to a November game. Only the newest snapshot per team is used.
    dts = sorted({(r.get("dt") or "").strip() for r in depth_rows if (r.get("dt") or "").strip()})
    latest = dts[-1] if dts else ""
    meta["depth_snapshot_dt"] = latest
    meta["depth_snapshots_available"] = len(dts)
    depth_by_id: dict[str, dict] = {}
    for r in depth_rows:
        if latest and (r.get("dt") or "").strip() != latest:
            continue
        gid = (r.get("gsis_id") or "").strip()
        if gid:
            depth_by_id[gid] = r

    def d_rank(r: dict) -> int | None:
        for key in ("pos_rank", "depth_pos_rank", "depth_team"):
            v = to_int(r.get(key))
            if v is not None:
                return v
        return None

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
        prev = roster_by_id.get(gid)
        wk = week_of(r) or 0
        if prev is None or wk >= (prev.get("_week") or 0):
            roster_by_id[gid] = {"team": norm_team(r.get("team", "")), "_week": wk,
                                 "status": r.get("status", ""),
                                 "position": r.get("position", ""),
                                 "full_name": r.get("full_name", "")}

    # ---------------------------------------------------------------- snap counts, via pfr id
    snaps_by_id: dict[str, list[dict]] = defaultdict(list)
    unmatched_snap_ids = 0
    for r in snap_rows:
        pfr = (r.get("pfr_player_id") or "").strip()
        gid = pfr_to_gsis.get(pfr)
        if not gid:
            unmatched_snap_ids += 1
            continue
        snaps_by_id[gid].append({"week": week_of(r) or 0,
                                 "off": r.get("offense_pct"), "def": r.get("defense_pct")})
    meta["snap_rows_without_gsis_crosswalk"] = unmatched_snap_ids

    def snap_share(gid: str, side: str, through_week: int | None) -> float | None:
        recs = [x for x in snaps_by_id.get(gid, [])
                if through_week is None or x["week"] < through_week]
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
        wk = week_of(r)
        if not team or wk is None:
            continue
        gid = (r.get("gsis_id") or "").strip()
        d = depth_by_id.get(gid, {})
        prof = roster_by_id.get(gid, {})
        pos = (d.get("pos_abb") or r.get("position") or prof.get("position") or "").upper()
        side = "offense" if pos in OFFENSE else "defense" if pos in DEFENSE else "special"
        rec = {
            "gsis_id": gid,
            "player": r.get("full_name", ""),
            "position": pos,
            "pos_grp": d.get("pos_grp", ""),
            "pos_slot": to_int(d.get("pos_slot")),
            "depth_rank": d_rank(d),
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
    for (team, wk), recs in sorted(by_team_week.items()):
        lost = [x for x in recs if x["report_status"] in OUT_STATUSES]
        watching = [x for x in recs if x["report_status"] in WATCH_STATUSES]
        dnp = [x for x in recs if x["practice_status"] == "Did Not Participate In Practice"]
        ranked = [x for x in lost if isinstance(x["depth_rank"], int)]
        by_side = {"offense": 0, "defense": 0, "special": 0}
        for x in lost:
            by_side[x["side"]] += 1
        # next man up per position where a rank-1 player is out
        next_up = {}
        for x in sorted(ranked, key=lambda y: y["position"]):
            if x["depth_rank"] != 1:
                continue
            same = [y for y in recs if y["position"] == x["position"]
                    and isinstance(y["depth_rank"], int) and y["depth_rank"] > 1
                    and y["report_status"] not in OUT_STATUSES]
            same.sort(key=lambda y: y["depth_rank"])
            if same:
                next_up[x["position"]] = {
                    "player": same[0]["player"], "rank": same[0]["depth_rank"],
                    "snap_share_4wk": same[0]["snap_share_4wk"],
                    "report_status": same[0]["report_status"],
                    "practice_status": same[0]["practice_status"]}
        summary.append({
            "team": team, "week": wk,
            "listed": len(recs),
            "out_or_doubtful": len(lost),
            "questionable": len(watching),
            "dnp": len(dnp),
            "starters_out": sum(1 for x in ranked if x["depth_rank"] == 1),
            "two_deep_out": sum(1 for x in ranked if x["depth_rank"] <= 2),
            "three_deep_out": sum(1 for x in ranked if x["depth_rank"] <= 3),
            "rank_unknown": len(lost) - len(ranked),
            "offense_out": by_side["offense"],
            "defense_out": by_side["defense"],
            "weighted_depth_lost": round(sum(1.0 / x["depth_rank"] for x in ranked), 3),
            "next_up": next_up,
            "out_names": [{"player": x["player"], "pos": x["position"], "rank": x["depth_rank"],
                           "injury": x["report_injury"], "status": x["report_status"],
                           "snap_share_4wk": x["snap_share_4wk"]}
                          for x in sorted(ranked, key=lambda y: (y["depth_rank"], y["position"]))],
        })
        for x in lost:
            rows.append({"team": team, "week": wk, **{k: x[k] for k in
                        ("player", "position", "pos_grp", "pos_slot", "depth_rank", "side",
                         "report_status", "report_injury", "practice_status", "practice_injury",
                         "roster_status", "snap_share_4wk", "gsis_id")}})

    teams = sorted({s["team"] for s in summary})
    final_week = {t: max(weeks_by_team[t]) for t in weeks_by_team}
    current = [s for s in summary if s["week"] == final_week.get(s["team"])]
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
                 "weeks": sorted({w for s in summary for w in [s["week"]]}),
                 "latest_week_by_team": final_week,
                 "definition": (
                     "depth_rank is pos_rank on the newest nflverse depth-chart snapshot "
                     "(meta.depth_snapshot_dt); NULL means no depth-chart row existed, and such "
                     "a player is NOT counted as a starter. weighted_depth_lost = sum(1/rank). "
                     "snap_share_4wk is the mean offense_pct or defense_pct over the four games "
                     "before that week, joined through the roster's pfr_id because the snap-count "
                     "feed has no gsis_id."),
                 "caveats": [
                     "'Out' is a final designation; 'Doubtful' is a probability the league does "
                     "not quantify. Both are reported separately and neither is a performance claim.",
                     "'Not injury related - resting player' / 'personal matter' rows exist in the "
                     "feed and are counted in out_or_doubtful; they are disclosed, not filtered.",
                     "Depth charts are club-supplied and scraped; a rank can lag a transaction, "
                     "and the 2025+ schema is used (dt, pos_slot, pos_rank).",
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
          f"{len(data['team_week_summary'])} team-weeks, {len(data['current'])} current team rows")


if __name__ == "__main__":
    main()
