"""
Authentication utilities.
"""
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from ..database.models import Agent

# Password hashing context
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def generate_api_key() -> str:
    """Generate a secure API key."""
    return secrets.token_urlsafe(16)


def generate_agent_id() -> str:
    """Generate a unique agent ID."""
    return str(uuid.uuid4())


def hash_api_key(api_key: str) -> str:
    """Hash an API key using bcrypt."""
    # Bcrypt has a 72-byte limit, so truncate if necessary
    key_to_hash = api_key[:72] if len(api_key) > 72 else api_key
    return pwd_context.hash(key_to_hash)


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash."""
    # Bcrypt has a 72-byte limit, so truncate if necessary
    key_to_verify = plain_key[:72] if len(plain_key) > 72 else plain_key
    return pwd_context.verify(key_to_verify, hashed_key)


def authenticate_agent(db: Session, api_key: str) -> Optional[Agent]:
    """
    Authenticate an agent using its API key.
    
    Args:
        db: Database session
        api_key: Plain API key from request
        
    Returns:
        Agent object if authentication successful, None otherwise
    """
    # Get all agents (we need to check hash for each)
    agents = db.query(Agent).all()
    
    for agent in agents:
        if verify_api_key(api_key, agent.api_key_hash):
            # Update last_seen timestamp
            agent.last_seen = datetime.utcnow()
            agent.status = "online"
            db.commit()
            return agent
    
    return None


def check_agent_timeout(db: Session, timeout_seconds: int = 300):
    """
    Mark agents as offline if they haven't sent metrics recently.
    
    Args:
        db: Database session
        timeout_seconds: Seconds before marking offline (default 5 minutes)
    """
    timeout_threshold = datetime.utcnow() - timedelta(seconds=timeout_seconds)
    
    agents = db.query(Agent).filter(
        Agent.last_seen < timeout_threshold,
        Agent.status != "offline"
    ).all()
    
    for agent in agents:
        agent.status = "offline"
    
    if agents:
        db.commit()
