#!/usr/bin/env python3
"""Build a dependency-free, source-linked static research dashboard."""
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parents[1]
S = {
 'nfl': ('NFL Operations · tracking', 'https://operations.nfl.com/game-operations-logistics/technology/performance-tracking-data-next-gen-stats'),
 'passing': ('NFL · passing score', 'https://www.nfl.com/news/next-gen-stats-intro-to-passing-score-metric'),
 'injury': ('NFL · injury report', 'https://www.nfl.com/injuries/league/2025/reg1'),
 'stats': ('NFL · player statistics', 'https://www.nfl.com/players/justin-fields/stats/'),
 'weather': ('NWS · NOWData FAQ', 'https://www.weather.gov/climateservices/nowdatafaq'),
 'parlay': ('DraftKings · parlay rules', 'https://help.draftkings.com/hc/en-us/articles/4405235694739-What-is-a-parlay-bet-US'),
 'prop': ('DraftKings · prop bets', 'https://help.draftkings.com/hc/en-us/articles/4405232143507-What-is-a-prop-bet-US'),
 'sgp': ('DraftKings · SGP example', 'https://dknetwork.draftkings.com/2026/02/06/how-to-build-super-bowl-lx-same-game-parlay-draftkings/'),
 'leak': ('scikit-learn · leakage', 'https://scikit-learn.org/stable/common_pitfalls.html'),
 'score': ('scikit-learn · scoring', 'https://scikit-learn.org/stable/modules/model_evaluation.html'),
 'corr': ('NIST · correlation limits', 'https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/corrconf.htm'),
 'dep': ('NIST · dependence', 'https://www.itl.nist.gov/div898/possolo/TutorialWEBServer/TutorialMetrologists2011Nov09.xht'),
 'multiple': ('NIST · multiple comparisons', 'https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/onewayan.htm'),
}
NAV = [('index.html','Overview','01'),('strategies.html','Strategies','02'),('validation.html','Validation','03'),('correlations.html','Correlations','04'),('sources.html','Source library','05'),('flagged.html','Flagged for review','06')]
def source(keys):
    return ' · '.join(f'<a href="{escape(S[k][1], quote=True)}" target="_blank" rel="noopener noreferrer">{escape(S[k][0])} ↗</a>' for k in keys.split(','))
def table(headers, rows):
    head = ''.join('<th scope="col">'+escape(h)+'</th>' for h in headers) + '<th scope="col">Primary source</th>'
    body = ''.join('<tr>'+''.join('<td>'+cell+'</td>' for cell in row[:-1])+'<td class="source">'+source(row[-1])+'</td></tr>' for row in rows)
    return '<div class="table-wrap"><table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table></div>'
def pill(s, cls='neutral'): return f'<span class="pill {cls}">{s}</span>'
def block(title, subtitle, content, tag='RESEARCH NOTE'):
    return f'<section class="panel"><div class="panel-head"><div><span class="eyebrow">{tag}</span><h2>{title}</h2><p>{subtitle}</p></div></div>{content}</section>'

def layout(file, title, intro, content):
    nav=''.join(f'<a class="nav-link {"active" if file == href else ""}" href="{href}" {"aria-current=page" if file == href else ""}><span>{num}</span>{name}</a>' for href,name,num in NAV)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Source-linked research on originating NFL lines and validating strategy skill."><title>{escape(title)} | Fourth &amp; Signal</title><link rel="stylesheet" href="assets/style.css"><script src="assets/app.js" defer></script></head><body><a class="skip" href="#main">Skip to content</a><div class="app"><aside class="sidebar"><a class="brand" href="index.html"><span class="brand-icon">4<span>+</span></span><span>FOURTH <i>&amp;</i> SIGNAL<small>NFL RESEARCH LAB</small></span></a><div class="sidebar-label">WORKSPACE</div><nav aria-label="Main navigation">{nav}</nav><div class="sidebar-bottom"><span class="status-dot"></span><div><strong>Research mode</strong><small>No live recommendations</small></div></div></aside><div class="workspace"><header class="topbar"><div>RESEARCH / <span>{escape(title.upper())}</span></div><div class="top-right"><span class="live-dot"></span> SOURCE-LED ANALYSIS <span class="date">AS OF 01 NOV 2026</span></div></header><main id="main"><div class="page-heading"><div><div class="kicker"><span></span> NFL ANALYTICS / RESEARCH BRIEF</div><h1>{title}</h1><p>{intro}</p></div><a class="heading-link" href="flagged.html">View review queue <span>↗</span></a></div>{content}<footer><span>FOURTH &amp; SIGNAL <b> / </b> RESEARCH, NOT BETTING ADVICE</span><span>Built for careful decisions. No outcome is guaranteed.</span></footer></main></div></div></body></html>'''

strategies = [
 ('S01','Single · team spread / total','Use pre-game team efficiency, opponent strength and availability to model a score distribution; derive cover and push probabilities.','Compare to a timestamped executable line; test against a no-vig market baseline.','nfl,leak'),
 ('S02','Single · player prop','Model opportunity first (snaps, attempts or targets), then efficiency and participation; estimate the full outcome distribution.','Evaluate availability, push and void rules; calibrate by market and line.','passing,prop'),
 ('S03','Cross-game parlay','Combine separately modeled legs only after testing dependence and settlement rules. Price the joint event, not a story.','Do not assume independence across shared weather, slate or teams.','parlay,dep'),
 ('S04','Same-game prop combo','Jointly simulate team plays, pass attempts and receiver share for QB passing yards plus receiver yards.','Estimate dependence out of sample; compare fair joint price with the actual combined quote.','sgp,nfl'),
 ('S05','Game script combo','Jointly model team result, play volume and rushing attempts rather than multiplying marginal hit rates.','Stress-test alternate scripts; verify allowed selections and repricing rules.','sgp,parlay'),
]
gates=[
 ('01','Provenance &amp; timing','Every record has source URL, event ID, publication / capture time, odds and rules. Reject post-cutoff features.','Blocked · no historical quote archive','leak,injury'),
 ('02','Leakage-safe evaluation','Use rolling, chronological train / calibration / test windows; fit preprocessing and model selection inside training only. Keep a final season untouched.','Not run','leak'),
 ('03','Forecast quality','Compare Brier / log loss to a same-market no-vig baseline on identical events; inspect reliability and sample counts separately.','Not run','score'),
 ('04','Economic evidence','Evaluate net unit returns at captured prices, including push / void rules; compare matched benchmark and report game-clustered uncertainty.','Not run','parlay,corr'),
 ('05','Selection &amp; stability','Pre-register strategy family and threshold; adjust for multiple comparisons, report every trial, and test future seasons and market subgroups.','Not run','multiple,leak'),
 ('06','Release gate','Only rank a strategy after all prior gates pass and a pre-specified uncertainty criterion supports an edge. Abstain otherwise.','No strategy eligible','score,leak'),
]
corr=[
 ('QB passing yards / same-team receiver yards','Binary over indicators at the exact lines','', '','Not estimated · matched event data unavailable','sgp,corr'),
 ('Team win / team rushing yards','Binary win and over indicators','', '', 'Not estimated · matched event data unavailable','sgp,corr'),
 ('Player receiving yards / team total','Binary over indicators at the exact lines','', '', 'Not estimated · matched event data unavailable','sgp,corr'),
 ('Cross-game legs','Binary leg outcomes','', '', 'Not estimated · shared slate risks remain','dep,corr'),
]
flags=[
 ('F01','No verified point-in-time market archive','No executable historical prices, capture timestamps, or book / jurisdiction rule snapshots were supplied or acquired. No edge, CLV, ROI or fair line is published.','parlay,leak'),
 ('F02','No reproducible NFL training dataset','Official sites identify football data, but historical, point-in-time access and reuse rights have not been established. There is no ingestion, live feed or trained model.','nfl,stats'),
 ('F03','Correlations and skill are unmeasured','Matched historical prop outcomes and lines are absent; correlation, intervals, backtests, rankings and rewards cannot be verified.','corr,score'),
 ('F04','Archived injury page has misleading metadata','The NFL 2025/reg1 page title says Week 8, but its body says Week 1. The page also shows season records; do not assume these were known pregame.','injury,leak'),
 ('F05','Weather and settlement caveats','NOWData may contain preliminary observations; stadium conditions may differ. Parlay push rules do not automatically establish same-game rules.','weather,parlay'),
 ('F06','Competition and deployment','Leaderboard and rewards are proposed internal design, not a real competition or funded prize. Live availability, legality and permitted data reuse remain unverified.','score,parlay'),
]

home='''<section class="hero"><div><div class="hero-label"><span></span> THE RESEARCH BRIEF <span class="hero-num"> / 01</span></div><h2>Better signals.<br><em>Fewer assumptions.</em></h2><p>A framework for originating NFL lines, separating signal from noise, and putting every strategy through the same evidence-first gates.</p><div class="hero-actions"><a class="button primary" href="strategies.html">Explore strategies <span>↗</span></a><a class="button ghost" href="validation.html">See validation process <span>→</span></a></div></div><div class="hero-art" aria-hidden="true"><div class="field-line one"></div><div class="field-line two"></div><div class="field-line three"></div><div class="field-ball">✳</div><div class="art-caption">THE EDGE IS<br>IN THE EVIDENCE <span>↗</span></div></div></section>
<div class="metrics"><div class="metric"><span>STRATEGIES IN RESEARCH</span><strong>05</strong><small>Hypotheses, not recommendations</small></div><div class="metric"><span>PASSED VALIDATION</span><strong>00</strong><small>No backtests have been run</small></div><div class="metric"><span>VERIFIED CORRELATIONS</span><strong>—</strong><small>Historical pairs unavailable</small></div><div class="metric"><span>REVIEW ITEMS</span><strong>06</strong><small>Open limitations &amp; irregularities</small></div></div>
<div class="section-title"><div><span class="eyebrow">THE EXECUTIVE SUMMARY</span><h2>What matters now</h2></div><a href="sources.html">Browse all sources ↗</a></div>
<div class="summary-grid"><article><span class="card-number">01 / OPPORTUNITY</span><h3>Model the distribution,<br>not just the winner.</h3><p>Price single bets from game and player outcome distributions. For combinations, estimate a joint distribution and compare it with the actual offered price.</p><a href="strategies.html">Strategy library →</a></article><article><span class="card-number">02 / THE STANDARD</span><h3>Proof before<br>performance.</h3><p>Require point-in-time data, chronological holdouts, calibration, market benchmarks and uncertainty. A winning streak alone is not evidence of skill.</p><a href="validation.html">Validation gates →</a></article><article><span class="card-number">03 / THE REALITY</span><h3>Luck can be measured,<br>not removed.</h3><p>No strategy has passed: verified historical odds and matched outcomes are missing. Numbers, ranks and rewards remain blank until the evidence exists.</p><a href="flagged.html">Review the gaps →</a></article></div>'''
home+=block('Current research inventory','Proposed strategies are awaiting data and validation. Each source supports the topic, not a claim of profitability.',table(['ID','Strategy','Status'],[(x[0],x[1],pill('NOT VALIDATED','amber'),x[4]) for x in strategies]),'AT A GLANCE')

strategy_content=block('Candidate strategies','Five testable ideas, not proven edges. All features must be available before the decision cutoff.',table(['ID','Market','Signal & line construction','Required comparison'],strategies),'RESEARCH PIPELINE')
strategy_content+='''<section class="note"><span>01</span><div><h3>Line construction &amp; expected value</h3><p>For a binary no-push bet, a fair decimal price is 1 / p. At decimal odds d, expected net return per unit is p × d − 1. With win, loss and push probabilities, EV = p(win) × (d − 1) − p(loss), assuming a push refunds stake. For parlays, price the joint outcome and all settlement states; do not multiply marginal probabilities unless independence is justified. These are mathematical definitions, not verified market prices.</p></div></section>'''
validation_content=block('The six gates','All checks are proposed controls. “Not run” is not a pass; thresholds must be fixed before testing.',table(['Gate','Check','Acceptance standard','Status'],gates),'RELEASE FRAMEWORK')
validation_content+='''<section class="note"><span>02</span><div><h3>Leaderboard &amp; rewards design</h3><p>Freeze submissions and prices before kickoff. Rank only eligible strategies using a pre-registered paired out-of-sample improvement in proper score versus the same market baseline; show confidence intervals and matched sample size. Use net ROI and closing-line comparison as secondary diagnostics, not as proof. Equal event coverage or matched comparisons prevent selection bias; report abstentions and all trials. Allocate any hypothetical rewards only to strategies passing all gates; ties and uncertainty should produce no winner. There is no funded competition or active leaderboard.</p><p>Use a game- or week-block bootstrap to reflect clustered outcomes; adjust comparisons across strategy families and preserve a final untouched test period. Selection and repeated testing still make false discoveries possible. No method eliminates luck.</p></div></section>'''
correlation_content=block('Pairwise dependence register','Blank cells are intentionally blank: no measured value or confidence interval has been established.',table(['Pair','Definition','Correlation','95% interval','Status'],corr),'MEASUREMENT PENDING')
correlation_content+='''<section class="note"><span>03</span><div><h3>How to estimate it</h3><p>Match the same event, time, player, line and settlement definition; exclude or separately model voids and pushes. For paired binary wins A and B, estimate pA, pB and pAB, then φ = (pAB − pA pB) / √[pA(1−pA)pB(1−pB)]. It is undefined when a marginal is constant. Estimate uncertainty with a game-clustered bootstrap and report sample size, date range and subgroup stability. For two binary legs, pAB can be recovered from φ and the marginals, subject to valid probability bounds. More than two legs require a joint model; pairwise correlations alone are insufficient. Zero correlation does not imply independence.</p></div></section>'''
sources_rows=[
 ('NFL tracking','League describes tracking and examples including completion probability and expected rushing yards.','Possible contextual features; accessibility and predictive value remain unverified.','nfl'),
 ('NFL passing score','NFL describes completion probability, expected yards after catch and expected points models.','Candidates for lagged features, not an independently validated edge.','passing'),
 ('NFL injury archive','Official player practice and game status reports.','Archive is not a timestamped historical snapshot; Week 1 title mismatch flagged.','injury'),
 ('NFL player stats','Official player season totals and recent game statistics.','Use finalized outcomes only after event; check corrections and data rights.','stats'),
 ('National Weather Service','NOWData combines archived and preliminary holdings; NCEI supplies finalized data.','Use forecast available at decision time, not observed future weather.','weather'),
 ('DraftKings rules','Describes traditional parlay settlement and directs readers to sport-specific SGP rules.','Snapshot the actual operator, jurisdiction and settlement rules.','parlay'),
 ('scikit-learn documentation','Documents leakage and proper scoring metrics.','Supports validation design, not any NFL performance conclusion.','leak,score'),
 ('NIST statistical reference','Describes correlation intervals and multiple-comparison adjustment.','Use uncertainty methods appropriate to dependent game-level data.','corr,multiple'),
]
sources_content=block('Primary-source library','Reviewed 01 Nov 2026. Sources are official publishers for their respective subject matter; links are for manual review.',table(['Source','Verified finding','Application / limitation'],sources_rows),'EVIDENCE REGISTER')
flag_content=block('Open review queue','These items do not prevent publication of the research site; they do prevent claims of validated performance.',table(['ID','Irregularity / gap','Impact'],flags),'TRANSPARENCY LOG')
flag_content+='''<section class="note"><span>!</span><div><h3>What this site does not do</h3><p>It does not fetch live odds, place bets, calculate real-world correlations, train models, run historical backtests, award prizes or guarantee profit. It is a research specification and a source-linked inventory, not a functioning production betting system. No real values were filled in from assumptions.</p></div></section>'''
pages={
 'index.html':('Overview','A clear view of the research, the evidence and what comes next.',home),
 'strategies.html':('Strategy library','Candidate approaches for singles, parlays and player prop combinations.',strategy_content),
 'validation.html':('Validation gates','A consistent, conservative standard for separating signal from noise.',validation_content),
 'correlations.html':('Correlation research','Measure dependence before pricing combinations. No invented coefficients.',correlation_content),
 'sources.html':('Source library','A traceable collection of official sources and how they inform the work.',sources_content),
 'flagged.html':('Flagged for review','The gaps, limitations and irregularities that remain visible by design.',flag_content),
}
for file, (title,intro,content) in pages.items(): (ROOT / file).write_text(layout(file,title,intro,content),encoding='utf-8')
print(f'Built {len(pages)} pages.')
