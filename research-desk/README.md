# Line / Lab — NFL research desk

A static, source-linked research dashboard for investigating NFL line origination. The project contains three proposed strategy designs, validation and leaderboard rules, a correlation protocol, a small verified NFL evidence sample, and an explicit review register. **No strategy has been validated; no live data collection, predictions, prices, real competition or bets are implemented.** Gambling outcomes contain irreducible uncertainty.

## Run and validate

The checked-in HTML is generated with Python 3, without dependencies:

```sh
cd research-desk
python3 scripts/build_site.py
python3 scripts/check_site.py
python3 -m http.server 8000
```

Open `http://localhost:8000/`. GitHub Pages is configured on the repository to serve the root of `main`; this independent desk is under `research-desk/` and relative links support project Pages paths. Rebuild after changes to `scripts/build_site.py`. The checker verifies local links, table-row source links, and generated-page consistency; it does not verify external sites' current availability or facts. Sources and their exact scope are documented on the Evidence and Flagged for Review pages. The historical review snapshot is dated 2026-11-01 UTC.
