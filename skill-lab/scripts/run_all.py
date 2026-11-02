#!/usr/bin/env python3
"""Deterministic end-to-end build pipeline for Skill Lab.

Runs every analytical stage in strict dependency order, regenerates all 12 HTML
pages, removes transient prediction caches, and runs verify_all.py.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
CACHE_FILE = SCRIPTS_DIR.parent / "data" / "_predictions_cache.json"

PIPELINE = [
    "originate.py",
    "signals_and_luck.py",
    "correlations.py",
    "strategies.py",
    "repo_audit.py",
    "build_site.py",
]


def main() -> int:
    try:
        for script in PIPELINE:
            print(f"[skill-lab] running {script} ...")
            subprocess.run([sys.executable, str(SCRIPTS_DIR / script)], check=True)
    finally:
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
            print(f"[skill-lab] cleaned transient {CACHE_FILE.name}")

    print("[skill-lab] running verify_all.py ...")
    subprocess.run([sys.executable, str(SCRIPTS_DIR / "verify_all.py")], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
