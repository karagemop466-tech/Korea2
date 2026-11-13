#!/usr/bin/env python3
"""Ingest the sibling hubs' registers into one de-duplicated review board.

Everything this script writes is READ from files already committed in the repository plus the one
transcribed official snapshot in `review-board/data/raw/`. Nothing here is typed by hand into the
site: hub names, row counts, statuses, priorities, priorities, sources and the reconciliation values
are all read from the sibling registers. If a register is missing, the row is skipped and the fact is
recorded as missing rather than guessed.

Outputs (all under review-board/data/):
  queue.json          de-duplicated suggestion review queue (topic clusters + per-hub provenance)
  readiness.json      de-duplicated decision-readiness register (questions: have / don't have)
  injuries.json       current-slate availability snapshot derived from the official report
  hub_map.json        inventory of every hub directory in the repository and how it is wired up
  reconciliation.json the same quantity published with different values by different hubs
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.dirname(HERE)                       # review-board/
REPO = os.path.dirname(HUB)                       # repository root

sys.path.insert(0, HERE)
from topics import TOPICS, classify                # noqa: E402

CAPTURE_DATE = "2026-11-13"
SOURCE_PAGE_URL = "https://www.nfl.com/injuries/league/2026/reg10"

# Every sibling hub that publishes a suggestion or question register, with the JSON key that holds
# the rows and the fields to read. Heterogeneous schemas are normalised here rather than by hand.
SUGGESTION_SOURCES = [
    ("decision-desk", "decision-desk/data/suggestions.json", "suggestions", {
        "text": ("title", "description"), "category": ("category",), "priority": ("priority",),
        "effort": ("effort",), "impact": ("benefit",), "risk": (), "status": ("status",),
        "decision": ("decision",)}),
    ("decision-hub", "decision-hub/data/suggestions.json", "suggestions", {
        "text": ("title", "suggestion"), "category": ("category",), "priority": (),
        "effort": ("effort_days",), "impact": ("impact",), "risk": ("risk",), "status": ("status",),
        "decision": ()}),
    ("lineup-lab", "lineup-lab/data/suggestions.json", "rows", {
        "text": ("idea",), "category": ("area",), "priority": (), "effort": ("effort",),
        "impact": ("expected_impact",), "risk": (), "status": ("status",), "decision": ()}),
    ("nfl-command", "nfl-command/data/suggestions.json", "rows", {
        "text": ("title",), "category": (), "priority": (), "effort": (),
        "impact": ("recommendation",), "risk": (), "status": (), "decision": ("decision_needed",)}),
    ("site", "site/data/suggestions.json", "suggestions", {
        "text": ("title", "proposal"), "category": ("area",), "priority": ("payoff",),
        "effort": ("effort",), "impact": ("problem",), "risk": ("risk",), "status": ("review",),
        "decision": ("recommend",)}),
    ("suggestions", "suggestions/data/suggestions.json", "rows", {
        "text": ("proposal", "detail"), "category": ("category",), "priority": ("priority",),
        "effort": (), "impact": ("expected_impact",), "risk": (), "status": ("status",),
        "decision": ()}),
    ("verify-hub", "verify-hub/data/suggestions.json", "rows", {
        "text": ("proposal",), "category": ("category",), "priority": ("priority",),
        "effort": ("effort",), "impact": ("expected_impact",), "risk": ("tradeoffs",),
        "status": ("status",), "decision": ()}),
]

QUESTION_SOURCES = [
    ("decision-desk", "decision-desk/data/questions.json", "questions", {
        "text": ("question",), "answer": ("answer",), "status": ("status",), "gap": ("gap",),
        "how": (), "category": ("category",)}),
    ("decision-hub", "decision-hub/data/questions.json", "questions", {
        "text": ("question",), "answer": ("known",), "status": ("status",), "gap": ("unknown",),
        "how": ("how_to_answer",), "category": ()}),
    ("lineup-lab", "lineup-lab/data/questions.json", "rows", {
        "text": ("question",), "answer": ("current_verified_answer",), "status": ("priority",),
        "gap": ("missing_to_resolve",), "how": (), "category": ()}),
    ("nfl-command", "nfl-command/data/questions.json", "rows", {
        "text": ("question",), "answer": ("known",), "status": (), "gap": ("unknown",),
        "how": ("how_to_find_out",), "category": ()}),
    ("site", "site/data/questions.json", "questions", {
        "text": ("question",), "answer": ("answer",), "status": ("group",), "gap": ("missing",),
        "how": ("decision_needed",), "category": ()}),
    ("suggestions", "suggestions/data/questions.json", "rows", {
        "text": ("question",), "answer": ("answer",), "status": ("have_or_missing",),
        "gap": ("information_needed",), "how": ("suggestion_if_missing",), "category": ()}),
    ("verify-hub", "verify-hub/data/questions.json", "rows", {
        "text": ("question",), "answer": ("answer",), "status": ("status",),
        "gap": ("information_needed",), "how": ("discovery_suggestion",), "category": ()}),
]

# Hubs that publish a source register, so a row's `SRC-...` id can be resolved to a real URL.
SOURCE_REGISTERS = {
    "decision-desk": "decision-desk/data/sources.json",
    "decision-hub": "decision-hub/data/sources.json",
    "lineup-lab": "lineup-lab/data/sources.json",
    "nfl-command": "nfl-command/data/sources.json",
    "verify-hub": "verify-hub/data/sources.json",
    "suggestions": "suggestions/data/sources.json",
    "skill-lab": "skill-lab/data/sources.json",
    "root": "data/sources.json",
}


def read_json(rel: str, default=None):
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        return default
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:                       # unreadable -> recorded, not guessed
        return {"__error__": f"{type(exc).__name__}: {exc}", "path": rel}


def pick(row: dict, names) -> str:
    """First non-empty field among `names`, flattened to a string. '' when none exists."""
    for n in names:
        v = row.get(n)
        if isinstance(v, (list, tuple)):
            v = "; ".join(str(x) for x in v if x)
        if isinstance(v, dict):
            v = "; ".join(f"{k}: {x}" for k, x in v.items() if x)
        if v not in (None, "", []):
            return str(v).strip()
    return ""


def source_register(hub: str) -> dict:
    reg = read_json(SOURCE_REGISTERS.get(hub, ""), {}) or {}
    out = {}
    for entry in (reg.get("sources") if isinstance(reg, dict) else None) or []:
        if isinstance(entry, dict) and entry.get("id"):
            out[str(entry["id"])] = {
                "url": entry.get("url", ""),
                "label": entry.get("short") or entry.get("title") or entry.get("label") or entry.get("id"),
                "official": entry.get("official"),
                "accessed": entry.get("accessed") or entry.get("opened") or entry.get("as_of") or "",
                "quote": entry.get("quote") or entry.get("what_it_supports") or "",
            }
    return out


def resolve_sources(hub: dict, ids) -> list[dict]:
    """Hub source ids -> URLs, using that hub's own register. Unknown ids stay unlinked."""
    out = []
    for sid in ids or []:
        rec = hub.get(str(sid))
        if rec and rec.get("url", "").startswith("https://"):
            out.append({"id": str(sid), **rec})
        else:
            out.append({"id": str(sid), "url": "", "label": f"{sid} (url not published)",
                        "official": None, "accessed": "", "quote": ""})
    return out


# ------------------------------------------------------------------ suggestions
def build_queue() -> dict:
    rows, missing_files = [], []
    for hub, rel, key, fields in SUGGESTION_SOURCES:
        doc = read_json(rel)
        if not isinstance(doc, dict) or key not in doc:
            missing_files.append(rel)
            continue
        reg = source_register(hub)
        for r in doc[key]:
            text = pick(r, fields["text"])
            if not text:
                continue
            rows.append({
                "hub": hub,
                "hub_id": str(r.get("id", "")),
                "text": text,
                "detail": pick(r, ("problem", "description", "detail", "idea", "proposal")),
                "recommended": pick(r, ("recommended_path", "recommend", "recommendation")),
                "category": pick(r, fields["category"]),
                "priority": pick(r, fields["priority"]),
                "effort": pick(r, fields["effort"]),
                "impact": pick(r, fields["impact"]),
                "risk": pick(r, fields["risk"]),
                "status": pick(r, fields["status"]),
                "decision": pick(r, fields["decision"]),
                "sources": resolve_sources(reg, r.get("sources") or []),
            })

    topics = {t["id"]: {**t, "rows": [], "hubs": set(), "priorities": Counter(),
                        "statuses": Counter(), "efforts": Counter()} for t in TOPICS}
    unclassified = []
    for row in rows:
        tid = classify(row["hub"], row["hub_id"], f'{row["category"]} {row["text"]} {row["detail"]}')
        if tid in topics:
            topics[tid]["rows"].append(row)
            topics[tid]["hubs"].add(row["hub"])
            topics[tid]["priorities"][row["priority"].lower()] += 1
            topics[tid]["statuses"][row["status"].lower()] += 1
            topics[tid]["efforts"][row["effort"].lower()] += 1
        else:
            unclassified.append(row)

    clusters = []
    for t in TOPICS:
        node = topics[t["id"]]
        rows_here = sorted(node["rows"], key=lambda r: (r["hub"], r["hub_id"]))
        if not rows_here:
            continue
        urls = sorted({s["url"] for r in rows_here for s in r["sources"] if s["url"]})
        clusters.append({
            "id": t["id"],
            "title": t["title"],
            "decision": t["decision"],
            "options": t["options"],
            "why_now": t["why_now"],
            "prerequisite_of": t["prerequisite_of"],
            "owner_of_change": t["owner_of_change"],
            "proposals_total": len(rows_here),
            "hubs": sorted(node["hubs"]),
            "hub_count": len(node["hubs"]),
            "priority_votes": dict(node["priorities"]),
            "status_votes": dict(node["statuses"]),
            "effort_votes": dict(node["efforts"]),
            "evidence_urls": urls,
            "proposal_ids": [f'{r["hub"]}:{r["hub_id"]}' for r in rows_here],
            "rows": rows_here,
        })

    # Rank: how many hubs independently proposed it (breadth), then whether any hub called it high
    # priority, then whether it gates other clusters. Pure arithmetic on the registers above.
    for c in clusters:
        high = sum(1 for p in ("high", "must", "critical", "5", "4")
                   if c["priority_votes"].get(p))
        c["rank_score"] = c["hub_count"] * 10 + high * 3 + len(c["prerequisite_of"])
    clusters.sort(key=lambda c: (-c["rank_score"], c["id"]))
    for i, c in enumerate(clusters, 1):
        c["rank"] = i

    return {
        "generated_from": [rel for _, rel, _, _ in SUGGESTION_SOURCES],
        "unreadable_registers": missing_files,
        "proposal_rows": len(rows),
        "clusters": clusters,
        "untriaged": unclassified,
        "method": (
            "Every suggestion published by a sibling hub is read from that hub's own JSON register, "
            "normalised to one row per hub proposal, then clustered by keyword rules (explicit "
            "overrides where a hub's wording was ambiguous). The cluster rank is arithmetic: "
            "10 x number of hubs that proposed it, + 3 if any hub labelled it high priority, "
            "+ 1 per other cluster it unblocks. No cluster contains a number that was typed in."
        ),
    }


# ------------------------------------------------------------------ questions
ANSWERED = ("answered", "have", "answerable now", "resolved", "yes")
PARTIAL = ("partial", "partially", "in progress", "needs review", "answerable")


def build_readiness() -> dict:
    rows = []
    for hub, rel, key, fields in QUESTION_SOURCES:
        doc = read_json(rel)
        if not isinstance(doc, dict) or key not in doc:
            continue
        reg = source_register(hub)
        for r in doc[key]:
            text = pick(r, fields["text"])
            if not text:
                continue
            answer = pick(r, fields["answer"])
            gap = pick(r, fields["gap"])
            raw_status = pick(r, fields["status"]).lower()
            if raw_status in ANSWERED or (answer and not gap and raw_status):
                state = "answered"
            elif answer and gap:
                state = "partially answered"
            elif answer:
                state = "answered"
            elif gap:
                state = "unanswered"
            else:
                state = "unclassified"
            rows.append({
                "hub": hub, "hub_id": str(r.get("id", "")), "question": text, "answer": answer,
                "gap": gap, "how": pick(r, fields["how"]), "state": state,
                "raw_status": pick(r, fields["status"]), "category": pick(r, fields["category"]),
                "sources": resolve_sources(reg, r.get("sources") or []),
            })

    topics = {t["id"]: {"hubs": set(), "answered": 0, "partial": 0, "unanswered": 0,
                        "other": 0, "rows": []} for t in TOPICS}
    unplaced = []
    for row in rows:
        tid = classify(row["hub"], row["hub_id"], f'{row["category"]} {row["question"]} '
                                                  f'{row["answer"]} {row["gap"]}')
        node = topics.get(tid)
        if node is None:
            # a row no rule matched is reported, never dropped - the queue is only trustworthy if its
            # row count reconciles with the registers it was built from
            unplaced.append(row)
            continue
        node["hubs"].add(row["hub"])
        node["rows"].append(row)
        if row["state"] == "answered":
            node["answered"] += 1
        elif row["state"] == "partially answered":
            node["partial"] += 1
        elif row["state"] == "unanswered":
            node["unanswered"] += 1
        else:
            node["other"] += 1

    clusters = []
    for t in TOPICS:
        node = topics[t["id"]]
        if not node["rows"]:
            continue
        clusters.append({
            "id": t["id"], "title": t["title"], "decision": t["decision"],
            "hubs": sorted(node["hubs"]), "hub_count": len(node["hubs"]),
            "answered": node["answered"], "partial": node["partial"],
            "unanswered": node["unanswered"], "other": node["other"],
            "blocking": node["unanswered"] + node["partial"] + node["other"],
            "questions": sorted(node["rows"], key=lambda r: (r["state"] != "unanswered",
                                                              r["hub"], r["hub_id"])),
        })
    clusters.sort(key=lambda c: (-c["unanswered"], -c["hub_count"], c["id"]))
    return {
        "question_rows": len(rows),
        "state_totals": dict(Counter(r["state"] for r in rows)),
        "unplaced": unplaced,
        "clusters": clusters,
        "method": (
            "Each hub's own decision-readiness register is read as-is and normalised to three states: "
            "answered (the hub records an answer and no gap), partially answered (an answer and a "
            "stated gap), unanswered (a stated gap and no answer). A cluster is only 'closed' when no "
            "hub has an open item in it; disagreement between hubs is shown side by side, never averaged."
        ),
    }


# ------------------------------------------------------------------ injuries
OFFENSE = {"QB", "RB", "WR", "TE", "T", "G", "C", "FB", "LS", "K", "P"}
DEFENSE = {"DE", "DT", "LB", "CB", "S"}


def build_injuries() -> dict:
    path = os.path.join(HUB, "data", "raw", "injury_report_2026-11-13_week10.csv")
    with open(path, newline="") as fh:
        raw = [r for r in csv.DictReader(fh)]
    snap_url = SOURCE_PAGE_URL
    by_team = defaultdict(list)
    for r in raw:
        by_team[r["team"]].append(r)

    games = []
    seen = set()
    for r in raw:
        key = tuple(sorted({r["team"], r["opp"]})) + (r["slot"],)
        if key in seen:
            continue
        seen.add(key)
        teams = [t for t in (r["team"], r["opp"]) if t]
        games.append({"slot": r["slot"], "away": r["team"], "home": r["opp"],
                      "teams": teams})
    games.sort(key=lambda g: (g["slot"], g["away"]))

    team_rows = []
    for team in sorted(by_team):
        rows_t = by_team[team]
        out = [r for r in rows_t if r["game_status"] == "Out"]
        doub = [r for r in rows_t if r["game_status"] == "Doubtful"]
        ques = [r for r in rows_t if r["game_status"] == "Questionable"]
        nod = [r for r in rows_t if not r["game_status"]]
        dnp = [r for r in rows_t if r["practice"] == "DNP"]
        team_rows.append({
            "team": team, "opponent": rows_t[0]["opp"], "slot": rows_t[0]["slot"],
            "listed": len(rows_t), "out": len(out), "doubtful": len(doub),
            "questionable": len(ques), "no_designation": len(nod), "dnp": len(dnp),
            "out_offense": sum(1 for r in out if r["pos"] in OFFENSE),
            "out_defense": sum(1 for r in out if r["pos"] in DEFENSE),
            "qb_out": "; ".join(sorted({r["player"] for r in rows_t
                                        if r["pos"] == "QB" and r["game_status"] == "Out"})),
            "names_out": "; ".join(sorted(f'{r["player"]} ({r["pos"]})' for r in out)),
            "names_doubtful": "; ".join(sorted(f'{r["player"]} ({r["pos"]})' for r in doub)),
            "source_url": snap_url,
        })

    designated = [r for r in raw if r["game_status"] in ("Out", "Doubtful", "Questionable")]
    counts = Counter(r["game_status"] for r in designated)
    pos_counts = Counter(r["pos"] for r in designated)
    return {
        "captured": CAPTURE_DATE,
        "season": 2026,
        "week": 10,
        "source_url": snap_url,
        "source_title": "Official NFL Injury Report for Players - Week 10 of the 2026 Season | NFL.com",
        "scope_rule": (
            "The official report lists a player only when a designation or practice limitation "
            "applies. This snapshot keeps every listed player whose game status is Out, Doubtful or "
            "Questionable, plus every player listed with no game status but a DNP or Limited "
            "practice mark (those carry the availability information the Monday slate has to offer: "
            "its status report is not due until Saturday). Players published as a full participant "
            "with no designation carry no information and are not copied."
        ),
        "totals": {
            "rows_transcribed": len(raw),
            "teams_represented": len(by_team),
            "games": len(games),
            "slots": len({r["slot"] for r in raw}),
            "team_blocks": len(by_team),
            "out": counts["Out"], "doubtful": counts["Doubtful"],
            "questionable": counts["Questionable"],
            "no_designation_but_limited": sum(1 for r in raw if not r["game_status"]),
        },
        "by_position": dict(sorted(pos_counts.items())),
        "games": games,
        "teams": team_rows,
        "players": [
            {
                "slot": r["slot"], "team": r["team"], "opponent": r["opp"],
                "player": r["player"], "pos": r["pos"], "injury": r["injury"],
                "practice": r["practice"], "status": r["game_status"],
                "side": "offense" if r["pos"] in OFFENSE else ("defense" if r["pos"] in DEFENSE
                                                                else "special teams"),
                "source_url": snap_url,
            } for r in designated
        ],
    }


# ------------------------------------------------------------------ hub map
IGNORE_DIRS = {".git", "assets", "node_modules", "__pycache__"}


def build_hub_map() -> dict:
    nav_src = os.path.join(REPO, "scripts", "lib", "site.py")
    nav_targets, nav_labels = [], []
    if os.path.exists(nav_src):
        block = open(nav_src).read()
        for href, label in re.findall(r'\("([^"]+)",\s*"([^"]+)"\)', block):
            nav_targets.append(href)
            nav_labels.append(re.sub(r"\s*&nearr;", "", label))
    label_counts = Counter(nav_labels)

    hubs = []
    for name in sorted(os.listdir(REPO)):
        if name.startswith(".") or name in IGNORE_DIRS:
            continue
        path = os.path.join(REPO, name)
        if not os.path.isdir(path):
            continue
        htmls, datas, py = 0, 0, 0
        for base, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for f in files:
                if f.endswith(".html"):
                    htmls += 1
                elif f.endswith(".json"):
                    datas += 1
                elif f.endswith(".py"):
                    py += 1
        if not htmls and not datas and not py:
            continue
        try:
            when = subprocess.run(
                ["git", "-C", REPO, "log", "-1", "--format=%cs", "--", name],
                capture_output=True, text=True).stdout.strip()
        except OSError:
            when = ""
        top_files = sorted(f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)))
        entry = {
            "dir": name,
            "kind": ("site hub" if os.path.exists(os.path.join(path, "index.html"))
                     else "code" if py and not htmls
                     else "data register" if datas and not htmls
                     else "documentation" if any(f.lower().endswith(".md") for f in top_files)
                     else "other"),
            "index_page": os.path.exists(os.path.join(path, "index.html")),
            "pages": htmls,
            "data_files": datas,
            "scripts": py,
            "last_touched": when or "(no commit recorded)",
            "nav_links": sorted({h for h in nav_targets if h.startswith(name + "/")}),
            "nav_labels": [l for href, l in zip(nav_targets, nav_labels)
                           if href.startswith(name + "/")],
        }
        hubs.append(entry)

    kinds = Counter(h["kind"] for h in hubs)
    return {
        "kind_totals": dict(sorted(kinds.items())),
        "base_commit": subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                                      capture_output=True, text=True).stdout.strip(),
        "hub_count": len(hubs),
        "nav_target_count": len(nav_targets),
        "nav_duplicate_labels": [{"label": l, "count": n} for l, n in sorted(label_counts.items())
                                 if n > 1],
        "nav": [{"href": h, "label": l} for h, l in zip(nav_targets, nav_labels)],
        "hubs": hubs,
        "total_pages": sum(h["pages"] for h in hubs) + 1,
        "total_data_files": sum(h["data_files"] for h in hubs),
    }


# ------------------------------------------------------------------ reconciliation
# Hubs publish the same quantity under different definitions. Rather than average them, this
# section reads each hub's own committed JSON and shows the values side by side, then flags any
# quantity whose published values disagree.

# A published number: hub file -> (label, value). Matched by key name so nothing is transcribed.
NUMBER_KEYS = re.compile(r"^(r|pearson_r|value|coefficient|correlation|r_value|published_value)$", re.I)
LABEL_KEYS = ("label", "name", "quantity", "pair", "claim", "id")
STAMP_KEYS = ("as_of", "captured", "verified_on", "generated_utc", "created", "verified", "checked")
COUNT_KEYS = ("strategies", "candidates", "evaluations", "entries", "ranking", "rows",
              "total_evaluated", "cross_lab_rows", "leaderboard")
PASS_KEYS = ("approved_count", "qualified_strategies", "approved", "qualified", "awarded_count",
             "points_awarded")


def _first(d: dict, keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return ""


def _leaf(node, key, out, depth=0, context=None):
    """Collect (label, value, path) for every dict that has `key` as a scalar field."""
    if depth > 9:
        return
    if isinstance(node, dict):
        ctx = _first(node, LABEL_KEYS) or context
        if key in node and isinstance(node[key], (int, float)) and not isinstance(node[key], bool):
            out.append((str(ctx or ""), node[key]))
        for k, v in node.items():
            _leaf(v, key, out, depth + 1, ctx if isinstance(v, (dict, list)) else ctx)
    elif isinstance(node, list):
        for v in node:
            _leaf(v, key, out, depth + 1, context)


# Explicit label aliases: hubs name the same quantity differently, so the match is declared here
# (and printed on the page) instead of being guessed by string equality.
ALIAS_TABLE = {
    "QB passing yards vs WR1 receiving yards": r"qb.{0,28}wr ?1",
    "WR1 vs WR2 receiving yards": r"wr ?1.{0,30}wr ?2",
    "Home ATS cover vs game total over": r"(cover|ats).{0,26}(game total|total over)",
    "Home points vs away points": r"home p?oints.{0,22}away",
    "RB rushing yards vs team points": r"rb.{0,25}(rush|yards).{0,30}team p?oints",
    "Winning margin vs game total": r"margin.{0,20}total",
    "Player's own receptions vs own receiving yards": r"receptions? vs.{0,20}receiving",
    "QB passing yards vs game total points": r"qb.{0,25}(game total|total points)",
}


def repo_json_files() -> list[str]:
    """Every committed JSON register in the repository, excluding this hub's own output."""
    out = []
    for base, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in sorted(dirs) if d not in IGNORE_DIRS and d != "review-board"]
        for f in sorted(files):
            if f.endswith(".json"):
                rel = os.path.relpath(os.path.join(base, f), REPO).replace(os.sep, "/")
                if "/node_modules/" in rel:
                    continue
                out.append(rel)
    return out


def hub_json_files(rel: str) -> list[str]:
    return [rel]


def _stamp_range(stamps: list) -> dict:
    """Span over the registers that actually publish a date.

    A window object ({"season": 2026, "week": 8}) is not a timestamp; comparing one lexically against
    ISO stamps would produce a range no reader could act on, so those registers are counted separately."""
    dated = sorted(str(s["stamp"]) for s in stamps if s.get("stamp_kind") == "date")
    return {"earliest": dated[0] if dated else "",
            "latest": dated[-1] if dated else "",
            "dated_registers": len(dated),
            "window_only_registers": len(stamps) - len(dated)}


def build_reconciliation() -> dict:
    files = repo_json_files()
    numbers, stamps, verdicts, gate_defs = [], [], [], []

    for rel in files:
        if True:
            hub = rel.split("/")[0]
            doc = read_json(rel)
            if not isinstance(doc, dict):
                continue
            url = "https://github.com/karagemop466-tech/Korea2/tree/main/" + rel
            # 1. published numbers that look like a correlation/coefficient, with their label
            bucket = defaultdict(list)
            for key in ("r", "pearson_r", "coefficient", "correlation"):
                found: list = []
                _leaf(doc, key, found)
                for label, value in found:
                    if label and abs(value) <= 1:
                        bucket[(label, key)].append(round(float(value), 3))
            for (label, key), vals in bucket.items():
                numbers.append({"hub": hub, "file": rel, "quantity": label, "field": key,
                                "values": ", ".join(f"{v:.3f}" for v in sorted(set(vals))),
                                "spread": round(max(set(vals)) - min(set(vals)), 3) if len(set(vals)) > 1 else 0,
                                "source_url": url})
            # 2. the as-of stamp each hub publishes for the file
            meta = doc.get("meta") if isinstance(doc.get("meta"), dict) else {}
            stamp = _first(doc, STAMP_KEYS)
            if stamp in (None, "", [], {}):
                stamp = _first(meta, STAMP_KEYS)
            if stamp:
                # A stamp may be a date or a window object. Only the first is an as-of date, and the
                # page has to say which it got - silently printing a dict as a timestamp would imply
                # a freshness the register never claimed.
                if isinstance(stamp, dict):
                    parts = ", ".join(f"{k} {v}" for k, v in sorted(stamp.items())
                                      if v not in (None, "", [], {}))
                    stamps.append({"hub": hub, "file": rel,
                                   "stamp": f"window only: {parts}",
                                   "stamp_kind": "no date published", "source_url": url})
                else:
                    stamps.append({"hub": hub, "file": rel, "stamp": str(stamp),
                                   "stamp_kind": "date", "source_url": url})
            # 3. strategy count + pass count, read from the same file
            n = ""
            for key in COUNT_KEYS:
                v = doc.get(key)
                if v in (None, "", [], {}):
                    v = meta.get(key)
                if isinstance(v, list):
                    n = len(v)
                    break
                if isinstance(v, int):
                    n = v
                    break
            passed = _first(doc, PASS_KEYS)
            if passed in ("", None):
                passed = _first(meta, PASS_KEYS)
            if n != "" and passed not in ("", None):
                verdicts.append({"hub": hub, "file": rel, "evaluated": n, "passed": passed,
                                 "source_url": url})
            # 4. gate definitions, so the same gate id can be compared across hubs
            defs = doc.get("gates_definition") or (doc.get("gates") if isinstance(doc.get("gates"), list) else None)
            if isinstance(defs, list):
                for g in defs:
                    if isinstance(g, dict) and g.get("id"):
                        gate_defs.append({"hub": hub, "file": rel, "gate": g["id"],
                                          "name": g.get("name") or g.get("title") or "",
                                          "rule": str(g.get("rule") or g.get("pass_rule") or ""),
                                          "source_url": url})

    # conflict: the same quantity published with different numbers by different hubs. Labels are
    # written by hand in each hub, so quantities are matched through an explicit alias table rather
    # than by string equality - the alias table is printed on the page so the match is auditable.
    aliases = ALIAS_TABLE
    canon = defaultdict(list)
    for row in numbers:
        lab = row["quantity"].lower().replace("<->", " vs ").replace(" <-> ", " vs ")
        for name, pat in aliases.items():
            if re.search(pat, lab):
                canon[name].append(row)
                break
    conflicts = []
    for name, rows in sorted(canon.items()):
        distinct = sorted({v for r in rows for v in r["values"].split(", ")})
        if len(rows) < 2 or len(distinct) < 2:
            continue
        for r in rows:
            conflicts.append({**r, "quantity_canonical": name, "all_values": ", ".join(distinct)})
    gate_conflicts = []
    by_gate = defaultdict(list)
    for g in gate_defs:
        by_gate[str(g["gate"]).upper()].append(g)
    for gid, rows in sorted(by_gate.items()):
        names = sorted({r["name"] for r in rows if r["name"]})
        if len(names) > 1:
            for r in rows:
                gate_conflicts.append({**r, "all_names": " | ".join(names)})

    return {
        "hubs_scanned": len({r.split("/")[0] for r in files}),
        "files_scanned": len(files),
        "published_numbers": sorted(numbers, key=lambda r: (r["quantity"].lower(), r["file"])),
        "quantity_conflicts": conflicts,
        "conflict_quantity_count": len({r["quantity_canonical"] for r in conflicts}),
        "quantity_aliases": {k: v for k, v in ALIAS_TABLE.items()},
        "gate_definitions": sorted(gate_defs, key=lambda r: (str(r["gate"]), r["file"])),
        "gate_name_conflicts": gate_conflicts,
        "stamps": sorted(stamps, key=lambda r: r["file"]),
        "stamp_range": _stamp_range(stamps),
        "verdicts": sorted(verdicts, key=lambda r: r["file"]),
        "method": (
            "Each hub's own committed JSON is read; a value counts as published only when the file "
            "carries it under a recognised field name (r / pearson_r / coefficient / correlation) with a "
            "label. Values are shown exactly as stored, rounded to three decimals. A quantity is a "
            "conflict when two or more hubs publish different numbers for the same label - the board "
            "shows both and links both files. Nothing is averaged and nothing is re-derived here."
        ),
    }


def build_injury_delta() -> dict:
    """Compare this session's Friday capture with the sibling hub's Wednesday capture."""
    prior = read_json("decision-desk/data/injuries.json")
    cur = read_json("review-board/data/injuries.json")
    if not isinstance(prior, dict) or not isinstance(cur, dict):
        return {"available": False, "note": "a register is missing"}
    prev = {r["player"].lower(): r for r in prior.get("report_rows", [])}
    now = {}
    for r in cur["players"]:
        now[r["player"].lower()] = r
    added = [r for k, r in now.items() if k not in prev]
    gone = [r for k, r in prev.items() if k not in now and r.get("game_status") in
            ("Out", "Doubtful", "Questionable")]
    changed = [{"player": r["player"], "team": r["team"], "pos": r["pos"],
                "was": prev[k].get("practice", "") +
                       ((" / " + prev[k]["game_status"]) if prev[k].get("game_status") else ""),
                "now": r["practice"] + ((" / " + r["status"]) if r["status"] else "")}
               for k, r in now.items() if k in prev and
               (prev[k].get("practice", "") != r["practice"]
                or (prev[k].get("game_status") or "") != (r["status"] or ""))]
    return {
        "available": True,
        "previous_capture": prior.get("meta", {}).get("captured", ""),
        "previous_source": "decision-desk/data/injuries.json",
        "previous_source_url": "https://github.com/karagemop466-tech/Korea2/tree/main/"
                               "decision-desk/data/injuries.json",
        "current_capture": cur["captured"],
        "current_source_url": cur["source_url"],
        "counts": {"in_previous": len(prev), "in_current": len(now),
                   "players_listed_with_a_designation_before": sum(
                       1 for r in prev.values() if r.get("game_status")),
                   "players_listed_with_a_designation_now": sum(
                       1 for r in cur["players"] if r["status"] in
                       ("Out", "Doubtful", "Questionable")),
                   "added": len(added), "changed": len(changed), "dropped": len(gone)},
        "teams_that_said_no_injuries": prior.get("no_report", []),
        "changed": sorted(changed, key=lambda c: (c["team"], c["player"]))[:60],
        "note": (
            "The sibling capture is the Wednesday practice report; this one is the Friday report that "
            "carries game statuses. Designation counts are therefore not comparable as a rate - the "
            "point of the row is that the Friday statuses exist only on Friday, which is exactly why "
            "an archived point-in-time snapshot (and not a re-read of the live page) is required to "
            "backtest any availability signal."
        ),
    }


def main() -> int:
    os.makedirs(os.path.join(HUB, "data"), exist_ok=True)
    commit = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    hub_map = build_hub_map()
    out = {"queue.json": build_queue(), "readiness.json": build_readiness(),
           "injuries.json": build_injuries(), "hub_map.json": hub_map,
           "reconciliation.json": build_reconciliation()}
    for name, doc in out.items():
        doc["_generated_by"] = "review-board/scripts/ingest.py"
        doc["_generated_from_repo_commit"] = commit
        with open(os.path.join(HUB, "data", name), "w") as fh:
            json.dump(doc, fh, indent=1, sort_keys=False)
            fh.write("\n")
        print(f"wrote review-board/data/{name}")
    delta = build_injury_delta()
    delta["_generated_by"] = "review-board/scripts/ingest.py"
    delta["_generated_from_repo_commit"] = commit
    with open(os.path.join(HUB, "data", "injury_delta.json"), "w") as fh:
        json.dump(delta, fh, indent=1)
        fh.write("\n")
    print("wrote review-board/data/injury_delta.json")
    q = out["queue.json"]
    print(f"  suggestions: {q['proposal_rows']} rows -> {len(q['clusters'])} clusters "
          f"({len(q['untriaged'])} untriaged)")
    r = out["readiness.json"]
    print(f"  questions:   {r['question_rows']} rows -> {len(r['clusters'])} clusters "
          f"{r['state_totals']}")
    i = out["injuries.json"]
    print(f"  injuries:    {i['totals']['rows_transcribed']} rows, "
          f"{i['totals']['teams_represented']} teams in {i['totals']['teams_represented']} blocks, "
          f"{i['totals']['games']} games across {i['totals']['slots']} slots")
    rec = out["reconciliation.json"]
    print(f"  recon:       {rec['files_scanned']} files, "
          f"{len(rec['published_numbers'])} published numbers, "
          f"{rec['conflict_quantity_count']} conflicting quantities, "
          f"{len(rec['gate_name_conflicts'])} gate-name conflicts")
    if delta.get("available"):
        print(f"  delta:       {delta['counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
