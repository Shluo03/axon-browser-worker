#!/bin/bash
# setup-worker.sh - Setup Browser Worker on VM
# Run this on the VM after cloning the repo

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=========================================="
echo "  Axon Browser Worker Setup"
echo "=========================================="
echo "Project directory: $PROJECT_DIR"
echo ""

# Check if running as axon user
if [ "$USER" != "axon" ] && [ "$USER" != "ubuntu" ]; then
    echo "Warning: Running as $USER, recommended to run as axon or ubuntu"
fi

# 1. Create Python virtual environment
echo "[1/5] Setting up Python environment..."
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "  Created virtual environment"
else
    echo "  Virtual environment already exists"
fi

source .venv/bin/activate

# 2. Install dependencies
echo "[2/5] Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  Dependencies installed"

# 3. Create config file
echo "[3/5] Creating configuration..."
CONFIG_FILE="$PROJECT_DIR/config.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" << 'EOF'
# Axon Browser Worker Configuration
server:
  host: 0.0.0.0
  port: 8080

adspower:
  api_url: http://127.0.0.1:50325
  timeout: 30

worker:
  artifacts_dir: /data/artifacts
  max_concurrent: 5

# Uncomment to register with central server
# central:
#   url: http://your-central-server.com
#   api_key: your-api-key
EOF
    echo "  Created config.yaml"
else
    echo "  config.yaml already exists"
fi

# 4. Create systemd service
echo "[4/5] Setting up systemd service..."
SERVICE_FILE="/etc/systemd/system/browser-worker.service"

if [ ! -f "$SERVICE_FILE" ]; then
    sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Axon Browser Worker
After=network.target xvfb.service
Wants=xvfb.service

[Service]
Type=simple
User=axon
Group=axon
WorkingDirectory=$PROJECT_DIR
Environment=DISPLAY=:99
Environment=PATH=$PROJECT_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$PROJECT_DIR/.venv/bin/uvicorn src.server:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    echo "  Created systemd service"
else
    echo "  systemd service already exists"
fi

# 5. Check AdsPower
echo "[5/5] Checking AdsPower..."
if curl -s http://127.0.0.1:50325/status > /dev/null 2>&1; then
    echo "  ✓ AdsPower is running"
else
    echo "  ✗ AdsPower is NOT running"
    echo ""
    echo "  To install AdsPower:"
    echo "    1. Download from https://www.adspower.com/download"
    echo "    2. Extract to /opt/adspower"
    echo "    3. Run: DISPLAY=:99 /opt/adspower/AdsPower"
    echo "    4. Activate your license in the GUI (via VNC)"
    echo ""
fi

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Install & start AdsPower (if not done):"
echo "     DISPLAY=:99 /opt/adspower/AdsPower &"
echo ""
echo "  2. Start Browser Worker:"
echo "     sudo systemctl start browser-worker"
echo "     sudo systemctl enable browser-worker"
echo ""
echo "  3. Check status:"
echo "     sudo systemctl status browser-worker"
echo "     curl http://localhost:8080/health"
echo ""
echo "  4. View logs:"
echo "     journalctl -u browser-worker -f"
echo ""
echo "  5. Connect via VNC (for AdsPower GUI):"
echo "     vnc://<server-ip>:5900"
echo ""
