#!/bin/sh
# Copy the SmartStake scripts the 5-minute launchd job runs into ~/.config/smartstake/bin/scripts, from this checkout.
#
# WHY: com.vault.smartstake-publish runs a COPY of the scripts, not the repo (bin/data is a symlink to the repo's data/, the scripts are not).
# A merged change to any of them does nothing on the Mac until it is copied. On 2026-10-22 the copy was two days old: it had no Bankroll Builder and no
# Combo Check pick list, so neither updated or settled until this was run.
#
#   sh scripts/sync_smartstake_job.sh          # backs the old copies up, copies the new ones, links nba/, prints what changed
#
# Run it from a checkout on main, after pulling (SYNC_ALLOW_BRANCH=1 overrides the check, for testing only). The job uses nba/scripts (the model code) through a symlink, so that code follows the checkout too.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="$HOME/.config/smartstake"
BIN="$CONF/bin"
FILES="combo_calls.py smartstake_publish_alts.py bankroll_builder.py smartstake_alts.py smartstake_props.py smartstake_to_book_tape.py"
if [ "$(git -C "$ROOT" branch --show-current)" != "main" ] && [ -z "$SYNC_ALLOW_BRANCH" ]; then
  echo "Not on main: the job would run unmerged code. Check out main and pull first." >&2
  exit 1
fi
BAK="$CONF/bin-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BAK" "$BIN/scripts"
for f in $FILES; do
  [ -f "$BIN/scripts/$f" ] && cp "$BIN/scripts/$f" "$BAK/$f"
  if [ -f "$BIN/scripts/$f" ] && cmp -s "$ROOT/scripts/$f" "$BIN/scripts/$f"; then
    echo "same     $f"
  else
    cp "$ROOT/scripts/$f" "$BIN/scripts/$f"
    echo "updated  $f"
  fi
done
[ -e "$BIN/nba" ] || ln -s "$ROOT/nba" "$BIN/nba"
[ -e "$BIN/data" ] || ln -s "$ROOT/data" "$BIN/data"
echo "old copies saved in $BAK"
