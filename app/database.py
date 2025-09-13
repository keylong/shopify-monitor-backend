"""
Database connection and session management
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator
import os
from loguru import logger

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "")

# If no DATABASE_URL is provided, use in-memory SQLite for production
if not DATABASE_URL:
    if os.getenv("ENVIRONMENT") == "production":
        # Use in-memory database for production if no external DB provided
        DATABASE_URL = "sqlite:///:memory:"
        logger.warning("No DATABASE_URL provided, using in-memory SQLite database. Data will not persist!")
    else:
        # Use file-based SQLite for development
        DATABASE_URL = "sqlite:///./shopify_monitor.db"

# Handle PostgreSQL URL format for production
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine with appropriate settings
try:
    if "sqlite" in DATABASE_URL:
        # SQLite settings
        if ":memory:" in DATABASE_URL:
            # In-memory database settings
            engine = create_engine(
                DATABASE_URL,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=False
            )
        else:
            # File-based SQLite settings
            engine = create_engine(
                DATABASE_URL,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=False
            )
    else:
        # PostgreSQL settings for production
        engine = create_engine(
            DATABASE_URL,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )
except ImportError as e:
    # If psycopg2 is not installed but DATABASE_URL points to PostgreSQL,
    # fall back to in-memory SQLite
    logger.error(f"Database driver not found: {e}")
    logger.warning("Falling back to in-memory SQLite database")
    DATABASE_URL = "sqlite:///:memory:"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    Database dependency for FastAPI
    
    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Initialize database tables
    """
    from app.models.database import Base
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

def reset_db():
    """
    Reset database (for development/testing)
    """
    from app.models.database import Base
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("Database reset successfully")