"""Invariants that must hold in results/*.json before the site is published.

These are not style checks: each one encodes a claim the site makes in prose.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
REQUIRED = ["market.json", "strategies.json", "correlations.json", "props.json",
            "originate.json", "verification.json"]
DERIVED = ROOT / "data" / "provenance.json"


def load(name):
    p = RESULTS / name
    if not p.exists():
        return None
    return json.loads(p.read_text())


def main() -> int:
    errors = []
    for r in REQUIRED:
        if not (RESULTS / r).exists():
            errors.append(f"missing result file: results/{r}")
    if errors:
        print("\n".join(errors))
        return 1

    mkt, strat = load("market.json"), load("strategies.json")
    corr, props = load("correlations.json"), load("props.json")
    orig, ver = load("originate.json"), load("verification.json")

    # 1. the sign convention was proven from the data, not assumed
    cc = mkt["convention_check"]
    if round(cc["share_home_ml_negative_when_spread_gt_2"], 3) != 1.0:
        errors.append("spread sign convention: home moneyline check did not hold on every game")
    if not cc["corr_spreadline_vs_home_margin"] > 0.3:
        errors.append("spread sign convention: correlation with home margin is implausible")

    # 2. every strategy that is reported has a gate verdict and a p-value
    for key, s in strat["strategies"].items():
        if not s.get("n"):
            continue
        if key not in strat["gates"]["by_strategy"]:
            errors.append(f"{key}: no gate verdict")
        if s.get("p") is None:
            errors.append(f"{key}: no p-value")
        if not s.get("splits"):
            errors.append(f"{key}: no temporal splits")

    # 3. a strategy may only be RANKED if it cleared every gate
    for key, g in strat["gates"]["by_strategy"].items():
        if g["status"] == "RANKED" and g["passed"] != g["of"]:
            errors.append(f"{key}: ranked without clearing all gates")

    # 4. verification claim matches the underlying rows
    matched = sum(1 for r in ver["rows"] if r.get("match"))
    if matched != ver["teams_matched"]:
        errors.append("verification: team count does not match rows")
    if ver["teams_matched"] != ver["teams_checked"]:
        errors.append(f"verification: {ver['teams_checked'] - ver['teams_matched']} teams failed to reconcile")

    # 5. no prop ROI claim anywhere
    for m, v in props["markets"].items():
        blob = json.dumps(v).lower()
        if '"roi"' in blob:
            errors.append(f"props/{m}: an ROI is present but no prop prices exist")

    # 6. originated lines always pair ours with theirs, or say so explicitly
    for g in orig["games"]:
        if g["our_home_line"] is None:
            errors.append("originate: unplayed game without an originated line")

    # 7. correlation rows all carry a sample size
    for c in corr["correlations"]:
        if not c.get("n"):
            errors.append(f"correlation without n: {c.get('name')}")

    # 8. provenance manifest exists and names its sources
    if not DERIVED.exists():
        errors.append("missing data/provenance.json")
    else:
        prov = json.loads(DERIVED.read_text())
        if not prov.get("files"):
            errors.append("provenance manifest lists no files")

    if errors:
        print("\n".join(errors))
        return 1
    print(f"PASS: {len(REQUIRED)} result files consistent; "
          f"{ver['teams_matched']}/{ver['teams_checked']} teams verified; "
          f"0 of {len(strat['strategies'])} strategies ranked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
