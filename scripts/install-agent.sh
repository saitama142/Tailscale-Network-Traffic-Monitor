#!/bin/bash
#
# Tailscale Network Monitor - Agent Installation Script
# Installs the monitoring agent
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/tailscale-monitor/agent"
CONFIG_DIR="/etc/tailscale-monitor"
LOG_DIR="/var/log/tailscale-monitor"

echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}Tailscale Network Monitor - Agent${NC}"
echo -e "${BLUE}Installation Script${NC}"
echo -e "${BLUE}=======================================${NC}\n"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo -e "Please run: sudo $0"
    exit 1
fi

# Check for required environment variable
if [ -z "$COLLECTOR_URL" ]; then
    echo -e "${YELLOW}COLLECTOR_URL not set, using interactive mode${NC}\n"
    read -p "Enter collector URL (e.g., http://100.113.155.67:8080): " COLLECTOR_URL
    
    if [ -z "$COLLECTOR_URL" ]; then
        echo -e "${RED}Error: Collector URL is required${NC}"
        exit 1
    fi
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VERSION=$VERSION_ID
else
    echo -e "${RED}Error: Cannot detect OS${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Detected OS: $OS $VERSION"

# Check for Tailscale
echo -e "${YELLOW}Checking Tailscale installation...${NC}"
if ! command -v tailscale &> /dev/null; then
    echo -e "${RED}Error: Tailscale is not installed${NC}"
    echo -e "Please install Tailscale first: https://tailscale.com/download"
    exit 1
fi

# Check if Tailscale is running
if ! tailscale status &> /dev/null; then
    echo -e "${RED}Error: Tailscale is not running${NC}"
    echo -e "Please start Tailscale first"
    exit 1
fi

TAILSCALE_IP=$(ip -4 addr show tailscale0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "")
if [ -z "$TAILSCALE_IP" ]; then
    echo -e "${RED}Error: Could not detect Tailscale IP${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Tailscale is running (IP: $TAILSCALE_IP)\n"

# Check for Python 3.8+
echo -e "${YELLOW}Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION found\n"

# Install system dependencies
echo -e "${YELLOW}Installing system dependencies...${NC}"
case "$OS" in
    ubuntu|debian)
        apt-get update
        apt-get install -y python3-pip python3-venv curl
        ;;
    centos|rhel|fedora)
        yum install -y python3-pip python3-virtualenv curl
        ;;
    *)
        echo -e "${YELLOW}Warning: Unknown OS, skipping dependency installation${NC}"
        ;;
esac
echo -e "${GREEN}✓${NC} Dependencies installed\n"

# Create directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p "$INSTALL_DIR"/{src,config}
mkdir -p "$CONFIG_DIR"
mkdir -p "$LOG_DIR"
echo -e "${GREEN}✓${NC} Directories created\n"

# Download agent files from collector
echo -e "${YELLOW}Downloading agent files from collector...${NC}"

# Try to fetch from collector or use local files
if curl -f -s "${COLLECTOR_URL}/api/v1/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Collector is reachable"
    
    # For now, check if we have local files
    if [ -d "$(dirname "$0")/../agent" ]; then
        SOURCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
        echo -e "${BLUE}Installing from local source${NC}"
        
        cp -r "$SOURCE_DIR/agent/src" "$INSTALL_DIR/"
        cp "$SOURCE_DIR/agent/requirements.txt" "$INSTALL_DIR/"
        cp -r "$SOURCE_DIR/shared" "$(dirname "$INSTALL_DIR")/"
    else
        echo -e "${RED}Error: Agent source files not found${NC}"
        exit 1
    fi
else
    echo -e "${RED}Error: Cannot reach collector at $COLLECTOR_URL${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Files installed\n"

# Create Python virtual environment
echo -e "${YELLOW}Creating Python virtual environment...${NC}"
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
echo -e "${GREEN}✓${NC} Environment ready\n"

# Create configuration file
echo -e "${YELLOW}Creating configuration...${NC}"
cat > "$CONFIG_DIR/agent.yaml" << EOF
collector:
  url: "${COLLECTOR_URL}"
  api_key: null  # Will be set on first run
  timeout: 5
  retry_attempts: 3

monitoring:
  interval: 25
  interface: tailscale0

logging:
  level: INFO
  file: ${LOG_DIR}/agent.log
  max_size_mb: 10
  backup_count: 3
EOF

chmod 600 "$CONFIG_DIR/agent.yaml"
echo -e "${GREEN}✓${NC} Configuration created\n"

# Install systemd service
echo -e "${YELLOW}Installing systemd service...${NC}"
if [ -f "$SOURCE_DIR/systemd/tailscale-monitor-agent.service" ]; then
    cp "$SOURCE_DIR/systemd/tailscale-monitor-agent.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable tailscale-monitor-agent
    echo -e "${GREEN}✓${NC} Service installed and enabled"
else
    echo -e "${YELLOW}Warning: Service file not found${NC}"
fi

# Start service
echo -e "\n${YELLOW}Starting agent service...${NC}"
systemctl start tailscale-monitor-agent
sleep 2

if systemctl is-active --quiet tailscale-monitor-agent; then
    echo -e "${GREEN}✓${NC} Agent service is running\n"
else
    echo -e "${RED}✗${NC} Service failed to start. Check logs with: journalctl -u tailscale-monitor-agent\n"
fi

# Check if registration was successful
sleep 3
if grep -q "api_key: null" "$CONFIG_DIR/agent.yaml"; then
    echo -e "${YELLOW}Note: Agent will register on first successful connection${NC}\n"
else
    echo -e "${GREEN}✓${NC} Agent registered successfully\n"
fi

# Final message
echo -e "${GREEN}=======================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${GREEN}=======================================${NC}\n"

echo -e "${BLUE}Agent Information:${NC}"
echo -e "  Hostname: $(hostname)"
echo -e "  Tailscale IP: $TAILSCALE_IP"
echo -e "  Collector: $COLLECTOR_URL"

echo -e "\n${BLUE}Service Management:${NC}"
echo -e "  sudo systemctl status tailscale-monitor-agent"
echo -e "  sudo systemctl stop tailscale-monitor-agent"
echo -e "  sudo systemctl start tailscale-monitor-agent"
echo -e "  sudo journalctl -u tailscale-monitor-agent -f"

echo -e "\n${BLUE}Configuration:${NC}"
echo -e "  Config file: $CONFIG_DIR/agent.yaml"
echo -e "  Log file: $LOG_DIR/agent.log"

echo -e "\n${YELLOW}The agent is now monitoring network traffic and sending metrics to the collector.${NC}\n"
