"""Suggestion review queue and decision-question register.

Nothing in this module is auto-implemented. Each suggestion carries explicit
options so a reviewer can choose a path; each question states what is already
known, what is missing, how the missing piece could be discovered, and which
decision stays blocked until it is answered.
"""

from __future__ import annotations

INJ_W10 = "https://www.nfl.com/injuries/league/2026/REG10"
SCHED_W11 = "https://www.nfl.com/schedules/2026/by-week/week-11"
STANDINGS = "https://www.nfl.com/standings/division/2026/REG"
GAMEBOOK = "https://operations.nfl.com/players/players-rights-and-responsibilities/official-game-book/"
GENIUS = "https://www.nfl.com/news/nfl-extends-strategic-partnership-with-genius-sports"
NWS = "https://www.weather.gov/documentation/services-web-api"
NFL_TERMS = "https://www.nfl.com/legal/terms"
NFL_PRIVACY = "https://www.nfl.com/legal/privacy"
NIST_CORR = "https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm"

# --------------------------------------------------------------------------
# Suggestion review queue
#
# priority : P1 unblocks the most requirements / P2 material / P3 optional
# options  : the paths a reviewer may choose. Nothing here is implemented
#            until one is explicitly selected.
# --------------------------------------------------------------------------

SUGGESTIONS = [
    dict(
        id="S01", priority="P1",
        title="Capture the same official pages on a schedule, outside the agent",
        area="Injury & depth, results, schedule",
        problem=("Every availability fact in this project rests on a capture an agent performed by hand. "
                 "One capture cannot support a surprise term, a weekly diff, a designation-reliability "
                 "study or a lookahead-safe backtest. The requirement set asks for a Wednesday-to-kickoff "
                 "series and none exists."),
        proposal=("Add a scheduled job that captures the official injury report, the weekly schedule page "
                  "and the standings page at fixed UTC times, writing each capture to durable storage with "
                  "a UTC timestamp, source URL and content hash. The job, not the agent, owns the cadence."),
        options=[
            "Run it on GitHub Actions at 15:00 UTC Wed/Thu/Fri/Sat plus a pre-kickoff pass, committing only the manifest and hashes to the repo and the payload to durable storage.",
            "Run it in a small external scheduler with object storage; keep the repository free of raw payloads entirely.",
            "Keep agent-driven capture for now and accept that no surprise or diff feature can be published until this is built.",
        ],
        unblocks="R29, R32, R33, R34, R43, R50, R51, R65, R74",
        clears="Two consecutive weeks with ≥3 dated captures per week, each with a content hash, produced with no agent in the loop.",
        source_url=INJ_W10,
    ),
    dict(
        id="S02", priority="P1",
        title="Settle the price-data policy in writing before another price backtest is published",
        area="Price & market data",
        problem=("Closing-line value, market residual and price-based ROI are all uncomputed because no "
                 "authorised price source has been approved. Several hubs hold third-party price columns "
                 "that are labelled archived-unverified; publishing ROI from them would present an "
                 "unverified number as a result."),
        proposal=("Write a single policy document naming the authorised feed, its permitted use, the exact "
                  "definition of opening and closing, the retention period, and the rule that absent prices "
                  "stay blank. Commit it, then capture against it."),
        options=[
            "Adopt an official/league-authorised feed and pay for it; fastest route to a defensible CLV number.",
            "Adopt a licensed commercial odds archive with written redistribution terms; cheaper, still defensible if the terms permit storage.",
            "Publish no price-derived number at all for one season and evaluate only proper scores on unpriced forecasts; slowest, but zero terms risk.",
        ],
        unblocks="R01, R02, R03, R04, R05, R06",
        clears="A dated, committed policy plus ≥1,000 game-market rows with both opening and closing prices, source URL and UTC timestamp.",
        source_url=GENIUS,
    ),
    dict(
        id="S03", priority="P1",
        title="Pick one canonical originator and retire the rest as historical",
        area="Origination",
        problem=("Two committed originators disagree by 1.5 to 9.0 points on each of the same 15 games. "
                 "A residual against the market is meaningless while two different numbers are both called "
                 "'our line'."),
        proposal=("Name one model version as the source of truth, reproduce every displayed fair line from "
                  "it, and label every other line as historical on its page."),
        options=[
            "Keep the newer walk-forward model and relabel the older one historical.",
            "Keep the older model and relabel the newer one experimental.",
            "Publish both under the 'two totals until one wins' rule until a pre-registered walk-forward comparison produces an interval that excludes zero.",
        ],
        unblocks="R03, R04, R11, R12",
        clears="One named originator version reproducing ≥20 published markets, with the competitor visibly retired.",
        source_url=SCHED_W11,
    ),
    dict(
        id="S04", priority="P1",
        title="Resolve the depth source for all 32 clubs, or stop trying to build deficiency features",
        area="Injury & depth",
        problem=("The interactive deficiency matrix, the backup-replacement flag and the string-tier feature "
                 "all need a depth order. No club depth chart has been parsed, the league depth path returns "
                 "nothing, the Texans publish depth as an image, and no official snap-count source has been "
                 "confirmed. Every route is currently at 0 of 32 clubs."),
        proposal=("Evaluate the two routes in the order the brief specifies - club depth pages first, snap "
                  "counts second - and publish a club-by-club verdict table. Do not build the deficiency "
                  "feature until one route is verified for all 32 clubs."),
        options=[
            "Verify club depth pages one club at a time and publish a 32-row provenance table; build nothing until it reads 32/32.",
            "Confirm an official snap-count source and derive a starter proxy with a published threshold and sensitivity analysis.",
            "Declare depth unobtainable for this season, leave the replacement and string-tier columns permanently blank, and drop the deficiency matrix from scope.",
        ],
        unblocks="R26, R27, R35, R36, R37, R39, R41, R47, R48, R52, R54",
        clears="Either 32/32 club depth pages parsed into a dated register, or an official snap-count source confirmed for 32/32 clubs over ≥1 season.",
        source_url=GAMEBOOK,
    ),
    dict(
        id="S05", priority="P2",
        title="Capture official inactives so designation reliability can be measured",
        area="Injury & depth",
        problem=("The brief asks for 'Questionable' to be calibrated empirically rather than assigned a "
                 "percentage. That needs designations joined to who actually played. No inactives list has "
                 "been captured, so no play rate per designation can be computed and the label must not "
                 "enter any model."),
        proposal=("Capture the official inactives artefact for every game, join it to the injury report by "
                  "player and week, and publish a play rate with a 95% interval for each designation before "
                  "the designation is used as a feature."),
        options=[
            "Capture the weekly inactives article NFL.com publishes and transcribe it row by row.",
            "Capture Game Book Not-Active sections per game, which also gives starters and Did-Not-Play.",
            "Do neither and keep the designation out of every model, recording it as a permanently blocked feature.",
        ],
        unblocks="R26, R29, R35, R40, R49, R56",
        clears="≥2 seasons and ≥1,000 designation-to-outcome pairs, each designation carrying a play rate and interval.",
        source_url=GAMEBOOK,
    ),
    dict(
        id="S06", priority="P2",
        title="Collapse the duplicate hubs into one canonical navigation",
        area="Governance & site",
        problem=("The repository holds roughly 26 independently built dashboards. The root navigation repeats "
                 "the suggestions link and omits newer hubs. Two leaderboards rank different candidate sets "
                 "under different rules, and three results registers use different verification labels, so "
                 "their numbers cannot be compared or added."),
        proposal=("Keep every hub reachable but make one navigation the index, mark each hub's data vintage "
                  "and verification tier, and state on the leaderboard page that the two ranking rules are "
                  "not comparable."),
        options=[
            "Integrate now: one nav, one canonical page per subject, sibling hubs archived behind a dated link.",
            "Integrate lazily: keep siblings live, but add a vintage and tier banner to every hub and one top-level index.",
            "Freeze new hubs and let the existing ones stand, accepting the duplication.",
        ],
        unblocks="R07, R15, R17, R19, R72, R73",
        clears="One navigation with 0 duplicate entries and every hub carrying a visible data-vintage and verification tier.",
        source_url=SCHED_W11,
    ),
    dict(
        id="S07", priority="P2",
        title="Read the source terms before publishing any more row-level data",
        area="Governance & data policy",
        problem=("The brief asks for a public analysis layer and a private data layer. Raw row-level extracts "
                 "are currently committed alongside the public site, and no source-by-source terms register "
                 "exists."),
        proposal=("Publish a terms register per source stating what may be stored, derived and redistributed, "
                  "then move raw rows behind access-controlled storage and leave only derived analysis and "
                  "official links on the public site."),
        options=[
            "Full separation: derived analysis public, all raw rows private, links only.",
            "Partial separation: public derived aggregates plus the official injury-report rows (already public on NFL.com), everything else private.",
            "No change: accept the terms risk and keep raw rows in the repository.",
        ],
        unblocks="R62, R63, R64",
        clears="A terms register covering 100% of ingested sources plus external durable storage with freshness and schema alerts.",
        source_url=NFL_TERMS,
    ),
    dict(
        id="S08", priority="P2",
        title="Start the singles-only shadow baseline now, so prospective data begins accumulating",
        area="Origination, leaderboard",
        problem=("Every skill claim needs a pre-registered forecast recorded before kickoff. Nothing has "
                 "accumulated, so the prospective sample is zero and no promotion or demotion gate can ever "
                 "fire."),
        proposal=("Freeze a simple team-strength model, publish its pre-kickoff forecasts every week with a "
                  "timestamp and commit hash, and score them on untouched data. Keep it singles-only."),
        options=[
            "Freeze the existing point-ratings model as the shadow baseline and start logging immediately.",
            "Freeze a deliberately naive baseline (point differential only) so the skill bar is easy to beat and honest.",
            "Wait until the price policy is settled so CLV can be logged from the first week - costs a season of prospective data.",
        ],
        unblocks="R06, R14, R16, R17, R21, R22",
        clears="≥6 consecutive weeks of frozen pre-kickoff forecasts with a commit hash per week, scored on data untouched until after kickoff.",
        source_url=STANDINGS,
    ),
    dict(
        id="S09", priority="P3",
        title="Capture venue, roof and weather from first-party sources only",
        area="Fixture, venue & weather",
        problem=("Venue strings are currently transcribed from the schedule page's own stadium reference. "
                 "Roof status and an NWS forecast grid have not been captured at all, so the totals and "
                 "passing-prop weather overlay cannot be built."),
        proposal=("Transcribe the venue per fixture from the game centre, capture the roof designation with "
                  "its timestamp, and capture the NWS hourly grid at a recorded time, keeping forecast-captured-at "
                  "separate from observed."),
        options=[
            "Capture game-centre venue for 13 fixtures a week and reconcile against the schedule-page string.",
            "Skip game-centre transcription and treat the schedule-page venue as sufficient, documenting the downgrade.",
            "Defer weather entirely and keep totals free of any weather term this season.",
        ],
        unblocks="R57, R58, R59, R60",
        clears="Venue verified for 100% of fixtures over ≥2 weeks from the game centre, plus roof and NWS captures with timestamps for ≥2 weeks.",
        source_url=NWS,
    ),
    dict(
        id="S10", priority="P3",
        title="Publish the luck panel with the persistence test once historical standings exist",
        area="Leaderboard & skill",
        problem=("The luck panel published today shows one season: Pythagorean expectation, the luck "
                 "distribution and four official correlations, all at n=32. It cannot show whether luck "
                 "persists, which is the part that matters for separating skill from variance."),
        proposal=("Capture official standings for at least three prior seasons and publish a season-to-season "
                  "luck correlation with n and interval, alongside the single-season panel already computed."),
        options=[
            "Backfill three seasons of official standings and publish the persistence test.",
            "Publish the single-season panel with an explicit 'persistence not tested' banner and revisit next season.",
            "Drop the persistence test and rely only on proper scores and holdouts for the skill claim.",
        ],
        unblocks="R23",
        clears="≥3 seasons of official standings producing a season-to-season luck correlation with n≥90 and a 95% interval.",
        source_url=STANDINGS,
    ),
    dict(
        id="S11", priority="P3",
        title="Make the reward structure explicitly hypothetical until it is funded and lawful",
        area="Leaderboard & skill",
        problem=("Leaderboard pages describe reward tiers. No funded pool, no eligibility rules and no "
                 "jurisdiction review exist. Presenting tiers alongside live strategy pages implies a "
                 "competition that is not running."),
        proposal=("Label all rewards points-only and hypothetical, and gate any funded competition behind a "
                  "documented funding commitment, eligibility rules and jurisdiction-specific legal review."),
        options=[
            "Relabel everything points-only now and remove monetary framing from every page.",
            "Keep the tier table but add a prominent unfunded banner to every leaderboard page.",
            "Remove the reward section entirely until funding exists.",
        ],
        unblocks="R17, R18",
        clears="Every leaderboard page states the reward status; a funded competition requires a dated funding commitment and a jurisdiction review before launch.",
        source_url=NFL_PRIVACY,
    ),
    dict(
        id="S12", priority="P3",
        title="Add the two-sided falsification field to the strategy template",
        area="Leaderboard & skill",
        problem=("Pre-registration is described in several places but no strategy entry actually carries a "
                 "statement of what result would falsify it. Without it, pre-registration is a label rather "
                 "than a commitment."),
        proposal=("Add two required fields to the strategy template - the result that would confirm the "
                  "hypothesis and the result that would kill it - each a statistic with a threshold, committed "
                  "before the evaluation window opens."),
        options=[
            "Add the fields and make the template reject an entry that leaves either blank.",
            "Add the fields as optional for one season and review uptake.",
            "Leave the template as is and rely on the existing gates.",
        ],
        unblocks="R16, R21, R66",
        clears="100% of registered strategies carry both thresholds, committed before their evaluation window opens.",
        source_url=NIST_CORR,
    ),
]

# --------------------------------------------------------------------------
# Decision questions
# --------------------------------------------------------------------------

QUESTIONS = [
    dict(
        id="Q01", topic="Strategy eligibility",
        question="Can any strategy be used for real money or earn a reward today?",
        known=("No. Every hub reports zero qualified strategies. The Line Desk lists 7 candidates plus 2 "
               "controls with none qualified; the Price Desk reports 28 historical entrants all marked "
               "NEEDS_REVIEW or REJECTED. No reward is funded."),
        missing=("One frozen candidate registry with a single gate version; a funded pool; a jurisdiction "
                 "review. The hubs do not share a candidate set or a ranking rule, so their counts are not "
                 "interchangeable."),
        discover=("Select one registry and gate version, run every candidate through it on an untouched "
                  "holdout, and publish the gate-by-gate outcome. Keep all strategies PAPER until then."),
        blocked="Any promotion to LIVE, any reward, any ROI claim.",
        source_url=STANDINGS,
    ),
    dict(
        id="Q02", topic="Price data",
        question="What price-data policy governs market, opening, closing and our own prices?",
        known=("No official opening or closing price archive has been captured. The strict official-only "
               "store has 0 rows. The wider register holds 2,364 game-market rows with 2,364 blank opening "
               "fields and 1,956 third-party closing values."),
        missing=("An authorised source, its terms, the market coverage, timestamps, immutable raw evidence, "
                 "and a canonical definition of opening versus closing."),
        discover=("Approve the policy in writing first, then test capture on every market type for two weeks "
                  "and measure coverage before publishing any price-derived statistic."),
        blocked="Closing-line value, market residual, price-based ROI, the CLV escrow stage of the leaderboard.",
        source_url=GENIUS,
    ),
    dict(
        id="Q03", topic="Origination",
        question="Which model is the canonical line originator?",
        known=("Two committed originators disagree by 1.5 to 9.0 points on each of the same 15 Week 9 games. "
               "This is a repository-reported discrepancy, not an NFL fact."),
        missing=("The authority file, the version, the sign convention and the tie-breaking rule have not "
                 "been reconciled."),
        discover=("Name one source of truth, reproduce every displayed fair line from it, and reconcile a "
                  "fixed sample of games and markets against the published output."),
        blocked="Any residual against the market, any decomposition view, any origination-alpha claim.",
        source_url=SCHED_W11,
    ),
    dict(
        id="Q04", topic="Results corpus",
        question="Is the results corpus complete and canonical enough for backtests?",
        known=("Two registers with different scopes exist. One holds 44 NFL.com finals for Weeks 7 to 9 plus "
               "Week 10 Thursday. The other holds a 1,088-game feed with 22 official, 931 archived-unverified "
               "and 135 missing rows. This session added Week 10: 14 of 14 games FINAL from the official "
               "schedule page."),
        missing=("A single canonical game key, full-season coverage across the evaluation window, and "
                 "source-level verification for every outcome."),
        discover=("Reconcile one feed by NFL game id and require complete official coverage for the "
                  "pre-registered window. Keep third-party rows separately identified and never add the two "
                  "registers together."),
        blocked="Backtests, ROI, the 136-game pre-registered corpus, opponent-aware ratings.",
        source_url="https://www.nfl.com/schedules/2026/by-week/week-10",
    ),
    dict(
        id="Q05", topic="Availability",
        question="How is a starter defined, and who replaces an injured starter?",
        known=("The official injury report publishes no depth column, no starter field and no replacement "
               "name. This session's capture confirms that: 347 rows across 28 clubs, with practice status "
               "and game status only. Game Books identify who actually started, not who was expected to or "
               "what string they are."),
        missing=("An official expected-starter source; replacement identity; string tier; official snap counts. "
                 "Club depth pages have not been parsed for any of the 32 clubs."),
        discover=("Publish a club-by-club provenance table for both permitted routes. Build no deficiency "
                  "feature until one route reads 32 of 32."),
        blocked="The deficiency matrix, the backup-replacement flag, every depth-based feature, the ablation study.",
        source_url=GAMEBOOK,
    ),
    dict(
        id="Q06", topic="Designation reliability",
        question="What does 'Questionable' actually mean, and may it be a model feature?",
        known=("The official report publishes designations, not probabilities. This session counted 90 "
               "Questionable, 70 Out, 11 Doubtful and 176 blank game-status cells across 347 listed players. "
               "No play rate can be computed from that alone."),
        missing=("Designations joined to official inactives over several seasons, with sample sizes, "
                 "intervals, and role and position context."),
        discover=("Capture inactives, join to designations, and publish a play rate with a 95% interval per "
                  "designation. Only then may the label enter a model, and only as a surprise relative to the "
                  "prior capture, never as a level."),
        blocked="Injury as a model feature, any fixed injury penalty, the designation-reliability gate.",
        source_url=INJ_W10,
    ),
    dict(
        id="Q07", topic="Correlations",
        question="Which correlations are legitimate for each intended use?",
        known=("Four coefficients were computed this session from official 2026 standings at n=32, each with "
               "a Fisher-z 95% interval: win pct vs points for +0.657 [+0.400, +0.818]; win pct vs points "
               "against -0.670 [-0.826, -0.419]; win pct vs net points +0.875 [+0.758, +0.938]; win pct vs "
               "Pythagorean expected wins +0.872 [+0.752, +0.936]. The Line Desk register adds eight "
               "standings coefficients at n=32 and two pooled at n=64."),
        missing=("Any player-prop, injury or parlay-leg correlation from an official source. Team-standings "
                 "coefficients must not be transferred to player legs."),
        discover=("Publish separate named correlation families, each with source, definition, n and interval. "
                  "Where no official evidence exists, leave the value blank rather than substituting a "
                  "third-party estimate."),
        blocked="Parlay and same-game-parlay pricing, prop-combo joint probabilities.",
        source_url=STANDINGS,
    ),
    dict(
        id="Q08", topic="Parlays and combos",
        question="When may parlays and prop combos enter the competition?",
        known=("The joint-evidence gate is in force: nothing is ranked until a directly validated joint "
               "probability and the operator's void/push rules are both available. A marginal correlation "
               "does not determine a joint distribution."),
        missing=("Authorised historical prices, observed joint outcomes, calibration and uncertainty per "
                 "combo class, and the exact settlement rules for voids, pushes and partial settlement."),
        discover=("Pre-register a joint model, score it directly against observed joint outcomes in "
                  "chronological holdouts, and publish n, calibration, interval and the settlement contract."),
        blocked="Any ranked parlay or prop-combo entry, any combo reward.",
        source_url="https://www.itl.nist.gov/div898/possolo/TutorialWEBServer/TutorialMetrologists2011Nov09.xht",
    ),
    dict(
        id="Q09", topic="Skill versus luck",
        question="What proves signal skill rather than favourable staking or luck?",
        known=("Signal and staking are ranked separately in the Line Desk, so a lucky staking run cannot "
               "move the signal rank. The luck panel now has an official single-season basis: luck standard "
               "deviation 1.076 wins across 32 clubs, with the Pythagorean expectation explaining a large "
               "share of the win-pct variance."),
        missing=("A persistence test. One season cannot show whether luck repeats, and no strategy has a "
                 "prospective sample, so no promotion or demotion gate has ever fired."),
        discover=("Rank by pre-registered benchmark-relative proper score on chronological holdouts with "
                  "game-cluster uncertainty and multiplicity adjustment, include random and favourites-only "
                  "controls under identical settlement rules, and publish ROI separately."),
        blocked="Any promotion to LIVE, any skill claim, any demotion decision.",
        source_url=STANDINGS,
    ),
    dict(
        id="Q10", topic="Data governance",
        question="How are raw data, retention and source terms governed?",
        known=("The repository publishes both derived analysis and raw row-level datasets. No source-by-source "
               "terms register exists. This hub applies a derived-only policy for the data it added."),
        missing=("Terms for each source, permitted storage and redistribution, personal-data exposure, "
                 "immutable external retention, and a deletion and retention policy."),
        discover=("Add a terms register before widening ingestion, move raw rows to access-controlled durable "
                  "storage, and add freshness and schema alerts."),
        blocked="Widening ingestion, retaining raw payloads, any durable-snapshot claim.",
        source_url=NFL_TERMS,
    ),
    dict(
        id="Q11", topic="Rewards and legality",
        question="Who can receive a reward, and under what rules?",
        known=("Reward tiers appear on project pages. No funded pool, no eligibility rules and no "
               "jurisdiction-specific legal review exist anywhere in the repository."),
        missing=("Funding source, eligibility, taxes, age and jurisdiction rules, operator permissions and "
                 "independent administration."),
        discover=("Keep rewards explicitly points-only until a dated funding commitment and a jurisdiction "
                  "review exist, then publish eligibility, disputes, data policy and payment terms."),
        blocked="Any funded competition, any payout.",
        source_url=NFL_PRIVACY,
    ),
    dict(
        id="Q12", topic="Site trust",
        question="Can a reader tell, for any number on the site, whether it is verified?",
        known=("This hub enforces one official source link per table row and leaves unconfirmable values "
               "blank. The dated repository audit records 1,538 source-domain flags across 69 pages "
               "elsewhere, mostly in hubs built on third-party extracts."),
        missing=("A single verification tier label applied to every published table across all hubs, and "
                 "removal or relabelling of rows that carry no official source."),
        discover=("Apply a per-row source rule repository-wide, mark each hub's data vintage, and publish "
                  "everything that fails the rule on the Flagged for Review page rather than deleting it."),
        blocked="Treating any site-wide number as verified.",
        source_url=INJ_W10,
    ),
]
