#!/usr/bin/env python3
"""
Voice dictation tool using whisper.cpp for local transcription.

Usage:
    Cmd+Numpad7       - Toggle recording (press to start, press again to stop & save)
    Cmd+Numpad8 (hold) - Hold to speak (release to stop & save)
    Esc               - Quit
"""

import subprocess
import tempfile
import wave
import shutil
import sys
import os
from pathlib import Path
from threading import Thread, Event
import time

import numpy as np
import sounddevice as sd
import pyperclip
from pynput import keyboard
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

# Configuration
MODEL_PATH = Path(__file__).parent / "models" / "ggml-medium.bin"
DATA_DIR = Path(__file__).parent / "training_data"
SAMPLE_RATE = 16000
CHANNELS = 1
THREADS = 4

console = Console()

# Colors
ORANGE = "#FF8C00"
YELLOW = "#FFD700"
WHITE = "#FFFFFF"
DIM = "#666666"


def make_waveform(level: float, width: int = 40) -> Text:
    """Create a waveform visualization based on audio level."""
    bars = "▁▂▃▄▅▆▇█"
    text = Text()

    for i in range(width):
        # Create wave pattern with some randomness based on level
        wave_pos = abs(i - width // 2) / (width // 2)
        intensity = level * (1 - wave_pos * 0.5) * np.random.uniform(0.7, 1.3)
        intensity = max(0, min(1, intensity))
        bar_idx = int(intensity * (len(bars) - 1))

        # Color gradient: orange in center, yellow on edges
        if abs(i - width // 2) < width // 4:
            color = ORANGE
        else:
            color = YELLOW

        text.append(bars[bar_idx], style=color)

    return text


class Recorder:
    def __init__(self):
        self.recording = False
        self.audio_data = []
        self.stream = None
        self.current_level = 0.0

    def start(self):
        self.audio_data = []
        self.recording = True
        self.current_level = 0.0
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=np.float32,
            callback=self._callback
        )
        self.stream.start()

    def _callback(self, indata, frames, time, status):
        if self.recording:
            self.audio_data.append(indata.copy())
            # Calculate audio level for visualization
            self.current_level = min(1.0, np.abs(indata).max() * 3)

    def stop(self) -> Path:
        self.recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if not self.audio_data:
            return None

        audio = np.concatenate(self.audio_data, axis=0)
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        audio_int16 = (audio * 32767).astype(np.int16)

        with wave.open(temp_file.name, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())

        return Path(temp_file.name), len(audio) / SAMPLE_RATE


def transcribe(audio_path: Path) -> str:
    """Transcribe audio file using whisper.cpp"""
    result = subprocess.run(
        [
            "nice", "-n", "10",
            "whisper-cli",
            "-m", str(MODEL_PATH),
            "-f", str(audio_path),
            "--no-timestamps",
            "-t", str(THREADS),
            "-l", "en",
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return ""

    text = result.stdout.strip()
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return ' '.join(lines)


def get_next_file_number() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    existing = list(DATA_DIR.glob("audio_*.wav"))
    if not existing:
        return 1
    numbers = [int(f.stem.split('_')[1]) for f in existing]
    return max(numbers) + 1


class DictationApp:
    NUMPAD_7 = 89
    NUMPAD_8 = 91

    def __init__(self):
        self.recorder = Recorder()
        self.is_recording = False
        self.cmd_pressed = False
        self.numpad8_held = False
        self.quit_event = Event()
        self.current_audio_path = None
        self.status = "ready"  # ready, recording, transcribing
        self.last_transcription = ""
        self.last_duration = 0.0
        self.live = None
        self.ui_thread = None

    def _is_numpad_7(self, key):
        return hasattr(key, 'vk') and key.vk == self.NUMPAD_7

    def _is_numpad_8(self, key):
        return hasattr(key, 'vk') and key.vk == self.NUMPAD_8

    def _render_ui(self) -> Panel:
        """Render the current UI state."""
        content = Text()

        if self.status == "ready":
            content.append("● ", style=DIM)
            content.append("Ready", style=WHITE)
            content.append("\n\n")
            content.append("Cmd+Numpad7 ", style=YELLOW)
            content.append("toggle  ", style=DIM)
            content.append("Cmd+Numpad8 ", style=YELLOW)
            content.append("hold-to-speak", style=DIM)

        elif self.status == "recording":
            content.append("● ", style=ORANGE)
            content.append("Recording", style=f"bold {ORANGE}")
            content.append("\n\n")
            waveform = make_waveform(self.recorder.current_level)
            content.append_text(waveform)

        elif self.status == "transcribing":
            content.append("◐ ", style=YELLOW)
            content.append("Transcribing", style=f"bold {YELLOW}")
            content.append("...", style=DIM)
            content.append("\n\n")
            # Animated dots
            dots = "●○○", "○●○", "○○●"
            idx = int(time.time() * 3) % 3
            content.append(dots[idx], style=ORANGE)

        elif self.status == "done":
            content.append("✓ ", style="#00FF00")
            content.append(f"Saved ({self.last_duration:.1f}s)", style=WHITE)
            content.append("\n\n")
            content.append(self.last_transcription[:80], style=f"italic {YELLOW}")
            if len(self.last_transcription) > 80:
                content.append("...", style=DIM)

        return Panel(
            Align.center(content),
            title=f"[{ORANGE}]🎤 Whisper Dictate[/{ORANGE}]",
            border_style=ORANGE if self.status == "recording" else DIM,
            padding=(1, 2),
        )

    def _ui_loop(self):
        """Background thread for UI updates."""
        with Live(self._render_ui(), console=console, refresh_per_second=10, transient=True) as live:
            self.live = live
            while not self.quit_event.is_set():
                live.update(self._render_ui())
                time.sleep(0.1)

    def _start_recording(self, mode):
        if not self.is_recording:
            self.is_recording = True
            self.status = "recording"
            self.recorder.start()

    def _stop_and_save(self):
        if not self.is_recording:
            return

        self.is_recording = False
        self.status = "transcribing"

        result = self.recorder.stop()
        if not result:
            self.status = "ready"
            return

        audio_path, duration = result
        self.last_duration = duration

        transcription = transcribe(audio_path)

        if transcription:
            file_num = get_next_file_number()
            audio_dest = DATA_DIR / f"audio_{file_num:06d}.wav"
            text_dest = DATA_DIR / f"audio_{file_num:06d}.txt"

            shutil.move(str(audio_path), str(audio_dest))
            text_dest.write_text(transcription)
            pyperclip.copy(transcription)

            self.last_transcription = transcription
            self.status = "done"

            # Show done state briefly, then back to ready
            time.sleep(2)
        else:
            os.unlink(audio_path)

        self.status = "ready"

    def on_press(self, key):
        try:
            if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                self.cmd_pressed = True

            if self.cmd_pressed and self._is_numpad_7(key):
                if self.is_recording:
                    Thread(target=self._stop_and_save, daemon=True).start()
                else:
                    self._start_recording("toggle")

            if self.cmd_pressed and self._is_numpad_8(key):
                if not self.is_recording:
                    self.numpad8_held = True
                    self._start_recording("hold")

        except AttributeError:
            pass

    def on_release(self, key):
        try:
            if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                self.cmd_pressed = False
                if self.numpad8_held and self.is_recording:
                    self.numpad8_held = False
                    Thread(target=self._stop_and_save, daemon=True).start()

            if self._is_numpad_8(key):
                if self.numpad8_held and self.is_recording:
                    self.numpad8_held = False
                    Thread(target=self._stop_and_save, daemon=True).start()

            if key == keyboard.Key.esc:
                self.quit_event.set()
                return False

        except AttributeError:
            pass

    def run(self):
        DATA_DIR.mkdir(exist_ok=True)

        console.clear()
        console.print(f"\n[{ORANGE}]Whisper Dictate[/{ORANGE}] [dim]v1.0[/dim]\n")
        console.print(f"[dim]Model:[/dim] [{YELLOW}]{MODEL_PATH.name}[/{YELLOW}]")
        console.print(f"[dim]Saving to:[/dim] [{YELLOW}]{DATA_DIR}/[/{YELLOW}]\n")

        # Start UI thread
        self.ui_thread = Thread(target=self._ui_loop, daemon=True)
        self.ui_thread.start()

        with keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        ) as listener:
            self.quit_event.wait()

        console.print(f"\n[{ORANGE}]👋 Goodbye![/{ORANGE}]\n")


def main():
    if not MODEL_PATH.exists():
        console.print(f"[red]Error:[/red] Model not found at {MODEL_PATH}")
        sys.exit(1)

    app = DictationApp()
    try:
        app.run()
    except KeyboardInterrupt:
        console.print(f"\n[{ORANGE}]👋 Goodbye![/{ORANGE}]\n")


if __name__ == "__main__":
    main()
