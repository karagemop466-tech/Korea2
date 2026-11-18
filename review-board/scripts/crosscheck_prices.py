#!/usr/bin/env python3
"""Cross-check the originated-line residual across the repository's two price stores.

Open item left by the 2026-11-18 integration session (COORDINATION.md): the residual published in
`data/derived/model.json` (`edge_vs_market_*`) was never reconciled against the price-snapshot store
`results/price_snapshots.json`. This script reads both committed stores and publishes, as data:

  1. every market field the model's Week 9 originated lines carry vs the same field in the
     price-snapshot store (spread, total, home moneyline closing values);
  2. whether each published `edge_vs_market_*` column equals model_fair minus market_price;
  3. the distribution of the fair-minus-market residual for spread and total.

Output: review-board/data/price_crosscheck.json (byte-stable - no wall-clock input).
"""
from __future__ import annotations

import json
import os
from statistics import mean

HERE = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.dirname(HERE)
REPO = os.path.dirname(HUB)

MODEL = os.path.join(REPO, "data", "derived", "model.json")
PRICES = os.path.join(REPO, "results", "price_snapshots.json")

TREE = "https://github.com/karagemop466-tech/Korea2/tree/main/"
MODEL_URL = TREE + "data/derived/model.json"
PRICES_URL = TREE + "results/price_snapshots.json"

FIELDS = [
    ("spread", "market_spread_home", ("spread", "closing")),
    ("total", "market_total", ("total", "closing")),
    ("home moneyline", "market_home_ml", ("moneyline", "home", "closing")),
]
EDGES = [
    ("edge_vs_market_spread", "model_spread_home", "market_spread_home"),
    ("edge_vs_market_total", "model_total", "market_total"),
]
TOL = 0.0501  # published values are rounded to one decimal


def dig(d, path):
    for p in path:
        d = d[p]
    return d


def build() -> dict:
    with open(MODEL) as fh:
        model = json.load(fh)
    with open(PRICES) as fh:
        prices = json.load(fh)
    store = {g["game_id"]: g for g in prices["games"]}
    ol = model["originated_lines"]

    field_rows = []
    mismatches = 0
    nulls = 0
    for row in ol["games"]:
        p = store.get(row["game_id"])
        for label, mkey, path in FIELDS:
            mval = row.get(mkey)
            sval = dig(p, path) if p else None
            if mval is None and sval is None:
                nulls += 1
                agree = True
            elif (mval is None) != (sval is None):
                agree = False
            else:
                agree = abs(float(mval) - float(sval)) <= 1e-9
            mismatches += 0 if agree else 1
            field_rows.append({
                "game_id": row["game_id"], "market": label,
                "model_store": mval, "price_store": sval,
                "agree": agree,
                "source_url": PRICES_URL,
            })

    edge_rows = []
    edge_bad = 0
    for row in ol["games"]:
        for ecol, fkey, mkey in EDGES:
            f, m, e = row.get(fkey), row.get(mkey), row.get(ecol)
            ok = None if None in (f, m, e) else abs((f - m) - e) <= TOL
            if ok is False:
                edge_bad += 1
            edge_rows.append({
                "game_id": row["game_id"], "edge_column": ecol,
                "fair": f, "market": m, "published_edge": e,
                "recomputed": None if ok is None else round(f - m, 4),
                "agree": ok,
                "source_url": MODEL_URL,
            })

    spread_res = [row["model_spread_home"] - row["market_spread_home"]
                  for row in ol["games"]
                  if row.get("model_spread_home") is not None and row.get("market_spread_home") is not None]
    total_res = [row["model_total"] - row["market_total"]
                 for row in ol["games"]
                 if row.get("model_total") is not None and row.get("market_total") is not None]

    n_market_fields = sum(1 for r in field_rows if r["model_store"] is not None)
    return {
        "title": "Originated-line residual, cross-checked across the two price stores",
        "question": ("The 2026-11-18 integration session left open whether the residual published in "
                     "data/derived/model.json agrees with the price-snapshot store in "
                     "results/price_snapshots.json. This register reads both committed files and "
                     "answers it with field-level comparisons."),
        "stores": {
            "model": {
                "file": "data/derived/model.json",
                "season": ol.get("season"), "week": ol.get("week"),
                "games": len(ol["games"]),
                "market_source": ol.get("market_source"),
                "generated_from": ol.get("generated_from"),
                "url": MODEL_URL,
            },
            "prices": {
                "file": "results/price_snapshots.json",
                "n_games": prices["meta"].get("n_games"),
                "data_as_of_gameday": prices["meta"].get("data_as_of_gameday"),
                "source_label": prices["meta"].get("source_label"),
                "url": PRICES_URL,
            },
        },
        "provenance_warning": (
            "Both stores carry the same third-party provenance: the model's market columns and the "
            "price store's closing lines are nflverse schedules-feed values, not official book "
            "quotes. Agreement between the two stores is a consistency result inside one lineage, "
            "NOT official-market verification. Flag FL-21 (no opening or closing official price for "
            "any originated market) is unchanged by this register."),
        "field_comparison": {
            "rows_checked": len(field_rows),
            "non_null_checked": n_market_fields,
            "null_on_both_sides": nulls,
            "mismatches": mismatches,
            "result": (f"{len(field_rows) - mismatches}/{len(field_rows)} field comparisons agree; "
                       f"{nulls} are null on both sides; {mismatches} disagree."),
            "rows": field_rows,
        },
        "edge_arithmetic": {
            "rows_checked": len(edge_rows),
            "mismatches": edge_bad,
            "tolerance": TOL,
            "result": (f"{len(edge_rows) - edge_bad}/{len(edge_rows)} published edge columns equal "
                       "fair minus market within the rounding tolerance." if edge_bad == 0
                       else f"{edge_bad} published edge columns do NOT equal fair minus market."),
            "rows": edge_rows,
        },
        "residual_distribution": {
            "spread": {
                "n": len(spread_res),
                "mean": round(mean(spread_res), 4) if spread_res else None,
                "mean_abs": round(mean(abs(x) for x in spread_res), 4) if spread_res else None,
                "min": min(spread_res) if spread_res else None,
                "max": max(spread_res) if spread_res else None,
            },
            "total": {
                "n": len(total_res),
                "mean": round(mean(total_res), 4) if total_res else None,
                "mean_abs": round(mean(abs(x) for x in total_res), 4) if total_res else None,
                "min": min(total_res) if total_res else None,
                "max": max(total_res) if total_res else None,
            },
            "reading": ("The residual exists only against third-party archived closes. Its mean and "
                        "spread describe how far this originator sat from that feed on one slate; it "
                        "is not a CLV measurement and not an official-market residual."),
            "source_url": MODEL_URL,
        },
        "_generated_by": "review-board/scripts/crosscheck_prices.py",
    }


def main() -> None:
    out = os.path.join(HUB, "data", "price_crosscheck.json")
    with open(out, "w") as fh:
        json.dump(build(), fh, indent=1)
        fh.write("\n")
    print(f"wrote {os.path.relpath(out, REPO)}")


if __name__ == "__main__":
    main()
