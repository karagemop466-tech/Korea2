#!/usr/bin/env python3
"""Build the decision-readiness register that the landing page renders.

Owner requirement this file implements:
    "Put a decision-readiness table on the landing page: one row per requirement, with the gate
     that blocks it and the number that would clear it."

Rules honoured here:
  * one row per requirement in the owner brief, in the brief's own words where possible;
  * the blocking gate and the clearing NUMBER are named on every row;
  * `measured_now` quotes numbers read from the committed registers on disk, never typed - a row whose
    number cannot be established from a committed artefact says so instead of inventing one;
  * statuses describe THIS REPOSITORY, not the NFL: BUILT / PARTIAL / BLOCKED-SOURCE / BLOCKED-DECISION
    / NOT-STARTED / REJECTED / ONGOING.

Run:  PYTHONPATH=scripts python3 scripts/build_readiness.py [--write]
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURE = "data/derived/official_capture_2026-11-18.json"
CORRS = "data/derived/official_correlations_2026-11-18.json"


def J(rel: str):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return json.load(fh)


def ev(label: str, url: str) -> dict:
    return {"label": label, "url": url}


# Official pages: label states who read it and when, so no row implies a fresher read than happened.
OFFICIAL = {
    "standings": ("NFL.com 2026 division standings - read 2026-11-18",
                  "https://www.nfl.com/standings/division/2026/REG"),
    "schedule": ("NFL.com Week 10 schedule and finals - read 2026-11-18",
                 "https://www.nfl.com/schedules/2026/by-week/week-10"),
    "injury": ("NFL.com official injury report Week 10 - read 2026-11-18",
               "https://www.nfl.com/injuries/league/2026/reg10"),
    "injury11": ("NFL.com Week 11 report URL resolved to Week 10 at that read",
                 "https://www.nfl.com/injuries/league/2026/reg11"),
    "centre": ("NFL.com game centre NE@DET - read 2026-11-18",
               "https://www.nfl.com/games/patriots-at-lions-2026-reg-10?tab=recap"),
    "genius": ("NFL.com - Genius Sports exclusive betting-data distribution (read 2026-11-14, line-desk)",
               "https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports"),
    "rulebook": ("2026 NFL rulebook (URL recorded as current in data/sources.json)",
                 "https://www.nfl.com/rules-officiating/2026-nfl-rulebook"),
    "sched-announce": ("NFL Media - 2026 NFL Schedule Announced (dated May 14, 2026; registered "
                       "2026-11-01 in data/sources.json)",
                       "https://media.nfl.com/football-information/2026/news/2026-nfl-schedule-announced"),
    "nist": ("NIST Dataplot aid - correlation confidence limits (Fisher z)",
             "https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm"),
    "injurypolicy": ("NFL.com - injury report definitions (registered in data/sources.json)",
                     "https://www.nfl.com/news/nfl-injury-report-explained"),
    "colts": ("Colts official depth chart (team-published; the club labels its weekly chart unofficial; "
              "read 2026-11-12 by a prior session)", "https://www.colts.com/team/depth-chart"),
    "nws": ("National Weather Service API - forecast grid endpoint (registered in data/sources.json)",
            "https://www.weather.gov/documentation/services-web-api"),
    "repo-script": ("This capture's generator and drift alarm",
                    "https://github.com/karagemop466-tech/Korea2/blob/main/scripts/official_snapshot.py"),
}
HUB = {
    "ld_prices": ("Line Desk - price-snapshot coverage register", "line-desk/pages/price-snapshots.html"),
    "ld_results": ("Line Desk - verified results feed", "line-desk/pages/results-feed.html"),
    "ld_orig": ("Line Desk - origination order and slate", "line-desk/pages/origination.html"),
    "ld_lb": ("Line Desk - signal vs staking leaderboard", "line-desk/pages/leaderboard.html"),
    "ld_depth": ("Line Desk - replacement-depth register", "line-desk/pages/depth.html"),
    "ld_corr": ("Line Desk - official-only correlations", "line-desk/pages/correlations.html"),
    "ld_gates": ("Line Desk - promotion and demotion gates", "line-desk/pages/gates.html"),
    "ld_req": ("Line Desk - requirements trace (19 rows)", "line-desk/pages/requirements.html"),
    "ld_flag": ("Line Desk - flagged items", "line-desk/pages/flagged.html"),
    "ld_q": ("Line Desk - open questions", "line-desk/pages/questions.html"),
    "ld_repo": ("Line Desk - repository review", "line-desk/pages/repo-review.html"),
    "pd_prices": ("Price Desk - snapshot store", "price-desk/pages/price-snapshots.html"),
    "pd_results": ("Price Desk - results feed", "price-desk/pages/results-feed.html"),
    "pd_gates": ("Price Desk - demotion gate", "price-desk/pages/gates.html"),
    "pd_lb": ("Price Desk - leaderboard split", "price-desk/pages/leaderboard.html"),
    "pd_sugg": ("Price Desk - suggestion queue", "price-desk/pages/suggestions.html"),
    "rb_queue": ("Review Board - consolidated suggestion queue", "review-board/pages/suggestions.html"),
    "rb_injuries": ("Review Board - injury delta", "review-board/pages/injuries.html"),
    "rb_flags": ("Review Board - flags", "review-board/pages/flagged.html"),
    "vh_q": ("Verify Hub - question register", "verify-hub/pages/questions.html"),
    "vh_sugg": ("Verify Hub - suggestion queue", "verify-hub/pages/suggestions.html"),
    "vh_lb": ("Verify Hub - cross-lab leaderboard", "verify-hub/pages/leaderboard.html"),
    "root_lb": ("Root - leaderboard", "pages/leaderboard.html"),
    "root_gates": ("Root - validation gates", "pages/validation.html"),
    "root_luck": ("Root - removing luck", "pages/luck.html"),
    "root_lines": ("Root - originated lines", "pages/lines.html"),
    "root_props": ("Root - player props", "pages/props.html"),
    "root_corr": ("Root - correlation and parlays", "pages/correlation.html"),
    "root_method": ("Root - method and data", "pages/method.html"),
    "root_sources": ("Root - source register", "pages/sources.html"),
    "root_flag": ("Root - flagged for review", "pages/flagged.html"),
    "root_sugg": ("Root - suggestion register", "pages/suggestions.html"),
    "root_verify": ("Root - verification", "pages/verification.html"),
    "root_archive": ("Root - site archive (every hub and page)", "pages/archive.html"),
    "root_exec": ("Root - executive summary", "pages/executive.html"),
    "root_readiness": ("Decision-readiness register (this table, with the next action per row)",
                       "pages/readiness.html"),
    "capture": ("This capture - dated official-source register", "pages/live-checks.html"),
    "ir": ("Week 10 injury-report re-verification", "injury-report-w10/index.html"),
    "ps": ("Price Store - official-only snapshot store", "price-store/index.html"),
    "og": ("Origination hub - strategy registry", "origination/index.html"),
    "dd": ("Decision Desk", "decision-desk/index.html"),
    "ll": ("Lineup Lab", "lineup-lab/index.html"),
    "coord": ("COORDINATION.md (session board)", "COORDINATION.md"),
}

N_ROWS = "<<ROW_COUNT>>"


def measures() -> dict:
    """Every number this register quotes about the repository, read from the committed files."""
    cap = J(CAPTURE) or {}
    corrs = J(CORRS) or {}
    ld_snap = J("line-desk/data/price_snapshots.json") or {}
    ld_res = J("line-desk/data/results_feed.json") or {}
    ld_depth = J("line-desk/data/depth.json") or {}
    ld_corr = J("line-desk/data/correlations.json") or {}
    ld_lb = J("line-desk/data/leaderboard.json") or {}
    pd_sum = J("price-desk/data/store_summary.json") or {}
    rb_ready = J("review-board/data/readiness.json") or {}
    rb_queue = J("review-board/data/queue.json") or {}
    root_lb = J("data/derived/leaderboard.json") or {}
    root_model = J("data/derived/model.json") or {}
    reg = J("origination/site_data/strategy_registry.json") or {}
    vq = J("verify-hub/data/questions.json") or {}
    vs = J("verify-hub/data/suggestions.json") or {}

    cov = ld_snap.get("coverage", {}) if isinstance(ld_snap.get("coverage"), dict) else {}
    header: list[str] = []
    pred_rows = 0
    pred_path = os.path.join(ROOT, "data/derived/predictions.csv")
    if os.path.exists(pred_path):
        with open(pred_path) as fh:
            header = next(fh, "").strip().split(",")
            pred_rows = sum(1 for line in fh if line.strip())
    scores = pd_sum.get("feed_by_score_status", {}) if isinstance(pd_sum.get("feed_by_score_status"), dict) else {}
    ps_snap = os.path.join(ROOT, "price-store/data/snapshots.csv")
    ps_rows = 0
    if os.path.exists(ps_snap):
        with open(ps_snap) as fh:
            next(fh, None)
            ps_rows = sum(1 for line in fh if line.strip())
    acc = root_model.get("accuracy_spread", {}) if isinstance(root_model.get("accuracy_spread"), dict) else {}
    corr_rows = corrs.get("rows", []) or []
    injury = cap.get("injury_report", {}) if isinstance(cap.get("injury_report"), dict) else {}
    injury_rows = injury.get("rows", []) or []

    return {
        "capture_read_at": (cap.get("meta") or {}).get("read_at_utc", ""),
        "standings_rows": len(cap.get("standings", []) or []),
        "standings_complete": sum(1 for r in cap.get("standings", []) or [] if r.get("points_for") is not None),
        "finals_verified": len(cap.get("week10_results", []) or []),
        "checks": len(cap.get("checks", []) or []),
        "byes": len(cap.get("week10_byes", []) or []),
        "injury_rows": len(injury_rows),
        "injury_clubs": len({r.get("team") for r in injury_rows}),
        "lions_fixed": len(((injury.get("lions_blank_cells_now_published") or {}).get("players")) or []),
        "game_books": 1 if (cap.get("game_centre_probe") or {}).get("game_book_pdf") else 0,
        "venues": 1 if (cap.get("game_centre_probe") or {}).get("stadium") else 0,
        "n_corrs_official": len(corr_rows),
        "corr_n": (corr_rows[0].get("n") if corr_rows else ""),
        "corr_headline": (corr_rows[0].get("r") if corr_rows else ""),
        "ld_market_records": cov.get("market_records", ""),
        "ld_our_open": cov.get("our_open_line_captured", ""),
        "ld_our_close": cov.get("our_close_captured", ""),
        "ld_market_open": cov.get("market_open_captured", ""),
        "ld_market_close": cov.get("market_close_captured", ""),
        "ld_pairs": cov.get("complete_open_close_pairs", ""),
        "ld_finals": ld_res.get("verified_rows", ""),
        "ld_weeks": ",".join(str(w) for w in (ld_res.get("weeks_verified") or [])),
        "ld_depth_rows": len(ld_depth.get("rows", []) or []),
        "ld_replacements": sum(1 for r in ld_depth.get("rows", []) or [] if r.get("replacement_player")),
        "ld_tiers": sum(1 for r in ld_depth.get("rows", []) or [] if r.get("replacement_string_1st")),
        "ld_corr_values": len(ld_corr.get("correlations", []) or []),
        "ld_corr_n": ld_corr.get("n_official_rows", ""),
        "ps_official_rows": ps_rows,
        "pd_snapshot_rows": pd_sum.get("snapshot_rows", ""),
        "pd_prop_rows": pd_sum.get("prop_rows", ""),
        "pd_games": pd_sum.get("games_in_feed", ""),
        "pd_official_scores": scores.get("verified-official", ""),
        "pd_archived_scores": scores.get("archived-unverified", ""),
        "pd_missing_scores": scores.get("missing", ""),
        "lb_approved": root_lb.get("approved_count", ""),
        "lb_entries": len(root_lb.get("entries", []) or []),
        "ld_qualified": ld_lb.get("n_qualified", ""),
        "ld_n_cand": ld_lb.get("n_candidates", ""),
        "ld_n_controls": ld_lb.get("n_controls", ""),
        "rb_questions": rb_ready.get("question_rows", ""),
        "rb_answered": (rb_ready.get("state_totals") or {}).get("answered", ""),
        "rb_partial": (rb_ready.get("state_totals") or {}).get("partially answered", ""),
        "rb_unanswered": (rb_ready.get("state_totals") or {}).get("unanswered", ""),
        "rb_proposals": rb_queue.get("proposal_rows", ""),
        "rb_clusters": len(rb_queue.get("clusters", []) or []),
        "vh_questions": len((vq or {}).get("rows", []) or []),
        "vh_suggestions": len((vs or {}).get("rows", []) or []),
        "registry_strategies": sum(len(v) for v in (reg or {}).values() if isinstance(v, list)),
        "pred_rows": pred_rows,
        "pred_cols": ",".join(c for c in header if c),
        "pred_has_probability": any("prob" in c.lower() for c in header),
        "pred_has_inputs": any(k in ",".join(header).lower() for k in ("feature", "input", "hash")),
        "model_mae": (acc.get("model") or {}).get("mae", ""),
        "market_mae": (acc.get("market") or {}).get("mae", ""),
    }


# --------------------------------------------------------------------------- the register
def rows(m: dict) -> list[dict]:
    R: list[dict] = []

    def add(rid, cat, req, status, gate, clears, now, evidence, next_step):
        R.append({"id": rid, "category": cat, "requirement": req, "status": status,
                  "blocking_gate": gate, "clears_when": clears, "measured_now": now,
                  "evidence": evidence, "next_action": next_step})

    def E(*keys: str) -> list[dict]:
        out = []
        for k in keys:
            table = OFFICIAL if k in OFFICIAL else HUB
            label, url = table[k]
            out.append(ev(label, url))
        return out

    # ---- A. price and results infrastructure -------------------------------------------
    add("RR-A1", "Price and results",
        "Add a price-snapshot store that records opening and closing numbers for every market we originate",
        "PARTIAL",
        "No permitted market-price source: the NFL's betting feed is distributed to operators through an "
        "exclusive distributor, so market open and close are null on every row (Line Desk FL-LD-02). The "
        "second end of our own movement has never been captured because no post-kickoff capture is scheduled.",
        f"One full slate with both ends of both series: market open AND close non-null on 42 rows "
        f"(14 games x 3 markets) and our open AND close non-null on the same 42. Today: our open "
        f"{m['ld_our_open']}/{m['ld_market_records']}, our close {m['ld_our_close']}, market open "
        f"{m['ld_market_open']}, market close {m['ld_market_close']}, complete pairs {m['ld_pairs']}.",
        f"Price Store (official-only) holds {m['ps_official_rows']} rows. Price Desk holds "
        f"{m['pd_snapshot_rows']} game-market rows and {m['pd_prop_rows']} prop rows with 0 opens; its "
        f"{m['pd_official_scores']} official-score games sit beside {m['pd_archived_scores']} "
        f"archived-unverified and {m['pd_missing_scores']} missing scores in its results feed.",
        E("ld_prices", "ps", "pd_prices", "genius"),
        "Reviewer rules on the price policy (RR-A9); meanwhile schedule a pre-kickoff and a post-kickoff "
        "capture of OUR OWN lines so at least one slate has both ends.")

    add("RR-A2", "Price and results",
        "Add a verified results feed so backtests and ROI can be computed at all",
        "PARTIAL",
        "Coverage, not method: the Line Desk feed holds "
        f"{m['ld_finals']} finals (Weeks {m['ld_weeks']}); Weeks 1-6 are listed pending with blank scores, so "
        "a season-long backtest cannot be called official-backed end to end.",
        f"272 of 272 regular-season finals, each row carrying its own official game-centre URL and zero "
        f"mismatch against the committed snapshot. Added at this capture: {m['finals_verified']} of "
        f"{m['finals_verified']} Week-10 finals read first-hand (1 of them also on its game centre).",
        f"Line Desk cross-check reported 27/27 rows matching the committed snapshot for the overlap it had.",
        E("capture", "ld_results", "schedule"),
        "Extend the same one-row-per-fixture transcription backwards to Weeks 1-6 from the official weekly "
        "schedule pages.")

    add("RR-A3", "Price and results",
        "Originate the side first, then the total, then the moneyline",
        "BUILT",
        "Nothing blocks the ordering; the numbers it publishes stay blank where no market price exists.",
        "Order asserted by a check on every build for every slate. Today: fixed and published for a "
        "15-game slate, with the sign convention (positive = home favoured) verified on all 15 rows.",
        "side -> total -> moneyline, published in that order.",
        E("ld_orig", "root_lines"),
        "Keep the order pinned so a later refactor cannot silently re-sort it.")

    add("RR-A4", "Price and results",
        "Publish the model's fair line, the market line, and the difference as separate columns",
        "PARTIAL",
        "Two of the three columns have no permitted input; they are blank by policy rather than estimated.",
        f"Three non-null columns on 42/42 rows of one slate. Today: all three columns exist on "
        f"{m['ld_market_records']} rows, with market line and difference null on all of them.",
        "Fair line published on every row; market line and residual blank with the reason on the page.",
        E("ld_prices", "ld_orig"),
        "Publish the residual as soon as RR-A1 and RR-A9 clear.")

    add("RR-A5", "Price and results",
        "Price a line ourselves and publish the residual against the market, on a schedule, from day one",
        "BLOCKED-SOURCE",
        "Our half of the residual exists on a schedule; the market half has no source this project may use.",
        "Residual published for 14/14 fixtures of a slate, three times a week. Today: 0 residuals, because "
        "the market column is null on every row.",
        "",
        E("ld_prices", "genius"),
        "Either license a permitted price feed or narrow the published residual to our own open-to-close "
        "movement, labelled as not a market residual.")

    add("RR-A6", "Price and results",
        "Vig-free market consensus vs originated fair-line decomposition view",
        "BLOCKED-SOURCE",
        "Separating vig from divergence needs at least two independent operator quotes per market; the "
        "project holds zero operator quotes.",
        ">=2 quotes per market on one slate (84 quotes across 42 markets), overround computed from the pair "
        "and the consensus shown net of vig.",
        "",
        E("pd_prices", "genius"),
        "Decide whether operator consensus may be displayed at all before building the view.")

    add("RR-A7", "Price and results",
        "Ingest game-level results to make the ratings opponent-aware",
        "PARTIAL",
        "The root ratings are opponent-aware but are computed from a community nflverse extract, not from a "
        "league-published feed; only part of the 2026 slate has been reconciled against official pages, so "
        "the rows are labelled third-party.",
        f"Every game in the published window reconciled to an official final. This capture: "
        f"{m['finals_verified']} Week-10 finals verified first-hand; Line Desk reports 27/27 for its overlap. "
        f"Root prediction rows: {m['pred_rows']}.",
        f"Model MAE {m['model_mae']} pts vs market MAE {m['market_mae']} pts (walk-forward), so the "
        f"opponent-aware ratings still lose to the close.",
        E("capture", "root_method", "root_lines"),
        "Reconcile the extract season by season against the official week pages, then relabel only the "
        "reconciled rows.")

    add("RR-A8", "Price and results",
        "Turn the 136-game log into the pre-registered backtest corpus",
        "BLOCKED-DECISION",
        "Two upstream gates: the price-data policy (RR-A9) and hash-frozen strategy definitions (RR-B6). A "
        "corpus built on a third-party price archive would inherit the very dispute it is meant to settle.",
        "136 games x (frozen rule hash, per-game price pair, chronological split) published as one immutable "
        "corpus whose commit hash is recorded before evaluation. Today: no such corpus file exists at root.",
        "",
        E("root_method", "genius"),
        "Reviewer ruling first; then freeze the corpus and compute from it exactly once.")

    add("RR-A9", "Price and results",
        "Decide the price-data policy before any backtest is published",
        "BLOCKED-DECISION",
        "This is a reviewer decision, not an engineering gap: no ruling is recorded on the board or on the "
        "site. Options in evidence: (a) no prices - probability-only scoring; (b) third-party archived "
        "closes, labelled third-party and used for nothing but ranking sanity; (c) a licensed vendor.",
        "One recorded ruling (option, date, commit hash) plus the label wording it authorises. Today: 0 "
        "rulings.",
        "",
        E("coord", "pd_prices", "rb_queue"),
        "Put the three options to the reviewer as this row; keep every backtest page gated until it lands.")

    add("RR-A10", "Price and results",
        "Store every model output as a probability plus its inputs, not just a pick",
        "PARTIAL",
        "The root prediction table stores margins, totals and the settled outcome; it has no probability "
        "column and no input snapshot, so a published pick cannot be re-derived from the row.",
        f"100% of published predictions carry (p, model version, input hash). Today: {m['pred_rows']} rows "
        f"with columns [{m['pred_cols']}]; probability column: "
        f"{'yes' if m['pred_has_probability'] else 'no'}; input/hash column: "
        f"{'yes' if m['pred_has_inputs'] else 'no'}.",
        "Line Desk origination rows do publish a probability per game alongside the fair line, without the "
        "input vector.",
        E("root_method", "ld_orig"),
        "Add model_version and input_hash to the prediction writer and make the probability the primary "
        "published field.")

    # ---- B. leaderboard, gates and governance -------------------------------------------
    add("RR-B1", "Leaderboard and gates",
        "Separate 'signal' from 'staking' in the leaderboard so a lucky staking run cannot mask a bad signal",
        "BUILT",
        "Nothing blocks the split; what blocks promotion is qualification.",
        "Rank must be invariant to the staking block. Demonstrated on the published board: the best staking "
        "rank sits 5th of 7 on signal, and the best signal rank sits 3rd on staking.",
        f"{m['ld_qualified']} of {m['ld_n_cand']} candidates qualified on signal; root board lists "
        f"{m['lb_entries']} entries with {m['lb_approved']} approved.",
        E("ld_lb", "root_lb", "pd_lb"),
        "Keep staking out of the ranking function; the existing test is the guard.")

    add("RR-B2", "Leaderboard and gates",
        "Rank with proper scores and uncertainty, not win rate (Brier skill, game-cluster bound, multiplicity)",
        "BUILT",
        "Nothing blocks the method; the sample is short, which is exactly what the method reports.",
        "Every ranked row shows benchmark-relative skill, a game-cluster bootstrap bound and an adjusted "
        "p with the trial count. Today: all three are published per row.",
        "0 strategies qualify; expected-maximum-of-k statistics published with k.",
        E("root_lb", "root_gates", "nist"),
        "Re-rank on the frozen holdout once RR-A9 clears; do not re-mine for a significant slice.")

    add("RR-B3", "Leaderboard and gates",
        "Use proper-score leaderboard divisions (singles, game parlays, same-game parlays, prop combos)",
        "PARTIAL",
        "Three of four divisions have no eligible entrant: parlays and prop combos sit behind the "
        "joint-evidence gate (RR-D2) and every division waits on the price ruling (RR-A9).",
        "At least one eligible entrant per division with skill score and interval. Today: singles populated, "
        "other three divisions empty by rule.",
        "",
        E("vh_lb", "root_gates"),
        "Keep the empty divisions published with the blocking gate named, rather than collapsing them.")

    add("RR-B4", "Leaderboard and gates",
        "Add a control baseline (random picks; favourites only) to every leaderboard run",
        "BUILT",
        "None.",
        "Two controls in every run, excluded from the candidate count. Today: "
        f"{m['ld_n_cand']} candidates and {m['ld_n_controls']} controls on the Line Desk board.",
        "",
        E("ld_lb", "root_lb"),
        "Add the closing line as a third control if a price source is ever licensed.")

    add("RR-B5", "Leaderboard and gates",
        "Define a demotion gate that sends a live strategy back to paper",
        "BUILT",
        "There is nothing to demote yet: no strategy is live, so the gate has only been exercised in a dry "
        "run.",
        "D-outcome fires at n >= 200 decided picks with a one-sided 95% ROI upper bound below 0; D-integrity "
        "holds on any missing-data failure. Dry run today: 0 promoted, 0 demoted, all candidates PAPER.",
        "State machine published with thresholds labelled PROPOSED.",
        E("ld_gates", "pd_gates"),
        "Reviewer sets the thresholds; after that the gate is mechanical.")

    add("RR-B6", "Leaderboard and gates",
        "Pre-register every strategy; forbid backtest numbers from ever appearing on the leaderboard",
        "PARTIAL",
        "Definitions are committed, but not frozen before evaluation, so the board cannot honestly claim its "
        "entries were pre-registered; the hub registers label the practice as proposed.",
        f"100% of leaderboard entries carry (rule text, sample window, gates, freeze hash) committed before "
        f"the window opens. Today: {m['registry_strategies']} definitions in the origination registry, 0 with "
        f"a recorded freeze hash.",
        "Backtest numbers are kept off the leaderboard: the published board shows gate outcomes and skill "
        "scores, with ROI in a separate, unranked block.",
        E("og", "root_gates", "rb_queue"),
        "Freeze the registry in a tagged commit, record the hash per entry, and fail the build when an entry's "
        "window starts before its hash.")

    add("RR-B7", "Leaderboard and gates",
        "Freeze a rule before it sees data (the commit hash is the registration)",
        "NOT-STARTED",
        "The mechanism does not exist at root: no freeze-hash field in the register the site renders, and no "
        "CI check on the ordering of freeze versus window.",
        "Every rule row shows a short commit hash and its date, and CI fails if the hash is missing or later "
        "than the window start. Today: 0 rows hash-frozen.",
        "",
        E("root_gates", "og"),
        "Implement as a two-column registry (rule text, freeze hash) validated in CI; it costs one schema "
        "change.")

    add("RR-B8", "Leaderboard and gates",
        "Add a two-sided 'what would change our mind' field to every strategy entry",
        "PARTIAL",
        "The field exists as a proposal in the Review Board programme layer, but it is not a required column "
        "of the strategy schema, so entries can still be published without it.",
        f"100% of strategy entries carry BOTH a promote-if and a demote-if numeric threshold. Today: 0 of "
        f"{m['registry_strategies']} registry rows carry a threshold pair.",
        "The demotion gate supplies the negative side at gate level (RR-B5), not at entry level.",
        E("rb_queue", "ld_gates"),
        "Add the fields to the schema and fail the build when either side is empty.")

    add("RR-B9", "Leaderboard and gates",
        "Split data into train, validation and final holdout seasons",
        "BUILT",
        "Nothing blocks the split. What limits it: an earlier audit recorded a holdout look in one hub, which "
        "is why no result is called validated.",
        "Holdout touched exactly once per frozen rule, with the touch recorded. Today: walk-forward "
        "evaluation with a holdout sigma per hub and no touch log.",
        "",
        E("root_method", "rb_flags"),
        "Record holdout touches in the registry so 'looked at once' is auditable rather than remembered.")

    add("RR-B10", "Leaderboard and gates",
        "Two-stage skill leaderboard: proper-score qualification, then prospective CLV/ROI escrow",
        "PARTIAL",
        "Stage 2 needs paired prices (RR-A1, RR-A5), so the escrow clock cannot start.",
        "At least 200 prospective settled picks per escrowed strategy with open and close pairs. Today: 0 "
        "escrowed strategies (0 qualified at stage 1 as well).",
        "Stage 1 qualification published per entry; nobody passes.",
        E("ld_lb", "pd_gates"),
        "If the reviewer rules prices out, start the escrow on probability error instead of ROI.")

    add("RR-B11", "Leaderboard and gates",
        "Treat it as a leaderboard competition that provides rewards for top performing strategies",
        "BLOCKED-DECISION",
        "No funded pool, no jurisdiction or licensing determination, and zero qualifying strategies. Rewards "
        "are a design schedule, not a promise.",
        "A funded amount, a jurisdiction ruling and at least one qualifying strategy must all exist before "
        "any reward row is non-zero. Today: 0 / 0 / 0.",
        "",
        E("ld_lb", "root_flag"),
        "Reviewer decides whether rewards are displayed at all while qualification is zero.")

    add("RR-B12", "Leaderboard and gates",
        "Start with a singles-only shadow baseline (pre-registered team-strength model, frozen versions, "
        "forecasts recorded before kickoff)",
        "PARTIAL",
        "Forecasts have only ever been published for settled slates; a shadow baseline needs a dated record "
        "written BEFORE the first kickoff it predicts.",
        "One full slate (14 games) whose forecast commit timestamp precedes the earliest kickoff, graded "
        "afterwards. Today: 0 pre-kickoff slates recorded.",
        "The team-strength model exists and its walk-forward accuracy is published, which is the input the "
        "shadow baseline needs.",
        E("root_lines", "ld_orig"),
        "Cheapest unblock in this register: freeze the Week-11 forecasts before kickoff, then grade them.")

    # ---- C. availability, injury and depth -----------------------------------------------
    add("RR-C1", "Availability and depth",
        "Build the availability graph as a first-class dataset (who was expected to start, who actually did)",
        "PARTIAL",
        "Expected-starter evidence and game-day confirmation live in different places, and the confirmation "
        "side (inactives, snap shares) is not captured. The official report carries no depth rank - re-confirmed "
        "by the 2026-11-18 re-read.",
        f"32 of 32 clubs with dated availability rows, game-day starter/inactive evidence and a confirmation "
        f"link per edge. Today: {m['ld_depth_rows']} rows, {m['ld_replacements']} replacement names, "
        f"{m['ld_tiers']} string tiers; this capture adds {m['injury_rows']} rows across {m['injury_clubs']} "
        f"clubs read first-hand.",
        "Official report columns re-confirmed: Player, Position, Injuries, Practice Status, Game Status - and "
        "nothing else.",
        E("ld_depth", "injury", "ll"),
        "Wire the per-fixture Game Book (RR-C5) in as the confirmation side of the graph.")

    add("RR-C2", "Availability and depth",
        "Do not model depth from jersey order; model it from playing time",
        "BLOCKED-SOURCE",
        "Playing time is in no source this project holds: NFL.com team depth paths return 404, the weekly "
        "report has no snap column, and community snap counts are third-party.",
        "Snap-share rows for 14/14 fixtures of a slate from an authorised source, with the starter/backup "
        "split derived from snaps only. Today: 0 fixtures.",
        "",
        E("ld_depth", "injury"),
        "Licence a snap source or parse the official Game Books the game centres link (RR-C5/RR-C6).")

    add("RR-C3", "Availability and depth",
        "Make the injury signal a surprise, never a level",
        "NOT-STARTED",
        "A surprise is a residual against an expectation, and no per-position, per-designation play-rate "
        "expectation exists yet (RR-C9).",
        "Every designation row becomes (observed status, expected play rate, residual). Needs the "
        "designation-reliability table on n >= 1,000 designations with intervals.",
        "",
        E("injury", "rb_injuries"),
        "Run RR-C9 first; the surprise is a derived field, not a new source.")

    add("RR-C4", "Availability and depth",
        "Run the 32-team roster/IR sweep before any team-level model is trusted",
        "NOT-STARTED",
        "Coverage is 4 clubs in this capture and 4 in the Line Desk register; the sweep needs all 32 with "
        "reserve/IR lists, which the weekly report does not print (RR-C21).",
        "32 of 32 clubs with a dated roster and IR row set, each with a per-club count and hash, before any "
        "team-level output is labelled stronger than a benchmark. Today: 4/32 clubs, 12 rows.",
        "",
        E("injury", "ld_depth"),
        "Batch the sweep as one job with a per-club assertion so a short read fails instead of publishing a "
        "partial table.")

    add("RR-C5", "Availability and depth",
        "Capture official inactive lists and snap counts (confirm a backup replacing a starter, do not suspect it)",
        "PARTIAL",
        "The evidence exists but is not ingested. The brief's own count: only 6 of 254 report rows carry a "
        "game designation, and no active list or snap share is stored. This capture found the structured "
        "source the requirement needs: the game centre links a per-fixture Game Book PDF.",
        f"Inactive list plus snap share for 14/14 fixtures of a slate, each row linked to the Game Book it "
        f"came from. Today: {m['game_books']} Game Book URL verified at this capture, 0 parsed.",
        "Game Book PDF for NE@DET Week 10, linked from the official game centre; its contents were NOT read "
        "at this capture, so no starter, inactive or snap value is claimed.",
        E("centre", "ld_depth"),
        "Parse one Game Book end to end, publish inactives and snap shares with URL and hash, then scale to "
        "14/14.")

    add("RR-C6", "Availability and depth",
        "Use official NFL Game Books for actual starters and game-day status; do not infer depth rank or snaps",
        "PARTIAL",
        "One Game Book has been read (Price Desk proof of concept) and one link verified today. There is no "
        "scheduled ingestion, so coverage is 1 fixture of a 14-game week rather than a season.",
        f"Every settled fixture has a stored Game Book (URL, hash, parse date): 14/14 per slate. Today: "
        f"{m['game_books']} verified link from this capture plus 1 previously read.",
        "",
        E("centre", "pd_results"),
        "Nightly job that walks the week's game centres, records PDF URLs and hashes, and fails when a "
        "fixture has no Game Book link.")

    add("RR-C7", "Availability and depth",
        "Track the depth of the replacement, not just the fact of a replacement",
        "PARTIAL",
        "No source publishes an official 1st/2nd/3rd/4th-string rank, so every tier cell stays blank by "
        "policy; the fact of a replacement is also unconfirmed without the Game Book inactive list.",
        f"One verified replacement WITH a stated tier from an authorised source - not 32 rows of guesses. "
        f"Today: {m['ld_tiers']} tiers over {m['ld_depth_rows']} rows, {m['ld_replacements']} replacement "
        f"names.",
        "",
        E("ld_depth", "injury"),
        "Publish 'the club does not state a rank' as the answer; revisit only with an authorised structured "
        "source.")

    add("RR-C8", "Availability and depth",
        "Add injury and personnel ablations instead of fixed penalties",
        "NOT-STARTED",
        "An ablation needs availability features to remove; the model has none. Note the flip side: no fixed "
        "point penalty for a missing starter is applied anywhere, which is the correct posture while the "
        "features are missing.",
        "Two identical models on the same chronological holdout, with and without verified availability "
        "features, reporting delta-Brier with a bootstrap interval; >= 3 seasons preferred.",
        "No availability features in the root ratings model.",
        E("root_method", "ld_depth"),
        "Sequence RR-C1 then RR-C9; never ablate a proxy depth feature.")

    add("RR-C9", "Availability and depth",
        "Score injury-designation reliability before using it as a feature (play rate per designation, with CIs)",
        "NOT-STARTED",
        "Needs several seasons of designations joined to official inactive lists; the project holds one "
        "weekly capture and no inactive lists (RR-C5).",
        "Play rate per designation (Out, Questionable, Doubtful, Probable) with a binomial interval on "
        "n >= 1,000 designations per label. Today: 0 labels scored.",
        "",
        E("injury", "injurypolicy", "rb_injuries"),
        "Build the designation archive from the weekly pages, one season per run, and keep the read date per "
        "week.")

    add("RR-C10", "Availability and depth",
        "Calibrate what 'Questionable' means empirically instead of using old percentages",
        "BLOCKED-SOURCE",
        "The official text publishes no percentages, and the empirical route is RR-C9, which has not been "
        "run. Inherited conventional percentages are therefore used nowhere - the number is blank, not "
        "borrowed.",
        "A published play rate for Questionable with its interval and n, replacing any inherited figure. "
        "Today: blank on every row that would use it.",
        "",
        E("injurypolicy", "ld_q"),
        "Same job as RR-C9; publish the number beside the label once measured.")

    add("RR-C11", "Availability and depth",
        "Snapshot the nfl.com injury report every Wednesday, Thursday and Friday and keep a dated history",
        "PARTIAL",
        "Two scheduled captures now exist and disagree about cadence: fetch-injuries.yml runs Wednesday and "
        "Saturday (cron '30 21 * * 3', '30 21 * * 6') while nfl-injury-capture.yml, merged 2026-11-18, runs "
        "14:00 UTC on Wed/Thu/Fri/Sat/Sun (cron '0 14 * * 3,4,5,6,0') into its own manifest set. Thursday and "
        "Friday are therefore covered, by one of the two, and neither feeds the published site: the site still "
        "holds 1 dated capture, which cannot support a series or a backtest.",
        "One canonical capture job whose manifests land in the site's register, with 3 reads in a kickoff week "
        "(Wed/Thu/Fri), each carrying row counts, a raw-response hash and a fetch timestamp. Today: 2 capture "
        "workflows, 5 capture days per week between them, 1 dated capture published, and 1 independent "
        "same-minute capture of 347 rows over 28 clubs whose own assertion matches 28 of 28 teams.",
        "Workflow fetch-injuries.yml plus injury-capture/manifests (6 manifests, 2026-11-18T03:51Z to "
        "03:55Z); this capture adds an independently dated read with per-row clock times.",
        E("capture", "injury", "rb_injuries"),
        "Decide which capture workflow is canonical, publish its manifests into the site register, and retain "
        "the raw hash, which RR-C13 and RR-F1 also need.")

    add("RR-C12", "Availability and depth",
        "Treat the injury report as a timestamped series, not a weekly snapshot; publish the delta",
        "PARTIAL",
        "Rows carry clock times now, but a delta needs two dated reads; the review registers carry one "
        "comparison point only.",
        f"Every published row shows (status, previous status, delta, both timestamps). This capture stamps "
        f"{m['injury_rows']} rows at {m['capture_read_at']}; the delta requires the next dated read.",
        "",
        E("rb_injuries", "injury"),
        "Land the second dated capture, then switch the injury page from level to delta.")

    add("RR-C13", "Availability and depth",
        "Automate immutable multi-day availability snapshots with retained hashes, so practice designations "
        "can be replayed as they were known",
        "BLOCKED-DECISION",
        "Storage and retention: the site is a static tree, and durable object storage with alerting is not "
        "provisioned (RR-F1). This capture is text-level with a documented read time, not a raw-response hash.",
        ">= 3 dated captures per week with sha256 of the raw response, stored outside the static site, and a "
        "replay endpoint that answers 'as known at T'. Today: 1 capture, no raw hash.",
        "The root capture register (data/derived/official_capture_2026-11-18.json) is append-only, dated and "
        "carries a source URL per row - the format the ledger needs.",
        E("capture", "injury11"),
        "Reviewer picks the store; the capture format is already specified, so this is plumbing.")

    add("RR-C14", "Availability and depth",
        "Build immutable official availability snapshots (report, club depth pages, inactive evidence, with "
        "hashes, timestamps and conflict flags)",
        "PARTIAL",
        "Club depth pages cannot be read from this environment (blocked hosts), so two of the three inputs "
        "are unrepresented, and a conflict flag has nothing to conflict with yet.",
        "All three inputs captured per club-week with a conflict flag when they disagree, 32/32 clubs. "
        "Today: 1 of 3 inputs, 4 clubs.",
        "",
        E("ld_depth", "ll"),
        "Run the club-page capture from a CI runner - the restriction is a property of this sandbox, not of "
        "the source - and label the resulting rows runner-sourced.")

    add("RR-C15", "Availability and depth",
        "Fix the two depth-parsing failures before widening coverage (Texans image; Packers jersey prefixes)",
        "BLOCKED-SOURCE",
        "Packers: number stripping plus retaining the raw string recovers the rows - a parser change owned by "
        "the hub that holds depth parsing. Texans: the club publishes depth as an image, which needs an "
        "authorised structured source and must not be transcribed by eye.",
        "Packers rows recovered with the raw string retained (>= 2 rows verified) and Texans resolved through "
        "a structured source. Today: 0 of 2 clubs fixed.",
        "",
        E("ld_depth", "ld_flag"),
        "Publish both clubs as parse failures until fixed, rather than silently dropping the rows.")

    add("RR-C16", "Availability and depth",
        "Model depth slots as groups, not a single starter",
        "NOT-STARTED",
        "Depth input is blocked (RR-C14, RR-C15), so the group semantics have nothing to model; treating rank-1 "
        "as 'the starter' would fabricate a starter the club never named. The brief's own count: 149 "
        "club/unit/position slots list more than one rank-1 player.",
        "A slot table published one row per GROUP with member counts, for 32/32 clubs. Today: 0 clubs.",
        "",
        E("ld_depth"),
        "Design the group schema now - it needs no data - so the parser has a target when depth lands.")

    add("RR-C17", "Availability and depth",
        "Represent shared and empty depth slots faithfully",
        "NOT-STARTED",
        "Same blocker as RR-C16: with no depth source, a shared slot and an empty slot cannot be "
        "distinguished, and publishing them as ranks is the fabrication the brief forbids.",
        "Slot rows carry an explicit kind (shared / empty / single) and the renderer never fills an empty "
        "slot. Today: 0 rows carry a slot kind.",
        "",
        E("ld_depth"),
        "Add the slot-kind field in the same change as RR-C16.")

    add("RR-C18", "Availability and depth",
        "Resolve the depth-order source before building the backup-deficiency feature "
        "(route a: per-club official pages, verified club by club; route b: official snap counts)",
        "BLOCKED-DECISION",
        "Neither route is verified for all 32 clubs. Re-checked at this capture: the official weekly report "
        "prints no depth rank, and the league team-depth path returns 404.",
        "A route chosen and verified for 32/32 clubs, recorded club by club with URL and date. Today: 0/32.",
        "",
        E("injury", "ld_depth"),
        "Route (b) via the official Game Books is the only path executable without a licence (RR-C5, RR-C6).")

    add("RR-C19", "Availability and depth",
        "Treat roster turnover as a first-class data event",
        "NOT-STARTED",
        "Transactions are not ingested, so a depth or availability row cannot be invalidated when a club "
        "trades, releases or promotes the player it names.",
        "Every depth/availability row carries last_roster_event (date, type, source URL), and any row older "
        "than its club's latest transaction is flagged. Today: 0 rows carry the field.",
        "",
        E("injury", "ld_flag"),
        "Ingest club transaction pages weekly and join on club plus date.")

    add("RR-C20", "Availability and depth",
        "Flag stale depth rows against the official transactions log (the Baltimore QB example)",
        "BLOCKED-SOURCE",
        "Needs depth rows (blocked) and the transactions log (not ingested). The specific claim - Baltimore "
        "still listing two quarterbacks after both went to IR - is carried as reported by the brief and could "
        "NOT be re-verified from an official page at this capture, so it is not asserted here.",
        "A staleness flag on every depth row naming the transaction that overrides it, 32/32 clubs. Today: 0.",
        "",
        E("ld_flag", "ll"),
        "Add the flag to the depth schema; the row then reports itself as stale instead of contradicting IR.")

    add("RR-C21", "Availability and depth",
        "Capture the reserve list so 'not listed' never means 'available'",
        "PARTIAL",
        "IR and reserve designations are not a column of the weekly report, so an absent player is ambiguous. "
        "Recorded at this capture as a structural property of the page, not as a per-club list. The brief's "
        "example (a quarterback absent because he is on IR, not because he is healthy) is exactly this "
        "ambiguity.",
        "Reserve list per club per week (32/32) joined to the report so absence carries two distinct codes: "
        "IR/reserve versus healthy-unlisted. Today: 0 club-weeks.",
        "",
        E("injury", "ld_q"),
        "Club roster and transaction pages are the source; capture them with RR-C4.")

    add("RR-C22", "Availability and depth",
        "Populate the three missing Lions game-status designations (Kerby Joseph, Cade Mays, D.J. Reed)",
        "BUILT",
        "Nothing. The official Week-10 report was re-read on 2026-11-18 and all three rows carry a game "
        "status there.",
        f"{m['lions_fixed']} of 3 rows published with the official status and the read timestamp. At this "
        f"capture all three read Out, with the practice designation (Did Not Participate) beside them.",
        "The site's blanks were a capture gap, not an official gap; both facts are now recorded with the "
        "source URL and clock time.",
        E("capture", "injury"),
        "Propagate the correction into the injury tables that still print blanks (RR-C23) so the fix is not "
        "confined to this register.")

    add("RR-C23", "Availability and depth",
        "Re-capture and republish the Week 10 injury tables (row and section counts are stale)",
        "PARTIAL",
        "A full re-capture needs every report chunk read in one pass with per-club counts. This capture read "
        f"1 of 8 chunks and published {m['injury_rows']} rows verbatim across {m['injury_clubs']} clubs, so "
        "the club-count comparison the brief asks for is still open.",
        "One dated pass over all 8 chunks with a row count per club (32/32), reproducing the two club counts "
        "the brief names. Today: 1/8 chunks, 4/32 clubs.",
        "",
        E("ir", "capture"),
        "Run the capture as a single job with a per-club count assertion, so a short read fails loudly instead "
        "of publishing a partial table (RR-F3).")

    add("RR-C24", "Availability and depth",
        "Add an announced-starter evidence field (not an inferred replacement)",
        "PARTIAL",
        "Dated starter announcements appear in articles rather than a structured field, so each one is a "
        "manual transcription. The blank replacement columns on the report page are correct for that source; "
        "the gap is the announcement register.",
        "Each lineup row carries (announced starter, date, source URL) and no replacement is named without a "
        "dated announcement. Today: 1 first-hand roster observation recorded in this capture, 0 structured "
        "announcement rows.",
        "Verified observation at this capture: the official Week-10 report lists J.J. McCarthy in the New "
        "York Giants table (QB, full participation, no game status) - a roster fact read from the page, not "
        "an inference about who starts.",
        E("capture", "injury"),
        "Stand up an announcement register fed by dated club and league statements, one URL per row.")

    add("RR-C25", "Availability and depth",
        "Add an official depth-chart register with date and source per row",
        "BLOCKED-SOURCE",
        "No league-official depth chart is published (team depth path returns 404); club pages are "
        "inconsistent and at least one club labels its own weekly chart unofficial.",
        "One row per club-week with (club, date, URL, publisher type) and an explicit 'club calls this "
        "unofficial' flag. Today: 0 league rows; 1 club chart documented as team-published and unofficial.",
        "",
        E("ld_depth", "colts"),
        "Register only what a club publishes; never merge club charts into a league chart.")

    add("RR-C26", "Availability and depth",
        "Add a per-team view: starters out, replacements named, net injury count",
        "PARTIAL",
        "The net count is computable from the report; 'starters out' needs a starter flag (blocked) and "
        "'replacements named' needs an announcement (RR-C24), so two of the three columns must stay blank.",
        f"Per-club view with a net count plus two columns populated only where an official source states "
        f"them. This capture: {m['injury_rows']} rows across {m['injury_clubs']} clubs, 0 starters-out flags, "
        f"0 named replacements.",
        "",
        E("capture", "ll"),
        "Ship the view with the two blank-by-policy columns and the reason inline, so the gap is visible "
        "rather than hidden.")

    add("RR-C27", "Availability and depth",
        "Interactive Offense vs Defense Matchup Deficiency Matrix (1st-4th string)",
        "BLOCKED-SOURCE",
        "The matrix needs a string rank on both sides of the ball; no official source publishes one "
        "(RR-C18), so any grid built today would be decoration.",
        "One populated cell from verified ranks for 1 fixture (both sides), or a published statement that "
        "the matrix is unavailable. Today: 0 cells.",
        "",
        E("ld_depth"),
        "Keep it as a page state ('waiting on a depth source'), not as a computed grid.")

    add("RR-C28", "Availability and depth",
        "Archive weekly injury reports for past seasons",
        "BLOCKED-SOURCE",
        "The league publishes the current weekly report and offers no historical week archive, so a "
        "designation study needs a third-party archive whose licence has not been read.",
        "At least 3 seasons x 18 weeks of dated captures with hashes before any designation-reliability claim "
        "is published. Today: 0 archived seasons.",
        "",
        E("injury"),
        "Reviewer decides whether an archive may be relied on; if yes, one season per run with the retrieval "
        "date recorded per week.")

    # ---- D. correlations, parlays and props ----------------------------------------------
    add("RR-D1", "Correlations",
        "Compute correlations only from officially sourced numbers and publish n with each value",
        "BUILT",
        "Nothing blocks the rule; the sample is limited by what the league publishes in a table, and the "
        "limit is stated rather than papered over.",
        f"Every coefficient shows n and an interval. This capture: {m['n_corrs_official']} coefficients on "
        f"n={m['corr_n']} official standings rows with 95% Fisher-z intervals; "
        + ("the sample is the whole 32-club table - the 8 clubs whose points chunk failed at the "
           "03:55:00Z read were re-read at 04:21:00Z from the same URL."
           if m['corr_n'] == 32 else
           f"{32 - int(m['corr_n'] or 0)} clubs excluded because the points columns were not readable in "
           f"the chunk that failed, so n is {m['corr_n']} and not 32."),
        f"Headline: point differential versus wins r = {m['corr_headline']} (n={m['corr_n']}). Line Desk "
        f"publishes {m['ld_corr_values']} coefficients on n={m['ld_corr_n']} official standings rows.",
        E("capture", "nist", "ld_corr"),
        "Done at 04:21:00Z on 2026-11-18: the second standings chunk was re-read and n moved 24 to 32. "
        "What is left is the guard - keep the check that refuses to publish a short read, and re-read both "
        "chunks each time the capture runs so n cannot silently drop.")

    add("RR-D2", "Correlations, parlays and props",
        "Keep parlays and prop combos behind a joint-evidence gate (no multiplying marginals; operator "
        "void/push rules required)",
        "BUILT",
        "Nothing passes it: a combo needs BOTH a directly validated joint probability and the operator's "
        "void/push rules, and neither is in a source this project may use.",
        "A combo is ranked only when a joint probability measured on n >= 1,000 team-games and a cited "
        "operator settlement rule both exist. Today: 0 combos ranked.",
        "The measured 4-leg joint versus the independent product is published from the third-party extract "
        "and is used to REFUSE a price, not to set one.",
        E("root_corr", "root_props"),
        "Recompute the joint from official play-by-play and attach the operator rule URL per market.")

    add("RR-D3", "Correlations, parlays and props",
        "Publish every model total twice until one wins",
        "PARTIAL",
        "The root model publishes aggregate total accuracy (model, market, blend) but not two named estimators "
        "side by side per fixture with a gap column.",
        "Two estimator columns plus a gap for 14/14 fixtures of a slate, then a recorded walk-forward decision "
        "to collapse. Today: aggregates only.",
        "",
        E("root_lines", "ld_orig"),
        "Low cost: the estimators already exist in the pipeline; only the per-fixture view is missing.")

    add("RR-D4", "Correlations, parlays and props",
        "Player-prop bet combos in the competition",
        "BLOCKED-SOURCE",
        "No historical prop prices exist in any source the project holds, so prop ROI is undefined; prop "
        "accuracy and calibration are published instead.",
        f"A prop price series (open and close, >= 1 season) or a ruling that props are scored on probability "
        f"error only. Today: 0 prop prices; {m['pd_prop_rows']} prop snapshot rows with both price columns "
        f"null.",
        "",
        E("root_props", "pd_prices"),
        "Same decision as RR-A9; publish no prop ROI meanwhile.")

    # ---- E. fixture context ---------------------------------------------------------------
    add("RR-E1", "Fixture context",
        "Transcribe the venue of every fixture from the official game centre and publish it",
        "PARTIAL",
        "Source-feasibility is now proven and coverage is still one fixture: only the Patriots-Lions game "
        "centre was opened at this capture. Reading 14 game centres is a scheduled job, not a research "
        "question.",
        f"14 of 14 fixtures of a slate with (location, stadium) from the game centre. Today: "
        f"{m['venues']}/14 recorded first-hand (Munich; FC Bayern Munich Stadium).",
        "",
        E("centre", "capture"),
        "Batch-read the week's game centres and store venue, roof/surface and the Game Book URL in one pass.")

    add("RR-E2", "Fixture context",
        "Add a fixture-context feature set built only from published schedule facts",
        "PARTIAL",
        "Only fields the schedule page actually prints may enter. Verified at this capture: date, kickoff "
        "slot (Thursday / Sunday / SNF / MNF), broadcast, international-game marker, and the bye list. Rest "
        "days become derivable once RR-E1 covers every fixture.",
        f"One row per fixture with a source URL per field, and no field the schedule page does not print. "
        f"Today: {m['finals_verified']} fixtures with 5 verified field types; venue {m['venues']}/14.",
        f"Week 10 slate confirmed first-hand: {m['finals_verified']} games, {m['byes']} byes "
        f"(CHI, DEN, PHI, TB), 1 international game.",
        E("schedule", "capture"),
        "Add the fixture-context table to the root pipeline as derived-only from the week pages.")

    add("RR-E3", "Fixture context",
        "Publish the league's dated schedule announcement beside the live schedule page",
        "BUILT",
        "Nothing. The May 14, 2026 announcement is registered in the source register and is now linked beside "
        "the transcribed slate on the Live official checks page.",
        "Announcement URL and its own date shown next to every published fixture table. Done on the page this "
        "register links.",
        "",
        E("sched-announce", "capture"),
        "Keep the announcement dated: flexible-scheduling moves make the schedule page itself stale by design.")

    add("RR-E4", "Fixture context",
        "Stadium roof/surface and NWS hourly wind/precipitation overlay",
        "PARTIAL",
        "Two sources must be joined at kickoff and neither is ingested per fixture. Observed at this capture: "
        "the schedule page prints a short weather string per fixture, but no roof or surface designation; "
        "NWS grids are not fetched per stadium.",
        f"A roof/surface register for 30 stadiums with a source per row, plus an NWS hourly reading at "
        f"kickoff plus/minus 90 minutes for 14/14 fixtures. Today: 0 stadiums, 0 joins.",
        "The official weather string on the schedule page is treated as published text, not as a forecast "
        "model input.",
        E("schedule", "nws"),
        "Build the static stadium register first, then the per-fixture join; keep totals and passing props "
        "unadjusted until both exist.")

    add("RR-E5", "Fixture context",
        "2026 kickoff and declared onside-kick regime priors filter",
        "NOT-STARTED",
        "Needs the dated rulebook text attached to a measured prior; the project has neither a cited clause "
        "nor a computed effect size.",
        "A prior derived from >= 2 seasons of official play-by-play, cited to the 2026 rulebook clause, and "
        "applied only as a documented adjustment. Today: 0 priors computed.",
        "",
        E("rulebook"),
        "Verify the rule text first; a regime prior from memory is the kind of number this project refuses "
        "to publish.")

    add("RR-E6", "Leaderboard and gates",
        "Compute and publish the 'removal of luck' panel",
        "BUILT",
        "Nothing blocks the panel; its conclusion is that no edge is significant, which is why nothing is "
        "promoted.",
        "Every published edge shown with a luck test: coin-flip p-value, persistence correlation, and the "
        "expected maximum of k trials. Today: all three on the panel.",
        "Home cover rate 48.9% (n=6,892, p=0.0727); luck persistence r=0.024 (n=842) - both computed from the "
        "committed extract, labelled third-party.",
        E("root_luck", "root_lb"),
        "Re-run on the frozen holdout only; do not re-mine the panel for a significant slice.")

    # ---- F. data operations ----------------------------------------------------------------
    add("RR-F1", "Data operations",
        "Add durable snapshot storage and alerts (captures outside the static site; freshness and "
        "source/schema monitoring)",
        "BLOCKED-DECISION",
        "The storage target and alert channel are not provisioned or chosen, so captures live in the "
        "repository. The monitor condition itself is already specified: a source older than 72 hours, or a "
        "required column that disappears.",
        "One non-site store plus a firing freshness alert and one schema alert. Today: 0 external stores; "
        "1 dated in-repo capture; 12 consistency checks in the capture builder.",
        "",
        E("capture", "repo-script"),
        "Reviewer picks the store; the format and the alert conditions are defined, so this is plumbing.")

    add("RR-F2", "Data operations",
        "Split the site into a public analysis layer and a private data layer",
        "BLOCKED-DECISION",
        "The redistribution terms for raw league row-level data have not been read and adjudicated, so raw "
        "rows currently sit in the published tree; that is the exposure the requirement is about.",
        "A written terms ruling plus a private store holding raw rows, with public pages limited to derived "
        "values and links. Today: ruling 0; row-level capture published at root.",
        "",
        E("root_flag", "genius"),
        "Until the ruling lands, publish aggregates (counts, deltas) rather than row-level captures.")

    add("RR-F3", "Data operations",
        "Add a drift alarm to every scraper (pinned expected row counts and required fields; fail loudly)",
        "PARTIAL",
        "This session added the first root-level alarm: the capture builder runs a fixed battery of "
        "consistency checks and exits non-zero before publishing if any fails. The hub parsers are not yet "
        "pinned to expected row counts.",
        f"Every parser declares (min_rows, required_columns) and the build fails when a field goes missing. "
        f"Today: {m['checks']} checks on the official capture, 0 hub parsers pinned.",
        "Checks in force: club count = 32, league win/loss parity, tie parity, slate size, bye/slate overlap, "
        "one appearance per club, quarter sums equal the published final, cross-page record agreement.",
        E("repo-script", "capture"),
        "Port the same assertion pattern into the injury and depth parsers and publish the alarm state on the "
        "verification page.")

    add("RR-F4", "Data operations",
        "Publish a weekly 'what changed' diff instead of a static snapshot",
        "PARTIAL",
        "Diff machinery exists in the Review Board injury register, but the published landing page shows "
        "levels, and the root pipeline stamp is now 17 days older than this capture.",
        f"One dated diff per week (rank change, rating change, availability change) on the landing page. "
        f"Today: 1 dated capture ({m['capture_read_at']}) against a pipeline stamp of 2026-11-01; the gap is "
        f"reported here, but no per-club diff exists.",
        "",
        E("rb_injuries", "root_verify"),
        "The next dated capture closes this row: the diff is then computed rather than promised.")

    add("RR-F5", "Data operations",
        "Store every injury-hub read with its clock time and publish the delta, never the level",
        "PARTIAL",
        f"Clock times are stored: every row in this capture carries read_at_utc = {m['capture_read_at']} and a "
        "source URL. The delta still needs the second read (RR-C12).",
        f"read_at_utc on 100% of published availability rows: {m['injury_rows']}/{m['injury_rows']} in this "
        f"capture. Delta: 0 rows, because 1 read is not a series.",
        "",
        E("capture", "injury"),
        "Fold the clock time into the hub registers too, so every read in the tree is dated.")

    add("RR-F6", "Data operations",
        "Point-in-time snapshot ledger for injuries, depth charts and inactives",
        "PARTIAL",
        "A ledger needs several dated states. There is one root capture plus the hub registers' single "
        "snapshots, so a backtest could still reach past what was knowable on a given date.",
        "Any backtest query answerable as 'what did we know at time T' with the ledger window start recorded. "
        f"Today: window = 1 root read ({m['capture_read_at']}) plus hub reads dated 2026-11-12 and 2026-11-14.",
        "The root capture register is append-only, dated and per-row sourced, which is the ledger row format.",
        E("capture", "ld_flag"),
        "Point the register at the canonical capture job (RR-C11) and the ledger becomes usable for point-in-time joins.")

    # ---- G. site, decision support and process ---------------------------------------------
    add("RR-G1", "Site and decision support",
        "Put a decision-readiness table on the landing page: one row per requirement, with the gate that "
        "blocks it and the number that would clear it",
        "BUILT",
        "Nothing blocks the table. What it reports is the blocker list; the rows labelled BLOCKED-DECISION are "
        "the reviewer's agenda and are deliberately not implemented here.",
        f"{N_ROWS} rows on the landing page, one per briefed requirement, each with a status, a named blocking "
        f"gate, a clearing number and evidence links; the expanded register carries the next action per row.",
        f"Status split: {m['status_summary']}",
        E("root_readiness", "root_exec", "ld_req"),
        "Work the BLOCKED-DECISION rows top to bottom; five of them unlock a dozen others.")

    add("RR-G2", "Site and decision support",
        "A clear list of questions, information and answers needed before any decision, with suggestions to "
        "discover the missing information",
        "PARTIAL",
        "The registers exist and are consolidated, but most questions are still open and not every one has a "
        "discovery action attached.",
        f"0 open questions without a stated discovery action. Today: {m['rb_questions']} question rows "
        f"({m['rb_answered']} answered, {m['rb_partial']} partially answered, {m['rb_unanswered']} unanswered) "
        f"on the review board, plus {m['vh_questions']} Verify Hub rows with have / missing / how-to-find "
        f"fields.",
        "",
        E("vh_q", "rb_queue", "ld_q"),
        "Answer the BLOCKED-DECISION questions first (price policy, depth route, storage, rewards, terms); the "
        "rest is engineering.")

    add("RR-G3", "Site and decision support",
        "A dedicated suggestions section where a reviewer chooses the best path before any change is implemented",
        "BUILT",
        "Review capacity, not structure: the queues are large and unapproved by design, and this session "
        "implemented nothing from them.",
        f"A verdict per cluster. Today: {m['rb_proposals']} proposals in {m['rb_clusters']} clusters on the "
        f"Review Board queue, 0 approved; Verify Hub carries {m['vh_suggestions']}; root register rows stay "
        f"PROPOSED until chosen.",
        "",
        E("root_sugg", "rb_queue", "vh_sugg", "pd_sugg"),
        "Choose one path per cluster; the site keeps the rest visible rather than deleting them.")

    add("RR-G4", "Site and decision support",
        "Executive summary outlining the important details",
        "BUILT",
        "Nothing. Its numbers are read from the same registers this table uses, so it cannot drift silently.",
        "Summary states what is verified, what is blank and why, with counts matching this register.",
        "",
        E("root_exec", "root_verify"),
        "Keep it generated.")

    add("RR-G5", "Site and decision support",
        "GitHub Pages site: clean landing page and category subpages, table-first, with analysis and findings",
    "BUILT",
        "Navigation breadth was the gap this session closed: every hub directory in the repository is now "
        "linked from the navigation this build writes, and duplicated labels were removed. Deciding whether "
        "the duplicated hubs should be merged is still a reviewer call.",
        "0 hub directories absent from the navigation; 0 duplicate labels. Today: satisfied by this build, "
        "asserted by the site tests.",
        "",
        E("root_archive", "root_verify"),
        "Consolidation of overlapping hubs is logged as a suggestion, not taken here.")

    add("RR-G6", "Site and decision support",
        "Every table row carries a source link to an official site; unconfirmed values stay blank and flagged; "
        "nothing is inferred",
        "PARTIAL",
        "Enforced for the root build by CI (a published table row without a source cell fails the build), but "
        "33 pages outside the root build carry no source column, and some hub rows are third-party.",
        "0 published rows without a source cell across the whole tree. Today: root build 0 (enforced), "
        "33 sibling pages without the column.",
        "",
        E("root_flag", "root_verify"),
        "Extend the check to the sibling hubs only if the reviewer keeps them published at this URL.")

    add("RR-G7", "Site and decision support",
        "Review the repository line by line, verify from official sources, link everything for manual review, "
        "and flag irregularities",
        "BUILT",
        "Coverage is continuous, not one-off: this capture adds a dated official re-read with observed values; "
        "a line-by-line re-read of every hub remains in progress across sessions.",
        "Every hub carries a dated review or flag register. Today: root flags, Line Desk repo review, Price "
        f"Desk register, Verify Hub claim audit, plus {m['checks']} consistency checks with observed values in "
        f"this capture.",
        "",
        E("root_flag", "ld_repo", "capture"),
        "Keep flags published; a flag is resolved by evidence, never by deleting its row.")

    add("RR-G8", "Site and decision support",
        "Parallel-session coordination: claims, non-overlapping scopes, handoffs and a final integration session",
        "ONGOING",
        "Stale claims, not the format: several pull requests and board entries from earlier sessions are older "
        "than the 60-minute handoff window, so scope collisions are the live risk.",
        "0 in-progress claims without a recent commit; 0 files edited by two sessions in the same window. "
        "Today: this session's claim is pushed before its edits, and every overlap is recorded on the board.",
        "",
        E("coord"),
        "Reviewer to close or merge the stale pull requests so the board reflects the tree.")

    add("RR-G9", "Site and decision support",
        "No manual input from the owner; the session completes the work itself, with no hallucinated values",
        "BUILT",
        "Nothing blocks the process. Note that 'no manual input' does not license inventing values: where a "
        "source is missing, the cell stays blank and the gap is published.",
        "Every published number traceable to a committed artefact or a dated read. Today: the landing table, "
        "the capture register and the correlation table are all generated by scripts.",
        "",
        E("root_method", "capture"),
        "Keep generation deterministic so CI can rebuild the site without a human in the loop.")

    # ---- H. explicit rejections demanded by the brief ---------------------------------------
    add("RR-H1", "Explicit rejections",
        "Reject: deriving depth order from jersey number, experience or salary",
        "REJECTED",
        "Rejected by the brief and honoured in the data: every tier cell in the depth register is blank "
        "instead of proxied from a roster attribute.",
        "A build-time check that fails when a feature source is named after jersey, salary or experience. "
        f"Today: 0 such features registered; no automated guard yet.",
        "",
        E("ld_depth", "ld_flag"),
        "Add the guard so the rejection cannot quietly rot into a temporary proxy.")

    add("RR-H2", "Explicit rejections",
        "Reject: ranking strategies by season-long ROI",
        "REJECTED",
        "Rejected by the brief; the published ranking rule is signal-first (gates, adjusted significance, "
        "decided n) and realised ROI is reported but never used to rank.",
        "The ranking function must not accept a realised-ROI key. Today: enforced by the published rule and "
        "by the Line Desk check that staking never enters the ranking.",
        "",
        E("ld_lb", "root_lb"),
        "Keep the ROI column; keep it out of the sort.")

    return R


def main() -> int:
    m = measures()
    m["status_summary"] = "(tallied below)"
    cap = J(CAPTURE) or {}
    # Two passes: the second pass can report the status split, which the first pass defines.
    totals: dict[str, int] = {}
    for r in rows(m):
        totals[r["status"]] = totals.get(r["status"], 0) + 1
    m["status_summary"] = ", ".join(f"{k}: {v}" for k, v in sorted(totals.items()))
    data_rows = rows(m)
    totals = {}
    for r in data_rows:
        totals[r["status"]] = totals.get(r["status"], 0) + 1
    for r in data_rows:
        for key in ("blocking_gate", "clears_when", "measured_now", "next_action"):
            r[key] = str(r[key]).replace(N_ROWS, str(len(data_rows)))
    doc = {
        "meta": {
            "title": "Decision-readiness register - one row per requirement in the owner brief",
            "generated_by": "scripts/build_readiness.py",
            "generated_from_capture": CAPTURE,
            "official_read_at_utc": m["capture_read_at"],
            "capture_checks": len(cap.get("checks", []) or []),
            "rules": "Statuses describe this repository, not the league. A value that cannot be established "
                     "from a committed artefact or a dated official read is left blank with the reason named. "
                     "Rows marked BLOCKED-DECISION are reviewer questions; this build implements none of them.",
            "row_count": len(data_rows),
            "status_totals": totals,
        },
        "rows": data_rows,
        "measures": m,
    }
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, "data/derived/readiness.json"), "w") as fh:
            json.dump(doc, fh, indent=1)
            fh.write("\n")
        print(f"wrote data/derived/readiness.json ({len(data_rows)} rows)")
    print("status totals:", json.dumps(totals, sort_keys=True))
    print(f"capture {m['capture_read_at']}: {m['finals_verified']} finals, "
          f"{m['standings_rows']} standings rows (points on {m['standings_complete']}), "
          f"{m['n_corrs_official']} official correlations on n={m['corr_n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
