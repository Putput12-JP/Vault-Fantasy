#!/bin/sh
# Install the SmartStake recorder as two launchd jobs: NBA every 5 minutes, NFL every 15.
#   sh scripts/smartstake_launchd.sh            # recorder jobs (and refresh the copies)
#   sh scripts/smartstake_launchd.sh publish    # ONLY the publish job: every 5 minutes (minutes 2, 7, 12 ...), after each NBA record, runs
#                                               # smartstake_publish_alts.py (alt prices -> the owner's Firestore). Needs ~/.config/smartstake/firebase-sa.json.
#                                               # Stop it with: launchctl bootout gui/$(id -u)/com.vault.smartstake-publish, or touch ~/.config/smartstake/publish.off
# The jobs run a copy under ~/.config/smartstake/bin, so switching branches in the checkout cannot break them.
# Re-run this script after changing the recorder scripts to refresh the copy. Logs: ~/Library/Logs/smartstake-<league>.log
set -e
REPO=$(cd "$(dirname "$0")/.." && pwd)
CHECKOUT=${SMARTSTAKE_CHECKOUT:-/Users/jacobputman/Desktop/Draft Tool}
BIN=$HOME/.config/smartstake/bin
PY=/opt/homebrew/bin/python3
mkdir -p "$BIN/scripts" "$HOME/Library/Logs" "$HOME/Library/LaunchAgents"

if [ "$1" = "publish" ]; then
  for f in smartstake_publish_alts smartstake_alts combo_calls smartstake_props smartstake_to_book_tape; do
    cp "$REPO/scripts/$f.py" "$BIN/scripts/$f.py"
  done
  ln -sfn "$CHECKOUT/data" "$BIN/data"
  label=com.vault.smartstake-publish
  cal=""; for m in 2 7 12 17 22 27 32 37 42 47 52 57; do cal="$cal<dict><key>Minute</key><integer>$m</integer></dict>"; done
  cat > "$HOME/Library/LaunchAgents/$label.plist" <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>$label</string>
<key>ProgramArguments</key><array><string>$PY</string><string>$BIN/scripts/smartstake_publish_alts.py</string></array>
<key>WorkingDirectory</key><string>$BIN</string>
<key>EnvironmentVariables</key><dict><key>PATH</key><string>/usr/bin:/bin:/opt/homebrew/bin</string></dict>
<key>StartCalendarInterval</key><array>$cal</array>
<key>StandardOutPath</key><string>$HOME/Library/Logs/smartstake-publish.log</string>
<key>StandardErrorPath</key><string>$HOME/Library/Logs/smartstake-publish.log</string>
</dict></plist>
P
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/$label.plist"
  launchctl list | grep smartstake-publish
  exit 0
fi
for f in smartstake_run_locked smartstake_record smartstake_client smartstake_props smartstake_to_book_tape; do
  cp "$REPO/scripts/$f.py" "$BIN/scripts/$f.py"
done
# the tape and book_tape live in the checkout's data folder; the copy reaches them through this link
ln -sfn "$CHECKOUT/data" "$BIN/data"

plist() { # label league minutes...
  label=$1; lg=$2; shift 2
  cal=""
  for m in "$@"; do cal="$cal<dict><key>Minute</key><integer>$m</integer></dict>"; done
  cat > "$HOME/Library/LaunchAgents/$label.plist" <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>$label</string>
<key>ProgramArguments</key><array><string>$PY</string><string>$BIN/scripts/smartstake_run_locked.py</string><string>$lg</string></array>
<key>WorkingDirectory</key><string>$BIN</string>
<key>StartCalendarInterval</key><array>$cal</array>
<key>StandardOutPath</key><string>$HOME/Library/Logs/smartstake-$lg.log</string>
<key>StandardErrorPath</key><string>$HOME/Library/Logs/smartstake-$lg.log</string>
</dict></plist>
P
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/$label.plist"
}

launchctl bootout "gui/$(id -u)/com.vault.smartstake-record" 2>/dev/null || true   # the old combined job
mv "$HOME/Library/LaunchAgents/com.vault.smartstake-record.plist" "$HOME/Library/LaunchAgents/com.vault.smartstake-record.plist.old" 2>/dev/null || true
plist com.vault.smartstake-nba nba 0 5 10 15 20 25 30 35 40 45 50 55
plist com.vault.smartstake-nfl nfl 2 17 32 47
launchctl list | grep smartstake
