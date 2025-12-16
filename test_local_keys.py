#!/usr/bin/env python3
"""
Test if we can capture keys when the app is focused (local monitor).
This tests if PyObjC is working at all.
"""

from AppKit import (
    NSApplication, NSApp, NSEvent, NSKeyDownMask,
    NSApplicationActivationPolicyRegular,
    NSCommandKeyMask, NSAlternateKeyMask, NSControlKeyMask
)
from PyObjCTools import AppHelper

def main():
    print("\n" + "="*60)
    print("🔍 LOCAL KEY TEST - Click this terminal window first!")
    print("="*60)
    print("This only captures keys when Terminal is focused.")
    print("Press Escape to quit\n")

    NSApplication.sharedApplication()
    # Use Regular policy so we can receive local events
    NSApp.setActivationPolicy_(NSApplicationActivationPolicyRegular)

    def on_key_down(event):
        keycode = event.keyCode()
        flags = event.modifierFlags()

        mods = []
        if flags & NSCommandKeyMask:
            mods.append("Cmd")
        if flags & NSAlternateKeyMask:
            mods.append("Opt")
        if flags & NSControlKeyMask:
            mods.append("Ctrl")

        mod_str = "+".join(mods) if mods else ""
        if mod_str:
            print(f"Key: {mod_str}+{keycode}")
        else:
            print(f"Key: {keycode}")

        if keycode == 53:
            print("Escape pressed, quitting...")
            AppHelper.stopEventLoop()

        return event

    # Try LOCAL monitor (only works when app is focused)
    NSEvent.addLocalMonitorForEventsMatchingMask_handler_(NSKeyDownMask, on_key_down)

    print("Listening... (make sure Terminal is focused)\n")

    try:
        AppHelper.runConsoleEventLoop()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()
