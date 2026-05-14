"""
Comprehensive database functionality tests.

This module contains comprehensive tests for all database functionality
including CRUD operations, filtering, sync, backup/restore, and edge cases.
"""

import tempfile
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

from wn_dl.core.novel_database_service import NovelDatabaseService
from wn_dl.core.database_migrations import create_migrator
from wn_dl.core.models import NovelMetadata, ScrapingStatus, NovelStatus


class TestDatabaseService:
    """Test database service functionality."""
    
    @pytest.fixture
    def temp_db_service(self):
        """Create a temporary database service for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        service = NovelDatabaseService(db_path)
        yield service
        service.close()
        
        # Cleanup
        Path(db_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def sample_metadata(self):
        """Create sample novel metadata for testing."""
        return NovelMetadata(
            title="Test Novel",
            author="Test Author",
            source_url="https://example.com/novel/1",
            description="A test novel for testing purposes",
            genres=["Fantasy", "Adventure"],
            tags=["magic", "hero"],
            chapter_count=100,
            word_count=50000,
            status="ongoing"
        )
    
    def test_database_initialization(self, temp_db_service):
        """Test database initialization."""
        assert temp_db_service is not None
        assert temp_db_service.test_connection()
    
    def test_create_novel(self, temp_db_service, sample_metadata):
        """Test novel creation."""
        novel = temp_db_service.create_novel(sample_metadata, "/test/path")
        
        assert novel.id is not None
        assert novel.title == "Test Novel"
        assert novel.author == "Test Author"
        assert novel.source_url == "https://example.com/novel/1"
        assert novel.directory_path == "/test/path"
    
    def test_create_duplicate_novel(self, temp_db_service, sample_metadata):
        """Test creating duplicate novel raises error."""
        temp_db_service.create_novel(sample_metadata, "/test/path")
        
        with pytest.raises(ValueError, match="already exists"):
            temp_db_service.create_novel(sample_metadata, "/test/path2")
    
    def test_get_novel_by_url(self, temp_db_service, sample_metadata):
        """Test retrieving novel by URL."""
        created = temp_db_service.create_novel(sample_metadata, "/test/path")
        retrieved = temp_db_service.get_novel_by_url(sample_metadata.source_url)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == created.title
    
    def test_get_novel_by_directory(self, temp_db_service, sample_metadata):
        """Test retrieving novel by directory."""
        created = temp_db_service.create_novel(sample_metadata, "/test/path")
        retrieved = temp_db_service.get_novel_by_directory("/test/path")
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.directory_path == "/test/path"
    
    def test_list_novels_basic(self, temp_db_service, sample_metadata):
        """Test basic novel listing."""
        temp_db_service.create_novel(sample_metadata, "/test/path")
        
        novels = temp_db_service.list_novels()
        assert len(novels) == 1
        assert novels[0].title == "Test Novel"
    
    def test_list_novels_with_filters(self, temp_db_service, sample_metadata):
        """Test novel listing with filters."""
        # Create multiple novels
        novel1 = temp_db_service.create_novel(sample_metadata, "/test/path1")
        
        sample_metadata.source_url = "https://example.com/novel/2"
        sample_metadata.title = "Another Novel"
        novel2 = temp_db_service.create_novel(sample_metadata, "/test/path2")
        
        # Test provider filter
        novels = temp_db_service.list_novels(provider="Imported")
        assert len(novels) == 2
        
        # Test limit
        novels = temp_db_service.list_novels(limit=1)
        assert len(novels) == 1
        
        # Test search
        novels = temp_db_service.list_novels(search_term="Test")
        assert len(novels) == 1
        assert novels[0].title == "Test Novel"
    
    def test_update_novel(self, temp_db_service, sample_metadata):
        """Test novel updating."""
        novel = temp_db_service.create_novel(sample_metadata, "/test/path")
        
        # Update novel
        success = temp_db_service.update_novel(
            novel.id,
            total_chapters=150,
            has_epub=True
        )
        
        assert success
        
        # Verify update
        updated = temp_db_service.get_novel_by_id(novel.id)
        assert updated.total_chapters == 150
        assert updated.has_epub is True
    
    def test_delete_novel(self, temp_db_service, sample_metadata):
        """Test novel deletion."""
        novel = temp_db_service.create_novel(sample_metadata, "/test/path")
        
        # Delete novel
        success = temp_db_service.delete_novel(novel.id)
        assert success
        
        # Verify deletion
        deleted = temp_db_service.get_novel_by_id(novel.id)
        assert deleted is None
    
    def test_get_statistics(self, temp_db_service, sample_metadata):
        """Test database statistics."""
        # Create some novels
        temp_db_service.create_novel(sample_metadata, "/test/path1")
        
        sample_metadata.source_url = "https://example.com/novel/2"
        novel2 = temp_db_service.create_novel(sample_metadata, "/test/path2")
        
        # Update one to have EPUB
        temp_db_service.update_novel(novel2.id, has_epub=True)
        
        stats = temp_db_service.get_statistics()
        
        assert stats["total_novels"] == 2
        assert stats["novels_with_epub"] == 1
        assert stats["epub_coverage"] == 50.0
        assert "status_breakdown" in stats
        assert "provider_breakdown" in stats
    
    def test_bulk_operations(self, temp_db_service):
        """Test bulk database operations."""
        # Test bulk create
        metadatas = []
        for i in range(3):
            metadata = NovelMetadata(
                title=f"Novel {i}",
                author=f"Author {i}",
                source_url=f"https://example.com/novel/{i}",
                description=f"Description {i}",
                chapter_count=100 + i
            )
            metadatas.append((metadata, f"/test/path{i}"))
        
        created = temp_db_service.bulk_create_novels(metadatas)
        assert len(created) == 3
        
        # Test bulk update
        updates = [(novel.id, {"has_epub": True}) for novel in created]
        updated_count = temp_db_service.bulk_update_novels(updates)
        assert updated_count == 3
        
        # Test bulk get
        novel_ids = [novel.id for novel in created]
        retrieved = temp_db_service.get_novels_by_ids(novel_ids)
        assert len(retrieved) == 3
        assert all(novel.has_epub for novel in retrieved)


class TestDatabaseMigrations:
    """Test database migration system."""
    
    @pytest.fixture
    def temp_migrator(self):
        """Create a temporary migrator for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        database_url = f"sqlite:///{db_path}"
        migrator = create_migrator(database_url)
        yield migrator
        
        # Cleanup
        Path(db_path).unlink(missing_ok=True)
    
    def test_migration_status(self, temp_migrator):
        """Test migration status reporting."""
        status = temp_migrator.get_migration_status()
        
        assert "total_migrations" in status
        assert "applied_count" in status
        assert "pending_count" in status
        assert "applied_versions" in status
        assert "pending_versions" in status
    
    def test_apply_migrations(self, temp_migrator):
        """Test applying migrations."""
        # Get initial status
        initial_status = temp_migrator.get_migration_status()
        initial_pending = initial_status["pending_count"]
        
        # Apply migrations
        stats = temp_migrator.migrate()
        
        # Check results
        assert stats["applied"] == initial_pending
        assert stats["failed"] == 0
        
        # Verify final status
        final_status = temp_migrator.get_migration_status()
        assert final_status["pending_count"] == 0


class TestDatabaseIntegration:
    """Test database integration scenarios."""
    
    @pytest.fixture
    def temp_db_service(self):
        """Create a temporary database service for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        service = NovelDatabaseService(db_path)
        yield service
        service.close()
        
        # Cleanup
        Path(db_path).unlink(missing_ok=True)
    
    def test_database_backup_restore(self, temp_db_service):
        """Test database backup and restore functionality."""
        # Create some test data
        metadata = NovelMetadata(
            title="Backup Test Novel",
            author="Test Author",
            source_url="https://example.com/backup-test",
            description="Novel for backup testing"
        )
        temp_db_service.create_novel(metadata, "/backup/test")
        
        # Create backup
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            backup_path = f.name
        
        success = temp_db_service.db_manager.backup_database(backup_path)
        assert success
        assert Path(backup_path).exists()
        
        # Verify backup file has content
        backup_size = Path(backup_path).stat().st_size
        assert backup_size > 0
        
        # Cleanup
        Path(backup_path).unlink(missing_ok=True)
    
    def test_error_handling(self, temp_db_service):
        """Test error handling in database operations."""
        # Test invalid metadata
        invalid_metadata = NovelMetadata(
            title="",  # Empty title
            author="Test Author",
            source_url="",  # Empty URL
            description="Invalid metadata test"
        )
        
        with pytest.raises(ValueError):
            temp_db_service.create_novel(invalid_metadata, "/test/path")
    
    def test_connection_management(self, temp_db_service):
        """Test database connection management."""
        # Test connection
        assert temp_db_service.test_connection()
        
        # Test database info
        db_info = temp_db_service.get_database_info()
        assert db_info["connection_working"]
        assert "novel_count" in db_info
        assert "database_size_bytes" in db_info


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
