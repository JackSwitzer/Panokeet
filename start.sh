#!/bin/bash
# Panokeet Launcher - Starts both Python backend and SwiftUI frontend

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🦜 Starting Panokeet..."

# Start Python backend
echo "Starting backend server..."
source .venv/bin/activate
python backend/server.py &
BACKEND_PID=$!

# Wait for backend to be ready
sleep 2

# Check if backend started
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ Backend failed to start"
    exit 1
fi

echo "✓ Backend running on http://localhost:8765"

# Start SwiftUI app
APP_PATH="$SCRIPT_DIR/PanokeetUI.app"
if [ -d "$APP_PATH" ]; then
    echo "Starting SwiftUI frontend..."
    open "$APP_PATH"
    echo "✓ Panokeet UI started"
else
    echo ""
    echo "⚠️  SwiftUI app not found at $APP_PATH"
    echo "   Run: xcodebuild -scheme PanokeetUI build"
    echo "   Then copy the .app to this folder"
    echo ""
fi

echo ""
echo "Press Ctrl+C to stop backend server."

# Wait for backend
wait $BACKEND_PID
