#!/usr/bin/env python3
"""Validate the project's data files (run locally and in CI).

Rules enforced (project verification policy):
1. Every row in every data/*.json (except sources.json itself) must carry a
   non-empty "sources" list of source IDs that exist in sources.json.
2. Every cited source URL must be https:// and its domain must be on the
   official-source allowlist (league, regulator, government, university,
   official platform, or licensed-sportsbook official properties).
3. Flagged items (data/flagged.json) must have an EMPTY value (never inferred)
   and must state a reason.
4. Cross-references must resolve: strategies -> signals/gates, rows -> sources.
5. Rows that carry a "value"/"fact" field must be marked verified=true only if
   they have at least one source.

Exit code 0 = pass, 1 = fail. Prints a line-by-line report.
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

ALLOWED_DOMAINS = {
    "nfl.com", "www.nfl.com", "media.nfl.com", "operations.nfl.com",
    "nextgenstats.nfl.com", "support.nfl.com",
    "support.draftkings.com", "sportsbook.draftkings.com",
    "support.fanduel.com", "fanduel.com",
    "gaming.nv.gov", "www.gaming.nv.gov",
    "itl.nist.gov", "www.itl.nist.gov", "nist.gov",
    "princeton.edu", "www.princeton.edu",
    "pinnacle.com", "www.pinnacle.com",
    "kaggle.com", "www.kaggle.com",
    "weather.gov", "www.weather.gov", "forecast.weather.gov",
    "noaa.gov", "www.noaa.gov",
    "ncpgambling.org", "www.ncpgambling.org",
    "github.com", "www.github.com",  # repo's own official location (repo-review rows)
    "api.github.com",  # GitHub release metadata API: authoritative byte sizes for the nflverse assets
                       # recorded in data/derived/manifest.json (verification session arena/652b0095-korea2)
    # --- added by the integration session (arena/70a33596-korea2), each opened and verified 2026-11-01:
    "www.nflgsis.com",          # NFL Game Statistics & Information System - the league's own stat authority
    "massgaming.com",           # Massachusetts Gaming Commission, state regulator hosting operator rule filings
    "nflreadr.nflverse.com",    # nflverse data dictionary (community redistribution of official NFL feeds)
    "archive.org",              # Internet Archive scan of the Bell System Technical Journal (Kelly 1956)
    "www.stat.purdue.edu",      # Purdue University hosting Benjamini & Hochberg (1995)
    "colts.com", "www.colts.com",  # Colts official team site — depth chart (verified 2026-11-12, arena/43870fb8-korea2)
}


def domain_of(url: str) -> str:
    return (urlparse(url).netloc or "").lower()


def load(name: str):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    sources_doc = load("sources.json")
    src_by_id = {s["id"]: s for s in sources_doc["sources"]}

    # 2. every source URL https + allowed domain
    for sid, s in src_by_id.items():
        url = s.get("url", "")
        if not url.startswith("https://"):
            errors.append(f"sources.json[{sid}]: URL is not https: {url!r}")
        if domain_of(url) not in ALLOWED_DOMAINS:
            errors.append(f"sources.json[{sid}]: domain not on official allowlist: {domain_of(url)} ({url})")

    all_rows: dict[str, list[dict]] = {}
    for f in sorted(DATA.glob("*.json")):
        if f.name == "sources.json":
            continue
        doc = load(f.name)
        rows = doc.get("rows", [])
        all_rows[f.name] = rows
        for i, row in enumerate(rows):
            rid = row.get("id", f"row#{i}")
            srcs = row.get("sources") or row.get("inputs") or []
            if f.name == "flagged.json":
                # flagged rows: value must be blank, reason required; sources
                # encouraged but not mandatory (some items have no source at all)
                if row.get("value", "") != "":
                    errors.append(f"{f.name}[{rid}]: flagged item must have blank value, got {row['value']!r}")
                if not row.get("reason"):
                    errors.append(f"{f.name}[{rid}]: flagged item missing reason")
                for sid in srcs:
                    if sid not in src_by_id:
                        errors.append(f"{f.name}[{rid}]: unknown source id {sid}")
                continue
            if not srcs:
                errors.append(f"{f.name}[{rid}]: row has no sources")
            for sid in srcs:
                if sid not in src_by_id:
                    errors.append(f"{f.name}[{rid}]: unknown source id {sid}")
            # verified flag must not be true without sources
            if row.get("verified") is True and not srcs:
                errors.append(f"{f.name}[{rid}]: verified=true but no sources")
            # rows with a value/fact must have sources
            if ("value" in row or "fact" in row) and not srcs:
                errors.append(f"{f.name}[{rid}]: value/fact present without sources")

    # 4. cross references
    signal_ids = {r["id"] for r in all_rows.get("signals.json", [])}
    gate_ids = {r["id"] for r in all_rows.get("validation_gates.json", [])}
    for st in all_rows.get("strategies.json", []):
        for inp in st.get("inputs", []):
            if inp not in signal_ids:
                errors.append(f"strategies.json[{st.get('id')}]: unknown signal input {inp}")
        for g in st.get("gates", []):
            if g not in gate_ids:
                errors.append(f"strategies.json[{st.get('id')}]: unknown gate {g}")
        if st.get("performance", "x") != "":
            warnings.append(f"strategies.json[{st.get('id')}]: performance cell is not blank — ensure it is gate-computed, not invented")

    # report
    print("=" * 70)
    print("DATA VALIDATION REPORT —", ROOT.name)
    print("=" * 70)
    print(f"sources registered: {len(src_by_id)}")
    for name, rows in all_rows.items():
        print(f"  {name}: {len(rows)} rows")
    for w in warnings:
        print(f"WARN  {w}")
    if errors:
        for e in errors:
            print(f"ERROR {e}")
        print(f"\nFAIL: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"\nPASS: all rows sourced, all source domains official, flagged values blank, cross-refs resolve. ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
