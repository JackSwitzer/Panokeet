#!/usr/bin/env python3
"""
Panokeet - Voice-to-text with training data collection.
Simple terminal version with global hotkeys.
"""

import subprocess
import tempfile
import wave
import shutil
import json
import os
from pathlib import Path
from datetime import datetime
from threading import Thread, Event
import time

import numpy as np
import sounddevice as sd
from AppKit import NSSound, NSPasteboard, NSPasteboardTypeString
from Quartz import (
    CGEventTapCreate, CGEventMaskBit, kCGEventKeyDown, kCGEventKeyUp,
    kCGHIDEventTap, kCGHeadInsertEventTap, kCGEventTapOptionDefault,
    kCGEventTapOptionListenOnly,
    CFMachPortCreateRunLoopSource, CFRunLoopGetCurrent, CFRunLoopAddSource,
    CFRunLoopRun, kCFRunLoopCommonModes, CGEventGetIntegerValueField,
    kCGKeyboardEventKeycode, CGEventTapEnable
)

# Paths
APP_DIR = Path(__file__).parent
MODEL_PATH = APP_DIR / "models" / "ggml-medium.bin"
DATA_DIR = APP_DIR / "training_data"
CONFIG_FILE = APP_DIR / "config.json"

SAMPLE_RATE = 16000
THREADS = 4

# State
recording = False
audio_data = []
stream = None
hold_key_pressed = False
config = {"toggle_key": None, "hold_key": None}


def play_sound(name):
    sounds = {"start": "Morse", "stop": "Tink", "done": "Glass"}
    s = NSSound.soundNamed_(sounds.get(name, ""))
    if s:
        s.play()


def start_recording():
    global recording, audio_data, stream
    if recording:
        return

    audio_data = []
    recording = True

    def callback(indata, frames, time, status):
        if recording:
            audio_data.append(indata.copy())

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype=np.float32, callback=callback)
    stream.start()
    play_sound("start")
    print("\n🔴 Recording... (press toggle key or release hold key to stop)")


def stop_recording():
    global recording, stream
    if not recording:
        return

    recording = False
    play_sound("stop")

    if stream:
        stream.stop()
        stream.close()
        stream = None

    if not audio_data:
        print("No audio captured")
        return

    print("⏳ Transcribing...")

    # Save audio
    audio = np.concatenate(audio_data, axis=0)
    duration = len(audio) / SAMPLE_RATE

    temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    audio_int16 = (audio * 32767).astype(np.int16)
    with wave.open(temp.name, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())

    # Transcribe
    result = subprocess.run(
        ["nice", "-n", "10", "whisper-cli", "-m", str(MODEL_PATH),
         "-f", temp.name, "--no-timestamps", "-t", str(THREADS), "-l", "en"],
        capture_output=True, text=True
    )

    text = ' '.join([l.strip() for l in result.stdout.strip().split('\n') if l.strip()])

    if text:
        play_sound("done")
        print(f"\n📝 Transcription ({duration:.1f}s):")
        print(f"   {text}")

        # Save to training data
        DATA_DIR.mkdir(exist_ok=True)
        existing = list(DATA_DIR.glob("audio_*.wav"))
        num = max([int(f.stem.split('_')[1]) for f in existing], default=0) + 1

        audio_dest = DATA_DIR / f"audio_{num:06d}.wav"
        text_dest = DATA_DIR / f"audio_{num:06d}.txt"

        shutil.move(temp.name, str(audio_dest))
        text_dest.write_text(text)

        # Copy to clipboard
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(text, NSPasteboardTypeString)

        print(f"💾 Saved: audio_{num:06d}")
        print("📋 Copied to clipboard!")
    else:
        print("❌ No speech detected")
        os.unlink(temp.name)

    print("\n🎤 Ready. Waiting for hotkey...")


def calibrate():
    """Capture hotkeys from user."""
    global config

    print("\n" + "="*50)
    print("🔧 HOTKEY CALIBRATION")
    print("="*50)

    # Toggle key
    print("\nPress the key for TOGGLE (start/stop recording)...")
    toggle = capture_key()
    if toggle:
        config["toggle_key"] = toggle
        print(f"✓ Toggle key: keycode {toggle}")

    # Hold key
    print("\nPress the key for HOLD-TO-SPEAK...")
    hold = capture_key()
    if hold:
        config["hold_key"] = hold
        print(f"✓ Hold key: keycode {hold}")

    # Save
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

    print("\n✅ Calibration complete! Keys saved.")
    print("="*50)


def capture_key():
    """Capture a single keypress."""
    result = {"key": None, "done": False}

    def callback(proxy, event_type, event, refcon):
        if event_type == kCGEventKeyDown and not result["done"]:
            result["key"] = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            result["done"] = True
        return event

    tap = CGEventTapCreate(
        kCGHIDEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly,
        CGEventMaskBit(kCGEventKeyDown), callback, None
    )

    if not tap:
        print("❌ No accessibility permission!")
        return None

    source = CFMachPortCreateRunLoopSource(None, tap, 0)
    CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopCommonModes)
    CGEventTapEnable(tap, True)

    # Wait for key
    start = time.time()
    while not result["done"] and time.time() - start < 10:
        time.sleep(0.1)

    CGEventTapEnable(tap, False)
    return result["key"]


def hotkey_callback(proxy, event_type, event, refcon):
    global hold_key_pressed

    keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
    toggle_key = config.get("toggle_key")
    hold_key = config.get("hold_key")

    if event_type == kCGEventKeyDown:
        if keycode == toggle_key:
            if recording:
                Thread(target=stop_recording, daemon=True).start()
            else:
                start_recording()
        elif keycode == hold_key and not hold_key_pressed:
            hold_key_pressed = True
            start_recording()

    elif event_type == kCGEventKeyUp:
        if keycode == hold_key and hold_key_pressed:
            hold_key_pressed = False
            Thread(target=stop_recording, daemon=True).start()

    return event


def main():
    global config

    print("\n" + "="*50)
    print("🦜 PANOKEET - Voice to Text")
    print("="*50)
    print(f"Model: {MODEL_PATH.name}")
    print(f"Saving to: {DATA_DIR}/")

    # Load config
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config = json.load(f)

    # Check if calibrated
    if not config.get("toggle_key") and not config.get("hold_key"):
        print("\n⚠️  No hotkeys configured!")
        calibrate()
    else:
        print(f"\nHotkeys: Toggle={config.get('toggle_key')}, Hold={config.get('hold_key')}")
        print("(Run with --calibrate to change)")

    # Set up hotkey listener (listen-only requires Input Monitoring permission)
    mask = CGEventMaskBit(kCGEventKeyDown) | CGEventMaskBit(kCGEventKeyUp)
    tap = CGEventTapCreate(
        kCGHIDEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly,
        mask, hotkey_callback, None
    )

    if not tap:
        print("\n❌ Cannot create event tap!")
        print("Add Python to: System Settings → Privacy & Security → Input Monitoring")
        print("Path: /Users/jackswitzer/.local/share/uv/python/cpython-3.13.6-macos-aarch64-none/bin/python3.13")
        return

    source = CFMachPortCreateRunLoopSource(None, tap, 0)
    CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopCommonModes)
    CGEventTapEnable(tap, True)

    print("\n🎤 Ready! Waiting for hotkey...")
    print("Press Ctrl+C to quit.\n")

    try:
        CFRunLoopRun()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")


if __name__ == "__main__":
    import sys
    if "--calibrate" in sys.argv:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                config = json.load(f)
        calibrate()
    else:
        main()
