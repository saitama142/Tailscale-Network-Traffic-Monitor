# Tailscale Network Monitor

Real-time network traffic monitoring for Tailscale networks with a beautiful CLI dashboard and REST API.

Monitor bandwidth, connections, and traffic across all your Tailscale machines from a central collector.

## ✨ Features

- 📊 **Real-time Traffic Monitoring** - Upload/download speeds, total traffic, active connections
- 🎨 **Beautiful CLI Dashboard** - Live updating stats with Rich formatting
- 🔌 **REST API** - Full API for integrations (Glance widgets, custom dashboards, etc.)
- � **Secure** - API key authentication with automatic agent registration
- �🚀 **One-Line Install** - Simple deployment via curl
- 📦 **Systemd Integration** - Auto-restart, proper logging, production-ready
- 💾 **SQLite Storage** - 30-day metric retention, no external database needed

## 🚀 Quick Start

### 1. Install Collector (Central Server)

On one Tailscale machine that will collect metrics:

```bash
git clone https://github.com/saitama142/Tailscale-Network-Traffic-Monitor.git
cd Tailscale-Network-Traffic-Monitor
sudo bash scripts/install-collector.sh
```

The collector will be available at `http://<tailscale-ip>:48321`

### 2. Install Agents (Monitored Machines)

On each machine you want to monitor, run this single command:

```bash
curl -fsSL http://100.x.x.x:48321/install/agent.sh | sudo bash -s -- http://100.x.x.x:48321
```

Replace `100.x.x.x` with your collector's Tailscale IP.

Or use the CLI to get the exact command:
```bash
tsmon generate-install
```

**That's it!** The agent automatically registers on first run.

## 💻 CLI Usage

The `tsmon` command is installed with the collector:

```bash
# View all registered agents
tsmon agents

# Live dashboard with real-time stats
tsmon dashboard

# Generate install command for new agents
tsmon generate-install

# Manage collector service
tsmon server status
tsmon server restart
tsmon server logs

# Show version
tsmon version
```

## 📡 REST API

The API is designed for easy integration with dashboards, widgets (like Glance), and custom tools.

### Base URL
```
http://<collector-tailscale-ip>:48321
```

### Public Endpoints (No Auth Required)

#### `GET /`
Service information
```json
{
  "service": "Tailscale Network Monitor",
  "version": "1.0.0",
  "status": "running",
  "api_docs": "/docs"
}
```

#### `GET /api/v1/health`
Health check
```json
{
  "status": "healthy",
  "timestamp": "2025-10-24T23:15:00.000000"
}
```

#### `POST /api/v1/register`
Register new agent (agents use this automatically)
```json
{
  "hostname": "machine-name",
  "tailscale_ip": "100.x.x.x",
  "os_type": "linux"
}
```
Returns: `{"agent_id": "...", "api_key": "...", "message": "..."}`

### Protected Endpoints (Require API Key)

All other endpoints require an API key in the header:
```bash
curl -H "X-API-Key: your-api-key-here" http://collector:48321/api/v1/agents
```

#### `GET /api/v1/agents`
List all registered agents with status
```json
[
  {
    "id": "uuid",
    "hostname": "sandbox",
    "tailscale_ip": "100.113.155.67",
    "os_type": "linux",
    "status": "online",
    "last_seen": "2025-10-24T23:15:10.071199",
    "registered_at": "2025-10-24T22:55:30.441823"
  }
]
```

#### `GET /api/v1/dashboard`
Dashboard summary
```json
{
  "total_hosts": 2,
  "online_hosts": 2,
  "offline_hosts": 0,
  "total_traffic_gb": 2.04,
  "avg_bandwidth_mbps": 0.01,
  "last_updated": "2025-10-24T23:15:00.000000"
}
```

#### `GET /api/v1/traffic/summary`
Detailed traffic summary with per-host breakdown
```json
{
  "summary": {
    "total_hosts": 2,
    "online_hosts": 2,
    "offline_hosts": 0,
    "total_traffic_gb": 2.04,
    "avg_bandwidth_mbps": 0.01,
    "last_updated": "2025-10-24T23:15:00.000000"
  },
  "hosts": [
    {
      "hostname": "sandbox",
      "ip": "100.113.155.67",
      "status": "online",
      "last_seen": "2025-10-24T23:15:10.071199",
      "traffic": {
        "sent_gb": 1.95,
        "received_gb": 0.04,
        "current_upload": 0.01,
        "current_download": 0.0
      }
    }
  ],
  "top_connections": [
    {
      "from_host": "sandbox",
      "to_ip": "100.125.37.23",
      "bytes_sent": 52428800,
      "bytes_received": 1048576
    }
  ]
}
```

#### `GET /api/v1/traffic/history?hours=24&hostname=sandbox`
Historical metrics (last 24 hours by default)
```json
{
  "data": [
    {
      "timestamp": "2025-10-24T23:15:10.071199",
      "hostname": "sandbox",
      "upload_mbps": 0.01,
      "download_mbps": 0.0,
      "bytes_sent": 1048576,
      "bytes_received": 4096
    }
  ],
  "start_time": "2025-10-23T23:15:00",
  "end_time": "2025-10-24T23:15:00",
  "interval_seconds": 25
}
```

#### `POST /api/v1/metrics`
Submit metrics (agents use this automatically)
```json
{
  "hostname": "sandbox",
  "timestamp": "2025-10-24T23:15:10.071199",
  "tailscale_ip": "100.113.155.67",
  "metrics": {
    "bytes_sent": 1048576,
    "bytes_received": 4096,
    "upload_mbps": 0.01,
    "download_mbps": 0.0,
    "active_connections": [
      {
        "remote_ip": "100.125.37.23",
        "bytes_sent": 524288,
        "bytes_received": 2048
      }
    ]
  }
}
```

### Interactive API Docs

Visit `http://<collector-ip>:48321/docs` for interactive Swagger documentation where you can test all endpoints.

## 🔐 Authentication

### For Agents
Agents automatically register and receive an API key on first run. The key is saved in `/etc/tailscale-monitor/agent.yaml` and used for all subsequent metric submissions.

### For Custom Integrations
To use the API from external tools (like Glance widgets):

1. Get an API key from any agent's config:
   ```bash
   sudo cat /etc/tailscale-monitor/agent.yaml | grep api_key
   ```

2. Use it in API calls:
   ```bash
   curl -H "X-API-Key: your-key-here" http://collector:48321/api/v1/dashboard
   ```

**Note:** Currently, all agents share the same API key pool. For production use with external integrations, consider generating a dedicated API key via the registration endpoint with a custom hostname.

## 🛠️ Management

### Collector Service
```bash
sudo systemctl status tailscale-monitor-collector
sudo systemctl restart tailscale-monitor-collector
sudo journalctl -u tailscale-monitor-collector -f
```

### Agent Service
```bash
sudo systemctl status tailscale-monitor-agent
sudo systemctl restart tailscale-monitor-agent
sudo journalctl -u tailscale-monitor-agent -f
```

### Configuration
- **Collector**: No config needed, uses environment variables
- **Agent**: `/etc/tailscale-monitor/agent.yaml`
  ```yaml
  collector:
    url: "http://100.x.x.x:48321"
    api_key: "auto-generated"
    timeout: 5
    retry_attempts: 3
  monitoring:
    interval: 25  # seconds
    interface: tailscale0
  logging:
    level: INFO
    file: /var/log/tailscale-monitor/agent.log
  ```

### Database
- **Location**: `/var/lib/tailscale-monitor/metrics.db`
- **Retention**: 30 days (automatic cleanup)
- **Backup**: Just copy the SQLite file

## 📊 System Validation

Test everything is working:
```bash
bash scripts/validate-system.sh
```

This checks:
- ✓ Services running
- ✓ API health
- ✓ Agents registered
- ✓ Metrics collecting
- ✓ CLI working
- ✓ Database exists

## 📝 Requirements

- **OS**: Linux with systemd (tested on Ubuntu 22.04, Debian 11)
- **Python**: 3.8+
- **Tailscale**: Installed and running
- **Access**: Root/sudo for installation
- **Network**: Agents must reach collector on port 8080

## 🏗️ Architecture

```
┌─────────────────┐
│   Tailscale     │
│    Machine 1    │
│                 │
│  ┌──────────┐   │
│  │  Agent   │───┼───┐
│  └──────────┘   │   │
└─────────────────┘   │
                      │ Metrics every 25s
┌─────────────────┐   │ (HTTP POST)
│   Tailscale     │   │
│    Machine 2    │   │
│                 │   │
│  ┌──────────┐   │   │
│  │  Agent   │───┼───┼──┐
│  └──────────┘   │   │  │
└─────────────────┘   │  │
                      ▼  ▼
                ┌──────────────┐
                │  Collector   │
                │              │
                │  FastAPI     │
                │  SQLite DB   │
                │  Port 8080   │
                └──────────────┘
                      │
                      ▼
                ┌──────────────┐
                │  CLI (tsmon) │
                │  Dashboard   │
                └──────────────┘
```

## 🔧 Tech Stack

- **Backend**: FastAPI, SQLAlchemy, Uvicorn
- **CLI**: Typer, Rich
- **Monitoring**: psutil
- **Database**: SQLite
- **Auth**: pbkdf2_sha256
- **Service**: systemd

## 🐛 Troubleshooting

### Agent not registering
```bash
# Check agent logs
sudo journalctl -u tailscale-monitor-agent -n 50

# Verify collector is reachable
curl http://<collector-ip>:48321/api/v1/health

# Check Tailscale connectivity
tailscale status
```

### No metrics showing
```bash
# Verify agent is submitting
sudo journalctl -u tailscale-monitor-agent | grep "Metrics submitted"

# Check database
sudo ls -lh /var/lib/tailscale-monitor/metrics.db

# Test API
curl -H "X-API-Key: $(sudo grep api_key /etc/tailscale-monitor/agent.yaml | awk '{print $2}')" \
  http://<collector-ip>:48321/api/v1/agents
```

### Service not starting
```bash
# Check systemd status
sudo systemctl status tailscale-monitor-{collector,agent}

# View full logs
sudo journalctl -xe -u tailscale-monitor-collector

# Verify Python dependencies
/opt/tailscale-monitor/{collector,agent}/venv/bin/pip list
```

## 📦 Uninstall

```bash
# Stop and disable services
sudo systemctl stop tailscale-monitor-collector tailscale-monitor-agent
sudo systemctl disable tailscale-monitor-collector tailscale-monitor-agent

# Remove files
sudo rm -rf /opt/tailscale-monitor
sudo rm -rf /etc/tailscale-monitor
sudo rm -rf /var/lib/tailscale-monitor
sudo rm -rf /var/log/tailscale-monitor
sudo rm /etc/systemd/system/tailscale-monitor-*.service
sudo rm /usr/local/bin/tsmon

# Reload systemd
sudo systemctl daemon-reload
```

## 🚧 Roadmap

- [ ] Windows agent support (v1.5)
- [ ] Web dashboard UI
- [ ] Grafana integration
- [ ] Alert notifications
- [ ] Per-connection bandwidth tracking
- [ ] Historical graphs in CLI

## 📄 License

MIT

## 🙏 Credits

Built with Python, FastAPI, and lots of ☕
