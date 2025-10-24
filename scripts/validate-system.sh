#!/bin/bash
#
# Tailscale Network Monitor - System Validation Script
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Tailscale Network Monitor${NC}"
echo -e "${BLUE}System Validation${NC}"
echo -e "${BLUE}========================================${NC}\n"

COLLECTOR_URL="${COLLECTOR_URL:-http://localhost:8080}"
ERRORS=0

# Check collector service
echo -e "${YELLOW}Checking collector service...${NC}"
if systemctl is-active --quiet tailscale-monitor-collector; then
    echo -e "${GREEN}✓${NC} Collector service is running"
else
    echo -e "${RED}✗${NC} Collector service is not running"
    ERRORS=$((ERRORS + 1))
fi

# Check agent service
echo -e "\n${YELLOW}Checking agent service...${NC}"
if systemctl is-active --quiet tailscale-monitor-agent; then
    echo -e "${GREEN}✓${NC} Agent service is running"
else
    echo -e "${RED}✗${NC} Agent service is not running"
    ERRORS=$((ERRORS + 1))
fi

# Check API health
echo -e "\n${YELLOW}Checking API health...${NC}"
if curl -sf "$COLLECTOR_URL/api/v1/health" > /dev/null; then
    echo -e "${GREEN}✓${NC} API is healthy"
    HEALTH=$(curl -s "$COLLECTOR_URL/api/v1/health" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
    echo -e "  Status: $HEALTH"
else
    echo -e "${RED}✗${NC} API health check failed"
    ERRORS=$((ERRORS + 1))
fi

# Check registered agents
echo -e "\n${YELLOW}Checking registered agents...${NC}"
AGENTS=$(curl -s "$COLLECTOR_URL/api/v1/agents" | python3 -c "import sys, json; agents = json.load(sys.stdin); print(len(agents))")
if [ "$AGENTS" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} $AGENTS agent(s) registered"
    curl -s "$COLLECTOR_URL/api/v1/agents" | python3 -c "
import sys, json
agents = json.load(sys.stdin)
for agent in agents:
    status = '●' if agent['status'] == 'online' else '○'
    print(f\"  {status} {agent['hostname']} ({agent['tailscale_ip']}) - {agent['status']}\")
"
else
    echo -e "${RED}✗${NC} No agents registered"
    ERRORS=$((ERRORS + 1))
fi

# Check metrics collection
echo -e "\n${YELLOW}Checking metrics collection...${NC}"
TRAFFIC=$(curl -s "$COLLECTOR_URL/api/v1/traffic/summary" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"{data['summary']['total_hosts']},{data['summary']['online_hosts']},{data['summary']['total_traffic_gb']:.2f}\")
")
IFS=',' read -r TOTAL ONLINE TRAFFIC_GB <<< "$TRAFFIC"

if [ "$TOTAL" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Metrics being collected"
    echo -e "  Total hosts: $TOTAL"
    echo -e "  Online hosts: $ONLINE"
    echo -e "  Total traffic: ${TRAFFIC_GB} GB"
else
    echo -e "${RED}✗${NC} No metrics collected"
    ERRORS=$((ERRORS + 1))
fi

# Check CLI command
echo -e "\n${YELLOW}Checking CLI command...${NC}"
if command -v tsmon &> /dev/null; then
    echo -e "${GREEN}✓${NC} CLI command 'tsmon' is available"
    VERSION=$(tsmon version 2>&1 | grep -o "v[0-9.]*" || echo "unknown")
    echo -e "  Version: $VERSION"
else
    echo -e "${RED}✗${NC} CLI command 'tsmon' not found"
    ERRORS=$((ERRORS + 1))
fi

# Check database
echo -e "\n${YELLOW}Checking database...${NC}"
DB_PATH="/var/lib/tailscale-monitor/metrics.db"
if [ -f "$DB_PATH" ]; then
    DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
    echo -e "${GREEN}✓${NC} Database exists"
    echo -e "  Location: $DB_PATH"
    echo -e "  Size: $DB_SIZE"
else
    echo -e "${RED}✗${NC} Database not found"
    ERRORS=$((ERRORS + 1))
fi

# Final summary
echo -e "\n${BLUE}========================================${NC}"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo -e "${GREEN}System is fully operational${NC}"
    exit 0
else
    echo -e "${RED}✗ $ERRORS check(s) failed${NC}"
    echo -e "${YELLOW}Please review the errors above${NC}"
    exit 1
fi
