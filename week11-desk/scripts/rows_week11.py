#!/usr/bin/env python3
"""Week 11 (2026) official injury-report transcription — one tuple per published row.

TRANSCRIPTION POLICY (owner rule: never infer, never fill in)
-------------------------------------------------------------
* Every tuple below was read first-hand from
  https://www.nfl.com/injuries/league/2026/reg11 at READ_AT_UTC using the platform
  page-retrieval tool, across 8 chunks (0-7). Nothing is derived from another page,
  from a previous week, from jersey order, from salary or from experience.
* `practice` and `game` store the page's own strings, verbatim. Where the page prints an
  empty practice-status or game-status cell, the field is the empty string '', exactly as
  published. It is never turned into "Healthy" or "Probable" — the NFL retired "Probable"
  and an empty cell is not evidence of availability.
* `injury` is the page's "Injuries" column verbatim, including multi-injury strings such as
  "Foot, Illness".
* A club printed with the literal block "No Injuries Reported" is recorded in that form and
  contributes zero player rows (CIN and WAS, Monday 2026-11-23). Zero rows for such a club is
  the page's statement, not an omission by this transcription.
* Rows are ordered as the page prints them, club by club, so the register can be diffed
  against the page in the same order.

Schema per tuple: (club, player, position, injury, practice, game)
"""
from __future__ import annotations

# --- provenance -----------------------------------------------------------------------
SOURCE_URL = "https://www.nfl.com/injuries/league/2026/reg11"
SOURCE_TITLE = "Official NFL Injury Report for Players - Week 11 of the 2026 Season"
SEASON, WEEK = 2026, 11
# Clock time of this session's read. Recorded to the minute, UTC, per the brief's
# "store every injury-hub read with its clock time" requirement. Two reads were made in
# this session; READ_AT_UTC is the read the rows below were transcribed from.
READ_AT_UTC = "2026-11-19T19:54:00Z"
READS = [
    # (started_utc, finished_utc, chunks, note)
    ("2026-11-19T19:44:00Z", "2026-11-19T19:52:00Z", "0-7",
     "full read, all 8 chunks, row-by-row transcription at read 1"),
    ("2026-11-19T19:53:30Z", "2026-11-19T19:54:33Z", "0",
     "second read of chunk 0 to confirm the Colts/Texans block and the page title "
     "(Week 11, 2026) after the Week 10 -> Week 11 changeover"),
]

# Page-level strings observed on the page, recorded once:
PAGE_HEADING = "Injuries - WEEK 11"
NO_INJURIES_BLOCK = "No Injuries Reported"

# Game slots exactly as the page groups them. The page prints a weekday date header and,
# for each fixture, the two clubs with counts. These headers are the page's, not derived.
GAME_SLOTS = [
    ("THURSDAY, NOVEMBER 19TH", "8:15 PM EST", "Prime Video", "IND", "HOU"),
    ("SUNDAY, NOVEMBER 22ND", "1:00 PM EST", "CBS", "PIT", "PHI"),
    ("SUNDAY, NOVEMBER 22ND", "1:00 PM EST", "CBS", "AZ", "KC"),
    ("SUNDAY, NOVEMBER 22ND", "1:00 PM EST", "FOX", "BAL", "CAR"),
    ("SUNDAY, NOVEMBER 22ND", "1:00 PM EST", "FOX", "TB", "DET"),
    ("SUNDAY, NOVEMBER 22ND", "1:00 PM EST", "CBS", "MIA", "BUF"),
    ("SUNDAY, NOVEMBER 22ND", "1:00 PM EST", "FOX", "TEN", "DAL"),
    ("SUNDAY, NOVEMBER 22ND", "1:00 PM EST", "FOX", "NO", "CHI"),
    ("SUNDAY, NOVEMBER 22ND", "4:05 PM EST", "FOX", "NYJ", "LAC"),
    ("SUNDAY, NOVEMBER 22ND", "4:25 PM EST", "CBS", "JAX", "NYG"),
    ("SUNDAY, NOVEMBER 22ND", "4:25 PM EST", "CBS", "LV", "DEN"),
    ("SUNDAY, NOVEMBER 22ND", "8:20 PM EST", "NBC", "MIN", "SF"),
    ("MONDAY, NOVEMBER 23RD", "8:15 PM EST", "ESPN", "CIN", "WAS"),
]

# Club display names exactly as the page's table headers print them.
CLUB_LABEL = {
    "IND": "Colts", "HOU": "Texans", "PIT": "Steelers", "PHI": "Eagles",
    "AZ": "Cardinals", "KC": "Chiefs", "BAL": "Ravens", "CAR": "Panthers",
    "TB": "Buccaneers", "DET": "Lions", "MIA": "Dolphins", "BUF": "Bills",
    "TEN": "Titans", "DAL": "Cowboys", "NO": "Saints", "CHI": "Bears",
    "NYJ": "Jets", "LAC": "Chargers", "JAX": "Jaguars", "NYG": "Giants",
    "LV": "Raiders", "DEN": "Broncos", "MIN": "Vikings", "SF": "49ers",
    "CIN": "Bengals", "WAS": "Commanders",
}

DNP = "Did Not Participate In Practice"
LP = "Limited Participation in Practice"
FP = "Full Participation in Practice"

# ---------------------------------------------------------------------------------------
# THE REGISTER. Order = page order. (club, player, position, injury, practice, game)
# ---------------------------------------------------------------------------------------
ROWS: list[tuple[str, str, str, str, str, str]] = [
    # ----- IND @ HOU, Thu Nov 19 8:15 PM EST, Prime Video -------------------------------
    ("IND", "Jaylon Carlies", "LB", "", DNP, ""),
    ("IND", "Sauce Gardner", "CB", "Calf", DNP, "Questionable"),
    ("IND", "Anthony Gould", "WR", "Toe", FP, "Questionable"),
    ("IND", "Charlie Heck", "T", "", DNP, ""),
    ("IND", "Will Mallory", "TE", "Hamstring", DNP, "Out"),
    ("IND", "Bernhard Raimann", "T", "Concussion", DNP, "Out"),
    ("IND", "Luke Rhodes", "LS", "Hamstring", LP, "Questionable"),
    ("IND", "Jerry Tillery", "DT", "Calf", DNP, "Out"),
    ("IND", "Jalen Travis", "T", "Knee", DNP, "Out"),
    ("IND", "Dalton Tucker", "G", "", FP, ""),
    ("IND", "Charvarius Ward", "CB", "Knee", DNP, "Out"),
    ("HOU", "Azeez Al-Shaair", "LB", "", DNP, ""),
    ("HOU", "Reed Blankenship", "S", "", FP, ""),
    ("HOU", "Tank Dell", "WR", "", FP, ""),
    ("HOU", "Blake Fisher", "T", "", FP, ""),
    ("HOU", "Marvin Harrison Jr.", "WR", "Hamstring", DNP, "Out"),
    ("HOU", "Jacob Hummel", "LB", "Groin", FP, "Questionable"),
    ("HOU", "Danielle Hunter", "DE", "Hamstring", DNP, "Out"),
    ("HOU", "Brevin Jordan", "TE", "Foot, Illness", DNP, "Out"),
    ("HOU", "Kamari Lassiter", "CB", "", FP, ""),
    ("HOU", "Woody Marks", "RB", "Concussion", DNP, "Out"),
    ("HOU", "David Montgomery", "RB", "", FP, ""),
    ("HOU", "Febechi Nwaiwu", "G", "", FP, ""),
    ("HOU", "Keylan Rutledge", "G", "", FP, ""),
    ("HOU", "Jaylin Smith", "CB", "Hamstring", FP, "Questionable"),
    ("HOU", "Wyatt Teller", "G", "Back", FP, "Questionable"),
    # ----- PIT @ PHI, Sun Nov 22 1:00 PM EST, CBS ---------------------------------------
    ("PIT", "Gennings Dunker", "G", "", FP, ""),
    ("PIT", "DeShon Elliott", "S", "", LP, ""),
    ("PIT", "Nick Herbig", "LB", "", DNP, ""),
    ("PIT", "Cameron Heyward", "DT", "", DNP, ""),
    ("PIT", "Michael Pittman", "WR", "", LP, ""),
    ("PIT", "Patrick Queen", "LB", "", LP, ""),
    ("PIT", "Jalen Ramsey", "CB", "", DNP, ""),
    ("PIT", "Darnell Washington", "TE", "", DNP, ""),
    ("PIT", "T.J. Watt", "LB", "", DNP, ""),
    ("PIT", "Roman Wilson", "WR", "", FP, ""),
    ("PHI", "Saquon Barkley", "RB", "", FP, ""),
    ("PHI", "Zack Baun", "LB", "", DNP, ""),
    ("PHI", "Jihaad Campbell", "LB", "", FP, ""),
    ("PHI", "Michael Carter II", "CB", "", LP, ""),
    ("PHI", "Britain Covey", "WR", "", LP, ""),
    ("PHI", "Jonathan Greenard", "LB", "", FP, ""),
    ("PHI", "Jalyx Hunt", "LB", "", FP, ""),
    ("PHI", "Jonathan Jones", "CB", "", LP, ""),
    ("PHI", "Tanner McKee", "QB", "", FP, ""),
    ("PHI", "Smael Mondon Jr.", "LB", "", FP, ""),
    ("PHI", "Andrew Mukuba", "S", "", FP, ""),
    ("PHI", "Will Shipley", "RB", "", LP, ""),
    ("PHI", "DeVonta Smith", "WR", "", LP, ""),
    ("PHI", "Nolan Smith", "LB", "", LP, ""),
    ("PHI", "Dontayvion Wicks", "WR", "", LP, ""),
    # ----- AZ @ KC, Sun Nov 22 1:00 PM EST, CBS -----------------------------------------
    ("AZ", "Budda Baker", "S", "", DNP, ""),
    ("AZ", "Zachary Carter", "DT", "", FP, ""),
    ("AZ", "Hjalte Froholdt", "C", "", LP, ""),
    ("AZ", "Jon Gaines II", "G", "", LP, ""),
    ("AZ", "Roy Lopez", "DT", "", LP, ""),
    ("AZ", "Max Melton", "CB", "", LP, ""),
    ("AZ", "Walter Nolen", "DT", "", DNP, ""),
    ("AZ", "Darius Robinson", "DT", "", FP, ""),
    ("AZ", "Isaac Seumalo", "G", "", DNP, ""),
    ("AZ", "Josh Sweat", "LB", "", DNP, ""),
    ("AZ", "Jayden Williams", "T", "", LP, ""),
    ("AZ", "Mack Wilson", "LB", "", DNP, ""),
    ("KC", "Jeffrey Bassa", "LB", "", FP, ""),
    ("KC", "Nick Bolton", "LB", "", LP, ""),
    ("KC", "Jadon Canady", "CB", "", FP, ""),
    ("KC", "Mansoor Delane", "CB", "", FP, ""),
    ("KC", "Justin Fields", "QB", "", FP, ""),
    ("KC", "Alohi Gilman", "S", "", FP, ""),
    ("KC", "Travis Kelce", "TE", "", FP, ""),
    ("KC", "Patrick Mahomes", "QB", "", FP, ""),
    ("KC", "Jaylon Moore", "T", "", DNP, ""),
    ("KC", "Omarr Norman-Lott", "DT", "", LP, ""),
    ("KC", "Jaydn Ott", "RB", "", FP, ""),
    ("KC", "Rashee Rice", "WR", "", FP, ""),
    ("KC", "Trey Smith", "G", "", DNP, ""),
    ("KC", "Kenneth Walker III", "RB", "", DNP, ""),
    ("KC", "Peter Woods", "DT", "", FP, ""),
    # ----- BAL @ CAR, Sun Nov 22 1:00 PM EST, FOX ---------------------------------------
    ("BAL", "Mike Green", "LB", "", FP, ""),
    ("BAL", "Jaylinn Hawkins", "S", "", LP, ""),
    ("BAL", "Matthew Hibner", "TE", "", FP, ""),
    ("BAL", "Olaivavega Ioane", "G", "", LP, ""),
    ("BAL", "Nnamdi Madubuike", "DT", "", DNP, ""),
    ("BAL", "Adam Randall", "RB", "", FP, ""),
    ("CAR", "Jonathon Brooks", "RB", "", FP, ""),
    ("CAR", "Brady Christensen", "G", "", FP, ""),
    ("CAR", "Feleipe Franks", "TE", "", FP, ""),
    ("CAR", "Trevis Gipson", "LB", "", LP, ""),
    ("CAR", "Chuba Hubbard", "RB", "", DNP, ""),
    ("CAR", "Mike Jackson", "CB", "", FP, ""),
    ("CAR", "Jackson Kuwatch", "LB", "", FP, ""),
    ("CAR", "Will Lee III", "CB", "", FP, ""),
    ("CAR", "Bobby Okereke", "LB", "", DNP, ""),
    ("CAR", "Isaiah Simmons", "S", "", DNP, ""),
    ("CAR", "Tommy Tremble", "TE", "", DNP, ""),
    ("CAR", "Darren Waller", "TE", "", DNP, ""),
    ("CAR", "Bryce Young", "QB", "", FP, ""),
    # ----- TB @ DET, Sun Nov 22 1:00 PM EST, FOX ----------------------------------------
    ("TB", "Yaya Diaby", "LB", "", LP, ""),
    ("TB", "Josh Hayes", "CB", "", FP, ""),
    ("TB", "Baker Mayfield", "QB", "", DNP, ""),
    ("TB", "Cade Otton", "TE", "", FP, ""),
    ("TB", "Antoine Winfield Jr.", "S", "", DNP, ""),
    ("TB", "Tristan Wirfs", "T", "", FP, ""),
    ("DET", "Joe Bachie", "LB", "", LP, ""),
    ("DET", "Khalil Dorsey", "CB", "", LP, ""),
    ("DET", "Kerby Joseph", "S", "", FP, ""),
    ("DET", "Tyler Lacy", "DE", "", LP, ""),
    ("DET", "Cade Mays", "C", "", DNP, ""),
    ("DET", "Ennis Rakestraw Jr.", "CB", "", LP, ""),
    ("DET", "D.J. Reed", "CB", "", LP, ""),
    ("DET", "Sione Vaki", "RB", "", LP, ""),
    # ----- MIA @ BUF, Sun Nov 22 1:00 PM EST, CBS ---------------------------------------
    ("MIA", "Tucker Addington", "LS", "", LP, ""),
    ("MIA", "Darrell Baker Jr.", "CB", "", FP, ""),
    ("MIA", "Chris Bell", "WR", "", LP, ""),
    ("MIA", "Julius Brents", "CB", "", LP, ""),
    ("MIA", "Aaron Brewer", "C", "", DNP, ""),
    ("MIA", "Caleb Douglas", "WR", "", LP, ""),
    ("MIA", "Andrew Meyer", "C", "", LP, ""),
    ("MIA", "Bradley Pinion", "P", "", DNP, ""),
    ("MIA", "Jaylin Simpson", "CB", "", DNP, ""),
    ("MIA", "Dante Trader Jr.", "S", "", DNP, ""),
    ("MIA", "Jared Wayne", "WR", "", DNP, ""),
    ("BUF", "Christian Benford", "CB", "", DNP, ""),
    ("BUF", "Cole Bishop", "S", "", LP, ""),
    ("BUF", "Keon Coleman", "WR", "", FP, ""),
    ("BUF", "Ray Davis", "RB", "", LP, ""),
    ("BUF", "Dee Alford", "CB", "", DNP, ""),
    ("BUF", "Damar Hamlin", "S", "", LP, ""),
    ("BUF", "Jackson Hawes", "TE", "", LP, ""),
    ("BUF", "Amani Hooker", "S", "", LP, ""),
    ("BUF", "Ty Johnson", "RB", "", FP, ""),
    ("BUF", "Dalton Kincaid", "TE", "", DNP, ""),
    ("BUF", "Connor McGovern", "C", "", FP, ""),
    ("BUF", "T.J. Sanders", "DE", "", FP, ""),
    ("BUF", "Tyrell Shavers", "WR", "", FP, ""),
    ("BUF", "O'Cyrus Torrence", "G", "", DNP, ""),
    ("BUF", "Dorian Williams", "LB", "", DNP, ""),
    # ----- TEN @ DAL, Sun Nov 22 1:00 PM EST, FOX ---------------------------------------
    ("TEN", "Tony Adams", "S", "", DNP, ""),
    ("TEN", "Cody Barton", "LB", "", FP, ""),
    ("TEN", "Fernando Carmona", "G", "", LP, ""),
    ("TEN", "John Franklin-Myers", "DE", "", LP, ""),
    ("TEN", "Kylen Granson", "TE", "", FP, ""),
    ("TEN", "Anthony Hill Jr.", "LB", "", LP, ""),
    ("TEN", "Tyjae Spears", "RB", "", DNP, ""),
    ("TEN", "Carnell Tate", "WR", "", LP, ""),
    ("TEN", "Kevin Winston Jr.", "S", "", FP, ""),
    ("DAL", "DaRon Bland", "CB", "", DNP, ""),
    ("DAL", "Tyler Booker", "G", "", DNP, ""),
    ("DAL", "Donovan Ezeiruaku", "LB", "", DNP, ""),
    ("DAL", "Jake Ferguson", "TE", "", DNP, ""),
    ("DAL", "Malik Hooker", "S", "", FP, ""),
    ("DAL", "James Houston", "LB", "", FP, ""),
    ("DAL", "P.J. Locke", "S", "", DNP, ""),
    ("DAL", "Von Miller", "LB", "", DNP, ""),
    ("DAL", "Jonathan Mingo", "WR", "", DNP, ""),
    ("DAL", "Devin Moore", "CB", "", FP, ""),
    ("DAL", "Otito Ogbonnia", "DE", "", FP, ""),
    ("DAL", "Joey Porter Jr.", "CB", "", FP, ""),
    ("DAL", "Juanyeh Thomas", "S", "", LP, ""),
    ("DAL", "Jalen Thompson", "S", "", LP, ""),
    # ----- NO @ CHI, Sun Nov 22 1:00 PM EST, FOX ----------------------------------------
    ("NO", "CJ Donaldson", "RB", "", FP, ""),
    ("NO", "Martin Emerson", "CB", "", DNP, ""),
    ("NO", "Taliese Fuaga", "T", "", DNP, ""),
    ("NO", "Alvin Kamara", "RB", "", DNP, ""),
    ("NO", "Erik McCoy", "C", "", DNP, ""),
    ("NO", "Justin Reid", "S", "", DNP, ""),
    ("NO", "Asim Richards", "T", "", DNP, ""),
    ("NO", "Decamerion Richardson", "CB", "", LP, ""),
    ("NO", "Jordyn Tyson", "WR", "", LP, ""),
    ("NO", "Pete Werner", "LB", "", DNP, ""),
    ("CHI", "Luther Burden III", "WR", "", FP, ""),
    ("CHI", "Kyler Gordon", "CB", "", DNP, ""),
    ("CHI", "Kyle Monangai", "RB", "", FP, ""),
    ("CHI", "Malik Muhammad", "CB", "", FP, ""),
    ("CHI", "Jeffery Simmons", "DT", "", LP, ""),
    # ----- NYJ @ LAC, Sun Nov 22 4:05 PM EST, FOX ---------------------------------------
    ("NYJ", "Omar Cooper Jr.", "WR", "", DNP, ""),
    ("NYJ", "David Onyemata", "DT", "", LP, ""),
    ("NYJ", "Joseph Ossai", "DE", "", LP, ""),
    ("NYJ", "Dylan Parham", "G", "", LP, ""),
    ("NYJ", "Harrison Phillips", "DT", "", DNP, ""),
    ("NYJ", "Geno Smith", "QB", "", LP, ""),
    ("NYJ", "Trevin Wallace", "LB", "", LP, ""),
    ("NYJ", "Isaiah Williams", "WR", "", DNP, ""),
    ("LAC", "Justin Eboigbe", "DE", "", LP, ""),
    ("LAC", "Daiyan Henley", "LB", "", DNP, ""),
    ("LAC", "Donte Jackson", "CB", "", LP, ""),
    ("LAC", "Charlie Kolar", "TE", "", DNP, ""),
    ("LAC", "Khalil Mack", "DE", "", DNP, ""),
    ("LAC", "Ladd McConkey", "WR", "", LP, ""),
    ("LAC", "Trey Pipkins", "T", "", LP, ""),
    ("LAC", "Rodney Shelley", "CB", "", DNP, ""),
    ("LAC", "Brenen Thompson", "WR", "", DNP, ""),
    ("LAC", "Isas Waxter", "CB", "", DNP, ""),
    ("LAC", "Kendall Williamson", "S", "", LP, ""),
    # ----- JAX @ NYG, Sun Nov 22 4:25 PM EST, CBS ---------------------------------------
    ("JAX", "LeQuint Allen Jr.", "RB", "", LP, ""),
    ("JAX", "Arik Armstead", "DT", "", DNP, ""),
    ("JAX", "Matt Dickerson", "DT", "", LP, ""),
    ("JAX", "BJ Green II", "DE", "", FP, ""),
    ("JAX", "Robert Hainsey", "C", "", DNP, ""),
    ("JAX", "Antonio Johnson", "S", "", LP, ""),
    ("JAX", "Jalen McLeod", "LB", "", LP, ""),
    ("JAX", "Jakobi Meyers", "WR", "", LP, ""),
    ("JAX", "Jonah Monheim", "C", "", LP, ""),
    ("JAX", "Chris Rodriguez Jr.", "RB", "", LP, ""),
    ("JAX", "Danny Striggow", "DE", "", LP, ""),
    ("JAX", "Bhayshul Tuten", "RB", "", LP, ""),
    ("JAX", "Travon Walker", "DE", "", LP, ""),
    ("NYG", "Deonte Banks", "CB", "", FP, ""),
    ("NYG", "Malik Harrison", "LB", "", LP, ""),
    ("NYG", "Nic Jones", "CB", "", DNP, ""),
    ("NYG", "Ben Mann", "LS", "", FP, ""),
    ("NYG", "Jason Pinnock", "S", "", LP, ""),
    ("NYG", "Cam Skattebo", "RB", "", FP, ""),
    # ----- LV @ DEN, Sun Nov 22 4:25 PM EST, CBS ----------------------------------------
    ("LV", "Thomas Booker", "DT", "", FP, ""),
    ("LV", "Brock Bowers", "TE", "", DNP, ""),
    ("LV", "Foley Fatukasi", "DT", "", LP, ""),
    ("LV", "Matt Gay", "K", "", LP, ""),
    ("LV", "Tonka Hemingway", "DT", "", DNP, ""),
    ("LV", "Ian Thomas", "TE", "", FP, ""),
    ("DEN", "Kris Abrams-Draine", "CB", "", LP, ""),
    ("DEN", "Zach Allen", "DE", "", LP, ""),
    ("DEN", "Talanoa Hufanga", "S", "", FP, ""),
    ("DEN", "Brandon Jones", "S", "", LP, ""),
    ("DEN", "Caleb Lohner", "TE", "", FP, ""),
    ("DEN", "Riley Moss", "CB", "", FP, ""),
    ("DEN", "Adam Prentice", "FB", "", FP, ""),
    ("DEN", "Courtland Sutton", "WR", "", LP, ""),
    ("DEN", "Jaylen Waddle", "WR", "", FP, ""),
    # ----- MIN @ SF, Sun Nov 22 8:20 PM EST, NBC (Mexico City) --------------------------
    ("MIN", "Jordan Addison", "WR", "", DNP, ""),
    ("MIN", "Blake Cashman", "LB", "", FP, ""),
    ("MIN", "T.J. Hockenson", "TE", "", LP, ""),
    ("MIN", "Tyrion Ingram-Dawkins", "DT", "", FP, ""),
    ("MIN", "Jauan Jennings", "WR", "", FP, ""),
    ("MIN", "Jeshaun Jones", "WR", "", LP, ""),
    ("MIN", "Kyler Murray", "QB", "", DNP, ""),
    ("MIN", "Andrew Van Ginkel", "LB", "", LP, ""),
    ("MIN", "Kyle Van Noy", "LB", "", LP, ""),
    ("MIN", "Jay Ward", "S", "", LP, ""),
    ("SF", "Ji'Ayir Brown", "S", "", LP, ""),
    ("SF", "Mike Evans", "WR", "", DNP, ""),
    ("SF", "Luke Gifford", "LB", "", LP, ""),
    ("SF", "Renardo Green", "CB", "", LP, ""),
    ("SF", "Dre Greenlaw", "LB", "", DNP, ""),
    ("SF", "Nate Hobbs", "CB", "", FP, ""),
    ("SF", "Mac Jones", "QB", "", LP, ""),
    ("SF", "Khalid Kareem", "DE", "", LP, ""),
    ("SF", "Christian McCaffrey", "RB", "", DNP, ""),
    ("SF", "Siran Neal", "S", "", LP, ""),
    ("SF", "Upton Stout", "CB", "", LP, ""),
    ("SF", "Jon Weeks", "LS", "", FP, ""),
    ("SF", "C.J. West", "DT", "", FP, ""),
    ("SF", "Mykel Williams", "DE", "", FP, ""),
    ("SF", "Trent Williams", "T", "", DNP, ""),
    # ----- CIN @ WAS, Mon Nov 23 8:15 PM EST, ESPN --------------------------------------
    # Both clubs print the literal block "No Injuries Reported" on the page. Zero player
    # rows is the page's own statement. Recorded in CLUBS_NO_REPORT below, not invented.
]

# Clubs that the page prints with the "No Injuries Reported" block (zero player rows).
CLUBS_NO_REPORT = ["CIN", "WAS"]
