#!/usr/bin/env python3
"""Compare the newest capture manifest's per-table counts with an expected-counts file.

Exit 0 only if: the manifest status is OK, every expected team appears exactly once,
and every per-team row count equals the expected count. Prints a line per team.
"""
import glob, json, sys, collections

manifest_glob, expected_path = sys.argv[1], sys.argv[2]
files = sorted(glob.glob(manifest_glob))
if not files:
    sys.exit("no manifest found")
m = json.load(open(files[-1]))
exp = json.load(open(expected_path))["counts"]
if m.get("status") != "OK":
    sys.exit(f"manifest {files[-1]} status {m.get('status')}: {m.get('problems')}")
got = collections.defaultdict(list)
for t in m["per_table"]:
    got[t["team_slug"]].append(t["rows"])
bad = []
for team, n in sorted(exp.items()):
    vals = got.get(team, [])
    ok = vals == [n]
    print(f"{'MATCH' if ok else 'DIFF '} {team:28s} expected {n:>3}  captured {vals}")
    if not ok:
        bad.append(team)
extra = sorted(set(got) - set(exp))
print(f"manifest: {files[-1]}  sha256={m['raw_sha256']}  fetched={m['fetched_at_utc']}")
print(f"teams matched {len(exp)-len(bad)}/{len(exp)}; unexpected slugs: {extra or 'none'}; total rows {m['listed_rows_parsed']}")
sys.exit(1 if bad or extra else 0)
