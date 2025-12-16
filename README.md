# Panokeet

Local voice-to-text dictation for macOS using whisper.cpp. Fast, private, runs entirely on your Mac.

![Status: Recording](https://img.shields.io/badge/Status-Active-green)
![Platform: macOS](https://img.shields.io/badge/Platform-macOS%20(Apple%20Silicon)-blue)

## Features

- **Global hotkey** - Toggle recording from anywhere with Cmd+Keypad7
- **Fast transcription** - GPU-accelerated via Metal on Apple Silicon
- **Privacy first** - Everything runs locally, no data leaves your Mac
- **Training data** - Optionally save audio/text pairs for future fine-tuning

## Quick Start

```bash
./start.sh
```

See [SETUP.md](SETUP.md) for installation instructions.

## How It Works

1. Press **Cmd+Keypad7** to start recording
2. Speak into your microphone
3. Press **Cmd+Keypad7** again to stop
4. Edit the transcript if needed, then press **Enter** to save & copy to clipboard

## Architecture

```
┌─────────────────┐     HTTP      ┌─────────────────┐
│   SwiftUI App   │◄────────────►│  Python Backend │
│   (Menu Bar)    │   :8765      │   (FastAPI)     │
└─────────────────┘              └────────┬────────┘
                                          │
                                          ▼
                                 ┌─────────────────┐
                                 │   whisper.cpp   │
                                 │  (Metal/GPU)    │
                                 └─────────────────┘
```

## License

MIT
