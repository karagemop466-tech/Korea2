#!/usr/bin/env python3
"""Build the two registers a decision needs before anyone writes more code:

  * suggestions.json - concrete proposals, each with a cost, an expected payoff, the evidence
    behind it, a recommended choice, and an explicit review status. Nothing here is a promise of a
    reward or of profit.
  * questions.json   - the questions a reasonable decision needs answered, split into "we can answer
    this from what we have", "we can answer this with one more feed", and "nobody can answer this
    yet", with the open/missing information listed beside each one.

Both files are data, not prose: the site renders them, and the same JSON is what a reviewer edits
when they accept, reject or park a proposal.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = Path(__file__).resolve().parents[1]

NFL = "https://www.nfl.com"
NFLVERSE = "https://github.com/nflverse/nflverse-data"
NFLVERSE_LICENSE = "https://github.com/nflverse/nflverse-data/blob/main/LICENSE.md"
INJURY = f"{NFL}/injuries/league/2026/reg10"
DATES = f"{NFL}/news/2026-27-national-football-league-important-dates"
RULEBOOK = "https://operations.nfl.com/rules-officiating/2026-nfl-rulebook"
STATS_GUIDE = "https://www.nflgsis.com/gsis/documentation/stadiumguides/guide_for_statisticians.pdf"
SNAPS = "https://nflreadr.nflverse.com/articles/dictionary_snap_counts.html"
DEPTH = "https://nflreadr.nflverse.com/articles/dictionary_depth_charts.html"
INJDICT = "https://nflreadr.nflverse.com/articles/dictionary_injuries.html"
PARTIC = "https://nflreadr.nflverse.com/articles/dictionary_participation.html"
NIST_CORR = "https://www.itl.nist.gov/div898/handbook/pmc/section5/pmc542.htm"
NIST_BOOT = "https://www.itl.nist.gov/div898/handbook/eda/section3/eda357.htm"
BENJAMINI = "https://www.jstor.org/stable/2346101"
KELLY = "https://www.princeton.edu/~wbialek/rome/refs/kelly_56.pdf"
SKLEARN_LEAK = "https://scikit-learn.org/stable/common_pitfalls.html"
BAILEY_LOPEZ = "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551"

# ---------------------------------------------------------------------------------------------
# SUGGESTIONS
# ---------------------------------------------------------------------------------------------
SUGGESTIONS = [
    {
        "id": "SG-01",
        "title": "Approve or reject the site's current answer before adding another model",
        "area": "decision",
        "problem": ("The three sibling research builds in this repository disagree in places, and a reader "
                    "cannot tell which verdict to act on: the root site says the closing market beats the "
                    "model, the Skill Lab says 0 of 21 strategies qualify, the origination lab publishes a "
                    "2026 Week 9 slate that cannot be priced because no prop prices exist."),
        "proposal": ("Adopt one decision rule for the whole repository: a strategy is only worth building "
                     "further once it passes the ten published gates on the committed extract, and no page "
                     "may show a slate, an edge or a reward until it does."),
        "effort": "S", "payoff": "High", "risk": "Low",
        "evidence": "site/data/signals.json (0 of 23 variants pass), data/derived/leaderboard.json (0 of 9)",
        "recommend": "Approve",
        "review": "pending",
        "source": f"{NFLVERSE}/releases/tag/schedules",
        "source_text": "evidence is recomputed from this feed on every run",
    },
    {
        "id": "SG-02",
        "title": "Timestamp every line, or stop calling any edge 'live'",
        "area": "data",
        "problem": ("The only line the repository holds is one closing number per game with no capture "
                    "time. That makes Gate G1 - point-in-time integrity - impossible to satisfy, which is "
                    "why every candidate in this session's lab fails at gate one regardless of its ROI."),
        "proposal": ("Add a capture job that writes (game_id, book, market, line, price, captured_utc) "
                     "every N minutes into a committed append-only file, starting with the current week. "
                     "Ten days of that is worth more than any new model, because it is the only way to "
                     "measure closing-line value."),
        "effort": "M", "payoff": "Very high", "risk": "Medium - a licensed price source is needed; none is verified here",
        "evidence": "site/data/verification.json IR-07; data/derived/strategies.json gates_definition[0]",
        "recommend": "Approve",
        "review": "pending",
        "source": DATES,
        "source_text": "the league calendar fixes when practice/game-status reports are filed, the anchor for a capture schedule",
    },
    {
        "id": "SG-03",
        "title": "Commit the injury, depth-chart and snap-count feeds on a runner",
        "area": "injury",
        "problem": ("Injury and 2nd/3rd/4th-string depth work cannot be done from the sandbox: the release "
                    "assets redirect to a host it cannot reach, and none of the three feeds is committed. "
                    "The Injury & depth page therefore has 108 transcribed players and 108 blank "
                    "'which string' cells."),
        "proposal": ("Extend the existing data-pipeline workflow (which already downloads on GitHub-hosted "
                     "runners) to fetch injuries_{season}, depth_charts_{season} and snap_counts_{season}, "
                     "then commit a pruned weekly summary with the download timestamp. Handle the 2024->2025 "
                     "depth-chart schema change explicitly."),
        "effort": "M", "payoff": "High", "risk": "Low - all three releases exist and are CC-BY-4.0",
        "evidence": "site/data/injury_depth.json feeds F-1..F-4; nflreadr data dictionaries",
        "recommend": "Approve",
        "review": "pending",
        "source": DEPTH,
        "source_text": "pos_rank is the only field that answers the 1st/2nd/3rd/4th-string question",
    },
    {
        "id": "SG-04",
        "title": "Fix the ATS coin-flip statistic before it is cited again",
        "area": "measurement",
        "problem": ("data/derived/luck.json reports n=13,784 ATS bets and a 50.0% cover rate with p=1.0. "
                    "13,784 is exactly twice 6,892 because every game contributes a cover on both sides, "
                    "so the statistic is 50% by construction and the p-value means nothing. The "
                    "conclusion ('no exploitable tilt') is still supported, but by the home-side rate of "
                    "48.91%, not by that number."),
        "proposal": "Replace the pooled per-team-game rate with a one-sided home cover rate and report the exact binomial p.",
        "effort": "S", "payoff": "Medium", "risk": "Low",
        "evidence": "site/data/verification.json IR-01 and check V-04",
        "recommend": "Approve",
        "review": "pending",
        "source": f"{NFLVERSE}/releases/tag/schedules",
        "source_text": "recomputable from spread_line, home_score and away_score",
    },
    {
        "id": "SG-05",
        "title": "Publish the parlay pricing gap as the headline, not correlation coefficients",
        "area": "pricing",
        "problem": ("The site leads with r = 0.561 between QB and WR1 yards. A reader cannot act on a "
                    "correlation coefficient; they can act on 'a 2-leg same-team ticket priced "
                    "independently is short by 38% on its fair price'."),
        "proposal": ("Lead with the measured joint-vs-product table, keep the coefficient as supporting "
                     "detail, and state plainly that a house pricing legs independently takes an extra "
                     "margin on correlated tickets."),
        "effort": "S", "payoff": "High", "risk": "Low",
        "evidence": "site/data/parlay.json joints and premium tables",
        "recommend": "Approve",
        "review": "pending",
        "source": f"{NFLVERSE}/releases/tag/stats_player",
        "source_text": "measured on 5,896 team-games, 2015-2026",
    },
    {
        "id": "SG-06",
        "title": "Give the leaderboard a reward rule that cannot be gamed by variance",
        "area": "competition",
        "problem": ("'Rewards for top performing strategies' is currently undefined, and a naive "
                    "highest-ROI rule rewards the luckiest of many variants. With 23 variants tested here "
                    "the best zero-skill per-bet Sharpe rises with the number of tries."),
        "proposal": ("Score on gates passed first, then on deflated Sharpe, with a minimum of 300 settled "
                     "bets and a required positive lower bound. Pay nothing until a strategy clears all "
                     "ten gates, and cap the number of variants a single entrant may submit."),
        "effort": "S", "payoff": "High", "risk": "Low - no money is held by this project",
        "evidence": "site/data/signals.json meta.multiplicity and the G8 gate detail",
        "recommend": "Approve",
        "review": "pending",
        "source": BAILEY_LOPEZ,
        "source_text": "deflated Sharpe ratio: expected maximum Sharpe under the null",
    },
    {
        "id": "SG-07",
        "title": "Stop publishing a 'current slate' that the data cannot support",
        "area": "publication",
        "problem": ("The committed extract ends 2026-11-01 while the official Week 10 injury report "
                    "(games of 12-15 November) is already out. Any latest-week slate is a snapshot at "
                    "best and stale at worst."),
        "proposal": "Label every week-sensitive page with the data cut-off and hide anything after it.",
        "effort": "S", "payoff": "Medium", "risk": "Low",
        "evidence": "site/data/verification.json IR-03; site/data/injury_depth.json IF-05",
        "recommend": "Approve",
        "review": "pending",
        "source": INJURY,
        "source_text": "the official page is ahead of the committed extract",
    },
    {
        "id": "SG-08",
        "title": "Quantify what a starting QB absence is worth, before adding any other injury signal",
        "area": "injury",
        "problem": ("Losing a starting QB is the one injury the market is known to move on, and this "
                    "repository has never measured it. The backup-QB candidate in this session's lab "
                    "returned ROI -13.9% over 208 bets, which is evidence that the naive version of the "
                    "signal is already priced - but the sample is small and the rule was crude."),
        "proposal": ("Once SG-03 lands, estimate the line movement attributable to a QB change from "
                     "timestamped prices, and only then build the in-game model. Expected value comes "
                     "from the timing of the news, not from the fact of the injury."),
        "effort": "L", "payoff": "High", "risk": "Medium - needs SG-02 and SG-03 first",
        "evidence": "site/data/signals.json S08_backup_qb_away", "recommend": "Park until SG-02 and SG-03 are done",
        "review": "pending",
        "source": INJURY,
        "source_text": "the report is the input; the timestamp is what makes it tradeable",
    },
    {
        "id": "SG-09",
        "title": "Treat third-party feeds as third-party, in the UI",
        "area": "provenance",
        "problem": ("Several numbers rest on the nflverse mirror, which redistributes the NFL feed, and "
                    "snap counts come from Pro Football Reference. The site sometimes reads as if the NFL "
                    "itself published the number."),
        "proposal": ("Add a provenance tag to every table: official NFL / mirrored official feed / "
                     "third-party. The same tag should appear on the source register page."),
        "effort": "S", "payoff": "Medium", "risk": "Low",
        "evidence": "site/data/injury_depth.json IF-03; data/sources.json",
        "recommend": "Approve",
        "review": "pending",
        "source": SNAPS,
        "source_text": "nflreadr describes snap counts as provided by Pro Football Reference",
    },
    {
        "id": "SG-10",
        "title": "Add a leakage test to CI that fails on any future-dated feature",
        "area": "process",
        "problem": ("G1 fails structurally today, and nothing stops a future commit from quietly using a "
                    "post-kickoff field. A gate that is only described in prose is not a gate."),
        "proposal": ("Add a CI check that every column used by a candidate rule is on an allow-list of "
                     "pre-kickoff fields, and that every join is on a strictly earlier date."),
        "effort": "S", "payoff": "High", "risk": "Low",
        "evidence": "site/data/verification.json IR-07; .github/workflows/validate.yml",
        "recommend": "Approve",
        "review": "pending",
        "source": SKLEARN_LEAK,
        "source_text": "common pitfalls: data leakage in time-ordered problems",
    },
    {
        "id": "SG-11",
        "title": "Do not chase a profit until the hold is modelled",
        "area": "pricing",
        "problem": ("At -110 a bettor needs 52.381% of decided bets to break even; the repository quotes "
                    "this but never shows what it implies for a 4-leg correlated ticket, where the house "
                    "margin compounds."),
        "proposal": ("Publish the break-even rate beside every strategy ROI, and compute the effective "
                     "hold on the measured joint prices rather than on independent multiplications."),
        "effort": "S", "payoff": "Medium", "risk": "Low",
        "evidence": "site/data/parlay.json premium table", "recommend": "Approve",
        "review": "pending",
        "source": f"{NFLVERSE}/releases/tag/schedules",
        "source_text": "prices in the feed are used for settlement, not assumed",
    },
    {
        "id": "SG-12",
        "title": "Fund nothing, and say so, until there is a verified execution path",
        "area": "governance",
        "problem": ("The brief asks for a leaderboard that pays rewards. No operator account, jurisdiction, "
                    "limit, or licence has been verified here, and this repository cannot verify one."),
        "proposal": ("Keep every reward tier marked 'not funded'. Publish a one-page execution checklist "
                     "(jurisdiction, age, licence, deposit limits, responsible-gambling links) that a "
                     "human must complete before any capital is exposed."),
        "effort": "S", "payoff": "Required", "risk": "High if skipped",
        "evidence": "pages/flagged.html; site/data/verification.json meta.caveat",
        "recommend": "Approve", "review": "pending",
        "source": f"{NFL}/news",
        "source_text": "no official NFL page evidences a betting licence for this project",
    },
]

# ---------------------------------------------------------------------------------------------
# QUESTIONS  (each carries what we have, what we are missing, and who can answer it)
# ---------------------------------------------------------------------------------------------
QUESTIONS = [
    # ---- answerable now ---------------------------------------------------------------------
    {"id": "Q-01", "group": "Answerable now",
     "question": "Do the headline numbers on the live site reproduce from the committed data?",
     "answer": "Yes, with two exceptions that are themselves findings.",
     "have": ("19 independent checks: 16 agree, 0 unverified, 2 mismatch, 1 documented difference. "
              "The two mismatches are the ATS coin-flip statistic (IR-01), not the model numbers."),
     "missing": "Nothing for these numbers. A price feed is still missing for any ROI claim.",
     "decision_needed": "Accept the numbers as reproducible and fix the ATS statistic.",
     "owner": "data", "source": "https://github.com/karagemop466-tech/Korea2/blob/main/site/data/verification.json"},
    {"id": "Q-02", "group": "Answerable now",
     "question": "Does the current model beat the closing line?",
     "answer": "No. Walk-forward spread MAE is 10.391 against the market's 9.711 on the same 936 games, "
               "and the coefficient on the model after controlling for the close is -0.019 (p = 0.881).",
     "have": "data/derived/predictions.csv, 2023-2026, 936 games.",
     "missing": "Nothing for this question; a different model is a different question.",
     "decision_needed": "Stop tuning this family of ratings models and spend the effort on timing data.",
     "owner": "modelling", "source": "https://github.com/karagemop466-tech/Korea2/blob/main/data/derived/model.json"},
    {"id": "Q-03", "group": "Answerable now",
     "question": "Are same-game parlay legs independent?",
     "answer": ("No. QB passing yards and WR1 receiving yards correlate at +0.560 over 5,896 team-games, "
                "and the 2-leg joint is 0.336 against a product of 0.243 - 38% higher."),
     "have": "data/derived/player_week.csv.gz (208,231 rows).",
     "missing": "Historical prop prices, so the gap is a pricing fact, not yet a profit.",
     "decision_needed": "Publish the pricing gap, and do not quote an independent-leg parlay ROI.",
     "owner": "pricing", "source": "https://github.com/karagemop466-tech/Korea2/blob/main/site/data/parlay.json"},
    {"id": "Q-04", "group": "Answerable now",
     "question": "Is a season win-loss record a repeatable skill?",
     "answer": "No. Pythagorean luck does not carry to the next season (r = 0.024 over 842 team-seasons).",
     "have": "1999-2026 schedules extract.",
     "missing": "Nothing for the conclusion. Roster turnover would explain it but is not committed.",
     "decision_needed": "Do not build a strategy on last season's record; if anything, fade it.",
     "owner": "modelling", "source": "https://github.com/karagemop466-tech/Korea2/blob/main/data/derived/luck.json"},
    {"id": "Q-05", "group": "Answerable now",
     "question": "Does any candidate strategy pass the ten gates?",
     "answer": "No. 0 of 23 variants tested in this session and 0 of 9 published candidates.",
     "have": "site/data/signals.json with a per-gate pass/fail and the exact failure reason.",
     "missing": "A candidate that survives G1 (see Q-11).",
     "decision_needed": "Do not fund, publish a pick, or build a ledger on top of these candidates.",
     "owner": "research", "source": "https://github.com/karagemop466-tech/Korea2/blob/main/site/data/signals.json"},
    {"id": "Q-06", "group": "Answerable now",
     "question": "Is the repository internally consistent about its own provenance?",
     "answer": ("Mostly. Heavily documented, with a working independent recomputation, but the README "
                "quotes a model MAE of 10.38/9.70 while the site and the data show 10.391/9.711, and the "
                "ATS statistic is wrong in the way described in Q-01."),
     "have": "This session's line-by-line review, 10 irregularities with sources.",
     "missing": "An owner for README prose; the data pipeline regenerates the site, not the README.",
     "decision_needed": "Assign the README fix and the ATS fix to one owner.",
     "owner": "docs", "source": "https://github.com/karagemop466-tech/Korea2/blob/main/site/data/verification.json"},

    # ---- answerable with one more feed ------------------------------------------------------
    {"id": "Q-07", "group": "One feed away",
     "question": "Which starters are out, and who is the 2nd/3rd/4th-string replacement?",
     "answer": "Not yet. The official injury report gives Out/Doubtful/Questionable but no depth rank.",
     "have": "108 players transcribed from the official Week 10 report, five games in full.",
     "missing": ("depth_charts_{season} (pos_rank) and snap_counts_{season} - both published upstream, "
                 "neither committed, both unreachable from this sandbox."),
     "decision_needed": "Run the download on a runner (SG-03) or accept that this question stays open.",
     "owner": "data", "source": DEPTH},
    {"id": "Q-08", "group": "One feed away",
     "question": "Did the backup actually play, and how much?",
     "answer": "Not yet. Box scores show what a player did, not how many snaps he was on the field for.",
     "have": "season snap totals in the upstream release, game-level snap counts in snap_counts.",
     "missing": "snap_counts_{season} (third-party: Pro Football Reference) or pbp_participation.",
     "decision_needed": "Pick one: snap counts for breadth, participation for precision. Do not use both as if independent.",
     "owner": "data", "source": PARTIC},
    {"id": "Q-09", "group": "One feed away",
     "question": "How much does the market move when a starter is ruled out?",
     "answer": "Unknown and unmeasurable until prices are captured over time.",
     "have": "One closing line per game.",
     "missing": "SG-02's timestamped capture; the injury feed dates the news.",
     "decision_needed": "Fund the capture first; it is the only way this question ever gets an answer.",
     "owner": "data", "source": INJDICT},
    {"id": "Q-10", "group": "One feed away",
     "question": "What is a player prop actually priced at, historically?",
     "answer": "Not in this repository. Accuracy is measured; price is not.",
     "have": "Prop forecasts and MAE against realised box scores (data/derived/props.json).",
     "missing": "Any licensed historical prop price. None is committed, and none is implied.",
     "decision_needed": "Either license a price history or stop listing prop combos as a tested family.",
     "owner": "pricing", "source": "https://github.com/karagemop466-tech/Korea2/blob/main/data/derived/props.json"},

    # ---- blocked on a decision, not on data ----------------------------------------------
    {"id": "Q-11", "group": "Blocked on a decision",
     "question": "Can Gate G1 (point-in-time integrity) ever pass in the current design?",
     "answer": "No. One un-timestamped closing line per game cannot evidence 'the price at bet time'.",
     "have": "The gate text itself, and the data that fails it.",
     "missing": "A timestamped capture (SG-02).",
     "decision_needed": "Either fund the capture or restate G1 as 'closing-line settlement only'.",
     "owner": "governance", "source": "https://github.com/karagemop466-tech/Korea2/blob/main/data/derived/strategies.json"},
    {"id": "Q-12", "group": "Blocked on a decision",
     "question": "What does 'top performing' mean for the rewards?",
     "answer": "Undefined today. Highest ROI rewards luck; gates-passed-first rewards process.",
     "have": "Ten published gates and a deflated-Sharpe threshold.",
     "missing": "A written reward rule, a variant cap, and a statement that no pool is funded.",
     "decision_needed": "Adopt SG-06.",
     "owner": "governance", "source": BAILEY_LOPEZ},
    {"id": "Q-13", "group": "Blocked on a decision",
     "question": "Which sibling build is the product?",
     "answer": ("Seven static sites exist from parallel sessions (root, dashboard, nfl-lines, nfl-research, "
                "research-desk, quant-lab, origination-lab, skill-lab, origination). They disagree in "
                "places and none is marked canonical."),
     "have": "COORDINATION.md records every session's claim and result.",
     "missing": "A single canonical site and an archive rule for the rest.",
     "decision_needed": "Adopt SG-01 and SG-07: one canonical site, the rest moved under /archive/.",
     "owner": "product", "source": "https://github.com/karagemop466-tech/Korea2/blob/main/COORDINATION.md"},
    {"id": "Q-14", "group": "Blocked on a decision",
     "question": "Is there a lawful, verified way to place a bet for this project?",
     "answer": "Not verified. No operator account, jurisdiction, licence or limit has been checked.",
     "have": "A statement on every page that this is research, not betting advice.",
     "missing": "A jurisdiction decision and an operator's published terms, read by a human.",
     "decision_needed": "Complete the execution checklist before any capital is discussed.",
     "owner": "governance", "source": f"{NFL}/news"},

    # ---- nobody can answer yet -----------------------------------------------------------
    {"id": "Q-15", "group": "Cannot be answered yet",
     "question": "Does any strategy make money after the hold?",
     "answer": "Unknown. Every measured candidate loses, which is evidence but not proof of impossibility.",
     "have": "23 variants settled at the closing line, all negative or insignificant.",
     "missing": "A timestamped price series, a licensed prop price, and a candidate that clears G1.",
     "decision_needed": "None yet - this is the question the whole project exists to answer.",
     "owner": "research", "source": NIST_BOOT},
    {"id": "Q-16", "group": "Cannot be answered yet",
     "question": "How much of a team's week-to-week variance is injury-driven rather than noise?",
     "answer": "Unknown. It needs the three missing feeds plus a variance decomposition.",
     "have": "A variance decomposition for season records (luck.json).",
     "missing": "Lineup continuity data at the player level.",
     "decision_needed": "Park until SG-03.",
     "owner": "research", "source": NIST_CORR},
    {"id": "Q-17", "group": "Cannot be answered yet",
     "question": "Would a correlated-parlay strategy be profitable at real, available prices?",
     "answer": "Unknown. The pricing gap is measured; the available price is not.",
     "have": "Measured joint vs independent pricing on 5,896 team-games.",
     "missing": "Available same-game-parlay prices and the operator's correlation policy (terms change).",
     "decision_needed": "Read the operator's current same-game-parlay terms; do not assume they ignore correlation.",
     "owner": "pricing", "source": RULEBOOK},
]

FLAGGED = [
    {"id": "QF-01", "item": "README model MAE is stale", "detail": "README says 10.38 vs 9.70; the data says 10.391 vs 9.711.", "source": "https://github.com/karagemop466-tech/Korea2/blob/main/README.md"},
    {"id": "QF-02", "item": "Canonical site undecided", "detail": "Nine static builds exist from parallel sessions; none is marked canonical.", "source": "https://github.com/karagemop466-tech/Korea2/blob/main/COORDINATION.md"},
    {"id": "QF-03", "item": "Reward pool not funded", "detail": "No prize, pool or payout exists or is promised anywhere in the repository.", "source": "https://github.com/karagemop466-tech/Korea2/blob/main/pages/flagged.html"},
    {"id": "QF-04", "item": "No licensed price or execution path verified", "detail": "No operator terms, jurisdiction or limit has been checked by this session.", "source": "https://github.com/karagemop466-tech/Korea2/blob/main/pages/sources.html"},
    {"id": "QF-05", "item": "Snapshot, not live data", "detail": "Committed results end 2026-11-01; the official injury report is already at Week 10 (12-15 Nov).", "source": INJURY},
    {"id": "QF-06", "item": "Third-party and mirror feeds presented as authoritative", "detail": "Snap counts are Pro Football Reference; the schedules/player feeds are the nflverse mirror of the NFL feed.", "source": SNAPS},
    {"id": "QF-07", "item": "Depth rank for every injured player is blank", "detail": "108 transcribed players, 0 verified starter/backup claims, because no depth-chart feed is committed.", "source": DEPTH},
    {"id": "QF-08", "item": "Injury report is mid-week", "detail": "Most game-status cells were blank at retrieval; a mid-week snapshot is not final availability.", "source": INJURY},
]

REVIEW_WORKFLOW = [
    {"step": 1, "label": "Triage", "detail": "Read the suggestion, its evidence and its cost. Nothing is implemented at this step."},
    {"step": 2, "label": "Check the evidence", "detail": "Open the linked source and the referenced data file. A suggestion with an unverifiable claim is sent back, not approved."},
    {"step": 3, "label": "Choose a path", "detail": "Accept, park, or reject. Exactly one path per suggestion, recorded in the register so the next session cannot silently reopen it."},
    {"step": 4, "label": "Assign a gate", "detail": "Say which of the ten gates the change is meant to move. A change that moves no gate is parked."},
    {"step": 5, "label": "Implement behind the gate", "detail": "Ship it with a check that fails if the gate regresses. No strategy page updates on an unapproved change."},
    {"step": 6, "label": "Re-measure", "detail": "Re-run the pipeline and publish the new numbers, including the ones that got worse."},
]


def stamp() -> str:
    """Deterministic build stamp.

    Wall-clock generation times made every CI rebuild differ from the committed file, which broke the
    reproducibility check for a reason that had nothing to do with the numbers. The stamp is therefore
    the date the committed data ends, read from data/provenance.json.
    """
    p = ROOT / "data" / "provenance.json"
    try:
        with open(p) as fh:
            day = json.load(fh).get("data_as_of_gameday")
    except (OSError, ValueError):
        day = None
    return f"{day}T00:00:00Z" if day else "unknown"


def main() -> int:
    import pandas as pd

    sug = {
        "meta": {
            "session": "arena/90e4fdbe-korea2",
            "generated_utc": stamp(),
            "count": len(SUGGESTIONS),
            "statuses": ["pending", "accepted", "parked", "rejected"],
            "how_to_use": ("Each row is a decision, not a task. Read the evidence, pick one of the four "
                           "statuses, and record it here before any code changes. The workflow on the "
                           "Suggestions page is the order the review is meant to happen in."),
            "rule": "No suggestion may be implemented while its status is 'pending'.",
        },
        "review_workflow": REVIEW_WORKFLOW,
        "suggestions": SUGGESTIONS,
        "sources": {
            "nflverse": NFLVERSE, "license": NFLVERSE_LICENSE, "injury": INJURY, "dates": DATES,
            "stats_guide": STATS_GUIDE, "snaps": SNAPS, "depth": DEPTH, "participation": PARTIC,
            "rulebook": RULEBOOK, "nist_corr": NIST_CORR, "nist_boot": NIST_BOOT,
            "benjamini_hochberg": BENJAMINI, "kelly": KELLY, "sklearn_leak": SKLEARN_LEAK,
            "deflated_sharpe": BAILEY_LOPEZ,
        },
    }
    qs = {
        "meta": {
            "session": "arena/90e4fdbe-korea2",
            "generated_utc": stamp(),
            "count": len(QUESTIONS),
            "groups": ["Answerable now", "One feed away", "Blocked on a decision", "Cannot be answered yet"],
            "rule": ("A question is only marked answered when the answer is computed from a committed file "
                     "and that file is linked. Anything else says what is missing."),
        },
        "questions": QUESTIONS,
        "flagged": FLAGGED,
    }
    (SITE / "data" / "suggestions.json").write_text(json.dumps(sug, indent=1) + "\n")
    (SITE / "data" / "questions.json").write_text(json.dumps(qs, indent=1) + "\n")
    print(f"wrote suggestions.json ({len(SUGGESTIONS)}) and questions.json ({len(QUESTIONS)} + {len(FLAGGED)} flagged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
