"""Database configuration and session management.

This module provides database connection and session management.
"""

import os
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

# Database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://username:password@localhost/database_name"
)

# Create engine
engine = create_engine(DATABASE_URL)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db() -> Iterator[Session]:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
