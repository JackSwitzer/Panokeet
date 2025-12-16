# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Panokeet - Local voice-to-text dictation for macOS. SwiftUI menu bar app + Python backend using whisper.cpp.

## Architecture

```
PanokeetUI (SwiftUI)          backend/server.py (FastAPI)
├── Menu bar app              ├── /status - recording state
├── FloatingPanel popups      ├── /toggle - start/stop recording
├── Polls backend @ 150ms     ├── /level - audio levels
└── State: recording →        ├── /pending - get transcript
    transcribing →            └── /save, /cancel
    showingTranscript
```

## Tech Stack

- **Frontend**: SwiftUI, AppKit (NSPanel for floating windows)
- **Backend**: Python 3.13, FastAPI, uvicorn
- **Transcription**: whisper.cpp via Homebrew (Metal GPU accelerated)
- **Package Manager**: uv

## Key Files

| File | Purpose |
|------|---------|
| `PanokeetUI/PanokeetUI/PanokeetUIApp.swift` | Main app, AppState, PopupView |
| `PanokeetUI/PanokeetUI/FloatingPanel.swift` | NSPanel subclass for floating windows |
| `PanokeetUI/PanokeetUI/APIClient.swift` | HTTP client for backend |
| `backend/server.py` | FastAPI server, audio recording, whisper integration |
| `start.sh` | Launch script for both backend and UI |

## Commands

```bash
# Run everything
./start.sh

# Build UI only
cd PanokeetUI && xcodebuild -scheme PanokeetUI -configuration Release build

# Run backend only
uv run python backend/server.py
```

## State Machine

```
.ready → .recording → .transcribing → .showingTranscript → .ready
           │                              │
           └──── (cancel) ────────────────┘
```

## Important Notes

- PopupView is a unified view that switches content based on AppState.status
- All content views (Recording, Transcribing, Transcript) are same size (500x200)
- Panel stays open through all states, only closes on save/cancel
- Global hotkey: Cmd+Keypad7 → F13 (via Karabiner) → backend toggle
