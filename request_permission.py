#!/usr/bin/env python3
"""Request accessibility permission properly using macOS API."""

import objc
from ApplicationServices import AXIsProcessTrustedWithOptions
from Foundation import NSDictionary

# This key tells macOS to show the prompt
kAXTrustedCheckOptionPrompt = "AXTrustedCheckOptionPrompt"

# Request permission with prompt
options = NSDictionary.dictionaryWithObject_forKey_(True, kAXTrustedCheckOptionPrompt)
trusted = AXIsProcessTrustedWithOptions(options)

if trusted:
    print("✅ Accessibility permission GRANTED!")
    print("You can now run: uv run python panokeet.py")
else:
    print("⚠️  Permission dialog should have appeared.")
    print("")
    print("If you see a dialog, click 'Open System Settings'")
    print("Then enable the toggle for Python.")
    print("")
    print("After enabling, run this again to verify.")
