"""Run the whole pipeline in order. Nothing here is interactive."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = ["build_features.py", "build_players.py", "originate.py", "strategies.py",
         "gates.py", "props.py", "correlation.py", "verify.py", "build_site.py"]


def main(steps: list[str] | None = None) -> int:
    for step in steps or STEPS:
        path = HERE / step
        if not path.exists():
            print(f"SKIP {step} (not present)")
            continue
        t0 = time.time()
        print(f"\n=== {step} " + "=" * (60 - len(step)))
        rc = subprocess.call([sys.executable, str(path)], cwd=HERE)
        if rc != 0:
            print(f"FAILED {step} (exit {rc})")
            return rc
        print(f"--- {step} ok in {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
