"""
Network monitoring module for the agent.
"""
import psutil
import platform
import socket
import time
import logging
from typing import Optional, Tuple, List, Dict
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from shared.schemas import MetricsData, ConnectionInfo
from shared.constants import (
    TAILSCALE_INTERFACE_LINUX,
    TAILSCALE_INTERFACE_WINDOWS,
    TAILSCALE_IP_PREFIX,
    BYTES_TO_MBPS
)

logger = logging.getLogger(__name__)


class NetworkMonitor:
    """Monitor network interface for Tailscale traffic."""
    
    def __init__(self):
        """Initialize the monitor."""
        self.interface_name = self._detect_interface()
        self.os_type = "windows" if platform.system() == "Windows" else "linux"
        self.hostname = socket.gethostname()
        self.tailscale_ip = self._get_tailscale_ip()
        
        # Previous measurement for bandwidth calculation
        self.prev_bytes_sent = None
        self.prev_bytes_recv = None
        self.prev_timestamp = None
        
        logger.info(f"Monitor initialized: interface={self.interface_name}, "
                   f"hostname={self.hostname}, ip={self.tailscale_ip}")
    
    def _detect_interface(self) -> str:
        """Detect the Tailscale network interface."""
        os_name = platform.system()
        
        # Get all network interfaces
        interfaces = psutil.net_if_addrs()
        
        if os_name == "Linux":
            # Try exact match first
            if TAILSCALE_INTERFACE_LINUX in interfaces:
                return TAILSCALE_INTERFACE_LINUX
        elif os_name == "Windows":
            # Windows might have variations
            for iface in interfaces:
                if "tailscale" in iface.lower():
                    return iface
        
        # Fallback: look for interface with 100.x.x.x IP
        for iface_name, addrs in interfaces.items():
            for addr in addrs:
                if addr.family == socket.AF_INET:  # IPv4
                    if addr.address.startswith(TAILSCALE_IP_PREFIX):
                        logger.info(f"Detected Tailscale interface: {iface_name}")
                        return iface_name
        
        raise RuntimeError("Could not detect Tailscale interface. Is Tailscale running?")
    
    def _get_tailscale_ip(self) -> str:
        """Get the Tailscale IP address."""
        interfaces = psutil.net_if_addrs()
        
        if self.interface_name in interfaces:
            for addr in interfaces[self.interface_name]:
                if addr.family == socket.AF_INET:  # IPv4
                    if addr.address.startswith(TAILSCALE_IP_PREFIX):
                        return addr.address
        
        raise RuntimeError(f"Could not find Tailscale IP on interface {self.interface_name}")
    
    def get_interface_stats(self) -> Optional[Tuple[int, int, int, int]]:
        """
        Get current interface statistics.
        
        Returns:
            Tuple of (bytes_sent, bytes_recv, packets_sent, packets_recv) or None
        """
        try:
            stats = psutil.net_io_counters(pernic=True)
            
            if self.interface_name not in stats:
                logger.warning(f"Interface {self.interface_name} not found in stats")
                return None
            
            iface_stats = stats[self.interface_name]
            return (
                iface_stats.bytes_sent,
                iface_stats.bytes_recv,
                iface_stats.packets_sent,
                iface_stats.packets_recv
            )
        except Exception as e:
            logger.error(f"Error getting interface stats: {e}")
            return None
    
    def calculate_bandwidth(
        self,
        bytes_sent: int,
        bytes_recv: int,
        timestamp: float
    ) -> Tuple[float, float]:
        """
        Calculate current bandwidth from byte deltas.
        
        Args:
            bytes_sent: Current bytes sent counter
            bytes_recv: Current bytes received counter
            timestamp: Current timestamp
            
        Returns:
            Tuple of (upload_mbps, download_mbps)
        """
        if self.prev_bytes_sent is None:
            # First measurement, no bandwidth to calculate yet
            self.prev_bytes_sent = bytes_sent
            self.prev_bytes_recv = bytes_recv
            self.prev_timestamp = timestamp
            return (0.0, 0.0)
        
        # Calculate time elapsed
        time_elapsed = timestamp - self.prev_timestamp
        
        if time_elapsed <= 0:
            return (0.0, 0.0)
        
        # Calculate byte deltas
        sent_delta = bytes_sent - self.prev_bytes_sent
        recv_delta = bytes_recv - self.prev_bytes_recv
        
        # Handle counter rollover (unlikely with 64-bit counters)
        if sent_delta < 0:
            sent_delta = bytes_sent
        if recv_delta < 0:
            recv_delta = bytes_recv
        
        # Calculate bandwidth in Mbps
        upload_mbps = (sent_delta / time_elapsed) * BYTES_TO_MBPS
        download_mbps = (recv_delta / time_elapsed) * BYTES_TO_MBPS
        
        # Store current values for next calculation
        self.prev_bytes_sent = bytes_sent
        self.prev_bytes_recv = bytes_recv
        self.prev_timestamp = timestamp
        
        return (upload_mbps, download_mbps)
    
    def get_active_connections(self) -> List[ConnectionInfo]:
        """
        Get active connections to other Tailscale IPs.
        
        Returns:
            List of ConnectionInfo objects
        """
        connections = []
        
        try:
            # Get all network connections
            # Note: This requires root/admin privileges
            all_connections = psutil.net_connections(kind='inet')
            
            # Track unique remote IPs and aggregate data
            conn_map: Dict[str, Dict] = {}
            
            for conn in all_connections:
                # Check if connection has local and remote addresses
                if not conn.laddr or not conn.raddr:
                    continue
                
                # Check if local address is our Tailscale IP
                if conn.laddr.ip != self.tailscale_ip:
                    continue
                
                # Check if remote address is a Tailscale IP
                remote_ip = conn.raddr.ip
                if not remote_ip.startswith(TAILSCALE_IP_PREFIX):
                    continue
                
                # Aggregate by remote IP
                if remote_ip not in conn_map:
                    conn_map[remote_ip] = {
                        'ip': remote_ip,
                        'ports': set(),
                        'states': set(),
                        'bytes': 0  # We can't get per-connection bytes easily
                    }
                
                conn_map[remote_ip]['ports'].add(conn.raddr.port)
                if conn.status:
                    conn_map[remote_ip]['states'].add(conn.status)
            
            # Convert to ConnectionInfo objects
            for remote_ip, data in conn_map.items():
                # Try to resolve hostname
                hostname = self._resolve_hostname(remote_ip)
                
                # Get primary port and state
                port = min(data['ports']) if data['ports'] else None
                state = "ESTABLISHED" if "ESTABLISHED" in data['states'] else next(iter(data['states']), None)
                
                connections.append(ConnectionInfo(
                    ip=remote_ip,
                    hostname=hostname,
                    bytes=data['bytes'],
                    port=port,
                    state=state
                ))
        
        except (psutil.AccessDenied, PermissionError):
            logger.warning("Permission denied when getting connections. Run as root/administrator.")
        except Exception as e:
            logger.error(f"Error getting connections: {e}")
        
        return connections
    
    def _resolve_hostname(self, ip: str) -> Optional[str]:
        """
        Try to resolve IP to hostname.
        
        Args:
            ip: IP address to resolve
            
        Returns:
            Hostname or None
        """
        try:
            hostname, _, _ = socket.gethostbyaddr(ip)
            return hostname
        except (socket.herror, socket.gaierror, socket.timeout):
            return None
    
    def collect_metrics(self) -> Optional[MetricsData]:
        """
        Collect all network metrics.
        
        Returns:
            MetricsData object or None if collection failed
        """
        try:
            # Get interface stats
            stats = self.get_interface_stats()
            if stats is None:
                return None
            
            bytes_sent, bytes_recv, packets_sent, packets_recv = stats
            timestamp = time.time()
            
            # Calculate bandwidth
            upload_mbps, download_mbps = self.calculate_bandwidth(
                bytes_sent, bytes_recv, timestamp
            )
            
            # Get active connections
            connections = self.get_active_connections()
            
            # Create metrics object
            metrics = MetricsData(
                bytes_sent=bytes_sent,
                bytes_received=bytes_recv,
                current_upload_mbps=round(upload_mbps, 2),
                current_download_mbps=round(download_mbps, 2),
                packets_sent=packets_sent,
                packets_received=packets_recv,
                active_connections=connections
            )
            
            logger.debug(f"Collected metrics: up={metrics.current_upload_mbps}Mbps, "
                        f"down={metrics.current_download_mbps}Mbps, "
                        f"connections={len(connections)}")
            
            return metrics
        
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return None
