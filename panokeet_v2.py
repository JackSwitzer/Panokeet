#!/usr/bin/env python3
"""
Panokeet v2 - Using NSEvent for hotkeys (different permission model)
"""

import subprocess
import tempfile
import wave
import shutil
import json
import os
from pathlib import Path
from threading import Thread
import time

import numpy as np
import sounddevice as sd
import objc
from AppKit import (
    NSApplication, NSApp, NSEvent, NSKeyDownMask, NSKeyUpMask,
    NSSound, NSPasteboard, NSPasteboardTypeString,
    NSApplicationActivationPolicyAccessory
)
from PyObjCTools import AppHelper

APP_DIR = Path(__file__).parent
MODEL_PATH = APP_DIR / "models" / "ggml-medium.bin"
DATA_DIR = APP_DIR / "training_data"
CONFIG_FILE = APP_DIR / "config.json"
SAMPLE_RATE = 16000

class Panokeet:
    def __init__(self):
        self.recording = False
        self.audio_data = []
        self.stream = None
        self.config = self.load_config()
        self.hold_active = False

    def load_config(self):
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                return json.load(f)
        return {"toggle_key": 18, "hold_key": 19}  # Default: 1 and 2 keys

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f)

    def play_sound(self, name):
        sounds = {"start": "Morse", "stop": "Tink", "done": "Glass"}
        s = NSSound.soundNamed_(sounds.get(name, ""))
        if s:
            s.play()

    def start_recording(self):
        if self.recording:
            return

        self.audio_data = []
        self.recording = True

        def callback(indata, frames, t, status):
            if self.recording:
                self.audio_data.append(indata.copy())

        self.stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                      dtype=np.float32, callback=callback)
        self.stream.start()
        self.play_sound("start")
        print("\n🔴 Recording...")

    def stop_recording(self):
        if not self.recording:
            return

        self.recording = False
        self.play_sound("stop")

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if not self.audio_data:
            print("No audio")
            return

        print("⏳ Transcribing...")

        # Process in background
        Thread(target=self._process_audio, daemon=True).start()

    def _process_audio(self):
        audio = np.concatenate(self.audio_data, axis=0)
        duration = len(audio) / SAMPLE_RATE

        # Save temp file
        temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        audio_int16 = (audio * 32767).astype(np.int16)
        with wave.open(temp.name, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())

        # Transcribe
        result = subprocess.run(
            ["whisper-cli", "-m", str(MODEL_PATH), "-f", temp.name,
             "--no-timestamps", "-t", "4", "-l", "en"],
            capture_output=True, text=True
        )
        text = ' '.join([l.strip() for l in result.stdout.strip().split('\n') if l.strip()])

        if text:
            self.play_sound("done")
            print(f"\n📝 {text}")

            # Save
            DATA_DIR.mkdir(exist_ok=True)
            existing = list(DATA_DIR.glob("audio_*.wav"))
            num = max([int(f.stem.split('_')[1]) for f in existing], default=0) + 1

            shutil.move(temp.name, str(DATA_DIR / f"audio_{num:06d}.wav"))
            (DATA_DIR / f"audio_{num:06d}.txt").write_text(text)

            # Clipboard
            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.setString_forType_(text, NSPasteboardTypeString)

            print(f"💾 Saved audio_{num:06d} | 📋 Copied!")
        else:
            print("❌ No speech")
            os.unlink(temp.name)

        print("\n🎤 Ready...")

    def handle_key_down(self, event):
        keycode = event.keyCode()

        if keycode == self.config.get("toggle_key"):
            if self.recording:
                self.stop_recording()
            else:
                self.start_recording()

        elif keycode == self.config.get("hold_key"):
            if not self.hold_active:
                self.hold_active = True
                self.start_recording()

    def handle_key_up(self, event):
        keycode = event.keyCode()

        if keycode == self.config.get("hold_key"):
            if self.hold_active:
                self.hold_active = False
                self.stop_recording()

def main():
    print("\n" + "="*50)
    print("🦜 PANOKEET v2")
    print("="*50)

    DATA_DIR.mkdir(exist_ok=True)
    app = Panokeet()

    # Set up NSApplication
    NSApplication.sharedApplication()
    NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    # Key mappings for reference
    print("""
Common key codes:
  0=A  1=S  2=D  3=F  4=H  5=G  6=Z  7=X  8=C  9=V
  11=B 12=Q 13=W 14=E 15=R 16=Y 17=T 18=1 19=2 20=3
  21=4 22=6 23=5 24== 25=9 26=7 27=- 28=8 29=0

  49=Space  36=Return  48=Tab  51=Delete  53=Escape

  123=Left 124=Right 125=Down 126=Up

  F1=122 F2=120 F3=99 F4=118 F5=96 F6=97 F7=98 F8=100
    """)

    # Get user's preferred keys
    print(f"Current config: Toggle={app.config.get('toggle_key')}, Hold={app.config.get('hold_key')}")

    change = input("\nChange hotkeys? (y/n): ").strip().lower()
    if change == 'y':
        try:
            toggle = int(input("Enter keycode for TOGGLE: "))
            hold = int(input("Enter keycode for HOLD-TO-SPEAK: "))
            app.config["toggle_key"] = toggle
            app.config["hold_key"] = hold
            app.save_config()
            print(f"✅ Saved: Toggle={toggle}, Hold={hold}")
        except:
            print("Invalid input, using defaults")

    # Set up global event monitors
    def on_key_down(event):
        app.handle_key_down(event)
        return event

    def on_key_up(event):
        app.handle_key_up(event)
        return event

    NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSKeyDownMask, on_key_down)
    NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSKeyUpMask, on_key_up)

    print(f"\n🎤 Ready! Using Toggle={app.config['toggle_key']}, Hold={app.config['hold_key']}")
    print("Press Ctrl+C to quit.\n")

    try:
        AppHelper.runConsoleEventLoop()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()
