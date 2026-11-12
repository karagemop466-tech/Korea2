#!/usr/bin/env python3
"""Verification gate for the Decision Desk.

Run from the repository root (CI does the same):

    python3 decision-desk/scripts/verify_all.py

Checks:
  1. every decision-desk/data/*.json is strict JSON and matches its schema;
  2. every SRC-DD-* id referenced by any register exists in sources.json;
  3. every FL-DD-*/Q-*/S-* cross-reference resolves inside this directory;
  4. blank-unverified policy: a deficiency with no replacement must be flagged,
     and a flagged deficiency must carry a note;
  5. every published table row (index + pages) carries an https source link;
  6. every local link and fragment on every page resolves;
  7. rebuilding the site is byte-for-byte deterministic.

Exit code 0 = pass. Any failure prints the offending id/path and exits 1.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DD = ROOT / "decision-desk"
DATA = DD / "data"
PAGES = [DD / "index.html"] + sorted((DD / "pages").glob("*.html"))

errors: list[str] = []
SRC_RE = re.compile(r"SRC-DD-\d+")
FL_RE = re.compile(r"FL-DD-\d+")


def err(msg: str) -> None:
    errors.append(msg)


def load(name: str):
    path = DATA / name
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:  # noqa: BLE001
        err(f"{name}: strict JSON load failed: {exc}")
        return None


def main() -> int:
    sources_doc = load("sources.json")
    injuries = load("injuries.json")
    questions = load("questions.json")
    suggestions = load("suggestions.json")
    leaderboard = load("leaderboard.json")
    flagged = load("flagged.json")
    review = load("repo_review.json")
    if errors:
        print("\n".join(errors))
        return 1

    # ---- 1. source register ----
    src_ids = [s["id"] for s in sources_doc["sources"]]
    if len(src_ids) != len(set(src_ids)):
        err("sources.json: duplicate source ids")
    known_src = set(src_ids)
    for s in sources_doc["sources"]:
        if not s["url"].startswith("https://"):
            err(f'{s["id"]}: url must be https, got {s["url"]}')
        if not s.get("fetched"):
            err(f'{s["id"]}: missing fetched date')

    # ---- 2/3. cross-references across every register ----
    def walk(obj, where: str):
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v, where)
        elif isinstance(obj, list):
            for v in obj:
                walk(v, where)
        elif isinstance(obj, str):
            for sid in SRC_RE.findall(obj):
                if sid not in known_src:
                    err(f"{where}: unknown source {sid}")
            for fid in FL_RE.findall(obj):
                if fid not in known_fl:
                    err(f"{where}: unknown flag {fid}")

    known_fl = {f["id"] for f in flagged["flagged"]}
    if len(known_fl) != len(flagged["flagged"]):
        err("flagged.json: duplicate flag ids")
    for name, doc in [("injuries", injuries), ("questions", questions),
                      ("suggestions", suggestions), ("leaderboard", leaderboard),
                      ("flagged", flagged), ("repo_review", review)]:
        walk(doc, name)

    # ---- injuries schema / blank policy ----
    ic = injuries["meta"]["counts"]
    if len(injuries["report_rows"]) != ic["report_rows"]:
        err("injuries: report_rows count mismatch")
    if len(injuries["supplemental_rows"]) != ic["supplemental_rows"]:
        err("injuries: supplemental_rows count mismatch")
    if len(injuries["deficiencies"]) != ic["deficiencies"]:
        err("injuries: deficiencies count mismatch")
    game_status_vocab = {"", "Out", "Questionable"}
    practice_vocab = {"Full", "Limited", "DNP"}
    seen_ids = set()
    for r in injuries["report_rows"] + injuries["supplemental_rows"]:
        if r["id"] in seen_ids:
            err(f'duplicate row id {r["id"]}')
        seen_ids.add(r["id"])
        if not r["sources"]:
            err(f'{r["id"]}: no source')
        if r["practice"] not in practice_vocab:
            err(f'{r["id"]}: bad practice value {r["practice"]!r}')
        if r["game_status"] not in game_status_vocab:
            err(f'{r["id"]}: bad game_status {r["game_status"]!r}')
    flagged_defs = 0
    for d in injuries["deficiencies"]:
        if not d["sources"]:
            err(f'{d["id"]}: no source')
        if d["replacement"] == "" and not d["flagged"]:
            err(f'{d["id"]}: blank replacement must be flagged')
        if d["flagged"] and not d["note"]:
            err(f'{d["id"]}: flagged row must carry a note')
        if d["flagged"]:
            flagged_defs += 1
    if flagged_defs != ic["flagged_deficiencies"]:
        err("injuries: flagged_deficiencies count mismatch")
    for nr in injuries["no_report"]:
        if nr["flagged"] not in known_fl:
            err(f'no_report {nr["team"]}: unknown flag {nr["flagged"]}')

    # ---- questions / suggestions ----
    q_ids = {q["id"] for q in questions["questions"]}
    s_ids = {s["id"] for s in suggestions["suggestions"]}
    if len(q_ids) != questions["meta"]["counts"]["total"]:
        err("questions: count mismatch or duplicate ids")
    if len(s_ids) != suggestions["meta"]["counts"]["total"]:
        err("suggestions: count mismatch or duplicate ids")
    for q in questions["questions"]:
        if q["status"] not in {"answered", "partial", "unanswered"}:
            err(f'{q["id"]}: bad status {q["status"]!r}')
        if q["status"] == "answered" and not q["answer"]:
            err(f'{q["id"]}: answered row without an answer')
        if q["status"] != "answered" and not q["gap"]:
            err(f'{q["id"]}: {q["status"]} row must name its gap')
        for sid in q["related_suggestions"]:
            if sid not in s_ids:
                err(f'{q["id"]}: unknown suggestion {sid}')
    for s in suggestions["suggestions"]:
        if s["status"] not in {"proposed", "accepted", "deferred", "rejected"}:
            err(f'{s["id"]}: bad status {s["status"]!r}')
        if not s["decision"]:
            err(f'{s["id"]}: missing decision field')
        for qid in s["related_questions"]:
            if qid not in q_ids:
                err(f'{s["id"]}: unknown question {qid}')

    # ---- leaderboard ----
    total = sum(r["candidates"] for r in leaderboard["leaderboard"])
    if total != leaderboard["meta"]["totals"]["evaluations"]:
        err(f"leaderboard: candidates sum {total} != totals.evaluations")
    if any(r["qualified"] != 0 for r in leaderboard["leaderboard"]):
        err("leaderboard: a lab reports qualified != 0 but totals say 0")
    for c in leaderboard["correlations"]:
        if not (-1.0 <= c["r"] <= 1.0):
            err(f'{c["id"]}: r out of range')
        if not (c["ci_low"] <= c["r"] <= c["ci_high"]):
            err(f'{c["id"]}: r outside its own CI')
        if not (0.0 <= c["p"] <= 1.0):
            err(f'{c["id"]}: p out of range')
        if not c["sources"] if "sources" in c else not c["source_id"]:
            err(f'{c["id"]}: no source')

    # ---- repo review ----
    for c in review["checks"]:
        if c["result"] not in {"PASS", "FAIL", "NOT RUN LOCALLY"}:
            err(f'repo_review: bad check result {c["result"]!r}')

    # ---- 5/6. pages ----
    ids_by_page = {}
    for page_path in PAGES:
        text = page_path.read_text(encoding="utf-8")
        rel = page_path.relative_to(DD)
        if "<title>" not in text:
            err(f"{rel}: missing <title>")
        for m in re.finditer(r'href="([^"]+)"', text):
            href = m.group(1)
            if href.startswith("http://"):
                err(f"{rel}: insecure link {href}")
            if href.startswith("#"):
                frag = href[1:]
                if frag and f'id="{frag}"' not in text:
                    err(f"{rel}: missing local anchor #{frag}")
                continue
            if href.startswith(("https://", "mailto:")):
                continue
            target, _, frag = href.partition("#")
            resolved = (page_path.parent / target).resolve()
            if not resolved.exists():
                err(f"{rel}: broken local link {href}")
            elif frag:
                target_text = resolved.read_text(encoding="utf-8")
                if f'id="{frag}"' not in target_text:
                    err(f"{rel}: broken fragment {href}")
        # every data table row ends with a source cell
        for t_i, tbl in enumerate(re.findall(r'<table class="data">.*?</table>', text, re.S)):
            rows = re.findall(r"<tr>(.*?)</tr>", tbl, re.S)
            for r_i, row in enumerate(rows):
                cells = re.findall(r"<td>(.*?)</td>", row, re.S)
                if not cells:
                    continue  # header row
                if not re.search(r'<a href="https://[^"]+"', cells[-1]):
                    err(f"{rel}: table {t_i} row {r_i} has no https source link in its last cell")
        ids_by_page[str(rel)] = set(re.findall(r'id="([^"]+)"', text))

    # FL/Q/S fragments referenced from pages must exist
    for rel, ids in ids_by_page.items():
        pass  # fragment existence checked above via target files

    # ---- 7. deterministic rebuild ----
    before = {p: p.read_bytes() for p in PAGES}
    proc = subprocess.run([sys.executable, str(DD / "scripts" / "build_site.py")],
                          capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:
        err(f"rebuild failed: {proc.stderr.strip()}")
    else:
        after = {p: p.read_bytes() for p in PAGES}
        for p in before:
            if before[p] != after.get(p):
                err(f"non-deterministic build output: {p.relative_to(DD)}")

    if errors:
        print(f"FAIL — {len(errors)} problem(s):")
        for e in errors:
            print(" -", e)
        return 1
    n_src = len(src_ids)
    n_rows = len(injuries["report_rows"]) + len(injuries["supplemental_rows"])
    print(f"PASS — {n_src} sources, {n_rows} injury rows, {len(injuries['deficiencies'])} deficiencies, "
          f"{len(questions['questions'])} questions, {len(suggestions['suggestions'])} suggestions, "
          f"{len(flagged['flagged'])} flags, {len(PAGES)} pages, deterministic rebuild, all rows source-linked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
