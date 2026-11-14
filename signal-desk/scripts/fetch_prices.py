#!/usr/bin/env python3
"""Download the opening and closing line files that the price-snapshot store is built from.

Why a separate script
---------------------
The sandbox this repository is developed in can reach ``api.github.com`` but not
``objects.githubusercontent.com`` (the host GitHub release assets redirect to). These two files
are *repository* files, not release assets, so they are fetched through the contents API with
``Accept: application/vnd.github.raw``, which serves them directly and works here.

They are written to ``signal-desk/data/raw/`` which is gitignored: raw upstream files are not
committed, matching the convention already used for ``data/raw/``. The derived artefacts
(``signal-desk/data/price_snapshots.json``) are committed, and every row in them names the file
and commit it came from.

Usage
    python signal-desk/scripts/fetch_prices.py [--check]

``--check`` only reports whether the upstream files are reachable and what they contain; it
writes nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.abspath(os.path.join(HERE, "..", "data", "raw"))
COMMIT = "a270278f3ac4e937295fe6a27814b3c4a2b62645"
FILES = {
    "initial_lines.csv": ("https://api.github.com/repos/nflverse/nfldata/contents/data/"
                          f"initial_lines.csv?ref={COMMIT}",
                          "https://github.com/nflverse/nfldata/blob/" + COMMIT + "/data/initial_lines.csv"),
    "closing_lines.csv": ("https://api.github.com/repos/nflverse/nfldata/contents/data/"
                          f"closing_lines.csv?ref={COMMIT}",
                          "https://github.com/nflverse/nfldata/blob/" + COMMIT + "/data/closing_lines.csv"),
}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github.raw",
        "User-Agent": "signal-desk-fetch/1.0",
    })
    with urllib.request.urlopen(req, timeout=90) as fh:
        return fh.read()


def main() -> int:
    check = "--check" in sys.argv
    os.makedirs(RAW, exist_ok=True)
    manifest = {"commit": COMMIT, "files": []}
    ok = True
    for name, (api, blob) in FILES.items():
        try:
            body = get(api)
        except Exception as exc:            # network failure must be reported, not guessed at
            ok = False
            print(f"  {name}: FETCH FAILED ({exc}) - the price store will report it as not loaded")
            manifest["files"].append({"name": name, "status": "fetch failed", "error": str(exc),
                                      "url": blob})
            continue
        rows = max(0, body.count(b"\n") - 1)
        manifest["files"].append({"name": name, "status": "ok", "bytes": len(body), "rows": rows,
                                  "sha256": hashlib.sha256(body).hexdigest(), "url": blob,
                                  "raw": api})
        print(f"  {name}: {len(body)} bytes, {rows} rows, sha256 {hashlib.sha256(body).hexdigest()[:12]}...")
        if not check:
            with open(os.path.join(RAW, name), "wb") as fh:
                fh.write(body)
    if not check:
        with open(os.path.join(RAW, "manifest.json"), "w") as fh:
            json.dump(manifest, fh, indent=1)
            fh.write("\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
