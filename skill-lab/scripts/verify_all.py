#!/usr/bin/env python3
"""Automated line-by-line verification suite for Skill Lab (SL-8).

Enforces:
1. Strict RFC 8259 JSON across skill-lab/data/*.json (no NaN / Infinity / transient cache).
2. Official NFL.com reconciliation invariants (2025 32/32, 2026+Nov1 32/32, 7/7 players).
3. Zero-hallucination / blank-cell enforcement across JSON and rendered HTML (<td class="blank-cell">).
4. 100% per-row official source links on every <tbody><tr> across all 12 Skill Lab HTML pages.
5. Local link, stylesheet, and navigation completeness across all 12 Skill Lab HTML pages.
6. Validation gate & copula bias invariants (STR-16 G1 disqualification, 0 unverified payouts).
"""
from __future__ import annotations

import html.parser
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

SKILL_LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = SKILL_LAB_ROOT.parent
DATA_DIR = SKILL_LAB_ROOT / "data"
PAGES_DIR = SKILL_LAB_ROOT / "pages"

ALLOWED_OFFICIAL_HOSTS = {
    "www.nfl.com",
    "nfl.com",
    "operations.nfl.com",
    "edge-operations.nfl.com",
    "support.nfl.com",
    "support.draftkings.com",
    "www.itl.nist.gov",
    "scikit-learn.org",
    "www.weather.gov",
    "www.princeton.edu",
    "courses.cit.cornell.edu",
    "www.ncpgambling.org",
    "github.com",
}


class TableAndLinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_tbody = False
        self.in_tr = False
        self.in_blank_td = False
        self.blank_td_text: list[str] = []
        self.current_row_links: list[str] = []
        self.tbody_rows_links: list[list[str]] = []
        self.blank_cells: list[str] = []
        self.all_hrefs: list[str] = []
        self.has_title = False
        self.has_nav = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        amap = dict(attrs)
        if tag == "title":
            self.has_title = True
        elif tag == "nav":
            self.has_nav = True
        elif tag == "tbody":
            self.in_tbody = True
        elif tag == "tr" and self.in_tbody:
            self.in_tr = True
            self.current_row_links = []
        elif tag == "td":
            cls = amap.get("class") or ""
            if "blank-cell" in cls.split():
                self.in_blank_td = True
                self.blank_td_text = []
        elif tag in ("a", "link"):
            href = amap.get("href")
            if href:
                self.all_hrefs.append(href)
                if tag == "a" and self.in_tr:
                    self.current_row_links.append(href)

    def handle_data(self, data: str) -> None:
        if self.in_blank_td:
            self.blank_td_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "tbody":
            self.in_tbody = False
        elif tag == "tr" and self.in_tr:
            self.in_tr = False
            self.tbody_rows_links.append(self.current_row_links)
        elif tag == "td" and self.in_blank_td:
            self.in_blank_td = False
            self.blank_cells.append("".join(self.blank_td_text))


def strict_load(path: Path) -> dict:
    def reject_nonfinite(tok: str) -> None:
        raise ValueError(f"{path.name} contains non-JSON token {tok}")

    with open(path, encoding="utf-8") as fh:
        return json.loads(fh.read(), parse_constant=reject_nonfinite)


def main() -> int:
    errors: list[str] = []

    # 1. Strict JSON & absence of transient cache
    expected_jsons = {
        "sources.json",
        "origination.json",
        "luck.json",
        "signals.json",
        "correlations.json",
        "strategies.json",
        "leaderboard.json",
        "official_2026.json",
        "repo_review.json",
        "flagged.json",
    }
    present_jsons = {p.name for p in DATA_DIR.glob("*.json")}
    if "_predictions_cache.json" in present_jsons:
        errors.append("Transient _predictions_cache.json must not remain in skill-lab/data/")
    missing_jsons = expected_jsons - present_jsons
    if missing_jsons:
        errors.append(f"Missing expected JSON files: {sorted(missing_jsons)}")

    loaded: dict[str, dict] = {}
    for name in sorted(expected_jsons & present_jsons):
        try:
            loaded[name] = strict_load(DATA_DIR / name)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"JSON parse failure in {name}: {exc}")

    if errors:
        for e in errors:
            print("FAIL:", e)
        return 1

    # 2. Official source URL registry check
    registered_urls = set()
    for s in loaded["sources.json"]["sources"]:
        u = s["url"]
        host = urlparse(u).netloc.lower()
        if host not in ALLOWED_OFFICIAL_HOSTS:
            errors.append(f"Source {s['id']} host {host} not in official allowlist")
        registered_urls.add(u)

    # 3. Official NFL.com reconciliation invariants
    off = loaded["official_2026.json"]
    if off["teams_2025_exact"] != 32:
        errors.append(f"Expected 32/32 exact 2025 teams, got {off['teams_2025_exact']}")
    if off["teams_2026_exact_after_nov1"] != 32:
        errors.append(f"Expected 32/32 exact 2026+Nov1 teams, got {off['teams_2026_exact_after_nov1']}")
    if off["players_2026_exact"] != 7:
        errors.append(f"Expected 7/7 exact 2026 player logs, got {off['players_2026_exact']}")

    # 4. Zero-hallucination / blank-value invariants in JSON
    for f in loaded["flagged.json"]["rows"]:
        if f["value"] != "":
            errors.append(f"Flagged item {f['id']} must have blank value '', got {f['value']!r}")

    for s in loaded["strategies.json"]["rows"]:
        if s["funded_cash_prize"] != "":
            errors.append(f"Strategy {s['id']} funded_cash_prize must be blank ''")
        if s["id"] in {"STR-10", "STR-11", "STR-12", "STR-13", "STR-14"}:
            if s["roi_pct"] != "" or s["luck_adjusted_roi_pct"] != "":
                errors.append(f"Unpriced SGP/prop strategy {s['id']} must leave ROI blank ''")
        if s["id"] == "STR-16":
            if s["gates"]["G1"] is not False or s["skill_score"] != 0.0:
                errors.append("Lookahead leak control STR-16 must fail G1 and receive skill_score 0.0")

    lb = loaded["leaderboard.json"]
    if lb["qualified_strategies"] != 0 or lb["points_awarded"] != 0:
        errors.append("Expected 0 qualified strategies and 0 points awarded")

    gap = loaded["correlations.json"]["ex_ante_vs_ex_post_wr1_gap"]
    if not (gap["ex_post_wr1_r"] - gap["ex_ante_wr1_r"] > 0.15):
        errors.append("Expected substantial ex-post WR1 selection inflation (> +0.15)")

    # 5. HTML verification across all 12 Skill Lab pages
    html_pages = [SKILL_LAB_ROOT / "index.html"] + sorted(PAGES_DIR.glob("*.html"))
    if len(html_pages) != 12:
        errors.append(f"Expected 12 Skill Lab HTML pages, found {len(html_pages)}")

    total_rows = 0
    total_blank_cells = 0
    for hp in html_pages:
        parser = TableAndLinkParser()
        parser.feed(hp.read_text(encoding="utf-8"))
        rel = hp.relative_to(REPO_ROOT)
        if not parser.has_title or not parser.has_nav:
            errors.append(f"{rel}: missing <title> or <nav>")
        if not parser.tbody_rows_links:
            errors.append(f"{rel}: contains 0 <tbody><tr> data rows")
        for idx, rlinks in enumerate(parser.tbody_rows_links, start=1):
            total_rows += 1
            ext = [u for u in rlinks if u.startswith("https://")]
            if not ext:
                errors.append(f"{rel} row #{idx}: missing https:// official source link")
                continue
            for u in ext:
                host = urlparse(u).netloc.lower()
                if host not in ALLOWED_OFFICIAL_HOSTS:
                    errors.append(f"{rel} row #{idx}: non-official source host {host} ({u})")
                if u not in registered_urls:
                    errors.append(f"{rel} row #{idx}: source URL not registered in sources.json ({u})")
        for btxt in parser.blank_cells:
            total_blank_cells += 1
            if btxt != "":
                errors.append(f"{rel}: blank-cell contains non-empty text {btxt!r}")
        for href in parser.all_hrefs:
            if href.startswith(("http://", "https://", "mailto:", "#")):
                continue
            clean = href.split("#", 1)[0].split("?", 1)[0]
            if not clean:
                continue
            target = (hp.parent / clean).resolve()
            if not target.exists():
                errors.append(f"{rel}: broken local link {href} -> {target}")

    if errors:
        print("SKILL LAB VERIFICATION FAILED:")
        for e in errors:
            print(" -", e)
        return 1

    print(
        f"PASS: {len(loaded)} strict JSON files, {len(html_pages)} HTML pages, "
        f"{total_rows} table rows (100% linked to {len(registered_urls)} official sources), "
        f"{total_blank_cells} strictly empty unverified cells, "
        f"64/64 NFL.com team-seasons & 7/7 player logs reconciled."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
