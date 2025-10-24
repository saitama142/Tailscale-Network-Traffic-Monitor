.PHONY: help install-collector install-agent uninstall test clean

help:
	@echo "Tailscale Network Monitor - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install-collector  - Install collector and CLI (requires root)"
	@echo "  install-agent      - Install agent (requires root, needs COLLECTOR_URL env)"
	@echo "  uninstall          - Uninstall all components"
	@echo "  test               - Run tests"
	@echo "  clean              - Clean build artifacts"

install-collector:
	@echo "Installing collector..."
	sudo bash scripts/install-collector.sh

install-agent:
	@echo "Installing agent..."
	@if [ -z "$$COLLECTOR_URL" ]; then \
		echo "Error: COLLECTOR_URL environment variable not set"; \
		echo "Example: COLLECTOR_URL=http://100.113.155.67:8080 make install-agent"; \
		exit 1; \
	fi
	sudo bash scripts/install-agent.sh

uninstall:
	@echo "Uninstalling Tailscale Network Monitor..."
	sudo systemctl stop tailscale-monitor-collector 2>/dev/null || true
	sudo systemctl stop tailscale-monitor-agent 2>/dev/null || true
	sudo systemctl disable tailscale-monitor-collector 2>/dev/null || true
	sudo systemctl disable tailscale-monitor-agent 2>/dev/null || true
	sudo rm -f /etc/systemd/system/tailscale-monitor-*.service
	sudo systemctl daemon-reload
	sudo rm -f /usr/local/bin/tsmon
	sudo rm -rf /opt/tailscale-monitor
	sudo rm -rf /etc/tailscale-monitor
	sudo rm -rf /var/lib/tailscale-monitor
	sudo rm -rf /var/log/tailscale-monitor
	sudo userdel tailscale-monitor 2>/dev/null || true
	@echo "Uninstall complete"

test:
	@echo "Running tests..."
	cd collector && python3 -m pytest tests/ -v
	cd agent && python3 -m pytest tests/ -v

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	find . -type f -name "*.db" -delete
	@echo "Clean complete"
