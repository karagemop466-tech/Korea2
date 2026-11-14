#!/usr/bin/env python3
"""DA-1/DA-3/DA-7 inputs: fetch the three upstream feeds this hub needs, with hashes.

Why this is a separate step from the build: GitHub release assets are only reachable from
a normal network (the CI runner). The build itself must stay runnable offline against
whatever is committed, so the fetch is explicit and fail-closed:

  * every download is hashed and recorded in data/inputs/manifest.json;
  * a download that fails or is empty makes the step exit non-zero, so a partial snapshot
    can never be published as if it were complete;
  * the committed files are pruned to the columns the build actually reads, so the
    repository does not grow by tens of megabytes per refresh.

The feeds are third-party redistributors (see data/sources.json). Nothing fetched here is
called official; official NFL.com pages are cited separately per published row.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "inputs")
REL = "https://github.com/nflverse/nflverse-data/releases/download"

# (local name, url, columns to keep when pruning)
FEEDS = [
    (
        "depth_charts.csv.gz",
        f"{REL}/depth_charts/depth_charts_{'{season}'}.csv.gz",
        ["dt", "team", "player_name", "gsis_id", "pos_grp", "pos_name", "pos_abb", "pos_slot", "pos_rank"],
    ),
    (
        "snap_counts.csv.gz",
        f"{REL}/snap_counts/snap_counts_{'{season}'}.csv.gz",
        ["game_type", "season", "week", "player", "pfr_player_id", "position", "team", "opponent",
         "offense_snaps", "offense_pct", "defense_snaps", "defense_pct"],
    ),
    (
        "injuries.csv.gz",
        f"{REL}/injuries/injuries_{'{season}'}.csv.gz",
        ["season", "game_type", "week", "team", "gsis_id", "full_name", "position",
         "report_status", "practice_status", "date_modified"],
    ),
]

# The schedules feed is small and already committed at data/derived/games.csv.gz by the root
# pipeline; it is re-fetched here only to record a fresh hash and row count for the manifest.
SCHEDULES = (f"{REL}/schedules/games.csv", "games.csv.gz", ["game_id", "season", "game_type", "week",
            "gameday", "gametime", "away_team", "home_team", "away_score", "home_score", "location",
            "spread_line", "total_line", "home_moneyline", "away_moneyline", "home_spread_odds",
            "away_spread_odds", "over_odds", "under_odds", "roof", "surface", "temp", "wind"])


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "decision-arena/1.0 (+research)"})
    with urllib.request.urlopen(req, timeout=180) as fh:
        body = fh.read()
    if not body:
        raise RuntimeError(f"empty response from {url}")
    return body


def prune_csv_bytes(body: bytes, keep: list[str]) -> tuple[bytes, int, list[str]]:
    """Keep only `keep` columns; return gzipped bytes, row count and the header actually seen."""
    raw = gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body
    text = raw.decode("utf-8-sig", "replace")   # utf-8-sig strips a BOM; without this the first
    # column is named "\ufeffgame_type" and is silently dropped by the pruning step.
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing = [c for c in keep if c not in header]
    cols = [c for c in keep if c in header]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    rows = 0
    for row in reader:
        writer.writerow({c: row.get(c, "") for c in cols})
        rows += 1
    return gzip.compress(out.getvalue().encode(), 9), rows, missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2026")
    ap.add_argument("--raw", default=RAW, help="directory for the pruned committed extracts")
    args = ap.parse_args()

    os.makedirs(args.raw, exist_ok=True)
    manifest = {
        "generated_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": args.season,
        "publisher": "nflverse-data releases (third party; not the league)",
        "note": ("Pruned to the columns the build reads. Raw downloads are never committed. "
                 "Each sha256 is of the pruned file as committed, and raw_sha256 is of the "
                 "unpruned download, so either can be re-checked."),
        "files": [],
    }
    problems: list[str] = []
    feeds = [(name, url.replace("{season}", args.season), keep) for name, url, keep in FEEDS]
    feeds.append(("games.csv.gz", SCHEDULES[0], SCHEDULES[2]))

    for name, url, keep in feeds:
        try:
            raw = get(url)
        except Exception as exc:  # fail-closed, and say exactly which feed failed
            problems.append(f"{name}: {exc}")
            continue
        try:
            pruned, rows, missing = prune_csv_bytes(raw, keep)
        except Exception as exc:
            problems.append(f"{name}: could not parse ({exc})")
            continue
        path = os.path.join(args.raw, name)
        with open(path, "wb") as fh:
            fh.write(pruned)
        entry = {
            "name": name,
            "url": url,
            "rows": rows,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "sha256": hashlib.sha256(pruned).hexdigest(),
            "bytes": len(pruned),
        }
        if missing:
            entry["columns_absent_upstream"] = missing
            # Some columns are optional (weather, odds); others the build cannot run without.
            required = {"game_type", "season", "week", "team", "position"}
            fatal = sorted(required & set(missing))
            if fatal:
                problems.append(f"{name}: required column(s) absent upstream: {fatal}")
                os.remove(path)
                continue
        manifest["files"].append(entry)
        print(f"  {name:24s} rows={rows:7d}  -> {len(pruned)/1024:.0f} KiB")

    with open(os.path.join(args.raw, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1, sort_keys=False)
        fh.write("\n")

    if problems:
        print("FETCH FAILED (fail-closed, nothing published):", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"fetched {len(manifest['files'])} feeds for season {args.season}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
