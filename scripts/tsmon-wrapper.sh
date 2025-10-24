#!/bin/bash
export PYTHONPATH="/opt/tailscale-monitor:$PYTHONPATH"
source /opt/tailscale-monitor/cli/venv/bin/activate
python3 /opt/tailscale-monitor/cli/src/main.py "$@"
