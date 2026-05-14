"""
SQLAlchemy database models for persistent novel storage.

This module defines the database schema for storing novel metadata,
scraping progress, and other persistent data using SQLAlchemy ORM.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import func

from .models import NovelMetadata, NovelStatus, ScrapingProgress, ScrapingStatus

logger = logging.getLogger(__name__)

Base = declarative_base()


class NovelRecord(Base):
    """
    SQLAlchemy model for storing novel metadata and status.

    This table stores persistent information about novels including
    metadata, scraping status, file locations, and progress tracking.
    """

    __tablename__ = "novels"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Novel identification
    title = Column(String(500), nullable=False)
    author = Column(String(200), nullable=False)
    source_url = Column(String(1000), nullable=False, unique=True)
    provider = Column(String(50), nullable=True)
    provider_id = Column(String(100), nullable=True)

    # File system information
    directory_path = Column(String(1000), nullable=True)
    markdown_file_path = Column(String(1000), nullable=True)
    epub_file_path = Column(String(1000), nullable=True)
    cover_file_path = Column(String(1000), nullable=True)

    # Novel metadata
    description = Column(Text, nullable=True)
    cover_url = Column(String(1000), nullable=True)
    genres = Column(JSON, nullable=True)  # List of genre strings
    tags = Column(JSON, nullable=True)  # List of tag strings
    alternative_names = Column(JSON, nullable=True)  # List of alternative names

    # Novel status and statistics
    novel_status = Column(String(20), nullable=False, default=NovelStatus.UNKNOWN.value)
    scraping_status = Column(
        String(20), nullable=False, default=ScrapingStatus.NOT_STARTED.value
    )

    # Chapter and content information
    total_chapters = Column(Integer, nullable=True)
    completed_chapters = Column(Integer, nullable=False, default=0)
    last_chapter_scraped = Column(Integer, nullable=True)
    last_chapter_url = Column(String(1000), nullable=True)

    # Statistics
    word_count = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)
    rating_count = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
    last_scraped_at = Column(DateTime, nullable=True)
    publication_date = Column(DateTime, nullable=True)
    novel_last_updated = Column(
        DateTime, nullable=True
    )  # When the novel was last updated on the source

    # Progress tracking
    scraping_start_time = Column(DateTime, nullable=True)
    scraping_end_time = Column(DateTime, nullable=True)
    estimated_completion = Column(DateTime, nullable=True)
    chapters_per_minute = Column(Float, nullable=True)

    # Error tracking
    error_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)

    # Additional metadata as JSON
    metadata_json = Column(
        JSON, nullable=True
    )  # For storing additional flexible metadata

    # File information
    markdown_file_size = Column(Integer, nullable=True)
    epub_file_size = Column(Integer, nullable=True)

    # Flags
    has_epub = Column(Boolean, nullable=False, default=False)
    has_cover = Column(Boolean, nullable=False, default=False)
    is_favorite = Column(Boolean, nullable=False, default=False)
    is_archived = Column(Boolean, nullable=False, default=False)

    def to_novel_metadata(self) -> NovelMetadata:
        """Convert database record to NovelMetadata dataclass."""
        return NovelMetadata(
            title=self.title,
            author=self.author,
            description=self.description or "",
            source_url=self.source_url,
            cover_url=self.cover_url,
            genres=self.genres or [],
            tags=self.tags or [],
            status=(
                NovelStatus(self.novel_status)
                if self.novel_status
                else NovelStatus.UNKNOWN
            ),
            alternative_names=self.alternative_names or [],
            rating=self.rating,
            rating_count=self.rating_count,
            chapter_count=self.total_chapters,
            word_count=self.word_count,
            publication_date=self.publication_date,
            last_updated=self.novel_last_updated,
            scraped_at=self.last_scraped_at or self.created_at,
            provider=self.provider,
            provider_id=self.provider_id,
        )

    def to_scraping_progress(self) -> ScrapingProgress:
        """Convert database record to ScrapingProgress dataclass."""
        return ScrapingProgress(
            novel_url=self.source_url,
            total_chapters=self.total_chapters or 0,
            completed_chapters=self.completed_chapters,
            failed_chapters=[],  # Would need separate table for detailed tracking
            skipped_chapters=[],  # Would need separate table for detailed tracking
            status=(
                ScrapingStatus(self.scraping_status)
                if self.scraping_status
                else ScrapingStatus.NOT_STARTED
            ),
            start_time=self.scraping_start_time,
            end_time=self.scraping_end_time,
            last_update=self.updated_at,
            estimated_completion=self.estimated_completion,
            chapters_per_minute=self.chapters_per_minute,
            error_count=self.error_count,
            last_error=self.last_error,
            retry_count=self.retry_count,
            output_directory=self.directory_path,
            generated_files=[],  # Would need separate table for detailed tracking
        )

    def update_from_metadata(self, metadata: NovelMetadata) -> None:
        """Update record from NovelMetadata dataclass."""
        self.title = metadata.title
        self.author = metadata.author
        self.description = metadata.description
        self.cover_url = metadata.cover_url
        self.genres = metadata.genres
        self.tags = metadata.tags
        self.novel_status = (
            metadata.status.value if metadata.status else NovelStatus.UNKNOWN.value
        )
        self.alternative_names = metadata.alternative_names
        self.rating = metadata.rating
        self.rating_count = metadata.rating_count
        self.total_chapters = metadata.chapter_count
        self.word_count = metadata.word_count
        self.publication_date = metadata.publication_date
        self.novel_last_updated = metadata.last_updated
        self.provider = metadata.provider
        self.provider_id = metadata.provider_id
        self.last_scraped_at = metadata.scraped_at
        self.updated_at = datetime.now()

    def update_from_progress(self, progress: ScrapingProgress) -> None:
        """Update record from ScrapingProgress dataclass."""
        self.total_chapters = progress.total_chapters
        self.completed_chapters = progress.completed_chapters
        self.scraping_status = progress.status.value
        self.scraping_start_time = progress.start_time
        self.scraping_end_time = progress.end_time
        self.estimated_completion = progress.estimated_completion
        self.chapters_per_minute = progress.chapters_per_minute
        self.error_count = progress.error_count
        self.last_error = progress.last_error
        self.retry_count = progress.retry_count
        self.directory_path = progress.output_directory
        self.updated_at = datetime.now()

    def __repr__(self) -> str:
        try:
            return f"<NovelRecord(id={self.id}, title='{self.title}', author='{self.author}', status='{self.scraping_status}')>"
        except:
            # Handle detached instances
            return f"<NovelRecord(detached)>"

    # Define table arguments with indexes
    __table_args__ = (
        Index("idx_novels_status_updated", "scraping_status", "updated_at"),
        Index("idx_novels_provider_status", "provider", "scraping_status"),
        Index("idx_novels_created_status", "created_at", "scraping_status"),
        Index("idx_novels_title_author", "title", "author"),
        Index("idx_novels_last_scraped", "last_scraped_at"),
        Index("idx_novels_has_epub", "has_epub"),
        Index("idx_novels_favorite_archived", "is_favorite", "is_archived"),
        Index("idx_novels_directory_path", "directory_path"),
    )


# Indexes are defined in NovelRecord.__table_args__ above


class DatabaseManager:
    """
    Database manager for handling SQLAlchemy operations.

    Provides a centralized interface for database operations including
    connection management, session handling, and schema creation.
    """

    def __init__(self, database_url: str = "sqlite:///novels.db"):
        """
        Initialize database manager.

        Args:
            database_url: SQLAlchemy database URL
        """
        self.database_url = database_url
        # Create engine with optimized connection pooling
        if database_url.startswith("sqlite"):
            # SQLite-specific optimizations
            self.engine = create_engine(
                database_url,
                echo=False,  # Set to True for SQL debugging
                pool_pre_ping=True,  # Verify connections before use
                pool_recycle=3600,  # Recycle connections after 1 hour
                # SQLite doesn't support connection pooling, but we can optimize other settings
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30,
                },
            )
        else:
            # PostgreSQL/MySQL optimizations
            self.engine = create_engine(
                database_url,
                echo=False,  # Set to True for SQL debugging
                pool_pre_ping=True,  # Verify connections before use
                pool_recycle=3600,  # Recycle connections after 1 hour
                pool_size=10,  # Number of connections to maintain
                max_overflow=20,  # Additional connections allowed
                pool_timeout=30,  # Timeout for getting connection from pool
            )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        # Enable WAL mode for SQLite for better concurrency
        if database_url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.close()

    def create_tables(self) -> None:
        """Create all database tables and run migrations."""
        Base.metadata.create_all(bind=self.engine)

        # Run database migrations
        self._run_migrations()

    def _run_migrations(self) -> None:
        """Run database migrations."""
        try:
            from .database_migrations import create_migrator

            migrator = create_migrator(self.database_url)
            stats = migrator.migrate()

            if stats["applied"] > 0:
                logger.info(f"Applied {stats['applied']} database migrations")
            if stats["failed"] > 0:
                logger.warning(f"Failed to apply {stats['failed']} migrations")

        except Exception as e:
            logger.error(f"Migration error: {e}")
            # Don't fail database initialization for migration errors
            logger.warning("Continuing without migrations")

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    def close(self) -> None:
        """Close the database engine."""
        self.engine.dispose()

    def backup_database(self, backup_path: str) -> bool:
        """
        Create a backup of the database.

        Args:
            backup_path: Path where to save the backup

        Returns:
            True if backup was successful
        """
        try:
            import shutil
            from pathlib import Path

            if self.database_url.startswith("sqlite"):
                # Extract database file path from URL
                db_path = self.database_url.replace("sqlite:///", "")
                if Path(db_path).exists():
                    shutil.copy2(db_path, backup_path)
                    return True
            return False
        except Exception:
            return False

    def restore_database(self, backup_path: str) -> bool:
        """
        Restore database from backup.

        Args:
            backup_path: Path to backup file

        Returns:
            True if restore was successful
        """
        try:
            import shutil
            from pathlib import Path

            if self.database_url.startswith("sqlite") and Path(backup_path).exists():
                # Extract database file path from URL
                db_path = self.database_url.replace("sqlite:///", "")
                # Close current connections
                self.close()
                # Restore backup
                shutil.copy2(backup_path, db_path)
                # Recreate engine
                self.engine = create_engine(
                    self.database_url,
                    echo=False,
                    pool_pre_ping=True,
                )
                self.SessionLocal = sessionmaker(
                    autocommit=False, autoflush=False, bind=self.engine
                )
                return True
            return False
        except Exception:
            return False

    def get_schema_version(self) -> int:
        """
        Get current database schema version.

        Returns:
            Schema version number
        """
        try:
            with self.get_session() as session:
                # Try to get version from a metadata table (if it exists)
                result = session.execute(
                    "SELECT version FROM schema_version ORDER BY id DESC LIMIT 1"
                )
                row = result.fetchone()
                return row[0] if row else 1
        except Exception:
            # If table doesn't exist, assume version 1
            return 1

    def set_schema_version(self, version: int) -> bool:
        """
        Set database schema version.

        Args:
            version: Version number to set

        Returns:
            True if successful
        """
        try:
            with self.get_session() as session:
                # Create schema_version table if it doesn't exist
                session.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_version (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version INTEGER NOT NULL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # Insert new version
                session.execute(
                    "INSERT INTO schema_version (version) VALUES (?)", (version,)
                )
                session.commit()
                return True
        except Exception:
            return False
