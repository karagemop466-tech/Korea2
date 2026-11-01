#!/usr/bin/env python3
"""Rebuild every derived artefact and the static site, in dependency order.

    python3 scripts/build_all.py            # data + site
    python3 scripts/build_all.py --site     # site only (uses cached derived data)

Inputs are the hashed raw extracts described in data/manifest.json (fetch them with
scripts/fetch_data.py). Outputs are data/derived/*.json and the site in origination-lab/*.html.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    "build_integrity.py",
    "build_lines.py",
    "build_signals.py",
    "build_strategies.py",
    "build_props.py",
    "build_correlations.py",
    "build_luck.py",
    "build_site.py",
    "check_links.py",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", action="store_true")
    ap.add_argument("--skip-links", action="store_true")
    args = ap.parse_args()
    steps = ["build_site.py"] + ([] if args.skip_links else ["check_links.py"]) \
        if args.site else STEPS
    for step in steps:
        if args.skip_links and step == "check_links.py":
            continue
        t0 = time.time()
        print(f"\n=== {step} " + "=" * (46 - len(step)), flush=True)
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / step)], cwd=ROOT)
        if r.returncode != 0:
            raise SystemExit(f"{step} failed with exit code {r.returncode}")
        print(f"    ok in {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
