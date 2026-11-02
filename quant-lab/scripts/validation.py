#!/usr/bin/env python3
"""
validation.py — validation gates, luck removal, and the leaderboard.

Each strategy in data/processed/strategies.json must clear ALL nine gates below. Thresholds are
pre-registered here (not chosen after seeing results), and the family-wise error rate is
controlled with Benjamini-Hochberg FDR across every strategy tested.

G1 SAMPLE      holdout sample >= 100 settled bets (60 for props)
G2 HOLDOUT     holdout ROI > 0
G3 DISCOVERY   discovery ROI > 0 (signal must not appear only in the recent window)
G4 SIGNIFICANCE holdout bootstrap 95% CI lower bound > 0 AND BH-FDR q < 0.10
G5 CALIBRATION |observed hit rate - mean model probability| <= 5pp and Brier < 0.25
G6 STABILITY   >= 60% of holdout seasons (with >=10 bets) profitable, and >= 3 such seasons
G7 ROBUSTNESS  worst leave-one-season-out ROI > -5%
G8 CONCENTRATION top-1% of bets produce <= 60% of total profit
G9 PRICE       leg-by-leg price sensitivity: each ticket is repriced from its OWN recorded
               decimal, shifting every leg by the -110 -> new-price ratio, and must stay
               profitable at BOTH a better price (-105) and a worse one (-115). Multi-leg
               tickets move by the leg ratio raised to the number of legs; quoted-package
               prices (teasers) cannot be decomposed and fail the gate closed.

Luck removal
  Every bet is settled at the price actually taken. Because a fair market price implies zero
  expected return before vig, the ROI a *luck-free* bettor can expect is -vig, i.e. -4.55% for
  -110. `luck_z` measures how far observed wins are from the wins the MARKET expected:
        z = (wins - SUM p_market) / sqrt(SUM p_market(1-p_market))
  `excess_roi` = ROI - (-0.0455) is the part of the return that luck alone cannot explain.
"""
import json, math, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")

FDR_Q = 0.10
VIG_ROI = -0.0455          # -110 both ways, no edge
GATES = {
    "G1_sample": 100, "G1_sample_prop": 60,
    "G5_calibration_pp": 5.0, "G5_brier_max": 0.25,
    "G6_stability_frac": 0.60, "G6_min_seasons": 3,
    "G7_worst_loso_roi": -0.05, "G8_concentration_max": 0.60,
}


def norm_sf(z):
    return 0.5 * (1.0 - math.erf(z / math.sqrt(2.0)))


def decimal_of(american: float) -> float:
    """Decimal equivalent of American odds."""
    a = float(american)
    return 1.0 + (a / 100.0 if a > 0 else 100.0 / -a)


# how many legs each strategy kind has; teaser prices are quoted as a package and
# therefore cannot be repriced leg by leg (gate fails closed for them)
LEGS_BY_KIND = {"single": 1, "prop": 1, "parlay2": 2, "parlay3": 3, "sgp": 2}


def repriced_roi(bets, new_price=-105, legs=1):
    """ROI if every leg of every ticket had been priced at ``new_price``.

    Issue #24 fix: the old version REPLACED each ticket's decimal with the new
    single-leg price, which mispriced multi-leg tickets both ways (a 2-leg ticket
    recorded at 3.6446 became 1.9524). Now each ticket's own recorded decimal is
    multiplied by (decimal(new_price)/decimal(-110)) ** legs, which is the exact
    transformation when every leg moves from -110 to the new price.
    """
    ratio = decimal_of(new_price) / decimal_of(-110)
    units = []
    for b in bets:
        if b.get("hit") is None or b.get("void"):
            continue
        d = float(b["decimal"]) * ratio ** legs
        units.append((d - 1.0) if b["hit"] else -1.0)
    return sum(units) / len(units) if units else None


def load_bets(strategy):
    """Re-derive the holdout bets for a strategy from strategies.json by_season + ledger files."""
    led = json.load(open(os.path.join(PROC, "bets_all.json")))
    return led.get(strategy, [])


def gates_for(name, res, bets):
    hold = res["holdout"]
    disc = res["discovery"]
    kind = res.get("kind", "single")
    n = hold.get("n", 0)
    g = {}
    g["G1_sample"] = {"pass": n >= (GATES["G1_sample_prop"] if kind.startswith("prop") else GATES["G1_sample"]),
                      "value": n}
    g["G2_holdout_roi"] = {"pass": (hold.get("roi") is not None and hold["roi"] > 0), "value": hold.get("roi")}
    g["G3_discovery_roi"] = {"pass": (disc.get("roi") is not None and disc["roi"] > 0), "value": disc.get("roi")}
    ci = hold.get("roi_ci95") or [None, None]
    g["G4_ci_lower_gt_0"] = {"pass": ci[0] is not None and ci[0] > 0, "value": ci}
    cal = hold.get("calibration_gap_pp")
    brier = hold.get("brier")
    g["G5_calibration"] = {"pass": cal is not None and abs(cal) <= GATES["G5_calibration_pp"] and
                                   brier is not None and brier < GATES["G5_brier_max"],
                           "value": {"gap_pp": cal, "brier": brier}}
    hb = [b for b in bets if b["season"] >= 2020 and b.get("hit") is not None and not b.get("void")]
    seasons = {}
    for b in hb:
        s = seasons.setdefault(b["season"], [0, 0])
        s[0] += b["units"]; s[1] += 1
    qual = {k: (v[0] / v[1]) for k, v in seasons.items() if v[1] >= 10}
    frac = (sum(1 for v in qual.values() if v > 0) / len(qual)) if qual else 0.0
    g["G6_stability"] = {"pass": len(qual) >= GATES["G6_min_seasons"] and frac >= GATES["G6_stability_frac"],
                         "value": {"profitable_frac": round(frac, 3), "seasons_scored": len(qual)}}
    loso = []
    for k in sorted({b["season"] for b in hb}):
        sub = [b for b in hb if b["season"] != k]
        if sub:
            loso.append(sum(x["units"] for x in sub) / len(sub))
    g["G7_robustness"] = {"pass": bool(loso) and min(loso) > GATES["G7_worst_loso_roi"],
                          "value": round(min(loso), 4) if loso else None}
    conc = hold.get("top1pct_profit_share")
    g["G8_concentration"] = {"pass": conc is not None and conc <= GATES["G8_concentration_max"], "value": conc}
    # G9 (issue #24): a better price alone is not a robustness test. Require the
    # strategy to survive both a better (-105) and a worse (-115) price, with each
    # ticket repriced leg by leg from its own recorded decimal.
    legs = LEGS_BY_KIND.get(kind)
    if legs is None:
        g["G9_price_sensitivity"] = {
            "pass": False, "value": None,
            "note": ("not evaluated: this kind's price is a quoted package that cannot be "
                     "decomposed into -110 legs, so the gate fails closed"),
        }
    else:
        r_better = repriced_roi(hb, -105, legs)
        r_worse = repriced_roi(hb, -115, legs)
        g["G9_price_sensitivity"] = {
            "pass": (r_better is not None and r_worse is not None and r_better > 0 and r_worse > 0),
            "value": {"roi_at_-105": None if r_better is None else round(r_better, 4),
                      "roi_at_-115": None if r_worse is None else round(r_worse, 4),
                      "legs": legs},
            "note": ("each ticket repriced from its own recorded decimal by the leg ratio; "
                     "must stay profitable at BOTH -105 and -115"),
        }
    return g, seasons


def main():
    strat = json.load(open(os.path.join(PROC, "strategies.json")))
    ledgers = json.load(open(os.path.join(PROC, "bets_all.json")))
    out = []
    pvals = []
    for name, res in strat.items():
        bets = ledgers.get(name, [])
        g, seasons = gates_for(name, res, bets)
        hold = res["holdout"]
        lz = hold.get("luck_z")
        p = None if lz is None else round(norm_sf(lz), 5)
        pvals.append((name, p))
        g["G4_ci_lower_gt_0"]["p_value_raw"] = p
        out.append({
            "strategy": name, "desc": res["desc"], "kind": res.get("kind"),
            "n_all": res["all"].get("n"), "n_holdout": hold.get("n"),
            "roi_holdout": hold.get("roi"), "roi_discovery": res["discovery"].get("roi"),
            "roi_all": res["all"].get("roi"),
            "hit_holdout": hold.get("hit_rate"), "units_holdout": hold.get("units"),
            "ci95_holdout": hold.get("roi_ci95"), "luck_z": lz, "p_value": p,
            "excess_roi_holdout": None if hold.get("roi") is None else round(hold["roi"] - VIG_ROI, 4),
            "gates": g, "by_season": res.get("by_season", []),
        })

    # ---- player-prop strategies (limited by available data, shown as tested) ----
    diag_path = os.path.join(PROC, "prop_diag.json")
    corr_path = os.path.join(PROC, "prop_corr.json")
    if os.path.exists(diag_path):
        d = json.load(open(diag_path))
        n = d["n_observations"]
        hit = d["side_hit_rate"]
        roi = None if hit is None else round(hit * (1 / 1.1) - (1 - hit), 4)
        out.append({
            "strategy": "S19_prop_singles", "kind": "prop",
            "desc": "Player-yardage over/under from the prop origination engine, expanding-window, "
                    "settled at the -110 assumption because no prop price exists in any reachable source.",
            "n_all": n, "n_holdout": n, "roi_holdout": roi, "roi_discovery": None, "roi_all": roi,
            "hit_holdout": hit, "units_holdout": None, "ci95_holdout": [None, None],
            "luck_z": None, "p_value": None, "excess_roi_holdout": None,
            "gates": {
                "G1_sample": {"pass": n >= GATES["G1_sample_prop"], "value": n},
                "G2_holdout_roi": {"pass": roi is not None and roi > 0, "value": roi},
                "G3_discovery_roi": {"pass": False, "value": None},
                "G4_significance": {"pass": False, "value": {"note": "no price, no CI"}},
                "G5_calibration": {"pass": d["brier"] is not None and d["brier"] < 0.25,
                                   "value": {"gap_pp": None, "brier": d["brier"]}},
                "G6_stability": {"pass": False, "value": {"profitable_frac": 0.0, "seasons_scored": 0}},
                "G7_robustness": {"pass": False, "value": None},
                "G8_concentration": {"pass": True, "value": None},
                "G9_price_sensitivity": {"pass": False, "value": None},
            },
            "by_season": [], "status": "needs review",
            "note": "Gate G1 blocks this strategy on sample size alone. It stays on the board so the gate "
                    "can be seen doing its job.",
        })
    if os.path.exists(corr_path):
        c = json.load(open(corr_path))
        out.append({
            "strategy": "S20_prop_sgp_qb_wr", "kind": "prop",
            "desc": "Same-game parlay of a quarterback passing-yards leg and his own No.1 receiver's "
                    "receiving-yards leg. Correlation measured; price cannot be tested.",
            "n_all": 0, "n_holdout": 0, "roi_holdout": None, "roi_discovery": None, "roi_all": None,
            "hit_holdout": None, "units_holdout": None, "ci95_holdout": [None, None],
            "luck_z": None, "p_value": None, "excess_roi_holdout": None,
            "gates": {k: {"pass": False, "value": None} for k in
                      ("G1_sample", "G2_holdout_roi", "G3_discovery_roi", "G4_significance",
                       "G5_calibration", "G6_stability", "G7_robustness", "G8_concentration",
                       "G9_price_sensitivity")},
            "by_season": [], "status": "needs review",
            "note": "Measured r = " + str(c["pooled_qb_wr"]["r"]) + " (n=" + str(c["pooled_qb_wr"]["n"]) +
                    ") between QB1 passing yards and WR1 receiving yards in the same game. No prop price "
                    "is reachable from this environment, so no return, no ROI and no rank are published.",
        })

    # ---- Benjamini-Hochberg across the whole tested family -------------------
    valid = [(n, p) for n, p in pvals if p is not None]
    valid.sort(key=lambda x: x[1])
    m = len(valid)
    rejected = {}
    kmax = 0
    for i, (n, p) in enumerate(valid, start=1):
        if p <= (i / m) * FDR_Q:
            kmax = i
    for i, (n, p) in enumerate(valid, start=1):
        rejected[n] = i <= kmax

    for row in out:
        row["bh_fdr_pass"] = bool(rejected.get(row["strategy"], False))
        g = row["gates"]
        if "G4_ci_lower_gt_0" in g:
            base4 = g.pop("G4_ci_lower_gt_0")
            g["G4_significance"] = {
                "pass": bool(base4["pass"] and row["bh_fdr_pass"]),
                "value": {"ci_lower": (row["ci95_holdout"] or [None])[0], "bh_fdr_pass": row["bh_fdr_pass"],
                          "family_size": m, "q": FDR_Q, "raw_p": base4.get("p_value_raw")},
            }
        passed = [k for k, v in g.items() if v["pass"]]
        failed = [k for k, v in g.items() if not v["pass"]]
        row["gates_passed"] = len(passed)
        row["gates_failed"] = failed
        row["qualified"] = len(failed) == 0
        # composite skill score (only meaningful once every gate is clear)
        season_rows = row["by_season"]
        hr = [s for s in season_rows if s["season"] >= 2020 and s["n"] >= 10]
        stab = (sum(1 for s in hr if s["roi"] and s["roi"] > 0) / len(hr)) if hr else 0.0
        base = (row["roi_holdout"] or 0.0) * 100
        zbonus = 1.0 + max(0.0, (row["luck_z"] or 0.0)) / 3.0
        sample = min(1.0, (row["n_holdout"] or 0) / 300.0) ** 0.5
        row["score"] = round(base * zbonus * (0.5 + 0.5 * stab) * (0.5 + 0.5 * sample), 3)

    ranked = sorted([r for r in out if r["qualified"]], key=lambda r: -r["score"])
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
    unranked = sorted([r for r in out if not r["qualified"]],
                      key=lambda r: (-r["gates_passed"], -(r["roi_holdout"] or -9)))
    for r in unranked:
        r["rank"] = None

    payload = {
        "generated": "deterministic",
        "family_size": m, "fdr_q": FDR_Q, "vig_roi": VIG_ROI,
        "gate_thresholds": GATES,
        "leaderboard": ranked + unranked,
        "summary": {
            "strategies_tested": len(out),
            "qualified": len(ranked),
            "top": ranked[0]["strategy"] if ranked else None,
            "holdout_years": [2020, 2026],
            "discovery_years": [2002, 2019],
        },
    }
    json.dump(payload, open(os.path.join(PROC, "leaderboard.json"), "w"), indent=1)

    print(f"strategies: {len(out)}  qualified: {len(ranked)}  family: {m}  BH rejects: {sum(rejected.values())}")
    for r in ranked + unranked:
        print(f"  {str(r['rank']):>4} {r['strategy']:24s} roi_h={r['roi_holdout']} gates={r['gates_passed']}/9 "
              f"p={r['p_value']} fail={','.join(r['gates_failed']) or '-'}")


if __name__ == "__main__":
    main()
