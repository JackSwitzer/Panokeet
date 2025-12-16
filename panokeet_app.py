#!/usr/bin/env python3
"""
Panokeet - Voice to Text Menu Bar App

Features:
- Menu bar icon with status (Ready/Recording/Transcribing)
- Global hotkeys via Karabiner (Cmd+Keypad7 → F13, Cmd+Keypad8 → F14)
- Popup window for editing transcriptions
- Training data with JSON metadata
"""

import subprocess
import tempfile
import wave
import shutil
import json
import os
from pathlib import Path
from datetime import datetime
from threading import Thread

import rumps
import numpy as np
import sounddevice as sd
from AppKit import NSSound, NSApp, NSApplication
from Quartz import (
    CGEventTapCreate, CGEventMaskBit, kCGEventKeyDown, kCGEventKeyUp,
    kCGHIDEventTap, kCGHeadInsertEventTap, kCGEventTapOptionDefault,
    CFMachPortCreateRunLoopSource, CFRunLoopGetMain, CFRunLoopAddSource,
    kCFRunLoopCommonModes, CGEventGetIntegerValueField,
    kCGKeyboardEventKeycode, CGEventTapEnable
)

from popup import show_transcription_popup

# Paths
APP_DIR = Path(__file__).parent
MODEL_PATH = APP_DIR / "models" / "ggml-medium.bin"
DATA_DIR = APP_DIR / "training_data"
SAMPLE_RATE = 16000

# F-key keycodes (via Karabiner remap)
F13_KEYCODE = 105  # Toggle recording
F14_KEYCODE = 107  # Hold to speak

# Status icons
ICON_READY = "🎤"
ICON_RECORDING = "🔴"
ICON_TRANSCRIBING = "⏳"


class PanokeetApp(rumps.App):
    def __init__(self):
        super().__init__(ICON_READY, quit_button=None)

        self.recording = False
        self.audio_data = []
        self.stream = None
        self.hold_active = False
        self.temp_audio_path = None
        self._pending_popup_data = None  # (raw_text, duration) when ready

        # Menu items
        self.status_item = rumps.MenuItem("Status: Ready")
        self.status_item.set_callback(None)

        self.menu = [
            self.status_item,
            None,  # Separator
            rumps.MenuItem("Toggle Recording (Cmd+Keypad7)", callback=self.toggle_recording),
            None,
            rumps.MenuItem("Open Training Data", callback=self.open_training_data),
            None,
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        # Set up global hotkeys
        self.setup_hotkeys()

        # Timer to check for pending popups (runs on main thread)
        self._popup_timer = rumps.Timer(self._check_pending_popup, 0.1)
        self._popup_timer.start()

    def setup_hotkeys(self):
        """Set up CGEventTap for global hotkeys."""
        mask = CGEventMaskBit(kCGEventKeyDown) | CGEventMaskBit(kCGEventKeyUp)

        def callback(proxy, event_type, event, refcon):
            keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)

            # Check if this is our hotkey
            is_our_key = keycode in (F13_KEYCODE, F14_KEYCODE)

            if event_type == kCGEventKeyDown:
                if keycode == F13_KEYCODE:
                    self.toggle_recording(None)
                elif keycode == F14_KEYCODE and not self.hold_active:
                    self.hold_active = True
                    self.start_recording()

            elif event_type == kCGEventKeyUp:
                if keycode == F14_KEYCODE and self.hold_active:
                    self.hold_active = False
                    self.stop_recording()

            # Consume F13/F14 events (return None), pass others through
            if is_our_key:
                return None
            return event

        tap = CGEventTapCreate(
            kCGHIDEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionDefault,  # Can modify/consume events
            mask,
            callback,
            None
        )

        if tap:
            source = CFMachPortCreateRunLoopSource(None, tap, 0)
            CFRunLoopAddSource(CFRunLoopGetMain(), source, kCFRunLoopCommonModes)
            CGEventTapEnable(tap, True)
            print("✓ Global hotkeys active")
        else:
            print("❌ Failed to create event tap - check Input Monitoring permissions")
            rumps.notification(
                "Panokeet",
                "Permission Required",
                "Add Terminal to Input Monitoring in System Settings"
            )

    def set_status(self, status, icon):
        """Update menu bar icon and status."""
        self.title = icon
        self.status_item.title = f"Status: {status}"

    def play_sound(self, name):
        """Play system sounds."""
        sounds = {"start": "Morse", "stop": "Tink", "done": "Glass", "error": "Basso"}
        s = NSSound.soundNamed_(sounds.get(name, ""))
        if s:
            s.play()

    def toggle_recording(self, sender):
        """Toggle recording on/off."""
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        """Start audio recording."""
        if self.recording:
            return

        self.audio_data = []
        self.recording = True
        self.set_status("Recording...", ICON_RECORDING)

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
        print("🔴 Recording...")

    def stop_recording(self):
        """Stop recording and start transcription."""
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
            self.set_status("Ready", ICON_READY)
            return

        self.set_status("Transcribing...", ICON_TRANSCRIBING)
        print("⏳ Transcribing...")

        # Process in thread
        Thread(target=self._process_audio, daemon=True).start()

    def _process_audio(self):
        """Process audio: transcribe, show popup, save."""
        audio = np.concatenate(self.audio_data, axis=0)
        duration = len(audio) / SAMPLE_RATE

        # Save to temp file
        temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self.temp_audio_path = temp.name
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
        raw_text = ' '.join([l.strip() for l in result.stdout.strip().split('\n') if l.strip()])

        if raw_text:
            self.play_sound("done")
            print(f"📝 {raw_text}")

            # Store for main thread to pick up
            self._pending_popup_data = (raw_text, duration)
        else:
            self.play_sound("error")
            print("❌ No speech detected")
            os.unlink(temp.name)
            self.temp_audio_path = None
            self.set_status("Ready", ICON_READY)

    def _check_pending_popup(self, _):
        """Check for pending popup data and show popup on main thread."""
        if self._pending_popup_data:
            raw_text, duration = self._pending_popup_data
            self._pending_popup_data = None
            self._show_popup(raw_text, duration)

    def _show_popup(self, raw_text, duration):
        """Show popup window for editing."""
        # Activate app to show popup
        NSApp.activateIgnoringOtherApps_(True)

        result = show_transcription_popup(raw_text, duration)

        if result['action'] == 'done':
            self._save_training_data(raw_text, result['text'], duration, result['was_edited'])
            print(f"💾 Saved | 📋 Copied | Edited: {result['was_edited']}")
        else:
            # Cancelled - delete temp audio
            if self.temp_audio_path and os.path.exists(self.temp_audio_path):
                os.unlink(self.temp_audio_path)
            print("❌ Cancelled")

        self.temp_audio_path = None
        self.set_status("Ready", ICON_READY)

    def _save_training_data(self, raw_text, final_text, duration, was_edited):
        """Save audio and metadata to training data."""
        DATA_DIR.mkdir(exist_ok=True)

        # Get next number
        existing = list(DATA_DIR.glob("audio_*.wav"))
        nums = [int(f.stem.split('_')[1]) for f in existing if f.stem.split('_')[1].isdigit()]
        num = max(nums, default=0) + 1

        # Move audio file
        audio_path = DATA_DIR / f"audio_{num:06d}.wav"
        if self.temp_audio_path and os.path.exists(self.temp_audio_path):
            shutil.move(self.temp_audio_path, str(audio_path))

        # Save metadata JSON
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "duration": round(duration, 2),
            "raw_transcript": raw_text,
            "final_transcript": final_text,
            "was_edited": was_edited,
            "needs_review": not was_edited
        }
        json_path = DATA_DIR / f"audio_{num:06d}.json"
        with open(json_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        # Also save plain text for compatibility
        txt_path = DATA_DIR / f"audio_{num:06d}.txt"
        txt_path.write_text(final_text)

        print(f"💾 Saved audio_{num:06d} ({duration:.1f}s)")

    def open_training_data(self, sender):
        """Open training data folder in Finder."""
        DATA_DIR.mkdir(exist_ok=True)
        subprocess.run(["open", str(DATA_DIR)])

    def quit_app(self, sender):
        """Quit the application."""
        rumps.quit_application()


def main():
    print("\n" + "=" * 50)
    print("🦜 PANOKEET - Voice to Text")
    print("=" * 50)
    print(f"Model: {MODEL_PATH.name}")
    print(f"Data: {DATA_DIR}/")
    print("\nHotkeys (via Karabiner):")
    print("  Cmd+Keypad7 → Toggle recording")
    print("  Cmd+Keypad8 → Hold to speak")
    print("=" * 50)

    DATA_DIR.mkdir(exist_ok=True)

    # Ensure proper app activation
    NSApplication.sharedApplication()

    app = PanokeetApp()
    app.run()


if __name__ == "__main__":
    main()
