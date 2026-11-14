"""Official-source transcriptions, with the URL each figure was read from.

Every dict in this module is a *transcription* of a page that was actually opened and read on
the retrieval date recorded in ``RETRIEVED``. A transcription is not a computation: the values
below are copied from the page and are checked against the committed data by
``analysis.py``, which reports every difference instead of smoothing it over.

Nothing in this file is inferred. Where a page did not publish a value, the key is absent and
the dependent table cell is blank with an ``unverified`` status.

Source pages read for this build
--------------------------------
2026-11-14  https://www.nfl.com/standings/division/2026/REG          (W L T PCT PF PA)
2026-11-14  https://www.nfl.com/standings/division/2025/REG          (W L T PCT PF PA)
2026-11-14  https://www.nfl.com/standings/division/2020/REG          (W L T PCT PF PA)
2026-11-14  https://www.nfl.com/scores/2026/week-8                   (final scores)
2026-11-14  https://www.nfl.com/scores/2026/week-9                   (final scores)
2026-11-14  https://www.nfl.com/scores/2026/week-10                  (final scores)
2026-11-14  https://www.nfl.com/stats/player-stats/category/passing/2026/reg/all/passingyards/desc
2026-11-14  https://www.nfl.com/stats/player-stats/category/receiving/2026/reg/all/receivingyards/desc
2026-11-14  https://www.nfl.com/injuries/                            (Week 10 report)
2026-11-14  https://www.nfl.com/injuries/league/2026/reg9            (Week 9 report)
2026-11-14  https://www.nfl.com/teams/arizona-cardinals/roster       (roster has no depth rank)
"""

RETRIEVED = "2026-11-14"

URL = {
    "standings_2026": "https://www.nfl.com/standings/division/2026/REG",
    "standings_2025": "https://www.nfl.com/standings/division/2025/REG",
    "standings_2020": "https://www.nfl.com/standings/division/2020/REG",
    "scores_w8": "https://www.nfl.com/scores/2026/week-8",
    "scores_w9": "https://www.nfl.com/scores/2026/week-9",
    "scores_w10": "https://www.nfl.com/scores/2026/week-10",
    "passing_2026": "https://www.nfl.com/stats/player-stats/category/passing/2026/reg/all/passingyards/desc",
    "receiving_2026": "https://www.nfl.com/stats/player-stats/category/receiving/2026/reg/all/receivingyards/desc",
    "injuries_w10": "https://www.nfl.com/injuries/",
    "injuries_w9": "https://www.nfl.com/injuries/league/2026/reg9",
    "roster_ari": "https://www.nfl.com/teams/arizona-cardinals/roster",
    "schedule_2026": "https://media.nfl.com/football-information/2026/news/2026-nfl-schedule-announced",
}

# --------------------------------------------------------------------------- standings
# (wins, losses, ties, points_for, points_against) exactly as printed in the W/L/T/PF/PA columns.
STANDINGS = {
    2026: {
        "BUF": (7, 1, 0, 256, 187), "NE": (5, 4, 0, 211, 207), "NYJ": (2, 7, 0, 182, 223),
        "MIA": (1, 7, 0, 126, 200), "PIT": (6, 2, 0, 180, 144), "CIN": (6, 2, 0, 240, 175),
        "CLE": (5, 4, 0, 161, 196), "BAL": (4, 5, 0, 189, 236), "JAX": (6, 2, 0, 229, 121),
        "HOU": (3, 5, 0, 209, 192), "IND": (2, 7, 0, 184, 249), "TEN": (1, 7, 0, 144, 199),
        "DEN": (7, 2, 0, 198, 186), "KC": (6, 2, 0, 202, 143), "LV": (4, 5, 0, 238, 268),
        "LAC": (0, 8, 0, 121, 219), "NYG": (5, 3, 1, 203, 196), "DAL": (4, 5, 0, 246, 236),
        "WAS": (3, 5, 1, 196, 223), "PHI": (2, 7, 0, 148, 221), "CHI": (7, 2, 0, 241, 184),
        "DET": (6, 2, 0, 222, 189), "MIN": (6, 2, 0, 146, 116), "GB": (6, 3, 0, 216, 191),
        "CAR": (3, 5, 0, 199, 219), "NO": (3, 5, 0, 185, 216), "TB": (3, 6, 0, 202, 178),
        "ATL": (3, 6, 0, 188, 223), "SF": (7, 1, 0, 235, 156), "SEA": (5, 4, 0, 202, 162),
        "LA": (5, 4, 0, 214, 181), "ARI": (3, 6, 0, 178, 255),
    },
    2025: {
        "NE": (14, 3, 0, 490, 320), "BUF": (12, 5, 0, 481, 365), "MIA": (7, 10, 0, 347, 424),
        "NYJ": (3, 14, 0, 300, 503), "PIT": (10, 7, 0, 397, 387), "BAL": (8, 9, 0, 424, 398),
        "CIN": (6, 11, 0, 414, 492), "CLE": (5, 12, 0, 279, 379), "JAX": (13, 4, 0, 474, 336),
        "HOU": (12, 5, 0, 404, 295), "IND": (8, 9, 0, 466, 412), "TEN": (3, 14, 0, 284, 478),
        "DEN": (14, 3, 0, 401, 311), "LAC": (11, 6, 0, 368, 340), "KC": (6, 11, 0, 362, 328),
        "LV": (3, 14, 0, 241, 432), "PHI": (11, 6, 0, 379, 325), "DAL": (7, 9, 1, 471, 511),
        "WAS": (5, 12, 0, 356, 451), "NYG": (4, 13, 0, 381, 439), "CHI": (11, 6, 0, 441, 415),
        "GB": (9, 7, 1, 391, 360), "MIN": (9, 8, 0, 344, 333), "DET": (9, 8, 0, 481, 413),
        "CAR": (8, 9, 0, 311, 380), "TB": (8, 9, 0, 380, 411), "ATL": (8, 9, 0, 353, 401),
        "NO": (6, 11, 0, 306, 383), "SEA": (14, 3, 0, 483, 292), "LA": (12, 5, 0, 518, 346),
        "SF": (12, 5, 0, 437, 371), "ARI": (3, 14, 0, 355, 488),
    },
    2020: {
        "BUF": (13, 3, 0, 501, 375), "MIA": (10, 6, 0, 404, 338), "NE": (7, 9, 0, 326, 353),
        "NYJ": (2, 14, 0, 243, 457), "PIT": (12, 4, 0, 416, 312), "BAL": (11, 5, 0, 468, 303),
        "CLE": (11, 5, 0, 408, 419), "CIN": (4, 11, 1, 311, 424), "TEN": (11, 5, 0, 491, 439),
        "IND": (11, 5, 0, 451, 362), "HOU": (4, 12, 0, 384, 464), "JAX": (1, 15, 0, 306, 492),
        "KC": (14, 2, 0, 473, 362), "LV": (8, 8, 0, 434, 478), "LAC": (7, 9, 0, 384, 426),
        "DEN": (5, 11, 0, 323, 446), "WAS": (7, 9, 0, 335, 329), "NYG": (6, 10, 0, 280, 357),
        "DAL": (6, 10, 0, 395, 473), "PHI": (4, 11, 1, 334, 418), "GB": (13, 3, 0, 509, 369),
        "CHI": (8, 8, 0, 372, 370), "MIN": (7, 9, 0, 430, 475), "DET": (5, 11, 0, 377, 519),
        "NO": (12, 4, 0, 482, 337), "TB": (11, 5, 0, 492, 355), "CAR": (5, 11, 0, 350, 402),
        "ATL": (4, 12, 0, 396, 414), "SEA": (12, 4, 0, 459, 371), "LA": (10, 6, 0, 372, 296),
        "ARI": (8, 8, 0, 410, 367), "SF": (6, 10, 0, 376, 390),
    },
}

# --------------------------------------------------------------------------- final scores
# (away_points, home_points) per ``AWAY@HOME`` key, plus the official game page for that match.
# (away_points, home_points). Every game below was read off the page named in SCORES_URL.
# Week 8 byes were HOU, NO, NYG and SF, so that week lists 14 games; week 9 lists 15 and its byes
# were PIT and TEN; week 10 was in progress when read and only one game had gone final.
SCORES = {
    8: {
        "CAR@GB": (19, 27), "BAL@BUF": (10, 36), "TEN@CIN": (36, 43), "ARI@DAL": (33, 30),
        "MIN@DET": (15, 19), "IND@JAX": (7, 42), "LV@NYJ": (38, 33), "CLE@PIT": (6, 27),
        "ATL@TB": (0, 16), "LAC@LA": (9, 24), "KC@DEN": (24, 28), "NE@MIA": (24, 19),
        "PHI@WAS": (10, 27), "CHI@SEA": (34, 17),
    },
    9: {
        "JAX@BAL": (33, 10), "CIN@ATL": (34, 17), "DEN@CAR": (26, 21), "DAL@IND": (27, 23),
        "NYJ@KC": (12, 35), "DET@MIA": (19, 9), "CLE@NO": (22, 23), "NYG@PHI": (19, 11),
        "LA@WAS": (20, 13), "HOU@LAC": (44, 22), "LV@SF": (17, 38), "GB@NE": (45, 27),
        "ARI@SEA": (3, 17), "TB@CHI": (24, 27), "BUF@MIN": (23, 6),
    },
    10: {"WAS@NYG": (24, 21)},
}
SCORES_URL = {8: URL["scores_w8"], 9: URL["scores_w9"], 10: URL["scores_w10"]}
SCORES_NOTE = {
    8: "14 games; byes HOU, NO, NYG, SF.",
    9: "15 games; byes PIT, TEN.",
    10: "Only the Thursday game (WAS at NYG) was final when the page was read.",
}
# Weeks whose official final scores were transcribed. Anything outside this list is not claimed.
SCORES_VERIFIED_WEEKS = [8, 9, 10]

# Official player leaders (2026 regular season, through Week 10 as published on 2026-11-14).
PASSING_2026 = {
    "Jordan Love": (2618, 19), "Joe Burrow": (2386, 23), "Dak Prescott": (2381, 16),
    "Matthew Stafford": (2374, 16), "Kirk Cousins": (2340, 20), "Drake Maye": (2282, 18),
    "C.J. Stroud": (2251, 16), "Bryce Young": (2197, 16), "Jared Goff": (2134, 15),
    "Geno Smith": (2078, 12), "Patrick Mahomes": (2037, 14), "Josh Allen": (2027, 12),
    "Tyler Shough": (1986, 14), "Brock Purdy": (1980, 17), "Trevor Lawrence": (1932, 18),
    "Aaron Rodgers": (1871, 13), "Deshaun Watson": (1806, 7), "Bo Nix": (1730, 11),
    "Daniel Jones": (1722, 6), "Jacoby Brissett": (1719, 10), "Justin Herbert": (1591, 6),
    "Caleb Williams": (1546, 8), "Jayden Daniels": (1499, 10), "Cam Ward": (1483, 6),
    "Sam Darnold": (1478, 10),
}
RECEIVING_2026 = {
    "Jaxon Smith-Njigba": 1036, "CeeDee Lamb": 904, "Christian Watson": 879,
    "Matthew Golden": 783, "Tee Higgins": 758, "Chris Olave": 734, "Puka Nacua": 715,
    "Drake London": 692, "Malik Nabers": 692, "Brock Bowers": 658,
    "Amon-Ra St. Brown": 657, "Ja'Marr Chase": 647, "Luther Burden III": 644,
    "Tetairoa McMillan": 625, "Zay Flowers": 614, "Trey McBride": 598,
}

# --------------------------------------------------------------------------- official depth evidence
# What the official injury report actually publishes: per player, position, injury, practice
# status and game status. It does *not* publish a depth-chart rank. These rows are the exact
# strings read from the official page and are used to test the depth claim, not asserted as depth.
INJURY_EVIDENCE = [
    {"week": 9, "team": "BAL", "player": "Lamar Jackson", "position": "QB",
     "injury": "Thumb", "practice": "Did Not Participate In Practice", "game_status": "Out",
     "url": URL["injuries_w9"]},
    {"week": 9, "team": "BAL", "player": "Tyler Huntley", "position": "QB",
     "injury": "Toe", "practice": "Did Not Participate In Practice", "game_status": "Out",
     "url": URL["injuries_w9"]},
    {"week": 9, "team": "BAL", "player": "Joe Fagnano", "position": "QB",
     "injury": "", "practice": "Full Participation in Practice", "game_status": "",
     "url": URL["injuries_w9"]},
    {"week": 10, "team": "DET", "player": "Kerby Joseph", "position": "S",
     "injury": "Knee", "practice": "Did Not Participate In Practice", "game_status": "Out",
     "url": URL["injuries_w10"]},
    {"week": 10, "team": "DET", "player": "D.J. Reed", "position": "CB",
     "injury": "Hip", "practice": "Did Not Participate In Practice", "game_status": "Out",
     "url": URL["injuries_w10"]},
    {"week": 10, "team": "DET", "player": "Cade Mays", "position": "C",
     "injury": "Ankle", "practice": "Did Not Participate In Practice", "game_status": "Out",
     "url": URL["injuries_w10"]},
    {"week": 10, "team": "NE", "player": "Carlton Davis III", "position": "CB",
     "injury": "Knee", "practice": "Did Not Participate In Practice", "game_status": "Out",
     "url": URL["injuries_w10"]},
    {"week": 10, "team": "NE", "player": "Ben Brown", "position": "C",
     "injury": "Knee", "practice": "Did Not Participate In Practice", "game_status": "Out",
     "url": URL["injuries_w10"]},
    {"week": 10, "team": "NE", "player": "TreVeyon Henderson", "position": "RB",
     "injury": "Illness", "practice": "Did Not Participate In Practice", "game_status": "Out",
     "url": URL["injuries_w10"]},
    {"week": 10, "team": "WAS", "player": "Lucas Patrick", "position": "C",
     "injury": "Concussion", "practice": "Did Not Participate In Practice", "game_status": "Out",
     "url": URL["injuries_w10"]},
]

# Statements about what the pages do and do not contain, each tied to the page that was read.
PAGE_FINDINGS = [
    {"claim": "The official team roster page lists players with position and roster status (e.g. ACT).",
     "verdict": "confirmed", "url": URL["roster_ari"],
     "detail": "Arizona Cardinals roster returns players with position and ACT status."},
    {"claim": "The official team roster page publishes a depth-chart rank (1st/2nd/3rd string).",
     "verdict": "not confirmed", "url": URL["roster_ari"],
     "detail": "No depth ordinal appears in the roster table; only position, status, height, weight, "
               "experience and college."},
    {"claim": "The official injury report publishes, per player, position, injury, practice and game status.",
     "verdict": "confirmed", "url": URL["injuries_w10"],
     "detail": "Columns: Player, Position, Injuries, Practice Status, Game Status."},
    {"claim": "The official injury report publishes depth-chart order.",
     "verdict": "not confirmed", "url": URL["injuries_w10"],
     "detail": "No depth column exists on the page."},
    {"claim": "The NFL publishes official game odds (opening or closing prices) as a data feed.",
     "verdict": "not confirmed", "url": URL["scores_w9"],
     "detail": "The scores page publishes final scores and a game link, not prices. No official "
               "price feed was located; prices in this repository are third-party."},
    {"claim": "The Week 9 injury report page's own heading says 'WEEK 9'.",
     "verdict": "confirmed", "url": URL["injuries_w9"],
     "detail": "In-page heading reads 'Injuries - WEEK 9', the document title says Week 10, and the "
               "week-10 page is the default. The mismatch is flagged."},
]

UPSTREAM = {
    "initial_lines": {
        "url": "https://github.com/nflverse/nfldata/blob/a270278f3ac4e937295fe6a27814b3c4a2b62645/data/initial_lines.csv",
        "raw": "https://api.github.com/repos/nflverse/nfldata/contents/data/initial_lines.csv?ref=a270278f3ac4e937295fe6a27814b3c4a2b62645",
        "commit": "a270278f3ac4e937295fe6a27814b3c4a2b62645",
        "publisher": "nflverse/nfldata (third party, not the league)",
    },
    "closing_lines": {
        "url": "https://github.com/nflverse/nfldata/blob/a270278f3ac4e937295fe6a27814b3c4a2b62645/data/closing_lines.csv",
        "raw": "https://api.github.com/repos/nflverse/nfldata/contents/data/closing_lines.csv?ref=a270278f3ac4e937295fe6a27814b3c4a2b62645",
        "commit": "a270278f3ac4e937295fe6a27814b3c4a2b62645",
        "publisher": "nflverse/nfldata (third party, not the league)",
    },
    "games": {
        "url": "https://github.com/nflverse/nfldata/blob/a270278f3ac4e937295fe6a27814b3c4a2b62645/data/games.csv",
        "publisher": "nflverse/nfldata (third party, not the league)",
        "note": "Committed to this repository as data/derived/games.csv.gz and hashed in "
                "data/derived/manifest.json and data/PROVENANCE.md.",
    },
}
