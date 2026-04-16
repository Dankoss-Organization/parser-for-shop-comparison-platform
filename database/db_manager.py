"""
Database management module for PostgreSQL connectivity.

This module initializes the SQLAlchemy engine and session factory. It serves
as the entry point for all database interactions within the Shop Comparison
Platform, handling connection pooling and session lifecycle management.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
from typing import Generator

# Load environment variables from a .env file
load_dotenv()

# Retrieve the database connection string from environment variables.
# Expected format: postgresql+psycopg2://user:password@host:port/dbname
DB_URL: Optional[str] = os.getenv("DATABASE_URL")

if not DB_URL:
    raise ValueError("❌ DATABASE_URL not found in .env file! Please ensure the environment is configured correctly.")

# --- SQLAlchemy Configuration ---

# The Engine is the starting point for any SQLAlchemy application.
# pool_pre_ping=True: Enables a "pessimistic" connection handling strategy that
# checks if a connection is still alive before using it, preventing 'server closed
# the connection' errors (critical for serverless DBs like Neon).
engine = create_engine(DB_URL, pool_pre_ping=True)

# SessionLocal is a factory for creating new Session objects.
# autocommit=False: Transactions must be explicitly committed.
# autoflush=False: Prevents automatic flushing of changes before every query.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    A dependency generator that provides a standalone SQLAlchemy session.

    This function is designed to be used as a context manager or a dependency
    (e.g., in FastAPI). It ensures that every operation has access to a fresh
    database session and, most importantly, guarantees that the session is
    closed after the operation is complete, even if an exception occurs.

    Yields:
        Generator[Session, None, None]: An active SQLAlchemy Session instance.

    Usage:
        >>> with next(get_db()) as session:
        >>>     # perform database operations
        >>>     pass
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        # Ensures that the database connection is returned to the pool
        db.close()