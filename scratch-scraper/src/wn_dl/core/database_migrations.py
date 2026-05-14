"""
Database Migration System for wn-dl.

This module provides database schema versioning and migration capabilities
to handle database upgrades and schema changes gracefully.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Migration tracking table
MigrationBase = declarative_base()


class MigrationRecord(MigrationBase):
    """Track applied database migrations."""

    __tablename__ = "schema_migrations"

    id = Column(Integer, primary_key=True)
    version = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow)
    checksum = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)


class Migration:
    """Base class for database migrations."""

    def __init__(self, version: str, name: str, description: str = ""):
        self.version = version
        self.name = name
        self.description = description

    def up(self, engine) -> None:
        """Apply the migration."""
        raise NotImplementedError("Migration must implement up() method")

    def down(self, engine) -> None:
        """Rollback the migration (optional)."""
        logger.warning(f"Migration {self.version} does not support rollback")

    def get_checksum(self) -> str:
        """Get migration checksum for verification."""
        import hashlib

        content = f"{self.version}:{self.name}:{self.description}"
        return hashlib.sha256(content.encode()).hexdigest()


class DatabaseMigrator:
    """Database migration manager."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.migrations: Dict[str, Migration] = {}

        # Ensure migration tracking table exists
        MigrationBase.metadata.create_all(self.engine)

    def register_migration(self, migration: Migration) -> None:
        """Register a migration."""
        self.migrations[migration.version] = migration
        logger.debug(f"Registered migration: {migration.version} - {migration.name}")

    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions."""
        with self.SessionLocal() as session:
            records = (
                session.query(MigrationRecord).order_by(MigrationRecord.version).all()
            )
            return [record.version for record in records]

    def get_pending_migrations(self) -> List[Migration]:
        """Get list of pending migrations."""
        applied = set(self.get_applied_migrations())
        pending = []

        # Sort migrations by version
        for version in sorted(self.migrations.keys()):
            if version not in applied:
                pending.append(self.migrations[version])

        return pending

    def apply_migration(self, migration: Migration) -> bool:
        """Apply a single migration."""
        try:
            logger.info(f"Applying migration {migration.version}: {migration.name}")

            # Apply the migration
            migration.up(self.engine)

            # Record the migration
            with self.SessionLocal() as session:
                record = MigrationRecord(
                    version=migration.version,
                    name=migration.name,
                    description=migration.description,
                    checksum=migration.get_checksum(),
                    applied_at=datetime.utcnow(),
                )
                session.add(record)
                session.commit()

            logger.info(f"Successfully applied migration {migration.version}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply migration {migration.version}: {e}")
            return False

    def migrate(self) -> Dict[str, int]:
        """Apply all pending migrations."""
        pending = self.get_pending_migrations()

        stats = {"pending": len(pending), "applied": 0, "failed": 0}

        if not pending:
            logger.info("No pending migrations")
            return stats

        logger.info(f"Found {len(pending)} pending migrations")

        for migration in pending:
            if self.apply_migration(migration):
                stats["applied"] += 1
            else:
                stats["failed"] += 1
                # Stop on first failure
                break

        return stats

    def get_migration_status(self) -> Dict[str, any]:
        """Get current migration status."""
        applied = self.get_applied_migrations()
        pending = self.get_pending_migrations()

        return {
            "total_migrations": len(self.migrations),
            "applied_count": len(applied),
            "pending_count": len(pending),
            "applied_versions": applied,
            "pending_versions": [m.version for m in pending],
            "current_version": applied[-1] if applied else None,
        }


# Define migrations
class InitialSchemaMigration(Migration):
    """Initial database schema migration."""

    def __init__(self):
        super().__init__(
            version="001",
            name="initial_schema",
            description="Create initial database schema with novels table",
        )

    def up(self, engine) -> None:
        """Create initial schema - this is handled by SQLAlchemy create_all()."""
        # The initial schema is created by the main database models
        # This migration exists for tracking purposes
        logger.info("Initial schema migration - tables created by SQLAlchemy")


class AddIndexesMigration(Migration):
    """Add performance indexes migration."""

    def __init__(self):
        super().__init__(
            version="002",
            name="add_performance_indexes",
            description="Add database indexes for better query performance",
        )

    def up(self, engine) -> None:
        """Add performance indexes."""
        from sqlalchemy import text

        with engine.connect() as conn:
            try:
                # Add index for novel search by title and author
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_novels_search
                    ON novels(title, author)
                """
                    )
                )

                # Add index for filtering by novel status
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_novels_novel_status
                    ON novels(novel_status)
                """
                    )
                )

                # Add index for filtering by provider
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_novels_provider_filter
                    ON novels(provider)
                """
                    )
                )

                # Add index for date-based queries
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_novels_dates
                    ON novels(created_at, updated_at)
                """
                    )
                )

                conn.commit()
                logger.info("Successfully added performance indexes")

            except Exception as e:
                logger.warning(f"Some indexes may already exist: {e}")


class AddFullTextSearchMigration(Migration):
    """Add full-text search capabilities."""

    def __init__(self):
        super().__init__(
            version="003",
            name="add_fulltext_search",
            description="Add full-text search indexes for title and description",
        )

    def up(self, engine) -> None:
        """Add full-text search indexes."""
        from sqlalchemy import text

        with engine.connect() as conn:
            try:
                # Check if we're using SQLite (which has limited FTS support)
                if "sqlite" in str(engine.url):
                    # For SQLite, create a simple text index
                    conn.execute(
                        text(
                            """
                        CREATE INDEX IF NOT EXISTS idx_novels_title_search
                        ON novels(title COLLATE NOCASE)
                    """
                        )
                    )
                    conn.execute(
                        text(
                            """
                        CREATE INDEX IF NOT EXISTS idx_novels_description_search
                        ON novels(description COLLATE NOCASE)
                    """
                        )
                    )
                else:
                    # For PostgreSQL, use full-text search
                    conn.execute(
                        text(
                            """
                        CREATE INDEX IF NOT EXISTS idx_novels_title_fts
                        ON novels USING gin(to_tsvector('english', title))
                    """
                        )
                    )
                    conn.execute(
                        text(
                            """
                        CREATE INDEX IF NOT EXISTS idx_novels_description_fts
                        ON novels USING gin(to_tsvector('english', description))
                    """
                        )
                    )

                conn.commit()
                logger.info("Successfully added full-text search indexes")

            except Exception as e:
                logger.warning(f"Failed to add full-text search indexes: {e}")


class AddFileMetadataMigration(Migration):
    """Add file metadata tracking."""

    def __init__(self):
        super().__init__(
            version="004",
            name="add_file_metadata",
            description="Add columns for tracking file metadata and checksums",
        )

    def up(self, engine) -> None:
        """Add file metadata columns."""
        from sqlalchemy import text

        with engine.connect() as conn:
            try:
                # Add markdown file checksum for change detection
                conn.execute(
                    text(
                        """
                    ALTER TABLE novels
                    ADD COLUMN markdown_checksum VARCHAR(64)
                """
                    )
                )

                # Add EPUB file checksum
                conn.execute(
                    text(
                        """
                    ALTER TABLE novels
                    ADD COLUMN epub_checksum VARCHAR(64)
                """
                    )
                )

                # Add last sync timestamp
                conn.execute(
                    text(
                        """
                    ALTER TABLE novels
                    ADD COLUMN last_synced_at DATETIME
                """
                    )
                )

                conn.commit()
                logger.info("Successfully added file metadata columns")

            except Exception as e:
                logger.warning(f"File metadata columns may already exist: {e}")


# Migration registry
def get_default_migrations() -> List[Migration]:
    """Get the default set of migrations."""
    return [
        InitialSchemaMigration(),
        AddIndexesMigration(),
        AddFullTextSearchMigration(),
        AddFileMetadataMigration(),
    ]


def create_migrator(database_url: str) -> DatabaseMigrator:
    """Create a database migrator with default migrations."""
    migrator = DatabaseMigrator(database_url)

    # Register default migrations
    for migration in get_default_migrations():
        migrator.register_migration(migration)

    return migrator
