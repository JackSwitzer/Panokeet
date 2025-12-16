#!/bin/bash
# Install Whisper Dictate to start on login

PLIST_SRC="/Users/jackswitzer/Desktop/Panokeet/com.panokeet.whisper-dictate.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.panokeet.whisper-dictate.plist"

# Create LaunchAgents dir if needed
mkdir -p "$HOME/Library/LaunchAgents"

# Copy plist
cp "$PLIST_SRC" "$PLIST_DST"

# Load it
launchctl load "$PLIST_DST"

echo "✓ Whisper Dictate installed!"
echo "  It will start automatically on login."
echo ""
echo "To start now: launchctl start com.panokeet.whisper-dictate"
echo "To stop:      launchctl stop com.panokeet.whisper-dictate"
echo "To uninstall: launchctl unload $PLIST_DST && rm $PLIST_DST"
