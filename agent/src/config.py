"""
Configuration management for the agent.
"""
import os
import yaml
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CollectorConfig:
    """Collector connection configuration."""
    url: str
    api_key: Optional[str]
    timeout: int = 5
    retry_attempts: int = 3


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""
    interval: int = 25
    interface: Optional[str] = None


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: Optional[str] = None
    max_size_mb: int = 10
    backup_count: int = 3


@dataclass
class AgentConfig:
    """Complete agent configuration."""
    collector: CollectorConfig
    monitoring: MonitoringConfig
    logging: LoggingConfig


def load_config(config_path: str = None) -> AgentConfig:
    """
    Load configuration from file or environment variables.
    
    Args:
        config_path: Path to YAML config file
        
    Returns:
        AgentConfig object
    """
    # Default config path
    if config_path is None:
        config_path = os.getenv("AGENT_CONFIG", "/etc/tailscale-monitor/agent.yaml")
    
    # Start with defaults
    config_data = {
        'collector': {
            'url': os.getenv('COLLECTOR_URL', 'http://localhost:8080'),
            'api_key': os.getenv('AGENT_API_KEY'),
            'timeout': int(os.getenv('COLLECTOR_TIMEOUT', '5')),
            'retry_attempts': int(os.getenv('RETRY_ATTEMPTS', '3'))
        },
        'monitoring': {
            'interval': int(os.getenv('METRIC_INTERVAL', '25')),
            'interface': os.getenv('TAILSCALE_INTERFACE')
        },
        'logging': {
            'level': os.getenv('LOG_LEVEL', 'INFO'),
            'file': os.getenv('LOG_FILE', '/var/log/tailscale-monitor/agent.log'),
            'max_size_mb': int(os.getenv('LOG_MAX_SIZE_MB', '10')),
            'backup_count': int(os.getenv('LOG_BACKUP_COUNT', '3'))
        }
    }
    
    # Load from file if exists
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                file_config = yaml.safe_load(f)
                if file_config:
                    # Merge file config with defaults (file takes precedence)
                    for section in config_data:
                        if section in file_config:
                            config_data[section].update(file_config[section])
            
            logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.warning(f"Error loading config file {config_path}: {e}")
    
    # Create config objects
    collector_config = CollectorConfig(**config_data['collector'])
    monitoring_config = MonitoringConfig(**config_data['monitoring'])
    logging_config = LoggingConfig(**config_data['logging'])
    
    return AgentConfig(
        collector=collector_config,
        monitoring=monitoring_config,
        logging=logging_config
    )


def save_config(config: AgentConfig, config_path: str = None):
    """
    Save configuration to file.
    
    Args:
        config: AgentConfig object to save
        config_path: Path to save YAML config file
    """
    if config_path is None:
        config_path = "/etc/tailscale-monitor/agent.yaml"
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    config_data = {
        'collector': {
            'url': config.collector.url,
            'api_key': config.collector.api_key,
            'timeout': config.collector.timeout,
            'retry_attempts': config.collector.retry_attempts
        },
        'monitoring': {
            'interval': config.monitoring.interval,
            'interface': config.monitoring.interface
        },
        'logging': {
            'level': config.logging.level,
            'file': config.logging.file,
            'max_size_mb': config.logging.max_size_mb,
            'backup_count': config.logging.backup_count
        }
    }
    
    try:
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)
        
        logger.info(f"Configuration saved to {config_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving config to {config_path}: {e}")
        return False
