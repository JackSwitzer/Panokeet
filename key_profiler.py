#!/usr/bin/env python3
"""
Key Profiler - Shows exactly what keycodes and modifiers your keyboard sends.
Press any key to see its details. Press Ctrl+C to quit.
"""

from AppKit import (
    NSApplication, NSApp, NSEvent, NSKeyDownMask, NSKeyUpMask,
    NSApplicationActivationPolicyAccessory,
    NSCommandKeyMask, NSShiftKeyMask, NSAlternateKeyMask, NSControlKeyMask,
    NSNumericPadKeyMask, NSFunctionKeyMask
)
from PyObjCTools import AppHelper

# Store monitors globally to prevent garbage collection
monitors = []

def on_key_down(event):
    keycode = event.keyCode()
    flags = event.modifierFlags()
    chars = event.charactersIgnoringModifiers() or ""

    # Decode modifier flags
    mods = []
    if flags & NSCommandKeyMask:
        mods.append("Cmd")
    if flags & NSShiftKeyMask:
        mods.append("Shift")
    if flags & NSAlternateKeyMask:
        mods.append("Opt")
    if flags & NSControlKeyMask:
        mods.append("Ctrl")
    if flags & NSNumericPadKeyMask:
        mods.append("NumPad")
    if flags & NSFunctionKeyMask:
        mods.append("Fn")

    mod_str = "+".join(mods) if mods else "(none)"

    print(f"┌─────────────────────────────────────────")
    print(f"│ Keycode: {keycode}")
    print(f"│ Character: '{chars}'")
    print(f"│ Modifiers: {mod_str}")
    print(f"│ Raw flags: 0x{flags:08x}")
    print(f"│")
    print(f"│ Config format: ", end="")

    config_mods = []
    if flags & NSCommandKeyMask:
        config_mods.append("cmd")
    if flags & NSShiftKeyMask:
        config_mods.append("shift")
    if flags & NSAlternateKeyMask:
        config_mods.append("opt")
    if flags & NSControlKeyMask:
        config_mods.append("ctrl")

    if config_mods:
        print(f"{'+'.join(config_mods)}+{keycode}")
    else:
        print(f"{keycode}")
    print(f"└─────────────────────────────────────────\n")

    return event

def main():
    global monitors

    print("\n" + "="*60)
    print("🔍 KEY PROFILER - Press keys to see their codes")
    print("="*60)
    print("Press Ctrl+C to quit\n")

    NSApplication.sharedApplication()
    NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    # Store monitor references to prevent garbage collection
    monitor1 = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSKeyDownMask, on_key_down)
    monitors.append(monitor1)

    if monitor1:
        print("✓ Global key monitor installed successfully")
    else:
        print("✗ Failed to install global key monitor!")
        print("  Check: System Settings → Privacy & Security → Input Monitoring")
        return

    print("Listening for keypresses in ANY app...\n")

    try:
        AppHelper.runConsoleEventLoop()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()
