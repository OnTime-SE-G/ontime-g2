"""Configuration for Crowd Service."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Service
    service_name: str = "crowd-service"
    debug: bool = False
    
    # Logging
    log_level: str = "INFO"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_crowd_predictions_key: str = "crowd:predictions"  # Redis key prefix for predictions
    
    # Model
    model_path: Optional[str] = None  # Path to trained Random Forest model (pickle)
    
    # Stop zones configuration
    stops_config_path: Optional[str] = None  # Path to stops JSON config
    
    class Config:
        env_file = ".env"
        case_sensitive = False
