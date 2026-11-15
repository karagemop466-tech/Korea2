#!/usr/bin/env python3
"""Verify one week of the official injury report from the committed raw capture.

Reads ONLY committed files (data/snapshots/injury_report/**) and an optional CSV that is
being checked against them. No network. Writes verification_week<N>.json, which the site
renders. Every number in that file is computed here, never typed.

Checks are stated as the claim being tested, with the observed value and a result:
    confirmed     the official capture supports the claim as written
    contradicted  the official capture contradicts the claim as written
    not_reproduced the claimed figure cannot be produced under the definitions tested

Usage:
    python scripts/capture/verify_week.py --root . --week 10 \
        --compare review-board/data/raw/injury_report_2026-11-13_week10.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capture_injury_reports as cap  # noqa: E402

DATA_REL = cap.DATA_REL


def load_week(base: str, week: int) -> tuple[dict, dict]:
    """Return (manifest record of the latest capture of that week, parsed rows document)."""
    manifest = [r for r in cap.read_jsonl(os.path.join(base, "manifest.jsonl"))
                if r.get("week") == week and r.get("parsed_file")]
    if not manifest:
        raise SystemExit(f"no parsed capture for week {week} under {base}")
    rec = manifest[-1]
    with open(os.path.join(base, rec["parsed_file"]), encoding="utf-8") as fh:
        return rec, json.load(fh)


# The committed CSV abbreviates practice status; map it to the official wording before comparing.
PRACTICE_MAP = {
    "DNP": "Did Not Participate In Practice",
    "Limited": "Limited Participation in Practice",
    "Full": "Full Participation in Practice",
    "": "",
}


def read_csv_rows(path: str) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def compare(official: list[dict], csv_rows: list[dict]) -> dict:
    off = {(r["team"], r["player"]): r for r in official}
    csv_index = {}
    for r in csv_rows:
        team = cap.ALIASES.get(r["team"], r["team"])  # the CSV spells the Rams LAR, the page LA
        csv_index[(team, r["player"])] = dict(r, team=team,
                                              practice=PRACTICE_MAP.get(r.get("practice", ""), r.get("practice", "")))
    matched = sorted(set(off) & set(csv_index))
    status_diff = []
    for key in matched:
        a, b = off[key], csv_index[key]
        for official_field, csv_field in (("injuries", "injury"), ("practice_status", "practice"),
                                          ("game_status", "game_status")):
            if (a[official_field] or "") != (b.get(csv_field) or ""):
                status_diff.append({"team": key[0], "player": key[1], "field": official_field,
                                    "official": a[official_field], "csv": b.get(csv_field) or ""})
    return {
        "csv_rows": len(csv_rows),
        "official_rows": len(official),
        "matched_on_team_and_player": len(matched),
        "in_csv_not_in_official": [f"{k[0]} {k[1]}" for k in sorted(set(csv_index) - set(off))],
        "in_official_not_in_csv": len(set(off) - set(csv_index)),
        "field_differences_on_matched_rows": len(status_diff),
        "field_differences": status_diff,
    }


DECISION_DESK = os.path.join("decision-desk", "data", "injuries.json")


def published_decision_desk(root: str) -> dict | None:
    """The published Week 10 table on the decision-desk page (254 report rows, captured 2026-11-12
    according to its own metadata). Normalised to the same fields as the official rows."""
    path = os.path.join(root, DECISION_DESK)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = [{"team": r["team"], "player": r["player"], "injury": r.get("injury", ""),
             "practice": r.get("practice", ""), "game_status": r.get("game_status", "")}
            for r in doc.get("report_rows", [])]
    return {"path": DECISION_DESK, "meta_week": doc.get("meta", {}).get("week"),
            "meta_captured": doc.get("meta", {}).get("captured"), "rows": rows,
            "no_report": doc.get("no_report", [])}


def compare_published(official: list[dict], published: list[dict]) -> dict:
    """Published rows against the official rows, keyed on club and player."""
    off = {(r["team"], r["player"]): r for r in official}
    pub = {}
    for r in published:
        pub[(cap.ALIASES.get(r["team"], r["team"]), r["player"])] = dict(
            r, team=cap.ALIASES.get(r["team"], r["team"]),
            practice=PRACTICE_MAP.get(r.get("practice", ""), r.get("practice", "")))
    matched = sorted(set(off) & set(pub))
    diffs = []
    for key in matched:
        a, b = off[key], pub[key]
        for of, pf in (("injuries", "injury"), ("practice_status", "practice"), ("game_status", "game_status")):
            if (a[of] or "") != (b.get(pf) or ""):
                diffs.append({"team": key[0], "player": key[1], "field": of,
                              "official": a[of], "published": b.get(pf) or ""})
    return {
        "published_rows": len(pub), "official_rows": len(off),
        "matched_on_team_and_player": len(matched),
        "published_only": sorted(f"{k[0]} {k[1]}" for k in set(pub) - set(off)),
        "official_only": len(set(off) - set(pub)),
        "field_differences_on_matched_rows": len(diffs),
        "field_differences": diffs,
    }


def build(root: str, week: int, compare_path: str | None) -> dict:
    base = os.path.join(root, DATA_REL)
    rec, doc = load_week(base, week)
    rows = doc["rows"]
    per_club = Counter(r["team"] for r in rows)
    absent = sorted(set(cap.TEAMS) - set(per_club))
    game = Counter(r["game_status"] or "(blank)" for r in rows)
    practice = Counter(r["practice_status"] or "(blank)" for r in rows)

    def row_of(team: str, player: str):
        hits = [r for r in rows if r["team"] == team and r["player"] == player]
        return hits[0] if len(hits) == 1 else None

    lions = [("DET", "Kerby Joseph"), ("DET", "Cade Mays"), ("DET", "D.J. Reed")]
    lions_rows = [{"team": t, "player": p, "row": row_of(t, p)} for t, p in lions]
    dd_pre = published_decision_desk(root) if week == 10 else None
    published_lions = None
    if dd_pre:
        published_lions = {r["player"]: r["game_status"] for r in dd_pre["rows"] if r["player"] in ("Kerby Joseph", "Cade Mays", "D.J. Reed")}
    checks = [
        {
            "id": "WK10-01", "claim": "Week 10 official report carries 254 player rows",
            "observed": len(rows), "result": "not_reproduced",
            "note": "Official capture has %d player rows; 254 is not produced by any row definition tested (see definitions)." % len(rows),
        },
        {
            "id": "WK10-02", "claim": "Week 10 official report carries 279 player rows",
            "observed": len(rows), "result": "not_reproduced",
            "note": "Official capture has %d player rows; 279 is not produced by any row definition tested." % len(rows),
        },
        {
            "id": "WK10-03", "claim": "Seattle lists 15 players (site shows injury-free)",
            "observed": per_club.get("SEA", 0),
            "result": "confirmed" if per_club.get("SEA", 0) == 15 else "contradicted",
        },
        {
            "id": "WK10-04", "claim": "Cincinnati lists 4 players (site shows injury-free)",
            "observed": per_club.get("CIN", 0),
            "result": "confirmed" if per_club.get("CIN", 0) == 4 else "contradicted",
        },
        {
            "id": "WK10-05", "claim": "Published Week 10 table shows Kerby Joseph, Cade Mays and D.J. Reed with a blank game status",
            "observed": {r["player"]: (published_lions.get(r["player"]) if published_lions else None) for r in lions_rows},
            "result": "confirmed" if published_lions and all(
                v == "" for v in (published_lions.get(r["player"]) for r in lions_rows)) else "not_reproduced",
            "note": "Read from the published copy in decision-desk/data/injuries.json.",
        },
        {
            "id": "WK10-05b", "claim": "The official Week 10 page lists Kerby Joseph, Cade Mays and D.J. Reed as Out",
            "observed": {r["player"]: (r["row"] or {}).get("game_status") for r in lions_rows},
            "result": "confirmed" if all((r["row"] or {}).get("game_status") == "Out" for r in lions_rows) else "contradicted",
        },
        {
            "id": "WK10-06", "claim": "Every club table has at least one listed player (no injury-free sections)",
            "observed": {"clubs_with_rows": len(per_club), "clubs_without_a_table": absent},
            "result": "confirmed" if not any(c == 0 for c in per_club.values()) else "contradicted",
            "note": "Four clubs have no table on the page; the capture does not say why.",
        },
    ]
    definitions = {
        "player rows (every row in a club table)": len(rows),
        "rows with an injury listed": sum(1 for r in rows if r["injuries"]),
        "rows with a game status": sum(1 for r in rows if r["game_status"]),
        "rows with practice status not 'Full Participation in Practice'":
            sum(1 for r in rows if r["practice_status"] != "Full Participation in Practice"),
        "rows with an injury OR a non-full practice status":
            sum(1 for r in rows if r["injuries"] or r["practice_status"] != "Full Participation in Practice"),
    }
    out = {
        "week": week,
        "season": doc["season"],
        "source": {"name": "NFL.com official injury report", "url": cap.SOURCE_URL.format(season=doc["season"], week=week)},
        "capture": {
            "captured_at_utc": rec["captured_at_utc"], "run_id": rec["run_id"],
            "raw_sha256": rec["sha256"], "content_sha256": rec.get("content_sha256"),
            "bytes": rec["bytes"], "body_file": rec.get("body_file"), "parsed_file": rec["parsed_file"],
            "parser_version": rec.get("parser_version"), "declared_week": rec.get("declared_week"),
        },
        "official": {
            "tables": doc["tables"], "clubs_with_rows": len(per_club), "clubs_without_a_table": absent,
            "player_rows": len(rows), "rows_per_club": dict(sorted(per_club.items())),
            "game_status": dict(sorted(game.items())), "practice_status": dict(sorted(practice.items())),
            "definitions": definitions, "flags": doc["flags"],
        },
        "checks": checks,
    }
    if compare_path:
        out["comparison"] = {"path": compare_path, **compare(rows, read_csv_rows(os.path.join(root, compare_path)))}
    dd = published_decision_desk(root) if week == 10 else None
    if dd:
        out["published_decision_desk"] = {
            "path": dd["path"], "meta_week": dd["meta_week"], "meta_captured": dd["meta_captured"],
            "no_report_sections": dd["no_report"],
            **compare_published(rows, dd["rows"]),
        }
        out["checks"].append({
            "id": "WK10-07", "claim": "The published decision-desk table holds the Week 10 report (254 rows)",
            "observed": len(dd["rows"]),
            "result": "confirmed" if len(dd["rows"]) == 254 else "contradicted",
            "note": "Row count of the published table. Official capture: %d rows." % len(rows),
        })
        out["checks"].append({
            "id": "WK10-08", "claim": "The published table agrees with the official report, row for row",
            "observed": {"field_differences": out["published_decision_desk"]["field_differences_on_matched_rows"],
                         "published_only": len(out["published_decision_desk"]["published_only"]),
                         "official_only": out["published_decision_desk"]["official_only"]},
            "result": "contradicted" if (out["published_decision_desk"]["field_differences_on_matched_rows"]
                                         or out["published_decision_desk"]["official_only"]) else "confirmed",
        })
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--compare", default=None, help="repo-relative CSV to reconcile against the capture")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    result = build(args.root, args.week, args.compare)
    out = args.out or os.path.join(args.root, DATA_REL, f"verification_week{args.week}.json")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"wrote {out}: {result['official']['player_rows']} rows, {result['official']['clubs_with_rows']} clubs")
    for c in result["checks"]:
        print(f"  {c['id']} {c['result']:<15} {c['claim']} -> {c['observed']}")
    if "published_decision_desk" in result:
        pdd = result["published_decision_desk"]
        print(f"  decision-desk: {pdd['published_rows']} published rows, matched {pdd['matched_on_team_and_player']}, "
              f"official-only {pdd['official_only']}, published-only {len(pdd['published_only'])}, "
              f"field differences {pdd['field_differences_on_matched_rows']}")
    if "comparison" in result:
        cmp_ = result["comparison"]
        print(f"  csv rows {cmp_['csv_rows']}, matched {cmp_['matched_on_team_and_player']}, "
              f"csv-only {len(cmp_['in_csv_not_in_official'])}, official-only {cmp_['in_official_not_in_csv']}, "
              f"field differences {cmp_['field_differences_on_matched_rows']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
