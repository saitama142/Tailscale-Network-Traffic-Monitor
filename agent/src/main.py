"""
Main agent application.
"""
import os
import sys
import time
import logging
import signal
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.schemas import MetricSubmission
from src.monitor import NetworkMonitor
from src.collector_client import CollectorClient
from src.config import load_config, save_config

# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global running
    logging.info(f"Received signal {signum}, shutting down...")
    running = False


def setup_logging(config):
    """Setup logging configuration."""
    log_level = getattr(logging, config.logging.level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if config.logging.file:
        try:
            # Ensure log directory exists
            log_dir = os.path.dirname(config.logging.file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            
            file_handler = RotatingFileHandler(
                config.logging.file,
                maxBytes=config.logging.max_size_mb * 1024 * 1024,
                backupCount=config.logging.backup_count
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not setup file logging: {e}")
    
    return logger


def main():
    """Main agent loop."""
    global running
    
    # Load configuration
    try:
        config = load_config()
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)
    
    # Setup logging
    logger = setup_logging(config)
    logger.info("Tailscale Network Monitor Agent starting...")
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize network monitor
    try:
        monitor = NetworkMonitor()
        logger.info(f"Monitoring interface: {monitor.interface_name}")
        logger.info(f"Hostname: {monitor.hostname}")
        logger.info(f"Tailscale IP: {monitor.tailscale_ip}")
    except Exception as e:
        logger.error(f"Failed to initialize monitor: {e}")
        sys.exit(1)
    
    # Initialize collector client
    client = CollectorClient(
        collector_url=config.collector.url,
        api_key=config.collector.api_key,
        timeout=config.collector.timeout
    )
    
    # Check if we need to register
    if not config.collector.api_key:
        logger.info("No API key found, registering agent...")
        
        # Register
        response = client.register(
            hostname=monitor.hostname,
            tailscale_ip=monitor.tailscale_ip,
            os_type=monitor.os_type
        )
        
        if response:
            # Save API key to config
            config.collector.api_key = response.api_key
            save_config(config)
            logger.info("Agent registered and configuration saved")
        else:
            logger.error("Registration failed")
            sys.exit(1)
    else:
        logger.info("Using existing API key")
    
    # Main monitoring loop
    logger.info(f"Starting metric collection (interval: {config.monitoring.interval}s)")
    
    consecutive_failures = 0
    max_failures = 10
    
    while running:
        try:
            # Collect metrics
            metrics = monitor.collect_metrics()
            
            if metrics is None:
                logger.warning("Failed to collect metrics")
                consecutive_failures += 1
            else:
                # Create submission
                submission = MetricSubmission(
                    hostname=monitor.hostname,
                    timestamp=datetime.utcnow(),
                    tailscale_ip=monitor.tailscale_ip,
                    metrics=metrics
                )
                
                # Submit to collector
                success = client.submit_metrics(
                    submission,
                    retry_attempts=config.collector.retry_attempts
                )
                
                if success:
                    consecutive_failures = 0
                    logger.info(
                        f"Metrics submitted: ↑{metrics.current_upload_mbps:.2f} Mbps, "
                        f"↓{metrics.current_download_mbps:.2f} Mbps, "
                        f"{len(metrics.active_connections)} connections"
                    )
                else:
                    consecutive_failures += 1
            
            # Check if too many failures
            if consecutive_failures >= max_failures:
                logger.error(f"Too many consecutive failures ({consecutive_failures}), exiting")
                break
            
            # Sleep until next interval
            time.sleep(config.monitoring.interval)
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            consecutive_failures += 1
            time.sleep(config.monitoring.interval)
    
    logger.info("Agent stopped")
    sys.exit(0)


if __name__ == "__main__":
    main()
