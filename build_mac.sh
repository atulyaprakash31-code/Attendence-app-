#!/bin/bash
# =============================================================================
# build_mac.sh — Build AttendanceSystem for macOS
# =============================================================================
# Run this script on a Mac:
#   chmod +x build_mac.sh
#   ./build_mac.sh
#
# Requirements:
#   - Python 3.9+ installed  (check: python3 --version)
#   - Internet connection (to install PyInstaller the first time)
#
# Output:
#   dist/AttendanceSystem           ← Unix binary (run from Terminal)
#   dist/AttendanceSystem.app       ← Double-clickable .app (opens Terminal)
# =============================================================================

set -e

echo ""
echo "=============================================="
echo "  Attendance System — macOS Build Script"
echo "=============================================="
echo ""

# --- Check Python 3 ---
if ! command -v python3 &>/dev/null; then
    echo "[!] python3 not found."
    echo "    Install from: https://www.python.org/downloads/"
    exit 1
fi
echo "[✓] $(python3 --version)"

# --- Install / upgrade PyInstaller ---
echo ""
echo "[→] Installing/upgrading PyInstaller..."
python3 -m pip install --quiet --upgrade pyinstaller
echo "[✓] PyInstaller ready: $(pyinstaller --version)"

# --- Clean previous build ---
echo ""
echo "[→] Cleaning previous build..."
rm -rf build dist AttendanceSystem.spec __pycache__
echo "[✓] Clean done."

# --- Build single-file binary ---
echo ""
echo "[→] Building single-file binary..."
pyinstaller \
    --onefile \
    --console \
    --name AttendanceSystem \
    --clean \
    attendance_system.py

BINARY_PATH="$(pwd)/dist/AttendanceSystem"
BINARY_SIZE=$(du -sh "$BINARY_PATH" | cut -f1)
echo "[✓] Binary built: $BINARY_PATH ($BINARY_SIZE)"

# =============================================================================
# Create a double-clickable .app bundle
#
# Structure:
#   AttendanceSystem.app/
#   └── Contents/
#       ├── Info.plist           ← App metadata
#       └── MacOS/
#           └── AttendanceSystem ← Shell script that opens Terminal
#
# When the user double-clicks the .app, macOS runs the MacOS/ script.
# That script uses AppleScript to open a new Terminal window and run
# the actual binary.
# =============================================================================

echo ""
echo "[→] Creating AttendanceSystem.app bundle..."

APP_DIR="dist/AttendanceSystem.app"
MACOS_DIR="$APP_DIR/Contents/MacOS"
mkdir -p "$MACOS_DIR"

# --- Info.plist ---
cat > "$APP_DIR/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>AttendanceSystem</string>
    <key>CFBundleDisplayName</key>
    <string>Attendance System</string>
    <key>CFBundleIdentifier</key>
    <string>com.attendancesystem.app</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>AttendanceSystem</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
PLIST

# --- Launcher shell script (the actual .app executable) ---
# Copies the binary next to the .app so it stays self-contained,
# then opens Terminal.app and runs it.
BINARY_DEST="$APP_DIR/Contents/MacOS/AttendanceSystem_bin"
cp "$BINARY_PATH" "$BINARY_DEST"

cat > "$MACOS_DIR/AttendanceSystem" << 'LAUNCHER'
#!/bin/bash
# Launcher: open a Terminal window and run the attendance system binary.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BINARY="$SCRIPT_DIR/AttendanceSystem_bin"

osascript <<EOF
tell application "Terminal"
    activate
    do script "\"$BINARY\"; exit"
end tell
EOF
LAUNCHER

chmod +x "$MACOS_DIR/AttendanceSystem"
echo "[✓] .app bundle created: dist/AttendanceSystem.app"

# --- Summary ---
echo ""
echo "=============================================="
echo "  Build complete!"
echo ""
echo "  Option A — Run from Terminal (recommended):"
echo "    ./dist/AttendanceSystem"
echo ""
echo "  Option B — Double-click in Finder:"
echo "    dist/AttendanceSystem.app"
echo "    (Opens a new Terminal window automatically)"
echo ""
echo "  Attendance data is stored in:"
echo "    ~/Documents/Attendance System/AttendanceData/"
echo "    (Never inside the app — safe to update/replace)"
echo "=============================================="
echo ""
