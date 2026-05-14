"""
Novel Database Service for persistent storage operations.

This module provides a high-level service interface for managing novel
metadata and scraping progress in the database.
"""

import logging
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.exc import SQLAlchemyError

from .database_models import DatabaseManager, NovelRecord
from .models import NovelMetadata, NovelStatus, ScrapingProgress, ScrapingStatus

logger = logging.getLogger(__name__)


class NovelDatabaseService:
    """
    High-level service for novel database operations.

    Provides CRUD operations, search functionality, and data synchronization
    for novel metadata and scraping progress.
    """

    def __init__(self, database_path: Optional[str] = None):
        """
        Initialize the database service.

        Args:
            database_path: Path to the SQLite database file. If None, uses default location.
        """
        try:
            if database_path is None:
                # Default to user's home directory
                home_dir = Path.home()
                database_path = str(home_dir / ".wn-dl" / "novels.db")

            logger.debug(f"Initializing database at path: {database_path}")

            # Ensure directory exists
            db_path = Path(database_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)

            database_url = f"sqlite:///{database_path}"
            logger.debug(f"Database URL: {database_url}")

            self.db_manager = DatabaseManager(database_url)
            self.db_manager.create_tables()

            logger.info(f"Successfully initialized novel database at: {database_path}")

        except Exception as e:
            logger.error(f"Failed to initialize database at {database_path}: {e}")
            logger.debug(f"Error details: {type(e).__name__}: {e}")
            raise RuntimeError(f"Database initialization failed: {e}") from e

    @contextmanager
    def get_session(self):
        """Context manager for database sessions with automatic cleanup."""
        session = self.db_manager.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def create_novel(
        self, metadata: NovelMetadata, directory_path: Optional[str] = None
    ) -> NovelRecord:
        """
        Create a new novel record in the database.

        Args:
            metadata: Novel metadata
            directory_path: Path to the novel's directory

        Returns:
            Created NovelRecord

        Raises:
            ValueError: If novel with same URL already exists or metadata is invalid
            RuntimeError: If database operation fails
        """
        try:
            # Validate metadata
            if not metadata.source_url:
                raise ValueError("Novel metadata must have a source URL")
            if not metadata.title:
                raise ValueError("Novel metadata must have a title")

            logger.debug(f"Creating novel record for: {metadata.title}")

            with self.get_session() as session:
                # Check if novel already exists
                existing = (
                    session.query(NovelRecord)
                    .filter_by(source_url=metadata.source_url)
                    .first()
                )
                if existing:
                    logger.warning(
                        f"Novel with URL {metadata.source_url} already exists (ID: {existing.id})"
                    )
                    raise ValueError(
                        f"Novel with URL {metadata.source_url} already exists"
                    )

                # Create new record
                novel = NovelRecord(
                    source_url=metadata.source_url,
                    directory_path=directory_path,
                )
                novel.update_from_metadata(metadata)

                session.add(novel)
                session.flush()  # Get the ID

                # Eagerly load all attributes to avoid DetachedInstanceError
                _ = (
                    novel.id,
                    novel.title,
                    novel.author,
                    novel.source_url,
                    novel.provider,
                    novel.provider_id,
                    novel.directory_path,
                    novel.markdown_file_path,
                    novel.epub_file_path,
                    novel.cover_file_path,
                    novel.description,
                    novel.genres,
                    novel.tags,
                    novel.alternative_names,
                    novel.novel_status,
                    novel.scraping_status,
                    novel.total_chapters,
                    novel.completed_chapters,
                    novel.last_chapter_scraped,
                    novel.last_chapter_url,
                    novel.word_count,
                    novel.rating,
                    novel.rating_count,
                    novel.created_at,
                    novel.updated_at,
                    novel.last_scraped_at,
                    novel.publication_date,
                    novel.novel_last_updated,
                    novel.scraping_start_time,
                    novel.scraping_end_time,
                    novel.estimated_completion,
                    novel.chapters_per_minute,
                    novel.error_count,
                    novel.last_error,
                    novel.retry_count,
                    novel.metadata_json,
                    novel.markdown_file_size,
                    novel.epub_file_size,
                    novel.has_epub,
                    novel.has_cover,
                    novel.is_favorite,
                    novel.is_archived,
                )

                # Expunge the record from session to make it independent
                session.expunge(novel)

                logger.info(
                    f"Successfully created novel record: {novel.title} (ID: {novel.id})"
                )
                return novel

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(f"Failed to create novel record for {metadata.title}: {e}")
            logger.debug(f"Error details: {type(e).__name__}: {e}")
            raise RuntimeError(f"Database operation failed: {e}") from e

    def get_novel_by_id(self, novel_id: int) -> Optional[NovelRecord]:
        """Get novel by database ID."""
        with self.get_session() as session:
            record = session.query(NovelRecord).filter_by(id=novel_id).first()
            if record:
                # Eagerly load all attributes to avoid DetachedInstanceError
                _ = (
                    record.id,
                    record.title,
                    record.author,
                    record.source_url,
                    record.provider,
                    record.provider_id,
                    record.directory_path,
                    record.markdown_file_path,
                    record.epub_file_path,
                    record.cover_file_path,
                    record.description,
                    record.genres,
                    record.tags,
                    record.alternative_names,
                    record.novel_status,
                    record.scraping_status,
                    record.total_chapters,
                    record.completed_chapters,
                    record.last_chapter_scraped,
                    record.last_chapter_url,
                    record.word_count,
                    record.rating,
                    record.rating_count,
                    record.created_at,
                    record.updated_at,
                    record.last_scraped_at,
                    record.publication_date,
                    record.novel_last_updated,
                    record.scraping_start_time,
                    record.scraping_end_time,
                    record.estimated_completion,
                    record.chapters_per_minute,
                    record.error_count,
                    record.last_error,
                    record.retry_count,
                    record.metadata_json,
                    record.markdown_file_size,
                    record.epub_file_size,
                    record.has_epub,
                    record.has_cover,
                    record.is_favorite,
                    record.is_archived,
                )
                # Expunge the record from session to make it independent
                session.expunge(record)
            return record

    def get_novel_by_url(self, source_url: str) -> Optional[NovelRecord]:
        """Get novel by source URL."""
        with self.get_session() as session:
            record = session.query(NovelRecord).filter_by(source_url=source_url).first()
            if record:
                # Eagerly load all attributes to avoid DetachedInstanceError
                _ = (
                    record.id,
                    record.title,
                    record.author,
                    record.source_url,
                    record.provider,
                    record.provider_id,
                    record.directory_path,
                    record.markdown_file_path,
                    record.epub_file_path,
                    record.cover_file_path,
                    record.description,
                    record.genres,
                    record.tags,
                    record.alternative_names,
                    record.novel_status,
                    record.scraping_status,
                    record.total_chapters,
                    record.completed_chapters,
                    record.last_chapter_scraped,
                    record.last_chapter_url,
                    record.word_count,
                    record.rating,
                    record.rating_count,
                    record.created_at,
                    record.updated_at,
                    record.last_scraped_at,
                    record.publication_date,
                    record.novel_last_updated,
                    record.scraping_start_time,
                    record.scraping_end_time,
                    record.estimated_completion,
                    record.chapters_per_minute,
                    record.error_count,
                    record.last_error,
                    record.retry_count,
                    record.metadata_json,
                    record.markdown_file_size,
                    record.epub_file_size,
                    record.has_epub,
                    record.has_cover,
                    record.is_favorite,
                    record.is_archived,
                )
                # Expunge the record from session to make it independent
                session.expunge(record)
            return record

    def get_novel_by_directory(self, directory_path: str) -> Optional[NovelRecord]:
        """Get novel by directory path."""
        with self.get_session() as session:
            record = (
                session.query(NovelRecord)
                .filter_by(directory_path=directory_path)
                .first()
            )
            if record:
                # Eagerly load all attributes to avoid DetachedInstanceError
                _ = (
                    record.id,
                    record.title,
                    record.author,
                    record.source_url,
                    record.provider,
                    record.provider_id,
                    record.directory_path,
                    record.markdown_file_path,
                    record.epub_file_path,
                    record.cover_file_path,
                    record.description,
                    record.genres,
                    record.tags,
                    record.alternative_names,
                    record.novel_status,
                    record.scraping_status,
                    record.total_chapters,
                    record.completed_chapters,
                    record.last_chapter_scraped,
                    record.last_chapter_url,
                    record.word_count,
                    record.rating,
                    record.rating_count,
                    record.created_at,
                    record.updated_at,
                    record.last_scraped_at,
                    record.publication_date,
                    record.novel_last_updated,
                    record.scraping_start_time,
                    record.scraping_end_time,
                    record.estimated_completion,
                    record.chapters_per_minute,
                    record.error_count,
                    record.last_error,
                    record.retry_count,
                    record.metadata_json,
                    record.markdown_file_size,
                    record.epub_file_size,
                    record.has_epub,
                    record.has_cover,
                    record.is_favorite,
                    record.is_archived,
                )
                # Expunge the record from session to make it independent
                session.expunge(record)
            return record

    def update_novel(
        self,
        novel_id: int,
        metadata: Optional[NovelMetadata] = None,
        progress: Optional[ScrapingProgress] = None,
        **kwargs,
    ) -> Optional[NovelRecord]:
        """
        Update an existing novel record.

        Args:
            novel_id: Database ID of the novel
            metadata: Updated metadata (optional)
            progress: Updated scraping progress (optional)
            **kwargs: Additional fields to update

        Returns:
            Updated NovelRecord or None if not found
        """
        with self.get_session() as session:
            novel = session.query(NovelRecord).filter_by(id=novel_id).first()
            if not novel:
                return None

            # Update from metadata
            if metadata:
                novel.update_from_metadata(metadata)

            # Update from progress
            if progress:
                novel.update_from_progress(progress)

            # Update additional fields
            for key, value in kwargs.items():
                if hasattr(novel, key):
                    setattr(novel, key, value)

            novel.updated_at = datetime.now()

            logger.info(f"Updated novel record: {novel.title} (ID: {novel.id})")
            return novel

    def update_novel_by_url(
        self,
        source_url: str,
        metadata: Optional[NovelMetadata] = None,
        progress: Optional[ScrapingProgress] = None,
        **kwargs,
    ) -> Optional[NovelRecord]:
        """Update novel by source URL."""
        with self.get_session() as session:
            novel = session.query(NovelRecord).filter_by(source_url=source_url).first()
            if not novel:
                return None

            # Update from metadata
            if metadata:
                novel.update_from_metadata(metadata)

            # Update from progress
            if progress:
                novel.update_from_progress(progress)

            # Update additional fields
            for key, value in kwargs.items():
                if hasattr(novel, key):
                    setattr(novel, key, value)

            novel.updated_at = datetime.now()

            logger.info(f"Updated novel record: {novel.title} (ID: {novel.id})")
            return novel

    def delete_novel(self, novel_id: int) -> bool:
        """
        Delete a novel record.

        Args:
            novel_id: Database ID of the novel

        Returns:
            True if deleted, False if not found
        """
        with self.get_session() as session:
            novel = session.query(NovelRecord).filter_by(id=novel_id).first()
            if not novel:
                return False

            title = novel.title
            session.delete(novel)

            logger.info(f"Deleted novel record: {title} (ID: {novel_id})")
            return True

    def list_novels(
        self,
        status: Optional[Union[ScrapingStatus, List[ScrapingStatus]]] = None,
        novel_status: Optional[Union[NovelStatus, List[NovelStatus]]] = None,
        provider: Optional[str] = None,
        has_epub: Optional[bool] = None,
        is_favorite: Optional[bool] = None,
        is_archived: Optional[bool] = None,
        search_term: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        order_by: str = "updated_at",
        order_desc: bool = True,
    ) -> List[NovelRecord]:
        """
        List novels with filtering and pagination.

        Args:
            status: Filter by scraping status(es)
            novel_status: Filter by novel status(es)
            provider: Filter by provider
            has_epub: Filter by EPUB availability
            is_favorite: Filter by favorite status
            is_archived: Filter by archived status
            search_term: Search in title, author, or description
            limit: Maximum number of results
            offset: Number of results to skip
            order_by: Field to order by
            order_desc: Whether to order in descending order

        Returns:
            List of NovelRecord objects
        """
        with self.get_session() as session:
            query = session.query(NovelRecord)

            # Apply filters
            if status:
                if isinstance(status, list):
                    status_values = [s.value for s in status]
                    query = query.filter(NovelRecord.scraping_status.in_(status_values))
                else:
                    query = query.filter(NovelRecord.scraping_status == status.value)

            if novel_status:
                if isinstance(novel_status, list):
                    status_values = [s.value for s in novel_status]
                    query = query.filter(NovelRecord.novel_status.in_(status_values))
                else:
                    query = query.filter(NovelRecord.novel_status == novel_status.value)

            if provider:
                query = query.filter(NovelRecord.provider == provider)

            if has_epub is not None:
                query = query.filter(NovelRecord.has_epub == has_epub)

            if is_favorite is not None:
                query = query.filter(NovelRecord.is_favorite == is_favorite)

            if is_archived is not None:
                query = query.filter(NovelRecord.is_archived == is_archived)

            if search_term:
                search_pattern = f"%{search_term}%"
                query = query.filter(
                    or_(
                        NovelRecord.title.ilike(search_pattern),
                        NovelRecord.author.ilike(search_pattern),
                        NovelRecord.description.ilike(search_pattern),
                    )
                )

            # Apply ordering
            if hasattr(NovelRecord, order_by):
                order_column = getattr(NovelRecord, order_by)
                if order_desc:
                    query = query.order_by(desc(order_column))
                else:
                    query = query.order_by(asc(order_column))

            # Apply pagination
            if offset > 0:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)

            # Execute query and eagerly load all attributes to avoid DetachedInstanceError
            results = query.all()

            # Force loading of all attributes while session is still active
            for record in results:
                # Access all attributes to ensure they're loaded
                _ = (
                    record.id,
                    record.title,
                    record.author,
                    record.source_url,
                    record.provider,
                    record.provider_id,
                    record.directory_path,
                    record.markdown_file_path,
                    record.epub_file_path,
                    record.cover_file_path,
                    record.description,
                    record.genres,
                    record.tags,
                    record.alternative_names,
                    record.novel_status,
                    record.scraping_status,
                    record.total_chapters,
                    record.completed_chapters,
                    record.last_chapter_scraped,
                    record.last_chapter_url,
                    record.word_count,
                    record.rating,
                    record.rating_count,
                    record.created_at,
                    record.updated_at,
                    record.last_scraped_at,
                    record.publication_date,
                    record.novel_last_updated,
                    record.scraping_start_time,
                    record.scraping_end_time,
                    record.estimated_completion,
                    record.chapters_per_minute,
                    record.error_count,
                    record.last_error,
                    record.retry_count,
                    record.metadata_json,
                    record.markdown_file_size,
                    record.epub_file_size,
                    record.has_epub,
                    record.has_cover,
                    record.is_favorite,
                    record.is_archived,
                )

            # Expunge all objects from session to make them independent
            session.expunge_all()

            return results

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with various statistics
        """
        with self.get_session() as session:
            total_novels = session.query(NovelRecord).count()

            # Count by novel status (completion status)
            status_counts = {}
            # Get all unique novel statuses from the database
            novel_statuses = session.query(NovelRecord.novel_status).distinct().all()
            for (status,) in novel_statuses:
                if status:  # Skip None values
                    count = (
                        session.query(NovelRecord)
                        .filter_by(novel_status=status)
                        .count()
                    )
                    status_counts[status] = count

            # Also count by scraping status for additional info
            scraping_status_counts = {}
            for status in ScrapingStatus:
                count = (
                    session.query(NovelRecord)
                    .filter_by(scraping_status=status.value)
                    .count()
                )
                scraping_status_counts[status.value] = count

            # Count novels with EPUBs
            novels_with_epub = (
                session.query(NovelRecord).filter_by(has_epub=True).count()
            )

            # Count by provider
            provider_counts = (
                session.query(NovelRecord.provider, func.count(NovelRecord.id))
                .group_by(NovelRecord.provider)
                .all()
            )

            # Recent activity
            week_ago = datetime.now() - timedelta(days=7)
            recent_updates = (
                session.query(NovelRecord)
                .filter(NovelRecord.updated_at >= week_ago)
                .count()
            )

            return {
                "total_novels": total_novels,
                "status_counts": status_counts,  # Novel completion status
                "scraping_status_counts": scraping_status_counts,  # Scraping progress status
                "novels_with_epub": novels_with_epub,
                "epub_percentage": (
                    (novels_with_epub / total_novels * 100) if total_novels > 0 else 0
                ),
                "provider_counts": dict(provider_counts),
                "recent_updates": recent_updates,
                "last_updated": datetime.now().isoformat(),
            }

    def create_or_update_novel(
        self, metadata: NovelMetadata, directory_path: Optional[str] = None
    ) -> NovelRecord:
        """
        Create a new novel or update existing one based on URL.

        Args:
            metadata: Novel metadata
            directory_path: Path to the novel's directory

        Returns:
            Created or updated NovelRecord
        """
        existing = self.get_novel_by_url(metadata.source_url)
        if existing:
            return self.update_novel_by_url(
                metadata.source_url,
                metadata=metadata,
                directory_path=directory_path or existing.directory_path,
            )
        else:
            return self.create_novel(metadata, directory_path)

    def mark_scraping_started(self, source_url: str) -> Optional[NovelRecord]:
        """Mark a novel as having started scraping."""
        return self.update_novel_by_url(
            source_url,
            scraping_status=ScrapingStatus.IN_PROGRESS.value,
            scraping_start_time=datetime.now(),
        )

    def mark_scraping_completed(self, source_url: str) -> Optional[NovelRecord]:
        """Mark a novel as having completed scraping."""
        return self.update_novel_by_url(
            source_url,
            scraping_status=ScrapingStatus.COMPLETED.value,
            scraping_end_time=datetime.now(),
        )

    def mark_scraping_failed(
        self, source_url: str, error: str
    ) -> Optional[NovelRecord]:
        """Mark a novel as having failed scraping."""
        return self.update_novel_by_url(
            source_url,
            scraping_status=ScrapingStatus.FAILED.value,
            scraping_end_time=datetime.now(),
            last_error=error,
        )

    def update_file_paths(
        self,
        source_url: str,
        markdown_path: Optional[str] = None,
        epub_path: Optional[str] = None,
        cover_path: Optional[str] = None,
    ) -> Optional[NovelRecord]:
        """Update file paths for a novel."""
        updates = {}
        if markdown_path:
            updates["markdown_file_path"] = markdown_path
            # Update file size if file exists
            if os.path.exists(markdown_path):
                updates["markdown_file_size"] = os.path.getsize(markdown_path)

        if epub_path:
            updates["epub_file_path"] = epub_path
            updates["has_epub"] = True
            # Update file size if file exists
            if os.path.exists(epub_path):
                updates["epub_file_size"] = os.path.getsize(epub_path)

        if cover_path:
            updates["cover_file_path"] = cover_path
            updates["has_cover"] = True

        return self.update_novel_by_url(source_url, **updates)

    def get_novels_without_epub(self) -> List[NovelRecord]:
        """Get all novels that don't have EPUB files."""
        return self.list_novels(has_epub=False)

    def get_novels_by_status(self, status: ScrapingStatus) -> List[NovelRecord]:
        """Get novels by scraping status."""
        return self.list_novels(status=status)

    def search_novels(self, search_term: str, limit: int = 50) -> List[NovelRecord]:
        """Search novels by title, author, or description."""
        return self.list_novels(search_term=search_term, limit=limit)

    def cleanup_orphaned_records(self) -> int:
        """
        Remove records for novels whose directories no longer exist.

        Returns:
            Number of records cleaned up
        """
        cleaned_count = 0
        with self.get_session() as session:
            novels = (
                session.query(NovelRecord)
                .filter(NovelRecord.directory_path.isnot(None))
                .all()
            )

            for novel in novels:
                if novel.directory_path and not os.path.exists(novel.directory_path):
                    logger.info(
                        f"Cleaning up orphaned record: {novel.title} (directory not found: {novel.directory_path})"
                    )
                    session.delete(novel)
                    cleaned_count += 1

        return cleaned_count

    def sync_from_filesystem(
        self, base_directory: str, progress_callback=None
    ) -> Dict[str, int]:
        """
        Sync database with filesystem by scanning for novels.

        Args:
            base_directory: Base directory to scan for novels
            progress_callback: Optional callback function to report progress

        Returns:
            Dictionary with sync statistics
        """
        from .novel_discovery import NovelDiscoveryService

        if progress_callback:
            progress_callback("Initializing novel discovery...")

        discovery_service = NovelDiscoveryService(base_directory)

        if progress_callback:
            progress_callback("Scanning directories and reading markdown files...")

        # Force filesystem discovery to read actual files and get latest metadata
        discovered_novels = discovery_service._discover_novels_from_filesystem(
            Path(base_directory), progress_callback=progress_callback
        )

        stats = {
            "discovered": len(discovered_novels),
            "created": 0,
            "updated": 0,
            "errors": 0,
        }

        if progress_callback:
            progress_callback(
                f"Processing {len(discovered_novels)} discovered novels..."
            )

        for i, novel_info in enumerate(discovered_novels, 1):
            try:
                if progress_callback:
                    progress_callback(
                        f"Processing {i}/{len(discovered_novels)}: {novel_info.title}"
                    )

                # Check if we already have this novel in database
                existing = self.get_novel_by_directory(str(novel_info.directory))

                if existing:
                    # Update existing record with comprehensive metadata
                    update_data = {
                        "markdown_file_path": str(novel_info.markdown_file),
                        "epub_file_path": (
                            str(novel_info.epub_file) if novel_info.epub_file else None
                        ),
                        "cover_file_path": (
                            str(novel_info.cover_file)
                            if novel_info.cover_file
                            else None
                        ),
                        "markdown_file_size": novel_info.markdown_size,
                        "epub_file_size": novel_info.epub_size,
                        "has_epub": novel_info.has_epub,
                        "has_cover": novel_info.has_cover,
                        "total_chapters": novel_info.chapter_count,
                        "word_count": getattr(novel_info, "word_count", None),
                    }

                    # Update status if available from novel_info
                    if hasattr(novel_info, "status") and novel_info.status:
                        update_data["novel_status"] = novel_info.status

                    # Update description if available
                    if novel_info.description:
                        update_data["description"] = novel_info.description

                    # Update genres if available
                    if hasattr(novel_info, "genres") and novel_info.genres:
                        update_data["genres"] = novel_info.genres

                    self.update_novel(existing.id, **update_data)
                    stats["updated"] += 1
                else:
                    # Create basic metadata from discovered info
                    metadata = NovelMetadata(
                        title=novel_info.title,
                        author=novel_info.author,
                        description=novel_info.description or "",
                        source_url=f"file://{novel_info.directory}",  # Placeholder URL
                        chapter_count=novel_info.chapter_count,
                        word_count=getattr(novel_info, "word_count", None),
                    )

                    novel_record = self.create_novel(
                        metadata, str(novel_info.directory)
                    )

                    # Update file paths
                    self.update_file_paths(
                        novel_record.source_url,
                        markdown_path=str(novel_info.markdown_file),
                        epub_path=(
                            str(novel_info.epub_file) if novel_info.epub_file else None
                        ),
                        cover_path=(
                            str(novel_info.cover_file)
                            if novel_info.cover_file
                            else None
                        ),
                    )
                    stats["created"] += 1

            except Exception as e:
                logger.error(f"Error syncing novel {novel_info.title}: {e}")
                stats["errors"] += 1

        return stats

    def bulk_create_novels(
        self, novel_metadatas: List[Tuple[NovelMetadata, str]]
    ) -> List[NovelRecord]:
        """
        Create multiple novels in a single transaction for better performance.

        Args:
            novel_metadatas: List of (metadata, directory_path) tuples

        Returns:
            List of created NovelRecord objects
        """
        created_records = []

        with self.get_session() as session:
            try:
                for metadata, directory_path in novel_metadatas:
                    novel_record = NovelRecord(
                        title=metadata.title,
                        author=metadata.author,
                        source_url=metadata.source_url,
                        provider="Imported",  # Default for bulk imports
                        directory_path=directory_path,
                        description=metadata.description,
                        genres=metadata.genres,
                        tags=metadata.tags,
                        alternative_names=metadata.alternative_names,
                        novel_status=(
                            metadata.status
                            if isinstance(metadata.status, str)
                            else metadata.status.value if metadata.status else "unknown"
                        ),
                        total_chapters=metadata.chapter_count,
                        word_count=metadata.word_count,
                        rating=metadata.rating,
                        rating_count=metadata.rating_count,
                        publication_date=metadata.publication_date,
                        scraping_status=ScrapingStatus.NOT_STARTED.value,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    session.add(novel_record)
                    created_records.append(novel_record)

                # Commit all at once
                session.commit()

                # Refresh all records to get their IDs
                for record in created_records:
                    session.refresh(record)

                logger.info(f"Bulk created {len(created_records)} novel records")
                return created_records

            except Exception as e:
                session.rollback()
                logger.error(f"Error in bulk create: {e}")
                raise

    def bulk_update_novels(self, updates: List[Tuple[int, Dict[str, Any]]]) -> int:
        """
        Update multiple novels in a single transaction for better performance.

        Args:
            updates: List of (novel_id, update_dict) tuples

        Returns:
            Number of records updated
        """
        updated_count = 0

        with self.get_session() as session:
            try:
                for novel_id, update_data in updates:
                    # Add updated_at timestamp
                    update_data["updated_at"] = datetime.utcnow()

                    result = (
                        session.query(NovelRecord)
                        .filter_by(id=novel_id)
                        .update(update_data)
                    )
                    updated_count += result

                session.commit()
                logger.info(f"Bulk updated {updated_count} novel records")
                return updated_count

            except Exception as e:
                session.rollback()
                logger.error(f"Error in bulk update: {e}")
                raise

    def get_novels_by_ids(self, novel_ids: List[int]) -> List[NovelRecord]:
        """
        Get multiple novels by their IDs in a single query.

        Args:
            novel_ids: List of novel IDs

        Returns:
            List of NovelRecord objects
        """
        with self.get_session() as session:
            records = (
                session.query(NovelRecord).filter(NovelRecord.id.in_(novel_ids)).all()
            )

            # Eagerly load all attributes
            for record in records:
                _ = (
                    record.id,
                    record.title,
                    record.author,
                    record.source_url,
                    record.provider,
                    record.provider_id,
                    record.directory_path,
                    record.markdown_file_path,
                    record.epub_file_path,
                    record.cover_file_path,
                    record.description,
                    record.genres,
                    record.tags,
                    record.alternative_names,
                    record.novel_status,
                    record.scraping_status,
                    record.total_chapters,
                    record.completed_chapters,
                    record.last_chapter_scraped,
                    record.last_chapter_url,
                    record.word_count,
                    record.rating,
                    record.rating_count,
                    record.created_at,
                    record.updated_at,
                    record.last_scraped_at,
                    record.publication_date,
                    record.novel_last_updated,
                    record.scraping_start_time,
                    record.scraping_end_time,
                    record.estimated_completion,
                    record.chapters_per_minute,
                    record.error_count,
                    record.last_error,
                    record.retry_count,
                    record.metadata_json,
                    record.markdown_file_size,
                    record.epub_file_size,
                    record.has_epub,
                    record.has_cover,
                    record.is_favorite,
                    record.is_archived,
                )

            # Expunge all objects from session
            session.expunge_all()
            return records

    def cleanup_old_records(self, days_old: int = 365) -> int:
        """
        Clean up old records that haven't been updated in specified days.

        Args:
            days_old: Number of days since last update to consider record old

        Returns:
            Number of records cleaned up
        """
        cleaned_count = 0
        cutoff_date = datetime.now() - timedelta(days=days_old)

        with self.get_session() as session:
            # Find old records that haven't been updated and don't have EPUBs
            old_records = (
                session.query(NovelRecord)
                .filter(
                    and_(
                        NovelRecord.updated_at < cutoff_date,
                        NovelRecord.has_epub == False,
                        NovelRecord.scraping_status.in_(["failed", "not_started"]),
                    )
                )
                .all()
            )

            for record in old_records:
                # Verify directory doesn't exist before deleting
                if record.directory_path and not os.path.exists(record.directory_path):
                    logger.info(
                        f"Cleaning up old record: {record.title} (last updated: {record.updated_at})"
                    )
                    session.delete(record)
                    cleaned_count += 1

        return cleaned_count

    def optimize_database(self) -> bool:
        """
        Optimize database performance by running maintenance commands.

        Returns:
            True if optimization was successful
        """
        try:
            with self.get_session() as session:
                # For SQLite, run VACUUM and ANALYZE
                if self.db_manager.database_url.startswith("sqlite"):
                    session.execute("VACUUM")
                    session.execute("ANALYZE")
                    session.commit()
                    logger.info("Database optimization completed")
                    return True
            return False
        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            return False

    def get_database_size(self) -> int:
        """
        Get the size of the database file in bytes.

        Returns:
            Database file size in bytes, or 0 if unable to determine
        """
        try:
            if self.db_manager.database_url.startswith("sqlite"):
                db_path = self.db_manager.database_url.replace("sqlite:///", "")
                if os.path.exists(db_path):
                    return os.path.getsize(db_path)
            return 0
        except Exception:
            return 0

    def close(self) -> None:
        """Close the database connection."""
        try:
            logger.debug("Closing database connection")
            self.db_manager.close()
            logger.info("Database connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")
            # Don't raise here as this is cleanup code

    def test_connection(self) -> bool:
        """
        Test database connection and return True if successful.

        Returns:
            True if connection is working, False otherwise
        """
        try:
            with self.get_session() as session:
                # Simple query to test connection
                from sqlalchemy import text

                session.execute(text("SELECT 1")).fetchone()
            logger.debug("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

    def get_database_info(self) -> Dict[str, Any]:
        """
        Get database information and statistics.

        Returns:
            Dictionary with database information
        """
        try:
            with self.get_session() as session:
                # Get table count
                novel_count = session.query(NovelRecord).count()

                # Get database file size if SQLite
                db_size = None
                if self.db_manager.database_url.startswith("sqlite"):
                    db_path = self.db_manager.database_url.replace("sqlite:///", "")
                    if os.path.exists(db_path):
                        db_size = os.path.getsize(db_path)

                return {
                    "database_url": self.db_manager.database_url,
                    "novel_count": novel_count,
                    "database_size_bytes": db_size,
                    "connection_working": True,
                }
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {
                "database_url": getattr(self.db_manager, "database_url", "Unknown"),
                "novel_count": 0,
                "database_size_bytes": None,
                "connection_working": False,
                "error": str(e),
            }
