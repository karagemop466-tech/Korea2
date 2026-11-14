#!/usr/bin/env python3
"""Run the whole Decision Arena pipeline in dependency order.

    python decision-arena/scripts/run_all.py            # build everything and verify
    python decision-arena/scripts/run_all.py --verify   # verify only (no rebuild)

Order matters: origins read the results feed, the strategies read the same features, the
registers the pages render are computed from the built data, so the site is always rendered
last and verified afterwards.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable

STEPS = [
    ("market and origination", ["scripts/build_market.py"]),
    ("strategy competition", ["scripts/build_strategies.py"]),
    ("correlations and parlay pricing", ["scripts/build_correlation.py"]),
    ("injuries and replacement depth", ["scripts/build_depth.py"]),
    ("registers (verification + flags)", ["scripts/verify.py", "--pre-site"]),
    ("pages", ["scripts/build_site.py"]),
    ("unit tests (sign, leakage, statistics)", ["tests/test_arena.py"]),
    ("verification suite", ["scripts/verify.py"]),
]


def main():
    verify_only = "--verify" in sys.argv
    steps = [STEPS[-1]] if verify_only else STEPS
    failed = []
    for name, cmd in steps:
        t0 = time.time()
        print(f"\n=== {name} ===", flush=True)
        r = subprocess.run([PY, cmd[0]] + cmd[1:], cwd=ROOT)
        dt = time.time() - t0
        status = "ok" if r.returncode == 0 else f"FAILED ({r.returncode})"
        print(f"--- {name}: {status} in {dt:.1f}s", flush=True)
        if r.returncode != 0:
            failed.append(name)
            if name in ("verification suite", "unit tests (sign, leakage, statistics)"):
                break
    if failed:
        print(f"\nPIPELINE FAILED: {failed}")
        return 1
    print("\nPIPELINE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
