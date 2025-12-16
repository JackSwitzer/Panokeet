# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Whisper Dictation - Local speech-to-text tool using whisper.cpp on macOS Apple Silicon.

## Tech Stack

- Python 3.13 with uv for package management
- whisper.cpp via Homebrew for transcription (Metal/GPU accelerated)
- Whisper large-v3 model (~3GB in models/)

## Commands

```bash
# Run the dictation tool
uv run python dictate.py

# Add dependencies
uv add <package>
```

## Architecture

- `dictate.py` - Main script with hotkey listener, audio recording, and whisper.cpp integration
- `models/ggml-large-v3.bin` - Whisper model file (not in git)
- `training_data/` - Saved audio+text pairs for future fine-tuning (not in git)

## Key Bindings

- **Cmd+1** - Toggle recording on/off (auto-saves when stopped)
- **Cmd+2 (hold)** - Hold to speak (auto-saves on release)
- **Esc** - Quit

## Training Data Format

Auto-saved on each recording:
- `training_data/audio_000001.wav` - 16kHz mono audio
- `training_data/audio_000001.txt` - Transcription text

## Important Notes

- Requires Accessibility permissions for global hotkey listening
- whisper.cpp uses Metal for GPU acceleration on Apple Silicon
- Audio recorded at 16kHz mono (Whisper's expected format)
