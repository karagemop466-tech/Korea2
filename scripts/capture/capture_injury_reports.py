#!/usr/bin/env python3
"""Immutable capture of the official NFL injury-report pages, with a drift alarm.

Source: https://www.nfl.com/injuries/league/<season>/reg<week>  (NFL.com, official)

Per run, for every regular-season week requested:

  1. fetch the page and keep the raw response bytes;
  2. content-address the bytes by SHA-256 and store them ONCE, gzipped, under bodies/
     (write-once: an existing body is never overwritten);
  3. append ONE line to manifest.jsonl for every fetch (the manifest is never rewritten):
     UTC fetch time, the server's Date and Last-Modified headers, HTTP status, byte count,
     SHA-256, whether the body is new, and the parse result with its flags;
  4. parse the team tables into normalised rows (parsed/<sha256>.json), pinned to the
     expected header  Player | Position | Injuries | Practice Status | Game Status;
  5. append player-level changes between consecutive DIFFERENT captures of the same week to
     deltas.jsonl (the delta is published, the level is kept only in the raw body);
  6. rewrite status.json, a convenience summary of the latest state per week.

DRIFT ALARM (exit code 1, printed as "DRIFT ALARM"): a table whose header differs from the
pinned schema, a table with no attributable team, a malformed data row, a page that used to
carry tables and no longer does, or every fetch failing. The raw body is stored BEFORE the
alarm is raised, so nothing is lost when the alarm fires.

Not an alarm: a week the NFL has not published yet (404 or a page with no tables before any
week has carried a table). Those are recorded with their status and flags.

Usage:
    python scripts/capture/capture_injury_reports.py --root . --season 2026 --weeks 1-18
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

SOURCE_URL = "https://www.nfl.com/injuries/league/{season}/reg{week}"
DATA_REL = os.path.join("data", "snapshots", "injury_report")
UA = "Mozilla/5.0 (compatible; korea2-injury-capture/1.0; +https://github.com/karagemop466-tech/Korea2)"

EXPECTED_HEADER = ["Player", "Position", "Injuries", "Practice Status", "Game Status"]

# NFL.com club abbreviation -> nickname as printed in the report.
TEAMS = {
    "AZ": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills",
    "CAR": "Panthers", "CHI": "Bears", "CIN": "Bengals", "CLE": "Browns",
    "DAL": "Cowboys", "DEN": "Broncos", "DET": "Lions", "GB": "Packers",
    "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars", "KC": "Chiefs",
    "LA": "Rams", "LAC": "Chargers", "LV": "Raiders", "MIA": "Dolphins",
    "MIN": "Vikings", "NE": "Patriots", "NO": "Saints", "NYG": "Giants",
    "NYJ": "Jets", "PHI": "Eagles", "PIT": "Steelers", "SEA": "Seahawks",
    "SF": "49ers", "TB": "Buccaneers", "TEN": "Titans", "WAS": "Commanders",
}
# Abbreviations as the NFL.com page itself uses them in logo paths (observed 2026-11-15:
# the Cardinals are AZ and the Rams are LA in clubs/logos/...). Aliases map other spellings.
ALIASES = {"ARI": "AZ", "LAR": "LA"}
PARSER_VERSION = "1.1"
DECLARED_WEEK_RE = re.compile(r"Injuries\s*-\s*WEEK\s*(\d+)", re.I)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
LOGO_RE = re.compile(r"clubs/logos/([A-Z]{2,3})(?![A-Za-z])")
COMPARED_FIELDS = ("injuries", "practice_status", "game_status")
ALARM = "DRIFT ALARM"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


# ----------------------------------------------------------------------------- parsing
class ReportParser(HTMLParser):
    """Collects every <table> with the club it belongs to.

    A club logo (clubs/logos/XXX) precedes the two team tables of each game. Logos are queued
    in document order and each <table> takes the next queued logo, so a game's two tables get
    its two clubs in order. The nickname printed just before each table is kept so the
    attribution can be checked against TEAMS.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pending: list[str] = []
        self.tables: list[dict] = []
        self.cur_table: dict | None = None
        self.cur_row: list[str] | None = None
        self.cur_cell: list[str] | None = None
        self.cur_row_has_th = False
        self.text_before = ""
        self.skip = 0

    def _logo(self, value: str) -> None:
        for raw in LOGO_RE.findall(value or ""):
            abbr = ALIASES.get(raw, raw)
            if abbr in TEAMS and abbr not in self.pending:
                self.pending.append(abbr)

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
            return
        for _, value in attrs:
            self._logo(value)
        if tag == "table":
            team = self.pending.pop(0) if self.pending else None
            self.cur_table = {"team": team, "label": norm(self.text_before)[-200:],
                              "rows": [], "row_has_th": []}
        elif tag == "tr" and self.cur_table is not None:
            self.cur_row = []
            self.cur_row_has_th = False
        elif tag in ("td", "th") and self.cur_row is not None:
            self.cur_cell = []
            if tag == "th":
                self.cur_row_has_th = True
        elif tag == "br" and self.cur_cell is not None:
            self.cur_cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
            return
        if tag in ("td", "th") and self.cur_cell is not None and self.cur_row is not None:
            self.cur_row.append(norm("".join(self.cur_cell)))
            self.cur_cell = None
        elif tag == "tr" and self.cur_row is not None and self.cur_table is not None:
            if any(c for c in self.cur_row):
                self.cur_table["rows"].append(self.cur_row)
                self.cur_table["row_has_th"].append(self.cur_row_has_th)
            self.cur_row = None
        elif tag == "table" and self.cur_table is not None:
            self.tables.append(self.cur_table)
            self.cur_table = None

    def handle_data(self, data):
        if self.skip:
            return
        if self.cur_cell is not None:
            self.cur_cell.append(data)
        elif self.cur_table is None:
            self.text_before = (self.text_before + " " + data)[-400:]


def declared_week(html: str) -> int | None:
    """The week the page itself shows in its body heading ('Injuries - WEEK N').

    The <title> is NOT used: on 2026-11-15 every captured body, including the Week 1 body,
    carried the same <title> ('... Week 10 of the 2026 Season'), so it is a static template.
    """
    m = DECLARED_WEEK_RE.search(html)
    return int(m.group(1)) if m else None


def parse_report(html: str, season: int, week: int) -> dict:
    """Turn one report page into normalised rows plus the flags raised while doing so."""
    p = ReportParser()
    p.feed(html)
    p.close()
    flags: list[str] = []
    shown = declared_week(html)
    title = norm(TITLE_RE.search(html).group(1)) if TITLE_RE.search(html) else ""
    if shown is not None and shown != week:
        flags.append(f"week_mismatch:requested {week} page shows {shown}")
    tm = re.search(r"Week (\d+) of the (\d{4}) Season", title)
    if tm and shown is not None and int(tm.group(1)) != shown:
        flags.append(f"title_week_static:title says {tm.group(1)}, body says {shown}")
    rows: list[dict] = []
    teams_seen: dict[str, dict] = {}
    alarms: list[str] = []
    for i, t in enumerate(p.tables):
        table_rows = t["rows"]
        team = t["team"]
        if not table_rows:
            continue
        header = table_rows[0]
        body = table_rows[1:]
        looks_like_header = bool(t["row_has_th"][0]) or (header and header[0].lower() == "player")
        if looks_like_header and header != EXPECTED_HEADER:
            alarms.append(f"table {i}: header {header} != pinned {EXPECTED_HEADER}")
            continue
        if not looks_like_header:
            alarms.append(f"table {i}: no header row (first row {header})")
            continue
        if team is None:
            alarms.append(f"table {i}: no club attributable (label '{t['label'][-60:]}')")
            continue
        nickname = TEAMS[team]
        if nickname.lower() not in t["label"].lower():
            flags.append(f"label_mismatch:{team}")
        info = teams_seen.setdefault(team, {"team": team, "nickname": nickname, "rows": 0, "tables": 0})
        info["tables"] += 1
        for r in body:
            if len(r) != len(EXPECTED_HEADER):
                alarms.append(f"{team}: malformed row ({len(r)} cells) {r}")
                continue
            player, position, injuries, practice, game = r
            if not player:
                alarms.append(f"{team}: row with empty player name {r}")
                continue
            rows.append({"team": team, "player": player, "position": position,
                         "injuries": injuries, "practice_status": practice,
                         "game_status": game})
            info["rows"] += 1
            if practice == "Did Not Participate In Practice" and not game:
                flags.append(f"dnp_without_game_status:{team}:{player}")
    names = [(r["team"], r["player"]) for r in rows]
    for key in sorted({k for k in names if names.count(k) > 1}):
        flags.append(f"duplicate_player:{key[0]}:{key[1]}")
    return {
        "season": season, "week": week, "declared_week": shown, "title": title,
        "parser_version": PARSER_VERSION, "tables": len(p.tables),
        "teams": sorted(teams_seen.values(), key=lambda x: x["team"]),
        "rows": rows, "flags": sorted(set(flags)), "alarms": alarms,
    }


# ----------------------------------------------------------------------------- storage
def read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def write_once(path: str, data: bytes) -> bool:
    """Create a file; refuse to replace an existing one. Returns True when newly written."""
    if os.path.exists(path):
        with open(path, "rb") as fh:
            if hashlib.sha256(fh.read()).hexdigest() != hashlib.sha256(data).hexdigest():
                raise RuntimeError(f"refusing to overwrite {path}: content differs")
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "xb") as fh:
        fh.write(data)
    return True


def append_jsonl(path: str, records: list[dict]) -> None:
    if not records:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n")


def fetch(url: str, timeout: int = 60) -> tuple[int, bytes, dict]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers.items())
    except urllib.error.HTTPError as err:
        return err.code, err.read() or b"", dict(err.headers.items()) if err.headers else {}


def diff_rows(old: dict, new: dict) -> list[dict]:
    """Player-level changes between two parsed captures of the same week."""
    def index(doc):
        return {(r["team"], r["player"]): r for r in doc.get("rows", [])}
    a, b = index(old), index(new)
    out = []
    for key in sorted(set(a) | set(b)):
        team, player = key
        if key not in a:
            out.append({"team": team, "player": player, "change": "added",
                        "field": None, "before": None, "after": b[key]["game_status"] or b[key]["practice_status"]})
        elif key not in b:
            out.append({"team": team, "player": player, "change": "removed",
                        "field": None, "before": a[key]["game_status"] or a[key]["practice_status"], "after": None})
        else:
            for f in COMPARED_FIELDS:
                if a[key][f] != b[key][f]:
                    out.append({"team": team, "player": player, "change": "changed", "field": f,
                                "before": a[key][f], "after": b[key][f]})
    return out


def parse_weeks(spec: str) -> list[int]:
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(x) for x in spec.split(",") if x.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="repository root to write under")
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--weeks", default="1-18")
    ap.add_argument("--pause", type=float, default=1.0, help="seconds between requests")
    args = ap.parse_args(argv)

    base = os.path.join(args.root, DATA_REL)
    manifest_path = os.path.join(base, "manifest.jsonl")
    deltas_path = os.path.join(base, "deltas.jsonl")
    status_path = os.path.join(base, "status.json")
    manifest = read_jsonl(manifest_path)
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    run_started = utc_now()

    # Latest distinct parsed capture per week, and whether that week has ever carried a table.
    last_parsed: dict[int, dict] = {}
    had_tables: dict[int, bool] = {}
    for rec in manifest:
        if rec.get("parsed_file") and rec.get("week") is not None:
            last_parsed[rec["week"]] = rec
        if rec.get("tables"):
            had_tables[rec["week"]] = True

    new_manifest: list[dict] = []
    new_deltas: list[dict] = []
    alarms: list[str] = []
    fetched_ok = 0
    weeks = parse_weeks(args.weeks)
    state: dict[str, dict] = {}

    for n, week in enumerate(weeks):
        url = SOURCE_URL.format(season=args.season, week=week)
        t0 = utc_now()
        try:
            status, body, headers = fetch(url)
        except Exception as exc:  # network failure is recorded, not hidden
            status, body, headers = 0, b"", {"error": f"{type(exc).__name__}: {exc}"}
        if status == 200 and body:
            fetched_ok += 1
        sha = hashlib.sha256(body).hexdigest()
        entry = {
            "captured_at_utc": t0, "returned_at_utc": utc_now(), "run_id": run_id,
            "season": args.season, "week": week, "url": url, "http_status": status,
            "bytes": len(body), "sha256": sha,
            "server_date": headers.get("Date"), "last_modified": headers.get("Last-Modified"),
            "body_file": None, "body_new": False, "parsed_file": None,
            "tables": 0, "rows": 0, "teams": 0, "flags": [], "alarm": False,
        }
        if status == 200 and body:
            new_body = write_once(os.path.join(base, "bodies", f"{sha}.html.gz"),
                                  gzip.compress(body, mtime=0))
            entry["body_file"] = f"bodies/{sha}.html.gz"
            entry["body_new"] = new_body
            parsed = parse_report(body.decode("utf-8", errors="replace"), args.season, week)
            entry["declared_week"] = parsed["declared_week"]
            entry["parser_version"] = PARSER_VERSION
            entry.update({"tables": parsed["tables"], "rows": len(parsed["rows"]),
                          "teams": len(parsed["teams"]), "flags": list(parsed["flags"])})
            if parsed["tables"] == 0:
                entry["flags"].append("no_tables")
            week_alarms = list(parsed["alarms"])
            if parsed["tables"] == 0 and had_tables.get(week):
                week_alarms.append("page carried tables before and has none now")
            if parsed["tables"] > 0 and not parsed["rows"]:
                week_alarms.append("tables present but zero data rows")
            if week_alarms:
                entry["alarm"] = True
                entry["alarm_detail"] = week_alarms
                alarms += [f"week {week}: {a}" for a in week_alarms]
            if parsed["tables"] > 0:
                had_tables[week] = True
            # An echo (requested week N, page shows another week) is stored and flagged but not
            # parsed into week N's rows: its content belongs to the week it shows.
            echo = entry.get("declared_week") is not None and entry["declared_week"] != week
            if parsed["tables"] > 0 and not week_alarms and not echo:
                fname = f"{sha}.v{PARSER_VERSION}.json"
                entry["parsed_file"] = f"parsed/{fname}"
                write_once(os.path.join(base, "parsed", fname),
                           (json.dumps(parsed, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
                prev = last_parsed.get(week)
                if prev and prev["parsed_file"] != entry["parsed_file"]:
                    with open(os.path.join(base, prev["parsed_file"]), encoding="utf-8") as fh:
                        old_doc = json.load(fh)
                    for ch in diff_rows(old_doc, parsed):
                        new_deltas.append({"captured_at_utc": t0, "season": args.season, "week": week,
                                           "from_sha256": prev["sha256"], "to_sha256": sha, **ch})
                last_parsed[week] = entry
        else:
            entry["flags"].append(f"http_{status}" if status else "fetch_error")
            if status == 404:
                entry["flags"].append("not_published_or_not_found")
        new_manifest.append(entry)
        state[str(week)] = {
            "last_fetch_utc": t0, "http_status": status, "sha256": sha,
            "rows": entry["rows"], "teams": entry["teams"], "tables": entry["tables"],
            "body_new": entry["body_new"], "parsed_file": entry["parsed_file"],
            "declared_week": entry.get("declared_week"),
            "flags": entry["flags"], "alarm": entry["alarm"],
        }
        print(f"week {week:>2}  http {status}  bytes {len(body):>7}  sha {sha[:12]}  "
              f"tables {entry['tables']:>2}  rows {entry['rows']:>3}  "
              f"new_body {entry['body_new']!s:<5}  alarm {entry['alarm']}")
        if args.pause and n < len(weeks) - 1:
            time.sleep(args.pause)

    if weeks and fetched_ok == 0:
        alarms.append("every fetch failed (no HTTP 200 with a body)")

    append_jsonl(manifest_path, new_manifest)
    append_jsonl(deltas_path, new_deltas)
    status_doc = {
        "run_started_utc": run_started, "run_finished_utc": utc_now(), "run_id": run_id,
        "season": args.season, "source": SOURCE_URL.format(season=args.season, week="{week}"),
        "weeks_requested": weeks, "weeks_with_fetch_200": fetched_ok,
        "new_bodies": sum(1 for e in new_manifest if e["body_new"]),
        "deltas_appended": len(new_deltas), "alarms": alarms, "weeks": state,
    }
    os.makedirs(base, exist_ok=True)
    with open(status_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(status_doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n")

    print(f"manifest lines appended {len(new_manifest)}; new bodies "
          f"{status_doc['new_bodies']}; deltas appended {len(new_deltas)}")
    if alarms:
        for a in alarms:
            print(f"{ALARM}: {a}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
