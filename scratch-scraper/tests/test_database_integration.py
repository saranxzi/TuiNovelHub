"""
Tests for database integration functionality.

This module tests the database models, service layer, and integration
with the scraping system.
"""

import os
import tempfile
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from wn_dl.core.database_models import DatabaseManager, NovelRecord
from wn_dl.core.novel_database_service import NovelDatabaseService
from wn_dl.core.models import NovelMetadata, NovelStatus, ScrapingStatus


@pytest.fixture
def temp_db_path():
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def db_service(temp_db_path):
    """Create a database service instance for testing."""
    service = NovelDatabaseService(temp_db_path)
    yield service
    service.close()


@pytest.fixture
def sample_metadata():
    """Create sample novel metadata for testing."""
    return NovelMetadata(
        title="Test Novel",
        author="Test Author",
        description="A test novel for database testing",
        source_url="https://example.com/novel/test",
        cover_url="https://example.com/cover.jpg",
        genres=["Fantasy", "Adventure"],
        tags=["Magic", "Dragons"],
        status=NovelStatus.ONGOING,
        chapter_count=100,
        word_count=250000,
        provider="TestProvider",
        provider_id="test123"
    )


class TestDatabaseManager:
    """Test the DatabaseManager class."""
    
    def test_database_creation(self, temp_db_path):
        """Test database and table creation."""
        db_manager = DatabaseManager(f"sqlite:///{temp_db_path}")
        db_manager.create_tables()
        
        # Verify database file exists
        assert os.path.exists(temp_db_path)
        
        # Verify we can get a session
        session = db_manager.get_session()
        assert session is not None
        session.close()
        
        db_manager.close()
    
    def test_backup_restore(self, temp_db_path):
        """Test database backup and restore functionality."""
        db_manager = DatabaseManager(f"sqlite:///{temp_db_path}")
        db_manager.create_tables()
        
        # Create backup
        backup_path = temp_db_path + ".backup"
        success = db_manager.backup_database(backup_path)
        assert success
        assert os.path.exists(backup_path)
        
        # Restore backup
        success = db_manager.restore_database(backup_path)
        assert success
        
        # Cleanup
        os.unlink(backup_path)
        db_manager.close()


class TestNovelDatabaseService:
    """Test the NovelDatabaseService class."""
    
    def test_create_novel(self, db_service, sample_metadata):
        """Test creating a novel record."""
        novel_record = db_service.create_novel(sample_metadata, "/test/directory")
        
        assert novel_record.id is not None
        assert novel_record.title == sample_metadata.title
        assert novel_record.author == sample_metadata.author
        assert novel_record.source_url == sample_metadata.source_url
        assert novel_record.directory_path == "/test/directory"
    
    def test_create_duplicate_novel(self, db_service, sample_metadata):
        """Test that creating duplicate novels raises an error."""
        # Create first novel
        db_service.create_novel(sample_metadata, "/test/directory")
        
        # Attempt to create duplicate should raise ValueError
        with pytest.raises(ValueError, match="already exists"):
            db_service.create_novel(sample_metadata, "/test/directory2")
    
    def test_get_novel_by_url(self, db_service, sample_metadata):
        """Test retrieving a novel by URL."""
        # Create novel
        created_novel = db_service.create_novel(sample_metadata, "/test/directory")
        
        # Retrieve by URL
        retrieved_novel = db_service.get_novel_by_url(sample_metadata.source_url)
        
        assert retrieved_novel is not None
        assert retrieved_novel.id == created_novel.id
        assert retrieved_novel.title == sample_metadata.title
    
    def test_update_novel(self, db_service, sample_metadata):
        """Test updating a novel record."""
        # Create novel
        novel_record = db_service.create_novel(sample_metadata, "/test/directory")
        
        # Update metadata
        updated_metadata = sample_metadata
        updated_metadata.title = "Updated Test Novel"
        updated_metadata.chapter_count = 150
        
        # Update novel
        updated_record = db_service.update_novel(
            novel_record.id, 
            metadata=updated_metadata
        )
        
        assert updated_record is not None
        assert updated_record.title == "Updated Test Novel"
        assert updated_record.total_chapters == 150
    
    def test_list_novels_with_filters(self, db_service, sample_metadata):
        """Test listing novels with various filters."""
        # Create multiple novels
        novel1 = db_service.create_novel(sample_metadata, "/test/directory1")
        
        sample_metadata2 = sample_metadata
        sample_metadata2.source_url = "https://example.com/novel/test2"
        sample_metadata2.title = "Test Novel 2"
        sample_metadata2.provider = "AnotherProvider"
        novel2 = db_service.create_novel(sample_metadata2, "/test/directory2")
        
        # Mark one as completed
        db_service.mark_scraping_completed(sample_metadata.source_url)
        
        # Test filtering by status
        completed_novels = db_service.list_novels(status=ScrapingStatus.COMPLETED)
        assert len(completed_novels) == 1
        assert completed_novels[0].id == novel1.id
        
        # Test filtering by provider
        provider_novels = db_service.list_novels(provider="TestProvider")
        assert len(provider_novels) == 1
        assert provider_novels[0].id == novel1.id
        
        # Test search
        search_results = db_service.search_novels("Test Novel 2")
        assert len(search_results) == 1
        assert search_results[0].id == novel2.id
    
    def test_status_tracking(self, db_service, sample_metadata):
        """Test novel status tracking functionality."""
        # Create novel
        novel_record = db_service.create_novel(sample_metadata, "/test/directory")
        
        # Test marking as started
        updated_record = db_service.mark_scraping_started(sample_metadata.source_url)
        assert updated_record.scraping_status == ScrapingStatus.IN_PROGRESS.value
        assert updated_record.scraping_start_time is not None
        
        # Test marking as completed
        updated_record = db_service.mark_scraping_completed(sample_metadata.source_url)
        assert updated_record.scraping_status == ScrapingStatus.COMPLETED.value
        assert updated_record.scraping_end_time is not None
        
        # Test marking as failed
        updated_record = db_service.mark_scraping_failed(sample_metadata.source_url, "Test error")
        assert updated_record.scraping_status == ScrapingStatus.FAILED.value
        assert updated_record.last_error == "Test error"
    
    def test_file_path_updates(self, db_service, sample_metadata):
        """Test updating file paths for a novel."""
        # Create novel
        novel_record = db_service.create_novel(sample_metadata, "/test/directory")
        
        # Update file paths
        updated_record = db_service.update_file_paths(
            sample_metadata.source_url,
            markdown_path="/test/novel.md",
            epub_path="/test/novel.epub",
            cover_path="/test/cover.jpg"
        )
        
        assert updated_record.markdown_file_path == "/test/novel.md"
        assert updated_record.epub_file_path == "/test/novel.epub"
        assert updated_record.cover_file_path == "/test/cover.jpg"
        assert updated_record.has_epub is True
        assert updated_record.has_cover is True
    
    def test_statistics(self, db_service, sample_metadata):
        """Test database statistics functionality."""
        # Create some test data
        novel1 = db_service.create_novel(sample_metadata, "/test/directory1")
        
        sample_metadata2 = sample_metadata
        sample_metadata2.source_url = "https://example.com/novel/test2"
        sample_metadata2.title = "Test Novel 2"
        novel2 = db_service.create_novel(sample_metadata2, "/test/directory2")
        
        # Mark one as completed with EPUB
        db_service.mark_scraping_completed(sample_metadata.source_url)
        db_service.update_file_paths(sample_metadata.source_url, epub_path="/test/novel.epub")
        
        # Get statistics
        stats = db_service.get_statistics()
        
        assert stats["total_novels"] == 2
        assert stats["novels_with_epub"] == 1
        assert stats["epub_percentage"] == 50.0
        assert "status_counts" in stats
        assert "provider_counts" in stats
    
    def test_cleanup_orphaned_records(self, db_service, sample_metadata):
        """Test cleanup of orphaned records."""
        # Create novel with non-existent directory
        novel_record = db_service.create_novel(sample_metadata, "/nonexistent/directory")
        
        # Run cleanup
        cleaned_count = db_service.cleanup_orphaned_records()
        
        # Should have cleaned up the orphaned record
        assert cleaned_count == 1
        
        # Verify record is gone
        retrieved_novel = db_service.get_novel_by_url(sample_metadata.source_url)
        assert retrieved_novel is None


class TestDatabaseIntegration:
    """Test integration with other components."""
    
    def test_create_or_update_novel(self, db_service, sample_metadata):
        """Test create or update functionality."""
        # First call should create
        novel_record = db_service.create_or_update_novel(sample_metadata, "/test/directory")
        original_id = novel_record.id
        
        # Second call should update
        updated_metadata = sample_metadata
        updated_metadata.title = "Updated Title"
        
        updated_record = db_service.create_or_update_novel(updated_metadata, "/test/directory")
        
        # Should be same record, just updated
        assert updated_record.id == original_id
        assert updated_record.title == "Updated Title"
    
    def test_database_performance(self, db_service):
        """Test database performance with multiple records."""
        # Create multiple novels to test performance
        novels_count = 100
        
        for i in range(novels_count):
            metadata = NovelMetadata(
                title=f"Test Novel {i}",
                author=f"Author {i}",
                description=f"Description {i}",
                source_url=f"https://example.com/novel/{i}",
                provider="TestProvider"
            )
            db_service.create_novel(metadata, f"/test/directory{i}")
        
        # Test listing performance
        start_time = datetime.now()
        novels = db_service.list_novels(limit=50)
        end_time = datetime.now()
        
        assert len(novels) == 50
        # Should complete within reasonable time (adjust as needed)
        assert (end_time - start_time).total_seconds() < 1.0
        
        # Test search performance
        start_time = datetime.now()
        search_results = db_service.search_novels("Test Novel 5")
        end_time = datetime.now()
        
        assert len(search_results) >= 1
        assert (end_time - start_time).total_seconds() < 1.0


if __name__ == "__main__":
    pytest.main([__file__])
