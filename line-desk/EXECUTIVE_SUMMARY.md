# Line Desk — executive summary (2026-11-14)

Line Desk delivers the brief's origination-requirements infrastructure as a deterministic,
source-linked static site (`line-desk/index.html` + 14 category pages). Headlines:

| Topic | State | Evidence |
| --- | --- | --- |
| Verified results feed | **44 official finals** transcribed first-hand (Weeks 7, 8, 9 + Week-10 Thursday), each row linked to its NFL.com week page and game-centre page; cross-check vs the committed third-party snapshot: **27/27 match, 0 mismatches**. Weeks 1–6 (93 games) pending official capture — scores left blank. | `line-desk/data/results_feed.json` |
| Price-snapshot store | Contract live: **45 market records** (15 games × side, total, moneyline); our open line captured on 45/45; **market prices 0/45** (no official public source exists — the NFL's official betting feed is distributed to operators by an exclusive distributor); our close 0/45 (second capture not scheduled). Nothing back-filled. | `line-desk/data/price_snapshots.json` |
| Origination order | Fixed **side → total → moneyline**, enforced in `compute.py`; fair line / market line / difference published as separate columns for all three markets; market and difference blank by policy; all 15 fair lines settled against official results. | `line-desk/data/origination.json` |
| Signal vs staking | Two separate ranks. Signal rank = gates + outcome statistics only; staking (ROI, CI) reported in its own block and **never** enters the rank. Demonstration: the best staking rank (S7, +1.51% ROI) is signal **#5 of 7**; the best signal rank (S6) is staking #3. | `line-desk/data/leaderboard.json` |
| Demotion gate | Promotions P1–P3 and demotions D1-CLV (price-store), D2-outcome (n ≥ 200 and one-sided 95% ROI upper bound < 0), D3-integrity (HOLD on missing data). Dry run: **0 promoted, 0 demoted, all stay PAPER** — 0 of 7 candidates pass 10/10 gates and no strategy is live. | `line-desk/data/gates.json` |
| Official-only correlations | **8 coefficients computed only from NFL.com standings transcriptions** (2026 n=32, 2025 n=32, pooled n=64), each with n and a 95% Fisher-z CI (NIST method). Net points vs wins: r = +0.848 (n=32, 2026); pooled points-for vs wins r = +0.800 (n=64). No third-party number enters any coefficient. | `line-desk/data/correlations.json` |
| Replacement depth | Store and schema built (replacement player, string tier 1st–4th, depth source); 11 official injury rows first-hand; **0/11 replacements named, 0/11 string tiers** — the league depth-chart path returns HTTP 404 and the official report has no depth column (both verified first-hand). Blank + flagged, never proxied. | `line-desk/data/depth.json` |
| Requirements trace | 19 requirements: **11 built**, 6 partial/blocked with named discovery paths, 2 existing in sibling hubs. | `line-desk/data/requirements.json` |
| Suggestions / questions | 12 proposals (all *proposed — awaiting reviewer*; nothing implemented) and 15 decision-readiness questions with have/missing/discovery fields. | `line-desk/data/{suggestions,questions}.json` |
| Flagged for review | 16 irregularities, each with a source: no official price source, empty price store, feed coverage gap, stale snapshot, dual-originator line discrepancy (1.5–9.0 pts), depth 404, unfunded rewards, committed `.venv-b6` (6,214 files), and more. | `line-desk/data/flagged.json` |

**Verification policy in one line:** every table row ends in a source link; any value that cannot be
confirmed from an official source is left blank and flagged — nothing is inferred.

**What would change the picture (in order):** (1) an official timestamped price feed (unblocks
market columns, closing-line value, official ROI — SG-01/Q-01); (2) automated official results
capture for weeks 1–6 (completes the feed — SG-02/Q-04); (3) a club-official depth source
(unblocks string tiers and the deficiency signal — SG-04/Q-05).

**Checks:** `line-desk/scripts/verify.py` (blank policy, per-row sources, recomputed correlations,
deterministic rebuild) plus the repository suites `tests/check_site.py`, `scripts/check_links.py`,
`scripts/validate_data.py`, `tests/check_data.py`, `tests/check_derived.py` — all PASS on this tree.
