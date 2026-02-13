#!/bin/bash
# health-check.sh - Check all services are running correctly

echo "=========================================="
echo "  Axon Browser Worker Health Check"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_service() {
    local name=$1
    local service=$2

    if systemctl is-active --quiet "$service"; then
        echo -e "  ${GREEN}✓${NC} $name"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name (not running)"
        return 1
    fi
}

check_port() {
    local name=$1
    local port=$2
    local url=$3

    if curl -s "$url" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} $name (port $port)"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name (port $port not responding)"
        return 1
    fi
}

echo "Services:"
check_service "Xvfb (virtual display)" "xvfb"
check_service "X11VNC (remote view)" "x11vnc"
check_service "Fluxbox (window manager)" "fluxbox"
check_service "AdsPower" "adspower"
check_service "Browser Worker" "browser-worker"

echo ""
echo "API Endpoints:"
check_port "AdsPower API" "50325" "http://127.0.0.1:50325/status"
check_port "Browser Worker API" "8080" "http://127.0.0.1:8080/health"

echo ""
echo "Network:"
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "unknown")
echo "  Public IP: $PUBLIC_IP"
echo ""

# Check disk space
echo "Disk Usage:"
df -h / | tail -1 | awk '{print "  Root: " $5 " used (" $4 " free)"}'
df -h /data 2>/dev/null | tail -1 | awk '{print "  Data: " $5 " used (" $4 " free)"}' || echo "  Data: /data not mounted"

echo ""
echo "Memory:"
free -h | grep Mem | awk '{print "  " $3 " used / " $2 " total"}'

echo ""
echo "=========================================="

# Final status
if check_port "Worker" "8080" "http://127.0.0.1:8080/health" > /dev/null 2>&1; then
    echo -e "${GREEN}Status: HEALTHY${NC}"
    echo ""
    echo "Worker API: http://$PUBLIC_IP:8080"
    echo "VNC Access: vnc://$PUBLIC_IP:5900"
else
    echo -e "${YELLOW}Status: DEGRADED${NC}"
    echo ""
    echo "Run these commands to diagnose:"
    echo "  journalctl -u browser-worker -n 50"
    echo "  journalctl -u adspower -n 50"
fi
