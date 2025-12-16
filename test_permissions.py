#!/usr/bin/env python3
"""Test if we have accessibility permissions for event tap."""

from Quartz import (
    CGEventTapCreate, CGEventMaskBit, kCGEventKeyDown,
    kCGHIDEventTap, kCGHeadInsertEventTap, kCGEventTapOptionDefault
)

def test_callback(proxy, event_type, event, refcon):
    return event

# Try to create event tap
mask = CGEventMaskBit(kCGEventKeyDown)
tap = CGEventTapCreate(
    kCGHIDEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionDefault,
    mask,
    test_callback,
    None
)

if tap is None:
    print("❌ NO PERMISSION - Event tap failed")
    print("")
    print("You need to add Python to Accessibility:")
    print("1. System Settings → Privacy & Security → Accessibility")
    print("2. Click + button")
    print("3. Press Cmd+Shift+G and paste:")
    print("   /Users/jackswitzer/Desktop/Panokeet/.venv/bin/python3")
    print("4. Click Open, then enable the toggle")
else:
    print("✅ PERMISSION OK - Event tap works!")
    print("Hotkeys should work now.")
