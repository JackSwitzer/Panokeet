"""Whisper transcription module using whisper.cpp."""

import subprocess
from pathlib import Path

MODEL_PATH = Path(__file__).parent / "models" / "ggml-medium.bin"
THREADS = 4


def transcribe(audio_path: Path) -> str:
    """
    Transcribe audio file using whisper.cpp.

    Args:
        audio_path: Path to WAV file (16kHz mono)

    Returns:
        Transcribed text or empty string on error
    """
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    result = subprocess.run(
        [
            "nice", "-n", "10",  # Lower priority
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

    # Clean up output
    text = result.stdout.strip()
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return ' '.join(lines)


def check_model():
    """Check if the whisper model exists."""
    return MODEL_PATH.exists()


def get_model_name():
    """Get the model filename."""
    return MODEL_PATH.name
