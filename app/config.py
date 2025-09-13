"""
Configuration management using Pydantic Settings
"""

from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    app_name: str = "Shopify Monitor API"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="production", env="ENVIRONMENT")
    
    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=4, env="WORKERS")
    
    # Database
    database_url: str = Field(
        default="sqlite:///./shopify_monitor.db",
        env="DATABASE_URL"
    )
    
    # Redis (Optional - will use in-memory if not available)
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")
    
    # Security
    secret_key: str = Field(
        default="your-secret-key-change-in-production",
        env="SECRET_KEY"
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # CORS
    cors_origins: List[str] = Field(
        default=["*"],
        env="CORS_ORIGINS"
    )
    
    # Shopify Monitoring
    max_concurrent_requests: int = Field(default=10, env="MAX_CONCURRENT_REQUESTS")
    request_timeout: int = Field(default=30, env="REQUEST_TIMEOUT")
    batch_size: int = Field(default=100, env="BATCH_SIZE")
    
    # Scheduling
    enable_scheduler: bool = Field(default=True, env="ENABLE_SCHEDULER")
    default_scan_interval: int = Field(default=3600, env="SCAN_INTERVAL")  # seconds
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: Optional[str] = Field(default="app.log", env="LOG_FILE")
    
    # API Keys (for authentication)
    api_keys: List[str] = Field(
        default=["demo-api-key"],
        env="API_KEYS"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Create global settings instance
settings = Settings()