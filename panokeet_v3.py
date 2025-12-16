#!/usr/bin/env python3
"""
Panokeet v3 - With modifier keys (Cmd, Shift, etc.) and numpad support
"""

import subprocess
import tempfile
import wave
import shutil
import json
import os
from pathlib import Path
from threading import Thread

import numpy as np
import sounddevice as sd
import objc
from AppKit import (
    NSApplication, NSApp, NSEvent, NSKeyDownMask, NSKeyUpMask,
    NSSound, NSPasteboard, NSPasteboardTypeString,
    NSApplicationActivationPolicyAccessory,
    NSCommandKeyMask, NSShiftKeyMask, NSAlternateKeyMask, NSControlKeyMask
)
from PyObjCTools import AppHelper

APP_DIR = Path(__file__).parent
MODEL_PATH = APP_DIR / "models" / "ggml-medium.bin"
DATA_DIR = APP_DIR / "training_data"
CONFIG_FILE = APP_DIR / "config.json"
SAMPLE_RATE = 16000

# Keycode reference
KEYCODES = """
╔══════════════════════════════════════════════════════════════╗
║                    KEYBOARD KEYCODES                          ║
╠══════════════════════════════════════════════════════════════╣
║ Regular Numbers (top row):                                    ║
║   18=1  19=2  20=3  21=4  23=5  22=6  26=7  28=8  25=9  29=0 ║
╠══════════════════════════════════════════════════════════════╣
║ NUMPAD (your external keypad):                                ║
║   89=Num7  91=Num8  92=Num9                                  ║
║   86=Num4  87=Num5  88=Num6                                  ║
║   83=Num1  84=Num2  85=Num3                                  ║
║   82=Num0  65=Num.  76=NumEnter                              ║
║   75=Num/  67=Num*  78=Num-  69=Num+                         ║
╠══════════════════════════════════════════════════════════════╣
║ Function Keys:                                                ║
║   122=F1  120=F2  99=F3  118=F4  96=F5  97=F6  98=F7  100=F8 ║
║   101=F9  109=F10 103=F11 111=F12                            ║
║   F13-F19 may vary by keyboard                               ║
╠══════════════════════════════════════════════════════════════╣
║ Modifiers (combine with +):                                   ║
║   cmd  shift  opt  ctrl                                       ║
║   Example: "cmd+89" = Command + Numpad 7                      ║
╚══════════════════════════════════════════════════════════════╝
"""

class Panokeet:
    def __init__(self):
        self.recording = False
        self.audio_data = []
        self.stream = None
        self.config = self.load_config()
        self.hold_active = False

    def load_config(self):
        default = {
            "toggle_key": 89,      # Numpad 7
            "toggle_mods": ["cmd", "opt", "ctrl"],
            "hold_key": 91,        # Numpad 8
            "hold_mods": ["cmd", "opt", "ctrl"]
        }
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    cfg = json.load(f)
                    # Ensure all keys exist
                    for k, v in default.items():
                        if k not in cfg:
                            cfg[k] = v
                    return cfg
            except:
                return default
        return default

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)

    def play_sound(self, name):
        sounds = {"start": "Morse", "stop": "Tink", "done": "Glass"}
        s = NSSound.soundNamed_(sounds.get(name, ""))
        if s:
            s.play()

    def check_modifiers(self, event, required_mods):
        """Check if the required modifier keys are pressed."""
        flags = event.modifierFlags()

        has_cmd = bool(flags & NSCommandKeyMask)
        has_shift = bool(flags & NSShiftKeyMask)
        has_opt = bool(flags & NSAlternateKeyMask)
        has_ctrl = bool(flags & NSControlKeyMask)

        # Check each required modifier
        for mod in required_mods:
            if mod == "cmd" and not has_cmd:
                return False
            if mod == "shift" and not has_shift:
                return False
            if mod == "opt" and not has_opt:
                return False
            if mod == "ctrl" and not has_ctrl:
                return False

        return True

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
        Thread(target=self._process_audio, daemon=True).start()

    def _process_audio(self):
        audio = np.concatenate(self.audio_data, axis=0)
        duration = len(audio) / SAMPLE_RATE

        temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        audio_int16 = (audio * 32767).astype(np.int16)
        with wave.open(temp.name, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())

        result = subprocess.run(
            ["whisper-cli", "-m", str(MODEL_PATH), "-f", temp.name,
             "--no-timestamps", "-t", "4", "-l", "en"],
            capture_output=True, text=True
        )
        text = ' '.join([l.strip() for l in result.stdout.strip().split('\n') if l.strip()])

        if text:
            self.play_sound("done")
            print(f"\n📝 {text}")

            DATA_DIR.mkdir(exist_ok=True)
            existing = list(DATA_DIR.glob("audio_*.wav"))
            num = max([int(f.stem.split('_')[1]) for f in existing], default=0) + 1

            shutil.move(temp.name, str(DATA_DIR / f"audio_{num:06d}.wav"))
            (DATA_DIR / f"audio_{num:06d}.txt").write_text(text)

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
        toggle_key = self.config.get("toggle_key")
        toggle_mods = self.config.get("toggle_mods", [])
        hold_key = self.config.get("hold_key")
        hold_mods = self.config.get("hold_mods", [])

        # Toggle hotkey
        if keycode == toggle_key and self.check_modifiers(event, toggle_mods):
            if self.recording:
                self.stop_recording()
            else:
                self.start_recording()

        # Hold hotkey
        elif keycode == hold_key and self.check_modifiers(event, hold_mods):
            if not self.hold_active:
                self.hold_active = True
                self.start_recording()

    def handle_key_up(self, event):
        keycode = event.keyCode()
        hold_key = self.config.get("hold_key")

        if keycode == hold_key and self.hold_active:
            self.hold_active = False
            self.stop_recording()


def parse_hotkey(s):
    """Parse hotkey string like 'cmd+89' into (keycode, [modifiers])"""
    parts = s.lower().strip().split('+')
    mods = []
    keycode = None

    for part in parts:
        part = part.strip()
        if part in ('cmd', 'command'):
            mods.append('cmd')
        elif part in ('shift',):
            mods.append('shift')
        elif part in ('opt', 'option', 'alt'):
            mods.append('opt')
        elif part in ('ctrl', 'control'):
            mods.append('ctrl')
        else:
            try:
                keycode = int(part)
            except:
                pass

    return keycode, mods


def format_hotkey(keycode, mods):
    """Format hotkey for display."""
    parts = []
    if 'cmd' in mods:
        parts.append('Cmd')
    if 'shift' in mods:
        parts.append('Shift')
    if 'opt' in mods:
        parts.append('Opt')
    if 'ctrl' in mods:
        parts.append('Ctrl')
    parts.append(str(keycode))
    return '+'.join(parts)


def main():
    print("\n" + "="*60)
    print("🦜 PANOKEET v3 - Voice to Text")
    print("="*60)

    DATA_DIR.mkdir(exist_ok=True)
    app = Panokeet()

    print(KEYCODES)

    toggle_display = format_hotkey(app.config['toggle_key'], app.config.get('toggle_mods', []))
    hold_display = format_hotkey(app.config['hold_key'], app.config.get('hold_mods', []))

    print(f"\nCurrent hotkeys:")
    print(f"  Toggle: {toggle_display}")
    print(f"  Hold:   {hold_display}")

    change = input("\nChange hotkeys? (y/n): ").strip().lower()
    if change == 'y':
        print("\nEnter hotkeys like: cmd+89 or shift+cmd+91")
        print("(See NUMPAD section above for keypad codes)\n")

        toggle_str = input("Toggle hotkey (e.g. cmd+89 for Cmd+Numpad7): ").strip()
        if toggle_str:
            keycode, mods = parse_hotkey(toggle_str)
            if keycode:
                app.config['toggle_key'] = keycode
                app.config['toggle_mods'] = mods
                print(f"  ✓ Toggle: {format_hotkey(keycode, mods)}")

        hold_str = input("Hold hotkey (e.g. cmd+91 for Cmd+Numpad8): ").strip()
        if hold_str:
            keycode, mods = parse_hotkey(hold_str)
            if keycode:
                app.config['hold_key'] = keycode
                app.config['hold_mods'] = mods
                print(f"  ✓ Hold: {format_hotkey(keycode, mods)}")

        app.save_config()
        print("\n✅ Config saved!")

    # Set up NSApplication
    NSApplication.sharedApplication()
    NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    # Set up global event monitors
    def on_key_down(event):
        app.handle_key_down(event)
        return event

    def on_key_up(event):
        app.handle_key_up(event)
        return event

    NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSKeyDownMask, on_key_down)
    NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSKeyUpMask, on_key_up)

    toggle_display = format_hotkey(app.config['toggle_key'], app.config.get('toggle_mods', []))
    hold_display = format_hotkey(app.config['hold_key'], app.config.get('hold_mods', []))

    print(f"\n🎤 Ready!")
    print(f"   Toggle: {toggle_display}")
    print(f"   Hold:   {hold_display}")
    print(f"\nPress Ctrl+C to quit.\n")

    try:
        AppHelper.runConsoleEventLoop()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()
