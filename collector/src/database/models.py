"""
Database models for the collector.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Agent(Base):
    """Registered agent information."""
    __tablename__ = "agents"
    
    id = Column(String, primary_key=True)  # UUID
    hostname = Column(String, nullable=False, index=True)
    tailscale_ip = Column(String, nullable=False, unique=True, index=True)
    os_type = Column(String, nullable=False)  # linux, windows
    api_key_hash = Column(String, nullable=False)  # bcrypt hash
    first_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String, nullable=False, default="offline")  # online, offline, idle
    
    # Relationships
    metrics = relationship("Metric", back_populates="agent", cascade="all, delete-orphan")


class Metric(Base):
    """Network metrics collected from agents."""
    __tablename__ = "metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Raw counters
    bytes_sent = Column(Integer, nullable=False)
    bytes_received = Column(Integer, nullable=False)
    packets_sent = Column(Integer, nullable=False, default=0)
    packets_received = Column(Integer, nullable=False, default=0)
    
    # Calculated bandwidth
    upload_mbps = Column(Float, nullable=False, default=0.0)
    download_mbps = Column(Float, nullable=False, default=0.0)
    
    # Connection count
    active_connections = Column(Integer, nullable=False, default=0)
    
    # Relationships
    agent = relationship("Agent", back_populates="metrics")
    connections = relationship("Connection", back_populates="metric", cascade="all, delete-orphan")
    
    # Composite index for efficient queries
    __table_args__ = (
        Index('idx_agent_timestamp', 'agent_id', 'timestamp'),
    )


class Connection(Base):
    """Active connection details."""
    __tablename__ = "connections"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_id = Column(Integer, ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False, index=True)
    
    remote_ip = Column(String, nullable=False)
    remote_hostname = Column(String, nullable=True)
    remote_port = Column(Integer, nullable=True)
    bytes_transferred = Column(Integer, nullable=False, default=0)
    state = Column(String, nullable=True)
    
    # Relationships
    metric = relationship("Metric", back_populates="connections")
    
    __table_args__ = (
        Index('idx_metric_remote', 'metric_id', 'remote_ip'),
    )
