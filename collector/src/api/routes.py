"""
API routes for the collector.
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import datetime, timedelta
import sys
import os

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from shared.schemas import (
    MetricSubmission,
    AgentRegistration,
    AgentRegistrationResponse,
    AgentInfo,
    TrafficSummaryResponse,
    DashboardSummary,
    HostTraffic,
    TrafficStats,
    ConnectionPair,
    HistoricalDataResponse,
    HistoricalDataPoint,
    APIResponse
)
from shared.constants import (
    STATUS_ONLINE,
    STATUS_OFFLINE,
    BYTES_TO_GB,
    AGENT_TIMEOUT_SECONDS
)
from ..database import get_db
from ..database.models import Agent, Metric, Connection
from .auth import (
    generate_api_key,
    generate_agent_id,
    hash_api_key,
    authenticate_agent,
    check_agent_timeout
)

router = APIRouter()


def get_current_agent(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Agent:
    """Dependency to get current authenticated agent."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    # Extract Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    
    api_key = parts[1]
    
    # Authenticate
    agent = authenticate_agent(db, api_key)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return agent


@router.post("/register", response_model=AgentRegistrationResponse)
def register_agent(
    registration: AgentRegistration,
    db: Session = Depends(get_db)
):
    """Register a new agent and get API key."""
    
    # Check if agent already exists
    existing_agent = db.query(Agent).filter(
        Agent.tailscale_ip == registration.tailscale_ip
    ).first()
    
    if existing_agent:
        raise HTTPException(
            status_code=409,
            detail=f"Agent with IP {registration.tailscale_ip} already registered"
        )
    
    # Generate credentials
    agent_id = generate_agent_id()
    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)
    
    # Create agent
    agent = Agent(
        id=agent_id,
        hostname=registration.hostname,
        tailscale_ip=registration.tailscale_ip,
        os_type=registration.os_type,
        api_key_hash=api_key_hash,
        first_seen=datetime.utcnow(),
        last_seen=datetime.utcnow(),
        status=STATUS_ONLINE
    )
    
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    return AgentRegistrationResponse(
        agent_id=agent_id,
        api_key=api_key,
        message=f"Agent {registration.hostname} registered successfully"
    )


@router.post("/metrics")
def submit_metrics(
    submission: MetricSubmission,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """Receive metrics from an agent."""
    
    # Create metric record
    metric = Metric(
        agent_id=agent.id,
        timestamp=submission.timestamp,
        bytes_sent=submission.metrics.bytes_sent,
        bytes_received=submission.metrics.bytes_received,
        packets_sent=submission.metrics.packets_sent,
        packets_received=submission.metrics.packets_received,
        upload_mbps=submission.metrics.current_upload_mbps,
        download_mbps=submission.metrics.current_download_mbps,
        active_connections=len(submission.metrics.active_connections)
    )
    
    db.add(metric)
    db.flush()  # Get metric.id
    
    # Add connection details
    for conn_info in submission.metrics.active_connections:
        connection = Connection(
            metric_id=metric.id,
            remote_ip=conn_info.ip,
            remote_hostname=conn_info.hostname,
            remote_port=conn_info.port,
            bytes_transferred=conn_info.bytes,
            state=conn_info.state
        )
        db.add(connection)
    
    # Update agent last_seen
    agent.last_seen = datetime.utcnow()
    agent.status = STATUS_ONLINE
    
    db.commit()
    
    return {"success": True, "message": "Metrics received"}


@router.get("/agents", response_model=List[AgentInfo])
def list_agents(db: Session = Depends(get_db)):
    """List all registered agents."""
    
    # Check for timeouts
    check_agent_timeout(db, AGENT_TIMEOUT_SECONDS)
    
    agents = db.query(Agent).all()
    
    return [
        AgentInfo(
            id=agent.id,
            hostname=agent.hostname,
            tailscale_ip=agent.tailscale_ip,
            status=agent.status,
            first_seen=agent.first_seen,
            last_seen=agent.last_seen,
            os_type=agent.os_type
        )
        for agent in agents
    ]


@router.get("/dashboard", response_model=DashboardSummary)
def get_dashboard(db: Session = Depends(get_db)):
    """Get dashboard summary statistics."""
    
    # Check for timeouts
    check_agent_timeout(db, AGENT_TIMEOUT_SECONDS)
    
    # Get agent counts
    total_hosts = db.query(Agent).count()
    online_hosts = db.query(Agent).filter(Agent.status == STATUS_ONLINE).count()
    offline_hosts = total_hosts - online_hosts
    
    # Get latest metrics for total traffic
    subquery = db.query(
        Metric.agent_id,
        func.max(Metric.id).label("max_id")
    ).group_by(Metric.agent_id).subquery()
    
    latest_metrics = db.query(Metric).join(
        subquery,
        (Metric.agent_id == subquery.c.agent_id) & (Metric.id == subquery.c.max_id)
    ).all()
    
    total_bytes = sum(m.bytes_sent + m.bytes_received for m in latest_metrics)
    total_traffic_gb = total_bytes / BYTES_TO_GB if total_bytes else 0
    
    # Calculate average bandwidth
    avg_bandwidth = sum(m.upload_mbps + m.download_mbps for m in latest_metrics)
    avg_bandwidth_mbps = avg_bandwidth / max(len(latest_metrics), 1)
    
    return DashboardSummary(
        total_hosts=total_hosts,
        online_hosts=online_hosts,
        offline_hosts=offline_hosts,
        total_traffic_gb=round(total_traffic_gb, 2),
        avg_bandwidth_mbps=round(avg_bandwidth_mbps, 2),
        last_updated=datetime.utcnow()
    )


@router.get("/traffic/summary", response_model=TrafficSummaryResponse)
def get_traffic_summary(db: Session = Depends(get_db)):
    """Get comprehensive traffic summary."""
    
    # Get dashboard summary
    summary = get_dashboard(db)
    
    # Get per-host traffic
    agents = db.query(Agent).all()
    hosts = []
    
    for agent in agents:
        # Get latest metric
        latest_metric = db.query(Metric).filter(
            Metric.agent_id == agent.id
        ).order_by(desc(Metric.timestamp)).first()
        
        if latest_metric:
            traffic = TrafficStats(
                sent_gb=round(latest_metric.bytes_sent / BYTES_TO_GB, 2),
                received_gb=round(latest_metric.bytes_received / BYTES_TO_GB, 2),
                current_upload=round(latest_metric.upload_mbps, 2),
                current_download=round(latest_metric.download_mbps, 2)
            )
        else:
            traffic = TrafficStats(
                sent_gb=0.0,
                received_gb=0.0,
                current_upload=0.0,
                current_download=0.0
            )
        
        hosts.append(HostTraffic(
            hostname=agent.hostname,
            ip=agent.tailscale_ip,
            status=agent.status,
            last_seen=agent.last_seen,
            traffic=traffic
        ))
    
    # Get top connections (aggregate connection data)
    # This is a simplified version - join connections with agents
    recent_time = datetime.utcnow() - timedelta(hours=1)
    
    connection_data = db.query(
        Agent.hostname.label("source_hostname"),
        Connection.remote_hostname,
        func.sum(Connection.bytes_transferred).label("total_bytes")
    ).join(
        Metric, Metric.agent_id == Agent.id
    ).join(
        Connection, Connection.metric_id == Metric.id
    ).filter(
        Metric.timestamp >= recent_time,
        Connection.remote_hostname.isnot(None)
    ).group_by(
        Agent.hostname,
        Connection.remote_hostname
    ).order_by(
        desc("total_bytes")
    ).limit(10).all()
    
    top_connections = [
        ConnectionPair(
            from_host=row.source_hostname,
            to_host=row.remote_hostname,
            traffic_gb=round(row.total_bytes / BYTES_TO_GB, 2) if row.total_bytes else 0
        )
        for row in connection_data
    ]
    
    return TrafficSummaryResponse(
        summary=summary,
        hosts=hosts,
        top_connections=top_connections
    )


@router.get("/traffic/by-host/{hostname}", response_model=HostTraffic)
def get_host_traffic(hostname: str, db: Session = Depends(get_db)):
    """Get traffic data for a specific host."""
    
    agent = db.query(Agent).filter(Agent.hostname == hostname).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Host {hostname} not found")
    
    # Get latest metric
    latest_metric = db.query(Metric).filter(
        Metric.agent_id == agent.id
    ).order_by(desc(Metric.timestamp)).first()
    
    if latest_metric:
        traffic = TrafficStats(
            sent_gb=round(latest_metric.bytes_sent / BYTES_TO_GB, 2),
            received_gb=round(latest_metric.bytes_received / BYTES_TO_GB, 2),
            current_upload=round(latest_metric.upload_mbps, 2),
            current_download=round(latest_metric.download_mbps, 2)
        )
    else:
        traffic = TrafficStats(sent_gb=0.0, received_gb=0.0, current_upload=0.0, current_download=0.0)
    
    return HostTraffic(
        hostname=agent.hostname,
        ip=agent.tailscale_ip,
        status=agent.status,
        last_seen=agent.last_seen,
        traffic=traffic
    )


@router.get("/traffic/history", response_model=HistoricalDataResponse)
def get_traffic_history(
    hours: int = Query(default=24, ge=1, le=720),  # 1 hour to 30 days
    hostname: Optional[str] = Query(default=None),
    db: Session = Depends(get_db)
):
    """Get historical traffic data."""
    
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)
    
    query = db.query(Metric, Agent.hostname).join(
        Agent, Metric.agent_id == Agent.id
    ).filter(
        Metric.timestamp >= start_time,
        Metric.timestamp <= end_time
    )
    
    if hostname:
        query = query.filter(Agent.hostname == hostname)
    
    results = query.order_by(Metric.timestamp).all()
    
    data = [
        HistoricalDataPoint(
            timestamp=metric.timestamp,
            hostname=hostname_str,
            upload_mbps=round(metric.upload_mbps, 2),
            download_mbps=round(metric.download_mbps, 2),
            bytes_sent=metric.bytes_sent,
            bytes_received=metric.bytes_received
        )
        for metric, hostname_str in results
    ]
    
    return HistoricalDataResponse(
        data=data,
        start_time=start_time,
        end_time=end_time,
        interval_seconds=25
    )


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        # Test database connection
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "timestamp": datetime.utcnow()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")
