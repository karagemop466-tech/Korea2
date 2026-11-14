#!/usr/bin/env python3
"""line-desk verifier. Enforces the brief's verification policy on the committed site:

  1. strict JSON (no NaN/Infinity) for every register under line-desk/data/;
  2. every table row on every line-desk page carries a source link;
  3. every internal link resolves, every external link is https;
  4. blank-by-policy: market prices, untranscribed scores and depth tiers are null
     in JSON and render as empty cells - nothing is inferred or filled;
  5. correlations are recomputed from the official standings transcription and must
     match the published coefficients, with n equal to the row count;
  6. compute.py and build_site.py are deterministic: a fresh run must produce
     byte-identical committed outputs.

Exit code 0 = all checks pass.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LD = os.path.join(ROOT, "line-desk")

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def strict_load(path: str):
    def _reject(x):
        raise ValueError(f"non-standard constant {x}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh, parse_constant=_reject)


def check_json_files() -> dict:
    data = {}
    ddir = os.path.join(LD, "data")
    for name in sorted(os.listdir(ddir)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(ddir, name)
        try:
            data[name] = strict_load(path)
        except Exception as exc:  # noqa: BLE001
            err(f"{name}: strict JSON failed: {exc}")
    return data


def check_source_urls(data: dict) -> None:
    def walk(obj, where):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("source_url", "game_url", "data_source_url", "method_source_url",
                         "depth_chart_check_url") and isinstance(v, str):
                    for u in v.split(" | "):
                        if not u.startswith("https://"):
                            err(f"{where}: non-https source {u!r}")
                else:
                    walk(v, f"{where}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{where}[{i}]")
    for name, obj in data.items():
        walk(obj, name)
    src = data.get("sources.json")
    if src:
        for s in src["sources"]:
            if not s["url"].startswith("https://"):
                err(f"sources.json: {s['id']} url not https")


def check_blank_policy(data: dict) -> None:
    snap = data.get("price_snapshots.json")
    if snap:
        for i, r in enumerate(snap["rows"]):
            for field in ("market_open", "market_close", "ours_close"):
                if r.get(field) is not None:
                    err(f"price_snapshots row {i}: {field} must be null (no official source)")
            if r.get("verified") is not False:
                err(f"price_snapshots row {i}: verified must be false while prices are absent")
        cov = snap["coverage"]
        if cov["market_open_captured"] or cov["market_close_captured"]:
            err("price_snapshots coverage: market captures must be 0 without an official feed")

    orig = data.get("origination.json")
    if orig:
        for g in orig["games"]:
            for step, fields in (
                ("step1_side", ("market_line", "difference")),
                ("step2_total", ("market_line", "difference")),
                ("step3_moneyline", ("market_home_ml", "market_away_ml", "difference")),
            ):
                for f in fields:
                    if g[step].get(f) is not None:
                        err(f"origination {g['game_id']}.{step}.{f} must be null")
        if orig["market_columns_published"] != 0:
            err("origination: market_columns_published must be 0 under the policy")

    feed = data.get("results_feed.json")
    if feed:
        for r in feed["rows"]:
            if not r["verified"]:
                err(f"results_feed {r['game_id']}: unpublished row must not exist - pending games live in coverage.pending_weeks with no scores")
            if not isinstance(r["away_score"], int) or not isinstance(r["home_score"], int):
                err(f"results_feed {r['game_id']}: verified rows must carry integer scores")
            if r["status"] != "FINAL":
                err(f"results_feed {r['game_id']}: status must be FINAL")

    depth = data.get("depth.json")
    if depth:
        for i, r in enumerate(depth["rows"]):
            for f in ("replacement_player", "replacement_string", "depth_source"):
                if r.get(f) is not None:
                    err(f"depth row {i}: {f} must be null (no official depth source)")


def check_counts_and_correlations(data: dict) -> None:
    st = data.get("official_standings.json")
    corr = data.get("correlations.json")
    feed = data.get("results_feed.json")
    off_res = data.get("official_results.json")
    snap = data.get("price_snapshots.json")
    orig = data.get("origination.json")

    if st:
        n26 = sum(1 for r in st["rows"] if r["season"] == 2026)
        n25 = sum(1 for r in st["rows"] if r["season"] == 2025)
        if n26 != 32 or n25 != 32:
            err(f"official_standings: expected 32+32 rows, got {n26}+{n25}")

    if off_res and feed:
        n_off = sum(len(w["games"]) for w in off_res["weeks"])
        if n_off != feed["verified_rows"] or n_off != len(feed["rows"]):
            err(f"results_feed: row count {len(feed['rows'])} != official transcription {n_off}")

    if snap and orig:
        if len(snap["rows"]) != orig["n_games"] * 3:
            err("price_snapshots: expected 3 records per originated game")

    if corr and st:
        rows = st["rows"]
        by_season = {2026: [r for r in rows if r["season"] == 2026],
                     2025: [r for r in rows if r["season"] == 2025]}
        pooled = by_season[2026] + by_season[2025]

        def r_of(xs, ys):
            n = len(xs)
            mx, my = sum(xs) / n, sum(ys) / n
            sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            sxx = sum((x - mx) ** 2 for x in xs)
            syy = sum((y - my) ** 2 for y in ys)
            return round(sxy / math.sqrt(sxx * syy), 4)

        expect = {
            "C-PF-W-2026": (r_of([r["pf"] for r in by_season[2026]], [r["w"] for r in by_season[2026]]), 32),
            "C-PA-L-2026": (r_of([r["pa"] for r in by_season[2026]], [r["l"] for r in by_season[2026]]), 32),
            "C-NET-W-2026": (r_of([r["pf"] - r["pa"] for r in by_season[2026]], [r["w"] for r in by_season[2026]]), 32),
            "C-PF-W-2025": (r_of([r["pf"] for r in by_season[2025]], [r["w"] for r in by_season[2025]]), 32),
            "C-PA-L-2025": (r_of([r["pa"] for r in by_season[2025]], [r["l"] for r in by_season[2025]]), 32),
            "C-NET-W-2025": (r_of([r["pf"] - r["pa"] for r in by_season[2025]], [r["w"] for r in by_season[2025]]), 32),
            "C-PF-W-POOL": (r_of([r["pf"] for r in pooled], [r["w"] for r in pooled]), 64),
            "C-PA-L-POOL": (r_of([r["pa"] for r in pooled], [r["l"] for r in pooled]), 64),
        }
        pub = {c["id"]: c for c in corr["correlations"]}
        if set(pub) != set(expect):
            err(f"correlations: id set mismatch {set(pub) ^ set(expect)}")
        for cid, (r, n) in expect.items():
            if cid not in pub:
                continue
            c = pub[cid]
            if c["r"] != r:
                err(f"correlations {cid}: published r={c['r']} != recomputed {r}")
            if c["n"] != n:
                err(f"correlations {cid}: published n={c['n']} != {n}")
            if not (-1 <= c["r"] <= 1 and c["ci95"][0] <= c["r"] <= c["ci95"][1]):
                err(f"correlations {cid}: r outside CI or bounds")
            if not c.get("official_only"):
                err(f"correlations {cid}: official_only flag missing")


class RowLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.title = ""
        self._in_title = False
        self._in_tbody = False
        self._in_cell = False
        self._row_has_link = False
        self.rows = 0
        self.rows_missing_link = 0
        self.generator = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("name") == "generator":
            self.generator = a.get("content", "")
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "title":
            self._in_title = True
        if tag == "tbody":
            self._in_tbody = True
        if tag == "tr" and self._in_tbody:
            self.rows += 1
            self._row_has_link = False
        if tag in ("td", "th"):
            self._in_cell = True
        if tag == "a":
            self._row_has_link = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in ("td", "th"):
            self._in_cell = False
        if tag == "tbody":
            self._in_tbody = False
        if tag == "tr" and self._in_tbody and not self._row_has_link:
            self.rows_missing_link += 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def iter_line_desk_html():
    for base, dirs, files in os.walk(LD):
        dirs[:] = [d for d in dirs if d not in ("data", "scripts", "assets")]
        for n in files:
            if n.endswith(".html"):
                yield os.path.join(base, n)


def check_html() -> None:
    docs = {}
    for path in iter_line_desk_html():
        rel = os.path.relpath(path, ROOT)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        p = RowLinkParser()
        p.feed(content)
        docs[rel] = p
        if not p.title.strip():
            err(f"{rel}: missing title")
        if "line-desk/scripts/build_site.py" not in p.generator:
            err(f"{rel}: generator marker missing")
        if p.rows_missing_link:
            err(f"{rel}: {p.rows_missing_link} table row(s) without a source link")
    # link resolution
    for rel, p in docs.items():
        for href in p.links:
            if href.startswith(("mailto:",)):
                continue
            if href.startswith("http://"):
                err(f"{rel}: insecure external link {href}")
                continue
            if href.startswith("#"):
                if href[1:] and href[1:] not in p.ids:
                    err(f"{rel}: broken anchor {href}")
                continue
            if href.startswith("https://"):
                continue
            target = href.split("#")[0]
            resolved = os.path.normpath(os.path.join(os.path.dirname(rel), target))
            if not os.path.exists(os.path.join(ROOT, resolved)):
                err(f"{rel}: broken internal link {href} -> {resolved}")
    # every declared NAV page exists on disk
    import importlib.util
    spec = importlib.util.spec_from_file_location("ld_build", os.path.join(LD, "scripts", "build_site.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for href, _label in mod.NAV:
        if href not in mod.PAGES:
            err(f"NAV entry {href} has no builder")
        elif not os.path.exists(os.path.join(LD, href)):
            err(f"NAV page missing on disk: {href}")


def check_determinism() -> None:
    # compute.py: re-run must leave files byte-identical
    ddir = os.path.join(LD, "data")
    derived = ["correlations.json", "results_feed.json", "price_snapshots.json",
               "origination.json", "leaderboard.json", "gates.json", "depth.json"]
    before = {}
    for name in derived:
        with open(os.path.join(ddir, name), "rb") as fh:
            before[name] = fh.read()
    r = subprocess.run([sys.executable, os.path.join(LD, "scripts", "compute.py")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        err(f"compute.py failed: {r.stderr[-400:]}")
        return
    for name, content in before.items():
        with open(os.path.join(ddir, name), "rb") as fh:
            if fh.read() != content:
                err(f"compute.py is not deterministic: {name} changed")
    # build_site.py --check
    r = subprocess.run([sys.executable, os.path.join(LD, "scripts", "build_site.py"), "--check"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        err(f"build_site.py --check failed: {(r.stdout + r.stderr)[-400:]}")


def main() -> int:
    data = check_json_files()
    check_source_urls(data)
    check_blank_policy(data)
    check_counts_and_correlations(data)
    check_html()
    check_determinism()
    if errors:
        print(f"line-desk verify: FAIL ({len(errors)} issue(s))")
        for e in errors[:50]:
            print(" -", e)
        return 1
    print("line-desk verify: PASS "
          f"({len(data)} registers, blank policy ok, correlations recomputed, "
          "rows sourced, links resolved, outputs deterministic)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
