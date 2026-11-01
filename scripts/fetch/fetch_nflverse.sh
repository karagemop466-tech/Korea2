#!/usr/bin/env bash
# Manifest of the nflverse assets this project consumes. The authoritative,
# executable copy of these URLs is .github/workflows/fetch-nflverse.yml.
#
#   games.csv                      nflverse schedules release
#                                  -> final scores, closing spread_line / total_line, prices
#   stats_team_week_<year>.csv     nflverse team-week release (NFL GSIS play-by-play aggregates)
#   stats_player_week_<year>.csv   nflverse player-week release (basis for prop research)
#
# nflverse publishes machine-readable extracts of the NFL's official play-by-play
# and box scores. It is a data redistributor, not the league itself; every headline
# figure in this project is cross-checked against NFL.com on the Verification page.
echo "See .github/workflows/fetch-nflverse.yml"
