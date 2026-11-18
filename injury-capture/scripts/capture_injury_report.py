#!/usr/bin/env python3
"""Capture the official NFL weekly injury report with a raw-byte hash and a fetch time.

Designed to run on a GitHub-hosted runner (the authoring sandbox cannot reach nfl.com).

What it does
------------
1. GET https://www.nfl.com/injuries/league/<season>/reg<week> and keep the raw bytes.
2. Record SHA-256 of the raw bytes, HTTP status, final URL, Content-Length, fetch time (UTC).
3. Parse every <table> with a stdlib HTML parser (no hand transcription).
4. Fail loudly (non-zero exit) if the page is not the requested week, has no injury tables,
   or a table is missing a required column. A missing field must never become a blank value.
5. Write:
   - a raw capture file and parsed-rows CSV to --out-dir (uploaded as a workflow artifact,
     i.e. kept outside the static site);
   - a small manifest JSON (hash, time, URL, counts) to injury-capture/manifests/ (committed).

What it does NOT do
-------------------
It does not infer starters, depth order, replacements or game status. It does not fill blanks.
"""
import argparse, csv, datetime as dt, hashlib, json, os, re, sys, urllib.request
from html.parser import HTMLParser

UA = "injury-capture/1.0 (+https://github.com/karagemop466-tech/Korea2)"
REQUIRED_COLS = {"player", "pos", "injury", "practice status"}  # game status checked separately


class TableParser(HTMLParser):
    """Collects tables as {headings_before, header, rows}. A header is a row inside <thead>
    or a row whose cells are <th>. Rows keep their cell text in document order."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._open = []        # stack of table dicts being parsed
        self._headings = []    # text of h1..h5 seen so far (document order)
        self._h_buf = None
        self._row = None       # list of cell strings for the open <tr>
        self._row_is_th = False
        self._cell = None      # list of text fragments for the open cell

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3", "h4", "h5"):
            self._h_buf = []
        elif tag == "table":
            self._open.append({"headings_before": self._headings[-3:], "header": None,
                               "rows": [], "in_thead": False})
        elif tag == "thead" and self._open:
            self._open[-1]["in_thead"] = True
        elif tag == "tr" and self._open:
            self._row, self._row_is_th = [], False
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            if tag == "th":
                self._row_is_th = True

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4", "h5") and self._h_buf is not None:
            text = " ".join("".join(self._h_buf).split())
            if text:
                self._headings.append(text)
            self._h_buf = None
        elif tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._open:
            t = self._open[-1]
            if self._row:
                if t["in_thead"] or self._row_is_th:
                    if t["header"] is None:
                        t["header"] = self._row
                else:
                    t["rows"].append(self._row)
            self._row = None
        elif tag == "thead" and self._open:
            self._open[-1]["in_thead"] = False
        elif tag == "table" and self._open:
            self.tables.append(self._open.pop())

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)
        if self._h_buf is not None:
            self._h_buf.append(data)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    fetched_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.status, r.geturl(), r.headers.get("Last-Modified", ""), r.read(), fetched_at


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--manifest-dir", default="injury-capture/manifests")
    ap.add_argument("--min-rows", type=int, default=50, help="pinned lower bound on listed players")
    a = ap.parse_args()

    url = f"https://www.nfl.com/injuries/league/{a.season}/reg{a.week}"
    status, final_url, last_mod, raw, fetched_at = fetch(url)
    sha = hashlib.sha256(raw).hexdigest()
    stamp = fetched_at.replace(":", "").replace("-", "")
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(a.manifest_dir, exist_ok=True)
    base = f"nfl_injury_{a.season}_reg{a.week}_{stamp}"
    raw_path = os.path.join(a.out_dir, base + ".html")
    with open(raw_path, "wb") as fh:
        fh.write(raw)

    text = raw.decode("utf-8", "replace")
    problems = []
    if status != 200:
        problems.append(f"HTTP status {status}")
    week_ok = re.search(rf"Week\s+{a.week}\b", text) is not None
    if not week_ok:
        problems.append(f"page does not contain 'Week {a.week}'")

    p = TableParser()
    p.feed(text)
    tables = []
    for t in p.tables:
        if not t["header"]:
            continue
        cols = [c.strip().lower().rstrip(".") for c in t["header"]]
        tables.append({"heading": (t["headings_before"] or [""])[-1], "cols": cols, "rows": t["rows"]})

    # Structural diagnostic (page markup only, no row content beyond the first row's cells).
    diagnostics = {
        "markers": {m: text.count(m) for m in ["<table", "<thead", "<th", "<tr", "__NEXT_DATA__",
                                               "application/ld+json", "Practice Status",
                                               "Game Status", "Did Not Participate", "Injury Report"]},
        "tables": [{"heading": (t["headings_before"] or [""])[-1][:120],
                    "header_cells": (t["header"] or [])[:12],
                    "n_rows": len(t["rows"]),
                    "first_row_cells": [c[:60] for c in (t["rows"][0] if t["rows"] else [])][:12]}
                   for t in p.tables[:40]],
    }
    injury_tables = [t for t in tables if REQUIRED_COLS.issubset(set(t["cols"]))]
    if not injury_tables:
        problems.append("no table with required columns " + ", ".join(sorted(REQUIRED_COLS)))

    rows_out = []
    for t in injury_tables:
        idx = {c: i for i, c in enumerate(t["cols"])}
        for r in t["rows"]:
            if len(r) != len(t["cols"]):
                problems.append(f"row width {len(r)} != header width {len(t['cols'])} in '{t['heading']}'")
                continue
            rows_out.append({
                "team_heading": t["heading"],
                "player": r[idx["player"]],
                "pos": r[idx["pos"]],
                "injury": r[idx["injury"]] if "injury" in idx else "",
                "practice_status": r[idx["practice status"]],
                "game_status": r[idx["game status"]] if "game status" in idx else None,
            })

    if len(rows_out) < a.min_rows:
        problems.append(f"only {len(rows_out)} listed rows parsed (pinned minimum {a.min_rows})")
    if any(r["game_status"] is None for r in rows_out):
        problems.append("required column 'game status' missing from at least one table")

    csv_path = os.path.join(a.out_dir, base + ".rows.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()) if rows_out else ["team_heading"])
        w.writeheader()
        for r in rows_out:
            w.writerow(r)

    manifest = {
        "source_url": url, "final_url": final_url, "season": a.season, "week": a.week,
        "http_status": status, "last_modified_header": last_mod, "fetched_at_utc": fetched_at,
        "raw_sha256": sha, "raw_bytes": len(raw), "raw_file_in_artifact": os.path.basename(raw_path),
        "html_tables_total": len(tables), "injury_tables": len(injury_tables),
        "listed_rows_parsed": len(rows_out), "week_text_found": week_ok,
        "problems": problems, "pinned_min_rows": a.min_rows, "diagnostics": diagnostics,
        "status": "FAILED" if problems else "OK",
    }
    mpath = os.path.join(a.manifest_dir, f"reg{a.week}_{a.season}_{stamp}.json")
    with open(mpath, "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(json.dumps(manifest, indent=2))
    if problems:
        print("CAPTURE FAILED: " + "; ".join(problems), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
