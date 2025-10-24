"""
Basic tests for the collector API.
"""
import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from fastapi.testclient import TestClient
from collector.src.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint returns service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert data["service"] == "Tailscale Network Monitor"


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"


def test_register_agent():
    """Test agent registration."""
    registration_data = {
        "hostname": "test-host",
        "tailscale_ip": "100.64.0.1",
        "os_type": "linux"
    }
    
    response = client.post("/api/v1/register", json=registration_data)
    assert response.status_code == 200
    data = response.json()
    assert "agent_id" in data
    assert "api_key" in data
    assert "message" in data


def test_list_agents():
    """Test listing agents."""
    response = client.get("/api/v1/agents")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_dashboard():
    """Test dashboard endpoint."""
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "total_hosts" in data
    assert "online_hosts" in data
    assert "offline_hosts" in data


def test_traffic_summary():
    """Test traffic summary endpoint."""
    response = client.get("/api/v1/traffic/summary")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "hosts" in data
    assert "top_connections" in data
