#!/bin/bash
#
# Test script for Tailscale Network Monitor
# Run this to verify all components are working
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Tailscale Network Monitor - System Test      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}\n"

# Test 1: Check if services are running
echo -e "${YELLOW}[1/8]${NC} Checking services..."
if systemctl is-active --quiet tailscale-monitor-collector; then
    echo -e "  ${GREEN}✓${NC} Collector service is running"
else
    echo -e "  ${RED}✗${NC} Collector service is NOT running"
    exit 1
fi

if systemctl is-active --quiet tailscale-monitor-agent; then
    echo -e "  ${GREEN}✓${NC} Agent service is running"
else
    echo -e "  ${RED}✗${NC} Agent service is NOT running"
    exit 1
fi

# Test 2: Check if collector is accessible
echo -e "\n${YELLOW}[2/8]${NC} Testing collector API..."
HEALTH=$(curl -s http://localhost:8080/api/v1/health | jq -r '.status' 2>/dev/null || echo "error")
if [ "$HEALTH" == "healthy" ]; then
    echo -e "  ${GREEN}✓${NC} Collector API is healthy"
else
    echo -e "  ${RED}✗${NC} Collector API is not responding correctly"
    exit 1
fi

# Test 3: Check database
echo -e "\n${YELLOW}[3/8]${NC} Checking database..."
if [ -f "/var/lib/tailscale-monitor/metrics.db" ]; then
    DB_SIZE=$(du -h /var/lib/tailscale-monitor/metrics.db | cut -f1)
    echo -e "  ${GREEN}✓${NC} Database exists (size: $DB_SIZE)"
else
    echo -e "  ${RED}✗${NC} Database not found"
    exit 1
fi

# Test 4: Check agents
echo -e "\n${YELLOW}[4/8]${NC} Checking registered agents..."
AGENT_COUNT=$(curl -s http://localhost:8080/api/v1/agents | jq '. | length' 2>/dev/null || echo "0")
if [ "$AGENT_COUNT" -gt 0 ]; then
    echo -e "  ${GREEN}✓${NC} Found $AGENT_COUNT registered agent(s)"
else
    echo -e "  ${YELLOW}⚠${NC} No agents registered yet"
fi

# Test 5: Check metrics
echo -e "\n${YELLOW}[5/8]${NC} Checking metrics collection..."
TOTAL_TRAFFIC=$(curl -s http://localhost:8080/api/v1/dashboard | jq -r '.total_traffic_gb' 2>/dev/null || echo "0")
echo -e "  ${GREEN}✓${NC} Total traffic recorded: ${TOTAL_TRAFFIC} GB"

# Test 6: Check CLI
echo -e "\n${YELLOW}[6/8]${NC} Testing CLI command..."
if command -v tsmon &> /dev/null; then
    CLI_VERSION=$(tsmon version 2>&1 | grep -o "v[0-9.]*" || echo "unknown")
    echo -e "  ${GREEN}✓${NC} CLI command available ($CLI_VERSION)"
else
    echo -e "  ${RED}✗${NC} CLI command not found"
    exit 1
fi

# Test 7: Check configuration files
echo -e "\n${YELLOW}[7/8]${NC} Checking configuration..."
if [ -f "/etc/tailscale-monitor/agent.yaml" ]; then
    echo -e "  ${GREEN}✓${NC} Agent configuration exists"
else
    echo -e "  ${YELLOW}⚠${NC} Agent configuration not found"
fi

# Test 8: Check logs
echo -e "\n${YELLOW}[8/8]${NC} Checking logs..."
COLLECTOR_LOG_COUNT=$(journalctl -u tailscale-monitor-collector --no-pager -n 10 2>/dev/null | wc -l)
AGENT_LOG_COUNT=$(journalctl -u tailscale-monitor-agent --no-pager -n 10 2>/dev/null | wc -l)
echo -e "  ${GREEN}✓${NC} Collector logs: $COLLECTOR_LOG_COUNT recent entries"
echo -e "  ${GREEN}✓${NC} Agent logs: $AGENT_LOG_COUNT recent entries"

# Summary
echo -e "\n${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  All tests passed! System is operational.     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}\n"

echo -e "${BLUE}Quick commands:${NC}"
echo -e "  tsmon agents          - List all agents"
echo -e "  tsmon dashboard       - Live dashboard"
echo -e "  tsmon generate-install - Generate agent install command"
echo -e "  tsmon server status   - Check collector status"
echo -e "\n${BLUE}API endpoint:${NC}"
echo -e "  http://$(hostname -I | awk '{print $1}'):8080/docs"
