"""
Shared data models and schemas for Tailscale Network Monitor.
Used by both agent and collector components.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, IPvAnyAddress


class ConnectionInfo(BaseModel):
    """Information about an active connection."""
    ip: str = Field(..., description="Remote Tailscale IP address")
    hostname: Optional[str] = Field(None, description="Remote hostname if known")
    bytes: int = Field(..., description="Bytes transferred in this connection")
    port: Optional[int] = Field(None, description="Remote port number")
    state: Optional[str] = Field(None, description="Connection state (ESTABLISHED, etc)")


class MetricsData(BaseModel):
    """Network metrics collected by the agent."""
    bytes_sent: int = Field(..., description="Total bytes sent since boot")
    bytes_received: int = Field(..., description="Total bytes received since boot")
    current_upload_mbps: float = Field(..., description="Current upload speed in Mbps")
    current_download_mbps: float = Field(..., description="Current download speed in Mbps")
    packets_sent: int = Field(0, description="Total packets sent")
    packets_received: int = Field(0, description="Total packets received")
    active_connections: List[ConnectionInfo] = Field(default_factory=list, description="List of active Tailscale connections")


class MetricSubmission(BaseModel):
    """Payload sent from agent to collector."""
    hostname: str = Field(..., description="Machine hostname")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Metric collection timestamp")
    tailscale_ip: str = Field(..., description="Tailscale IP address (100.x.x.x)")
    metrics: MetricsData = Field(..., description="Collected network metrics")


class AgentInfo(BaseModel):
    """Information about a registered agent."""
    id: str = Field(..., description="Unique agent ID")
    hostname: str = Field(..., description="Machine hostname")
    tailscale_ip: str = Field(..., description="Tailscale IP address")
    status: str = Field(..., description="Agent status (online/offline)")
    first_seen: datetime = Field(..., description="First registration time")
    last_seen: datetime = Field(..., description="Last metric submission time")
    os_type: str = Field(..., description="Operating system (linux/windows)")


class AgentRegistration(BaseModel):
    """Agent registration request."""
    hostname: str = Field(..., description="Machine hostname")
    tailscale_ip: str = Field(..., description="Tailscale IP address")
    os_type: str = Field(..., description="Operating system (linux/windows)")


class AgentRegistrationResponse(BaseModel):
    """Response to agent registration."""
    agent_id: str = Field(..., description="Assigned agent ID")
    api_key: str = Field(..., description="API key for authentication")
    message: str = Field(..., description="Registration message")


class TrafficStats(BaseModel):
    """Traffic statistics for an agent."""
    sent_gb: float = Field(..., description="Total data sent in GB")
    received_gb: float = Field(..., description="Total data received in GB")
    current_upload: float = Field(..., description="Current upload speed in Mbps")
    current_download: float = Field(..., description="Current download speed in Mbps")


class HostTraffic(BaseModel):
    """Per-host traffic information."""
    hostname: str
    ip: str
    status: str
    last_seen: datetime
    traffic: TrafficStats


class ConnectionPair(BaseModel):
    """Connection between two hosts."""
    from_host: str
    to_host: str
    traffic_gb: float


class DashboardSummary(BaseModel):
    """Overall dashboard summary."""
    total_hosts: int
    online_hosts: int
    offline_hosts: int
    total_traffic_gb: float
    avg_bandwidth_mbps: float
    last_updated: datetime


class TrafficSummaryResponse(BaseModel):
    """Response for /api/v1/traffic/summary endpoint."""
    summary: DashboardSummary
    hosts: List[HostTraffic]
    top_connections: List[ConnectionPair]


class HistoricalDataPoint(BaseModel):
    """Single data point in historical data."""
    timestamp: datetime
    hostname: str
    upload_mbps: float
    download_mbps: float
    bytes_sent: int
    bytes_received: int


class HistoricalDataResponse(BaseModel):
    """Response for /api/v1/traffic/history endpoint."""
    data: List[HistoricalDataPoint]
    start_time: datetime
    end_time: datetime
    interval_seconds: int


class APIResponse(BaseModel):
    """Generic API response wrapper."""
    success: bool
    message: str
    data: Optional[dict] = None
