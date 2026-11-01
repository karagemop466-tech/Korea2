#!/usr/bin/env python3
"""Download the official NFL feed redistributed by nflverse, and record provenance.

Why this script exists: this repository must be reproducible from committed code and a committed
manifest. The sandbox shell used by the authoring session cannot reach GitHub release assets
(they redirect to objects.githubusercontent.com), so the download runs on GitHub-hosted runners.

Source of truth for the data itself is the NFL's own stats/play-by-play feed, redistributed by the
nflverse project:  https://github.com/nflverse/nflverse-data
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

RELEASE_BASE = "https://github.com/nflverse/nflverse-data/releases/download"
RAW_DIR = os.path.join("data", "raw")
DERIVED_DIR = os.path.join("data", "derived")
API_REPO = "https://api.github.com/repos/nflverse/nflverse-data/releases/tags/"

# 2012-2026 gives 14 completed seasons plus the in-progress current season, which is enough to
# estimate outcome correlations and to walk-forward test signals while keeping downloads small.
PLAYER_TEAM_SEASONS = list(range(2012, 2027))


def assets() -> list[dict]:
    out = [
        {
            "name": "games.parquet",
            "tag": "schedules",
            "url": f"{RELEASE_BASE}/schedules/games.parquet",
            "desc": "Game-level results and pregame market lines, 1999-present",
        }
    ]
    for s in PLAYER_TEAM_SEASONS:
        out.append(
            {
                "name": f"stats_player_week_{s}.parquet",
                "tag": "stats_player",
                "url": f"{RELEASE_BASE}/stats_player/stats_player_week_{s}.parquet",
                "desc": f"Player box score by week, {s}",
            }
        )
        out.append(
            {
                "name": f"stats_team_week_{s}.parquet",
                "tag": "stats_team",
                "url": f"{RELEASE_BASE}/stats_team/stats_team_week_{s}.parquet",
                "desc": f"Team box score by week, {s}",
            }
        )
    return out


def release_meta(tag: str) -> dict:
    try:
        req = urllib.request.Request(API_REPO + tag, headers={"User-Agent": "line-lab"})
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.load(r)
        return {"tag": tag, "updated_at": d.get("updated_at"), "html_url": d.get("html_url")}
    except Exception as exc:  # noqa: BLE001
        return {"tag": tag, "error": repr(exc)}


def download(url: str, dest: str) -> dict:
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        with open(dest, "rb") as fh:
            blob = fh.read()
        return {"status": "cached", "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}
    req = urllib.request.Request(url, headers={"User-Agent": "line-lab"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as fh:
        status = r.status
        fh.write(r.read())
    with open(dest, "rb") as fh:
        blob = fh.read()
    return {"status": status, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}


def main() -> int:
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(DERIVED_DIR, exist_ok=True)
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_repository": "https://github.com/nflverse/nflverse-data",
        "source_description": (
            "nflverse redistributes the NFL's official play-by-play and box score feeds; "
            "game-level market lines in games.parquet are third-party (sportsbook-derived) and are "
            "not an official sportsbook archive."
        ),
        "downloads": [],
        "releases": {},
    }
    failures = 0
    for a in assets():
        dest = os.path.join(RAW_DIR, a["name"])
        try:
            meta = download(a["url"], dest)
        except Exception as exc:  # noqa: BLE001
            meta = {"status": "error", "error": repr(exc)}
            failures += 1
        manifest["downloads"].append({**a, **meta})
        print(f"{a['name']}: {meta.get('status')} {meta.get('bytes', '')}", flush=True)
        if a["tag"] not in manifest["releases"]:
            manifest["releases"][a["tag"]] = release_meta(a["tag"])
    manifest["failed_downloads"] = failures
    with open(os.path.join(DERIVED_DIR, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"failed_downloads={failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
