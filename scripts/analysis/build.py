"""Run the whole project end to end.

    python scripts/analysis/build.py

Produces results/*.json and the static site. Deterministic: no network calls.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import market          # noqa: E402
import strategies      # noqa: E402
import correlations    # noqa: E402
import props           # noqa: E402
import originate       # noqa: E402
import verification     # noqa: E402
import build_site      # noqa: E402

STEPS = [
    ("market efficiency", market.main),
    ("strategy walk-forward + gates", strategies.main),
    ("correlation study", correlations.main),
    ("player props", props.main),
    ("line origination", originate.main),
    ("official verification", verification.main),
    ("render site", build_site.main),
]


def main() -> int:
    t0 = time.time()
    for name, fn in STEPS:
        start = time.time()
        print(f"\n=== {name}")
        fn()
        print(f"    done in {time.time() - start:.1f}s")
    print(f"\nbuild complete in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
