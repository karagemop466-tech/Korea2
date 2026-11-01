"""Standalone smoke test for the published site (runs in CI, no pandas needed)."""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SITE = ROOT / "origination"


def main() -> int:
    files = sorted((SITE / "site_data").glob("*.json"))
    assert files, "origination/site_data is empty"
    for f in files:
        json.loads(f.read_text())
    print(f"{len(files)} JSON artefacts parse")

    pages = sorted([SITE / "index.html", *(SITE / "pages").glob("*.html")])
    assert len(pages) >= 13, f"only {len(pages)} pages"
    for p in pages:
        assert p.stat().st_size > 2000, f"{p} looks empty"
        text = p.read_text()
        assert "<title>" in text and "</body>" in text, f"{p} is not a full page"
    print(f"{len(pages)} pages present, all complete")

    for asset in ("site.css", "site.js"):
        assert (SITE / "assets" / asset).stat().st_size > 500, asset
    print("assets present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
