#!/usr/bin/env python3
"""
Panokeet - Voice to Text with Global Hotkeys

Hotkeys (via Karabiner remapping):
  Cmd+Keypad7 → F13 = Toggle recording
  Cmd+Keypad8 → F14 = Hold to speak

Workflow:
  Record → Transcribe → Copy to clipboard → Save to training_data/
"""

import subprocess
import tempfile
import wave
import shutil
import os
from pathlib import Path
from threading import Thread

import numpy as np
import sounddevice as sd
from AppKit import NSSound, NSPasteboard, NSPasteboardTypeString
from Quartz import (
    CGEventTapCreate, CGEventMaskBit, kCGEventKeyDown, kCGEventKeyUp,
    kCGHIDEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly,
    CFMachPortCreateRunLoopSource, CFRunLoopGetCurrent, CFRunLoopAddSource,
    CFRunLoopRun, kCFRunLoopCommonModes, CGEventGetIntegerValueField,
    kCGKeyboardEventKeycode, CGEventTapEnable
)

# Paths
APP_DIR = Path(__file__).parent
MODEL_PATH = APP_DIR / "models" / "ggml-medium.bin"
DATA_DIR = APP_DIR / "training_data"
SAMPLE_RATE = 16000

# F-key keycodes (via Karabiner remap from Cmd+Keypad)
F13_KEYCODE = 105  # Toggle recording
F14_KEYCODE = 107  # Hold to speak


class Panokeet:
    def __init__(self):
        self.recording = False
        self.audio_data = []
        self.stream = None
        self.hold_active = False

    def play_sound(self, name):
        """Play system sounds for feedback."""
        sounds = {"start": "Morse", "stop": "Tink", "done": "Glass", "error": "Basso"}
        s = NSSound.soundNamed_(sounds.get(name, ""))
        if s:
            s.play()

    def start_recording(self):
        """Start audio recording."""
        if self.recording:
            return

        self.audio_data = []
        self.recording = True

        def callback(indata, frames, t, status):
            if self.recording:
                self.audio_data.append(indata.copy())

        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype=np.float32,
            callback=callback
        )
        self.stream.start()
        self.play_sound("start")
        print("\n🔴 Recording...")

    def stop_recording(self):
        """Stop recording and transcribe."""
        if not self.recording:
            return

        self.recording = False
        self.play_sound("stop")

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if not self.audio_data:
            print("No audio captured")
            return

        print("⏳ Transcribing...")
        Thread(target=self._process_audio, daemon=True).start()

    def _process_audio(self):
        """Process and transcribe audio in background."""
        audio = np.concatenate(self.audio_data, axis=0)
        duration = len(audio) / SAMPLE_RATE

        # Save to temp file
        temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        audio_int16 = (audio * 32767).astype(np.int16)
        with wave.open(temp.name, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())

        # Transcribe with whisper
        result = subprocess.run(
            ["whisper-cli", "-m", str(MODEL_PATH), "-f", temp.name,
             "--no-timestamps", "-t", "4", "-l", "en"],
            capture_output=True, text=True
        )
        text = ' '.join([l.strip() for l in result.stdout.strip().split('\n') if l.strip()])

        if text:
            self.play_sound("done")
            print(f"\n📝 {text}")

            # Save to training data
            DATA_DIR.mkdir(exist_ok=True)
            existing = list(DATA_DIR.glob("audio_*.wav"))
            num = max([int(f.stem.split('_')[1]) for f in existing], default=0) + 1

            shutil.move(temp.name, str(DATA_DIR / f"audio_{num:06d}.wav"))
            (DATA_DIR / f"audio_{num:06d}.txt").write_text(text)

            # Copy to clipboard
            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.setString_forType_(text, NSPasteboardTypeString)

            print(f"💾 Saved audio_{num:06d} ({duration:.1f}s) | 📋 Copied!")
        else:
            self.play_sound("error")
            print("❌ No speech detected")
            os.unlink(temp.name)

        print("\n🎤 Ready... (Cmd+Keypad7 to toggle, Cmd+Keypad8 to hold)")


# Global app instance
app = None


def event_callback(proxy, event_type, event, refcon):
    """CGEventTap callback for global hotkeys."""
    global app

    keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)

    if event_type == kCGEventKeyDown:
        if keycode == F13_KEYCODE:
            # Toggle mode
            if app.recording:
                app.stop_recording()
            else:
                app.start_recording()
        elif keycode == F14_KEYCODE and not app.hold_active:
            # Hold mode - start on press
            app.hold_active = True
            app.start_recording()

    elif event_type == kCGEventKeyUp:
        if keycode == F14_KEYCODE and app.hold_active:
            # Hold mode - stop on release
            app.hold_active = False
            app.stop_recording()

    return event


def main():
    global app

    print("\n" + "=" * 60)
    print("🦜 PANOKEET - Voice to Text")
    print("=" * 60)
    print(f"Model: {MODEL_PATH.name}")
    print(f"Saving to: {DATA_DIR}/")
    print("\nHotkeys (via Karabiner):")
    print("  Cmd+Keypad7 → Toggle recording")
    print("  Cmd+Keypad8 → Hold to speak")
    print("=" * 60)

    DATA_DIR.mkdir(exist_ok=True)
    app = Panokeet()

    # Create CGEventTap for global hotkey capture
    mask = CGEventMaskBit(kCGEventKeyDown) | CGEventMaskBit(kCGEventKeyUp)
    tap = CGEventTapCreate(
        kCGHIDEventTap,
        kCGHeadInsertEventTap,
        kCGEventTapOptionListenOnly,
        mask,
        event_callback,
        None
    )

    if not tap:
        print("\n❌ Cannot create event tap!")
        print("Check: System Settings → Privacy & Security → Input Monitoring")
        print("Add Terminal (or the Python executable) to the list.")
        return

    # Set up run loop
    source = CFMachPortCreateRunLoopSource(None, tap, 0)
    CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopCommonModes)
    CGEventTapEnable(tap, True)

    print("\n✓ Global hotkey capture active (CGEventTap)")
    print("\n🎤 Ready! Press Cmd+Keypad7 to start recording...")
    print("Press Ctrl+C to quit.\n")

    try:
        CFRunLoopRun()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()
