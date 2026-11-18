"""Official-source capture registers for the Requirements Desk.

Every row in this module was transcribed from an NFL.com page that was opened
with the session's page-retrieval tool on 2026-11-18 (see manifest below).
Nothing here is inferred, modelled or copied from a third-party feed.

Rules followed while transcribing:

* A blank cell on the official page is stored as an empty string, never filled.
* Practice status and game status are stored verbatim as published.
* Club abbreviations are the ones the official page prints next to each table.
* Where the official page prints no table for a club, no row is invented; the
  club is recorded in the "absent clubs" register with the reason the page
  gives (bye) or "reason not stated by the source" if it gives none.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

# --------------------------------------------------------------------------
# Capture manifest — what was opened, when, and how.
# --------------------------------------------------------------------------

CAPTURE_UTC = "2026-11-18T03:52Z"
CAPTURE_METHOD = (
    "Page retrieved with the session's page-retrieval tool; content returned as "
    "markdown text. The sandbox shell has no network route to nfl.com, so no raw "
    "HTTP response bytes could be retained. The register hash below therefore covers "
    "the transcribed register, not the NFL response body. This limitation is published "
    "on the Flagged for Review page."
)

SOURCES = {
    "injury_w10": {
        "url": "https://www.nfl.com/injuries/league/2026/REG10",
        "title": "Official NFL Injury Report for Players - Week 10 of the 2026 Season",
        "chunks": 8,
        "captured_utc": CAPTURE_UTC,
    },
    "sched_w10": {
        "url": "https://www.nfl.com/schedules/2026/by-week/week-10",
        "title": "NFL Week 10 Schedule 2026: Games, Times, Matchups & Tickets",
        "chunks": 2,
        "captured_utc": CAPTURE_UTC,
    },
    "sched_w11": {
        "url": "https://www.nfl.com/schedules/2026/by-week/week-11",
        "title": "NFL Week 11 Schedule 2026: Games, Times, Matchups & Tickets",
        "chunks": 3,
        "captured_utc": CAPTURE_UTC,
    },
    "standings": {
        "url": "https://www.nfl.com/standings/division/2026/REG",
        "title": "2026 NFL Division Standings",
        "chunks": 2,
        "captured_utc": CAPTURE_UTC,
    },
}

# --------------------------------------------------------------------------
# Register 1 — Week 10 2026 official injury report, every listed player row.
#
# Tuple: (game_slot, club, player, position, injury, practice_status, game_status)
# `game_slot` identifies the fixture block the club table sits under on the page.
# --------------------------------------------------------------------------

INJURY_ROWS = [
    # --- Thursday, November 12 — WAS @ NYG ---------------------------------
    ("Thu Nov 12, 8:15 PM ET", "WAS", "John Bates", "TE", "", "Full Participation in Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "WAS", "Treylon Burks", "WR", "", "Did Not Participate In Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "WAS", "Jayden Daniels", "QB", "", "Full Participation in Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "WAS", "Matt Gulbin", "C", "", "Full Participation in Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "WAS", "Chig Okonkwo", "TE", "", "Full Participation in Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "WAS", "Lucas Patrick", "C", "Concussion", "Did Not Participate In Practice", "Out"),
    ("Thu Nov 12, 8:15 PM ET", "WAS", "Amik Robertson", "CB", "", "Limited Participation in Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "WAS", "Shy Tuttle", "DT", "", "Full Participation in Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "WAS", "Colson Yankoff", "TE", "Knee", "Did Not Participate In Practice", "Out"),
    ("Thu Nov 12, 8:15 PM ET", "NYG", "Abdul Carter", "LB", "", "Full Participation in Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "NYG", "Jermaine Eluemunor", "T", "", "Full Participation in Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "NYG", "Malik Harrison", "LB", "Groin", "Limited Participation in Practice", "Questionable"),
    ("Thu Nov 12, 8:15 PM ET", "NYG", "Colton Hood", "CB", "", "Full Participation in Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "NYG", "Theo Johnson", "TE", "", "Full Participation in Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "NYG", "Charlie Jones", "WR", "", "Full Participation in Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "NYG", "J.J. McCarthy", "QB", "", "Full Participation in Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "NYG", "Darnell Mooney", "WR", "", "Full Participation in Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "NYG", "Malik Nabers", "WR", "", "Full Participation in Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "NYG", "Cam Skattebo", "RB", "", "Full Participation in Practice", ""),
    ("Thu Nov 12, 8:15 PM ET", "NYG", "Andrew Thomas", "T", "", "Full Participation in Practice", ""),
    # --- Sunday, November 15, 9:30 AM — NE @ DET (Munich) -------------------
    ("Sun Nov 15, 9:30 AM ET", "NE", "Ben Brown", "C", "Knee", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 9:30 AM ET", "NE", "A.J. Brown", "WR", "Ankle, Knee", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 9:30 AM ET", "NE", "Kevin Byard", "S", "Chest", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 9:30 AM ET", "NE", "Carlton Davis III", "CB", "Knee", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 9:30 AM ET", "NE", "Reggie Gilliam", "FB", "Knee", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 9:30 AM ET", "NE", "TreVeyon Henderson", "RB", "Illness", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 9:30 AM ET", "NE", "Hunter Henry", "TE", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 9:30 AM ET", "NE", "Cameron Latu", "TE", "Back", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 9:30 AM ET", "NE", "Drake Maye", "QB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 9:30 AM ET", "NE", "Morgan Moses", "T", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 9:30 AM ET", "NE", "Walter Rouse", "T", "Concussion", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 9:30 AM ET", "NE", "Brenden Schooler", "S", "Hamstring", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 9:30 AM ET", "NE", "Rhamondre Stevenson", "RB", "Knee", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 9:30 AM ET", "NE", "Greg Van Roten", "G", "Hamstring", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 9:30 AM ET", "NE", "Charles Woods", "CB", "Hamstring", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 9:30 AM ET", "DET", "Brian Branch", "S", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 9:30 AM ET", "DET", "Jared Goff", "QB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 9:30 AM ET", "DET", "Kerby Joseph", "S", "Knee", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 9:30 AM ET", "DET", "Cade Mays", "C", "Ankle", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 9:30 AM ET", "DET", "D.J. Reed", "CB", "Hip", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 9:30 AM ET", "DET", "Jacob Saylors", "RB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 9:30 AM ET", "DET", "Amon-Ra St. Brown", "WR", "Rib", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 9:30 AM ET", "DET", "Sione Vaki", "RB", "Ankle", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 9:30 AM ET", "DET", "DJ Wonnum", "DE", "", "Full Participation in Practice", ""),
    # --- Sunday, November 15, 1:00 PM — KC @ ATL ----------------------------
    ("Sun Nov 15, 1:00 PM ET", "KC", "Jeffrey Bassa", "LB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "KC", "Mansoor Delane", "CB", "Shoulder", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "KC", "Justin Fields", "QB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "KC", "Jaden Hicks", "S", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "KC", "Travis Kelce", "TE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "KC", "Patrick Mahomes", "QB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "KC", "Jaylon Moore", "T", "Ankle", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "KC", "Omarr Norman-Lott", "DT", "Knee", "Limited Participation in Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "KC", "Jaydn Ott", "RB", "Hamstring", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "KC", "Rashee Rice", "WR", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "KC", "Kenneth Walker III", "RB", "Groin", "Did Not Participate In Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "KC", "Peter Woods", "DT", "Neck", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "KC", "Xavier Worthy", "WR", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "ATL", "Zachariah Branch", "WR", "Hamstring", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "ATL", "Kendal Daniels", "LB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "ATL", "Divine Deablo", "LB", "Forearm", "Did Not Participate In Practice", "Doubtful"),
    ("Sun Nov 15, 1:00 PM ET", "ATL", "Gervon Dexter Sr.", "DT", "Illness", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "ATL", "Jake Matthews", "T", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "ATL", "Liam McCullough", "LS", "", "Did Not Participate In Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "ATL", "James Pearce Jr.", "DE", "Back", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "ATL", "Za'Darius Smith", "DE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "ATL", "Jawaan Taylor", "T", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "ATL", "Cameron Thomas", "DE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "ATL", "Josh Woods", "LB", "Ankle", "Full Participation in Practice", "Questionable"),
    # --- Sunday, November 15, 1:00 PM — MIN @ GB ----------------------------
    ("Sun Nov 15, 1:00 PM ET", "MIN", "Jordan Addison", "WR", "Thumb", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "MIN", "Blake Cashman", "LB", "Concussion", "Limited Participation in Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "MIN", "Christian Darrisaw", "T", "", "Did Not Participate In Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "MIN", "T.J. Hockenson", "TE", "Wrist, Chest", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "MIN", "Tyrion Ingram-Dawkins", "DT", "Ankle", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "MIN", "Theo Jackson", "S", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "MIN", "Jauan Jennings", "WR", "Calf", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "MIN", "Josh Metellus", "S", "Shoulder", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "MIN", "Kyler Murray", "QB", "Hamstring", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "MIN", "Harrison Smith", "S", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "MIN", "Kyle Van Noy", "LB", "Calf", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "MIN", "Jay Ward", "S", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "MIN", "Carson Wentz", "QB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Aaron Banks", "G", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Chris Brooks", "RB", "Ankle", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Javon Bullard", "S", "Ankle, Knee", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Zaire Franklin", "LB", "Shin", "Did Not Participate In Practice", "Doubtful"),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Travis Glover", "G", "Knee", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Ty'Ron Hopper", "LB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Josh Jacobs", "RB", "Finger", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Xavier McKinney", "S", "Foot", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Bo Melton", "WR", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Skyy Moore", "WR", "Ankle", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Micah Parsons", "LB", "Knee, Illness", "Limited Participation in Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Sean Rhyan", "C", "Ankle", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Trey Smack", "K", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Lukas Van Ness", "LB", "Back", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Josh Whyle", "TE", "Concussion", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Savion Williams", "WR", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "GB", "Kevin Zeitler", "G", "Ankle, Triceps", "Did Not Participate In Practice", "Questionable"),
    # --- Sunday, November 15, 1:00 PM — JAX @ TEN ---------------------------
    ("Sun Nov 15, 1:00 PM ET", "JAX", "Jessie Bates", "S", "Not injury related - resting player", "Limited Participation in Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "JAX", "Ezra Cleveland", "G", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "JAX", "Branson Combs", "LB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "JAX", "Jordan Davis", "DT", "Not injury related - resting player", "Limited Participation in Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "JAX", "BJ Green II", "DE", "Forearm", "Full Participation in Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "JAX", "Robert Hainsey", "C", "Concussion", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "JAX", "Antonio Johnson", "S", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "JAX", "Jakobi Meyers", "WR", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "JAX", "Chris Rodriguez Jr.", "RB", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "JAX", "Bhayshul Tuten", "RB", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "JAX", "Travon Walker", "DE", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "TEN", "Cody Barton", "LB", "Concussion", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "TEN", "John Franklin-Myers", "DE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "TEN", "Marcus Harris", "CB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "TEN", "Anthony Hill Jr.", "LB", "Neck", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "TEN", "Jaylon Jones", "CB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "TEN", "JC Latham", "T", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "TEN", "Tony Pollard", "RB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "TEN", "Peter Skoronski", "G", "Hamstring", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "TEN", "Tyjae Spears", "RB", "Knee", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "TEN", "Carnell Tate", "WR", "Shoulder", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "TEN", "Tommy Townsend", "P", "Knee, Achilles", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "TEN", "Kevin Winston Jr.", "S", "", "Full Participation in Practice", ""),
    # --- Sunday, November 15, 1:00 PM — BUF @ NYJ ---------------------------
    ("Sun Nov 15, 1:00 PM ET", "BUF", "Alec Anderson", "G", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "BUF", "Christian Benford", "CB", "Wrist", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "BUF", "Terrel Bernard", "LB", "", "Did Not Participate In Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "BUF", "Spencer Brown", "T", "Ankle", "Did Not Participate In Practice", "Doubtful"),
    ("Sun Nov 15, 1:00 PM ET", "BUF", "Dion Dawkins", "T", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "BUF", "Sam Franklin Jr.", "S", "Shoulder", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "BUF", "Greg Gaines", "DT", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "BUF", "Jordan Hancock", "CB", "Hamstring", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "BUF", "Dalton Kincaid", "TE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "BUF", "Connor McGovern", "C", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "BUF", "Ed Oliver", "DE", "", "Did Not Participate In Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "BUF", "Ar'maj Reed-Adams", "G", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "BUF", "T.J. Sanders", "DE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "BUF", "Tyrell Shavers", "WR", "Knee", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "NYJ", "Jarvis Brownlee Jr.", "CB", "Illness", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "NYJ", "Omar Cooper Jr.", "WR", "Ankle", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "NYJ", "Adonai Mitchell", "WR", "Knee", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "NYJ", "Joseph Ossai", "DE", "Ankle", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "NYJ", "VJ Payne", "S", "Knee", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "NYJ", "Harrison Phillips", "DT", "Ankle", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "NYJ", "Trevin Wallace", "LB", "Groin", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "NYJ", "Garrett Wilson", "WR", "Concussion", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "NYJ", "Nahshon Wright", "CB", "Back", "Full Participation in Practice", "Questionable"),
    # --- Sunday, November 15, 1:00 PM — MIA @ IND ---------------------------
    ("Sun Nov 15, 1:00 PM ET", "MIA", "Tucker Addington", "LS", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "MIA", "Kaytron Allen", "RB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "MIA", "Darrell Baker Jr.", "CB", "Knee", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "MIA", "Chris Bell", "WR", "Knee", "Did Not Participate In Practice", "Doubtful"),
    ("Sun Nov 15, 1:00 PM ET", "MIA", "Aaron Brewer", "C", "Concussion", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "MIA", "Malik Herring", "DE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "MIA", "Will Kacmarek", "TE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "MIA", "Michael Taaffe", "S", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "MIA", "Dante Trader Jr.", "S", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "MIA", "Jared Wayne", "WR", "Quadricep", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "MIA", "Jaylen Wright", "RB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "IND", "Mo Alie-Cox", "TE", "Groin", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "IND", "CJ Allen", "LB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "IND", "Jaylon Carlies", "LB", "Neck", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "IND", "Akeem Davis-Gaither", "LB", "Knee", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "IND", "A.J. Haulcy", "S", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "IND", "Arden Key", "DE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "IND", "Will Mallory", "TE", "Hamstring", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "IND", "Luke Rhodes", "LS", "Hamstring", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "IND", "Grover Stewart", "DT", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "IND", "Jonathan Taylor", "RB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "IND", "Jerry Tillery", "DT", "Calf", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "IND", "Jalen Travis", "T", "Knee", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "IND", "Justin Walley", "CB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "IND", "Charvarius Ward", "CB", "", "Full Participation in Practice", ""),
    # --- Sunday, November 15, 1:00 PM — CAR @ NO ----------------------------
    ("Sun Nov 15, 1:00 PM ET", "CAR", "Jonathon Brooks", "RB", "Groin", "Limited Participation in Practice", "Doubtful"),
    ("Sun Nov 15, 1:00 PM ET", "CAR", "Brady Christensen", "G", "Hamstring", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "CAR", "Trevor Etienne", "RB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "CAR", "Chuba Hubbard", "RB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "CAR", "Lee Hunter", "DT", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "CAR", "Mike Jackson", "CB", "Groin", "Limited Participation in Practice", "Doubtful"),
    ("Sun Nov 15, 1:00 PM ET", "CAR", "Will Lee III", "CB", "Hamstring", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "CAR", "Xavier Legette", "WR", "Knee", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "CAR", "Damien Lewis", "G", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "CAR", "Bobby Okereke", "LB", "Foot", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "CAR", "Jaelan Phillips", "LB", "Hamstring", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "CAR", "Torricelli Simpkins III", "G", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "NO", "Kelvin Banks Jr.", "T", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "NO", "CJ Donaldson", "RB", "Shoulder", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "NO", "David Edwards", "G", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "NO", "Martin Emerson", "CB", "Shin", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "NO", "Travis Etienne", "RB", "Hamstring", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "NO", "Noah Fant", "TE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "NO", "Taliese Fuaga", "T", "Knee", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "NO", "Alvin Kamara", "RB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "NO", "Erik McCoy", "C", "Biceps", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "NO", "Christen Miller", "DT", "Knee", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "NO", "Asim Richards", "T", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "NO", "Quincy Riley", "CB", "", "Full Participation in Practice", ""),
    # --- Sunday, November 15, 1:00 PM — HOU @ CLE ---------------------------
    ("Sun Nov 15, 1:00 PM ET", "HOU", "Azeez Al-Shaair", "LB", "Groin, Not injury related - personal matter", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "HOU", "Will Anderson Jr.", "DE", "Ankle", "Did Not Participate In Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "HOU", "Reed Blankenship", "S", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "HOU", "Trent Brown", "T", "Wrist, Illness", "Did Not Participate In Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "HOU", "Tank Dell", "WR", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "HOU", "Blake Fisher", "T", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "HOU", "Marvin Harrison Jr.", "WR", "Hamstring", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "HOU", "Jacob Hummel", "LB", "Groin", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "HOU", "Danielle Hunter", "DE", "Hamstring", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "HOU", "Brevin Jordan", "TE", "Finger, Foot", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "HOU", "Woody Marks", "RB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "HOU", "David Montgomery", "RB", "Groin", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "HOU", "Keylan Rutledge", "G", "Neck, Shoulder", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "HOU", "Jaylin Smith", "CB", "Hamstring", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "HOU", "Wyatt Teller", "G", "Illness, Back", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "HOU", "Tommy Togiai", "DT", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "CLE", "Austin Barber", "T", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "CLE", "Denzel Boston", "WR", "Toe", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 1:00 PM ET", "CLE", "Michael Burton", "FB", "Calf", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "CLE", "Maliek Collins", "DT", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "CLE", "Harold Fannin Jr.", "TE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "CLE", "Ronnie Hickman Jr.", "S", "Concussion", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 1:00 PM ET", "CLE", "Tytus Howard", "T", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "CLE", "Elgton Jenkins", "C", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "CLE", "Donovan McMillon", "S", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "CLE", "Carson Schwesinger", "LB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "CLE", "Denzel Ward", "CB", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 1:00 PM ET", "CLE", "Quincy Williams", "LB", "", "Full Participation in Practice", ""),
    # --- Sunday, November 15, 4:05 PM — LAR @ AZ ----------------------------
    ("Sun Nov 15, 4:05 PM ET", "LAR", "Davis Allen", "TE", "Oblique", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:05 PM ET", "LAR", "Steve Avila", "G", "Hamstring", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 4:05 PM ET", "LAR", "Joe Cardona", "LS", "Ankle", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:05 PM ET", "LAR", "Kam Curl", "S", "Toe", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:05 PM ET", "LAR", "Aaron Donald", "DT", "", "Did Not Participate In Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "LAR", "Terrance Ferguson", "TE", "Ankle, Hamstring", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 4:05 PM ET", "LAR", "Braden Fiske", "DT", "", "Did Not Participate In Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "LAR", "Myles Garrett", "LB", "Knee, Not injury related - resting player", "Did Not Participate In Practice", "Questionable"),
    ("Sun Nov 15, 4:05 PM ET", "LAR", "Tyler Higbee", "TE", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "LAR", "Trent McDuffie", "CB", "Back", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:05 PM ET", "LAR", "Puka Nacua", "WR", "", "Did Not Participate In Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "LAR", "Colby Parkinson", "TE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "LAR", "Matthew Stafford", "QB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "LAR", "Byron Young", "LB", "", "Did Not Participate In Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "AZ", "Budda Baker", "S", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "AZ", "Zachary Carter", "DT", "Knee", "Limited Participation in Practice", "Out"),
    ("Sun Nov 15, 4:05 PM ET", "AZ", "Hjalte Froholdt", "C", "Concussion", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 4:05 PM ET", "AZ", "Jon Gaines II", "G", "Ankle", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 4:05 PM ET", "AZ", "Bam Knight", "RB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "AZ", "Hunter Long", "TE", "Knee", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:05 PM ET", "AZ", "Roy Lopez", "DT", "Toe, Ankle", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:05 PM ET", "AZ", "Max Melton", "CB", "Knee, Hand", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:05 PM ET", "AZ", "Darius Robinson", "DT", "Wrist", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:05 PM ET", "AZ", "Isaac Seumalo", "G", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "AZ", "Dante Stills", "DT", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "AZ", "Josh Sweat", "LB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "AZ", "Jayden Williams", "T", "Knee", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:05 PM ET", "AZ", "Mack Wilson", "LB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "AZ", "Andrew Wingard", "S", "Groin", "Did Not Participate In Practice", "Questionable"),
    # --- Sunday, November 15, 4:05 PM — SEA @ LV ----------------------------
    ("Sun Nov 15, 4:05 PM ET", "SEA", "AJ Barner", "TE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "SEA", "Anthony Bradford", "G", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "SEA", "Charles Cross", "T", "Ankle", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 4:05 PM ET", "SEA", "Sam Darnold", "QB", "Ribs, Quadricep", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 4:05 PM ET", "SEA", "Derick Hall", "LB", "", "Did Not Participate In Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "SEA", "Drew Lock", "QB", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "SEA", "Quenton Nelson", "G", "Knee", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 4:05 PM ET", "SEA", "Uchenna Nwosu", "LB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "SEA", "Patrick O'Connell", "LB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "SEA", "Connor O'Toole", "LB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "SEA", "Brandon Pili", "DT", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "SEA", "Jarran Reed", "DT", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "SEA", "Rashid Shaheed", "WR", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "SEA", "Jaxon Smith-Njigba", "WR", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "SEA", "Leonard Williams", "DT", "Stinger", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 4:05 PM ET", "LV", "Thomas Booker", "DT", "Ankle", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:05 PM ET", "LV", "Foley Fatukasi", "DT", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "LV", "Ian Thomas", "TE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:05 PM ET", "LV", "Dont'e Thornton Jr.", "WR", "Back", "Did Not Participate In Practice", "Questionable"),
    ("Sun Nov 15, 4:05 PM ET", "LV", "Trey Zuhn III", "C", "", "Full Participation in Practice", ""),
    # --- Sunday, November 15, 4:25 PM — SF @ DAL ----------------------------
    ("Sun Nov 15, 4:25 PM ET", "SF", "Mike Evans", "WR", "Achilles", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 4:25 PM ET", "SF", "Renardo Green", "CB", "Back", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:25 PM ET", "SF", "Dre Greenlaw", "LB", "Knee", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:25 PM ET", "SF", "Nate Hobbs", "CB", "Groin", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:25 PM ET", "SF", "Deommodore Lenoir", "CB", "Foot", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:25 PM ET", "SF", "Christian McCaffrey", "RB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:25 PM ET", "SF", "Siran Neal", "S", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:25 PM ET", "SF", "Demarcus Robinson", "WR", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:25 PM ET", "SF", "Deebo Samuel Sr.", "WR", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:25 PM ET", "SF", "Upton Stout", "CB", "Shoulder, Neck", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:25 PM ET", "SF", "C.J. West", "DT", "Knee", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:25 PM ET", "SF", "Trent Williams", "T", "Shoulder", "Did Not Participate In Practice", "Questionable"),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "DaRon Bland", "CB", "Ankle", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "Jonathan Bullard", "DT", "Calf", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "Alijah Clark", "S", "Illness", "Did Not Participate In Practice", "Questionable"),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "Donovan Ezeiruaku", "LB", "Ankle", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "Jake Ferguson", "TE", "Knee, Ankle", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "Tyler Goodson", "RB", "Ankle, Knee", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "Malik Hooker", "S", "", "Did Not Participate In Practice", ""),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "Marist Liufau", "LB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "P.J. Locke", "S", "Concussion", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "Von Miller", "LB", "", "Did Not Participate In Practice", ""),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "Jonathan Mingo", "WR", "Ankle", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "Devin Moore", "CB", "Hip", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "DeMarvion Overshown", "LB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "George Pickens", "WR", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "Joey Porter Jr.", "CB", "Ankle, Foot", "Limited Participation in Practice", "Questionable"),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "Luke Schoonmaker", "TE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "Brevyn Spann-Ford", "TE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "Juanyeh Thomas", "S", "Hamstring", "Did Not Participate In Practice", "Doubtful"),
    ("Sun Nov 15, 4:25 PM ET", "DAL", "KaVontae Turpin", "WR", "", "Full Participation in Practice", ""),
    # --- Sunday, November 15, 8:20 PM — PIT @ CIN ---------------------------
    ("Sun Nov 15, 8:20 PM ET", "PIT", "Brandin Echols", "CB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 8:20 PM ET", "PIT", "DeShon Elliott", "S", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 8:20 PM ET", "PIT", "Derrick Harmon", "DT", "Foot", "Full Participation in Practice", "Questionable"),
    ("Sun Nov 15, 8:20 PM ET", "PIT", "Cameron Heyward", "DT", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 8:20 PM ET", "PIT", "Ben Skowronek", "WR", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 8:20 PM ET", "PIT", "Doneiko Slaughter", "CB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 8:20 PM ET", "PIT", "Darnell Washington", "TE", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 8:20 PM ET", "PIT", "T.J. Watt", "LB", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 8:20 PM ET", "CIN", "Jonathan Allen", "DT", "", "Limited Participation in Practice", ""),
    ("Sun Nov 15, 8:20 PM ET", "CIN", "Jalen Davis", "CB", "Hamstring", "Full Participation in Practice", "Doubtful"),
    ("Sun Nov 15, 8:20 PM ET", "CIN", "Kyle Dugger", "S", "Quadricep", "Did Not Participate In Practice", "Out"),
    ("Sun Nov 15, 8:20 PM ET", "CIN", "Dylan Fairchild", "G", "", "Full Participation in Practice", ""),
    ("Sun Nov 15, 8:20 PM ET", "CIN", "B.J. Hill", "DT", "", "Did Not Participate In Practice", ""),
    ("Sun Nov 15, 8:20 PM ET", "CIN", "Andrei Iosivas", "WR", "Thumb", "Full Participation in Practice", "Doubtful"),
    ("Sun Nov 15, 8:20 PM ET", "CIN", "Dexter Lawrence", "DT", "", "Did Not Participate In Practice", ""),
    ("Sun Nov 15, 8:20 PM ET", "CIN", "Brian Parker II", "G", "Knee", "Full Participation in Practice", "Doubtful"),
    ("Sun Nov 15, 8:20 PM ET", "CIN", "DJ Turner II", "CB", "", "Full Participation in Practice", ""),
    # --- Monday, November 16, 8:15 PM — LAC @ BAL ---------------------------
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Kayode Awosika", "G", "Fibula", "Full Participation in Practice", "Questionable"),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Bud Dupree", "DE", "", "Full Participation in Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Justin Eboigbe", "DE", "Ankle", "Limited Participation in Practice", "Questionable"),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Alex Harkey", "G", "", "Full Participation in Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Tre Harris", "WR", "", "Full Participation in Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Cam Hart", "CB", "", "Full Participation in Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Daiyan Henley", "LB", "", "Full Participation in Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Deane Leonard", "CB", "", "Full Participation in Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Khalil Mack", "LB", "", "Full Participation in Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Ladd McConkey", "WR", "Back", "Did Not Participate In Practice", "Questionable"),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Keaton Mitchell", "RB", "", "Full Participation in Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "David Njoku", "TE", "Fibula", "Full Participation in Practice", "Questionable"),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Denzel Perryman", "LB", "Pectoral", "Full Participation in Practice", "Questionable"),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Trey Pipkins", "T", "Not injury related - personal matter, Knee", "Limited Participation in Practice", "Questionable"),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Rodney Shelley", "CB", "", "Full Participation in Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Branson Taylor", "G", "Ankle", "Did Not Participate In Practice", "Out"),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Brenen Thompson", "WR", "Hamstring", "Did Not Participate In Practice", "Doubtful"),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Isas Waxter", "CB", "Ankle", "Did Not Participate In Practice", "Out"),
    ("Mon Nov 16, 8:15 PM ET", "LAC", "Kendall Williamson", "S", "Calf", "Did Not Participate In Practice", "Out"),
    ("Mon Nov 16, 8:15 PM ET", "BAL", "Rasheen Ali", "RB", "", "Full Participation in Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "BAL", "Rashod Bateman", "WR", "", "Full Participation in Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "BAL", "Calais Campbell", "DT", "", "Did Not Participate In Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "BAL", "Kyle Hamilton", "S", "", "Full Participation in Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "BAL", "Jaylinn Hawkins", "S", "Knee", "Limited Participation in Practice", "Out"),
    ("Mon Nov 16, 8:15 PM ET", "BAL", "Matthew Hibner", "TE", "", "Full Participation in Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "BAL", "Olaivavega Ioane", "G", "", "Full Participation in Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "BAL", "Adam Randall", "RB", "Neck, Hamstring", "Full Participation in Practice", "Questionable"),
    ("Mon Nov 16, 8:15 PM ET", "BAL", "Ronnie Stanley", "T", "", "Did Not Participate In Practice", ""),
    ("Mon Nov 16, 8:15 PM ET", "BAL", "Nate Wiggins", "CB", "", "Full Participation in Practice", ""),
]

# Clubs with no table on the Week 10 page, with the reason the source gives.
INJURY_ABSENT_CLUBS = [
    ("CHI", "No table on the Week 10 page. Week 10 schedule page lists Chicago under 'Teams on Bye'.",
     "https://www.nfl.com/schedules/2026/by-week/week-10"),
    ("DEN", "No table on the Week 10 page. Week 10 schedule page lists Denver under 'Teams on Bye'.",
     "https://www.nfl.com/schedules/2026/by-week/week-10"),
    ("PHI", "No table on the Week 10 page. Week 10 schedule page lists Philadelphia under 'Teams on Bye'.",
     "https://www.nfl.com/schedules/2026/by-week/week-10"),
    ("TB", "No table on the Week 10 page. Week 10 schedule page lists Tampa Bay under 'Teams on Bye'.",
     "https://www.nfl.com/schedules/2026/by-week/week-10"),
]


# --------------------------------------------------------------------------
# Register 2 — Week 10 2026 official results.
#
# Tuple: (date, away, away_pts, home, home_pts, status, source_url)
# Every score below is printed as FINAL by the official Week 10 schedule page.
# --------------------------------------------------------------------------

RESULTS_W10 = [
    ("2026-11-12", "WAS", 24, "NYG", 21, "FINAL", "https://www.nfl.com/games/commanders-at-giants-2026-reg-10"),
    ("2026-11-15", "NE", 10, "DET", 35, "FINAL", "https://www.nfl.com/games/patriots-at-lions-2026-reg-10"),
    ("2026-11-15", "KC", 35, "ATL", 13, "FINAL", "https://www.nfl.com/games/chiefs-at-falcons-2026-reg-10"),
    ("2026-11-15", "HOU", 24, "CLE", 27, "FINAL", "https://www.nfl.com/games/texans-at-browns-2026-reg-10"),
    ("2026-11-15", "MIN", 30, "GB", 10, "FINAL", "https://www.nfl.com/games/vikings-at-packers-2026-reg-10"),
    ("2026-11-15", "MIA", 22, "IND", 24, "FINAL", "https://www.nfl.com/games/dolphins-at-colts-2026-reg-10"),
    ("2026-11-15", "CAR", 20, "NO", 17, "FINAL", "https://www.nfl.com/games/panthers-at-saints-2026-reg-10"),
    ("2026-11-15", "BUF", 31, "NYJ", 12, "FINAL", "https://www.nfl.com/games/bills-at-jets-2026-reg-10"),
    ("2026-11-15", "JAX", 40, "TEN", 23, "FINAL", "https://www.nfl.com/games/jaguars-at-titans-2026-reg-10"),
    ("2026-11-15", "LAR", 34, "AZ", 6, "FINAL", "https://www.nfl.com/games/rams-at-cardinals-2026-reg-10"),
    ("2026-11-15", "SEA", 21, "LV", 13, "FINAL", "https://www.nfl.com/games/seahawks-at-raiders-2026-reg-10"),
    ("2026-11-15", "SF", 46, "DAL", 40, "FINAL", "https://www.nfl.com/games/49ers-at-cowboys-2026-reg-10"),
    ("2026-11-15", "PIT", 18, "CIN", 38, "FINAL", "https://www.nfl.com/games/steelers-at-bengals-2026-reg-10"),
    ("2026-11-16", "LAC", 23, "BAL", 20, "FINAL", "https://www.nfl.com/games/chargers-at-ravens-2026-reg-10"),
]

# The Week 10 page marks NE@DET as an International Game played in Munich.
RESULTS_W10_NOTES = {
    "NE@DET": "Official Week 10 schedule page labels this an International Game and prints 'Munich' beside it.",
}

# --------------------------------------------------------------------------
# Register 3 — Week 11 2026 official schedule (fixture context).
#
# Tuple: (kickoff_date, kickoff_et, away, home, network, venue, neutral, source_url)
# `venue` is the stadium string the official page publishes in its own
# on-page hotel deep link for that fixture. It is a transcription of a string
# published by NFL.com, not an independently sourced game-centre read.
# --------------------------------------------------------------------------

SCHEDULE_W11 = [
    ("2026-11-19", "8:15 PM", "IND", "HOU", "Prime Video", "NRG Stadium", "no",
     "https://www.nfl.com/games/colts-at-texans-2026-reg-11"),
    ("2026-11-22", "1:00 PM", "MIA", "BUF", "CBS", "Highmark Stadium", "no",
     "https://www.nfl.com/games/dolphins-at-bills-2026-reg-11"),
    ("2026-11-22", "1:00 PM", "BAL", "CAR", "FOX", "Bank of America Stadium", "no",
     "https://www.nfl.com/games/ravens-at-panthers-2026-reg-11"),
    ("2026-11-22", "1:00 PM", "NO", "CHI", "FOX", "Soldier Field", "no",
     "https://www.nfl.com/games/saints-at-bears-2026-reg-11"),
    ("2026-11-22", "1:00 PM", "TEN", "DAL", "FOX", "AT&T Stadium", "no",
     "https://www.nfl.com/games/titans-at-cowboys-2026-reg-11"),
    ("2026-11-22", "1:00 PM", "TB", "DET", "FOX", "Ford Field", "no",
     "https://www.nfl.com/games/buccaneers-at-lions-2026-reg-11"),
    ("2026-11-22", "1:00 PM", "AZ", "KC", "CBS", "GEHA Field at Arrowhead Stadium", "no",
     "https://www.nfl.com/games/cardinals-at-chiefs-2026-reg-11"),
    ("2026-11-22", "1:00 PM", "PIT", "PHI", "CBS", "Lincoln Financial Field", "no",
     "https://www.nfl.com/games/steelers-at-eagles-2026-reg-11"),
    ("2026-11-22", "4:05 PM", "NYJ", "LAC", "FOX", "SoFi Stadium", "no",
     "https://www.nfl.com/games/jets-at-chargers-2026-reg-11"),
    ("2026-11-22", "4:25 PM", "JAX", "NYG", "CBS", "MetLife Stadium", "no",
     "https://www.nfl.com/games/jaguars-at-giants-2026-reg-11"),
    ("2026-11-22", "4:25 PM", "LV", "DEN", "CBS", "Empower Field at Mile High", "no",
     "https://www.nfl.com/games/raiders-at-broncos-2026-reg-11"),
    ("2026-11-22", "8:20 PM", "MIN", "SF", "NBC", "Mexico City", "yes",
     "https://www.nfl.com/games/vikings-at-49ers-2026-reg-11"),
    ("2026-11-23", "8:15 PM", "CIN", "WAS", "ESPN", "FedEx Field", "no",
     "https://www.nfl.com/games/bengals-at-commanders-2026-reg-11"),
]

# Clubs the official Week 11 page lists under "Teams on Bye".
BYE_W11 = ["ATL", "CLE", "GB", "LAR", "NE", "SEA"]

# --------------------------------------------------------------------------
# Register 4 — 2026 official division standings, as published on capture date.
#
# Tuple: (club, conference, division, w, l, t, pct, pf, pa, net_pts)
# --------------------------------------------------------------------------

STANDINGS = [
    ("BUF", "AFC", "AFC East", 8, 1, 0, 0.889, 287, 199, 88),
    ("NE", "AFC", "AFC East", 5, 5, 0, 0.500, 221, 242, -21),
    ("NYJ", "AFC", "AFC East", 2, 8, 0, 0.200, 194, 254, -60),
    ("MIA", "AFC", "AFC East", 1, 8, 0, 0.111, 148, 224, -76),
    ("CIN", "AFC", "AFC North", 7, 2, 0, 0.778, 278, 193, 85),
    ("PIT", "AFC", "AFC North", 6, 3, 0, 0.667, 198, 182, 16),
    ("CLE", "AFC", "AFC North", 6, 4, 0, 0.600, 188, 220, -32),
    ("BAL", "AFC", "AFC North", 4, 6, 0, 0.400, 209, 259, -50),
    ("JAX", "AFC", "AFC South", 7, 2, 0, 0.778, 269, 144, 125),
    ("HOU", "AFC", "AFC South", 3, 6, 0, 0.333, 233, 219, 14),
    ("IND", "AFC", "AFC South", 3, 7, 0, 0.300, 208, 271, -63),
    ("TEN", "AFC", "AFC South", 1, 8, 0, 0.111, 167, 239, -72),
    ("KC", "AFC", "AFC West", 7, 2, 0, 0.778, 237, 156, 81),
    ("DEN", "AFC", "AFC West", 7, 2, 0, 0.778, 198, 186, 12),
    ("LV", "AFC", "AFC West", 4, 6, 0, 0.400, 251, 289, -38),
    ("LAC", "AFC", "AFC West", 1, 8, 0, 0.111, 144, 239, -95),
    ("NYG", "NFC", "NFC East", 5, 3, 1, 0.611, 203, 196, 7),
    ("DAL", "NFC", "NFC East", 4, 6, 0, 0.400, 286, 282, 4),
    ("WAS", "NFC", "NFC East", 3, 5, 1, 0.389, 196, 223, -27),
    ("PHI", "NFC", "NFC East", 2, 7, 0, 0.222, 148, 221, -73),
    ("DET", "NFC", "NFC North", 7, 2, 0, 0.778, 257, 199, 58),
    ("MIN", "NFC", "NFC North", 7, 2, 0, 0.778, 176, 126, 50),
    ("CHI", "NFC", "NFC North", 7, 2, 0, 0.778, 241, 184, 57),
    ("GB", "NFC", "NFC North", 6, 4, 0, 0.600, 226, 221, 5),
    ("CAR", "NFC", "NFC South", 4, 5, 0, 0.444, 219, 236, -17),
    ("TB", "NFC", "NFC South", 3, 6, 0, 0.333, 202, 178, 24),
    ("NO", "NFC", "NFC South", 3, 6, 0, 0.333, 202, 236, -34),
    ("ATL", "NFC", "NFC South", 3, 7, 0, 0.300, 201, 258, -57),
    ("SF", "NFC", "NFC West", 8, 1, 0, 0.889, 281, 196, 85),
    ("SEA", "NFC", "NFC West", 6, 4, 0, 0.600, 223, 175, 48),
    ("LAR", "NFC", "NFC West", 6, 4, 0, 0.600, 248, 187, 61),
    ("AZ", "NFC", "NFC West", 3, 7, 0, 0.300, 184, 289, -105),
]

# --------------------------------------------------------------------------
# Register 5 — news items the official injury page itself links, used only as
# dated, sourced context for "absent from the report" cases. Each entry is a
# headline published by NFL.com; this register records the headline, not a
# conclusion drawn from it.
# --------------------------------------------------------------------------

INJURY_PAGE_NEWS = [
    ("2026-11-17", "NFL news roundup: Latest league updates from Tuesday, Nov. 17",
     "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-tuesday-nov-17"),
    ("2026-11-16", "NFL news roundup: Vikings WR Jordan Addison needs thumb surgery, could go to IR; Buccaneers add QB",
     "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-monday-nov-16"),
    ("2026-11-16", "NFL Network: Patriots QB Drake Maye could miss rest of 2026 season",
     "https://www.nfl.com/news/nfl-network-patriots-qb-drake-maye-could-miss-rest-of-2026-season"),
    ("2026-11-15", "NFL Network: Lions' Aidan Hutchinson feared to have suffered significant knee injury on sack celebration",
     "https://www.nfl.com/news/lions-aidan-hutchinson-knee-injury-patriots"),
    ("2026-11-15", "NFL Network: Buccaneers QB Baker Mayfield dealing with lower leg injury ahead of Week 11",
     "https://www.nfl.com/news/buccaneers-qb-baker-mayfield-injury-week-11"),
    ("2026-11-15", "Notable injuries, news from Sunday's Week 10 games: Jets QB Geno Smith suffers ankle injury vs. Bills",
     "https://www.nfl.com/news/notable-injuries-news-sunday-week-10-games-2026"),
    ("2026-11-15", "Patriots QB Drake Maye suffers ankle injury early in loss to Lions",
     "https://www.nfl.com/news/patriots-drake-maye-ankle-injury-lions"),
    ("2026-11-14", "NFL news roundup: Patriots place RB TreVeyon Henderson (illness) on injured reserve",
     "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-saturday-nov-14"),
    ("2026-11-13", "NFL news roundup: Ravens confirm Lamar Jackson expected to miss 6-10 weeks; Kenneth Walker questionable",
     "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-friday-nov-13"),
    ("2026-11-11", "NFL news roundup: Browns to start QB Deshaun Watson vs. Texans; Cardinals' Carson Beck to start vs. Rams",
     "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-wednesday-nov-11"),
    ("2026-11-11", "Dolphins place QB Malik Willis (groin) on injured reserve; Kyle McCord in line for first start",
     "https://www.nfl.com/news/dolphins-place-qb-malik-willis-groin-on-injured-reserve-kyle-mccord-in-line-for-first-start"),
    ("2026-11-10", "NFL news roundup: Bills acquire S Amani Hooker; Broncos trade for Chargers' Daiyan Henley",
     "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-tuesday-nov-10"),
    ("2026-11-09", "Rams WR Puka Nacua likely to be placed on injured reserve with turf toe, sprained MCL and PCL",
     "https://www.nfl.com/news/rams-wr-puka-nacua-likely-to-be-placed-on-injured-reserve-with-turf-toe-sprained-mcl-and-pcl"),
    ("2026-11-09", "Packers RB Josh Jacobs to undergo surgery on finger this week; timeline to return TBD",
     "https://www.nfl.com/news/packers-rb-josh-jacobs-to-undergo-surgery-on-finger-this-week"),
    ("2026-11-09", "Sam Darnold ruled out for Seahawks' Week 10 game vs. Raiders; Drew Lock expected to start again",
     "https://www.nfl.com/news/sam-darnold-ruled-out-for-seahawks-week-10-game-vs-raiders-drew-lock-expected-to-start-again"),
    ("2026-11-08", "NFL Network: Ravens' Lamar Jackson (right thumb) out 6-9 weeks, expects to return this season",
     "https://www.nfl.com/news/ravens-lamar-jackson-right-thumb-out-6-9-weeks-expects-to-return-this-season"),
    ("2026-11-07", "NFL Week 9 inactives: Players ruled out for Sunday's 13 games",
     "https://www.nfl.com/news/nfl-week-9-inactives-players-ruled-out-sunday-2026-season"),
    ("2026-11-06", "NFL news roundup: Saints waive Kendre Miller; Cowboys place Malachi Lawrence on IR",
     "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-saturday-nov-7"),
    ("2026-11-05", "NFL news roundup: Jets' Garrett Wilson ruled out; Falcons RB Brian Robinson out for Madrid game",
     "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-friday-nov-6"),
    ("2026-11-05", "NFL news roundup: Latest league updates from Thursday, Nov. 12",
     "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-thursday-nov-12"),
]

# --------------------------------------------------------------------------
# Writers
# --------------------------------------------------------------------------


def _sha256_rows(header, rows):
    body = "\n".join(["|".join(str(c) for c in header)] +
                     ["|".join(str(c) for c in r) for r in rows])
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _write_csv(name, header, rows):
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, name)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path, _sha256_rows(header, rows)


def build():
    os.makedirs(DATA, exist_ok=True)
    manifest = {
        "capture_utc": CAPTURE_UTC,
        "capture_method": CAPTURE_METHOD,
        "sources": SOURCES,
        "registers": {},
    }

    p, h = _write_csv(
        "injury_report_2026_w10.csv",
        ["game_slot", "club", "player", "position", "injury",
         "practice_status", "game_status"],
        INJURY_ROWS,
    )
    manifest["registers"]["injury_report_2026_w10"] = {
        "file": "data/injury_report_2026_w10.csv",
        "rows": len(INJURY_ROWS),
        "sha256": h,
        "source_url": SOURCES["injury_w10"]["url"],
        "captured_utc": CAPTURE_UTC,
    }

    p, h = _write_csv(
        "results_2026_w10.csv",
        ["date", "away", "away_points", "home", "home_points", "status", "source_url"],
        RESULTS_W10,
    )
    manifest["registers"]["results_2026_w10"] = {
        "file": "data/results_2026_w10.csv",
        "rows": len(RESULTS_W10),
        "sha256": h,
        "source_url": SOURCES["sched_w10"]["url"],
        "captured_utc": CAPTURE_UTC,
    }

    p, h = _write_csv(
        "schedule_2026_w11.csv",
        ["date", "kickoff_et", "away", "home", "network", "venue",
         "neutral_site", "source_url"],
        SCHEDULE_W11,
    )
    manifest["registers"]["schedule_2026_w11"] = {
        "file": "data/schedule_2026_w11.csv",
        "rows": len(SCHEDULE_W11),
        "sha256": h,
        "source_url": SOURCES["sched_w11"]["url"],
        "captured_utc": CAPTURE_UTC,
        "bye_clubs": BYE_W11,
    }

    p, h = _write_csv(
        "standings_2026.csv",
        ["club", "conference", "division", "wins", "losses", "ties",
         "pct", "points_for", "points_against", "net_points"],
        STANDINGS,
    )
    manifest["registers"]["standings_2026"] = {
        "file": "data/standings_2026.csv",
        "rows": len(STANDINGS),
        "sha256": h,
        "source_url": SOURCES["standings"]["url"],
        "captured_utc": CAPTURE_UTC,
    }

    p, h = _write_csv(
        "absent_clubs_2026_w10.csv",
        ["club", "reason_as_published", "source_url"],
        INJURY_ABSENT_CLUBS,
    )
    manifest["registers"]["absent_clubs_2026_w10"] = {
        "file": "data/absent_clubs_2026_w10.csv",
        "rows": len(INJURY_ABSENT_CLUBS),
        "sha256": h,
        "source_url": SOURCES["sched_w10"]["url"],
        "captured_utc": CAPTURE_UTC,
    }

    p, h = _write_csv(
        "injury_page_news_2026.csv",
        ["news_date", "headline", "source_url"],
        INJURY_PAGE_NEWS,
    )
    manifest["registers"]["injury_page_news_2026"] = {
        "file": "data/injury_page_news_2026.csv",
        "rows": len(INJURY_PAGE_NEWS),
        "sha256": h,
        "source_url": SOURCES["injury_w10"]["url"],
        "captured_utc": CAPTURE_UTC,
    }

    manifest_path = os.path.join(DATA, "capture_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return manifest


if __name__ == "__main__":
    m = build()
    for key, reg in m["registers"].items():
        print(f"{key}: {reg['rows']} rows  sha256={reg['sha256'][:16]}...")
    print(f"manifest: {os.path.join(DATA, 'capture_manifest.json')}")
