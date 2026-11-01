#!/usr/bin/env bash
# Fetch the (only) data this environment can reach: public GitHub repositories.
# Everything is pinned by commit SHA so a re-run is byte-reproducible.
#
# Source: nflverse/nfldata — an open, documented mirror that the nflverse project builds from
#         official NFL gamebooks (scores, dates, rest, roof/surface) and from sportsbook
#         closing lines (spread_line, total_line, moneylines). See data/sources.json.
# Pinned commit: a270278f3ac4e937295fe6a27814b3c4a2b62645 (nflverse/nfldata, branch master)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW="$ROOT/data/raw"
SHA="a270278f3ac4e937295fe6a27814b3c4a2b62645"
mkdir -p "$RAW"
TMP="$(mktemp -d)"
echo "Downloading nflverse/nfldata @ $SHA ..."
curl -sSL --fail --retry 3 -o "$TMP/nfldata.tgz" \
  "https://codeload.github.com/nflverse/nfldata/tar.gz/$SHA"
tar xzf "$TMP/nfldata.tgz" -C "$TMP"
mkdir -p "$RAW/nfldata"
for f in games.csv closing_lines.csv teams.csv standings.csv initial_lines.csv; do
  cp "$TMP"/nfldata-*/data/"$f" "$RAW/nfldata/$f"
done
# record provenance
{
  echo "source=https://github.com/nflverse/nfldata"
  echo "commit=$SHA"
  echo "fetched_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "files=games.csv,closing_lines.csv,teams.csv,standings.csv,initial_lines.csv"
} > "$RAW/nfldata/PROVENANCE.txt"
sha256sum "$RAW"/nfldata/*.csv >> "$RAW/nfldata/PROVENANCE.txt"
rm -rf "$TMP"
echo "OK -> $RAW/nfldata"
