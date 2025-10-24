"""
Shared constants for Tailscale Network Monitor.
"""

# API Configuration
DEFAULT_COLLECTOR_PORT = 8080
API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"

# Monitoring Configuration
METRIC_INTERVAL_SECONDS = 25
TAILSCALE_INTERFACE_LINUX = "tailscale0"
TAILSCALE_INTERFACE_WINDOWS = "Tailscale"
TAILSCALE_IP_PREFIX = "100."  # Tailscale CGNAT range: 100.64.0.0/10

# Data Retention
DATA_RETENTION_DAYS = 30
CLEANUP_INTERVAL_HOURS = 24

# Agent Configuration
AGENT_TIMEOUT_SECONDS = 300  # 5 minutes before marking offline
MAX_RETRY_ATTEMPTS = 5
RETRY_BACKOFF_SECONDS = [1, 2, 5, 10, 30]  # Exponential backoff

# Connection States
CONNECTION_STATES = ["ESTABLISHED", "TIME_WAIT", "CLOSE_WAIT", "SYN_SENT", "SYN_RECV"]

# Conversion Constants
BYTES_TO_GB = 1024 ** 3
BYTES_TO_MBPS = 8 / (1024 ** 2)  # Convert bytes/sec to Mbps

# Status
STATUS_ONLINE = "online"
STATUS_OFFLINE = "offline"
STATUS_IDLE = "idle"

# OS Types
OS_LINUX = "linux"
OS_WINDOWS = "windows"

# Service Names
SERVICE_NAME_COLLECTOR = "tailscale-monitor-collector"
SERVICE_NAME_AGENT = "tailscale-monitor-agent"

# Paths
DEFAULT_CONFIG_DIR = "/etc/tailscale-monitor"
DEFAULT_DATA_DIR = "/var/lib/tailscale-monitor"
DEFAULT_LOG_DIR = "/var/log/tailscale-monitor"

# CLI
CLI_NAME = "tsmon"
CLI_VERSION = "1.0.0"
