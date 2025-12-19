#!/bin/bash
# Panokeet - Smart launcher with built-in setup
# If everything is installed: launches the app
# If something is missing: shows setup menu

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Quick check if setup is needed
needs_setup() {
    # Check whisper-cli
    command -v whisper-cli &> /dev/null || return 0
    # Check model
    [ -f "$SCRIPT_DIR/models/ggml-medium.bin" ] || return 0
    # Check Python venv
    [ -d "$SCRIPT_DIR/.venv" ] || return 0
    # Check SwiftUI app
    find ~/Library/Developer/Xcode/DerivedData/PanokeetUI-*/Build/Products/Release -name "PanokeetUI.app" -type d 2>/dev/null | head -1 | grep -q . || return 0
    # All good
    return 1
}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Whisper models with sizes
declare -A WHISPER_MODELS
WHISPER_MODELS=(
    ["tiny"]="75 MB|~1 GB RAM|Fastest, lowest accuracy"
    ["base"]="142 MB|~1 GB RAM|Fast, basic accuracy"
    ["small"]="466 MB|~2 GB RAM|Good balance"
    ["medium"]="1.5 GB|~5 GB RAM|High accuracy (recommended)"
    ["large"]="2.9 GB|~10 GB RAM|Best accuracy, slowest"
)

print_header() {
    clear
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║   🦜  PANOKEET SETUP                                         ║"
    echo "║       Local Voice-to-Text Dictation for macOS                ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

get_disk_space() {
    df -h "$SCRIPT_DIR" | awk 'NR==2 {print $4}'
}

get_ram() {
    sysctl -n hw.memsize | awk '{print int($1/1024/1024/1024)" GB"}'
}

check_command() {
    command -v "$1" &> /dev/null
}

# ============================================================================
# SYSTEM CHECK
# ============================================================================
check_system() {
    print_header
    echo -e "${BOLD}System Requirements Check${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # macOS version
    MACOS_VERSION=$(sw_vers -productVersion)
    echo -e "macOS Version:     ${CYAN}$MACOS_VERSION${NC}"

    # Architecture
    ARCH=$(uname -m)
    echo -e "Architecture:      ${CYAN}$ARCH${NC}"
    if [[ "$ARCH" == "arm64" ]]; then
        print_status "Apple Silicon detected (Metal acceleration available)"
    else
        print_warning "Intel Mac - whisper.cpp will use CPU only"
    fi

    # RAM
    RAM=$(get_ram)
    echo -e "System RAM:        ${CYAN}$RAM${NC}"

    # Disk Space
    DISK=$(get_disk_space)
    echo -e "Available Space:   ${CYAN}$DISK${NC}"

    echo ""
    echo -e "${BOLD}Required Dependencies${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Homebrew
    if check_command brew; then
        BREW_VERSION=$(brew --version | head -1)
        print_status "Homebrew: $BREW_VERSION"
    else
        print_error "Homebrew: Not installed"
        echo "         Install: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    fi

    # Xcode CLI
    if xcode-select -p &> /dev/null; then
        print_status "Xcode CLI Tools: Installed"
    else
        print_error "Xcode CLI Tools: Not installed"
        echo "         Install: xcode-select --install"
    fi

    # whisper.cpp
    if check_command whisper-cli; then
        WHISPER_PATH=$(which whisper-cli)
        print_status "whisper-cli: $WHISPER_PATH"
    else
        print_warning "whisper-cli: Not installed (required for transcription)"
    fi

    # uv
    if check_command uv; then
        UV_VERSION=$(uv --version)
        print_status "uv: $UV_VERSION"
    else
        print_warning "uv: Not installed (Python package manager)"
    fi

    # Python venv
    if [ -d "$SCRIPT_DIR/.venv" ]; then
        print_status "Python venv: Created"
    else
        print_warning "Python venv: Not created"
    fi

    # Whisper model
    if [ -f "$SCRIPT_DIR/models/ggml-medium.bin" ]; then
        MODEL_SIZE=$(ls -lh "$SCRIPT_DIR/models/ggml-medium.bin" | awk '{print $5}')
        print_status "Whisper model: ggml-medium.bin ($MODEL_SIZE)"
    else
        print_warning "Whisper model: Not downloaded"
    fi

    # SwiftUI app
    APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData/PanokeetUI-*/Build/Products/Release -name "PanokeetUI.app" -type d 2>/dev/null | head -1)
    if [ -d "$APP_PATH" ]; then
        print_status "PanokeetUI.app: Built"
    else
        print_warning "PanokeetUI.app: Not built"
    fi

    echo ""
    read -p "Press Enter to continue..."
}

# ============================================================================
# INSTALL WHISPER
# ============================================================================
install_whisper() {
    print_header
    echo -e "${BOLD}Install whisper.cpp${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "whisper.cpp is a C/C++ port of OpenAI's Whisper model."
    echo "On Apple Silicon, it uses Metal for GPU acceleration."
    echo ""

    if check_command whisper-cli; then
        print_status "whisper-cli is already installed"
        echo ""
    else
        echo -e "${BOLD}Installing whisper.cpp via Homebrew...${NC}"
        echo ""

        if ! check_command brew; then
            print_error "Homebrew is required. Please install it first."
            read -p "Press Enter to continue..."
            return
        fi

        brew install whisper-cpp

        if check_command whisper-cli; then
            print_status "whisper-cli installed successfully"
        else
            print_error "Installation failed"
            read -p "Press Enter to continue..."
            return
        fi
    fi

    echo ""
    echo -e "${BOLD}Select Whisper Model${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Available models:"
    echo ""
    printf "  %-10s %-12s %-15s %s\n" "Model" "Size" "RAM Required" "Notes"
    echo "  ────────── ──────────── ─────────────── ─────────────────────────────"

    i=1
    MODEL_KEYS=(tiny base small medium large)
    for model in "${MODEL_KEYS[@]}"; do
        IFS='|' read -r size ram notes <<< "${WHISPER_MODELS[$model]}"
        if [[ "$model" == "medium" ]]; then
            printf "  ${GREEN}%d) %-8s %-12s %-15s %s (recommended)${NC}\n" $i "$model" "$size" "$ram" "$notes"
        else
            printf "  %d) %-8s %-12s %-15s %s\n" $i "$model" "$size" "$ram" "$notes"
        fi
        ((i++))
    done

    echo ""
    echo "  Your system: $(get_ram) RAM, $(get_disk_space) available"
    echo ""
    read -p "Select model [1-5, default=4 (medium)]: " MODEL_CHOICE
    MODEL_CHOICE=${MODEL_CHOICE:-4}

    case $MODEL_CHOICE in
        1) SELECTED_MODEL="tiny" ;;
        2) SELECTED_MODEL="base" ;;
        3) SELECTED_MODEL="small" ;;
        4) SELECTED_MODEL="medium" ;;
        5) SELECTED_MODEL="large" ;;
        *) SELECTED_MODEL="medium" ;;
    esac

    echo ""
    echo -e "${BOLD}Downloading ggml-${SELECTED_MODEL}.bin...${NC}"

    mkdir -p "$SCRIPT_DIR/models"
    MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-${SELECTED_MODEL}.bin"
    MODEL_PATH="$SCRIPT_DIR/models/ggml-${SELECTED_MODEL}.bin"

    if [ -f "$MODEL_PATH" ]; then
        print_status "Model already exists at $MODEL_PATH"
    else
        curl -L --progress-bar "$MODEL_URL" -o "$MODEL_PATH"
        print_status "Model downloaded to $MODEL_PATH"
    fi

    # Update symlink or config to use selected model
    ln -sf "ggml-${SELECTED_MODEL}.bin" "$SCRIPT_DIR/models/ggml-medium.bin" 2>/dev/null || true

    echo ""
    print_status "Whisper setup complete!"
    read -p "Press Enter to continue..."
}

# ============================================================================
# INSTALL PYTHON DEPENDENCIES
# ============================================================================
install_python() {
    print_header
    echo -e "${BOLD}Install Python Dependencies${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Install uv if needed
    if ! check_command uv; then
        echo "Installing uv (fast Python package manager)..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
        print_status "uv installed"
    else
        print_status "uv already installed"
    fi

    echo ""
    echo "Creating Python virtual environment..."
    uv venv --python 3.13 2>/dev/null || uv venv
    print_status "Virtual environment created"

    echo ""
    echo "Installing Python dependencies..."
    uv sync
    print_status "Dependencies installed"

    echo ""
    echo -e "${BOLD}Installed packages:${NC}"
    uv pip list 2>/dev/null | head -15

    echo ""
    print_status "Python setup complete!"
    read -p "Press Enter to continue..."
}

# ============================================================================
# BUILD SWIFTUI APP
# ============================================================================
build_app() {
    print_header
    echo -e "${BOLD}Build SwiftUI App${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    if ! xcode-select -p &> /dev/null; then
        print_error "Xcode Command Line Tools required"
        echo "Install with: xcode-select --install"
        read -p "Press Enter to continue..."
        return
    fi

    echo "Building PanokeetUI (Release)..."
    echo ""

    cd "$SCRIPT_DIR/PanokeetUI"

    xcodebuild -scheme PanokeetUI -configuration Release build 2>&1 | while read line; do
        if [[ "$line" == *"BUILD SUCCEEDED"* ]]; then
            echo -e "${GREEN}$line${NC}"
        elif [[ "$line" == *"error:"* ]]; then
            echo -e "${RED}$line${NC}"
        elif [[ "$line" == *"warning:"* ]]; then
            echo -e "${YELLOW}$line${NC}"
        elif [[ "$line" == *"Compiling"* ]] || [[ "$line" == *"Linking"* ]]; then
            echo "$line"
        fi
    done

    cd "$SCRIPT_DIR"

    APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData/PanokeetUI-*/Build/Products/Release -name "PanokeetUI.app" -type d 2>/dev/null | head -1)
    if [ -d "$APP_PATH" ]; then
        print_status "Build successful!"
        echo "  App location: $APP_PATH"
    else
        print_error "Build may have failed - app not found"
    fi

    echo ""
    read -p "Press Enter to continue..."
}

# ============================================================================
# FULL INSTALL
# ============================================================================
full_install() {
    print_header
    echo -e "${BOLD}Full Installation${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "This will install everything needed to run Panokeet:"
    echo ""
    echo "  1. whisper.cpp (via Homebrew)"
    echo "  2. Whisper model (medium, ~1.5 GB download)"
    echo "  3. Python dependencies (via uv)"
    echo "  4. Build SwiftUI app"
    echo ""
    echo -e "Estimated time: ${CYAN}5-10 minutes${NC} (depending on download speed)"
    echo -e "Disk space needed: ${CYAN}~2 GB${NC}"
    echo ""
    read -p "Continue with full installation? [Y/n]: " CONFIRM
    CONFIRM=${CONFIRM:-Y}

    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        read -p "Press Enter to continue..."
        return
    fi

    echo ""
    echo -e "${BOLD}Step 1/4: Installing whisper.cpp${NC}"
    echo "────────────────────────────────────────────────────────────────"
    if ! check_command whisper-cli; then
        brew install whisper-cpp
    fi
    print_status "whisper.cpp ready"

    echo ""
    echo -e "${BOLD}Step 2/4: Downloading Whisper model${NC}"
    echo "────────────────────────────────────────────────────────────────"
    mkdir -p "$SCRIPT_DIR/models"
    if [ ! -f "$SCRIPT_DIR/models/ggml-medium.bin" ]; then
        curl -L --progress-bar "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin" \
            -o "$SCRIPT_DIR/models/ggml-medium.bin"
    fi
    print_status "Whisper model ready"

    echo ""
    echo -e "${BOLD}Step 3/4: Setting up Python${NC}"
    echo "────────────────────────────────────────────────────────────────"
    if ! check_command uv; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    fi
    uv venv --python 3.13 2>/dev/null || uv venv
    uv sync
    print_status "Python environment ready"

    echo ""
    echo -e "${BOLD}Step 4/4: Building SwiftUI app${NC}"
    echo "────────────────────────────────────────────────────────────────"
    cd "$SCRIPT_DIR/PanokeetUI"
    xcodebuild -scheme PanokeetUI -configuration Release build -quiet
    cd "$SCRIPT_DIR"
    print_status "SwiftUI app built"

    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  Installation complete! 🦜${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "  To start Panokeet, run:"
    echo -e "    ${CYAN}./start.sh${NC}  or  ${CYAN}pan${NC} (if aliased)"
    echo ""
    echo "  Hotkey: Cmd+Keypad7 (configure in Karabiner)"
    echo ""
    read -p "Press Enter to continue..."
}

# ============================================================================
# UNINSTALL
# ============================================================================
uninstall() {
    print_header
    echo -e "${BOLD}Uninstall Panokeet${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "This will remove:"
    echo "  - Python virtual environment (.venv)"
    echo "  - Downloaded whisper models (models/)"
    echo "  - Built app (from DerivedData)"
    echo ""
    echo -e "${YELLOW}Note: whisper-cpp (Homebrew) will NOT be removed${NC}"
    echo ""
    read -p "Are you sure? [y/N]: " CONFIRM

    if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo ""
        rm -rf "$SCRIPT_DIR/.venv" && print_status "Removed .venv"
        rm -rf "$SCRIPT_DIR/models" && print_status "Removed models/"
        rm -rf ~/Library/Developer/Xcode/DerivedData/PanokeetUI-* && print_status "Removed built app"
        echo ""
        print_status "Uninstall complete"
    else
        echo "Cancelled."
    fi

    read -p "Press Enter to continue..."
}

# ============================================================================
# LAUNCH APP (when everything is installed)
# ============================================================================
launch_app() {
    echo "🦜 Starting Panokeet..."

    # Kill any existing instances
    echo "Cleaning up old processes..."
    launchctl unload ~/Library/LaunchAgents/com.panokeet.backend.plist 2>/dev/null || true
    pkill -9 -f "PanokeetUI" 2>/dev/null || true
    pkill -9 -f "server.py" 2>/dev/null || true
    pkill -9 -f "uvicorn" 2>/dev/null || true

    # Clear port 8765
    for i in {1..5}; do
        pid=$(lsof -ti:8765 2>/dev/null) || true
        [ -z "$pid" ] && break
        kill -9 $pid 2>/dev/null || true
        sleep 0.5
    done

    # Start backend
    echo "Starting backend server..."
    source .venv/bin/activate
    uv run python backend/server.py &
    BACKEND_PID=$!

    sleep 2

    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "❌ Backend failed to start"
        exit 1
    fi

    echo "✓ Backend running on http://localhost:8765"

    # Start UI
    APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData/PanokeetUI-*/Build/Products/Release -name "PanokeetUI.app" -type d 2>/dev/null | head -1)
    if [ -d "$APP_PATH" ]; then
        echo "Starting SwiftUI frontend..."
        open "$APP_PATH"
        echo "✓ Panokeet UI started"
    fi

    echo ""
    echo "Press Ctrl+C to stop."
    wait $BACKEND_PID
}

# ============================================================================
# MAIN MENU
# ============================================================================
main_menu() {
    while true; do
        print_header
        echo -e "${BOLD}Setup Menu${NC}"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "  1) Check System Requirements"
        echo "  2) Install whisper.cpp + Model"
        echo "  3) Install Python Dependencies"
        echo "  4) Build SwiftUI App"
        echo ""
        echo "  5) Full Install (All of the above)"
        echo ""
        echo "  6) Uninstall"
        echo "  7) Launch App (skip checks)"
        echo "  0) Exit"
        echo ""
        read -p "Select option: " CHOICE

        case $CHOICE in
            1) check_system ;;
            2) install_whisper ;;
            3) install_python ;;
            4) build_app ;;
            5) full_install ;;
            6) uninstall ;;
            7) launch_app ;;
            0)
                echo ""
                echo "Goodbye! 🦜"
                exit 0
                ;;
            *)
                print_error "Invalid option"
                sleep 1
                ;;
        esac
    done
}

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

# Handle --setup flag to force menu
if [[ "$1" == "--setup" ]] || [[ "$1" == "-s" ]]; then
    main_menu
    exit 0
fi

# Auto-detect: if everything is installed, just launch
if ! needs_setup; then
    launch_app
else
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  Setup required - some dependencies are missing${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    sleep 1
    main_menu
fi
