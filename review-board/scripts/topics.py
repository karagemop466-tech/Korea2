#!/usr/bin/env python3
"""Topic taxonomy + classifier used by ingest.py.

The clusters are the editorial layer of the review board: they say which decision a proposal serves,
what the options are, and what must be true before it can be implemented. The rows inside each cluster
are read from the sibling hubs by ingest.py; only the text of a cluster and the keyword rules below are
authored here. `OVERRIDES` pins individual hub rows that keyword matching would place wrongly, so the
mapping is auditable row by row.
"""
from __future__ import annotations

import re

TOPICS = [
    {
        "id": "T01",
        "title": "Execution, jurisdiction and licensing",
        "decision": "Is there a legal, verifiable way to place and settle a bet from here at all - "
                    "and if not, does the project stay a research system?",
        "options": [
            ("A. Keep the project research-only", "Zero legal exposure, zero bankroll; nothing on the "
             "site may be described as a betting edge. Cheapest and consistent with every lab's "
             "'0 approved' verdict."),
            ("B. Commission a jurisdiction-specific legal review", "Answers licensing, geolocation, "
             "age and operator-terms questions with evidence; costs external advice and changes "
             "nothing about the maths."),
            ("C. Assume a broker or account exists", "Fastest to a bet, unverifiable from this "
             "repository, and it breaks the project's own rule that nothing unverified is asserted."),
        ],
        "why_now": "Every lab fails the same gate (executable pricing / access), so no measured edge "
                    "can be turned into anything until this is chosen.",
        "prerequisite_of": ["T02", "T09"],
        "owner_of_change": "Owner (legal decision), not an agent session.",
    },
    {
        "id": "T02",
        "title": "Price data: closing/opening lines and player-prop prices",
        "decision": "Which price feed becomes the project's source of truth, and does it carry "
                    "historical player-prop and alt-line prices at the granularity the props work needs?",
        "options": [
            ("A. Stay on the nflverse community release", "Free and reproducible; already the committed "
             "input; but community-maintained, so it must be labelled third-party, and it has no "
             "historical prop prices."),
            ("B. License a commercial archive", "Point-in-time prices, prop/alt lines, closing timestamps; "
             "recurring cost and a data-licence review before any of it can be republished on a public site."),
            ("C. Build a self-collected timestamped log", "Full provenance and it is the only route to "
             "opening-line data; earns nothing retrospectively, so validation stays blocked for months."),
        ],
        "why_now": "It is the single input that unblocks prop ROI, CLV, and any 'we beat the close' "
                    "claim. Six of the seven hubs ask for it.",
        "prerequisite_of": ["T05", "T06", "T08", "T09"],
        "owner_of_change": "Owner approves spend; a session can wire the fetcher and the schema.",
    },
    {
        "id": "T03",
        "title": "Injury and availability data engineering",
        "decision": "Do we archive the official report as a point-in-time series (so availability can "
                    "be backtested), or keep reading it as a weekly page?",
        "options": [
            ("A. Daily automated capture of the official report", "Creates the as-of history that every "
             "lab says is missing; storage is trivial; needs a scheduled job and a retention rule."),
            ("B. Manual weekly capture", "No engineering, but the history is thin and the timestamps are "
             "not trustworthy - which is exactly the flaw already flagged in this repo."),
            ("C. Do nothing; treat injuries as commentary", "Honest, and keeps the site free of "
             "un-backtested injury 'signals'."),
        ],
        "why_now": "The Friday report is not final, Monday's status is not published until Saturday, and "
                    "an archived snapshot is the only way to know what was actually knowable pre-game.",
        "prerequisite_of": ["T04", "T05"],
        "owner_of_change": "A session can build the capture; the owner chooses retention and licensing terms.",
    },
    {
        "id": "T04",
        "title": "Depth charts, starter definition and 'who replaces whom'",
        "decision": "How is a 'starter', '2nd string' or '4th string' defined with a citable source, "
                    "given that the league publishes no official depth chart?",
        "options": [
            ("A. Club-published charts, captured weekly and labelled 'unofficial team document'", "Closest "
             "to official; 32 fragile pages; several clubs' pages were already found stale or missing "
             "in this repo's own audit."),
            ("B. Derived depth from snaps + participation (nflverse)", "Consistent and reproducible across "
             "all clubs; it is a construct, so the definition and its limits must be published with it."),
            ("C. Leave depth blank", "Keeps every published number verifiable; makes the 'backup quality' "
             "requirement unanswerable."),
        ],
        "why_now": "The 'defence missing its 2nd/3rd/4th string' requirement cannot be met without a "
                   "source that defines strings, and the audit shows the official path returns 404.",
        "prerequisite_of": ["T05"],
        "owner_of_change": "Owner picks A or B; a session implements the capture and the label.",
    },
    {
        "id": "T05",
        "title": "Line-origination model and feature set",
        "decision": "Given the committed result that the ratings model does not beat the close, does the "
                    "model keep being developed, or does the project pivot to pricing only what the "
                    "market cannot see (availability, lineup structure, market microstructure)?",
        "options": [
            ("A. Keep improving the ratings model", "Cheap to try, but the published MAE gap is ~0.14 pts "
             "and the incremental-information test is p = 0.881; expect another null."),
            ("B. Pivot features to availability and slate structure", "Uses T02/T03 data; the only "
             "direction with information the close may not contain; unproven until those feeds exist."),
            ("C. Freeze the model, keep the pipeline", "Preserves a reproducible benchmark and stops "
             "spending on a null result."),
        ],
        "why_now": "It decides whether more analysis time goes into the model or into the data gaps.",
        "prerequisite_of": ["T08"],
        "owner_of_change": "A session can implement; the owner chooses the research direction.",
    },
    {
        "id": "T06",
        "title": "Correlation, parlays and player-prop combos",
        "decision": "Do we price multi-leg bets with measured joint outcomes (and a published correlation "
                    "matrix), or refuse to publish parlay edges at all?",
        "options": [
            ("A. Measure joint distributions from player box scores", "Already partially done (QB-WR1 r = "
             "0.562 in the root site) and reproducible; it prices correlation but not the operator's "
             "actual parlay price."),
            ("B. Wait for a parlay price archive, then price against the market", "Correct comparison, "
             "blocked on T02."),
            ("C. No parlay content", "Removes the most misleading surface on a site like this."),
        ],
        "why_now": "Parlays are where an independent-legs assumption does the most damage, and the hubs "
                   "publish four different QB-WR1 coefficients for the same quantity.",
        "prerequisite_of": ["T09"],
        "owner_of_change": "A session can publish one canonical matrix; the owner decides whether parlay "
                            "edges are ever shown.",
    },
    {
        "id": "T07",
        "title": "Validation gates and statistical rigour",
        "decision": "Which gate set is canonical, and are its thresholds (sample floor, correction, "
                    "push handling, leakage tests) enforced in CI or only described?",
        "options": [
            ("A. Adopt the root ten-gate set as the single standard", "One definition of 'passed'; every "
             "other hub reports against it; requires the labs' differing implementations to be labelled."),
            ("B. Keep per-lab gate sets, publish the differences", "Preserves each lab's independence; "
             "leaves the same strategy passing in one lab and failing in another."),
            ("C. Strengthen the gates (bootstrap CIs, BH correction, minimum-events floor, "
             "push-inclusive settlement)", "Fewer false positives; more candidates rejected, which is "
             "already the site's dominant outcome."),
        ],
        "why_now": "The audit found gate implementations that differ materially (push handling, repricing "
                   "in G9, pooled ATS arithmetic); the leaderboard is only as trustworthy as that choice.",
        "prerequisite_of": ["T08", "T09"],
        "owner_of_change": "A session can implement; the owner approves the standard.",
    },
    {
        "id": "T08",
        "title": "Removing luck: skill measurement and sizing",
        "decision": "What is the headline skill metric - closing-line value, Brier score against the "
                    "market, or ROI - and at what sample size is a strategy allowed to be called skilled?",
        "options": [
            ("A. CLV vs the close as the primary metric", "Least luck-dependent per bet, available "
             "immediately once lines are timestamped; needs T02 option C."),
            ("B. ROI with a fixed minimum-bets floor and variance-adjusted leaderboard", "Directly "
             "decision-relevant; noisy at small n and gameable by low-frequency bets."),
            ("C. Both, with ROI demoted until n is sufficient", "Harder to explain, hardest to game."),
        ],
        "why_now": "The repo already shows why: Pythagorean luck does not persist (r ~ 0.02) and every "
                   "published ROI sits inside its own noise band.",
        "prerequisite_of": ["T09"],
        "owner_of_change": "A session can define and compute it; the owner sets the floor.",
    },
    {
        "id": "T09",
        "title": "Leaderboard, rewards and competition governance",
        "decision": "Is there a leaderboard competition at all, what does a winner receive, and who funds "
                    "it - given that no strategy currently qualifies?",
        "options": [
            ("A. Run a paper leaderboard with zero payout", "Real signal about methodology, no money, no "
             "legal exposure; publishable today."),
            ("B. Fund prizes now", "Attracts participation but attaches a reward to a system with no "
             "qualified strategy and no verified legal position."),
            ("C. No competition", "Cheapest; loses the incentive mechanism the project was asked to build."),
        ],
        "why_now": "Four different reward schedules are published across the hubs; a competition with no "
                   "agreed prize rule cannot be judged, and 'reward for top performers' is currently "
                   "unfunded.",
        "prerequisite_of": [],
        "owner_of_change": "Owner funds/declines; a session writes the rule into the site.",
    },
    {
        "id": "T10",
        "title": "Site and information architecture",
        "decision": "Which surface is the canonical site, and do the sibling hubs get archived, merged, "
                    "or kept as linked category pages?",
        "options": [
            ("A. One root site, hubs become category subpages", "One navigation, one disclaimer, one "
             "place to review; needs link surgery and an archive page."),
            ("B. Keep every hub, link them all from one index", "Zero risk of losing work; the reader still "
             "faces ~20 near-identical pages with duplicated labels."),
            ("C. Freeze the hubs, build one review layer above them", "What review-board/ does now; cheap, "
             "but it adds a layer unless it later replaces the hubs."),
        ],
        "why_now": "The shared navigation now carries 28 links, including two labelled 'Suggestions hub', "
                   "and the same suggestion exists in seven registers with colliding IDs.",
        "prerequisite_of": ["T11", "T12"],
        "owner_of_change": "Root-site/final-integration owner (this session may not edit root nav).",
    },
    {
        "id": "T11",
        "title": "Reproducibility, CI and provenance hygiene",
        "decision": "Must every published number be regenerable in CI from committed inputs, and does a "
                    "failing check block publication?",
        "options": [
            ("A. Fail-closed CI on every PR (links, per-row sources, rebuild equality)", "Publishing a stale "
             "number becomes a build failure; costs CI minutes and forces the 28 source-less pages to be "
             "fixed or demoted."),
            ("B. Advisory checks", "Keeps velocity; this repository already has a direct-to-main refresh "
             "that bypassed CI (logged as an irregularity)."),
        ],
        "why_now": "The data snapshot behind the live pages is 12 days older than the slate on the site "
                   "that reports it, and the flag exists precisely because regeneration is not enforced.",
        "prerequisite_of": ["T12"],
        "owner_of_change": "A session can implement; the owner accepts the CI cost.",
    },
    {
        "id": "T12",
        "title": "Review workflow, disclosure and decision record",
        "decision": "How is a reviewer's choice recorded and enforced - status fields on the suggestion "
                    "page, a decision register, or nothing?",
        "options": [
            ("A. Decision register in the repo, one row per choice, with date and evidence", "Auditable, "
             "survives agent sessions, and stops a rejected idea being rebuilt next week."),
            ("B. Decisions live only in chat/issues", "Faster, but the site then re-proposes what was "
             "already refused."),
            ("C. No register, add a legal/responsible-use notice only", "Covers disclosure, not governance."),
        ],
        "why_now": "The brief is 'review suggestions and choose the best path before implementing'; "
                   "without a register there is no place to choose.",
        "prerequisite_of": [],
        "owner_of_change": "Owner writes the choice; the board stores it.",
    },
]

# ---------------------------------------------------------------- keyword rules
# Applied in order to the concatenated category + text of a row. Deliberately broad: a proposal
# about "disclaimers" and one about "legal review" are the same decision for a reviewer.
RULES = [
    ("T01", ["jurisdict", "legal", "licen", "responsib", "disclaim", "self-exclu", "age verification",
              "gambling commission", "operator terms", "geo", "account"]),
    ("T02", ["price feed", "odds feed", "closing line archive", "historical odds", "prop price",
              "player-prop price", "prices", "spread market data", "licensed", "market data",
              "opening line", "timestamp"]),
    ("T03", ["injury", "inactives", "availability", "report fetch", "point-in-time", "snapshot",
              "friday sweep", "starter confirmation", "ir list", "practice status"]),
    ("T04", ["depth chart", "depth-chart", "depth string", "starter", "backup", "next man up",
             "next-man-up", "2nd string", "stringing", "lineup sheet", "roster order"]),
    ("T05", ["model", "ratings", "feature", "blend", "origination", "originate", "projection",
             "quarterback", "weather", "rest", "home field", "home-field"]),
    ("T06", ["correlat", "parlay", "combination", "joint", "copula", "prop combo", "same-game",
             "leg dependency", "independence"]),
    ("T07", ["gate", "leakage", "multiple comparison", "benjamini", "correction", "push",
             "settlement", "void rule", "sign convention", "null", "test", "hypothesis", "sample",
             "negative control", "p-value", "arithmetic identity", "one-sided", "uncertainty"]),
    ("T08", ["clv", "skill", "luck", "variance", "brier", "roi", "sizing", "kelly", "shrink",
             "confidence interval", "ev ", "edge", "drawdown", "stake"]),
    ("T09", ["leaderboard", "reward", "prize", "funded", "competition", "tier", "winner",
             "payout", "gaming"]),
    ("T10", ["navigation", "nav ", "canonical", "hub", "duplicate", "archive index", "merge the",
             "consolidat", "site structure", "information architecture", "landing", "index page",
             "one page", "register above"]),
    ("T11", ["ci", "reproducib", "deterministic", "build", "workflow", "provenance", "hash",
             "re-run", "unit test", "verify", "audit", "as-of", "source link", "label",
             "third-party", "commit"], ),
    ("T12", ["decision", "approve", "reject", "review", "workflow of review", "record",
             "governance", "sign-off", "triage", "owner"], ),
]

# Rows the keyword rules place badly. Keyed "hub:id" -> topic.
OVERRIDES = {
    # question rows no keyword rule reaches; each is a hub:id pair, same namespace as the suggestion rows
    "decision-desk:Q-19": "T12",      # do flagged items block the merge - a review-workflow rule
    "lineup-lab:Q-03": "T03",         # why an empty injury report says "no injuries"
    "lineup-lab:Q-06": "T03",         # pricing a cluster of defensive absences
    "lineup-lab:Q-08": "T08",         # regression candidates: skill vs luck, not injuries
    "suggestions:Q-07": "T11",        # independent recomputation of published numbers
    "decision-desk:S-01": "T07",     # "no-bet status quo until gates pass" is a gate decision
    "decision-desk:S-05": "T02",     # line timestamping / CLV logger is price data
    "decision-desk:S-13": "T11",
    "decision-hub:S-01": "T10",
    "decision-hub:S-03": "T08",
    "decision-hub:S-13": "T10",
    "lineup-lab:SUG-01": "T03",
    "nfl-command:SUG-07": "T09",
    "site:SG-01": "T12",
    "site:SG-11": "T08",
    "suggestions:SUG-01": "T12",
    "verify-hub:SG-01": "T10",
    "lineup-lab:SUG-03": "T05",   # snap-share / NGS charting = model feature input
    "lineup-lab:SUG-11": "T03",   # T-85 inactive-list check = availability capture
    "nfl-command:SUG-03": "T03",  # IR vs report reconciliation = availability capture
    "verify-hub:SG-07": "T11",    # dead-URL / retrieval-date hygiene
}

_TOPIC_IDS = {t["id"] for t in TOPICS}


def _pattern(word: str):
    """Short words must match whole; longer ones are treated as stems (prefix matches)."""
    w = word.lower().strip()
    if not w:
        return None
    tail = r"\b" if len(w.split()[-1]) <= 3 else r""
    return re.compile(r"\b" + re.escape(w).replace(r"\ ", r"\s+") + tail)


PATTERNS = [(tid, [(p, word) for word in words
                  for p in [_pattern(word)] if p])
            for tid, words in RULES]


def classify(hub: str, hub_id: str, text: str) -> str:
    """Return the topic id a register row belongs to (or '' when nothing matches)."""
    key = f"{hub}:{hub_id}"
    if key in OVERRIDES:
        return OVERRIDES[key]
    low = text.lower()
    scores = {}
    for tid, plist in PATTERNS:
        score = 0
        for pat, word in plist:
            n = len(pat.findall(low))
            if n:
                score += 2 if n >= 2 else 1
        if score:
            scores[tid] = score
    if not scores:
        return ""
    best = max(scores.values())
    # deterministic tie-break: earliest rule in the list wins
    for tid, _ in RULES:
        if scores.get(tid) == best:
            return tid if tid in _TOPIC_IDS else ""
    return ""


def audit(hub: str, hub_id: str, text: str) -> str:
    """Human-readable trace of why a row landed where it did (used on the page)."""
    key = f"{hub}:{hub_id}"
    if key in OVERRIDES:
        return "explicit override"
    low = text.lower()
    out = []
    for tid, plist in PATTERNS:
        for pat, word in plist:
            n = len(pat.findall(low))
            if n:
                out.append(f"{tid}:{word}({n})")
    return ", ".join(out[:6])
