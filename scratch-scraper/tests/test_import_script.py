"""
Tests for the import existing novels script.

This module tests the functionality of importing existing novels
from filesystem to database.
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add the scripts directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from import_existing_novels import (
    import_novels_from_directory,
    create_metadata_from_novel_info,
    extract_metadata_from_markdown,
    parse_novel_status
)

from wn_dl.core.database_models import DatabaseManager, NovelRecord
from wn_dl.core.novel_database_service import NovelDatabaseService
from wn_dl.core.models import NovelStatus


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
def temp_novels_dir():
    """Create a temporary directory structure with test novels."""
    with tempfile.TemporaryDirectory() as temp_dir:
        novels_dir = Path(temp_dir)
        
        # Create test novel 1
        novel1_dir = novels_dir / "Test Novel 1"
        novel1_dir.mkdir()
        
        # Create markdown file with YAML frontmatter
        markdown_content = """---
title: "Test Novel 1"
author: "Test Author 1"
description: "A test novel for import testing"
source_url: "https://example.com/novel1"
provider: "TestProvider"
status: "completed"
genres: ["Fantasy", "Adventure"]
tags: ["Magic", "Dragons"]
---

# Test Novel 1

## Chapter 1

This is test content for chapter 1.

## Chapter 2

This is test content for chapter 2.
"""
        (novel1_dir / "Test Novel 1.md").write_text(markdown_content, encoding='utf-8')
        (novel1_dir / "Test Novel 1.epub").write_text("fake epub content", encoding='utf-8')
        (novel1_dir / "cover.jpg").write_text("fake image content", encoding='utf-8')
        
        # Create test novel 2 (without YAML frontmatter)
        novel2_dir = novels_dir / "Test Novel 2"
        novel2_dir.mkdir()
        
        simple_markdown = """# Test Novel 2

## Chapter 1

Simple novel without metadata.
"""
        (novel2_dir / "Test Novel 2.md").write_text(simple_markdown, encoding='utf-8')
        
        # Create test novel 3 (only EPUB)
        novel3_dir = novels_dir / "Test Novel 3"
        novel3_dir.mkdir()
        (novel3_dir / "Test Novel 3.epub").write_text("fake epub content", encoding='utf-8')
        
        yield novels_dir


class TestImportScript:
    """Test the import script functionality."""
    
    def test_parse_novel_status(self):
        """Test novel status parsing."""
        assert parse_novel_status("completed") == NovelStatus.COMPLETED
        assert parse_novel_status("COMPLETED") == NovelStatus.COMPLETED
        assert parse_novel_status("finished") == NovelStatus.COMPLETED
        
        assert parse_novel_status("ongoing") == NovelStatus.ONGOING
        assert parse_novel_status("in progress") == NovelStatus.ONGOING
        assert parse_novel_status("updating") == NovelStatus.ONGOING
        
        assert parse_novel_status("hiatus") == NovelStatus.HIATUS
        assert parse_novel_status("paused") == NovelStatus.HIATUS
        
        assert parse_novel_status("dropped") == NovelStatus.DROPPED
        assert parse_novel_status("cancelled") == NovelStatus.DROPPED
        
        assert parse_novel_status("unknown") == NovelStatus.UNKNOWN
        assert parse_novel_status("") == NovelStatus.UNKNOWN
        assert parse_novel_status(None) == NovelStatus.UNKNOWN
    
    def test_extract_metadata_from_markdown(self, temp_novels_dir):
        """Test metadata extraction from markdown files."""
        # Test with YAML frontmatter
        novel1_md = temp_novels_dir / "Test Novel 1" / "Test Novel 1.md"
        metadata = extract_metadata_from_markdown(novel1_md)
        
        assert metadata["title"] == "Test Novel 1"
        assert metadata["author"] == "Test Author 1"
        assert metadata["source_url"] == "https://example.com/novel1"
        assert metadata["provider"] == "TestProvider"
        assert metadata["status"] == "completed"
        assert metadata["genres"] == ["Fantasy", "Adventure"]
        assert metadata["tags"] == ["Magic", "Dragons"]
        
        # Test without YAML frontmatter
        novel2_md = temp_novels_dir / "Test Novel 2" / "Test Novel 2.md"
        metadata = extract_metadata_from_markdown(novel2_md)
        assert metadata == {}
        
        # Test with non-existent file
        metadata = extract_metadata_from_markdown(Path("/nonexistent/file.md"))
        assert metadata == {}
    
    def test_create_metadata_from_novel_info(self, temp_novels_dir):
        """Test creating metadata from novel info."""
        from wn_dl.core.novel_discovery import NovelDiscoveryService
        
        # Mock novel info
        class MockNovelInfo:
            def __init__(self, title, author, directory, markdown_file=None):
                self.title = title
                self.author = author
                self.directory = directory
                self.markdown_file = markdown_file
                self.description = "Test description"
                self.status = "ongoing"
                self.chapter_count = 10
                self.word_count = 50000
                self.created_at = None
        
        # Test with YAML frontmatter
        novel1_dir = temp_novels_dir / "Test Novel 1"
        novel1_md = novel1_dir / "Test Novel 1.md"
        novel_info = MockNovelInfo("Test Novel 1", "Test Author 1", novel1_dir, novel1_md)
        
        metadata = create_metadata_from_novel_info(novel_info)
        
        assert metadata.title == "Test Novel 1"
        assert metadata.author == "Test Author 1"
        assert metadata.source_url == "https://example.com/novel1"
        assert metadata.provider == "TestProvider"
        assert metadata.status == NovelStatus.COMPLETED
        assert metadata.genres == ["Fantasy", "Adventure"]
        assert metadata.tags == ["Magic", "Dragons"]
        
        # Test without YAML frontmatter
        novel2_dir = temp_novels_dir / "Test Novel 2"
        novel2_md = novel2_dir / "Test Novel 2.md"
        novel_info = MockNovelInfo("Test Novel 2", "Test Author 2", novel2_dir, novel2_md)
        
        metadata = create_metadata_from_novel_info(novel_info)
        
        assert metadata.title == "Test Novel 2"
        assert metadata.author == "Test Author 2"
        assert metadata.source_url == f"file://{novel2_dir}"
        assert metadata.provider == "Unknown"
        assert metadata.status == NovelStatus.ONGOING
    
    @patch('import_existing_novels.NovelDiscoveryService')
    def test_import_novels_dry_run(self, mock_discovery_service, db_service):
        """Test import in dry run mode."""
        # Mock discovery service
        mock_novel_info = MagicMock()
        mock_novel_info.title = "Test Novel"
        mock_novel_info.author = "Test Author"
        mock_novel_info.directory = Path("/test/novel")
        mock_novel_info.markdown_file = None
        mock_novel_info.epub_file = None
        mock_novel_info.cover_file = None
        mock_novel_info.description = "Test description"
        mock_novel_info.status = "ongoing"
        mock_novel_info.chapter_count = 10
        mock_novel_info.has_epub = False
        mock_novel_info.has_cover = False
        mock_novel_info.markdown_size = 1000
        mock_novel_info.epub_size = None
        mock_novel_info.created_at = None
        
        mock_discovery_instance = mock_discovery_service.return_value
        mock_discovery_instance._discover_novels_from_filesystem.return_value = [mock_novel_info]
        
        # Run import in dry run mode
        stats = import_novels_from_directory(
            Path("/test/directory"),
            db_service,
            dry_run=True
        )
        
        assert stats["scanned"] == 1
        assert stats["imported"] == 1
        assert stats["updated"] == 0
        assert stats["skipped"] == 0
        assert stats["errors"] == 0
        
        # Verify no records were actually created
        novels = db_service.list_novels()
        assert len(novels) == 0
    
    @patch('import_existing_novels.NovelDiscoveryService')
    def test_import_novels_real(self, mock_discovery_service, db_service):
        """Test actual import of novels."""
        # Mock discovery service
        mock_novel_info = MagicMock()
        mock_novel_info.title = "Test Novel"
        mock_novel_info.author = "Test Author"
        mock_novel_info.directory = Path("/test/novel")
        mock_novel_info.markdown_file = None
        mock_novel_info.epub_file = None
        mock_novel_info.cover_file = None
        mock_novel_info.description = "Test description"
        mock_novel_info.status = "ongoing"
        mock_novel_info.chapter_count = 10
        mock_novel_info.has_epub = False
        mock_novel_info.has_cover = False
        mock_novel_info.markdown_size = 1000
        mock_novel_info.epub_size = None
        mock_novel_info.created_at = None
        
        mock_discovery_instance = mock_discovery_service.return_value
        mock_discovery_instance._discover_novels_from_filesystem.return_value = [mock_novel_info]
        
        # Run actual import
        stats = import_novels_from_directory(
            Path("/test/directory"),
            db_service,
            dry_run=False
        )
        
        assert stats["scanned"] == 1
        assert stats["imported"] == 1
        assert stats["updated"] == 0
        assert stats["skipped"] == 0
        assert stats["errors"] == 0
        
        # Verify record was created
        novels = db_service.list_novels()
        assert len(novels) == 1
        assert novels[0].title == "Test Novel"
        assert novels[0].author == "Test Author"
    
    @patch('import_existing_novels.NovelDiscoveryService')
    def test_import_novels_skip_existing(self, mock_discovery_service, db_service):
        """Test skipping existing novels."""
        # Create existing novel in database
        from wn_dl.core.models import NovelMetadata
        existing_metadata = NovelMetadata(
            title="Existing Novel",
            author="Existing Author",
            description="Existing description",
            source_url="https://example.com/existing"
        )
        db_service.create_novel(existing_metadata, "/test/existing")
        
        # Mock discovery service to return novel with same directory
        mock_novel_info = MagicMock()
        mock_novel_info.title = "Existing Novel"
        mock_novel_info.author = "Existing Author"
        mock_novel_info.directory = Path("/test/existing")
        mock_novel_info.markdown_file = None
        mock_novel_info.epub_file = None
        mock_novel_info.cover_file = None
        mock_novel_info.description = "Existing description"
        mock_novel_info.status = "ongoing"
        mock_novel_info.chapter_count = 10
        mock_novel_info.has_epub = False
        mock_novel_info.has_cover = False
        mock_novel_info.markdown_size = 1000
        mock_novel_info.epub_size = None
        mock_novel_info.created_at = None
        
        mock_discovery_instance = mock_discovery_service.return_value
        mock_discovery_instance._discover_novels_from_filesystem.return_value = [mock_novel_info]
        
        # Run import
        stats = import_novels_from_directory(
            Path("/test/directory"),
            db_service,
            dry_run=False,
            force_update=False
        )
        
        assert stats["scanned"] == 1
        assert stats["imported"] == 0
        assert stats["updated"] == 0
        assert stats["skipped"] == 1
        assert stats["errors"] == 0
        
        # Verify still only one record
        novels = db_service.list_novels()
        assert len(novels) == 1
    
    @patch('import_existing_novels.NovelDiscoveryService')
    def test_import_novels_force_update(self, mock_discovery_service, db_service):
        """Test force updating existing novels."""
        # Create existing novel in database
        from wn_dl.core.models import NovelMetadata
        existing_metadata = NovelMetadata(
            title="Existing Novel",
            author="Existing Author",
            description="Old description",
            source_url="https://example.com/existing"
        )
        db_service.create_novel(existing_metadata, "/test/existing")
        
        # Mock discovery service to return updated novel info
        mock_novel_info = MagicMock()
        mock_novel_info.title = "Existing Novel"
        mock_novel_info.author = "Existing Author"
        mock_novel_info.directory = Path("/test/existing")
        mock_novel_info.markdown_file = None
        mock_novel_info.epub_file = None
        mock_novel_info.cover_file = None
        mock_novel_info.description = "Updated description"
        mock_novel_info.status = "completed"
        mock_novel_info.chapter_count = 20
        mock_novel_info.has_epub = True
        mock_novel_info.has_cover = False
        mock_novel_info.markdown_size = 2000
        mock_novel_info.epub_size = 1500
        mock_novel_info.created_at = None
        
        mock_discovery_instance = mock_discovery_service.return_value
        mock_discovery_instance._discover_novels_from_filesystem.return_value = [mock_novel_info]
        
        # Run import with force update
        stats = import_novels_from_directory(
            Path("/test/directory"),
            db_service,
            dry_run=False,
            force_update=True
        )
        
        assert stats["scanned"] == 1
        assert stats["imported"] == 0
        assert stats["updated"] == 1
        assert stats["skipped"] == 0
        assert stats["errors"] == 0
        
        # Verify record was updated
        novels = db_service.list_novels()
        assert len(novels) == 1
        assert novels[0].total_chapters == 20
        assert novels[0].has_epub == True


class TestImportScriptIntegration:
    """Integration tests for the import script."""
    
    def test_real_directory_import(self, temp_novels_dir, db_service):
        """Test importing from a real directory structure."""
        from wn_dl.core.novel_discovery import NovelDiscoveryService
        
        # Run actual import on test directory
        stats = import_novels_from_directory(
            temp_novels_dir,
            db_service,
            dry_run=False
        )
        
        # Should find and import the test novels
        assert stats["scanned"] >= 2  # At least 2 novels should be found
        assert stats["imported"] >= 2
        assert stats["errors"] == 0
        
        # Verify novels were imported
        novels = db_service.list_novels()
        assert len(novels) >= 2
        
        # Check that novel with YAML metadata was imported correctly
        novel1 = next((n for n in novels if n.title == "Test Novel 1"), None)
        assert novel1 is not None
        assert novel1.author == "Test Author 1"
        assert novel1.source_url == "https://example.com/novel1"
        assert novel1.provider == "TestProvider"
        assert novel1.has_epub == True
        assert novel1.has_cover == True


if __name__ == "__main__":
    pytest.main([__file__])
