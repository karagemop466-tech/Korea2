# Official NFL injury-report capture (IC-1)

**What it does.** `scripts/capture_injury_report.py` fetches `https://www.nfl.com/injuries/league/<season>/reg<week>` on a GitHub-hosted runner (the authoring sandbox cannot reach nfl.com), then:

- stores the raw response bytes (artifact, retained 90 days — outside the static site);
- records the SHA-256 of those bytes, the HTTP status, the final URL and the fetch time (UTC);
- parses every `<table>` with a stdlib HTML parser, reading the table headers the page prints (`Player | Position | Injuries | Practice Status | Game Status`);
- assigns each table to a team from the team links the page prints before each game's pair of tables (the k-th table of a block takes the k-th team of that block);
- fails the run (exit 2) if the week text is absent, no injury table has the required columns, a row's cell count differs from the header, or fewer than the pinned minimum (50) rows are parsed;
- commits a small manifest (`manifests/`) with hash, time, counts, per-table team slug and row count — **no player names**.

**What it does not do.** It does not infer starters, depth order, replacements, or game status; it does not fill blank cells; it does not treat an absent player as healthy.

**Cross-check.** `scripts/check_against_expected.py` compares the newest manifest with `expected/reg10_2026_prior_manual_counts.json` (a hand transcription of per-team counts from the 2026-11-15 Week 10 page, logged in COORDINATION.md). This is a consistency check, not a verification source.

**Known limits.**
- Each run is one week. The scheduled trigger uses the workflow's `WEEK` default and must be updated each week (or replaced with a schedule source); this is open.
- Manifests are committed only from `arena/**` branches; a durable store for raw captures on `main` is an open decision.
- The page has no published "no injuries" sections in the captured markup; a team with an empty section would show up here as a zero-row table, so the capture would flag it rather than hide it.
- Week-level content is only as current as the page at fetch time; the manifest records that time.
