#!/usr/bin/env python3
"""Simple test - press Enter to start/stop recording. No hotkeys needed."""

import subprocess
import tempfile
import wave
import shutil
import os
from pathlib import Path
from datetime import datetime
import numpy as np
import sounddevice as sd
from AppKit import NSSound, NSPasteboard, NSPasteboardTypeString

APP_DIR = Path(__file__).parent
MODEL_PATH = APP_DIR / "models" / "ggml-medium.bin"
DATA_DIR = APP_DIR / "training_data"
SAMPLE_RATE = 16000

def play_sound(name):
    sounds = {"start": "Morse", "stop": "Tink", "done": "Glass"}
    s = NSSound.soundNamed_(sounds.get(name, ""))
    if s:
        s.play()

def record_audio():
    """Record until user presses Enter."""
    audio_data = []
    recording = True

    def callback(indata, frames, time, status):
        if recording:
            audio_data.append(indata.copy())

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype=np.float32, callback=callback)
    stream.start()
    play_sound("start")

    print("\n🔴 RECORDING... Press Enter to stop.")
    input()

    recording = False
    stream.stop()
    stream.close()
    play_sound("stop")

    if not audio_data:
        return None, 0

    audio = np.concatenate(audio_data, axis=0)
    duration = len(audio) / SAMPLE_RATE

    # Save to temp file
    temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    audio_int16 = (audio * 32767).astype(np.int16)
    with wave.open(temp.name, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())

    return temp.name, duration

def transcribe(audio_path):
    result = subprocess.run(
        ["whisper-cli", "-m", str(MODEL_PATH), "-f", audio_path,
         "--no-timestamps", "-t", "4", "-l", "en"],
        capture_output=True, text=True
    )
    return ' '.join([l.strip() for l in result.stdout.strip().split('\n') if l.strip()])

def main():
    print("\n" + "="*50)
    print("🦜 PANOKEET - Simple Test")
    print("="*50)
    print("Press Enter to START recording")
    print("Press Enter again to STOP and transcribe")
    print("Type 'q' to quit")
    print("="*50)

    DATA_DIR.mkdir(exist_ok=True)

    while True:
        cmd = input("\n🎤 Press Enter to record (or 'q' to quit): ").strip().lower()
        if cmd == 'q':
            print("👋 Goodbye!")
            break

        # Record
        audio_path, duration = record_audio()
        if not audio_path:
            print("No audio captured")
            continue

        print(f"✓ Recorded {duration:.1f}s")
        print("⏳ Transcribing...")

        # Transcribe
        text = transcribe(audio_path)

        if text:
            play_sound("done")
            print(f"\n📝 Transcription:")
            print(f"   {text}")

            # Save
            existing = list(DATA_DIR.glob("audio_*.wav"))
            num = max([int(f.stem.split('_')[1]) for f in existing], default=0) + 1

            audio_dest = DATA_DIR / f"audio_{num:06d}.wav"
            text_dest = DATA_DIR / f"audio_{num:06d}.txt"

            shutil.move(audio_path, str(audio_dest))
            text_dest.write_text(text)

            # Copy to clipboard
            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.setString_forType_(text, NSPasteboardTypeString)

            print(f"💾 Saved: audio_{num:06d}")
            print("📋 Copied to clipboard!")
        else:
            print("❌ No speech detected")
            os.unlink(audio_path)

if __name__ == "__main__":
    main()
