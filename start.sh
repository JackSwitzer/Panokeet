#!/bin/bash
# Panokeet Launcher - Starts both Python backend and SwiftUI frontend

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🦜 Starting Panokeet..."

# Kill any existing instances first
echo "Cleaning up old processes..."
launchctl unload ~/Library/LaunchAgents/com.panokeet.backend.plist 2>/dev/null
pkill -9 -f "PanokeetUI" 2>/dev/null
pkill -9 -f "server.py" 2>/dev/null
pkill -9 -f "uvicorn" 2>/dev/null

# Force kill anything on port 8765, retry until clear
for i in {1..5}; do
    pid=$(lsof -ti:8765 2>/dev/null)
    [ -z "$pid" ] && break
    kill -9 $pid 2>/dev/null
    sleep 0.5
done

# Start Python backend
echo "Starting backend server..."
source .venv/bin/activate
uv run python backend/server.py &
BACKEND_PID=$!

# Wait for backend to be ready
sleep 2

# Check if backend started
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ Backend failed to start"
    exit 1
fi

echo "✓ Backend running on http://localhost:8765"

# Start SwiftUI app - find in standard Xcode DerivedData location
APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData/PanokeetUI-*/Build/Products/Release -name "PanokeetUI.app" -type d 2>/dev/null | head -1)
if [ -d "$APP_PATH" ]; then
    echo "Starting SwiftUI frontend..."
    open "$APP_PATH"
    echo "✓ Panokeet UI started"
else
    echo ""
    echo "⚠️  SwiftUI app not found in DerivedData"
    echo "   Run: cd PanokeetUI && xcodebuild -scheme PanokeetUI -configuration Release build"
    echo ""
fi

echo ""
echo "Press Ctrl+C to stop backend server."

# Wait for backend
wait $BACKEND_PID
