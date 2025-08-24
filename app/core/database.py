"""Database configuration and session management."""

from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os

from .config import settings

# Database engine configuration
# Handle different database types
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite configuration
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=settings.DEBUG,
        poolclass=StaticPool
    )
elif settings.DATABASE_URL.startswith("postgresql"):
    # PostgreSQL configuration - use psycopg2 if available, otherwise fallback
    try:
        import psycopg2
        # Use standard PostgreSQL URL
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=settings.DEBUG
        )
    except ImportError:
        # Fallback to SQLite for development
        print("⚠️  psycopg2 not available, using SQLite fallback")
        engine = create_engine(
            "sqlite:///./ad-platform.db",
            pool_pre_ping=True,
            pool_recycle=300,
            echo=settings.DEBUG,
            poolclass=StaticPool
        )
else:
    # Default configuration
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=settings.DEBUG
    )

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Database dependency for FastAPI endpoints."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Database event handlers
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key support for SQLite."""
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log slow queries in debug mode."""
    if settings.DEBUG:
        conn.info.setdefault('query_start_time', []).append(conn.info.get('query_start_time', [None])[-1])


@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log query execution time in debug mode."""
    if settings.DEBUG:
        total = conn.info.get('query_start_time', [None])[-1]
        if total is not None:
            print(f"Query executed in {total:.4f}s: {statement[:100]}...")


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def close_db() -> None:
    """Close database connections."""
    engine.dispose() 