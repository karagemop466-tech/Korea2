#!/usr/bin/env python3
"""LL-9: Comprehensive self-verification & CI audit gate for Lineup Lab.

Checks:
  1. Strict JSON parsing (rejects NaN/Infinity/-Infinity) across lineup-lab/data/*.json.
  2. Source ID referential integrity against lineup-lab/data/sources.json.
  3. 32/32 official standings reconciliation (2020, 2025, 2026 Wk 9).
  4. Zero-imputation guards (blank prop ROI, blank Wk 10 odds, blank Def/OL snap dropoffs).
  5. Complete 12-page HTML build integrity, nav completeness, internal link validity.
  6. Zero errors and zero primary-publisher flags via audit/check_site.py scoped to lineup-lab/.
"""
from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

sys.path.insert(0, str(C.REPO_ROOT / "audit"))
import check_site as AUDIT  # type: ignore


REQUIRED_PAGES = [
    "index.html",
    "pages/executive.html",
    "pages/lines.html",
    "pages/props.html",
    "pages/correlation.html",
    "pages/strategies.html",
    "pages/leaderboard.html",
    "pages/luck.html",
    "pages/injuries-depth.html",
    "pages/suggestions.html",
    "pages/decision-questions.html",
    "pages/verification.html",
]


class TableCellChecker(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_tbody = False
        self.in_tr = False
        self.in_td = False
        self.row_cells: list[bool] = []
        self.rows_missing_last_link: list[int] = []
        self.title = ""
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "tbody":
            self.in_tbody = True
        elif tag == "tr" and self.in_tbody:
            self.in_tr = True
            self.row_cells = []
        elif tag == "td" and self.in_tr:
            self.in_td = True
            self.row_cells.append(False)
        elif tag == "a" and self.in_td and a.get("href"):
            self.row_cells[-1] = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        elif tag == "tbody":
            self.in_tbody = False
        elif tag == "td" and self.in_td:
            self.in_td = False
        elif tag == "tr" and self.in_tr:
            self.in_tr = False
            if self.row_cells and not self.row_cells[-1]:
                self.rows_missing_last_link.append(self.getpos()[0])

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data


def main() -> int:
    errors: list[str] = []

    # 1 & 2. Strict JSON + source registry
    sources_path = C.DATA_DIR / "sources.json"
    sources_doc = C.load_strict_json(sources_path)
    src_ids = {s["id"] for s in sources_doc["sources"]}
    for s in sources_doc["sources"]:
        if not s["url"].startswith("https://"):
            errors.append(f"sources.json: {s['id']} non-HTTPS URL {s['url']}")

    def check_src_refs(obj, fname: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("sources", "source_ids", "inputs") and isinstance(v, list):
                    for item in v:
                        if isinstance(item, str) and item not in src_ids:
                            errors.append(f"{fname}: unknown source ID {item!r}")
                else:
                    check_src_refs(v, fname)
        elif isinstance(obj, list):
            for x in obj:
                check_src_refs(x, fname)

    json_files = sorted(C.DATA_DIR.glob("*.json"))
    if len(json_files) < 14:
        errors.append(f"Expected >= 14 JSON files in lineup-lab/data, found {len(json_files)}")
    for p in json_files:
        doc = C.load_strict_json(p)
        if p.name != "sources.json":
            check_src_refs(doc, p.name)

    # 3. Official 32/32 standings reconciliation
    rec = C.load_strict_json(C.DATA_DIR / "official_reconciliation.json")["meta"]["summary"]
    for yr_key in ("teams_2020_matched", "teams_2025_matched", "teams_2026_w9_matched"):
        if rec[yr_key] != 32:
            errors.append(f"official_reconciliation.json: {yr_key}={rec[yr_key]} != 32")

    # 4. Zero-imputation & schema guards
    strats = C.load_strict_json(C.DATA_DIR / "strategies.json")
    if strats["meta"]["total_evaluated"] != 8 or strats["meta"]["approved_count"] != 0:
        errors.append(f"Unexpected strategy evaluation summary: {strats['meta']}")
    sigs = C.load_strict_json(C.DATA_DIR / "signals.json")
    for row in sigs["prop_calibration"]:
        if row["historical_prop_closing_line"] != "" or row["historical_prop_roi"] != "":
            errors.append(f"signals.json: prop line/ROI must remain blank (FL-01): {row['market']}")
    orig = C.load_strict_json(C.DATA_DIR / "origination.json")
    if len(orig["week10_slate"]) != 14:
        errors.append(f"origination.json: expected 14 Week 10 games, got {len(orig['week10_slate'])}")
    for row in orig["week10_slate"]:
        if row["market_spread_home"] != "" or row["market_odds"] != "":
            errors.append(f"origination.json: Week 10 market odds must remain blank: {row['game_id']}")
    inj = C.load_strict_json(C.DATA_DIR / "injuries_depth.json")
    if inj["def_ol_extract_audit"]["historical_def_snap_dropoff"] != "":
        errors.append("injuries_depth.json: historical_def_snap_dropoff must be blank (FL-04)")
    clubs = {r["team"] for r in inj["live_week10"]["club_depth_audit"]}
    if clubs != {"NE", "IND", "WAS", "MIA", "SEA", "BAL", "LA", "DET", "GB"}:
        errors.append(f"injuries_depth.json: unexpected club_depth_audit teams {clubs}")

    # 5 & 6. HTML page inventory, last-cell links, and audit/check_site.py on lineup-lab/
    for rel in REQUIRED_PAGES:
        fp = C.LAB_ROOT / rel
        if not fp.is_file():
            errors.append(f"Missing required HTML page: {rel}")
            continue
        parser = TableCellChecker()
        parser.feed(fp.read_text(encoding="utf-8"))
        if not parser.title.strip():
            errors.append(f"{rel}: empty <title>")
        if parser.rows_missing_last_link:
            errors.append(f"{rel}: tbody row(s) missing link in last cell at lines {parser.rows_missing_last_link[:5]}")

    audit_issues, pages_cnt, row_cnt = AUDIT.audit(C.LAB_ROOT)
    for issue in audit_issues:
        errors.append(f"audit/check_site: {issue}")

    d_errs, d_warns, _, d_rows = AUDIT.audit_dashboard_data(C.LAB_ROOT)
    for e in d_errs:
        errors.append(f"audit_dashboard_data error: {e}")
    for w in d_warns:
        if not w.startswith("data/sources.json: SRC-CLUB-"):
            errors.append(f"audit_dashboard_data row warning: {w}")

    if errors:
        print("FAIL:", len(errors), "issue(s) in Lineup Lab verification:")
        for e in errors[:30]:
            print(" -", e)
        return 1

    print(
        f"PASS: Lineup Lab verified cleanly — {len(json_files)} strict JSONs, "
        f"{len(src_ids)} verified sources, 32/32 standings (2020/2025/2026 W9), "
        f"{pages_cnt} HTML pages / {row_cnt} data rows with 0 source/link flags."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
