"""
HTTP client for sending metrics to the collector.
"""
import requests
import logging
from typing import Optional
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from shared.schemas import MetricSubmission, AgentRegistration, AgentRegistrationResponse
from shared.constants import RETRY_BACKOFF_SECONDS

logger = logging.getLogger(__name__)


class CollectorClient:
    """HTTP client for communicating with the collector."""
    
    def __init__(self, collector_url: str, api_key: Optional[str] = None, timeout: int = 5):
        """
        Initialize the client.
        
        Args:
            collector_url: Base URL of the collector (e.g., http://100.113.155.67:8080)
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.collector_url = collector_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'TailscaleMonitorAgent/1.0'
        })
        
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}'
            })
    
    def set_api_key(self, api_key: str):
        """Update the API key."""
        self.api_key = api_key
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}'
        })
    
    def register(self, hostname: str, tailscale_ip: str, os_type: str) -> Optional[AgentRegistrationResponse]:
        """
        Register the agent with the collector.
        
        Args:
            hostname: Machine hostname
            tailscale_ip: Tailscale IP address
            os_type: Operating system (linux/windows)
            
        Returns:
            AgentRegistrationResponse or None if registration failed
        """
        url = f"{self.collector_url}/api/v1/register"
        
        registration = AgentRegistration(
            hostname=hostname,
            tailscale_ip=tailscale_ip,
            os_type=os_type
        )
        
        try:
            logger.info(f"Registering agent: {hostname} ({tailscale_ip})")
            
            response = self.session.post(
                url,
                json=registration.model_dump(),
                timeout=self.timeout
            )
            
            response.raise_for_status()
            data = response.json()
            
            result = AgentRegistrationResponse(**data)
            logger.info(f"Registration successful: agent_id={result.agent_id}")
            
            # Update API key for future requests
            self.set_api_key(result.api_key)
            
            return result
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                logger.error("Agent already registered. Use existing credentials.")
            else:
                logger.error(f"Registration failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return None
    
    def submit_metrics(
        self,
        submission: MetricSubmission,
        retry_attempts: int = 3
    ) -> bool:
        """
        Submit metrics to the collector with retry logic.
        
        Args:
            submission: Metrics to submit
            retry_attempts: Number of retry attempts
            
        Returns:
            True if successful, False otherwise
        """
        url = f"{self.collector_url}/api/v1/metrics"
        
        for attempt in range(retry_attempts):
            try:
                response = self.session.post(
                    url,
                    json=submission.model_dump(mode='json'),
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                
                logger.debug(f"Metrics submitted successfully")
                return True
            
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    logger.error("Authentication failed. Check API key.")
                    return False
                else:
                    logger.warning(f"HTTP error submitting metrics: {e}")
            
            except requests.exceptions.ConnectionError:
                logger.warning(f"Connection error (attempt {attempt + 1}/{retry_attempts})")
            
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{retry_attempts})")
            
            except Exception as e:
                logger.error(f"Unexpected error submitting metrics: {e}")
            
            # Wait before retry (exponential backoff)
            if attempt < retry_attempts - 1:
                import time
                backoff = RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)]
                logger.debug(f"Retrying in {backoff} seconds...")
                time.sleep(backoff)
        
        logger.error(f"Failed to submit metrics after {retry_attempts} attempts")
        return False
    
    def health_check(self) -> bool:
        """
        Check if collector is reachable.
        
        Returns:
            True if collector is healthy, False otherwise
        """
        url = f"{self.collector_url}/api/v1/health"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False
