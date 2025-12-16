# Panokeet Setup Guide

## Prerequisites

- macOS 14+ (Apple Silicon recommended)
- [Homebrew](https://brew.sh)
- [Xcode](https://developer.apple.com/xcode/) (for building the UI)

## Installation

### 1. Install Dependencies

```bash
# Install uv (Python package manager)
brew install uv

# Install whisper.cpp
brew install whisper-cpp
```

### 2. Download Whisper Model

```bash
# Create models directory
mkdir -p models

# Download medium model (~1.5GB, good balance of speed/accuracy)
curl -L "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin" -o models/ggml-medium.bin
```

For better accuracy (slower), use large-v3:
```bash
curl -L "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin" -o models/ggml-large-v3.bin
```

### 3. Setup Python Environment

```bash
# Create virtual environment and install dependencies
uv sync
```

### 4. Build the UI

```bash
cd PanokeetUI
xcodebuild -scheme PanokeetUI -configuration Release -derivedDataPath build build
cd ..
```

### 5. Setup Global Hotkey (Karabiner)

Install [Karabiner-Elements](https://karabiner-elements.pqrs.org/), then add this rule:

1. Open Karabiner-Elements → Complex Modifications → Add your own rule
2. Paste the JSON from [karabiner_rule.md](karabiner_rule.md)

This maps **Cmd+Keypad7** to F13, which the app listens for.

### 6. Grant Permissions

The app needs:
- **Microphone access** - For recording audio
- **Accessibility** - For global hotkey (if not using Karabiner)

Go to System Settings → Privacy & Security and grant these permissions when prompted.

## Running

```bash
./start.sh
```

Or manually:
```bash
# Terminal 1: Start backend
source .venv/bin/activate
uv run python backend/server.py

# Terminal 2: Start UI (or just click the app)
open PanokeetUI/build/Build/Products/Release/PanokeetUI.app
```

## Configuration

Edit `config.json` to customize:

```json
{
  "model": "ggml-medium.bin",
  "language": "en"
}
```

## Troubleshooting

### Port already in use
```bash
lsof -ti:8765 | xargs kill -9
```

### Hotkey not working
- Ensure Karabiner rule is active
- Check System Settings → Privacy & Security → Input Monitoring

### No transcription appearing
- Check backend is running: `curl http://localhost:8765/status`
- Ensure whisper model exists in `models/`
