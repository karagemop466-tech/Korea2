"""Fetch every upstream data file this project uses, verify it, and record provenance.

Design rules
------------
1. Every file is fetched from a *pinned* git commit, never from a moving branch.
2. Every file is hashed (SHA-256) and the hash is written to ``data/PROVENANCE.md``.
3. Nothing is silently transformed here. Transformation happens in
   ``build_features.py`` / ``build_players.py`` so that raw -> derived stays auditable.

Network note
------------
GitHub release assets (``release-assets.githubusercontent.com``) and
``raw.githubusercontent.com`` are not reachable from the build sandbox, so the
canonical ``nflverse-data`` release CSVs cannot be pulled here. The same upstream
feeds are available as *committed* files inside data-only GitHub repositories, which
`codeload.github.com` can serve. That substitution is logged as IR-01 in
COORDINATION.md and on the Flagged-for-Review page.

Usage
-----
    python pipeline/fetch_data.py              # download what is missing
    python pipeline/fetch_data.py --check      # verify hashes only, no download
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CACHE = RAW / "_tarballs"

# repo -> (commit sha, tarball prefix)
#
# SHAs were resolved from https://api.github.com/repos/<repo>/commits?per_page=1 at
# 2026-11-01T13:30Z. Re-pin deliberately, never implicitly.
SOURCES = {
    "nflverse/nfldata": {
        "sha": "a270278f3ac4e937295fe6a27814b3c4a2b62645",
        "date": "2026-11-01T13:05:15Z",
        "files": {
            "data/games.csv": "nfldata_games.csv",
            "data/closing_lines.csv": "nfldata_closing_lines.csv",
            "data/initial_lines.csv": "nfldata_initial_lines.csv",
            "data/win_totals.csv": "nfldata_win_totals.csv",
            "data/teams.csv": "nfldata_teams.csv",
            "data/officials.csv": "nfldata_officials.csv",
            "data/rosters.csv": "nfldata_rosters.csv",
            "DATASETS.md": "nfldata_DATASETS.md",
        },
        "license": "MIT (see upstream repository)",
        "role": "game results, closing spread/total/moneyline prices, rest, roof, weather, officials, rosters",
    },
    "ryurko/nflscrapR-data": {
        "sha": "c9274b9f2baf4d62581ba2cb40f77bd6b8a9c76d",
        "date": "2020-03-02T23:40:31Z",
        "files": {
            "legacy_data/game_player_stats/game_passing_df.csv": "scrapr_game_passing.csv",
            "legacy_data/game_player_stats/game_rushing_df.csv": "scrapr_game_rushing.csv",
            "legacy_data/game_player_stats/game_receiving_df.csv": "scrapr_game_receiving.csv",
        },
        "license": "see upstream repository (data derived from NFL play-by-play)",
        "role": "player-game box statistics 2009-2019 (props layer)",
    },
    "nflverse/nflverse-pfr": {
        "sha": "3ec2fac9e8baecca75cdebaa87260e1c9d39bdbc",
        "date": "2026-11-01T08:15:03Z",
        "files": {
            "data/adv_stats/adv_receiving_season.csv": "pfr_adv_receiving_season.csv",
            "data/adv_stats/adv_passing_season.csv": "pfr_adv_passing_season.csv",
            "data/adv_stats/adv_rushing_season.csv": "pfr_adv_rushing_season.csv",
        },
        "license": "see upstream repository",
        "role": "independent cross-check of player aggregate statistics",
    },
}

CANONICAL_URLS = {
    # where the same feed normally comes from (documented for review, not fetched)
    "player_stats_release": "https://github.com/nflverse/nflverse-data/releases/tag/player_stats",
    "schedules_release": "https://github.com/nflverse/nflverse-data/releases/tag/schedules",
    "pbp_release": "https://github.com/nflverse/nflverse-data/releases/tag/pbp",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  cached {dest.name} ({dest.stat().st_size/1e6:.1f} MB)")
        return
    print(f"  GET {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "korea2-nfl-research/1.0"})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=180) as resp, open(tmp, "wb") as out:
        shutil.copyfileobj(resp, out)
    tmp.rename(dest)
    print(f"  saved {dest.name} ({dest.stat().st_size/1e6:.1f} MB)")


def extract(repo: str, info: dict) -> dict[str, dict]:
    """Download the repo tarball at the pinned SHA and pull out the wanted files."""
    owner, name = repo.split("/")
    tar_path = CACHE / f"{name}-{info['sha'][:12]}.tar.gz"
    url = f"https://codeload.github.com/{owner}/{name}/tar.gz/{info['sha']}"
    download(url, tar_path)

    got: dict[str, dict] = {}
    wanted = info["files"]
    with tarfile.open(tar_path, "r:gz") as tf:
        members = {m.name: m for m in tf.getmembers() if m.isfile()}
        for src, dest_name in wanted.items():
            matches = [n for n in members if n.endswith("/" + src)]
            if not matches:
                raise RuntimeError(f"{repo}: {src} not found at {info['sha']}")
            member = members[matches[0]]
            dest = RAW / dest_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tf.extractfile(member) as fh, open(dest, "wb") as out:
                shutil.copyfileobj(fh, out)
            got[dest_name] = {
                "repo": repo,
                "sha": info["sha"],
                "path": src,
                "url": f"https://github.com/{repo}/blob/{info['sha']}/{src}",
                "codeload": url,
                "bytes": dest.stat().st_size,
                "sha256": sha256(dest),
                "role": info["role"],
                "license": info["license"],
                "commit_date": info["date"],
            }
            print(f"    ok {dest_name} ({dest.stat().st_size/1e6:.2f} MB)")
    return got


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify existing files, do not download")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    manifest_path = RAW / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    if args.check:
        bad = 0
        for name, meta in sorted(manifest.items()):
            p = RAW / name
            if not p.exists():
                print(f"MISSING {name}")
                bad += 1
                continue
            digest = sha256(p)
            if digest != meta["sha256"]:
                print(f"HASH MISMATCH {name}")
                bad += 1
            else:
                print(f"ok {name}")
        print(f"\n{bad} problem(s)")
        return 1 if bad else 0

    for repo, info in SOURCES.items():
        print(f"[{repo}] {info['sha'][:12]}")
        manifest.update(extract(repo, info))

    # Keep the workspace small: tarballs are re-downloadable, the extracted files are hashed.
    for tar in CACHE.glob("*.tar.gz"):
        if tar.stat().st_size > 20_000_000:
            print(f"  pruning cache {tar.name} ({tar.stat().st_size/1e6:.0f} MB)")
            tar.unlink()

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    site_manifest = ROOT / "origination" / "site_data"
    site_manifest.mkdir(parents=True, exist_ok=True)
    (site_manifest / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    write_provenance(manifest)
    print(f"\nwrote {manifest_path.relative_to(ROOT)} and data/PROVENANCE.md")
    return 0


def write_provenance(manifest: dict) -> None:
    lines = [
        "# Data provenance",
        "",
        "Generated by `pipeline/fetch_data.py`. Do not edit by hand.",
        "",
        f"Generated (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "Every upstream file is pinned to a git commit SHA and hashed. "
        "Re-running the pipeline re-verifies both.",
        "",
        "| Local file | Upstream repository | Commit | Upstream path | Bytes | SHA-256 | Used for |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, m in sorted(manifest.items()):
        lines.append(
            f"| `{name}` | [{m['repo']}](https://github.com/{m['repo']}) | "
            f"`{m['sha'][:12]}` | [`{m['path']}`]({m['url']}) | {m['bytes']:,} | "
            f"`{m['sha256'][:16]}…` | {m['role']} |"
        )
    lines += [
        "",
        "## Canonical feeds that could not be fetched here",
        "",
        "The canonical `nflverse-data` release assets are not reachable from the build",
        "sandbox (see IR-01). They are listed so a reviewer can compare like for like:",
        "",
    ]
    for label, url in CANONICAL_URLS.items():
        lines.append(f"- `{label}`: {url}")
    lines += [
        "",
        "## Official league sources used for cross-verification",
        "",
        "NFL.com is the only *official* (league-operated) source used in this project.",
        "It is used for spot verification of scheduled games and final scores, not for bulk",
        "ingestion, because no bulk download endpoint is reachable without a paid feed.",
        "",
        "- https://www.nfl.com/schedules/",
        "- https://www.nfl.com/games/ (individual game pages)",
        "",
    ]
    (ROOT / "data" / "PROVENANCE.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
