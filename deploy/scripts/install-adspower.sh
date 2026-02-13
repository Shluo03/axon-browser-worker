#!/bin/bash
# install-adspower.sh - Download and install AdsPower
# This script downloads AdsPower but you still need to activate it manually via GUI

set -e

ADSPOWER_DIR="/opt/adspower"
DOWNLOAD_URL="https://adspower.com/download/AdsPower-Global-5.9.14-x64.tar.gz"

echo "=========================================="
echo "  AdsPower Installation"
echo "=========================================="

# Check if already installed
if [ -f "$ADSPOWER_DIR/AdsPower" ]; then
    echo "AdsPower already installed at $ADSPOWER_DIR"
    echo "To reinstall, remove the directory first: sudo rm -rf $ADSPOWER_DIR"
    exit 0
fi

# Create directory
echo "[1/4] Creating directory..."
sudo mkdir -p "$ADSPOWER_DIR"
sudo chown axon:axon "$ADSPOWER_DIR"

# Download
echo "[2/4] Downloading AdsPower..."
echo "Note: If this URL is outdated, download manually from https://www.adspower.com/download"
cd /tmp

# Try to download, but don't fail if URL is outdated
if wget -q --show-progress "$DOWNLOAD_URL" -O adspower.tar.gz 2>/dev/null; then
    echo "  Downloaded successfully"
else
    echo ""
    echo "  ✗ Automatic download failed (URL may be outdated)"
    echo ""
    echo "  Please download manually:"
    echo "    1. Visit https://www.adspower.com/download"
    echo "    2. Download Linux version"
    echo "    3. Copy to VM: scp AdsPower*.tar.gz ubuntu@<vm-ip>:/tmp/"
    echo "    4. Re-run this script"
    echo ""

    # Check if file exists from manual download
    if ls /tmp/AdsPower*.tar.gz 1> /dev/null 2>&1; then
        echo "  Found manually downloaded file, continuing..."
        mv /tmp/AdsPower*.tar.gz /tmp/adspower.tar.gz
    else
        exit 1
    fi
fi

# Extract
echo "[3/4] Extracting..."
cd "$ADSPOWER_DIR"
tar -xzf /tmp/adspower.tar.gz --strip-components=1 || tar -xzf /tmp/adspower.tar.gz
rm /tmp/adspower.tar.gz
echo "  Extracted to $ADSPOWER_DIR"

# Make executable
chmod +x "$ADSPOWER_DIR/AdsPower"

# Create systemd service
echo "[4/4] Creating systemd service..."
sudo tee /etc/systemd/system/adspower.service > /dev/null << EOF
[Unit]
Description=AdsPower Browser
After=network.target xvfb.service
Requires=xvfb.service

[Service]
Type=simple
User=axon
Group=axon
Environment=DISPLAY=:99
WorkingDirectory=$ADSPOWER_DIR
ExecStart=$ADSPOWER_DIR/AdsPower
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
echo "  Created adspower.service"

echo ""
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo ""
echo "IMPORTANT: You need to activate AdsPower license manually!"
echo ""
echo "Steps:"
echo "  1. Connect via VNC: vnc://<server-ip>:5900"
echo "  2. Start AdsPower:"
echo "     sudo systemctl start adspower"
echo "  3. In the GUI, log in with your AdsPower account"
echo "  4. Activate your license"
echo ""
echo "After activation:"
echo "  sudo systemctl enable adspower"
echo "  sudo systemctl start browser-worker"
echo ""
