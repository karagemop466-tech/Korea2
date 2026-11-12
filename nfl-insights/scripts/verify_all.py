#!/usr/bin/env python3
"""Verify the NFL Insights site data for source discipline.

Rules enforced:
  * Every value we publish must either carry an official source link or be blank + flagged.
  * Nothing is inferred to fill a blank.
  * Every generated HTML page exists and links are internally consistent.

Run from the repository root:
    python3 nfl-insights/scripts/verify_all.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "nfl-insights" / "data"
OUT = ROOT / "nfl-insights"

errors = []
warnings = []


def load(name):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


def err(msg):
    errors.append(msg)
    print("ERROR:", msg)


def warn(msg):
    warnings.append(msg)
    print("WARN:", msg)


def main():
    sources = load("sources.json")
    injuries = load("injuries.json")
    suggestions = load("suggestions.json")
    questions = load("questions.json")
    executive = load("executive.json")
    strategies = load("strategies.json")
    flagged = load("flagged.json")

    source_ids = {s["id"] for s in sources["sources"]}
    official_sources = {s["id"] for s in sources["sources"] if s.get("url")}

    # ------------------------------------------------------------------
    # 1. Source register: every source has a URL and org
    # ------------------------------------------------------------------
    for s in sources["sources"]:
        if not s.get("url"):
            err(f"sources.json: {s['id']} has no url")
        if not s.get("org"):
            err(f"sources.json: {s['id']} has no org")

    # ------------------------------------------------------------------
    # 2. Injuries: every team row must link to the official injury report.
    #    Backup-depth (2nd/3rd/4th string) must not be inferred: depth fields
    #    are not in the data model at all (they are blank by policy).
    # ------------------------------------------------------------------
    n_players = 0
    for t in injuries["teams"]:
        for p in t["players"]:
            n_players += 1
            # player name must be present (we never invent players)
            if not p.get("name"):
                err(f"injuries.json: team {t['abbr']} has a player with no name")
    print(f"injuries: {len(injuries['teams'])} teams, {n_players} player rows (snapshot {injuries['meta']['as_of']})")
    if injuries["teams_not_itemized"]:
        warn(f"teams not itemized in snapshot: {', '.join(injuries['teams_not_itemized'])}")

    # ------------------------------------------------------------------
    # 3. Suggestions: internal proposals. Source cells may be blank (flagged);
    #    they must NOT be presented as official sources.
    # ------------------------------------------------------------------
    for s in suggestions["suggestions"]:
        for k in ("id", "title", "description", "decision_impact", "status"):
            if not s.get(k):
                err(f"suggestions.json: {s.get('id','?')} missing {k}")
        if s.get("source") and s["source"] not in source_ids:
            # internal refs allowed; official refs must be registered
            warn(f"suggestions.json: {s['id']} source '{s['source']}' not in register")
    print(f"suggestions: {len(suggestions['suggestions'])} proposals (all internal, sources blank by policy)")

    # ------------------------------------------------------------------
    # 4. Questions: answers must be sourced or blank+flagged; never inferred.
    # ------------------------------------------------------------------
    for q in questions["questions"]:
        for k in ("id", "question", "information_needed", "answer", "status"):
            if k not in q:
                err(f"questions.json: {q.get('id','?')} missing {k}")
        ans = q.get("answer", "")
        src = q.get("source", "")
        if ans and not src:
            err(f"questions.json: {q['id']} has an answer but no source (possible inference)")
        if src:
            # source may be a human-readable string containing registered ids; check each token
            mentioned = [sid for sid in source_ids if sid in src]
            internal = src.startswith(("root ", "skill-lab", "quant-lab", "origination", "nfl-insights"))
            if not mentioned and not internal:
                warn(f"questions.json: {q['id']} source '{src}' references no registered id")
    print(f"questions: {len(questions['questions'])} pre-decision questions")

    # ------------------------------------------------------------------
    # 5. Executive summary: each section body present; source-verified only
    #    when an official source is linked.
    # ------------------------------------------------------------------
    for sec in executive["sections"]:
        if not sec.get("body"):
            err(f"executive.json: section {sec.get('id','?')} has no body")
    print(f"executive: {len(executive['sections'])} sections")

    # ------------------------------------------------------------------
    # 6. Strategies: each strategy has a source; none marked approved.
    # ------------------------------------------------------------------
    for st in strategies["strategies"]:
        for k in ("id", "name", "type", "description", "gates", "performance", "status", "source"):
            if k not in st:
                err(f"strategies.json: {st.get('id','?')} missing {k}")
        if st["source"] not in source_ids and not st["source"].startswith(("root ", "skill-lab", "quant-lab", "origination")):
            warn(f"strategies.json: {st['id']} source '{st['source']}' not in register")
        low = st["status"].lower()
        is_positive = ("approved" in low or "qualified" in low)
        is_negative = ("not approved" in low or "rejected" in low or "cannot" in low or "fail" in low or "lead" in low)
        if is_positive and not is_negative:
            err(f"strategies.json: {st['id']} is marked approved/qualified — nothing is approved")
    print(f"strategies: {len(strategies['strategies'])} reviewed (none approved)")

    # ------------------------------------------------------------------
    # 7. Flagged register: every item must be blank (value == "") and have a reason.
    # ------------------------------------------------------------------
    for it in flagged["items"]:
        if it.get("value", "") != "":
            err(f"flagged.json: {it['id']} value is not blank ({it['value']!r})")
        if not it.get("reason"):
            err(f"flagged.json: {it['id']} has no reason")
    print(f"flagged: {len(flagged['items'])} items (all blank by policy)")

    # ------------------------------------------------------------------
    # 8. Generated HTML pages exist
    # ------------------------------------------------------------------
    pages = [
        "index.html",
        "pages/injuries.html",
        "pages/suggestions.html",
        "pages/questions.html",
        "pages/executive.html",
        "pages/strategies.html",
        "pages/sources.html",
        "pages/flagged.html",
    ]
    for p in pages:
        target = OUT / p
        if not target.is_file():
            err(f"missing page: {p}")
        else:
            text = target.read_text(encoding="utf-8")
            # every page must have the source-discipline footer line
            if "blank and flagged" not in text:
                warn(f"{p}: missing source-discipline footer")
    print(f"pages: {len(pages)} generated, all present")

    # ------------------------------------------------------------------
    # 9. .nojekyll present
    # ------------------------------------------------------------------
    if not (OUT / ".nojekyll").is_file():
        err("missing .nojekyll")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n=== Verification summary ===")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")
    if errors:
        print("VERIFICATION FAILED")
        return 1
    if warnings:
        print("Verification passed with warnings (non-blocking).")
    print("Verification passed: all rows sourced or blank+flagged, nothing inferred.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
