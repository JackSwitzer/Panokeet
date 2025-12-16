#!/usr/bin/env python3
"""
Whisper Dictate - Menu Bar App
Local speech-to-text with training data collection.
"""

import rumps
import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from threading import Thread
import subprocess

from AppKit import NSPasteboard, NSPasteboardTypeString, NSSound, NSEvent, NSKeyDownMask
from Quartz import (
    CGEventTapCreate, CGEventMaskBit, kCGEventKeyDown, kCGEventKeyUp,
    kCGHIDEventTap, kCGHeadInsertEventTap, kCGEventTapOptionDefault,
    CFMachPortCreateRunLoopSource, CFRunLoopGetCurrent, CFRunLoopAddSource,
    kCFRunLoopCommonModes, CGEventGetIntegerValueField, kCGKeyboardEventKeycode,
    CGEventTapEnable
)
import objc

from recorder import Recorder
from transcriber import transcribe, check_model, get_model_name
from popup import show_transcription_popup

# Paths
APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "training_data"
CONFIG_FILE = APP_DIR / "config.json"

# Default config
DEFAULT_CONFIG = {
    "toggle_key": None,  # Will be set in calibration
    "hold_key": None,    # Will be set in calibration
    "calibrated": False
}


class WhisperDictateApp(rumps.App):
    def __init__(self):
        super().__init__(
            "Whisper Dictate",
            icon=None,
            title="🎤",
            quit_button=None  # We'll add our own
        )

        self.config = self.load_config()
        self.recorder = Recorder()
        self.is_recording = False
        self.hold_key_pressed = False
        self.status = "ready"  # ready, recording, transcribing

        # Setup menu
        self.menu = [
            rumps.MenuItem("Status: Ready", callback=None),
            None,  # Separator
            rumps.MenuItem("Toggle Recording", callback=self.toggle_recording),
            None,
            rumps.MenuItem("Calibrate Hotkeys", callback=self.calibrate),
            rumps.MenuItem("Open Training Data", callback=self.open_training_data),
            None,
            rumps.MenuItem("Quit", callback=self.quit_app)
        ]

        # Ensure directories exist
        DATA_DIR.mkdir(exist_ok=True)

        # Check model
        if not check_model():
            rumps.alert(
                title="Model Not Found",
                message="Whisper model not found. Please download it first.",
                ok="OK"
            )

        # Start hotkey listener
        self.setup_hotkeys()

        # Don't auto-prompt calibration - let user do it from menu
        # if not self.config.get("calibrated"):
        #     rumps.Timer(self.prompt_calibration, 1).start()

    def load_config(self):
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                return json.load(f)
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)

    def update_status(self, status):
        self.status = status
        status_text = {
            "ready": "Status: Ready",
            "recording": "Status: 🔴 Recording...",
            "transcribing": "Status: ⏳ Transcribing..."
        }
        self.menu["Status: Ready"].title = status_text.get(status, "Status: Ready")

        # Update menu bar icon
        icons = {"ready": "🎤", "recording": "🔴", "transcribing": "⏳"}
        self.title = icons.get(status, "🎤")

    def play_sound(self, sound_type):
        """Play system sound for feedback."""
        sounds = {
            "start": "Morse",
            "stop": "Tink",
            "done": "Glass"
        }
        sound_name = sounds.get(sound_type)
        if sound_name:
            sound = NSSound.soundNamed_(sound_name)
            if sound:
                sound.play()

    def toggle_recording(self, _=None):
        """Toggle recording on/off."""
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.is_recording:
            return

        self.is_recording = True
        self.update_status("recording")
        self.play_sound("start")
        self.recorder.start()

    def stop_recording(self):
        if not self.is_recording:
            return

        self.is_recording = False
        self.play_sound("stop")
        self.update_status("transcribing")

        # Stop recording and get audio
        result = self.recorder.stop()
        if not result:
            self.update_status("ready")
            return

        audio_path, duration = result

        # Transcribe in background thread
        def do_transcribe():
            text = transcribe(audio_path)

            if text:
                # Show popup for editing
                self.play_sound("done")
                result = show_transcription_popup(text, duration)

                if result['action'] == 'save':
                    self.save_training_data(audio_path, result['text'], text, duration, result['was_edited'])
                elif result['action'] == 'copy':
                    # Already copied by popup, optionally save too
                    pass
                else:
                    # Cancelled - delete temp audio
                    os.unlink(audio_path)
            else:
                os.unlink(audio_path)
                rumps.notification(
                    title="Whisper Dictate",
                    subtitle="No speech detected",
                    message="",
                    sound=False
                )

            self.update_status("ready")

        Thread(target=do_transcribe, daemon=True).start()

    def save_training_data(self, audio_path, final_text, raw_text, duration, was_edited):
        """Save audio and transcription to training data folder."""
        # Get next file number
        existing = list(DATA_DIR.glob("audio_*.wav"))
        if not existing:
            num = 1
        else:
            numbers = [int(f.stem.split('_')[1]) for f in existing]
            num = max(numbers) + 1

        # Save files
        audio_dest = DATA_DIR / f"audio_{num:06d}.wav"
        text_dest = DATA_DIR / f"audio_{num:06d}.txt"

        shutil.move(str(audio_path), str(audio_dest))
        text_dest.write_text(final_text)

        # Save raw text if different
        if was_edited:
            raw_dest = DATA_DIR / f"audio_{num:06d}_raw.txt"
            raw_dest.write_text(raw_text)

        # Update manifest
        manifest_path = DATA_DIR / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)
        else:
            manifest = {"entries": []}

        manifest["entries"].append({
            "id": num,
            "timestamp": datetime.now().isoformat(),
            "duration": duration,
            "was_edited": was_edited,
            "audio": audio_dest.name,
            "text": text_dest.name
        })

        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        rumps.notification(
            title="Saved",
            subtitle=f"audio_{num:06d}",
            message=final_text[:50] + "..." if len(final_text) > 50 else final_text,
            sound=False
        )

    def open_training_data(self, _):
        """Open training data folder in Finder."""
        subprocess.run(["open", str(DATA_DIR)])

    def prompt_calibration(self, _):
        """Prompt user to calibrate on first run."""
        response = rumps.alert(
            title="Welcome to Whisper Dictate!",
            message="Would you like to set up your hotkeys now?\n\nYou'll press the keys you want to use for:\n• Toggle recording (press to start/stop)\n• Hold to speak (hold down while talking)",
            ok="Calibrate Now",
            cancel="Later"
        )
        if response == 1:  # OK
            self.calibrate(None)

    def calibrate(self, _):
        """Run hotkey calibration."""
        # First key: Toggle
        rumps.alert(
            title="Calibration: Toggle Key",
            message="After clicking OK, press the key you want to use for TOGGLE recording.\n\n(Press once to start, press again to stop)",
            ok="OK"
        )
        toggle_key = self.capture_next_key()
        if toggle_key is None:
            rumps.alert("Calibration cancelled")
            return

        # Second key: Hold
        rumps.alert(
            title="Calibration: Hold Key",
            message=f"Toggle key set to keycode {toggle_key}.\n\nNow press the key you want to use for HOLD-TO-SPEAK.\n\n(Hold while talking, release to transcribe)",
            ok="OK"
        )
        hold_key = self.capture_next_key()
        if hold_key is None:
            rumps.alert("Calibration cancelled")
            return

        # Save config
        self.config["toggle_key"] = toggle_key
        self.config["hold_key"] = hold_key
        self.config["calibrated"] = True
        self.save_config()

        # Restart hotkey listener
        self.setup_hotkeys()

        rumps.alert(
            title="Calibration Complete!",
            message=f"Toggle: keycode {toggle_key}\nHold: keycode {hold_key}\n\nYour hotkeys are now active!",
            ok="OK"
        )

    def capture_next_key(self):
        """Capture the next key press and return its keycode."""
        captured = {"keycode": None, "done": False}

        def callback(proxy, event_type, event, refcon):
            if event_type == kCGEventKeyDown and not captured["done"]:
                keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
                captured["keycode"] = keycode
                captured["done"] = True
            return event

        # Create event tap
        mask = CGEventMaskBit(kCGEventKeyDown)
        tap = CGEventTapCreate(
            kCGHIDEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionDefault,
            mask,
            callback,
            None
        )

        if tap is None:
            rumps.alert(
                title="Permission Required",
                message="Please grant Accessibility permission in System Preferences > Privacy & Security > Accessibility",
                ok="OK"
            )
            return None

        source = CFMachPortCreateRunLoopSource(None, tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopCommonModes)
        CGEventTapEnable(tap, True)

        # Wait for key press (with timeout)
        import time
        start = time.time()
        while not captured["done"] and (time.time() - start) < 10:
            time.sleep(0.1)

        CGEventTapEnable(tap, False)
        return captured["keycode"]

    def setup_hotkeys(self):
        """Set up global hotkey listener."""
        toggle_key = self.config.get("toggle_key")
        hold_key = self.config.get("hold_key")

        if not toggle_key and not hold_key:
            return

        def callback(proxy, event_type, event, refcon):
            keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)

            if event_type == kCGEventKeyDown:
                if keycode == toggle_key:
                    # Toggle on key down
                    rumps.Timer(lambda _: self.toggle_recording(), 0).start()
                elif keycode == hold_key and not self.hold_key_pressed:
                    # Start recording on hold key down
                    self.hold_key_pressed = True
                    rumps.Timer(lambda _: self.start_recording(), 0).start()

            elif event_type == kCGEventKeyUp:
                if keycode == hold_key and self.hold_key_pressed:
                    # Stop recording on hold key up
                    self.hold_key_pressed = False
                    rumps.Timer(lambda _: self.stop_recording(), 0).start()

            return event

        # Create event tap for both key down and key up
        mask = CGEventMaskBit(kCGEventKeyDown) | CGEventMaskBit(kCGEventKeyUp)
        tap = CGEventTapCreate(
            kCGHIDEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionDefault,
            mask,
            callback,
            None
        )

        if tap is None:
            print("Failed to create event tap. Need Accessibility permission.")
            return

        source = CFMachPortCreateRunLoopSource(None, tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopCommonModes)
        CGEventTapEnable(tap, True)

    def quit_app(self, _):
        rumps.quit_application()


def main():
    WhisperDictateApp().run()


if __name__ == "__main__":
    main()
