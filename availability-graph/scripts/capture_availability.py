#!/usr/bin/env python3
"""Capture official NFL availability evidence: Game Books, club rosters, depth-chart sources.

Designed to run on a GitHub-hosted runner (the authoring sandbox cannot reach nfl.com).

What it does
------------
1. For each requested week it reads the official NFL schedule page
   (https://www.nfl.com/schedules/<season>/by-week/week-<w>) and extracts the official games:
   slug, clubs, kickoff slot, date and final score when the page states them.
2. For each game it reads the official Game Center page (https://www.nfl.com/games/<slug>) and
   follows the official Game Book PDF link that page publishes.
3. For each Game Book PDF it keeps the raw bytes (SHA-256) and extracts, with `pdftotext -layout`:
   the date and venue, the roof/surface line, the game-day weather, the official starting lineups
   (both clubs, offense and defense), the substitution list, the Did-Not-Play list and the
   Not-Active list.
4. For each of the 32 clubs it reads the official NFL.com team roster page and records every
   player's official roster status (ACTIVE / RESERVE / INJURED RESERVE / ...) and the club's own
   official depth-chart URL as published on that page.
5. It reads each club depth-chart page and records what is actually there: HTTP status, SHA-256,
   whether the depth information is a machine-readable table or an image, and whether the club
   labels the chart "unofficial".

What it does NOT do
-------------------
It does not infer a starter, a depth rank, a snap count, a replacement tier, a replacement or a
game status. It does not fill blanks. A section that cannot be parsed is recorded as a failure in
the manifest (with a bounded excerpt of the extracted text) and the run exits non-zero.

Outputs
-------
  --raw-dir      raw bytes (uploaded as a workflow artifact, i.e. kept outside the static site)
  --data-dir     parsed registers (committed)
  --manifest-dir hash/count manifests (committed)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser

UA = "availability-capture/1.0 (+https://github.com/karagemop466-tech/Korea2)"

# Club slug (as used on nfl.com) -> (abbreviation, full name). The abbreviation is only a label;
# every captured row carries the official URL it came from.
CLUBS = {
    "arizona-cardinals": ("AZ", "Arizona Cardinals"),
    "atlanta-falcons": ("ATL", "Atlanta Falcons"),
    "baltimore-ravens": ("BAL", "Baltimore Ravens"),
    "buffalo-bills": ("BUF", "Buffalo Bills"),
    "carolina-panthers": ("CAR", "Carolina Panthers"),
    "chicago-bears": ("CHI", "Chicago Bears"),
    "cincinnati-bengals": ("CIN", "Cincinnati Bengals"),
    "cleveland-browns": ("CLE", "Cleveland Browns"),
    "dallas-cowboys": ("DAL", "Dallas Cowboys"),
    "denver-broncos": ("DEN", "Denver Broncos"),
    "detroit-lions": ("DET", "Detroit Lions"),
    "green-bay-packers": ("GB", "Green Bay Packers"),
    "houston-texans": ("HOU", "Houston Texans"),
    "indianapolis-colts": ("IND", "Indianapolis Colts"),
    "jacksonville-jaguars": ("JAX", "Jacksonville Jaguars"),
    "kansas-city-chiefs": ("KC", "Kansas City Chiefs"),
    "las-vegas-raiders": ("LV", "Las Vegas Raiders"),
    "los-angeles-chargers": ("LAC", "Los Angeles Chargers"),
    "los-angeles-rams": ("LAR", "Los Angeles Rams"),
    "miami-dolphins": ("MIA", "Miami Dolphins"),
    "minnesota-vikings": ("MIN", "Minnesota Vikings"),
    "new-england-patriots": ("NE", "New England Patriots"),
    "new-orleans-saints": ("NO", "New Orleans Saints"),
    "new-york-giants": ("NYG", "New York Giants"),
    "new-york-jets": ("NYJ", "New York Jets"),
    "philadelphia-eagles": ("PHI", "Philadelphia Eagles"),
    "pittsburgh-steelers": ("PIT", "Pittsburgh Steelers"),
    "san-francisco-49ers": ("SF", "San Francisco 49ers"),
    "seattle-seahawks": ("SEA", "Seattle Seahawks"),
    "tampa-bay-buccaneers": ("TB", "Tampa Bay Buccaneers"),
    "tennessee-titans": ("TEN", "Tennessee Titans"),
    "washington-commanders": ("WAS", "Washington Commanders"),
}
SLUG_TO_ABBR = {slug: abbr for slug, (abbr, _) in CLUBS.items()}
ABBR_TO_FULL = {abbr: full for _, (abbr, full) in CLUBS.items()}
SLUG_TO_FULL = {slug: full for slug, (_, full) in CLUBS.items()}

# Official roster status codes printed by the NFL.com team roster page.
ROSTER_STATUS = {
    "ACT", "RES", "IR", "DEV", "PUP", "RSR", "TRD", "TRT", "PS", "NTR", "UDF", "UIR", "NFI",
    "JPS", "WAX", "MIL", "RET",
}

GAMEBOOK_PDF_RE = re.compile(r"https://static\.www\.nfl\.com/image/upload/[^\"'\s<>]+?\.pdf", re.I)
GAME_URL_RE = re.compile(r"/games/([a-z0-9\-]+-at-[a-z0-9\-]+-\d{4}-reg-\d+)", re.I)
SCORE_RE = re.compile(
    r"(?P<away>[A-Z][A-Za-z'&.]{1,20}(?:\s+[A-Z][A-Za-z'&.]{1,20})?)\s+(?P<ascore>\d{1,3}),\s+"
    r"(?P<home>[A-Z][A-Za-z'&.]{1,20}(?:\s+[A-Z][A-Za-z'&.]{1,20})?)\s+(?P<hscore>\d{1,3}),\s+"
    r"(?P<status>FINAL|Final|SCHEDULED|Scheduled|POSTPONED|Postponed)"
)
SLOT_RE = re.compile(
    r"(?P<day>Thursday|Friday|Saturday|Sunday|Monday|Tuesday|Wednesday)[^|]{0,24}?"
    r"\b(?P<tz>EST|EDT|CST|CDT|MST|MDT|PST|PDT)\b[^)]{0,40}\((?P<broadcast>[^)]{0,120})\)"
)

# A lineup cell: position label, jersey number, player name. Position labels on an NFL game book
# are 1-3 capital letters, optionally prefixed by a digit (3QB).
CELL_RE = re.compile(
    r"^(?P<pos>\d?[A-Z]{1,3})\s+(?P<num>\d{1,2})\s+"
    r"(?P<name>[A-Za-z][A-Za-z'\.\-]*(?:\s+[A-Za-z][A-Za-z'\.\-]*)*)$"
)
ENTRY_RE = re.compile(
    r"^(?P<pos>\d?[A-Z]{1,3})\s+(?P<num>\d{1,2})\s+"
    r"(?P<name>[A-Za-z][A-Za-z'\.\-]*(?:\s+[A-Za-z][A-Za-z'\.\-]*)*)$"
)


# --------------------------------------------------------------------------- fetch helpers
def fetch(url: str, out_path: str | None = None, timeout: int = 60):
    """GET a URL, keep the raw bytes, return (manifest record, body)."""
    rec = {
        "url": url,
        "final_url": url,
        "status": None,
        "content_type": None,
        "bytes": 0,
        "sha256": None,
        "fetched_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "error": None,
    }
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    body = b""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            rec["status"] = resp.status
            rec["final_url"] = resp.geturl()
            rec["content_type"] = resp.headers.get("Content-Type")
    except urllib.error.HTTPError as exc:
        rec["status"] = exc.code
        rec["error"] = f"HTTPError {exc.code}"
    except Exception as exc:                                   # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
    rec["bytes"] = len(body)
    rec["sha256"] = hashlib.sha256(body).hexdigest() if body else None
    if out_path and body:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as fh:
            fh.write(body)
    return rec, body


def pdf_to_text(pdf_bytes: bytes, out_txt: str | None = None):
    """Extract layout-preserving text from a PDF. Returns (text, method)."""
    last = "pdftotext unavailable"
    if shutil.which("pdftotext"):
        try:
            proc = subprocess.run(["pdftotext", "-layout", "-", "-"], input=pdf_bytes,
                                  capture_output=True, timeout=180)
            if proc.returncode == 0 and proc.stdout:
                text = proc.stdout.decode("utf-8", "replace")
                if out_txt:
                    with open(out_txt, "w", encoding="utf-8") as fh:
                        fh.write(text)
                return text, "pdftotext-layout"
            last = "pdftotext returned no output"
        except Exception as exc:                               # noqa: BLE001
            last = f"pdftotext failed: {exc}"
    try:
        import io
        from pypdf import PdfReader                            # type: ignore
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        if out_txt:
            with open(out_txt, "w", encoding="utf-8") as fh:
                fh.write(text)
        return text, "pypdf"
    except Exception as exc:                                   # noqa: BLE001
        return "", f"{last}; pypdf failed: {exc}"


# --------------------------------------------------------------------------- html helpers
class TableParser(HTMLParser):
    """Collect every table as {header, rows}; rows are lists of cell texts in document order."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[dict] = []
        self.links: list[tuple[str, str]] = []      # (href, text)
        self._table = None
        self._row = None
        self._cell = None
        self._cell_link = None
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag == "table":
            self._table = {"header": [], "rows": []}
            self.tables.append(self._table)
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            self._cell_link = None
            self._in_cell = True
        elif tag == "a" and self._in_cell:
            self._cell_link = ad.get("href")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            if self._cell_link:
                self.links.append((self._cell_link, self._row[-1]))
            self._cell = None
            self._cell_link = None
            self._in_cell = False
        elif tag == "tr" and self._table is not None and self._row is not None:
            if self._row:
                self._table["rows"].append(self._row)
            self._row = None
        elif tag == "table":
            self._table = None

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self._in_cell and self._cell is not None:
            self._cell.append(data)


def strip_tags(html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#39;", "'")
                .replace("&quot;", '"').replace("&#x27;", "'"))
    return re.sub(r"\s+", " ", text)


# --------------------------------------------------------------------------- schedule parse
def parse_schedule(html: str, season: str, week: str) -> list[dict]:
    """Extract the official games of one week from the official schedule page."""
    games: dict[str, dict] = {}
    for m in GAME_URL_RE.finditer(html):
        slug = m.group(1)
        if not slug.endswith(f"-reg-{week}"):
            continue
        if slug in games:
            continue
        parts = slug.split("-at-")
        away_slug = parts[0]
        home_slug = parts[1].rsplit(f"-{season}-reg-{week}", 1)[0]
        games[slug] = {
            "slug": slug,
            "game_url": f"https://www.nfl.com/games/{slug}",
            "away_team": SLUG_TO_ABBR.get(away_slug, away_slug),
            "home_team": SLUG_TO_ABBR.get(home_slug, home_slug),
            "away_score": "", "home_score": "", "status": "", "slot": "", "broadcast": "",
            "date_text": "", "source_url": f"https://www.nfl.com/schedules/{season}/by-week/week-{week}",
        }
    if not games:
        return []
    # Scores: the page prints "Steelers 18, Bengals 38, FINAL, Sunday, November 15th" next to the
    # game link. A score is only accepted when the printed club names match the game slug.
    plain = strip_tags(html)
    for sm in SCORE_RE.finditer(plain):
        away_txt, home_txt = sm.group("away"), sm.group("home")
        for game in games.values():
            away_full = SLUG_TO_FULL.get(game["away_team"], "")
            home_full = SLUG_TO_FULL.get(game["home_team"], "")
            if not away_full or not home_full:
                continue
            away_last = away_full.split()[-1].lower()
            home_last = home_full.split()[-1].lower()
            if away_last not in away_txt.lower() or home_last not in home_txt.lower():
                continue
            if game["away_score"]:
                continue
            game["away_score"] = sm.group("ascore")
            game["home_score"] = sm.group("hscore")
            game["status"] = sm.group("status").upper()
            break
    # Kickoff slot: "Sunday 8:20 PM EST (NBC, Universo)".
    for km in SLOT_RE.finditer(plain):
        window = plain[max(0, km.start() - 400): km.end() + 400]
        for game in games.values():
            if game["slot"] or game["away_team"] not in window:
                continue
            game["slot"] = f"{km.group('day')} {km.group('tz')}"
            game["broadcast"] = km.group("broadcast").strip()
            break
    # Date: "Nov 15" style text next to the game.
    for game in games.values():
        m = re.search(r"(January|February|March|April|May|June|July|August|September|October|"
                      r"November|December)\s+(\d{1,2})", plain)
        if m:
            game["date_text"] = f"{m.group(1)} {m.group(2)}"
            break
    return list(games.values())


# --------------------------------------------------------------------------- game book parse
def split_cells(line: str) -> list[str]:
    """Split a table line into its columns.

    Handles the two shapes an extracted game-book row can take:
      * a markdown row  ``| LT | 66 W.Campbell | OLB | 5 Dr.Jones |``  (position and number/name
        are separate cells);
      * a layout row    ``LT 66 W.Campbell     OLB 5 Dr.Jones``       (cells separated by 2+ spaces).
    Empty markdown cells are preserved so that a two-club row keeps its alignment.
    """
    if "|" in line:
        return [p.strip() for p in line.strip().strip("|").split("|")]
    return [p.strip() for p in re.split(r"\s{2,}", line.strip())]


def logical_columns(cells: list[str]) -> list[str] | None:
    """Return the four logical lineup columns (away off, away def, home off, home def).

    A game-book lineup row can be extracted as 4 cells (one per column), as 8 cells (position and
    number/name separate) or as 12 cells (position, number and name separate).
    """
    cells = list(cells)
    while cells and cells[-1] == "":
        cells.pop()
    if len(cells) == 4:
        return cells
    if len(cells) == 8:
        return [f"{cells[0]} {cells[1]}".strip(), f"{cells[2]} {cells[3]}".strip(),
                f"{cells[4]} {cells[5]}".strip(), f"{cells[6]} {cells[7]}".strip()]
    if len(cells) == 12:
        return [" ".join(cells[i:i + 3]).strip() for i in range(0, 12, 3)]
    return None


def parse_cell(cell: str):
    cell = cell.strip()
    m = CELL_RE.match(cell)
    if not m:
        return None
    return {"pos": m.group("pos"), "num": m.group("num"), "name": m.group("name").strip()}


def norm_line(line: str) -> str:
    """A table line reduced to its text (markdown pipes removed)."""
    return line.strip().strip("|").strip()


def find_section(lines: list[str], header: str):
    """Return (start, end) line indexes of a game-book section."""
    start = None
    for i, line in enumerate(lines):
        if norm_line(line).lower().startswith(header.lower()):
            start = i + 1
            break
    if start is None:
        return -1, -1
    end = len(lines)
    for j in range(start, len(lines)):
        low = norm_line(lines[j]).lower()
        if low.startswith(("substitutions", "did not play", "not active", "field goals",
                           "scoring plays", "paid attendance", "final individual statistics",
                           "individual statistics")):
            end = j
            break
    return start, end


def parse_lineups(text: str) -> dict:
    """Parse the official starting lineups of both clubs out of the game-book text."""
    lines = text.splitlines()
    start, end = find_section(lines, "Lineups")
    result = {"ok": False, "rows": [], "note": ""}
    if start < 0:
        result["note"] = "no Lineups section"
        return result
    header_idx = -1
    for i in range(start, min(end, start + 12)):
        low = norm_line(lines[i]).lower()
        if low.count("offense") >= 2 and low.count("defense") >= 2:
            header_idx = i
            break
    if header_idx < 0:
        result["note"] = "no Offense/Defense header row"
        return result
    body = []
    for line in lines[header_idx + 1: end]:
        if not line.strip():
            continue
        cols = logical_columns(split_cells(line))
        if cols and all(parse_cell(c) for c in cols):
            body.append(cols)
        elif body:
            break
    if len(body) < 10:
        result["note"] = f"only {len(body)} four-column lineup rows parsed"
        return result
    for row in body[:22]:
        for col, cell_text in enumerate(row):
            cell = parse_cell(cell_text)
            result["rows"].append({
                "col": col,                     # 0 away off, 1 away def, 2 home off, 3 home def
                "unit": "offense" if col % 2 == 0 else "defense",
                "pos": cell["pos"], "num": cell["num"], "name": cell["name"],
            })
    result["ok"] = len(result["rows"]) >= 20
    result["note"] = f"{len(body)} lineup rows"
    return result


def parse_player_list(block: str) -> list[dict]:
    """Parse a comma separated 'POS NUM Name' list (substitutions / did not play / not active)."""
    entries = []
    for chunk in re.split(r",(?=\s)", block or ""):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = ENTRY_RE.match(chunk)
        if not m:
            continue
        entries.append({"pos": m.group("pos"), "num": m.group("num"), "name": m.group("name").strip()})
    return entries


def split_two_columns(block_lines: list[str]):
    """Split a two-column block (one column per club) into its two texts.

    A markdown row keeps its alignment (``| left |  | right |``); a layout row is split on the
    widest run of whitespace.
    """
    if any("|" in ln for ln in block_lines):
        lefts, rights = [], []
        for line in block_lines:
            if not line.strip() or "|" not in line:
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3:
                lefts.append(cells[0])
                rights.append(cells[2])
        if lefts:
            return " ".join(x for x in lefts if x), " ".join(x for x in rights if x)
    best_idx, best_gap = None, 0
    for line in block_lines:
        if not line.strip():
            continue
        for m in re.finditer(r"\s{2,}", line):
            if m.end() - m.start() > best_gap:
                best_gap = m.end() - m.start()
                best_idx = m.start()
        if best_gap:
            break
    if best_idx is None:
        return "\n".join(block_lines), ""
    left, right = [], []
    for line in block_lines:
        if not line.strip():
            continue
        cut = min(best_idx, len(line))
        left.append(line[:cut])
        right.append(line[cut:])
    return " ".join(left), " ".join(right)


def parse_gamebook(text: str) -> dict:
    """Extract everything this project needs from one official Game Book."""
    lines = text.splitlines()
    out: dict = {"sections": {}, "date_text": "", "venue": "", "start_time": "", "weather": "",
                 "temp": "", "humidity": "", "wind": "", "roof": "", "surface": "", "attendance": ""}
    head = "\n".join(lines[:60])
    m = re.search(r"Date:\s*(?P<date>[A-Za-z]+,\s*\d{1,2}/\d{1,2}/\d{4})(?P<rest>[^\n|]*)", head)
    if m:
        out["date_text"] = m.group("date").strip()
        rest = re.split(r"\s{2,}", m.group("rest").strip())[0]
        out["venue"] = rest.rsplit(" at ", 1)[-1].strip() if " at " in rest else rest
    else:
        out["date_text"] = ""
        out["venue"] = ""
    # Head fields are read cell by cell: a game book prints one fact per line or per table cell.
    for line in lines[:60]:
        for cell in line.split("|"):
            raw = cell.strip()
            if not raw:
                continue
            if "Start Time:" in raw:
                out["start_time"] = raw.split("Start Time:", 1)[1].strip().rstrip("|").strip()
            if "Game Weather:" in raw:
                out["weather"] = raw.split("Game Weather:", 1)[1].strip().rstrip("|").strip()
            mm = re.search(r"Temp:\s*(.+?)(?:\s+Humidity:|$)", raw)
            if mm:
                out["temp"] = mm.group(1).strip().rstrip("|").strip()
            mm = re.search(r"Humidity:\s*([^,|]+)", raw)
            if mm:
                out["humidity"] = mm.group(1).strip()
            mm = re.search(r"Wind:\s*(.+?)(?:\s*\||$)", raw)
            if mm:
                out["wind"] = mm.group(1).strip()
    rm = re.search(r"(?P<roof>[A-Z][A-Za-z ]*?Stadium)\s+on\s+(?P<surface>Natural Grass|Artificial Turf)",
                   head)
    out["roof"] = rm.group("roof").strip() if rm else ""
    out["surface"] = rm.group("surface").strip() if rm else ""
    am = re.search(r"Paid Attendance:\s*(?P<a>[\d,]+)", text)
    out["attendance"] = am.group("a").strip() if am else ""
    out["lineups"] = parse_lineups(text)
    for section, key in (("Substitutions", "substitutions"), ("Did Not Play", "did_not_play"),
                         ("Not Active", "not_active")):
        s, e = find_section(lines, section)
        if s < 0:
            out["sections"][key] = {"ok": False, "note": f"no {section} section", "away": [], "home": []}
            continue
        block = [ln for ln in lines[s:e] if ln.strip()]
        left, right = split_two_columns(block)
        out["sections"][key] = {
            "ok": True,
            "note": f"{len(block)} lines",
            "away": parse_player_list(left),
            "home": parse_player_list(right),
            "raw_left": " ".join(left)[:900],
            "raw_right": " ".join(right)[:900],
        }
    return out


# --------------------------------------------------------------------------- club pages
def parse_roster(html: str) -> list[dict]:
    """Parse the official NFL.com team roster table.

    The table is printed as: player | jersey | position | status | height (in inches) | weight |
    experience | college. A row is accepted only when the whole signature matches, so that no
    other table on the page can be mistaken for a roster row. The status is kept as printed
    (ACTIVE, RES, IR, DEV, PUP, RSR, TRD, TRT, TRC, ...); it is never translated.
    """
    parser = TableParser()
    parser.feed(html)
    rows = []
    for table in parser.tables:
        for cells in table["rows"]:
            if len(cells) < 6:
                continue
            jersey, position, status = cells[1].strip(), cells[2].strip(), cells[3].strip()
            height, weight = cells[4].strip(), cells[5].strip()
            if jersey and not jersey.isdigit():
                continue
            if not re.fullmatch(r"[A-Z]{1,3}", position):
                continue
            if not re.fullmatch(r"[A-Z]{2,4}", status):
                continue
            if not height.isdigit() or not weight.isdigit():
                continue
            rows.append({
                "player": cells[0].strip(),
                "jersey": jersey,
                "position": position,
                "status": status,
                "height": height,
                "weight": weight,
            })
    return rows


def find_depth_url(html: str) -> str:
    """The club's own official depth-chart URL, as linked from the NFL.com roster page."""
    parser = TableParser()
    parser.feed(html)
    best = ""
    for href, text in parser.links:
        if "depth" in href.lower() and "depth" in text.lower():
            best = href
            break
    if not best:
        for href, _ in parser.links:
            if "depth" in href.lower():
                best = href
                break
    if best.startswith("/"):
        return "https://www.nfl.com" + best
    return best


def classify_depth_page(html: str) -> dict:
    """Describe what a club depth-chart page actually publishes (no inference)."""
    parser = TableParser()
    parser.feed(html)
    text = strip_tags(html)
    headers = []
    for table in parser.tables:
        for cells in table["rows"]:
            joined = " ".join(cells).lower()
            if any(k in joined for k in ("quarterback", "wide receiver", "left tackle", "running back",
                                         "tight end", "defensive end", "middle linebacker",
                                         "left guard", "right guard")):
                headers = cells
                break
        if headers:
            break
    image_srcs = re.findall(r'<img[^>]+src="([^"]+)"', html, flags=re.I)
    return {
        "has_depth_table": bool(headers),
        "table_header_cells": headers,
        "image_count": len(image_srcs),
        "image_srcs": image_srcs[:12],
        "mentions_unofficial": "unofficial depth chart" in text.lower(),
        "text_sample": text[:400],
    }


# --------------------------------------------------------------------------- main
def write_csv(path: str, rows: list[dict]) -> None:
    if not rows:
        return
    keys = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def main() -> int:
    try:
        return run()
    except Exception:                                            # noqa: BLE001
        import traceback
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        args = sys.argv[1:]
        manifest_dir = "availability-graph/manifests"
        for i, a in enumerate(args):
            if a == "--manifest-dir" and i + 1 < len(args):
                manifest_dir = args[i + 1]
        os.makedirs(manifest_dir, exist_ok=True)
        path = os.path.join(manifest_dir, f"capture_error_{stamp}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({
                "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": "error",
                "traceback": traceback.format_exc(),
            }, fh, indent=2)
        traceback.print_exc()
        print(f"capture failed; diagnostics written to {path}", file=sys.stderr)
        return 2


def run() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2026")
    ap.add_argument("--weeks", default="9,10")
    ap.add_argument("--raw-dir", default="")
    ap.add_argument("--data-dir", default="availability-graph/data")
    ap.add_argument("--manifest-dir", default="availability-graph/manifests")
    ap.add_argument("--skip-rosters", action="store_true")
    ap.add_argument("--skip-depth", action="store_true")
    ap.add_argument("--delay", type=float, default=0.6)
    args = ap.parse_args()

    season = args.season
    weeks = [w.strip() for w in args.weeks.split(",") if w.strip()]
    raw_dir = args.raw_dir or os.path.join("availability-graph", "raw")
    os.makedirs(args.data_dir, exist_ok=True)
    os.makedirs(args.manifest_dir, exist_ok=True)
    os.makedirs(raw_dir, exist_ok=True)

    manifest = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": season,
        "weeks": weeks,
        "requests": [],
        "failures": [],
        "counts": {},
    }
    failures: list[str] = []
    log_path = os.path.join(args.manifest_dir, "capture_log.txt")

    def log(message: str) -> None:
        line = f"{dt.datetime.now(dt.timezone.utc).strftime('%H:%M:%S')} {message}"
        print(line, flush=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    games_rows, lineup_rows, inactive_rows, sub_rows = [], [], [], []

    def raw_path(name: str) -> str:
        return os.path.join(raw_dir, name)

    for week in weeks:
        sched_url = f"https://www.nfl.com/schedules/{season}/by-week/week-{week}"
        rec, body = fetch(sched_url, raw_path(f"schedule_{season}_reg{week}.html"))
        manifest["requests"].append(rec)
        if not body:
            failures.append(f"schedule week {week}: {rec.get('error')}")
            continue
        games = parse_schedule(body.decode("utf-8", "replace"), season, week)
        manifest["counts"][f"week{week}_games"] = len(games)
        log(f"week {week}: {len(games)} official games on the schedule page")
        if not games:
            failures.append(f"schedule week {week}: no game links found")
            continue
        for game in games:
            slug = game["slug"]
            game_url = game["game_url"]
            rec, body = fetch(game_url, raw_path(f"gamecenter_{slug}.html"))
            manifest["requests"].append(rec)
            time.sleep(args.delay)
            if not body:
                failures.append(f"game {slug}: {rec.get('error')}")
                continue
            ghtml = body.decode("utf-8", "replace")
            pdfs = GAMEBOOK_PDF_RE.findall(ghtml)
            if not pdfs:
                failures.append(f"game {slug}: no Game Book PDF link on the official game centre page")
                continue
            pdf_url = pdfs[0]
            rec, body = fetch(pdf_url, raw_path(f"gamebook_{slug}.pdf"))
            manifest["requests"].append(rec)
            time.sleep(args.delay)
            if not body:
                failures.append(f"gamebook {slug}: {rec.get('error')}")
                continue
            text, method = pdf_to_text(body, raw_path(f"gamebook_{slug}.txt"))
            if not text.strip():
                failures.append(f"gamebook {slug}: no extractable text ({method})")
                continue
            gb = parse_gamebook(text)
            away, home = game["away_team"], game["home_team"]
            log(f"week {week} {slug}: lineups={'ok' if gb['lineups']['ok'] else 'FAILED'} "
                f"({gb['lineups']['note']}); method={method}")
            games_rows.append({
                "season": season, "week": week, "slug": slug,
                "game_url": game_url, "gamebook_url": pdf_url,
                "away_team": away, "home_team": home,
                "away_score": game["away_score"], "home_score": game["home_score"],
                "status": game["status"], "slot": game["slot"], "broadcast": game["broadcast"],
                "gamebook_date": gb.get("date_text", ""), "venue_text": gb.get("venue", ""),
                "start_time": gb.get("start_time", ""),
                "roof": gb.get("roof", ""), "surface": gb.get("surface", ""),
                "weather": gb.get("weather", ""), "temp": gb.get("temp", ""),
                "humidity": gb.get("humidity", ""), "wind": gb.get("wind", ""),
                "attendance": gb.get("attendance", ""),
                "pdf_sha256": rec.get("sha256"), "pdf_bytes": rec.get("bytes"),
                "text_method": method,
                "lineups_parsed": "yes" if gb["lineups"]["ok"] else "no",
                "captured_utc": rec.get("fetched_utc"),
            })
            if gb["lineups"]["ok"]:
                for r in gb["lineups"]["rows"]:
                    team = away if r["col"] in (0, 1) else home
                    lineup_rows.append({
                        "season": season, "week": week, "slug": slug, "game_url": game_url,
                        "team": team, "unit": r["unit"], "slot": r["pos"], "jersey": r["num"],
                        "player": r["name"], "source_url": pdf_url, "captured_utc": rec.get("fetched_utc"),
                    })
            else:
                failures.append(f"gamebook {slug}: lineups not parsed ({gb['lineups']['note']})")
            for key in ("did_not_play", "not_active"):
                sec = gb["sections"][key]
                if not sec["ok"]:
                    failures.append(f"gamebook {slug}: {key} section not found")
                    continue
                for side, team in ((0, away), (1, home)):
                    for p in sec[side]:
                        inactive_rows.append({
                            "season": season, "week": week, "slug": slug, "game_url": game_url,
                            "team": team, "category": key, "position": p["pos"], "jersey": p["num"],
                            "player": p["name"], "source_url": pdf_url,
                            "captured_utc": rec.get("fetched_utc"),
                        })
            sec = gb["sections"]["substitutions"]
            if sec["ok"]:
                for side, team in ((0, away), (1, home)):
                    for p in sec[side]:
                        sub_rows.append({
                            "season": season, "week": week, "slug": slug, "game_url": game_url,
                            "team": team, "position": p["pos"], "jersey": p["num"], "player": p["name"],
                            "source_url": pdf_url, "captured_utc": rec.get("fetched_utc"),
                        })
            else:
                failures.append(f"gamebook {slug}: substitutions section not found")

    roster_rows: list[dict] = []
    depth_rows: list[dict] = []
    if not args.skip_rosters:
        for slug, (abbr, _full) in CLUBS.items():
            url = f"https://www.nfl.com/teams/{slug}/roster"
            rec, body = fetch(url, raw_path(f"roster_{abbr}.html"))
            manifest["requests"].append(rec)
            time.sleep(args.delay)
            if not body:
                failures.append(f"roster {abbr}: {rec.get('error')}")
                depth_rows.append({
                    "club": abbr, "club_slug": slug, "roster_url": url, "depth_url": "",
                    "depth_http_status": None, "depth_sha256": None, "depth_has_table": None,
                    "depth_table_headers": "", "depth_image_count": None,
                    "depth_mentions_unofficial": None, "depth_text_sample": "",
                    "depth_image_srcs": "", "roster_rows": 0,
                    "captured_utc": rec.get("fetched_utc"),
                    "note": f"roster fetch failed: {rec.get('error')}",
                })
                continue
            html = body.decode("utf-8", "replace")
            depth_url = find_depth_url(html)
            rows = parse_roster(html)
            log(f"roster {abbr}: {len(rows)} players parsed; depth url={depth_url or '(none)'}")
            for r in rows:
                roster_rows.append({
                    "season": season, "club": abbr, "club_slug": slug, "player": r["player"],
                    "jersey": r["jersey"], "position": r["position"], "status": r["status"],
                    "height": r["height"], "weight": r["weight"],
                    "source_url": url, "captured_utc": rec.get("fetched_utc"),
                })
            if not rows:
                failures.append(f"roster {abbr}: no roster rows parsed")
            depth_rows.append({
                "club": abbr, "club_slug": slug, "roster_url": url, "depth_url": depth_url,
                "depth_http_status": None, "depth_sha256": None, "depth_has_table": None,
                "depth_table_headers": "", "depth_image_count": None,
                "depth_mentions_unofficial": None, "depth_text_sample": "",
                "depth_image_srcs": "", "roster_rows": len(rows),
                "captured_utc": rec.get("fetched_utc"),
                "note": "" if depth_url else "no depth-chart link found on the NFL.com roster page",
            })

    if not args.skip_depth:
        for row in depth_rows:
            depth_url = row.get("depth_url") or ""
            if not depth_url:
                continue
            rec, body = fetch(depth_url, raw_path(f"depth_{row['club']}.html"))
            manifest["requests"].append(rec)
            time.sleep(args.delay)
            row["depth_http_status"] = rec.get("status")
            row["depth_sha256"] = rec.get("sha256")
            log(f"depth {row['club']}: {rec.get('status')} {depth_url}")
            if body:
                html = body.decode("utf-8", "replace")
                info = classify_depth_page(html)
                row["depth_has_table"] = "yes" if info["has_depth_table"] else "no"
                row["depth_table_headers"] = " | ".join(info["table_header_cells"])[:400]
                row["depth_image_count"] = info["image_count"]
                row["depth_mentions_unofficial"] = "yes" if info["mentions_unofficial"] else "no"
                row["depth_text_sample"] = info["text_sample"]
                row["depth_image_srcs"] = " | ".join(info["image_srcs"])[:600]
            else:
                row["note"] = (row["note"] + "; " if row["note"] else "") + \
                    f"depth page fetch failed: {rec.get('error')}"

    write_csv(os.path.join(args.data_dir, "gamebooks.csv"), games_rows)
    write_csv(os.path.join(args.data_dir, "lineups.csv"), lineup_rows)
    write_csv(os.path.join(args.data_dir, "inactives.csv"), inactive_rows)
    write_csv(os.path.join(args.data_dir, "substitutions.csv"), sub_rows)
    write_csv(os.path.join(args.data_dir, "roster_status.csv"), roster_rows)
    write_csv(os.path.join(args.data_dir, "depth_sources.csv"), depth_rows)

    manifest["counts"].update({
        "gamebooks": len(games_rows), "lineup_rows": len(lineup_rows),
        "inactive_rows": len(inactive_rows), "substitution_rows": len(sub_rows),
        "roster_rows": len(roster_rows), "depth_rows": len(depth_rows),
    })
    manifest["failures"] = failures
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(args.manifest_dir, f"capture_{season}_wk{'-'.join(weeks)}_{stamp}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)

    print(json.dumps(manifest["counts"], indent=2))
    if failures:
        print(f"FAILURES ({len(failures)}):", file=sys.stderr)
        for f in failures[:60]:
            print("  -", f, file=sys.stderr)
        return 1
    print("capture complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
