#!/usr/bin/env python3
"""
Panokeet Backend - FastAPI server for SwiftUI frontend

Endpoints:
  POST /record/start  - Start recording
  POST /record/stop   - Stop recording and transcribe
  POST /save          - Save training data
  POST /cancel        - Cancel current transcription
  GET  /status        - Get current status
"""

import subprocess
import tempfile
import wave
import shutil
import json
import os
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

import numpy as np
import sounddevice as sd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Paths
APP_DIR = Path(__file__).parent.parent
MODEL_PATH = APP_DIR / "models" / "ggml-medium.bin"
DATA_DIR = APP_DIR / "training_data"
SAMPLE_RATE = 16000


class RecorderState:
    """Manages recording state and audio data."""

    def __init__(self):
        self.recording = False
        self.audio_data = []
        self.stream = None
        self.temp_audio_path = None
        self.last_transcript = None
        self.last_duration = None
        self.current_level = 0.0

    def start_recording(self):
        if self.recording:
            return {"success": False, "error": "Already recording"}

        self.audio_data = []
        self.temp_audio_path = None
        self.last_transcript = None
        self.current_level = 0.0

        def callback(indata, frames, t, status):
            if self.recording:
                self.audio_data.append(indata.copy())
                self.current_level = float(np.sqrt(np.mean(indata**2)))

        try:
            # Check for available input devices first
            devices = sd.query_devices()
            input_devices = [d for d in devices if d['max_input_channels'] > 0]
            if not input_devices:
                print("❌ No audio input devices found")
                return {"success": False, "error": "No audio input device found. Please connect a microphone."}

            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype=np.float32,
                callback=callback
            )
            self.stream.start()
            self.recording = True
            print("🔴 Recording started")
            return {"success": True}

        except sd.PortAudioError as e:
            error_msg = str(e)
            if "device" in error_msg.lower():
                print(f"❌ Audio device error: {e}")
                return {"success": False, "error": "No audio input device connected. Please connect a microphone."}
            print(f"❌ PortAudio error: {e}")
            return {"success": False, "error": f"Audio system error: {e}"}
        except Exception as e:
            print(f"❌ Recording error: {e}")
            return {"success": False, "error": f"Failed to start recording: {e}"}

    def stop_recording(self):
        if not self.recording:
            return None, 0

        self.recording = False

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if not self.audio_data:
            print("No audio captured")
            return None, 0

        # Concatenate audio
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

        print(f"⏹ Recording stopped ({duration:.1f}s)")
        return self.temp_audio_path, duration

    def transcribe(self, audio_path):
        """Transcribe audio using whisper-cli."""
        print("⏳ Transcribing...")

        try:
            result = subprocess.run(
                ["/opt/homebrew/bin/whisper-cli", "-m", str(MODEL_PATH), "-f", audio_path,
                 "--no-timestamps", "-t", "4", "-l", "en"],
                capture_output=True, text=True, timeout=120
            )

            if result.returncode != 0:
                print(f"❌ whisper-cli failed (code {result.returncode})")
                if result.stderr:
                    print(f"   stderr: {result.stderr[:500]}")
                return None

            text = ' '.join([l.strip() for l in result.stdout.strip().split('\n') if l.strip()])
            self.last_transcript = text
            print(f"📝 {text}")
            return text

        except subprocess.TimeoutExpired:
            print("❌ Transcription timed out (>120s)")
            return None
        except FileNotFoundError:
            print("❌ whisper-cli not found at /opt/homebrew/bin/whisper-cli")
            return None
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            return None

    def cleanup_temp(self):
        """Remove temporary audio file."""
        if self.temp_audio_path and os.path.exists(self.temp_audio_path):
            os.unlink(self.temp_audio_path)
            self.temp_audio_path = None


# Global state
recorder = RecorderState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    DATA_DIR.mkdir(exist_ok=True)
    print(f"\n{'='*50}")
    print("🦜 PANOKEET BACKEND")
    print(f"{'='*50}")
    print(f"Model: {MODEL_PATH.name}")
    print(f"Data: {DATA_DIR}/")
    print(f"API: http://localhost:8765")
    print(f"{'='*50}\n")
    yield
    # Cleanup on shutdown
    recorder.cleanup_temp()


app = FastAPI(title="Panokeet Backend", lifespan=lifespan)

# Allow CORS for SwiftUI app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class TranscriptResult(BaseModel):
    transcript: str
    duration: float


class SaveRequest(BaseModel):
    raw_text: str
    final_text: str
    duration: float
    was_edited: bool


class StatusResponse(BaseModel):
    status: str
    recording: bool


@app.post("/toggle")
async def toggle_recording():
    """Toggle recording on/off."""
    if recorder.recording:
        # Stop and transcribe
        audio_path, duration = recorder.stop_recording()
        if not audio_path:
            return {"status": "ready", "action": "stopped", "error": "No audio"}

        recorder.last_duration = duration
        transcript = recorder.transcribe(audio_path)

        if not transcript:
            recorder.cleanup_temp()
            return {"status": "ready", "action": "stopped", "error": "No speech"}

        return {"status": "transcribed", "action": "stopped", "transcript": transcript, "duration": duration}
    else:
        # Start recording
        result = recorder.start_recording()
        if not result.get("success"):
            return {"status": "error", "action": "failed", "error": result.get("error", "Unknown error")}
        return {"status": "recording", "action": "started"}


@app.post("/record/start")
async def start_recording():
    """Start audio recording."""
    if recorder.recording:
        return {"status": "already_recording"}

    result = recorder.start_recording()
    if not result.get("success"):
        return {"status": "error", "error": result.get("error", "Unknown error")}
    return {"status": "recording"}


@app.post("/record/stop")
async def stop_recording() -> TranscriptResult:
    """Stop recording and return transcription."""
    if not recorder.recording:
        raise HTTPException(status_code=400, detail="Not recording")

    audio_path, duration = recorder.stop_recording()

    if not audio_path:
        raise HTTPException(status_code=400, detail="No audio captured")

    recorder.last_duration = duration

    # Transcribe
    transcript = recorder.transcribe(audio_path)

    if not transcript:
        recorder.cleanup_temp()
        raise HTTPException(status_code=400, detail="No speech detected")

    return TranscriptResult(transcript=transcript, duration=duration)


@app.post("/save")
async def save_transcript(request: SaveRequest):
    """Save training data (audio + metadata)."""
    DATA_DIR.mkdir(exist_ok=True)

    # Get next number
    existing = list(DATA_DIR.glob("audio_*.wav"))
    nums = [int(f.stem.split('_')[1]) for f in existing if f.stem.split('_')[1].isdigit()]
    num = max(nums, default=0) + 1

    # Move audio file
    audio_path = DATA_DIR / f"audio_{num:06d}.wav"
    if recorder.temp_audio_path and os.path.exists(recorder.temp_audio_path):
        shutil.move(recorder.temp_audio_path, str(audio_path))
        recorder.temp_audio_path = None

    # Save metadata JSON
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "duration": round(request.duration, 2),
        "raw_transcript": request.raw_text,
        "final_transcript": request.final_text,
        "was_edited": request.was_edited,
        "needs_review": not request.was_edited
    }
    json_path = DATA_DIR / f"audio_{num:06d}.json"
    with open(json_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    # Also save plain text
    txt_path = DATA_DIR / f"audio_{num:06d}.txt"
    txt_path.write_text(request.final_text)

    print(f"💾 Saved audio_{num:06d} ({request.duration:.1f}s)")
    return {"status": "saved", "id": num}


@app.post("/cancel")
async def cancel_transcript():
    """Cancel current transcription and cleanup."""
    recorder.cleanup_temp()
    print("❌ Cancelled")
    return {"status": "cancelled"}


@app.get("/status")
async def get_status() -> StatusResponse:
    """Get current recorder status."""
    if recorder.recording:
        return StatusResponse(status="recording", recording=True)
    return StatusResponse(status="ready", recording=False)


@app.get("/pending")
async def get_pending():
    """Get pending transcript for UI to display."""
    if recorder.last_transcript and recorder.temp_audio_path:
        return {
            "pending": True,
            "transcript": recorder.last_transcript,
            "duration": recorder.last_duration or 0
        }
    return {"pending": False}


@app.get("/level")
async def get_level():
    """Get current audio level for waveform visualization."""
    return {"level": recorder.current_level, "recording": recorder.recording}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "model": MODEL_PATH.name}


def main():
    """Run the server."""
    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
        log_level="warning"
    )


if __name__ == "__main__":
    main()
