#!/bin/bash
#
# Tailscale Network Monitor - Collector Installation Script
# Installs the collector service and CLI tool
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/tailscale-monitor"
CONFIG_DIR="/etc/tailscale-monitor"
DATA_DIR="/var/lib/tailscale-monitor"
LOG_DIR="/var/log/tailscale-monitor"
SERVICE_USER="tailscale-monitor"
SERVICE_GROUP="tailscale-monitor"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Tailscale Network Monitor - Collector${NC}"
echo -e "${BLUE}Installation Script${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo -e "Please run: sudo $0"
    exit 1
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

echo -e "${GREEN}✓${NC} Detected OS: $OS $VERSION\n"

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

# Create service user
echo -e "${YELLOW}Creating service user...${NC}"
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -s /bin/false -d "$DATA_DIR" "$SERVICE_USER"
    echo -e "${GREEN}✓${NC} User $SERVICE_USER created"
else
    echo -e "${GREEN}✓${NC} User $SERVICE_USER already exists"
fi

# Create directories
echo -e "\n${YELLOW}Creating directories...${NC}"
mkdir -p "$INSTALL_DIR"/{collector,cli,shared,scripts}
mkdir -p "$CONFIG_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$LOG_DIR"
echo -e "${GREEN}✓${NC} Directories created\n"

# Download or copy files
echo -e "${YELLOW}Installing application files...${NC}"

# For now, we'll check if we're in the source directory
if [ -d "$(dirname "$0")/../collector" ]; then
    SOURCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
    echo -e "${BLUE}Installing from local source: $SOURCE_DIR${NC}"
    
    # Copy collector
    cp -r "$SOURCE_DIR/collector"/* "$INSTALL_DIR/collector/"
    cp -r "$SOURCE_DIR/shared" "$INSTALL_DIR/"
    cp -r "$SOURCE_DIR/cli"/* "$INSTALL_DIR/cli/"
    cp -r "$SOURCE_DIR/scripts"/*.sh "$INSTALL_DIR/scripts/"
else
    echo -e "${RED}Error: Source files not found${NC}"
    echo -e "Please run this script from the project directory"
    exit 1
fi

echo -e "${GREEN}✓${NC} Files copied\n"

# Create Python virtual environments
echo -e "${YELLOW}Creating Python virtual environment for collector...${NC}"
python3 -m venv "$INSTALL_DIR/collector/venv"
"$INSTALL_DIR/collector/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/collector/venv/bin/pip" install -r "$INSTALL_DIR/collector/requirements.txt"
echo -e "${GREEN}✓${NC} Collector environment ready\n"

echo -e "${YELLOW}Creating Python virtual environment for CLI...${NC}"
python3 -m venv "$INSTALL_DIR/cli/venv"
"$INSTALL_DIR/cli/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/cli/venv/bin/pip" install -r "$INSTALL_DIR/cli/requirements.txt"
echo -e "${GREEN}✓${NC} CLI environment ready\n"

# Set permissions
echo -e "${YELLOW}Setting permissions...${NC}"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR/collector"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$DATA_DIR"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$LOG_DIR"
chown -R root:root "$INSTALL_DIR/cli"
chown -R root:root "$INSTALL_DIR/shared"
chmod 755 "$INSTALL_DIR/collector/src/main.py"
chmod 755 "$INSTALL_DIR/cli/src/main.py"
echo -e "${GREEN}✓${NC} Permissions set\n"

# Install systemd service
echo -e "${YELLOW}Installing systemd service...${NC}"
if [ -f "$SOURCE_DIR/systemd/tailscale-monitor-collector.service" ]; then
    cp "$SOURCE_DIR/systemd/tailscale-monitor-collector.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable tailscale-monitor-collector
    echo -e "${GREEN}✓${NC} Service installed and enabled"
else
    echo -e "${YELLOW}Warning: Service file not found${NC}"
fi

# Create CLI symlink
echo -e "\n${YELLOW}Creating CLI command...${NC}"
cat > /usr/local/bin/tsmon << 'EOFWRAPPER'
#!/bin/bash
export PYTHONPATH="/opt/tailscale-monitor:$PYTHONPATH"
source /opt/tailscale-monitor/cli/venv/bin/activate
python3 /opt/tailscale-monitor/cli/src/main.py "$@"
EOFWRAPPER
chmod +x /usr/local/bin/tsmon
echo -e "${GREEN}✓${NC} CLI command 'tsmon' installed\n"

# Initialize database
echo -e "${YELLOW}Initializing database...${NC}"
sudo -u "$SERVICE_USER" "$INSTALL_DIR/collector/venv/bin/python" -c "
import sys
sys.path.insert(0, '$INSTALL_DIR')
from collector.src.database import get_database
db = get_database('$DATA_DIR/metrics.db')
print('Database initialized')
"
echo -e "${GREEN}✓${NC} Database ready\n"

# Start service
echo -e "${YELLOW}Starting collector service...${NC}"
systemctl start tailscale-monitor-collector
sleep 2

if systemctl is-active --quiet tailscale-monitor-collector; then
    echo -e "${GREEN}✓${NC} Collector service is running\n"
else
    echo -e "${RED}✗${NC} Service failed to start. Check logs with: journalctl -u tailscale-monitor-collector\n"
fi

# Get Tailscale IP
TAILSCALE_IP=$(ip -4 addr show tailscale0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "unknown")

# Final message
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo -e "${BLUE}Collector is running at:${NC}"
echo -e "  Local: http://localhost:48321"
if [ "$TAILSCALE_IP" != "unknown" ]; then
    echo -e "  Tailscale: http://$TAILSCALE_IP:48321"
fi

echo -e "\n${BLUE}API Documentation:${NC}"
echo -e "  http://localhost:48321/docs"

echo -e "\n${BLUE}CLI Commands:${NC}"
echo -e "  tsmon agents              - List all agents"
echo -e "  tsmon dashboard           - Live dashboard"
echo -e "  tsmon generate-install    - Generate agent install command"
echo -e "  tsmon server status       - Check service status"
echo -e "  tsmon --help              - Show all commands"

echo -e "\n${BLUE}Service Management:${NC}"
echo -e "  sudo systemctl status tailscale-monitor-collector"
echo -e "  sudo systemctl stop tailscale-monitor-collector"
echo -e "  sudo systemctl start tailscale-monitor-collector"
echo -e "  sudo journalctl -u tailscale-monitor-collector -f"

echo -e "\n${YELLOW}Next Steps:${NC}"
echo -e "  1. Run 'tsmon generate-install' to get agent installation commands"
echo -e "  2. Install agents on machines you want to monitor"
echo -e "  3. Run 'tsmon dashboard' to see live statistics\n"
