#!/usr/bin/env python3
"""Fetch the raw datasets used by this project and write a provenance manifest.

Every byte published by this project comes from the extracts listed here.
Nothing is typed in by hand: numbers are computed by scripts from these files.

Network notes (recorded 2026-11-01):
  * The build sandbox has an egress allow-list. github.com / api.github.com /
    codeload.github.com / pypi.org are reachable. objects.githubusercontent.com
    (the GitHub *release asset* CDN, which is where nflverse publishes its data
    releases) is NOT reachable, so the canonical release assets cannot be pulled
    directly here.
  * Mitigation: `nflverse/nfldata` publishes the same `games.csv`,
    `closing_lines.csv`, `initial_lines.csv`, `sc_lines.csv`, `teams.csv`,
    `standings.csv` files inside its **git tree**, which codeload can serve.
  * The player-week extract is a third-party mirror of the nflverse
    `player_stats` schema (2023-2024 only). It is used only for the player-prop
    research layer and is flagged as such on the Flagged for Review page.

Usage: python3 scripts/fetch_data.py [--verify-only]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "manifest.json"

NFLDAT_REPO = "nflverse/nfldata"
NFLDAT_TARBALL = (
    "https://codeload.github.com/nflverse/nfldata/tar.gz/refs/heads/master"
)

# file inside data/raw  <-  path inside the nfldata repo
NFLDAT_FILES = {
    "games.csv": "data/games.csv",
    "closing_lines.csv": "data/closing_lines.csv",
    "initial_lines.csv": "data/initial_lines.csv",
    "sc_lines.csv": "data/sc_lines.csv",
    "teams.csv": "data/teams.csv",
    "standings.csv": "data/standings.csv",
    "win_totals.csv": "data/win_totals.csv",
}

PLAYER_MIRROR = [
    ("player/weekly_stats_2023.csv",
     "https://github.com/kadetownsend4/ML-Betting/blob/main/NFL/weekly_nfl_stats_season/"
     "weekly_stats_2023.csv"),
    ("player/weekly_stats_2024.csv",
     "https://github.com/kadetownsend4/ML-Betting/blob/main/NFL/weekly_nfl_stats_season/"
     "weekly_stats_2024.csv"),
]

# Documented upstream that publishes the canonical versions of these files.
CANONICAL_UPSTREAM = {
    "games.csv": "https://github.com/nflverse/nflverse-data/releases/tag/schedules",
    "closing_lines.csv": "https://github.com/nflverse/nfldata/blob/master/data/closing_lines.csv",
    "initial_lines.csv": "https://github.com/nflverse/nfldata/blob/master/data/initial_lines.csv",
    "sc_lines.csv": "https://github.com/nflverse/nfldata/blob/master/data/sc_lines.csv",
    "teams.csv": "https://github.com/nflverse/nfldata/blob/master/data/teams.csv",
    "standings.csv": "https://github.com/nflverse/nfldata/blob/master/data/standings.csv",
    "win_totals.csv": "https://github.com/nflverse/nfldata/blob/master/data/win_totals.csv",
    "player/weekly_stats_2023.csv":
        "https://github.com/nflverse/nflverse-data/releases/tag/player_stats",
    "player/weekly_stats_2024.csv":
        "https://github.com/nflverse/nflverse-data/releases/tag/player_stats",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_rows(path: Path) -> int:
    with path.open("rb") as fh:
        n = sum(1 for _ in fh)
    return max(n - 1, 0)  # minus header


def gh_api(path: str) -> dict:
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def download_nfldata() -> str:
    """Pull the nfldata git tree and extract the CSVs we need."""
    RAW.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(NFLDAT_TARBALL, headers={"User-Agent": "korea2-build"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        blob = resp.read()
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        members = {m.name: m for m in tf.getmembers()}
        for local, remote in NFLDAT_FILES.items():
            # tarball prefixes with nfldata-master/
            match = [k for k in members if k.endswith("/" + remote)]
            if not match:
                raise SystemExit(f"missing in tarball: {remote}")
            fh = tf.extractfile(members[match[0]])
            (RAW / local).write_bytes(fh.read())
    return hashlib.sha256(blob).hexdigest()


def download_player() -> None:
    (RAW / "player").mkdir(parents=True, exist_ok=True)
    for local, url in PLAYER_MIRROR:
        # https://github.com/<o>/<r>/blob/<branch>/<path...>  ->  /repos/<o>/<r>/contents/<path...>?ref=<branch>
        _, _, _, owner, repo, _, branch, *rest = url.split("/")
        api = f"/repos/{owner}/{repo}/contents/{'/'.join(rest)}?ref={branch}"
        out = subprocess.run(
            ["gh", "api", api, "-H", "Accept: application/vnd.github.raw"],
            capture_output=True, check=True,
        )
        (RAW / local).write_bytes(out.stdout)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()

    tarball_sha = None
    if not args.verify_only:
        print("downloading nflverse/nfldata tree ...", flush=True)
        tarball_sha = download_nfldata()
        print("downloading player-week mirror ...", flush=True)
        download_player()

    commit = gh_api(f"/repos/{NFLDAT_REPO}/commits/master")["sha"]

    files = []
    for local in list(NFLDAT_FILES) + [p for p, _ in PLAYER_MIRROR]:
        path = RAW / local
        if not path.exists():
            raise SystemExit(f"missing raw file {path}; run without --verify-only")
        entry = {
            "file": f"data/raw/{local}",
            "bytes": path.stat().st_size,
            "rows": count_rows(path),
            "sha256": sha256(path),
            "retrieved_utc": datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if local in NFLDAT_FILES:
            entry["retrieved_from"] = (
                f"https://github.com/{NFLDAT_REPO}/blob/{commit}/{NFLDAT_FILES[local]}"
            )
            entry["transport"] = NFLDAT_TARBALL
            entry["pinned_commit"] = commit
        else:
            entry["retrieved_from"] = dict(PLAYER_MIRROR)[local]
            entry["transport"] = "api.github.com contents (raw media type)"
            entry["pinned_commit"] = gh_api("/repos/kadetownsend4/ML-Betting/commits/main")["sha"]
        entry["canonical_upstream"] = CANONICAL_UPSTREAM[local]
        files.append(entry)

    manifest = {
        "generated_utc": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "publisher": {
            "nflverse_nfldata_commit": commit,
            "nflverse_nfldata_tarball_sha256": tarball_sha,
            "nflverse_nfldata_tarball_url": NFLDAT_TARBALL,
        },
        "files": files,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")

    # Provenance cross-check: does games.csv agree with closing_lines.csv?
    import csv

    games = {}
    with (RAW / "games.csv").open() as fh:
        for row in csv.DictReader(fh):
            games[row["game_id"]] = row
    agree = disagree = 0
    examples = []
    with (RAW / "closing_lines.csv").open() as fh:
        for row in csv.DictReader(fh):
            if row["type"] != "SPREAD":
                continue
            g = games.get(row["alt_game_id"])
            if not g or not g["spread_line"]:
                continue
            # closing_lines SPREAD rows are per side; home side line == -spread_line
            home_line = float(row["line"])
            if row["side"] == g["home_team"]:
                if abs(home_line - (-float(g["spread_line"]))) < 1e-9:
                    agree += 1
                else:
                    disagree += 1
                    if len(examples) < 5:
                        examples.append({**row, "games_spread_line": g["spread_line"]})
    manifest["cross_check_spread_vs_closing_lines"] = {
        "agree": agree,
        "disagree": disagree,
        "disagree_examples": examples,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: v for k, v in manifest.items() if k != "files"}, indent=2)[:1200])
    print(f"wrote {MANIFEST} with {len(files)} files")


if __name__ == "__main__":
    main()
