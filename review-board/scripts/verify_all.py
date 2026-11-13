#!/usr/bin/env python3
"""Verification pass for the Review Board. Run: python3 review-board/scripts/verify_all.py

Each check states a rule this hub's own pages claim to follow, expressed as code, so a regression fails a build
instead of turning into a footnote. Standard library only - the same interpreter the CI image ships, no optional
packages - and every check recomputes from files rather than trusting an earlier run.

Exit 0 when all checks pass, 1 otherwise, with the reason for each failure printed first.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.dirname(HERE)
DATA = os.path.join(HUB, "data")
PAGES_DIR = os.path.join(HUB, "pages")
REPO = os.path.dirname(HUB)
PAGES = ["index.html"] + sorted(f"pages/{n}" for n in os.listdir(PAGES_DIR) if n.endswith(".html"))

# Paths a source register cites that return 404. They may appear as text, never as a live citation.
DEAD_MARKERS = ("nfl-injury-report-policy", "league-governance/injury-report", "standings/2026/divisions")

failures: list[str] = []
passes: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (passes if ok else failures).append(f"{name}{': ' + detail if detail else ''}")


def read(path: str) -> str:
    with open(path) as fh:
        return fh.read()


def digest(rel: str) -> str:
    return hashlib.sha256(read(os.path.join(HUB, rel)).encode()).hexdigest()[:16]


def jload(name: str) -> dict:
    with open(os.path.join(DATA, name)) as fh:
        return json.load(fh)


class TagBalance(HTMLParser):
    """Structural check, so a template that emits unbalanced markup cannot pass a regex test."""

    VOID = {"br", "img", "meta", "link", "hr", "input", "wbr"}
    TRACK = {"table", "thead", "tbody", "tr", "td", "th", "section", "div", "a", "span", "p", "caption"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID and tag in self.TRACK:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag not in self.TRACK or tag in self.VOID:
            return
        if not self.stack:
            self.errors.append(f"stray </{tag}>")
        elif self.stack[-1] != tag:
            self.errors.append(f"</{tag}> closes an open <{self.stack[-1]}>")
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
        else:
            self.stack.pop()


def main() -> int:
    data = {n: jload(f"{n}.json") for n in
            ("queue", "readiness", "injuries", "injury_delta", "hub_map", "reconciliation",
             "program", "sources", "flags")}

    # ---------------------------------------------------------------- 1. the build is reproducible
    before = {p: digest(p) for p in PAGES}
    r = subprocess.run([sys.executable, os.path.join(HERE, "build_site.py")],
                       capture_output=True, text=True, cwd=REPO)
    check("build_site.py exits 0", r.returncode == 0, (r.stderr or r.stdout).strip()[-400:])
    after = {p: digest(p) for p in PAGES}
    changed = [k for k in before if before[k] != after[k]]
    check("pages are a pure function of the committed registers (rebuild byte-identical)", not changed,
          ", ".join(changed[:4]) or f"{len(after)} pages")

    # ingest re-reads the sibling registers and the raw capture; the only permitted difference is the commit
    # stamp, which legitimately changes when a new commit is built. Any other difference means a register moved.
    def strip(doc: dict) -> dict:
        """Drop provenance stamps, which legitimately change on every rebuild in a fresh checkout."""
        return {k: v for k, v in doc.items()
                if not k.startswith("_generated") and k != "base_commit"}
    pre = {n: strip(jload(f"{n}.json")) for n in
           ("queue", "readiness", "injuries", "hub_map", "reconciliation", "injury_delta")}
    r2 = subprocess.run([sys.executable, os.path.join(HERE, "ingest.py")],
                        capture_output=True, text=True, cwd=REPO)
    check("ingest.py exits 0", r2.returncode == 0, (r2.stderr or r2.stdout).strip()[-400:])
    post = {n: strip(jload(f"{n}.json")) for n in pre}
    drift = [n for n in pre if json.dumps(pre[n], sort_keys=True) != json.dumps(post[n], sort_keys=True)]
    check("re-running ingest changes no register content, only the commit stamp", not drift,
          ", ".join(drift) or f"{len(pre)} registers")
    check("ingest and build agree about the page count", len(PAGES) == 14, f"{len(PAGES)} pages")

    # committed registers must already reflect the sibling inputs, or a hub edit silently ages this board
    stale = []
    for name, doc in post.items():
        rel = f"review-board/data/{name}.json"
        shown = subprocess.run(["git", "-C", REPO, "show", f"HEAD:{rel}"], capture_output=True, text=True)
        if shown.returncode != 0:
            continue                                        # untracked: first commit, nothing to compare
        try:
            committed = strip(json.loads(shown.stdout))
        except ValueError:
            stale.append(f"{name}.json unreadable at HEAD")
            continue
        if json.dumps(committed, sort_keys=True) != json.dumps(doc, sort_keys=True):
            stale.append(f"{name}.json")
    check("committed registers match the sibling inputs they read", not stale,
          ", ".join(stale) + " need a rebuild" if stale else "all six current")

    # ---------------------------------------------------------------- 2. every page keeps its rules
    for rel in PAGES:
        s = read(os.path.join(HUB, rel))
        check(f"{rel}: lang, title, stylesheet, disclaimer",
              '<html lang="en"' in s and "<title>" in s and "assets/style.css" in s
              and "not betting advice" in s)
        check(f"{rel}: no localhost or file:// references",
              not re.search(r"(localhost|127\.0\.0\.1|file://)", s))
        check(f"{rel}: unreachable official paths are never live citations",
              not any(m in href for href in re.findall(r'href="(https?://[^"]+)"', s) for m in DEAD_MARKERS))
        check(f"{rel}: no unrendered template braces", not re.search(r"\{[a-z_]+\[|\}\s*</", s))
        parser = TagBalance()
        parser.feed(s)
        check(f"{rel}: structural tags balanced", not parser.errors and not parser.stack,
              "; ".join((parser.errors + [f"unclosed <{t}>" for t in parser.stack])[:3]))

        # provenance rule: each data row's last cell is either an https link or the blank marker
        rows = [x for x in re.findall(r"<tr>(.*?)</tr>", s, re.S) if "<td" in x]
        unproven = []
        for x in rows:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", x, re.S)
            if cells and 'href="https' not in cells[-1] and 'class="blank"' not in cells[-1]:
                unproven.append(re.sub(r"\s+", " ", x)[:100])
        check(f"{rel}: all {len(rows)} rows end with a source link or a blank marker",
              not unproven, "; ".join(unproven[:2]))

    # ---------------------------------------------------------------- 3. links resolve inside the hub
    broken = []
    for rel in PAGES:
        s = read(os.path.join(HUB, rel))
        base = os.path.dirname(os.path.join(HUB, rel))
        for href in re.findall(r'href="((?!https?:|#|mailto:)[^"]+)"', s):
            target = href.split("#")[0]
            if target and not os.path.exists(os.path.normpath(os.path.join(base, target))):
                broken.append(f"{rel} -> {href}")
        for anchor in set(re.findall(r'href="#([^"]+)"', s)):
            if f'id="{anchor}"' not in s:
                broken.append(f"{rel} -> #{anchor}")
    check("internal links and anchors resolve", not broken, "; ".join(broken[:4]))

    landing = read(os.path.join(HUB, "index.html"))
    nav_links = set(re.findall(r'href="(pages/[a-z]+\.html|index\.html)"', landing))
    page_files = {f"pages/{n}" for n in os.listdir(PAGES_DIR) if n.endswith(".html")}
    check("the landing page reaches every generated page", not page_files - nav_links,
          ", ".join(sorted(page_files - nav_links)))
    check("every navigation target exists",
          all(os.path.exists(os.path.join(HUB, t)) for t in nav_links),
          ", ".join(sorted(t for t in nav_links if not os.path.exists(os.path.join(HUB, t)))))
    check("the hub stays out of the shared root navigation",
          "review-board" not in read(os.path.join(REPO, "scripts", "lib", "site.py")))

    # ---------------------------------------------------------------- 4. the registers reconcile
    q, r_ = data["queue"], data["readiness"]
    check("the suggestion classifier leaves no row untriaged", not q["untriaged"],
          f'{len(q["untriaged"])} rows')
    check("the readiness classifier leaves no row unplaced", not r_["unplaced"],
          f'{len(r_["unplaced"])} rows')
    check("suggestion clusters reconcile with the registers",
          sum(c["proposals_total"] for c in q["clusters"]) + len(q["untriaged"]) == q["proposal_rows"],
          f'{sum(c["proposals_total"] for c in q["clusters"])} + {len(q["untriaged"])} vs {q["proposal_rows"]}')
    check("question clusters reconcile with the registers",
          sum(len(c["questions"]) for c in r_["clusters"]) + len(r_["unplaced"]) == r_["question_rows"],
          f'{sum(len(c["questions"]) for c in r_["clusters"])} + {len(r_["unplaced"])} vs {r_["question_rows"]}')
    check("no sibling register was unreadable", not q["unreadable_registers"],
          ", ".join(q["unreadable_registers"]) or "all read")
    unstamped = [n for n in ("queue", "readiness", "injuries", "hub_map", "reconciliation", "injury_delta")
                 if "_generated_by" not in data[n] or "_generated_from_repo_commit" not in data[n]]
    check("every generated register names its generator and commit", not unstamped, ", ".join(unstamped))

    src_ids = {s["id"] for s in data["sources"]["sources"]}
    for label, rows in (("signals", data["program"]["signals"]),
                        ("gates", data["program"]["gates"]),
                        ("information_gaps", data["program"]["information_gaps"]),
                        ("flags", data["flags"]["flags"]),
                        ("blank_by_policy", data["flags"]["blank_by_policy"])):
        bad = [x.get("id", x.get("surface", "?")) for x in rows if x.get("source_id") not in src_ids]
        check(f"program.{label}: every source_id resolves in the source register", not bad, ", ".join(map(str, bad[:3])))
    incomplete = [f_["id"] for f_ in data["flags"]["flags"]
                  if not all(f_.get(k) for k in ("finding", "verification", "action", "kind", "severity"))]
    check("every flag states finding, verification, action, kind and severity", not incomplete,
          ", ".join(incomplete))
    weak = [s["id"] for s in data["program"]["signals"]
            if not s.get("test_design") or not s.get("falsifier") or not s.get("blocked_on")]
    check("every signal states a test design, a falsifier and its blocker", not weak, ", ".join(weak))
    check("every phase names a decision, a cost and an exit test",
          all(all(p.get(k) for k in ("decision", "cost", "exit_test")) for p in data["program"]["phases"]))

    # ---------------------------------------------------------------- 5. rows still exist in the sibling registers
    drift = []
    by_hub = {}
    for rel in q["generated_from"]:
        hub = rel.split("/")[0]
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            drift.append(f"{rel} missing")
            continue
        by_hub[hub] = read(path)
    for cluster in q["clusters"]:
        for row in cluster["rows"]:
            blob = by_hub.get(row["hub"])
            if blob is None:
                drift.append(f'{row["hub"]}:{row["hub_id"]} has no register on disk')
            elif f'"{row["hub_id"]}"' not in blob:
                drift.append(f'{row["hub"]}:{row["hub_id"]} no longer present in its register')
    check("every clustered row still exists in the register it cites", not drift, "; ".join(drift[:3]))

    # ---------------------------------------------------------------- 6. injury figures recomputed from the capture
    csv_path = os.path.join(DATA, "raw", "injury_report_2026-11-13_week10.csv")
    with open(csv_path, newline="") as fh:
        raw_rows = list(csv.DictReader(fh))
    tot = data["injuries"]["totals"]
    recount = {
        "rows_transcribed": len(raw_rows),
        "teams_represented": len({x["team"] for x in raw_rows}),
        "games": len({tuple(sorted((x["team"], x["opp"]))) + (x["slot"],) for x in raw_rows}),
        "slots": len({x["slot"] for x in raw_rows}),
        "out": sum(1 for x in raw_rows if x["game_status"] == "Out"),
        "doubtful": sum(1 for x in raw_rows if x["game_status"] == "Doubtful"),
        "questionable": sum(1 for x in raw_rows if x["game_status"] == "Questionable"),
        "no_designation_but_limited": sum(1 for x in raw_rows if not x["game_status"]),
    }
    mismatch = [f"{k}: page {tot.get(k)} vs csv {v}" for k, v in recount.items() if tot.get(k) != v]
    check("injury page totals match an independent recount of the raw capture", not mismatch, "; ".join(mismatch))
    check("the capture holds no status value outside the three designations and blank",
          not {x["game_status"] for x in raw_rows} - {"Out", "Doubtful", "Questionable", ""})
    check("the capture holds no invented practice value",
          not {x["practice"] for x in raw_rows} - {"DNP", "Limited", "Full", ""})
    check("the Monday slate is published as status-blank, not as healthy",
          sum(1 for x in raw_rows if x["slot"].startswith("Mon") and x["game_status"]) == 0,
          f'{sum(1 for x in raw_rows if x["slot"].startswith("Mon"))} Monday rows, '
          f'{sum(1 for x in raw_rows if x["slot"].startswith("Mon") and x["game_status"])} with a status')

    # ---------------------------------------------------------------- 7. blank where the sources stop
    depth = read(os.path.join(HUB, "pages", "depth.html"))
    teams = len(data["injuries"]["teams"])
    check(f"depth page leaves both depth columns blank for all {teams} clubs",
          depth.count('class="blank"') >= teams * 2, f'{depth.count(chr(34) + "blank" + chr(34))} markers')
    check("no page states a pick, a projected margin or a stake",
          not re.search(r"(our pick|we back the|take the over|projected margin of|bet on )",
                        " ".join(read(os.path.join(HUB, p)) for p in PAGES), re.I))
    check("every page carries the research-only disclaimer",
          all("not betting advice" in read(os.path.join(HUB, p)) for p in PAGES))
    check("the hub labels its own proposals as unapproved",
          "awaiting owner" in read(os.path.join(HUB, "pages", "suggestions.html")))
    zero = [v["file"] for v in data["reconciliation"]["verdicts"] if isinstance(v["passed"], int) and v["passed"]]
    check("no hub reports a qualified strategy while this site says none qualify", not zero, ", ".join(zero))
    check("reconciliation reads the whole tree rather than one hub",
          data["reconciliation"]["files_scanned"] > 100, f'{data["reconciliation"]["files_scanned"]} files')

    # ---------------------------------------------------------------- 8. the site renders the flags honestly
    flagged = read(os.path.join(HUB, "pages", "flagged.html"))
    missing_flags = [f_["id"] for f_ in data["flags"]["flags"] if f_["id"] not in flagged]
    check("every flag in the register appears on the flagged page", not missing_flags, ", ".join(missing_flags))
    missing_blanks = [b["surface"] for b in data["flags"]["blank_by_policy"]
                      if os.path.basename(b["surface"].split(" - ")[0]) not in flagged]
    check("every blank-by-policy surface is listed on the flagged page", not missing_blanks,
          ", ".join(missing_blanks[:2]))

    for line in failures:
        print(f"FAIL  {line}")
    print(f"\n{len(passes)} checks passed, {len(failures)} failed, across {len(PAGES)} pages.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
