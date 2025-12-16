#!/usr/bin/env python3
"""Simple test: record 5 seconds, transcribe, save."""

import subprocess
import wave
import time
from pathlib import Path
import numpy as np
import sounddevice as sd

MODEL_PATH = Path(__file__).parent / "models" / "ggml-medium.bin"
DATA_DIR = Path(__file__).parent / "training_data"
SAMPLE_RATE = 16000

print("🎙️  Recording for 5 seconds... speak now!")
print()

# Record 5 seconds
audio = sd.rec(int(5 * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype=np.float32)
sd.wait()

print("✓ Recording done")

# Save to WAV
DATA_DIR.mkdir(exist_ok=True)
audio_path = DATA_DIR / "test_recording.wav"
audio_int16 = (audio * 32767).astype(np.int16)

with wave.open(str(audio_path), 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(audio_int16.tobytes())

print(f"💾 Saved audio: {audio_path}")
print()
print("⏳ Transcribing...")

# Transcribe
result = subprocess.run(
    ["whisper-cli", "-m", str(MODEL_PATH), "-f", str(audio_path), "--no-timestamps", "-t", "4", "-l", "en"],
    capture_output=True,
    text=True
)

if result.returncode != 0:
    print(f"Error: {result.stderr}")
else:
    text = ' '.join([line.strip() for line in result.stdout.strip().split('\n') if line.strip()])
    print(f"📝 Transcription: {text}")

    # Save transcription
    text_path = DATA_DIR / "test_recording.txt"
    text_path.write_text(text)
    print(f"💾 Saved text: {text_path}")

print()
print("Done! Check training_data/ folder.")
