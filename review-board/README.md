# Review Board — `review-board/`

A review layer, not another model. This hub reads the proposal registers and decision-readiness registers that
the repository's sibling hubs publish, collapses them into clusters a person can actually decide on, and sets
each against what the official sources support today. It starts no pipeline, edits no sibling hub, and records
no decision on a reviewer's behalf.

Slate data here is a **capture**, dated 2026-11-13 (Week 10 of the 2026 season). Analytical figures quoted from
sibling hubs carry their own stamps and are shown as of those stamps.

## Layout

```
review-board/
├── index.html                     landing page: KPI grid, phase table, tile grid to every subpage
├── pages/                        13 subpages, one per review surface (see the nav)
├── assets/style.css              design language from scripts/lib/site.py (deep-green/cream/Golden-page)
├── EXECUTIVE_SUMMARY.md          prose companion to pages/executive.html
├── data/
│   ├── queue.json                generated: every suggestion row from every hub, clustered
│   ├── readiness.json            generated: every decision question, normalised + clustered
│   ├── injuries.json             generated: current-slate availability from the official report
│   ├── injury_delta.json         generated: this capture versus a sibling hub's earlier capture
│   ├── hub_map.json              generated: inventory of every hub directory and how it is wired up
│   ├── reconciliation.json       generated: the same quantity published with different values by
│   │                             different hubs, gate-ID collisions, as-of stamps
│   ├── program.json              authored: phases, review rules, signals, gates, competition, gaps
│   ├── sources.json              authored: the source register every table row links
│   ├── flags.json                authored: irregularities and everything left blank, with reasons
│   └── raw/injury_report_2026-11-13_week10.csv   the transcription rebuilds read
└── scripts/
    ├── ingest.py                 capture + sibling registers → the six generated registers
    ├── topics.py                 cluster definitions and the routing rules
    ├── build_site.py             registers → pages (no numbers typed into templates)
    └── verify_all.py             the checks below, as code
```

## Rebuild and verify

```bash
python3 review-board/scripts/ingest.py      # reads sibling registers + the raw capture, writes data/*.json
python3 review-board/scripts/build_site.py  # data/*.json -> index.html + pages/*.html
python3 review-board/scripts/verify_all.py  # 121 checks; exit 1 on any failure
```

Stdlib only. No pandas, no numpy, no network — the same commands run in `.github/workflows/review-board.yml`.
Both generators are deterministic: rebuilding into a clean checkout produces byte-identical output, and every
generated register carries `_generated_by` plus `_generated_from_repo_commit`.

## The rules this hub keeps

1. **Every table row ends with a link to what states it** — an official page, a file in this repository, or an
   explicit `blank · no official source` marker. `verify_all.py` counts rows and fails on any that do not.
2. **No value is invented to fill a gap.** Depth strings, replacement-quality ratings and prop profitability
   have no citable source; the columns are blank and `data/flags.json` says why.
3. **No number is retyped from a sibling page.** Figures quoted from other hubs are read from their committed
   registers at build time, and the file is linked.
4. **Conflicts are shown, not averaged.** Where two hubs publish different values under one label, the
   reconciliation page lists both with both links.
5. **Contradictions between official surfaces are reported as such.** The weekly injury report is not a
   complete absence ledger, and the flags page keeps the evidence for that.
6. **Nothing is implemented from this board by the session that wrote it.** Every cluster's state is
   `proposed — awaiting owner`.

## What this hub deliberately does not touch

The root shared navigation (`scripts/lib/site.py`) is not edited here, so `review-board/` is not linked from
the published root site yet: an additive nav edit belongs to the integration pass, and other sessions are
editing the same file. Reach the hub at `/review-board/index.html` (Pages builds the whole tree, so the
directory is served as committed). Cluster T10 in the review queue is the decision that changes this.
