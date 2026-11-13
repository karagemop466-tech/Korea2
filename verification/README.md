# Independent verification (session `arena/652b0095-korea2`)

This directory is **not** part of the published dashboard's build chain. It is an
independent re-implementation of the headline statistics, written from the committed
extracts (`data/derived/*.csv.gz`) rather than from the project's own analysis modules,
so a coding or definition error in `scripts/` cannot make the check agree with itself.

| File | What it is |
| --- | --- |
| `recompute.py` | Recomputes the published headline numbers with numpy/pandas only, compares each to the published JSON, and writes `verification/recompute.json` + `data/derived/verification.json`. |
| `sources_2026-11-02.json` | Official-source re-checks performed on 2026-11-02 by the verifying session: URL, what was read, the extracted value, and the verdict. |
| `recompute.json` | Output of the last run (committed so the site can render it). |
| `integration_recompute.py` | Second independent implementation, written by the 2026-11-13 integration session. It re-derives 45 published figures from the committed extracts only (no network, no raw downloads) and writes `integration_recompute.json`. |
| `integration_recompute.json` | Output of the last run (committed; the site renders it on the Verification page and CI re-checks it). |
| `nfl_standings_2026-11-13.json` | The NFL.com 2026 division standings transcribed on 2026-11-13, used to measure how far the committed snapshot is behind the live page (17 games). |

## Run

```bash
pip install pandas numpy scipy
python verification/recompute.py
python verification/integration_recompute.py
```

The script exits non-zero if a recomputed value disagrees with the published JSON by more
than the stated tolerance, so it is usable as a gate.

## What this does and does not establish

* It establishes that the published numbers follow from the committed extracts under an
  independent implementation, and that the committed extracts reconcile with the NFL's own
  published standings for a completed season (2020) field by field.
* It does not establish that any strategy is profitable, that a price is obtainable, or that
  the tests would generalise. Reproducibility is not validation.
