"""
Tests for MarkdownGenerator EPUB formatting improvements.

Tests the fixes for:
1. Redundant 'Chapter' word in titles
2. Proper page breaks between chapters
3. Novel description paragraph formatting
4. Configuration options for chapter title formatting
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import os

from wn_dl.core.markdown_generator import MarkdownGenerator
from wn_dl.core.models import NovelMetadata, ChapterData, NovelStatus


class TestMarkdownGenerator:
    """Test cases for MarkdownGenerator EPUB formatting improvements."""

    @pytest.fixture
    def sample_metadata(self):
        """Create sample novel metadata for testing."""
        return NovelMetadata(
            title="Test Novel",
            author="Test Author",
            description="This is a test description.\n\nIt has multiple paragraphs.\n\nAnd should be formatted properly.",
            source_url="https://example.com/novel",
            genres=["Fantasy", "Adventure"],
            status=NovelStatus.ONGOING,
            rating=8.5,
            rating_count=1000,
            provider="TestProvider"
        )

    @pytest.fixture
    def sample_chapters(self):
        """Create sample chapter data for testing."""
        return [
            ChapterData(
                title="The Beginning",
                content="This is the first chapter content.\n\nIt has multiple paragraphs.",
                url="https://example.com/chapter-1",
                chapter_number=1
            ),
            ChapterData(
                title="The Journey Continues",
                content="This is the second chapter content.\n\nWith more paragraphs.",
                url="https://example.com/chapter-2",
                chapter_number=2
            )
        ]

    @pytest.fixture
    def default_config(self):
        """Default configuration for testing."""
        return {
            "epub": {
                "chapter_level": 2,
                "include_toc": True,
                "chapter_title_format": "title_only",
                "chapter_number_format": "arabic"
            },
            "output": {
                "add_page_breaks": True
            }
        }

    def test_chapter_title_format_title_only(self, default_config, sample_chapters):
        """Test chapter title formatting with title_only format."""
        config = default_config.copy()
        config["epub"]["chapter_title_format"] = "title_only"
        
        generator = MarkdownGenerator(config)
        
        # Test the _format_chapter_title method
        formatted_title = generator._format_chapter_title("The Beginning", 1)
        assert formatted_title == "The Beginning"
        
        # Test in full chapter markdown
        chapter_markdown = generator._generate_chapter_markdown(sample_chapters[0], 1)
        assert "## The Beginning {" in chapter_markdown
        assert "Chapter 1:" not in chapter_markdown

    def test_chapter_title_format_number_title(self, default_config, sample_chapters):
        """Test chapter title formatting with number_title format."""
        config = default_config.copy()
        config["epub"]["chapter_title_format"] = "number_title"
        
        generator = MarkdownGenerator(config)
        
        formatted_title = generator._format_chapter_title("The Beginning", 1)
        assert formatted_title == "1. The Beginning"
        
        chapter_markdown = generator._generate_chapter_markdown(sample_chapters[0], 1)
        assert "## 1. The Beginning {" in chapter_markdown

    def test_chapter_title_format_chapter_number_title(self, default_config, sample_chapters):
        """Test chapter title formatting with chapter_number_title format."""
        config = default_config.copy()
        config["epub"]["chapter_title_format"] = "chapter_number_title"
        
        generator = MarkdownGenerator(config)
        
        formatted_title = generator._format_chapter_title("The Beginning", 1)
        assert formatted_title == "Chapter 1: The Beginning"
        
        chapter_markdown = generator._generate_chapter_markdown(sample_chapters[0], 1)
        assert "## Chapter 1: The Beginning {" in chapter_markdown

    def test_chapter_title_format_number_only(self, default_config, sample_chapters):
        """Test chapter title formatting with number_only format."""
        config = default_config.copy()
        config["epub"]["chapter_title_format"] = "number_only"
        
        generator = MarkdownGenerator(config)
        
        formatted_title = generator._format_chapter_title("The Beginning", 1)
        assert formatted_title == "1"
        
        chapter_markdown = generator._generate_chapter_markdown(sample_chapters[0], 1)
        assert "## 1 {" in chapter_markdown

    def test_chapter_div_wrapper_for_page_breaks(self, default_config, sample_chapters):
        """Test that chapters are wrapped in div with class for CSS page breaks."""
        generator = MarkdownGenerator(default_config)
        
        chapter_markdown = generator._generate_chapter_markdown(sample_chapters[0], 1)
        
        # Check for chapter div wrapper
        assert '<div class="chapter">' in chapter_markdown
        assert '</div>' in chapter_markdown
        
        # Check structure
        lines = chapter_markdown.split('\n')
        assert lines[0] == '<div class="chapter">'
        # Find the closing div (should be before the newpage)
        div_close_index = None
        for i, line in enumerate(lines):
            if line == '</div>':
                div_close_index = i
                break
        assert div_close_index is not None

    def test_description_paragraph_formatting(self, default_config, sample_metadata):
        """Test that novel descriptions are properly formatted with paragraphs."""
        generator = MarkdownGenerator(default_config)
        
        # Test the _format_description method directly
        formatted_desc = generator._format_description(sample_metadata.description)
        
        # Should split into separate paragraphs
        paragraphs = formatted_desc.split('\n\n')
        assert len(paragraphs) == 3
        assert paragraphs[0] == "This is a test description."
        assert paragraphs[1] == "It has multiple paragraphs."
        assert paragraphs[2] == "And should be formatted properly."

    def test_description_single_line_breaks(self, default_config):
        """Test description formatting with single line breaks."""
        generator = MarkdownGenerator(default_config)
        
        # Test description with single line breaks
        description = "Line one\nLine two\nLine three"
        formatted = generator._format_description(description)
        
        # Should join single line breaks with spaces
        assert formatted == "Line one Line two Line three"

    def test_description_mixed_line_breaks(self, default_config):
        """Test description formatting with mixed line break patterns."""
        generator = MarkdownGenerator(default_config)
        
        description = "Paragraph one.\n\nParagraph two with\nsingle line break.\n\nParagraph three."
        formatted = generator._format_description(description)
        
        paragraphs = formatted.split('\n\n')
        assert len(paragraphs) == 3
        assert paragraphs[0] == "Paragraph one."
        assert paragraphs[1] == "Paragraph two with single line break."
        assert paragraphs[2] == "Paragraph three."

    def test_table_of_contents_uses_consistent_formatting(self, default_config, sample_chapters):
        """Test that table of contents uses the same title formatting as chapters."""
        config = default_config.copy()
        config["epub"]["chapter_title_format"] = "number_title"
        
        generator = MarkdownGenerator(config)
        
        toc_markdown = generator._generate_toc(sample_chapters)
        
        # Should use the same formatting as chapters
        assert "[1. The Beginning]" in toc_markdown
        assert "[2. The Journey Continues]" in toc_markdown
        assert "Chapter 1:" not in toc_markdown

    def test_page_breaks_configuration(self, default_config, sample_chapters):
        """Test that page breaks can be configured."""
        # Test with page breaks enabled
        config_with_breaks = default_config.copy()
        config_with_breaks["output"]["add_page_breaks"] = True
        
        generator = MarkdownGenerator(config_with_breaks)
        chapter_markdown = generator._generate_chapter_markdown(sample_chapters[0], 1)
        assert "\\newpage" in chapter_markdown
        
        # Test with page breaks disabled
        config_no_breaks = default_config.copy()
        config_no_breaks["output"]["add_page_breaks"] = False
        
        generator = MarkdownGenerator(config_no_breaks)
        chapter_markdown = generator._generate_chapter_markdown(sample_chapters[0], 1)
        assert "\\newpage" not in chapter_markdown

    def test_full_markdown_generation(self, default_config, sample_metadata, sample_chapters):
        """Test complete markdown generation with all improvements."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            generator = MarkdownGenerator(default_config)
            
            # Generate markdown file
            result_path = generator.generate_markdown(
                sample_metadata, sample_chapters, output_dir
            )
            
            assert result_path is not None
            assert Path(result_path).exists()
            
            # Read and verify content
            with open(result_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check YAML frontmatter
            assert "title: Test Novel" in content
            assert "author: Test Author" in content
            
            # Check description formatting (should be in YAML and title page)
            assert "This is a test description." in content
            
            # Check chapter formatting (default is title_only)
            assert "## The Beginning {" in content
            assert "Chapter 1:" not in content
            
            # Check chapter div wrappers
            assert '<div class="chapter">' in content
            assert '</div>' in content
            
            # Check page breaks
            assert "\\newpage" in content

    def test_empty_description_handling(self, default_config):
        """Test handling of empty or None descriptions."""
        generator = MarkdownGenerator(default_config)
        
        # Test empty string
        assert generator._format_description("") == ""
        
        # Test None
        assert generator._format_description(None) == ""
        
        # Test whitespace only
        assert generator._format_description("   \n\n   ") == ""

    def test_invalid_chapter_title_format_fallback(self, default_config, sample_chapters):
        """Test fallback behavior for invalid chapter title format."""
        config = default_config.copy()
        config["epub"]["chapter_title_format"] = "invalid_format"
        
        generator = MarkdownGenerator(config)
        
        # Should fallback to title_only
        formatted_title = generator._format_chapter_title("Test Title", 1)
        assert formatted_title == "Test Title"
