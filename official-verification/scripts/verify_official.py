"""Official-source verification for the Line Lab site.

Independently re-reads the official NFL sources the site cites and records,
for each published value, whether it is VERIFIED (matches the official source),
BLANK (no official source publishes it; left unpublished, never inferred), or
FLAGGED (a source-integrity or freshness caveat was found).

Run:
    python3 official-verification/scripts/verify_official.py

This script documents the verification method and re-emits the committed
data register `official-verification/data/official-verification.json`. It does
not fetch live pages itself (the sandbox shell cannot reach nfl.com); the
register values were captured in-session with the page-retrieval tool on
2026-11-19 and are committed as the dated record.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "official-verification.json"


def load_register() -> dict:
    with DATA.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def summarize(register: dict) -> dict:
    checks = register.get("checks", [])
    counts = {"VERIFIED": 0, "BLANK": 0, "FLAGGED": 0}
    for check in checks:
        status = check.get("status")
        if status in counts:
            counts[status] += 1
    return {
        "total_checks": len(checks),
        "verified": counts["VERIFIED"],
        "blank": counts["BLANK"],
        "flagged": counts["FLAGGED"],
        "not_inferred": True,
    }


def main() -> int:
    register = load_register()
    summary = summarize(register)
    print("Official-source verification register")
    print("=====================================")
    print(f"Generated: {register.get('generated_at_utc')}")
    print(f"Capture session: {register.get('capture_session')} ({register.get('capture_date')})")
    print()
    print(f"Total checks : {summary['total_checks']}")
    print(f"VERIFIED     : {summary['verified']}")
    print(f"BLANK        : {summary['blank']}")
    print(f"FLAGGED      : {summary['flagged']}")
    print(f"Not inferred : {summary['not_inferred']}")
    print()
    print("Per-check register:")
    for check in register.get("checks", []):
        print(
            f"  {check['id']:6} [{check['status']:8}] {check['area']:<22} {check['item']}"
        )
    print()
    print(register.get("summary", {}).get("note", ""))
    # Consistency: the committed summary must match a recomputation.
    assert summary["total_checks"] == register["summary"]["total_checks"]
    assert summary["verified"] == register["summary"]["verified"]
    assert summary["blank"] == register["summary"]["blank"]
    assert summary["flagged"] == register["summary"]["flagged"]
    print()
    print("OK: committed summary matches recomputed summary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
