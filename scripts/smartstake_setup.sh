#!/bin/sh
# Save the SmartStake key from the clipboard to ~/.config/smartstake/key (mode 600).
# Copy the key first, then run this. The key never enters the repo.
set -e
k=$(pbpaste | tr -d '[:space:]')
[ -n "$k" ] || { echo "Clipboard is empty: copy your key first"; exit 1; }
mkdir -p ~/.config/smartstake
printf '%s' "$k" > ~/.config/smartstake/key
chmod 600 ~/.config/smartstake/key
echo "saved (${#k} characters)"
pbcopy < /dev/null  # clear the clipboard
